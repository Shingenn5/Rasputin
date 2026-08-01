import unittest
from unittest.mock import Mock, patch

from backend.models import registry


class ModelRegistryStatusCacheTests(unittest.TestCase):
    def setUp(self):
        registry.clear_runtime_status_cache()

    def tearDown(self):
        registry.clear_runtime_status_cache()

    def test_managed_model_status_is_reused_for_short_registry_refreshes(self):
        fake_registry = {"models": [{
            "key": "managed-coder", "container": "coder-runtime",
            "managed": True, "enabled": True, "base_url": "http://127.0.0.1:8001/v1",
        }]}
        provider = Mock()
        provider.status.return_value = "running"
        with patch("backend.models.registry._load", return_value=fake_registry), \
             patch("backend.core.security.load", return_value={"allow_docker_control": True}), \
             patch("backend.models.registry.get_provider", return_value=provider):
            first = registry.all_models()
            second = registry.all_models()

        self.assertEqual(first[0]["container_status"], "running")
        self.assertEqual(second[0]["container_status"], "running")
        provider.status.assert_called_once()

    def test_lifecycle_invalidation_forces_a_fresh_status_probe(self):
        fake_registry = {"models": [{
            "key": "managed-coder", "container": "coder-runtime",
            "managed": True, "enabled": True, "base_url": "http://127.0.0.1:8001/v1",
        }]}
        provider = Mock()
        provider.status.side_effect = ["running", "stopped"]
        with patch("backend.models.registry._load", return_value=fake_registry), \
             patch("backend.core.security.load", return_value={"allow_docker_control": True}), \
             patch("backend.models.registry.get_provider", return_value=provider):
            registry.all_models()
            registry.clear_runtime_status_cache("managed-coder")
            result = registry.all_models()

        self.assertEqual(result[0]["container_status"], "stopped")
        self.assertEqual(provider.status.call_count, 2)
