import json
import re
import time
from pathlib import Path
from threading import Lock

from . import output
from . import runtime_store as store

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARCHIVE_FILE = DATA_DIR / "archive_sessions.json"
_lock = Lock()


def _blank():
    return {"sessions": []}


def _load():
    DATA_DIR.mkdir(exist_ok=True)
    if not ARCHIVE_FILE.exists():
        ARCHIVE_FILE.write_text(json.dumps(_blank(), indent=2), encoding="utf-8")
    with _lock:
        try:
            data = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = _blank()
    if "sessions" not in data:
        data = _blank()
    return data


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        ARCHIVE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _slug(text):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(text or "")).strip("-").lower()[:64] or "archive"


def sessions():
    data = _load()
    return {"sessions": sorted(data.get("sessions", []), key=lambda item: item.get("updated_at", 0), reverse=True)}


def save_session(payload):
    payload = payload or {}
    stamp = time.time()
    session_id = payload.get("id") or store.new_id("arch")
    title = str(payload.get("title") or "Untitled archive draft").strip()[:160]
    content = str(payload.get("content") or "")
    session = {
        "id": session_id,
        "title": title,
        "content": content,
        "format": "markdown",
        "created_at": stamp,
        "updated_at": stamp,
        "word_count": len([word for word in re.split(r"\s+", content.strip()) if word]),
    }
    data = _load()
    existing = next((item for item in data.get("sessions", []) if item.get("id") == session_id), None)
    if existing:
        session["created_at"] = existing.get("created_at") or stamp
    data["sessions"] = [item for item in data.get("sessions", []) if item.get("id") != session_id] + [session]
    _save(data)
    return session


def export_session(session_id, folder=None):
    data = _load()
    session = next((item for item in data.get("sessions", []) if item.get("id") == session_id), None)
    if not session:
        raise ValueError("archive session missing")
    cfg = output.get_config()
    target = output._safe_path(folder or cfg.get("markdownFolder") or cfg.get("markdown_folder"))
    target.mkdir(parents=True, exist_ok=True)
    filename = f"{time.strftime('%Y%m%d-%H%M%S')}-{_slug(session.get('title'))}.md"
    path = target / filename
    path.write_text(session.get("content") or "", encoding="utf-8")
    return {"path": output._rel(path), "absolute_path": str(path), "title": session.get("title")}
