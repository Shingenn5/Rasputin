"""Build model resource manifests and side-effect-free launch decisions.

This module is the narrow bridge between model metadata, the capability
profile, and :mod:`resource_broker`.  It never probes hardware, creates a
lease, starts a runtime, or mutates the model registry.  A missing capability
profile therefore remains explicitly ``unmeasured`` instead of being treated
as either a fit or a failure.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.models import resource_manifest as manifest_builder
from backend.warsat import resource_broker


def _number(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _device_ids(raw: Any, profile: dict[str, Any] | None) -> list[str]:
    value = raw
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",") if part.strip()]
    if not isinstance(value, (list, tuple)):
        return []
    available = {
        str(item.get("deviceId") or item.get("device_id"))
        for item in ((profile or {}).get("devices") or [])
        if isinstance(item, dict) and (item.get("deviceId") or item.get("device_id"))
    }
    result = []
    for item in value:
        candidate = _text(item)
        if not candidate:
            continue
        if candidate.isdigit():
            candidate = f"gpu:{candidate}"
        if not available or candidate in available:
            result.append(candidate)
    return list(dict.fromkeys(result))


def _manifest_source(model: dict[str, Any] | None, entry: dict[str, Any] | None = None) -> dict[str, Any]:
    source = dict(model or {})
    for key in (
        "model_id",
        "parameter_count_b",
        "vram_estimate_gb",
        "context_window",
        "recommended_protocol",
        "runtime_options",
        "quantization",
        "purpose",
        "capabilities",
        "license",
        "checksum",
        "source",
        "source_url",
    ):
        if entry and entry.get(key) not in (None, ""):
            source[key] = entry[key]
    if entry:
        source.update({
            key: entry[key]
            for key in ("modelId", "parameterCountB", "vramEstimateGb", "contextWindow", "recommendedProtocol", "runtimeOptions")
            if entry.get(key) not in (None, "")
        })
    return source


def build_manifest(model: dict[str, Any] | None = None, entry: dict[str, Any] | None = None, supplied: Any = None) -> dict[str, Any]:
    """Return a validated manifest, rebuilding malformed user metadata."""

    if isinstance(supplied, dict):
        candidate = deepcopy(supplied)
        if manifest_builder.validate_manifest(candidate)["valid"]:
            return candidate
    return manifest_builder.build_manifest(_manifest_source(model, entry))


def _reconcile_selected_protocol(manifest: dict[str, Any], protocol_id: str) -> dict[str, Any]:
    """Keep supplied catalog evidence aligned with the runtime being planned.

    A catalog manifest can be built before Warsat inspects the repository.  A
    vLLM-first catalog entry that turns out to contain only GGUF weights is
    then rerouted to llama.cpp, but its valid old manifest would otherwise
    still say that combined VRAM is not allowed.  Preserve the measured/model
    evidence while making the selected runtime's placement capability explicit.
    """

    selected = _text(protocol_id)
    if not selected:
        return manifest
    result = deepcopy(manifest)
    placement = dict(result.get("placement") or {})
    placement["combinedVramAllowed"] = selected == "llamaCppGgufServer"
    result["placement"] = placement
    backends = [dict(item) for item in (result.get("backends") or []) if isinstance(item, dict)]
    if not any(_text(item.get("protocolId") or item.get("protocol_id")) == selected for item in backends):
        backends.append({"protocolId": selected, "label": selected, "support": "selected"})
    result["backends"] = backends
    return result


def _estimated_vram_gb(manifest: dict[str, Any], model: dict[str, Any] | None, payload: dict[str, Any] | None) -> float | None:
    payload = payload or {}
    envelope = manifest.get("runtimeEnvelope") or {}
    weights = manifest.get("weights") or {}
    for value in (
        envelope.get("estimatedVramGb"),
        weights.get("estimatedVramGb"),
        payload.get("vramEstimateGb"),
        payload.get("vram_estimate_gb"),
        (model or {}).get("vramEstimateGb"),
        (model or {}).get("vram_estimate_gb"),
    ):
        parsed = _number(value)
        if parsed is not None:
            return parsed
    return None


def _capability_profile(profile: Any) -> dict[str, Any] | None:
    if not isinstance(profile, dict):
        return None
    nested = profile.get("capabilityProfile")
    if isinstance(nested, dict):
        return nested
    if isinstance(profile.get("devices"), list):
        return profile
    return None


def _unmeasured_decision(request: dict[str, Any]) -> dict[str, Any]:
    requested_vram = request.get("requestedVramMb")
    requested_ram = int(request.get("requestedRamMb") or 0)
    reasons = ["runtime_inventory_not_supplied"]
    if requested_vram is None and requested_ram <= 0:
        reasons.append("resource_envelope_missing")
    return {
        "schemaVersion": resource_broker.LEASE_SCHEMA_VERSION,
        "status": "unmeasured",
        "ownerId": request["ownerId"],
        "packId": request["packId"],
        "runtime": request["runtime"],
        "requested": {
            "vramMb": requested_vram,
            "ramMb": requested_ram,
            "deviceIds": request["deviceIds"],
        },
        "placements": [],
        "capacity": {"devices": [], "reservedVramMbByDevice": {}, "observedDeviceCount": 0},
        "reasons": reasons,
        "leasesConsidered": 0,
    }


def plan_admission(
    *,
    model: dict[str, Any] | None = None,
    entry: dict[str, Any] | None = None,
    supplied_manifest: Any = None,
    capability_profile: Any = None,
    runtime: str = "unknown",
    protocol_id: str = "",
    owner_id: str = "admin",
    pack_id: str = "model-pack",
    payload: dict[str, Any] | None = None,
    explicit_combined: bool = False,
    allow_cpu_fallback: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return ``(manifest, decision, normalized_request)`` for a preview."""

    payload = dict(payload or {})
    manifest = _reconcile_selected_protocol(
        build_manifest(model, entry, supplied_manifest),
        protocol_id,
    )
    estimate_gb = _estimated_vram_gb(manifest, model, payload)
    profile = _capability_profile(capability_profile)
    device_value = payload.get("deviceIds") or payload.get("device_ids") or payload.get("gpuDevice") or payload.get("gpu_device")
    if isinstance(device_value, str) and device_value.strip().lower() in {"all", "*"}:
        device_ids = [
            str(item.get("deviceId") or item.get("device_id"))
            for item in ((profile or {}).get("devices") or [])
            if isinstance(item, dict) and (item.get("deviceId") or item.get("device_id"))
        ]
    else:
        device_ids = _device_ids(device_value, profile)
    requested_vram_mb = round(estimate_gb * 1024) if estimate_gb is not None else None
    requested_ram_mb = payload.get("requestedRamMb") or payload.get("requested_ram_mb")
    try:
        requested_ram_mb = max(0, int(requested_ram_mb or 0))
    except (TypeError, ValueError):
        requested_ram_mb = 0
    request = {
        "ownerId": _text(owner_id) or "admin",
        "workspaceRef": _text(payload.get("workspaceRef") or payload.get("workspace_ref")),
        "taskId": _text(payload.get("taskId") or payload.get("task_id")),
        "packId": _text(pack_id) or "model-pack",
        "runtime": _text(runtime).lower() or "unknown",
        "requestedVramMb": requested_vram_mb,
        "requestedRamMb": requested_ram_mb,
        "deviceIds": device_ids,
        "allowCombined": bool(explicit_combined and (manifest.get("placement") or {}).get("combinedVramAllowed")),
        "allowCpuFallback": bool(allow_cpu_fallback),
    }
    decision = (
        resource_broker.evaluate_admission(profile, request)
        if profile is not None
        else _unmeasured_decision(request)
    )
    decision["protocolId"] = _text(protocol_id)
    decision["manifestSchemaVersion"] = manifest.get("schemaVersion")
    return manifest, decision, request


def warning_for(decision: dict[str, Any]) -> str | None:
    status = str((decision or {}).get("status") or "unmeasured")
    reasons = ", ".join(str(item) for item in ((decision or {}).get("reasons") or []))
    if status == "blocked":
        return f"Resource admission blocked this launch: {reasons or 'capacity or runtime policy rejected the request'}."
    if status == "queued":
        return f"Resource admission queued this launch until safe capacity is available: {reasons or 'headroom is unavailable'}."
    if status == "degraded":
        return f"Resource admission selected a degraded fallback: {reasons or 'accelerator capacity was unavailable'}."
    if status == "unmeasured":
        return "Resource admission is unmeasured until a current runtime capability profile is supplied."
    return None


__all__ = ["build_manifest", "plan_admission", "warning_for"]
