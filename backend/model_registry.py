import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse, urlunparse

from . import audit
from . import security

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REGISTRY_FILE = DATA_DIR / "models.json"

_lock = Lock()


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


def _safe_file(path):
    target = Path(path).expanduser().resolve()
    if not target.exists() or not target.is_file():
        raise ValueError("model file missing")
    if target.suffix.lower() != ".gguf":
        raise ValueError("expected a .gguf file")
    return target


def all_models():
    data = _load()
    out = []
    for m in data["models"]:
        item = dict(m)
        item["url"] = chat_url(item)
        if item.get("managed"):
            item["container_status"] = container_status(item)
            item["runtime_status"] = "reachable" if item["container_status"] == "running" else "stopped"
        elif item.get("provider") == "mock" or item.get("provider") == "hash-vector":
            item["runtime_status"] = "reachable"
        else:
            item["runtime_status"] = "unknown"
        out.append(item)
    return out


def get_model(key):
    for m in _load()["models"]:
        if m.get("key") == key:
            return m
    return None


def enabled_models():
    return [m for m in all_models() if m.get("enabled", True)]


def chat_url(model):
    base = _runtime_base_url((model.get("base_url") or "").rstrip("/"))
    if not base:
        return ""
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def upsert(model):
    security.require("allow_model_registry_edit")
    base_url = model.get("base_url") or ""
    if base_url:
        security.require_local_url(base_url)
    data = _load()
    key = model.get("key") or _slug(model.get("name") or model.get("model") or "model")
    model["key"] = key
    model.setdefault("enabled", True)
    model.setdefault("managed", False)
    kept = [m for m in data["models"] if m.get("key") != key]
    kept.append(model)
    data["models"] = kept
    _save(data)
    audit.log("model_upsert", {"key": key, "provider": model.get("provider"), "managed": model.get("managed")})
    return model


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


def next_port():
    used = {int(m.get("port")) for m in _load()["models"] if str(m.get("port", "")).isdigit()}
    port = 8081
    while port in used:
        port += 1
    return port


def docker_args(model):
    if model.get("runtime") != "docker-llamacpp":
        raise ValueError("model is not a managed llama.cpp entry")
    file_path = _safe_file(model.get("host_model_path", ""))
    parent = str(file_path.parent)
    cmd = [
        "docker", "run", "-d",
        "--name", model.get("container") or f"ai-{model['key']}",
        "-p", f"127.0.0.1:{int(model.get('port', 8081))}:8080",
        "--security-opt", "no-new-privileges",
        "-v", f"{parent}:/models:ro",
        model.get("image") or "ghcr.io/ggml-org/llama.cpp:server",
        "-m", f"/models/{file_path.name}",
        "--host", "0.0.0.0",
        "--port", "8080",
        "-c", str(int(model.get("context", 4096))),
    ]
    gpu_layers = int(model.get("n_gpu_layers", 0))
    if gpu_layers:
        cmd.extend(["--n-gpu-layers", str(gpu_layers)])
    return cmd


def start_model(key):
    security.require("allow_docker_control")
    model = get_model(key)
    if not model:
        raise ValueError("model missing")
    if not model.get("managed"):
        return {"ok": False, "message": "external model, start it outside the wrapper"}
    status = container_status(model)
    if status == "running":
        return {"ok": True, "status": status, "message": "already running"}
    rm_model(key)
    cmd = docker_args(model)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        audit.log("model_start_failed", {"key": key, "error": proc.stderr.strip() or proc.stdout.strip()})
        return {"ok": False, "cmd": cmd, "error": proc.stderr.strip() or proc.stdout.strip()}
    audit.log("model_start", {"key": key, "container": model.get("container"), "port": model.get("port")})
    return {"ok": True, "container_id": proc.stdout.strip(), "cmd": cmd}


def stop_model(key):
    security.require("allow_docker_control")
    model = get_model(key)
    if not model or not model.get("managed"):
        return {"ok": False, "message": "model is not managed"}
    name = model.get("container")
    subprocess.run(["docker", "stop", name], capture_output=True, text=True, timeout=20)
    subprocess.run(["docker", "rm", name], capture_output=True, text=True, timeout=20)
    audit.log("model_stop", {"key": key, "container": name})
    return {"ok": True, "status": container_status(model)}


def rm_model(key):
    security.require("allow_docker_control")
    model = get_model(key)
    if model and model.get("managed") and model.get("container"):
        subprocess.run(["docker", "rm", "-f", model["container"]], capture_output=True, text=True, timeout=20)


def container_status(model):
    name = model.get("container")
    if not name:
        return "external"
    try:
        proc = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return "unknown"
    text = proc.stdout.strip().lower()
    if not text:
        return "stopped"
    if text.startswith("up"):
        return "running"
    return text


def test_model(key):
    security.require("allow_model_tests")
    model = get_model(key)
    if not model:
        return {"ok": False, "error": "model missing"}
    if key == "dry-run" or model.get("provider") in {"mock", "hash-vector"}:
        return {"ok": True, "status": "reachable", "latency_ms": 0, "message": f"{key} is local-only and available"}
    url = chat_url(model)
    security.require_local_url(url)
    payload = {
        "model": model.get("model"),
        "messages": [{"role": "user", "content": "Say ok."}],
        "temperature": 0,
        "stream": False,
        "max_tokens": 8,
    }
    try:
        start = time.perf_counter()
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
        latency_ms = round((time.perf_counter() - start) * 1000)
        data = json.loads(raw)
    except Exception as exc:
        audit.log("model_test_failed", {"key": key, "url": url, "error": str(exc)})
        return {"ok": False, "url": url, "error": str(exc)}
    audit.log("model_test", {"key": key, "url": url})
    return {"ok": True, "status": "reachable", "latency_ms": latency_ms, "url": url, "response": data}


def logs_model(key, limit=120):
    model = get_model(key)
    if not model or not model.get("managed"):
        return {"ok": False, "message": "model is not managed", "logs": ""}
    name = model.get("container")
    try:
        proc = subprocess.run(["docker", "logs", "--tail", str(max(1, min(int(limit), 500))), name], capture_output=True, text=True, timeout=15)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "logs": ""}
    return {"ok": proc.returncode == 0, "logs": proc.stdout + proc.stderr}
