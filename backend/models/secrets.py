import json
import os
from pathlib import Path
from threading import Lock

from backend.core.datadir import data_dir

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = data_dir()
SECRETS_FILE = DATA_DIR / "model_secrets.json"

DEFAULT_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

_lock = Lock()


def _provider(model):
    return str((model or {}).get("provider") or "").strip().lower()


from backend.core import runtime_store as store

def _load():
    data = store.get_kv("model_secrets")
    if not isinstance(data, dict):
        DATA_DIR.mkdir(exist_ok=True)
        if SECRETS_FILE.exists():
            with _lock:
                try:
                    data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
                except Exception:
                    data = {"models": {}}
        else:
            data = {"models": {}}
        store.set_kv("model_secrets", data)
    if "models" not in data:
        data = {"models": {}}
    return data


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        store.set_kv("model_secrets", data)


def set_api_key(model_key, api_key):
    key = str(model_key or "").strip()
    value = str(api_key or "").strip()
    if not key or not value:
        return False
    data = _load()
    data.setdefault("models", {})[key] = {"api_key": value}
    _save(data)
    return True


def clear_api_key(model_key):
    data = _load()
    removed = data.setdefault("models", {}).pop(str(model_key or ""), None)
    if removed is not None:
        _save(data)
    return removed is not None


def api_key_for(model):
    model = model or {}
    provider = _provider(model)
    configured_env = str(model.get("api_key_env") or "").strip()
    env_name = configured_env or DEFAULT_ENV.get(provider, "")
    if env_name and os.environ.get(env_name):
        return os.environ[env_name], f"env:{env_name}"
    key = str(model.get("key") or "").strip()
    stored = _load().get("models", {}).get(key, {}).get("api_key", "") if key else ""
    if stored:
        return stored, "stored"
    return "", ""


def public_state(model):
    api_key, source = api_key_for(model)
    return {
        "has_api_key": bool(api_key),
        "api_key_source": source,
    }
