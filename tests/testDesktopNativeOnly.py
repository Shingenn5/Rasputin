import os
import tempfile
import unittest
from unittest.mock import patch

from backend.core.response import AppError
from backend.warsat import hardware_probe
import backend.warsat as warsat_module
from backend.warsat.providers import get_provider


class DesktopNativeOnlyTests(unittest.TestCase):
    def test_hardware_probe_never_uses_docker_in_desktop_mode(self):
        with patch.dict(os.environ, {"RASPUTIN_DESKTOP_ONLY": "1"}, clear=False), \
             patch("backend.warsat._docker_cli_path", side_effect=AssertionError("Docker CLI must not be probed")), \
             patch("backend.warsat._gpu_probe_via_docker", side_effect=AssertionError("Docker GPU probe must not run")), \
             patch("backend.warsat.shutil.which", return_value=None), \
             patch("backend.warsat.security.load", return_value={"allow_docker_control": True}):
            result = hardware_probe()

        self.assertTrue(any(item["id"] == "dockerControl" and item["status"] == "skip" for item in result["checks"]))
        self.assertNotIn("dockerRuntimes", result["detectedHardware"])
        self.assertEqual(result["detectedHardware"]["gpus"], [])
        self.assertEqual(result["detectedHardware"]["gpuProbeSource"], "unknown")
        self.assertTrue(all("container" not in str(item).lower() for item in result["warnings"]))

    def test_desktop_deploy_validation_rejects_before_provider_work(self):
        with patch.dict(os.environ, {"RASPUTIN_DESKTOP_ONLY": "1"}, clear=False):
            with self.assertRaises(AppError) as raised:
                warsat_module._validate_deploy_plan({})
        self.assertEqual(raised.exception.code, "desktop_native_only")

    def test_provider_rejects_container_runtime_in_desktop_mode(self):
        with patch.dict(os.environ, {"RASPUTIN_DESKTOP_ONLY": "1"}, clear=False):
            with self.assertRaisesRegex(ValueError, "only native llama.cpp"):
                get_provider({"managed": True, "runtime": "docker-llamacpp"})

    def test_security_save_forces_docker_permission_off(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.dict(os.environ, {"RASPUTIN_DESKTOP_ONLY": "1", "RASPUTIN_DATA_DIR": temporary}, clear=False), \
             patch("backend.core.security.store.set_kv") as set_kv:
            from backend.core import security
            saved = security.save({"allow_docker_control": True})
        self.assertFalse(saved["allow_docker_control"])
        set_kv.assert_called_once()


if __name__ == "__main__":
    unittest.main()
