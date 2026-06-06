import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from .. import approvals
from .. import audit
from .. import model_registry
from .. import security
from ..response import AppError

ROOT = Path(__file__).resolve().parents[2]
BUILTIN_PROTOCOL_DIR = ROOT / "warsat" / "protocols"
DATA_DIR = ROOT / "data" / "warsat"
USER_PROTOCOL_DIR = DATA_DIR / "protocols"
DEPLOY_TIMEOUT_SECONDS = int(os.environ.get("WARSAT_DEPLOY_TIMEOUT", "1800"))
LOG_LIMIT_MAX = 500

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


def _slug(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "")).strip("-").lower() or "warsat-model"


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


def _runtime_command(protocol, model_ref, model_path, tuning):
    command = []
    model_mount = protocol.get("modelMount") or {}
    _, container_model_path = _model_mount_parts(model_path, model_ref, protocol)
    if protocol.get("modelArgument"):
        if protocol["modelFormat"] == "gguf":
            command.extend([protocol["modelArgument"], container_model_path or f"{model_mount.get('containerPath', '/models')}/{Path(model_ref).name}"])
        else:
            command.extend([protocol["modelArgument"], model_ref])
    command.extend(_runtime_arguments(protocol, tuning))
    return command


def _docker_run_preview(protocol, model_ref, model_path, host_port, container_name, tuning, limits):
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
    command.extend(_runtime_command(protocol, model_ref, model_path, tuning))
    return command


def _yaml_scalar(value):
    return json.dumps(str(value))


def _compose_preview(protocol, model_ref, model_path, host_port, container_name, strength, tuning, limits):
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
    command = _runtime_command(protocol, model_ref, model_path, tuning)
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


def make_plan(payload):
    protocol = get_protocol(payload.get("protocolId") or payload.get("protocol_id"))
    model_ref = str(payload.get("modelRef") or payload.get("model_ref") or "").strip()
    model_path = str(payload.get("modelPath") or payload.get("model_path") or "").strip()
    role = str(payload.get("role") or protocol.get("defaultRole") or "helper")
    strength = _safe_strength(payload.get("strengthProfile") or payload.get("strength_profile"))
    host_port = int(payload.get("hostPort") or payload.get("host_port") or protocol["defaultHostPort"])
    container_name = _slug(payload.get("containerName") or f"rasputin-{protocol['id']}-{host_port}")
    tuning = _build_tuning(payload, protocol, strength)
    limits = _build_limits(payload)

    if not model_ref and protocol["modelFormat"] != "gguf":
        raise AppError("warsat_model_required", "Enter a model id for this Warsat protocol.", 400)
    if protocol["modelFormat"] == "gguf":
        if not model_path:
            raise AppError("warsat_model_path_required", "Enter the mounted GGUF model folder or file path.", 400)
        if model_path.lower().endswith(".gguf"):
            model_ref = Path(model_path).name
        elif not model_ref:
            model_ref = Path(model_path).name

    endpoint = _endpoint_for(protocol["hostBinding"], host_port)
    model_key = _slug(f"{protocol['runtime']}-{model_ref or protocol['id']}-{host_port}")
    docker_run = _docker_run_preview(protocol, model_ref, model_path, host_port, container_name, tuning, limits)
    compose_preview = _compose_preview(protocol, model_ref, model_path, host_port, container_name, strength, tuning, limits)
    dockerfile_preview = _dockerfile_preview(protocol)
    execution = _docker_runtime_enabled()
    docker_control_enabled = execution["dockerControlEnabled"]
    warnings = []
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
    if tuning.get("maxModelLen", 0) >= 32768:
        warnings.append("Long context can sharply increase VRAM usage and startup time.")
    if limits.get("memoryLimitGb") and limits["memoryLimitGb"] < 8:
        warnings.append("Memory limit is low for most model runtimes.")

    plan = {
        "planId": f"warsat-{uuid.uuid4().hex[:12]}",
        "createdAt": time.time(),
        "status": "planned",
        "protocolId": protocol["id"],
        "protocolName": protocol["name"],
        "runtime": protocol["runtime"],
        "image": protocol["image"],
        "modelFormat": protocol["modelFormat"],
        "modelRef": model_ref,
        "modelPath": model_path,
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


def _run_command(args, timeout=120, check=True):
    if not isinstance(args, list) or not args or args[0] != "docker":
        raise AppError("warsat_command_rejected", "Warsat can only execute generated Docker commands.", 400)
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


def _validate_deploy_plan(plan):
    if not isinstance(plan, dict):
        raise AppError("warsat_plan_invalid", "Create a launch plan before deploying.", 400)
    security.require("allow_docker_control")
    security.require("allow_model_registry_edit")
    execution = _docker_runtime_enabled()
    if not execution["enabled"]:
        raise AppError("warsat_execution_disabled", execution["message"], 403)

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
    if pull_cmd[:2] != ["docker", "pull"] or pull_cmd[-1] != protocol["image"]:
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
    if protocol["image"] not in run_cmd:
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


def _operation_approval(action_type, container_name, labels):
    return approvals.create(
        action_type,
        {
            "container": container_name,
            "protocolId": labels.get("rasputin.protocol", ""),
            "runtime": labels.get("rasputin.runtime", ""),
            "workspace": "Warsat runtime",
        },
        risk_level="approval_required",
        workspace="Warsat runtime",
        ttl=10 * 60,
    )


def _container_operation(container_name, action, approval_id=None):
    execution = _docker_runtime_enabled()
    if not execution["enabled"]:
        raise AppError("warsat_execution_disabled", execution["message"], 403)
    name, labels = _managed_container(container_name)
    action_type = f"warsat_{action}"
    if not approval_id:
        approval = _operation_approval(action_type, name, labels)
        audit.log(f"{action_type}_approval_requested", {"container": name, "approvalId": approval["id"]})
        return {
            "approvalRequired": True,
            "status": "waitingForApproval",
            "approval": approval,
            "containerName": name,
            "message": f"Approval created. Approve it before Warsat can {action} this container.",
        }
    approvals.require_approved(approval_id, action_type)
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

    if not approval_id:
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
            "approval": approval,
            "containerName": container_name,
            "modelKey": registry_entry["key"],
            "endpoint": registry_entry["base_url"],
            "message": "Approval created. Approve it from Activity or Approvals, then run the deploy again.",
        }

    approvals.require_approved(approval_id, "warsat_deploy")

    audit.log("warsat_deploy_started", {
        "planId": plan.get("planId"),
        "approvalId": approval_id,
        "protocolId": protocol["id"],
        "image": protocol["image"],
        "container": container_name,
        "modelKey": registry_entry["key"],
    })

    pull = _run_command(pull_cmd, timeout=DEPLOY_TIMEOUT_SECONDS)
    _run_command(["docker", "rm", "-f", container_name], timeout=60, check=False)
    started = _run_command(run_cmd, timeout=120)
    saved = model_registry.upsert(registry_entry)
    status = _container_status(container_name)

    result = {
        "planId": plan.get("planId"),
        "status": "starting" if status.lower().startswith("up") else status,
        "containerId": started["stdout"],
        "containerName": container_name,
        "modelKey": saved["key"],
        "registryEntry": saved,
        "endpoint": registry_entry["base_url"],
        "healthUrl": plan.get("healthUrl"),
        "pull": pull,
        "run": started,
        "nextSteps": [
            "Wait for the model server to finish loading.",
            "Open Models and run Discover/Test on the new Warsat model.",
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
