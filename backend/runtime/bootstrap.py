"""Locate the pinned llama.cpp manifest in development and packaged apps."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from backend.core.datadir import data_dir


def _unique(paths):
    result = []
    seen = set()
    for path in paths:
        resolved = Path(path).expanduser().resolve()
        key = str(resolved).casefold()
        if key not in seen:
            seen.add(key)
            result.append(resolved)
    return result


def manifest_candidates(*, configured=None, data_root=None, executable=None, resource_root=None):
    """Return manifest paths from highest to lowest precedence."""
    explicit = configured if configured is not None else os.environ.get("RASPUTIN_LLAMA_CPP_MANIFEST")
    if explicit:
        return [Path(explicit).expanduser().resolve()]
    root = Path(data_root) if data_root is not None else data_dir(create=False)
    python_executable = Path(executable) if executable is not None else Path(sys.executable)
    resources = Path(resource_root) if resource_root is not None else None
    repo_root = Path(__file__).resolve().parents[2]
    return _unique([
        root / "runtimes" / "llama.cpp" / "manifest.json",
        *([resources / "llama" / "manifest.json"] if resources else []),
        python_executable.parent / "llama" / "manifest.json",
        python_executable.parent.parent / "llama" / "manifest.json",
        repo_root / "runtime" / "llama" / "manifest.json",
    ])


def discover_manifest_path(**kwargs):
    """Select the first existing manifest, preserving the search contract."""
    candidates = manifest_candidates(**kwargs)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


__all__ = ["discover_manifest_path", "manifest_candidates"]
