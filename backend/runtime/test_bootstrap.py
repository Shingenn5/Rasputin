from pathlib import Path
import json
from tempfile import TemporaryDirectory
import unittest

from backend.runtime.bootstrap import discover_manifest_path, manifest_candidates


class RuntimeBootstrapTests(unittest.TestCase):
    def test_cuda_manifests_pin_companion_cudart_assets(self):
        manifest_path = Path(__file__).resolve().parents[2] / "runtime" / "llama" / "manifest.json"
        manifests = json.loads(manifest_path.read_text(encoding="utf-8"))["runtimes"]
        expected = {
            "cuda12.4": {
                "name": "cudart-llama-bin-win-cuda-12.4-x64.zip",
                "url": "https://github.com/ggml-org/llama.cpp/releases/download/b10586/cudart-llama-bin-win-cuda-12.4-x64.zip",
                "size_bytes": 391443627,
                "sha256": "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6",
            },
            "cuda13.3": {
                "name": "cudart-llama-bin-win-cuda-13.3-x64.zip",
                "url": "https://github.com/ggml-org/llama.cpp/releases/download/b10586/cudart-llama-bin-win-cuda-13.3-x64.zip",
                "size_bytes": 390970417,
                "sha256": "1462a050eb4c684921ba51dcc4cc488a036674c3e73e9945ee705b854808d03e",
            },
        }
        for accelerator, asset in expected.items():
            with self.subTest(accelerator=accelerator):
                runtime = next(item for item in manifests if item["accelerator"] == accelerator)
                self.assertTrue(
                    any(
                        all(candidate.get(field) == value for field, value in asset.items())
                        for candidate in runtime["assets"]
                    )
                )

    def test_manifest_precedence_is_explicit_data_packaged_then_checkout(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            explicit = root / "explicit.json"
            data = root / "data" / "runtimes" / "llama.cpp" / "manifest.json"
            resources = root / "resources" / "llama" / "manifest.json"
            executable = root / "backend" / "rasputin-backend.exe"
            for path in (explicit, data, resources):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
            kwargs = {"data_root": root / "data", "resource_root": root / "resources", "executable": executable}
            self.assertEqual(discover_manifest_path(configured=explicit, **kwargs), explicit.resolve())
            explicit.unlink()
            self.assertEqual(discover_manifest_path(**kwargs), data.resolve())
            data.unlink()
            self.assertEqual(discover_manifest_path(**kwargs), resources.resolve())

    def test_missing_explicit_manifest_remains_missing_and_authoritative(self):
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "not-installed.json"
            self.assertEqual(discover_manifest_path(configured=missing), missing.resolve())
            self.assertFalse(discover_manifest_path(configured=missing).is_file())


if __name__ == "__main__":
    unittest.main()
