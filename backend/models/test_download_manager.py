import hashlib

import pytest

from backend.models.download_manager import (
    DownloadManager,
    DownloadVariant,
    InMemoryJobRepository,
    InvalidTransition,
    JsonJobRepository,
    StorageCallbacks,
    TransferError,
)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def variant(tmp_path, payloads, *, hashes=True):
    return {
        "repository": "acme/example",
        "revision": "0123456789abcdef",
        "files": [
            {
                "path": name,
                "expected_size": len(payload),
                "sha256": digest(payload) if hashes else None,
            }
            for name, payload in payloads.items()
        ],
        "destination": tmp_path / "installed",
    }


class FixtureTransfer:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []
        self.fail_once = False

    def __call__(self, file, part_path, offset, control, report):
        self.calls.append((file.path, offset))
        if self.fail_once:
            self.fail_once = False
            part_path.parent.mkdir(parents=True, exist_ok=True)
            part_path.write_bytes(self.payloads[file.path][: max(1, len(self.payloads[file.path]) // 2)])
            raise TransferError("temporary connection reset", transient=True, code="connection_reset")
        return self.payloads[file.path][offset:]


def make_manager(tmp_path, payloads, *, repository=None, transfer=None, storage=None):
    transfer = transfer or FixtureTransfer(payloads)
    manager = DownloadManager(
        repository or InMemoryJobRepository(),
        transfer=transfer,
        storage=storage,
    )
    return manager, transfer


def test_valid_and_invalid_transitions(tmp_path):
    payloads = {"model.gguf": b"model"}
    manager, _ = make_manager(tmp_path, payloads)
    job = manager.create_job(variant(tmp_path, payloads))
    with pytest.raises(InvalidTransition):
        manager.pause(job.id)
    assert manager.start(job.id).state == "completed"
    with pytest.raises(InvalidTransition):
        manager.transition(job.id, "downloading")


def test_pause_and_resume(tmp_path):
    payloads = {"model.gguf": b"model-data"}
    manager = DownloadManager(InMemoryJobRepository())
    should_pause = True

    def pausing_transfer(file, part_path, offset, control, report):
        nonlocal should_pause
        if should_pause:
            should_pause = False
            manager.pause(job.id)
            control.checkpoint()
        return payloads[file.path][offset:]

    manager.transfer = pausing_transfer
    job = manager.create_job(variant(tmp_path, payloads))
    assert manager.start(job.id).state == "paused"
    assert manager.get_job(job.id).downloaded_bytes == 0
    assert manager.resume(job.id).state == "completed"


def test_cancel_cleans_staging_files(tmp_path):
    payloads = {"model.gguf": b"model-data"}
    manager, _ = make_manager(tmp_path, payloads)
    job = manager.create_job(variant(tmp_path, payloads))
    manager.cancel(job.id)
    assert manager.get_job(job.id).state == "cancelled"
    assert not (tmp_path / f".installed.{job.id}.part").exists()
    with pytest.raises(InvalidTransition):
        manager.start(job.id)


def test_transient_failure_retries_and_preserves_partial_bytes(tmp_path):
    payloads = {"model.gguf": b"0123456789"}
    transfer = FixtureTransfer(payloads)
    transfer.fail_once = True
    manager, _ = make_manager(tmp_path, payloads, transfer=transfer)
    job = manager.create_job(variant(tmp_path, payloads))
    failed = manager.start(job.id)
    assert failed.state == "failed"
    assert failed.retryable is True
    assert failed.error_code == "connection_reset"
    part = tmp_path / f".installed.{job.id}.part" / "model.gguf.part"
    assert part.read_bytes() == payloads["model.gguf"][:5]
    assert manager.retry(job.id).state == "completed"
    assert transfer.calls == [("model.gguf", 0), ("model.gguf", 5)]


def test_restart_rehydrates_and_can_resume_paused_job(tmp_path):
    payloads = {"model.gguf": b"restart-safe"}
    repository_path = tmp_path / "jobs.json"
    repository = JsonJobRepository(repository_path)
    manager = DownloadManager(repository)
    should_pause = True

    def pause_once(file, part_path, offset, control, report):
        nonlocal should_pause
        if should_pause:
            should_pause = False
            manager.pause(job.id)
            control.checkpoint()
        return payloads[file.path][offset:]

    manager.transfer = pause_once
    job = manager.create_job(variant(tmp_path, payloads))
    assert manager.start(job.id).state == "paused"

    restarted = DownloadManager(JsonJobRepository(repository_path), transfer=FixtureTransfer(payloads))
    assert restarted.recover()[0].state == "paused"
    assert restarted.resume(job.id).state == "completed"


def test_multi_file_aggregate_progress(tmp_path):
    payloads = {"a.bin": b"1234", "nested/b.bin": b"567890"}
    manager, _ = make_manager(tmp_path, payloads)
    job = manager.create_job(variant(tmp_path, payloads))
    original = manager.transfer
    paused_once = False

    def pause_on_second(file, part_path, offset, control, report):
        nonlocal paused_once
        if file.path == "nested/b.bin" and not paused_once:
            paused_once = True
            manager.pause(job.id)
            control.checkpoint()
        return original(file, part_path, offset, control, report)

    manager.transfer = pause_on_second
    paused = manager.start(job.id)
    assert paused.state == "paused"
    assert paused.downloaded_bytes == 4
    assert paused.progress == 40.0
    assert manager.resume(job.id).state == "completed"


def test_hash_mismatch_is_not_retryable_and_does_not_publish(tmp_path):
    expected = b"good-data"
    manager, _ = make_manager(tmp_path, {"model.gguf": b"wrongdata"})
    job = manager.create_job(variant(tmp_path, {"model.gguf": expected}))
    failed = manager.start(job.id)
    assert failed.state == "failed"
    assert failed.error_code == "hash_mismatch"
    assert failed.retryable is False
    assert not (tmp_path / "installed").exists()


def test_disk_preflight_rejection_does_not_transfer(tmp_path):
    payloads = {"model.gguf": b"data"}
    transfer = FixtureTransfer(payloads)
    storage = StorageCallbacks(check_space=lambda destination, required: False)
    manager, _ = make_manager(tmp_path, payloads, transfer=transfer, storage=storage)
    job = manager.create_job(variant(tmp_path, payloads))
    failed = manager.start(job.id)
    assert failed.state == "failed"
    assert failed.error_code == "preflight_rejected"
    assert transfer.calls == []


def test_atomic_completion_publishes_marker_only_after_all_files_verified(tmp_path):
    payloads = {"model.gguf": b"model", "mmproj.gguf": b"projection"}
    manager, _ = make_manager(tmp_path, payloads)
    job = manager.create_job(variant(tmp_path, payloads))
    completed = manager.start(job.id)
    destination = tmp_path / "installed"
    assert completed.state == "completed"
    assert (destination / "model.gguf").read_bytes() == payloads["model.gguf"]
    assert (destination / "mmproj.gguf").read_bytes() == payloads["mmproj.gguf"]
    assert (destination / ".rasputin-complete.json").exists()
    assert not (tmp_path / f".installed.{job.id}.part").exists()


def test_mapping_input_supports_expected_size_and_hash_maps(tmp_path):
    payload = b"exact"
    value = {
        "repo_id": "acme/example",
        "revision": "rev1",
        "exact_files": ["model.gguf"],
        "expected_sizes": {"model.gguf": len(payload)},
        "expected_hashes": {"model.gguf": digest(payload)},
        "destination": tmp_path / "installed",
    }
    normalized = DownloadVariant.from_input(value)
    assert normalized.files[0].path == "model.gguf"
    assert normalized.files[0].sha256 == digest(payload)
