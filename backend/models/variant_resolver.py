"""Deterministic resolution of Hugging Face GGUF sibling files.

This module deliberately has no Hugging Face or network dependency.  The public
resolver accepts the dictionary-shaped data returned by ``model_info`` and
``siblings`` so catalog and acquisition code can adopt the contract
independently.

Only complete model file sets become :class:`ModelVariant` records.  A shard
family with a missing member is reported as an issue, but is never returned as
a downloadable variant.  When a repository has projection files, both the
model-only set and each exact model-plus-projection set are represented; the
former is useful for text-only loading and the latter is multimodal-capable.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any


UNKNOWN = "Unknown"
NEEDS_REVIEW = "needs-review"


# These are estimates of serialized GGUF bits per weight, including the
# quantization block overhead.  They are intentionally estimates, not fit
# claims; exact fit planning belongs to a later resource-planning layer.
_QUANTIZATION_BITS: dict[str, float] = {
    "Q2_K": 2.625,
    "Q3_K_S": 3.4375,
    "Q3_K_M": 3.875,
    "Q3_K_L": 4.25,
    "Q4_0": 4.5,
    "Q4_1": 5.0,
    "Q4_K_S": 4.5,
    "Q4_K_M": 4.75,
    "Q4_K_L": 5.0,
    "Q5_0": 5.5,
    "Q5_1": 6.0,
    "Q5_K_S": 5.5,
    "Q5_K_M": 5.75,
    "Q5_K_L": 6.0,
    "Q6_K": 6.5625,
    "Q8_0": 8.5,
    "IQ1_S": 1.5625,
    "IQ2_XXS": 2.0625,
    "IQ2_XS": 2.3125,
    "IQ2_S": 2.5625,
    "IQ3_XXS": 3.0625,
    "IQ3_S": 3.4375,
    "IQ4_XS": 4.25,
    "IQ4_NL": 4.5,
    "F16": 16.0,
    "BF16": 16.0,
    "F32": 32.0,
}

_QUANTIZATION_ALIASES = {
    "FP16": "F16",
    "FP32": "F32",
    "FLOAT16": "F16",
    "FLOAT32": "F32",
}

_QUANTIZATION_PATTERN = re.compile(
    r"(?<![A-Z0-9])(" + "|".join(
        sorted((*_QUANTIZATION_BITS, *_QUANTIZATION_ALIASES), key=len, reverse=True)
    ) + r")(?![A-Z0-9])",
    re.IGNORECASE,
)
_SHARD_PATTERN = re.compile(
    r"^(?P<base>.+)-(?P<index>\d+)-of-(?P<count>\d+)\.gguf$", re.IGNORECASE
)
_GGUF_SUFFIX = ".gguf"


@dataclass(frozen=True, slots=True)
class ModelVariant:
    """One exact, downloadable GGUF file set.

    ``files`` contains the complete set to acquire, including any projection
    companion.  ``model_files`` and ``mmproj_files`` make that split explicit
    for a future downloader.  ``total_bytes`` is ``None`` when any selected
    file lacks a trustworthy size in the supplied metadata.
    """

    id: str
    repository: str
    revision: str
    files: tuple[str, ...]
    model_files: tuple[str, ...]
    mmproj_files: tuple[str, ...]
    total_bytes: int | None
    quantization: str
    bits_per_weight: float | None
    shard_count: int
    multimodal: bool
    compatibility_state: str
    compatibility_reasons: tuple[str, ...]
    next_actions: tuple[str, ...]

    @property
    def reasons(self) -> tuple[str, ...]:
        """Short alias for consumers rendering the actionable explanation."""

        return self.compatibility_reasons

    @property
    def mmproj(self) -> str | None:
        """Return the single projection path for the common pairing case."""

        return self.mmproj_files[0] if len(self.mmproj_files) == 1 else None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly, stable representation for later API use."""

        return {
            "id": self.id,
            "repository": self.repository,
            "revision": self.revision,
            "files": list(self.files),
            "modelFiles": list(self.model_files),
            "mmprojFiles": list(self.mmproj_files),
            "totalBytes": self.total_bytes,
            "quantization": self.quantization,
            "bitsPerWeight": self.bits_per_weight,
            "shardCount": self.shard_count,
            "multimodal": self.multimodal,
            "compatibilityState": self.compatibility_state,
            "compatibilityReasons": list(self.compatibility_reasons),
            "nextActions": list(self.next_actions),
        }


@dataclass(frozen=True, slots=True)
class VariantIssue:
    """A sibling-file problem that cannot safely become a variant."""

    kind: str
    files: tuple[str, ...]
    reason: str
    next_action: str


@dataclass(frozen=True, slots=True)
class VariantResolution:
    """Variants plus non-downloadable input issues for catalog diagnostics."""

    variants: tuple[ModelVariant, ...]
    issues: tuple[VariantIssue, ...]


@dataclass(frozen=True, slots=True)
class _FileRecord:
    path: str
    size: int | None
    size_conflict: bool = False


@dataclass(slots=True)
class _ModelGroup:
    key: tuple[str, ...]
    model_files: list[_FileRecord]
    expected_shards: int
    shard_indices: set[int]


def resolve_model_variants(
    model_info: Mapping[str, Any] | None,
    siblings: Iterable[Mapping[str, Any]] | None = None,
) -> tuple[ModelVariant, ...]:
    """Resolve complete GGUF variants from plain Hugging Face-shaped dicts.

    ``siblings`` may be omitted when the model dictionary contains a
    ``siblings`` list.  Invalid records and incomplete shard families are
    excluded rather than turned into partial downloadable variants.  Use
    :func:`resolve_model_variants_with_issues` when the caller needs the
    actionable diagnostics for those exclusions.
    """

    return resolve_model_variants_with_issues(model_info, siblings).variants


def resolve_model_variants_with_issues(
    model_info: Mapping[str, Any] | None,
    siblings: Iterable[Mapping[str, Any]] | None = None,
) -> VariantResolution:
    """Resolve variants and report rejected sibling groups without network I/O."""

    info = model_info if isinstance(model_info, Mapping) else {}
    repository = _repository(info)
    revision = _revision(info)
    sibling_values = siblings if siblings is not None else info.get("siblings") or ()
    records, input_issues = _deduplicate_records(sibling_values)

    model_records = [record for record in records if not _is_mmproj(record.path)]
    mmproj_records = [record for record in records if _is_mmproj(record.path)]
    if not model_records:
        if mmproj_records:
            input_issues.append(
                VariantIssue(
                    kind="mmproj-without-model",
                    files=tuple(record.path for record in mmproj_records),
                    reason="Projection files are present, but no main GGUF model file was found.",
                    next_action="Add a complete model GGUF file set before offering a download.",
                )
            )
        else:
            input_issues.append(
                VariantIssue(
                    kind="no-gguf",
                    files=(),
                    reason="The repository metadata contains no GGUF files.",
                    next_action="Choose a repository with GGUF artifacts or use a format-specific importer.",
                )
            )
        return VariantResolution(variants=(), issues=_sort_issues(input_issues))

    groups: dict[tuple[str, ...], _ModelGroup] = {}
    for record in model_records:
        match = _SHARD_PATTERN.match(record.path)
        if match:
            base = match.group("base")
            index = int(match.group("index"))
            count = int(match.group("count"))
            key = ("shards", base, str(count))
        else:
            index = 1
            count = 1
            key = ("single", record.path)
        group = groups.setdefault(
            key,
            _ModelGroup(
                key=key,
                model_files=[],
                expected_shards=count,
                shard_indices=set(),
            ),
        )
        group.model_files.append(record)
        group.shard_indices.add(index)

    variants: list[ModelVariant] = []
    for group in groups.values():
        group.model_files.sort(key=lambda item: _path_key(item.path))
        expected = set(range(1, group.expected_shards + 1))
        present = group.shard_indices
        if group.key[0] == "shards" and present != expected:
            missing = tuple(
                f"{group.key[1]}-{index:05d}-of-{group.expected_shards:05d}.gguf"
                for index in sorted(expected - present)
            )
            input_issues.append(
                VariantIssue(
                    kind="incomplete-shard-group",
                    files=tuple(record.path for record in group.model_files),
                    reason=(
                        f"Shard family declares {group.expected_shards} files but "
                        f"is missing {len(missing)} member(s)."
                    ),
                    next_action="Refresh repository metadata and require every shard before downloading.",
                )
            )
            continue

        for projection in [None, *mmproj_records]:
            variants.append(
                _make_variant(
                    info=info,
                    repository=repository,
                    revision=revision,
                    model_files=tuple(group.model_files),
                    projection=projection,
                    expected_shards=group.expected_shards,
                )
            )

    # The key is the full exact file set, so this also protects against
    # equivalent groups produced by unusual duplicate metadata.
    unique: dict[str, ModelVariant] = {variant.id: variant for variant in variants}
    ordered = tuple(sorted(unique.values(), key=_variant_sort_key))
    return VariantResolution(variants=ordered, issues=_sort_issues(input_issues))


def _make_variant(
    *,
    info: Mapping[str, Any],
    repository: str,
    revision: str,
    model_files: tuple[_FileRecord, ...],
    projection: _FileRecord | None,
    expected_shards: int,
) -> ModelVariant:
    model_paths = tuple(record.path for record in model_files)
    projection_paths = (projection.path,) if projection else ()
    all_paths = tuple(sorted((*model_paths, *projection_paths), key=_path_key))
    all_records = (*model_files, *((projection,) if projection else ()))
    sizes = [record.size for record in all_records]
    total_bytes = sum(size for size in sizes if size is not None) if all(size is not None for size in sizes) else None

    quantizations = {
        quantization
        for quantization in (_detect_quantization(path) for path in model_paths)
        if quantization != UNKNOWN
    }
    metadata_quantization = _canonical_quantization(info.get("quantization"))
    if len(quantizations) == 1:
        quantization = next(iter(quantizations))
    elif len(quantizations) > 1:
        quantization = UNKNOWN
    elif metadata_quantization:
        quantization = metadata_quantization
    else:
        quantization = UNKNOWN
    bits_per_weight = _QUANTIZATION_BITS.get(quantization)

    reasons = ["llama.cpp compatibility has not been verified from sibling metadata alone."]
    next_actions = ["Validate the complete file set with the installed llama.cpp runtime before loading."]
    if quantization == UNKNOWN:
        reasons.append("Quantization could not be determined from the file name or model metadata.")
        next_actions.append("Review the GGUF metadata or select a file with a recognized quantization suffix.")
    if total_bytes is None:
        reasons.append("At least one selected file is missing a trustworthy byte size.")
        next_actions.append("Refresh Hugging Face metadata before showing an exact download-size or fit estimate.")
    if any(record.size_conflict for record in all_records):
        reasons.append("Duplicate sibling metadata reports conflicting sizes for a selected file.")
        next_actions.append("Refresh repository metadata and confirm the revision before downloading.")
    if projection:
        reasons.append("The mmproj companion is paired by repository filename metadata; runtime pairing remains unverified.")
        next_actions.append("Validate the projection architecture against the model before enabling multimodal use.")

    identity = {
        "repository": repository,
        "revision": revision,
        "files": all_paths,
    }
    digest = hashlib.sha256(
        json.dumps(identity, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return ModelVariant(
        id=f"gguf:{digest}",
        repository=repository,
        revision=revision,
        files=all_paths,
        model_files=model_paths,
        mmproj_files=projection_paths,
        total_bytes=total_bytes,
        quantization=quantization,
        bits_per_weight=bits_per_weight,
        shard_count=expected_shards,
        multimodal=bool(projection_paths),
        compatibility_state="unknown",
        compatibility_reasons=tuple(dict.fromkeys(reasons)),
        next_actions=tuple(dict.fromkeys(next_actions)),
    )


def _deduplicate_records(
    siblings: Iterable[Mapping[str, Any]],
) -> tuple[list[_FileRecord], list[VariantIssue]]:
    by_path: dict[str, list[int | None]] = {}
    invalid: list[VariantIssue] = []
    for sibling in siblings:
        if not isinstance(sibling, Mapping):
            continue
        path = _filename(sibling)
        if not path:
            invalid.append(
                VariantIssue(
                    kind="invalid-sibling",
                    files=(),
                    reason="A sibling record has no usable filename.",
                    next_action="Refresh repository metadata before resolving variants.",
                )
            )
            continue
        if not path.lower().endswith(_GGUF_SUFFIX):
            continue
        by_path.setdefault(path, []).append(_size(sibling))

    records = []
    for path in sorted(by_path, key=_path_key):
        values = by_path[path]
        known_sizes = {value for value in values if value is not None}
        conflict = len(known_sizes) > 1
        size = next(iter(known_sizes)) if len(known_sizes) == 1 and not conflict else None
        records.append(_FileRecord(path=path, size=size, size_conflict=conflict))
    return records, invalid


def _filename(sibling: Mapping[str, Any]) -> str:
    value = sibling.get("rfilename") or sibling.get("path") or sibling.get("filename") or sibling.get("name")
    if not isinstance(value, str):
        return ""
    path = value.replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def _size(sibling: Mapping[str, Any]) -> int | None:
    value = sibling.get("size")
    if value is None and isinstance(sibling.get("lfs"), Mapping):
        value = sibling["lfs"].get("size")
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _repository(info: Mapping[str, Any]) -> str:
    for key in ("id", "modelId", "model_id", "repo_id", "repository"):
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return UNKNOWN


def _revision(info: Mapping[str, Any]) -> str:
    for key in ("sha", "revision", "commit", "commit_hash"):
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return UNKNOWN


def _is_mmproj(path: str) -> bool:
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    return stem.startswith("mmproj") or bool(re.search(r"(?:^|[-_.])mmproj(?:[-_.]|$)", stem))


def _canonical_quantization(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().upper().replace("-", "_")
    text = _QUANTIZATION_ALIASES.get(text, text)
    return text if text in _QUANTIZATION_BITS else None


def _detect_quantization(path: str) -> str:
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0].upper()
    stem = re.sub(r"-\d+-OF-\d+$", "", stem)
    match = _QUANTIZATION_PATTERN.search(stem)
    if not match:
        return UNKNOWN
    return _canonical_quantization(match.group(1)) or UNKNOWN


def _path_key(path: str) -> tuple[str, str]:
    return (path.casefold(), path)


def _variant_sort_key(variant: ModelVariant) -> tuple[Any, ...]:
    # Highest precision first is useful for a detail view, while every tie is
    # broken by the complete file set and therefore independent of input order.
    precision = variant.bits_per_weight if variant.bits_per_weight is not None else float("-inf")
    return (-precision, variant.quantization.casefold(), variant.shard_count, not variant.multimodal, variant.files)


def _sort_issues(issues: Iterable[VariantIssue]) -> tuple[VariantIssue, ...]:
    return tuple(sorted(issues, key=lambda issue: (issue.kind, issue.files, issue.reason)))


__all__ = [
    "ModelVariant",
    "NEEDS_REVIEW",
    "UNKNOWN",
    "VariantIssue",
    "VariantResolution",
    "resolve_model_variants",
    "resolve_model_variants_with_issues",
]
