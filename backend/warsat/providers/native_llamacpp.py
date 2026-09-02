"""Native llama.cpp process lifecycle for the Rasputin Desktop build.

This provider deliberately speaks the same local OpenAI-compatible contract as
the Docker llama.cpp provider, but owns a host ``llama-server`` process instead
of creating a container.  The state file lets the desktop backend recover and
report a process that was left behind by a restart.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import threading
from functools import cache, lru_cache

import psutil
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from backend.core.datadir import data_dir
from backend.core.response import AppError
from backend.runtime.runtime_service import LlamaCppRuntimeService
from backend.runtime.bootstrap import discover_manifest_path
from backend.models.load_profiles import LoadProfileError, ResolvedLoadPlan, build_command, resolve_load_plan
from .base import DeploymentProvider


NATIVE_RUNTIME = "native-llamacpp"
_WARMUP_TIMEOUT = 120.0
_START_TIMEOUT = max(5.0, min(float(os.environ.get("RASPUTIN_LLAMA_START_TIMEOUT", "45")), 180.0))


def _runtime_dir():
    path = data_dir() / "llama.cpp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_key(model):
    return str(model.get("key") or "model").replace("/", "_").replace("\\", "_")


def _state_path(model):
    return _runtime_dir() / f"{_safe_key(model)}.json"


def _log_path(model):
    return _runtime_dir() / f"{_safe_key(model)}.log"


def _read_state(model):
    try:
        payload = json.loads(_state_path(model).read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(model, payload):
    path = _state_path(model)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _pid_alive(pid):
    try:
        process = psutil.Process(int(pid))
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (TypeError, ValueError, psutil.Error):
        return False


def _owned_process(state):
    """Never adopt or stop a reused PID from a stale runtime state file."""
    try:
        process = psutil.Process(int(state.get("pid")))
        if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
            return None
        created = state.get("processCreatedAt")
        if created is not None and abs(process.create_time() - float(created)) > 0.01:
            return None
        command = state.get("command")
        if not command or process.cmdline() != command:
            return None
        if os.path.normcase(os.path.realpath(process.exe())) != os.path.normcase(os.path.realpath(state.get("engine") or command[0])):
            return None
        return process
    except (TypeError, ValueError, OSError, psutil.Error):
        return None


@cache
def _lifecycle_lock(state_path):
    return threading.RLock()


def _port_available(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def _desktop_only():
    return str(os.environ.get("RASPUTIN_DESKTOP_ONLY", "")).strip().lower() in {"1", "true", "yes", "on"}


def _model_accelerator(model):
    snapshot = model.get("hardware_snapshot") if isinstance(model, Mapping) else {}
    devices = (snapshot or {}).get("devices") or (snapshot or {}).get("gpus") or []
    if any(
        str(device.get("vendor") or "").lower() == "nvidia"
        or any(token in str(device.get("name") or "").lower() for token in ("nvidia", "geforce", "rtx", "quadro", "tesla"))
        or device.get("compute_capability")
        for device in devices if isinstance(device, Mapping)
    ):
        return "cuda"
    if shutil.which("nvidia-smi"):
        return "cuda"
    return "cpu"


def _find_engine(model):
    configured = str(model.get("engine_path") or os.environ.get("RASPUTIN_LLAMA_SERVER") or "").strip()
    accelerator = _model_accelerator(model)
    service = LlamaCppRuntimeService(manifest_path=discover_manifest_path())
    if _desktop_only():
        return str(service.ensure_local_runtime().get("engine_path") or "")
    try:
        managed = service.active_engine_path(required=False, accelerator=accelerator)
    except (AppError, OSError, ValueError, TypeError):
        managed = ""
    candidates = [configured] if configured else []
    if managed:
        candidates.append(managed)
    bundled_root = str(os.environ.get("RASPUTIN_LLAMA_BUNDLED_DIR") or "").strip()
    if bundled_root:
        candidates.append(str(Path(bundled_root) / "llama-server.exe"))
    candidates.extend([
        str(Path(sys.executable).resolve().parent / "llama" / "llama-server.exe"),
        str(Path(sys.executable).resolve().parent / "llama-server.exe"),
        str(Path(__file__).resolve().parents[3] / "runtime" / "llama" / "llama-server.exe"),
        "llama-server",
        "llama-server.exe",
    ])
    for candidate in candidates:
        resolved = shutil.which(candidate) if not Path(candidate).is_file() else candidate
        if resolved:
            return str(Path(resolved).expanduser().resolve())
    return ""


@lru_cache(maxsize=8)
def _engine_capabilities(engine, modified_ns):
    try:
        result = subprocess.run(
            [engine, "--help"], capture_output=True, text=True, errors="replace",
            timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if result.returncode != 0:
        return {}
    help_text = result.stdout + "\n" + result.stderr
    flags = ("--fit", "--fit-target", "--fit-ctx", "--split-mode", "--tensor-split", "--cpu-moe", "--n-cpu-moe")
    return {"flags": {flag: flag in help_text.split() for flag in flags}}


def native_runtime_capabilities(model=None):
    """Probe the selected local binary once per version, without loading a model."""
    engine = _find_engine(model or {})
    if not engine:
        return {}
    try:
        modified_ns = Path(engine).stat().st_mtime_ns
    except OSError:
        return {}
    return _engine_capabilities(engine, modified_ns)


def _health_url(model):
    base = str(model.get("base_url") or "").rstrip("/")
    return base.rsplit("/v1", 1)[0] + "/health" if "/v1" in base else base + "/health"


def _health(model, timeout=1.5):
    url = _health_url(model)
    if not url:
        return False
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def _warm_up(model):
    """Exercise prompt and decode kernels before exposing a newly loaded model.

    This is synthetic runtime work, never a user task or chat message. Use the
    owned listener rather than a configurable URL, and bound both token counts
    and the request timeout. Disable prior prompt-cache reuse for this request.
    """
    context = max(32, int(model.get("context") or 4096))
    words = min(256, context // 4)
    payload = {
        "prompt": "warm " * words,
        "n_predict": 2,
        "ignore_eos": True,
        "temperature": 0,
        "stream": False,
        "cache_prompt": False,
    }
    request = urllib.request.Request(
        f"http://127.0.0.1:{int(model.get('port') or 8081)}/completion",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=_WARMUP_TIMEOUT) as response:
        data = json.loads(response.read(1024 * 1024))
    if not isinstance(data, dict) or data.get("error") or not data.get("tokens_predicted"):
        raise ValueError("The native runtime did not complete its warm-up prediction.")
    return {"status": "complete", "seconds": round(time.monotonic() - started, 3)}


def _terminate(pid, *, state=None):
    process = _owned_process(state or {})
    if process is None:
        return
    # psutil tracks process creation time, including during forceful recovery.
    # A PID alone is insufficient because the OS can reuse it after a restart.
    try:
        children = process.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    try:
        process.terminate()
    except psutil.NoSuchProcess:
        pass
    _, alive = psutil.wait_procs([*children, process], timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    _, remaining = psutil.wait_procs(alive, timeout=3)
    if remaining:
        raise OSError("The owned llama-server process could not be stopped; retry Stop before loading again.")


def _failure(code, message, guidance, *, status="failed", **extra):
    result = {"ok": False, "status": status, "failureCode": code, "error": message, "recoveryGuidance": guidance}
    result.update(extra)
    return result


def _classify_failure(text):
    lowered = str(text or "").lower()
    if any(token in lowered for token in ("unknown argument", "unrecognized option", "unsupported", "invalid option")):
        return "unsupported_flag", "Refresh runtime capabilities or remove the unsupported load-profile setting."
    if any(token in lowered for token in ("out of memory", "oom", "not enough memory", "failed to allocate")):
        return "load_oom", "Reduce context, GPU layers, or parallel slots, then retry with a fresh load plan."
    if any(token in lowered for token in ("corrupt", "invalid gguf", "bad gguf", "gguf magic", "failed to load model")):
        return "model_corrupt", "Re-download or replace the GGUF artifact and verify its checksum before retrying."
    return "process_crash", "Inspect the native llama.cpp log, verify the executable and model paths, then retry."


def _failure_from_text(text, message=None, **extra):
    code, guidance = _classify_failure(text)
    return _failure(code, message or str(text), guidance, **extra)


class NativeLlamaCppProvider(DeploymentProvider):
    """Own one host llama-server process per registered GGUF model."""

    def __init__(
        self,
        *,
        hardware_snapshot: Mapping[str, Any] | Callable[..., Mapping[str, Any]] | None = None,
        runtime_capabilities: Mapping[str, Any] | Callable[..., Mapping[str, Any]] | None = None,
        hardware_snapshot_provider: Callable[..., Mapping[str, Any]] | None = None,
        runtime_capabilities_provider: Callable[..., Mapping[str, Any]] | None = None,
        capabilities_provider: Callable[..., Mapping[str, Any]] | None = None,
    ):
        # Production callers can inject current probes, while tests and desktop
        # model records can provide immutable snapshots on the model itself.
        self._hardware_snapshot = hardware_snapshot
        self._runtime_capabilities = runtime_capabilities
        self._hardware_snapshot_provider = hardware_snapshot_provider
        self._runtime_capabilities_provider = runtime_capabilities_provider or capabilities_provider

    @staticmethod
    def _hook_value(hook, model):
        if not callable(hook):
            return hook
        try:
            return hook(model)
        except TypeError:
            return hook()

    def _snapshot(self, model, field, configured, provider):
        value = model.get(field)
        if value is None:
            value = self._hook_value(provider, model)
        if value is None:
            value = self._hook_value(configured, model)
        return dict(value) if isinstance(value, Mapping) else {}

    @staticmethod
    def _profile(model):
        supplied = model.get("load_profile")
        if supplied is None:
            supplied = model.get("profile")
        profile = dict(supplied) if isinstance(supplied, Mapping) else {}

        # Keep the existing flat model fields as a compatibility adapter. An
        # explicit profile wins when it contains either spelling of a field.
        aliases = {
            "context_length": ("context_length", "context"),
            "gpu_layers": ("gpu_layers", "n_gpu_layers"),
            "fit": ("fit",),
            "fit_target": ("fit_target",),
            "fit_ctx": ("fit_ctx",),
            "split_mode": ("split_mode",),
            "tensor_split": ("tensor_split",),
            "main_gpu": ("main_gpu",),
            "kv_offload": ("kv_offload",),
            "cache_type_k": ("cache_type_k",),
            "cache_type_v": ("cache_type_v",),
            "flash_attention": ("flash_attention",),
            "batch_size": ("batch_size",),
            "ubatch_size": ("ubatch_size",),
            "parallel_slots": ("parallel_slots", "parallel"),
            "threads": ("threads",),
            "threads_batch": ("threads_batch",),
            "cpu_moe": ("cpu_moe",),
            "n_cpu_moe": ("n_cpu_moe",),
            "extra_flags": ("extra_flags",),
        }
        for canonical, keys in aliases.items():
            parts = canonical.split("_")
            camel = parts[0] + "".join(part.title() for part in parts[1:])
            if any(key in profile for key in (*keys, camel)):
                continue
            for key in keys:
                if key in model:
                    # Imported artifacts use context=0 as an auto-detect sentinel.
                    # The planner represents automatic context with an omitted value.
                    if canonical == "context_length" and model.get("context_auto") and model[key] in (None, "", 0, "0"):
                        break
                    profile[canonical] = model[key]
                    break

        if "fit" not in profile and "context_auto" in model:
            profile["fit"] = "on" if bool(model.get("context_auto")) else "off"
        return profile

    @staticmethod
    def _planner_model(model):
        planner_model = dict(model)
        for key in ("model_memory", "modelMemory"):
            memory = model.get(key)
            if isinstance(memory, Mapping):
                for memory_key, value in memory.items():
                    planner_model.setdefault(memory_key, value)
        return planner_model

    @staticmethod
    def _model_path(model):
        model_path = Path(str(model.get("host_model_path") or "")).expanduser().resolve()
        if not model_path.is_file() or model_path.suffix.lower() != ".gguf":
            raise AppError("model_file_missing", "The registered GGUF file is missing.", 400)
        return model_path

    @staticmethod
    def _mmproj_path(model):
        metadata = next((model.get(key) for key in ("artifact", "artifact_metadata", "registered_artifact") if isinstance(model.get(key), Mapping)), {})
        value = next((model.get(key) for key in ("mmproj_path", "mmprojPath", "mmproj") if model.get(key)), None)
        if value is None:
            files = metadata.get("mmprojFiles", metadata.get("mmproj_files", []))
            if isinstance(files, (str, Path)):
                value = files
            elif isinstance(files, list) and files:
                item = files[0]
                value = item.get("localPath", item.get("local_path", item.get("path"))) if isinstance(item, Mapping) else item
        if not value:
            return None
        path = Path(str(value)).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".gguf":
            raise AppError("mmproj_file_missing", "The registered mmproj GGUF companion is missing.", 400)
        return path

    def _load_plan(self, model, engine="llama-server", model_path=None):
        path = model_path or self._model_path(model)
        return resolve_load_plan(
            self._profile(model),
            hardware=self._snapshot(model, "hardware_snapshot", self._hardware_snapshot, self._hardware_snapshot_provider),
            model=self._planner_model(model),
            capabilities=self._snapshot(
                model,
                "runtime_capabilities",
                self._runtime_capabilities,
                self._runtime_capabilities_provider,
            ),
            engine=str(engine),
            model_path=str(path),
        )

    @staticmethod
    def _command_for_plan(plan, engine, model_path, port, mmproj_path=None):
        command = build_command(
            plan,
            engine=str(engine),
            model_path=str(model_path),
            prefix=("--host", "127.0.0.1", "--port", str(port)),
        )
        if mmproj_path:
            command.extend(["--mmproj", str(mmproj_path)])
        return command

    @staticmethod
    def _plan_payload(plan: ResolvedLoadPlan, command):
        payload = plan.to_dict()
        payload["command"] = list(command)
        return payload

    @staticmethod
    def _blocked_message(plan):
        reasons = "; ".join(plan.block_reasons) or "no permitted allocation fits"
        return f"Native llama.cpp load plan is blocked: {reasons}. Supply a fresh hardware/runtime snapshot or adjust the load profile."

    def _command(self, model, engine):
        model_path = self._model_path(model)
        mmproj_path = self._mmproj_path(model)
        port = int(model.get("port") or 8081)
        plan = self._load_plan(model, engine=engine, model_path=model_path)
        if plan.blocked:
            raise AppError("model_load_blocked", self._blocked_message(plan), 409)
        return self._command_for_plan(plan, engine, model_path, port, self._mmproj_path(model))

    def start(self, model):
        with _lifecycle_lock(str(_state_path(model))):
            return self._start(model)

    def _start(self, model):
        if model.get("runtime") != NATIVE_RUNTIME:
            return {"ok": False, "message": "This provider only starts native llama.cpp models."}
        if self.status(model) == "running":
            return {"ok": True, "status": "running", "message": "already running"}
        try:
            model_path = self._model_path(model)
            mmproj_path = self._mmproj_path(model)
            port = int(model.get("port") or 8081)
            plan = self._load_plan(model, model_path=model_path)
        except AppError as exc:
            return _failure(exc.code, str(exc), "Fix the registered artifact or load-plan inputs, then retry.")
        except (LoadProfileError, ValueError, TypeError) as exc:
            return _failure("unsupported_flag" if "flag" in str(exc).lower() else "load_plan_invalid", str(exc), "Refresh runtime capabilities or correct the load profile, then retry.")
        if plan.blocked:
            plan_payload = self._plan_payload(plan, [])
            return _failure("model_load_blocked", self._blocked_message(plan), "Supply a fresh hardware/runtime snapshot or adjust the load profile.", status="blocked", blockReasons=list(plan.block_reasons), resolvedPlan=plan_payload, command=[])
        try:
            engine = _find_engine(model)
        except AppError as exc:
            return _failure(
                exc.code,
                str(exc),
                "Check the internet connection and retry Load. Rasputin downloads only the runtime selected for this hardware.",
                status="unavailable",
                resolvedPlan=self._plan_payload(plan, []),
            )
        if not engine:
            if _desktop_only():
                return _failure(
                    "runtime_unavailable",
                    "A compatible llama.cpp runtime is not installed.",
                    "Check the internet connection and retry Load so Rasputin can download the runtime selected for this hardware.",
                    status="unavailable",
                    resolvedPlan=self._plan_payload(plan, []),
                )
            return _failure("missing_runtime", "llama-server was not found. Install llama.cpp or set RASPUTIN_LLAMA_SERVER to llama-server.exe.", "Set RASPUTIN_LLAMA_SERVER to a valid llama-server executable and retry.", status="unavailable", resolvedPlan=self._plan_payload(plan, []))
        stopped = self.stop(model)
        if not stopped.get("ok"):
            return stopped
        if not _port_available(port):
            return _failure("port_in_use", f"Port {port} is already in use by another process.", "Choose another model port or stop the application using that port, then retry.")
        command = self._command_for_plan(plan, engine, model_path, port, mmproj_path)
        plan_payload = self._plan_payload(plan, command)
        log_path = _log_path(model)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a", encoding="utf-8", errors="replace")
        log_handle.write(f"\n--- native llama.cpp start {time.strftime('%Y-%m-%dT%H:%M:%S%z')} ---\n")
        log_handle.write("$ " + " ".join(command) + "\n")
        log_handle.flush()
        # Keep console interrupts scoped to llama-server. Without a new Windows process group, Ctrl+C from a shared console can reach the desktop/backend process that launched this provider.
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log_handle, stderr=subprocess.STDOUT, close_fds=True, start_new_session=os.name != "nt", creationflags=creationflags)
        except OSError as exc:
            log_handle.close()
            return _failure("missing_runtime", str(exc), "Verify the executable path and permissions, then retry.", command=command, resolvedPlan=plan_payload)
        log_handle.close()
        state = {"pid": process.pid, "command": command, "engine": engine, "logPath": str(log_path), "startedAt": time.time(), "resolvedPlan": plan_payload, "startupStage": "loading"}
        try:
            state["processCreatedAt"] = psutil.Process(process.pid).create_time()
        except psutil.Error:
            pass
        _write_state(model, state)
        deadline = time.monotonic() + _START_TIMEOUT
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self.stop(model)
                log_text = self.logs(model, limit=40).get("logs", "")
                return _failure_from_text(log_text, f"llama-server exited with code {process.returncode}.", command=command, logPath=str(log_path), resolvedPlan=plan_payload)
            if _health(model, timeout=1.0):
                state["startupStage"] = "warming"
                _write_state(model, state)
                try:
                    state["warmup"] = _warm_up({**model, "context": plan.resolved_settings.get("context_length", model.get("context"))})
                except (OSError, ValueError, urllib.error.URLError) as exc:
                    self.stop(model)
                    return _failure("warmup_failed", f"The model loaded but its warm-up failed: {exc}", "Check the native runtime log and available memory, then retry Load.", command=command, logPath=str(log_path), resolvedPlan=plan_payload)
                state["startupStage"] = "ready"
                _write_state(model, state)
                return {"ok": True, "status": "running", "pid": process.pid, "command": command, "logPath": str(log_path), "resolvedPlan": plan_payload, "warmup": state["warmup"]}
            time.sleep(0.25)
        self.stop(model)
        return _failure("health_timeout", f"llama-server did not become healthy within {_START_TIMEOUT:g} seconds.", "Check the native llama.cpp log, model fit, and port availability, then retry.", command=command, logPath=str(log_path), resolvedPlan=plan_payload)

    def stop(self, model):
        with _lifecycle_lock(str(_state_path(model))):
            return self._stop(model)

    def _stop(self, model):
        state = _read_state(model)
        pid = state.get("pid")
        try:
            _terminate(pid, state=state)
        except (OSError, psutil.Error) as exc:
            return _failure("stop_failed", str(exc), "Retry Stop and check the native process before loading another model.", pid=pid)
        try:
            _state_path(model).unlink()
        except OSError:
            pass
        return {"ok": True, "status": "stopped", "pid": pid}

    def rm(self, model):
        self.stop(model)

    def status(self, model):
        if model.get("runtime") != NATIVE_RUNTIME:
            return "external"
        state = _read_state(model)
        pid = state.get("pid")
        if _owned_process(state) is None:
            if state:
                try:
                    _state_path(model).unlink()
                except OSError:
                    pass
            return "stopped"
        if state.get("startupStage") in {"loading", "warming"}:
            return "starting"
        return "running" if _health(model) else "starting"

    def logs(self, model, limit=120):
        path = _log_path(model)
        if not path.exists():
            return {"ok": True, "logs": "", "logPath": str(path)}
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return {"ok": True, "logs": "\n".join(lines[-max(1, min(int(limit), 500)):]), "logPath": str(path)}
        except OSError as exc:
            return {"ok": False, "error": str(exc), "logs": "", "logPath": str(path)}
