import json
import os
import re
import time
import uuid
from pathlib import Path

from .. import audit
from .. import security
from ..response import AppError

ROOT = Path(__file__).resolve().parents[2]
BUILTIN_PROTOCOL_DIR = ROOT / "warsat" / "protocols"
DATA_DIR = ROOT / "data" / "warsat"
USER_PROTOCOL_DIR = DATA_DIR / "protocols"

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
    return {
        "protocols": protocols,
        "count": len(protocols),
        "strengthProfiles": STRENGTH_PROFILES,
        "dockerControlEnabled": bool(security.load().get("allow_docker_control", False)),
        "executionEnabled": False,
        "message": "Warsat is in safe planning mode. It can generate launch plans but will not pull images or start containers yet.",
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
        "-p", f"{protocol['hostBinding']}:{host_port}:{protocol['containerPort']}",
        "--security-opt", "no-new-privileges",
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
    docker_control_enabled = bool(security.load().get("allow_docker_control", False))
    warnings = []
    if not docker_control_enabled:
        warnings.append("Docker control is disabled. This plan cannot be executed from Rasputin yet.")
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
        "executionEnabled": False,
        "dockerControlEnabled": docker_control_enabled,
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
            "Enable Docker control only if you want Rasputin to manage containers.",
            "Require approval before pulling images or starting containers.",
            "After the runtime is healthy, register the endpoint as a model role.",
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
