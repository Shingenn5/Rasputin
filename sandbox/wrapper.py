"""Skill entrypoint inside the `--network none` sandbox container.

Protocol: the host writes one `{"type":"init","code","objective","plan"}` line on
stdin, then answers each tool call. We return `{"type":"result","result":...}`.
The skill's own stdout is redirected to stderr up front so its prints become host
logs and can't corrupt the RPC framing on the real stdout.
"""
import asyncio
import importlib.util
import json
import os
import sys


def main():
    # Install the RPC channel BEFORE anything can write to stdout: dup the real
    # stdout for RPC, then point fd 1 (and Python's sys.stdout) at stderr so skill
    # output is captured as logs rather than parsed as protocol frames.
    rpc_out = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    import client
    client.set_channel(rpc_out)

    init_line = sys.stdin.readline()
    if not init_line:
        client.send_result(None)
        return
    init = json.loads(init_line)
    code, objective, plan = init.get("code", ""), init.get("objective", ""), init.get("plan", "")

    try:
        spec = importlib.util.spec_from_loader("skill", loader=None)
        skill = importlib.util.module_from_spec(spec)
        exec(code, skill.__dict__)
        result = asyncio.run(skill.run(objective, plan, client.mcp, client.log))
    except Exception:
        import traceback
        traceback.print_exc()  # -> stderr -> host logs
        client.send_result(None)
        sys.exit(1)

    client.send_result(result)


if __name__ == "__main__":
    main()
