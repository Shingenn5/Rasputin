"""Admission/receipt integration with isolated real state and Windows execution."""
import concurrent.futures
import asyncio
import contextlib
import io
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import uuid

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-execution-tests-"))

from backend.core import approvals, auth, runtime_store as store, security, workspace
from backend.core import sandbox_execution as execution


@unittest.skipUnless(os.name == "nt" and os.environ.get("RASPUTIN_SANDBOX_PROBE_ROOT"),
                     "Opt-in Windows snapshot execution tests")
class SandboxExecutionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=os.environ["RASPUTIN_SANDBOX_PROBE_ROOT"], prefix="execution-source-")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "test.cjs"
        self.source.write_text("console.log('snapshot test passed');", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            auth.bootstrap()
        self.owner = auth.list_users()[0]["username"]
        self.member = "exec" + uuid.uuid4().hex[:12]
        self.member_password = uuid.uuid4().hex
        auth.create_user(self.member, self.member_password, role="member")
        workspace.add(str(self.root), owner_username=self.owner,
                      permission_profile={"read": True, "write": True, "reorganize": False})
        workspace.set_member(str(self.root), self.member, "contributor")
        security.save({"allow_file_read": True, "allow_shell_execution": True})
        self.node = shutil.which("node")
        self.assertTrue(self.node)
        execution.configure_toolchain(self.node, self.owner)

    def request(self, owner=None, **kwargs):
        return execution.create_request(owner or self.owner, str(self.root), ["test.cjs"],
                                        ["--preserve-symlinks", "--preserve-symlinks-main", "test.cjs"], **kwargs)

    def approve(self, request):
        approvals.approve(request["approval_id"])
        return request["plan"]["request_id"]

    def task(self):
        task_id, session_id = "task_" + uuid.uuid4().hex, "ses_" + uuid.uuid4().hex
        with store.connect() as conn:
            conn.execute("INSERT INTO sessions(id,title,created_at,updated_at,owner_id) VALUES(?,?,?,?,?)",
                         (session_id, "Sandbox fixture", store.now(), store.now(), self.owner))
            conn.execute("INSERT INTO tasks(id,session_id,objective,model,skill,mode,status,workspace,created_at,updated_at,owner_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (task_id, session_id, "Run snapshot test", "dry-run", "general", "code", "running", str(self.root), store.now(), store.now(), self.owner))
            conn.commit()
        return task_id

    def test_agent_tools_bind_workspace_task_and_redact_output_logs(self):
        from backend.mcp.layer import McpLayer
        layer = McpLayer()
        task_id = self.task()

        async def mission():
            preview = await layer.call_tool("sandbox_prepare", {"files": ["test.cjs"],
                "arguments": ["--preserve-symlinks", "--preserve-symlinks-main", "test.cjs"],
                "workspace_path": str(self.root.parent), "_task_id": task_id})
            approvals.approve(preview["approval_id"])
            other_task = self.task()
            with self.assertRaises(PermissionError):
                await layer.call_tool("sandbox_run", {"request_id": preview["request_id"], "_task_id": other_task})
            return await layer.call_tool("sandbox_run", {"request_id": preview["request_id"], "_task_id": task_id})

        receipt = asyncio.run(mission())
        self.assertTrue(receipt["passed"], receipt)
        self.assertEqual(task_id, receipt["task_id"])
        with store.connect() as conn:
            results = conn.execute("SELECT result_redacted FROM tool_calls WHERE task_id=?", (task_id,)).fetchall()
        self.assertNotIn("snapshot test passed", "".join(row["result_redacted"] for row in results))

    def test_cancelled_task_stops_waiting_for_approval_and_never_launches(self):
        from backend.mcp import sandbox_tools
        task_id = self.task()

        async def mission():
            preview = await sandbox_tools.sandbox_prepare(["test.cjs"], ["test.cjs"], _task_id=task_id)
            pending = asyncio.create_task(sandbox_tools.sandbox_run(preview["request_id"], _task_id=task_id))
            await asyncio.sleep(0.05)
            with store.connect() as conn:
                conn.execute("UPDATE tasks SET status='cancelled' WHERE id=?", (task_id,))
                conn.commit()
            with patch.object(execution.windows_sandbox, "probe") as launch:
                with self.assertRaises(PermissionError):
                    await pending
                launch.assert_not_called()
            self.assertFalse(execution.get_request(preview["request_id"], self.owner)["receipt"]["ran"])
        asyncio.run(mission())

    def test_phase_capabilities_and_restart_state_do_not_grant_execution(self):
        from backend.engine.agent import AgentHub
        task = SimpleNamespace(isolate_workspace=True, permission_snapshot=security.load(),
                               execution_workspace="", workspace=str(self.root))
        hub = AgentHub.__new__(AgentHub)
        planning = {item["id"] for item in hub._agent_tools(task, "planning")}
        execution_tools = {item["id"] for item in hub._agent_tools(task, "execution")}
        self.assertNotIn("sandbox_run", planning)
        self.assertIn("sandbox_run", execution_tools)
        request = self.request()
        request_id = self.approve(request)
        execution._consume_approval(request)
        request["state"] = "running"
        store.set_kv(execution._REQUEST_PREFIX + request_id, request)
        execution.recover()
        interrupted = execution.get_request(request_id, self.owner)
        self.assertEqual("interrupted", interrupted["state"])
        self.assertIsNone(interrupted["receipt"]["ran"])
        self.assertFalse(interrupted["receipt"]["passed"])
        with self.assertRaises(PermissionError):
            execution.execute_request(request_id, self.owner)

    def test_approved_snapshot_executes_once_and_has_durable_receipt(self):
        request = self.request()
        request_id = self.approve(request)
        # Approval authorizes the captured bytes, not later source changes.
        self.source.write_text("throw Error('source changed after approval');", encoding="utf-8")
        receipt = execution.execute_request(request_id, self.owner)
        self.assertTrue(receipt["ran"], receipt)
        self.assertTrue(receipt["passed"], receipt)
        self.assertIn("snapshot test passed", receipt["output"])
        self.assertEqual(request["plan"]["snapshot_sha256"], receipt["snapshot_sha256"])
        self.assertEqual(request["plan"]["toolchain"]["sha256"], receipt["toolchain_sha256"])
        self.assertEqual(request["approval_id"], receipt["approval_id"])
        self.assertEqual(receipt, execution.get_request(request_id, self.owner)["receipt"])
        self.assertIn("source changed after approval", self.source.read_text(encoding="utf-8"))
        with self.assertRaises(PermissionError):
            execution.execute_request(request_id, self.owner)
        with self.assertRaises(PermissionError):
            execution.get_request(request_id, self.member)

    def test_pending_denied_expired_and_foreign_approval_never_launch(self):
        for state in ("pending", "denied", "expired", "foreign"):
            with self.subTest(state=state):
                request = self.request()
                request_id = request["plan"]["request_id"]
                if state == "denied":
                    approvals.deny(request["approval_id"])
                elif state == "expired":
                    self.approve(request)
                    with store.connect() as conn:
                        conn.execute("UPDATE approvals SET expires_at=0 WHERE id=?", (request["approval_id"],))
                        conn.commit()
                elif state == "foreign":
                    other = self.request()
                    self.approve(other)
                    request["approval_id"] = other["approval_id"]
                    store.set_kv(execution._REQUEST_PREFIX + request_id, request)
                with patch.object(execution.windows_sandbox, "probe") as launch:
                    with self.assertRaises(PermissionError):
                        execution.execute_request(request_id, self.owner)
                    launch.assert_not_called()
                refusal = execution.get_request(request_id, self.owner)["last_refusal"]
                self.assertFalse(refusal["ran"])
                self.assertFalse(refusal["passed"])

    def test_policy_and_workspace_access_are_rechecked_after_approval(self):
        for revoked in ("global", "workspace"):
            with self.subTest(revoked=revoked):
                request = self.request(self.member)
                request_id = self.approve(request)
                if revoked == "global":
                    security.save({"allow_shell_execution": False})
                else:
                    workspace.set_member(str(self.root), self.member, "viewer")
                with patch.object(execution.windows_sandbox, "probe") as launch:
                    with self.assertRaises(PermissionError):
                        execution.execute_request(request_id, self.member)
                    launch.assert_not_called()
                security.save({"allow_shell_execution": True})
                workspace.set_member(str(self.root), self.member, "contributor")

    def test_snapshot_tampering_and_request_mutation_cannot_use_approval(self):
        request = self.request()
        request_id = self.approve(request)
        snapshot = Path(os.environ["RASPUTIN_DATA_DIR"]) / "execution-requests" / request_id / "test.cjs"
        snapshot.write_text("console.log('tampered');", encoding="utf-8")
        with patch.object(execution.windows_sandbox, "probe") as launch:
            with self.assertRaises(PermissionError):
                execution.execute_request(request_id, self.owner)
            launch.assert_not_called()
        request = self.request()
        request_id = self.approve(request)
        request["plan"]["arguments"] = ["-e", "console.log('different code')"]
        store.set_kv(execution._REQUEST_PREFIX + request_id, request)
        with self.assertRaises(PermissionError):
            execution.execute_request(request_id, self.owner)

    def test_changed_toolchain_bytes_are_refused_before_process_creation(self):
        toolchain = self.root / "pinned-node.exe"
        shutil.copyfile(self.node, toolchain)
        execution.configure_toolchain(str(toolchain), self.owner)
        request = self.request()
        with toolchain.open("ab") as changed:
            changed.write(b"changed-after-approval")
        with patch.object(execution.windows_sandbox, "_execute") as launch:
            receipt = execution.execute_request(self.approve(request), self.owner)
            launch.assert_not_called()
        self.assertFalse(receipt["ran"])
        self.assertFalse(receipt["passed"])
        self.assertEqual("toolchain_identity_changed", receipt["termination_reason"])

    def test_sensitive_files_traversal_and_oversized_snapshots_are_rejected(self):
        for path in ("../test.cjs", ".git/config", ".git. /config", ".env", "credential.key", "nul.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                execution.create_request(self.owner, str(self.root), [path], ["test.cjs"])
        self.source.write_bytes(b"x" * (execution._MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            self.request()

    def test_sandbox_changes_are_reported_without_changing_source(self):
        self.source.write_text("require('node:fs').writeFileSync('result.txt', 'generated');", encoding="utf-8")
        request = self.request()
        receipt = execution.execute_request(self.approve(request), self.owner)
        self.assertTrue(receipt["passed"], receipt)
        self.assertTrue(receipt["evidence_complete"])
        self.assertEqual(["result.txt"], [item["path"] for item in receipt["changes"]])
        self.assertFalse((self.root / "result.txt").exists())

    def test_cancellation_before_and_during_execution_never_passes(self):
        request = self.request()
        request_id = self.approve(request)
        cancelled = execution.cancel_request(request_id, self.owner)
        self.assertFalse(cancelled["receipt"]["ran"])
        with self.assertRaises(PermissionError):
            execution.execute_request(request_id, self.owner)
        self.source.write_text("setInterval(() => {}, 1000);", encoding="utf-8")
        request = self.request(timeout=10)
        request_id = self.approve(request)
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(execution.execute_request, request_id, self.owner)
            deadline = time.monotonic() + 5
            while execution.get_request(request_id, self.owner)["state"] != "running":
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.02)
            execution.cancel_request(request_id, self.owner)
            receipt = future.result(timeout=15)
        self.assertFalse(receipt["passed"])
        self.assertEqual("cancelled", receipt["termination_reason"])

    def test_api_requires_auth_and_restricts_configuration_to_admin(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.api.core import current_user
        client = TestClient(app, base_url="http://127.0.0.1:8899")
        with patch.dict(os.environ, {"RASPUTIN_DESKTOP_ONLY": "0", "RASPUTIN_LOCALHOST_BYPASS": "0", "RASPUTIN_TEST_BYPASS_AUTH": "0"}):
            unauthenticated = client.get("/api/execution")
            self.assertEqual(403, unauthenticated.status_code)
            self.assertIn("login required", unauthenticated.text)
        app.dependency_overrides[current_user] = lambda: {"username": self.member, "role": "member"}
        try:
            self.assertEqual(403, client.post("/api/execution/toolchain", json={"executable": self.node}).status_code)
            response = client.post("/api/execution/requests", json={"workspace": str(self.root), "files": ["test.cjs"],
                                   "arguments": ["--preserve-symlinks", "--preserve-symlinks-main", "test.cjs"]})
            self.assertEqual(200, response.status_code, response.text)
        finally:
            app.dependency_overrides.pop(current_user, None)

    def test_real_authenticated_api_approval_execution_and_receipt_roundtrip(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        administrator_password = uuid.uuid4().hex
        auth.reset_password(self.owner, new_password=administrator_password)
        member = TestClient(app, base_url="http://127.0.0.1:8899")
        administrator = TestClient(app, base_url="http://127.0.0.1:8899")
        self.assertEqual(200, member.post("/api/auth/login", json={"username": self.member, "password": self.member_password}).status_code)
        self.assertEqual(200, administrator.post("/api/auth/login", json={"username": self.owner, "password": administrator_password}).status_code)
        (self.root / "helper_test.json").write_text("{}", encoding="utf-8")
        prepared = member.post("/api/execution/requests", json={"workspace": str(self.root),
                              "files": ["test.cjs", "helper_test.json"],
                              "arguments": ["--preserve-symlinks", "--preserve-symlinks-main", "test.cjs"]})
        self.assertEqual(200, prepared.status_code, prepared.text)
        request = prepared.json()["data"]
        self.assertIn("helper_test.json", [item["path"] for item in request["plan"]["files"]])
        request_id = request["plan"]["requestId"]
        self.assertEqual(403, member.post(f"/api/approvals/{request['approvalId']}/approve").status_code)
        self.assertEqual(200, administrator.post(f"/api/approvals/{request['approvalId']}/approve").status_code)
        executed = member.post(f"/api/execution/requests/{request_id}/execute")
        self.assertEqual(200, executed.status_code, executed.text)
        receipt = executed.json()["data"]
        self.assertTrue(receipt["passed"], receipt)
        saved = member.get(f"/api/execution/requests/{request_id}").json()["data"]["receipt"]
        self.assertEqual(receipt, saved)
        self.assertEqual(403, member.post(f"/api/execution/requests/{request_id}/execute").status_code)


if __name__ == "__main__":
    unittest.main()
