import json
import os
import re
import time
from pathlib import Path

import httpx

from . import audit

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_FILE = DATA_DIR / "models_dev_catalog.json"
HF_SEARCH_CACHE_FILE = DATA_DIR / "hf_search_cache.json"
MODELS_DEV_URL = os.environ.get("MODELS_DEV_API_URL", "https://models.dev/api.json")
HF_API_URL = os.environ.get("HF_API_URL", "https://huggingface.co/api/models")
CACHE_TTL_SECONDS = int(os.environ.get("MODELS_DEV_CACHE_TTL_SECONDS", "86400"))
FETCH_TIMEOUT_SECONDS = float(os.environ.get("MODELS_DEV_FETCH_TIMEOUT_SECONDS", "8"))
HF_FETCH_TIMEOUT = float(os.environ.get("HF_FETCH_TIMEOUT_SECONDS", "12"))
MAX_REMOTE_ITEMS = int(os.environ.get("MODELS_DEV_MAX_ITEMS", "280"))

PURPOSES = [
    {"id": "chat", "label": "Chat"},
    {"id": "coding", "label": "Coding"},
    {"id": "reasoning", "label": "Reasoning"},
    {"id": "research", "label": "Research"},
    {"id": "vision", "label": "Vision"},
    {"id": "embeddings", "label": "Embeddings"},
    {"id": "reranker", "label": "Reranker"},
    {"id": "speech", "label": "Speech"},
    {"id": "multimodal", "label": "Multimodal"},
    {"id": "fast", "label": "Fast / low VRAM"},
]

# HF pipeline_tag → Rasputin purpose mapping
HF_PIPELINE_MAP = {
    "text-generation": "chat",
    "text2text-generation": "chat",
    "conversational": "chat",
    "fill-mask": "chat",
    "feature-extraction": "embeddings",
    "sentence-similarity": "embeddings",
    "image-to-text": "vision",
    "visual-question-answering": "vision",
    "image-classification": "vision",
    "object-detection": "vision",
    "automatic-speech-recognition": "speech",
    "text-to-speech": "speech",
    "text-to-image": "multimodal",
    "text-classification": "research",
    "question-answering": "research",
    "summarization": "research",
    "translation": "research",
}

RUNTIMES = [
    {"id": "vllmCudaOpenai", "label": "vLLM", "input": "Hugging Face model id"},
    {"id": "llamaCppGgufServer", "label": "llama.cpp", "input": "Mounted GGUF path"},
    {"id": "ollamaOpenaiServer", "label": "Ollama", "input": "Ollama model name"},
    {"id": "apiOnly", "label": "API only", "input": "Provider API registration"},
]

CURATED_DEPLOYABLE = [
    {
        "id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "name": "Qwen2.5 Coder 7B Instruct",
        "provider": "huggingface",
        "purpose": "coding",
        "capabilities": ["code", "chat", "tools"],
        "parameterCountB": 7,
        "vramEstimateGb": 12,
        "recommendedProfile": "balanced",
        "recommendedProtocol": "vllmCudaOpenai",
        "summary": "Practical coding helper size for a first Warsat vLLM deployment.",
    },
    {
        "id": "mistralai/Mistral-7B-Instruct-v0.3",
        "name": "Mistral 7B Instruct v0.3",
        "provider": "huggingface",
        "purpose": "chat",
        "capabilities": ["chat", "summarize"],
        "parameterCountB": 7,
        "vramEstimateGb": 12,
        "recommendedProfile": "balanced",
        "recommendedProtocol": "vllmCudaOpenai",
        "summary": "General chat model for local testing on midrange GPUs.",
    },
    {
        "id": "microsoft/Phi-3.5-mini-instruct",
        "name": "Phi-3.5 Mini Instruct",
        "provider": "huggingface",
        "purpose": "fast",
        "capabilities": ["chat", "summarize", "low-vram"],
        "parameterCountB": 3.8,
        "vramEstimateGb": 7,
        "recommendedProfile": "small",
        "recommendedProtocol": "vllmCudaOpenai",
        "summary": "Small local assistant candidate when VRAM is tight.",
    },
    {
        "id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "name": "DeepSeek R1 Distill Qwen 7B",
        "provider": "huggingface",
        "purpose": "reasoning",
        "capabilities": ["reasoning", "chat"],
        "parameterCountB": 7,
        "vramEstimateGb": 12,
        "recommendedProfile": "balanced",
        "recommendedProtocol": "vllmCudaOpenai",
        "summary": "Reasoning-focused local model candidate for analysis tasks.",
    },
    {
        "id": "llama3.2",
        "name": "Llama 3.2 via Ollama",
        "provider": "ollama",
        "purpose": "chat",
        "capabilities": ["chat", "general-local"],
        "parameterCountB": None,
        "vramEstimateGb": None,
        "recommendedProfile": "cpu",
        "recommendedProtocol": "ollamaOpenaiServer",
        "summary": "Ollama runtime target for quick local model experiments.",
    },
]


def _now():
    return int(time.time())


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "model"


def _text_blob(*values):
    return " ".join(str(value or "") for value in values).lower()


def _parameter_count(model_id, model):
    blob = _text_blob(model_id, model.get("name"), model.get("display_name"))
    match = re.search(r"(\d+(?:\.\d+)?)\s*b(?:\b|[-_])", blob)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _vram_estimate(parameter_count):
    if not parameter_count:
        return None
    return max(4, round(parameter_count * 1.7 + 2))


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
    if "/" in str(model_id) or provider in {"huggingface", "hf"} or model.get("open_weights") or model.get("openWeights"):
        options.append({"protocolId": "vllmCudaOpenai", "label": "Run through vLLM"})
    if "gguf" in blob:
        options.append({"protocolId": "llamaCppGgufServer", "label": "Run mounted GGUF with llama.cpp"})
    if not options:
        options.append({"protocolId": "apiOnly", "label": "Register as provider API"})
    if purpose == "embeddings":
        options = [{"protocolId": "apiOnly", "label": "Use as embedding provider"}]
    return options


def _normalize_item(provider_id, provider, model_id, model, source="models.dev"):
    model = dict(model or {})
    name = model.get("name") or model.get("display_name") or str(model_id)
    purpose = _purpose(model_id, model, provider_id)
    params = _parameter_count(model_id, model)
    runtime_options = _runtime_options(provider_id, model_id, model, purpose)
    context = None
    limit = model.get("limit") or {}
    if isinstance(limit, dict):
        context = limit.get("context") or limit.get("input")
    return {
        "id": f"{provider_id}/{model_id}" if provider_id and "/" not in str(model_id) else str(model_id),
        "modelId": str(model_id),
        "name": str(name),
        "provider": str(provider.get("name") or provider_id or "unknown"),
        "providerId": str(provider_id or "unknown"),
        "purpose": purpose,
        "capabilities": _capabilities(model_id, model, purpose),
        "contextWindow": context,
        "parameterCountB": params,
        "vramEstimateGb": _vram_estimate(params),
        "recommendedProfile": "small" if purpose == "fast" else "balanced",
        "recommendedProtocol": runtime_options[0]["protocolId"],
        "runtimeOptions": runtime_options,
        "deployable": runtime_options[0]["protocolId"] != "apiOnly",
        "apiOnly": runtime_options[0]["protocolId"] == "apiOnly",
        "source": source,
        "sourceUrl": MODELS_DEV_URL,
        "summary": model.get("description") or "Model metadata imported from the public models.dev catalog.",
    }


def _curated_items():
    items = []
    for model in CURATED_DEPLOYABLE:
        protocol = model["recommendedProtocol"]
        item = {
            **model,
            "modelId": model["id"],
            "providerId": model["provider"],
            "runtimeOptions": [{"protocolId": protocol, "label": f"Plan with {protocol}"}],
            "deployable": True,
            "apiOnly": False,
            "source": "rasputin-curated",
            "sourceUrl": "",
        }
        items.append(item)
    return items


def _hardware_vram_gb(hardware=None):
    env_vram = os.environ.get("WARSAT_AVAILABLE_VRAM_GB")
    if env_vram:
        try:
            return float(env_vram)
        except ValueError:
            pass
    gpus = ((hardware or {}).get("detected_hardware") or (hardware or {}).get("detectedHardware") or {}).get("gpus") or []
    values = []
    for gpu in gpus:
        mb = gpu.get("memory_total_mb") or gpu.get("memoryTotalMb")
        try:
            if mb:
                values.append(float(mb) / 1024)
        except Exception:
            continue
    return max(values) if values else None


def _fit_item(item, hardware=None):
    item = dict(item)
    blocked = []
    reasons = []
    score = 50
    vram = item.get("vramEstimateGb")
    available = _hardware_vram_gb(hardware)
    if not item.get("deployable"):
        blocked.append("No local Warsat runtime is known for this catalog entry.")
        score -= 45
    if vram:
        if available:
            margin = available - float(vram)
            if margin >= 4:
                score += 35
                reasons.append(f"Estimated {vram} GB VRAM fits inside detected {available:.1f} GB.")
            elif margin >= 0:
                score += 18
                reasons.append(f"Estimated {vram} GB VRAM fits, but headroom is tight.")
            else:
                score -= 40
                blocked.append(f"Estimated {vram} GB VRAM exceeds detected {available:.1f} GB.")
        else:
            score += 10 if float(vram) <= 12 else -5
            reasons.append(f"Estimated {vram} GB VRAM; run Warsat readiness for hardware-specific fit.")
    else:
        reasons.append("VRAM estimate is unknown.")
    purpose = item.get("purpose")
    if purpose in {"coding", "reasoning", "research"}:
        score += 8
        reasons.append(f"Useful for {purpose} workflows.")
    if item.get("recommendedProtocol") == "ollamaOpenaiServer":
        score += 5
        reasons.append("Ollama target is useful for quick local experiments.")
    score = max(0, min(100, int(score)))
    if blocked:
        label = "Blocked"
    elif score >= 82:
        label = "Strong fit"
    elif score >= 62:
        label = "Good fit"
    elif score >= 42:
        label = "Possible"
    else:
        label = "Weak fit"
    item.update({
        "fitScore": score,
        "fitLabel": label,
        "fitReasons": reasons[:4],
        "blockedReasons": blocked,
    })
    return item


def _apply_fit(items, hardware=None):
    fitted = [_fit_item(item, hardware) for item in items]
    fitted.sort(key=lambda item: (bool(item.get("blockedReasons")), -int(item.get("fitScore") or 0), item.get("name", "")))
    return fitted


def _read_cache():
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(payload):
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fetch_models_dev():
    with httpx.Client(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.get(MODELS_DEV_URL)
        response.raise_for_status()
        return response.json()


def _remote_items(raw):
    if not isinstance(raw, dict):
        return []
    items = []
    for provider_id, provider in raw.items():
        if not isinstance(provider, dict):
            continue
        models = provider.get("models") or {}
        if not isinstance(models, dict):
            continue
        for model_id, model in models.items():
            if not isinstance(model, dict):
                continue
            items.append(_normalize_item(provider_id, provider, model_id, model))
            if len(items) >= MAX_REMOTE_ITEMS:
                return items
    return items


def _catalog_payload(remote_items=None, source_status="fallback", source_error="", hardware=None):
    curated = _curated_items()
    remote_items = remote_items or []
    seen = {item["id"] for item in curated}
    merged_remote = [item for item in remote_items if item["id"] not in seen]
    items = _apply_fit(curated + merged_remote, hardware)
    return {
        "items": items,
        "count": len(items),
        "deployableCount": len([item for item in items if item.get("deployable")]),
        "categories": PURPOSES,
        "runtimes": RUNTIMES,
        "source": {
            "name": "models.dev",
            "url": MODELS_DEV_URL,
            "status": source_status,
            "error": source_error,
            "updatedAt": _now(),
            "cacheFile": str(CACHE_FILE),
        },
    }


def catalog(refresh=False, force=False, hardware=None):
    cached = _read_cache()
    cache_age = _now() - int((cached or {}).get("source", {}).get("updatedAt") or 0)
    if cached and not refresh and cache_age < CACHE_TTL_SECONDS:
        return {**cached, "items": _apply_fit(cached.get("items", []), hardware), "source": {**cached.get("source", {}), "status": "cache"}}
    if not refresh and cached:
        return {**cached, "items": _apply_fit(cached.get("items", []), hardware), "source": {**cached.get("source", {}), "status": "staleCache"}}
    if not refresh and not cached:
        return _catalog_payload(source_status="fallback", hardware=hardware)

    try:
        raw = _fetch_models_dev()
        payload = _catalog_payload(_remote_items(raw), source_status="fresh", hardware=hardware)
        _write_cache(payload)
        audit.log("model_catalog_refreshed", {"source": MODELS_DEV_URL, "count": payload["count"]})
        return payload
    except Exception as exc:
        audit.log("model_catalog_refresh_failed", {"source": MODELS_DEV_URL, "error": str(exc)})
        if cached and not force:
            return {**cached, "items": _apply_fit(cached.get("items", []), hardware), "source": {**cached.get("source", {}), "status": "cacheAfterRefreshError", "error": str(exc)}}
        payload = _catalog_payload(source_status="fallbackAfterRefreshError", source_error=str(exc), hardware=hardware)
        return payload


# ── Hugging Face Hub API search ──────────────────────────────────────

def _hf_purpose_from_pipeline(pipeline_tag):
    return HF_PIPELINE_MAP.get(pipeline_tag or "", "chat")


def _normalize_hf_model(hf_model):
    """Convert a HF API model dict into a Rasputin catalog item."""
    model_id = hf_model.get("modelId") or hf_model.get("id") or "unknown"
    pipeline_tag = hf_model.get("pipeline_tag") or ""
    purpose = _hf_purpose_from_pipeline(pipeline_tag)
    tags = hf_model.get("tags") or []
    params = _parameter_count(model_id, {"name": model_id, "tags": " ".join(tags)})
    license_tag = ""
    for tag in tags:
        if tag.startswith("license:"):
            license_tag = tag.replace("license:", "")
            break
    # Detect quantization from tags
    quant = ""
    for tag in tags:
        tag_lower = tag.lower()
        if any(q in tag_lower for q in ["gguf", "gptq", "awq", "bnb", "exl2", "fp16", "fp8", "int4", "int8"]):
            quant = tag
            break
    # Detect architecture
    architecture = ""
    if hf_model.get("config") and isinstance(hf_model["config"], dict):
        arch_list = hf_model["config"].get("architectures") or []
        if arch_list:
            architecture = arch_list[0]
    # Override purpose for known patterns
    blob = _text_blob(model_id, " ".join(tags))
    if any(w in blob for w in ["coder", "coding", "code"]):
        purpose = "coding"
    elif any(w in blob for w in ["reason", "thinking", "r1"]):
        purpose = "reasoning"
    elif any(w in blob for w in ["rerank"]):
        purpose = "reranker"
    elif "embed" in blob:
        purpose = "embeddings"
    elif any(w in blob for w in ["vision", "llava", "visual"]):
        purpose = "vision"
    elif any(w in blob for w in ["whisper", "speech", "tts"]):
        purpose = "speech"

    is_gguf = "gguf" in blob
    has_open_weights = "/" in model_id  # HF models with org/name are usually open weights
    runtime_options = []
    if is_gguf:
        runtime_options.append({"protocolId": "llamaCppGgufServer", "label": "Run GGUF with llama.cpp"})
    if has_open_weights and purpose not in {"embeddings", "reranker"}:
        runtime_options.append({"protocolId": "vllmCudaOpenai", "label": "Run through vLLM"})
    if not runtime_options:
        runtime_options.append({"protocolId": "apiOnly", "label": "Register as provider API"})

    return {
        "id": model_id,
        "modelId": model_id,
        "name": model_id.split("/")[-1] if "/" in model_id else model_id,
        "provider": model_id.split("/")[0] if "/" in model_id else "huggingface",
        "providerId": "huggingface",
        "purpose": purpose,
        "capabilities": _capabilities(model_id, {"name": model_id, "tags": " ".join(tags)}, purpose),
        "contextWindow": None,
        "parameterCountB": params,
        "vramEstimateGb": _vram_estimate(params),
        "recommendedProfile": "small" if purpose == "fast" else "balanced",
        "recommendedProtocol": runtime_options[0]["protocolId"],
        "runtimeOptions": runtime_options,
        "deployable": runtime_options[0]["protocolId"] != "apiOnly",
        "apiOnly": runtime_options[0]["protocolId"] == "apiOnly",
        "source": "huggingface",
        "sourceUrl": f"https://huggingface.co/{model_id}",
        "summary": (hf_model.get("description") or "")[:200] or f"Hugging Face model: {model_id}",
        "downloads": hf_model.get("downloads") or 0,
        "likes": hf_model.get("likes") or 0,
        "license": license_tag,
        "quantization": quant,
        "architecture": architecture,
        "pipelineTag": pipeline_tag,
        "lastModified": hf_model.get("lastModified") or "",
    }


def search_hf(query="", model_type="", sort="downloads", direction=-1, limit=100, hardware=None):
    """Search Hugging Face Hub API for models."""
    if sort == "trending":
        sort = "trendingScore"
    params = {
        "limit": min(int(limit), 100),
        "sort": sort or "downloads",
        "direction": str(direction),
    }
    if query:
        params["search"] = query
    if model_type:
        params["pipeline_tag"] = model_type

    try:
        with httpx.Client(timeout=HF_FETCH_TIMEOUT, follow_redirects=True) as client:
            response = client.get(HF_API_URL, params=params)
            response.raise_for_status()
            raw_models = response.json()
    except Exception as exc:
        audit.log("hf_search_failed", {"query": query, "error": str(exc)})
        return {"items": [], "count": 0, "error": str(exc), "source": "huggingface"}

    if not isinstance(raw_models, list):
        return {"items": [], "count": 0, "error": "Unexpected HF API response format", "source": "huggingface"}

    items = [_normalize_hf_model(m) for m in raw_models[:int(limit)]]
    if hardware:
        items = _apply_fit(items, hardware)
    
    audit.log("hf_search", {"query": query, "type": model_type, "count": len(items)})
    return {
        "items": items,
        "count": len(items),
        "query": query,
        "modelType": model_type,
        "sort": sort,
        "source": "huggingface",
    }


def hf_model_detail(model_id):
    """Fetch detailed info for a single HF model."""
    url = f"{HF_API_URL}/{model_id}"
    try:
        with httpx.Client(timeout=HF_FETCH_TIMEOUT, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            raw = response.json()
    except Exception as exc:
        return {"error": str(exc), "modelId": model_id}

    item = _normalize_hf_model(raw)
    # Enrich with extra detail fields
    siblings = raw.get("siblings") or []
    files = [{"rfilename": s.get("rfilename", ""), "size": s.get("size")} for s in siblings[:50]]
    item["files"] = files
    item["sha"] = raw.get("sha", "")
    item["private"] = raw.get("private", False)
    item["gated"] = raw.get("gated", False)
    item["disabled"] = raw.get("disabled", False)
    config = raw.get("config") or {}
    if isinstance(config, dict):
        item["architecture"] = (config.get("architectures") or [""])[0] if config.get("architectures") else item.get("architecture", "")
        item["modelType"] = config.get("model_type", "")
        item["torchDtype"] = config.get("torch_dtype", "")
    card = raw.get("cardData") or {}
    if isinstance(card, dict):
        item["language"] = card.get("language", [])
        item["datasets"] = card.get("datasets", [])
        item["library"] = card.get("library_name", "")
    return item
