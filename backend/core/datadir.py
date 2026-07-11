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
        path = Path(override)
    elif os.environ.get("WRAPPER_RUNTIME") == "docker":
        path = _REPO_ROOT / "data"
    else:
        local_app_data = os.environ.get("LOCALAPPDATA")
        path = (Path(local_app_data) / "Rasputin" / "data") if local_app_data else (_REPO_ROOT / "data")
    # The native default (%LOCALAPPDATA%\Rasputin\data) is nested, so its parent
    # may not exist on a fresh machine. Ensure the full path -- callers rely on
    # data_dir() returning a directory they can immediately write to. parents=True
    # is the fix for the old single-level `mkdir(exist_ok=True)` assumption.
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path
