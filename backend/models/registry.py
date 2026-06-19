import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse, urlunparse

from backend.core import audit as audit
from backend.models import providers as model_providers
from backend.models import secrets as model_secrets
from backend.core import security as security
from backend import workspace
from backend.core.response import AppError
from backend.warsat.providers import get_provider

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REGISTRY_FILE = DATA_DIR / "models.json"
MODEL_ROLES = ["main", "planner", "executor", "coder", "researcher", "summarizer", "memory", "embeddings", "helper", "test"]

_lock = Lock()


def _is_relative_to(child, parent):
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _model_library_roots():
    roots = []
    raw = os.environ.get("CONTAINER_MODELS_DIR")
    candidates = [Path(raw).expanduser() if raw else None, ROOT / "models"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        if resolved not in roots:
            roots.append(resolved)
    return roots


def _default_main_url():
    env_url = os.environ.get("MAIN_VLLM_BASE_URL")
    if env_url:
        return env_url
    if os.environ.get("WRAPPER_RUNTIME") == "docker":
        return "http://host.docker.internal:8000/v1"
    return "http://127.0.0.1:8000/v1"


def _runtime_base_url(base):
    if os.environ.get("WRAPPER_RUNTIME") != "docker":
        return base
    parsed = urlparse(base)
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost"}:
        return base
    netloc = "host.docker.internal"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def _defaults():
    return {
        "models": [
            {
                "key": "main-vllm",
                "name": "Main vLLM",
                "provider": "vllm",
                "role": "main",
                "base_url": _default_main_url(),
                "model": "local-main",
                "context_window": 1024,
                "max_tokens": 160,
                "enabled": True,
                "managed": False,
                "notes": "Your big vLLM container on port 8000.",
            },
            {
                "key": "dry-run",
                "name": "Dry Run",
                "provider": "mock",
                "role": "test",
                "base_url": "",
                "model": "no-model",
                "enabled": True,
                "managed": False,
                "notes": "No model call, just echoes prompts.",
            },
            {
                "key": "local-embeddings",
                "name": "Local Embeddings",
                "provider": "hash-vector",
                "role": "embeddings",
                "base_url": "",
                "model": "rasputin-local-hash-v1",
                "enabled": True,
                "managed": False,
                "notes": "Local deterministic retrieval vectors. No network calls.",
            },
        ]
    }


def _load():
    DATA_DIR.mkdir(exist_ok=True)
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text(json.dumps(_defaults(), indent=2), encoding="utf-8")
    with _lock:
        try:
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = _defaults()
    if "models" not in data:
        data = _defaults()
    defaults = _defaults()["models"]
    seen = {m.get("key") for m in data.get("models", [])}
    for model in defaults:
        if model.get("key") not in seen:
            data["models"].append(model)
    return data


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        REGISTRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _slug(text):
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "-", text).strip("-").lower()
    return text[:60] or "model"


def _normalize_base_url(base_url):
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ""
    if "://" not in base:
        base = f"http://{base}"
    parsed = urlparse(base)
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")]
    if path.endswith("/models"):
        path = path[: -len("/models")]
    if not path.endswith("/v1"):
        path = (path + "/v1").replace("//", "/")
    return urlunparse((parsed.scheme or "http", parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)).rstrip("/")


def _normalize_provider(provider):
    aliases = {
        "google": "gemini",
        "google-gemini": "gemini",
        "claude": "anthropic",
        "openai-compatible-api": "openai-compatible-remote",
    }
    value = str(provider or "openai-compatible").strip().lower()
    return aliases.get(value, value)


def _normalize_model_payload(model):
    out = {}
    for key, value in dict(model or {}).items():
        if value is None:
            continue
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key)).lower()
        out[normalized] = value
    return out


def _safe_file(path):
    target = Path(path).expanduser().resolve()
    if not target.exists() or not target.is_file():
        raise AppError("model_file_missing", "That GGUF path does not exist or is not visible to Rasputin.", 400)
    if target.suffix.lower() != ".gguf":
        raise AppError("model_file_type", "Expected a .gguf model file.", 400)
    allowed_roots = _model_library_roots()
    in_model_library = any(_is_relative_to(target, root) or target == root for root in allowed_roots)
    in_workspace = workspace.workspace_for_path(target) is not None
    if not in_model_library and not in_workspace:
        raise AppError(
            "model_file_outside_visible_roots",
            "GGUF files must be under the mounted models folder or an approved workspace.",
            403,
        )
    return target


def _gguf_already_imported(path):
    target = path.resolve()
    for model in _load().get("models", []):
        host_path = model.get("host_model_path")
        if not host_path:
            continue
        try:
            if Path(host_path).expanduser().resolve() == target:
                return model
        except Exception:
            continue
    return None


def _store_health(key, status, latency_ms=None, error=None, models=None):
    data = _load()
    changed = False
    for model in data["models"]:
        if model.get("key") != key:
            continue
        model["runtime_status"] = status
        model["last_checked_at"] = time.time()
        model["last_error"] = error or ""
        if latency_ms is not None:
            model["latency_ms"] = latency_ms
        if models is not None:
            model["discovered_models"] = models
        model["last_health"] = {
            "status": status,
            "latency_ms": latency_ms,
            "last_error": error or "",
            "models": models or [],
            "checked_at": model["last_checked_at"],
        }
        changed = True
        break
    if changed:
        _save(data)


def _http_error_payload(exc):
    try:
        raw = exc.read().decode("utf-8")
    except Exception:
        raw = ""
    message = raw.strip() or str(exc)
    try:
        body = json.loads(raw)
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                message = err.get("message") or message
            elif isinstance(err, str):
                message = err
            elif body.get("message"):
                message = body["message"]
    except Exception:
        body = None
    return {"status_code": getattr(exc, "code", None), "message": message, "body": body}


def _open_json(url, method="GET", payload=None, timeout=12):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8")
    return json.loads(raw)


def _parse_model_ids(payload):
    items = payload.get("data", payload) if isinstance(payload, dict) else payload
    ids = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
            elif isinstance(item, str):
                ids.append(item)
    return ids


def all_models():
    data = _load()
    out = []
    docker_allowed = security.load().get("allow_docker_control", False)
    for m in data["models"]:
        item = dict(m)
        item["url"] = chat_url(item)
        if item.get("managed"):
            if docker_allowed:
                try:
                    item["container_status"] = get_provider(item).status(item)
                except Exception:
                    item["container_status"] = "unknown"
                item["runtime_status"] = "reachable" if item["container_status"] == "running" else "stopped"
            else:
                item["container_status"] = "docker control disabled"
                item["runtime_status"] = item.get("runtime_status") or "unknown"
        elif item.get("provider") == "mock" or item.get("provider") == "hash-vector":
            item["runtime_status"] = "reachable"
        else:
            item["runtime_status"] = item.get("runtime_status") or "unknown"
        if model_providers.is_api_provider(item):
            item.update(model_secrets.public_state(item))
            item.pop("secret_ref", None)
        out.append(item)
    return out


def get_model(key):
    for m in _load()["models"]:
        if m.get("key") == key:
            return m
    return None


def enabled_models():
    return [m for m in all_models() if m.get("enabled", True)]


def roles():
    return MODEL_ROLES


def key_for_role(role, fallback="main-vllm"):
    role = str(role or "main")
    models = enabled_models()
    for model in models:
        if model.get("role") == role and model.get("runtime_status") in {"reachable", "unknown"}:
            return model.get("key")
    if role != "main":
        for model in models:
            if model.get("role") == "main" and model.get("runtime_status") in {"reachable", "unknown"}:
                return model.get("key")
    if get_model(fallback):
        return fallback
    return "dry-run"


def chat_url(model):
    if model_providers.is_api_provider(model):
        return model_providers.chat_url(model)
    base = _runtime_base_url((model.get("base_url") or "").rstrip("/"))
    if not base:
        return ""
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def models_url(model):
    if model_providers.is_api_provider(model):
        return model_providers.models_url(model)
    base = _runtime_base_url((model.get("base_url") or "").rstrip("/"))
    if not base:
        return ""
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    if base.endswith("/models"):
        return base
    return base + "/models"


def upsert(model):
    security.require("allow_model_registry_edit")
    model = _normalize_model_payload(model)
    api_key = str(model.pop("api_key", "") or "").strip()
    clear_api_key = bool(model.pop("clear_api_key", False))
    provider = _normalize_provider(model.get("provider"))
    model["provider"] = provider
    if provider in model_providers.API_PROVIDERS:
        model.setdefault("runtime", "remote-api")
        model.setdefault("model", model_providers.default_model(provider))
    base_url = model.get("base_url") or model_providers.default_base_url(provider)
    base_url = _normalize_base_url(base_url) if provider not in model_providers.NATIVE_API_PROVIDERS else str(base_url or "").strip().rstrip("/")
    if base_url:
        security.require_local_url(base_url)
        model["base_url"] = base_url
    data = _load()
    key = model.get("key") or _slug(model.get("name") or model.get("model") or "model")
    model["key"] = key
    if model.get("role") not in MODEL_ROLES:
        model["role"] = "helper"
    model.setdefault("provider", "openai-compatible")
    model.setdefault("runtime", "external-local")
    model.setdefault("enabled", True)
    model.setdefault("managed", False)
    if not model.get("name"):
        model["name"] = model.get("model") or key
    if model.get("context_window") in ("", None):
        model.pop("context_window", None)
    if model.get("max_tokens") in ("", None):
        model.pop("max_tokens", None)
    if api_key:
        model_secrets.set_api_key(key, api_key)
        model["secret_ref"] = f"model:{key}"
    elif clear_api_key:
        model_secrets.clear_api_key(key)
        model.pop("secret_ref", None)
    elif model_secrets.public_state({**model, "key": key}).get("has_api_key"):
        model["secret_ref"] = f"model:{key}"
    kept = [m for m in data["models"] if m.get("key") != key]
    kept.append(model)
    data["models"] = kept
    _save(data)
    audit.log("model_upsert", {"key": key, "provider": model.get("provider"), "managed": model.get("managed")})
    return model


PROTECTED_KEYS = {"dry-run", "local-embeddings"}


def delete_model(key):
    security.require("allow_model_registry_edit")
    if key in PROTECTED_KEYS:
        raise AppError("model_delete_protected", f"Cannot delete built-in model '{key}'.", 403)
    data = _load()
    model = None
    for m in data["models"]:
        if m.get("key") == key:
            model = m
            break
    if not model:
        raise AppError("model_missing", "Model is not registered.", 404)
    # Stop and remove container if managed
    if model.get("managed"):
        try:
            get_provider(model).rm(model)
        except Exception:
            pass
    # Clear API key if present
    try:
        model_secrets.clear_api_key(key)
    except Exception:
        pass
    data["models"] = [m for m in data["models"] if m.get("key") != key]
    _save(data)
    audit.log("model_delete", {"key": key, "name": model.get("name"), "provider": model.get("provider")})
    return {"deleted": True, "key": key, "name": model.get("name")}


def discover_model(key, require_permission=True):
    if require_permission:
        security.require("allow_model_tests")
    model = get_model(key)
    if not model:
        raise AppError("model_missing", "Model is not registered.", 404)
    if key == "dry-run" or model.get("provider") in {"mock", "hash-vector"}:
        result = {
            "key": key,
            "status": "reachable",
            "latency_ms": 0,
            "base_url": model.get("base_url", ""),
            "models_url": "",
            "current_model": model.get("model"),
            "models": [model.get("model")],
            "last_error": "",
        }
        _store_health(key, "reachable", 0, "", result["models"])
        return result

    url = models_url(model)
    if not url:
        _store_health(key, "unhealthy", error="No base URL configured.", models=[])
        return {
            "key": key,
            "status": "unhealthy",
            "latency_ms": None,
            "base_url": model.get("base_url", ""),
            "models_url": "",
            "current_model": model.get("model"),
            "models": [],
            "last_error": "No base URL configured.",
        }

    security.require_local_url(url)
    try:
        start = time.perf_counter()
        if model_providers.is_api_provider(model):
            ids = model_providers.discover_models(model)
        else:
            payload = _open_json(url, timeout=10)
            ids = _parse_model_ids(payload)
        latency_ms = round((time.perf_counter() - start) * 1000)
        status = "reachable" if ids else "unhealthy"
        error = "" if ids else "Endpoint responded but did not list any models."
        _store_health(key, status, latency_ms, error, ids)
        audit.log("model_discover", {"key": key, "url": url, "models": ids, "status": status})
        return {
            "key": key,
            "status": status,
            "latency_ms": latency_ms,
            "base_url": model.get("base_url", ""),
            "models_url": url,
            "current_model": model.get("model"),
            "models": ids,
            "last_error": error,
        }
    except urllib.error.HTTPError as exc:
        err = _http_error_payload(exc)
        message = f"HTTP {err['status_code']}: {err['message']}"
    except Exception as exc:
        message = str(exc)

    _store_health(key, "unhealthy", error=message, models=[])
    audit.log("model_discover_failed", {"key": key, "url": url, "error": message})
    return {
        "key": key,
        "status": "unhealthy",
        "latency_ms": None,
        "base_url": model.get("base_url", ""),
        "models_url": url,
        "current_model": model.get("model"),
        "models": [],
        "last_error": message,
    }


def repair_model(key):
    security.require("allow_model_registry_edit")
    model = get_model(key)
    if not model:
        raise AppError("model_missing", "Model is not registered.", 404)
    discovery = discover_model(key)
    ids = discovery.get("models") or []
    current = model.get("model")
    if current in ids:
        return {"repaired": False, "reason": "configured model already exists", "model": model, "discovery": discovery}
    if len(ids) != 1:
        reason = "no discovered models" if not ids else "multiple discovered models"
        return {"repaired": False, "reason": reason, "model": model, "discovery": discovery}

    replacement = ids[0]
    data = _load()
    updated = None
    for item in data["models"]:
        if item.get("key") == key:
            item["model"] = replacement
            item["repair_note"] = f"Auto-repaired from {current} to {replacement}."
            item["last_repaired_at"] = time.time()
            updated = dict(item)
            break
    if not updated:
        raise AppError("model_missing", "Model is not registered.", 404)
    _save(data)
    _store_health(key, discovery.get("status") or "reachable", discovery.get("latency_ms"), discovery.get("last_error"), ids)
    audit.log("model_repair", {"key": key, "from": current, "to": replacement})
    return {"repaired": True, "from": current, "to": replacement, "model": updated, "discovery": discovery}


def auto_repair_obvious():
    data = _load()
    candidates = [
        m for m in data.get("models", [])
        if m.get("enabled", True)
        and m.get("provider") not in {"mock", "hash-vector"}
        and not model_providers.is_api_provider(m)
        and (m.get("key") == "main-vllm" or m.get("role") == "main")
    ]
    results = []
    for model in candidates:
        key = model.get("key")
        current = model.get("model")
        try:
            discovery = discover_model(key, require_permission=False)
            ids = discovery.get("models") or []
            if current in ids:
                results.append({"key": key, "repaired": False, "reason": "already valid"})
                continue
            if len(ids) != 1:
                results.append({"key": key, "repaired": False, "reason": "no single safe replacement"})
                continue
            replacement = ids[0]
            fresh = _load()
            for item in fresh["models"]:
                if item.get("key") == key:
                    item["model"] = replacement
                    item["repair_note"] = f"Auto-repaired from {current} to {replacement}."
                    item["last_repaired_at"] = time.time()
                    break
            _save(fresh)
            _store_health(key, discovery.get("status") or "reachable", discovery.get("latency_ms"), discovery.get("last_error"), ids)
            audit.log("model_auto_repair", {"key": key, "from": current, "to": replacement})
            results.append({"key": key, "repaired": True, "from": current, "to": replacement})
        except Exception as exc:
            audit.log("model_auto_repair_failed", {"key": key, "error": str(exc)})
            results.append({"key": key, "repaired": False, "error": str(exc)})
    return results


def import_gguf(req):
    security.require("allow_model_registry_edit")
    file_path = _safe_file(req.get("path", ""))
    name = req.get("name") or file_path.stem
    key = req.get("key") or _slug(name)
    port = int(req.get("port") or next_port())
    container = req.get("container") or f"ai-{key}"
    model = {
        "key": key,
        "name": name,
        "provider": "llamacpp",
        "role": req.get("role") or "helper",
        "base_url": f"http://127.0.0.1:{port}/v1",
        "model": file_path.name,
        "enabled": True,
        "managed": True,
        "runtime": "docker-llamacpp",
        "container": container,
        "image": req.get("image") or "ghcr.io/ggml-org/llama.cpp:server",
        "port": port,
        "host_model_path": str(file_path),
        "context": int(req.get("context") or 4096),
        "n_gpu_layers": int(req.get("n_gpu_layers") if req.get("n_gpu_layers") is not None else 0),
        "notes": req.get("notes") or "Imported GGUF for llama.cpp server.",
    }
    out = upsert(model)
    audit.log("model_import_gguf", {"key": key, "path": str(file_path), "port": port})
    return out


def scan_gguf(root=None):
    security.require("allow_model_registry_edit")
    roots = _model_library_roots()
    if root:
        selected = Path(root).expanduser().resolve()
        if not any(_is_relative_to(selected, allowed) or selected == allowed for allowed in roots):
            raise AppError("model_scan_denied", "Rasputin can only scan the mounted models folder.", 403)
        roots = [selected]

    found = []
    for base in roots:
        if not base.exists() or not base.is_dir():
            continue
        try:
            files = sorted(base.rglob("*.gguf"))
        except Exception:
            files = []
        for file_path in files:
            if len(found) >= 200:
                break
            try:
                stat = file_path.stat()
            except Exception:
                continue
            imported = _gguf_already_imported(file_path)
            found.append({
                "name": file_path.stem,
                "path": str(file_path),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "imported": bool(imported),
                "imported_key": imported.get("key") if imported else "",
                "suggested_key": imported.get("key") if imported else _slug(file_path.stem),
                "suggested_role": "helper",
            })
    audit.log("model_scan_gguf", {"roots": [str(root) for root in roots], "count": len(found)})
    return {"roots": [str(root) for root in roots], "models": found, "count": len(found)}


def next_port():
    used = {int(m.get("port")) for m in _load()["models"] if str(m.get("port", "")).isdigit()}
    port = 8081
    while port in used:
        port += 1
    return port


def start_model(key):
    security.require("allow_docker_control")
    model = get_model(key)
    if not model:
        raise ValueError("model missing")
    if not model.get("managed"):
        return {"ok": False, "message": "external model, start it outside the wrapper"}
    try:
        provider = get_provider(model)
        result = provider.start(model)
        if result.get("ok"):
            audit.log("model_start", {"key": key, "container": model.get("container"), "port": model.get("port")})
        else:
            audit.log("model_start_failed", {"key": key, "error": result.get("error", "unknown error")})
        return result
    except Exception as exc:
        audit.log("model_start_failed", {"key": key, "error": str(exc)})
        return {"ok": False, "error": str(exc)}


def stop_model(key):
    security.require("allow_docker_control")
    model = get_model(key)
    if not model or not model.get("managed"):
        return {"ok": False, "message": "model is not managed"}
    try:
        provider = get_provider(model)
        result = provider.stop(model)
        audit.log("model_stop", {"key": key, "container": model.get("container")})
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def rm_model(key):
    security.require("allow_docker_control")
    model = get_model(key)
    if model and model.get("managed"):
        try:
            get_provider(model).rm(model)
        except Exception:
            pass


def test_model(key):
    security.require("allow_model_tests")
    model = get_model(key)
    if not model:
        return {"ok": False, "error": "model missing"}
    if key == "dry-run" or model.get("provider") in {"mock", "hash-vector"}:
        return {"ok": True, "status": "reachable", "latency_ms": 0, "message": f"{key} is local-only and available"}
    url = chat_url(model)
    security.require_local_url(url)
    try:
        start = time.perf_counter()
        if model_providers.is_api_provider(model):
            data = model_providers.chat_sync(model, [{"role": "user", "content": "Say ok."}], 8, 0)
        else:
            payload = {
                "model": model.get("model"),
                "messages": [{"role": "user", "content": "Say ok."}],
                "temperature": 0,
                "stream": False,
                "max_tokens": 8,
            }
            data = _open_json(url, method="POST", payload=payload, timeout=20)
        latency_ms = round((time.perf_counter() - start) * 1000)
    except urllib.error.HTTPError as exc:
        err = _http_error_payload(exc)
        discovery = discover_model(key, require_permission=False)
        models = discovery.get("models") or []
        message = err["message"]
        if err["status_code"] == 404 and models:
            available = "Available model" if len(models) == 1 else "Available models"
            message = f"Configured model {model.get('model')} was not found. {available}: {', '.join(models)}."
        _store_health(key, "unhealthy", error=message, models=models)
        audit.log("model_test_failed", {"key": key, "url": url, "status": err["status_code"], "error": message})
        return {"ok": False, "status": "unhealthy", "url": url, "error": message, "available_models": models}
    except Exception as exc:
        _store_health(key, "unhealthy", error=str(exc), models=[])
        audit.log("model_test_failed", {"key": key, "url": url, "error": str(exc)})
        return {"ok": False, "status": "unhealthy", "url": url, "error": str(exc), "available_models": []}
    _store_health(key, "reachable", latency_ms, "", [model.get("model")] if model.get("model") else [])
    audit.log("model_test", {"key": key, "url": url})
    return {"ok": True, "status": "reachable", "latency_ms": latency_ms, "url": url, "response": data}


def logs_model(key, limit=120):
    security.require("allow_docker_control")
    model = get_model(key)
    if not model or not model.get("managed"):
        return {"ok": False, "message": "model is not managed", "logs": ""}
    try:
        return get_provider(model).logs(model, limit)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "logs": ""}
