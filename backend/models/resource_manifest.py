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


_RUNTIME_OVERHEAD_GB = {
    "vllmcudaopenai": 1.50,
    "llamacppggufserver": 0.75,
    "ollamaopenaiserver": 1.00,
}


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


def _first_number(model, *keys):
    for key in keys:
        value = _number(model.get(key))
        if value is not None:
            return value
    return None


def _context_and_concurrency(model):
    context = _first_number(model, "contextWindow", "context_window", "maxModelLen", "max_model_len")
    concurrency = _first_number(model, "concurrency", "maxNumSeqs", "max_num_seqs")
    return (int(context) if context else None, int(concurrency) if concurrency else 1)


def _kv_cache_per_token_mb(model):
    raw = model.get("kvCache") or model.get("kv_cache") or {}
    if not isinstance(raw, dict):
        raw = {}
    explicit = _first_number(raw, "perTokenMb", "per_token_mb", "perTokenMB", "per_token_mib")
    if explicit is not None:
        return explicit, "declared"
    explicit = _first_number(model, "kvCachePerTokenMb", "kv_cache_per_token_mb")
    if explicit is not None:
        return explicit, "declared"

    # KV bytes/token = layers * 2 (K+V) * KV heads * head dimension * dtype.
    # Only emit this when architecture metadata is complete enough to avoid
    # pretending that parameter count alone determines KV memory.
    layers = _first_number(model, "numLayers", "num_layers", "nLayer", "n_layer")
    kv_heads = _first_number(model, "numKvHeads", "num_kv_heads", "nKvHeads", "n_kv_heads")
    head_dim = _first_number(model, "headDim", "head_dim", "nHeadKv", "n_head_kv")
    if layers and kv_heads and head_dim:
        dtype = str(model.get("kvCacheDtype") or model.get("kv_cache_dtype") or "fp16").lower()
        dtype_bytes = 1 if any(token in dtype for token in ("int8", "fp8", "q8")) else 2
        return layers * 2 * kv_heads * head_dim * dtype_bytes / 1_000_000, "architecture"
    return None, "unknown"


def estimate_vram_demand(model=None, *, parameter_count_b=None, quantization="", model_id=""):
    """Estimate total deployment demand with an inspectable breakdown.

    vramEstimateGb is total demand: weights + allocator margin + runtime
    overhead + KV cache when context metadata is available. Unknown architecture
    metadata lowers confidence and widens the range; measured evidence remains
    authoritative.
    """
    model = dict(model or {})
    if parameter_count_b is None:
        parameter_count_b = _parameter_count(model)
    if not parameter_count_b:
        return None
    if not quantization:
        quantization = model.get("quantization") or model.get("quantization_profile") or ""
    if not model_id:
        model_id = model.get("modelId") or model.get("id") or model.get("name") or ""
    q = quantization_profile(quantization, model_id)
    bits = _number(q.get("bitsPerWeight"))
    if bits is None and q.get("name") == "GGUF-unspecified":
        # WarSat selects a Q4-family GGUF artifact when a repository exposes
        # only the GGUF format; keep that assumption explicit and low confidence.
        bits = 4.5
        q = {**q, "name": "GGUF-default-Q4", "source": "format-default"}
    elif bits is None:
        # Transformer weights without a quantization tag are normally loaded
        # in FP16/BF16. Keep this as an explicit low-confidence assumption.
        bits = 16.0
        q = {**q, "name": "FP16-default", "source": "missing-quantization-default"}
    if bits is None:
        return {
            "totalGb": None, "weightsGb": None, "weightOverheadGb": None,
            "runtimeOverheadGb": None, "kvCacheGb": None, "rangeGb": None,
            "confidence": "unknown", "source": "missing-quantization",
            "assumptions": ["Quantization and parameter metadata are required."],
            "contextWindow": None, "concurrency": None,
        }
    raw_weights = float(parameter_count_b) * bits / 8.0
    weight_overhead = raw_weights * 0.08
    runtime_options = _runtime_options(model)
    protocol = str(model.get("recommendedProtocol") or model.get("recommended_protocol") or "").lower()
    if not protocol and runtime_options:
        protocol = str(runtime_options[0].get("protocolId") or "").lower()
    runtime_overhead = _RUNTIME_OVERHEAD_GB.get(protocol, 1.0)
    context, concurrency = _context_and_concurrency(model)
    per_token_mb, kv_source = _kv_cache_per_token_mb(model)
    kv_gb = None
    if context and per_token_mb is not None:
        kv_gb = per_token_mb * context * max(1, concurrency) / 1024.0
    base = raw_weights + weight_overhead + runtime_overhead
    total = base + (kv_gb or 0)
    if kv_source == "declared" and context:
        confidence, source, spread = "medium", "parameter-quantization-context", 0.12
    elif kv_source == "architecture" and context:
        confidence, source, spread = "medium", "parameter-quantization-architecture", 0.18
    else:
        confidence, source, spread = "low", "parameter-quantization-runtime-floor", 0.25
    return {
        "totalGb": round(total, 2),
        "weightsGb": round(raw_weights, 2),
        "weightOverheadGb": round(weight_overhead, 2),
        "runtimeOverheadGb": round(runtime_overhead, 2),
        "kvCacheGb": round(kv_gb, 2) if kv_gb is not None else None,
        "rangeGb": {"min": round(total * (1 - spread), 2), "max": round(total * (1 + spread), 2)},
        "confidence": confidence,
        "source": source,
        "assumptions": [
            f"Weights use {bits:g} bits/weight for {q.get('name') or 'declared quantization'}.",
            "Weight demand includes an 8% allocator/metadata margin.",
            f"Runtime overhead assumes {runtime_overhead:g} GB for {protocol or 'an unspecified runtime'}.",
            "KV cache is omitted when context or architecture metadata is unavailable." if kv_gb is None else
            f"KV cache uses {per_token_mb:.4g} MB/token, context {context}, concurrency {concurrency}.",
        ],
        "contextWindow": context,
        "concurrency": concurrency if context else None,
    }


def estimate_system_ram_demand(model=None, *, vram_estimate=None):
    """Estimate host RAM needed to stage and run a managed local model.

    GPU fit alone is insufficient: runtimes still map or stage model weights in
    host memory and keep a host-side process envelope.  This estimate excludes
    the operating-system safety reserve, which the live capacity check applies
    separately.  An explicit catalog/runtime estimate remains authoritative.
    """

    model = dict(model or {})
    explicit = _first_number(
        model,
        "systemRamEstimateGb",
        "system_ram_estimate_gb",
        "hostRamEstimateGb",
        "host_ram_estimate_gb",
    )
    if explicit is not None:
        return {
            "totalGb": round(explicit, 2),
            "rangeGb": {"min": round(explicit, 2), "max": round(explicit, 2)},
            "confidence": "declared",
            "source": "catalog-explicit-system-ram",
            "assumptions": ["The catalog or runtime supplied an explicit host RAM estimate."],
        }
    estimate = vram_estimate if isinstance(vram_estimate, dict) else estimate_vram_demand(model)
    weights_gb = _number((estimate or {}).get("weightsGb"))
    weight_overhead_gb = _number((estimate or {}).get("weightOverheadGb"), 0.0) or 0.0
    runtime_overhead_gb = _number((estimate or {}).get("runtimeOverheadGb"), 1.0) or 1.0
    if weights_gb is None:
        return {
            "totalGb": None,
            "rangeGb": None,
            "confidence": "unknown",
            "source": "missing-weight-envelope",
            "assumptions": ["Parameter and quantization metadata are required for a host RAM estimate."],
        }
    total = max(2.0, weights_gb + weight_overhead_gb + runtime_overhead_gb)
    spread = 0.20
    return {
        "totalGb": round(total, 2),
        "rangeGb": {"min": round(total * (1 - spread), 2), "max": round(total * (1 + spread), 2)},
        "confidence": "estimated",
        "source": "weight-staging-plus-runtime",
        "assumptions": [
            "Host RAM includes one model-weight staging or memory-map envelope.",
            f"Host runtime overhead is estimated at {runtime_overhead_gb:g} GB.",
            "The operating-system safety reserve is applied to live available RAM, not added to model demand.",
        ],
    }


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
    kv_cache = _measured_kv_cache(model, context_window)
    estimate = estimate_vram_demand(
        model,
        parameter_count_b=params,
        quantization=model.get("quantization"),
        model_id=model_id,
    )
    system_ram_estimate = estimate_system_ram_demand(model, vram_estimate=estimate)
    measured_kv_vram = kv_cache.get("residentVramGb") if kv_cache.get("status") == "measured" else None
    measured_total_vram = _rounded(
        model.get("measuredRuntimeVramGb")
        or model.get("measured_runtime_vram_gb")
        or model.get("measuredTotalVramGb")
        or model.get("measured_total_vram_gb")
    )
    explicit_vram = _rounded(model.get("vramEstimateGb") or model.get("vram_estimate_gb"))
    estimate_total = (estimate or {}).get("totalGb") if estimate else None
    estimate_kv = (estimate or {}).get("kvCacheGb") if estimate else None
    if measured_total_vram is not None:
        total_vram = measured_total_vram
        envelope_source = "measured-runtime-total"
        envelope_confidence = "measured"
        envelope_range = {"min": measured_total_vram, "max": measured_total_vram}
    elif explicit_vram is not None:
        # vramEstimateGb is an explicit total-envelope contract supplied by a
        # catalog or caller. Catalog normalization now computes this with the
        # same estimator, while older API clients still rely on their declared
        # value being honored instead of silently reinterpreted from a model
        # name. Keep the independent calculation as explanatory evidence.
        total_vram = explicit_vram
        estimate_matches = estimate_total is not None and abs(explicit_vram - estimate_total) < 0.01
        envelope_source = (estimate or {}).get("source") if estimate_matches else "catalog-explicit"
        envelope_confidence = (estimate or {}).get("confidence") if estimate_matches else "estimated"
        envelope_range = (estimate or {}).get("rangeGb") if estimate_matches else None
    elif measured_kv_vram is not None:
        # residentVramGb under kvCache is a component measurement, not the
        # whole process footprint. Replace only the estimated KV component.
        baseline = estimate_total if estimate_total is not None else explicit_vram
        total_vram = _rounded((baseline or 0) - (estimate_kv or 0) + measured_kv_vram)
        envelope_source = "measured-kv-cache-plus-estimated-runtime"
        envelope_confidence = "medium"
        estimate_range = (estimate or {}).get("rangeGb") if estimate else None
        if estimate_range:
            delta = measured_kv_vram - (estimate_kv or 0)
            envelope_range = {
                "min": round(float(estimate_range["min"]) + delta, 2),
                "max": round(float(estimate_range["max"]) + delta, 2),
            }
        else:
            envelope_range = None
    else:
        total_vram = _rounded(estimate_total)
        envelope_source = (estimate or {}).get("source") if estimate else "unmeasured"
        envelope_confidence = (estimate or {}).get("confidence") if estimate else "unknown"
        envelope_range = (estimate or {}).get("rangeGb") if estimate else None
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
            "estimatedSystemRamGb": system_ram_estimate.get("totalGb"),
            "estimateSource": envelope_source,
            "systemRamEstimateSource": system_ram_estimate.get("source"),
            "confidence": envelope_confidence,
            "systemRamConfidence": system_ram_estimate.get("confidence"),
            "rangeGb": envelope_range,
            "systemRamRangeGb": system_ram_estimate.get("rangeGb"),
            "breakdown": {
                "weightsGb": (estimate or {}).get("weightsGb") if estimate else weight_vram,
                "weightOverheadGb": (estimate or {}).get("weightOverheadGb") if estimate else None,
                "runtimeOverheadGb": (estimate or {}).get("runtimeOverheadGb") if estimate else None,
                "kvCacheGb": measured_kv_vram if measured_kv_vram is not None else
                             ((estimate or {}).get("kvCacheGb") if estimate else None),
            },
            "assumptions": list((estimate or {}).get("assumptions") or []) + list(system_ram_estimate.get("assumptions") or []) + (
                [f"The declared total VRAM estimate ({explicit_vram:g} GB) overrides the independent {estimate_total:g} GB heuristic for compatibility."]
                if explicit_vram is not None and estimate_total is not None and abs(explicit_vram - estimate_total) >= 0.01 else
                ["Measured KV-cache resident VRAM replaces only the estimated KV component."]
                if measured_kv_vram is not None and explicit_vram is None else
                ["Measured total runtime VRAM is authoritative."]
                if measured_total_vram is not None else []
            ),
        },
        "kvCache": kv_cache,
        "backends": runtime_options,
        "placement": {
            "default": "all_compatible_gpus_first",
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
            "availableSystemRamGb": None,
            "systemRamHeadroomGb": None,
            "basis": "not-evaluated",
            "blockedReasons": [],
        },
    }
    return manifest


def attach_fit(
    manifest,
    *,
    score,
    label,
    available_vram_gb=None,
    headroom_gb=None,
    available_system_ram_gb=None,
    system_ram_headroom_gb=None,
    basis="catalog-estimate",
    blocked_reasons=None,
):
    """Return a copy with dynamic hardware-fit evidence attached."""

    result = deepcopy(manifest or build_manifest())
    result.setdefault("fit", {})
    result["fit"].update({
        "score": int(score) if score is not None else None,
        "label": str(label or "unmeasured"),
        "availableVramGb": _rounded(available_vram_gb),
        "headroomGb": _rounded(headroom_gb),
        "availableSystemRamGb": _rounded(available_system_ram_gb),
        "systemRamHeadroomGb": _rounded(system_ram_headroom_gb),
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
