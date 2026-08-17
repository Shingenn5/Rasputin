"""Run a deterministic, isolated coding-agent acceptance scenario.

The fixture deliberately uses a scripted model response so it can certify the
Rasputin orchestration path without requiring a downloaded model or network
access.  File edits still go through the real MCP patch implementation; test
execution is a bounded local subprocess in the fixture workspace.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_fixture(root: Path) -> None:
    (root / "calculator.py").write_text(
        "def add(left, right):\n    return left + right\n",
        encoding="utf-8",
    )
    (root / "test_calculator.py").write_text(
        "import unittest\n\nfrom calculator import add\n\n\nclass CalculatorTests(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n",
        encoding="utf-8",
    )


def _test_result(root: Path) -> dict:
    # Both edits have the same byte length. Clear bytecode so Windows' coarse
    # timestamp resolution cannot make the second test run import stale code.
    for cache in root.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    completed = subprocess.run(
        [os.environ.get("RASPUTIN_PYTHON", str(VENV_PYTHON)), "-B", "-m", "unittest", "discover", "-s", "."],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "exit_code": completed.returncode,
        "output": (completed.stdout + completed.stderr)[-4000:],
    }


async def run_acceptance() -> dict:
    # Imports happen after the isolated data directory is selected so no
    # fixture state can touch the operator's real store.
    from backend.core import security, workspace
    from backend.engine import agent
    from backend.engine import context as context_governor
    from backend.mcp.layer import McpLayer

    with tempfile.TemporaryDirectory(prefix="rasputin-coding-acceptance-") as temp:
        root = Path(temp)
        _write_fixture(root)
        subprocess.run(["git", "init", "--quiet"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.name=Rasputin Fixture", "-c", "user.email=fixture@localhost", "commit", "--quiet", "-m", "fixture"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        approved = workspace.approve(str(root), "Coding acceptance fixture", read_only=False, owner_username="admin")
        workspace.set_trusted(approved["id"], True)
        workspace.set_host_shell(approved["id"], True)
        security.save({
            **security.load(),
            "allow_file_read": True,
            "allow_file_write": True,
            "allow_shell_execution": True,
            "allow_model_tests": True,
            "approval_required_file_write": True,
        })
        workspace.set_workspace_commands(approved["id"], test="python -m unittest discover -s .")

        hub = agent.AgentHub()
        real_mcp = McpLayer()
        state = {"model_calls": 0, "tests": [], "patches": []}

        async def scripted_model(*_args, **_kwargs):
            state["model_calls"] += 1
            if state["model_calls"] == 1:
                return "", [{
                    "id": "acceptance-edit-1",
                    "name": "fs_patch",
                    "args": {
                        "path": "calculator.py",
                        "old_string": "return left + right",
                        "new_string": "return left - right",
                        "workspace_path": str(root),
                    },
                }]
            if state["model_calls"] == 2:
                return "The focused test still fails; I will inspect the failure before making another change.", []
            if state["model_calls"] == 3:
                return "", [{
                    "id": "acceptance-edit-2",
                    "name": "fs_patch",
                    "args": {
                        "path": "calculator.py",
                        "old_string": "return left - right",
                        "new_string": "return left + right",
                        "workspace_path": str(root),
                    },
                }]
            return "Implemented the fix, reran the test, and left the changes ready for review.", []

        async def broker_call(name, args, on_log=None):
            if name == "shell_exec":
                result = _test_result(root)
                state["tests"].append(result)
                return result
            result = await real_mcp.call_tool(name, args, on_log=on_log)
            if name == "fs_patch":
                state["patches"].append(result)
            return result

        hub.mcp.call_tool = broker_call
        task = agent.AgentTask(
            "Fix calculator addition and verify the focused test",
            "dry-run",
            "general",
            mode="code",
            workspace_path=str(root),
        )
        task.owner_id = "admin"
        hub._persist_session(task)
        sections = [context_governor.section("task", "Task", task.objective, required=True, priority=0)]
        with patch("backend.engine.agent._chat", new=scripted_model):
            result = await hub.governed_chat(task, "execution", "coder", sections)

        status = await real_mcp.git_status(workspace_path=str(root))
        diff = await real_mcp.git_diff(workspace_path=str(root))
        return {
            "evidence_mode": "mocked",
            "live_model": {
                "status": "skipped",
                "reason": "The existing harness uses a scripted model; no credentials or local model are invoked.",
            },
            "passed": (
                result.startswith("Implemented the fix")
                and len(state["tests"]) >= 2
                and state["tests"][0]["exit_code"] != 0
                and state["tests"][-1]["exit_code"] == 0
                and "return left + right" in (root / "calculator.py").read_text(encoding="utf-8")
            ),
            "model_calls": state["model_calls"],
            "test_runs": state["tests"],
            "patch_results": state["patches"],
            "final_file": (root / "calculator.py").read_text(encoding="utf-8"),
            "task_trace_kinds": [entry.get("kind") for entry in task.trace],
            "task_logs": task.logs[-12:],
            "git_status": status,
            "git_diff": diff,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable evidence")
    args = parser.parse_args(argv)
    # SQLite may still have a connection owned by imported backend modules at
    # interpreter shutdown on Windows. Leave this isolated scratch directory in
    # the OS temp location instead of risking a cleanup race or touching repo
    # data; the OS can reclaim it normally.
    data_dir = tempfile.mkdtemp(prefix="rasputin-coding-acceptance-data-")
    os.environ["RASPUTIN_DATA_DIR"] = data_dir
    evidence = asyncio.run(run_acceptance())
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
