import asyncio
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


TEST_ROOT = Path(tempfile.mkdtemp(prefix="rasputin-testing-mode-"))
os.environ["RASPUTIN_DATA_DIR"] = str(TEST_ROOT / "data")

from backend.core import runtime_store as store  # noqa: E402
from backend.engine import agent  # noqa: E402


class TestingModeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._previous_data_dir = store.DATA_DIR
        cls._previous_db_file = store.DB_FILE
        store.DATA_DIR = TEST_ROOT / "data"
        store.DB_FILE = store.DATA_DIR / "rasputin.db"
        store.init_db()

    @classmethod
    def tearDownClass(cls):
        store.DATA_DIR = cls._previous_data_dir
        store.DB_FILE = cls._previous_db_file
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def _task(self, hub, mode, objective):
        task = agent.AgentTask(
            objective,
            "dry-run",
            "general",
            mode=mode,
            requested_mode=mode,
            workspace_path=str(TEST_ROOT / "workspace"),
        )
        task.owner_id = "testing-owner"
        hub.tasks[task.id] = task
        hub._wire(task)
        hub._persist_task(task)
        hub._add_message(task.session_id, task.id, "user", objective)
        return task

    def test_code_dry_run_is_bounded_private_and_non_mutating(self):
        marker = "INTERNAL_SECRET_MARKER_" + ("x" * 12000)
        hub = agent.AgentHub()
        task = self._task(hub, "code", "Refactor safely. " + marker)

        with patch.object(hub, "plan", new=AsyncMock(side_effect=AssertionError("plan must not run"))), \
                patch.object(hub, "execute", new=AsyncMock(side_effect=AssertionError("execute must not run"))), \
                patch.object(hub, "reflect", new=AsyncMock(side_effect=AssertionError("reflect must not run"))), \
                patch.object(hub, "chat_reply", new=AsyncMock(side_effect=AssertionError("chat must not run"))), \
                patch("backend.engine.agent._chat", new=AsyncMock(side_effect=AssertionError("model chat must not run"))), \
                patch("backend.engine.agent.model_providers.chat", new=AsyncMock(side_effect=AssertionError("provider must not run"))), \
                patch.object(hub.mcp, "call_tool", new=AsyncMock(side_effect=AssertionError("tool must not run"))):
            asyncio.run(hub.run_task(task))

        self.assertEqual(task.status, "done")
        self.assertEqual(task.progress, 100)
        self.assertIn("Code", task.result)
        self.assertIn("No files were changed", task.result)
        self.assertIn("healthy tool-capable model", task.result)
        self.assertNotIn(marker, task.result)
        self.assertNotIn(marker, "\n".join(task.logs))
        self.assertNotIn(marker, json.dumps(task.outputs))
        self.assertNotIn(marker, json.dumps(task.trace))
        self.assertTrue(any(item["kind"] == "testing_mode" for item in task.trace))
        self.assertTrue(any("no inference" in line.lower() for line in task.logs))
        self.assertEqual(task.generation_metrics["outputTokens"], 0)
        self.assertIsNone(task.generation_metrics["tokensPerSecond"])
        self.assertEqual(task.generation_metrics["lastOutputTokens"], 0)
        with store._lock, store.connect() as conn:
            messages = conn.execute(
                "SELECT role, content FROM messages WHERE task_id=? ORDER BY created_at ASC",
                (task.id,),
            ).fetchall()
        assistant = [row["content"] for row in messages if row["role"] == "assistant"]
        self.assertEqual(assistant, [task.result])
        self.assertEqual(len(assistant[0]), len(task.result))

    def test_testing_mode_names_each_requested_mode_without_inference_claims(self):
        for mode, expected in (("chat", "Chat"), ("research", "Research")):
            with self.subTest(mode=mode):
                hub = agent.AgentHub()
                task = self._task(hub, mode, f"Run a {mode} smoke check")
                asyncio.run(hub.run_task(task))
                self.assertEqual(task.status, "done")
                self.assertIn(expected, task.result)
                self.assertIn("No model inference", task.result)
                self.assertIsNone(task.generation_metrics["tokensPerSecond"])

    def test_non_testing_chat_still_uses_normal_chat_path(self):
        hub = agent.AgentHub()
        task = agent.AgentTask(
            "Answer normally",
            "healthy-local",
            "general",
            mode="chat",
            workspace_path=str(TEST_ROOT / "workspace"),
        )
        task.owner_id = "testing-owner"
        hub.tasks[task.id] = task
        hub._wire(task)
        hub._persist_task(task)
        hub._add_message(task.session_id, task.id, "user", task.objective)
        with patch.object(hub, "chat_reply", new=AsyncMock(return_value="normal answer")) as chat_reply, \
                patch.object(hub, "ground_chat_response", side_effect=lambda _task, text: text), \
                patch.object(hub, "compact_session", new=AsyncMock()), \
                patch.object(agent.memory, "remember"), \
                patch.object(agent.memory, "suggest_from_task"):
            asyncio.run(hub.run_task(task))
        chat_reply.assert_awaited_once_with(task)
        self.assertEqual(task.result, "normal answer")
        self.assertEqual(task.status, "done")


if __name__ == "__main__":
    unittest.main()
