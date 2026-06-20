import json
import time
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_FILE = DATA_DIR / "audit.jsonl"
SECURITY_FILE = DATA_DIR / "security.json"

_lock = Lock()


def log(action, detail=None, actor="local-user"):
    DATA_DIR.mkdir(exist_ok=True)
    if not _audit_on():
        return {"skipped": True, "action": action}
    event = {
        "ts": time.time(),
        "actor": actor,
        "action": action,
        "detail": detail or {},
    }
    with _lock:
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    return event


from backend.core import runtime_store as store

def _audit_on():
    data = store.get_kv("security")
    if not data:
        return True
    return bool(data.get("audit_enabled", True))


def recent(limit=100):
    if not AUDIT_FILE.exists():
        return []
    with _lock:
        lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()[-max(1, min(int(limit), 500)):]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out
