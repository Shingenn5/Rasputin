"""In-container tool client for skills. Talks to the host over a private stdio
RPC (no network) instead of HTTP — the container runs with `--network none`.

The channel (a writer on the real stdout) is installed by wrapper.main() BEFORE
any skill code runs; skill `print()` output is redirected to stderr so it can't
corrupt the RPC framing. Messages are newline-delimited JSON:
  container -> host (stdout): {"type":"tool_call","tool_id":...,"args":...}
                             {"type":"result","result":...}
  host -> container (stdin):  {"type":"tool_result","ok":bool,"data"/"error":...}
"""
import json
import sys

_rpc_out = None  # a writable text stream on the real stdout, set by wrapper.main()


def set_channel(rpc_out):
    global _rpc_out
    _rpc_out = rpc_out


def _send(message):
    _rpc_out.write(json.dumps(message) + "\n")
    _rpc_out.flush()


def send_result(result):
    _send({"type": "result", "result": result})


class MCPClient:
    async def call_tool(self, tool_id, args=None):
        # Async signature (skills await it) with a blocking request/response body:
        # nothing else runs in the skill's loop, so the blocking read is safe and
        # keeps the protocol strictly half-duplex (no interleaving deadlock).
        _send({"type": "tool_call", "tool_id": tool_id, "args": args or {}})
        line = sys.stdin.readline()
        if not line:
            raise RuntimeError("sandbox host closed the connection")
        resp = json.loads(line)
        if not resp.get("ok"):
            raise RuntimeError(f"Tool error: {resp.get('error')}")
        return resp.get("data")


class SandboxLogger:
    def __call__(self, msg):
        print(f"[skill] {msg}")  # redirected to stderr -> surfaced as host logs


mcp = MCPClient()
log = SandboxLogger()
