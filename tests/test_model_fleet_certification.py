import unittest
from unittest.mock import patch

from backend.models import registry
from backend.warsat import benchmarks
from scripts import certify_model_fleet


class ModelFleetCertificationTests(unittest.TestCase):
    def test_missing_roles_are_explicitly_blocked_without_starting_work(self):
        with patch.object(registry, "all_models", return_value=[]):
            report, code = certify_model_fleet.certify_fleet()
        self.assertEqual(code, 2)
        self.assertEqual(report["overallStatus"], "blocked")
        self.assertEqual({item["reason"] for item in report["roles"]}, {"local_model_not_registered"})
        self.assertFalse(report["policy"]["deploymentsStarted"])
        self.assertFalse(report["policy"]["remoteProvidersContacted"])

    def test_local_main_and_coder_save_latency_certificates(self):
        models = [
            {
                "key": "main-local",
                "name": "Main local",
                "model": "main-model",
                "provider": "mock",
                "runtime": "mock",
                "role": "main",
                "runtime_status": "reachable",
                "enabled": True,
                "managed": False,
                "context_window": 4096,
            },
            {
                "key": "coder-local",
                "name": "Coder local",
                "model": "coder-model",
                "provider": "mock",
                "runtime": "mock",
                "role": "coder",
                "runtime_status": "reachable",
                "enabled": True,
                "managed": False,
                "context_window": 4096,
            },
        ]

        def get_model(key):
            return next((item for item in models if item["key"] == key), None)

        def test_model(key):
            return {
                "ok": True,
                "status": "reachable",
                "latency_ms": 7,
                "compatibility": {
                    "status": "certified",
                    "supportedModes": ["chat", "code"],
                    "toolSupport": "agentic",
                },
            }

        with patch.object(registry, "all_models", return_value=models), \
             patch.object(registry, "get_model", side_effect=get_model), \
             patch.object(registry, "test_model", side_effect=test_model), \
             patch.object(benchmarks, "save_certificate", side_effect=lambda certificate: certificate):
            report, code = certify_model_fleet.certify_fleet(owner="fleet-test")

        self.assertEqual(code, 0)
        self.assertEqual(report["overallStatus"], "ready")
        self.assertEqual(report["selectedKeys"], ["main-local", "coder-local"])
        self.assertTrue(all(item["benchmark"]["fresh"] for item in report["roles"]))
        self.assertTrue(all(item["readyForCoding"] for item in report["roles"]))

    def test_explicit_remote_target_is_blocked_before_probe(self):
        remote = {
            "key": "remote-coder",
            "name": "Remote coder",
            "model": "remote",
            "provider": "openai",
            "runtime": "remote-api",
            "role": "coder",
            "runtime_status": "reachable",
            "enabled": True,
            "base_url": "https://api.example.invalid/v1",
        }
        with patch.object(registry, "all_models", return_value=[remote]), \
             patch.object(registry, "test_model") as probe:
            report, code = certify_model_fleet.certify_fleet(coder_key="remote-coder", main_key="missing-main")
        self.assertEqual(code, 2)
        self.assertTrue(any(item.get("reason") == "non_local_model" for item in report["roles"]))
        probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
