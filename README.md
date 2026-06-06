# Rasputin

Private, localhost AI workbench for local files, agent tasks, model routing, RAG, Graphify, and brokered web research.

The core privacy model is:

```text
approved local folders -> Rasputin -> local model endpoints
internet access -> MCP web broker only
```

Models do not receive direct internet access. Web search is brokered, query-guarded, approval-gated by default, and audited.

## Current Status

Rasputin now includes:

- FastAPI backend served through `server.py`
- local admin login with first-run password printed to server logs
- session expiry plus a small local login-failure throttle
- structured API responses
- task manager with live SSE updates, cancellation, modes, traces, and outputs
- SQLite-backed local runtime in `data/rasputin.db` for sessions, tasks, messages, approvals, memory, skills, schedules, traces, outputs, and user preferences
- pause/resume task controls and durable session history
- persistent approval queue for risky tool actions
- optional Telegram approval integration using outbound Bot API polling only
- Warmind recall store with review queue, SQLite search, and local Markdown exports
- local master context export under `data/warmind-context/` for cross-session recall across chats, tasks, workspaces, and models
- `SKILL.md` skill registry with built-in descriptors and session-to-skill previews
- workspace registry for approved folders, read-only folder approvals, and GUI folder browsing
- safety flags and audit log
- local RAG index with citations and hash-vector retrieval
- typed Graphify nodes/edges with evidence
- vLLM/GGUF model registry and health checks
- Warsat model-runtime protocols, safe Docker launch plans, approval-gated deployment, and managed runtime controls
- Docker model controls blocked unless explicitly enabled
- Docker Compose localhost deployment
- React + Vite frontend source in `frontend-src/`, built into `frontend/` for FastAPI

If you fork or publish Rasputin, set your own Git remote. Local runtime state, credentials, model files, generated indexes, and workspace contents are ignored by default.

## Run With Docker

```powershell
cd path\to\Rasputin
.\start-wrapper.ps1
```

The Docker container starts Rasputin and exposes the UI on localhost. Open this manually after the container is healthy:

```text
http://127.0.0.1:8787
```

First-run credentials are printed in the server/container logs.

Rasputin does not use an automatic restart policy. It starts when you start the Docker container or run the launcher.

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

Run the backend:

```powershell
python server.py
```

If Python is installed somewhere else, call that interpreter explicitly:

```powershell
& "path\to\python.exe" server.py
```

Run the frontend dev server:

```powershell
npm install
npm run dev
```

Build the frontend that Docker/FastAPI serves:

```powershell
npm run build
```

Frontend source lives in `frontend-src/`. The built files in `frontend/` are the static app served by FastAPI, with cache-busted assets under `/static/assets/`.

Rasputin uses React + Vite with React-Bootstrap components. Bootstrap is compiled from a selective SCSS entry at `frontend-src/src/styles/bootstrap.scss` instead of importing the full prebuilt Bootstrap CSS bundle.

Frontend redesign planning lives in:

```text
docs/FRONTEND_REDESIGN_PLAN.md
```

Full system guide:

```text
docs/RASPUTIN_ARCHITECTURE_GUIDE.md
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

## Testing Harness

The harness uses a separate Docker Compose file and writes only to `testdata/`.

Windows:

```powershell
.\scripts\test.ps1
```

Keep the isolated test wrapper running after the test:

```powershell
.\scripts\test.ps1 -KeepRunning
```

macOS/Linux:

```bash
sh scripts/test.sh
```

Keep it running on macOS/Linux:

```bash
RASPUTIN_KEEP_RUNNING=1 sh scripts/test.sh
```

What it runs:

- isolated wrapper on `http://127.0.0.1:8877`
- backend route smoke tests
- live API smoke test
- dry-run task lifecycle test
- structured error check for bad GGUF paths
- camelCase response checks

Optional browser UI tests:

```powershell
npm install
npx playwright install chromium
.\scripts\test.ps1 -Ui
```

The `-Ui` path rebuilds the Vite frontend before Docker starts. The UI suite opens the test wrapper, checks the chat-first home screen, settings views, model registry, workspace browser, theme switching, dry-run send flow, and mobile screenshots.

## Local Models

Main vLLM endpoint defaults to:

```text
http://127.0.0.1:8000/v1
```

When Rasputin runs in Docker, localhost model URLs are translated to:

```text
http://host.docker.internal:8000/v1
```

GGUF auxiliary models can be registered for llama.cpp. Starting/stopping model containers requires Docker control mode and the `allow_docker_control` safety flag.

Warsat is the model-runtime control layer. It reads curated protocols from `warsat/protocols/`, generates safe launch plans, creates an approval before Docker execution, and registers the model endpoint after the container starts. Deployment requires the docker-control compose overlay, Docker control enabled in Safety, and an approved `warsat_deploy` request. Warsat can also list managed containers, show logs, and approval-gate stop/restart actions.

For model servers Rasputin does not launch itself, use the Models tab's local endpoint form. Any localhost OpenAI-compatible endpoint can be registered, tested, and selected while privacy lock blocks remote model URLs by default. Examples include LM Studio, Ollama, text-generation-webui, or a custom local server that exposes `/v1/models` and `/v1/chat/completions`.

See `docs/WARSAT_PROTOCOLS_PLAN.md`.

## Safety Defaults

- Privacy lock is on.
- Remote model endpoints are blocked.
- Docker control is off.
- Shell execution is off.
- Folder reorganization is off.
- File writes and moves require preview approval.
- Web search requires approval before the broker sends a query.
- Telegram approval messages are optional and redacted; they never include file contents, prompts, diffs, secrets, or raw model output.
- New approved folders default to read-only unless a route explicitly grants write permission.
- RAG and Graphify search are treated as local file access and are blocked when file read is disabled.
- Markdown output writes are blocked when file write is disabled.
- Docker model logs/status calls are blocked when Docker control is disabled.
- Local memory, RAG indexes, graph indexes, model registry state, workspaces, and model files are ignored by Git.

## Production Hardening Notes

- Wrapper ports bind to `127.0.0.1`.
- Unknown backend exceptions return a generic structured `internalError` response.
- GGUF imports are limited to the mounted `models/` folder or approved workspaces.
- Docker mount requests are preview/record only unless Docker control is enabled.
- Managed-model container status does not call Docker while Docker control is disabled.

## Repo Hygiene

Before pushing:

```powershell
git status --short
npm run checkRepoSafety
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

Rasputin stores private runtime state under ignored local `data/` storage. User preferences are imported from legacy `data/preferences.json` when present, then persisted in SQLite under `data/rasputin.db`. The legacy JSON file is not required for new preference writes and must not be committed.
