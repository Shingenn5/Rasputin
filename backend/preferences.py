import json
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PREFERENCES_FILE = DATA_DIR / "preferences.json"

_lock = Lock()


def defaults():
    return {
        "theme": "rasputin-light",
        "sidebarCollapsed": False,
        "selectedModel": "dry-run",
        "testingMode": False,
        "activeWorkspace": ".",
        "skill": "general",
        "taskMode": "chat",
        "modeModelOverrides": {},
        "subagents": 0,
        "workspaceExplorer": {},
        "activeView": "home",
        "activeSettingsSection": "general",
    }


def _coerce(data):
    merged = defaults()
    if isinstance(data, dict):
        merged.update({k: data.get(k, v) for k, v in merged.items()})
    if merged["theme"] not in {"rasputin-light", "rasputin-dark", "contrast"}:
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
    merged["sidebarCollapsed"] = bool(merged["sidebarCollapsed"])
    return merged


def load():
    DATA_DIR.mkdir(exist_ok=True)
    if not PREFERENCES_FILE.exists():
        save(defaults())
    with _lock:
        try:
            data = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = defaults()
    return _coerce(data)


def save(payload):
    DATA_DIR.mkdir(exist_ok=True)
    current = defaults()
    if PREFERENCES_FILE.exists():
        try:
            current.update(json.loads(PREFERENCES_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    if isinstance(payload, dict):
        current.update({k: payload[k] for k in defaults() if k in payload})
    data = _coerce(current)
    with _lock:
        PREFERENCES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
