"""Bounded, local-only LoRA jobs in a separately provisioned training runtime."""
from __future__ import annotations

import json
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid
import zipfile

from backend.core import audit, runtime_store as store
from backend.core.datadir import data_dir
from backend.models import registry

_lock = threading.RLock()
_processes = {}
_KEY = "training_jobs_v1"
_ACTIVE = {"starting", "running", "stopping"}
_WORKER = Path(__file__).with_name("training_worker.py")


def _interpreter():
    configured = os.environ.get("RASPUTIN_TRAINING_PYTHON", "").strip()
    return configured or ("" if getattr(sys, "frozen", False) else sys.executable)


@contextmanager
def inference_slot():
    """Serialize model loading against training admission on this workstation."""
    with _lock:
        if any(j["status"] in _ACTIVE for j in jobs()):
            raise ValueError("Stop the active training run before loading an inference model.")
        yield


def capability():
    executable = _interpreter()
    blockers = []
    if not executable or not Path(executable).is_file():
        blockers.append("A separate training runtime must be provisioned by the maintainer.")
    else:
        probe = """import importlib.util,json
missing=[m for m in ['torch','transformers','peft','trl','datasets','accelerate'] if importlib.util.find_spec(m) is None]
result={'missing':missing,'cuda':False,'error':None}
if not missing:
    try:
        import torch
        from transformers import GPT2Config, GPT2LMHeadModel
        from peft import LoraConfig, get_peft_model
        from trl import SFTConfig, SFTTrainer
        result['cuda']=torch.cuda.is_available()
        tiny=GPT2LMHeadModel(GPT2Config(n_layer=1,n_head=1,n_embd=16,vocab_size=32,n_positions=128))
        get_peft_model(tiny,LoraConfig(r=4,lora_alpha=8,target_modules='all-linear',task_type='CAUSAL_LM'))
        SFTConfig(output_dir='.',max_length=128,dataset_text_field='text',report_to='none',use_cpu=True,bf16=False,fp16=False)
    except Exception as exc:
        result['error']=type(exc).__name__
print(json.dumps(result))
"""
        try:
            result = subprocess.run([executable, "-I", "-B", "-c", probe], capture_output=True, text=True,
                                    timeout=45, env={**os.environ, "HF_HUB_OFFLINE": "1", "PYTHONDONTWRITEBYTECODE": "1"},
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            runtime = json.loads(result.stdout.strip().splitlines()[-1]) if result.returncode == 0 and result.stdout.strip() else None
            if runtime and runtime["missing"]:
                blockers.append("Training runtime is missing: " + ", ".join(runtime["missing"]) + ".")
            elif runtime is None:
                blockers.append("The configured training runtime could not be inspected.")
            elif runtime.get("error"):
                blockers.append(f"Training runtime compatibility check failed ({runtime['error']}). A compatible ML environment is required.")
            elif not runtime["cuda"]:
                blockers.append("Training requires a CUDA-capable GPU and a matching PyTorch runtime.")
        except (OSError, subprocess.TimeoutExpired, ValueError):
            blockers.append("The configured training runtime could not be inspected.")
    return {"ready": not blockers, "blockers": blockers, "method": "LoRA supervised fine-tuning",
            "formats": ["local safetensors Transformers directory"], "cuda_checked_at_start": True,
            "downloads_models": False, "runtime_configured": bool(os.environ.get("RASPUTIN_TRAINING_PYTHON"))}


def jobs():
    with _lock:
        records = store.get_kv(_KEY, [])
        changed = False
        for job in records:
            if job["status"] in _ACTIVE and job["id"] not in _processes:
                job.update(status="interrupted", message="The application stopped before this run completed.", updated_at=store.now())
                changed = True
        if changed:
            store.set_kv(_KEY, records)
        return records


def _update(job_id, **fields):
    with _lock:
        records = store.get_kv(_KEY, [])
        for job in records:
            if job["id"] == job_id:
                job.update(fields, updated_at=store.now())
        store.set_kv(_KEY, records)


def validate_dataset(raw):
    if not raw.strip() or len(raw.encode("utf-8")) > 4 * 1024 * 1024:
        raise ValueError("Provide a nonempty JSONL dataset up to 4 MB.")
    records = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            raise ValueError(f"Dataset line {line_number} is not valid JSON.") from None
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError(f'Dataset line {line_number} needs a nonempty "text" field.')
        records.append({"text": item["text"]})
        if len(records) > 10000:
            raise ValueError("Use at most 10,000 examples per run.")
    if len(records) < 2:
        raise ValueError("Provide at least two training examples.")
    return records


def preflight(model_path, dataset):
    records = validate_dataset(dataset)
    path = Path(model_path).expanduser()
    if not path.is_absolute() or not path.is_dir():
        raise ValueError("Select an absolute local Transformers model directory.")
    if not (path / "config.json").is_file() or not list(path.glob("*.safetensors")):
        raise ValueError("Training requires config.json and safetensors weights. GGUF files cannot be fine-tuned.")
    if not any((path / name).is_file() for name in ("tokenizer.json", "tokenizer.model", "vocab.json")):
        raise ValueError("The local base model directory also needs its original tokenizer files.")
    state = capability()
    if any(m.get("runtime_status") in {"reachable", "starting", "loading", "running"} and m.get("runtime") == "native-llamacpp" for m in registry.all_models()):
        state["blockers"].append("Stop loaded inference models before training to free GPU memory.")
    with _lock:
        if any(j["status"] in _ACTIVE for j in jobs()):
            state["blockers"].append("Another training run is active.")
    state.update(ready=not state["blockers"], examples=len(records))
    return state


def start(owner, config):
    with _lock:
        state = preflight(config["model_path"], config["dataset"])
        if not state["ready"]:
            raise ValueError(" ".join(state["blockers"]))
        job_id = "train_" + uuid.uuid4().hex[:16]
        folder = data_dir() / "training" / job_id
        folder.mkdir(parents=True)
        records = validate_dataset(config["dataset"])
        (folder / "dataset.jsonl").write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        worker_config = {k: v for k, v in config.items() if k != "dataset"}
        worker_config.update(dataset_path=str(folder / "dataset.jsonl"), output_dir=str(folder / "adapter"))
        (folder / "config.json").write_text(json.dumps(worker_config), encoding="utf-8")
        job = {"id": job_id, "name": config["name"], "owner_id": owner, "status": "starting",
               "created_at": store.now(), "updated_at": store.now(), "step": 0,
               "max_steps": config["max_steps"], "examples": len(records), "message": "Checking CUDA and model compatibility."}
        env = {**os.environ, "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "WANDB_DISABLED": "true",
               "RASPUTIN_TRAINING_OWNER_PID": str(os.getpid()),
               "RASPUTIN_TRAINING_CANCEL_FILE": str(folder / "cancel.requested")}
        try:
            process = subprocess.Popen([_interpreter(), "-I", "-B", str(_WORKER), str(folder / "config.json")],
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                       env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError:
            raise ValueError("Training worker could not start in the configured runtime.") from None
        _processes[job_id] = process
        store.set_kv(_KEY, [job, *jobs()][:100])
        threading.Thread(target=_watch, args=(job_id, process), daemon=True).start()
        audit.log("training_started", {"id": job_id, "owner": owner, "examples": len(records)})
        return job


def _watch(job_id, process):
    completed = False
    try:
        for line in process.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") == "progress":
                with _lock:
                    job = next((j for j in jobs() if j["id"] == job_id), {})
                    if job.get("status") != "stopping":
                        _update(job_id, status="running", step=event.get("step", 0), loss=event.get("loss"), message="Training adapter.")
            elif event.get("event") == "complete":
                completed = True
            elif event.get("event") == "error":
                _update(job_id, message=event.get("message", "Training failed."))
        code = process.wait()
        with _lock:
            job = next((j for j in jobs() if j["id"] == job_id), {})
            stopped = job.get("status") == "stopping"
            _update(job_id, status="cancelled" if stopped else ("completed" if completed and code == 0 else "failed"),
                    **({"message": "Adapter saved in Rasputin's training storage."} if completed and code == 0 else {}))
            _processes.pop(job_id, None)
        audit.log("training_finished", {"id": job_id, "exit_code": code})
    finally:
        process.stdout.close()


def cancel(job_id):
    with _lock:
        process = _processes.get(job_id)
        if not process or process.poll() is not None:
            raise ValueError("No active training worker exists for this run.")
        _update(job_id, status="stopping", message="Stopping training worker.")
        _terminate(job_id, process)
        return {"id": job_id, "status": "stopping"}


def _terminate(job_id, process):
    (data_dir() / "training" / job_id / "cancel.requested").touch()
    if os.name == "nt" and process.poll() is None:
        # Windows venv launchers can own a second Python process. Stop the owned tree.
        result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                                timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode and process.poll() is None:
            process.terminate()
    elif process.poll() is None:
        process.terminate()


def export_adapter(job_id):
    job = next((j for j in jobs() if j["id"] == job_id), None)
    if not job or job["status"] != "completed":
        raise ValueError("Only completed adapters can be exported.")
    folder = data_dir() / "training" / job["id"]
    adapter = folder / "adapter"
    destination = folder / "adapter.zip"
    # Export only trainer-owned adapter/tokenizer files, never source datasets.
    names = {"adapter_config.json", "adapter_model.safetensors", "tokenizer.json", "tokenizer_config.json",
             "special_tokens_map.json", "tokenizer.model", "vocab.json", "merges.txt", "added_tokens.json", "chat_template.jinja"}
    with _lock:
        if not destination.exists():
            temporary = folder / "adapter-export.partial"
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in adapter.iterdir():
                    if path.name in names and path.is_file() and not path.is_symlink():
                        archive.write(path, path.name)
            temporary.replace(destination)
    return destination


def shutdown():
    with _lock:
        processes = list(_processes.items())
        for job_id, process in processes:
            if process.poll() is None:
                _update(job_id, status="stopping", message="Application shutdown stopped this run.")
                _terminate(job_id, process)
    for _, process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
