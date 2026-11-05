import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-load-recovery-"))

from backend.models.load_profiles import resolve_load_plan
from backend.models import registry


class ModelLoadRecoveryTests(unittest.TestCase):
    def plan(self, model, context=16384):
        return resolve_load_plan({"contextLength": context}, hardware={"devices": [{"id": "0", "free_mb": 16000}]},
                                 model={"size_mb": 4000, **model}, capabilities={})

    def test_previous_native_context_allocation_does_not_block_a_larger_reload(self):
        for model in ({"runtime": "native-llamacpp", "context_window": 2048, "context_detected_at": 1},
                      {"runtime": "native-llamacpp", "contextWindow": 2048, "contextDetectedAt": 1}):
            with self.subTest(model=model):
                plan = self.plan(model)
                self.assertTrue(plan.accepted, plan.block_reasons)
                self.assertEqual(plan.resolved_settings["context_length"], 16384)

    def test_real_model_maximum_still_blocks_unsupported_context(self):
        model = {"runtime": "native-llamacpp", "context_window": 2048, "context_detected_at": 1, "model_context_window": 8192}
        self.assertTrue(self.plan(model).blocked)
        self.assertTrue(self.plan(model, 4096).accepted)
        self.assertTrue(self.plan({"context_window": 8192}).blocked)

    def test_retired_runtime_cannot_remain_loading_from_saved_status(self):
        model = {"key": "retired", "managed": True, "runtime": "warsat-llama.cpp", "runtime_status": "starting"}
        with patch.object(registry, "_load", return_value={"models": [model]}), \
             patch.object(registry.security, "load", return_value={"allow_docker_control": False}):
            current = registry.all_models()[0]
        self.assertEqual(current["runtime_status"], "unknown")


if __name__ == "__main__":
    unittest.main()
