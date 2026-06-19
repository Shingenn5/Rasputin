import asyncio
import os
import uuid
import secrets
from pathlib import Path

# Note: In production, the token should be consistent or regenerated dynamically and passed to the host app as well.
# For now, we will assume SANDBOX_SECRET_TOKEN is set in the host environment, and we pass it down.
# If it's not set, we generate a random one and set it in the host's os.environ so the API can validate it.
if not os.environ.get("SANDBOX_SECRET_TOKEN"):
    os.environ["SANDBOX_SECRET_TOKEN"] = secrets.token_hex(16)

async def run_skill_in_sandbox(skill_path, objective, plan, log):
    log(f"Starting sandbox for {skill_path}...")
    
    # Read the skill file
    skill_code = Path(skill_path).read_text(encoding="utf-8")
    
    token = os.environ.get("SANDBOX_SECRET_TOKEN")
    
    # We must determine the API URL. If running inside Docker (WRAPPER_RUNTIME=docker),
    # the host is reachable at host.docker.internal. Otherwise, localhost or 127.0.0.1.
    # The default in client.py is host.docker.internal:8787/api/sandbox.
    
    cmd = [
        "docker", "run", "-i", "--rm",
        "--network", "host", # Use host network so it can reach localhost if running natively
        "-e", f"SANDBOX_SECRET_TOKEN={token}",
        "-e", f"RASPUTIN_API_URL={os.environ.get('RASPUTIN_API_URL', 'http://127.0.0.1:8787/api/sandbox')}",
        "rasputin-sandbox",
        "python", "/sandbox/wrapper.py", objective, plan
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate(input=skill_code.encode("utf-8"))
    
    out_text = stdout.decode("utf-8")
    err_text = stderr.decode("utf-8")
    
    if err_text:
        log(f"Sandbox stderr:\n{err_text}")
        
    if "---RESULT---" in out_text:
        parts = out_text.split("---RESULT---")
        if parts[0].strip():
            log(f"Sandbox stdout:\n{parts[0].strip()}")
        return parts[-1].strip()
        
    return out_text.strip()
