"""Approval-bound snapshot execution and owner-scoped receipts.

The installed toolchain acquisition and agent tool wiring are separate consumers.
No host shell is used, and results never apply changes to the source workspace.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import uuid

from backend.core import approvals, audit, auth, runtime_store as store, security, workspace
from backend.core.datadir import data_dir
from backend.core import windows_sandbox

_RUNTIME_KEY = "sandbox_toolchain_v1"
_REQUEST_PREFIX = "sandbox_request_v1:"
_MAX_FILES = 256
_MAX_BYTES = 8 * 1024 * 1024
_active = {}
_lock = threading.RLock()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _actor(username):
    user = next((item for item in auth.list_users() if item["username"] == username), None)
    if not user or not user["enabled"] or user["role"] not in {"admin", "member"}:
        raise PermissionError("An enabled local member account is required.")
    return user


def configure_toolchain(executable, username):
    if _actor(username)["role"] != "admin":
        raise PermissionError("Administrator access is required to pin a toolchain.")
    path = Path(executable)
    if not path.is_absolute() or not path.is_file() or path.suffix.lower() != ".exe":
        raise ValueError("Select an absolute self-contained Windows executable.")
    path = path.resolve(strict=True)
    # Pin bytes; do not execute a toolchain on the host to discover its version.
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    runtime = {"path": str(path), "sha256": digest, "name": path.name}
    store.set_kv(_RUNTIME_KEY, runtime)
    audit.log("sandbox_toolchain_pinned", {"sha256": digest})
    return {"name": path.name, "sha256": digest}


def capability():
    runtime = store.get_kv(_RUNTIME_KEY)
    return {"configured": bool(runtime), "boundary": "windows_appcontainer",
            "windows": os.name == "nt", "toolchain": {key: runtime[key] for key in ("name", "sha256")} if runtime else None,
            "packaged_toolchain": False, "experimental": True, "source_workspace_is_modified": False}


def _relative(value):
    if not isinstance(value, str) or not value or "\0" in value or ":" in value:
        raise ValueError("Snapshot paths must be relative file paths.")
    path = Path(value)
    if path.is_absolute() or path.drive or not path.parts or any(part in {".", ".."} for part in path.parts):
        raise ValueError("Snapshot paths must stay inside the workspace.")
    for part in path.parts:
        if part.rstrip(" .") != part or any(char in part for char in '<>"|?*'):
            raise ValueError("Snapshot paths cannot use Windows filename aliases.")
        lowered = part.casefold()
        if lowered.split(".")[0] in {"con", "prn", "aux", "nul", *{f"com{i}" for i in range(1, 10)}, *{f"lpt{i}" for i in range(1, 10)}}:
            raise ValueError("Device names cannot be snapshot paths.")
        if lowered in {".git", ".ssh", ".aws", ".azure", "id_rsa", "id_ed25519"} or lowered.startswith(".env"):
            raise ValueError("Credentials and Git administration files cannot be execution inputs.")
    if path.suffix.lower() in {".pem", ".key", ".pfx", ".p12"}:
        raise ValueError("Private key files cannot be execution inputs.")
    return path.as_posix()


def _read_file(root, relative, remaining):
    path = root / relative
    # Reject every reparse point, not just links resolving outside the root.
    for ancestor in [path, *path.parents]:
        if ancestor.lstat().st_file_attributes & 0x400:
            raise ValueError("Snapshot paths cannot traverse reparse points.")
        if ancestor == root:
            break
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("Snapshot path escaped its workspace.")
    with path.open("rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("Snapshot inputs must be ordinary files.")
        # Recheck the opened handle before reading, including an ancestor changed
        # concurrently after the lexical/reparse checks above.
        import ctypes as C
        from ctypes import wintypes as W
        import msvcrt
        kernel = C.WinDLL("kernel32", use_last_error=True)
        kernel.GetFinalPathNameByHandleW.argtypes = [W.HANDLE, W.LPWSTR, W.DWORD, W.DWORD]
        kernel.GetFinalPathNameByHandleW.restype = W.DWORD
        final = C.create_unicode_buffer(32768)
        length = kernel.GetFinalPathNameByHandleW(msvcrt.get_osfhandle(source.fileno()), final, len(final), 0)
        if not length or length >= len(final) or not Path(final.value.removeprefix("\\\\?\\")).is_relative_to(root):
            raise ValueError("Opened snapshot file is outside the workspace.")
        content = source.read(remaining + 1)
        if len(content) > remaining:
            raise ValueError("Snapshot exceeds the 8 MiB execution input limit.")
        return content


def _access(root, username, task_id=None):
    user = _actor(username)
    security.require("allow_file_read")
    security.require("allow_shell_execution")
    workspace.require_user_access(str(root), username, "contributor", user["role"] == "admin")
    workspace.require_path_permission(root, "read")
    if task_id:
        with store.connect() as conn:
            task = conn.execute("SELECT owner_id,workspace,execution_workspace,status FROM tasks WHERE id=?", (task_id,)).fetchone()
        if (not task or task["owner_id"] != username or task["status"] not in {"queued", "running", "paused"}
                or str(root) not in {str(workspace.resolve_path(task["workspace"])), task["execution_workspace"]}):
            raise PermissionError("Task owner, workspace, or execution state does not match.")


def _request(request_id, username):
    if not re.fullmatch(r"exec_[0-9a-f]{32}", str(request_id)):
        raise ValueError("Invalid execution request id.")
    request = store.get_kv(_REQUEST_PREFIX + request_id)
    if not request or request["owner_id"] != username:
        raise PermissionError("Execution request is unavailable to this account.")
    return request


def get_request(request_id, username):
    _actor(username)
    with _lock:
        request = _request(request_id, username)
        if request["state"] == "running" and request_id not in _active:
            request["state"] = "interrupted"
            request["receipt"] = {"request_id": request_id, "ran": None, "passed": False,
                                  "termination_reason": "owner_interrupted", "finished_at": store.now()}
            store.set_kv(_REQUEST_PREFIX + request_id, request)
    return request


def create_request(username, workspace_ref, file_paths, arguments, *, task_id=None, timeout=30):
    if os.name != "nt":
        raise ValueError("Snapshot execution currently requires Windows.")
    root = workspace.resolve_path(workspace_ref).resolve(strict=True)
    _access(root, username, task_id)
    storage = data_dir().resolve()
    if root.is_relative_to(storage) or storage.is_relative_to(root):
        # Approved task worktrees are intentionally under application storage.
        task_root = workspace.task_root_for_path(root)
        if not task_root or Path(task_root["root"]).resolve() != root:
            raise ValueError("Execution sources cannot overlap application storage.")
    runtime = store.get_kv(_RUNTIME_KEY)
    if not runtime:
        raise ValueError("An administrator must pin a self-contained toolchain first.")
    if not isinstance(file_paths, list) or not 1 <= len(file_paths) <= _MAX_FILES:
        raise ValueError("Select between 1 and 256 snapshot files.")
    if (not isinstance(arguments, list) or not arguments or len(arguments) > 64
            or any(not isinstance(arg, str) or "\0" in arg or len(arg) > 4096 for arg in arguments)
            or sum(len(arg) for arg in arguments) > 16000):
        raise ValueError("Provide a bounded argument vector, never a shell command.")
    if type(timeout) is not int or not 1 <= timeout <= 60:
        raise ValueError("Execution timeout must be between 1 and 60 seconds.")
    files, manifests, total = {}, {}, 0
    for value in file_paths:
        relative = _relative(value)
        if relative.casefold() in {name.casefold() for name in files}:
            raise ValueError("Snapshot paths must be unique.")
        content = _read_file(root, relative, _MAX_BYTES - total)
        files[relative] = content
        total += len(content)
        manifests[relative] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    request_id = "exec_" + uuid.uuid4().hex
    plan = {"request_id": request_id, "owner_id": username, "task_id": task_id,
            "workspace": str(root), "files": manifests, "snapshot_sha256": _digest(manifests),
            "toolchain": runtime, "arguments": arguments, "timeout": timeout}
    plan_hash = _digest(plan)
    folder = data_dir() / "execution-requests" / request_id
    folder.mkdir(parents=True)
    try:
        for relative, content in files.items():
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        approval = approvals.create("sandbox_execute", {"request_id": request_id, "request_digest": plan_hash,
                                     "arguments": arguments, "snapshot_sha256": plan["snapshot_sha256"],
                                     "toolchain_sha256": runtime["sha256"]},
                                    task_id=task_id, workspace=str(root), owner_id=username)
        request = {"plan": plan, "plan_sha256": plan_hash, "owner_id": username,
                   "approval_id": approval["id"], "state": "pending_approval", "created_at": store.now(), "receipt": None}
        store.set_kv(_REQUEST_PREFIX + request_id, request)
        audit.log("sandbox_request_created", {"request_id": request_id, "task_id": task_id, "plan_sha256": plan_hash})
        return request
    except Exception:
        # Keep failed preparation inspectable; never execute a partial request.
        audit.log("sandbox_request_preparation_failed", {"request_id": request_id})
        raise


def _consume_approval(request):
    plan = request["plan"]
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id=?", (request["approval_id"],)).fetchone()
        detail = store._loads(row["redacted_detail"], {}) if row else {}
        if (not row or row["owner_id"] != request["owner_id"] or row["task_id"] != plan["task_id"]
                or row["action_type"] != "sandbox_execute" or row["workspace"] != plan["workspace"]
                or detail.get("request_digest") != request["plan_sha256"]):
            raise PermissionError("Approval does not match the immutable execution request.")
        result = conn.execute("UPDATE approvals SET status='executed',executed_at=? WHERE id=? AND status='approved' AND executed_at IS NULL AND expires_at>?",
                              (store.now(), request["approval_id"], store.now()))
        if result.rowcount != 1:
            raise PermissionError("Execution approval is pending, expired, denied, or already consumed.")
        conn.commit()


def execute_request(request_id, username):
    try:
        return _execute_request(request_id, username)
    except (PermissionError, ValueError, OSError) as exc:
        with _lock:
            request = _request(request_id, username)
            if request["state"] == "pending_approval":
                request["last_refusal"] = {"request_id": request_id, "ran": False, "passed": False,
                                           "termination_reason": "admission_refused", "error_type": type(exc).__name__,
                                           "finished_at": store.now()}
                store.set_kv(_REQUEST_PREFIX + request_id, request)
        raise


def _execute_request(request_id, username):
    # Serialize admission; release the lock during the bounded OS execution.
    with _lock:
        request = _request(request_id, username)
        if request["state"] != "pending_approval":
            raise PermissionError("This execution request cannot be started again.")
        plan = request["plan"]
        _access(Path(plan["workspace"]), username, plan["task_id"])
        if _digest(plan) != request["plan_sha256"] or store.get_kv(_RUNTIME_KEY) != plan["toolchain"]:
            raise PermissionError("Execution plan or configured toolchain changed after review.")
        snapshot = data_dir() / "execution-requests" / request_id
        files = {}
        for relative, manifest in plan["files"].items():
            content = _read_file(snapshot, relative, manifest["bytes"])
            if len(content) != manifest["bytes"] or hashlib.sha256(content).hexdigest() != manifest["sha256"]:
                raise PermissionError("Approved snapshot content changed.")
            files[relative] = content
        _consume_approval(request)
        cancel = threading.Event()
        _active[request_id] = cancel
        request.update(state="running", started_at=store.now())
        store.set_kv(_REQUEST_PREFIX + request_id, request)
    receipt = {"request_id": request_id, "owner_id": username, "task_id": plan["task_id"],
               "plan_sha256": request["plan_sha256"], "snapshot_sha256": plan["snapshot_sha256"],
               "toolchain_sha256": plan["toolchain"]["sha256"], "approval_id": request["approval_id"],
               "arguments": plan["arguments"], "started_at": request["started_at"], "passed": False, "ran": False}
    try:
        scratch = data_dir() / "execution-scratch"
        scratch.mkdir(exist_ok=True)
        result = windows_sandbox.probe(plan["toolchain"]["path"], files, plan["arguments"],
                                       scratch_parent=scratch, timeout=plan["timeout"], cancel=cancel,
                                       expected_executable_sha256=plan["toolchain"]["sha256"])
        receipt.update(result)
        receipt["passed"] = (result["termination_reason"] == "exited" and result["exit_code"] == 0
                             and not result["truncated"] and result["evidence_complete"])
    except windows_sandbox.SandboxRefused:
        receipt.update(ran=False, termination_reason="toolchain_identity_changed")
    except Exception as exc:
        # Conservative: a runner exception cannot establish that code never ran.
        receipt.update(ran=None, termination_reason="runner_error", error_type=type(exc).__name__)
    finally:
        receipt["finished_at"] = store.now()
        with _lock:
            _active.pop(request_id, None)
            request.update(state="finished", receipt=receipt)
            store.set_kv(_REQUEST_PREFIX + request_id, request)
        audit.log("sandbox_request_finished", {"request_id": request_id, "ran": receipt["ran"], "passed": receipt["passed"],
                                               "termination_reason": receipt["termination_reason"]})
    return receipt


def cancel_request(request_id, username):
    _actor(username)
    with _lock:
        request = _request(request_id, username)
        if request_id in _active:
            _active[request_id].set()
        elif request["state"] == "pending_approval":
            request.update(state="cancelled", receipt={"request_id": request_id, "ran": False, "passed": False,
                                                       "termination_reason": "cancelled_before_launch", "finished_at": store.now()})
            store.set_kv(_REQUEST_PREFIX + request_id, request)
    return get_request(request_id, username)


def recover():
    """Startup recovery never replays commands or reuses a consumed approval."""
    with _lock:
        scratch = data_dir() / "execution-scratch"
        resources = windows_sandbox.recover_abandoned(scratch) if os.name == "nt" and scratch.exists() else []
        with store.connect() as conn:
            rows = conn.execute("SELECT key,value FROM runtime_kv WHERE key LIKE ?", (_REQUEST_PREFIX + "%",)).fetchall()
        interrupted = 0
        for row in rows:
            request = store._loads(row["value"], {})
            request_id = request.get("plan", {}).get("request_id")
            if request.get("state") == "running" and request_id not in _active:
                request.update(state="interrupted", receipt={"request_id": request_id, "ran": None, "passed": False,
                                                             "termination_reason": "owner_interrupted", "finished_at": store.now()})
                store.set_kv(row["key"], request)
                interrupted += 1
        return {"resources": resources, "interrupted_requests": interrupted}


def shutdown():
    with _lock:
        for cancel in _active.values():
            cancel.set()
