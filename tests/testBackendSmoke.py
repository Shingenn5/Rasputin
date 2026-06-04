import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main
from backend import approvals
from backend import model_registry
from backend import models
from backend import telegram
from backend.mcp_layer import McpLayer


class BackendSmokeTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[main.current_user] = lambda: {"username": "test", "role": "admin"}
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def assertOk(self, response):
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertIsNone(body["error"])
        return body["data"]

    def testHealthUsesCamelCase(self):
        data = self.assertOk(self.client.get("/api/health"))
        self.assertIn("privacyLock", data["privacy"])
        self.assertIn("remoteModelsBlocked", data["privacy"])

    def testAuthSessionShape(self):
        data = self.assertOk(self.client.get("/api/auth/session"))
        self.assertIn("authenticated", data)

    def testModelRegistryUsesCamelCase(self):
        data = self.assertOk(self.client.get("/api/model-registry"))
        self.assertIn("models", data)
        self.assertIsInstance(data["models"], list)

    def testModelPromptIsTrimmedForSmallContextWindow(self):
        message = {"role": "user", "content": "hello " + ("x" * 10000)}
        fitted = models._fit_messages([message], {"context_window": 1024}, 160)
        self.assertEqual(len(fitted), 1)
        self.assertLessEqual(len(fitted[0]["content"]), (1024 - 160 - 64) * 2)
        self.assertIn("prompt context shortened", fitted[0]["content"])

    def testUiBootstrapShape(self):
        data = self.assertOk(self.client.get("/api/ui/bootstrap"))
        for key in ["models", "tasks", "security", "workspace", "output", "preferences", "warsat"]:
            self.assertIn(key, data)

    def testPreferencesRoundTrip(self):
        saved = self.assertOk(self.client.post("/api/preferences", json={
            "theme": "rasputin-dark",
            "sidebarCollapsed": True,
            "selectedModel": "dry-run",
            "skill": "general",
            "taskMode": "code",
            "subagents": 2,
            "activeView": "settings",
            "activeSettingsSection": "models",
        }))
        self.assertEqual(saved["theme"], "rasputin-dark")
        self.assertTrue(saved["sidebarCollapsed"])
        self.assertEqual(saved["taskMode"], "code")
        loaded = self.assertOk(self.client.get("/api/preferences"))
        self.assertEqual(loaded["activeSettingsSection"], "models")
        self.assertOk(self.client.post("/api/preferences", json={
            "theme": "rasputin-light",
            "sidebarCollapsed": False,
            "selectedModel": "dry-run",
            "skill": "general",
            "taskMode": "chat",
            "subagents": 0,
            "activeView": "home",
            "activeSettingsSection": "general",
        }))

    def testDryRunDiscovery(self):
        with patch("backend.model_registry._store_health", lambda *args, **kwargs: None):
            data = self.assertOk(self.client.post("/api/model-registry/discover", json={"key": "dry-run"}))
        self.assertEqual(data["status"], "reachable")
        self.assertIn("latencyMs", data)
        self.assertIn("currentModel", data)

    def testGgufScanRoute(self):
        with patch("backend.security.require", lambda flag: True):
            data = self.assertOk(self.client.post("/api/model-registry/scan-gguf", json={}))
        self.assertIn("models", data)
        self.assertIn("roots", data)
        self.assertIn("count", data)

    def testManagedModelsDoNotTouchDockerWhenControlDisabled(self):
        fake_registry = {
            "models": [
                {
                    "key": "tiny-helper",
                    "name": "Tiny Helper",
                    "provider": "llamacpp",
                    "role": "helper",
                    "base_url": "http://127.0.0.1:8081/v1",
                    "model": "tiny.gguf",
                    "enabled": True,
                    "managed": True,
                    "runtime": "docker-llamacpp",
                    "container": "tiny-helper",
                }
            ]
        }
        with patch("backend.model_registry._load", return_value=fake_registry), \
             patch("backend.security.load", return_value={"allow_docker_control": False}), \
             patch("backend.model_registry.container_status", side_effect=AssertionError("docker should stay untouched")):
            models = model_registry.all_models()
        self.assertEqual(models[0]["container_status"], "docker control disabled")
        self.assertEqual(models[0]["runtime_status"], "unknown")

    def testTasksRoute(self):
        data = self.assertOk(self.client.get("/api/tasks"))
        self.assertIsInstance(data, list)
        task = self.assertOk(self.client.post("/api/tasks", json={
            "objective": "Inspect task details from the backend smoke test.",
            "model": "dry-run",
            "skill": "general",
            "mode": "chat",
            "workspacePath": ".",
        }))
        detail = self.assertOk(self.client.get(f"/api/tasks/{task['id']}"))
        for key in ["task", "session", "events", "trace", "outputs", "children", "approvals", "toolCalls"]:
            self.assertIn(key, detail)
        self.assertEqual(detail["task"]["id"], task["id"])
        missing = self.client.get("/api/tasks/definitely-missing-task")
        body = missing.json()
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "taskNotFound")

    def testRuntimeSessionsMemorySkillsAndSchedules(self):
        task = self.assertOk(self.client.post("/api/tasks", json={
            "objective": "Remember that I prefer concise local summaries.",
            "model": "dry-run",
            "skill": "general",
            "mode": "chat",
            "workspacePath": ".",
        }))
        self.assertIn("sessionId", task)

        sessions = self.assertOk(self.client.get("/api/sessions"))
        self.assertIn("sessions", sessions)
        self.assertTrue(any(item["id"] == task["sessionId"] for item in sessions["sessions"]))

        found = self.assertOk(self.client.post("/api/memory/search", json={
            "query": "concise",
            "limit": 5,
        }))
        self.assertIn("items", found)

        skills = self.assertOk(self.client.get("/api/skills"))
        self.assertIn("skills", skills)
        self.assertTrue(any(item["name"] == "general" for item in skills["skills"]))

        preview = self.assertOk(self.client.post("/api/skills/create-from-session", json={
            "sessionId": task["sessionId"],
            "save": False,
        }))
        self.assertTrue(preview["preview"])
        self.assertIn("## Workflow", preview["content"])

        schedule = self.assertOk(self.client.post("/api/schedules", json={
            "name": "Smoke Schedule",
            "prompt": "Summarize local status",
            "intervalSeconds": 0,
            "enabled": False,
        }))
        self.assertEqual(schedule["name"], "Smoke Schedule")

    def testWarsatProtocolsAndPlanAreSafeByDefault(self):
        protocols = self.assertOk(self.client.get("/api/warsat/protocols"))
        self.assertGreaterEqual(protocols["count"], 2)
        self.assertFalse(protocols["executionEnabled"])
        self.assertTrue(any(item["id"] == "vllmCudaOpenai" for item in protocols["protocols"]))

        plan = self.assertOk(self.client.post("/api/warsat/plan", json={
            "protocolId": "vllmCudaOpenai",
            "modelRef": "Qwen/Qwen2.5-Coder-7B-Instruct",
            "hostPort": 8020,
            "role": "coder",
        }))
        self.assertEqual(plan["protocolId"], "vllmCudaOpenai")
        self.assertFalse(plan["executionEnabled"])
        self.assertTrue(plan["requiresApproval"])
        self.assertTrue(plan["securityChecks"]["localhostOnly"])
        self.assertIn("127.0.0.1:8020:8000", " ".join(plan["commandPreview"]["run"]))
        self.assertEqual(plan["expectedModelRegistryEntry"]["role"], "coder")

        missing = self.client.post("/api/warsat/plan", json={"protocolId": "missingProtocol", "modelRef": "x"})
        body = missing.json()
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "warsatProtocolMissing")

    def testWorkspaceRootsBrowseAndMountPlan(self):
        data = self.assertOk(self.client.get("/api/workspace/roots"))
        self.assertIn("roots", data)
        self.assertGreaterEqual(len(data["roots"]), 1)
        root = next((item for item in data["roots"] if item["id"] == "workspace-folder"), data["roots"][0])
        root_id = root["id"]
        browsed = self.assertOk(self.client.post("/api/workspace/browse", json={"rootId": root_id}))
        self.assertIn("entries", browsed)
        self.assertIn("displayName", browsed)
        approved = self.assertOk(self.client.post("/api/workspace/approve", json={
            "path": browsed["path"],
            "name": "Smoke Workspace",
            "readOnly": True,
        }))
        self.assertIn("readOnly", approved)
        plan = self.assertOk(self.client.post("/api/workspace/mount-plan", json={
            "hostPath": "C:/Users/example/Documents",
            "name": "Documents",
            "readOnly": True,
        }))
        self.assertTrue(plan["requiresRestart"])
        self.assertTrue(plan["readOnly"])

    def testWorkspaceMountApplyRequiresDockerControl(self):
        response = self.client.post("/api/workspace/mount-apply", json={
            "hostPath": "C:/Users/example/Documents",
            "name": "Documents",
            "readOnly": True,
        })
        body = response.json()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "permissionDenied")

    def testApprovalQueueAndTelegramRedaction(self):
        preview = asyncio.run(McpLayer().call_tool("fs_write", {
            "path": "approval-smoke.txt",
            "content": "private local content should not be sent",
            "workspace_path": "project-root",
        }))
        self.assertTrue(preview["preview"])
        self.assertIn("approval_id", preview)

        queue = self.assertOk(self.client.get("/api/approvals"))
        approval = next(item for item in queue["approvals"] if item["id"] == preview["approval_id"])
        self.assertEqual(approval["status"], "pending")
        self.assertNotIn("private local content", str(approval["redactedDetail"]))

        approved = self.assertOk(self.client.post(f"/api/approvals/{approval['id']}/approve"))
        self.assertEqual(approved["status"], "approved")

        with patch("backend.telegram._post", return_value={"ok": True}):
            cfg = self.assertOk(self.client.post("/api/integrations/telegram/configure", json={
                "botToken": "123:ABC",
                "allowedChatId": "42",
                "enabled": False,
                "redactionMode": "summary",
            }))
            self.assertTrue(cfg["configured"])
            self.assertNotIn("botToken", cfg)
            reply = telegram.handle_command("/status", "999")
            self.assertIn("not authorized", reply)

    def testSensitiveRoutesRespectDisabledPermissions(self):
        def deny_file_read(flag):
            if flag == "allow_file_read":
                raise PermissionError("file read disabled for test")
            return True

        with patch("backend.security.require", deny_file_read):
            for method, path, payload in [
                ("post", "/api/rag/search", {"query": "secret", "limit": 3}),
                ("post", "/api/graph/search", {"query": "secret", "limit": 3}),
                ("get", "/api/workspace/roots", None),
                ("post", "/api/workspace/list", {"path": "."}),
            ]:
                response = getattr(self.client, method)(path, json=payload) if payload is not None else getattr(self.client, method)(path)
                body = response.json()
                self.assertEqual(response.status_code, 403)
                self.assertFalse(body["ok"])
                self.assertEqual(body["error"]["code"], "permissionDenied")

        def deny_file_write(flag):
            if flag == "allow_file_write":
                raise PermissionError("file write disabled for test")
            return True

        with patch("backend.security.require", deny_file_write):
            response = self.client.post("/api/output", json={"markdownFolder": "workspace/markdown-output"})
            body = response.json()
            self.assertEqual(response.status_code, 403)
            self.assertFalse(body["ok"])
            self.assertEqual(body["error"]["code"], "permissionDenied")

        def deny_docker(flag):
            if flag == "allow_docker_control":
                raise PermissionError("docker control disabled for test")
            return True

        with patch("backend.security.require", deny_docker):
            response = self.client.post("/api/model-registry/logs", json={"key": "dry-run"})
            body = response.json()
            self.assertEqual(response.status_code, 403)
            self.assertFalse(body["ok"])
            self.assertEqual(body["error"]["code"], "permissionDenied")

    def testReadOnlyWorkspaceBlocksMcpWrite(self):
        target = main.ROOT / "workspace" / "readonly-smoke"
        target.mkdir(parents=True, exist_ok=True)
        approved = self.assertOk(self.client.post("/api/workspace/approve", json={
            "path": "workspace/readonly-smoke",
            "name": "Read Only Smoke",
            "readOnly": True,
        }))
        with self.assertRaises(PermissionError):
            asyncio.run(McpLayer().call_tool("fs_write", {
                "path": "note.txt",
                "content": "nope",
                "workspace_path": approved["root"],
                "approved": True,
            }))

    def testGgufImportOutsideVisibleRootsIsStructured(self):
        with tempfile.NamedTemporaryFile(suffix=".gguf") as tmp:
            with patch("backend.security.require", lambda flag: True):
                response = self.client.post("/api/model-registry/import-gguf", json={"path": tmp.name})
        body = response.json()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "modelFileOutsideVisibleRoots")

    def testBadGgufPathIsStructured(self):
        with patch("backend.security.require", lambda flag: True):
            response = self.client.post("/api/model-registry/import-gguf", json={"path": "Z:/definitely/missing/model.gguf"})
        body = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "modelFileMissing")


if __name__ == "__main__":
    unittest.main()
