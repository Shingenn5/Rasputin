"""Owner-scoped, side-effect-free Assistant Model Request orchestration."""

from __future__ import annotations

import copy
import time
from typing import Any

from backend.assistant import contracts
from backend.core import runtime_store as store
from backend.core.response import AppError
from backend.models import catalog
from backend.models import compatibility
from backend.models import registry
from backend.warsat import advisor
from backend.warsat import benchmarks
from backend.warsat import hardware_probe


STORE_KEY_PREFIX = "assistant_model_requests:"
LOCAL_HEALTH_STATUSES = {"reachable", "healthy", "ready", "running"}


def _owner(owner_id: Any) -> str:
    value = str(owner_id or "").strip()
    if not value:
        raise ValueError("owner is required")
    return value[:120]


def _key(owner_id: str) -> str:
    return f"{STORE_KEY_PREFIX}{_owner(owner_id)}"


def _read(owner_id: str) -> list[dict[str, Any]]:
    records = store.get_kv(_key(owner_id), [])
    return copy.deepcopy(records) if isinstance(records, list) else []


def _write(owner_id: str, records: list[dict[str, Any]]) -> None:
    store.set_kv(_key(owner_id), copy.deepcopy(records))


def _public(record: dict[str, Any]) -> dict[str, Any]:
    """Return a detached snapshot so callers cannot mutate persisted state."""

    return copy.deepcopy(record)


def _find(owner_id: str, request_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = _read(owner_id)
    for record in records:
        if record.get("request_id") == request_id:
            return records, record
    raise AppError("assistant_model_request_missing", "Assistant model request was not found.", 404)


def _local_deployable(item: dict[str, Any]) -> bool:
    protocol = str(item.get("recommendedProtocol") or item.get("recommended_protocol") or "")
    if not protocol:
        options = item.get("runtimeOptions") or item.get("runtime_options") or []
        if isinstance(options, list) and options and isinstance(options[0], dict):
            protocol = str(options[0].get("protocolId") or options[0].get("protocol_id") or "")
    return (
        bool(item.get("deployable"))
        and not bool(item.get("apiOnly") or item.get("api_only"))
        and protocol in advisor.SUPPORTED_PARSERS
    )


def _capability_evidence(item: dict[str, Any], requested: list[str]) -> dict[str, Any]:
    advertised = {str(value).strip().lower() for value in item.get("capabilities") or []}
    matches = {}
    for capability in requested:
        if capability == "tools":
            matches[capability] = {
                "supported": True,
                "status": "unproven",
                "source": "catalog_hint",
                "note": "Catalog tool support is a hint only; verify the exact registered model before use.",
            }
        else:
            matches[capability] = {
                "supported": capability in advertised,
                "status": "catalog",
                "source": "catalog",
            }
    return {
        "requested": list(requested),
        "matches": matches,
        "allMatch": all(item.get("supported") for item in matches.values()),
    }


def _throughput_evidence(advice: dict[str, Any]) -> dict[str, Any]:
    benchmark = advice.get("benchmarkEvidence") or advice.get("benchmark") or {}
    metrics = benchmark.get("metrics") or {}
    evidence = {
        "status": "measured" if benchmark.get("exact") else "estimated",
        "source": "runtime_benchmark" if benchmark.get("exact") else "catalog_estimate",
        "decodeTokensPerSecond": copy.deepcopy(metrics.get("decodeTokensPerSecond")),
        "ttftMs": copy.deepcopy(metrics.get("ttftMs")),
    }
    estimated = (advice.get("evidence") or {}).get("estimated") or {}
    for key in ("decodeTokensPerSecond", "ttftMs"):
        if evidence[key] is None and estimated.get(key) is not None:
            evidence[key] = copy.deepcopy(estimated[key])
    return evidence


def _candidate(item: dict[str, Any], advice: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    snapshot = copy.deepcopy(item)
    protocol_id = str(advice.get("recommendation", {}).get("protocolId") or item.get("recommendedProtocol") or "")
    capability_evidence = _capability_evidence(snapshot, request["required_capabilities"])
    plan_seed = copy.deepcopy(advice.get("planSeed") or {})
    plan_seed.update({
        "mission": request["mission"],
        "role": request["role"],
        "requiredCapabilities": list(request["required_capabilities"]),
        "profile": request["profile"],
    })
    return {
        "candidate_id": store.new_id("assistant_candidate"),
        "catalog_item": snapshot,
        "protocol_id": protocol_id,
        "role": request["role"],
        "plan_seed": plan_seed,
        "capability_evidence": capability_evidence,
        "blockers": list(advice.get("blockers") or []),
        "warnings": list(advice.get("warnings") or []),
        "placement_evidence": copy.deepcopy(advice.get("placement") or {}),
        "resource_evidence": copy.deepcopy(snapshot.get("resourceManifest") or {}),
        "benchmark_evidence": copy.deepcopy(advice.get("benchmarkEvidence") or advice.get("benchmark") or {}),
        "throughput_evidence": _throughput_evidence(advice),
        "advisor_evidence": {
            "profileScore": advice.get("profileScore"),
            "status": advice.get("status"),
            "confidence": (advice.get("evidence") or {}).get("confidence"),
            "assumptions": list(advice.get("assumptions") or []),
        },
    }


def create_request(
    owner_id: str,
    mission: Any,
    required_capabilities: Any,
    profile: Any = None,
    context_window: Any = None,
    role: Any = None,
) -> dict[str, Any]:
    owner = _owner(owner_id)
    normalized = contracts.normalize_model_request(mission, required_capabilities, profile, context_window, role)
    hardware = hardware_probe()
    catalog_payload = catalog.catalog(refresh=False, hardware=hardware)
    items = [
        copy.deepcopy(item)
        for item in (catalog_payload.get("items") or [])
        if isinstance(item, dict)
        and _local_deployable(item)
        and set(normalized["required_capabilities"]).issubset({str(cap).strip().lower() for cap in item.get("capabilities") or []})
    ]
    certificates = benchmarks.list_certificates(owner=owner)
    advice = advisor.rank_recommendations(
        items,
        hardware,
        mission=normalized["mission"],
        profile=normalized["profile"],
        protocol_id="",
        context_window=normalized["context_window"],
        benchmark_certificates=certificates,
    )
    by_model = {}
    for item in items:
        by_model.setdefault(str(item.get("modelId") or item.get("id") or ""), []).append(item)
    candidates = []
    for item_advice in advice:
        model_ref = str((item_advice.get("recommendation") or {}).get("modelRef") or "")
        originals = by_model.get(model_ref) or []
        original = originals.pop(0) if originals else None
        if original is not None:
            candidates.append(_candidate(original, item_advice, normalized))

    record = {
        "request_id": store.new_id("assistant_model_request"),
        "owner_id": owner,
        "mission": normalized["mission"],
        "required_capabilities": list(normalized["required_capabilities"]),
        "profile": normalized["profile"],
        "context_window": normalized["context_window"],
        "role": normalized["role"],
        "status": "recommendation_ready" if any(not candidate.get("blockers") for candidate in candidates) else "blocked",
        "blockers": [] if any(not candidate.get("blockers") for candidate in candidates) else ["no_compatible_local_candidate"],
        "created_at": time.time(),
        "hardware_evidence": copy.deepcopy(hardware),
        "catalog_source": copy.deepcopy(catalog_payload.get("source") or {}),
        "recommendations": candidates,
        "selected_candidate_id": None,
        "verification": None,
    }
    records = _read(owner)
    records.insert(0, record)
    _write(owner, records[:100])
    return _public(record)


def list_requests(owner_id: str, limit: int = 50) -> list[dict[str, Any]]:
    records = _read(_owner(owner_id))
    return [_public(item) for item in records[: max(1, min(int(limit), 100))]]


def get_request(owner_id: str, request_id: str) -> dict[str, Any]:
    _records, record = _find(_owner(owner_id), request_id)
    return _public(record)


def select_candidate(owner_id: str, request_id: str, candidate_id: str) -> dict[str, Any]:
    owner = _owner(owner_id)
    records, record = _find(owner, request_id)
    candidate = next((item for item in record.get("recommendations") or [] if item.get("candidate_id") == candidate_id), None)
    if candidate is None:
        raise AppError("assistant_model_candidate_invalid", "candidateId must refer to a recommendation from this request.", 409)
    if candidate.get("blockers") or not (candidate.get("capability_evidence") or {}).get("allMatch", False):
        raise AppError("assistant_model_candidate_blocked", "The selected candidate does not satisfy this assistant request.", 409)
    record["selected_candidate_id"] = str(candidate_id)
    record["status"] = "candidate_selected"
    record["selected_at"] = time.time()
    record["verification"] = None
    _write(owner, records)
    return _public(record)


def selected_plan_payload(owner_id: str, request_id: str) -> dict[str, Any]:
    """Return the immutable WarSat input pinned by an owner-selected candidate."""

    _records, record = _find(_owner(owner_id), request_id)
    selected_id = record.get("selected_candidate_id")
    candidate = next(
        (item for item in record.get("recommendations") or [] if item.get("candidate_id") == selected_id),
        None,
    )
    if candidate is None:
        raise AppError(
            "assistant_model_not_selected",
            "Select an Assistant model recommendation before creating its WarSat plan.",
            409,
        )
    snapshot = copy.deepcopy(candidate.get("catalog_item") or {})
    seed = copy.deepcopy(candidate.get("plan_seed") or {})
    return {
        "protocolId": candidate.get("protocol_id") or seed.get("protocolId"),
        "modelRef": snapshot.get("warsatModelRef") or snapshot.get("modelId") or snapshot.get("id"),
        "modelPath": snapshot.get("modelPath"),
        "strengthProfile": record.get("profile") or "fast",
        "role": candidate.get("role") or record.get("role"),
        "contextWindow": record.get("context_window"),
        "maxModelLen": record.get("context_window"),
        "vramEstimateGb": snapshot.get("vramEstimateGb"),
        "resourceManifest": copy.deepcopy(snapshot.get("resourceManifest") or {}),
        "toolCallParser": seed.get("toolCallParser") or snapshot.get("toolCallParserHint"),
    }


def _protocol_id(model: dict[str, Any]) -> str:
    profile = model.get("deployment_profile") or {}
    explicit = model.get("protocol_id") or model.get("protocolId") or profile.get("protocolId")
    if explicit:
        return str(explicit)
    return {
        "warsat-vllm": "vllmCudaOpenai",
        "warsat-llama.cpp": "llamaCppGgufServer",
        "warsat-ollama": "ollamaOpenaiServer",
    }.get(str(model.get("runtime") or ""), "")


def _unqualified(reasons: list[str], model_key: str, candidate: dict[str, Any], model: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "unqualified",
        "qualified": False,
        "model_key": model_key,
        "candidate_id": candidate.get("candidate_id"),
        "reasons": reasons,
        "selected_candidate": copy.deepcopy(candidate),
        "registered_model": {"key": model.get("key"), "model": model.get("model")} if model else None,
    }


def verify(owner_id: str, request_id: str, model_key: str) -> dict[str, Any]:
    owner = _owner(owner_id)
    records, record = _find(owner, request_id)
    selected_id = record.get("selected_candidate_id")
    candidate = next((item for item in record.get("recommendations") or [] if item.get("candidate_id") == selected_id), None)
    if candidate is None:
        raise AppError("assistant_model_not_selected", "Select a recommendation before verifying a registered model.", 409)

    requested = record.get("required_capabilities") or []
    snapshot = candidate.get("catalog_item") or {}
    model = registry.get_model(str(model_key or ""))
    reasons = []
    if not model:
        reasons.append("registered_model_missing")
    else:
        registered_id = str(model.get("model") or model.get("model_id") or model.get("modelId") or "")
        selected_id_value = str(snapshot.get("modelId") or snapshot.get("model_id") or "")
        if not selected_id_value or registered_id != selected_id_value:
            reasons.append("registered_model_mismatch")
        snapshot_protocol = str(candidate.get("protocol_id") or "")
        registered_protocol = _protocol_id(model)
        if snapshot_protocol and registered_protocol and snapshot_protocol != registered_protocol:
            reasons.append("registered_protocol_mismatch")
        health_status = str(model.get("runtime_status") or model.get("runtimeStatus") or (model.get("last_health") or {}).get("status") or "").lower()
        if health_status not in LOCAL_HEALTH_STATUSES:
            reasons.append("registered_model_unreachable")
        profile = model.get("compatibility") or {}
        if profile.get("status") != "certified" or not compatibility.certification_is_current(model, profile):
            reasons.append("compatibility_certification_stale_or_missing")
        if "tools" in requested and profile.get("toolSupport") != "agentic":
            reasons.append("tool_support_not_certified")
        if "code" in requested and "code" not in (profile.get("supportedModes") or []):
            reasons.append("code_mode_not_certified")

    if reasons:
        result = _unqualified(reasons, str(model_key or ""), candidate, model)
        record["status"] = "verified_unqualified"
    else:
        result = {
            "status": "selected",
            "qualified": True,
            "model_key": str(model_key),
            "candidate_id": candidate.get("candidate_id"),
            "selected_candidate": copy.deepcopy(candidate),
            "registered_model": {
                "key": model.get("key"),
                "model": model.get("model"),
                "runtimeStatus": model.get("runtime_status") or model.get("runtimeStatus") or (model.get("last_health") or {}).get("status"),
                "compatibility": copy.deepcopy(model.get("compatibility") or {}),
            },
        }
        record["status"] = "verified_selected"
    record["verification"] = copy.deepcopy(result)
    record["verified_at"] = time.time()
    _write(owner, records)
    return result
