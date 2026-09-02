from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from backend.runtime.llamacpp_installer import AppError, HardwareRuntimeInput, RuntimeManifest, SmokeCheckResult
from backend.runtime.runtime_service import (
    LlamaCppRuntimeService,
    _default_http_downloader,
    _default_smoke_runner,
    detect_local_runtime_hardware,
)


def manifest(content: bytes = b"llama-server") -> RuntimeManifest:
    digest = hashlib.sha256(content).hexdigest()
    return RuntimeManifest.from_dict({
        "engine": "llama.cpp",
        "version": "b-test",
        "platform": "windows",
        "architecture": "x86_64",
        "accelerator": "cpu",
        "license": "MIT",
        "executable": "llama-server.exe",
        "assets": [{"name": "llama-server.exe", "url": "fixture://llama", "sha256": digest}],
    })


class RuntimeServiceTests(unittest.TestCase):
    def test_detects_nvidia_cuda_version_for_runtime_selection(self):
        inventory = subprocess.CompletedProcess(["nvidia-smi"], 0, stdout="NVIDIA GeForce RTX 5060 Ti\n", stderr="")
        details = subprocess.CompletedProcess(["nvidia-smi"], 0, stdout="CUDA UMD Version: 13.3", stderr="")
        with patch("backend.runtime.runtime_service.shutil.which", return_value="nvidia-smi.exe"), patch(
            "backend.runtime.runtime_service.subprocess.run",
            side_effect=[inventory, details],
        ):
            detected = detect_local_runtime_hardware()

        self.assertEqual(detected.accelerators, ("cuda", "cpu"))
        self.assertEqual(detected.cuda_versions, ("13.3",))

    def test_ensure_downloads_only_selected_runtime_once(self):
        cpu_content = b"cpu-runtime"
        cuda_content = b"cuda-runtime"
        cpu = manifest(cpu_content)
        cuda = RuntimeManifest.from_dict({
            **manifest(cuda_content).to_dict(),
            "manifest_id": "cuda-13.3",
            "accelerator": "cuda13.3",
        })
        downloaded = []

        def download(asset, destination):
            downloaded.append(asset.name)
            content = cuda_content if asset.sha256 == hashlib.sha256(cuda_content).hexdigest() else cpu_content
            Path(destination).write_bytes(content)

        with TemporaryDirectory() as tmp, patch(
            "backend.runtime.runtime_service.detect_local_runtime_hardware",
            return_value=HardwareRuntimeInput("windows", "x64", ("cuda", "cpu"), ("13.3",)),
        ):
            service = LlamaCppRuntimeService(
                root=tmp,
                manifests=[cpu, cuda],
                downloader=download,
                smoke_runner=lambda _: True,
            )
            first = service.ensure_local_runtime()
            second = service.ensure_local_runtime()

        self.assertEqual(first["manifest"]["accelerator"], "cuda13.3")
        self.assertTrue(first["downloaded"])
        self.assertFalse(second["downloaded"])
        self.assertEqual(downloaded, ["llama-server.exe"])

    def test_ensure_replaces_legacy_bundled_record_with_user_local_runtime(self):
        content = b"local-runtime"
        selected = RuntimeManifest.from_dict({
            **manifest(content).to_dict(),
            "manifest_id": "selected-cpu",
        })
        with TemporaryDirectory() as tmp, patch(
            "backend.runtime.runtime_service.detect_local_runtime_hardware",
            return_value=HardwareRuntimeInput("windows", "x64", ("cpu",)),
        ):
            root = Path(tmp)
            legacy = root / "legacy-bundle"
            legacy.mkdir()
            (legacy / "llama-server.exe").write_bytes(b"legacy")
            service = LlamaCppRuntimeService(
                root=root / "runtime",
                manifests=[selected],
                downloader=lambda _asset, destination: Path(destination).write_bytes(content),
                smoke_runner=lambda _: True,
            )
            service.installer._write_active({
                "version": selected.version,
                "installation_id": selected.installation_id,
                "path": str(legacy),
                "manifest": selected.to_dict(),
                "bundled": True,
            })

            ensured = service.ensure_local_runtime()

        self.assertTrue(ensured["downloaded"])
        self.assertNotEqual(Path(ensured["path"]), legacy)
    def test_default_hooks_install_and_verify_without_network(self):
        content = b"llama-server"

        def download(asset, destination):
            Path(destination).write_bytes(content)

        with TemporaryDirectory() as tmp:
            service = LlamaCppRuntimeService(root=tmp)
            with patch("backend.runtime.runtime_service._default_http_downloader", side_effect=download) as downloader:
                with patch(
                    "backend.runtime.runtime_service._default_smoke_runner",
                    return_value=SmokeCheckResult(True, "ok"),
                ) as smoke_runner:
                    service.install(manifest(content))
                    result = service.verify_active()
            downloader.assert_called_once()
            smoke_runner.assert_called()
            self.assertTrue(result["ok"])

    def test_default_downloader_streams_with_hf_authorization_and_replaces_atomically(self):
        content = b"streamed runtime"
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = [content[:8], content[8:], b""]
        asset = manifest(content).assets[0]

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / asset.name
            target.write_bytes(b"old runtime")
            with patch.dict(os.environ, {"HF_TOKEN": "secret-token", "HUGGINGFACE_HUB_TOKEN": ""}):
                with patch("backend.runtime.runtime_service.urllib.request.urlopen", return_value=response) as urlopen:
                    _default_http_downloader(asset, target)

            self.assertEqual(target.read_bytes(), content)
            request = urlopen.call_args.args[0]
            self.assertEqual(request.full_url, asset.url)
            self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
            self.assertEqual(urlopen.call_args.kwargs["timeout"], 120)
            self.assertEqual([item.name for item in Path(tmp).iterdir()], [asset.name])

    def test_default_downloader_converts_http_and_network_errors_without_token_leak(self):
        asset = manifest().assets[0]
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / asset.name
            with patch.dict(os.environ, {"HF_TOKEN": "secret-token"}):
                with patch(
                    "backend.runtime.runtime_service.urllib.request.urlopen",
                    side_effect=urllib.error.HTTPError(asset.url, 503, "unavailable", {}, None),
                ):
                    with self.assertRaises(AppError) as http_error:
                        _default_http_downloader(asset, target)
            self.assertEqual(http_error.exception.code, "runtime_download_failed")
            self.assertNotIn("secret-token", str(http_error.exception))
            self.assertFalse(target.exists())

            with patch("backend.runtime.runtime_service.urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
                with self.assertRaises(AppError) as network_error:
                    _default_http_downloader(asset, target)
            self.assertEqual(network_error.exception.code, "runtime_download_failed")

    def test_default_smoke_runner_only_checks_version_and_returns_result(self):
        executable = Path("llama-server.exe")
        completed = subprocess.CompletedProcess([str(executable), "--version"], 0, stdout="version", stderr="")
        with patch("backend.runtime.runtime_service.subprocess.run", return_value=completed) as run:
            result = _default_smoke_runner(executable)

        self.assertEqual(result, SmokeCheckResult(True, "Runtime executable responded to --version."))
        command, options = run.call_args
        self.assertEqual(command[0], [str(executable), "--version"])
        self.assertFalse(options["check"])
        self.assertTrue(options["capture_output"])
        self.assertEqual(options["timeout"], 15)
        if os.name == "nt":
            self.assertEqual(options["creationflags"], subprocess.CREATE_NO_WINDOW)

        with patch(
            "backend.runtime.runtime_service.subprocess.run",
            side_effect=subprocess.TimeoutExpired([str(executable), "--version"], 15),
        ):
            timed_out = _default_smoke_runner(executable)
        self.assertFalse(timed_out.ok)
        self.assertIn("timed out", timed_out.message)


    def test_selects_and_installs_pinned_runtime(self):
        content = b"llama-server"

        def download(asset, destination):
            Path(destination).write_bytes(content)

        with TemporaryDirectory() as tmp:
            service = LlamaCppRuntimeService(
                root=tmp,
                manifests=[manifest(content)],
                downloader=download,
                smoke_runner=lambda path: path.name == "llama-server.exe",
            )
            selected = service.select({"platform": "windows", "architecture": "x64", "accelerators": ["cpu"]})
            self.assertEqual(selected.version, "b-test")
            record = service.install(selected)
            self.assertEqual(record["version"], "b-test")
            self.assertTrue(Path(service.active_engine_path()).is_file())
            self.assertTrue(service.verify_active()["ok"])
            self.assertEqual(service.status()["installed"][0]["version"], "b-test")

    def test_missing_manifest_and_unsupported_hardware_are_actionable(self):
        with TemporaryDirectory() as tmp:
            service = LlamaCppRuntimeService(root=tmp)
            with self.assertRaises(AppError) as missing:
                service.select({"platform": "windows", "architecture": "x64", "accelerators": ["cpu"]})
            self.assertEqual(missing.exception.code, "runtime_manifest_missing")

            service = LlamaCppRuntimeService(root=tmp, manifests=[manifest()])
            with self.assertRaises(AppError) as unsupported:
                service.select({"platform": "windows", "architecture": "x64", "accelerators": ["cuda"]})
            self.assertEqual(unsupported.exception.code, "runtime_accelerator_unsupported")

    def test_bundled_runtime_is_ready_without_downloading_or_installing(self):
        bundled_manifest = RuntimeManifest.from_dict({
            **manifest(b"bundled").to_dict(),
            "manifest_id": "bundled-cpu",
            "bundled_path": "bundled/cpu",
        })
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundled" / "cpu"
            bundle.mkdir(parents=True)
            executable = bundle / "llama-server.exe"
            executable.write_bytes(b"bundled runtime")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps({"runtimes": [bundled_manifest.to_dict()]}), encoding="utf-8")

            service = LlamaCppRuntimeService(root=root / "state", manifest_path=manifest_path)
            with patch("backend.runtime.runtime_service._default_http_downloader", side_effect=AssertionError("bundled runtime must not download")):
                status = service.status()
                record = service.install(bundled_manifest)

            self.assertEqual(status["state"], "ready")
            self.assertTrue(status["bundled"])
            self.assertEqual(service.bundled_engine_path(), str(executable.resolve()))
            self.assertEqual(service.active_engine_path(), str(executable.resolve()))
            self.assertTrue(record["bundled"])

    def test_status_exposes_first_run_and_repair_states(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(json.dumps({"runtimes": [manifest(b"x").to_dict()]}), encoding="utf-8")
            service = LlamaCppRuntimeService(root=Path(tmp) / "runtime", manifest_path=manifest_path)
            first_run = service.status()
            self.assertEqual(first_run["state"], "install_required")
            self.assertTrue(first_run["manifestAvailable"])
            service.installer.active_path.write_text(json.dumps({
                "version": "b-test",
                "installation_id": manifest(b"x").installation_id,
                "path": str(Path(tmp) / "runtime" / "versions" / "missing"),
                "manifest": manifest(b"x").to_dict(),
            }), encoding="utf-8")
            repair = service.status()
            self.assertEqual(repair["state"], "repair_required")
            self.assertTrue(repair["repairRequired"])

    def test_rollback_restores_previous_active_runtime(self):
        first = manifest(b"one")
        second = RuntimeManifest.from_dict({**first.to_dict(), "version": "b-two", "manifest_id": "b-two"})

        def download(asset, destination):
            Path(destination).write_bytes(b"two" if asset.name == "llama-server.exe" and "two" in str(destination) else b"one")

        with TemporaryDirectory() as tmp:
            service = LlamaCppRuntimeService(root=tmp, manifests=[first, second], downloader=download, smoke_runner=lambda _: True)
            # Use separate deterministic installers for the two content hashes.
            service.install(first, downloader=lambda asset, path: Path(path).write_bytes(b"one"), smoke_runner=lambda _: True)
            service.install(second, downloader=lambda asset, path: Path(path).write_bytes(b"one"), smoke_runner=lambda _: True)
            self.assertEqual(service.status()["active"]["version"], "b-two")
            restored = service.rollback()
            self.assertEqual(restored["version"], "b-test")


if __name__ == "__main__":
    unittest.main()
