"""Background loads retain ownership, validation, and cancellation after HTTP returns."""
import os
import tempfile
import threading
import unittest
from contextvars import ContextVar
from unittest.mock import Mock, patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-load-test-"))

from backend.models import registry


class BackgroundLoadingTests(unittest.TestCase):
    def test_load_returns_before_ready_deduplicates_and_can_be_cancelled(self):
        entered, release = threading.Event(), threading.Event()
        identity = ContextVar("test_load_identity", default="missing")
        identity.set("administrator")
        observed = {}

        def load(key, profile, *, _cancel):
            observed.update(identity=identity.get(), profile=profile, cancel=_cancel)
            entered.set()
            release.wait(5)
            return {"ok": True, "status": "stopped"}

        model = {"key": "load-test", "runtime": registry.NATIVE_RUNTIME, "managed": True}
        with patch.object(registry.security, "require"), patch.object(registry, "get_model", return_value=model), \
             patch.object(registry, "start_model", side_effect=load) as start, \
             patch.object(registry.audit, "log"), patch.object(registry, "_record_load_outcome"):
            try:
                result = registry.start_model_background("load-test", {"contextLength": 16384})
                self.assertEqual(result["status"], "starting")
                self.assertTrue(entered.wait(2))
                self.assertEqual(observed["identity"], "administrator")
                self.assertEqual(observed["profile"]["contextLength"], 16384)
                registry.start_model_background("load-test")
                self.assertEqual(start.call_count, 1)
                with patch.object(registry, "_load", return_value={"models": [model]}), \
                     patch.object(registry.security, "load", return_value={}), \
                     patch.object(registry, "get_provider", return_value=Mock(status=Mock(return_value="stopped"))):
                    visible = registry.all_models()[0]
                    self.assertEqual(visible["runtime_status"], "starting")
                    self.assertEqual(visible["load_status"]["status"], "loading")
                self.assertEqual(registry.stop_model("load-test")["status"], "stopping")
                self.assertTrue(observed["cancel"].is_set())
                with self.assertRaisesRegex(Exception, "Cancel loading"):
                    registry.delete_model("load-test")
            finally:
                release.set()
                # Wait for the worker's finally block, without racing patch teardown.
                for thread in threading.enumerate():
                    if thread.name == "rasputin-model-load":
                        thread.join(3)
            self.assertNotIn("load-test", registry._model_loads)

    def test_permission_and_profile_validation_happen_before_worker_creation(self):
        model = {"key": "load-test", "runtime": registry.NATIVE_RUNTIME, "managed": True}
        with patch.object(registry.security, "require", side_effect=PermissionError("denied")), \
             patch.object(registry, "Thread") as thread:
            with self.assertRaises(PermissionError):
                registry.start_model_background("load-test")
            thread.assert_not_called()
        with patch.object(registry.security, "require"), patch.object(registry, "get_model", return_value=model), \
             patch.object(registry, "Thread") as thread:
            with self.assertRaises(ValueError):
                registry.start_model_background("load-test", {"contextLength": -1})
            thread.assert_not_called()

    def test_worker_failure_is_recorded_and_does_not_leave_a_stuck_job(self):
        model = {"key": "failed-load", "runtime": registry.NATIVE_RUNTIME, "managed": True}
        with patch.object(registry.security, "require"), patch.object(registry, "get_model", return_value=model), \
             patch.object(registry, "start_model", side_effect=RuntimeError("runtime unavailable")), \
             patch.object(registry, "_record_load_outcome") as record:
            registry.start_model_background("failed-load")
            for thread in threading.enumerate():
                if thread.name == "rasputin-model-load":
                    thread.join(3)
            record.assert_called_once_with("failed-load", {"ok": False, "error": "runtime unavailable"})
            self.assertNotIn("failed-load", registry._model_loads)

    def test_cancellation_after_runtime_ready_still_stops_the_model(self):
        model = {"key": "late-cancel", "runtime": registry.NATIVE_RUNTIME, "managed": True}
        def load(key, profile, *, _cancel):
            _cancel.set()
            return {"ok": True, "status": "running"}
        provider = Mock()
        provider.stop.return_value = {"ok": True, "status": "stopped"}
        with patch.object(registry.security, "require"), patch.object(registry, "get_model", return_value=model), \
             patch.object(registry, "start_model", side_effect=load), patch.object(registry, "get_provider", return_value=provider), \
             patch.object(registry, "_record_load_outcome"):
            registry.start_model_background("late-cancel")
            for thread in threading.enumerate():
                if thread.name == "rasputin-model-load":
                    thread.join(3)
            provider.stop.assert_called_once_with(model)


if __name__ == "__main__":
    unittest.main()
