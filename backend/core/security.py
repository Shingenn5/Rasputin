import json
import os
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

from backend.core import runtime_store as store
from backend.core.datadir import data_dir

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = data_dir()
SECURITY_FILE = DATA_DIR / "security.json"

_lock = Lock()


def _desktop_only():
    return str(os.environ.get("RASPUTIN_DESKTOP_ONLY", "")).strip().lower() in {"1", "true", "yes", "on"}


def _snake_key(key):
    out = []
    for char in str(key or ""):
        if char.isupper():
            out.append("_")
            out.append(char.lower())
        else:
            out.append(char)
    return "".join(out).lstrip("_")


def _normalize(data):
    return {_snake_key(k): v for k, v in (data or {}).items()}


def defaults():
    return {
        "privacy_lock": True,
        "offline_lock": False,
        "allow_file_read": True,
        "allow_file_write": True,
        "allow_file_reorganize": False,
        "allow_shell_execution": False,
        "allow_web_search": True,
        "allow_github_read": False,
        "allow_docker_control": False,
        "allow_model_tests": True,
        "allow_model_registry_edit": True,
        "allow_remote_models": False,
        "unattended_mode": False,
        "approval_required_file_write": True,
        "approval_required_file_move": True,
        "approval_required_web_search": True,
        "web_search_max_chars": 180,
        "audit_enabled": True,
        "notes": "Rasputin keeps model endpoints local. Web search is brokered and query-guarded.",
    }


def load():
    data = store.get_kv("security")
    if not isinstance(data, dict):
        DATA_DIR.mkdir(exist_ok=True)
        if SECURITY_FILE.exists():
            with _lock:
                try:
                    data = json.loads(SECURITY_FILE.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
        else:
            data = {}
        store.set_kv("security", data)
        
    merged = defaults()
    merged.update(data)
    if _desktop_only():
        # A desktop install may inherit server-era persisted settings. Docker
        # authority is a launch-mode invariant, not a user preference.
        merged["allow_docker_control"] = False
    return merged


def save(data):
    merged = defaults()
    merged.update(_normalize(data))
    if _desktop_only():
        merged["allow_docker_control"] = False
    with _lock:
        store.set_kv("security", merged)
    return merged


def require(flag):
    cfg = load()
    if not cfg.get(flag):
        raise PermissionError(f"{flag} is disabled")
    return True


def unattended_enabled(cfg=None):
    """Return whether the runtime is operating without a human in the loop.

    An explicit environment override is useful for a dedicated unattended
    process; otherwise the persisted administrator setting is authoritative.
    The default remains off so existing interactive installations keep their
    current behavior until the operator opts in.
    """

    raw = os.environ.get("RASPUTIN_UNATTENDED")
    if raw is not None:
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    return bool((cfg or load()).get("unattended_mode", False))


def is_local_url(url):
    if not url:
        return True
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}


def require_local_url(url):
    cfg = load()
    if cfg.get("privacy_lock", True) and not is_local_url(url):
        raise PermissionError("privacy_lock blocks non-local model endpoint")
    if not cfg.get("allow_remote_models") and not is_local_url(url):
        raise PermissionError("remote model endpoints are disabled")
    return True


def offline_status():
    cfg = load()
    return {
        "privacy_lock": cfg.get("privacy_lock", True),
        "offline_lock": cfg.get("offline_lock", False),
        "web_search_blocked": not cfg.get("allow_web_search", False),
        "remote_models_blocked": not cfg.get("allow_remote_models", False),
        "docker_control_blocked": not cfg.get("allow_docker_control", False),
        "unattended_mode": unattended_enabled(cfg),
    }
