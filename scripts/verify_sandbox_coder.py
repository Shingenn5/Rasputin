"""Run a real local model through an isolated edit/test/repair mission on Windows.

This maintainer check starts its own llama.cpp process and uses disposable app
state. It approves only this fixture's two editable files and exact test snapshots.
It never applies model edits to the source checkout or the installed application.
Evidence and the retained task worktree stay in the selected scratch directory.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
import uuid


FIXTURE = {
    "items.cjs": "exports.subtotal = items => items.reduce((sum, item) => sum + item.priceCents, 0);\n",
    "invoice.cjs": "const { subtotal } = require('./items.cjs');\nexports.total = (items, taxPercent) => subtotal(items) + taxPercent;\n",
    "check.cjs": """const assert = require('node:assert/strict');
const { subtotal } = require('./items.cjs');
const { total } = require('./invoice.cjs');
const cases = [
  ['empty cart', () => assert.equal(subtotal([]), 0)],
  ['quantity', () => assert.equal(subtotal([{priceCents: 125, quantity: 3}]), 375)],
  ['mixed cart', () => assert.equal(subtotal([{priceCents: 200, quantity: 2}, {priceCents: 75, quantity: 4}]), 700)],
  ['no tax', () => assert.equal(total([{priceCents: 125, quantity: 3}], 0), 375)],
  ['tax', () => assert.equal(total([{priceCents: 200, quantity: 2}], 10), 440)],
  ['round cents', () => assert.equal(total([{priceCents: 99, quantity: 3}], 7.5), 319)],
];
let failures = 0;
for (const [name, check] of cases) {
  try { check(); console.log('PASS', name); }
  catch (error) { failures++; console.log('FAIL', name, error.message); }
}
console.log(`${cases.length - failures}/${cases.length} checks passed`);
process.exitCode = failures ? 1 : 0;
""",
}
ARGUMENTS = ["--preserve-symlinks", "--preserve-symlinks-main", "check.cjs"]


def git(root, *arguments):
    result = subprocess.run(["git", "-c", "core.hooksPath=", "-c", "core.fsmonitor=false", *arguments],
                            cwd=root, capture_output=True, text=True, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    return result.stdout


async def mission(base, model_port):
    from backend.core import approvals, auth, sandbox_execution as execution, sandbox_runtime, security, workspace
    from backend.engine.agent import AgentHub
    from backend.engine.task_state import AgentTask
    from backend.models import registry

    auth.bootstrap()
    source = base / "source"
    source.mkdir()
    for name, content in FIXTURE.items():
        (source / name).write_text(content, encoding="utf-8")
    test_sha256 = hashlib.sha256((source / "check.cjs").read_bytes()).hexdigest()
    git(source, "init", "-b", "main")
    git(source, "add", "--", *FIXTURE)
    git(source, "-c", "user.name=Sandbox Verification", "-c", "user.email=verification@example.invalid",
        "commit", "-m", "Seed failing verification fixture")
    source_head = git(source, "rev-parse", "HEAD").strip()
    workspace.add(str(source), owner_username="admin", permission_profile={"read": True, "write": True})
    security.save({"allow_file_read": True, "allow_file_write": True, "allow_shell_execution": True,
                   "allow_web_search": False, "allow_github_read": False})
    await asyncio.to_thread(sandbox_runtime.install, "admin")
    registry.upsert({"key": "verification-coder", "name": "Local verification coder", "provider": "llamacpp",
                     "base_url": f"http://127.0.0.1:{model_port}/v1", "model": "verification-coder",
                     "role": "coder", "context_window": 16384,
                     "inference_profile": {"temperature": 0, "max_tokens": 2048}})
    task = AgentTask(
        "Repair the invoice fixture. First read items.cjs, invoice.cjs and check.cjs. "
        "Before editing, use sandbox_prepare with all three files and arguments " + json.dumps(ARGUMENTS) +
        ", then sandbox_run to observe the real failing baseline. Repair items.cjs and invoice.cjs: "
        "prices are integer cents, quantity multiplies each item, percentage tax is applied to the subtotal, "
        "and the final total is rounded to integer cents. Do not edit check.cjs. "
        "Prepare a new snapshot and run again after edits. Repair further if needed until the receipt says passed=true. "
        "Use fs_patch or fs_write for edits. Do not use shell_exec, git staging or commits. "
        "Leave changes in the isolated worktree for review and report the actual failed and passing receipts.",
        "verification-coder", "general", workspace_path=str(source), mode="code",
        isolate_workspace=True, memory_mode="suppress", reasoning="off",
    )
    task.owner_id = "admin"
    hub = AgentHub()
    hub.tasks[task.id] = task
    hub._wire(task)
    hub._persist_task(task)
    reviews = []
    running = asyncio.create_task(hub.run_task(task))
    last_log = 0
    try:
        deadline = time.monotonic() + 1200
        while not running.done():
            if time.monotonic() > deadline:
                await hub.cancel(task.id)
                raise TimeoutError("Local model mission exceeded 20 minutes")
            for approval in approvals.list_approvals("pending")["approvals"]:
                if approval["task_id"] != task.id:
                    continue
                allowed = False
                if approval["action_type"] == "sandbox_execute":
                    request_id = approval["redacted_detail"].get("request_id")
                    request = execution.get_request(request_id, "admin")
                    plan = request["plan"]
                    allowed = (plan["task_id"] == task.id and plan["arguments"] == ARGUMENTS
                               and set(plan["files"]) == set(FIXTURE) and plan["timeout"] <= 60
                               and plan["files"]["check.cjs"]["sha256"] == test_sha256)
                elif approval["action_type"] in {"fs_patch", "fs_write"} and task.execution_workspace:
                    path = Path(approval["redacted_detail"].get("path", "")).resolve()
                    allowed = path in {Path(task.execution_workspace) / name for name in ("items.cjs", "invoice.cjs")}
                if allowed:
                    approvals.approve(approval["id"], source="isolated_fixture", note="Exact disposable coding fixture only")
                else:
                    approvals.deny(approval["id"], source="isolated_fixture", note="Outside the fixture verification contract")
                reviews.append({"action": approval["action_type"], "approved": allowed,
                                "request_id": approval["redacted_detail"].get("request_id")})
            for line in task.logs[last_log:]:
                # Paths here refer only to the generated fixture, never user data.
                print(line.replace(str(base), "<fixture>"), flush=True)
            last_log = len(task.logs)
            await asyncio.sleep(.25)
        await running
    finally:
        if not running.done():
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
        execution.shutdown()
    receipts = []
    for review in reviews:
        if review["request_id"]:
            request = execution.get_request(review["request_id"], "admin")
            receipts.append({"plan": request["plan"], "receipt": request.get("receipt")})
    target = Path(task.execution_workspace) if task.execution_workspace else None
    diff = git(target, "diff", "--no-ext-diff", "--", *FIXTURE) if target else ""
    (base / "changes.diff").write_text(diff, encoding="utf-8")
    changed = git(target, "diff", "--name-only").splitlines() if target else []
    source_unchanged = git(source, "rev-parse", "HEAD").strip() == source_head and not git(source, "status", "--porcelain").strip()
    source_unchanged = source_unchanged and all((source / n).read_text(encoding="utf-8") == c for n, c in FIXTURE.items())
    evidence = [entry["receipt"] or {} for entry in receipts]
    failed_then_passed = (len(evidence) >= 2 and evidence[0].get("ran") is True
                          and evidence[0].get("exit_code") == 1 and evidence[-1].get("passed") is True)
    passed = (task.status == "done" and source_unchanged and failed_then_passed
              and set(changed) == {"items.cjs", "invoice.cjs"}
              and (target / "check.cjs").read_text(encoding="utf-8") == FIXTURE["check.cjs"])
    report = {"passed": passed, "task_status": task.status, "model_inference": "real local llama.cpp",
              "source_unchanged": source_unchanged, "changed_files": changed,
              "failed_then_passed": failed_then_passed, "reviews": reviews, "runs": receipts,
              "result": task.result, "logs": task.logs, "steps": task.steps,
              "installed_app_verified": False, "changes_applied_to_source": False}
    (base / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("passed", "task_status", "source_unchanged", "changed_files", "failed_then_passed")}), flush=True)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-dir", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True, help="Verified llama-server.exe, never a shell command")
    parser.add_argument("--model", type=Path, required=True, help="Existing local tool-capable GGUF, opened read-only")
    parser.add_argument("--port", type=int, default=8898)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    scratch = args.scratch_dir.resolve(strict=True)
    if os.name != "nt" or not args.scratch_dir.is_absolute() or scratch.is_relative_to(root) or root.is_relative_to(scratch):
        parser.error("Use an existing absolute scratch directory outside this repository on Windows")
    if not args.engine.is_absolute() or not args.engine.is_file() or not args.model.is_absolute() or not args.model.is_file():
        parser.error("Use existing absolute engine and model paths")
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged test port")
    with socket.socket() as check:
        check.bind(("127.0.0.1", args.port))
    base = scratch / ("sandbox-coder-" + uuid.uuid4().hex[:12])
    base.mkdir()
    identity = {}
    for label, path in (("engine", args.engine), ("model", args.model)):
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        identity[label] = {"name": path.name, "bytes": path.stat().st_size, "sha256": digest}
    (base / "inference-identity.json").write_text(json.dumps(identity, indent=2), encoding="utf-8")
    os.environ.update(RASPUTIN_DATA_DIR=str(base / "data"), RASPUTIN_ADMIN_USER="admin",
                      RASPUTIN_ADMIN_PASSWORD=secrets.token_urlsafe(24), RASPUTIN_DESKTOP_ONLY="0",
                      RASPUTIN_LOCALHOST_BYPASS="0", RASPUTIN_TEST_AUTH_BYPASS="0")
    sys.path.insert(0, str(root))
    command = [str(args.engine), "--model", str(args.model), "--host", "127.0.0.1", "--port", str(args.port),
               "--alias", "verification-coder", "--ctx-size", "16384", "--n-gpu-layers", "99", "--jinja", "--parallel", "1"]
    with (base / "inference.log").open("w", encoding="utf-8") as log:
        runtime_env = {key: value for key, value in os.environ.items()
                       if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA"}}
        runtime_env["LLAMA_CACHE"] = str(base / "cache")
        server = subprocess.Popen(command, stdout=log, stderr=log, cwd=base, env=runtime_env,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 180
            while True:
                if server.poll() is not None:
                    raise RuntimeError("Isolated inference process exited; inspect inference.log")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError("Isolated inference readiness expired")
                time.sleep(.25)
            return asyncio.run(mission(base, args.port))
        finally:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            print(f"Coding mission evidence: {base}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
