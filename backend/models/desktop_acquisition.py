"""Desktop-only exact-file model acquisition.

The older :mod:`backend.models.acquisition` module owns the legacy snapshot
download path.  This adapter keeps the desktop path separate: the catalog
selects one exact GGUF variant, :class:`DownloadManager` owns durable state,
and this module supplies the Hugging Face transfer boundary plus an
InstalledArtifact-shaped completion response.
"""

from __future__ import annotations

from concurrent.futures import Executor, ThreadPoolExecutor
import os
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from backend.core.datadir import data_dir
from backend.models.download_manager import (
    DownloadFile,
    DownloadJob,
    DownloadManager,
    DownloadVariant,
    JsonJobRepository,
    TransferError,
)
from backend.models.variant_resolver import resolve_model_variants_with_issues
from backend.models.artifacts import ArtifactStore


Transfer = Callable[..., Any]

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rasputin-model-download")


def _slug(value: str, fallback: str = "model") -> str:
    text = "".join(char if char.isalnum() or char in "._-" else "-" for char in str(value or ""))
    return text.strip(".-")[:80] or fallback


def _mapping_value(value: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in value and value[key] is not None:
            return value[key]
    return default


class DesktopAcquisitionService:
    """Durable desktop acquisition facade used by the model API.

    A new service object may be constructed for each API call.  Jobs are
    persisted in the app data directory, while the manager's worker thread
    continues to own the process that started a transfer.  Action calls from
    another service instance are therefore safe: the running worker observes
    pause/cancel state through the same JSON repository.
    """

    def __init__(
        self,
        *,
        data_root: str | Path | None = None,
        model_library: str | Path | None = None,
        transfer: Transfer | None = None,
        executor: Executor | None = None,
    ) -> None:
        root = Path(data_root) if data_root is not None else data_dir()
        root.mkdir(parents=True, exist_ok=True)
        library = Path(model_library) if model_library is not None else root / "models"
        library.mkdir(parents=True, exist_ok=True)
        self.data_root = root
        self.model_library = library
        self.repository = JsonJobRepository(root / "desktop-download-jobs.json")
        self.artifacts = ArtifactStore(root)
        self.executor = executor or _EXECUTOR
        self._transfer_callback = transfer
        self.manager = DownloadManager(repository=self.repository, transfer=self._transfer)
        self.artifacts.rehydrate_registry()

    @staticmethod
    def resolve_variants(model_info: Mapping[str, Any] | None, siblings: Any = None) -> dict[str, Any]:
        """Return JSON-friendly variants and rejected sibling diagnostics."""

        resolution = resolve_model_variants_with_issues(model_info, siblings)
        return {
            "variants": [variant.as_dict() for variant in resolution.variants],
            "issues": [
                {
                    "kind": issue.kind,
                    "files": list(issue.files),
                    "reason": issue.reason,
                    "nextAction": issue.next_action,
                }
                for issue in resolution.issues
            ],
        }

    def start_variant_download(
        self,
        variant_or_model_id: Mapping[str, Any] | str,
        variant: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and asynchronously run one exact variant job.

        ``variant`` is accepted as a compatibility second argument because the
        first API seam passes ``modelId`` separately.  The repository identity
        in the exact variant remains authoritative.
        """

        raw = variant if variant is not None else variant_or_model_id
        if not isinstance(raw, Mapping):
            raise ValueError("an exact model variant is required")
        normalized = self._variant_to_download(raw)
        for existing in self.manager.list_jobs():
            if (
                existing.repository == normalized.repository
                and existing.revision == normalized.revision
                and existing.destination == str(normalized.destination)
                and existing.state not in {"completed", "cancelled"}
            ):
                return self._job_payload(existing)

        job = self.manager.create_job(normalized)
        self._annotate_job(job, raw)
        self.repository.save(job)
        self.executor.submit(self.manager.run, job.id)
        return self._job_payload(job)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._job_payload(self.manager.get_job(job_id))

    def list_jobs(self) -> list[dict[str, Any]]:
        return [self._job_payload(job) for job in self.manager.list_jobs()]

    def pause(self, job_id: str) -> dict[str, Any]:
        return self._job_payload(self.manager.pause(job_id))

    def resume(self, job_id: str) -> dict[str, Any]:
        job = self.manager.resume(job_id)
        return self._job_payload(job)

    def cancel(self, job_id: str) -> dict[str, Any]:
        return self._job_payload(self.manager.cancel(job_id))

    def retry(self, job_id: str) -> dict[str, Any]:
        job = self.manager.retry(job_id)
        return self._job_payload(job)

    def recover(self) -> list[dict[str, Any]]:
        self.artifacts.rehydrate_registry()
        return [self._job_payload(job) for job in self.manager.recover()]

    def _variant_to_download(self, raw: Mapping[str, Any]) -> DownloadVariant:
        repository = str(_mapping_value(raw, "repository", "repo_id", "repo", default="")).strip()
        revision = str(_mapping_value(raw, "revision", "commit", default="")).strip()
        if not repository or not revision:
            raise ValueError("variant repository and revision are required")

        file_sizes = _mapping_value(raw, "fileSizes", "file_sizes", "expected_sizes", default={}) or {}
        file_hashes = _mapping_value(raw, "fileHashes", "file_hashes", "expected_hashes", default={}) or {}
        model_files = set(_mapping_value(raw, "modelFiles", "model_files", default=[]) or [])
        mmproj_files = set(_mapping_value(raw, "mmprojFiles", "mmproj_files", default=[]) or [])
        exact_files = _mapping_value(raw, "files", "exact_files", default=[]) or []
        files: list[DownloadFile] = []
        for item in exact_files:
            if isinstance(item, Mapping):
                path = str(_mapping_value(item, "path", "filename", "name", default=""))
                size = _mapping_value(item, "expected_size", "size", default=file_sizes.get(path))
                digest = _mapping_value(item, "sha256", "hash", default=file_hashes.get(path))
            else:
                path = str(item)
                size = file_sizes.get(path)
                digest = file_hashes.get(path)
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise ValueError(f"exact file size is required for {path or 'unnamed file'}")
            files.append(DownloadFile(path=path, expected_size=size, sha256=digest))
        if not files:
            raise ValueError("variant contains no exact files")

        variant_id = str(raw.get("id") or f"{repository}:{revision}:{files[0].path}")
        destination_value = raw.get("destination")
        destination = (
            Path(str(destination_value)).expanduser()
            if destination_value
            else self.model_library / _slug(repository.replace("/", "-")) / _slug(variant_id)
        )
        destination = destination.resolve()
        try:
            destination.relative_to(self.model_library.resolve())
        except ValueError as exc:
            raise ValueError("exact download destination must be under the model library") from exc
        return DownloadVariant(repository=repository, revision=revision, files=tuple(files), destination=destination)

    def _annotate_job(self, job: DownloadJob, raw: Mapping[str, Any]) -> None:
        model_files = set(_mapping_value(raw, "modelFiles", "model_files", default=[]) or [])
        mmproj_files = set(_mapping_value(raw, "mmprojFiles", "mmproj_files", default=[]) or [])
        for record in job.files:
            path = record.get("path")
            record["role"] = "mmproj" if path in mmproj_files else "model" if path in model_files else "artifact"
        job.variant_id = str(raw.get("id") or "")
        job.quantization = str(raw.get("quantization") or "")
        self.artifacts.save_job_metadata(job.id, {"variant_id": job.variant_id, "quantization": job.quantization})

    def _job_payload(self, job: DownloadJob) -> dict[str, Any]:
        payload = job.to_dict()
        if job.state == "completed":
            artifact = self.artifacts.install(job)
            self._register_artifact(artifact)
            destination = Path(artifact["destination"])
            files = [
                {
                    "path": record.get("path"),
                    "localPath": str(destination / record.get("path", "")),
                    "size": record.get("expected_size"),
                    "sha256": record.get("sha256"),
                    "role": record.get("role", "artifact"),
                }
                for record in job.files
            ]
            model_files = [item for item in files if item["role"] == "model"]
            mmproj_files = [item for item in files if item["role"] == "mmproj"]
            payload["artifact"] = {**artifact, "artifactId": artifact["artifact_id"],
                                    "jobId": artifact["job_id"], "variantId": artifact["variant_id"],
                                    "modelFiles": model_files, "mmprojFiles": mmproj_files,
                                    "mainModelPath": artifact["main_model_path"]}
        return payload

    @staticmethod
    def _register_artifact(artifact: Mapping[str, Any]) -> None:
        from backend.models import registry
        registry.register_artifact(dict(artifact))

    def _transfer(self, file: DownloadFile, target: Path, offset: int, control: Any, progress: Any) -> None:
        if self._transfer_callback is not None:
            return self._transfer_callback(file, target, offset, control, progress)
        job = self.manager.get_job(control.job_id)
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
        url = f"https://huggingface.co/{quote(job.repository, safe='/')}/resolve/{quote(job.revision, safe='')}/{quote(file.path, safe='/')}"
        headers = {"Accept": "application/octet-stream"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = Request(url, headers=headers)
        try:
            response = urlopen(request, timeout=60)
        except HTTPError as exc:
            retryable = exc.code >= 500 or exc.code == 429
            code = "hf_auth_required" if exc.code in {401, 403} else f"hf_http_{exc.code}"
            raise TransferError(f"model download failed for {file.path} ({exc.code})", transient=retryable, code=code) from exc
        except URLError as exc:
            raise TransferError(f"model download network error for {file.path}", transient=True, code="hf_network_error") from exc

        response_offset = offset if getattr(response, "status", 200) == 206 else 0
        mode = "ab" if response_offset else "wb"
        current = response_offset
        target.parent.mkdir(parents=True, exist_ok=True)
        with response, target.open(mode) as handle:
            while True:
                control.checkpoint()
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                current += len(chunk)
                progress(current)
            handle.flush()
            os.fsync(handle.fileno())


__all__ = ["DesktopAcquisitionService"]
