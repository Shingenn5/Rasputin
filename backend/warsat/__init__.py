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
BUILTIN_RECIPE_DIR = ROOT / "cookbook" / "recipes"
DATA_DIR = ROOT / "data" / "warsat"
USER_RECIPE_DIR = DATA_DIR / "recipes"


def _slug(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "")).strip("-").lower() or "warsat-model"


def _safe_recipe_id(value):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "", str(value or "")).strip(".-") or "warsatRecipe"


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AppError("warsat_recipe_invalid", f"{path.name} is not valid JSON: {exc}", 400)


def _recipe_files():
    files = []
    for folder in [BUILTIN_RECIPE_DIR, USER_RECIPE_DIR]:
        if folder.exists():
            files.extend(sorted(folder.glob("*.json")))
    return files


def _normalize_recipe(recipe, source="builtin"):
    required = ["id", "name", "runtime", "image", "modelFormat", "defaultHostPort", "containerPort"]
    missing = [key for key in required if not recipe.get(key)]
    if missing:
        raise AppError("warsat_recipe_invalid", f"Recipe {recipe.get('id') or 'unknown'} is missing: {', '.join(missing)}", 400)
    security_config = recipe.get("security") or {}
    return {
        **recipe,
        "id": _safe_recipe_id(recipe["id"]),
        "source": source,
        "capabilities": list(recipe.get("capabilities") or []),
        "notes": list(recipe.get("notes") or []),
        "defaultRole": recipe.get("defaultRole") or "helper",
        "hostBinding": security_config.get("hostBinding") or "127.0.0.1",
        "noNewPrivileges": bool(security_config.get("noNewPrivileges", True)),
        "hostNetwork": bool(security_config.get("hostNetwork", False)),
    }


def list_recipes():
    recipes = []
    seen = set()
    for path in _recipe_files():
        source = "user" if USER_RECIPE_DIR in path.parents else "builtin"
        recipe = _normalize_recipe(_read_json(path), source)
        if recipe["id"] in seen:
            continue
        seen.add(recipe["id"])
        recipes.append(recipe)
    recipes.sort(key=lambda item: (item.get("runtime", ""), item.get("name", "")))
    return {
        "recipes": recipes,
        "count": len(recipes),
        "dockerControlEnabled": bool(security.load().get("allow_docker_control", False)),
        "executionEnabled": False,
        "message": "Warsat is in safe planning mode. It can generate launch plans but will not pull images or start containers yet.",
    }


def summary():
    data = list_recipes()
    return {
        "count": data["count"],
        "dockerControlEnabled": data["dockerControlEnabled"],
        "executionEnabled": data["executionEnabled"],
        "recipes": [
            {
                "id": item["id"],
                "name": item["name"],
                "runtime": item["runtime"],
                "modelFormat": item["modelFormat"],
                "capabilities": item.get("capabilities", []),
            }
            for item in data["recipes"]
        ],
    }


def get_recipe(recipe_id):
    recipe_id = _safe_recipe_id(recipe_id)
    for recipe in list_recipes()["recipes"]:
        if recipe["id"] == recipe_id:
            return recipe
    raise AppError("warsat_recipe_missing", "Warsat recipe was not found.", 404)


def _endpoint_for(host_binding, host_port):
    visible_host = "host.docker.internal" if os.environ.get("WRAPPER_RUNTIME") == "docker" else host_binding
    return f"http://{visible_host}:{host_port}/v1"


def _docker_run_preview(recipe, model_ref, model_path, host_port, container_name):
    command = [
        "docker", "run", "-d",
        "--name", container_name,
        "-p", f"{recipe['hostBinding']}:{host_port}:{recipe['containerPort']}",
        "--security-opt", "no-new-privileges",
    ]
    if recipe.get("gpu", {}).get("required"):
        command.extend(["--gpus", "all"])
    for mount in recipe.get("dataMounts") or []:
        mode = "ro" if mount.get("readOnly") else "rw"
        command.extend(["-v", f"{mount['hostPath']}:{mount['containerPath']}:{mode}"])
    model_mount = recipe.get("modelMount") or {}
    if model_path and model_mount.get("containerPath"):
        mode = "ro" if model_mount.get("readOnly", True) else "rw"
        command.extend(["-v", f"{model_path}:{model_mount['containerPath']}:{mode}"])
    command.append(recipe["image"])
    if recipe.get("modelArgument"):
        if recipe["modelFormat"] == "gguf":
            command.extend([recipe["modelArgument"], f"{model_mount.get('containerPath', '/models')}/{Path(model_ref).name}"])
        else:
            command.extend([recipe["modelArgument"], model_ref])
    command.extend(recipe.get("defaultArguments") or [])
    return command


def make_plan(payload):
    recipe = get_recipe(payload.get("recipeId") or payload.get("recipe_id"))
    model_ref = str(payload.get("modelRef") or payload.get("model_ref") or "").strip()
    model_path = str(payload.get("modelPath") or payload.get("model_path") or "").strip()
    role = str(payload.get("role") or recipe.get("defaultRole") or "helper")
    host_port = int(payload.get("hostPort") or payload.get("host_port") or recipe["defaultHostPort"])
    container_name = _slug(payload.get("containerName") or f"rasputin-{recipe['id']}-{host_port}")

    if not model_ref and recipe["modelFormat"] != "gguf":
        raise AppError("warsat_model_required", "Enter a model id for this Warsat recipe.", 400)
    if recipe["modelFormat"] == "gguf":
        if not model_path:
            raise AppError("warsat_model_path_required", "Enter the mounted GGUF model folder or file path.", 400)
        if not model_ref:
            model_ref = Path(model_path).name

    endpoint = _endpoint_for(recipe["hostBinding"], host_port)
    model_key = _slug(f"{recipe['runtime']}-{model_ref or recipe['id']}-{host_port}")
    docker_run = _docker_run_preview(recipe, model_ref, model_path, host_port, container_name)
    docker_control_enabled = bool(security.load().get("allow_docker_control", False))
    warnings = []
    if not docker_control_enabled:
        warnings.append("Docker control is disabled. This plan cannot be executed from Rasputin yet.")
    if recipe.get("hostBinding") != "127.0.0.1":
        warnings.append("Recipe does not bind to 127.0.0.1. Review before execution.")
    if recipe.get("hostNetwork"):
        warnings.append("Recipe requests host networking. Rasputin should reject this by default.")
    if recipe.get("gpu", {}).get("required"):
        warnings.append("This recipe expects GPU passthrough to Docker.")

    plan = {
        "planId": f"warsat-{uuid.uuid4().hex[:12]}",
        "createdAt": time.time(),
        "status": "planned",
        "recipeId": recipe["id"],
        "recipeName": recipe["name"],
        "runtime": recipe["runtime"],
        "image": recipe["image"],
        "modelFormat": recipe["modelFormat"],
        "modelRef": model_ref,
        "modelPath": model_path,
        "role": role,
        "hostPort": host_port,
        "containerPort": recipe["containerPort"],
        "containerName": container_name,
        "endpoint": endpoint,
        "healthUrl": endpoint.rstrip("/v1") + recipe.get("healthPath", "/v1/models"),
        "riskLevel": "approvalRequired",
        "requiresApproval": True,
        "executionEnabled": False,
        "dockerControlEnabled": docker_control_enabled,
        "commandPreview": {
            "pull": ["docker", "pull", recipe["image"]],
            "run": docker_run,
        },
        "expectedModelRegistryEntry": {
            "key": model_key,
            "name": f"{recipe['name']} - {model_ref or host_port}",
            "provider": recipe["runtime"],
            "role": role,
            "baseUrl": endpoint,
            "model": model_ref,
            "enabled": True,
            "managed": True,
            "runtime": f"warsat-{recipe['runtime']}",
            "container": container_name,
            "port": host_port,
        },
        "securityChecks": {
            "localhostOnly": recipe.get("hostBinding") == "127.0.0.1",
            "noNewPrivileges": recipe.get("noNewPrivileges", True),
            "hostNetwork": recipe.get("hostNetwork", False),
            "modelMountReadOnly": bool((recipe.get("modelMount") or {}).get("readOnly", True)),
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
        "recipeId": plan["recipeId"],
        "runtime": plan["runtime"],
        "role": plan["role"],
        "hostPort": plan["hostPort"],
        "executionEnabled": plan["executionEnabled"],
    })
    return plan
