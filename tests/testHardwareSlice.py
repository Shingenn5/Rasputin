import asyncio
import os
import unittest
from unittest.mock import patch

from backend.api import warsat_api
from backend.core import security
from backend.core import settings_api


class HardwareSliceTests(unittest.TestCase):
    def test_hardware_monitor_setting_is_validated_and_persisted(self):
        self.assertFalse(settings_api.DEFAULT_SETTINGS["hardware"]["showLiveUsage"])
        self.assertIsNone(settings_api._domain_setting_error("hardware", "showLiveUsage", True))
        self.assertIsNotNone(settings_api._domain_setting_error("hardware", "showLiveUsage", "true"))
        self.assertIsNone(settings_api._domain_setting_error("models", "memoryMode", "hybrid"))
        self.assertIsNotNone(settings_api._domain_setting_error("models", "memoryMode", "unified_pool"))

        with patch.object(settings_api.store, "get_kv", return_value={}),              patch.object(settings_api.store, "set_kv") as set_kv,              patch.object(security, "load", return_value={}):
            result = settings_api.update_setting(
                "hardware",
                settings_api.SettingUpdate(key="showLiveUsage", value=True),
                _user={"username": "admin", "role": "admin"},
            )

        self.assertTrue(result["updatedSettings"]["showLiveUsage"])
        saved = set_kv.call_args.args[1]
        self.assertTrue(saved["hardware"]["showLiveUsage"])

    def test_desktop_system_metrics_never_call_docker_fallback(self):
        async def call_metrics():
            return await warsat_api.warsat_system_metrics(_user={"username": "admin"})

        with patch.dict(os.environ, {"RASPUTIN_DESKTOP_ONLY": "1"}, clear=False),              patch("shutil.which", return_value=None),              patch.object(
                 warsat_api.warsat,
                 "gpu_live_metrics_via_docker",
                 side_effect=AssertionError("desktop telemetry must not call Docker"),
             ):
            response = asyncio.run(call_metrics())

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["gpus"], [])


if __name__ == "__main__":
    unittest.main()
