"""Versioned, artifact-backed release evidence; never executes imported records.

These are operator attestations, not signed certificates. Hashes prove the selected
source/package and attached bytes match; an operator must still review what the
artifacts demonstrate. Historical prose and source fixtures are never promoted.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath
from typing import Any


SCHEMA_VERSION = 1
MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_RECORDS = 128
MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_BUNDLE_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_AGE = timedelta(days=7)
HASH = re.compile(r"[0-9a-f]{64}\Z")
ROLES = {"main", "coder", "assistant", "stt", "tts"}
TYPES = {
    "source-test", "mocked-workflow", "browser-test", "source-probe",
    "installed-package", "clean-machine", "model-runtime", "live-coder",
    "live-voice", "recovery",
}
ROWS = {
    "automatedRegression": "Automated regression",
    "nativeDeployment": "Native deployment",
    "modelRuntime": "Model runtime",
    "coderMission": "Coder mission",
    "voiceTurn": "Voice turn",
    "lastingMemory": "Lasting memory",
    "safeOrchestration": "Safe orchestration",
    "recovery": "Recovery",
    "operatorUx": "Operator UX",
}
ROW_MODELS = {
    "modelRuntime": {"main"}, "coderMission": {"coder"},
    "voiceTurn": {"assistant", "stt", "tts"},
}


class EvidenceError(ValueError):
    pass


def file_digest(path: Path, *, maximum: int | None = None) -> str:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            count += len(chunk)
            if maximum is not None and count > maximum:
                raise EvidenceError("artifact exceeds the size limit")
            digest.update(chunk)
    return digest.hexdigest()


def source_identity(root: Path) -> dict[str, Any]:
    """Hash tracked and non-ignored untracked bytes, including dirty changes.

    Keep evidence bundles outside this source tree to avoid a self-referential
    digest. Git-ignored build output is represented by the selected package hash.
    """
    root = root.resolve()

    def git(*args: str) -> bytes:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, check=True, timeout=30,
        ).stdout

    commit = git("rev-parse", "HEAD").decode("ascii").strip()
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    names = sorted(set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")) - {b""})
    if len(names) > 20000:
        raise EvidenceError("source inventory exceeds the file limit")
    digest = hashlib.sha256()
    total = 0
    for name in names:
        path = root / name.decode("utf-8")
        if not path.resolve().is_relative_to(root):
            raise EvidenceError("source link escapes the checkout")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        if not path.exists():
            digest.update(b"deleted\0")
            continue
        if not path.is_file() or path.is_symlink():
            raise EvidenceError("source inventory contains an unsupported link or directory")
        total += path.stat().st_size
        if total > 512 * 1024 * 1024:
            raise EvidenceError("source inventory exceeds the byte limit")
        digest.update(bytes.fromhex(file_digest(path, maximum=MAX_ARTIFACT_BYTES)))
    return {"commit": commit, "dirty": bool(status), "sha256": digest.hexdigest()}


def package_identity(target: str, source: dict[str, Any], package: Path | None) -> dict[str, str]:
    if target == "native-host":
        if package is not None:
            raise EvidenceError("--package is only applicable to the Desktop target")
        return {"kind": "source", "sha256": source["sha256"]}
    if package is None or not package.is_file():
        raise EvidenceError("Desktop requires --package pointing to the tested installer or package file")
    return {"kind": "desktop-package", "sha256": file_digest(package)}


def parse_models(values: list[str]) -> dict[str, dict[str, str]]:
    models = {}
    for value in values:
        role, separator, identity = value.partition("=")
        hashes = identity.split(":")
        if not separator or role not in ROLES or role in models or len(hashes) != 3 or not all(HASH.fullmatch(item) for item in hashes):
            raise EvidenceError("--model expects unique ROLE=ARTIFACT_SHA256:RUNTIME_SHA256:CONFIG_SHA256")
        models[role] = dict(zip(("artifactSha256", "runtimeSha256", "configSha256"), hashes))
    return models


def _object(value: Any, keys: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise EvidenceError(f"{label} has missing or unknown fields")


def _text(value: Any, label: str, maximum: int = 160) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(char) < 32 for char in value):
        raise EvidenceError(f"{label} must be bounded nonempty text")


def _hash(value: Any, label: str) -> None:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise EvidenceError(f"{label} must be a lowercase SHA-256 digest")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise EvidenceError("duplicate JSON field")
        value[key] = item
    return value


def _record(record: Any, subject: dict[str, Any], directory: Path, now: datetime, budget: list[int]) -> datetime:
    _object(record, {"id", "row", "type", "source", "target", "package", "environment", "models", "timestamp", "outcome", "artifacts"}, "record")
    _text(record["id"], "record id")
    if record["row"] not in ROWS or record["type"] not in TYPES:
        raise EvidenceError("unknown evidence row or type")
    _object(record["source"], {"commit", "dirty", "sha256"}, "source")
    _text(record["source"]["commit"], "commit", 64)
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", record["source"]["commit"]):
        raise EvidenceError("invalid source commit")
    if type(record["source"]["dirty"]) is not bool:
        raise EvidenceError("dirty must be boolean")
    _hash(record["source"]["sha256"], "source digest")
    _object(record["package"], {"kind", "sha256"}, "package")
    _hash(record["package"]["sha256"], "package digest")
    if any(record[field] != subject[field] for field in ("source", "target", "package")):
        raise EvidenceError("source, target, or selected package identity mismatch")
    environment = record["environment"]
    _object(environment, {"kind", "platform", "machineId", "owner", "hardwareId"}, "environment")
    if environment["kind"] not in {"source", "installed", "clean-machine"} or environment["platform"] != "windows" or environment["owner"] != subject["target"]:
        raise EvidenceError("environment is not a selected Windows native owner")
    _text(environment["machineId"], "machineId")
    if environment["hardwareId"] is not None:
        _text(environment["hardwareId"], "hardwareId")
    models = record["models"]
    if not isinstance(models, dict) or set(models) - ROLES:
        raise EvidenceError("models must contain supported roles")
    for role, identity in models.items():
        _object(identity, {"artifactSha256", "runtimeSha256", "configSha256"}, "model identity")
        for value in identity.values():
            _hash(value, "model identity")
        if subject["models"].get(role) != identity:
            raise EvidenceError("model identity does not match the selected role")
    required_models = ROW_MODELS.get(record["row"], set())
    if required_models - set(models):
        raise EvidenceError("selected model identities are required for this row")
    if required_models and environment["hardwareId"] is None:
        raise EvidenceError("live model evidence requires hardware identity")
    _text(record["timestamp"], "timestamp", 40)
    try:
        timestamp = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceError("invalid timestamp") from exc
    if timestamp.tzinfo is None or timestamp > now + timedelta(minutes=5) or now - timestamp > MAX_AGE:
        raise EvidenceError("evidence timestamp is missing its timezone, stale, or in the future")
    if record["outcome"] not in {"passed", "failed"}:
        raise EvidenceError("outcome must be passed or failed")
    artifacts = record["artifacts"]
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 16:
        raise EvidenceError("one to sixteen hashed artifact references are required")
    for artifact in artifacts:
        _object(artifact, {"path", "sha256"}, "artifact")
        _text(artifact["path"], "artifact path", 400)
        _hash(artifact["sha256"], "artifact digest")
        relative = Path(artifact["path"])
        windows = PureWindowsPath(artifact["path"])
        if relative.is_absolute() or windows.drive or windows.root or ".." in relative.parts or ".." in windows.parts or ":" in artifact["path"]:
            raise EvidenceError("artifact references must remain relative to the evidence directory")
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise EvidenceError("artifact is missing or escapes the evidence directory")
        budget[0] += path.stat().st_size
        if budget[0] > MAX_BUNDLE_ARTIFACT_BYTES:
            raise EvidenceError("evidence attachments exceed the bundle byte limit")
        if file_digest(path, maximum=MAX_ARTIFACT_BYTES) != artifact["sha256"]:
            raise EvidenceError("artifact digest mismatch")
    return timestamp


def evaluate(path: Path | None, subject: dict[str, Any], *, automated_passed: bool, now: datetime | None = None) -> dict[str, Any]:
    """Validate the bundle and close only evidence types suitable for each row."""
    now = now or datetime.now(timezone.utc)
    accepted = []
    rejected = []
    budget = [0]
    if path is not None:
        try:
            with path.open("rb") as stream:
                raw = stream.read(MAX_DOCUMENT_BYTES + 1)
            if len(raw) > MAX_DOCUMENT_BYTES:
                raise EvidenceError("evidence document exceeds the size limit")
            document = json.loads(raw, object_pairs_hook=_unique_object)
            _object(document, {"schemaVersion", "records"}, "evidence document")
            if type(document["schemaVersion"]) is not int or document["schemaVersion"] != SCHEMA_VERSION:
                raise EvidenceError("unsupported evidence schema version")
            records = document["records"]
            if not isinstance(records, list) or len(records) > MAX_RECORDS:
                raise EvidenceError("records must be a list of at most 128 items")
            seen = set()
            for index, record in enumerate(records):
                try:
                    timestamp = _record(record, subject, path.parent.resolve(), now, budget)
                    if record["id"] in seen:
                        raise EvidenceError("duplicate record id")
                    seen.add(record["id"])
                    accepted.append((record, timestamp))
                except (EvidenceError, OSError, TypeError) as exc:
                    rejected.append({"index": index, "reason": str(exc) if not isinstance(exc, OSError) else "artifact could not be read"})
        except (EvidenceError, OSError, ValueError, RecursionError, TypeError) as exc:
            rejected.append({"reason": str(exc) if not isinstance(exc, OSError) else "evidence document could not be read"})

    desktop = subject["target"] == "desktop"
    native_kinds = {"installed", "clean-machine"} if desktop else {"source"}
    requirements = {
        "nativeDeployment": [("installed-package", {"installed"}), ("clean-machine", {"clean-machine"})] if desktop else [("source-probe", {"source"})],
        "modelRuntime": [("model-runtime", native_kinds)],
        "coderMission": [("live-coder", native_kinds)],
        "voiceTurn": [("live-voice", native_kinds)],
        "lastingMemory": [("browser-test", native_kinds)],
        "safeOrchestration": [("browser-test", native_kinds)],
        "recovery": [("recovery", {"clean-machine"} if desktop else {"source"})],
        "operatorUx": [("browser-test", native_kinds)],
    }
    rows = [{"id": "automatedRegression", "label": ROWS["automatedRegression"], "status": "passed" if automated_passed else "open", "evidenceIds": [], "missing": [] if automated_passed else ["current automated regression gates"]}]
    for row, required in requirements.items():
        missing = []
        ids = []
        for evidence_type, kinds in required:
            candidates = [(record, timestamp) for record, timestamp in accepted if record["row"] == row and record["type"] == evidence_type and record["environment"]["kind"] in kinds]
            # A newer failure (including a timestamp tie) cannot be hidden by an older pass.
            latest = max(candidates, key=lambda item: (item[1], item[0]["outcome"] == "failed"), default=None)
            if latest is None or latest[0]["outcome"] != "passed":
                missing.append(f"{evidence_type} in {'/'.join(sorted(kinds))}" + (" (latest evidence failed)" if latest else ""))
            else:
                ids.append(latest[0]["id"])
        rows.append({"id": row, "label": ROWS[row], "status": "open" if missing else "passed", "evidenceIds": ids, "missing": missing})
    return {
        "schemaVersion": SCHEMA_VERSION, "maximumAgeDays": MAX_AGE.days,
        "rows": rows, "rejectedRecords": rejected,
        "acceptedRecordCount": len(accepted),
        "passed": not rejected and all(row["status"] == "passed" for row in rows),
        "trust": "Operator attestations with verified attachment hashes; artifact content and provenance require operator review.",
    }
