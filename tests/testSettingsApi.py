import os
import tempfile
import unittest

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-settings-test-"))

from fastapi.testclient import TestClient

from backend import main
from backend.api.core import current_user
from backend.core import runtime_store


class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        runtime_store.set_kv("platform_settings", {})
        main.app.dependency_overrides[current_user] = lambda: {"username": "settings-test", "role": "admin"}
        self.client = TestClient(main.app, base_url="http://127.0.0.1")

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def get_settings(self):
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_defaults_include_automatic_model_governance(self):
        models = self.get_settings()["models"]
        self.assertEqual(models["selectionMode"], "automatic")
        self.assertEqual(models["performancePreference"], "balanced")
        self.assertEqual(models["maxContextTokens"], "automatic")
        self.assertFalse(models["allowMultiGpu"])
        self.assertTrue(models["automaticBenchmarking"])
        self.assertEqual(models["fallbackBehavior"], "ask")

    def test_legacy_engine_is_preserved_without_becoming_the_primary_mode(self):
        runtime_store.set_kv("platform_settings", {"models": {"defaultEngine": "vllm"}})
        models = self.get_settings()["models"]
        self.assertEqual(models["defaultEngine"], "vllm")
        self.assertEqual(models["selectionMode"], "automatic")

    def test_governance_fields_round_trip_with_other_settings(self):
        updates = {
            "selectionMode": "automatic",
            "performancePreference": "responsive",
            "maxContextTokens": "8192",
            "allowMultiGpu": True,
            "automaticBenchmarking": False,
            "fallbackBehavior": "single_gpu",
        }
        for key, value in updates.items():
            response = self.client.post("/api/settings/models", json={"key": key, "value": value})
            self.assertEqual(response.status_code, 200, response.text)

        response = self.client.post("/api/settings/general", json={"key": "language", "value": "en"})
        self.assertEqual(response.status_code, 200, response.text)
        models = self.get_settings()["models"]
        for key, value in updates.items():
            self.assertEqual(models[key], value)

    def test_invalid_governance_value_is_rejected_and_reported(self):
        response = self.client.post("/api/settings/models", json={"key": "performancePreference", "value": "turbo"})
        self.assertEqual(response.status_code, 422)

        validation = self.client.post("/api/settings/validate/models", json={"performancePreference": "turbo"})
        self.assertEqual(validation.status_code, 200)
        self.assertFalse(validation.json()["valid"])
        self.assertIn("performancePreference", validation.json()["error"])

    def test_import_round_trip_preserves_new_fields_and_unknown_fields(self):
        payload = {
            "models": {
                "selectionMode": "automatic",
                "performancePreference": "maximum_quality",
                "maxContextTokens": 16384,
                "allowMultiGpu": True,
                "automaticBenchmarking": True,
                "fallbackBehavior": "ask",
                "futurePreference": "preserve-me",
            }
        }
        response = self.client.post("/api/settings/import", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        models = self.get_settings()["models"]
        self.assertEqual(models["maxContextTokens"], 16384)
        self.assertEqual(models["futurePreference"], "preserve-me")


if __name__ == "__main__":
    unittest.main()
