import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-training-tests-"))

from fastapi.testclient import TestClient
from backend import main
from backend.api.core import require_admin
from backend.core import runtime_store as store, training


DATASET = '{"text":"First training example."}\n{"text":"Second training example."}'


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rasputin-training-model-")
        self.model = Path(self.temp.name)
        (self.model / "config.json").write_text("{}")
        (self.model / "model.safetensors").write_bytes(b"fixture")
        (self.model / "tokenizer.json").write_text("{}")
        store.set_kv(training._KEY, [])
        training._processes.clear()
        self.client = TestClient(main.app, base_url="http://127.0.0.1:8899", raise_server_exceptions=False)
        self.config = {"model_path": str(self.model), "dataset": DATASET, "name": "Test", "max_steps": 2,
                       "learning_rate": 0.0002, "rank": 8, "max_length": 128}

    def tearDown(self):
        main.app.dependency_overrides.clear()
        training._processes.clear()
        store.set_kv(training._KEY, [])
        self.temp.cleanup()

    def test_dataset_rejects_invalid_and_oversized_records(self):
        self.assertEqual(len(training.validate_dataset(DATASET)), 2)
        for raw in ["", "[]", '{"text":"one"}', '{"messages":[]}', "broken", '{"text":"' + "x" * 4194304 + '"}']:
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                training.validate_dataset(raw)

    def test_preflight_requires_original_weights(self):
        with self.assertRaisesRegex(ValueError, "GGUF"):
            training.preflight(str(self.model.parent), DATASET)

    def test_preflight_blocks_loaded_inference_and_second_job(self):
        with patch.object(training, "capability", return_value={"ready": True, "blockers": []}), patch.object(training.registry, "all_models", return_value=[{"runtime": "native-llamacpp", "runtime_status": "reachable"}]):
            result = training.preflight(str(self.model), DATASET)
        self.assertFalse(result["ready"])
        self.assertIn("Stop loaded", result["blockers"][0])
        process = object()
        training._processes["active"] = process
        store.set_kv(training._KEY, [{"id": "active", "status": "running"}])
        with patch.object(training, "capability", return_value={"ready": True, "blockers": []}), patch.object(training.registry, "all_models", return_value=[]):
            self.assertFalse(training.preflight(str(self.model), DATASET)["ready"])

    def test_restart_marks_runs_interrupted(self):
        store.set_kv(training._KEY, [{"id": "missing", "status": "running"}])
        self.assertEqual(training.jobs()[0]["status"], "interrupted")

    def test_routes_require_admin_and_validate_bounds(self):
        with patch("backend.api.core.auth.public_session", return_value={"authenticated": False}):
            self.assertEqual(self.client.get("/api/training").status_code, 403)
        main.app.dependency_overrides[require_admin] = lambda: {"username": "admin", "role": "admin"}
        with patch.object(training, "capability", return_value={"ready": False, "blockers": ["No runtime"]}):
            self.assertEqual(self.client.get("/api/training").json()["data"]["capability"]["ready"], False)
        self.assertEqual(self.client.post("/api/training/jobs", json={**self.config, "max_steps": 10001}).status_code, 422)

    def test_worker_progress_and_completion_are_recorded(self):
        class Process:
            stdout = io.StringIO(json.dumps({"event": "progress", "step": 2, "loss": .5}) + '\n{"event":"complete"}\n')
            def wait(self): return 0
        process = Process()
        training._processes["run"] = process
        store.set_kv(training._KEY, [{"id": "run", "status": "starting"}])
        training._watch("run", process)
        job = training.jobs()[0]
        self.assertEqual((job["status"], job["step"], job["loss"]), ("completed", 2, .5))
        self.assertNotIn("run", training._processes)

    def test_start_rechecks_preflight_before_spawn(self):
        with patch.object(training, "preflight", return_value={"ready": False, "blockers": ["No runtime"]}), patch.object(training.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(ValueError, "No runtime"):
                training.start("admin", self.config)
            spawn.assert_not_called()

    def test_buffered_progress_cannot_undo_cancellation(self):
        class Process:
            stdout = io.StringIO('{"event":"progress","step":1}\n')
            def wait(self): return -15
        process = Process()
        training._processes["cancel"] = process
        store.set_kv(training._KEY, [{"id": "cancel", "status": "stopping"}])
        training._watch("cancel", process)
        self.assertEqual(training.jobs()[0]["status"], "cancelled")

    def test_inference_loading_is_blocked_during_training(self):
        training._processes["active"] = object()
        store.set_kv(training._KEY, [{"id": "active", "status": "running"}])
        with self.assertRaisesRegex(ValueError, "Stop the active training"):
            with training.inference_slot():
                self.fail("Inference entered during training")

    def test_adapter_export_excludes_dataset_and_is_immutable(self):
        import zipfile
        with patch.object(training, "data_dir", return_value=self.model):
            output = self.model / "training/export/adapter"
            output.mkdir(parents=True)
            (output / "adapter_config.json").write_text("{}")
            (output / "dataset.jsonl").write_text(DATASET)
            store.set_kv(training._KEY, [{"id": "export", "status": "completed"}])
            result = training.export_adapter("export")
            with zipfile.ZipFile(result) as archive:
                self.assertEqual(archive.namelist(), ["adapter_config.json"])
            original = result.stat().st_mtime_ns
            self.assertEqual(training.export_adapter("export").stat().st_mtime_ns, original)

    def test_capability_blocks_cpu_and_incompatible_adapter_environment(self):
        from types import SimpleNamespace
        for runtime, expected in [({"missing": [], "cuda": False, "error": None}, "CUDA-capable"),
                                  ({"missing": [], "cuda": True, "error": "ImportError"}, "compatibility check failed")]:
            with self.subTest(runtime=runtime), patch.object(training, "_interpreter", return_value=__import__("sys").executable), patch.object(training.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(runtime))):
                result = training.capability()
                self.assertFalse(result["ready"])
                self.assertIn(expected, result["blockers"][0])

    def test_cancel_stops_owned_python_worker(self):
        import subprocess
        import sys
        with patch.object(training, "data_dir", return_value=self.model):
            folder = self.model / "training/owned"
            folder.mkdir(parents=True)
            process = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"],
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                training._processes["owned"] = process
                store.set_kv(training._KEY, [{"id": "owned", "status": "running"}])
                self.assertEqual(training.cancel("owned")["status"], "stopping")
                process.wait(timeout=10)
                self.assertIsNotNone(process.poll())
                self.assertTrue((folder / "cancel.requested").exists())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
