import json
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MEMORY_FILE = DATA_DIR / "memory.json"

_lock = Lock()


def _blank():
    return {"prefs": {}, "facts": [], "sessions": []}


def load_memory():
    DATA_DIR.mkdir(exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text(json.dumps(_blank(), indent=2), encoding="utf-8")
    with _lock:
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return _blank()


def save_memory(data):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def remember(kind, value):
    mem = load_memory()
    if kind == "pref":
        if isinstance(value, dict):
            mem["prefs"].update(value)
    elif kind == "session":
        mem["sessions"].append(value)
        mem["sessions"] = mem["sessions"][-100:]
    else:
        mem["facts"].append(value)
        mem["facts"] = mem["facts"][-250:]
    save_memory(mem)
    return mem
