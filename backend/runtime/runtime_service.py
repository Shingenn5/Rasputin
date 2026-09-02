"""Application-level orchestration for the versioned llama.cpp runtime."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
from typing import Any, Callable, Mapping, Sequence
import urllib.error
import urllib.request

from backend.core.datadir import data_dir
from backend.core.response import AppError
from .llamacpp_installer import (
    HardwareRuntimeInput,
    LlamaCppRuntimeInstaller,
    RuntimeManifest,
    RuntimeAsset,
    RuntimeSelectionInput,
    SmokeCheckResult,
    select_compatible_manifest,
)


_DOWNLOAD_TIMEOUT_SECONDS = 120
_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
_SMOKE_TIMEOUT_SECONDS = 15
_RUNTIME_INSTALL_LOCK = threading.RLock()
_CUDA_VERSION_RE = re.compile(r"CUDA(?: UMD)? Version:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def _default_http_downloader(asset: RuntimeAsset, destination: str | Path) -> None:
    """Download one manifest asset to ``destination`` without partial files."""

    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = urllib.request.Request(asset.url, headers=headers)
    temporary: Path | None = None
    try:
        with urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                for chunk in iter(lambda: response.read(_DOWNLOAD_CHUNK_SIZE), b""):
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
    except urllib.error.HTTPError as exc:
        raise AppError("runtime_download_failed", f"Could not acquire {asset.name}: HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AppError(
            "runtime_download_failed",
            f"Could not acquire {asset.name}: {type(exc).__name__}.",
        ) from exc
    except Exception as exc:
        raise AppError(
            "runtime_download_failed",
            f"Could not acquire {asset.name}: {type(exc).__name__}.",
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _default_smoke_runner(executable: Path) -> SmokeCheckResult:
    """Check the executable version without starting a llama-server process."""

    options: dict[str, Any] = {
        "capture_output": True,
        "check": False,
        "text": True,
        "timeout": _SMOKE_TIMEOUT_SECONDS,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run([str(executable), "--version"], **options)
    except subprocess.TimeoutExpired:
        return SmokeCheckResult(False, f"Runtime smoke check timed out after {_SMOKE_TIMEOUT_SECONDS} seconds.")
    except OSError as exc:
        return SmokeCheckResult(False, f"Runtime smoke check could not start: {type(exc).__name__}.")
    if result.returncode == 0:
        return SmokeCheckResult(True, "Runtime executable responded to --version.")
    return SmokeCheckResult(False, f"Runtime executable exited with code {result.returncode}.")


def detect_local_runtime_hardware() -> HardwareRuntimeInput:
    """Detect enough local hardware detail to choose one pinned runtime safely."""

    accelerators = ["cpu"]
    cuda_versions: list[str] = []
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        options: dict[str, Any] = {
            "capture_output": True,
            "check": False,
            "text": True,
            "timeout": 10,
        }
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            inventory = subprocess.run(
                [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
                **options,
            )
            details = subprocess.run([nvidia_smi], **options)
        except (OSError, subprocess.SubprocessError):
            inventory = details = None
        if inventory and inventory.returncode == 0 and inventory.stdout.strip() and details and details.returncode == 0:
            match = _CUDA_VERSION_RE.search(f"{details.stdout}\n{details.stderr}")
            if match:
                accelerators.insert(0, "cuda")
                cuda_versions.append(match.group(1))
    return HardwareRuntimeInput(
        platform=platform.system(),
        architecture=platform.machine(),
        accelerators=tuple(accelerators),
        cuda_versions=tuple(cuda_versions),
    )


class LlamaCppRuntimeService:
    """Manage pinned llama.cpp versions without knowing the upstream source."""

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        manifests: Sequence[RuntimeManifest | Mapping[str, Any]] | None = None,
        manifest_path: str | Path | None = None,
        bundled_root: str | Path | None = None,
        downloader: Callable[..., Any] | None = None,
        smoke_runner: Callable[..., SmokeCheckResult | bool] | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else data_dir() / "runtimes" / "llama.cpp"
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = Path(manifest_path).expanduser().resolve() if manifest_path is not None else None
        configured_bundle = bundled_root or os.environ.get("RASPUTIN_LLAMA_BUNDLED_DIR")
        if configured_bundle:
            self.bundled_root = Path(configured_bundle).expanduser().resolve()
        elif self.manifest_path is not None and (self.manifest_path.parent / "bundled").is_dir():
            self.bundled_root = self.manifest_path.parent.resolve()
        else:
            self.bundled_root = None
        self._manifests = tuple(manifests or ())
        self.downloader = downloader
        self.smoke_runner = smoke_runner
        self.installer = LlamaCppRuntimeInstaller(
            self.root,
            downloader=downloader,
            smoke_runner=smoke_runner,
        )

    def _manifest_list(self) -> list[RuntimeManifest]:
        values: list[RuntimeManifest | Mapping[str, Any]] = list(self._manifests)
        if self.manifest_path is not None:
            try:
                raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                raw = []
            except (OSError, ValueError) as exc:
                raise AppError("runtime_manifest_invalid", f"Could not read the runtime manifest: {exc}") from exc
            if isinstance(raw, Mapping):
                raw = raw.get("runtimes", raw.get("manifests", [raw]))
            if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
                values.extend(item for item in raw if isinstance(item, (Mapping, RuntimeManifest)))
        result = [item if isinstance(item, RuntimeManifest) else RuntimeManifest.from_dict(item) for item in values]
        for item in result:
            item.validate()
        return result

    def _bundled_records(self) -> list[dict[str, Any]]:
        if self.bundled_root is None:
            return []
        records: list[dict[str, Any]] = []
        for manifest in self._manifest_list():
            if not manifest.bundled_path:
                continue
            candidate = (self.bundled_root / manifest.bundled_path).resolve()
            try:
                candidate.relative_to(self.bundled_root)
            except ValueError:
                continue
            executable = (candidate / manifest.executable).resolve()
            try:
                executable.relative_to(candidate)
            except ValueError:
                continue
            if not executable.is_file():
                continue
            records.append({
                "version": manifest.version,
                "installation_id": manifest.installation_id,
                "path": str(candidate),
                "manifest": manifest.to_dict(),
                "bundled": True,
                "engine_path": str(executable),
            })
        return records

    def bundled_engine_path(self, accelerator: str | None = None, *, required: bool = False) -> str:
        records = self._bundled_records()
        requested = str(accelerator or os.environ.get("RASPUTIN_LLAMA_ACCELERATOR") or "").strip().lower().replace("-", "")
        if requested:
            matching = [
                item for item in records
                if str((item.get("manifest") or {}).get("accelerator") or "").lower().replace("-", "") == requested
                or (requested == "cuda" and str((item.get("manifest") or {}).get("accelerator") or "").lower().startswith("cuda"))
            ]
            if matching:
                records = matching
        elif shutil.which("nvidia-smi"):
            cuda = [item for item in records if str((item.get("manifest") or {}).get("accelerator") or "").lower().startswith("cuda")]
            if cuda:
                records = sorted(cuda, key=lambda item: str((item.get("manifest") or {}).get("version") or ""), reverse=True)
        if not records:
            if required:
                raise AppError("runtime_unavailable", "The packaged llama.cpp runtime is missing.")
            return ""
        return str(records[0]["engine_path"])

    def status(self) -> dict[str, Any]:
        active = self.installer.active_record()
        installed: list[dict[str, Any]] = []
        for manifest_path in self.installer.versions_dir.glob("*/manifest.json"):
            try:
                manifest = RuntimeManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
                installed.append({
                    "version": manifest.version,
                    "installationId": manifest.installation_id,
                    "path": str(manifest_path.parent),
                    "active": bool(active and active.get("installation_id") == manifest.installation_id),
                })
            except (OSError, ValueError, TypeError):
                continue
        manifest_path = self.manifest_path
        manifest_available = bool(manifest_path and manifest_path.is_file())
        bundled = self._bundled_records()
        installed.extend({
            "version": item["version"],
            "installationId": item["installation_id"],
            "path": item["path"],
            "active": False,
            "bundled": True,
        } for item in bundled)
        if manifest_path is not None and not manifest_available:
            state = "manifest_missing"
        elif active:
            try:
                self.active_engine_path()
            except AppError:
                state = "repair_required"
            else:
                state = "ready"
        elif bundled:
            state = "ready"
        else:
            state = "install_required" if manifest_available else "manifest_missing"
        return {
            "engine": "llama.cpp",
            "root": str(self.root),
            "active": active,
            "installed": sorted(installed, key=lambda item: item["version"]),
            "bundled": bool(bundled),
            "manifestCount": len(self._manifest_list()),
            "manifestPath": str(manifest_path) if manifest_path else "",
            "manifestAvailable": manifest_available,
            "state": state,
            "repairRequired": state == "repair_required",
            "enginePath": self.active_engine_path(required=False),
            "bundledEnginePath": self.bundled_engine_path(required=False),
        }

    def select(
        self,
        hardware: HardwareRuntimeInput | Mapping[str, Any],
        runtime: RuntimeSelectionInput | Mapping[str, Any] | None = None,
    ) -> RuntimeManifest:
        manifests = self._manifest_list()
        if not manifests:
            raise AppError("runtime_manifest_missing", "No pinned llama.cpp runtime manifest is configured.")
        return select_compatible_manifest(manifests, hardware, runtime)

    def install(
        self,
        selection: RuntimeManifest | Mapping[str, Any],
        *,
        downloader: Callable[..., Any] | None = None,
        smoke_runner: Callable[..., SmokeCheckResult | bool] | None = None,
    ) -> dict[str, Any]:
        manifest = selection if isinstance(selection, RuntimeManifest) else RuntimeManifest.from_dict(selection)
        manifest.validate()
        if manifest.bundled_path:
            bundled = next((item for item in self._bundled_records() if item["installation_id"] == manifest.installation_id), None)
            if bundled:
                self.installer._write_active(bundled)
                return dict(bundled)
            raise AppError("runtime_executable_missing", f"The bundled llama.cpp runtime is missing: {manifest.installation_id}")
        installer = LlamaCppRuntimeInstaller(
            self.root,
            downloader=downloader if downloader is not None else (self.downloader or _default_http_downloader),
            smoke_runner=smoke_runner if smoke_runner is not None else (self.smoke_runner or _default_smoke_runner),
        )
        record = installer.install(selection)
        self.installer = installer
        return record

    def ensure_local_runtime(self) -> dict[str, Any]:
        """Install and activate only the runtime selected for this machine."""

        with _RUNTIME_INSTALL_LOCK:
            selection = self.select(detect_local_runtime_hardware())
            active = self.installer.active_record()
            if (
                active
                and active.get("installation_id") == selection.installation_id
                and not active.get("bundled")
            ):
                engine = self.active_engine_path(required=False)
                if engine:
                    return {**active, "engine_path": engine, "downloaded": False}

            installed_path = self.installer.version_path(selection)
            installed_manifest = installed_path / "manifest.json"
            installed_engine = installed_path / selection.executable
            if installed_manifest.is_file() and installed_engine.is_file():
                record = self.installer.activate(selection.installation_id)
                return {**record, "engine_path": str(installed_engine.resolve()), "downloaded": False}

            record = self.install(selection)
            return {
                **record,
                "engine_path": self.active_engine_path(),
                "downloaded": True,
            }

    def activate(self, version: str) -> dict[str, Any]:
        return self.installer.activate(version)

    def rollback(self) -> dict[str, Any]:
        return self.installer.restore_previous()

    def active_engine_path(self, *, required: bool = True, accelerator: str | None = None) -> str:
        active = self.installer.active_record()
        if active and active.get("path"):
            manifest = active.get("manifest") if isinstance(active.get("manifest"), Mapping) else {}
            executable = str(manifest.get("executable") or "llama-server.exe")
            path = (Path(str(active["path"])) / executable).resolve()
            if path.is_file():
                return str(path)
            if not active.get("bundled"):
                if required:
                    raise AppError("runtime_executable_missing", f"The active llama.cpp executable is missing: {path}")
                return ""
        bundled = self.bundled_engine_path(accelerator, required=required)
        return bundled

    def verify_active(self, runner: Callable[[Path], SmokeCheckResult | bool] | None = None) -> dict[str, Any]:
        path = Path(self.active_engine_path())
        checker = runner if runner is not None else (self.smoke_runner or _default_smoke_runner)
        result = checker(path)
        ok = result.ok if isinstance(result, SmokeCheckResult) else bool(result)
        return {"ok": ok, "path": str(path), "message": result.message if isinstance(result, SmokeCheckResult) else ""}


__all__ = ["LlamaCppRuntimeService", "detect_local_runtime_hardware"]
