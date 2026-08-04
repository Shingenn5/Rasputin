"""Create and verify isolated Git worktrees for explicitly opted-in code tasks.

This is intentionally a narrow safety boundary.  It only provisions a clean,
top-level local Git checkout into a generated folder under Rasputin's data
directory.  It does not fetch, stash, initialize submodules, apply changes
back to the source checkout, or clean itself up automatically.
"""

import os
import re
import subprocess
from pathlib import Path

from backend.core import audit
from backend.core import workspace
from backend.core.datadir import data_dir


class TaskWorktreeError(ValueError):
    """An isolation request cannot safely be fulfilled."""


def worktree_root():
    root = (data_dir() / "task-worktrees").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def hooks_root():
    """A deliberately empty hooks path for task-worktree Git invocations.

    Git treats a missing hooks directory as empty.  Do not create it here:
    `plan()` may be probing a source repo and must not write to that repo even
    when an operator accidentally configured RASPUTIN_DATA_DIR beneath it.
    """
    return (data_dir(create=False) / "task-worktree-hooks").resolve()


def _is_relative_to(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _require_task_id(task_id):
    value = str(task_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
        raise TaskWorktreeError("invalid task id for isolated workspace")
    return value


def _git_env():
    """Remove inherited Git routing/config overrides for worktree management."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    env.update({
        # Provisioning never contacts a remote or needs interactive credentials.
        "GIT_TERMINAL_PROMPT": "0",
        # Keep ordinary system/global configuration (notably core.autocrlf),
        # otherwise the clean preflight can misread a valid checkout as dirty.
        # Routing environment overrides are stripped above, while hooks,
        # fsmonitor, and external diffs are explicitly disabled in `_git`.
        "GIT_OPTIONAL_LOCKS": "0",
    })
    return env


def _git(cwd, args, timeout=30, allow_failure=False):
    command = [
        "git",
        "-c", f"core.hooksPath={hooks_root()}",
        "-c", "core.fsmonitor=false",
        "-c", "diff.external=",
        "-c", "submodule.recurse=false",
        *args,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=_git_env(),
        )
    except FileNotFoundError as exc:
        raise TaskWorktreeError("Git is required to isolate this coding task") from exc
    except subprocess.TimeoutExpired as exc:
        raise TaskWorktreeError(f"Git timed out while {' '.join(args[:3])}") from exc
    if result.returncode and not allow_failure:
        detail = (result.stderr or result.stdout or "Git command failed").strip().replace("\n", " ")
        raise TaskWorktreeError(detail[:500])
    return result


def _source_root(source_workspace):
    source = workspace.resolve_path(source_workspace)
    item = workspace.workspace_for_path(source)
    if not item or item.get("task_root"):
        raise TaskWorktreeError("choose an approved source workspace, not an existing task worktree")
    storage = data_dir(create=False).resolve()
    if source == storage or _is_relative_to(storage, source) or _is_relative_to(source, storage):
        raise TaskWorktreeError(
            "Rasputin's data directory overlaps the source workspace; configure a separate "
            "RASPUTIN_DATA_DIR before requesting workspace isolation"
        )
    top_level = Path(_git(source, ["rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    if top_level != source:
        raise TaskWorktreeError("workspace isolation requires the repository's top-level folder")
    return source, item


def plan(task_id, source_workspace):
    """Return deterministic metadata before any worktree is created."""
    task_id = _require_task_id(task_id)
    source, source_item = _source_root(source_workspace)
    target = (worktree_root() / task_id).resolve()
    if not _is_relative_to(target, worktree_root()) or target == worktree_root():
        raise TaskWorktreeError("isolated worktree path escaped Rasputin data")
    return {
        "requested": True,
        "state": "provisioning",
        "taskId": task_id,
        "sourceWorkspace": str(source),
        "sourceWorkspaceId": source_item.get("id"),
        "executionWorkspace": str(target),
        "branch": f"rasputin/task-{task_id}",
        "baseSha": "",
        "error": "",
    }


def _ensure_clean_source(metadata):
    source = Path(metadata.get("sourceWorkspace") or "").resolve()
    if not source.exists() or not source.is_dir():
        raise TaskWorktreeError("source workspace is no longer available")
    storage = data_dir(create=False).resolve()
    if source == storage or _is_relative_to(storage, source) or _is_relative_to(source, storage):
        raise TaskWorktreeError("Rasputin's data directory overlaps the source workspace")
    top_level = Path(_git(source, ["rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    if top_level != source:
        raise TaskWorktreeError("source workspace is no longer the repository top-level")
    status = _git(source, ["status", "--porcelain=v1", "--untracked-files=all"]).stdout
    if status.strip():
        raise TaskWorktreeError("source workspace has uncommitted changes; review or stash them before requesting isolation")
    base_sha = _git(source, ["rev-parse", "--verify", "HEAD"]).stdout.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", base_sha):
        raise TaskWorktreeError("source workspace has no valid HEAD commit")
    return source, base_sha


def _branch_exists(source, branch):
    return _git(source, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], allow_failure=True).returncode == 0


def _worktree_entry(source, target):
    output = _git(source, ["worktree", "list", "--porcelain"]).stdout
    entries = []
    current = {}
    for line in output.splitlines():
        if not line:
            if current:
                entries.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value.strip()
    if current:
        entries.append(current)
    target = Path(target).resolve()
    for entry in entries:
        raw_path = entry.get("worktree")
        if not raw_path:
            continue
        try:
            if Path(raw_path).resolve() == target:
                return entry
        except OSError:
            continue
    return None


def create(metadata):
    """Create the planned worktree once, with no implicit fallback to source."""
    task_id = _require_task_id(metadata.get("taskId"))
    source, base_sha = _ensure_clean_source(metadata)
    target = Path(metadata.get("executionWorkspace") or "").resolve()
    branch = str(metadata.get("branch") or "")
    if target.exists():
        raise TaskWorktreeError("isolated worktree path already exists; refusing to overwrite it")
    if not _is_relative_to(target, worktree_root()) or target == worktree_root():
        raise TaskWorktreeError("isolated worktree path escaped Rasputin data")
    if _is_relative_to(target, source) or _is_relative_to(source, target):
        raise TaskWorktreeError("isolated worktree path overlaps the source workspace")
    if not re.fullmatch(r"rasputin/task-[A-Za-z0-9_.-]{1,80}", branch):
        raise TaskWorktreeError("invalid isolated task branch")
    if _branch_exists(source, branch):
        raise TaskWorktreeError("isolated task branch already exists; refusing to reuse it")

    audit.log("task_worktree_provisioning", {
        "task_id": task_id,
        "source": str(source),
        "worktree": str(target),
        "branch": branch,
        "base_sha": base_sha,
    })
    try:
        _git(source, ["worktree", "add", "-b", branch, str(target), base_sha], timeout=60)
        workspace.register_task_root(task_id, target, metadata.get("sourceWorkspaceId") or str(source))
    except Exception as exc:
        audit.log("task_worktree_provision_failed", {
            "task_id": task_id,
            "source": str(source),
            "worktree": str(target),
            "error": str(exc),
        })
        if isinstance(exc, TaskWorktreeError):
            raise
        raise TaskWorktreeError(str(exc)) from exc
    result = {
        **metadata,
        "state": "ready",
        "baseSha": base_sha,
        "executionWorkspace": str(target),
        "error": "",
    }
    audit.log("task_worktree_ready", {
        "task_id": task_id,
        "source": str(source),
        "worktree": str(target),
        "branch": branch,
        "base_sha": base_sha,
    })
    return result


def verify(metadata):
    """Verify a retained worktree on resume without recreating or overwriting it."""
    task_id = _require_task_id(metadata.get("taskId"))
    source = Path(metadata.get("sourceWorkspace") or "").resolve()
    target = Path(metadata.get("executionWorkspace") or "").resolve()
    branch = str(metadata.get("branch") or "")
    if not source.exists() or not target.exists():
        raise TaskWorktreeError("retained isolated worktree is missing; Rasputin will not recreate it automatically")
    storage = data_dir(create=False).resolve()
    if source == storage or _is_relative_to(storage, source) or _is_relative_to(source, storage):
        raise TaskWorktreeError("Rasputin's data directory overlaps the source workspace")
    if not _is_relative_to(target, worktree_root()) or target == worktree_root():
        raise TaskWorktreeError("retained isolated worktree is outside Rasputin's task-worktree directory")
    entry = _worktree_entry(source, target)
    if not entry or entry.get("branch") != f"refs/heads/{branch}":
        raise TaskWorktreeError("retained isolated worktree no longer matches its recorded task branch")
    top_level = Path(_git(target, ["rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    if top_level != target:
        raise TaskWorktreeError("retained isolated worktree root is invalid")
    workspace.register_task_root(task_id, target, metadata.get("sourceWorkspaceId") or str(source))
    return {**metadata, "state": "ready", "error": ""}
