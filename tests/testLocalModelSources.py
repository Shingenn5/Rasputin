import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from backend.core.response import AppError
from backend.models import registry


class LocalModelSourcesTests(TestCase):
    def test_source_scan_registers_gguf_in_place_and_is_idempotent(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "export.gguf").write_bytes(b"GGUFfixture")
            (root / "broken.gguf").write_bytes(b"NOPE")
            (root / "weights.safetensors").write_bytes(b"fixture")
            records = {"models": []}
            saved = {}
            with patch.object(registry.workspace, "is_native", return_value=True), patch.object(registry.security, "require"), patch.object(registry.runtime_store, "get_kv", side_effect=lambda key, default=None: saved.get(key, default)), patch.object(registry.runtime_store, "set_kv", side_effect=lambda key, value: saved.update({key: value})), patch.object(registry, "_load", return_value=records), patch.object(registry, "_save", side_effect=lambda value: records.update(value)), patch.object(registry.audit, "log"):
                first = registry.scan_local_model_sources(str(root))
                second = registry.scan_local_model_sources(str(root))
            self.assertEqual(len(first["registered"]), 1)
            self.assertEqual(len(second["existing"]), 1)
            self.assertEqual(second["registered"], [])
            self.assertEqual(Path(records["models"][0]["host_model_path"]), root / "export.gguf")
            self.assertEqual(len(saved["external_model_folders"]), 1)

    def test_permission_denied_before_folder_is_persisted(self):
        with patch.object(registry.security, "require", side_effect=PermissionError), patch.object(registry.runtime_store, "set_kv") as save:
            with self.assertRaises(PermissionError):
                registry.scan_local_model_sources("anything")
            save.assert_not_called()

    def test_scan_rejects_root_home_and_missing_folders(self):
        with patch.object(registry.security, "require"), patch.object(registry.workspace, "is_native", return_value=True):
            for root in [Path.home(), Path(Path.home().anchor), Path.home() / "missing-model-fixture-99999"]:
                with self.subTest(root=str(root)), self.assertRaises(AppError):
                    registry.scan_local_model_sources(str(root))

    def test_probe_rejects_non_loopback_and_embedded_credentials(self):
        with patch.object(registry.security, "require"), patch.object(registry.urllib.request, "build_opener") as opener:
            for url in ["https://example.com/v1", "http://192.168.1.2:8888/v1", "http://secret@localhost/v1", "file:///tmp", "http://localhost/v1?key=secret"]:
                with self.subTest(url=url), self.assertRaises(AppError):
                    registry.probe_local_endpoint(url)
            opener.assert_not_called()

    def test_probe_sends_key_without_persisting_it(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"data": [{"id": "local-model"}]}).encode()
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(registry.security, "require"), patch.object(registry.urllib.request, "build_opener", return_value=opener) as build, patch.object(registry.runtime_store, "set_kv") as save:
            result = registry.probe_local_endpoint("http://127.0.0.1:8888", "fixture-secret")
        self.assertEqual(result["models"], ["local-model"])
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8888/v1/models")
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-secret")
        redirect = build.call_args.args[1]
        self.assertIsNone(redirect.redirect_request(None, None, 302, "", {}, "https://example.com"))
        save.assert_not_called()


class ModelInferenceProfileTests(IsolatedAsyncioTestCase):
    async def test_chat_uses_saved_temperature_and_bounded_output(self):
        from backend.engine import agent
        model = {"provider": "llamacpp", "model": "fixture", "inference_profile": {"temperature": 0.7, "max_tokens": 512}}
        with patch.object(agent.model_registry, "get_model", return_value=model), patch.object(agent.context_governor, "output_budget", return_value=256), patch.object(agent.model_providers, "chat", new=AsyncMock(return_value=("ok", []))) as chat:
            await agent._chat("fixture", [{"role": "user", "content": "hello"}])
        self.assertEqual(chat.call_args.args[2:4], (256, 0.7))

    async def test_openai_payload_sends_saved_stop_strings(self):
        from backend.models import providers
        model = {"model": "fixture", "inference_profile": {"stop_strings": ["END"]}}
        payload = providers._openai_payload(model, [{"role": "user", "content": "hello"}], 256, 0.7)
        self.assertEqual(payload["stop"], ["END"])

    async def test_invalid_profile_values_fail_validation(self):
        from backend.api.core import ModelInferenceIn
        from pydantic import ValidationError
        for fields in [{"temperature": float("nan")}, {"maxTokens": 0}, {"systemPrompt": "a" * 16001}, {"stopStrings": ["x"] * 5}]:
            with self.subTest(fields=list(fields)), self.assertRaises(ValidationError):
                ModelInferenceIn(key="fixture", **fields)
