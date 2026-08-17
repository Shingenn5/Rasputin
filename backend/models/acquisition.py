import os
import time
import uuid
import threading
import math
from pathlib import Path

from huggingface_hub import snapshot_download, model_info

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"

# In-memory store of active downloads
_ACTIVE_DOWNLOADS = {}

def _get_directory_size(path):
    """Count unique downloaded bytes without counting snapshot links twice."""
    root = Path(path)
    if not root.exists():
        return 0
    try:
        # Hugging Face stores content-addressed bytes under blobs and exposes
        # them again through snapshots. Only scan blobs when that directory
        # exists; the fallback is useful for a simple test/cache directory and
        # still de-duplicates hard links.
        blob_root = root / "blobs"
        scan_root = blob_root if blob_root.is_dir() else root
        total = 0
        seen = set()
        for item in scan_root.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            stat = item.stat()
            identity = (stat.st_dev, stat.st_ino) if stat.st_ino else str(item.resolve())
            if identity in seen:
                continue
            seen.add(identity)
            total += stat.st_size
        return total
    except (OSError, RuntimeError):
        # A transient cache race or permission failure is not evidence of a
        # smaller download. The caller will retain byte telemetry but withhold
        # the percentage until a complete scan succeeds.
        return None


def _trusted_progress(downloaded_bytes, total_bytes):
    """Return a percentage only when the byte bounds make it trustworthy."""
    if isinstance(downloaded_bytes, bool) or isinstance(total_bytes, bool):
        return None
    try:
        downloaded = float(downloaded_bytes)
        total = float(total_bytes)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(downloaded) or not math.isfinite(total):
        return None
    if total <= 0 or downloaded < 0 or downloaded > total:
        return None
    return round(downloaded / total * 100.0, 2)


def _known_total_bytes(info):
    """Return a positive total only when every Hub sibling has a valid size."""
    siblings = getattr(info, "siblings", None)
    if not siblings:
        return None
    total = 0
    for sibling in siblings:
        size = getattr(sibling, "size", None)
        if isinstance(size, bool):
            return None
        try:
            numeric_size = float(size)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric_size) or numeric_size < 0 or not numeric_size.is_integer():
            return None
        total += int(numeric_size)
    return total if total > 0 else None


def _completed_progress(total_bytes, downloaded_bytes):
    """Normalize a confirmed completion without inventing an unknown total."""
    if _trusted_progress(0, total_bytes) is not None:
        return total_bytes, 100.0, True
    try:
        observed = max(0, int(downloaded_bytes or 0))
    except (TypeError, ValueError):
        observed = 0
    return observed, None, False

def _download_thread(dl_id: str, model_id: str):
    state = _ACTIVE_DOWNLOADS.get(dl_id)
    if not state:
        return
        
    try:
        state["status"] = "fetching_metadata"
        info = model_info(model_id)
        
        # A partial sum is not a trustworthy total: one missing sibling size
        # means the Hub metadata is incomplete and the UI must withhold a bar.
        total_size = _known_total_bytes(info)
        state["totalBytes"] = total_size
        state["status"] = "downloading"
        state["progress"] = None
        state["progressTrusted"] = False
        
        # We start a background thread to poll progress
        stop_polling = threading.Event()
        
        # HuggingFace cache format for this model
        # models/--<repo_type>--<namespace>--<model_name>
        model_cache_name = f"models--{model_id.replace('/', '--')}"
        cache_path = MODELS_DIR / model_cache_name
        
        def poll_progress():
            while not stop_polling.is_set():
                current_size = _get_directory_size(cache_path)
                if current_size is not None:
                    state["downloadedBytes"] = current_size
                state["progress"] = _trusted_progress(current_size, total_size)
                state["progressTrusted"] = state["progress"] is not None
                time.sleep(1.0)
                
        poller = threading.Thread(target=poll_progress, daemon=True)
        poller.start()
        
        try:
            snapshot_download(
                repo_id=model_id,
                cache_dir=str(MODELS_DIR),
                local_files_only=False,
                resume_download=True
            )
            state["status"] = "completed"
            observed_size = _get_directory_size(cache_path)
            state["downloadedBytes"], state["progress"], state["progressTrusted"] = _completed_progress(
                total_size,
                observed_size,
            )
            
            # Post-Acquisition Pipeline: Auto-register model for WarSat deployment
            try:
                from backend.models import registry
                
                # Deduce protocol
                has_gguf = any(s.rfilename and s.rfilename.endswith(".gguf") for s in info.siblings)
                protocol = "llamaCppGgufServer" if has_gguf else "vllmCudaOpenai"
                
                # Create a safe registry key from the model ID
                model_name = model_id.split("/")[-1]
                safe_key = model_name.lower().replace(".", "-").replace("_", "-")
                
                new_model = {
                    "key": safe_key,
                    "name": model_name,
                    "model": model_id,
                    "role": "helper",
                    "provider": "openai-compatible",
                    "base_url": "http://host.docker.internal:8000/v1",  # Placeholder until deployed
                    "managed": True,
                    "enabled": False,  # Disabled by default until deployed
                    "warsatProtocol": protocol,
                    "warsatModelRef": model_id
                }
                
                registry.upsert(new_model)
            except Exception as e:
                # We log it but don't fail the download state if registration fails
                print(f"[WarSat] Failed to auto-register model: {e}")
                
        finally:
            stop_polling.set()
            poller.join(timeout=2.0)
            
    except Exception as e:
        state["status"] = "failed"
        state["error"] = str(e)

def start_download(model_id: str):
    # Check if already downloading
    for dl in _ACTIVE_DOWNLOADS.values():
        if dl["modelId"] == model_id and dl["status"] in ["starting", "fetching_metadata", "downloading"]:
            return dl
            
    dl_id = str(uuid.uuid4())
    state = {
        "id": dl_id,
        "modelId": model_id,
        "status": "starting",
        "progress": None,
        "downloadedBytes": 0,
        "totalBytes": None,
        "progressTrusted": False,
        "error": None
    }
    _ACTIVE_DOWNLOADS[dl_id] = state
    
    t = threading.Thread(target=_download_thread, args=(dl_id, model_id), daemon=True)
    t.start()
    return state

def get_active_downloads():
    return list(_ACTIVE_DOWNLOADS.values())
