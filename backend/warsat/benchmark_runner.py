"""Bounded measurements for already-registered model endpoints.

The runner is deliberately read-only with respect to runtime lifecycle. It may
issue a small number of chat requests to a registered endpoint, but it never
starts, stops, pulls, or redeploys a model.
"""

from __future__ import annotations

import concurrent.futures
import time

from backend.core.response import AppError
from backend.models import providers as model_providers
from backend.models import registry as model_registry
from backend.warsat import benchmarks


FIXED_PROMPT = (
    "This is a bounded local runtime performance check. Reply with one coherent "
    "plain-text paragraph of approximately forty-eight to sixty-four tokens. "
    "Explain that the endpoint is reachable, generation is functioning, and the "
    "response was produced by the selected model. Do not use bullets, code, "
    "tool calls, repetition, or prefatory commentary; stop after the paragraph."
)
MIN_SAMPLES = 1
MAX_SAMPLES = 3
MAX_TOKENS = 128
DEFAULT_MAX_TOKENS = 64
DEFAULT_TIMEOUT_SECONDS = 30.0


def _bounded_int(value, name, minimum, maximum):
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}") from exc
    if result < minimum or result > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


def _timeout(value):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("timeoutSeconds must be a positive number") from exc
    if result <= 0 or result > 120:
        raise ValueError("timeoutSeconds must be between 0 and 120 seconds")
    return result


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _metadata_values(metadata):
    """Collect provider/runtime timing and usage fields without estimating them."""
    values = {}
    if not isinstance(metadata, dict):
        return values
    sources = [metadata]
    for key in ("usage", "timing", "timings", "metrics"):
        if isinstance(metadata.get(key), dict):
            sources.append(metadata[key])
    aliases = {
        "outputTokens": (
            "outputTokens", "output_tokens", "completionTokens",
            "completion_tokens", "generatedTokens", "generated_tokens",
            "tokenCount", "token_count", "predicted_n", "predictedTokens",
            "predicted_tokens",
        ),
        "ttftMs": ("ttftMs", "ttft_ms", "timeToFirstTokenMs", "time_to_first_token_ms"),
        "totalLatencyMs": ("totalLatencyMs", "total_latency_ms", "latencyMs", "latency_ms"),
        "decodeMs": (
            "decodeMs", "decode_ms", "generationMs", "generation_ms",
            "predicted_ms", "prediction_ms",
        ),
        "decodePerTokenMs": (
            "decodePerTokenMs", "decode_per_token_ms", "predicted_per_token_ms",
        ),
        "decodeTokensPerSecond": (
            "decodeTokensPerSecond", "decode_tokens_per_second",
            "outputTokensPerSecond", "output_tokens_per_second", "tps",
            "predicted_per_second", "predictedTokensPerSecond",
            "predicted_tokens_per_second",
        ),
        "promptTokens": (
            "promptTokens", "prompt_tokens", "inputTokens", "input_tokens",
            "prompt_n",
        ),
        "promptProcessingMs": (
            "promptProcessingMs", "prompt_processing_ms", "promptMs",
            "prompt_ms",
        ),
    }
    for target, keys in aliases.items():
        for source in sources:
            for key in keys:
                number = _number(source.get(key))
                if number is not None:
                    values[target] = number
                    break
            if target in values:
                break
    if "decodeMs" not in values and values.get("outputTokens") and values.get("decodePerTokenMs"):
        values["decodeMs"] = values["outputTokens"] * values["decodePerTokenMs"]
    return values


def _identity(model):
    profile = model_registry.deployment_profile(model)
    protocol_id = profile.get("protocolId") or model.get("protocol_id") or ""
    model_id = profile.get("model") or model.get("model") or profile.get("key") or ""
    if not model_id or not protocol_id:
        raise AppError(
            "benchmark_identity_missing",
            "Registered model is missing an exact model/protocol identity.",
            409,
        )
    return {
        "modelId": str(model_id),
        "modelRevision": str(
            model.get("model_revision")
            or model.get("modelRevision")
            or model.get("revision")
            or ""
        ),
        "runtime": str(profile.get("runtime") or model.get("runtime") or ""),
        "protocolId": str(protocol_id),
        "deviceIds": [
            str(item)
            for item in (profile.get("deviceIds") or model.get("device_ids") or [])
        ],
        "contextWindow": profile.get("contextWindow") or model.get("context_window") or None,
        "concurrency": int(model.get("concurrency") or 1),
        "quantization": str(
            profile.get("quantization") or model.get("quantization") or ""
        ),
        "placementMode": str(
            profile.get("placementMode") or model.get("placement_mode") or "single-gpu"
        ),
    }


def _measure_one(model, max_tokens, timeout_seconds):
    started = time.perf_counter()
    first_delta = None
    events = []

    def on_delta(event):
        nonlocal first_delta
        event = dict(event or {}) if isinstance(event, dict) else {}
        now = time.perf_counter()
        if first_delta is None and (
            event.get("type") in {"text", "token"} or event.get("text")
        ):
            first_delta = now
        events.append((now, event))

    def request():
        return model_providers.chat_sync(
            model,
            [{"role": "user", "content": FIXED_PROMPT}],
            max_tokens,
            0,
            on_delta=on_delta,
            reasoning="off",
        )

    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="warsat-benchmark"
    )
    future = executor.submit(request)
    try:
        result = future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise AppError(
            "benchmark_timeout",
            f"Registered model did not respond within {timeout_seconds:g} seconds.",
            504,
        ) from exc
    except Exception as exc:  # noqa: BLE001 — expose reachability failures to the caller
        raise AppError(
            "benchmark_unreachable",
            f"Registered model benchmark request failed: {exc}",
            502,
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    ended = time.perf_counter()
    metadata = {}
    if isinstance(result, (tuple, list)) and len(result) >= 3 and isinstance(result[2], dict):
        metadata.update(result[2])
    elif isinstance(result, dict):
        metadata.update(result)
    values = _metadata_values(metadata)
    for _timestamp, event in events:
        values.update({
            key: value
            for key, value in _metadata_values(event).items()
            if key not in values
        })

    token_events = sum(
        int(event.get("count") or event.get("tokenCount") or 1)
        for _timestamp, event in events
        if event.get("type") == "token"
    )
    output_tokens = int(values.get("outputTokens") or token_events or 0)
    total_ms = values.get("totalLatencyMs") or (ended - started) * 1000
    ttft_ms = values.get("ttftMs")
    if ttft_ms is None and first_delta is not None:
        ttft_ms = (first_delta - started) * 1000
    decode_ms = values.get("decodeMs")
    if decode_ms is None and first_delta is not None:
        decode_ms = max(0.001, (ended - first_delta) * 1000)
    decode_tps = values.get("decodeTokensPerSecond")
    if decode_tps is None and output_tokens and decode_ms:
        decode_tps = output_tokens / (decode_ms / 1000)
    if output_tokens <= 0 or not decode_tps or decode_tps <= 0:
        raise AppError(
            "benchmark_metrics_unavailable",
            "Benchmark response did not provide usable generated-token and timing data.",
            502,
        )
    return {
        "status": "ok",
        "totalLatencyMs": total_ms,
        "ttftMs": ttft_ms,
        "decodeMs": decode_ms,
        "outputTokens": output_tokens,
        "decodeTokensPerSecond": decode_tps,
        "promptTokens": values.get("promptTokens", 0),
        "promptProcessingMs": values.get("promptProcessingMs"),
    }


def run_registered_model(
    model_id,
    *,
    owner,
    samples=1,
    max_tokens=DEFAULT_MAX_TOKENS,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
):
    sample_count = _bounded_int(samples, "samples", MIN_SAMPLES, MAX_SAMPLES)
    token_limit = _bounded_int(max_tokens, "maxTokens", 1, MAX_TOKENS)
    timeout = _timeout(timeout_seconds)
    model = model_registry.get_model(str(model_id or "").strip())
    if not model:
        raise AppError("model_missing", f"Registered model '{model_id}' was not found.", 404)
    if not model.get("enabled", True):
        raise AppError("model_unavailable", "The registered model is disabled.", 409)
    spec = _identity(model)
    measured = [
        _measure_one(model, token_limit, timeout)
        for _ in range(sample_count)
    ]
    certificate = benchmarks.build_certificate(spec, measured, owner=owner)
    saved = benchmarks.save_certificate(certificate)
    return {**saved, "fresh": benchmarks.is_fresh(saved)}
