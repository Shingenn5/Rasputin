import asyncio
from fastapi import APIRouter, Depends
from backend.core.response import ok
from backend.models import registry as model_registry
from backend.models import catalog as model_catalog
from backend.models import providers as model_providers
from backend.models import acquisition as model_acquisition
from backend import warsat
from backend.api.common import CamelModel, current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["models"])

class ModelDownloadReq(BaseModel):
    modelId: str

class ModelIn(CamelModel):
    key: str | None = None
    name: str | None = None
    provider: str = "openai-compatible"
    role: str = "helper"
    base_url: str = ""
    model: str = ""
    api_key: str | None = None
    api_key_env: str | None = None
    anthropic_version: str | None = None
    clear_api_key: bool = False
    runtime: str | None = None
    context_window: int | None = None
    max_tokens: int | None = None
    port: int | None = None
    container: str | None = None
    image: str | None = None
    enabled: bool = True
    managed: bool = False
    notes: str | None = None

class GgufImportIn(CamelModel):
    path: str
    key: str | None = None
    name: str | None = None
    role: str = "helper"
    port: int | None = None
    context: int = 4096
    n_gpu_layers: int = 0
    image: str | None = None
    notes: str | None = None

class GgufScanIn(CamelModel):
    root: str | None = None

class ModelKeyIn(CamelModel):
    key: str

class ModelLogsIn(CamelModel):
    key: str
    limit: int = 120

class ModelCatalogRefreshIn(CamelModel):
    force: bool = False

@router.get("/models")
async def models(_user=Depends(current_user)):
    return ok(model_registry.enabled_models())

@router.post("/models/download")
async def start_model_download(req: ModelDownloadReq, _user=Depends(current_user)):
    state = model_acquisition.start_download(req.modelId)
    return ok(state)

@router.get("/models/downloads/active")
async def get_active_downloads(_user=Depends(current_user)):
    return ok(model_acquisition.get_active_downloads())

@router.get("/model-registry")
async def model_registry_list(_user=Depends(current_user)):
    return ok({"models": model_registry.all_models(), "providers": model_providers.public_provider_options()})

@router.get("/model-providers")
async def model_provider_list(_user=Depends(current_user)):
    return ok({"providers": model_providers.public_provider_options()})

@router.get("/model-catalog")
async def model_catalog_get(fit: bool = False, _user=Depends(current_user)):
    hardware = await asyncio.to_thread(warsat.hardware_probe) if fit else None
    return ok(model_catalog.catalog(refresh=False, hardware=hardware))

@router.post("/model-catalog/refresh")
async def model_catalog_refresh(req: ModelCatalogRefreshIn | None = None, _user=Depends(current_user)):
    return ok(model_catalog.catalog(refresh=True, force=bool(req.force if req else False)))

@router.get("/model-catalog/search")
async def model_catalog_search(
    q: str = "", type: str = "", sort: str = "downloads",
    direction: int = -1, limit: int = 100, fit: bool = False, _user=Depends(current_user)
):
    hardware = await asyncio.to_thread(warsat.hardware_probe) if fit else None
    return ok(model_catalog.search_hf(query=q, model_type=type, sort=sort, direction=direction, limit=limit, hardware=hardware))

@router.get("/model-catalog/model/{model_id:path}")
async def model_catalog_detail(model_id: str, _user=Depends(current_user)):
    return ok(model_catalog.hf_model_detail(model_id))

@router.post("/model-registry/upsert")
async def model_registry_upsert(req: ModelIn, _user=Depends(current_user)):
    return ok(model_registry.upsert(req.model_dump()))

@router.post("/model-registry/import-gguf")
async def model_registry_import_gguf(req: GgufImportIn, _user=Depends(current_user)):
    return ok(model_registry.import_gguf(req.model_dump()))

@router.post("/model-registry/scan-gguf")
async def model_registry_scan_gguf(req: GgufScanIn | None = None, _user=Depends(current_user)):
    return ok(model_registry.scan_gguf(req.root if req else None))

@router.post("/model-registry/start")
async def model_registry_start(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.start_model(req.key))

@router.post("/model-registry/stop")
async def model_registry_stop(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.stop_model(req.key))

@router.post("/model-registry/test")
async def model_registry_test(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.test_model(req.key))

@router.post("/model-registry/discover")
async def model_registry_discover(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.discover_model(req.key))

@router.post("/model-registry/repair")
async def model_registry_repair(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.repair_model(req.key))

@router.post("/model-registry/logs")
async def model_registry_logs(req: ModelLogsIn, _user=Depends(current_user)):
    return ok(model_registry.logs_model(req.key, req.limit))

@router.post("/model-registry/delete")
async def model_registry_delete(req: ModelKeyIn, _user=Depends(current_user)):
    return ok(model_registry.delete_model(req.key))
