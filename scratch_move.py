import os
import subprocess

moves = {
    # Core
    "backend/security.py": "backend/core/security.py",
    "backend/approvals.py": "backend/core/approvals.py",
    "backend/audit.py": "backend/core/audit.py",
    "backend/auth.py": "backend/core/auth.py",
    "backend/response.py": "backend/core/response.py",
    "backend/preferences.py": "backend/core/preferences.py",
    "backend/settings_api.py": "backend/core/settings_api.py",
    "backend/schedules.py": "backend/core/schedules.py",
    "backend/telegram.py": "backend/core/telegram.py",
    "backend/leak_guard.py": "backend/core/leak_guard.py",
    "backend/runtime_store.py": "backend/core/runtime_store.py",

    # MCP
    "backend/mcp_layer.py": "backend/mcp/layer.py",
    "backend/mcp_relay.py": "backend/mcp/relay.py",
    "backend/tool_relay.py": "backend/mcp/tools.py",
    "backend/skill_store.py": "backend/mcp/skills.py",
    "backend/mcp_fixture_server.py": "backend/mcp/fixture.py",

    # Models
    "backend/model_registry.py": "backend/models/registry.py",
    "backend/model_catalog.py": "backend/models/catalog.py",
    "backend/model_providers.py": "backend/models/providers.py",
    "backend/model_acquisition.py": "backend/models/acquisition.py",
    "backend/model_secrets.py": "backend/models/secrets.py",
    "backend/models.py": "backend/models/legacy.py",  # 'models.py' could clash with the folder 'models/' so we'll rename to 'legacy.py'

    # Engine
    "backend/agent.py": "backend/engine/agent.py",
    "backend/context_governor.py": "backend/engine/context.py",
    "backend/output.py": "backend/engine/output.py",

    # RAG
    "backend/rag.py": "backend/rag/vector.py",
    "backend/graphify.py": "backend/rag/graph.py",
    "backend/memory.py": "backend/rag/memory.py",

    # API
    # I'll leave main.py in backend/main.py for now, we will split it later.
}

for src, dst in moves.items():
    if os.path.exists(src):
        print(f"git mv {src} {dst}")
        subprocess.run(["git", "mv", src, dst])

# Also create __init__.py files in all new packages
for pkg in ["core", "mcp", "models", "engine", "rag", "api"]:
    open(f"backend/{pkg}/__init__.py", "w").close()

print("Moves complete.")
