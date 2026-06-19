import os
from fastapi import APIRouter, HTTPException, Request
from backend.core.response import ok
from backend.mcp import relay as mcp_relay
from backend.api.common import CamelModel

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])

class SandboxCallToolIn(CamelModel):
    tool_id: str
    args: dict

@router.post("/call-tool")
async def sandbox_call_tool(req: SandboxCallToolIn, request: Request):
    # Very simple authentication: expect a SANDBOX_TOKEN header
    token = request.headers.get("X-Sandbox-Token")
    if not token or token != os.environ.get("SANDBOX_SECRET_TOKEN"):
        raise HTTPException(status_code=403, detail="Invalid sandbox token")
    
    result = await mcp_relay.call_tool(req.tool_id, req.args)
    return ok(result)
