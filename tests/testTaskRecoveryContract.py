import asyncio
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


TEST_ROOT = Path(tempfile.mkdtemp(prefix="rasputin-task-recovery-"))
os.environ["RASPUTIN_DATA_DIR"] = str(TEST_ROOT / "data")

from backend.core import runtime_store  # noqa: E402
from backend.engine import agent  # noqa: E402


class TaskRecoveryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # runtime_store captures its data paths when imported. Discovery may
        # import it before this module, so changing the environment alone is
        # insufficient to isolate this persistence contract.
        cls._previous_data_dir = runtime_store.DATA_DIR
        cls._previous_db_file = runtime_store.DB_FILE
        runtime_store.DATA_DIR = TEST_ROOT / "data"
        runtime_store.DB_FILE = runtime_store.DATA_DIR / "rasputin.db"
        runtime_store.init_db()

    @classmethod
    def tearDownClass(cls):
        runtime_store.DATA_DIR = cls._previous_data_dir
        runtime_store.DB_FILE = cls._previous_db_file
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def _persist(self, hub, status="queued", progress=0, started=False):
        task = agent.AgentTask(
            "contract fixture",
            "dry-run",
            "general",
            workspace_path=str(TEST_ROOT / "fixture-workspace"),
            task_id=f"fixture-{status}-{progress}-{started}",
        )
        task.owner_id = "contract-owner"
        task.status = status
        task.progress = progress
        task.started_at = runtime_store.now() if started else None
        hub._persist_task(task)
        return task

    def test_restart_restores_queued_and_quarantines_interrupted_running(self):
        first_hub = agent.AgentHub()
        queued = self._persist(first_hub, status="queued")
        interrupted = self._persist(first_hub, status="running", progress=42, started=True)

        restarted = agent.AgentHub()
        with patch.object(restarted, "_schedule_queued_task") as schedule:
            recovered = asyncio.run(restarted.recover_pending())

        self.assertEqual(recovered, 1)
        self.assertEqual(restarted.get_task(queued.id, "contract-owner")["status"], "queued")
        schedule.assert_called_once()

        interrupted_snapshot = restarted.get_task(interrupted.id, "contract-owner")
        self.assertEqual(interrupted_snapshot["status"], "paused")
        self.assertTrue(interrupted_snapshot["paused"])
        self.assertEqual(interrupted_snapshot["progress"], 42)

        # The current contract deliberately requires an explicit resume after
        # restart; recovery must not silently rerun interrupted work.
        with patch.object(restarted, "_schedule_queued_task") as resume_schedule:
            resumed = asyncio.run(restarted.resume(interrupted.id))
        self.assertEqual(resumed["status"], "queued")
        resume_schedule.assert_called_once()

    def test_terminal_success_and_failure_are_distinct_and_partial_gap_is_explicit(self):
        async def exercise():
            hub = agent.AgentHub()
            successful = agent.AgentTask(
                "successful fixture", "recovery-fixture", "general",
                workspace_path=str(TEST_ROOT / "success-workspace"),
            )
            failed = agent.AgentTask(
                "failed fixture", "recovery-fixture", "general",
                workspace_path=str(TEST_ROOT / "failure-workspace"),
            )
            successful.owner_id = failed.owner_id = "contract-owner"

            async def fail_after_progress(_task):
                _task.progress = 35
                raise RuntimeError("fixture failure")

            with patch.object(hub, "chat_reply", new=AsyncMock(return_value="fixture success")), \
                    patch.object(hub, "ground_chat_response", side_effect=lambda _task, text: text), \
                    patch.object(hub, "compact_session", new=AsyncMock()), \
                    patch.object(hub, "_add_message"), \
                    patch.object(agent.memory, "remember"), \
                    patch.object(agent.memory, "suggest_from_task"):
                await hub.run_task(successful)
                hub.chat_reply = fail_after_progress
                await hub.run_task(failed)

            return successful, failed

        successful, failed = asyncio.run(exercise())
        self.assertEqual(successful.status, "done")
        self.assertEqual(successful.progress, 100)
        self.assertEqual(successful.result, "fixture success")
        self.assertEqual(failed.status, "error")
        self.assertEqual(failed.progress, 35)
        self.assertIn("fixture failure", failed.result)
        self.assertNotEqual(successful.status, failed.status)

        # Exact remaining gap: progress-bearing failure is still exposed as
        # `error`; no explicit `partial` task status exists without a broader
        # backend/frontend contract change.
        self.assertNotIn("partial", {successful.status, failed.status})


if __name__ == "__main__":
    unittest.main()
