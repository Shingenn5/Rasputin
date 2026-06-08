import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main
from backend import approvals
from backend import model_registry
from backend import model_providers
from backend import models
from backend import runtime_store
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

    def testModelCatalogSupportsWarsatPlanning(self):
        catalog = self.assertOk(self.client.get("/api/model-catalog"))
        self.assertIn("items", catalog)
        self.assertGreaterEqual(catalog["deployableCount"], 1)
        deployable = next(item for item in catalog["items"] if item["deployable"])
        self.assertIn("recommendedProtocol", deployable)

        with patch("backend.model_catalog._fetch_models_dev", return_value={
            "test-provider": {
                "name": "Test Provider",
                "models": {
                    "code-7b": {
                        "name": "Code 7B",
                        "description": "coding model",
                        "limit": {"context": 8192},
                        "tool_call": True,
                    }
                },
            }
        }):
            refreshed = self.assertOk(self.client.post("/api/model-catalog/refresh", json={"force": True}))
        self.assertTrue(any(item["modelId"] == "code-7b" for item in refreshed["items"]))
        self.assertIn("models.dev", refreshed["source"]["name"])

        with patch("backend.security.load", return_value={"allow_docker_control": False}):
            plan = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": deployable["recommendedProtocol"],
                "modelRef": deployable["modelId"],
                "strengthProfile": deployable["recommendedProfile"],
                "hostPort": 8044,
            }))
        self.assertEqual(plan["modelRef"], deployable["modelId"])
        self.assertTrue(plan["requiresApproval"])

    def testLocalOpenAiCompatibleModelCanBeRegistered(self):
        with patch("backend.security.require", lambda flag: True):
            registered = self.assertOk(self.client.post("/api/model-registry/upsert", json={
                "name": "Smoke Local Endpoint",
                "provider": "custom-local",
                "role": "coder",
                "baseUrl": "127.0.0.1:1234",
                "model": "smoke-model",
                "contextWindow": 4096,
                "maxTokens": 512,
                "managed": False,
            }))
        self.assertEqual(registered["baseUrl"], "http://127.0.0.1:1234/v1")
        self.assertEqual(registered["runtime"], "external-local")
        self.assertFalse(registered["managed"])

        with patch("backend.security.require", lambda flag: True), \
             patch("backend.security.load", return_value={"privacy_lock": True, "allow_remote_models": False}):
            blocked = self.client.post("/api/model-registry/upsert", json={
                "name": "Remote Endpoint",
                "baseUrl": "https://example.com/v1",
                "model": "remote",
            })
        body = blocked.json()
        self.assertEqual(blocked.status_code, 403)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "permissionDenied")

    def testApiProviderRegistrationKeepsApiKeyOutOfRegistry(self):
        saved = {}
        with patch("backend.security.require", lambda flag: True), \
             patch("backend.security.load", return_value={"privacy_lock": False, "allow_remote_models": True}), \
             patch("backend.model_secrets.set_api_key", side_effect=lambda key, api_key: saved.update({key: api_key}) or True):
            registered = self.assertOk(self.client.post("/api/model-registry/upsert", json={
                "name": "Smoke OpenAI",
                "provider": "openai",
                "role": "helper",
                "model": "gpt-4o-mini",
                "apiKey": "test-api-secret",
                "maxTokens": 128,
                "managed": False,
            }))
        self.assertEqual(registered["provider"], "openai")
        self.assertEqual(registered["runtime"], "remote-api")
        self.assertEqual(registered["baseUrl"], "https://api.openai.com/v1")
        self.assertEqual(registered["secretRef"], f"model:{registered['key']}")
        self.assertNotIn("apiKey", registered)
        self.assertEqual(saved[registered["key"]], "test-api-secret")

    def testApiProviderAdaptersParseText(self):
        with patch("backend.model_secrets.api_key_for", return_value=("secret", "stored")), \
             patch("backend.security.require_local_url", lambda url: True), \
             patch("backend.model_providers._request_json", return_value={"content": [{"type": "text", "text": "anthropic ok"}]}):
            text = asyncio.run(model_providers.chat({
                "provider": "anthropic",
                "base_url": "https://api.anthropic.com/v1",
                "model": "claude-3-5-sonnet-20241022",
            }, [{"role": "system", "content": "be terse"}, {"role": "user", "content": "hello"}], 32, 0))
        self.assertEqual(text, "anthropic ok")

        with patch("backend.model_secrets.api_key_for", return_value=("secret", "stored")), \
             patch("backend.security.require_local_url", lambda url: True), \
             patch("backend.model_providers._request_json", return_value={"candidates": [{"content": {"parts": [{"text": "gemini ok"}]}}]}):
            text = asyncio.run(model_providers.chat({
                "provider": "gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "model": "gemini-2.5-flash",
            }, [{"role": "user", "content": "hello"}], 32, 0))
        self.assertEqual(text, "gemini ok")

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
            "theme": "bootswatch-slate",
            "sidebarCollapsed": True,
            "selectedModel": "dry-run",
            "skill": "general",
            "taskMode": "code",
            "subagents": 2,
            "activeView": "models",
            "activeSettingsSection": "safety",
            "activeChatFolder": "unfiled",
        }))
        self.assertEqual(saved["theme"], "bootswatch-slate")
        self.assertTrue(saved["sidebarCollapsed"])
        self.assertEqual(saved["taskMode"], "code")
        loaded = self.assertOk(self.client.get("/api/preferences"))
        self.assertEqual(loaded["activeView"], "models")
        self.assertEqual(loaded["activeSettingsSection"], "safety")
        self.assertEqual(loaded["activeChatFolder"], "unfiled")
        stored = runtime_store.get_kv("userPreferences")
        self.assertEqual(stored["theme"], "bootswatch-slate")
        self.assertEqual(stored["activeChatFolder"], "unfiled")
        self.assertOk(self.client.post("/api/preferences", json={
            "theme": "rasputin-light",
            "sidebarCollapsed": False,
            "selectedModel": "dry-run",
            "skill": "general",
            "taskMode": "chat",
            "subagents": 0,
            "activeView": "home",
            "activeSettingsSection": "general",
            "activeChatFolder": "all",
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

    def testBlankSessionCanBeCreatedAndRenamedByFirstTask(self):
        created = self.assertOk(self.client.post("/api/sessions", json={
            "title": "New chat",
            "workspace": ".",
            "model": "dry-run",
            "mode": "chat",
            "skill": "general",
        }))
        session_id = created["session"]["id"]
        self.assertEqual(created["session"]["title"], "New chat")
        self.assertEqual(created["messages"], [])

        task = self.assertOk(self.client.post("/api/tasks", json={
            "objective": "Rename this new chat from first message",
            "model": "dry-run",
            "skill": "general",
            "mode": "chat",
            "workspacePath": ".",
            "sessionId": session_id,
        }))
        self.assertEqual(task["sessionId"], session_id)
        detail = self.assertOk(self.client.get(f"/api/sessions/{session_id}"))
        self.assertEqual(detail["session"]["title"], "Rename this new chat from first message")
        self.assertTrue(any(message["role"] == "user" for message in detail["messages"]))

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

        folders = self.assertOk(self.client.get("/api/chat-folders"))
        self.assertIn("folders", folders)
        folder_name = f"Smoke Chats {task['sessionId'][-6:]}"
        created = self.assertOk(self.client.post("/api/chat-folders", json={"name": folder_name}))
        folder = next(item for item in created["folders"] if item["name"] == folder_name)
        moved = self.assertOk(self.client.post(f"/api/sessions/{task['sessionId']}/folder", json={"folder": folder["name"]}))
        self.assertEqual(moved["session"]["folder"], folder["name"])
        updated = self.assertOk(self.client.get("/api/chat-folders"))
        self.assertTrue(any(item["id"] == folder["id"] and item["sessionCount"] >= 1 for item in updated["folders"]))

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
        with patch("backend.security.load", return_value={"allow_docker_control": False}):
            protocols = self.assertOk(self.client.get("/api/warsat/protocols"))
            self.assertGreaterEqual(protocols["count"], 3)
            self.assertFalse(protocols["executionEnabled"])
            self.assertTrue(any(item["id"] == "vllmCudaOpenai" for item in protocols["protocols"]))
            self.assertTrue(any(item["id"] == "ollamaOpenaiServer" for item in protocols["protocols"]))

            plan = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": "vllmCudaOpenai",
                "modelRef": "Qwen/Qwen2.5-Coder-7B-Instruct",
                "hostPort": 8020,
                "role": "coder",
                "strengthProfile": "large",
                "maxModelLen": 12288,
                "gpuMemoryUtilization": 0.84,
                "tensorParallelSize": 2,
                "quantization": "awq",
                "memoryLimitGb": 24,
                "shmSizeGb": 8,
                "gpuDevice": "0",
            }))
        self.assertEqual(plan["protocolId"], "vllmCudaOpenai")
        self.assertEqual(plan["strengthProfile"], "large")
        self.assertFalse(plan["executionEnabled"])
        self.assertTrue(plan["requiresApproval"])
        self.assertTrue(plan["securityChecks"]["localhostOnly"])
        self.assertIn("127.0.0.1:8020:8000", " ".join(plan["commandPreview"]["run"]))
        self.assertEqual(plan["expectedModelRegistryEntry"]["role"], "coder")
        self.assertEqual(plan["tuning"]["maxModelLen"], 12288)
        self.assertEqual(plan["tuning"]["tensorParallelSize"], 2)
        self.assertEqual(plan["containerLimits"]["memoryLimitGb"], 24)
        self.assertIn("composePreview", plan)
        self.assertIn("dockerfilePreview", plan)
        self.assertIn("--max-model-len", plan["composePreview"])
        self.assertIn("--quantization", plan["composePreview"])
        self.assertIn("mem_limit", plan["composePreview"])
        self.assertIn("NVIDIA_VISIBLE_DEVICES", plan["composePreview"])
        self.assertTrue(any(item["kind"] == "compose" for item in plan["filesPreview"]))
        with patch("backend.security.load", return_value={"allow_docker_control": False}):
            blocked = self.client.post("/api/warsat/deploy", json={"plan": plan})
        blocked_body = blocked.json()
        self.assertEqual(blocked.status_code, 403)
        self.assertFalse(blocked_body["ok"])
        self.assertEqual(blocked_body["error"]["code"], "permissionDenied")

        with patch("backend.security.load", return_value={"allow_docker_control": False}):
            gguf = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": "llamaCppGgufServer",
                "modelPath": "models/tiny-helper.gguf",
                "hostPort": 8091,
                "strengthProfile": "small",
            }))
        self.assertIn("models:/models:ro", " ".join(gguf["commandPreview"]["run"]))
        self.assertIn("/models/tiny-helper.gguf", " ".join(gguf["commandPreview"]["run"]))
        self.assertIn("docker-compose.warsat.llamaCppGgufServer.small.yml", [item["path"] for item in gguf["filesPreview"]])

        with patch("backend.security.load", return_value={"allow_docker_control": False}):
            ollama = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": "ollamaOpenaiServer",
                "modelRef": "llama3.2",
                "hostPort": 11435,
                "role": "helper",
                "strengthProfile": "cpu",
            }))
        self.assertEqual(ollama["runtime"], "ollama")
        self.assertEqual(ollama["expectedModelRegistryEntry"]["baseUrl"], "http://host.docker.internal:11435/v1")
        self.assertIn("ollama/ollama:latest", " ".join(ollama["commandPreview"]["run"]))

        missing = self.client.post("/api/warsat/plan", json={"protocolId": "missingProtocol", "modelRef": "x"})
        body = missing.json()
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "warsatProtocolMissing")

    def testWarsatDeployCanRegisterGeneratedContainerWhenDockerControlIsEnabled(self):
        cfg = {
            "allow_docker_control": True,
            "allow_model_registry_edit": True,
            "privacy_lock": True,
            "allow_remote_models": False,
        }

        docker_calls = []

        def fake_run(args, timeout=120, check=True):
            docker_calls.append(args)
            if args[:2] == ["docker", "pull"]:
                return {"returnCode": 0, "stdout": "pulled", "stderr": ""}
            if args[:3] == ["docker", "rm", "-f"]:
                return {"returnCode": 0, "stdout": "", "stderr": ""}
            if args[:3] == ["docker", "run", "-d"]:
                return {"returnCode": 0, "stdout": "container-123", "stderr": ""}
            if args[:2] == ["docker", "ps"]:
                return {"returnCode": 0, "stdout": "Up 2 seconds", "stderr": ""}
            raise AssertionError(f"unexpected docker command: {args}")

        with patch("backend.security.load", return_value=cfg), \
             patch("backend.warsat._docker_cli_path", return_value="docker"), \
             patch("backend.warsat._run_command", side_effect=fake_run), \
             patch("backend.model_registry.upsert", side_effect=lambda entry: dict(entry)):
            plan = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": "vllmCudaOpenai",
                "modelRef": "Qwen/Qwen2.5-0.5B-Instruct",
                "hostPort": 8031,
                "role": "helper",
                "strengthProfile": "small",
                "gpuMemoryUtilization": 0.70,
                "gpuDevice": "0",
            }))
            self.assertTrue(plan["executionEnabled"])
            pending = self.assertOk(self.client.post("/api/warsat/deploy", json={"plan": plan}))
            self.assertTrue(pending["approvalRequired"])
            self.assertEqual(pending["status"], "waitingForApproval")
            self.assertEqual(pending["approval"]["actionType"], "warsat_deploy")
            self.assertEqual(pending["approval"]["workspace"], "Warsat runtime")
            self.assertEqual(pending["approval"]["redactedDetail"]["workspace"], "Warsat runtime")
            self.assertEqual(docker_calls, [])
            self.assertOk(self.client.post(f"/api/approvals/{pending['approval']['id']}/approve", json={}))
            deployed = self.assertOk(self.client.post("/api/warsat/deploy", json={
                "plan": plan,
                "approvalId": pending["approval"]["id"],
            }))

        self.assertEqual(deployed["containerId"], "container-123")
        self.assertEqual(deployed["containerName"], plan["containerName"])
        self.assertEqual(deployed["modelKey"], plan["expectedModelRegistryEntry"]["key"])
        self.assertEqual(deployed["registryEntry"]["baseUrl"], plan["expectedModelRegistryEntry"]["baseUrl"])
        self.assertTrue(any(call[:2] == ["docker", "pull"] for call in docker_calls))
        self.assertTrue(any(call[:3] == ["docker", "run", "-d"] for call in docker_calls))

    def testWarsatRuntimeLifecycleIsApprovalGated(self):
        cfg = {
            "allow_docker_control": True,
            "allow_model_registry_edit": True,
            "privacy_lock": True,
            "allow_remote_models": False,
        }
        docker_calls = []

        def fake_run(args, timeout=120, check=True):
            docker_calls.append(args)
            if args[:2] == ["docker", "ps"]:
                return {
                    "returnCode": 0,
                    "stdout": '{"ID":"abc123","Names":"rasputin-vllm-8031","Image":"vllm/vllm-openai:latest","Status":"Up 10 seconds","Ports":"127.0.0.1:8031->8000/tcp"}',
                    "stderr": "",
                }
            if args[:2] == ["docker", "inspect"]:
                return {
                    "returnCode": 0,
                    "stdout": '{"rasputin.managed":"true","rasputin.protocol":"vllmCudaOpenai","rasputin.runtime":"vllm"}',
                    "stderr": "",
                }
            if args[:2] == ["docker", "logs"]:
                return {"returnCode": 0, "stdout": "server ready", "stderr": ""}
            if args[:2] == ["docker", "stop"]:
                return {"returnCode": 0, "stdout": "rasputin-vllm-8031", "stderr": ""}
            raise AssertionError(f"unexpected docker command: {args}")

        with patch("backend.security.load", return_value={"allow_docker_control": False}):
            disabled = self.assertOk(self.client.get("/api/warsat/runtimes"))
        self.assertEqual(disabled["containers"], [])
        self.assertFalse(disabled["enabled"])

        with patch("backend.security.load", return_value=cfg), \
             patch("backend.warsat._docker_cli_path", return_value="docker"), \
             patch("backend.warsat._run_command", side_effect=fake_run):
            runtimes = self.assertOk(self.client.get("/api/warsat/runtimes"))
            self.assertEqual(runtimes["count"], 1)
            self.assertEqual(runtimes["containers"][0]["protocolId"], "vllmCudaOpenai")
            logs = self.assertOk(self.client.post("/api/warsat/logs", json={
                "containerName": "rasputin-vllm-8031",
            }))
            self.assertIn("server ready", logs["logs"])
            pending = self.assertOk(self.client.post("/api/warsat/stop", json={
                "containerName": "rasputin-vllm-8031",
            }))
            self.assertTrue(pending["approvalRequired"])
            self.assertEqual(pending["approval"]["actionType"], "warsat_stop")
            self.assertOk(self.client.post(f"/api/approvals/{pending['approval']['id']}/approve", json={}))
            stopped = self.assertOk(self.client.post("/api/warsat/stop", json={
                "containerName": "rasputin-vllm-8031",
                "approvalId": pending["approval"]["id"],
            }))
        self.assertEqual(stopped["action"], "stop")
        self.assertTrue(any(call[:2] == ["docker", "stop"] for call in docker_calls))

    def testWorkspaceRootsBrowseAndMountPlan(self):
        preview_file = main.ROOT / "workspace" / "smoke-preview.txt"
        preview_file.parent.mkdir(parents=True, exist_ok=True)
        preview_file.write_text("Rasputin workspace preview smoke.", encoding="utf-8")
        data = self.assertOk(self.client.get("/api/workspace/roots"))
        self.assertIn("roots", data)
        self.assertGreaterEqual(len(data["roots"]), 1)
        root = next(
            (
                item for item in data["roots"]
                if item["id"] == "workspace-folder" or item["path"] == "workspace" or item["absolutePath"].replace("\\", "/").endswith("/workspace")
            ),
            data["roots"][0],
        )
        root_id = root["id"]
        browse_payload = {"rootId": root_id}
        if root["path"] == ".":
            browse_payload["path"] = "workspace"
        browsed = self.assertOk(self.client.post("/api/workspace/browse", json=browse_payload))
        self.assertIn("entries", browsed)
        self.assertIn("displayName", browsed)
        self.assertTrue(any(item["kind"] == "file" for item in browsed["entries"]))
        found_preview = next(item for item in browsed["entries"] if item["path"].endswith("smoke-preview.txt"))
        self.assertTrue(found_preview["previewable"])
        preview = self.assertOk(self.client.post("/api/workspace/preview-file", json={
            "rootId": root_id,
            "path": found_preview["path"],
        }))
        self.assertIn("Rasputin workspace preview smoke.", preview["content"])
        escaped = self.client.post("/api/workspace/preview-file", json={
            "rootId": root_id,
            "path": "backend/main.py",
        })
        if root["path"] != ".":
            body = escaped.json()
            self.assertEqual(escaped.status_code, 400)
            self.assertFalse(body["ok"])
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
                ("post", "/api/workspace/preview-file", {"path": "workspace/smoke-preview.txt"}),
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
