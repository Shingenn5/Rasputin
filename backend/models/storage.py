"""Administrator-selected download storage, independent of application state."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from backend.core.datadir import data_dir

_lock = RLock()


def _config(root):
    path = root / "model-storage.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def download_folder(data_root=None):
    root = Path(data_root) if data_root is not None else data_dir()
    with _lock:
        return Path(_config(root).get("downloadFolder") or root / "models")


def library_folders(data_root=None):
    root = Path(data_root) if data_root is not None else data_dir()
    with _lock:
        config = _config(root)
        return list(dict.fromkeys([root / "models", *map(Path, config.get("folders", []))]))


def storage_settings(data_root=None):
    root = Path(data_root) if data_root is not None else data_dir()
    return {"downloadFolder": str(download_folder(root)), "defaultFolder": str(root / "models")}


def set_download_folder(value, data_root=None):
    root = Path(data_root) if data_root is not None else data_dir()
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter an absolute folder path.")
    target = Path(value.strip()).expanduser()
    if not target.is_absolute():
        raise ValueError("Enter an absolute folder path.")
    target = target.resolve()
    if target == Path(target.anchor) or target == Path.home().resolve():
        raise ValueError("Choose a dedicated model folder, rather than a drive root or home folder.")
    # An actual write catches read-only/offline destinations before saving.
    target.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(prefix=".rasputin-write-check-", dir=target):
        pass
    root.mkdir(parents=True, exist_ok=True)
    with _lock:
        folders = list(dict.fromkeys([*map(str, library_folders(root)), str(target)]))
        config = {"downloadFolder": str(target), "folders": folders}
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(config, handle)
            os.replace(temporary, root / "model-storage.json")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return storage_settings(root)
