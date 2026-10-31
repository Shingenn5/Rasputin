"""An isolated coding task must receive real, successful tool calls."""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-agent-evidence-"))

from backend.engine import agent, context


class AgentExecutionEvidenceTests(unittest.TestCase):
    def run_phase(self, responses, result=None, failure=None, isolated=True, phase="execution"):
        hub = agent.AgentHub()
        task = agent.AgentTask("Inspect and repair the fixture", "dry-run", "general", mode="code",
                               isolate_workspace=isolated, workspace_path=".")
        hub._persist_session(task)
        relay = AsyncMock(return_value=result or {"content": "fixture contents"}, side_effect=failure)
        hub.mcp.call_tool = relay
        chat = AsyncMock(side_effect=responses)
        sections = [context.section("task", "Task", task.objective, required=True, priority=0)]
        with patch("backend.engine.agent._chat", chat):
            try:
                answer = asyncio.run(hub.governed_chat(task, phase, "coder", sections, tools=[{"id": "fs_read"}]))
            except RuntimeError as exc:
                return task, chat, relay, exc
        return task, chat, relay, answer

    def test_prose_only_execution_retries_once_then_fails(self):
        task, chat, relay, outcome = self.run_phase([("I fixed everything.", []), ("Tests passed.", [])])
        self.assertIsInstance(outcome, RuntimeError)
        self.assertIn("without executing any tools", str(outcome))
        self.assertEqual(chat.await_count, 2)
        relay.assert_not_awaited()
        self.assertEqual(task.steps[-1]["status"], "error")
        self.assertEqual([event["detail"]["retry"] for event in task.trace if event["kind"] == "execution_tools_missing"], [True, False])

    def test_retry_can_recover_with_a_real_call(self):
        _, chat, relay, outcome = self.run_phase([
            ("Here is a tool call example.", []),
            ("", [{"id": "read-1", "name": "fs_read", "args": {"path": "items.cjs"}}]),
            ("The file was inspected.", []),
        ])
        self.assertEqual(outcome, "The file was inspected.")
        relay.assert_awaited_once()
        self.assertEqual(chat.await_count, 3)

    def test_blocked_call_is_not_execution_evidence(self):
        _, _, relay, outcome = self.run_phase([
            ("", [{"id": "blocked", "name": "shell_exec", "args": {}}]),
            ("Done.", []), ("Done.", []),
        ])
        self.assertIsInstance(outcome, RuntimeError)
        relay.assert_not_awaited()

    def test_failed_call_is_not_execution_evidence(self):
        _, _, relay, outcome = self.run_phase([
            ("", [{"id": "read-1", "name": "fs_read", "args": {"path": "items.cjs"}}]),
            ("Done.", []), ("Done.", []),
        ], failure=PermissionError("Access denied"))
        self.assertIsInstance(outcome, RuntimeError)
        relay.assert_awaited_once()

    def test_pending_approval_is_not_execution_evidence(self):
        _, _, _, outcome = self.run_phase([
            ("", [{"id": "read-1", "name": "fs_read", "args": {"path": "items.cjs"}}]),
            ("Done.", []), ("Done.", []),
        ], result={"approval_id": "pending-approval"})
        self.assertIsInstance(outcome, RuntimeError)

    def test_planning_and_nonisolated_answers_keep_existing_behavior(self):
        for options in ({"phase": "planning"}, {"isolated": False}):
            with self.subTest(options=options):
                _, _, relay, outcome = self.run_phase([("Read-only answer.", [])], **options)
                self.assertEqual(outcome, "Read-only answer.")
                relay.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
