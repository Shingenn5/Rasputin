"""Task-bound agent tools for approval-reviewed snapshot execution."""
import asyncio

from backend.core import approvals, runtime_store as store, sandbox_execution as execution


def _task(task_id):
    if not task_id:
        raise PermissionError("Sandbox tools require a persisted task identity.")
    with store.connect() as conn:
        row = conn.execute("SELECT owner_id,workspace,execution_workspace,status FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row or row["status"] not in {"queued", "running", "paused"}:
        raise PermissionError("Task is unavailable for sandbox execution.")
    return row


async def sandbox_prepare(files, arguments, workspace_path=None, timeout_seconds=30,
                          _task_id=None, _tool_call_id=None):
    task = _task(_task_id)
    # Never let model-supplied paths replace the persisted task workspace.
    root = task["execution_workspace"] or task["workspace"]
    request = await asyncio.to_thread(execution.create_request, task["owner_id"], root, files,
                                      arguments, task_id=_task_id, timeout=timeout_seconds)
    return {"request_id": request["plan"]["request_id"], "approval_id": request["approval_id"],
            "snapshot_sha256": request["plan"]["snapshot_sha256"], "status": request["state"],
            "message": "The operator must approve this snapshot and argument vector. Call sandbox_run with this request id; it waits for approval and returns actual execution evidence."}


async def sandbox_run(request_id, _task_id=None, _tool_call_id=None):
    task = _task(_task_id)
    request = execution.get_request(request_id, task["owner_id"])
    if request["plan"]["task_id"] != _task_id:
        raise PermissionError("Execution request belongs to a different task.")
    try:
        while True:
            _task(_task_id)  # cancellation and task state remain authoritative
            approval = approvals.get(request["approval_id"])
            if not approval or approval["status"] not in {"pending", "approved"}:
                raise PermissionError("Sandbox execution approval was denied, expired, or consumed.")
            if approval["status"] == "approved":
                break
            await asyncio.sleep(0.25)
        pending = asyncio.create_task(asyncio.to_thread(execution.execute_request, request_id, task["owner_id"]))
        try:
            while not pending.done():
                await asyncio.sleep(0.1)
                _task(_task_id)
            return await pending
        except (PermissionError, asyncio.CancelledError):
            execution.cancel_request(request_id, task["owner_id"])
            # Keep the worker observable through cleanup, even if task cancellation
            # arrives while its Windows process is still terminating.
            await asyncio.shield(pending)
            raise
    except (PermissionError, asyncio.CancelledError):
        execution.cancel_request(request_id, task["owner_id"])
        raise
