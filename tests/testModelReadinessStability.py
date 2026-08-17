import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-readiness-stability-"))

from backend.models import compatibility
from backend.models import registry


class ModelReadinessStabilityTests(unittest.TestCase):
    def test_certification_fingerprint_covers_runtime_identity(self):
        model = {
            "provider": "vllm",
            "runtime": "managed-local",
            "model": "qwen-coder",
            "image": "image:v1",
            "base_url": "http://127.0.0.1:8001/v1",
        }
        profile = {"fingerprint": compatibility.runtime_fingerprint(model)}
        self.assertTrue(compatibility.certification_is_current(model, profile))
        for field, value in (("provider", "llama.cpp"), ("runtime", "external-local"), ("model", "other-model"), ("image", "image:v2"), ("base_url", "http://127.0.0.1:8002/v1")):
            changed = dict(model)
            changed[field] = value
            self.assertFalse(compatibility.certification_is_current(changed, profile), field)

    def test_stale_certification_is_explicitly_chat_only_on_read(self):
        model = {
            "key": "coder",
            "provider": "vllm",
            "runtime": "managed-local",
            "model": "new-model",
            "image": "image:v2",
            "base_url": "http://127.0.0.1:8002/v1",
            "tool_support": "agentic",
            "certification_status": "certified",
            "compatibility": {
                "status": "certified",
                "supportedModes": ["chat", "code"],
                "toolSupport": "agentic",
                "fingerprint": "vllm:managed-local:old-model:image:v1:http://127.0.0.1:8001/v1",
            },
        }
        with patch.object(registry, "_load", return_value={"models": [model]}):
            result = registry.get_model("coder")
        profile = result["compatibility"]
        self.assertEqual(profile["status"], "unknown")
        self.assertEqual(profile["supportedModes"], [])
        self.assertEqual(profile["toolSupport"], "chat-only")
        self.assertTrue(profile["certificationInvalid"])
        self.assertEqual(result["certification_status"], "unknown")
        self.assertEqual(result["tool_support"], "chat-only")

    def test_upsert_does_not_accept_stale_profile_for_new_identity(self):
        old = {
            "key": "coder",
            "provider": "mock",
            "runtime": "mock",
            "model": "old-model",
            "image": "image:v1",
            "base_url": "http://127.0.0.1:8001/v1",
            "compatibility": {
                "status": "certified",
                "supportedModes": ["chat", "code"],
                "toolSupport": "agentic",
                "fingerprint": "mock:mock:old-model:image:v1:http://127.0.0.1:8001/v1",
            },
            "tool_support": "agentic",
            "certification_status": "certified",
        }
        saved = {}
        incoming = {
            "key": "coder",
            "provider": "mock",
            "runtime": "mock",
            "model": "new-model",
            "image": "image:v2",
            "base_url": "http://127.0.0.1:8002/v1",
            "compatibility": old["compatibility"],
            "tool_support": "agentic",
            "certification_status": "certified",
        }
        with patch.object(registry.security, "require"), \
             patch.object(registry, "_load", return_value={"models": [old]}), \
             patch.object(registry, "_save", side_effect=lambda data: saved.update(data)):
            result = registry.upsert(incoming)
        self.assertNotIn("compatibility", result)
        self.assertNotIn("compatibility", saved["models"][0])
        self.assertNotIn("tool_support", saved["models"][0])
        self.assertNotIn("certification_status", saved["models"][0])


if __name__ == "__main__":
    unittest.main()