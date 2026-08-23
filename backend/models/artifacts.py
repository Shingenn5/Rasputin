"""Durable installed-artifact manifests for desktop model downloads."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


def _stable_id(repository: str, revision: str, variant_id: str, files: list[Mapping[str, Any]]) -> str:
    identity = {"repository": repository, "revision": revision, "variant_id": variant_id,
                "files": [(str(item.get("path")), item.get("size"), item.get("sha256")) for item in files]}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"artifact-{digest[:24]}"


class ArtifactStore:
    """Atomic JSON index of completed, user-owned desktop artifacts."""

    def __init__(self, data_root: str | Path):
        self.data_root = Path(data_root).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.path = self.data_root / "installed-artifacts.json"

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"artifacts": [], "jobs": {}}
        except (OSError, ValueError):
            return {"artifacts": [], "jobs": {}}

    def _write(self, value: Mapping[str, Any]) -> None:
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)

    def save_job_metadata(self, job_id: str, metadata: Mapping[str, Any]) -> None:
        value = self._read()
        value.setdefault("jobs", {})[str(job_id)] = dict(metadata)
        self._write(value)

    def metadata_for_job(self, job_id: str) -> dict[str, Any]:
        metadata = self._read().get("jobs", {}).get(str(job_id), {})
        return dict(metadata) if isinstance(metadata, Mapping) else {}

    def install(self, job: Any, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        existing = next((item for item in self._read().get("artifacts", [])
                         if item.get("job_id") == str(job.id)), None)
        if isinstance(existing, Mapping):
            return dict(existing)
        metadata = {**self.metadata_for_job(job.id), **dict(metadata or {})}
        destination = Path(job.destination).resolve()
        files = []
        for record in job.files:
            path = destination / str(record["path"])
            digest = record.get("sha256")
            if not digest and path.is_file():
                hasher = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        hasher.update(chunk)
                digest = hasher.hexdigest()
            files.append({"path": str(record["path"]), "localPath": str(path),
                          "size": path.stat().st_size if path.is_file() else int(record["expected_size"]),
                          "sha256": digest, "role": record.get("role", "artifact")})
        repository, revision = str(job.repository), str(job.revision)
        variant_id = str(metadata.get("variant_id") or metadata.get("variantId") or "")
        artifact_id = str(metadata.get("artifact_id") or _stable_id(repository, revision, variant_id, files))
        model_files = [item for item in files if item["role"] == "model"]
        mmproj_files = [item for item in files if item["role"] == "mmproj"]
        main = model_files[0] if model_files else files[0]
        artifact = {"artifact_id": artifact_id, "job_id": str(job.id), "repository": repository,
                    "revision": revision, "variant_id": variant_id,
                    "quantization": str(metadata.get("quantization") or ""), "files": files,
                    "model_files": model_files, "mmproj_files": mmproj_files,
                    "destination": str(destination), "main_model_path": main["localPath"]}
        value = self._read()
        value["artifacts"] = [item for item in value.get("artifacts", []) if item.get("artifact_id") != artifact_id]
        value["artifacts"].append(artifact)
        value.setdefault("jobs", {}).pop(str(job.id), None)
        self._write(value)
        return artifact

    def list_installed(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._read().get("artifacts", []) if isinstance(item, Mapping)]

    def rehydrate_registry(self) -> list[dict[str, Any]]:
        from backend.models import registry
        registered = []
        for artifact in self.list_installed():
            if not Path(str(artifact.get("main_model_path") or "")).is_file():
                continue
            try:
                registered.append(registry.register_artifact(artifact))
            except Exception:
                continue
        return registered


def installed_artifacts(data_root: str | Path) -> list[dict[str, Any]]:
    return ArtifactStore(data_root).list_installed()


__all__ = ["ArtifactStore", "installed_artifacts"]
