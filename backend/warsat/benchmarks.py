"""Measured runtime benchmark certificates for local model placement.

This module accepts numeric observations from a runtime adapter or a test
harness. It never calls a model, starts a container, or treats a catalog
estimate as measured evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import time

from backend.core import runtime_store as store


SCHEMA_VERSION = "rasputin.runtime-benchmark.v1"
STORE_KEY = "warsat_runtime_benchmark_certificates"
MAX_CERTIFICATES = 200
DEFAULT_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def _text(value, default="", limit=160):
    return str(value if value is not None else default).strip()[:limit]


def _number(value, default=None, minimum=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number) or number < minimum:
        return default
    return number


def _integer(value, default=None, minimum=0, maximum=None):
    number = _number(value, default, float(minimum))
    if number is None:
        return default
    result = int(number)
    if maximum is not None:
        result = min(result, maximum)
    return result


def _alias(data, *names, default=None):
    for name in names:
        if name in data and data.get(name) not in (None, ""):
            return data.get(name)
    return default


def _percentile(values, fraction):
    values = sorted(float(item) for item in values)
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 3)
    position = (len(values) - 1) * float(fraction)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(values[lower], 3)
    weight = position - lower
    return round(values[lower] + (values[upper] - values[lower]) * weight, 3)


def _summary(values):
    values = [float(item) for item in values if item is not None]
    if not values:
        return {"count": 0, "mean": None, "p50": None, "p95": None}
    return {
        "count": len(values),
        "mean": round(sum(values) / len(values), 3),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
    }


def _normalize_sample(sample, index):
    if not isinstance(sample, dict):
        raise ValueError(f"sample {index + 1} must be an object")
    status = _text(_alias(sample, "status", default="ok"), "ok", 24).lower()
    if status not in {"ok", "error", "cancelled"}:
        raise ValueError(f"sample {index + 1} status must be ok, error, or cancelled")
    total_ms = _number(_alias(sample, "totalLatencyMs", "total_latency_ms", "latencyMs", "latency_ms"))
    if total_ms is None:
        raise ValueError(f"sample {index + 1} requires totalLatencyMs")
    ttft_ms = _number(_alias(sample, "ttftMs", "ttft_ms"))
    prompt_ms = _number(_alias(sample, "promptProcessingMs", "prompt_processing_ms"))
    decode_ms = _number(_alias(sample, "decodeMs", "decode_ms"))
    prompt_tokens = _integer(_alias(sample, "promptTokens", "prompt_tokens"), 0, 0, 10_000_000)
    output_tokens = _integer(
        _alias(sample, "outputTokens", "output_tokens", "decodeTokens", "decode_tokens"),
        0,
        0,
        10_000_000,
    )
    decode_tps = _number(_alias(sample, "decodeTokensPerSecond", "decode_tokens_per_second"))
    if decode_tps is None and decode_ms and output_tokens:
        decode_tps = output_tokens / (decode_ms / 1000.0)
    prompt_tps = _number(_alias(sample, "promptTokensPerSecond", "prompt_tokens_per_second"))
    if prompt_tps is None and prompt_ms and prompt_tokens:
        prompt_tps = prompt_tokens / (prompt_ms / 1000.0)
    return {
        "index": index + 1,
        "status": status,
        "totalLatencyMs": round(total_ms, 3),
        "ttftMs": round(ttft_ms, 3) if ttft_ms is not None else None,
        "promptProcessingMs": round(prompt_ms, 3) if prompt_ms is not None else None,
        "decodeMs": round(decode_ms, 3) if decode_ms is not None else None,
        "promptTokens": prompt_tokens,
        "outputTokens": output_tokens,
        "decodeTokensPerSecond": round(decode_tps, 3) if decode_tps is not None else None,
        "promptTokensPerSecond": round(prompt_tps, 3) if prompt_tps is not None else None,
        "queueMs": round(_number(_alias(sample, "queueMs", "queue_ms"), 0) or 0, 3),
        "memoryUsedMb": round(_number(_alias(sample, "memoryUsedMb", "memory_used_mb"), 0) or 0, 3),
        "memoryTotalMb": round(_number(_alias(sample, "memoryTotalMb", "memory_total_mb"), 0) or 0, 3),
    }


def _identity_key(spec):
    identity = {
        "modelId": spec["modelId"],
        "modelRevision": spec["modelRevision"],
        "runtime": spec["runtime"],
        "protocolId": spec["protocolId"],
        "deviceIds": spec["deviceIds"],
        "contextWindow": spec["contextWindow"],
        "concurrency": spec["concurrency"],
        "quantization": spec["quantization"],
        "placementMode": spec["placementMode"],
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def build_certificate(spec=None, samples=None, *, owner="", certificate_id="", measured_at=None):
    """Normalize observations into a deterministic, JSON-safe certificate."""

    spec = dict(spec or {})
    raw_samples = list(samples or [])[:100]
    if not raw_samples:
        raise ValueError("At least one runtime benchmark sample is required")
    model_id = _text(_alias(spec, "modelId", "model_id", "modelRef", "model_ref"))
    runtime = _text(spec.get("runtime"))
    protocol_id = _text(_alias(spec, "protocolId", "protocol_id"))
    if not model_id or not runtime or not protocol_id:
        raise ValueError("modelId, runtime, and protocolId are required")
    normalized_samples = [_normalize_sample(sample, index) for index, sample in enumerate(raw_samples)]
    successful = [sample for sample in normalized_samples if sample["status"] == "ok"]
    if not successful:
        raise ValueError("At least one benchmark sample must have status=ok")

    device_ids = _alias(spec, "deviceIds", "device_ids", default=[])
    if isinstance(device_ids, str):
        device_ids = [item.strip() for item in device_ids.split(",") if item.strip()]
    device_ids = [_text(item, limit=64) for item in (device_ids or []) if _text(item, limit=64)][:16]
    context_window = _integer(_alias(spec, "contextWindow", "context_window"), None, 1, 262144)
    concurrency = _integer(spec.get("concurrency"), 1, 1, 4096)
    normalized_spec = {
        "modelId": model_id,
        "modelRevision": _text(_alias(spec, "modelRevision", "model_revision", "checksum", "sha")),
        "runtime": runtime,
        "protocolId": protocol_id,
        "deviceIds": device_ids,
        "contextWindow": context_window,
        "concurrency": concurrency,
        "quantization": _text(spec.get("quantization")),
        "placementMode": _text(_alias(spec, "placementMode", "placement_mode"), "single-gpu"),
        "maxModelLen": _integer(_alias(spec, "maxModelLen", "max_model_len"), None, 1, 262144),
        "batchSize": _integer(_alias(spec, "batchSize", "batch_size"), None, 1, 65536),
    }
    certificate = {
        "schemaVersion": SCHEMA_VERSION,
        "certificateId": _text(certificate_id) or store.new_id("runtimecert"),
        "identityKey": _identity_key(normalized_spec),
        "owner": _text(owner, "admin", 80) or "admin",
        "createdAt": float(measured_at or time.time()),
        "spec": normalized_spec,
        "samples": normalized_samples,
        "summary": {
            "sampleCount": len(normalized_samples),
            "successCount": len(successful),
            "failureCount": len(normalized_samples) - len(successful),
            "successRate": round(len(successful) / len(normalized_samples), 4),
            "totalLatencyMs": _summary(sample["totalLatencyMs"] for sample in successful),
            "ttftMs": _summary(sample["ttftMs"] for sample in successful),
            "decodeTokensPerSecond": _summary(sample["decodeTokensPerSecond"] for sample in successful),
            "promptTokensPerSecond": _summary(sample["promptTokensPerSecond"] for sample in successful),
            "queueMs": _summary(sample["queueMs"] for sample in successful),
            "memoryUsedMb": _summary(sample["memoryUsedMb"] for sample in successful),
        },
        "quality": {
            "status": "unmeasured",
            "method": "not-supplied",
            "score": None,
        },
        "placement": {
            "status": "measured-observation-only",
            "runtimeCertificateRequired": True,
            "deviceIds": device_ids,
        },
        "status": "measured" if len(successful) == len(normalized_samples) else "partial",
        "limitations": [
            "Performance measurements describe this exact model/runtime/device/context/concurrency tuple.",
            "No semantic quality claim is made until an objective rubric is supplied.",
            "This certificate does not authorize host actions or bypass deployment approval.",
        ],
    }
    return certificate


def validate_certificate(certificate):
    errors = []
    if not isinstance(certificate, dict):
        return {"valid": False, "errors": ["certificate must be an object"]}
    if certificate.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion must be rasputin.runtime-benchmark.v1")
    for key in ("certificateId", "identityKey", "spec", "samples", "summary", "quality", "placement", "status"):
        if key not in certificate:
            errors.append(f"missing field: {key}")
    if not isinstance(certificate.get("samples"), list) or not certificate.get("samples"):
        errors.append("samples must be a non-empty list")
    summary = certificate.get("summary") or {}
    success_rate = _number(summary.get("successRate"))
    if success_rate is None or success_rate > 1:
        errors.append("summary.successRate must be between 0 and 1")
    return {"valid": not errors, "errors": errors}


def save_certificate(certificate):
    validation = validate_certificate(certificate)
    if not validation["valid"]:
        raise ValueError("Invalid runtime benchmark certificate: " + "; ".join(validation["errors"]))
    certificates = store.get_kv(STORE_KEY, [])
    if not isinstance(certificates, list):
        certificates = []
    certificates = [item for item in certificates if item.get("certificateId") != certificate["certificateId"]]
    certificates.insert(0, certificate)
    store.set_kv(STORE_KEY, certificates[:MAX_CERTIFICATES])
    return certificate


def list_certificates(*, owner=None, model_id=None):
    certificates = store.get_kv(STORE_KEY, [])
    if not isinstance(certificates, list):
        return []
    owner = _text(owner) if owner is not None else None
    model_id = _text(model_id) if model_id else None
    return [
        item for item in certificates
        if (owner is None or item.get("owner") == owner)
        and (model_id is None or (item.get("spec") or {}).get("modelId") == model_id)
    ]


def get_certificate(certificate_id, *, owner=None):
    for certificate in list_certificates(owner=owner):
        if certificate.get("certificateId") == certificate_id:
            return certificate
    return None


def is_fresh(certificate, *, now=None, max_age_seconds=DEFAULT_MAX_AGE_SECONDS):
    if not certificate or certificate.get("status") not in {"measured", "partial"}:
        return False
    try:
        age = float(now if now is not None else time.time()) - float(certificate.get("createdAt") or 0)
    except (TypeError, ValueError):
        return False
    return 0 <= age <= max(1, int(max_age_seconds))
