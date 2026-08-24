import unittest
from unittest.mock import patch

from backend.models import registry
from backend.models.load_profiles import resolve_load_plan
from backend.warsat import providers


class NativeDesktopPreferencesTests(unittest.TestCase):
    def test_global_memory_mode_and_headroom_reach_native_model_start_profile(self):
        model = {"key": "demo", "runtime": "native-llamacpp", "load_profile": {"context_length": 4096}}
        with patch.object(
            registry.runtime_store,
            "get_kv",
            return_value={
                "models": {"memoryMode": "hybrid"},
                "resources": {"hostMemoryHeadroomMb": 3072},
            },
        ):
            resolved = registry._native_model_with_desktop_preferences(model)

        self.assertEqual(resolved["load_profile"]["memory_mode"], "hybrid")
        self.assertEqual(resolved["load_profile"]["context_length"], 4096)
        self.assertEqual(resolved["host_memory_headroom_mb"], 3072)
        self.assertNotIn("memory_mode", model["load_profile"])

    def test_per_model_memory_mode_overrides_global_default(self):
        model = {"load_profile": {"memory_mode": "cpu_only"}}
        with patch.object(
            registry.runtime_store,
            "get_kv",
            return_value={"models": {"memoryMode": "hybrid"}},
        ):
            resolved = registry._native_model_with_desktop_preferences(model)
        self.assertEqual(resolved["load_profile"]["memory_mode"], "cpu_only")

    def test_live_hardware_snapshot_preserves_headroom_and_nested_gpu_capacity(self):
        snapshot = {
            "capabilityProfile": {
                "cpu": {"memoryAvailableMb": 12000, "memoryTotalMb": 32000},
                "devices": [{
                    "deviceId": "gpu:0",
                    "volatile": {"memoryFreeMb": 6000},
                    "static": {"memoryTotalMb": 8192},
                }],
            }
        }
        with patch("backend.warsat.hardware_probe", return_value=snapshot):
            live = providers._native_hardware_snapshot({"host_memory_headroom_mb": 2048})

        self.assertEqual(live["host_memory_headroom_mb"], 2048)
        plan = resolve_load_plan(
            {"memory_mode": "hybrid"},
            hardware=live,
            model={"size_mb": 7000, "context_window": 8192},
            capabilities={},
        )
        self.assertTrue(plan.accepted, plan.block_reasons)
        self.assertEqual([item["device_id"] for item in plan.device_allocation], ["gpu:0", "cpu"])
        self.assertEqual(plan.device_allocation[-1]["role"], "host_ram")


if __name__ == "__main__":
    unittest.main()
