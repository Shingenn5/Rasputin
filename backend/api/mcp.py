from fastapi import APIRouter, Depends
from backend.core.response import ok
from backend.api.common import CamelModel, current_user, hub
from backend.mcp import relay as mcp_relay
from backend.mcp import tools as tool_relay

router = APIRouter(prefix="/api", tags=["mcp", "tools"])

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


@router.get("/tools")
async def tools_get(_user=Depends(current_user)):
    return ok(tool_relay.catalog())

@router.get("/mcp/servers")
async def mcp_servers(_user=Depends(current_user)):
    return ok(mcp_relay.servers())

@router.post("/mcp/servers")
async def mcp_servers_create(req: McpRelayIn, _user=Depends(current_user)):
    return ok(mcp_relay.register(req.model_dump()))

@router.post("/mcp/fixtures/operator/register")
async def mcp_operator_fixture_register(_user=Depends(current_user)):
    return ok(mcp_relay.register_operator_fixture())

@router.post("/mcp/servers/{server_id}/enable")
async def mcp_servers_enable(server_id: str, _user=Depends(current_user)):
    return ok(mcp_relay.set_enabled(server_id, True))

@router.post("/mcp/servers/{server_id}/disable")
async def mcp_servers_disable(server_id: str, _user=Depends(current_user)):
    return ok(mcp_relay.set_enabled(server_id, False))

@router.post("/mcp/servers/{server_id}/discover")
async def mcp_servers_discover(server_id: str, _user=Depends(current_user)):
    return ok(await mcp_relay.discover(server_id))

@router.post("/mcp/servers/{server_id}/start")
async def mcp_servers_start(server_id: str, req: McpServerActionIn | None = None, _user=Depends(current_user)):
    return ok(await mcp_relay.start(server_id, approval_id=req.approval_id if req else None))

@router.post("/mcp/servers/{server_id}/stop")
async def mcp_servers_stop(server_id: str, _user=Depends(current_user)):
    return ok(await mcp_relay.stop(server_id))

@router.post("/mcp/servers/{server_id}/restart")
async def mcp_servers_restart(server_id: str, req: McpServerActionIn | None = None, _user=Depends(current_user)):
    return ok(await mcp_relay.restart(server_id, approval_id=req.approval_id if req else None))

@router.post("/mcp/servers/{server_id}/test")
async def mcp_servers_test(server_id: str, _user=Depends(current_user)):
    return ok(await mcp_relay.test_server(server_id))

@router.get("/mcp/servers/{server_id}/tools")
async def mcp_server_tools(server_id: str, _user=Depends(current_user)):
    return ok(mcp_relay.server_tools(server_id))

@router.post("/mcp/tools/{tool_id:path}/classify")
async def mcp_tool_classify(tool_id: str, req: McpToolClassifyIn, _user=Depends(current_user)):
    return ok(mcp_relay.classify_tool(tool_id, req.model_dump()))

@router.post("/mcp/tools/{tool_id:path}/test-call")
async def mcp_tool_test_call(tool_id: str, req: McpToolTestCallIn, _user=Depends(current_user)):
    detail = await hub.run_tool_test(tool_id, {"message": req.message})
    return ok(detail)
