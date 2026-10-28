"""Named-key inference contracts; all state and model responses are isolated."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-inference-api-tests-"))

from fastapi.testclient import TestClient

from backend import main
from backend.api import serving
from backend.api.core import current_user, require_admin, require_member
from backend.core import api_keys, auth
from backend.core import runtime_store as store


LOCAL_MODEL = {
    "key": "local-model", "model": "local-model", "provider": "openai-compatible",
    "base_url": "http://127.0.0.1:9999/v1", "runtime_status": "reachable", "enabled": True,
}


async def fake_chat(model, messages, **kwargs):
    if kwargs.get("on_delta"):
        kwargs["on_delta"]({"type": "text", "text": "hello"})
    return "hello", []


class InferenceApiTests(unittest.TestCase):
    def setUp(self):
        self.user = {"username": "alice", "role": "member"}
        main.app.dependency_overrides[require_member] = lambda: dict(self.user)
        main.app.dependency_overrides[require_admin] = lambda: dict(self.user)
        self.owners = patch.object(auth, "list_users", return_value=[{
            "id": "owner-alice", "username": "alice", "role": "member", "enabled": True,
        }])
        self.owners.start()
        store.set_kv(api_keys._STORE_KEY, {})
        serving._save_config(serving._defaults())
        self.client = TestClient(main.app, base_url="http://127.0.0.1:8899", raise_server_exceptions=False)

    def tearDown(self):
        self.owners.stop()
        main.app.dependency_overrides.clear()
        store.set_kv(api_keys._STORE_KEY, {})
        serving._save_config(serving._defaults())

    def create(self, name="Editor"):
        response = self.client.post("/api/model-serving/keys", json={"name": name})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def test_named_secret_returned_once_and_only_digest_is_stored(self):
        result = self.create()
        self.assertTrue(result["apiKey"].startswith("ras_sk_"))
        listed = self.client.get("/api/model-serving/keys").json()["data"]["keys"]
        self.assertEqual(listed[0]["scope"], "local-inference")
        self.assertEqual(listed[0]["name"], "Editor")
        self.assertEqual(listed[0]["ownerId"], "alice")
        self.assertNotIn(result["apiKey"], json.dumps(listed))
        saved = store.get_kv(api_keys._STORE_KEY)
        self.assertNotIn(result["apiKey"], json.dumps(saved))
        self.assertEqual(len(saved[result["key"]["id"]]["token_hash"]), 64)
        self.assertTrue(self.client.get("/api/model-serving").json()["data"]["apiKeyConfigured"])
        protocols = self.client.get("/api/model-serving").json()["data"]["protocols"]
        self.assertEqual(next(item for item in protocols if item["id"] == "mcp")["status"], "needs_key")

    @patch.object(serving.model_registry, "all_models", return_value=[LOCAL_MODEL])
    def test_multiple_keys_revocation_and_restart_safe_persistence(self, _models):
        first, second = self.create("Editor"), self.create("Notebook")
        key_id = first["key"]["id"]
        headers = {"Authorization": f"Bearer {first['apiKey']}"}
        self.assertEqual(self.client.get("/v1/models", headers=headers).status_code, 200)
        self.assertIsNotNone(api_keys.list_keys("alice")[0]["last_used_at"])
        self.assertEqual(self.client.delete(f"/api/model-serving/keys/{key_id}").status_code, 200)
        self.assertEqual(self.client.get("/v1/models", headers=headers).status_code, 401)
        self.assertEqual(self.client.get("/v1/models", headers={"Authorization": f"Bearer {second['apiKey']}"}).status_code, 200)
        # Authentication reads the persisted store rather than a session cache.
        self.assertIsNotNone(api_keys.authenticate(second["apiKey"]))

    def test_keys_are_owner_scoped_and_admin_can_revoke(self):
        first = self.create()
        self.user = {"username": "bob", "role": "member"}
        self.assertEqual(self.client.get("/api/model-serving/keys").json()["data"]["keys"], [])
        self.assertEqual(self.client.delete(f"/api/model-serving/keys/{first['key']['id']}").status_code, 404)
        self.user["role"] = "admin"
        self.assertEqual(len(self.client.get("/api/model-serving/keys").json()["data"]["keys"]), 1)
        self.assertEqual(self.client.delete(f"/api/model-serving/keys/{first['key']['id']}").status_code, 200)

    def test_member_cannot_create_keys_or_enable_appliance_serving(self):
        main.app.dependency_overrides.pop(require_admin)
        main.app.dependency_overrides[current_user] = lambda: dict(self.user)
        response = self.client.post("/api/model-serving/keys", json={"name": "Not an admin"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(serving._load_config()["enabled"])
        self.assertEqual(api_keys.list_keys("alice"), [])

    def test_disabling_serving_blocks_valid_named_key(self):
        headers = {"Authorization": f"Bearer {self.create()['apiKey']}"}
        config = serving._load_config()
        config["enabled"] = False
        serving._save_config(config)
        self.assertEqual(self.client.get("/v1/models", headers=headers).status_code, 503)

    @patch.object(serving.model_registry, "all_models", return_value=[LOCAL_MODEL])
    def test_disabled_deleted_or_demoted_owner_invalidates_key(self, _models):
        key = self.create()["apiKey"]
        for owners in ([], [{"id": "owner-alice", "username": "alice", "role": "member", "enabled": False}],
                       [{"id": "owner-alice", "username": "alice", "role": "viewer", "enabled": True}],
                       [{"id": "replacement-alice", "username": "alice", "role": "member", "enabled": True}]):
            with self.subTest(owners=owners), patch.object(auth, "list_users", return_value=owners):
                self.assertEqual(self.client.get("/v1/models", headers={"Authorization": f"Bearer {key}"}).status_code, 401)

    @patch.object(serving.model_registry, "all_models", return_value=[
        LOCAL_MODEL, {**LOCAL_MODEL, "key": "remote", "provider": "openai", "base_url": "https://api.openai.com/v1"},
        {**LOCAL_MODEL, "key": "down", "runtime_status": "stopped"},
    ])
    @patch.object(serving.providers, "chat", side_effect=fake_chat)
    def test_local_models_nonstream_stream_and_unavailable_model(self, chat, _models):
        key = self.create()["apiKey"]
        headers = {"Authorization": f"Bearer {key}"}
        models = self.client.get("/v1/models", headers=headers)
        self.assertEqual([item["id"] for item in models.json()["data"]], ["local-model"])
        request = {"model": "local-model", "messages": [{"role": "user", "content": "hi"}]}
        response = self.client.post("/v1/chat/completions", headers=headers, json=request)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["choices"][0]["message"]["content"], "hello")
        self.assertIsNone(chat.call_args.kwargs["tools"])
        stream = self.client.post("/v1/chat/completions", headers=headers, json={**request, "stream": True})
        self.assertIn('"content": "hello"', stream.text)
        self.assertIn("data: [DONE]", stream.text)
        for model in ("remote", "down", "missing"):
            with self.subTest(model=model):
                self.assertEqual(self.client.post("/v1/chat/completions", headers=headers, json={**request, "model": model}).status_code, 404)

    @patch.object(serving.model_registry, "all_models", return_value=[LOCAL_MODEL])
    @patch.object(serving.providers, "chat", side_effect=RuntimeError("private upstream error"))
    def test_model_failure_is_redacted_for_normal_and_streaming_clients(self, _chat, _models):
        headers = {"Authorization": f"Bearer {self.create()['apiKey']}"}
        request = {"model": "local-model", "messages": [{"role": "user", "content": "hi"}]}
        normal = self.client.post("/v1/chat/completions", headers=headers, json=request)
        self.assertEqual(normal.status_code, 502)
        stream = self.client.post("/v1/chat/completions", headers=headers, json={**request, "stream": True})
        self.assertIn("upstream_error", stream.text)
        self.assertNotIn("private upstream error", normal.text + stream.text)

    def test_key_does_not_grant_mcp_metrics_or_native_protocol(self):
        headers = {"Authorization": f"Bearer {self.create()['apiKey']}"}
        for path in ("/mcp", "/rasputin/v1/metrics"):
            self.assertEqual(self.client.get(path, headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/v1/messages", headers=headers, json={}).status_code, 403)
        self.assertEqual(self.client.post("/rasputin/v1/responses", headers=headers, json={}).status_code, 403)
        self.assertEqual(self.client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "tools/call", "id": 1}).status_code, 403)

    def test_bearer_key_does_not_become_a_ui_session_or_bypass_host_checks(self):
        headers = {"Authorization": f"Bearer {self.create()['apiKey']}"}
        main.app.dependency_overrides.clear()
        with patch.object(auth, "public_session", return_value={"authenticated": False}):
            self.assertEqual(self.client.get("/api/model-serving/keys", headers=headers).status_code, 403)
        self.assertEqual(self.client.get("/v1/models", headers={**headers, "Host": "attacker.example"}).status_code, 403)
        self.assertEqual(self.client.post("/v1/chat/completions", headers={**headers, "Origin": "https://attacker.example"}, json={}).status_code, 403)

    def test_key_name_is_validated_and_missing_wrong_keys_fail_even_desktop(self):
        for name in (None, "", " " * 2, "x" * 81, 123):
            self.assertEqual(self.client.post("/api/model-serving/keys", json={"name": name}).status_code, 400)
        self.create()
        with patch.dict(os.environ, {"RASPUTIN_DESKTOP_ONLY": "1"}):
            self.assertEqual(self.client.get("/v1/models").status_code, 401)
            self.assertEqual(self.client.get("/v1/models", headers={"Authorization": "Bearer invalid"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
