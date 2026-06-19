import os

old_to_new = {
    "security": "core.security",
    "approvals": "core.approvals",
    "audit": "core.audit",
    "auth": "core.auth",
    "response": "core.response",
    "preferences": "core.preferences",
    "settings_api": "core.settings_api",
    "schedules": "core.schedules",
    "telegram": "core.telegram",
    "leak_guard": "core.leak_guard",
    "runtime_store": "core.runtime_store",
    "mcp_layer": "mcp.layer",
    "mcp_relay": "mcp.relay",
    "tool_relay": "mcp.tools",
    "skill_store": "mcp.skills",
    "mcp_fixture_server": "mcp.fixture",
    "model_registry": "models.registry",
    "model_catalog": "models.catalog",
    "model_providers": "models.providers",
    "model_acquisition": "models.acquisition",
    "model_secrets": "models.secrets",
    "models": "models.legacy",
    "agent": "engine.agent",
    "context_governor": "engine.context",
    "output": "engine.output",
    "rag": "rag.vector",
    "graphify": "rag.graph",
    "memory": "rag.memory",
}

def update_content(content):
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if not (line.startswith("import ") or line.startswith("from ")):
            continue
            
        # Fix specific root dot imports first
        if "from . import workspace" in line:
            line = line.replace("from . import workspace", "from backend import workspace")
        elif "from . import trials" in line:
            line = line.replace("from . import trials", "from backend import trials")
        elif "from . import warsat" in line:
            line = line.replace("from . import warsat", "from backend import warsat")

        for old, new in old_to_new.items():
            modified = False
            # Handle `from . import foo`
            # Needs to become `from backend.core import foo`
            if f"from . import {old}" in line:
                new_pkg = new.rsplit(".", 1)[0]
                new_mod = new.rsplit(".", 1)[1]
                if f" as {old}" not in line and f" as " not in line:
                    line = line.replace(f"from . import {old}", f"from backend.{new_pkg} import {new_mod} as {old}")
                elif f" as " in line:
                    alias = line.split(" as ")[1].strip()
                    line = f"from backend.{new_pkg} import {new_mod} as {alias}"
                modified = True
                
            # Handle `from backend import foo`
            elif f"from backend import {old}" in line:
                new_pkg = new.rsplit(".", 1)[0]
                new_mod = new.rsplit(".", 1)[1]
                if f" as " not in line:
                    line = line.replace(f"from backend import {old}", f"from backend.{new_pkg} import {new_mod} as {old}")
                else:
                    alias = line.split(" as ")[1].strip()
                    line = f"from backend.{new_pkg} import {new_mod} as {alias}"
                modified = True

            # Handle `from .foo import bar`
            elif f"from .{old} import" in line:
                line = line.replace(f"from .{old} import", f"from backend.{new} import")
                modified = True
                
            # Handle `from backend.foo import bar`
            elif f"from backend.{old} import" in line:
                line = line.replace(f"from backend.{old} import", f"from backend.{new} import")
                modified = True

            # Handle `import backend.foo`
            elif f"import backend.{old}" in line:
                line = line.replace(f"import backend.{old}", f"import backend.{new} as {old}")
                modified = True

            if modified:
                break

        lines[i] = line
    return "\n".join(lines)

for root, _, files in os.walk("backend"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = update_content(content)
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)

for root, _, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = update_content(content)
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
