import json
import os
import re
import time
from pathlib import Path
from threading import Lock

from backend.core.datadir import data_dir

ROOT = Path(__file__).resolve().parents[2]
# RASPUTIN_DATA_DIR (shared with runtime_store.py) redirects file-based
# workspace state during native test/verification runs, so they stop writing
# workspace.json / the generated compose override into the real repo's data/
# folder. Unset in every shipped compose file, so production is unaffected.
DATA_DIR = data_dir()
WORKSPACE_FILE = DATA_DIR / "workspace.json"
IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache"}
PREVIEW_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
    ".json", ".csv", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".env", ".sql", ".sh",
    ".ps1", ".bat", ".dockerfile", ".gitignore",
}
MAX_PREVIEW_BYTES = 128 * 1024
MAX_SEARCH_FILE_BYTES = 256 * 1024

_lock = Lock()
WORKSPACE_ROLES = {"viewer": 1, "contributor": 2, "developer": 3, "owner": 4}


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
                "trusted": False,
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


from backend.core import runtime_store as store

def _load():
    data = store.get_kv("workspace_config")
    if not isinstance(data, dict):
        DATA_DIR.mkdir(exist_ok=True)
        if WORKSPACE_FILE.exists():
            with _lock:
                try:
                    data = json.loads(WORKSPACE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    data = _blank()
        else:
            data = _blank()
        store.set_kv("workspace_config", data)
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
        store.set_kv("workspace_config", data)


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
        "trusted": bool(item.get("trusted", False)),
        "allow_host_shell": bool(item.get("allow_host_shell", False)),
        "commands": dict(item.get("commands") or {}),
        "members": dict(item.get("members") or {}),
    }


def claim_legacy_membership(username):
    """Make the original administrator owner of pre-ACL workspaces."""
    data = _load()
    changed = False
    for item in data.get("workspaces", []):
        if not isinstance(item.get("members"), dict) or not item.get("members"):
            item["members"] = {username: "owner"}
            changed = True
    if changed:
        _save(data)


def access_role(workspace_ref, username, is_admin=False):
    if is_admin:
        return "owner"
    try:
        _, item = _find(workspace_ref)
    except ValueError:
        item = workspace_for_path(workspace_ref)
    if not item:
        return None
    return (item.get("members") or {}).get(username)


def require_user_access(workspace_ref, username, minimum="viewer", is_admin=False):
    role = access_role(workspace_ref, username, is_admin)
    if not role or WORKSPACE_ROLES.get(role, 0) < WORKSPACE_ROLES.get(minimum, 1):
        raise PermissionError(f"workspace {minimum} access required")
    return role


def set_member(workspace_ref, username, role=None):
    data, item = _find(workspace_ref)
    members = dict(item.get("members") or {})
    if role is None:
        members.pop(username, None)
    else:
        role = str(role).lower()
        if role not in WORKSPACE_ROLES:
            raise ValueError("workspace role must be viewer, contributor, developer, or owner")
        members[username] = role
    if not any(value == "owner" for value in members.values()):
        raise ValueError("a workspace must retain at least one owner")
    item["members"] = members
    _save(data)
    return _public_item(item)


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
        "trusted": False,
    }


def approved_roots(username=None, is_admin=False):
    data = _load()
    roots = []
    seen = set()
    for item in data.get("workspaces", []):
        if username and not is_admin and not (item.get("members") or {}).get(username):
            continue
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
            "trusted": public["trusted"],
        })
    workspace_dir = _workspace_dir()
    if (not username or is_admin) and workspace_dir.exists() and workspace_dir not in seen:
        roots.append(_root_entry("workspace-folder", "Workspace Folder", workspace_dir))
    return {"roots": roots}


def _root_by_id(root_id):
    for root in approved_roots()["roots"]:
        if root.get("id") == root_id:
            return root
    raise ValueError("approved root missing")


def _path_under_base(base, path=None):
    raw = str(path or "").strip()
    if not raw:
        return base
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    root_relative = (ROOT / candidate).resolve()
    if root_relative == base or _is_relative_to(root_relative, base):
        return root_relative
    return (base / candidate).resolve()


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
    target = _path_under_base(base, path)
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


def _search_snippet(text, needle, radius=80):
    lowered = text.lower()
    index = lowered.find(needle.lower())
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(text), index + len(needle) + radius)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + " ".join(text[start:end].split()) + suffix


def search_files(root_id=None, path=None, query="", max_results=40, include_content=False):
    text = " ".join(str(query or "").split())
    if not text:
        raise ValueError("search query is required")
    root, base, target = _browse_target(root_id, path)
    if not target.exists() or not target.is_dir():
        raise ValueError("folder missing")
    limit = max(1, min(int(max_results or 40), 100))
    read_only = bool(root.get("read_only", True))
    needle = text.lower()
    matches = []
    searched = 0
    truncated = False

    def add_match(p, kind, score, match_type, snippet=""):
        entry = _entry(p, kind, read_only)
        entry.update({
            "score": score,
            "match_type": match_type,
            "snippet": snippet,
        })
        matches.append(entry)

    import os
    for current, dirs, files in os.walk(target):
        dirs[:] = [name for name in dirs if name not in IGNORED_DIRS]
        current_path = Path(current)
        for folder in sorted(dirs, key=str.lower):
            if len(matches) >= limit:
                truncated = True
                break
            p = current_path / folder
            searched += 1
            haystack = f"{folder} {rel_path(p)}".lower()
            if needle in haystack:
                score = 80 if folder.lower() == needle else 60
                add_match(p, "folder", score, "path")
        if truncated:
            break
        for filename in sorted(files, key=str.lower):
            if len(matches) >= limit:
                truncated = True
                break
            p = current_path / filename
            searched += 1
            haystack = f"{filename} {rel_path(p)}".lower()
            if needle in haystack:
                score = 100 if filename.lower() == needle else 72
                add_match(p, "file", score, "path")
                continue
            if not include_content or not _is_previewable(p):
                continue
            try:
                stat = p.stat()
            except OSError:
                continue
            if stat.st_size > MAX_SEARCH_FILE_BYTES:
                continue
            try:
                raw = p.read_bytes()
                if b"\0" in raw:
                    continue
                content = raw.decode("utf-8", errors="replace")
            except OSError:
                continue
            if needle in content.lower():
                add_match(p, "file", 42, "content", _search_snippet(content, text))
        if truncated:
            break

    matches.sort(key=lambda item: (-int(item.get("score") or 0), item.get("path") or ""))
    return {
        "root": root,
        "path": rel_path(target),
        "display_name": _display_name(target),
        "query": text,
        "matches": matches[:limit],
        "searched": searched,
        "truncated": truncated,
        "include_content": bool(include_content),
    }


def approve(path, name=None, read_only=True, owner_username=None):
    profile = {"read": True, "write": not bool(read_only), "reorganize": False}
    return add(path, name or _display_name(path), profile, owner_username)


def _validate_mount_host_path(raw):
    if any(char in raw for char in ("\0", "\r", "\n")):
        raise ValueError("host folder path cannot contain line breaks or null bytes")
    if raw.strip() != raw:
        raise ValueError("host folder path cannot start or end with spaces")
    if raw.startswith("-"):
        raise ValueError("host folder path cannot start with '-'")
    return raw


def is_native():
    return os.environ.get("WRAPPER_RUNTIME") != "docker"


def mount_plan(host_path, name=None, read_only=True):
    raw = str(host_path or "").strip()
    if not raw:
        raise ValueError("host folder path is required")
    raw = _validate_mount_host_path(raw)
    display = name or Path(raw).name or "Mounted Folder"
    if is_native():
        # Native has no container: the host folder is directly usable, so there
        # is nothing to bind-mount and nothing to restart. Approving registers
        # the host path as-is (the mount-request subsystem is Docker-only).
        return {
            "display_name": display,
            "host_path": raw,
            "container_path": raw,
            "read_only": bool(read_only),
            "is_mounted": True,
            "requires_restart": False,
            "compose_volume": "",
            "message": "Folder is directly accessible in native mode -- approve to start using it.",
        }
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


COMPOSE_MOUNTS_FILE = DATA_DIR / "docker-compose.mounts.yml"
COMPOSE_MOUNTS_SERVICE = "rasputin-wrapper"


def _normalize_host_path_key(path):
    text = str(path or "").strip().replace("\\", "/")
    while len(text) > 3 and text.endswith("/"):
        text = text[:-1]
    # Windows paths are case-insensitive; POSIX paths are not.
    return text.lower() if re.match(r"^[A-Za-z]:/", text) else text


def _yaml_single_quoted(text):
    # Single-quoted YAML scalars need no escaping except doubling embedded
    # single quotes; backslashes and colons are safe as-is in this style.
    return "'" + str(text).replace("'", "''") + "'"


def _write_compose_mounts_override(requests):
    """Regenerate the Compose override with one volume line per pending
    mount request, so restarting Rasputin picks up newly-approved folders
    without any manual YAML editing. Compose concatenates (does not replace)
    list-valued keys like `volumes` across -f files, so this purely adds to
    the base file's mounts. Deleted when there is nothing pending so restart
    scripts can skip a stale -f flag."""
    if not requests:
        COMPOSE_MOUNTS_FILE.unlink(missing_ok=True)
        return False
    lines = ["services:", f"  {COMPOSE_MOUNTS_SERVICE}:", "    volumes:"]
    for item in requests:
        lines.append(f"      - {_yaml_single_quoted(item['compose_volume'])}")
    DATA_DIR.mkdir(exist_ok=True)
    COMPOSE_MOUNTS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def save_mount_request(host_path, name=None, read_only=True):
    """Register a host folder to be bind-mounted, regenerating the Compose
    override from every registered mount. Entries here are permanent once
    saved: this is the only record of which host path a given
    /app/workspace/mounted/<slug> container path came from, so once a folder
    is approved as a workspace, this entry must keep producing that volume
    line on every future restart -- otherwise the mount silently disappears
    (and the workspace becomes an empty, broken folder) the next time
    Rasputin restarts without this exact host_path re-submitted. Only
    remove_mount_request (an explicit user action) may delete an entry."""
    plan = mount_plan(host_path, name, read_only)
    if is_native():
        # No bind mount, compose override, or restart natively: register the host
        # folder as a workspace directly. Nothing is stored in mount_requests, so
        # the pending-mounts panel stays empty in native mode.
        public = approve(plan["host_path"], plan["display_name"], read_only)
        plan = dict(plan)
        plan["compose_written"] = False
        plan["compose_file"] = ""
        plan["registered"] = True
        plan["workspace"] = public
        return plan
    data = _load()
    requests = data.setdefault("mount_requests", [])
    # Idempotent by host path: re-approving the same folder (or a UI retry)
    # replaces its entry instead of piling up duplicates.
    key = _normalize_host_path_key(plan["host_path"])
    requests[:] = [r for r in requests if _normalize_host_path_key(r.get("host_path")) != key]
    plan["requested_at"] = time.time()
    requests.append(plan)
    _save(data)
    written = _write_compose_mounts_override(requests)
    plan = dict(plan)
    plan["compose_written"] = written
    plan["compose_file"] = str(COMPOSE_MOUNTS_FILE) if written else ""
    return plan


def _mount_already_approved(container_path, workspaces):
    target = Path(container_path)
    return any(_abs(item) == target for item in workspaces)


def list_mount_requests():
    """Host-folder mounts still needing user action, oldest first. Entries
    already approved as a workspace are left out here (nothing left to do)
    but stay in storage permanently -- see save_mount_request's docstring for
    why they must not be deleted just because they were approved.

    `ready` means the bind mount is already live in the running container
    (an earlier restart already picked it up), so the folder can be approved
    as a workspace right now with no further restart needed."""
    data = _load()
    requests = sorted(data.get("mount_requests", []), key=lambda r: r.get("requested_at", 0))
    workspaces = data.get("workspaces", [])
    result = []
    for item in requests:
        if _mount_already_approved(item["container_path"], workspaces):
            continue
        entry = dict(item)
        entry["ready"] = Path(item["container_path"]).is_dir()
        result.append(entry)
    return {"requests": result}


def remove_mount_request(host_path):
    """Cancel a registered mount so it stops being written into the Compose
    override. If the bind mount is already live, it stays live in the
    running container until the next restart, at which point it goes away
    for good -- Docker has no way to detach a mount from a running
    container, only to leave it out of the next one."""
    data = _load()
    requests = data.get("mount_requests", [])
    key = _normalize_host_path_key(host_path)
    remaining = [r for r in requests if _normalize_host_path_key(r.get("host_path")) != key]
    removed = len(remaining) != len(requests)
    data["mount_requests"] = remaining
    _save(data)
    _write_compose_mounts_override(remaining)
    return {"removed": removed, "requests": remaining}


def _plan_path(workspace_path=".", path="."):
    base = resolve_path(workspace_path or ".")
    target = _path_under_base(base, path)
    if target != base and not _is_relative_to(target, base):
        raise ValueError("path outside approved workspace")
    item = workspace_for_path(target if target.exists() else target.parent)
    if not item:
        raise ValueError("path outside approved workspaces")
    return base, target, item


def _path_detail(path, base=None):
    exists = path.exists()
    stat = None
    try:
        stat = path.stat() if exists else None
    except OSError:
        stat = None
    return {
        "path": rel_path(path),
        "display_name": path.name or "workspace root",
        "exists": exists,
        "kind": "folder" if exists and path.is_dir() else "file",
        "size_bytes": stat.st_size if stat and path.is_file() else None,
        "relative_to_workspace": str(path.relative_to(base)).replace("\\", "/") if base and (path == base or _is_relative_to(path, base)) else rel_path(path),
    }


def _organize_bucket(path):
    ext = _extension(path)
    if ext in {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".yml", ".yaml", ".toml", ".sql", ".sh", ".ps1"}:
        return "Code"
    if ext in {".md", ".txt", ".pdf", ".docx"}:
        return "Documents"
    if ext in {".csv", ".xlsx"}:
        return "Data"
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return "Media"
    return "Other"


def mutation_preview(kind, workspace_path=".", path=None, source=None, target=None, content=None, max_items=40):
    operation = str(kind or "").strip().lower().replace("-", "_")
    if operation == "rename":
        operation = "move"
    if operation not in {"write", "mkdir", "move", "organize"}:
        raise ValueError("unsupported mutation preview kind")
    base = resolve_path(workspace_path or ".")
    item = workspace_for_path(base)
    if not item:
        raise ValueError("workspace is not approved")
    profile = item.get("permission_profile", {})
    warnings = []
    affected = []
    steps = []
    rollback = []

    if operation == "write":
        _, target_path, item = _plan_path(workspace_path, path)
        parent = target_path.parent
        if not _is_relative_to(parent, base) and parent != base:
            raise ValueError("path outside approved workspace")
        if not profile.get("write", False):
            warnings.append("Workspace write permission is currently disabled. This is a preview only.")
        affected.append({"role": "target", **_path_detail(target_path, base)})
        bytes_count = len(str(content or "").encode("utf-8"))
        action = "replace file" if target_path.exists() else "create file"
        steps.append({"action": action, "path": rel_path(target_path), "bytes": bytes_count})
        rollback.append("Keep a copy of the previous file content before applying a future write.")

    elif operation == "mkdir":
        _, target_path, item = _plan_path(workspace_path, path)
        if not profile.get("reorganize", False):
            warnings.append("Workspace reorganize permission is currently disabled. This is a preview only.")
        affected.append({"role": "target", **_path_detail(target_path, base)})
        steps.append({"action": "create folder", "path": rel_path(target_path)})
        rollback.append("Remove the empty folder if the future create action is reversed.")

    elif operation == "move":
        _, source_path, item = _plan_path(workspace_path, source)
        _, target_path, _ = _plan_path(workspace_path, target)
        if not source_path.exists():
            raise ValueError("source path does not exist")
        if not profile.get("reorganize", False):
            warnings.append("Workspace reorganize permission is currently disabled. This is a preview only.")
        if target_path.exists():
            warnings.append("Target path already exists. A future move would need conflict handling.")
        affected.append({"role": "source", **_path_detail(source_path, base)})
        affected.append({"role": "target", **_path_detail(target_path, base)})
        steps.append({"action": "move", "source": rel_path(source_path), "target": rel_path(target_path)})
        rollback.append(f"Move {rel_path(target_path)} back to {rel_path(source_path)} if the future move is reversed.")

    else:
        _, folder, item = _plan_path(workspace_path, path or ".")
        if not folder.exists() or not folder.is_dir():
            raise ValueError("folder missing")
        if not profile.get("reorganize", False):
            warnings.append("Workspace reorganize permission is currently disabled. This is a preview only.")
        limit = max(1, min(int(max_items or 40), 100))
        planned = 0
        for child in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
            if planned >= limit:
                warnings.append("Preview truncated before all files were inspected.")
                break
            if not child.is_file():
                continue
            bucket = _organize_bucket(child)
            destination = folder / bucket / child.name
            if destination == child:
                continue
            affected.append({"role": "source", **_path_detail(child, base)})
            steps.append({"action": "move", "source": rel_path(child), "target": rel_path(destination), "bucket": bucket})
            planned += 1
        rollback.append("Move files back to their original paths using the before/after list.")

    return {
        "kind": operation,
        "dry_run": True,
        "will_mutate": False,
        "workspace": item.get("root") or workspace_path or ".",
        "workspace_name": item.get("name") or item.get("id"),
        "permission_profile": profile,
        "affected_paths": affected,
        "steps": steps,
        "warnings": warnings,
        "rollback_notes": rollback,
        "created_at": time.time(),
        "message": "Preview only. No files were changed.",
    }


def all_workspaces(username=None, is_admin=False):
    data = _load()
    items = data.get("workspaces", [])
    if username and not is_admin:
        items = [item for item in items if (item.get("members") or {}).get(username)]
    return {
        "active_id": (data.get("active_by_user") or {}).get(username, data.get("active_id", "project-root")),
        "workspaces": [_public_item(w) for w in items],
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


def get_active(username=None, is_admin=False):
    data = _load()
    visible = data.get("workspaces", []) if (not username or is_admin) else [w for w in data.get("workspaces", []) if (w.get("members") or {}).get(username)]
    if not visible:
        return {"active_id": None, "active_path": None, "active_name": "No workspace access", "absolute_path": None, "root": str(ROOT), "workspaces": []}
    active_id = (data.get("active_by_user") or {}).get(username, data.get("active_id") or "project-root")
    item = next((w for w in visible if w.get("id") == active_id), visible[0])
    root = _abs(item)
    return {
        "active_id": item.get("id"),
        "active_path": item.get("root") or ".",
        "active_name": item.get("name") or item.get("id"),
        "absolute_path": str(root),
        "root": str(ROOT),
        "workspaces": [_public_item(w) for w in visible],
    }


def _unsafe_workspace_root(target):
    # A workspace root must be a project folder -- never a drive/system/home root.
    # In native mode this path becomes the agent's file-tool scope and, once
    # Host Shell is enabled, its shell cwd/ACL scope, so a broad root is a broad
    # blast radius. Trusted Dev Mode is a separate file/git approval setting.
    # Rejects the drive root, the home dir, the Rasputin data dir, and anything
    # inside the Windows / Program Files (or POSIX system) trees. Fails open on
    # unexpected paths so it can never wrongly block a legitimate project folder.
    try:
        if len(target.parts) <= 1:
            return "a drive or filesystem root"

        def _r(p):
            try:
                return p.resolve()
            except Exception:
                return p

        exact = []
        home = os.environ.get("USERPROFILE")
        if home:
            exact.append(Path(home))
        try:
            dd = data_dir()
            exact.extend([dd, dd.parent])  # data dir + %LOCALAPPDATA%\Rasputin
        except Exception:
            pass
        for s in exact:
            if target == _r(s):
                return f"a protected location ({s})"

        subtree = []
        for var in ("WINDIR", "SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            v = os.environ.get(var)
            if v:
                subtree.append(Path(v))
        if os.name != "nt":
            # POSIX-only: on Windows these resolve to drive-relative paths (e.g.
            # Path("/") -> C:\) and would falsely flag every folder on C:.
            for p in ("/etc", "/usr", "/bin", "/sbin", "/root", "/boot", "/var", "/lib"):
                subtree.append(Path(p))
        for s in subtree:
            sr = _r(s)
            if target == sr or sr in target.parents:
                return f"inside a protected system location ({s})"
    except Exception:
        return None
    return None


def add(path=".", name=None, permission_profile=None, owner_username=None):
    target = _root_from_value(path)
    if not target.exists() or not target.is_dir():
        raise ValueError("workspace must be an existing folder")
    unsafe = _unsafe_workspace_root(target)
    if unsafe:
        raise ValueError(f"refusing to use {unsafe} as a workspace root -- choose a project folder")
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
        "trusted": False,
        "allow_host_shell": False,
        "members": {owner_username: "owner"} if owner_username else {},
    }
    data.setdefault("workspaces", []).append(item)
    _save(data)
    return _public_item(item)


def select(path, username=None, is_admin=False):
    data = _load()
    try:
        _, item = _find(path)
    except ValueError:
        # `path` may be the id of a synthetic pseudo-root that approved_roots()
        # surfaces (e.g. "workspace-folder" for ./workspace) but that was never
        # actually registered in data["workspaces"]. Resolve it to its real
        # absolute path first -- otherwise add() treats the id string itself
        # as a relative path (ROOT/"workspace-folder"), which doesn't exist.
        resolved = path
        resolved_name = None
        for root in approved_roots()["roots"]:
            if root.get("id") == path:
                resolved = root.get("absolute_path")
                resolved_name = root.get("name")
                break
        add(resolved, name=resolved_name, permission_profile=_read_only_profile())
        data = _load()
        _, item = _find(resolved)
    if username:
        require_user_access(item.get("id"), username, "viewer", is_admin)
    item["last_used"] = time.time()
    if username:
        data.setdefault("active_by_user", {})[username] = item.get("id")
    else:
        data["active_id"] = item.get("id")
    _save(data)
    return get_active(username, is_admin)


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


def set_trusted(workspace_ref, trusted=True):
    data, item = _find(workspace_ref)
    item["trusted"] = bool(trusted)
    _save(data)
    return _public_item(item)


def is_trusted(path):
    item = workspace_for_path(_root_from_value(path))
    return bool(item and item.get("trusted"))


def set_workspace_commands(workspace_ref, test=None, build=None, lint=None):
    # Per-workspace test/build/lint commands the operator configures once per
    # repo. Stored on the workspace record alongside trusted/host_shell; a
    # value of "" clears that command, None leaves it unchanged.
    data, item = _find(workspace_ref)
    commands = dict(item.get("commands") or {})
    for key, value in (("test", test), ("build", build), ("lint", lint)):
        if value is None:
            continue
        text = str(value).strip()[:2000]
        if text:
            commands[key] = text
        else:
            commands.pop(key, None)
    item["commands"] = commands
    _save(data)
    return _public_item(item)


def get_workspace_commands(path):
    item = workspace_for_path(_root_from_value(path))
    return dict((item or {}).get("commands") or {})


def set_host_shell(workspace_ref, enabled=True):
    # Host command execution is a capability distinct from Trusted Dev Mode:
    # trusting a folder auto-approves file edits, but must NOT silently grant
    # unattended shell on the real machine. This is the separate opt-in.
    data, item = _find(workspace_ref)
    item["allow_host_shell"] = bool(enabled)
    _save(data)
    # Windows-native side effect: grant/revoke the sandbox account's access to this
    # workspace tree so its run-as commands can reach it (and nothing else). Best
    # effort + import-local to avoid a hard dependency on non-Windows / non-provisioned
    # setups; the shell path fails closed if the grant didn't take.
    try:
        from backend.core import sandbox_exec
        root = item.get("root")
        if root:
            if enabled:
                sandbox_exec.grant_workspace_acl(root)
            else:
                sandbox_exec.revoke_workspace_acl(root)
    except Exception:
        pass
    return _public_item(item)


def is_host_shell_allowed(path):
    item = workspace_for_path(_root_from_value(path))
    return bool(item and item.get("allow_host_shell"))


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
