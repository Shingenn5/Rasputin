import json
import os
import re
import subprocess
import threading
import time
from urllib.parse import urlparse
from pathlib import Path

import httpx

from backend.core import audit as audit
from backend.core.datadir import data_dir
from backend.models import resource_manifest

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = data_dir()
MODELS_DIR = ROOT / "models"
CACHE_FILE = DATA_DIR / "models_dev_catalog.json"
HF_SEARCH_CACHE_FILE = DATA_DIR / "hf_search_cache.json"
MODELS_DEV_URL = os.environ.get("MODELS_DEV_API_URL", "https://models.dev/api.json")
HF_API_URL = os.environ.get("HF_API_URL", "https://huggingface.co/api/models")
CACHE_TTL_SECONDS = int(os.environ.get("MODELS_DEV_CACHE_TTL_SECONDS", "86400"))
FETCH_TIMEOUT_SECONDS = float(os.environ.get("MODELS_DEV_FETCH_TIMEOUT_SECONDS", "8"))
HF_FETCH_TIMEOUT = float(os.environ.get("HF_FETCH_TIMEOUT_SECONDS", "12"))
MAX_REMOTE_ITEMS = int(os.environ.get("MODELS_DEV_MAX_ITEMS", "280"))
MANAGED_CONTAINER_CACHE_TTL_SECONDS = int(os.environ.get("RASPUTIN_MANAGED_CONTAINER_CACHE_TTL_SECONDS", "30"))
_MANAGED_CONTAINER_CACHE = {"updatedAt": 0.0, "items": []}
_MANAGED_CONTAINER_CACHE_LOCK = threading.Lock()

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


def _vram_estimate(parameter_count, quantization="", model_id=""):
    if not parameter_count:
        return None
    bits = _quantization_bits(quantization, model_id)
    # Weight bytes plus roughly 10% runtime overhead and a 2 GB floor for KV
    # cache / CUDA allocations. It is intentionally conservative: context
    # length and architecture can still move the real number.
    weights_gb = float(parameter_count) * bits / 8.0
    return max(4, round(weights_gb * 1.10 + 2))


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
    recommended_protocol = runtime_options[0]["protocolId"]
    item = {
        "id": f"{provider_id}/{model_id}" if provider_id and "/" not in str(model_id) else str(model_id),
        "modelId": str(model_id),
        "name": str(name),
        "provider": str(provider.get("name") or provider_id or "unknown"),
        "providerId": str(provider_id or "unknown"),
        "purpose": purpose,
        "capabilities": _capabilities(model_id, model, purpose),
        "contextWindow": context,
        "parameterCountB": params,
        "vramEstimateGb": _vram_estimate(params, model.get("quantization"), model_id),
        "recommendedProfile": "small" if purpose == "fast" else "balanced",
        "recommendedProtocol": recommended_protocol,
        "toolCallParserHint": _tool_call_parser_hint(model_id, recommended_protocol),
        "runtimeOptions": runtime_options,
        "deployable": runtime_options[0]["protocolId"] != "apiOnly",
        "apiOnly": runtime_options[0]["protocolId"] == "apiOnly",
        "source": source,
        "sourceUrl": MODELS_DEV_URL,
        "summary": model.get("description") or "Model metadata imported from the public models.dev catalog.",
        "license": model.get("license") or model.get("license_id") or "",
        "checksum": model.get("checksum") or model.get("sha") or "",
    }
    item["resourceManifest"] = resource_manifest.build_manifest(item)
    return item


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
            "toolCallParserHint": _tool_call_parser_hint(model["id"], protocol),
        }
        item["resourceManifest"] = resource_manifest.build_manifest(item)
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
    # Multi-GPU llama.cpp deployments shard layers across every visible card.
    # Catalog fit must use that aggregate capacity or a 12+16 GB machine is
    # incorrectly presented as a 16 GB machine.
    return sum(values) if values else None


def _fit_item(item, hardware=None):
    item = dict(item)
    # Cached catalogs created before parser hints were introduced still pass
    # through fit scoring on every read, so enrich them here as well as during
    # normalization. This makes the API change effective without a forced
    # network refresh or cache migration.
    if "toolCallParserHint" not in item:
        item["toolCallParserHint"] = _tool_call_parser_hint(
            item.get("modelId") or item.get("id"),
            item.get("recommendedProtocol"),
        )
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
    manifest = item.get("resourceManifest") or resource_manifest.build_manifest(item)
    item["resourceManifest"] = resource_manifest.attach_fit(
        manifest,
        score=score,
        label=label,
        available_vram_gb=available,
        headroom_gb=(available - float(vram)) if available and vram else None,
        basis="catalog-estimate",
        blocked_reasons=blocked,
    )
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


def _local_model_roots():
    """Folders Rasputin is allowed to treat as on-device model storage."""
    roots = []
    configured = os.environ.get("CONTAINER_MODELS_DIR")
    hf_cache = os.environ.get("RASPUTIN_HF_CACHE_DIR")
    llama_cache = os.environ.get("RASPUTIN_LLAMA_CACHE_DIR")
    host_hf_home = os.environ.get("HF_HOME")
    host_hub_cache = os.environ.get("HUGGINGFACE_HUB_CACHE") or os.environ.get("HF_HUB_CACHE")
    for candidate in [
        Path(configured).expanduser() if configured else None,
        Path(hf_cache).expanduser() / "hub" if hf_cache else None,
        Path(hf_cache).expanduser() if hf_cache else None,
        Path(llama_cache).expanduser() / "hub" if llama_cache else None,
        Path(llama_cache).expanduser() if llama_cache else None,
        Path(host_hub_cache).expanduser() if host_hub_cache else None,
        Path(host_hf_home).expanduser() / "hub" if host_hf_home else None,
        Path.home() / ".cache" / "huggingface" / "hub",
        Path(os.environ["LOCALAPPDATA"]) / "huggingface" / "hub" if os.environ.get("LOCALAPPDATA") else None,
        MODELS_DIR,
    ]:
        if not candidate:
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    return roots


def _directory_size(path):
    total = 0
    try:
        for child in path.rglob("*"):
            if child.is_file():
                total += child.stat().st_size
    except OSError:
        pass
    return total


def _has_readable_file(path):
    """Return whether a snapshot contains at least one accessible file."""
    try:
        for child in path.rglob("*"):
            try:
                if child.is_file():
                    return True
            except OSError:
                # Windows can expose dangling Hugging Face cache symlinks.
                # They are not complete local weights and should be skipped.
                continue
    except OSError:
        return False
    return False


def _local_item(model_id, name, path, protocol, source, size_bytes=0):
    params = _parameter_count(model_id, {"name": name})
    return {
        "id": f"local:{path}", "modelId": model_id, "name": name,
        "provider": "local storage", "providerId": "local",
        "purpose": _purpose(model_id, {"name": name}, "local"),
        "capabilities": ["local", "ready-to-deploy"], "contextWindow": None,
        "parameterCountB": params, "vramEstimateGb": _vram_estimate(params, model_id=f"{model_id} {name}"),
        "recommendedProfile": "balanced", "recommendedProtocol": protocol,
        "toolCallParserHint": _tool_call_parser_hint(model_id, protocol),
        "runtimeOptions": [{"protocolId": protocol, "label": f"Deploy with {protocol}"}],
        "deployable": True, "apiOnly": False, "source": source, "sourceUrl": "",
        "local": True, "localPath": str(path), "sizeBytes": size_bytes,
        "summary": "Saved on this computer. Deployment reuses the local weights without downloading them again.",
    }


def _local_items():
    """Inventory only persisted GGUF files and complete HF cache snapshots."""
    items, seen = [], set()
    for root in _local_model_roots():
        if not root.is_dir():
            continue
        for cache_dir in root.glob("models--*"):
            snapshots_dir = cache_dir / "snapshots"
            try:
                snapshots = [path for path in snapshots_dir.iterdir() if path.is_dir()]
            except OSError:
                snapshots = []
            if not snapshots:
                continue
            try:
                snapshot = max(snapshots, key=lambda path: path.stat().st_mtime)
            except OSError:
                continue
            if not _has_readable_file(snapshot):
                continue
            resolved = str(snapshot.resolve()).lower()
            if resolved in seen:
                continue
            seen.add(resolved)
            model_id = cache_dir.name.removeprefix("models--").replace("--", "/")
            items.append(_local_item(model_id, model_id.split("/")[-1], snapshot, "vllmCudaOpenai", "local-huggingface-cache", _directory_size(snapshot)))
        for gguf_path in root.rglob("*.gguf"):
            try:
                resolved = str(gguf_path.resolve()).lower()
                if resolved in seen:
                    continue
                seen.add(resolved)
                items.append(_local_item(gguf_path.name, gguf_path.stem, gguf_path, "llamaCppGgufServer", "local-gguf", gguf_path.stat().st_size))
            except OSError:
                continue
    return items


def _native_docker_cache_items():
    """Read the Docker wrapper's cache inventory when serving natively.

    Docker Desktop named volumes are intentionally not exposed as Windows
    paths. The native host therefore asks the running Docker wrapper to
    inventory its read-only cache, rather than copying model weights or
    treating a stopped container as a ready model.
    """
    if os.environ.get("RASPUTIN_NATIVE_DOCKER_CACHE") != "1":
        return []
    try:
        listed = subprocess.run(
            ["docker", "ps", "--filter", "label=com.docker.compose.service=rasputin-wrapper", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if listed.returncode != 0:
        return []
    script = "import json; from backend.models.catalog import _local_items; print(json.dumps(_local_items()))"

    def parse_items(text):
        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            return []
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict) and item.get("source") in {"local-huggingface-cache", "local-gguf"}]

    for container in (line.strip() for line in listed.stdout.splitlines()):
        if not container:
            continue
        try:
            result = subprocess.run(
                ["docker", "exec", container, "python", "-c", script],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                continue
            items = parse_items(result.stdout)
            if items:
                return items
        except (OSError, subprocess.TimeoutExpired):
            continue

    # Native/Electron can still be the only Rasputin host. In that case, use
    # the locally built wrapper image solely as a read-only volume inspector;
    # this does not start a server or modify the cache.
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm", "--mount",
                "type=volume,source=rasputin-huggingface-cache,target=/cache,readonly",
                "-e", "RASPUTIN_HF_CACHE_DIR=/cache", "--entrypoint", "python",
                os.environ.get("WRAPPER_SELF_IMAGE", "rasputin-wrapper:latest"), "-c", script,
            ],
            capture_output=True, text=True, timeout=45,
        )
        if result.returncode == 0:
            return parse_items(result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return []


def _command_value(command, option):
    """Return a Docker command option value without assuming argument order."""
    try:
        index = command.index(option)
    except (AttributeError, ValueError):
        return ""
    return str(command[index + 1]).strip() if index + 1 < len(command) else ""


def _scan_native_managed_container_items():
    """Inventory complete GGUFs retained by pre-cache-volume containers.

    Older llama.cpp deployments downloaded weights into the container writable
    layer. Those weights remain local after the container stops, but neither
    the host model folders nor the shared cache volumes can see them. Inspect
    only Rasputin-managed llama.cpp containers and require Docker's filesystem
    diff to prove the requested GGUF exists before exposing it in the catalog.
    """
    if os.environ.get("RASPUTIN_NATIVE_DOCKER_CACHE") != "1":
        return []
    try:
        listed = subprocess.run(
            [
                "docker", "ps", "-a",
                "--filter", "label=rasputin.managed=true",
                "--filter", "label=rasputin.protocol=llamaCppGgufServer",
                "--format", "{{.Names}}",
            ],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if listed.returncode != 0:
        return []

    items = []
    for container in (line.strip() for line in listed.stdout.splitlines()):
        if not container:
            continue
        try:
            inspected = subprocess.run(
                ["docker", "inspect", container],
                capture_output=True, text=True, timeout=10,
            )
            payload = json.loads(inspected.stdout) if inspected.returncode == 0 else []
            details = payload[0] if isinstance(payload, list) and payload else {}
            command = ((details.get("Config") or {}).get("Cmd") or [])
            repo = _command_value(command, "--hf-repo")
            filename = _command_value(command, "--hf-file")
            if not repo or not filename:
                continue
            changed = subprocess.run(
                ["docker", "diff", container],
                capture_output=True, text=True, timeout=20,
            )
            cache_key = f"models--{repo.replace('/', '--')}".lower()
            diff_text = changed.stdout.lower() if changed.returncode == 0 else ""
            if cache_key not in diff_text or filename.lower() not in diff_text:
                continue
            state = details.get("State") or {}
            item = _local_item(
                repo,
                Path(filename).stem,
                f"Docker container: {container}",
                "llamaCppGgufServer",
                "local-managed-container",
            )
            item.update({
                "id": f"container:{container}",
                "deployable": False,
                "containerBacked": True,
                "containerName": container,
                "containerStatus": str(state.get("Status") or "unknown"),
                "cachedArtifact": filename,
                "capabilities": ["local", "managed-container", "gguf"],
                "summary": "Saved inside an existing Rasputin llama.cpp container. The model is local, but redeploy it into the shared cache before replacing that container.",
            })
            items.append(item)
        except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
            continue
    return items


def _native_managed_container_items():
    """Return the legacy-container inventory without rescanning per request."""
    if os.environ.get("RASPUTIN_NATIVE_DOCKER_CACHE") != "1":
        return []
    now = time.monotonic()
    cached = _MANAGED_CONTAINER_CACHE
    if now - cached["updatedAt"] < MANAGED_CONTAINER_CACHE_TTL_SECONDS:
        return [dict(item) for item in cached["items"]]
    with _MANAGED_CONTAINER_CACHE_LOCK:
        now = time.monotonic()
        cached = _MANAGED_CONTAINER_CACHE
        if now - cached["updatedAt"] < MANAGED_CONTAINER_CACHE_TTL_SECONDS:
            return [dict(item) for item in cached["items"]]
        items = _scan_native_managed_container_items()
        _MANAGED_CONTAINER_CACHE["updatedAt"] = now
        _MANAGED_CONTAINER_CACHE["items"] = [dict(item) for item in items]
        return items


def _warsat_cache_items():
    """Return only Warsat models proven ready for immediate interaction.

    A cached artifact or a stale registry entry does not prove that the model
    will start within three minutes. To avoid overstating readiness, this view
    requires a running managed container and a healthy local endpoint.
    """
    try:
        from backend.models import registry
        registered = registry.all_models()
    except Exception:
        return []
    items = []
    for model in registered:
        runtime = str(model.get("runtime") or "")
        state = str(model.get("container_status") or "").lower()
        health = str(model.get("runtime_status") or "").lower()
        if (
            not model.get("managed")
            or not runtime.startswith("warsat-")
            # The registry reports a live Docker container as "running".
            # Older callers used the Docker CLI display value ("Up ..."),
            # so accept both representations while still requiring health.
            or (state not in {"running", "healthy"} and not state.startswith("up"))
            or health not in {"reachable", "healthy", "ready", "running"}
        ):
            continue
        protocol = {
            "warsat-vllm": "vllmCudaOpenai",
            "warsat-llama.cpp": "llamaCppGgufServer",
            "warsat-ollama": "ollamaOpenaiServer",
        }.get(runtime)
        model_id = str(model.get("model") or "").strip()
        if not protocol or not model_id:
            continue
        item = _local_item(model_id, str(model.get("name") or model_id), f"Docker cache: {model.get('container') or model.get('key')}", protocol, "local-warsat-cache")
        item["readyWithinThreeMinutes"] = True
        item["summary"] = "Running locally and health-checked. Ready to interact with now."
        items.append(item)
    return items


def local_catalog(hardware=None, include_runtime_cache=True):
    """Catalog of complete local weights, with running models marked ready now."""
    # A complete cache snapshot is safe to expose as locally deployable even
    # when it is not running. Running health-checked models replace the cache
    # entry for the same model and carry readyWithinThreeMinutes=True.
    # Shared cache entries intentionally win over legacy container-backed
    # entries with the same model id because they are safely redeployable.
    unfiltered = _local_items()
    if include_runtime_cache:
        unfiltered = _native_managed_container_items() + unfiltered + _native_docker_cache_items()
    deduped = {item["modelId"]: item for item in unfiltered}
    if include_runtime_cache:
        for item in _warsat_cache_items():
            deduped[item["modelId"]] = item
    items = _apply_fit(list(deduped.values()), hardware)
    return {
        "items": items, "count": len(items), "deployableCount": len(items),
        "categories": PURPOSES, "runtimes": RUNTIMES,
        "source": {"name": "local model cache", "status": "available", "error": "", "updatedAt": _now()},
    }


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
    # GGUF-only uploads (quant repos) have no transformers weights, so vLLM
    # can never load them — offering it just produces crash-looping deploys.
    library = str(hf_model.get("library_name") or "").lower()
    tag_blob = " ".join(str(tag).lower() for tag in tags)
    has_transformers_weights = (
        library == "transformers"
        or "safetensors" in tag_blob
        or "pytorch" in tag_blob
        or bool(architecture)
    )
    gguf_only = is_gguf and not has_transformers_weights
    runtime_options = []
    if is_gguf:
        runtime_options.append({"protocolId": "llamaCppGgufServer", "label": "Run GGUF with llama.cpp"})
    if has_open_weights and not gguf_only and purpose not in {"embeddings", "reranker"}:
        runtime_options.append({"protocolId": "vllmCudaOpenai", "label": "Run through vLLM"})
    if not runtime_options:
        runtime_options.append({"protocolId": "apiOnly", "label": "Register as provider API"})

    recommended_protocol = runtime_options[0]["protocolId"]
    item = {
        "id": model_id,
        "modelId": model_id,
        "name": model_id.split("/")[-1] if "/" in model_id else model_id,
        "provider": model_id.split("/")[0] if "/" in model_id else "huggingface",
        "providerId": "huggingface",
        "purpose": purpose,
        "capabilities": _capabilities(model_id, {"name": model_id, "tags": " ".join(tags)}, purpose),
        "contextWindow": None,
        "parameterCountB": params,
        "vramEstimateGb": _vram_estimate(params, quant, model_id),
        "recommendedProfile": "small" if purpose == "fast" else "balanced",
        "recommendedProtocol": recommended_protocol,
        "toolCallParserHint": _tool_call_parser_hint(model_id, recommended_protocol),
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
        "checksum": hf_model.get("sha") or hf_model.get("checksum") or "",
    }
    item["resourceManifest"] = resource_manifest.build_manifest(item)
    return item


_HF_REPO_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def normalize_hf_reference(value):
    """Return a canonical Hugging Face model id, or None for non-exact text.

    Accepted references are org/model and model URLs on the trusted
    huggingface.co hosts. Collection/revision suffixes are reduced to the
    model repository because the catalog API addresses model repositories,
    not individual files or revisions.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    explicit_scheme = "://" in raw
    host_url = raw.lower().startswith(("huggingface.co/", "www.huggingface.co/"))
    if explicit_scheme or host_url:
        parsed = urlparse(raw if explicit_scheme else f"https://{raw}")
        if parsed.scheme.lower() not in {"", "http", "https"}:
            return None
        host = (parsed.hostname or "").lower().rstrip(".")
        if host not in {"huggingface.co", "www.huggingface.co"}:
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return None
        repo_parts = parts[:2]
        if any(not _HF_REPO_PART.fullmatch(part) for part in repo_parts):
            return None
        if len(parts) == 2:
            return "/".join(repo_parts)
        if parts[2] not in {"tree", "blob"} or len(parts) < 4:
            return None
        return "/".join(repo_parts)

    candidate = raw.strip("/")
    parts = candidate.split("/")
    if len(parts) != 2 or any(not _HF_REPO_PART.fullmatch(part) for part in parts):
        return None
    return "/".join(parts)


def _looks_like_url(value):
    raw = str(value or "").strip()
    if not raw:
        return False
    return "://" in raw or raw.lower().startswith(("huggingface.co/", "www.huggingface.co/"))


def search_hf(
    query="", model_type="", sort="popular", direction=-1, limit=100,
    hardware=None, min_vram_gb=None, max_vram_gb=None,
):
    """Search Hugging Face Hub API for models."""
    original_query = "" if query is None else str(query)
    normalized_model_id = normalize_hf_reference(original_query)
    exact_match = bool(normalized_model_id)
    if _looks_like_url(original_query) and not exact_match:
        return {
            "items": [],
            "count": 0,
            "query": original_query,
            "modelType": model_type,
            "sort": sort or "popular",
            "source": "huggingface",
            "exactMatch": False,
            "normalizedModelId": "",
            "error": "Enter a Hugging Face model URL from huggingface.co.",
        }

    requested_sort = sort or "popular"
    if requested_sort == "popular":
        sort = "downloads"
    elif sort == "trending":
        sort = "trendingScore"
    elif sort in {"vram_desc", "vram_asc"}:
        sort = "downloads"
    limit = max(1, min(int(limit), 500))
    params = {
        "limit": min(limit, 100),
        "sort": sort or "downloads",
        "direction": str(direction),
    }
    if original_query:
        params["search"] = normalized_model_id or original_query
    if model_type:
        params["pipeline_tag"] = model_type

    raw_models = []
    try:
        with httpx.Client(timeout=HF_FETCH_TIMEOUT, follow_redirects=True) as client:
            url = HF_API_URL
            while url and len(raw_models) < limit:
                response = client.get(url, params=params)
                response.raise_for_status()
                batch = response.json()
                if not isinstance(batch, list) or not batch:
                    break
                raw_models.extend(batch)
                url = (response.links.get("next") or {}).get("url")
                params = None
    except Exception as exc:
        audit.log("hf_search_failed", {"query": original_query, "error": str(exc)})
        return {
            "items": [],
            "count": 0,
            "query": original_query,
            "exactMatch": False,
            "normalizedModelId": normalized_model_id or "",
            "error": str(exc),
            "source": "huggingface",
        }

    if not isinstance(raw_models, list):
        return {
            "items": [],
            "count": 0,
            "query": original_query,
            "exactMatch": False,
            "normalizedModelId": normalized_model_id or "",
            "error": "Unexpected HF API response format",
            "source": "huggingface",
        }

    items = [_normalize_hf_model(m) for m in raw_models[:limit]]

    def in_vram_range(item):
        estimate = item.get("vramEstimateGb")
        if min_vram_gb is not None and (estimate is None or float(estimate) < float(min_vram_gb)):
            return False
        if max_vram_gb is not None and (estimate is None or float(estimate) > float(max_vram_gb)):
            return False
        return True

    lookup = normalized_model_id
    if lookup and not any(i["id"].lower() == lookup.lower() for i in items):
        try:
            with httpx.Client(timeout=HF_FETCH_TIMEOUT, follow_redirects=True) as client:
                response = client.get(f"{HF_API_URL}/{lookup}")
                if response.status_code == 200:
                    exact = response.json()
                    if isinstance(exact, dict) and (exact.get("id") or exact.get("modelId")):
                        items.insert(0, _normalize_hf_model(exact))
        except Exception:
            pass

    if min_vram_gb is not None or max_vram_gb is not None:
        items = [item for item in items if in_vram_range(item)]

    if hardware:
        items = _apply_fit(items, hardware)

    if requested_sort in {"vram_desc", "vram_asc"}:
        items.sort(
            key=lambda item: float(item.get("vramEstimateGb") or (-1 if requested_sort == "vram_desc" else 10**9)),
            reverse=requested_sort == "vram_desc",
        )
    elif requested_sort in {"popular", "downloads"}:
        items.sort(key=lambda item: (
            -int(item.get("downloads") or 0),
            -int(item.get("likes") or 0),
            str(item.get("name") or item.get("id") or "").lower(),
        ))
    elif requested_sort == "likes":
        items.sort(key=lambda item: (
            -int(item.get("likes") or 0),
            -int(item.get("downloads") or 0),
            str(item.get("name") or item.get("id") or "").lower(),
        ))

    exact_not_found = False
    if lookup:
        idx = next((i for i, item in enumerate(items) if item["id"].lower() == lookup.lower()), None)
        if idx is None:
            items = []
            exact_not_found = True
        elif idx != 0:
            items.insert(0, items.pop(idx))

    audit.log("hf_search", {"query": original_query, "type": model_type, "count": len(items)})
    return {
        "items": items,
        "count": len(items),
        "query": original_query,
        "modelType": model_type,
        "sort": requested_sort,
        "source": "huggingface",
        "exactMatch": bool(lookup and not exact_not_found),
        "normalizedModelId": normalized_model_id or "",
        **({"error": f"Hugging Face model '{lookup}' was not found."} if exact_not_found else {}),
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
