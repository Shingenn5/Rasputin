"""Model identity, capability and weight metadata."""

import math
import re

from backend.models import resource_manifest


def _tool_call_parser_hint(model_id, protocol_id):
    """Return a conservative, non-binding vLLM parser recommendation.

    Parser selection remains opt-in at deployment because a wrong parser can
    silently corrupt tool calls. Only families proven through Rasputin's real
    deploy path belong here; unknown models intentionally return None.
    """
    if protocol_id != "vllmCudaOpenai":
        return None
    collapsed = re.sub(r"[^a-z0-9]+", "", str(model_id or "").lower())
    if "qwen25" in collapsed:
        return "hermes"
    return None


def _text_blob(*values):
    return " ".join(str(value or "") for value in values).lower()


def _parameter_count(model_id, model):
    for field in ("gguf", "safetensors"):
        metadata = model.get(field)
        if isinstance(metadata, dict):
            try:
                total = float(metadata.get("total") or 0)
                if math.isfinite(total) and total > 0:
                    return total / 1_000_000_000
            except (ValueError, TypeError):
                pass
    blob = _text_blob(model_id, model.get("name"), model.get("display_name"))
    match = re.search(r"(\d+(?:\.\d+)?)\s*([bm])(?:\b|[-_])", blob)
    if not match:
        return None
    try:
        return float(match.group(1)) / (1000 if match.group(2) == "m" else 1)
    except ValueError:
        return None


def _quantization_bits(quantization="", model_id=""):
    blob = _text_blob(quantization, model_id)
    for token, bits in (
        ("q2", 2.5), ("iq2", 2.5),
        ("q3", 3.5), ("iq3", 3.5),
        ("q4", 4.5), ("iq4", 4.5), ("int4", 4.5),
        ("awq", 4.5), ("gptq", 4.5), ("bnb", 4.5), ("bitsandbytes", 4.5),
        ("q5", 5.5), ("q6", 6.5),
        ("q8", 8.5), ("int8", 8.5), ("fp8", 8.5),
        ("fp16", 16.0), ("float16", 16.0), ("bf16", 16.0), ("bfloat16", 16.0),
    ):
        if token in blob:
            return bits
    # WarSat chooses a Q4-family file first from GGUF repositories, so a GGUF
    # repo without a quant suffix should be estimated using the artifact it
    # will actually select rather than as unquantized transformer weights.
    if "gguf" in blob:
        return 4.5
    return 16.0


def _vram_estimate(parameter_count, quantization="", model_id="", model=None,
                    context_window=None, concurrency=None, protocol_id=""):
    if not parameter_count:
        return None
    metadata = dict(model or {})
    if context_window is not None:
        metadata["contextWindow"] = context_window
    if concurrency is not None:
        metadata["concurrency"] = concurrency
    if protocol_id:
        metadata["recommendedProtocol"] = protocol_id
    estimate = resource_manifest.estimate_vram_demand(
        metadata,
        parameter_count_b=parameter_count,
        quantization=quantization,
        model_id=model_id,
    )
    total = (estimate or {}).get("totalGb")
    return max(4, round(float(total), 2)) if total is not None else None


def _purpose(model_id, model, provider_id):
    blob = _text_blob(model_id, provider_id, model.get("name"), model.get("description"), model.get("modalities"), model.get("capabilities"))
    if "embed" in blob:
        return "embeddings"
    if any(word in blob for word in ["vision", "image", "visual", "llava", "multimodal"]):
        return "vision"
    if any(word in blob for word in ["code", "coder", "coding"]):
        return "coding"
    if any(word in blob for word in ["reason", "thinking", "r1", "o1", "o3"]):
        return "reasoning"
    if any(word in blob for word in ["search", "research", "deep research"]):
        return "research"
    if any(word in blob for word in ["mini", "small", "flash", "lite", "haiku", "fast"]):
        return "fast"
    return "chat"


def _capabilities(model_id, model, purpose):
    caps = set()
    blob = _text_blob(model_id, model.get("name"), model.get("description"))
    for key in ["tool_call", "toolCalls", "tools", "reasoning", "structured_output", "attachments"]:
        if model.get(key):
            caps.add(str(key).replace("_", "-"))
    for word in ["vision", "image", "audio", "code", "reasoning", "embedding"]:
        if word in blob:
            caps.add(word)
    caps.add(purpose)
    return sorted(caps)


def _runtime_options(provider_id, model_id, model, purpose):
    provider = str(provider_id or "").lower()
    blob = _text_blob(provider_id, model_id, model.get("name"), model.get("description"))
    options = []
    if provider in {"ollama"}:
        options.append({"protocolId": "ollamaOpenaiServer", "label": "Run through Ollama"})
    if "gguf" in blob:
        options.append({"protocolId": "llamaCppGgufServer", "label": "Run GGUF with llama.cpp"})
    if "/" in str(model_id) or provider in {"huggingface", "hf"} or model.get("open_weights") or model.get("openWeights"):
        options.append({"protocolId": "vllmCudaOpenai", "label": "Run through vLLM"})
    if not options:
        options.append({"protocolId": "apiOnly", "label": "Register as provider API"})
    if purpose == "embeddings":
        options = [{"protocolId": "apiOnly", "label": "Use as embedding provider"}]
    return options
