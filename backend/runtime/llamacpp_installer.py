"""Bounded, injectable llama.cpp runtime installation primitives.

This module deliberately does not know how to discover hardware, download from
the network, or launch a real executable. Callers supply an explicit manifest
and inject those side effects, which keeps the installer deterministic and
safe to exercise in unit tests.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence

from backend.core.response import AppError


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DEFAULT_ENGINE = "llama.cpp"
_DEFAULT_EXECUTABLE = "llama-server.exe"


@dataclass(frozen=True)
class RuntimeAsset:
    """One manifest-pinned runtime asset."""

    name: str
    url: str
    sha256: str
    size_bytes: int | None = None
    license: str | None = None
    archive: bool | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RuntimeAsset":
        return cls(
            name=str(payload.get("name") or ""),
            url=str(payload.get("url") or ""),
            sha256=str(payload.get("sha256") or payload.get("hash") or "").lower(),
            size_bytes=_optional_int(payload.get("size_bytes", payload.get("size"))),
            license=_optional_string(payload.get("license")),
            archive=_optional_bool(payload.get("archive")),
        )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "url": self.url,
            "sha256": self.sha256,
        }
        if self.size_bytes is not None:
            payload["size_bytes"] = self.size_bytes
        if self.license:
            payload["license"] = self.license
        if self.archive is not None:
            payload["archive"] = self.archive
        return payload

    @property
    def is_archive(self) -> bool:
        return self.archive if self.archive is not None else self.name.lower().endswith(".zip")


@dataclass(frozen=True)
class RuntimeManifest:
    """A complete, explicit compatibility and integrity contract."""

    engine: str
    version: str
    platform: str
    accelerator: str
    assets: tuple[RuntimeAsset, ...]
    license: str
    architecture: str = "x86_64"
    executable: str = _DEFAULT_EXECUTABLE
    manifest_id: str | None = None
    bundled_path: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RuntimeManifest":
        raw_assets = payload.get("assets")
        if not isinstance(raw_assets, Sequence) or isinstance(raw_assets, (str, bytes)):
            raw_assets = []
        return cls(
            engine=str(payload.get("engine") or ""),
            version=str(payload.get("version") or ""),
            platform=str(payload.get("platform") or ""),
            accelerator=str(payload.get("accelerator") or ""),
            assets=tuple(RuntimeAsset.from_dict(item) for item in raw_assets if isinstance(item, Mapping)),
            license=str(payload.get("license") or ""),
            architecture=str(payload.get("architecture") or "x86_64"),
            executable=str(payload.get("executable") or _DEFAULT_EXECUTABLE),
            manifest_id=_optional_string(payload.get("manifest_id", payload.get("id"))),
            bundled_path=_optional_string(payload.get("bundled_path", payload.get("bundledPath"))),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "version": self.version,
            "platform": self.platform,
            "architecture": self.architecture,
            "accelerator": self.accelerator,
            "assets": [asset.to_dict() for asset in self.assets],
            "license": self.license,
            "executable": self.executable,
            **({"manifest_id": self.manifest_id} if self.manifest_id else {}),
            **({"bundled_path": self.bundled_path} if self.bundled_path else {}),
        }

    @property
    def installation_id(self) -> str:
        raw = self.manifest_id or "-".join(
            (self.engine, self.version, self.platform, self.architecture, self.accelerator)
        )
        return _safe_name(raw)

    def validate(self) -> None:
        if not self.engine or not self.version or not self.platform or not self.accelerator:
            raise AppError("runtime_manifest_invalid", "A runtime manifest is missing a required identity field.")
        if not self.assets:
            raise AppError("runtime_manifest_invalid", "A runtime manifest must contain at least one asset.")
        if not self.license:
            raise AppError("runtime_manifest_invalid", "A runtime manifest must identify its license.")
        if not self.executable or Path(self.executable).is_absolute():
            raise AppError("runtime_manifest_invalid", "The runtime executable must be a relative path.")
        if self.bundled_path:
            bundled = Path(self.bundled_path)
            if bundled.is_absolute() or bundled.drive or ".." in bundled.parts:
                raise AppError("runtime_manifest_invalid", "The bundled runtime path must stay relative to the package resources.")
        for asset in self.assets:
            if not asset.name or Path(asset.name).name != asset.name:
                raise AppError("runtime_manifest_invalid", f"Runtime asset name is invalid: {asset.name!r}.")
            if not _SHA256_RE.fullmatch(asset.sha256.lower()):
                raise AppError("runtime_manifest_invalid", f"Runtime asset hash is invalid: {asset.name!r}.")
            if asset.size_bytes is not None and asset.size_bytes < 0:
                raise AppError("runtime_manifest_invalid", f"Runtime asset size is invalid: {asset.name!r}.")


@dataclass(frozen=True)
class HardwareRuntimeInput:
    """Explicit hardware facts used for manifest selection."""

    platform: str
    architecture: str
    accelerators: tuple[str, ...]
    cuda_versions: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "HardwareRuntimeInput":
        raw_accelerators = payload.get("accelerators", payload.get("accelerator"))
        accelerators = _as_strings(raw_accelerators)
        raw_cuda = payload.get("cuda_versions", payload.get("cuda_version"))
        return cls(
            platform=str(payload.get("platform") or ""),
            architecture=str(payload.get("architecture") or ""),
            accelerators=tuple(accelerators),
            cuda_versions=tuple(_as_strings(raw_cuda)),
        )


@dataclass(frozen=True)
class RuntimeSelectionInput:
    """Optional runtime constraints kept separate from hardware facts."""

    engine: str = _DEFAULT_ENGINE
    version: str | None = None


@dataclass(frozen=True)
class SmokeCheckResult:
    ok: bool
    message: str = ""


Downloader = Callable[[RuntimeAsset, Path], None]
SmokeRunner = Callable[[Path], SmokeCheckResult | bool]


def sha256_file(path: str | os.PathLike[str], chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: str | os.PathLike[str], expected: str) -> str:
    actual = sha256_file(path)
    if actual.lower() != str(expected).lower():
        raise AppError(
            "runtime_hash_mismatch",
            f"SHA-256 mismatch for {Path(path).name}: expected {expected}, got {actual}.",
        )
    return actual


def extract_zip_safely(archive: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
    """Extract a ZIP only when every member stays below ``destination``."""

    target_root = Path(destination).resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        for member in members:
            relative = _safe_zip_member(member.filename)
            if relative is None:
                continue
            if _zip_member_is_symlink(member):
                raise AppError("runtime_archive_unsafe", f"ZIP member is a symlink: {member.filename!r}.")
            output = (target_root / Path(*relative.parts)).resolve()
            try:
                output.relative_to(target_root)
            except ValueError:
                raise AppError("runtime_archive_unsafe", f"ZIP member escapes the install root: {member.filename!r}.") from None
            if member.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, output.open("wb") as sink:
                shutil.copyfileobj(source, sink)


class LlamaCppRuntimeInstaller:
    """Install and activate one explicit manifest using injected side effects."""

    def __init__(self, root: str | os.PathLike[str], downloader: Downloader | None = None, smoke_runner: SmokeRunner | None = None):
        self.root = Path(root).expanduser().resolve()
        self.versions_dir = self.root / "versions"
        self.active_path = self.root / "active.json"
        self.downloader = downloader
        self.smoke_runner = smoke_runner

    def install(self, manifest: RuntimeManifest | Mapping[str, object]):
        manifest = _coerce_manifest(manifest)
        manifest.validate()
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".llama-", dir=self.root))
        final_path = self.version_path(manifest)
        previous = self.active_record()
        try:
            downloads = staging / ".downloads"
            downloads.mkdir()
            for asset in manifest.assets:
                archive_path = downloads / asset.name
                self._download(asset, archive_path)
                if not archive_path.is_file():
                    raise AppError("runtime_asset_missing", f"Downloader did not create {asset.name!r}.")
                verify_sha256(archive_path, asset.sha256)
                if asset.is_archive:
                    extract_zip_safely(archive_path, staging)
                else:
                    output = _safe_relative_path(staging, asset.name)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(archive_path, output)
            executable = _safe_relative_path(staging, manifest.executable)
            if not executable.is_file():
                raise AppError("runtime_executable_missing", f"Manifest executable was not found: {manifest.executable}.")
            self._smoke_check(executable)
            metadata = staging / "manifest.json"
            metadata.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")
            if final_path.exists():
                raise AppError("runtime_version_exists", f"Runtime version {manifest.version!r} is already installed.")
            os.replace(staging, final_path)
            staging = None
            record = {
                "version": manifest.version,
                "installation_id": manifest.installation_id,
                "path": str(final_path),
                "manifest": manifest.to_dict(),
                "previous": previous,
            }
            self._write_active(record)
            return record
        finally:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)

    def activate(self, version: str) -> dict[str, object]:
        candidate = self._find_record(version)
        if candidate is None:
            raise AppError("runtime_version_missing", f"Installed runtime version {version!r} was not found.")
        current = self.active_record()
        if current and current.get("installation_id") == candidate.get("installation_id"):
            return current
        candidate = dict(candidate)
        candidate["previous"] = current
        self._write_active(candidate)
        return candidate

    def restore_previous(self) -> dict[str, object]:
        current = self.active_record()
        previous = current.get("previous") if current else None
        if not isinstance(previous, Mapping) or not previous.get("path"):
            raise AppError("runtime_previous_missing", "No previous active llama.cpp runtime is available to restore.")
        if not Path(str(previous["path"])).is_dir():
            raise AppError("runtime_previous_missing", "The previous llama.cpp runtime directory is missing.")
        restored = dict(previous)
        restored["previous"] = current
        self._write_active(restored)
        return restored

    def active_record(self) -> dict[str, object] | None:
        try:
            payload = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def version_path(self, manifest: RuntimeManifest | Mapping[str, object] | str) -> Path:
        if isinstance(manifest, str):
            return self.versions_dir / _safe_name(manifest)
        value = _coerce_manifest(manifest)
        return self.versions_dir / value.installation_id

    def _download(self, asset: RuntimeAsset, destination: Path) -> None:
        if self.downloader is None:
            raise AppError("runtime_downloader_required", "A downloader must be injected for runtime installation.")
        try:
            self.downloader(asset, destination)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("runtime_download_failed", f"Could not acquire {asset.name}: {exc}") from exc

    def _smoke_check(self, executable: Path) -> None:
        if self.smoke_runner is None:
            raise AppError("runtime_smoke_runner_required", "A smoke runner must be injected for runtime installation.")
        try:
            result = self.smoke_runner(executable)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("runtime_smoke_failed", f"Runtime smoke check failed: {exc}") from exc
        ok = result.ok if isinstance(result, SmokeCheckResult) else bool(result)
        if not ok:
            message = result.message if isinstance(result, SmokeCheckResult) else "The runtime smoke check was unsuccessful."
            raise AppError("runtime_smoke_failed", message)

    def _find_record(self, version: str) -> dict[str, object] | None:
        active = self.active_record()
        if active and (active.get("version") == version or active.get("installation_id") == version):
            return active
        for path in self.versions_dir.glob("*/manifest.json"):
            try:
                manifest = RuntimeManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError):
                continue
            if manifest.version == version or manifest.installation_id == version:
                return {
                    "version": manifest.version,
                    "installation_id": manifest.installation_id,
                    "path": str(path.parent),
                    "manifest": manifest.to_dict(),
                }
        return None

    def _write_active(self, record: Mapping[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / f".active-{uuid.uuid4().hex}.tmp"
        temporary.write_text(json.dumps(dict(record), indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.active_path)


def select_compatible_manifest(
    manifests: Sequence[RuntimeManifest | Mapping[str, object]],
    hardware: HardwareRuntimeInput | Mapping[str, object],
    runtime: RuntimeSelectionInput | Mapping[str, object] | None = None,
) -> RuntimeManifest:
    """Select the first manifest matching explicit platform and accelerator facts."""

    hardware = hardware if isinstance(hardware, HardwareRuntimeInput) else HardwareRuntimeInput.from_dict(hardware)
    runtime = runtime or RuntimeSelectionInput()
    runtime = runtime if isinstance(runtime, RuntimeSelectionInput) else RuntimeSelectionInput(
        engine=str(runtime.get("engine") or _DEFAULT_ENGINE), version=_optional_string(runtime.get("version"))
    )
    candidates = [_coerce_manifest(item) for item in manifests]
    requested_accelerators = [_normalise_accelerator(value) for value in hardware.accelerators]
    if not requested_accelerators:
        raise AppError("runtime_accelerator_unsupported", "No supported accelerator was supplied.")
    for requested in requested_accelerators:
        for manifest in candidates:
            if manifest.engine != runtime.engine or (runtime.version and manifest.version != runtime.version):
                continue
            if _normalise_platform(manifest.platform) != _normalise_platform(hardware.platform):
                continue
            if _normalise_architecture(manifest.architecture) != _normalise_architecture(hardware.architecture):
                continue
            if _accelerator_matches(manifest.accelerator, requested, hardware.cuda_versions):
                manifest.validate()
                return manifest
    raise AppError(
        "runtime_accelerator_unsupported",
        f"No {runtime.engine} runtime matches {', '.join(hardware.accelerators)} on {hardware.platform}/{hardware.architecture}.",
    )


def _coerce_manifest(value: RuntimeManifest | Mapping[str, object]) -> RuntimeManifest:
    if isinstance(value, RuntimeManifest):
        return value
    if isinstance(value, Mapping):
        return RuntimeManifest.from_dict(value)
    raise AppError("runtime_manifest_invalid", "Expected a runtime manifest object.")


def _optional_string(value: object) -> str | None:
    value = str(value).strip() if value is not None else ""
    return value or None


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_bool(value: object) -> bool | None:
    return None if value is None else bool(value)


def _as_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    return []


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "runtime"


def _safe_relative_path(root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or relative.drive:
        raise AppError("runtime_archive_unsafe", f"Runtime path must be relative: {value!r}.")
    output = (root / relative).resolve()
    try:
        output.relative_to(root.resolve())
    except ValueError:
        raise AppError("runtime_archive_unsafe", f"Runtime path escapes the install root: {value!r}.") from None
    return output


def _safe_zip_member(name: str) -> PurePosixPath | None:
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", normalized):
        raise AppError("runtime_archive_unsafe", f"ZIP member has an absolute path: {name!r}.")
    parts = path.parts
    if not parts or all(part in ("", ".") for part in parts):
        return None
    if any(part == ".." for part in parts):
        raise AppError("runtime_archive_unsafe", f"ZIP member traverses outside the install root: {name!r}.")
    return PurePosixPath(*[part for part in parts if part not in ("", ".")])


def _zip_member_is_symlink(member: zipfile.ZipInfo) -> bool:
    return (member.external_attr >> 16) & 0o170000 == 0o120000


def _normalise_platform(value: str) -> str:
    value = value.lower().strip()
    return {"win32": "windows", "win": "windows"}.get(value, value)


def _normalise_architecture(value: str) -> str:
    return value.lower().replace("amd64", "x86_64").replace("x64", "x86_64")


def _normalise_accelerator(value: str) -> str:
    return value.lower().replace(" ", "").replace("-", "")


def _accelerator_matches(manifest: str, requested: str, cuda_versions: Sequence[str]) -> bool:
    manifest = _normalise_accelerator(manifest)
    requested = _normalise_accelerator(requested)
    if manifest == requested:
        return True
    if requested == "cuda" and manifest.startswith("cuda"):
        suffix = manifest.removeprefix("cuda")
        return not suffix or not cuda_versions or suffix in {_normalise_accelerator(item).removeprefix("cuda") for item in cuda_versions}
    return False
