import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

from backend.core.response import AppError
from backend.runtime.llamacpp_installer import (
    HardwareRuntimeInput,
    LlamaCppRuntimeInstaller,
    RuntimeAsset,
    RuntimeManifest,
    extract_zip_safely,
    select_compatible_manifest,
)


def _manifest(version="v1", accelerator="cpu", archive_name="runtime.zip", archive_hash=None):
    return RuntimeManifest(
        engine="llama.cpp",
        version=version,
        platform="windows",
        architecture="x86_64",
        accelerator=accelerator,
        assets=(RuntimeAsset(archive_name, f"fixture://{archive_name}", archive_hash or "0" * 64),),
        license="Apache-2.0",
    )


class LlamaCppInstallerTests(TestCase):
    def test_selects_compatible_manifest_and_rejects_unsupported_accelerator(self):
        cpu = _manifest(accelerator="cpu")
        cuda = _manifest(version="v2", accelerator="cuda12")
        selected = select_compatible_manifest(
            [cpu, cuda],
            HardwareRuntimeInput("windows", "amd64", ("cuda",), ("12",)),
        )
        self.assertEqual(selected.version, "v2")
        with self.assertRaisesRegex(AppError, "No llama.cpp runtime matches"):
            select_compatible_manifest([cpu], HardwareRuntimeInput("windows", "x86_64", ("vulkan",)))

    def test_hash_mismatch_is_rejected_before_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "runtime.zip"
            _write_zip(source, {"llama-server.exe": b"fake"})
            installer = LlamaCppRuntimeInstaller(
                Path(temporary) / "runtimes",
                downloader=lambda _asset, destination: shutil.copyfile(source, destination),
                smoke_runner=lambda _executable: True,
            )
            with self.assertRaisesRegex(AppError, "SHA-256 mismatch"):
                installer.install(_manifest(archive_hash="f" * 64))
            self.assertIsNone(installer.active_record())

    def test_zip_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "unsafe.zip"
            _write_zip(archive, {"../outside.txt": b"nope"})
            with self.assertRaisesRegex(AppError, "traverses outside"):
                extract_zip_safely(archive, Path(temporary) / "out")

    def test_install_activates_atomically_and_restores_previous_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "runtime.zip"
            _write_zip(source, {"llama-server.exe": b"fake"})
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            installer = LlamaCppRuntimeInstaller(
                Path(temporary) / "runtimes",
                downloader=lambda _asset, destination: shutil.copyfile(source, destination),
                smoke_runner=lambda executable: executable.name == "llama-server.exe",
            )
            first = installer.install(_manifest(version="v1", archive_hash=digest))
            second = installer.install(_manifest(version="v2", archive_hash=digest))
            self.assertEqual(installer.active_record()["version"], "v2")
            self.assertTrue(installer.active_path.is_file())
            self.assertTrue(Path(first["path"]).is_dir())
            restored = installer.restore_previous()
            self.assertEqual(restored["version"], "v1")
            self.assertEqual(installer.active_record()["previous"]["version"], "v2")
            self.assertEqual(second["previous"]["version"], "v1")


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
