import os
import time
import uuid
import threading
from pathlib import Path

from huggingface_hub import snapshot_download, model_info

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"

# In-memory store of active downloads
_ACTIVE_DOWNLOADS = {}

def _get_directory_size(path):
    total = 0
    try:
        for p in Path(path).rglob('*'):
            if p.is_file():
                total += p.stat().st_size
    except Exception:
        pass
    return total

def _download_thread(dl_id: str, model_id: str):
    state = _ACTIVE_DOWNLOADS.get(dl_id)
    if not state:
        return
        
    try:
        state["status"] = "fetching_metadata"
        info = model_info(model_id)
        
        # Calculate total size roughly
        total_size = sum(sibling.size for sibling in info.siblings if sibling.size is not None)
        state["totalBytes"] = total_size
        state["status"] = "downloading"
        
        # We start a background thread to poll progress
        stop_polling = threading.Event()
        
        # HuggingFace cache format for this model
        # models/--<repo_type>--<namespace>--<model_name>
        model_cache_name = f"models--{model_id.replace('/', '--')}"
        cache_path = MODELS_DIR / model_cache_name
        
        def poll_progress():
            while not stop_polling.is_set():
                current_size = _get_directory_size(cache_path)
                state["downloadedBytes"] = current_size
                if total_size > 0:
                    state["progress"] = min(100.0, (current_size / total_size) * 100.0)
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
            state["progress"] = 100.0
            if total_size > 0:
                state["downloadedBytes"] = total_size
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
        "progress": 0.0,
        "downloadedBytes": 0,
        "totalBytes": 0,
        "error": None
    }
    _ACTIVE_DOWNLOADS[dl_id] = state
    
    t = threading.Thread(target=_download_thread, args=(dl_id, model_id), daemon=True)
    t.start()
    return state

def get_active_downloads():
    return list(_ACTIVE_DOWNLOADS.values())
