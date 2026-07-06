from pathlib import Path
from threading import Lock

from backend.core import runtime_store as store

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
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
    if merged["activeView"] not in {"home", "workspaces", "activity", "agents", "sessions", "tasks", "approvals", "memory", "skills", "telegram", "schedules", "models", "warsat", "settings", "audit"}:
        merged["activeView"] = "home"
    if merged["activeSettingsSection"] not in {"general", "workspaces", "safety", "knowledge", "output", "appearance", "admin"}:
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


def load():
    data = store.get_kv(PREFERENCES_KEY)
    if isinstance(data, dict):
        return _coerce(data)

    legacy = _load_legacy_json()
    data = _coerce(legacy or defaults())
    store.set_kv(PREFERENCES_KEY, data)
    return data


def save(payload):
    current = load()
    if isinstance(payload, dict):
        current.update({k: payload[k] for k in defaults() if k in payload})
    data = _coerce(current)
    with _lock:
        store.set_kv(PREFERENCES_KEY, data)
    return data


def _load_legacy_json():
    return None
