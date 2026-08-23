"""Durable, exact-file download jobs for the desktop model library.

This module deliberately does not know about Hugging Face, Docker, or the
existing snapshot acquisition API.  A caller supplies an exact variant and a
transfer callback.  The manager owns the state machine, resumable ``.part``
files, integrity checks, and atomic publication of a completed artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol


STATES = (
    "queued",
    "resolving",
    "downloading",
    "paused",
    "verifying",
    "installing",
    "completed",
    "failed",
    "cancelled",
)

TERMINAL_STATES = {"completed", "cancelled"}

VALID_TRANSITIONS = {
    "queued": {"resolving", "cancelled"},
    "resolving": {"downloading", "failed", "cancelled"},
    "downloading": {"paused", "verifying", "failed", "cancelled"},
    "paused": {"downloading", "cancelled"},
    "verifying": {"installing", "failed", "cancelled"},
    "installing": {"completed", "failed"},
    "completed": set(),
    "failed": {"queued", "cancelled"},
    "cancelled": set(),
}


class DownloadManagerError(Exception):
    """Base class for errors raised by the download manager."""


class InvalidTransition(DownloadManagerError):
    """Raised when a requested state transition is not allowed."""


class PreflightError(DownloadManagerError):
    """Raised when a job cannot safely begin."""


class TransferError(DownloadManagerError):
    """An error from the injected transfer implementation."""

    def __init__(self, message: str, *, transient: bool = True, code: str = "transfer_error"):
        super().__init__(message)
        self.transient = transient
        self.code = code


class PauseRequested(DownloadManagerError):
    """Internal cooperative signal used by :class:`DownloadControl`."""


class CancellationRequested(DownloadManagerError):
    """Internal cooperative signal used by :class:`DownloadControl`."""


@dataclass(frozen=True)
class DownloadFile:
    """One exact remote file in a variant."""

    path: str
    expected_size: int
    sha256: str | None = None

    def __post_init__(self) -> None:
        normalized = _normalize_relative_path(self.path)
        if normalized != self.path:
            object.__setattr__(self, "path", normalized)
        if isinstance(self.expected_size, bool) or not isinstance(self.expected_size, int):
            raise ValueError("expected_size must be a non-negative integer")
        if self.expected_size < 0:
            raise ValueError("expected_size must be a non-negative integer")
        if self.sha256 is not None:
            digest = self.sha256.lower()
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("sha256 must be a 64-character hexadecimal digest")
            object.__setattr__(self, "sha256", digest)


@dataclass(frozen=True)
class DownloadVariant:
    """The immutable input needed to acquire one exact artifact variant."""

    repository: str
    revision: str
    files: tuple[DownloadFile, ...]
    destination: Path

    def __post_init__(self) -> None:
        if not self.repository or not self.revision:
            raise ValueError("repository and revision are required")
        if not self.files:
            raise ValueError("at least one exact file is required")
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("exact files must not contain duplicates")
        object.__setattr__(self, "destination", Path(self.destination))

    @property
    def total_bytes(self) -> int:
        return sum(item.expected_size for item in self.files)

    @classmethod
    def from_input(cls, value: "DownloadVariant | Mapping[str, Any]") -> "DownloadVariant":
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("variant must be DownloadVariant or a mapping")
        repository = value.get("repository", value.get("repo_id", value.get("repo")))
        revision = value.get("revision", value.get("commit"))
        destination = value.get("destination")
        raw_files = value.get("files", value.get("exact_files"))
        expected_sizes = value.get("expected_sizes", {}) or {}
        expected_hashes = value.get("expected_hashes", {}) or {}
        if raw_files is None:
            raise ValueError("variant.files is required")
        files: list[DownloadFile] = []
        for raw in raw_files:
            if isinstance(raw, DownloadFile):
                files.append(raw)
                continue
            if isinstance(raw, str):
                path = raw
                size = expected_sizes[path]
                digest = expected_hashes.get(path)
            else:
                path = raw.get("path", raw.get("filename", raw.get("name")))
                size = raw.get("expected_size", raw.get("size", expected_sizes.get(path)))
                digest = raw.get("sha256", raw.get("hash", expected_hashes.get(path)))
            files.append(DownloadFile(path=path, expected_size=size, sha256=digest))
        return cls(repository=repository, revision=revision, files=tuple(files), destination=destination)


@dataclass
class DownloadJob:
    id: str
    repository: str
    revision: str
    destination: str
    files: list[dict[str, Any]]
    state: str = "queued"
    downloaded_bytes: int = 0
    total_bytes: int = 0
    retry_count: int = 0
    retryable: bool = False
    error: str | None = None
    error_code: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    staging_dir: str = ""

    @property
    def progress(self) -> float:
        if self.total_bytes <= 0:
            return 100.0 if self.state == "completed" else 0.0
        return round(min(100.0, max(0.0, self.downloaded_bytes / self.total_bytes * 100)), 2)

    @property
    def can_retry(self) -> bool:
        return self.state == "failed" and self.retryable

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["progress"] = self.progress
        value["can_retry"] = self.can_retry
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DownloadJob":
        known = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value[key] for key in known if key in value})


class JobRepository(Protocol):
    def get(self, job_id: str) -> DownloadJob | None: ...
    def save(self, job: DownloadJob) -> None: ...
    def list(self) -> list[DownloadJob]: ...


class InMemoryJobRepository:
    """Small repository useful for callers that already own persistence."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def get(self, job_id: str) -> DownloadJob | None:
        with self._lock:
            value = self._jobs.get(job_id)
            return DownloadJob.from_dict(value) if value else None

    def save(self, job: DownloadJob) -> None:
        with self._lock:
            self._jobs[job.id] = job.to_dict()

    def list(self) -> list[DownloadJob]:
        with self._lock:
            return [DownloadJob.from_dict(value) for value in self._jobs.values()]


class JsonJobRepository:
    """Self-contained atomic JSON persistence; it has no runtime-store dependency."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}

    def get(self, job_id: str) -> DownloadJob | None:
        with self._lock:
            value = self._read().get(job_id)
            return DownloadJob.from_dict(value) if value else None

    def save(self, job: DownloadJob) -> None:
        with self._lock:
            values = self._read()
            values[job.id] = job.to_dict()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
            try:
                with temporary.open("w", encoding="utf-8") as handle:
                    json.dump(values, handle, sort_keys=True)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary.exists():
                    temporary.unlink()

    def list(self) -> list[DownloadJob]:
        with self._lock:
            return [DownloadJob.from_dict(value) for value in self._read().values()]


@dataclass
class StorageCallbacks:
    """Replaceable filesystem operations for deterministic integration tests."""

    check_space: Callable[[Path, int], bool] | None = None
    hash_file: Callable[[Path], str] | None = None
    atomic_replace: Callable[[Path, Path], None] = os.replace
    remove_tree: Callable[[Path], None] = shutil.rmtree


class DownloadControl:
    def __init__(self, manager: "DownloadManager", job_id: str) -> None:
        self._manager = manager
        self.job_id = job_id

    @property
    def paused(self) -> bool:
        job = self._manager.get_job(self.job_id)
        return bool(job and job.state == "paused")

    @property
    def cancelled(self) -> bool:
        job = self._manager.get_job(self.job_id)
        return bool(job and job.state == "cancelled")

    def checkpoint(self) -> None:
        if self.cancelled:
            raise CancellationRequested()
        if self.paused:
            raise PauseRequested()


TransferCallback = Callable[
    [DownloadFile, Path, int, DownloadControl, Callable[[int], None]],
    Iterable[bytes] | bytes | None,
]


class DownloadManager:
    """Coordinates durable exact-file jobs without owning a network client."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        *,
        transfer: TransferCallback | None = None,
        storage: StorageCallbacks | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.repository = repository or InMemoryJobRepository()
        self.transfer = transfer or self._missing_transfer
        self.storage = storage or StorageCallbacks()
        self.clock = clock
        self._lock = threading.RLock()

    def create_job(self, variant: DownloadVariant | Mapping[str, Any], *, job_id: str | None = None) -> DownloadJob:
        normalized = DownloadVariant.from_input(variant)
        identifier = job_id or uuid.uuid4().hex
        staging = self._staging_path(normalized.destination, identifier)
        job = DownloadJob(
            id=identifier,
            repository=normalized.repository,
            revision=normalized.revision,
            destination=str(normalized.destination),
            files=[
                {"path": item.path, "expected_size": item.expected_size, "sha256": item.sha256, "status": "pending"}
                for item in normalized.files
            ],
            total_bytes=normalized.total_bytes,
            staging_dir=str(staging),
            created_at=self.clock(),
            updated_at=self.clock(),
        )
        if self.repository.get(identifier):
            raise ValueError(f"download job already exists: {identifier}")
        self.repository.save(job)
        return job

    def get_job(self, job_id: str) -> DownloadJob:
        job = self.repository.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def list_jobs(self) -> list[DownloadJob]:
        return self.repository.list()

    def start(self, job_id: str) -> DownloadJob:
        job = self.get_job(job_id)
        if job.state != "queued":
            raise InvalidTransition(f"cannot start job in {job.state} state")
        return self.run(job_id)

    def run(self, job_id: str) -> DownloadJob:
        """Run one job synchronously; callers may place this in their worker pool."""
        with self._lock:
            job = self.get_job(job_id)
            if job.state not in {"queued", "downloading"}:
                raise InvalidTransition(f"cannot run job in {job.state} state")
            if job.state == "queued":
                self._transition(job, "resolving")
                try:
                    self._preflight(job)
                except PreflightError as exc:
                    self._fail(job, str(exc), code="preflight_rejected", retryable=False)
                    return job
                self._transition(job, "downloading")
            control = DownloadControl(self, job.id)
            try:
                for file_record in job.files:
                    control.checkpoint()
                    self._download_file(job, file_record, control)
                self._transition(job, "verifying")
                self._verify_all(job)
                self._transition(job, "installing")
                self._finalize(job)
                self._transition(job, "completed")
                job.retryable = False
                job.error = None
                job.error_code = None
                self._save(job)
            except PauseRequested:
                if job.state != "paused":
                    self._transition(job, "paused")
                self._update_progress(job)
                self._save(job)
            except CancellationRequested:
                if job.state != "cancelled":
                    self._transition(job, "cancelled")
                self._cleanup_staging(job)
                self._save(job)
            except TransferError as exc:
                self._fail(job, str(exc), code=exc.code, retryable=exc.transient)
            except (OSError, ValueError, DownloadManagerError) as exc:
                self._fail(job, str(exc), code="download_failed", retryable=False)
            return job

    def pause(self, job_id: str) -> DownloadJob:
        job = self.get_job(job_id)
        self._transition(job, "paused")
        self._save(job)
        return job

    def resume(self, job_id: str) -> DownloadJob:
        job = self.get_job(job_id)
        self._transition(job, "downloading")
        self._save(job)
        return self.run(job_id)

    def cancel(self, job_id: str) -> DownloadJob:
        job = self.get_job(job_id)
        self._transition(job, "cancelled")
        self._cleanup_staging(job)
        self._save(job)
        return job

    def retry(self, job_id: str) -> DownloadJob:
        job = self.get_job(job_id)
        if not job.can_retry:
            raise InvalidTransition("job is not eligible for retry")
        self._transition(job, "queued")
        job.retry_count += 1
        job.error = None
        job.error_code = None
        self._save(job)
        return self.run(job_id)

    def recover(self) -> list[DownloadJob]:
        """Rehydrate jobs after restart while retaining safe staged bytes."""
        recovered: list[DownloadJob] = []
        for job in self.repository.list():
            destination = Path(job.destination)
            marker = destination / ".rasputin-complete.json"
            if marker.exists() and self._marker_matches(marker, job):
                if job.state != "completed":
                    job.state = "completed"
                    job.downloaded_bytes = job.total_bytes
                    for record in job.files:
                        record["status"] = "verified"
                    self._save(job)
                recovered.append(job)
                continue
            if job.state in {"resolving", "downloading", "verifying", "installing"}:
                self._update_progress(job)
                job.state = "queued"
                job.error = "recovered after process restart"
                job.error_code = "restart_recovery"
                job.retryable = True
                self._save(job)
            recovered.append(job)
        return recovered

    def transition(self, job_id: str, state: str) -> DownloadJob:
        """Expose the explicit transition table for orchestration/UI adapters."""
        if state not in STATES:
            raise ValueError(f"unknown download state: {state}")
        job = self.get_job(job_id)
        self._transition(job, state)
        self._save(job)
        return job

    def _preflight(self, job: DownloadJob) -> None:
        destination = Path(job.destination)
        if destination.exists():
            marker = destination / ".rasputin-complete.json"
            if not (marker.exists() and self._marker_matches(marker, job)):
                raise PreflightError("destination exists without a matching completion marker")
        parent = destination.parent
        parent.mkdir(parents=True, exist_ok=True)
        if self.storage.check_space and not self.storage.check_space(parent, job.total_bytes):
            raise PreflightError("insufficient disk space for exact artifact")
        for record in job.files:
            _normalize_relative_path(record["path"])

    def _download_file(self, job: DownloadJob, record: dict[str, Any], control: DownloadControl) -> None:
        staging = Path(job.staging_dir)
        staging.mkdir(parents=True, exist_ok=True)
        relative = Path(record["path"])
        final_path = staging / relative
        part_path = staging / f"{record['path']}.part"
        final_path.parent.mkdir(parents=True, exist_ok=True)
        expected_size = int(record["expected_size"])

        if final_path.exists() and self._matches(record, final_path):
            record["status"] = "verified"
            self._update_progress(job)
            self._save(job)
            return
        if final_path.exists():
            final_path.unlink()
        offset = part_path.stat().st_size if part_path.exists() else 0
        if offset > expected_size:
            part_path.unlink()
            offset = 0
        if offset == expected_size and self._matches(record, part_path):
            self.storage.atomic_replace(part_path, final_path)
            record["status"] = "verified"
            self._update_progress(job)
            self._save(job)
            return
        if offset == expected_size:
            part_path.unlink()
            offset = 0

        self._save(job)
        result = self.transfer(
            DownloadFile(record["path"], expected_size, record.get("sha256")),
            part_path,
            offset,
            control,
            lambda current: self._progress_callback(job, record, current),
        )
        if result is not None:
            with part_path.open("ab") as handle:
                if isinstance(result, (bytes, bytearray, memoryview)):
                    handle.write(result)
                else:
                    for chunk in result:
                        if not isinstance(chunk, (bytes, bytearray, memoryview)):
                            raise TransferError("transfer callback yielded a non-byte chunk", transient=False)
                        handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        control.checkpoint()
        actual_size = part_path.stat().st_size if part_path.exists() else 0
        if actual_size != expected_size:
            raise TransferError(
                f"incomplete file {record['path']}: expected {expected_size} bytes, got {actual_size}",
                transient=True,
                code="incomplete_transfer",
            )
        if not self._matches(record, part_path):
            part_path.unlink(missing_ok=True)
            raise TransferError(f"hash mismatch for {record['path']}", transient=False, code="hash_mismatch")
        self.storage.atomic_replace(part_path, final_path)
        record["status"] = "verified"
        self._update_progress(job)
        self._save(job)

    def _verify_all(self, job: DownloadJob) -> None:
        for record in job.files:
            path = Path(job.staging_dir) / record["path"]
            if not path.exists() or not self._matches(record, path):
                raise TransferError(f"verification failed for {record['path']}", transient=False, code="verification_failed")
        job.downloaded_bytes = job.total_bytes
        self._save(job)

    def _finalize(self, job: DownloadJob) -> None:
        staging = Path(job.staging_dir)
        destination = Path(job.destination)
        marker = staging / ".rasputin-complete.json"
        marker_payload = {
            "job_id": job.id,
            "repository": job.repository,
            "revision": job.revision,
            "files": [{"path": item["path"], "size": item["expected_size"], "sha256": item.get("sha256")} for item in job.files],
        }
        marker_tmp = staging / ".rasputin-complete.json.tmp"
        with marker_tmp.open("w", encoding="utf-8") as handle:
            json.dump(marker_payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        self.storage.atomic_replace(marker_tmp, marker)
        if destination.exists():
            raise PreflightError("destination appeared during atomic installation")
        self.storage.atomic_replace(staging, destination)

    def _matches(self, record: Mapping[str, Any], path: Path) -> bool:
        try:
            if path.stat().st_size != int(record["expected_size"]):
                return False
            expected_hash = record.get("sha256")
            return not expected_hash or self._hash_file(path) == expected_hash.lower()
        except OSError:
            return False

    def _hash_file(self, path: Path) -> str:
        if self.storage.hash_file:
            return self.storage.hash_file(path)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _update_progress(self, job: DownloadJob) -> None:
        total = 0
        staging = Path(job.staging_dir)
        for record in job.files:
            final_path = staging / record["path"]
            part_path = staging / f"{record['path']}.part"
            if final_path.exists():
                total += min(int(record["expected_size"]), final_path.stat().st_size)
            elif part_path.exists():
                total += min(int(record["expected_size"]), part_path.stat().st_size)
        job.downloaded_bytes = total

    def _progress_callback(self, job: DownloadJob, record: Mapping[str, Any], current: int) -> None:
        self._update_progress(job)
        self._save(job)

    def _transition(self, job: DownloadJob, target: str) -> None:
        if target not in VALID_TRANSITIONS[job.state]:
            raise InvalidTransition(f"cannot transition {job.state} -> {target}")
        job.state = target
        job.updated_at = self.clock()

    def _fail(self, job: DownloadJob, message: str, *, code: str, retryable: bool) -> None:
        if job.state != "failed":
            self._transition(job, "failed")
        job.error = message
        job.error_code = code
        job.retryable = retryable
        self._update_progress(job)
        self._save(job)

    def _save(self, job: DownloadJob) -> None:
        job.updated_at = self.clock()
        self.repository.save(job)

    def _cleanup_staging(self, job: DownloadJob) -> None:
        staging = Path(job.staging_dir)
        if staging.exists():
            self.storage.remove_tree(staging)

    @staticmethod
    def _staging_path(destination: Path, job_id: str) -> Path:
        return destination.parent / f".{destination.name}.{job_id}.part"

    @staticmethod
    def _marker_matches(marker: Path, job: DownloadJob) -> bool:
        try:
            with marker.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value.get("job_id") == job.id and value.get("revision") == job.revision and value.get("repository") == job.repository
        except (OSError, ValueError, AttributeError):
            return False

    @staticmethod
    def _missing_transfer(*_: Any) -> None:
        raise TransferError("no transfer callback configured", transient=False, code="transfer_unconfigured")


def _normalize_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("file path must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe exact file path: {value!r}")
    return path.as_posix()
