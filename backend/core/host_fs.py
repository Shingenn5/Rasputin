"""Browse the host machine's folders so users can pick one to approve/mount.

The wrapper usually runs inside Docker and cannot see the host filesystem.
When Docker control is enabled, listings run in short-lived sibling
containers that bind-mount the requested folder read-only
(`docker run --rm --network none`). Docker Desktop reports bind sources in
native host form (e.g. ``C:\\Users\\elliott\\...``), and its daemon accepts the
same form back in ``--mount`` specs, so no path translation is needed.

When the server runs natively (no Docker), listings use os.scandir directly.
"""
import json
import os
import re
import socket
import subprocess
from pathlib import Path, PureWindowsPath

from backend.core.response import AppError

PROBE_IMAGE = "rasputin-wrapper:latest"
PROBE_TIMEOUT = 45
MAX_ENTRIES = 400

# Runs inside the probe container; prints one JSON object either way. The
# probe mounts the drive root (which always exists) and walks to PROBE_REL
# inside the container — mounting the target directly would make Docker
# Desktop silently create it on the host when the path has a typo.
_LIST_SCRIPT = (
    "import json,os\n"
    "rel=os.environ.get('PROBE_REL','').strip('/')\n"
    "target=os.path.join('/probe',rel) if rel else '/probe'\n"
    "if not os.path.isdir(target):\n"
    "    print(json.dumps({'missing': True})); raise SystemExit(0)\n"
    "dirs=[]\n"
    "try:\n"
    "    with os.scandir(target) as it:\n"
    "        for e in it:\n"
    "            try:\n"
    "                if e.is_dir(follow_symlinks=False): dirs.append(e.name)\n"
    "            except OSError: pass\n"
    "except OSError as exc:\n"
    "    print(json.dumps({'error': str(exc)})); raise SystemExit(0)\n"
    "dirs.sort(key=str.lower)\n"
    f"print(json.dumps({{'dirs': dirs[:{MAX_ENTRIES}]}}))\n"
)


def _in_docker():
    return os.environ.get("WRAPPER_RUNTIME") == "docker"


def _is_windows_path(path):
    return bool(re.match(r"^[A-Za-z]:[\\/]", str(path)))


def _validate_host_path(raw):
    text = str(raw or "").strip()
    if not text:
        raise AppError("host_path_required", "Choose or enter a host folder path.", 400)
    if any(char in text for char in ("\0", "\r", "\n")):
        raise AppError("host_path_invalid", "Host folder path cannot contain line breaks or null bytes.", 400)
    if text.startswith("-"):
        raise AppError("host_path_invalid", "Host folder path cannot start with '-'.", 400)
    if any(part == ".." for part in re.split(r"[\\/]", text)):
        raise AppError("host_path_invalid", "Host folder path cannot contain '..' segments.", 400)
    return text


def _split_mount_root(path):
    """Split a host path into (always-existing mount root, relative walk)."""
    if _is_windows_path(path):
        drive = f"{path[0].upper()}:\\"
        rel = path[2:].replace("\\", "/").strip("/")
        return drive, rel
    return "/", str(path).lstrip("/")


def _join(base, name):
    if _is_windows_path(base):
        return str(PureWindowsPath(base) / name)
    return str(Path(base) / name) if base != "/" else f"/{name}"


def _parent(path):
    if _is_windows_path(path):
        pure = PureWindowsPath(path)
        parent = pure.parent
        return None if parent == pure else str(parent)
    pure = Path(path)
    parent = pure.parent
    return None if parent == pure else str(parent)


def _run_docker(args, timeout=PROBE_TIMEOUT):
    try:
        proc = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise AppError("docker_unavailable", "Docker CLI is not available. Restart with the docker-control profile.", 503)
    except subprocess.TimeoutExpired:
        raise AppError("docker_timeout", "Docker took too long to list that folder.", 504)
    return proc


def _self_mounts():
    """Bind mounts of this wrapper container, via docker inspect on ourselves."""
    container = socket.gethostname()
    proc = _run_docker(["inspect", "--format", "{{json .Mounts}}", container], timeout=20)
    if proc.returncode != 0:
        proc = _run_docker([
            "ps", "--filter", "label=com.docker.compose.service=rasputin-wrapper",
            "--format", "{{.ID}}",
        ], timeout=20)
        container = (proc.stdout or "").strip().splitlines()[0] if proc.stdout.strip() else ""
        if not container:
            return []
        proc = _run_docker(["inspect", "--format", "{{json .Mounts}}", container], timeout=20)
        if proc.returncode != 0:
            return []
    try:
        mounts = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return mounts if isinstance(mounts, list) else []


def _docker_roots():
    """Derive useful starting points from where this container's volumes live on the host."""
    project_root = None
    for mount in _self_mounts():
        if mount.get("Destination") == "/app/workspace" and mount.get("Type") == "bind":
            source = str(mount.get("Source") or "")
            if source and source != "/var/run/docker.sock":
                project_root = _parent(source)
            break
    roots = []
    if project_root:
        roots.append({"name": "Rasputin project folder", "path": project_root})
        if _is_windows_path(project_root):
            match = re.match(r"^([A-Za-z]:[\\/]Users[\\/][^\\/]+)", project_root)
            if match:
                roots.append({"name": "Home folder", "path": match.group(1)})
            roots.append({"name": f"Drive {project_root[0].upper()}:", "path": f"{project_root[0].upper()}:\\"})
        else:
            match = re.match(r"^(/(?:home|Users)/[^/]+)", project_root)
            if match:
                roots.append({"name": "Home folder", "path": match.group(1)})
            roots.append({"name": "Filesystem root", "path": "/"})
    deduped = []
    seen = set()
    for root in roots:
        if root["path"] not in seen:
            seen.add(root["path"])
            deduped.append(root)
    return deduped


def _native_roots():
    roots = [{"name": "Home folder", "path": str(Path.home())}]
    if os.name == "nt":
        for letter in "CDEFGH":
            drive = f"{letter}:\\"
            if Path(drive).exists():
                roots.append({"name": f"Drive {letter}:", "path": drive})
    else:
        roots.append({"name": "Filesystem root", "path": "/"})
    return roots


def _docker_list(path):
    root, rel = _split_mount_root(path)
    proc = _run_docker([
        "run", "--rm", "--network", "none",
        "--entrypoint", "python",
        "-e", f"PROBE_REL={rel}",
        "--mount", f"type=bind,source={root},target=/probe,readonly",
        PROBE_IMAGE, "-c", _LIST_SCRIPT,
    ])
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[-400:]
        raise AppError("host_browse_failed", detail or "Docker could not open that folder.", 502)
    try:
        payload = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        raise AppError("host_browse_failed", "The folder probe returned unreadable output.", 502)
    if payload.get("missing"):
        raise AppError("host_path_missing", "That folder does not exist on the host.", 404)
    if payload.get("error"):
        raise AppError("host_browse_failed", payload["error"], 502)
    return payload.get("dirs", [])


def _native_list(path):
    target = Path(path)
    if not target.exists() or not target.is_dir():
        raise AppError("host_path_missing", "That folder does not exist on the host.", 404)
    dirs = []
    try:
        with os.scandir(target) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(entry.name)
                except OSError:
                    continue
    except OSError as exc:
        raise AppError("host_browse_failed", str(exc), 502)
    dirs.sort(key=str.lower)
    return dirs[:MAX_ENTRIES]


def roots():
    items = _docker_roots() if _in_docker() else _native_roots()
    return {
        "roots": items,
        "runtime": "docker" if _in_docker() else "native",
        "message": "" if items else "Could not detect host folders automatically. Type a path to browse it.",
    }


def browse(path):
    clean = _validate_host_path(path)
    names = _docker_list(clean) if _in_docker() else _native_list(clean)
    return {
        "path": clean,
        "parent": _parent(clean),
        "entries": [{"name": name, "path": _join(clean, name), "kind": "folder"} for name in names],
    }
