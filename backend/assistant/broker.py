"""Allowlisted adapters for the assistant broker boundary.

The assistant runtime owns plan, workspace, and approval validation.  This
module owns the final adapter lookup and keeps each adapter's invocation
surface explicit.  In particular, host actions receive a normalized path and
fixed argv; callers never provide an arbitrary command string.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend import warsat
from backend.core.response import AppError


DISPATCH_CONTRACT_VERSION = "0.1"

# This metadata is also the UI contract for the future assistant command
# center: it describes the consequence of dispatch without exposing an
# implementation-specific command surface.
OPERATION_METADATA: dict[str, dict[str, Any]] = {
    "docker_status": {
        "adapter": "warsat.containers",
        "action_kind": "read_only",
        "requires_workspace": False,
        "side_effects": False,
        "host_mutation": False,
    },
    "open_vscode": {
        "adapter": "vscode.cli",
        "action_kind": "host_action",
        "requires_workspace": True,
        "side_effects": True,
        "host_mutation": True,
    },
}

READ_ONLY_OPERATIONS = {name for name, metadata in OPERATION_METADATA.items() if not metadata["side_effects"]}
HOST_ACTION_OPERATIONS = {name for name, metadata in OPERATION_METADATA.items() if metadata["side_effects"]}


def supported_operations() -> list[str]:
    """Return operations with a concrete adapter implementation."""

    return sorted(OPERATION_METADATA)


def operation_metadata() -> dict[str, dict[str, Any]]:
    """Return a copy of the adapter consequence metadata for API/UI use."""

    return {name: dict(metadata) for name, metadata in OPERATION_METADATA.items()}


def _clean_operation(operation: str) -> str:
    clean_operation = str(operation or "").strip().lower()
    if clean_operation not in OPERATION_METADATA:
        raise AppError(
            "assistant_broker_adapter_unavailable",
            "No executable adapter is registered for that operation.",
            409,
        )
    return clean_operation


def _workspace_directory(workspace_path: str | Path | None) -> Path:
    if not workspace_path:
        raise AppError(
            "assistant_broker_workspace_required",
            "This host action requires an approved workspace.",
            409,
        )
    candidate = Path(str(workspace_path)).expanduser()
    if not candidate.is_absolute():
        raise AppError(
            "assistant_broker_workspace_invalid",
            "The broker requires an absolute approved workspace path.",
            409,
        )
    try:
        target = candidate.resolve()
    except OSError as exc:
        raise AppError("assistant_broker_workspace_invalid", "The approved workspace path could not be resolved.", 409) from exc
    if not target.exists() or not target.is_dir():
        raise AppError("assistant_broker_workspace_invalid", "The approved workspace folder is missing.", 409)
    return target


def _resolve_vscode_executable() -> str:
    """Resolve only the platform's VS Code CLI from PATH.

    No user-provided executable or command text is accepted.  Windows commonly
    exposes ``code.cmd`` while Linux/macOS expose ``code``; ``code.exe`` is
    checked first on Windows for installations that include the native shim.
    """

    candidates = ["code.exe", "code.cmd", "code"] if os.name == "nt" else ["code"]
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            return executable
    raise AppError(
        "assistant_broker_dependency_missing",
        "The VS Code CLI was not found on PATH. Install or expose the `code` command before dispatching.",
        503,
    )


def _dispatch_docker_status() -> dict[str, Any]:
    result = warsat.containers()
    return {
        "contract_version": DISPATCH_CONTRACT_VERSION,
        "operation": "docker_status",
        "adapter": OPERATION_METADATA["docker_status"]["adapter"],
        "result": result,
        "action_state": "completed",
        "side_effects": False,
        "host_mutation": False,
        "execution_started": False,
    }


def _dispatch_open_vscode(workspace_path: str | Path | None) -> dict[str, Any]:
    target = _workspace_directory(workspace_path)
    executable = _resolve_vscode_executable()
    # Keep this argv fixed and inspectable.  In particular, do not add shell=True
    # or pass a command assembled from request input.
    argv = [executable, "--reuse-window", str(target)]
    try:
        process = subprocess.Popen(argv, cwd=str(target), shell=False, close_fds=True)
    except OSError as exc:
        raise AppError("assistant_broker_launch_failed", "VS Code could not be launched for the approved workspace.", 503) from exc
    return {
        "contract_version": DISPATCH_CONTRACT_VERSION,
        "operation": "open_vscode",
        "adapter": OPERATION_METADATA["open_vscode"]["adapter"],
        "result": {
            "launched": True,
            "pid": getattr(process, "pid", None),
            "workspace": str(target),
            "argv": argv,
        },
        "action_state": "completed",
        "side_effects": True,
        "host_mutation": True,
        "execution_started": True,
    }


def dispatch(operation: str, workspace_path: str | Path | None = None) -> dict[str, Any]:
    """Run one allowlisted adapter and return its bounded result."""

    clean_operation = _clean_operation(operation)
    if clean_operation == "docker_status":
        return _dispatch_docker_status()
    if clean_operation == "open_vscode":
        return _dispatch_open_vscode(workspace_path)
    # Keep a defensive fallback if metadata and adapters diverge.
    raise AppError("assistant_broker_adapter_unavailable", "No executable adapter is registered for that operation.", 409)
