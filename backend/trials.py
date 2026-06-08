import asyncio
import json
import time
from pathlib import Path
from threading import Lock

from . import models
from . import model_registry
from . import runtime_store as store

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TRIALS_FILE = DATA_DIR / "trials.json"
_lock = Lock()


def _blank():
    return {"runs": []}


def _load():
    DATA_DIR.mkdir(exist_ok=True)
    if not TRIALS_FILE.exists():
        TRIALS_FILE.write_text(json.dumps(_blank(), indent=2), encoding="utf-8")
    with _lock:
        try:
            data = json.loads(TRIALS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = _blank()
    if "runs" not in data:
        data = _blank()
    return data


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        TRIALS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _public(run, reveal=False):
    outputs = []
    for item in run.get("outputs", []):
        visible = {k: v for k, v in item.items() if k != "model_key"}
        if reveal or run.get("revealed"):
            visible["modelKey"] = item.get("model_key")
        outputs.append(visible)
    return {**run, "outputs": outputs, "revealed": bool(reveal or run.get("revealed"))}


async def compare(prompt, model_keys=None):
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("trial prompt required")
    chosen = [key for key in (model_keys or []) if model_registry.get_model(key)]
    if not chosen:
        chosen = ["dry-run"]
    chosen = chosen[:4]
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    outputs = []
    for index, key in enumerate(chosen):
        started = time.perf_counter()
        try:
            text = await models.chat(key, [{"role": "user", "content": prompt}], temperature=0.2)
            status = "done"
            error = ""
        except Exception as exc:
            text = ""
            status = "error"
            error = str(exc)
        outputs.append({
            "id": store.new_id("trialout"),
            "label": labels[index],
            "model_key": key,
            "status": status,
            "text": text,
            "error": error,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        })
        await asyncio.sleep(0)
    run = {
        "id": store.new_id("trial"),
        "prompt": prompt,
        "outputs": outputs,
        "revealed": False,
        "created_at": time.time(),
    }
    data = _load()
    data["runs"] = [run] + data.get("runs", [])[:49]
    _save(data)
    return _public(run, reveal=False)


def runs():
    data = _load()
    return {"runs": [_public(item, reveal=False) for item in data.get("runs", [])]}


def reveal(run_id):
    data = _load()
    for item in data.get("runs", []):
        if item.get("id") == run_id:
            item["revealed"] = True
            _save(data)
            return _public(item, reveal=True)
    raise ValueError("trial run missing")
