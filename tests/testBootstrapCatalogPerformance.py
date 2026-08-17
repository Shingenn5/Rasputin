import unittest
from unittest.mock import patch

from backend.models import catalog


class BootstrapCatalogPerformanceTests(unittest.TestCase):
    def test_bootstrap_catalog_skips_slow_runtime_cache_inventory(self):
        with patch.object(catalog, "_local_items", return_value=[]), \
             patch.object(catalog, "_native_managed_container_items", side_effect=AssertionError("legacy Docker scan must be deferred")), \
             patch.object(catalog, "_native_docker_cache_items", side_effect=AssertionError("Docker cache scan must be deferred")), \
             patch.object(catalog, "_warsat_cache_items", side_effect=AssertionError("running-runtime scan must be deferred")):
            payload = catalog.local_catalog(include_runtime_cache=False)

        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["count"], 0)


if __name__ == "__main__":
    unittest.main()