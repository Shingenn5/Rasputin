import json
import re
import time
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WORKSPACE_FILE = DATA_DIR / "workspace.json"
IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache"}
PREVIEW_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
    ".json", ".csv", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".env", ".sql", ".sh",
    ".ps1", ".bat", ".dockerfile", ".gitignore",
}
MAX_PREVIEW_BYTES = 128 * 1024

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


def _normalize_project_root(data):
    workspaces = data.setdefault("workspaces", [])
    project_root = next((item for item in workspaces if item.get("id") == "project-root"), None)
    if not project_root:
        project_root = _blank()["workspaces"][0]
        workspaces.insert(0, project_root)
    project_root["id"] = "project-root"
    project_root["name"] = "Project Root"
    project_root["root"] = "."
    project_root["permission_profile"] = {"read": True, "write": True, "reorganize": False}
    if not data.get("active_id"):
        data["active_id"] = "project-root"
    return data


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
    return _normalize_project_root(data)


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
    profile = item.get("permission_profile", {})
    return {
        "id": item.get("id"),
        "name": item.get("name") or item.get("id"),
        "display_name": item.get("name") or item.get("id"),
        "root": item.get("root") or ".",
        "absolute_path": str(root),
        "permission_profile": profile,
        "read_only": not bool(profile.get("write", False)),
        "is_mounted": bool(item.get("is_mounted", True)),
        "requires_restart": bool(item.get("requires_restart", False)),
        "indexed": bool(item.get("indexed", False)),
        "last_used": item.get("last_used"),
    }


def _is_relative_to(child, parent):
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _display_name(path):
    target = _root_from_value(path)
    if target == ROOT:
        return "Project Root"
    if target == ROOT / "workspace":
        return "Workspace Folder"
    return target.name or str(target)


def _extension(path):
    name = path.name.lower()
    if name in {".env", ".gitignore", "dockerfile"}:
        return name
    return path.suffix.lower()


def _is_previewable(path):
    return path.is_file() and _extension(path) in PREVIEW_EXTENSIONS


def _entry(path, kind, read_only=False):
    stat = None
    try:
        stat = path.stat()
    except OSError:
        pass
    size = stat.st_size if stat and path.is_file() else None
    modified = stat.st_mtime if stat else None
    return {
        "name": path.name,
        "display_name": "Parent folder" if kind == "parent" else path.name,
        "path": rel_path(path),
        "absolute_path": str(path.resolve()),
        "kind": kind,
        "is_directory": kind in {"folder", "parent"},
        "is_file": kind == "file",
        "extension": "" if kind != "file" else _extension(path),
        "size_bytes": size,
        "modified_at": modified,
        "read_only": bool(read_only),
        "previewable": _is_previewable(path),
    }


def _workspace_dir():
    return (ROOT / "workspace").resolve()


def _read_only_profile():
    return {"read": True, "write": False, "reorganize": False}


def _root_entry(root_id, name, path, mounted=True):
    target = _root_from_value(path)
    return {
        "id": root_id,
        "name": name,
        "display_name": name,
        "path": rel_path(target),
        "absolute_path": str(target),
        "is_mounted": bool(mounted),
        "read_only": False,
        "requires_restart": False,
        "indexed": False,
    }


def approved_roots():
    data = _load()
    roots = []
    seen = set()
    for item in data.get("workspaces", []):
        root = _abs(item)
        if root in seen or not root.exists():
            continue
        seen.add(root)
        public = _public_item(item)
        roots.append({
            "id": public["id"],
            "name": public["name"],
            "display_name": public["display_name"],
            "path": public["root"],
            "absolute_path": public["absolute_path"],
            "is_mounted": public["is_mounted"],
            "read_only": public["read_only"],
            "requires_restart": public["requires_restart"],
            "indexed": public["indexed"],
        })
    workspace_dir = _workspace_dir()
    if workspace_dir.exists() and workspace_dir not in seen:
        roots.append(_root_entry("workspace-folder", "Workspace Folder", workspace_dir))
    return {"roots": roots}


def _root_by_id(root_id):
    for root in approved_roots()["roots"]:
        if root.get("id") == root_id:
            return root
    raise ValueError("approved root missing")


def _browse_target(root_id=None, path=None):
    if root_id:
        root = _root_by_id(root_id)
        base = _root_from_value(root.get("path"))
    else:
        item = workspace_for_path(_root_from_value(path or "."))
        if not item:
            raise ValueError("path outside approved workspaces")
        base = _abs(item)
        root = {
            "id": item.get("id"),
            "display_name": item.get("name") or item.get("id"),
            "path": item.get("root") or ".",
            "absolute_path": str(base),
        }
    target = base if not path else _root_from_value(path)
    if target != base and not _is_relative_to(target, base):
        raise ValueError("path outside approved root")
    return root, base, target


def browse(root_id=None, path=None):
    root, base, target = _browse_target(root_id, path)
    if not target.exists() or not target.is_dir():
        raise ValueError("folder missing")
    read_only = bool(root.get("read_only", True))
    entries = []
    if target != base:
        entries.append(_entry(target.parent, "parent", read_only))
    folders = []
    files = []
    for p in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        if p.is_dir():
            if p.name in IGNORED_DIRS:
                continue
            folders.append(_entry(p, "folder", read_only))
        elif p.is_file():
            files.append(_entry(p, "file", read_only))
    entries.extend(folders)
    entries.extend(files)
    return {
        "root": root,
        "path": rel_path(target),
        "display_name": _display_name(target),
        "absolute_path": str(target),
        "entries": entries,
    }


def preview_file(root_id=None, path=None, max_bytes=MAX_PREVIEW_BYTES):
    if not path:
        raise ValueError("file path is required")
    root, base, target = _browse_target(root_id, path)
    if not target.exists() or not target.is_file():
        raise ValueError("file missing")
    if target != base and not _is_relative_to(target, base):
        raise ValueError("path outside approved root")
    if not _is_previewable(target):
        raise ValueError("file type is not previewable")
    try:
        stat = target.stat()
    except OSError as exc:
        raise ValueError("file cannot be read") from exc
    limit = max(1, min(int(max_bytes or MAX_PREVIEW_BYTES), MAX_PREVIEW_BYTES))
    if stat.st_size > limit:
        raise ValueError(f"file is larger than the {limit} byte preview limit")
    raw = target.read_bytes()
    if b"\0" in raw:
        raise ValueError("binary files cannot be previewed")
    try:
        text = raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
        encoding = "utf-8-replace"
    return {
        "root": root,
        "path": rel_path(target),
        "display_name": target.name,
        "absolute_path": str(target),
        "extension": _extension(target),
        "size_bytes": stat.st_size,
        "modified_at": stat.st_mtime,
        "encoding": encoding,
        "truncated": False,
        "content": text,
        "read_only": bool(root.get("read_only", True)),
    }


def approve(path, name=None, read_only=True):
    profile = {"read": True, "write": not bool(read_only), "reorganize": False}
    return add(path, name or _display_name(path), profile)


def _validate_mount_host_path(raw):
    if any(char in raw for char in ("\0", "\r", "\n")):
        raise ValueError("host folder path cannot contain line breaks or null bytes")
    if raw.strip() != raw:
        raise ValueError("host folder path cannot start or end with spaces")
    if raw.startswith("-"):
        raise ValueError("host folder path cannot start with '-'")
    return raw


def mount_plan(host_path, name=None, read_only=True):
    raw = str(host_path or "").strip()
    if not raw:
        raise ValueError("host folder path is required")
    raw = _validate_mount_host_path(raw)
    display = name or Path(raw).name or "Mounted Folder"
    target = f"/app/workspace/mounted/{_slug(display)}"
    return {
        "display_name": display,
        "host_path": raw,
        "container_path": target,
        "read_only": bool(read_only),
        "is_mounted": False,
        "requires_restart": True,
        "compose_volume": f"{raw}:{target}{':ro' if read_only else ''}",
        "message": "Preview only. Docker must restart with this folder mounted before Rasputin can browse it.",
    }


def save_mount_request(host_path, name=None, read_only=True):
    plan = mount_plan(host_path, name, read_only)
    data = _load()
    requests = data.setdefault("mount_requests", [])
    plan["requested_at"] = time.time()
    requests.append(plan)
    _save(data)
    return plan


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


def require_path_permission(path, permission):
    target = _root_from_value(path)
    item = workspace_for_path(target)
    if not item:
        raise ValueError("path outside approved workspaces")
    profile = item.get("permission_profile", {})
    if not profile.get(permission, False):
        raise PermissionError(f"workspace {permission} permission is disabled")
    return item


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
        if permission_profile is not None:
            for item in data.get("workspaces", []):
                if item.get("id") == existing.get("id"):
                    if item.get("id") != "project-root":
                        item["permission_profile"] = permission_profile
                    if name and item.get("id") != "project-root":
                        item["name"] = name
                    _save(data)
                    return _public_item(item)
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
        "permission_profile": permission_profile or _read_only_profile(),
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
        add(path, permission_profile=_read_only_profile())
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
