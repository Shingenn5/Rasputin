import os
import requests

class MCPClient:
    def __init__(self):
        self.api_url = os.environ.get("RASPUTIN_API_URL", "http://host.docker.internal:8787/api/sandbox")
        self.token = os.environ.get("SANDBOX_SECRET_TOKEN")

    async def call_tool(self, tool_id, args=None):
        if not self.token:
            raise ValueError("No sandbox token provided")
        
        headers = {"X-Sandbox-Token": self.token}
        payload = {"tool_id": tool_id, "args": args or {}}
        
        # We use requests here, but skills expect an async function,
        # so this synchronous call is wrapped in an async signature.
        response = requests.post(f"{self.api_url}/call-tool", json=payload, headers=headers)
        
        if not response.ok:
            raise RuntimeError(f"Tool call failed: {response.text}")
            
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Tool error: {data.get('error')}")
            
        return data.get("data")

class SandboxLogger:
    def __call__(self, msg):
        print(f"[Sandbox Log] {msg}")

mcp = MCPClient()
log = SandboxLogger()
