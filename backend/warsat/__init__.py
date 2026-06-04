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


def _docker_run_preview(protocol, model_ref, model_path, host_port, container_name):
    command = [
        "docker", "run", "-d",
        "--name", container_name,
        "-p", f"{protocol['hostBinding']}:{host_port}:{protocol['containerPort']}",
        "--security-opt", "no-new-privileges",
    ]
    if protocol.get("gpu", {}).get("required"):
        command.extend(["--gpus", "all"])
    for mount in protocol.get("dataMounts") or []:
        mode = "ro" if mount.get("readOnly") else "rw"
        command.extend(["-v", f"{mount['hostPath']}:{mount['containerPath']}:{mode}"])
    model_mount = protocol.get("modelMount") or {}
    if model_path and model_mount.get("containerPath"):
        mode = "ro" if model_mount.get("readOnly", True) else "rw"
        command.extend(["-v", f"{model_path}:{model_mount['containerPath']}:{mode}"])
    command.append(protocol["image"])
    if protocol.get("modelArgument"):
        if protocol["modelFormat"] == "gguf":
            command.extend([protocol["modelArgument"], f"{model_mount.get('containerPath', '/models')}/{Path(model_ref).name}"])
        else:
            command.extend([protocol["modelArgument"], model_ref])
    command.extend(protocol.get("defaultArguments") or [])
    return command


def make_plan(payload):
    protocol = get_protocol(payload.get("protocolId") or payload.get("protocol_id"))
    model_ref = str(payload.get("modelRef") or payload.get("model_ref") or "").strip()
    model_path = str(payload.get("modelPath") or payload.get("model_path") or "").strip()
    role = str(payload.get("role") or protocol.get("defaultRole") or "helper")
    host_port = int(payload.get("hostPort") or payload.get("host_port") or protocol["defaultHostPort"])
    container_name = _slug(payload.get("containerName") or f"rasputin-{protocol['id']}-{host_port}")

    if not model_ref and protocol["modelFormat"] != "gguf":
        raise AppError("warsat_model_required", "Enter a model id for this Warsat protocol.", 400)
    if protocol["modelFormat"] == "gguf":
        if not model_path:
            raise AppError("warsat_model_path_required", "Enter the mounted GGUF model folder or file path.", 400)
        if not model_ref:
            model_ref = Path(model_path).name

    endpoint = _endpoint_for(protocol["hostBinding"], host_port)
    model_key = _slug(f"{protocol['runtime']}-{model_ref or protocol['id']}-{host_port}")
    docker_run = _docker_run_preview(protocol, model_ref, model_path, host_port, container_name)
    docker_control_enabled = bool(security.load().get("allow_docker_control", False))
    warnings = []
    if not docker_control_enabled:
        warnings.append("Docker control is disabled. This plan cannot be executed from Rasputin yet.")
    if protocol.get("hostBinding") != "127.0.0.1":
        warnings.append("Protocol does not bind to 127.0.0.1. Review before execution.")
    if protocol.get("hostNetwork"):
        warnings.append("Protocol requests host networking. Rasputin should reject this by default.")
    if protocol.get("gpu", {}).get("required"):
        warnings.append("This protocol expects GPU passthrough to Docker.")

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
