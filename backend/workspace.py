import json
import re
import time
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WORKSPACE_FILE = DATA_DIR / "workspace.json"

_lock = Lock()


def _slug(text):
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "-", text or "").strip("-").lower()
    return text[:64] or "workspace"


def _blank():
    return {
        "active_id": "project-root",
        "workspaces": [
            {
                "id": "project-root",
                "name": "Project Root",
                "root": ".",
                "permission_profile": {"read": True, "write": True, "reorganize": False},
                "indexed": False,
                "last_used": None,
            }
        ],
    }


def _load():
    DATA_DIR.mkdir(exist_ok=True)
    if not WORKSPACE_FILE.exists():
        WORKSPACE_FILE.write_text(json.dumps(_blank(), indent=2), encoding="utf-8")
    with _lock:
        try:
            data = json.loads(WORKSPACE_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = _blank()
    if "active_path" in data and "workspaces" not in data:
        root = data.get("active_path") or "."
        data = _blank()
        data["workspaces"][0]["root"] = root
    if "workspaces" not in data:
        data = _blank()
    return data


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        WORKSPACE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _root_from_value(value):
    raw = str(value or ".")
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (ROOT / raw).resolve()


def _stored_root(path):
    target = Path(path).expanduser().resolve()
    if target == ROOT:
        return "."
    if ROOT in target.parents:
        return str(target.relative_to(ROOT)).replace("\\", "/")
    return str(target)


def _abs(item):
    return _root_from_value(item.get("root") or ".")


def _public_item(item):
    root = _abs(item)
    return {
        "id": item.get("id"),
        "name": item.get("name") or item.get("id"),
        "root": item.get("root") or ".",
        "absolute_path": str(root),
        "permission_profile": item.get("permission_profile", {}),
        "indexed": bool(item.get("indexed", False)),
        "last_used": item.get("last_used"),
    }


def all_workspaces():
    data = _load()
    return {
        "active_id": data.get("active_id", "project-root"),
        "workspaces": [_public_item(w) for w in data.get("workspaces", [])],
    }


def _find(ref=None):
    data = _load()
    ref = str(ref or data.get("active_id") or "project-root")
    target = _root_from_value(ref)
    for item in data.get("workspaces", []):
        root = _abs(item)
        if ref == item.get("id") or ref == item.get("root") or target == root:
            return data, item
    if ref in {".", ""}:
        for item in data.get("workspaces", []):
            if item.get("id") == data.get("active_id"):
                return data, item
    raise ValueError("workspace is not approved")


def workspace_for_path(path):
    target = _root_from_value(path)
    data = _load()
    matches = []
    for item in data.get("workspaces", []):
        root = _abs(item)
        if target == root or root in target.parents:
            matches.append((len(str(root)), item))
    if not matches:
        return None
    return sorted(matches, key=lambda x: x[0], reverse=True)[0][1]


def resolve_path(path="."):
    if path in {None, "", "."}:
        _, item = _find()
        return _abs(item)
    try:
        _, item = _find(path)
        return _abs(item)
    except ValueError:
        target = _root_from_value(path)
        item = workspace_for_path(target)
        if not item:
            raise
        return target


def rel_path(path):
    target = _root_from_value(path)
    if target == ROOT:
        return "."
    if ROOT in target.parents:
        return str(target.relative_to(ROOT)).replace("\\", "/")
    return str(target)


def get_active():
    data = _load()
    active_id = data.get("active_id") or "project-root"
    item = next((w for w in data.get("workspaces", []) if w.get("id") == active_id), data.get("workspaces", [])[0])
    root = _abs(item)
    return {
        "active_id": item.get("id"),
        "active_path": item.get("root") or ".",
        "active_name": item.get("name") or item.get("id"),
        "absolute_path": str(root),
        "root": str(ROOT),
        "workspaces": [_public_item(w) for w in data.get("workspaces", [])],
    }


def add(path=".", name=None, permission_profile=None):
    target = _root_from_value(path)
    if not target.exists() or not target.is_dir():
        raise ValueError("workspace must be an existing folder")
    data = _load()
    existing = workspace_for_path(target)
    if existing and _abs(existing) == target:
        return _public_item(existing)
    base_id = _slug(name or target.name or "workspace")
    used = {w.get("id") for w in data.get("workspaces", [])}
    wid = base_id
    n = 2
    while wid in used:
        wid = f"{base_id}-{n}"
        n += 1
    item = {
        "id": wid,
        "name": name or target.name or "Workspace",
        "root": _stored_root(target),
        "permission_profile": permission_profile or {"read": True, "write": True, "reorganize": False},
        "indexed": False,
        "last_used": None,
    }
    data.setdefault("workspaces", []).append(item)
    _save(data)
    return _public_item(item)


def select(path):
    data = _load()
    try:
        _, item = _find(path)
    except ValueError:
        add(path)
        data = _load()
        _, item = _find(path)
    item["last_used"] = time.time()
    data["active_id"] = item.get("id")
    _save(data)
    return get_active()


def remove(workspace_id):
    data = _load()
    if workspace_id == "project-root":
        raise ValueError("project-root cannot be removed")
    kept = [w for w in data.get("workspaces", []) if w.get("id") != workspace_id]
    if len(kept) == len(data.get("workspaces", [])):
        raise ValueError("workspace missing")
    data["workspaces"] = kept
    if data.get("active_id") == workspace_id:
        data["active_id"] = "project-root"
    _save(data)
    return all_workspaces()


def mark_indexed(workspace_ref=None, indexed=True):
    data, item = _find(workspace_ref)
    item["indexed"] = bool(indexed)
    _save(data)
    return _public_item(item)


def _safe_child(target):
    item = workspace_for_path(target)
    if not item:
        raise ValueError("path outside approved workspaces")
    root = _abs(item)
    if root not in target.parents and target != root:
        raise ValueError("path outside approved workspace")
    return item, root


def list_dirs(path="."):
    target = resolve_path(path)
    if not target.exists() or not target.is_dir():
        raise ValueError("folder missing")
    item, root = _safe_child(target)
    dirs = []
    if target != root:
        dirs.append({"name": "..", "path": rel_path(target.parent), "kind": "parent"})
    for p in sorted(target.iterdir(), key=lambda x: x.name.lower()):
        if p.is_dir() and p.name not in {".git", "__pycache__", "node_modules"}:
            dirs.append({"name": p.name, "path": rel_path(p), "kind": "dir"})
    return {
        "path": rel_path(target),
        "workspace_id": item.get("id"),
        "workspace_name": item.get("name"),
        "absolute_path": str(target),
        "dirs": dirs,
    }
