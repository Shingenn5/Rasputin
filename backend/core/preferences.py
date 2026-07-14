from pathlib import Path
from threading import Lock

from backend.core import runtime_store as store
from backend.core.datadir import data_dir

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = data_dir()
PREFERENCES_FILE = DATA_DIR / "preferences.json"
PREFERENCES_KEY = "userPreferences"

_lock = Lock()

THEMES = {
    "rasputin-light",
    "rasputin-dark",
    "contrast",
    "bootswatch-slate",
    "bootswatch-cyborg",
    "bootswatch-darkly",
    "bootswatch-lux",
    "bootswatch-solar",
    "bootswatch-superhero",
}


def defaults():
    return {
        "theme": "rasputin-light",
        "motionMode": "full",
        "sidebarCollapsed": False,
        "selectedModel": "",
        "testingMode": False,
        "activeWorkspace": ".",
        "skill": "general",
        "taskMode": "chat",
        "reasoning": "auto",
        "modeModelOverrides": {},
        "subagents": 0,
        "workspaceExplorer": {},
        "activeView": "home",
        "activeSettingsSection": "general",
        "activeChatFolder": "all",
    }


def _coerce(data):
    merged = defaults()
    if isinstance(data, dict):
        merged.update({k: data.get(k, v) for k, v in merged.items()})
    if merged["theme"] not in THEMES:
        merged["theme"] = "rasputin-light"
    if merged["motionMode"] not in {"full", "reduced"}:
        merged["motionMode"] = "full"
    if merged["activeView"] not in {"home", "workspaces", "activity", "agents", "sessions", "tasks", "approvals", "memory", "skills", "telegram", "schedules", "models", "warsat", "settings", "audit"}:
        merged["activeView"] = "home"
    if merged["activeSettingsSection"] not in {"general", "workspaces", "accounts", "safety", "knowledge", "output", "appearance", "admin"}:
        merged["activeSettingsSection"] = "general"
    try:
        merged["subagents"] = max(0, min(int(merged["subagents"]), 4))
    except Exception:
        merged["subagents"] = 0
    if not isinstance(merged.get("modeModelOverrides"), dict):
        merged["modeModelOverrides"] = {}
    if not isinstance(merged.get("workspaceExplorer"), dict):
        merged["workspaceExplorer"] = {}
    if not isinstance(merged.get("activeChatFolder"), str):
        merged["activeChatFolder"] = "all"
    if merged.get("reasoning") not in {"auto", "off", "low", "medium", "high"}:
        merged["reasoning"] = "auto"
    merged["sidebarCollapsed"] = bool(merged["sidebarCollapsed"])
    # The dry-run mock model is only selectable while testing mode is on;
    # never resurrect it from stored preferences otherwise.
    if not merged["testingMode"] and merged["selectedModel"] == "dry-run":
        merged["selectedModel"] = ""
    return merged


def _key(username):
    return f"{PREFERENCES_KEY}:{str(username or 'admin').strip() or 'admin'}"


def load(username="admin"):
    key = _key(username)
    data = store.get_kv(key)
    if isinstance(data, dict):
        return _coerce(data)

    # Existing installations had one global preference document. The original
    # administrator inherits it; every later account starts from safe defaults.
    if username == "admin":
        legacy_kv = store.get_kv(PREFERENCES_KEY)
        if isinstance(legacy_kv, dict):
            data = _coerce(legacy_kv)
            store.set_kv(key, data)
            return data

    legacy = _load_legacy_json()
    data = _coerce(legacy or defaults())
    store.set_kv(key, data)
    return data


def save(payload, username="admin"):
    current = load(username)
    if isinstance(payload, dict):
        current.update({k: payload[k] for k in defaults() if k in payload})
    data = _coerce(current)
    with _lock:
        store.set_kv(_key(username), data)
        # Keep the legacy compatibility view current on single-user installs.
        # It is no longer read once multiple accounts exist.
        try:
            from backend.core import auth
            if auth.load_public().get("user_count", 1) == 1:
                store.set_kv(PREFERENCES_KEY, data)
        except Exception:
            pass
    return data


def _load_legacy_json():
    return None
