from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-model-serving-tests-"))

from fastapi.testclient import TestClient

from backend import main
from backend.api import serving
from backend.api.core import current_user, require_admin
from backend.models import providers as model_providers


FAKE_MODEL = {
    "key": "local-test",
    "model": "local-test",
    "provider": "openai-compatible",
    "runtime": "native-llamacpp",
    "base_url": "http://127.0.0.1:9999/v1",
    "runtime_status": "reachable",
    "enabled": True,
}


async def fake_chat(model, messages, max_tokens=1024, temperature=0.2, tools=None, on_delta=None, reasoning="auto"):
    if on_delta:
        on_delta({"type": "text", "text": "hello"})
        on_delta({
            "type": "metrics",
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            "timing": {"predicted_per_second": 22.5},
        })
    return "hello", [{"id": "call_1", "name": "read_file", "args": {"path": "README.md"}}] if tools else []


class ModelServingTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides[current_user] = lambda: {"username": "admin", "role": "admin"}
        main.app.dependency_overrides[require_admin] = lambda: {"username": "admin", "role": "admin"}
        serving._save_config(serving._defaults())
        with serving._METRICS_LOCK:
            serving._METRICS.clear()
        self.client = TestClient(main.app, base_url="http://127.0.0.1:8899", raise_server_exceptions=False)

    def tearDown(self):
        serving._save_config(serving._defaults())
        with serving._METRICS_LOCK:
            serving._METRICS.clear()
        main.app.dependency_overrides.clear()

    def rotate_key(self):
        response = self.client.post("/api/model-serving/key/rotate")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertTrue(data["apiKey"].startswith("ras_"))
        return data["apiKey"]

    @staticmethod
    def auth_headers(key, **extra):
        return {"Authorization": f"Bearer {key}", **extra}

    def test_admin_status_lists_all_required_protocols_and_never_replays_key(self):
        initial = self.client.get("/api/model-serving")
        self.assertEqual(initial.status_code, 200, initial.text)
        self.assertFalse(initial.json()["data"]["enabled"])
        self.assertEqual(
            {item["id"] for item in initial.json()["data"]["protocols"]},
            {"openai", "anthropic", "rasputin", "mcp"},
        )

        self.rotate_key()
        status = self.client.get("/api/model-serving").json()["data"]
        self.assertTrue(status["enabled"])
        self.assertTrue(status["apiKeyConfigured"])
        self.assertNotIn("apiKey", status)
        self.assertFalse(status["mcpToolExecution"])
        self.assertFalse(status["promptLogging"])

    @patch.object(serving.model_registry, "all_models", return_value=[])
    def test_status_readiness_reflects_disabled_key_and_model_state(self, _models):
        initial = self.client.get("/api/model-serving").json()["data"]
        self.assertEqual(initial["readiness"], "disabled")
        self.assertEqual(initial["servableModelCount"], 0)
        self.assertEqual(initial["configuredModelCount"], 0)
        self.assertFalse(initial["hasServableModel"])
        self.assertTrue(initial["nextActions"])
        self.assertEqual({item["status"] for item in initial["protocols"] if item["id"] != "mcp"}, {"disabled"})
        self.rotate_key()
        ready = self.client.get("/api/model-serving").json()["data"]
        self.assertEqual(ready["readiness"], "no_models")
        self.assertEqual(ready["servableModelCount"], 0)
        self.assertFalse(ready["hasServableModel"])
        self.assertTrue(ready["nextActions"])
        self.assertEqual({item["status"] for item in ready["protocols"] if item["id"] != "mcp"}, {"no_models"})
        self.assertEqual(next(item for item in ready["protocols"] if item["id"] == "mcp")["status"], "ready")

    @patch.object(serving.model_registry, "all_models", return_value=[
        FAKE_MODEL,
        {**FAKE_MODEL, "key": "embeddings", "role": "embeddings"},
        {**FAKE_MODEL, "key": "down", "runtime_status": "unhealthy"},
    ])
    def test_status_reports_ready_and_distinguishes_configured_from_servable(self, _models):
        key = self.rotate_key()
        status = self.client.get("/api/model-serving").json()["data"]
        self.assertEqual(status["readiness"], "ready")
        self.assertEqual(status["servableModelCount"], 1)
        self.assertEqual(status["configuredModelCount"], 2)
        self.assertTrue(status["hasServableModel"])
        self.assertEqual(status["nextActions"], [])

    @patch.object(serving.model_registry, "all_models", return_value=[
        FAKE_MODEL,
        {**FAKE_MODEL, "key": "embeddings", "role": "embeddings"},
        {**FAKE_MODEL, "key": "down", "runtime_status": "unhealthy"},
    ])
    def test_model_discovery_excludes_embeddings_and_unavailable(self, _models):
        key = self.rotate_key()
        response = self.client.get("/v1/models", headers=self.auth_headers(key))
        self.assertEqual([item["id"] for item in response.json()["data"]], ["local-test"])

    @patch.object(serving.model_registry, "all_models", return_value=[FAKE_MODEL])
    @patch.object(serving.providers, "chat", side_effect=fake_chat)
    def test_openai_validation_and_tool_choice_none(self, chat, _models):
        key = self.rotate_key()
        headers = self.auth_headers(key)
        base = {"model": "local-test", "messages": [{"role": "user", "content": "hello"}]}
        bad_number = self.client.post("/v1/chat/completions", headers=headers, json={**base, "temperature": "hot"})
        self.assertEqual(bad_number.status_code, 400)
        unsupported = self.client.post("/v1/chat/completions", headers=headers, json={**base, "tool_choice": "required"})
        self.assertEqual(unsupported.status_code, 400)
        none = self.client.post(
            "/v1/chat/completions", headers=headers,
            json={**base, "tool_choice": "none", "tools": [{"type": "function", "function": {"name": "read_file"}}]},
        )
        self.assertEqual(none.status_code, 200, none.text)
        self.assertNotIn("tool_calls", none.json()["choices"][0]["message"])
        self.assertIsNone(chat.call_args.kwargs["tools"])

    def test_mcp_version_jsonrpc_and_argument_validation(self):
        key = self.rotate_key()
        headers = self.auth_headers(key, **{"MCP-Protocol-Version": "2025-06-18"})
        response = self.client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(response.headers["MCP-Protocol-Version"], "2025-06-18")
        invalid = self.client.post("/mcp", headers=headers, json={"id": 2, "method": "ping"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], -32600)
        config = serving._load_config()
        config["mcp_tool_execution"] = True
        serving._save_config(config)
        bad_args = self.client.post(
            "/mcp", headers=headers,
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_file", "arguments": []}},
        )
        self.assertEqual(bad_args.status_code, 400)
        self.assertEqual(bad_args.json()["error"]["data"]["code"], "invalid_params")

    @patch.object(serving.model_registry, "all_models", return_value=[FAKE_MODEL])
    @patch.object(serving.providers, "chat", side_effect=RuntimeError("secret upstream prompt"))
    def test_upstream_error_is_redacted_from_response_and_metrics(self, _chat, _models):
        key = self.rotate_key()
        headers = self.auth_headers(key)
        response = self.client.post("/rasputin/v1/responses", headers=headers, json={"model": "local-test", "input": "private"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret upstream prompt", response.text)
        metrics = self.client.get("/rasputin/v1/metrics", headers=headers).json()
        self.assertEqual(metrics["requests"][0]["error"], "upstream_error")
        self.assertNotIn("secret upstream prompt", json.dumps(metrics))

    def test_anthropic_tool_result_survives_provider_payload_normalization(self):
        payload = model_providers._anthropic_payload(
            FAKE_MODEL,
            [
                {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "name": "read_file", "args": {"path": "README.md"}}]},
                {"role": "tool", "tool_call_id": "call_1", "content": "file text"},
            ],
            32,
            0.2,
        )
        self.assertEqual(payload["messages"][0]["content"][0]["type"], "tool_use")
        self.assertEqual(payload["messages"][1]["content"][0]["type"], "tool_result")
        self.assertEqual(payload["messages"][1]["content"][0]["tool_use_id"], "call_1")

    @patch.object(serving.model_registry, "all_models", return_value=[FAKE_MODEL])
    @patch.object(serving.providers, "chat", side_effect=fake_chat)
    def test_openai_models_chat_tools_usage_and_streaming(self, _chat, _models):
        key = self.rotate_key()
        unauthorized = self.client.get("/v1/models")
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(unauthorized.json()["error"]["type"], "authentication_error")

        headers = self.auth_headers(key)
        models = self.client.get("/v1/models", headers=headers)
        self.assertEqual(models.status_code, 200, models.text)
        self.assertEqual(models.json()["data"][0]["id"], "local-test")

        request = {
            "model": "local-test",
            "messages": [{"role": "user", "content": "private prompt marker"}],
            "tools": [{"type": "function", "function": {"name": "read_file", "parameters": {"type": "object"}}}],
        }
        response = self.client.post("/v1/chat/completions", headers=headers, json=request)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["object"], "chat.completion")
        self.assertEqual(body["choices"][0]["finish_reason"], "tool_calls")
        self.assertEqual(body["choices"][0]["message"]["tool_calls"][0]["function"]["name"], "read_file")
        self.assertEqual(body["usage"]["total_tokens"], body["usage"]["prompt_tokens"] + body["usage"]["completion_tokens"])
        self.assertTrue(body["rasputin"]["metrics"]["usage_estimated"])
        self.assertIsNone(_chat.call_args_list[0].kwargs["on_delta"])

        streamed = self.client.post(
            "/v1/chat/completions",
            headers=headers,
            json={**request, "stream": True, "stream_options": {"include_usage": True}},
        )
        self.assertEqual(streamed.status_code, 200, streamed.text)
        self.assertIn("chat.completion.chunk", streamed.text)
        self.assertIn("data: [DONE]", streamed.text)
        self.assertLess(streamed.text.index('"content": "hello"'), streamed.text.index("data: [DONE]"))

    @patch.object(serving.model_registry, "all_models", return_value=[FAKE_MODEL])
    @patch.object(serving.providers, "chat", side_effect=fake_chat)
    def test_anthropic_messages_content_blocks_and_streaming(self, _chat, _models):
        key = self.rotate_key()
        headers = self.auth_headers(key)
        missing_version = self.client.post(
            "/v1/messages",
            headers=headers,
            json={"model": "local-test", "max_tokens": 32, "messages": [{"role": "user", "content": "hello"}]},
        )
        self.assertEqual(missing_version.status_code, 400)
        self.assertEqual(missing_version.json()["type"], "error")

        headers["anthropic-version"] = "2023-06-01"
        request = {
            "model": "local-test",
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"name": "read_file", "description": "Read", "input_schema": {"type": "object"}}],
        }
        response = self.client.post("/v1/messages", headers=headers, json=request)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["type"], "message")
        self.assertEqual(body["content"][0], {"type": "text", "text": "hello"})
        self.assertEqual(body["content"][1]["type"], "tool_use")
        self.assertEqual(body["usage"]["output_tokens"], body["rasputin"]["metrics"]["output_tokens"])

        streamed = self.client.post("/v1/messages", headers=headers, json={**request, "stream": True})
        self.assertEqual(streamed.status_code, 200, streamed.text)
        self.assertIn("event: message_start", streamed.text)
        self.assertIn("event: content_block_delta", streamed.text)
        self.assertIn("event: message_stop", streamed.text)

    @patch.object(serving.model_registry, "all_models", return_value=[FAKE_MODEL])
    @patch.object(serving.providers, "chat", side_effect=fake_chat)
    def test_native_response_records_content_free_performance_metrics(self, _chat, _models):
        key = self.rotate_key()
        headers = self.auth_headers(key)
        response = self.client.post(
            "/rasputin/v1/responses",
            headers=headers,
            json={"model": "local-test", "input": "top secret native prompt"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["object"], "rasputin.response")
        self.assertEqual(response.json()["output"][0]["content"], "hello")

        metrics = self.client.get("/rasputin/v1/metrics", headers=headers)
        self.assertEqual(metrics.status_code, 200, metrics.text)
        body = metrics.json()
        self.assertFalse(body["prompt_logging"])
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["requests"][0]["protocol"], "rasputin")
        self.assertIsNone(body["requests"][0]["decode_tokens_per_second"])
        self.assertTrue(body["requests"][0]["usage_estimated"])
        self.assertNotIn("top secret native prompt", json.dumps(body))

    def test_mcp_initialize_and_tools_list_work_while_tool_execution_is_opt_in(self):
        key = self.rotate_key()
        headers = self.auth_headers(key, **{"MCP-Protocol-Version": "2025-11-25"})
        initialized = self.client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        )
        self.assertEqual(initialized.status_code, 200, initialized.text)
        self.assertEqual(initialized.json()["result"]["serverInfo"]["name"], "Rasputin")
        self.assertIn("tools", initialized.json()["result"]["capabilities"])

        with patch.object(serving.tool_relay, "catalog", return_value={
            "callable_tools": [{
                "id": "read_file",
                "display_name": "Read file",
                "description": "Read a workspace file",
                "risk": "safe",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
            }]
        }):
            tools = self.client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(tools.status_code, 200, tools.text)
        self.assertEqual(tools.json()["result"]["tools"][0]["name"], "read_file")

        blocked = self.client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_file", "arguments": {}}},
        )
        self.assertEqual(blocked.status_code, 403, blocked.text)
        self.assertEqual(blocked.json()["error"]["data"]["code"], "mcp_execution_disabled")


if __name__ == "__main__":
    unittest.main()
