from __future__ import annotations

import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from concurrent.futures import ThreadPoolExecutor
import unittest

from backend.models.desktop_acquisition import DesktopAcquisitionService


class DesktopAcquisitionTests(unittest.TestCase):
    def test_resolves_exact_variants_without_network(self):
        result = DesktopAcquisitionService.resolve_variants(
            {"id": "acme/coder", "sha": "rev-1"},
            [
                {"rfilename": "coder-Q4_K_M.gguf", "size": 4},
                {"rfilename": "mmproj-coder-f16.gguf", "size": 2},
            ],
        )
        self.assertEqual(result["issues"], [])
        self.assertEqual(len(result["variants"]), 2)
        self.assertEqual(result["variants"][0]["revision"], "rev-1")

    def test_exact_download_publishes_artifact_and_rehydrates(self):
        payloads = {
            "coder-Q4_K_M.gguf": b"model",
            "mmproj-coder-f16.gguf": b"project",
        }

        def transfer(file, target, offset, control, progress):
            data = payloads[file.path]
            with target.open("ab" if offset else "wb") as handle:
                handle.write(data[offset:])
            progress(len(data))

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_data_dir = os.environ.get("RASPUTIN_DATA_DIR")
            os.environ["RASPUTIN_DATA_DIR"] = str(root)
            executor = ThreadPoolExecutor(max_workers=1)
            try:
                service = DesktopAcquisitionService(data_root=root, transfer=transfer, executor=executor)
                variant = {
                    "id": "acme-coder-q4",
                    "repository": "acme/coder",
                    "revision": "rev-1",
                    "files": list(payloads),
                    "modelFiles": ["coder-Q4_K_M.gguf"],
                    "mmprojFiles": ["mmproj-coder-f16.gguf"],
                    "fileSizes": {key: len(value) for key, value in payloads.items()},
                    "quantization": "Q4_K_M",
                }
                created = service.start_variant_download(variant)
                deadline = time.monotonic() + 3
                finished = created
                while finished["state"] not in {"completed", "failed"} and time.monotonic() < deadline:
                    time.sleep(0.01)
                    finished = service.get_job(created["id"])
                self.assertEqual(finished["state"], "completed")
                artifact = finished["artifact"]
                self.assertTrue(Path(artifact["mainModelPath"]).is_file())
                self.assertEqual(len(artifact["modelFiles"]), 1)
                self.assertEqual(len(artifact["mmprojFiles"]), 1)
                self.assertEqual(Path(artifact["mainModelPath"]).read_bytes(), b"model")

                rehydrated = DesktopAcquisitionService(data_root=root, transfer=transfer, executor=executor)
                persisted = rehydrated.get_job(created["id"])
                self.assertEqual(persisted["state"], "completed")
                self.assertTrue(persisted["artifact"]["mainModelPath"].endswith("coder-Q4_K_M.gguf"))
            finally:
                executor.shutdown(wait=True)
                if previous_data_dir is None:
                    os.environ.pop("RASPUTIN_DATA_DIR", None)
                else:
                    os.environ["RASPUTIN_DATA_DIR"] = previous_data_dir

    def test_variant_requires_exact_sizes(self):
        with TemporaryDirectory() as tmp:
            service = DesktopAcquisitionService(data_root=tmp, executor=ThreadPoolExecutor(max_workers=1))
            with self.assertRaises(ValueError):
                service.start_variant_download({
                    "repository": "acme/coder",
                    "revision": "rev-1",
                    "files": ["coder.gguf"],
                })


if __name__ == "__main__":
    unittest.main()
