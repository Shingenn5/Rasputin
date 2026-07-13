from fastapi import APIRouter, Depends, Request, Response, HTTPException
from backend.api.core import CamelModel, current_user, hub, require_admin
from backend.core.response import ok
from backend.mcp import relay as mcp_relay
from backend.mcp import tools as tool_relay
import os

router = APIRouter()

mcp_router = APIRouter(prefix="/api", tags=["mcp", "tools"])


class McpRelayIn(CamelModel):
    id: str | None = None
    name: str | None = None
    transport: str = "stdio"
    command: str | None = None
    args: list[str] | str | None = None
    env: dict | None = None
    cwd: str | None = None
    enabled: bool = False

class McpServerActionIn(CamelModel):
    approval_id: str | None = None

class McpToolClassifyIn(CamelModel):
    risk: str = "approval_required"
    permission_flag: str | None = None
    enabled: bool = True

class McpToolTestCallIn(CamelModel):
    message: str = "operator fixture ok"


@mcp_router.get("/tools")

async def tools_get(_user=Depends(current_user)):
    return ok(tool_relay.catalog())

@mcp_router.get("/mcp/servers")

async def mcp_servers(_user=Depends(current_user)):
    return ok(mcp_relay.servers())

@mcp_router.post("/mcp/servers")

async def mcp_servers_create(req: McpRelayIn, _user=Depends(require_admin)):
    return ok(mcp_relay.register(req.model_dump()))

@mcp_router.post("/mcp/fixtures/operator/register")

async def mcp_operator_fixture_register(_user=Depends(require_admin)):
    return ok(mcp_relay.register_operator_fixture())

@mcp_router.post("/mcp/servers/{server_id}/enable")

async def mcp_servers_enable(server_id: str, _user=Depends(require_admin)):
    return ok(mcp_relay.set_enabled(server_id, True))

@mcp_router.post("/mcp/servers/{server_id}/disable")

async def mcp_servers_disable(server_id: str, _user=Depends(require_admin)):
    return ok(mcp_relay.set_enabled(server_id, False))

@mcp_router.post("/mcp/servers/{server_id}/discover")

async def mcp_servers_discover(server_id: str, _user=Depends(require_admin)):
    return ok(await mcp_relay.discover(server_id))

@mcp_router.post("/mcp/servers/{server_id}/start")

async def mcp_servers_start(server_id: str, req: McpServerActionIn | None = None, _user=Depends(require_admin)):
    return ok(await mcp_relay.start(server_id, approval_id=req.approval_id if req else None))

@mcp_router.post("/mcp/servers/{server_id}/stop")

async def mcp_servers_stop(server_id: str, _user=Depends(require_admin)):
    return ok(await mcp_relay.stop(server_id))

@mcp_router.post("/mcp/servers/{server_id}/restart")

async def mcp_servers_restart(server_id: str, req: McpServerActionIn | None = None, _user=Depends(require_admin)):
    return ok(await mcp_relay.restart(server_id, approval_id=req.approval_id if req else None))

@mcp_router.post("/mcp/servers/{server_id}/test")

async def mcp_servers_test(server_id: str, _user=Depends(require_admin)):
    return ok(await mcp_relay.test_server(server_id))

@mcp_router.get("/mcp/servers/{server_id}/tools")

async def mcp_server_tools(server_id: str, _user=Depends(current_user)):
    return ok(mcp_relay.server_tools(server_id))

@mcp_router.post("/mcp/tools/{tool_id:path}/classify")

async def mcp_tool_classify(tool_id: str, req: McpToolClassifyIn, _user=Depends(require_admin)):
    return ok(mcp_relay.classify_tool(tool_id, req.model_dump()))

@mcp_router.post("/mcp/tools/{tool_id:path}/test-call")

async def mcp_tool_test_call(tool_id: str, req: McpToolTestCallIn, _user=Depends(require_admin)):
    detail = await hub.run_tool_test(tool_id, {"message": req.message})
    return ok(detail)

sandbox_router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


class SandboxCallToolIn(CamelModel):
    tool_id: str
    args: dict

@sandbox_router.post("/call-tool")

async def sandbox_call_tool(req: SandboxCallToolIn, request: Request):
    # Very simple authentication: expect a SANDBOX_TOKEN header
    token = request.headers.get("X-Sandbox-Token")
    if not token or token != os.environ.get("SANDBOX_SECRET_TOKEN"):
        raise HTTPException(status_code=403, detail="Invalid sandbox token")

    result = await mcp_relay.call_tool(req.tool_id, req.args)
    return ok(result)

router.include_router(mcp_router)
router.include_router(sandbox_router)
