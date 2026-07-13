from fastapi import APIRouter, Depends
from pydantic import BaseModel
import copy
import logging

from backend.core import runtime_store as store
from backend.core import security as core_security
from backend.api.core import require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    key: str
    value: dict | str | bool | int | list | float | None = None

DEFAULT_SETTINGS = {
    "general": {
        "theme": "rasputin-dark",
        "language": "en",
        "workspacePath": "/app/workspace",
        "markdownOutput": True,
        "testingMode": False
    },
    "runtime": {
        "autoRestart": True,
        "maxMemory": "16GB",
        "timeout": 3600,
        "logLevel": "INFO",
        "gpuEnabled": False
    },
    "security": {
        "requireAuth": False,
        "sessionTimeout": 24,
        "strictMode": True,
        "allowUnsigned": False
    },
    "deployments": {
        "autoDeploy": False,
        "registryUrl": "docker.io",
        "approvalRequired": True,
        "rollbackOnFail": True
    },
    "integrations": {
        "huggingfaceEnabled": True,
        "ollamaEnabled": True,
        "githubEnabled": False
    },
    "models": {
        "defaultEngine": "llamacpp",
        "downloadPath": "",
        "autoQuantization": True,
        "allowUnverifiedSources": False
    },
    "resources": {
        "cpuLimit": 4,
        "memoryLimit": 8192,
        "gpuAllocation": 0,
        "diskQuota": 50
    },
    "notifications": {
        "emailAlerts": False,
        "slackAlerts": False,
        "notifyOnFailure": True,
        "notifyOnSuccess": False
    },
    "audit": {
        "auditEnabled": True,
        "retentionDays": 30,
        "logPayloads": False
    },
    "diagnostics": {
        "autoReport": False,
        "debugMode": False,
        "profiling": False
    }
}

def _get_hydrated_settings():
    saved_settings = store.get_kv("platform_settings", {})
    if not isinstance(saved_settings, dict):
        saved_settings = {}
        
    hydrated = copy.deepcopy(DEFAULT_SETTINGS)
    for domain, domain_defaults in hydrated.items():
        if domain in saved_settings and isinstance(saved_settings[domain], dict):
            domain_defaults.update(saved_settings[domain])
    # Preserve saved domains that have no defaults entry. Without this, any
    # update_setting() round-trip re-saved only the default domains and
    # silently erased everything else (the "models" domain lost defaultEngine
    # on every reload this way).
    for domain, saved in saved_settings.items():
        if domain not in hydrated and isinstance(saved, dict):
            hydrated[domain] = copy.deepcopy(saved)
    # The enforcement flags (allow_docker_control, privacy_lock, ...) live in
    # the core security config, not platform_settings. Overlay them so the
    # Settings > Security page always shows what is actually enforced.
    hydrated.setdefault("security", {}).update(core_security.load())
    return hydrated

def _apply_dynamic_settings(domain: str, key: str, value: any):
    if domain == "diagnostics" and key == "debugMode":
        level = logging.DEBUG if value else logging.INFO
        logging.getLogger().setLevel(level)
        print(f"Set root logger level to {'DEBUG' if value else 'INFO'}")
    elif domain == "runtime" and key == "logLevel":
        if isinstance(value, str):
            level_name = value.upper()
            level = getattr(logging, level_name, logging.INFO)
            logging.getLogger().setLevel(level)
            print(f"Set root logger level to {level_name}")

@router.get("")
def get_all_settings(_user=Depends(require_admin)):
    return _get_hydrated_settings()

@router.post("/{domain}")
def update_setting(domain: str, data: SettingUpdate, _user=Depends(require_admin)):
    # Security enforcement flags must land in the core security config —
    # writing them only to platform_settings would leave the toggle cosmetic
    # while warsat/mcp keep enforcing the old value.
    if domain == "security" and data.key in core_security.defaults():
        cfg = core_security.load()
        cfg[data.key] = data.value
        core_security.save(cfg)
        return {"updatedSettings": _get_hydrated_settings()["security"]}

    all_settings = _get_hydrated_settings()

    if domain not in all_settings:
        all_settings[domain] = {}

    all_settings[domain][data.key] = data.value
    store.set_kv("platform_settings", all_settings)

    _apply_dynamic_settings(domain, data.key, data.value)

    return {"updatedSettings": all_settings[domain]}

@router.post("/validate/{domain}")
def validate_setting(domain: str, data: dict, _user=Depends(require_admin)):
    return {"valid": True}

@router.get("/export")
def export_settings(_user=Depends(require_admin)):
    return _get_hydrated_settings()

@router.post("/import")
def import_settings(data: dict, _user=Depends(require_admin)):
    store.set_kv("platform_settings", data)
    return {"success": True}

@router.post("/restore")
def restore_defaults(data: dict, _user=Depends(require_admin)):
    domain = data.get("domain", "all")
    if domain == "all":
        store.set_kv("platform_settings", {})
    else:
        all_settings = store.get_kv("platform_settings", {})
        if isinstance(all_settings, dict) and domain in all_settings:
            del all_settings[domain]
            store.set_kv("platform_settings", all_settings)
    return {"success": True}

@router.get("/diagnostics")
def run_diagnostics(category: str = "all", _user=Depends(require_admin)):
    return {"status": "ok", "category": category}

@router.post("/integrations/test")
def test_integration(data: dict, _user=Depends(require_admin)):
    return {"success": True}

@router.post("/security/rotate")
def rotate_security(data: dict, _user=Depends(require_admin)):
    return {"success": True}
