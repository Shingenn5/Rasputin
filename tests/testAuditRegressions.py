"""Cancellation and concurrent persistence regressions from the runtime audit."""

import atexit
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

_DATA = tempfile.TemporaryDirectory(prefix="rasputin-audit-tests-", ignore_cleanup_errors=True)
os.environ.setdefault("RASPUTIN_DATA_DIR", _DATA.name)
atexit.register(_DATA.cleanup)

from backend.engine import agent, context as context_governor
from backend.models.download_manager import DownloadManager, JsonJobRepository, InvalidTransition


class AgentControlRegressionTests(unittest.IsolatedAsyncioTestCase):
    def make_task(self):
        hub = agent.AgentHub()
        task = agent.AgentTask("control regression", "dry-run", "general", mode="code", workspace_path=".")
        task.status = "running"
        hub.tasks[task.id] = task
        hub._persist_session(task)
        hub.emit = AsyncMock()
        hub.mcp.call_tool = AsyncMock(return_value={"output": "simulated edit"})
        return hub, task

    async def execute(self, hub, task):
        sections = [context_governor.section("task", "Task", "probe", required=True, priority=0)]
        with patch("backend.core.workspace.get_workspace_commands", return_value={}):
            return await hub.governed_chat(task, "execution", "coder", sections, tools=[{"id": "fs_patch"}])

    async def test_stop_cancels_pending_inference_without_waiting_for_response(self):
        hub, task = self.make_task()
        entered = asyncio.Event()
        inference_cancelled = asyncio.Event()

        async def slow_chat(*args, **kwargs):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                inference_cancelled.set()

        with patch("backend.engine.agent._chat", slow_chat):
            runner = asyncio.create_task(self.execute(hub, task))
            await asyncio.wait_for(entered.wait(), 2)
            await hub.cancel(task.id)
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(runner, 2)
        self.assertTrue(inference_cancelled.is_set())
        hub.mcp.call_tool.assert_not_awaited()

    async def test_late_model_response_cannot_dispatch_tools_after_stop(self):
        hub, task = self.make_task()

        async def cancelled_response(*args, **kwargs):
            await hub.cancel(task.id)
            return "", [{"id": "late", "name": "fs_patch", "args": {"path": "test.txt"}}]

        with patch("backend.engine.agent._chat", cancelled_response):
            with self.assertRaises(asyncio.CancelledError):
                await self.execute(hub, task)
        hub.mcp.call_tool.assert_not_awaited()

    async def test_stop_between_tool_calls_blocks_remaining_calls(self):
        hub, task = self.make_task()
        calls = [{"id": str(i), "name": "fs_patch", "args": {"path": "test.txt"}} for i in range(2)]

        async def first_tool(*args, **kwargs):
            await hub.cancel(task.id)
            return {"output": "first tool finished"}

        hub.mcp.call_tool.side_effect = first_tool
        with patch("backend.engine.agent._chat", AsyncMock(return_value=("", calls))):
            with self.assertRaises(asyncio.CancelledError):
                await self.execute(hub, task)
        self.assertEqual(hub.mcp.call_tool.await_count, 1)

    async def test_terminal_tasks_ignore_pause_and_resume(self):
        for status in ("done", "error", "cancelled"):
            with self.subTest(status=status):
                hub, task = self.make_task()
                task.status = status
                for action in (hub.cancel, hub.pause, hub.resume):
                    self.assertEqual((await action(task.id))["status"], status)
                hub.emit.assert_not_awaited()
                self.assertFalse(task.paused_requested)

    async def test_cancelled_stream_stops_provider_delta_consumption(self):
        hub, task = self.make_task()
        consume = hub._stream_delta_handler(task)
        await hub.cancel(task.id)
        with self.assertRaises(asyncio.CancelledError):
            consume({"type": "text", "text": "late token"})
        self.assertEqual(task.stream_text, "")


class DownloadControlRegressionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="rasputin-download-control-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.path = self.root / "jobs.json"

    def manager(self, transfer=None):
        return DownloadManager(JsonJobRepository(self.path), transfer=transfer)

    def job(self, manager, identity="model"):
        return manager.create_job({
            "repository": "test/" + identity, "revision": "1",
            "destination": self.root / identity,
            "files": [{"path": "model.gguf", "expected_size": 8}],
        })

    def exercise_open_transfer_control(self, action):
        entered = threading.Event()
        release = threading.Event()

        def transfer(file, part, offset, control, progress):
            with part.open("wb") as handle:
                handle.write(b"GGUFdata")
                handle.flush()
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test transfer was not released")
                # The control request happened after the last checkpoint and
                # before the progress save, while Windows held the file open.
                progress(8)

        worker = self.manager(transfer)
        job = self.job(worker)
        controller = self.manager()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker.run, job.id)
            try:
                self.assertTrue(entered.wait(3))
                result = getattr(controller, action)(job.id)
                self.assertEqual(result.state, "cancelled" if action == "cancel" else "paused")
            finally:
                release.set()
            final = future.result(timeout=5)
        return worker, job, final

    def test_cancel_persists_before_open_file_cleanup(self):
        worker, job, final = self.exercise_open_transfer_control("cancel")
        self.assertEqual(final.state, "cancelled")
        self.assertEqual(worker.get_job(job.id).state, "cancelled")
        self.assertFalse(Path(job.staging_dir).exists())
        self.assertFalse(Path(job.destination).exists())

    def test_pause_survives_progress_save_and_can_resume(self):
        worker, job, final = self.exercise_open_transfer_control("pause")
        self.assertEqual(final.state, "paused")
        self.assertEqual(worker.get_job(job.id).state, "paused")
        self.assertFalse(Path(job.destination).exists())
        resumed = self.manager(lambda file, part, offset, control, progress: b"GGUFdata"[offset:]).resume(job.id)
        self.assertEqual(resumed.state, "completed")

    def test_cancel_after_verification_prevents_atomic_publication(self):
        manager = self.manager(lambda *args: b"GGUFdata")
        job = self.job(manager)
        verify = manager._verify_all

        def cancel_after_verify(current):
            verify(current)
            self.manager().cancel(current.id)

        with patch.object(manager, "_verify_all", cancel_after_verify):
            self.assertEqual(manager.run(job.id).state, "cancelled")
        self.assertFalse(Path(job.destination).exists())

    def test_completed_download_rejects_cancel(self):
        manager = self.manager(lambda *args: b"GGUFdata")
        job = self.job(manager)
        self.assertEqual(manager.run(job.id).state, "completed")
        with self.assertRaises(InvalidTransition):
            self.manager().cancel(job.id)
        self.assertTrue(Path(job.destination).exists())

    def test_repository_instances_serialize_read_modify_write(self):
        factory = DownloadManager()
        jobs = [self.job(factory, str(i)) for i in range(2)]
        first, second = JsonJobRepository(self.path), JsonJobRepository(self.path)
        entered = threading.Event()
        release = threading.Event()
        second_started = threading.Event()
        read = first._read

        def held_read():
            value = read()
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test transaction was not released")
            return value

        def second_save():
            second_started.set()
            second.save(jobs[1])

        with patch.object(first, "_read", held_read), ThreadPoolExecutor(max_workers=2) as pool:
            initial = pool.submit(first.save, jobs[0])
            try:
                self.assertTrue(entered.wait(3))
                overlapping = pool.submit(second_save)
                self.assertTrue(second_started.wait(3))
                self.assertFalse(overlapping.done())
            finally:
                release.set()
            initial.result(timeout=5)
            overlapping.result(timeout=5)
        self.assertEqual({job.id for job in second.list()}, {job.id for job in jobs})


if __name__ == "__main__":
    unittest.main()
