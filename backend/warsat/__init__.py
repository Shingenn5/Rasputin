import json
import os
import platform
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from backend.core import approvals
from backend.core import audit
from backend.core import runtime_store as store
from backend.models import registry as model_registry
from backend.core import security
from backend.core.response import AppError

ROOT = Path(__file__).resolve().parents[2]
BUILTIN_PROTOCOL_DIR = ROOT / "backend" / "warsat" / "protocols"
DATA_DIR = ROOT / "data" / "warsat"
USER_PROTOCOL_DIR = DATA_DIR / "protocols"
MODELS_DIR = ROOT / "models"
DEPLOY_TIMEOUT_SECONDS = int(os.environ.get("WARSAT_DEPLOY_TIMEOUT", "1800"))
HEALTH_PROBE_ATTEMPTS = max(1, min(int(os.environ.get("WARSAT_HEALTH_PROBE_ATTEMPTS", "6")), 30))
HEALTH_PROBE_INTERVAL_SECONDS = max(0.0, min(float(os.environ.get("WARSAT_HEALTH_PROBE_INTERVAL", "5")), 30.0))
HEALTH_PROBE_TIMEOUT_SECONDS = max(1.0, min(float(os.environ.get("WARSAT_HEALTH_PROBE_TIMEOUT", "5")), 30.0))
LOG_LIMIT_MAX = 500

DEPLOY_PHASES = [
    ("planned", "Plan reviewed", "Launch plan generated and validated."),
    ("approvalPending", "Approval", "Deployment requires a one-time local approval."),
    ("pulling", "Pull image", "Docker image pull is running."),
    ("starting", "Start container", "Warsat is replacing any old container and starting the new runtime."),
    ("probing", "Probe health", "Warsat is checking the local model endpoint."),
    ("registered", "Register model", "The healthy endpoint is saved in the model registry."),
]

STRENGTH_PROFILES = {
    "cpu": {
        "label": "CPU safe",
        "description": "Slow but predictable fallback for testing without GPU pressure.",
        "contextWindow": 2048,
        "maxModelLen": 4096,
        "gpuMemoryUtilization": 0.0,
        "gpuLayers": 0,
        "batchSize": 256,
        "maxNumSeqs": 8,
    },
    "small": {
        "label": "Low VRAM",
        "description": "Lower memory use for helper models or constrained GPUs.",
        "contextWindow": 2048,
        "maxModelLen": 4096,
        "gpuMemoryUtilization": 0.72,
        "gpuLayers": 0,
        "batchSize": 512,
        "maxNumSeqs": 16,
    },
    "balanced": {
        "label": "Balanced",
        "description": "Default testing profile for normal local work.",
        "contextWindow": 4096,
        "maxModelLen": 8192,
        "gpuMemoryUtilization": 0.82,
        "gpuLayers": None,
        "batchSize": 768,
        "maxNumSeqs": 32,
    },
    "throughput": {
        "label": "Throughput",
        "description": "Higher batching for serving more parallel local requests.",
        "contextWindow": 4096,
        "maxModelLen": 8192,
        "gpuMemoryUtilization": 0.88,
        "gpuLayers": None,
        "batchSize": 1024,
        "maxNumSeqs": 64,
    },
    "long-context": {
        "label": "Long context",
        "description": "Prioritizes context length over raw throughput.",
        "contextWindow": 8192,
        "maxModelLen": 32768,
        "gpuMemoryUtilization": 0.86,
        "gpuLayers": 999,
        "batchSize": 512,
        "maxNumSeqs": 16,
    },
    "large": {
        "label": "Large",
        "description": "Higher context and GPU use for stronger main runtimes.",
        "contextWindow": 8192,
        "maxModelLen": 16384,
        "gpuMemoryUtilization": 0.90,
        "gpuLayers": 999,
        "batchSize": 1024,
        "maxNumSeqs": 32,
    },
}

DTYPE_CHOICES = {"auto", "float16", "half", "bfloat16", "float32"}
KV_CACHE_CHOICES = {"auto", "fp8", "fp8_e5m2", "fp8_e4m3"}
QUANTIZATION_CHOICES = {"", "awq", "gptq", "fp8", "bitsandbytes"}


def _truthy_env(name):
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _fake_deploy_enabled():
    if not _truthy_env("RASPUTIN_WARSAT_FAKE_DEPLOY"):
        return False
    env = str(os.environ.get("RASPUTIN_ENV", "")).strip().lower()
    return env in {"test", "gui-test", "ci"} or _truthy_env("RASPUTIN_TEST_AUTH_BYPASS")


def _slug(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "")).strip("-").lower() or "warsat-model"


def _model_label_for_container(model_ref, model_path):
    # container names built from the protocol id + port ("rasputin-
    # llamacppggufserver-8081") give no hint which model is inside once you
    # have more than one running -- prefer the model itself when we know it.
    base = ""
    if model_ref:
        base = str(model_ref).split("/")[-1]
    elif model_path:
        base = Path(str(model_path)).stem
    return base[:60]


def _safe_protocol_id(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "", str(value or "")).strip(".-") or "warsatProtocol"


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AppError("warsat_protocol_invalid", f"{path.name} is not valid JSON: {exc}", 400)


def _protocol_files():
    files = []
    for folder in [BUILTIN_PROTOCOL_DIR, USER_PROTOCOL_DIR]:
        if folder.exists():
            files.extend(sorted(folder.glob("*.json")))
    return files


def _docker_cli_path():
    if _fake_deploy_enabled():
        return "docker-test-double"
    return shutil.which("docker")


def _docker_runtime_enabled():
    cfg = security.load()
    if not cfg.get("allow_docker_control", False):
        return {
            "enabled": False,
            "dockerControlEnabled": False,
            "dockerCliAvailable": bool(_docker_cli_path()),
            "message": "Docker control is disabled in Safety settings.",
        }
    if not _docker_cli_path():
        return {
            "enabled": False,
            "dockerControlEnabled": True,
            "dockerCliAvailable": False,
            "message": "Docker control is enabled, but the Docker CLI is not available inside this Rasputin runtime. Restart with the docker-control compose overlay.",
        }
    return {
        "enabled": True,
        "dockerControlEnabled": True,
        "dockerCliAvailable": True,
        "message": "Warsat can pull images and start containers after you create a launch plan.",
    }


def _normalize_protocol(protocol, source="builtin"):
    required = ["id", "name", "runtime", "image", "modelFormat", "defaultHostPort", "containerPort"]
    missing = [key for key in required if not protocol.get(key)]
    if missing:
        raise AppError("warsat_protocol_invalid", f"Protocol {protocol.get('id') or 'unknown'} is missing: {', '.join(missing)}", 400)
    security_config = protocol.get("security") or {}
    return {
        **protocol,
        "id": _safe_protocol_id(protocol["id"]),
        "source": source,
        "capabilities": list(protocol.get("capabilities") or []),
        "notes": list(protocol.get("notes") or []),
        "defaultRole": protocol.get("defaultRole") or "helper",
        "hostBinding": security_config.get("hostBinding") or "127.0.0.1",
        "noNewPrivileges": bool(security_config.get("noNewPrivileges", True)),
        "hostNetwork": bool(security_config.get("hostNetwork", False)),
    }


def list_protocols():
    protocols = []
    seen = set()
    for path in _protocol_files():
        source = "user" if USER_PROTOCOL_DIR in path.parents else "builtin"
        protocol = _normalize_protocol(_read_json(path), source)
        if protocol["id"] in seen:
            continue
        seen.add(protocol["id"])
        protocols.append(protocol)
    protocols.sort(key=lambda item: (item.get("runtime", ""), item.get("name", "")))
    execution = _docker_runtime_enabled()
    message = execution["message"]
    if not execution["enabled"]:
        message = f"Warsat is in safe planning mode. {message}"
    return {
        "protocols": protocols,
        "count": len(protocols),
        "strengthProfiles": STRENGTH_PROFILES,
        "dockerControlEnabled": execution["dockerControlEnabled"],
        "dockerCliAvailable": execution["dockerCliAvailable"],
        "executionEnabled": execution["enabled"],
        "message": message,
    }


def summary():
    data = list_protocols()
    return {
        "count": data["count"],
        "dockerControlEnabled": data["dockerControlEnabled"],
        "executionEnabled": data["executionEnabled"],
        "protocols": [
            {
                "id": item["id"],
                "name": item["name"],
                "runtime": item["runtime"],
                "modelFormat": item["modelFormat"],
                "capabilities": item.get("capabilities", []),
            }
            for item in data["protocols"]
        ],
    }


def _probe_command(args, timeout=10):
    if _fake_deploy_enabled() and isinstance(args, list) and args and args[0] == "docker":
        if args[:2] == ["docker", "version"]:
            return {
                "available": True,
                "ok": True,
                "returnCode": 0,
                "stdout": json.dumps({
                    "Client": {"Version": "test-double"},
                    "Server": {"Version": "test-double"},
                }),
                "stderr": "",
                "latencyMs": 1,
            }
        if args[:2] == ["docker", "info"]:
            return {
                "available": True,
                "ok": True,
                "returnCode": 0,
                "stdout": json.dumps({
                    "Runtimes": {"runc": {}, "nvidia": {}},
                    "OSType": "linux",
                    "Architecture": "x86_64",
                }),
                "stderr": "",
                "latencyMs": 1,
            }
        if args[:2] == ["docker", "ps"]:
            return {
                "available": True,
                "ok": True,
                "returnCode": 0,
                "stdout": "",
                "stderr": "",
                "latencyMs": 1,
            }
    started = time.perf_counter()
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {
            "available": True,
            "ok": proc.returncode == 0,
            "returnCode": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
            "latencyMs": round((time.perf_counter() - started) * 1000),
        }
    except FileNotFoundError:
        return {
            "available": False,
            "ok": False,
            "returnCode": None,
            "stdout": "",
            "stderr": "Command is not available in this Rasputin runtime.",
            "latencyMs": round((time.perf_counter() - started) * 1000),
        }
    except subprocess.TimeoutExpired:
        return {
            "available": True,
            "ok": False,
            "returnCode": None,
            "stdout": "",
            "stderr": "Command timed out.",
            "latencyMs": round((time.perf_counter() - started) * 1000),
        }


def _check(check_id, label, status, message, detail=None, next_step=None):
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "ok": status == "pass",
        "message": message,
        "detail": detail or {},
        "nextStep": next_step or "",
    }


def _json_object(text):
    try:
        data = json.loads(text or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _model_mount_state():
    exists = MODELS_DIR.exists()
    files = []
    if exists:
        try:
            files = [
                item.name
                for item in sorted(MODELS_DIR.iterdir(), key=lambda path: path.name.lower())
                if not item.name.startswith(".")
            ][:12]
        except Exception:
            files = []
    status = "pass" if exists else "warn"
    message = "Model folder is visible to Rasputin." if exists else "Model folder is not visible to Rasputin."
    if exists and not files:
        status = "warn"
        message = "Model folder is mounted but currently empty."
    return _check(
        "modelMount",
        "Model Mount",
        status,
        message,
        {"visiblePath": "models", "sample": files, "countShown": len(files)},
        "Mount local model files into ./models or use Hugging Face model ids for vLLM recipes." if status == "warn" else "",
    )


def _docker_info_checks(docker_path, docker_version):
    checks = []
    detected = {}
    if not docker_path:
        checks.append(_check(
            "dockerCli",
            "Docker CLI",
            "block",
            "Docker CLI is not available inside this Rasputin runtime.",
            {},
            "Restart with the docker-control compose overlay if you want Warsat deployment controls.",
        ))
        checks.append(_check(
            "dockerDaemon",
            "Docker Daemon",
            "block",
            "Docker daemon cannot be checked because the CLI is missing.",
            {},
            "Install Docker Desktop or expose Docker CLI/socket to the wrapper only when you want Warsat control.",
        ))
        return checks, detected

    checks.append(_check(
        "dockerCli",
        "Docker CLI",
        "pass",
        "Docker CLI is available to this runtime.",
        {"path": "docker"},
    ))
    version = docker_version.get("Client", {}).get("Version") or docker_version.get("Client", {}).get("Platform", {}).get("Name")
    server_version = docker_version.get("Server", {}).get("Version")
    detected["dockerClientVersion"] = version or ""
    detected["dockerServerVersion"] = server_version or ""
    daemon_ok = bool(server_version)
    checks.append(_check(
        "dockerDaemon",
        "Docker Daemon",
        "pass" if daemon_ok else "block",
        "Docker daemon is reachable." if daemon_ok else "Docker CLI is present, but the daemon is not reachable.",
        {"clientVersion": version or "", "serverVersion": server_version or ""},
        "Start Docker Desktop and ensure the wrapper has Docker socket access." if not daemon_ok else "",
    ))
    return checks, detected


def hardware_probe():
    cfg = security.load()
    docker_path = _docker_cli_path()
    docker_version_raw = _probe_command(["docker", "version", "--format", "{{json .}}"], timeout=10) if docker_path else {"ok": False, "stdout": "", "stderr": ""}
    docker_version = _json_object(docker_version_raw.get("stdout"))
    checks, detected = _docker_info_checks(docker_path, docker_version)

    detected.update({
        "os": platform.system(),
        "platform": platform.platform(),
        "runtime": os.environ.get("WRAPPER_RUNTIME") or "native",
        "insideDocker": os.environ.get("WRAPPER_RUNTIME") == "docker",
    })

    docker_control_enabled = bool(cfg.get("allow_docker_control", False))
    checks.append(_check(
        "dockerControl",
        "Docker Control Permission",
        "pass" if docker_control_enabled else "block",
        "Docker control is enabled in Safety settings." if docker_control_enabled else "Docker control is disabled in Safety settings.",
        {"enabled": docker_control_enabled},
        "Enable Docker control only when you are ready for Rasputin to request approved container actions." if not docker_control_enabled else "",
    ))

    if docker_path and docker_version_raw.get("ok"):
        docker_info_raw = _probe_command(["docker", "info", "--format", "{{json .}}"], timeout=10)
        info = _json_object(docker_info_raw.get("stdout"))
        runtimes = info.get("Runtimes") or {}
        runtime_names = sorted(runtimes.keys()) if isinstance(runtimes, dict) else []
        detected["dockerRuntimes"] = runtime_names
        detected["dockerOSType"] = info.get("OSType") or ""
        detected["dockerArchitecture"] = info.get("Architecture") or ""
        has_nvidia_runtime = "nvidia" in runtime_names
        checks.append(_check(
            "dockerGpuRuntime",
            "Docker GPU Runtime",
            "pass" if has_nvidia_runtime else "warn",
            "Docker reports an NVIDIA runtime." if has_nvidia_runtime else "Docker does not report an NVIDIA runtime.",
            {"runtimes": runtime_names},
            "Install/configure NVIDIA Container Toolkit if you expect GPU acceleration." if not has_nvidia_runtime else "",
        ))
        ps = _probe_command(["docker", "ps", "-a", "--filter", "label=rasputin.managed=true", "--format", "{{json .}}"], timeout=10)
        managed = _parse_json_lines(ps.get("stdout")) if ps.get("ok") else []
        checks.append(_check(
            "managedContainers",
            "Warsat Containers",
            "pass" if ps.get("ok") else "warn",
            f"{len(managed)} Warsat-managed container(s) visible." if ps.get("ok") else "Warsat-managed containers could not be listed.",
            {"count": len(managed)},
            "Check Docker daemon access if managed containers should be visible." if not ps.get("ok") else "",
        ))
    else:
        detected["dockerRuntimes"] = []
        checks.append(_check(
            "dockerGpuRuntime",
            "Docker GPU Runtime",
            "warn",
            "Docker GPU runtime cannot be checked until Docker daemon is reachable.",
            {},
            "Start Docker and expose Docker control to Rasputin before deploying GPU containers.",
        ))
        checks.append(_check(
            "managedContainers",
            "Warsat Containers",
            "warn",
            "Warsat-managed containers cannot be listed until Docker daemon is reachable.",
        ))

    nvidia_smi = shutil.which("nvidia-smi")
    gpus = []
    probed_via_docker = False
    if nvidia_smi:
        gpu_raw = _probe_command([
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ], timeout=10)
        if gpu_raw.get("ok"):
            gpus = _parse_gpu_csv(gpu_raw.get("stdout", ""))
    else:
        gpus = _gpu_probe_via_docker()
        probed_via_docker = bool(gpus)
    detected["gpus"] = gpus
    if gpus:
        checks.append(_check(
            "hostGpu",
            "GPU Visibility",
            "pass",
            f"{len(gpus)} GPU(s) visible to Rasputin" + (" (probed through Docker)." if probed_via_docker else "."),
            {"gpus": gpus},
            "",
        ))
    elif nvidia_smi:
        checks.append(_check(
            "hostGpu",
            "GPU Visibility",
            "warn",
            "nvidia-smi is present, but no GPU details were returned.",
            {},
            "Confirm NVIDIA drivers are installed and available to Docker.",
        ))
    else:
        checks.append(_check(
            "hostGpu",
            "GPU Visibility",
            "warn",
            "nvidia-smi is not available inside this Rasputin runtime, and the Docker GPU probe found nothing.",
            {},
            "CPU deployment can still work. For GPU deployment, expose NVIDIA tools/runtime to the container.",
        ))

    checks.append(_model_mount_state())

    blocked = [item for item in checks if item["status"] == "block"]
    warnings = [item for item in checks if item["status"] == "warn"]
    recommendations = [item["nextStep"] for item in checks if item.get("nextStep")]
    return {
        "ok": not blocked,
        "status": "blocked" if blocked else "warning" if warnings else "ready",
        "checks": checks,
        "warnings": [item["message"] for item in warnings],
        "blockedReasons": [item["message"] for item in blocked],
        "recommendations": recommendations,
        "detectedHardware": detected,
        "generatedAt": time.time(),
    }


def get_protocol(protocol_id):
    protocol_id = _safe_protocol_id(protocol_id)
    for protocol in list_protocols()["protocols"]:
        if protocol["id"] == protocol_id:
            return protocol
    raise AppError("warsat_protocol_missing", "Warsat protocol was not found.", 404)


def _endpoint_for(host_binding, host_port):
    visible_host = "host.docker.internal" if os.environ.get("WRAPPER_RUNTIME") == "docker" else host_binding
    return f"http://{visible_host}:{host_port}/v1"


def _safe_strength(value):
    key = str(value or "balanced").strip().lower()
    return key if key in STRENGTH_PROFILES else "balanced"


def _payload_get(payload, *names, default=None):
    for name in names:
        if name in payload and payload.get(name) not in (None, ""):
            return payload.get(name)
    return default


def _int_value(payload, names, default=None, minimum=None, maximum=None):
    raw = _payload_get(payload, *names, default=default)
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _float_value(payload, names, default=None, minimum=None, maximum=None):
    raw = _payload_get(payload, *names, default=default)
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _choice_value(payload, names, choices, default=""):
    value = str(_payload_get(payload, *names, default=default) or "").strip().lower()
    return value if value in choices else default


def _build_tuning(payload, protocol, strength):
    profile = STRENGTH_PROFILES[_safe_strength(strength)]
    return {
        "contextWindow": _int_value(payload, ["contextWindow", "context_window"], profile["contextWindow"], 512, 262144),
        "maxModelLen": _int_value(payload, ["maxModelLen", "max_model_len"], profile["maxModelLen"], 512, 262144),
        "gpuMemoryUtilization": _float_value(payload, ["gpuMemoryUtilization", "gpu_memory_utilization"], profile["gpuMemoryUtilization"], 0.0, 0.98),
        "gpuLayers": _int_value(payload, ["gpuLayers", "gpu_layers"], profile.get("gpuLayers"), 0, 999),
        "tensorParallelSize": _int_value(payload, ["tensorParallelSize", "tensor_parallel_size"], 1, 1, 16),
        "cpuThreads": _int_value(payload, ["cpuThreads", "cpu_threads"], 0, 0, 256),
        "batchSize": _int_value(payload, ["batchSize", "batch_size"], profile.get("batchSize", 512), 1, 65536),
        "maxNumSeqs": _int_value(payload, ["maxNumSeqs", "max_num_seqs"], profile.get("maxNumSeqs", 32), 1, 4096),
        "dtype": _choice_value(payload, ["dtype"], DTYPE_CHOICES, "auto"),
        "quantization": _choice_value(payload, ["quantization"], QUANTIZATION_CHOICES, ""),
        "kvCacheDtype": _choice_value(payload, ["kvCacheDtype", "kv_cache_dtype"], KV_CACHE_CHOICES, "auto"),
        "swapSpaceGb": _int_value(payload, ["swapSpaceGb", "swap_space_gb"], 0, 0, 1024),
    }


def _build_limits(payload):
    gpu_device = str(_payload_get(payload, "gpuDevice", "gpu_device", default="") or "").strip()
    return {
        "memoryLimitGb": _int_value(payload, ["memoryLimitGb", "memory_limit_gb"], None, 0, 2048),
        "cpuLimit": _float_value(payload, ["cpuLimit", "cpu_limit"], None, 0.0, 256.0),
        "shmSizeGb": _int_value(payload, ["shmSizeGb", "shm_size_gb"], 2, 0, 1024),
        "gpuDevice": gpu_device,
    }


def _uses_gpu(protocol, tuning, limits):
    if protocol.get("gpu", {}).get("required"):
        return True
    gpu_device = str(limits.get("gpuDevice") or "").strip().lower()
    if gpu_device and gpu_device not in {"none", "cpu", "off"}:
        return True
    return bool(tuning.get("gpuLayers"))


HF_API_BASE = os.environ.get("HF_API_URL", "https://huggingface.co/api/models")
_HF_INVENTORY_CACHE = {}
_HF_INVENTORY_TTL_SECONDS = 300

# Mid-size quants first: what people actually run on desktop GPUs/CPUs.
GGUF_QUANT_PREFERENCE = (
    "q4_k_m", "q4_k_s", "q4_k", "q5_k_m", "q5_k", "q4_0",
    "q6_k", "iq4", "q8_0", "q3_k_m", "q3_k", "iq3", "q2_k",
)


def _looks_like_hf_repo(model_ref):
    ref = str(model_ref or "").strip()
    return bool(ref) and "/" in ref and not ref.lower().endswith(".gguf") and not ref.startswith(("/", ".", "\\"))


def _hf_repo_inventory(model_ref):
    """What weight formats a Hugging Face repo actually ships.

    Returns {"ggufFiles": [...], "transformersOk": bool} or None when the Hub
    can't be reached — offline plans keep today's behavior instead of failing.
    """
    if _fake_deploy_enabled() or not _looks_like_hf_repo(model_ref):
        return None
    ref = str(model_ref).strip().strip("/")
    cached = _HF_INVENTORY_CACHE.get(ref.lower())
    if cached and time.time() - cached[0] < _HF_INVENTORY_TTL_SECONDS:
        return cached[1]
    try:
        req = urllib.request.Request(f"{HF_API_BASE}/{ref}", headers={"User-Agent": "rasputin-warsat/0.1"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read(2_000_000).decode("utf-8", "replace"))
    except Exception:
        return None
    files = [str(item.get("rfilename") or "") for item in data.get("siblings") or [] if isinstance(item, dict)]
    lowered = [name.lower() for name in files]
    gguf_files = [
        name for name in files
        if name.lower().endswith(".gguf") and not Path(name).name.lower().startswith("mmproj")
    ]
    has_config = "config.json" in lowered
    has_weights = any(name.endswith((".safetensors", ".bin", ".pt")) for name in lowered)
    inventory = {"ggufFiles": gguf_files, "transformersOk": has_config and has_weights}
    _HF_INVENTORY_CACHE[ref.lower()] = (time.time(), inventory)
    return inventory


def _pick_gguf_file(gguf_files):
    ranked = sorted(gguf_files)
    for quant in GGUF_QUANT_PREFERENCE:
        for name in ranked:
            if quant in name.lower():
                return name
    return ranked[0] if ranked else ""


def _strip_option(args, names):
    names = set(names)
    out = []
    skip = False
    for item in args:
        if skip:
            skip = False
            continue
        if item in names:
            skip = True
            continue
        out.append(item)
    return out


def _runtime_arguments(protocol, tuning):
    args = list(protocol.get("defaultArguments") or [])
    runtime = str(protocol.get("runtime", "")).lower()
    if runtime == "vllm":
        args = _strip_option(args, [
            "--max-model-len", "--gpu-memory-utilization", "--tensor-parallel-size",
            "--dtype", "--quantization", "--kv-cache-dtype", "--max-num-seqs", "--swap-space",
        ])
        args.extend([
            "--max-model-len", str(tuning["maxModelLen"]),
            "--gpu-memory-utilization", str(tuning["gpuMemoryUtilization"]),
        ])
        if tuning.get("tensorParallelSize", 1) > 1:
            args.extend(["--tensor-parallel-size", str(tuning["tensorParallelSize"])])
        if tuning.get("dtype") and tuning["dtype"] != "auto":
            args.extend(["--dtype", tuning["dtype"]])
        if tuning.get("quantization"):
            args.extend(["--quantization", tuning["quantization"]])
        if tuning.get("kvCacheDtype") and tuning["kvCacheDtype"] != "auto":
            args.extend(["--kv-cache-dtype", tuning["kvCacheDtype"]])
        if tuning.get("maxNumSeqs"):
            args.extend(["--max-num-seqs", str(tuning["maxNumSeqs"])])
        if tuning.get("swapSpaceGb"):
            args.extend(["--swap-space", str(tuning["swapSpaceGb"])])
    elif protocol.get("modelFormat") == "gguf":
        args = _strip_option(args, ["-c", "--ctx-size", "--ctx_size", "-ngl", "--n-gpu-layers", "--threads", "-b", "--batch-size", "--parallel"])
        args.extend(["-c", str(tuning["contextWindow"])])
        if tuning.get("gpuLayers") is not None:
            args.extend(["-ngl", str(tuning["gpuLayers"])])
        if tuning.get("cpuThreads"):
            args.extend(["--threads", str(tuning["cpuThreads"])])
        if tuning.get("batchSize"):
            args.extend(["-b", str(tuning["batchSize"])])
        if tuning.get("maxNumSeqs"):
            args.extend(["--parallel", str(tuning["maxNumSeqs"])])
    return args


def _model_mount_parts(model_path, model_ref, protocol):
    model_mount = protocol.get("modelMount") or {}
    container_root = model_mount.get("containerPath", "/models")
    if not model_path:
        return None, None
    model_path_text = str(model_path)
    model_name = Path(model_ref or model_path_text).name
    if model_path_text.lower().endswith(".gguf"):
        host_path = str(Path(model_path_text).parent or ".")
        model_name = Path(model_path_text).name
        return host_path, f"{container_root}/{model_name}"
    return model_path_text, f"{container_root}/{model_name}"


def _runtime_command(protocol, model_ref, model_path, tuning, hf_source=None):
    command = []
    model_mount = protocol.get("modelMount") or {}
    _, container_model_path = _model_mount_parts(model_path, model_ref, protocol)
    if protocol["modelFormat"] == "gguf" and hf_source:
        # llama.cpp downloads the GGUF from the Hub itself; no mount needed.
        command.extend(["--hf-repo", hf_source["repo"], "--hf-file", hf_source["file"]])
    elif protocol.get("modelArgument"):
        if protocol["modelFormat"] == "gguf":
            command.extend([protocol["modelArgument"], container_model_path or f"{model_mount.get('containerPath', '/models')}/{Path(model_ref).name}"])
        else:
            command.extend([protocol["modelArgument"], model_ref])
    if protocol["modelFormat"] == "gguf" and str(protocol.get("runtime", "")).lower() == "llama.cpp" and model_ref:
        # Serve under a stable id so health probes and chat requests can
        # address the model by the same name the registry stores.
        command.extend(["--alias", model_ref])
    command.extend(_runtime_arguments(protocol, tuning))
    return command


def _docker_run_preview(protocol, model_ref, model_path, host_port, container_name, tuning, limits, hf_source=None):
    command = [
        "docker", "run", "-d",
        "--name", container_name,
        "--restart", "unless-stopped",
        "-p", f"{protocol['hostBinding']}:{host_port}:{protocol['containerPort']}",
        "--security-opt", "no-new-privileges",
        "--label", "rasputin.managed=true",
        "--label", f"rasputin.protocol={protocol['id']}",
        "--label", f"rasputin.runtime={protocol['runtime']}",
    ]
    if _uses_gpu(protocol, tuning, limits):
        command.extend(["--gpus", "all"])
    if limits.get("gpuDevice"):
        command.extend(["-e", f"NVIDIA_VISIBLE_DEVICES={limits['gpuDevice']}"])
    if limits.get("memoryLimitGb"):
        command.extend(["--memory", f"{limits['memoryLimitGb']}g"])
    if limits.get("cpuLimit"):
        command.extend(["--cpus", str(limits["cpuLimit"])])
    if limits.get("shmSizeGb"):
        command.extend(["--shm-size", f"{limits['shmSizeGb']}g"])
    for mount in protocol.get("dataMounts") or []:
        mode = "ro" if mount.get("readOnly") else "rw"
        command.extend(["-v", f"{mount['hostPath']}:{mount['containerPath']}:{mode}"])
    model_mount = protocol.get("modelMount") or {}
    host_model_path, _ = _model_mount_parts(model_path, model_ref, protocol)
    if host_model_path and model_mount.get("containerPath"):
        mode = "ro" if model_mount.get("readOnly", True) else "rw"
        command.extend(["-v", f"{host_model_path}:{model_mount['containerPath']}:{mode}"])
    command.append(protocol["image"])
    command.extend(_runtime_command(protocol, model_ref, model_path, tuning, hf_source))
    return command


def _yaml_scalar(value):
    return json.dumps(str(value))


def _compose_preview(protocol, model_ref, model_path, host_port, container_name, strength, tuning, limits, hf_source=None):
    service = _slug(container_name)
    port_spec = f"{protocol['hostBinding']}:{host_port}:{protocol['containerPort']}"
    lines = [
        "services:",
        f"  {service}:",
        f"    image: {_yaml_scalar(protocol['image'])}",
        f"    container_name: {_yaml_scalar(container_name)}",
        "    restart: unless-stopped",
        "    security_opt:",
        "      - no-new-privileges:true",
        "    ports:",
        f"      - {_yaml_scalar(port_spec)}",
    ]
    if _uses_gpu(protocol, tuning, limits):
        lines.extend([
            "    gpus: all",
        ])
    if limits.get("memoryLimitGb"):
        lines.append(f"    mem_limit: {_yaml_scalar(str(limits['memoryLimitGb']) + 'g')}")
    if limits.get("cpuLimit"):
        lines.append(f"    cpus: {_yaml_scalar(limits['cpuLimit'])}")
    if limits.get("shmSizeGb"):
        lines.append(f"    shm_size: {_yaml_scalar(str(limits['shmSizeGb']) + 'g')}")
    if limits.get("gpuDevice"):
        lines.extend([
            "    environment:",
            f"      NVIDIA_VISIBLE_DEVICES: {_yaml_scalar(limits['gpuDevice'])}",
        ])
    volumes = []
    for mount in protocol.get("dataMounts") or []:
        mode = "ro" if mount.get("readOnly") else "rw"
        volumes.append(f"{mount['hostPath']}:{mount['containerPath']}:{mode}")
    model_mount = protocol.get("modelMount") or {}
    host_model_path, _ = _model_mount_parts(model_path, model_ref, protocol)
    if host_model_path and model_mount.get("containerPath"):
        mode = "ro" if model_mount.get("readOnly", True) else "rw"
        volumes.append(f"{host_model_path}:{model_mount['containerPath']}:{mode}")
    if volumes:
        lines.append("    volumes:")
        for volume in volumes:
            lines.append(f"      - {_yaml_scalar(volume)}")
    command = _runtime_command(protocol, model_ref, model_path, tuning, hf_source)
    if command:
        lines.append("    command:")
        for part in command:
            lines.append(f"      - {_yaml_scalar(part)}")
    lines.extend([
        "    labels:",
        '      rasputin.managed: "planned"',
        f"      rasputin.protocol: {_yaml_scalar(protocol['id'])}",
        f"      rasputin.strength: {_yaml_scalar(_safe_strength(strength))}",
        f"      rasputin.context: {_yaml_scalar(tuning.get('contextWindow'))}",
    ])
    return "\n".join(lines) + "\n"


def _dockerfile_preview(protocol):
    return "\n".join([
        f"FROM {protocol['image']}",
        'LABEL rasputin.managed="planned"',
        f'LABEL rasputin.protocol="{protocol["id"]}"',
        "",
        "# Models are mounted at runtime. Do not bake private model files into images.",
    ]) + "\n"


def _phase_item(phase_id, label, message, status="pending", detail=None):
    return {
        "id": phase_id,
        "label": label,
        "status": status,
        "message": message,
        "detail": detail or {},
        "updatedAt": time.time() if status != "pending" else None,
    }


def _lifecycle(active=None, done=None, failed=None, details=None):
    done = set(done or [])
    details = details or {}
    items = []
    for phase_id, label, message in DEPLOY_PHASES:
        status = "pending"
        if phase_id in done:
            status = "done"
        if active == phase_id:
            status = "active"
        if failed == phase_id:
            status = "error"
        items.append(_phase_item(phase_id, label, message, status, details.get(phase_id)))
    return items


def _command_log(phase, command, result=None, status="done", error=None):
    return {
        "phase": phase,
        "status": status,
        "command": " ".join(str(item) for item in (command or [])[:12]),
        "returnCode": result.get("returnCode") if isinstance(result, dict) else None,
        "stdout": (result.get("stdout") if isinstance(result, dict) else "")[:1000],
        "stderr": (result.get("stderr") if isinstance(result, dict) else "")[:1000],
        "error": str(error)[:1000] if error else "",
        "createdAt": time.time(),
    }


def _probe_model_endpoint(health_url, expected_model=None, attempts=None, interval=None):
    security.require_local_url(health_url)
    if _fake_deploy_enabled():
        return {
            "ok": True,
            "status": "reachable",
            "attempts": 1,
            "latencyMs": 3,
            "statusCode": 200,
            "availableModels": [str(expected_model or "warsat-test-model")],
            "message": "Test-mode model endpoint passed the simulated health probe.",
        }
    safe_attempts = max(1, min(int(attempts or HEALTH_PROBE_ATTEMPTS), 30))
    safe_interval = max(0.0, min(float(interval if interval is not None else HEALTH_PROBE_INTERVAL_SECONDS), 30.0))
    last_error = ""
    started = time.time()
    for attempt in range(1, safe_attempts + 1):
        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "rasputin-warsat/0.1"})
            with urllib.request.urlopen(req, timeout=HEALTH_PROBE_TIMEOUT_SECONDS) as response:
                raw = response.read(512_000).decode("utf-8", "replace")
                status_code = getattr(response, "status", 200)
            data = json.loads(raw or "{}") if raw else {}
            model_ids = []
            for item in data.get("data") or data.get("models") or []:
                if isinstance(item, dict):
                    model_ids.append(str(item.get("id") or item.get("model") or item.get("name") or ""))
                else:
                    model_ids.append(str(item))
            expected = str(expected_model or "").strip()
            # An empty model list must NOT count as "present" -- for Ollama
            # deploys (Warsat starts the bare server; it never pulls the
            # model itself), a fresh container with nothing pulled yet
            # returns an empty /v1/models list, and treating that as success
            # registered a model that was never actually loaded.
            model_present = not expected or expected in model_ids
            if 200 <= int(status_code) < 300 and model_present:
                return {
                    "ok": True,
                    "status": "reachable",
                    "attempts": attempt,
                    "latencyMs": int((time.time() - started) * 1000),
                    "statusCode": status_code,
                    "availableModels": [item for item in model_ids if item][:20],
                    "message": "Model endpoint responded to the health probe.",
                }
            last_error = f"health endpoint responded, but expected model {expected} was not listed"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_error = str(exc)
        if attempt < safe_attempts and safe_interval:
            time.sleep(safe_interval)
    return {
        "ok": False,
        "status": "unhealthy",
        "attempts": safe_attempts,
        "latencyMs": int((time.time() - started) * 1000),
        "lastError": last_error or "endpoint did not become reachable",
        "message": "Container started, but the model endpoint did not pass the health probe.",
    }


def _probe_failure_log_tail(container_name, limit=15):
    # The probe's own error ("connection refused", "remote end closed
    # connection without response", etc.) only describes the symptom -- a TCP
    # connection was accepted or refused. The actual cause (gated HF repo,
    # OOM, CUDA driver mismatch, bad CLI args) is almost always in the last
    # few lines of the container's own stderr, so pull that in instead of
    # making the user dig through Managed Runtimes to find it.
    try:
        result = _run_command(["docker", "logs", "--tail", str(limit), container_name], timeout=15, check=False)
    except Exception:
        return ""
    text = ((result.get("stdout") or "") + "\n" + (result.get("stderr") or "")).strip()
    if not text:
        return ""
    return "\n".join(text.splitlines()[-limit:])[:1500]


def make_plan(payload):
    protocol = get_protocol(payload.get("protocolId") or payload.get("protocol_id"))
    model_ref = str(payload.get("modelRef") or payload.get("model_ref") or "").strip()
    model_path = str(payload.get("modelPath") or payload.get("model_path") or "").strip()

    # A Hugging Face repo only works on the runtime that matches the weights
    # it actually ships. Check the repo's file list and reroute rather than
    # letting the container crash-loop on an incompatible format.
    reroute_note = ""
    inventory = _hf_repo_inventory(model_ref) if not model_path else None
    if protocol["runtime"] == "vllm" and inventory is not None and not inventory["transformersOk"]:
        if inventory["ggufFiles"]:
            reroute_note = (
                f"{model_ref} only ships GGUF weights, which vLLM cannot load. "
                "Warsat rerouted this deployment to the llama.cpp GGUF server."
            )
            protocol = get_protocol("llamaCppGgufServer")
        else:
            raise AppError(
                "warsat_model_format",
                f"{model_ref} has no deployable weights: no transformers config/weights and no GGUF files. "
                "Pick a different upload of this model.",
                400,
            )

    role = str(payload.get("role") or "").strip()
    if not role:
        suggested = model_registry.suggest_role(
            payload.get("modelRef") or payload.get("model_ref"),
            payload.get("modelPath") or payload.get("model_path"),
        )
        role = suggested if suggested != "helper" else str(protocol.get("defaultRole") or "helper")
    strength = _safe_strength(payload.get("strengthProfile") or payload.get("strength_profile"))
    requested_port = payload.get("hostPort") or payload.get("host_port")
    # No explicit port -> pick the first one not held by another running
    # container, so a second deploy doesn't collide with the first.
    host_port = int(requested_port) if requested_port else _pick_host_port(protocol)
    model_label = _model_label_for_container(model_ref, model_path)
    default_name = f"rasputin-{model_label}-{host_port}" if model_label else f"rasputin-{protocol['id']}-{host_port}"
    container_name = _slug(payload.get("containerName") or default_name)
    tuning = _build_tuning(payload, protocol, strength)
    limits = _build_limits(payload)

    if not model_ref and protocol["modelFormat"] != "gguf":
        raise AppError("warsat_model_required", "Enter a model id for this Warsat protocol.", 400)
    hf_source = None
    if protocol["modelFormat"] == "gguf":
        if model_path:
            if model_path.lower().endswith(".gguf"):
                model_ref = Path(model_path).name
            elif not model_ref:
                model_ref = Path(model_path).name
        elif _looks_like_hf_repo(model_ref):
            # No local file: let llama.cpp pull the GGUF from the Hub itself.
            if inventory is None:
                inventory = _hf_repo_inventory(model_ref)
            gguf_files = (inventory or {}).get("ggufFiles") or []
            if not gguf_files:
                raise AppError(
                    "warsat_model_path_required",
                    f"Could not find GGUF files for {model_ref} on Hugging Face. "
                    "Download the GGUF into the models folder and set the model path, or retry while online.",
                    400,
                )
            hf_file = _pick_gguf_file(gguf_files)
            hf_source = {"repo": str(model_ref).strip().strip("/"), "file": hf_file}
            model_ref = Path(hf_file).stem
        else:
            raise AppError("warsat_model_path_required", "Enter the mounted GGUF model folder or file path.", 400)

    if protocol.get("imageCuda") and _uses_gpu(protocol, tuning, limits):
        protocol = dict(protocol)
        protocol["image"] = protocol["imageCuda"]

    endpoint = _endpoint_for(protocol["hostBinding"], host_port)
    model_key = _slug(f"{protocol['runtime']}-{model_ref or protocol['id']}-{host_port}")
    docker_run = _docker_run_preview(protocol, model_ref, model_path, host_port, container_name, tuning, limits, hf_source)
    compose_preview = _compose_preview(protocol, model_ref, model_path, host_port, container_name, strength, tuning, limits, hf_source)
    dockerfile_preview = _dockerfile_preview(protocol)
    execution = _docker_runtime_enabled()
    docker_control_enabled = execution["dockerControlEnabled"]
    warnings = []
    if reroute_note:
        warnings.append(reroute_note)
    if hf_source:
        warnings.append(
            f"llama.cpp downloads {hf_source['file']} from {hf_source['repo']} on first start, "
            "so the first health probe can take several minutes. The download is cached only for the "
            "container's lifetime; a redeploy fetches it again."
        )
    elif protocol.get("modelFormat") == "huggingface" and model_ref:
        warnings.append(
            f"vLLM downloads {model_ref} from Hugging Face on first start, so the first health probe "
            "can take several minutes for a multi-GB model. The download is cached in a persistent "
            "volume, so later deploys of the same model reuse it."
        )
    if not docker_control_enabled:
        warnings.append("Docker control is disabled. This plan cannot be executed from Rasputin yet.")
    elif not execution["dockerCliAvailable"]:
        warnings.append("Docker control is enabled, but the wrapper was not started with Docker CLI access.")
    if protocol.get("hostBinding") != "127.0.0.1":
        warnings.append("Protocol does not bind to 127.0.0.1. Review before execution.")
    if protocol.get("hostNetwork"):
        warnings.append("Protocol requests host networking. Rasputin should reject this by default.")
    if _uses_gpu(protocol, tuning, limits):
        warnings.append("This protocol expects GPU passthrough to Docker.")
    if tuning.get("gpuMemoryUtilization", 0) >= 0.92:
        warnings.append("GPU memory utilization is aggressive. Leave headroom if you use the desktop while the model runs.")
    size_match = re.search(r"(\d+(?:\.\d+)?)\s*[bB](?![a-zA-Z0-9])", model_ref or "")
    if protocol["runtime"] == "vllm" and size_match and not tuning.get("quantization"):
        params_b = float(size_match.group(1))
        est_weights_gb = params_b * 2.05  # bf16 = 2 bytes/param plus overhead
        if est_weights_gb >= 12:
            warnings.append(
                f"~{params_b:g}B parameters at bf16 needs roughly {est_weights_gb:.0f} GB of VRAM for weights alone, "
                "before any KV cache. On 16 GB-class GPUs the engine will fail to start — set Quantization "
                "(fp8 works well on RTX 40/50 series) or pick a smaller model."
            )
    if tuning.get("maxModelLen", 0) >= 32768:
        warnings.append("Long context can sharply increase VRAM usage and startup time.")
    if limits.get("memoryLimitGb") and limits["memoryLimitGb"] < 8:
        warnings.append("Memory limit is low for most model runtimes.")

    plan = {
        "planId": f"warsat-{uuid.uuid4().hex[:12]}",
        "createdAt": time.time(),
        "status": "planned",
        "phase": "planned",
        "lifecycle": _lifecycle(active="planned"),
        "protocolId": protocol["id"],
        "protocolName": protocol["name"],
        "runtime": protocol["runtime"],
        "image": protocol["image"],
        "modelFormat": protocol["modelFormat"],
        "modelRef": model_ref,
        "modelPath": model_path,
        "hfSource": hf_source,
        # Startup downloads need a much longer probe window than a warm model --
        # a multi-GB GGUF pulled by llama.cpp's own --hf-repo/--hf-file flags, or
        # a multi-GB HF model vLLM downloads itself via --model, can take well
        # past 5 minutes on an ordinary connection. 30 * 30s is the max
        # _probe_model_endpoint's own clamps allow (15 minutes).
        "healthProbe": {"attempts": 30, "intervalSeconds": 30}
        if (hf_source or (protocol.get("modelFormat") == "huggingface" and model_ref))
        else None,
        "role": role,
        "strengthProfile": strength,
        "resourceProfile": STRENGTH_PROFILES[strength],
        "tuning": tuning,
        "containerLimits": limits,
        "hostPort": host_port,
        "containerPort": protocol["containerPort"],
        "containerName": container_name,
        "endpoint": endpoint,
        "healthUrl": endpoint.rstrip("/v1") + protocol.get("healthPath", "/v1/models"),
        "riskLevel": "approvalRequired",
        "requiresApproval": True,
        # An identical deployment approved before deploys without re-asking.
        "approvalGranted": False,
        "executionEnabled": execution["enabled"],
        "dockerControlEnabled": docker_control_enabled,
        "dockerCliAvailable": execution["dockerCliAvailable"],
        "commandPreview": {
            "pull": ["docker", "pull", protocol["image"]],
            "run": docker_run,
        },
        "composePreview": compose_preview,
        "dockerfilePreview": dockerfile_preview,
        "filesPreview": [
            {
                "path": f"docker-compose.warsat.{protocol['id']}.{strength}.yml",
                "kind": "compose",
                "content": compose_preview,
            },
            {
                "path": f"Dockerfile.warsat.{protocol['id']}",
                "kind": "dockerfile",
                "content": dockerfile_preview,
            },
        ],
        "expectedModelRegistryEntry": {
            "key": model_key,
            "name": f"{protocol['name']} - {model_ref or host_port}",
            "provider": protocol["runtime"],
            "role": role,
            "baseUrl": endpoint,
            "model": model_ref,
            "enabled": True,
            "managed": True,
            "runtime": f"warsat-{protocol['runtime']}",
            "container": container_name,
            "port": host_port,
            "image": protocol["image"],
            "contextWindow": tuning.get("contextWindow") or tuning.get("maxModelLen"),
            "maxTokens": 512,
        },
        "securityChecks": {
            "localhostOnly": protocol.get("hostBinding") == "127.0.0.1",
            "noNewPrivileges": protocol.get("noNewPrivileges", True),
            "hostNetwork": protocol.get("hostNetwork", False),
            "modelMountReadOnly": bool((protocol.get("modelMount") or {}).get("readOnly", True)),
        },
        "warnings": warnings,
        "nextSteps": [
            "Review the launch plan.",
            "Copy or export the compose preview if you want a standalone model compose file.",
            "Enable Docker control and restart with the docker-control profile if you want Rasputin to manage containers.",
            "Deploy only after reviewing the image, port, resource limits, and model id.",
            "After the runtime is healthy, test the model from the Models page.",
        ],
    }
    plan["approvalGranted"] = _matching_deploy_grant(plan, protocol) is not None
    audit.log("warsat_plan_created", {
        "protocolId": plan["protocolId"],
        "runtime": plan["runtime"],
        "role": plan["role"],
        "hostPort": plan["hostPort"],
        "executionEnabled": plan["executionEnabled"],
    })
    return plan


def _command_output(proc):
    return (proc.stdout or "").strip() or (proc.stderr or "").strip()


def _fake_run_command(args, timeout=120, check=True):
    if args[:2] == ["docker", "pull"]:
        return {
            "returnCode": 0,
            "stdout": f"test mode: skipped image pull for {args[-1]}",
            "stderr": "",
        }
    if args[:3] == ["docker", "rm", "-f"]:
        return {
            "returnCode": 0,
            "stdout": "test mode: previous container removed if present",
            "stderr": "",
        }
    if args[:3] == ["docker", "run", "-d"]:
        container_name = "warsat-test-container"
        if "--name" in args:
            idx = args.index("--name")
            if idx + 1 < len(args):
                container_name = args[idx + 1]
        return {
            "returnCode": 0,
            "stdout": f"test-{_slug(container_name)}",
            "stderr": "",
        }
    if args[:2] == ["docker", "ps"]:
        if "--format" in args and "{{.Status}}" in args:
            return {"returnCode": 0, "stdout": "Up 2 seconds", "stderr": ""}
        return {"returnCode": 0, "stdout": "", "stderr": ""}
    if args[:2] == ["docker", "inspect"]:
        return {
            "returnCode": 0,
            "stdout": json.dumps({
                "rasputin.managed": "true",
                "rasputin.protocol": "test",
                "rasputin.runtime": "test",
            }),
            "stderr": "",
        }
    if args[:2] == ["docker", "logs"]:
        return {
            "returnCode": 0,
            "stdout": "test mode: runtime logs are simulated",
            "stderr": "",
        }
    if args[:2] in (["docker", "stop"], ["docker", "restart"]):
        return {
            "returnCode": 0,
            "stdout": args[-1],
            "stderr": "",
        }
    if check:
        raise AppError("warsat_test_command_unhandled", f"Test-mode Warsat did not handle command: {' '.join(args[:4])}", 500)
    return {"returnCode": 1, "stdout": "", "stderr": "test mode: command not handled"}


def _run_command(args, timeout=120, check=True):
    if not isinstance(args, list) or not args or args[0] != "docker":
        raise AppError("warsat_command_rejected", "Warsat can only execute generated Docker commands.", 400)
    if _fake_deploy_enabled():
        return _fake_run_command(args, timeout, check)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise AppError("warsat_docker_unavailable", "Docker CLI is not available to Rasputin. Restart with the docker-control profile.", 503)
    except subprocess.TimeoutExpired:
        raise AppError("warsat_docker_timeout", "Docker command timed out before it finished.", 504)
    if check and proc.returncode != 0:
        raise AppError("warsat_docker_failed", _command_output(proc) or "Docker command failed.", 502)
    return {
        "returnCode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def _image_exists_locally(image):
    if _fake_deploy_enabled():
        return False
    result = _run_command(["docker", "image", "inspect", image], timeout=20, check=False)
    return result["returnCode"] == 0


_DOCKER_GPU_CACHE = {"at": 0.0, "gpus": None}


def _parse_gpu_csv(text):
    gpus = []
    for line in (text or "").splitlines():
        parts = [part.strip() for part in line.split(",")]
        if parts and parts[0]:
            gpus.append({
                "name": parts[0],
                "memoryTotalMb": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None,
            })
    return gpus


def _gpu_probe_via_docker():
    """GPU visibility for the containerized wrapper, which has no nvidia-smi.

    The NVIDIA container toolkit injects nvidia-smi into any --gpus container,
    so run it through our own (glibc-based) image. Cached — this spins up a
    short-lived container.
    """
    if _fake_deploy_enabled() or not _docker_cli_path():
        return []
    if not security.load().get("allow_docker_control", False):
        return []
    now = time.time()
    if _DOCKER_GPU_CACHE["gpus"] is not None and now - _DOCKER_GPU_CACHE["at"] < 600:
        return _DOCKER_GPU_CACHE["gpus"]
    image = os.environ.get("WRAPPER_SELF_IMAGE", "rasputin-wrapper:latest")
    gpus = []
    try:
        if _image_exists_locally(image):
            result = _run_command([
                "docker", "run", "--rm", "--gpus", "all", "--entrypoint", "nvidia-smi", image,
                "--query-gpu=name,memory.total", "--format=csv,noheader,nounits",
            ], timeout=45, check=False)
            if result["returnCode"] == 0:
                gpus = _parse_gpu_csv(result["stdout"])
    except AppError:
        gpus = []
    _DOCKER_GPU_CACHE["at"] = now
    _DOCKER_GPU_CACHE["gpus"] = gpus
    return gpus


def _parse_gpu_metrics_csv(text):
    out = []
    for line in (text or "").strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 6:
            try:
                out.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "utilization": float(parts[2]),
                    "memory_used_mb": float(parts[3]),
                    "memory_total_mb": float(parts[4]),
                    "temperature": float(parts[5]),
                })
            except ValueError:
                continue
    return out


def gpu_live_metrics_via_docker():
    """Live GPU telemetry for the containerized wrapper (no local nvidia-smi):
    exec nvidia-smi inside a running Rasputin-managed GPU container — cheap
    per poll — falling back to cached totals with zeroed live values."""
    if _fake_deploy_enabled() or not _docker_cli_path():
        return []
    if not security.load().get("allow_docker_control", False):
        return []
    query = [
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        ps = _run_command(["docker", "ps", "--filter", "label=rasputin.managed=true", "--format", "{{.Names}}"], timeout=10, check=False)
        names = [n.strip() for n in ps["stdout"].splitlines() if n.strip()] if ps["returnCode"] == 0 else []
        for name in names:
            result = _run_command(["docker", "exec", name] + query, timeout=10, check=False)
            if result["returnCode"] == 0 and result["stdout"].strip():
                metrics = _parse_gpu_metrics_csv(result["stdout"])
                if metrics:
                    return metrics
    except AppError:
        pass
    return [
        {
            "index": i,
            "name": gpu["name"],
            "utilization": 0.0,
            "memory_used_mb": 0.0,
            "memory_total_mb": float(gpu.get("memoryTotalMb") or 0),
            "temperature": 0.0,
        }
        for i, gpu in enumerate(_gpu_probe_via_docker())
    ]


def _occupied_host_ports():
    """Host port -> container name for running containers."""
    try:
        result = _run_command(["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"], timeout=15, check=False)
    except AppError:
        return {}
    if result["returnCode"] != 0:
        return {}
    occupied = {}
    for line in result["stdout"].splitlines():
        name, _, ports = line.partition("\t")
        for match in re.findall(r":(\d+)->", ports):
            occupied[int(match)] = name.strip()
    return occupied


def _registry_reserved_ports():
    """Host port -> container name for registered managed models, so a new
    deploy can't steal the port of a runtime that is merely stopped."""
    reserved = {}
    try:
        for model in model_registry.all_models():
            port = model.get("port")
            container = model.get("container")
            if port and container:
                reserved[int(port)] = str(container)
    except Exception:
        return {}
    return reserved


def _pick_host_port(protocol):
    """First free host port at or after the protocol default. A port still
    counts as free when its occupant is the very container this plan would
    replace, so redeploys keep their port."""
    start = int(protocol["defaultHostPort"])
    if not _docker_cli_path() or _fake_deploy_enabled():
        return start
    occupied = _occupied_host_ports()
    reserved = _registry_reserved_ports()
    port = start
    while port < start + 200:
        own_name = _slug(f"rasputin-{protocol['id']}-{port}")
        if occupied.get(port) in (None, own_name) and reserved.get(port) in (None, own_name):
            return port
        port += 1
    return start


def _pull_image(pull_cmd, image):
    """Pull the protocol image, skipping the registry when a local copy exists.

    Rasputin is local-first: a cached image should never block a deploy behind
    a multi-GB registry download. Users refresh images explicitly.
    """
    if _image_exists_locally(image):
        return {
            "returnCode": 0,
            "stdout": f"Image {image} already present locally - skipped registry pull.",
            "stderr": "",
        }
    return _run_command(pull_cmd, timeout=DEPLOY_TIMEOUT_SECONDS)


def _streamed_pull(pull_cmd):
    """Run docker pull, yielding ('progress', line) then ('result', result).

    Mirrors _run_command's error contract (503 missing CLI, 504 timeout,
    502 failure) but keeps output flowing so the UI can show live layer
    progress during large downloads instead of appearing hung.
    """
    if _fake_deploy_enabled():
        yield ("result", _fake_run_command(pull_cmd, DEPLOY_TIMEOUT_SECONDS, True))
        return
    try:
        proc = subprocess.Popen(pull_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        raise AppError("warsat_docker_unavailable", "Docker CLI is not available to Rasputin. Restart with the docker-control profile.", 503)
    deadline = time.time() + DEPLOY_TIMEOUT_SECONDS
    lines = []
    last_emit = 0.0
    try:
        for raw in proc.stdout:
            if time.time() > deadline:
                proc.kill()
                raise AppError("warsat_docker_timeout", "Docker command timed out before it finished.", 504)
            line = raw.strip()
            if not line:
                continue
            lines.append(line)
            now = time.time()
            if now - last_emit >= 2.0:
                last_emit = now
                yield ("progress", line[:300])
        proc.wait(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    output = "\n".join(lines[-30:])
    if proc.returncode != 0:
        raise AppError("warsat_docker_failed", output or "Docker pull failed.", 502)
    yield ("result", {"returnCode": proc.returncode, "stdout": output, "stderr": ""})


def _validate_deploy_plan(plan):
    if not isinstance(plan, dict):
        raise AppError("warsat_plan_invalid", "Create a launch plan before deploying.", 400)
    security.require("allow_docker_control")
    security.require("allow_model_registry_edit")

    protocol = get_protocol(plan.get("protocolId"))
    checks = plan.get("securityChecks") or {}
    if not checks.get("localhostOnly"):
        raise AppError("warsat_binding_rejected", "Warsat only deploys containers bound to 127.0.0.1.", 400)
    if checks.get("hostNetwork"):
        raise AppError("warsat_host_network_rejected", "Warsat will not deploy containers with host networking.", 400)
    if not checks.get("noNewPrivileges", True):
        raise AppError("warsat_privileges_rejected", "Warsat requires no-new-privileges for model containers.", 400)

    endpoint = plan.get("endpoint") or (plan.get("expectedModelRegistryEntry") or {}).get("baseUrl")
    security.require_local_url(endpoint)

    run_cmd = ((plan.get("commandPreview") or {}).get("run") or [])
    pull_cmd = ((plan.get("commandPreview") or {}).get("pull") or [])
    allowed_images = {protocol["image"]}
    if protocol.get("imageCuda"):
        allowed_images.add(protocol["imageCuda"])
    if pull_cmd[:2] != ["docker", "pull"] or pull_cmd[-1] not in allowed_images:
        raise AppError("warsat_command_rejected", "Docker pull command does not match the selected protocol image.", 400)
    if run_cmd[:3] != ["docker", "run", "-d"]:
        raise AppError("warsat_command_rejected", "Docker run command must be generated by Warsat.", 400)
    forbidden = {"--privileged", "--network=host", "--pid=host", "--ipc=host"}
    if any(item in forbidden for item in run_cmd):
        raise AppError("warsat_command_rejected", "Docker run command contains a forbidden host-level option.", 400)
    if "--network" in run_cmd:
        idx = run_cmd.index("--network")
        if idx + 1 < len(run_cmd) and run_cmd[idx + 1] == "host":
            raise AppError("warsat_command_rejected", "Docker host networking is not allowed.", 400)
    port_spec = f"127.0.0.1:{int(plan.get('hostPort'))}:{int(plan.get('containerPort'))}"
    if port_spec not in run_cmd:
        raise AppError("warsat_binding_rejected", "Docker run command must bind the model to 127.0.0.1.", 400)
    if "--security-opt" not in run_cmd or "no-new-privileges" not in run_cmd:
        raise AppError("warsat_privileges_rejected", "Docker run command must include no-new-privileges.", 400)
    if not any(image in run_cmd for image in allowed_images):
        raise AppError("warsat_command_rejected", "Docker run command does not match the selected protocol image.", 400)

    container_name = _slug(plan.get("containerName"))
    if not container_name or container_name != plan.get("containerName"):
        raise AppError("warsat_container_name_rejected", "Container name must be a safe generated name.", 400)
    if "--name" not in run_cmd or run_cmd[run_cmd.index("--name") + 1] != container_name:
        raise AppError("warsat_command_rejected", "Docker run command container name does not match the launch plan.", 400)
    return protocol, pull_cmd, run_cmd, container_name


def _registry_entry_from_plan(plan):
    entry = dict(plan.get("expectedModelRegistryEntry") or {})
    if not entry.get("key"):
        raise AppError("warsat_registry_entry_missing", "Launch plan is missing the model registry entry.", 400)
    base_url = entry.get("baseUrl") or entry.get("base_url") or plan.get("endpoint") or ""
    security.require_local_url(base_url)
    return {
        "key": entry.get("key"),
        "name": entry.get("name") or plan.get("protocolName") or entry.get("key"),
        "provider": entry.get("provider") or plan.get("runtime") or "openai-compatible",
        "role": entry.get("role") or plan.get("role") or "helper",
        "base_url": base_url,
        "model": entry.get("model") or plan.get("modelRef") or "",
        "enabled": bool(entry.get("enabled", True)),
        "managed": True,
        "runtime": entry.get("runtime") or f"warsat-{plan.get('runtime')}",
        "container": entry.get("container") or plan.get("containerName"),
        "port": int(entry.get("port") or plan.get("hostPort")),
        "image": entry.get("image") or plan.get("image"),
        "context_window": int(entry.get("contextWindow") or plan.get("tuning", {}).get("contextWindow") or plan.get("tuning", {}).get("maxModelLen") or 4096),
        "max_tokens": int(entry.get("maxTokens") or 512),
        "notes": "Managed by Warsat. Review Docker control before changing this entry.",
    }


def _container_status(container_name):
    result = _run_command(
        ["docker", "ps", "-a", "--filter", f"name=^{container_name}$", "--format", "{{.Status}}"],
        timeout=15,
        check=False,
    )
    text = result["stdout"].strip()
    if not text:
        return "stopped"
    return text


def _safe_container_name(value):
    name = _slug(value)
    if not name or name != str(value or ""):
        raise AppError("warsat_container_name_rejected", "Container name must be a safe Warsat container name.", 400)
    return name


def _parse_json_lines(text):
    rows = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"raw": line})
    return rows


def _inspect_labels(container_name):
    result = _run_command(
        ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_name],
        timeout=15,
        check=False,
    )
    if result["returnCode"] != 0:
        return {}
    try:
        return json.loads(result["stdout"] or "{}") or {}
    except json.JSONDecodeError:
        return {}


def _managed_container(container_name):
    name = _safe_container_name(container_name)
    labels = _inspect_labels(name)
    if labels.get("rasputin.managed") != "true":
        raise AppError("warsat_container_unmanaged", "Warsat can only control containers it created.", 403)
    return name, labels


def containers():
    execution = _docker_runtime_enabled()
    if not execution["enabled"]:
        return {
            **execution,
            "containers": [],
            "message": f"Warsat runtime listing is unavailable. {execution['message']}",
        }
    result = _run_command(
        ["docker", "ps", "-a", "--filter", "label=rasputin.managed=true", "--format", "{{json .}}"],
        timeout=20,
        check=False,
    )
    items = []
    for row in _parse_json_lines(result["stdout"]):
        name = row.get("Names") or row.get("Name") or ""
        labels = _inspect_labels(name) if name else {}
        status = row.get("Status") or ""
        state = "running" if status.lower().startswith("up") else "stopped" if status else "unknown"
        items.append({
            "id": row.get("ID") or row.get("IDShort") or "",
            "name": name,
            "image": row.get("Image") or "",
            "status": status or "unknown",
            "state": state,
            "ports": row.get("Ports") or "",
            "protocolId": labels.get("rasputin.protocol", ""),
            "runtime": labels.get("rasputin.runtime", ""),
            "managed": labels.get("rasputin.managed") == "true",
        })
    return {
        **execution,
        "containers": items,
        "count": len(items),
    }


def _discovery_hosts():
    # Inside the containerized wrapper 127.0.0.1 is the wrapper itself —
    # published container ports live on the host, reachable only via
    # host.docker.internal. A native wrapper reaches them on loopback.
    if os.environ.get("WRAPPER_RUNTIME") == "docker":
        return ["host.docker.internal", "127.0.0.1"]
    return ["127.0.0.1"]


def _probe_openai_endpoint(base_url: str, timeout: float = 2.0):
    """Try GET /v1/models and return list of model IDs, or empty list if unreachable."""
    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/v1/models",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            models = data.get("data") or data.get("models") or []
            return [m.get("id") or m.get("name") for m in models if m.get("id") or m.get("name")]
    except Exception:
        return None


def _probe_ollama_endpoint(base_url: str, timeout: float = 2.0):
    """Try GET /api/tags (Ollama native API) and return list of model names, or None."""
    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            models = data.get("models") or []
            return [m.get("name") for m in models if m.get("name")]
    except Exception:
        return None


def _extract_host_port(ports_str: str):
    """Parse Docker ports string like '0.0.0.0:8000->8000/tcp' → return host port int or None."""
    if not ports_str:
        return None
    # Match any host binding: 0.0.0.0:PORT->, 127.0.0.1:PORT->, :::PORT->,
    # [::]:PORT-> — Warsat's own containers bind 127.0.0.1.
    matches = re.findall(r'(?:\d{1,3}(?:\.\d{1,3}){3}|:::|\[[^\]]*\]):(\d+)->', ports_str)
    if not matches:
        # Maybe a simple mapping without host binding like 8000/tcp
        simple = re.findall(r'(\d{4,5})/tcp', ports_str)
        if simple:
            return int(simple[0])
        return None
    return int(matches[0])


def discover():
    """
    Scan ALL running Docker containers (not just Rasputin-managed ones)
    for OpenAI-compatible or Ollama model endpoints.
    Returns a list of discovered model candidates ready for one-click import.
    """
    execution = _docker_runtime_enabled()
    if not execution["enabled"]:
        return {
            **execution,
            "discovered": [],
            "message": f"Docker discovery unavailable. {execution['message']}",
        }

    # Get all running containers regardless of labels
    result = _run_command(
        ["docker", "ps", "--format", "{{json .}}"],
        timeout=20,
        check=False,
    )

    # Get registered model base_urls to avoid suggesting already-registered endpoints
    try:
        existing_models = model_registry.all_models()
        existing_urls = {
            str(m.get("base_url") or "").rstrip("/").lower()
            for m in existing_models
            if m.get("base_url")
        }
    except Exception:
        existing_urls = set()

    discovered = []
    for row in _parse_json_lines(result["stdout"]):
        name = row.get("Names") or row.get("Name") or ""
        ports_str = row.get("Ports") or ""
        image = row.get("Image") or ""
        container_id = row.get("ID") or row.get("IDShort") or ""

        host_port = _extract_host_port(ports_str)
        if not host_port:
            continue

        base_url = None
        model_ids = None
        protocol_hint = "openai-compatible"
        is_ollama = False
        already_registered = False
        for host in _discovery_hosts():
            candidate = f"http://{host}:{host_port}"
            # Registered entries usually carry a /v1 suffix — match both.
            if candidate.lower() in existing_urls or f"{candidate.lower()}/v1" in existing_urls:
                already_registered = True
                break
            ids = _probe_openai_endpoint(candidate)
            if ids is None:
                # Try Ollama native API
                ollama_models = _probe_ollama_endpoint(candidate)
                if ollama_models is not None:
                    ids = ollama_models
                    protocol_hint = "ollamaOpenaiServer"
                    is_ollama = True
            if ids is not None:
                base_url = candidate
                model_ids = ids
                break

        if already_registered or model_ids is None:
            # Registered already, or port open but not a model endpoint
            continue

        for model_id in model_ids:
            if not model_id:
                continue
            discovered.append({
                "containerName": name,
                "containerId": container_id,
                "image": image,
                "port": host_port,
                "baseUrl": base_url,
                "modelId": model_id,
                "protocolHint": protocol_hint,
                "isOllama": is_ollama,
                "alreadyRegistered": False,
            })

    audit.log("warsat_discover", {"found": len(discovered)})
    return {
        **execution,
        "discovered": discovered,
        "count": len(discovered),
    }


def import_discovered(model_id: str, base_url: str, container_name: str, protocol_hint: str = "openai-compatible"):
    """
    One-click import: register a discovered container's model endpoint into the
    model registry as an enabled, external-local model ready for chat.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")
    key = f"discovered-{slug}"

    # Determine a user-friendly name
    name = model_id
    if "/" in model_id:
        name = model_id.split("/")[-1]

    model_entry = {
        "key": key,
        "name": name,
        "model": model_id,
        "provider": "openai-compatible",
        "runtime": "external-local",
        "base_url": base_url,
        "enabled": True,
        "managed": False,
        "role": "main",
        "tags": ["discovered", "docker", protocol_hint],
        "description": f"Auto-discovered from Docker container: {container_name}",
    }

    model_registry.upsert(model_entry)
    audit.log("warsat_import_discovered", {
        "key": key,
        "modelId": model_id,
        "baseUrl": base_url,
        "containerName": container_name,
    })
    return {
        "ok": True,
        "key": key,
        "name": name,
        "modelId": model_id,
        "baseUrl": base_url,
        "message": f"'{name}' has been added to your model registry and is ready to chat.",
    }


def logs(container_name, limit=120):
    execution = _docker_runtime_enabled()
    if not execution["enabled"]:
        raise AppError("warsat_execution_disabled", execution["message"], 403)
    name, labels = _managed_container(container_name)
    safe_limit = max(1, min(int(limit or 120), LOG_LIMIT_MAX))
    result = _run_command(
        ["docker", "logs", "--tail", str(safe_limit), name],
        timeout=20,
        check=False,
    )
    return {
        "containerName": name,
        "protocolId": labels.get("rasputin.protocol", ""),
        "runtime": labels.get("rasputin.runtime", ""),
        "ok": result["returnCode"] == 0,
        "logs": (result["stdout"] + "\n" + result["stderr"]).strip(),
    }


def _container_operation(container_name, action, approval_id=None):
    # Stop/restart only touch containers Rasputin itself created (label
    # enforced below) and are reversible, so they run immediately under the
    # allow_docker_control permission. Deploys — which pull images and create
    # new containers — remain approval-gated. approval_id is accepted for
    # backward compatibility but no longer required.
    execution = _docker_runtime_enabled()
    if not execution["enabled"]:
        raise AppError("warsat_execution_disabled", execution["message"], 403)
    name, labels = _managed_container(container_name)
    action_type = f"warsat_{action}"
    docker_action = "restart" if action == "restart" else "stop"
    result = _run_command(["docker", docker_action, name], timeout=60, check=True)
    status = _container_status(name)
    audit.log(f"{action_type}_completed", {"container": name, "status": status})
    return {
        "approvalRequired": False,
        "status": status,
        "containerName": name,
        "action": action,
        "result": result,
    }


def stop(container_name, approval_id=None):
    return _container_operation(container_name, "stop", approval_id)


def restart(container_name, approval_id=None):
    return _container_operation(container_name, "restart", approval_id)


def _deploy_grant_fingerprint(plan, protocol):
    # The risk-relevant shape of a deployment. Tuning knobs (context length,
    # GPU utilization, quantization) can change without re-approval; a new
    # image, model, or port is a new risk decision.
    return {
        "protocolId": protocol["id"],
        "image": protocol["image"],
        "modelRef": str(plan.get("modelRef") or ""),
        "modelPath": str(plan.get("modelPath") or ""),
        "hostPort": int(plan.get("hostPort") or 0),
    }


def _deploy_grants():
    grants = store.get_kv("warsat_deploy_grants", {})
    return grants if isinstance(grants, dict) else {}


def _matching_deploy_grant(plan, protocol):
    container = _slug(str(plan.get("containerName") or ""))
    grant = _deploy_grants().get(container)
    if grant and grant.get("fingerprint") == _deploy_grant_fingerprint(plan, protocol):
        return grant
    return None


def _save_deploy_grant(plan, protocol, approval_id):
    grants = _deploy_grants()
    grants[_slug(str(plan.get("containerName") or ""))] = {
        "fingerprint": _deploy_grant_fingerprint(plan, protocol),
        "approvalId": approval_id,
        "approvedAt": time.time(),
    }
    store.set_kv("warsat_deploy_grants", grants)


def has_deploy_grant(plan):
    """True when an identical deployment was already approved once —
    redeploys and retries then execute without a fresh approval."""
    try:
        protocol = get_protocol((plan or {}).get("protocolId"))
    except Exception:
        return False
    return _matching_deploy_grant(plan, protocol) is not None


def _deployment_approval_detail(plan, protocol, container_name, registry_entry):
    return {
        "planId": plan.get("planId"),
        "protocolId": protocol["id"],
        "runtime": protocol["runtime"],
        "image": protocol["image"],
        "container": container_name,
        "modelKey": registry_entry["key"],
        "model": registry_entry.get("model"),
        "endpoint": registry_entry.get("base_url"),
        "hostPort": plan.get("hostPort"),
        "role": registry_entry.get("role"),
        "workspace": "Warsat runtime",
    }


def deploy(plan, approval_id=None):
    protocol, pull_cmd, run_cmd, container_name = _validate_deploy_plan(plan)
    registry_entry = _registry_entry_from_plan(plan)
    approval_detail = _deployment_approval_detail(plan, protocol, container_name, registry_entry)
    logs_out = []

    granted = _matching_deploy_grant(plan, protocol) is not None
    if not approval_id and not granted:
        approval = approvals.create(
            "warsat_deploy",
            approval_detail,
            risk_level="approval_required",
            workspace="Warsat runtime",
            ttl=15 * 60,
        )
        audit.log("warsat_deploy_approval_requested", {
            "planId": plan.get("planId"),
            "approvalId": approval["id"],
            "container": container_name,
            "modelKey": registry_entry["key"],
        })
        return {
            "approvalRequired": True,
            "status": "waitingForApproval",
            "phase": "approvalPending",
            "lifecycle": _lifecycle(active="approvalPending", done={"planned"}),
            "approval": approval,
            "containerName": container_name,
            "modelKey": registry_entry["key"],
            "endpoint": registry_entry["base_url"],
            "logs": logs_out,
            "message": "Approval created. Approve it from Activity or Approvals, then run the deploy again.",
            "nextSteps": [
                "Approve the deployment request.",
                "Run the approved deploy from Warsat.",
                "Warsat will pull the image, start the container, probe health, then register the model.",
            ],
        }

    if approval_id:
        approvals.require_approved(approval_id, "warsat_deploy")
        _save_deploy_grant(plan, protocol, approval_id)
    else:
        audit.log("warsat_deploy_grant_reused", {
            "planId": plan.get("planId"),
            "container": container_name,
        })

    audit.log("warsat_deploy_started", {
        "planId": plan.get("planId"),
        "approvalId": approval_id,
        "protocolId": protocol["id"],
        "image": protocol["image"],
        "container": container_name,
        "modelKey": registry_entry["key"],
    })

    plan_image = plan.get("image") or protocol["image"]
    pull = _pull_image(pull_cmd, plan_image)
    logs_out.append(_command_log("pulling", pull_cmd, pull))
    _run_command(["docker", "rm", "-f", container_name], timeout=60, check=False)
    started = _run_command(run_cmd, timeout=120)
    logs_out.append(_command_log("starting", run_cmd, started))
    status = _container_status(container_name)
    probe_cfg = plan.get("healthProbe") or {}
    health = _probe_model_endpoint(
        plan.get("healthUrl"),
        registry_entry.get("model"),
        attempts=probe_cfg.get("attempts"),
        interval=probe_cfg.get("intervalSeconds"),
    )
    logs_out.append({
        "phase": "probing",
        "status": "done" if health.get("ok") else "error",
        "message": health.get("message") or health.get("lastError") or "",
        "attempts": health.get("attempts"),
        "latencyMs": health.get("latencyMs"),
        "createdAt": time.time(),
    })

    if not health.get("ok"):
        last_error = health.get("lastError") or health.get("message")
        log_tail = _probe_failure_log_tail(container_name)
        if log_tail:
            last_error = f"{last_error}\n\nContainer log tail:\n{log_tail}"
        result = {
            "planId": plan.get("planId"),
            "approvalRequired": False,
            "status": "failed",
            "phase": "failed",
            "failedPhase": "probing",
            "lifecycle": _lifecycle(failed="probing", done={"planned", "approvalPending", "pulling", "starting"}),
            "containerId": started["stdout"],
            "containerName": container_name,
            "modelKey": registry_entry["key"],
            "endpoint": registry_entry["base_url"],
            "healthUrl": plan.get("healthUrl"),
            "health": health,
            "pull": pull,
            "run": started,
            "logs": logs_out,
            "lastError": last_error,
            "message": "Container started, but Warsat did not register the model because the health probe failed.",
            "nextSteps": [
                "Open container logs from Managed Runtimes to see if the model is still loading.",
                "If the container is still running, do not redeploy -- that removes the container "
                "and restarts any in-progress download from scratch. Instead wait for it to report "
                "healthy, then use Discover (below) to import it without redeploying.",
                "Only retry the deploy if the container actually exited or crashed.",
                "Check the selected model id, port, GPU settings, and mounted model path.",
            ],
        }
        audit.log("warsat_deploy_failed", {
            "planId": plan.get("planId"),
            "container": container_name,
            "modelKey": registry_entry["key"],
            "failedPhase": "probing",
            "error": result["lastError"],
        })
        return result

    saved = model_registry.upsert(registry_entry)

    result = {
        "planId": plan.get("planId"),
        "approvalRequired": False,
        "status": "registered",
        "phase": "registered",
        "lifecycle": _lifecycle(done={"planned", "approvalPending", "pulling", "starting", "probing", "registered"}),
        "containerId": started["stdout"],
        "containerName": container_name,
        "modelKey": saved["key"],
        "registryEntry": saved,
        "endpoint": registry_entry["base_url"],
        "healthUrl": plan.get("healthUrl"),
        "health": health,
        "containerStatus": "starting" if status.lower().startswith("up") else status,
        "pull": pull,
        "run": started,
        "logs": logs_out,
        "message": "Warsat container started, health probe passed, and the model registry entry was saved.",
        "nextSteps": [
            "Open Models and run Discover/Test if you want an additional latency check.",
            "Select the model in chat after it reports healthy.",
        ],
    }
    audit.log("warsat_deploy_completed", {
        "planId": plan.get("planId"),
        "container": container_name,
        "modelKey": saved["key"],
        "status": result["status"],
    })
    return result


def deploy_stream(plan, approval_id):
    protocol, pull_cmd, run_cmd, container_name = _validate_deploy_plan(plan)
    registry_entry = _registry_entry_from_plan(plan)
    logs_out = []

    if approval_id:
        approvals.require_approved(approval_id, "warsat_deploy")
        _save_deploy_grant(plan, protocol, approval_id)
    elif _matching_deploy_grant(plan, protocol) is None:
        raise AppError("warsat_approval_required", "This deployment has not been approved yet.", 403)
    else:
        audit.log("warsat_deploy_grant_reused", {
            "planId": plan.get("planId"),
            "container": container_name,
        })

    audit.log("warsat_deploy_started", {
        "planId": plan.get("planId"),
        "approvalId": approval_id,
        "protocolId": protocol["id"],
        "image": protocol["image"],
        "container": container_name,
        "modelKey": registry_entry["key"],
    })

    yield {
        "ok": True,
        "final": False,
        "data": {
            "status": "pulling",
            "phase": "pulling",
            "lifecycle": _lifecycle(active="pulling", done={"planned", "approvalPending"}),
            "containerName": container_name,
            "message": "Warsat is checking for the image...",
        }
    }

    plan_image = plan.get("image") or protocol["image"]
    if _image_exists_locally(plan_image):
        pull = {
            "returnCode": 0,
            "stdout": f"Image {plan_image} already present locally - skipped registry pull.",
            "stderr": "",
        }
    else:
        pull = None
        for kind, payload in _streamed_pull(pull_cmd):
            if kind == "result":
                pull = payload
                continue
            lifecycle = _lifecycle(active="pulling", done={"planned", "approvalPending"})
            for item in lifecycle:
                if item["id"] == "pulling":
                    item["message"] = payload
            yield {
                "ok": True,
                "final": False,
                "data": {
                    "status": "pulling",
                    "phase": "pulling",
                    "lifecycle": lifecycle,
                    "containerName": container_name,
                    "message": payload,
                }
            }
    logs_out.append(_command_log("pulling", pull_cmd, pull))
    _run_command(["docker", "rm", "-f", container_name], timeout=60, check=False)

    yield {
        "ok": True,
        "final": False,
        "data": {
            "status": "starting",
            "phase": "starting",
            "lifecycle": _lifecycle(active="starting", done={"planned", "approvalPending", "pulling"}),
            "containerName": container_name,
            "message": "Warsat is starting the container...",
        }
    }

    started = _run_command(run_cmd, timeout=120)
    logs_out.append(_command_log("starting", run_cmd, started))
    status = _container_status(container_name)

    yield {
        "ok": True,
        "final": False,
        "data": {
            "status": "probing",
            "phase": "probing",
            "lifecycle": _lifecycle(active="probing", done={"planned", "approvalPending", "pulling", "starting"}),
            "containerName": container_name,
            "message": "Warsat is running health probes...",
        }
    }

    probe_cfg = plan.get("healthProbe") or {}
    health = _probe_model_endpoint(
        plan.get("healthUrl"),
        registry_entry.get("model"),
        attempts=probe_cfg.get("attempts"),
        interval=probe_cfg.get("intervalSeconds"),
    )
    logs_out.append({
        "phase": "probing",
        "status": "done" if health.get("ok") else "error",
        "message": health.get("message") or health.get("lastError") or "",
        "attempts": health.get("attempts"),
        "latencyMs": health.get("latencyMs"),
        "createdAt": time.time(),
    })

    if not health.get("ok"):
        last_error = health.get("lastError") or health.get("message")
        log_tail = _probe_failure_log_tail(container_name)
        if log_tail:
            last_error = f"{last_error}\n\nContainer log tail:\n{log_tail}"
        result = {
            "planId": plan.get("planId"),
            "approvalRequired": False,
            "status": "failed",
            "phase": "failed",
            "failedPhase": "probing",
            "lifecycle": _lifecycle(failed="probing", done={"planned", "approvalPending", "pulling", "starting"}),
            "containerId": started["stdout"],
            "containerName": container_name,
            "modelKey": registry_entry["key"],
            "endpoint": registry_entry["base_url"],
            "healthUrl": plan.get("healthUrl"),
            "health": health,
            "pull": pull,
            "run": started,
            "logs": logs_out,
            "lastError": last_error,
            "message": "Container started, but Warsat did not register the model because the health probe failed.",
            "nextSteps": [
                "Open container logs from Managed Runtimes to see if the model is still loading.",
                "If the container is still running, do not redeploy -- that removes the container "
                "and restarts any in-progress download from scratch. Instead wait for it to report "
                "healthy, then use Discover (below) to import it without redeploying.",
                "Only retry the deploy if the container actually exited or crashed.",
                "Check the selected model id, port, GPU settings, and mounted model path.",
            ],
        }
        audit.log("warsat_deploy_failed", {
            "planId": plan.get("planId"),
            "container": container_name,
            "modelKey": registry_entry["key"],
            "failedPhase": "probing",
            "error": result["lastError"],
        })
        yield {"ok": True, "final": True, "data": result}
        return

    saved = model_registry.upsert(registry_entry)

    result = {
        "planId": plan.get("planId"),
        "approvalRequired": False,
        "status": "registered",
        "phase": "registered",
        "lifecycle": _lifecycle(done={"planned", "approvalPending", "pulling", "starting", "probing", "registered"}),
        "containerId": started["stdout"],
        "containerName": container_name,
        "modelKey": saved["key"],
        "registryEntry": saved,
        "endpoint": registry_entry["base_url"],
        "healthUrl": plan.get("healthUrl"),
        "health": health,
        "containerStatus": "starting" if status.lower().startswith("up") else status,
        "pull": pull,
        "run": started,
        "logs": logs_out,
        "message": "Warsat container started, health probe passed, and the model registry entry was saved.",
        "nextSteps": [
            "Open Models and run Discover/Test if you want an additional latency check.",
            "Select the model in chat after it reports healthy.",
        ],
    }
    audit.log("warsat_deploy_completed", {
        "planId": plan.get("planId"),
        "container": container_name,
        "modelKey": saved["key"],
        "status": result["status"],
    })
    yield {"ok": True, "final": True, "data": result}
