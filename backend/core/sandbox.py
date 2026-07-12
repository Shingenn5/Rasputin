import asyncio
import json

# §6.2 RESOLVED: skill containers run with NO network (`--network none`) instead of
# `--network host`. The skill reaches host tools over a private stdio RPC, not HTTP,
# so it can't touch the host's network namespace, the LAN, or the internet. (The tool
# callback itself remains a host-privilege surface — see THREAT_MODEL §6.2.)

# Tool results can be large (a workspace preview alone is up to ~128KB), so raise the
# asyncio stream buffer well past its 64KB default or readline() would raise on a big frame.
_STREAM_LIMIT = 16 * 1024 * 1024


async def run_skill_in_sandbox(skill_name, skill_code, objective, plan, log):
    from backend.mcp import relay as mcp_relay

    log(f"Starting sandbox for {skill_name}...")
    cmd = [
        "docker", "run", "-i", "--rm",
        "--network", "none",  # no host network / no egress; tools come over stdio
        "rasputin-sandbox",
        "python", "/sandbox/wrapper.py",
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=_STREAM_LIMIT,
    )

    async def drain_logs():
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            log(f"[sandbox] {line.decode('utf-8', 'replace').rstrip()}")

    logs_task = asyncio.create_task(drain_logs())
    result = None
    try:
        # 1. Send the skill code + task as the first stdin frame.
        proc.stdin.write((json.dumps({
            "type": "init", "code": skill_code, "objective": objective, "plan": plan,
        }) + "\n").encode("utf-8"))
        await proc.stdin.drain()

        # 2. Service tool-call requests until the skill returns its result.
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8"))
            except ValueError:
                log(f"[sandbox] ignoring non-JSON stdout: {line[:200]!r}")
                continue

            kind = msg.get("type")
            if kind == "tool_call":
                try:
                    data = await mcp_relay.call_tool(msg["tool_id"], msg.get("args") or {})
                    resp = {"type": "tool_result", "ok": True, "data": data}
                    payload = json.dumps(resp)
                except Exception as exc:  # tool failure OR non-serializable result
                    payload = json.dumps({"type": "tool_result", "ok": False, "error": str(exc)})
                proc.stdin.write((payload + "\n").encode("utf-8"))
                await proc.stdin.drain()
            elif kind == "result":
                result = msg.get("result")
                break
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        await proc.wait()
        await logs_task

    return result
