import asyncio
import json
import os
import sys
import tempfile
import urllib.parse
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main
from backend.api.core import current_user, hub
from backend.core import approvals as approvals
from backend.engine import agent as agent
from backend.engine import context as context_governor
from backend.models import catalog as model_catalog
from backend.models import registry as model_registry
from backend.models import providers as model_providers
from backend.mcp import relay as mcp_relay
from backend.rag import vector as rag
from backend.core import runtime_store as runtime_store
from backend.core import security as security
from backend.core import telegram as telegram
from backend.mcp.layer import McpLayer
from backend.core.response import AppError


def minimal_pdf_bytes(text):
    safe = str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode("utf-8")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_start = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("ascii"))
    return bytes(out)


class BackendSmokeTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[current_user] = lambda: {"username": "test", "role": "admin"}
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def assertOk(self, response):
        if response.status_code != 200:
            print("Response Failed:", response.status_code, response.content)
        self.assertEqual(response.status_code, 200)
        if response.headers.get("content-type") == "application/x-ndjson":
            lines = [line for line in response.text.splitlines() if line.strip()]
            body = json.loads(lines[-1]) if lines else {}
        else:
            body = response.json()
        if "ok" in body:
            self.assertTrue(body["ok"])
        return body.get("data", body)

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

        with patch("backend.models.catalog._fetch_models_dev", return_value={
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

        with patch("backend.core.security.load", return_value={"allow_docker_control": False}):
            plan = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": deployable["recommendedProtocol"],
                "modelRef": deployable["modelId"],
                "strengthProfile": deployable["recommendedProfile"],
                "hostPort": 8044,
            }))
        self.assertEqual(plan["modelRef"], deployable["modelId"])
        self.assertTrue(plan["requiresApproval"])

    def testLocalOpenAiCompatibleModelCanBeRegistered(self):
        with patch("backend.core.security.require", lambda flag: True):
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

        with patch("backend.core.security.require", lambda flag: True), \
             patch("backend.core.security.load", return_value={"privacy_lock": True, "allow_remote_models": False}):
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
        with patch("backend.core.security.require", lambda flag: True), \
             patch("backend.core.security.load", return_value={"privacy_lock": False, "allow_remote_models": True}), \
             patch("backend.models.secrets.set_api_key", side_effect=lambda key, api_key: saved.update({key: api_key}) or True):
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
        with patch("backend.models.secrets.api_key_for", return_value=("secret", "stored")), \
             patch("backend.core.security.require_local_url", lambda url: True), \
             patch("backend.models.providers._request_json", return_value={"content": [{"type": "text", "text": "anthropic ok"}]}):
            text, tool_calls = asyncio.run(model_providers.chat({
                "provider": "anthropic",
                "base_url": "https://api.anthropic.com/v1",
                "model": "claude-3-5-sonnet-20241022",
            }, [{"role": "system", "content": "be terse"}, {"role": "user", "content": "hello"}], 32, 0))
        self.assertEqual(text, "anthropic ok")

        with patch("backend.models.secrets.api_key_for", return_value=("secret", "stored")), \
             patch("backend.core.security.require_local_url", lambda url: True), \
             patch("backend.models.providers._request_json", return_value={"candidates": [{"content": {"parts": [{"text": "gemini ok"}]}}]}):
            text, tool_calls = asyncio.run(model_providers.chat({
                "provider": "gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "model": "gemini-2.5-flash",
            }, [{"role": "user", "content": "hello"}], 32, 0))
        self.assertEqual(text, "gemini ok")

    def testContextGovernorNormalizesUnsafeModelLimits(self):
        limits = context_governor.normalize_limits({"context_window": 512, "max_tokens": 0})
        self.assertEqual(limits["contextWindow"], 1024)
        self.assertGreater(limits["maxTokens"], 0)

    def testContextGovernorTrimsLowPriorityContextForSmallModel(self):
        with patch("backend.engine.context.model_registry.get_model", return_value={"context_window": 1024, "max_tokens": 160}):
            bundle = context_governor.compose_prompt("tiny-local", "chat", [
                context_governor.section("current_user_message", "Current user message", "hello", required=True, priority=0),
                context_governor.section("rules", "Rules", "Answer directly and do not invent tool use.", required=True, priority=0),
                context_governor.section("file_snippets", "File snippets", "important snippet\n" * 260, priority=35, min_chars=220),
                context_governor.section("workspace_tree", "Workspace tree", "some/file.py\n" * 900, priority=70, min_chars=220),
            ])
        trace = bundle["trace"]
        self.assertLessEqual(trace["estimatedInputTokens"], trace["inputBudgetTokens"])
        section_status = {item["key"]: item["status"] for item in trace["sections"]}
        self.assertIn(section_status["current_user_message"], {"included", "trimmed"})
        self.assertIn(section_status["workspace_tree"], {"trimmed", "omitted"})

    def testAgentChatRecordsContextBudgetTrace(self):
        hub = agent.AgentHub()
        task = agent.AgentTask("hello", "dry-run", "general", workspace_path=".")

        async def fake_call(tool_id, payload):
            if tool_id == "graph_search":
                return {"edges": []}
            return {"hits": []}

        async def fake_workspace_context(_task):
            return {
                "tree": {"items": [{"kind": "file", "path": f"file-{index}.md", "bytes": 12, "depth": 0} for index in range(100)]},
                "snippets": [{"path": "file.md", "content": "short local note", "truncated": False}],
            }

        hub.mcp.call_tool = fake_call
        hub.workspace_context = fake_workspace_context
        asyncio.run(hub.chat_reply(task))
        budgets = [item for item in task.trace if item["kind"] == "context_budget"]
        self.assertTrue(budgets)
        detail = budgets[-1]["detail"]
        self.assertEqual(detail["phase"], "chat")
        self.assertGreater(detail["maxTokens"], 0)
        self.assertIn("sections", detail)

    def testUiBootstrapShape(self):
        data = self.assertOk(self.client.get("/api/ui/bootstrap"))
        for key in ["models", "tasks", "security", "workspace", "output", "preferences", "warsat", "tools", "setup"]:
            self.assertIn(key, data)
        self.assertIn("steps", data["setup"])
        self.assertGreaterEqual(data["setup"]["totalSteps"], 5)

    def testSetupStatusDoesNotExposeSecrets(self):
        data = self.assertOk(self.client.get("/api/setup/status"))
        self.assertIn("steps", data)
        self.assertIn("auth", data)
        self.assertIn("model", data)
        blob = json.dumps(data).lower()
        self.assertNotIn("password:", blob)
        self.assertNotIn("password_hash", blob)
        self.assertNotIn("salt", blob)

    def testToolRelayCatalogAndMcpTraces(self):
        catalog = self.assertOk(self.client.get("/api/tools"))
        self.assertIn("groups", catalog)
        self.assertIn("tools", catalog)
        ids = {item["id"] for item in catalog["tools"]}
        for tool_id in ["rag_search", "graph_search", "workspace_browse", "file_preview", "fs_search", "workspace_mutation_preview", "memory_search", "model_health", "fs_write", "web_search"]:
            self.assertIn(tool_id, ids)
        shell = next(item for item in catalog["tools"] if item["id"] == "shell_exec")
        self.assertTrue(shell["implemented"])
        self.assertFalse(shell["available"])
        self.assertIn("allow_shell_execution", shell["disabledReason"])

        task_id = runtime_store.new_id("toolsmoke")
        result = asyncio.run(McpLayer().call_tool("fs_read", {
            "path": "requirements.txt",
            "workspace_path": "project-root",
            "_task_id": task_id,
        }))
        self.assertIn("content", result)
        with runtime_store._lock, runtime_store.connect() as conn:
            row = conn.execute("SELECT * FROM tool_calls WHERE task_id=? AND name='fs_read' ORDER BY created_at DESC LIMIT 1", (task_id,)).fetchone()
        self.assertIsNotNone(row)
        args_redacted = runtime_store._loads(row["args_redacted"], {})
        result_redacted = runtime_store._loads(row["result_redacted"], {})
        self.assertEqual(row["risk"], "safe")
        self.assertEqual(row["status"], "done")
        self.assertEqual(args_redacted["path"], "requirements.txt")
        self.assertTrue(result_redacted["content"]["redacted"])
        self.assertNotIn("fastapi", str(result_redacted).lower())

        blocked_task_id = runtime_store.new_id("toolblocked")
        blocked_cfg = security.defaults()
        blocked_cfg["allow_file_read"] = False
        with patch("backend.core.security.load", return_value=blocked_cfg):
            with self.assertRaises(PermissionError):
                asyncio.run(McpLayer().call_tool("rag_search", {
                    "query": "local docs",
                    "_task_id": blocked_task_id,
                }))
        with runtime_store._lock, runtime_store.connect() as conn:
            blocked = conn.execute("SELECT * FROM tool_calls WHERE task_id=? AND name='rag_search' ORDER BY created_at DESC LIMIT 1", (blocked_task_id,)).fetchone()
        self.assertIsNotNone(blocked)
        self.assertEqual(blocked["status"], "error")

        with self.assertRaises(AppError):
            asyncio.run(McpLayer().call_tool("missing_tool", {}))

    def testWorkspaceSearchToolFindsRequestedFilesSafely(self):
        target_dir = main.ROOT / "workspace" / f"search-smoke-{runtime_store.new_id('search')[-6:]}"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "server.py").write_text("def boot_server():\n    return 'search target'\n", encoding="utf-8")
        (target_dir / "notes.md").write_text("search smoke notes", encoding="utf-8")
        approved = self.assertOk(self.client.post("/api/workspace/approve", json={
            "path": f"workspace/{target_dir.name}",
            "name": "Search Smoke",
            "readOnly": True,
        }))

        searched = self.client.post("/api/workspace/search", json={
            "rootId": approved["id"],
            "query": "server.py",
            "maxResults": 5,
        })
        if searched.status_code != 200:
            print("ERROR BODY:", searched.text)
        searched = self.assertOk(searched)
        self.assertTrue(searched["matches"])
        self.assertEqual(searched["matches"][0]["path"], f"workspace/{target_dir.name}/server.py")

        task_id = runtime_store.new_id("searchtool")
        tool_result = asyncio.run(McpLayer().call_tool("fs_search", {
            "query": "server.py",
            "workspace_path": approved["root"],
            "_task_id": task_id,
        }))
        self.assertEqual(tool_result["matches"][0]["path"], f"workspace/{target_dir.name}/server.py")
        with runtime_store._lock, runtime_store.connect() as conn:
            row = conn.execute("SELECT * FROM tool_calls WHERE task_id=? AND name='fs_search' ORDER BY created_at DESC LIMIT 1", (task_id,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "done")
        result_redacted = runtime_store._loads(row["result_redacted"], {})
        self.assertEqual(result_redacted["match_count"], 1)
        self.assertNotIn("boot_server", str(result_redacted))

        escaped = self.client.post("/api/workspace/search", json={
            "rootId": approved["id"],
            "path": "backend",
            "query": "main.py",
        })
        body = escaped.json()
        self.assertEqual(escaped.status_code, 400)
        self.assertFalse(body["ok"])

        hub = agent.AgentHub()
        task = agent.AgentTask("read server.py", "dry-run", "general", workspace_path=approved["root"])
        context = asyncio.run(hub.workspace_context(task))
        self.assertTrue(context["searches"])
        self.assertEqual(context["searches"][0]["matches"][0]["path"], f"workspace/{target_dir.name}/server.py")
        self.assertTrue(any(item["path"].endswith("server.py") for item in context["snippets"]))

    def testMcpRelayRegistryAndLocalStdioFlow(self):
        servers = self.assertOk(self.client.get("/api/mcp/servers"))
        self.assertTrue(any(item["id"] == "rasputin-tool-relay" for item in servers["servers"]))

        discovered = self.assertOk(self.client.post("/api/mcp/servers/rasputin-tool-relay/discover"))
        self.assertGreaterEqual(len(discovered["tools"]), 1)
        self.assertIn("Internal Tool Relay", discovered["message"])

        script = main.ROOT / "workspace" / "fake_mcp_smoke.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            "\n".join([
                "import json, sys",
                "for line in sys.stdin:",
                "    if not line.strip():",
                "        continue",
                "    msg = json.loads(line)",
                "    mid = msg.get('id')",
                "    method = msg.get('method')",
                "    if method == 'initialize':",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'fake-smoke','version':'1'}}}), flush=True)",
                "    elif method == 'tools/list':",
                "        tool = {'name':'echo','description':'Echo a short message','inputSchema':{'type':'object','properties':{'message':{'type':'string'}},'required':['message']}}",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'tools':[tool]}}), flush=True)",
                "    elif method == 'tools/call':",
                "        args = (msg.get('params') or {}).get('arguments') or {}",
                "        text = args.get('message', '')",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'content':[{'type':'text','text':text}], 'structuredContent': {'echo': text}}}), flush=True)",
                "    elif method in {'resources/list', 'prompts/list'}:",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'error':{'code':-32601,'message':'unsupported'}}), flush=True)",
            ]),
            encoding="utf-8",
        )
        relay_id = f"smoke-relay-{runtime_store.new_id('relay')[-6:]}"
        registered = self.assertOk(self.client.post("/api/mcp/servers", json={
            "id": relay_id,
            "name": "Smoke Relay",
            "transport": "stdio",
            "command": f"{sys.executable.replace(chr(92), '/')} {str(script).replace(chr(92), '/')}",
            "enabled": False,
        }))
        self.assertEqual(registered["id"], relay_id)
        self.assertFalse(registered["enabled"])
        self.assertFalse(registered["commandApproved"])
        self.assertTrue(registered["pendingApprovalId"])
        disabled = self.assertOk(self.client.post(f"/api/mcp/servers/{relay_id}/discover"))
        self.assertEqual(disabled["tools"], [])
        self.assertIn("disabled", disabled["message"].lower())
        blocked_start = self.client.post(f"/api/mcp/servers/{relay_id}/start", json={})
        self.assertEqual(blocked_start.status_code, 403)
        self.assertFalse(blocked_start.json()["ok"])

        approvals.approve(registered["pendingApprovalId"])

        async def flow():
            started = await mcp_relay.start(relay_id, registered["pendingApprovalId"])
            self.assertEqual(started["status"], "running")
            self.assertIn("compatibilityStatus", started)
            tested = self.assertOk(self.client.post(f"/api/mcp/servers/{relay_id}/test"))
            self.assertIn("capabilities", tested)
            stdio = await mcp_relay.discover(relay_id)
            self.assertEqual(len(stdio["tools"]), 1)
            self.assertEqual(stdio["resources"], [])
            self.assertEqual(stdio["prompts"], [])
            self.assertIn("resourcesCount", stdio["server"])
            self.assertIn("promptsCount", stdio["server"])
            self.assertIn("lastDiscoveredAt", stdio["server"])
            tool_id = stdio["tools"][0]["id"]
            self.assertFalse(stdio["tools"][0]["available"])
            server_tools = self.assertOk(self.client.get(f"/api/mcp/servers/{relay_id}/tools"))
            self.assertEqual(server_tools["tools"][0]["id"], tool_id)
            self.assertEqual(server_tools["resources"], [])
            self.assertEqual(server_tools["prompts"], [])
            encoded_tool_id = urllib.parse.quote(tool_id, safe="")
            classified = self.assertOk(self.client.post(f"/api/mcp/tools/{encoded_tool_id}/classify", json={
                "risk": "guarded",
                "permissionFlag": "allow_file_read",
                "enabled": True,
            }))
            self.assertTrue(classified["available"])
            result = await McpLayer().call_tool(tool_id, {"message": "mcp ok"})
            self.assertEqual(result["structuredContent"]["echo"], "mcp ok")
            stopped = await mcp_relay.stop(relay_id)
            self.assertEqual(stopped["status"], "stopped")

        asyncio.run(flow())

    def testMcpRelayDiscoversReadOnlyResourcesPromptsAndNoisyStdout(self):
        script = main.ROOT / "workspace" / "fake_mcp_caps.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            "\n".join([
                "import json, sys",
                "print('boot noise from fixture', flush=True)",
                "for line in sys.stdin:",
                "    if not line.strip():",
                "        continue",
                "    msg = json.loads(line)",
                "    mid = msg.get('id')",
                "    method = msg.get('method')",
                "    if method == 'initialize':",
                "        result = {'protocolVersion':'2025-06-18','capabilities':{'tools':{},'resources':{},'prompts':{}},'serverInfo':{'name':'fake-caps','version':'1'}}",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':result}), flush=True)",
                "    elif method == 'tools/list':",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'tools':[]}}), flush=True)",
                "    elif method == 'resources/list':",
                "        resource = {'uri':'file://local/readme.md','name':'Local Readme','description':'Read-only fixture resource','mimeType':'text/markdown'}",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'resources':[resource]}}), flush=True)",
                "    elif method == 'prompts/list':",
                "        prompt = {'name':'summarize-local','description':'Fixture prompt','arguments':[{'name':'topic','description':'Topic','required':True}]}",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'prompts':[prompt]}}), flush=True)",
            ]),
            encoding="utf-8",
        )
        relay_id = f"caps-relay-{runtime_store.new_id('relay')[-6:]}"
        registered = self.assertOk(self.client.post("/api/mcp/servers", json={
            "id": relay_id,
            "name": "Caps Relay",
            "transport": "stdio",
            "command": f"{sys.executable.replace(chr(92), '/')} {str(script).replace(chr(92), '/')}",
            "enabled": False,
        }))
        approvals.approve(registered["pendingApprovalId"])

        async def flow():
            await mcp_relay.start(relay_id, registered["pendingApprovalId"])
            discovered = await mcp_relay.discover(relay_id)
            self.assertEqual(discovered["tools"], [])
            self.assertEqual(len(discovered["resources"]), 1)
            self.assertEqual(len(discovered["prompts"]), 1)
            self.assertEqual(discovered["server"]["resourcesCount"], 1)
            self.assertEqual(discovered["server"]["promptsCount"], 1)
            self.assertEqual(discovered["server"]["compatibilityStatus"], "read_only_capabilities")
            self.assertTrue(any("boot noise" in item for item in discovered["server"]["recentLogs"]))
            listed = self.assertOk(self.client.get(f"/api/mcp/servers/{relay_id}/tools"))
            self.assertEqual(listed["resources"][0]["name"], "Local Readme")
            self.assertEqual(listed["prompts"][0]["name"], "summarize-local")
            await mcp_relay.stop(relay_id)

        asyncio.run(flow())

    def testOperatorMcpFixtureFlowCreatesTaskTrace(self):
        registered = self.assertOk(self.client.post("/api/mcp/fixtures/operator/register"))
        self.assertEqual(registered["id"], "operator-mcp-fixture")
        self.assertTrue(registered["pendingApprovalId"])
        approvals.approve(registered["pendingApprovalId"])

        async def flow():
            try:
                started = await mcp_relay.start("operator-mcp-fixture", registered["pendingApprovalId"])
            except Exception as e:
                import json
                print("SERVER LOGS:", json.dumps(mcp_relay._load(), indent=2))
                raise
            self.assertEqual(started["status"], "running")
            discovered = await mcp_relay.discover("operator-mcp-fixture")
            self.assertEqual(len(discovered["tools"]), 1)
            self.assertEqual(len(discovered["resources"]), 1)
            self.assertEqual(len(discovered["prompts"]), 1)
            tool_id = discovered["tools"][0]["id"]
            with patch("backend.core.security.load", return_value={"allow_file_read": True}):
                classified = mcp_relay.classify_tool(tool_id, {
                    "risk": "guarded",
                    "permission_flag": "allow_file_read",
                    "enabled": True,
                })
                self.assertTrue(classified["available"])
                called = await hub.run_tool_test(tool_id, {
                    "message": "fixture e2e",
                })
            self.assertEqual(called["task"]["status"], "done")
            self.assertEqual(called["task"]["skill"], "tool-relay-test")
            self.assertTrue(any(item["kind"] == "tool_relay_test" for item in called["trace"]))
            self.assertTrue(any(item["name"] == tool_id and item["status"] == "done" for item in called["toolCalls"]))
            detail = self.assertOk(self.client.get(f"/api/tasks/{called['task']['id']}"))
            self.assertTrue(any(item["name"] == tool_id for item in detail["toolCalls"]))
            await mcp_relay.stop("operator-mcp-fixture")

        asyncio.run(flow())

    def testMcpRelayCompatibilityFailuresAreStructured(self):
        crash_script = main.ROOT / "workspace" / "fake_mcp_crash.py"
        bad_schema_script = main.ROOT / "workspace" / "fake_mcp_bad_schema.py"
        hang_script = main.ROOT / "workspace" / "fake_mcp_hang.py"
        crash_script.parent.mkdir(parents=True, exist_ok=True)
        crash_script.write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
        bad_schema_script.write_text(
            "\n".join([
                "import json, sys",
                "for line in sys.stdin:",
                "    msg = json.loads(line)",
                "    mid = msg.get('id')",
                "    method = msg.get('method')",
                "    if method == 'initialize':",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'bad-schema','version':'1'}}}), flush=True)",
                "    elif method == 'tools/list':",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'tools':[{'name':'bad','inputSchema':'not-an-object'}]}}), flush=True)",
            ]),
            encoding="utf-8",
        )
        hang_script.write_text(
            "\n".join([
                "import json, sys, time",
                "for line in sys.stdin:",
                "    msg = json.loads(line)",
                "    mid = msg.get('id')",
                "    method = msg.get('method')",
                "    if method == 'initialize':",
                "        print(json.dumps({'jsonrpc':'2.0','id':mid,'result':{'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'hang','version':'1'}}}), flush=True)",
                "    elif method == 'tools/list':",
                "        time.sleep(5)",
            ]),
            encoding="utf-8",
        )

        crash_id = f"crash-relay-{runtime_store.new_id('relay')[-6:]}"
        crash_registered = self.assertOk(self.client.post("/api/mcp/servers", json={
            "id": crash_id,
            "transport": "stdio",
            "command": f"{sys.executable.replace(chr(92), '/')} {str(crash_script).replace(chr(92), '/')}",
        }))
        approvals.approve(crash_registered["pendingApprovalId"])
        crash_start = self.client.post(f"/api/mcp/servers/{crash_id}/start", json={"approvalId": crash_registered["pendingApprovalId"]})
        self.assertEqual(crash_start.status_code, 502)
        self.assertFalse(crash_start.json()["ok"])
        self.assertIn(crash_start.json()["error"]["code"], {"mcpServerExited", "mcpRequestTimeout"})

        bad_id = f"bad-schema-relay-{runtime_store.new_id('relay')[-6:]}"
        bad_registered = self.assertOk(self.client.post("/api/mcp/servers", json={
            "id": bad_id,
            "transport": "stdio",
            "command": f"{sys.executable.replace(chr(92), '/')} {str(bad_schema_script).replace(chr(92), '/')}",
        }))
        approvals.approve(bad_registered["pendingApprovalId"])

        hang_id = f"hang-relay-{runtime_store.new_id('relay')[-6:]}"
        hang_registered = self.assertOk(self.client.post("/api/mcp/servers", json={
            "id": hang_id,
            "transport": "stdio",
            "command": f"{sys.executable.replace(chr(92), '/')} {str(hang_script).replace(chr(92), '/')}",
        }))
        approvals.approve(hang_registered["pendingApprovalId"])

        async def flow():
            await mcp_relay.start(bad_id, bad_registered["pendingApprovalId"])
            with self.assertRaises(AppError) as bad_error:
                await mcp_relay.discover(bad_id)
            self.assertEqual(bad_error.exception.code, "mcp_bad_schema")
            await mcp_relay.stop(bad_id)

            await mcp_relay.start(hang_id, hang_registered["pendingApprovalId"])
            with self.assertRaises(AppError) as timeout_error:
                await mcp_relay._request(hang_id, "tools/list", {}, timeout=0.1)
            self.assertEqual(timeout_error.exception.code, "mcp_request_timeout")
            await mcp_relay.stop(hang_id)

        asyncio.run(flow())

    def testModelCatalogFitScoringAndHardwareHints(self):
        hardware = {"detectedHardware": {"gpus": [{"memoryTotalMb": 24576}]}}
        payload = model_catalog._catalog_payload(model_catalog._curated_items(), hardware=hardware)
        self.assertTrue(payload["items"])
        fit_item = next(item for item in payload["items"] if item["modelId"] == "Qwen/Qwen2.5-Coder-7B-Instruct")
        self.assertIn("fitScore", fit_item)
        self.assertIn("fitLabel", fit_item)
        self.assertGreaterEqual(fit_item["fitScore"], 70)
        self.assertTrue(any("VRAM" in reason for reason in fit_item["fitReasons"]))

        with patch("backend.warsat.hardware_probe", return_value=hardware):
            routed = self.assertOk(self.client.get("/api/model-catalog?fit=true"))
        self.assertIn("fitScore", routed["items"][0])

    def testRagIngestAddsIncrementalDocumentIntel(self):
        from docx import Document
        from openpyxl import Workbook

        target_dir = main.ROOT / "workspace" / f"rag-smoke-{runtime_store.new_id('rag')[-6:]}"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "notes.md").write_text("Rasputin archive recall smoke document.\n" * 4, encoding="utf-8")
        (target_dir / "field-report.pdf").write_bytes(minimal_pdf_bytes("Rasputin PDF memory smoke document."))
        docx = Document()
        docx.add_paragraph("Rasputin DOCX archive smoke document.")
        docx.save(str(target_dir / "briefing.docx"))
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Signals"
        sheet.append(["Signal", "Meaning"])
        sheet.append(["warsat", "Rasputin XLSX telemetry smoke document"])
        workbook.save(str(target_dir / "telemetry.xlsx"))
        rel_path = str(target_dir.relative_to(main.ROOT)).replace("\\", "/")

        self.assertOk(self.client.post("/api/workspace/approve", json={
            "path": rel_path,
            "name": "RAG Smoke",
            "readOnly": True,
        }))
        self.assertOk(self.client.post("/api/workspace/select", json={"path": rel_path}))

        first = self.assertOk(self.client.post("/api/rag/ingest", json={"path": rel_path, "label": "Smoke RAG"}))
        self.assertEqual(first["indexBackend"], "local-hash-vector-json")
        self.assertEqual(first["parserStatus"]["pdf"], "enabled")
        self.assertEqual(first["parserStatus"]["docx"], "enabled")
        self.assertEqual(first["parserStatus"]["xlsx"], "enabled")
        self.assertGreaterEqual(first["docsIndexed"], 4)

        second = self.assertOk(self.client.post("/api/rag/ingest", json={"path": rel_path, "label": "Smoke RAG"}))
        self.assertGreaterEqual(second["docsSkippedUnchanged"], 4)

        stats = self.assertOk(self.client.get("/api/rag/stats"))
        self.assertEqual(stats["indexBackend"], "local-hash-vector-json")
        self.assertEqual(stats["parserStatus"]["docx"], "enabled")

        pdf_hits = self.assertOk(self.client.post("/api/rag/search", json={"path": rel_path, "query": "PDF memory smoke", "limit": 3}))
        self.assertTrue(any(hit.get("pageStart") == 1 for hit in pdf_hits["hits"]))
        docx_hits = self.assertOk(self.client.post("/api/rag/search", json={"path": rel_path, "query": "DOCX archive smoke", "limit": 3}))
        self.assertTrue(any(hit.get("parser") == "docx" for hit in docx_hits["hits"]))
        xlsx_hits = self.assertOk(self.client.post("/api/rag/search", json={"path": rel_path, "query": "telemetry smoke", "limit": 3}))
        self.assertTrue(any(hit.get("sheetName") == "Signals" for hit in xlsx_hits["hits"]))

    def testRagSearchBoostsExactFilePathMatches(self):
        target_dir = main.ROOT / "workspace" / f"rag-path-{runtime_store.new_id('ragpath')[-6:]}"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "server.py").write_text(
            "def boot_server():\n    return 'target file'\n",
            encoding="utf-8",
        )
        (target_dir / "tool_relay.py").write_text(
            ("server configuration schema metadata timeout server object path " * 80).strip(),
            encoding="utf-8",
        )
        rel_path = str(target_dir.relative_to(main.ROOT)).replace("\\", "/")

        self.assertOk(self.client.post("/api/workspace/approve", json={
            "path": rel_path,
            "name": "RAG Path",
            "readOnly": True,
        }))
        self.assertOk(self.client.post("/api/workspace/select", json={"path": rel_path}))
        self.assertOk(self.client.post("/api/rag/ingest", json={"path": rel_path, "label": "RAG Path"}))
        found = self.assertOk(self.client.post("/api/rag/search", json={
            "path": rel_path,
            "query": "server.py",
            "limit": 5,
        }))

        self.assertTrue(found["hits"])
        self.assertEqual(found["hits"][0]["path"], "server.py")
        self.assertGreater(found["hits"][0]["pathScore"], 0)

    def testGraphifyBuildsTypedEvidenceRelationships(self):
        target_dir = main.ROOT / "workspace" / f"graph-smoke-{runtime_store.new_id('graph')[-6:]}"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "engine.py").write_text(
            "\n".join([
                "import json",
                "class WarmindNode:",
                "    def transmit_signal(self):",
                "        return parse_signal('warsat')",
                "def parse_signal(value):",
                "    return value",
            ]),
            encoding="utf-8",
        )
        (target_dir / "field-report.pdf").write_bytes(minimal_pdf_bytes(
            "Warsat Protocol references engine.py and WarmindNode evidence."
        ))
        rel_path = str(target_dir.relative_to(main.ROOT)).replace("\\", "/")

        self.assertOk(self.client.post("/api/workspace/approve", json={
            "path": rel_path,
            "name": "Graph Smoke",
            "readOnly": True,
        }))
        self.assertOk(self.client.post("/api/workspace/select", json={"path": rel_path}))
        self.assertOk(self.client.post("/api/rag/ingest", json={"path": rel_path, "label": "Graph Smoke"}))

        built = self.assertOk(self.client.post("/api/graph/build", json={"path": rel_path}))
        self.assertGreaterEqual(built["nodes"], 4)
        self.assertGreaterEqual(built["edges"], 4)
        self.assertGreaterEqual(built["nodeKinds"].get("file", 0), 1)
        self.assertGreaterEqual(built["nodeKinds"].get("document", 0), 1)
        self.assertGreaterEqual(built["edgeTypes"].get("defines", 0), 1)

        found = self.assertOk(self.client.post("/api/graph/search", json={
            "query": "WarmindNode engine.py",
            "limit": 12,
        }))
        self.assertTrue(any(node["kind"] == "class" and node["name"] == "WarmindNode" for node in found["nodes"]))
        self.assertTrue(any(edge["relation"] == "defines" and edge["targetKind"] == "class" for edge in found["edges"]))
        self.assertTrue(any(edge["relation"] == "references" and edge["sourceKind"] == "document" for edge in found["edges"]))
        evidence = found["edges"][0]["evidence"][0]
        self.assertIn("citation", evidence)
        self.assertTrue(evidence["citation"].get("path"))
        self.assertTrue(found["edges"][0].get("why"))
        compact = agent.AgentHub().compact_graph_edges({"edges": found["edges"]})
        self.assertTrue(compact[0]["evidence"])
        self.assertTrue(compact[0]["evidence"][0]["path"])
        self.assertLessEqual(len(compact[0]["evidence"][0].get("snippet", "")), 260)

    def testArchiveSessionsSaveAndExportWithPermission(self):
        title = f"Archive Smoke {runtime_store.new_id('arch')[-6:]}"
        saved = self.assertOk(self.client.post("/api/archive/sessions", json={
            "title": title,
            "content": "# Smoke\n\nArchive editor content.",
        }))
        self.assertEqual(saved["title"], title)
        sessions = self.assertOk(self.client.get("/api/archive/sessions"))
        self.assertTrue(any(item["id"] == saved["id"] for item in sessions["sessions"]))

        def deny_file_write(flag):
            if flag == "allow_file_write":
                raise PermissionError("file write disabled for archive smoke")
            return True

        with patch("backend.core.security.require", deny_file_write):
            denied = self.client.post("/api/archive/export", json={"id": saved["id"], "folder": "workspace/archive-smoke"})
        self.assertEqual(denied.status_code, 403)
        with patch("backend.core.security.require", lambda flag: True):
            exported = self.assertOk(self.client.post("/api/archive/export", json={
                "id": saved["id"],
                "folder": "workspace/archive-smoke",
            }))
        self.assertTrue(exported["path"].endswith(".md"))
        self.assertIn("archive-smoke", exported["path"])

    def testArchiveCitationSearchUsesLocalIndexes(self):
        target_dir = main.ROOT / "workspace" / f"archive-cite-{runtime_store.new_id('archcite')[-6:]}"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "briefing.md").write_text(
            "# Archive Citations\n\nRasputin archive citation smoke source for local document workflows.",
            encoding="utf-8",
        )
        rel_path = str(target_dir.relative_to(main.ROOT)).replace("\\", "/")

        self.assertOk(self.client.post("/api/workspace/approve", json={
            "path": rel_path,
            "name": "Archive Citations",
            "readOnly": True,
        }))
        self.assertOk(self.client.post("/api/workspace/select", json={"path": rel_path}))
        self.assertOk(self.client.post("/api/rag/ingest", json={"path": rel_path, "label": "Archive Citations"}))
        self.assertOk(self.client.post("/api/graph/build", json={"path": rel_path}))

        citations = self.assertOk(self.client.post("/api/archive/citations", json={
            "query": "archive citation smoke",
            "path": rel_path,
            "limit": 4,
        }))
        self.assertGreaterEqual(citations["total"], 1)
        self.assertTrue(citations["ragHits"])
        self.assertEqual(citations["ragHits"][0]["path"], "briefing.md")
        self.assertLessEqual(len(citations["ragHits"][0]["snippet"]), 423)

    def testTrialsCompareIsBlindUntilReveal(self):
        compared = self.assertOk(self.client.post("/api/trials/compare", json={
            "prompt": "Compare this answer style.",
            "modelKeys": ["dry-run"],
        }))
        self.assertFalse(compared["revealed"])
        self.assertEqual(len(compared["outputs"]), 1)
        self.assertNotIn("modelKey", compared["outputs"][0])
        blocked = self.client.post(f"/api/trials/{compared['id']}/routing", json={
            "outputId": compared["outputs"][0]["id"],
            "mode": "code",
        })
        self.assertEqual(blocked.status_code, 400)

        runs = self.assertOk(self.client.get("/api/trials"))
        self.assertTrue(any(item["id"] == compared["id"] for item in runs["runs"]))

        revealed = self.assertOk(self.client.post(f"/api/trials/{compared['id']}/reveal"))
        self.assertTrue(revealed["revealed"])
        self.assertEqual(revealed["outputs"][0]["modelKey"], "dry-run")
        routed = self.assertOk(self.client.post(f"/api/trials/{compared['id']}/routing", json={
            "outputId": revealed["outputs"][0]["id"],
            "mode": "code",
        }))
        self.assertEqual(routed["route"]["mode"], "code")
        self.assertEqual(routed["route"]["modelKey"], "dry-run")
        self.assertEqual(routed["preferences"]["modeModelOverrides"]["code"], "dry-run")

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
        with patch("backend.models.registry._store_health", lambda *args, **kwargs: None):
            data = self.assertOk(self.client.post("/api/model-registry/discover", json={"key": "dry-run"}))
        self.assertEqual(data["status"], "reachable")
        self.assertIn("latencyMs", data)
        self.assertIn("currentModel", data)

    def testGgufScanRoute(self):
        with patch("backend.core.security.require", lambda flag: True):
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
        with patch("backend.models.registry._load", return_value=fake_registry), \
             patch("backend.core.security.load", return_value={"allow_docker_control": False}), \
             patch("backend.warsat.providers.get_provider", side_effect=AssertionError("docker should stay untouched")):
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
        with patch("backend.core.security.load", return_value={"allow_docker_control": False}):
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
        with patch("backend.core.security.load", return_value={"allow_docker_control": False}):
            blocked = self.client.post("/api/warsat/deploy", json={"plan": plan})
        blocked_body = blocked.json()
        self.assertEqual(blocked.status_code, 403)
        self.assertFalse(blocked_body["ok"])
        self.assertEqual(blocked_body["error"]["code"], "permissionDenied")

        with patch("backend.core.security.load", return_value={"allow_docker_control": False}):
            gguf = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": "llamaCppGgufServer",
                "modelPath": "models/tiny-helper.gguf",
                "hostPort": 8091,
                "strengthProfile": "small",
            }))
        self.assertIn("models:/models:ro", " ".join(gguf["commandPreview"]["run"]))
        self.assertIn("/models/tiny-helper.gguf", " ".join(gguf["commandPreview"]["run"]))
        self.assertIn("docker-compose.warsat.llamaCppGgufServer.small.yml", [item["path"] for item in gguf["filesPreview"]])

        with patch("backend.core.security.load", return_value={"allow_docker_control": False}):
            ollama = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": "ollamaOpenaiServer",
                "modelRef": "llama3.2",
                "hostPort": 11435,
                "role": "helper",
                "strengthProfile": "cpu",
            }))
        self.assertEqual(ollama["runtime"], "ollama")
        # The visible host depends on runtime: containers reach the host via
        # host.docker.internal (WRAPPER_RUNTIME=docker), in-process it's the
        # localhost binding. Accept whichever the current environment yields.
        expected_ollama_host = "host.docker.internal" if os.environ.get("WRAPPER_RUNTIME") == "docker" else "127.0.0.1"
        self.assertEqual(
            ollama["expectedModelRegistryEntry"]["baseUrl"],
            f"http://{expected_ollama_host}:11435/v1",
        )
        self.assertIn("ollama/ollama:latest", " ".join(ollama["commandPreview"]["run"]))

        missing = self.client.post("/api/warsat/plan", json={"protocolId": "missingProtocol", "modelRef": "x"})
        body = missing.json()
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "warsatProtocolMissing")

    def testWarsatHardwareProbeReportsReadinessWithoutMutatingDocker(self):
        docker_outputs = {
            ("docker", "version", "--format", "{{json .}}"): {
                "available": True,
                "ok": True,
                "returnCode": 0,
                "stdout": '{"Client":{"Version":"27.0"},"Server":{"Version":"27.0"}}',
                "stderr": "",
                "latencyMs": 2,
            },
            ("docker", "info", "--format", "{{json .}}"): {
                "available": True,
                "ok": True,
                "returnCode": 0,
                "stdout": '{"Runtimes":{"runc":{},"nvidia":{}},"OSType":"linux","Architecture":"x86_64"}',
                "stderr": "",
                "latencyMs": 3,
            },
            ("docker", "ps", "-a", "--filter", "label=rasputin.managed=true", "--format", "{{json .}}"): {
                "available": True,
                "ok": True,
                "returnCode": 0,
                "stdout": '{"Names":"rasputin-model","Image":"test","Status":"Up 1 minute"}',
                "stderr": "",
                "latencyMs": 4,
            },
        }

        def fake_probe(args, timeout=10):
            if args[0] == "nvidia-smi":
                return {
                    "available": True,
                    "ok": True,
                    "returnCode": 0,
                    "stdout": "RTX 4090, 24564",
                    "stderr": "",
                    "latencyMs": 5,
                }
            return docker_outputs[tuple(args)]

        with patch("backend.core.security.load", return_value={"allow_docker_control": True}), \
             patch("backend.warsat._docker_cli_path", return_value="docker"), \
             patch("backend.warsat.shutil.which", side_effect=lambda name: "nvidia-smi" if name == "nvidia-smi" else None), \
             patch("backend.warsat._model_mount_state", return_value={
                 "id": "modelMount",
                 "label": "Model Mount",
                 "status": "warn",
                 "ok": False,
                 "message": "Model folder is mounted but currently empty.",
                 "detail": {"visiblePath": "models", "sample": [], "countShown": 0},
                 "nextStep": "Mount local model files into ./models.",
             }), \
             patch("backend.warsat._probe_command", side_effect=fake_probe):
            hardware = self.assertOk(self.client.get("/api/warsat/hardware"))

        self.assertEqual(hardware["status"], "warning")
        self.assertTrue(any(item["id"] == "dockerDaemon" and item["status"] == "pass" for item in hardware["checks"]))
        self.assertTrue(any(item["id"] == "dockerGpuRuntime" and item["status"] == "pass" for item in hardware["checks"]))
        self.assertEqual(hardware["detectedHardware"]["dockerServerVersion"], "27.0")
        self.assertEqual(hardware["detectedHardware"]["gpus"][0]["memoryTotalMb"], 24564)
        self.assertIn("blockedReasons", hardware)

    def testWarsatHardwareProbeBlocksWhenDockerIsMissingAndControlDisabled(self):
        with patch("backend.core.security.load", return_value={"allow_docker_control": False}), \
             patch("backend.warsat._docker_cli_path", return_value=None), \
             patch("backend.warsat.shutil.which", return_value=None), \
             patch("backend.warsat._model_mount_state", return_value={
                 "id": "modelMount",
                 "label": "Model Mount",
                 "status": "warn",
                 "ok": False,
                 "message": "Model folder is not visible to Rasputin.",
                 "detail": {},
                 "nextStep": "Mount local model files into ./models.",
             }):
            hardware = self.assertOk(self.client.get("/api/warsat/hardware"))

        self.assertEqual(hardware["status"], "blocked")
        self.assertFalse(hardware["ok"])
        self.assertTrue(any(item["id"] == "dockerCli" and item["status"] == "block" for item in hardware["checks"]))
        self.assertTrue(any(item["id"] == "dockerControl" and item["status"] == "block" for item in hardware["checks"]))
        self.assertTrue(hardware["recommendations"])

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

        with patch("backend.core.security.load", return_value=cfg), \
             patch("backend.warsat._docker_cli_path", return_value="docker"), \
             patch("backend.warsat._run_command", side_effect=fake_run), \
             patch("backend.warsat._probe_model_endpoint", return_value={
                 "ok": True,
                 "status": "reachable",
                 "attempts": 1,
                 "latencyMs": 4,
                 "availableModels": ["Qwen/Qwen2.5-0.5B-Instruct"],
                 "message": "model ready",
             }), \
             patch("backend.models.registry.upsert", side_effect=lambda entry: dict(entry)):
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

        self.assertEqual(deployed["status"], "registered")
        self.assertEqual(deployed["phase"], "registered")
        self.assertTrue(deployed["health"]["ok"])
        self.assertTrue(any(item["id"] == "probing" and item["status"] == "done" for item in deployed["lifecycle"]))
        self.assertEqual(deployed["containerId"], "container-123")
        self.assertEqual(deployed["containerName"], plan["containerName"])
        self.assertEqual(deployed["modelKey"], plan["expectedModelRegistryEntry"]["key"])
        self.assertEqual(deployed["registryEntry"].get("baseUrl") or deployed["registryEntry"].get("base_url"), plan["expectedModelRegistryEntry"]["baseUrl"])
        self.assertTrue(any(call[:2] == ["docker", "pull"] for call in docker_calls))
        self.assertTrue(any(call[:3] == ["docker", "run", "-d"] for call in docker_calls))

    def testWarsatDeployDoesNotRegisterWhenHealthProbeFails(self):
        cfg = {
            "allow_docker_control": True,
            "allow_model_registry_edit": True,
            "privacy_lock": True,
            "allow_remote_models": False,
        }

        def fake_run(args, timeout=120, check=True):
            if args[:2] == ["docker", "pull"]:
                return {"returnCode": 0, "stdout": "pulled", "stderr": ""}
            if args[:3] == ["docker", "rm", "-f"]:
                return {"returnCode": 0, "stdout": "", "stderr": ""}
            if args[:3] == ["docker", "run", "-d"]:
                return {"returnCode": 0, "stdout": "container-456", "stderr": ""}
            if args[:2] == ["docker", "ps"]:
                return {"returnCode": 0, "stdout": "Up 2 seconds", "stderr": ""}
            raise AssertionError(f"unexpected docker command: {args}")

        with patch("backend.core.security.load", return_value=cfg), \
             patch("backend.warsat._docker_cli_path", return_value="docker"), \
             patch("backend.warsat._run_command", side_effect=fake_run), \
             patch("backend.warsat._probe_model_endpoint", return_value={
                 "ok": False,
                 "status": "unhealthy",
                 "attempts": 2,
                 "latencyMs": 20,
                 "lastError": "connection refused",
                 "message": "Container started, but the model endpoint did not pass the health probe.",
             }), \
             patch("backend.models.registry.upsert", side_effect=AssertionError("unhealthy model should not register")):
            plan = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": "vllmCudaOpenai",
                "modelRef": "Qwen/Qwen2.5-0.5B-Instruct",
                "hostPort": 8032,
                "role": "helper",
                "strengthProfile": "small",
            }))
            pending = self.assertOk(self.client.post("/api/warsat/deploy", json={"plan": plan}))
            self.assertOk(self.client.post(f"/api/approvals/{pending['approval']['id']}/approve", json={}))
            failed = self.assertOk(self.client.post("/api/warsat/deploy", json={
                "plan": plan,
                "approvalId": pending["approval"]["id"],
            }))

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["failedPhase"], "probing")
        self.assertFalse(failed["health"]["ok"])
        self.assertNotIn("registryEntry", failed)
        self.assertTrue(any(item["id"] == "probing" and item["status"] == "error" for item in failed["lifecycle"]))

    def testWarsatFakeDeployModeExercisesApprovalAndRegistration(self):
        cfg = {
            "allow_docker_control": True,
            "allow_model_registry_edit": True,
            "privacy_lock": True,
            "allow_remote_models": False,
        }
        env = {
            "RASPUTIN_WARSAT_FAKE_DEPLOY": "1",
            "RASPUTIN_ENV": "test",
        }
        with patch.dict(os.environ, env, clear=False), patch("backend.core.security.load", return_value=cfg):
            plan = self.assertOk(self.client.post("/api/warsat/plan", json={
                "protocolId": "vllmCudaOpenai",
                "modelRef": "Qwen/Qwen2.5-0.5B-Instruct",
                "hostPort": 8033,
                "role": "helper",
                "strengthProfile": "small",
            }))
            self.assertTrue(plan["executionEnabled"])
            pending = self.assertOk(self.client.post("/api/warsat/deploy", json={"plan": plan}))
            self.assertTrue(pending["approvalRequired"])
            self.assertEqual(pending["status"], "waitingForApproval")
            self.assertOk(self.client.post(f"/api/approvals/{pending['approval']['id']}/approve", json={}))
            deployed = self.assertOk(self.client.post("/api/warsat/deploy", json={
                "plan": plan,
                "approvalId": pending["approval"]["id"],
            }))

        self.assertEqual(deployed["status"], "registered")
        self.assertEqual(deployed["phase"], "registered")
        self.assertTrue(deployed["health"]["ok"])
        self.assertIn("test mode", deployed["pull"]["stdout"])
        self.assertTrue(deployed["containerId"].startswith("test-"))
        self.assertTrue(any(item["id"] == "registered" and item["status"] == "done" for item in deployed["lifecycle"]))

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

        with patch("backend.core.security.load", return_value={"allow_docker_control": False}):
            disabled = self.assertOk(self.client.get("/api/warsat/runtimes"))
        self.assertEqual(disabled["containers"], [])
        self.assertFalse(disabled["enabled"])

        with patch("backend.core.security.load", return_value=cfg), \
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
        with patch("backend.core.security.load", return_value={"allow_docker_control": False}):
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
        with patch("backend.core.security.load", return_value={"allow_file_write": True, "approval_required_file_write": True}):
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

        with patch("backend.core.telegram._post", return_value={"ok": True}):
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

    def testTrustedWorkspaceBypassesFileWriteApproval(self):
        with tempfile.TemporaryDirectory() as tmp:
            approved = self.assertOk(self.client.post("/api/workspace/approve", json={
                "path": tmp,
                "name": "Trust Smoke Workspace",
                "readOnly": False,
            }))
            workspace_id = approved["id"]
            self.assertFalse(approved["trusted"])
            try:
                with patch("backend.core.security.load", return_value={"allow_file_write": True, "approval_required_file_write": True}):
                    preview = asyncio.run(McpLayer().call_tool("fs_write", {
                        "path": "untrusted.txt",
                        "content": "should require approval",
                        "workspace_path": tmp,
                    }))
                self.assertTrue(preview["preview"])
                self.assertIn("approval_id", preview)
                self.assertFalse((Path(tmp) / "untrusted.txt").exists())

                trusted = self.assertOk(self.client.post("/api/workspace/trust", json={
                    "workspaceId": workspace_id,
                    "trusted": True,
                }))
                self.assertTrue(trusted["trusted"])

                with patch("backend.core.security.load", return_value={"allow_file_write": True, "approval_required_file_write": True}):
                    result = asyncio.run(McpLayer().call_tool("fs_write", {
                        "path": "trusted.txt",
                        "content": "no approval needed",
                        "workspace_path": tmp,
                    }))
                self.assertNotIn("approval_id", result)
                self.assertEqual((Path(tmp) / "trusted.txt").read_text(encoding="utf-8"), "no approval needed")

                revoked = self.assertOk(self.client.post("/api/workspace/trust", json={
                    "workspaceId": workspace_id,
                    "trusted": False,
                }))
                self.assertFalse(revoked["trusted"])

                with patch("backend.core.security.load", return_value={"allow_file_write": True, "approval_required_file_write": True}):
                    preview_again = asyncio.run(McpLayer().call_tool("fs_write", {
                        "path": "post-revoke.txt",
                        "content": "should require approval again",
                        "workspace_path": tmp,
                    }))
                self.assertIn("approval_id", preview_again)
                self.assertFalse((Path(tmp) / "post-revoke.txt").exists())
            finally:
                self.client.post("/api/workspace/remove", json={"workspaceId": workspace_id})

    def testShellExecRequiresPermissionFlagAndTrustedWorkspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            approved = self.assertOk(self.client.post("/api/workspace/approve", json={
                "path": tmp,
                "name": "Shell Smoke Workspace",
                "readOnly": False,
            }))
            workspace_id = approved["id"]
            try:
                # Global permission flag off -> blocked even though nothing else is checked yet.
                with patch("backend.core.security.load", return_value={"allow_shell_execution": False}):
                    with self.assertRaises(PermissionError):
                        asyncio.run(McpLayer().call_tool("shell_exec", {
                            "command": "echo should-not-run",
                            "workspace_path": tmp,
                        }))

                # Flag on but workspace not trusted -> still blocked.
                with patch("backend.core.security.load", return_value={"allow_shell_execution": True}):
                    with self.assertRaises(PermissionError):
                        asyncio.run(McpLayer().call_tool("shell_exec", {
                            "command": "echo should-not-run",
                            "workspace_path": tmp,
                        }))

                self.assertOk(self.client.post("/api/workspace/trust", json={
                    "workspaceId": workspace_id,
                    "trusted": True,
                }))

                marker = "rasputin-shell-smoke-ok"
                with patch("backend.core.security.load", return_value={"allow_shell_execution": True}):
                    result = asyncio.run(McpLayer().call_tool("shell_exec", {
                        "command": f"echo {marker}",
                        "workspace_path": tmp,
                    }))
                self.assertEqual(result["exit_code"], 0)
                self.assertIn(marker, result["output"])
                self.assertFalse(result["timed_out"])

                # A soft-guardrail-blocked command is rejected even when trusted.
                with patch("backend.core.security.load", return_value={"allow_shell_execution": True}):
                    with self.assertRaises(PermissionError):
                        asyncio.run(McpLayer().call_tool("shell_exec", {
                            "command": "rm -rf /",
                            "workspace_path": tmp,
                        }))

                # A command that outlives its timeout is killed and reported, not left hanging.
                with patch("backend.core.security.load", return_value={"allow_shell_execution": True}):
                    timeout_result = asyncio.run(McpLayer().call_tool("shell_exec", {
                        "command": "python -c \"import time; time.sleep(30)\"",
                        "workspace_path": tmp,
                        "timeout_seconds": 5,
                    }))
                self.assertTrue(timeout_result["timed_out"])
                self.assertIsNone(timeout_result["exit_code"])
            finally:
                self.client.post("/api/workspace/remove", json={"workspaceId": workspace_id})

    def testSensitiveRoutesRespectDisabledPermissions(self):
        def deny_file_read(flag):
            if flag == "allow_file_read":
                raise PermissionError("file read disabled for test")
            return True

        with patch("backend.core.security.require", deny_file_read):
            for method, path, payload in [
                ("post", "/api/rag/search", {"query": "secret", "limit": 3}),
                ("post", "/api/graph/search", {"query": "secret", "limit": 3}),
                ("get", "/api/workspace/roots", None),
                ("post", "/api/workspace/list", {"path": "."}),
                ("post", "/api/workspace/preview-file", {"path": "workspace/smoke-preview.txt"}),
                ("post", "/api/workspace/search", {"path": ".", "query": "server.py"}),
                ("post", "/api/workspace/mutation-preview", {"kind": "write", "path": "workspace/smoke.txt"}),
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

        with patch("backend.core.security.require", deny_file_write):
            response = self.client.post("/api/output", json={"markdownFolder": "workspace/markdown-output"})
            body = response.json()
            self.assertEqual(response.status_code, 403)
            self.assertFalse(body["ok"])
            self.assertEqual(body["error"]["code"], "permissionDenied")

        def deny_docker(flag):
            if flag == "allow_docker_control":
                raise PermissionError("docker control disabled for test")
            return True

        with patch("backend.core.security.require", deny_docker):
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

    def testWorkspaceMutationPreviewDoesNotMutateFiles(self):
        target = main.ROOT / "workspace" / f"mutation-preview-{runtime_store.new_id('preview')[-6:]}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "old.txt").write_text("keep me", encoding="utf-8")
        approved = self.assertOk(self.client.post("/api/workspace/approve", json={
            "path": f"workspace/{target.name}",
            "name": "Mutation Preview Smoke",
            "readOnly": True,
        }))

        planned = self.assertOk(self.client.post("/api/workspace/mutation-preview", json={
            "kind": "write",
            "workspacePath": approved["root"],
            "path": "new.txt",
            "content": "private content should not be written",
        }))
        self.assertTrue(planned["dryRun"])
        self.assertFalse(planned["willMutate"])
        self.assertFalse((target / "new.txt").exists())
        self.assertTrue(any("disabled" in warning.lower() for warning in planned["warnings"]))

        tool_task_id = runtime_store.new_id("previewtool")
        tool_plan = asyncio.run(McpLayer().call_tool("workspace_mutation_preview", {
            "kind": "move",
            "workspace_path": approved["root"],
            "source": "old.txt",
            "target": "archive/old.txt",
            "_task_id": tool_task_id,
        }))
        self.assertTrue(tool_plan["dry_run"])
        self.assertTrue((target / "old.txt").exists())
        self.assertFalse((target / "archive" / "old.txt").exists())
        with runtime_store._lock, runtime_store.connect() as conn:
            row = conn.execute("SELECT * FROM tool_calls WHERE task_id=? AND name='workspace_mutation_preview' ORDER BY created_at DESC LIMIT 1", (tool_task_id,)).fetchone()
        self.assertIsNotNone(row)
        result_redacted = runtime_store._loads(row["result_redacted"], {})
        self.assertFalse(result_redacted["will_mutate"])
        self.assertNotIn("private content", str(result_redacted).lower())

        escaped = self.client.post("/api/workspace/mutation-preview", json={
            "kind": "move",
            "workspacePath": approved["root"],
            "source": "old.txt",
            "target": "../outside.txt",
        })
        body = escaped.json()
        self.assertEqual(escaped.status_code, 400)
        self.assertFalse(body["ok"])

    def testGgufImportOutsideVisibleRootsIsStructured(self):
        with tempfile.NamedTemporaryFile(suffix=".gguf") as tmp:
            with patch("backend.core.security.require", lambda flag: True):
                response = self.client.post("/api/model-registry/import-gguf", json={"path": tmp.name})
        body = response.json()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "modelFileOutsideVisibleRoots")

    def testBadGgufPathIsStructured(self):
        with patch("backend.core.security.require", lambda flag: True):
            response = self.client.post("/api/model-registry/import-gguf", json={"path": "Z:/definitely/missing/model.gguf"})
        body = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "modelFileMissing")


if __name__ == "__main__":
    unittest.main()
