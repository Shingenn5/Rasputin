import json
import re
import time
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "output.json"

_lock = Lock()


def _blank():
    return {"markdown_folder": "workspace/markdown-output"}


from backend.core import runtime_store as store

def _load():
    data = store.get_kv("output")
    if not isinstance(data, dict):
        DATA_DIR.mkdir(exist_ok=True)
        if OUTPUT_FILE.exists():
            with _lock:
                try:
                    data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
        else:
            data = {}
        store.set_kv("output", data)
    base = _blank()
    base.update(data or {})
    return base


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        store.set_kv("output", data)


def _safe_path(path="."):
    target = (ROOT / (path or ".")).resolve()
    if ROOT not in target.parents and target != ROOT:
        raise ValueError("output folder outside safe root")
    return target


def _rel(path):
    target = _safe_path(path)
    if target == ROOT:
        return "."
    return str(target.relative_to(ROOT)).replace("\\", "/")


def get_config():
    data = _load()
    target = _safe_path(data.get("markdown_folder"))
    return {
        "markdown_folder": _rel(target),
        "absolute_path": str(target),
    }


def save_config(data):
    payload = data or {}
    target = _safe_path(payload.get("markdownFolder") or payload.get("markdown_folder", "workspace/markdown-output"))
    target.mkdir(parents=True, exist_ok=True)
    out = {"markdown_folder": _rel(target)}
    _save(out)
    return get_config()


def _slug(text):
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "-", text or "").strip("-").lower()
    return text[:64] or "task"


def export_markdown(task, folder=None):
    if not task:
        raise ValueError("task missing")
    cfg = _load()
    target = _safe_path(folder or cfg.get("markdown_folder"))
    target.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"{stamp}-{_slug(task.get('objective'))}.md"
    path = target / filename
    lines = [
        f"# {task.get('objective') or 'Task'}",
        "",
        f"- Status: {task.get('status', '')}",
        f"- Model: {task.get('model', '')}",
        f"- Skill: {task.get('skill', '')}",
        f"- Workspace: {task.get('workspace', '')}",
        "",
        "## Result",
        "",
        task.get("result") or "",
        "",
        "## Sources",
        "",
    ]
    sources = task.get("sources") or []
    if sources:
        for src in sources:
            lines.append(f"- {src.get('source')}#{src.get('chunk')} score={src.get('score')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Logs", ""])
    for log in task.get("logs") or []:
        lines.append(f"- {log}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"ok": True, "path": _rel(path), "absolute_path": str(path)}
