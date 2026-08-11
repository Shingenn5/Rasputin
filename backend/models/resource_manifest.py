"""Portable model resource metadata used by catalog and placement decisions.

The manifest deliberately separates declared model facts from measured runtime
evidence.  A catalog estimate can help sort candidates, but it is not a launch
certificate until a runtime benchmark records the actual memory envelope.
"""

from __future__ import annotations

import re
from copy import deepcopy


SCHEMA_VERSION = "rasputin.model-resource.v1"

_QUANTIZATION_PROFILES = (
    ("q2", "Q2", 2.5),
    ("iq2", "IQ2", 2.5),
    ("q3", "Q3", 3.5),
    ("iq3", "IQ3", 3.5),
    ("q4", "Q4", 4.5),
    ("iq4", "IQ4", 4.5),
    ("int4", "INT4", 4.5),
    ("awq", "AWQ", 4.5),
    ("gptq", "GPTQ", 4.5),
    ("bnb", "bitsandbytes", 4.5),
    ("bitsandbytes", "bitsandbytes", 4.5),
    ("q5", "Q5", 5.5),
    ("q6", "Q6", 6.5),
    ("q8", "Q8", 8.5),
    ("int8", "INT8", 8.5),
    ("fp8", "FP8", 8.5),
    ("fp16", "FP16", 16.0),
    ("float16", "FP16", 16.0),
    ("bf16", "BF16", 16.0),
    ("bfloat16", "BF16", 16.0),
)


def _number(value, default=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


def _rounded(value, digits=2):
    number = _number(value)
    if number is None:
        return None
    return round(number, digits)


def quantization_profile(quantization="", model_id=""):
    """Return a canonical quantization name and bits-per-weight estimate."""

    blob = " ".join(str(value or "") for value in (quantization, model_id)).lower()
    if "gguf" in blob and not any(token in blob for token, _label, _bits in _QUANTIZATION_PROFILES):
        return {"name": "GGUF-unspecified", "bitsPerWeight": None, "source": "format-only"}
    for token, label, bits in _QUANTIZATION_PROFILES:
        if token in blob:
            return {"name": label, "bitsPerWeight": bits, "source": "declared-or-name"}
    return {"name": "unspecified", "bitsPerWeight": None, "source": "not-declared"}


def _parameter_count(model):
    model = model or {}
    value = _number(model.get("parameterCountB") or model.get("parameter_count_b"))
    if value:
        return value
    blob = " ".join(str(model.get(key) or "") for key in ("modelId", "id", "name"))
    match = re.search(r"(\d+(?:\.\d+)?)\s*b(?:\b|[-_])", blob.lower())
    return _number(match.group(1)) if match else None


def _runtime_options(model):
    options = model.get("runtimeOptions") or model.get("runtime_options") or []
    if isinstance(options, str):
        options = [{"protocolId": options}]
    normalized = []
    for option in options:
        if isinstance(option, str):
            option = {"protocolId": option}
        if not isinstance(option, dict):
            continue
        protocol_id = str(option.get("protocolId") or option.get("id") or "").strip()
        if protocol_id:
            normalized.append({
                "protocolId": protocol_id,
                "label": str(option.get("label") or protocol_id),
                "support": str(option.get("support") or "declared"),
            })
    recommended = str(model.get("recommendedProtocol") or model.get("recommended_protocol") or "").strip()
    if recommended and not any(item["protocolId"] == recommended for item in normalized):
        normalized.insert(0, {"protocolId": recommended, "label": recommended, "support": "declared"})
    return normalized


def _measured_kv_cache(model, context_window):
    raw = model.get("kvCache") or model.get("kv_cache") or {}
    if not isinstance(raw, dict):
        raw = {}
    status = str(raw.get("status") or ("measured" if raw.get("measuredAt") else "unmeasured")).lower()
    if status not in {"measured", "estimated", "unmeasured"}:
        status = "unmeasured"
    return {
        "status": status,
        "contextWindow": int(_number(raw.get("contextWindow") or context_window, 0) or 0) or None,
        "perTokenMb": _rounded(raw.get("perTokenMb") or raw.get("per_token_mb"), 4),
        "residentVramGb": _rounded(raw.get("residentVramGb") or raw.get("resident_vram_gb")),
        "measuredAt": str(raw.get("measuredAt") or raw.get("measured_at") or ""),
        "source": str(raw.get("source") or ("runtime-benchmark" if status == "measured" else "not-measured")),
    }


def build_manifest(model=None):
    """Build a JSON-safe resource manifest from a catalog/registry item."""

    model = dict(model or {})
    model_id = str(model.get("modelId") or model.get("id") or model.get("model") or "")
    quantization = quantization_profile(model.get("quantization"), model_id)
    params = _parameter_count(model)
    bits = quantization.get("bitsPerWeight")
    weight_vram = round(params * bits / 8.0 * 1.05, 2) if params and bits else None
    context_window = int(_number(model.get("contextWindow") or model.get("context_window"), 0) or 0) or None
    total_vram = _rounded(model.get("vramEstimateGb") or model.get("vram_estimate_gb"))
    runtime_options = _runtime_options(model)
    protocol_ids = {item["protocolId"] for item in runtime_options}
    recommended_protocol = str(model.get("recommendedProtocol") or model.get("recommended_protocol") or "")
    combined_allowed = "llamaCppGgufServer" in protocol_ids or recommended_protocol == "llamaCppGgufServer"
    checksum = str(model.get("checksum") or model.get("sha") or "").strip()
    license_id = str(model.get("license") or model.get("licenseId") or model.get("license_id") or "").strip()

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "identity": {
            "modelId": model_id,
            "checksum": checksum,
            "license": license_id,
            "source": str(model.get("source") or "unknown"),
            "sourceUrl": str(model.get("sourceUrl") or model.get("source_url") or ""),
        },
        "weights": {
            "parameterCountB": _rounded(params),
            "quantization": quantization,
            "estimatedVramGb": weight_vram,
            "estimateSource": "parameter-and-quantization" if weight_vram is not None else "not-enough-metadata",
        },
        "runtimeEnvelope": {
            "estimatedVramGb": total_vram,
            "estimateSource": "catalog-heuristic" if total_vram is not None else "unmeasured",
            "confidence": "estimated" if total_vram is not None else "unknown",
        },
        "kvCache": _measured_kv_cache(model, context_window),
        "backends": runtime_options,
        "placement": {
            "default": "largest_fitting_single_gpu_first",
            "combinedVramAllowed": combined_allowed,
            "requiresRuntimeCertificate": True,
        },
        "roleFit": {
            "purpose": str(model.get("purpose") or "chat"),
            "capabilities": sorted({str(item) for item in (model.get("capabilities") or [])}),
            "recommendedProfile": str(model.get("recommendedProfile") or model.get("recommended_profile") or "balanced"),
        },
        "fit": {
            "score": None,
            "label": "unmeasured",
            "availableVramGb": None,
            "headroomGb": None,
            "basis": "not-evaluated",
            "blockedReasons": [],
        },
    }
    return manifest


def attach_fit(manifest, *, score, label, available_vram_gb=None, headroom_gb=None, basis="catalog-estimate", blocked_reasons=None):
    """Return a copy with dynamic hardware-fit evidence attached."""

    result = deepcopy(manifest or build_manifest())
    result.setdefault("fit", {})
    result["fit"].update({
        "score": int(score) if score is not None else None,
        "label": str(label or "unmeasured"),
        "availableVramGb": _rounded(available_vram_gb),
        "headroomGb": _rounded(headroom_gb),
        "basis": str(basis or "catalog-estimate"),
        "blockedReasons": [str(item) for item in (blocked_reasons or [])],
    })
    return result


def validate_manifest(manifest):
    """Validate the stable fields before a manifest is persisted or exposed."""

    errors = []
    if not isinstance(manifest, dict):
        return {"valid": False, "errors": ["manifest must be an object"]}
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion must be rasputin.model-resource.v1")
    for section in ("identity", "weights", "runtimeEnvelope", "kvCache", "backends", "placement", "roleFit", "fit"):
        if section not in manifest:
            errors.append(f"missing section: {section}")
    weights = manifest.get("weights") or {}
    bits = (weights.get("quantization") or {}).get("bitsPerWeight")
    if bits is not None and _number(bits) is None:
        errors.append("weights.quantization.bitsPerWeight must be numeric or null")
    for key in ("estimatedVramGb",):
        if weights.get(key) is not None and _number(weights.get(key)) is None:
            errors.append(f"weights.{key} must be numeric or null")
    if not isinstance(manifest.get("backends"), list):
        errors.append("backends must be a list")
    return {"valid": not errors, "errors": errors}
