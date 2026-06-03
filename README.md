# Rasputin

Private, localhost AI workbench for local files, agent tasks, model routing, RAG, Graphify, and brokered web research.

The core privacy model is:

```text
approved local folders -> Rasputin -> local model endpoints
internet access -> MCP web broker only
```

Models do not receive direct internet access. Web search is brokered, query-guarded, and audited.

## Current Status

Rasputin now includes:

- FastAPI backend served through `server.py`
- local admin login with first-run password printed to server logs
- structured API responses
- task manager with live SSE updates, cancellation, modes, traces, and artifacts
- workspace registry for approved folders
- safety flags and audit log
- local RAG index with citations and hash-vector retrieval
- typed Graphify nodes/edges with evidence
- vLLM/GGUF model registry and health checks
- Docker Compose localhost deployment

The private GitHub repo target is:

```text
Shingenn5/Rasputin
```

That repo does not currently exist or is not accessible to the GitHub connector from this workspace. Create it privately before the first push, or install/authenticate GitHub CLI with explicit approval.

## Run With Docker

```powershell
cd "C:\Users\elliott\OneDrive\Documents\WrapperProject"
.\start-wrapper.ps1
```

Open:

```text
http://127.0.0.1:8787
```

First-run credentials are printed in the server/container logs.

Detached:

```powershell
.\start-wrapper.ps1 -Detached
docker compose logs rasputin-wrapper
```

Stop:

```powershell
.\stop-wrapper.ps1
```

## Native Development

```powershell
python server.py
```

Or with the bundled runtime:

```powershell
& "C:\Users\elliott\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" server.py
```

## Docker Profiles

Default wrapper only:

```powershell
docker compose up --build
```

Advanced Docker control:

```powershell
.\start-wrapper-docker-control.ps1
```

Optional future vector DB:

```powershell
docker compose --profile rag up --build
```

Optional brokered search service:

```powershell
docker compose --profile search up --build
```

## Local Models

Main vLLM endpoint defaults to:

```text
http://127.0.0.1:8000/v1
```

When Rasputin runs in Docker, localhost model URLs are translated to:

```text
http://host.docker.internal:8000/v1
```

GGUF helper models can be registered for llama.cpp. Starting/stopping model containers requires Docker control mode and the `allow_docker_control` safety flag.

## Safety Defaults

- Privacy lock is on.
- Remote model endpoints are blocked.
- Docker control is off.
- Shell execution is off.
- Folder reorganization is off.
- File writes and moves require preview approval.
- Local memory, RAG indexes, graph indexes, model registry state, workspaces, and model files are ignored by Git.

## Repo Hygiene

Before pushing:

```powershell
git status --short
```

The staged set should include source, docs, Docker files, scripts, examples, and placeholder folders only. It should not include:

- `data/`
- `workspace/`
- `models/`
- logs
- generated indexes
- local memory
- private model registry state
- local auth files
