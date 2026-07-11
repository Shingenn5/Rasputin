"""Single source of truth for Rasputin's data directory.

Resolution order:
  1. RASPUTIN_DATA_DIR   -- explicit override (tests, dev, server operators)
  2. WRAPPER_RUNTIME=docker -> <repo>/data  (the compose-mounted named volume)
  3. Native default      -> %LOCALAPPDATA%\\Rasputin\\data  (keeps runtime state
                            out of the repo and off any bind mount)
  4. Fallback            -> <repo>/data

Resolved once at import time by callers that assign `DATA_DIR = data_dir()`,
matching the existing module-level snapshot semantics.
"""
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    override = os.environ.get("RASPUTIN_DATA_DIR")
    if override:
        return Path(override)
    if os.environ.get("WRAPPER_RUNTIME") == "docker":
        return _REPO_ROOT / "data"
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Rasputin" / "data"
    return _REPO_ROOT / "data"
