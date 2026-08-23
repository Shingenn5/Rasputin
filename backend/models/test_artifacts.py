import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from backend.core.response import AppError
from backend.models.artifacts import ArtifactStore
from backend.models import registry


class ArtifactStoreTests(unittest.TestCase):
    def test_manifest_is_durable_and_duplicate_install_is_idempotent(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_dir = root / "models" / "org" / "variant"
            model_dir.mkdir(parents=True)
            model = model_dir / "model-Q4_K_M.gguf"
            mmproj = model_dir / "mmproj.gguf"
            model.write_bytes(b"model")
            mmproj.write_bytes(b"mmproj")
            job = SimpleNamespace(
                id="job-1", repository="org/model", revision="rev-1", destination=str(model_dir),
                files=[
                    {"path": model.name, "expected_size": 5, "sha256": None, "role": "model"},
                    {"path": mmproj.name, "expected_size": 6, "sha256": None, "role": "mmproj"},
                ],
            )
            store = ArtifactStore(root)
            store.save_job_metadata(job.id, {"variant_id": "q4", "quantization": "Q4_K_M"})
            first = store.install(job)
            second = store.install(job)
            self.assertEqual(first["artifact_id"], second["artifact_id"])
            self.assertEqual(len(store.list_installed()), 1)
            self.assertEqual(store.list_installed()[0]["mmproj_files"][0]["localPath"], str(mmproj.resolve()))
            self.assertEqual(ArtifactStore(root).list_installed()[0]["variant_id"], "q4")

    def test_registry_accepts_configured_data_model_root_and_rejects_outside(self):
        with TemporaryDirectory() as tmp:
            previous = os.environ.get("RASPUTIN_DATA_DIR")
            os.environ["RASPUTIN_DATA_DIR"] = tmp
            try:
                allowed = Path(tmp) / "models" / "installed.gguf"
                allowed.parent.mkdir(parents=True)
                allowed.write_bytes(b"gguf")
                self.assertEqual(registry._safe_file(allowed), allowed.resolve())
                outside = Path(tmp) / "outside.gguf"
                outside.write_bytes(b"gguf")
                with self.assertRaises(AppError):
                    registry._safe_file(outside)
            finally:
                if previous is None:
                    os.environ.pop("RASPUTIN_DATA_DIR", None)
                else:
                    os.environ["RASPUTIN_DATA_DIR"] = previous


if __name__ == "__main__":
    unittest.main()
