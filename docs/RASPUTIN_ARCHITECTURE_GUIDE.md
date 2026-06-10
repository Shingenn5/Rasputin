# Rasputin Architecture Guide

This guide explains how Rasputin is built, how it runs, where things are stored, and how the main pieces talk to each other.

## 1. Mental Model

Rasputin is a local AI workbench.

The browser UI is only the control surface. The real application is a local FastAPI server that runs inside Docker or directly through Python.

```text
Browser
  -> http://127.0.0.1:8787
  -> Docker port mapping
  -> FastAPI server inside container
  -> backend services
  -> local model endpoints, workspace files, RAG, Graphify, audit log
```

The important privacy idea:

```text
approved local folders -> Rasputin backend -> local model endpoints
internet access -> brokered tools only, not direct model access
```

Models do not get direct file-system or internet access. Rasputin gives them curated context through backend tools.

## 2. Runtime Startup

### Docker Path

The main Docker files are:

```text
Dockerfile
docker-compose.yml
start-wrapper.ps1
stop-wrapper.ps1
```

`docker-compose.yml` starts the `rasputin-wrapper` service.

Important Compose details:

```yaml
ports:
  - "127.0.0.1:${WRAPPER_PORT:-8787}:8787"
```

This means:

- Rasputin listens on port `8787` inside the container.
- Docker exposes it only on host `127.0.0.1:8787`.
- Other machines on your network should not be able to reach it through this binding.

The container does not auto-restart:

```yaml
restart: "no"
```

That means Rasputin starts when you start the container. Docker Desktop should not resurrect it automatically after a reboot.

### What Runs Inside The Container

The Dockerfile ends with:

```dockerfile
CMD ["python", "-u", "server.py"]
```

So Docker starts Python, and Python starts the web server.

`server.py` reads:

```python
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8787"))
uvicorn.run("backend.main:app", host=HOST, port=PORT)
```

Inside Docker, Compose sets:

```text
HOST=0.0.0.0
PORT=8787
```

`0.0.0.0` inside the container means "listen on the container network interface." Docker then maps that to host `127.0.0.1:8787`.

Manual URL:

```text
http://127.0.0.1:8787
```

## 3. Frontend Build

Source lives here:

```text
frontend-src/
```

Built output lives here:

```text
frontend/
```

FastAPI serves `frontend/index.html` at `/` and serves built assets under `/static/`.

The Vite config is:

```text
vite.config.mjs
```

Important config:

```js
root: "frontend-src"
base: "/static/"
outDir: "../frontend"
```

That means Vite builds the React app from `frontend-src/` and writes static files into `frontend/`.

Production build:

```powershell
npm run build
```

The built assets are cache-busted:

```text
/static/assets/index-xxxxx.js
/static/assets/index-xxxxx.css
```

This avoids the old white-screen problem where the browser could reuse stale `/static/app.js`.

## 4. Frontend Stack

Current stack:

```text
React
Vite
React-Bootstrap
Bootstrap CSS from npm
React Query
React Markdown
rehype-sanitize
lucide-react
Playwright
```

Installed packages are listed in:

```text
package.json
package-lock.json
```

### Why Bootstrap Adds CSS

Bootstrap components work through CSS classes like:

```text
btn
card
form-control
row
col
badge
accordion
list-group
```

Those classes need CSS definitions to mean anything.

Rasputin imports Bootstrap CSS from the local npm package:

```text
bootstrap/dist/css/bootstrap.min.css
```

This keeps dependency warnings out of the normal Vite build while preserving React-Bootstrap component styling. Rasputin-specific layout, spacing, themes, and Warmind-style surfaces live in:

```text
frontend-src/src/styles/rasputin.css
```
- transitions
- utilities
- utilities

Rasputin-specific CSS is in:

```text
frontend-src/src/styles/rasputin.css
```

That file should stay small. It handles layout and product-specific polish, not generic button/form/card styling.

## 5. Frontend Source Structure

The frontend is now split into modules:

```text
frontend-src/src/
  main.jsx
  api/
    client.js
  app/
    App.jsx
    AppProviders.jsx
  components/
    AppShell.jsx
    Sidebar.jsx
  features/
    audit/
      AuditView.jsx
    auth/
      LoginShell.jsx
    chat/
      HomeView.jsx
    settings/
      SettingsView.jsx
    tasks/
      TasksView.jsx
  hooks/
    useLocalStorageFlag.js
  lib/
    constants.js
    display.js
  styles/
    rasputin.css
```

## Agent Runtime

Rasputin now has a durable native agent runtime. The source of truth is:

```text
data/rasputin.db
```

The SQLite database stores:

```text
sessions
messages
tasks
task_events
tool_calls
approvals
memory_items
skills
schedules
outputs
agent_traces
```

The in-process `AgentHub` still runs active async work, but it persists each task, log, trace, output, message, and session update as the task moves through the pipeline.

The runtime pipeline is:

```text
intake
  -> context assembly
  -> planning
  -> tool planning
  -> approval check
  -> execution
  -> reflection
  -> memory review
  -> output write
```

Existing `/api/tasks` calls remain compatible. New runtime APIs include:

```text
GET  /api/sessions
GET  /api/sessions/{id}
POST /api/tasks/{id}/pause
POST /api/tasks/{id}/resume
GET  /api/approvals
POST /api/approvals/{id}/approve
POST /api/approvals/{id}/deny
POST /api/memory/search
GET  /api/memory/review
POST /api/memory/review
GET  /api/skills
POST /api/skills/create-from-session
GET  /api/integrations/telegram
POST /api/integrations/telegram/configure
POST /api/integrations/telegram/test
GET  /api/schedules
POST /api/schedules
```

## Memory

Memory is SQLite-backed and exported to local Markdown files:

```text
data/memory/user.md
data/memory/memory.md
data/memory/projects/<workspaceId>.md
```

The compatibility functions `load_memory()` and `remember()` still exist, but they now write to `memory_items` in SQLite. Existing `data/memory.json` is imported once on first boot and copied to a timestamped backup.

Memory item kinds are:

```text
preference
fact
project_note
workflow_lesson
tool_lesson
blocked_pattern
session
```

Task completion creates local memory suggestions when useful. Sensitive or inferred items stay in the review queue until approved.

## Skills

Rasputin skills are stored as local packages:

```text
data/skills/<skillName>/SKILL.md
```

Built-in Python skills now have matching `SKILL.md` descriptors. Successful sessions can generate a preview skill through `/api/skills/create-from-session`; saving generated skills is explicit.

## Approval Queue

Risky tools create persistent approval records instead of only returning a transient preview.

Approval statuses are:

```text
pending
approved
denied
expired
executed
```

Approval records contain redacted metadata only:

```text
action type
risk level
workspace
short approval code
shortened paths
task/tool ids
```

They do not store file contents, diffs, prompts, raw model output, secrets, or private document text.

## Telegram Approvals

Telegram is optional and uses outbound Bot API polling only:

```text
Rasputin container -> Telegram Bot API
```

No webhook is exposed and no public port is required.

Telegram commands:

```text
/approve CODE
/deny CODE
/status
```

Only the configured chat id can approve or deny actions. Telegram messages are intentionally sparse and redacted so the phone approval path does not become a data leak.

### main.jsx

`main.jsx` is now only the boot file.

It imports:

- local Bootstrap CSS from `bootstrap/dist/css/bootstrap.min.css`
- Rasputin CSS
- React Query provider
- the main `App`

### AppProviders.jsx

Creates the React Query client.

React Query is used for repeatable server-state paths:

- model registry
- tasks
- audit events

### App.jsx

Owns the top-level app state:

- auth session
- active view
- active settings section
- active theme
- sidebar collapsed state
- selected model
- testing mode
- workspace state
- task state
- security state
- RAG and graph stats
- audit events

It also handles:

- login
- logout
- initial `/api/ui/bootstrap` load
- Server-Sent Events for live task updates
- task creation
- model actions
- workspace browsing
- safety setting saves

### AppShell.jsx

Wraps the app frame:

- skip link
- global status alert
- sidebar
- main content area

### Sidebar.jsx

The persistent navigation:

- Home
- Workspaces
- Tasks
- Knowledge
- Models
- Audit
- Settings

It preserves test IDs such as:

```text
data-testid="nav-home"
data-testid="nav-models"
data-testid="sidebar-toggle"
```

### HomeView.jsx

The chat-first home screen:

- top bar
- active workspace pill
- active model picker
- privacy badge
- quick prompts
- message composer
- task thread display
- markdown rendering for assistant output

Markdown is rendered with:

```text
react-markdown
rehype-sanitize
```

This is safer than raw `dangerouslySetInnerHTML`.

### SettingsView.jsx

The full-page settings area:

- General
- Workspaces
- Models
- Safety
- Knowledge
- Output
- Appearance
- Admin

Raw/advanced model registry details are behind disclosures instead of being the normal path.

### TasksView.jsx

The operational task list:

- task count
- running count
- main task count
- sub-agent task count
- task cards

### AuditView.jsx

Displays recent audit events.

## 6. Backend Structure

Main backend files:

```text
backend/main.py
backend/agent.py
backend/auth.py
backend/model_registry.py
backend/models.py
backend/workspace.py
backend/security.py
backend/rag.py
backend/graphify.py
backend/mcp_layer.py
backend/audit.py
backend/output.py
backend/preferences.py
backend/response.py
backend/memory.py
```

### main.py

Creates the FastAPI app and defines routes.

Important jobs:

- mounts frontend static files
- adds CORS for localhost
- adds security headers
- adds request timeouts
- converts backend errors to structured JSON
- defines API models
- wires routes to backend services

API responses follow this shape:

```json
{ "ok": true, "data": {}, "error": null }
```

or:

```json
{ "ok": false, "data": null, "error": { "code": "permissionDenied", "message": "..." } }
```

### response.py

Central response helpers:

- `ok(...)`
- `fail(...)`
- `AppError`
- exception handlers

### auth.py

Handles local admin authentication:

- first boot admin setup
- login
- logout
- password change
- session cookie
- localhost/test bypass rules

The first-run admin password is printed in container/server logs.

### security.py

Stores safety flags such as:

- privacy lock
- file read permission
- file write permission
- web search permission
- Docker control permission
- approval requirements
- audit enabled

Many backend tools call `security.require(...)` before doing sensitive work.

### audit.py

Records sensitive or important actions.

Examples:

- model registry edits
- Docker control attempts
- workspace changes
- security changes
- blocked actions

### workspace.py

Controls which folders Rasputin can see.

It manages:

- active workspace
- approved folder registry
- workspace browser
- mount plan preview
- path safety
- read-only profiles

The frontend workspace browser talks to:

```text
GET  /api/workspace/roots
POST /api/workspace/browse
POST /api/workspace/approve
POST /api/workspace/mount-plan
POST /api/workspace/mount-apply
```

Mount apply is blocked unless Docker control permission is enabled.

### model_registry.py

Manages local model definitions.

Default model roles:

- `main-vllm`
- `dry-run`
- `local-embeddings`

It supports:

- vLLM discovery
- model health checks
- registry repair
- GGUF scan/import
- Docker-managed model start/stop when explicitly enabled

When Rasputin runs in Docker, local model endpoints like:

```text
http://127.0.0.1:8000/v1
```

are translated to:

```text
http://host.docker.internal:8000/v1
```

That lets the wrapper container reach a model server running on the host.

### models.py

Sends chat requests to the selected model runtime.

It supports:

- dry-run mock model
- OpenAI-compatible model endpoints
- API-key providers through adapters:
  - OpenAI-compatible remote APIs
  - Anthropic Messages API
  - Gemini GenerateContent API
- clean handling for model HTTP errors

API keys do not belong in `models.json`. A registry entry may point to an environment variable such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`, or to Rasputin's ignored local secret store at `data/model_secrets.json`. Remote providers remain blocked while Privacy lock is enabled or Remote models are disabled.

### agent.py

Runs tasks.

Core concepts:

- `AgentTask`
- `AgentHub`
- task lifecycle: queued, running, done, error, cancelled
- live logs
- outputs
- traces
- sources
- graph context

For simple chat tasks, it calls:

```text
chat_reply()
```

For more agentic tasks, it can run:

```text
plan -> execute -> reflect
```

Task updates are streamed through Server-Sent Events:

```text
GET /api/events
```

### mcp_layer.py

Provides a local tool layer for the agent.

It exposes controlled tools such as:

- RAG search
- graph search
- file operations through approved workspaces
- brokered research/search hooks where enabled

The model does not directly call these tools. The backend calls them and passes safe context into the model prompt.

### rag.py

Local retrieval system.

Current behavior:

- indexes supported local files
- chunks content
- stores local retrieval data under `data/`
- returns cited chunks to the agent

### graphify.py

Local graph system.

Current behavior:

- builds local relationship data
- stores typed nodes/edges
- returns graph relationships for agent context

### document_intel.py

Planned local document intelligence layer.

Target behavior:

- parses approved workspace PDFs into text chunks and citation metadata
- parses approved workspace DOCX files into sections, headings, tables, and text chunks
- stores parsed text, summaries, and memory candidates only under local `data/`
- sends parsed chunks into RAG indexing for retrieval
- sends document entities and section links into Graphify so files are easier to locate later
- exposes editor-safe previews before any DOCX rewrite or PDF-derived output is saved

PDF and DOCX content must follow the same privacy rules as workspace files: local models may read approved local context, but direct internet access remains blocked and brokered search cannot receive private document text.

### output.py

Controls Markdown output/export settings and task export.

File writes are blocked when safety settings do not allow writing.

### preferences.py

Stores UI preferences:

- theme
- sidebar state
- selected model
- active view
- active settings section
- testing mode

The frontend also mirrors some instant UI preferences in browser `localStorage` so the app does not visually jump on boot.

## 7. Main API Groups

### Auth

```text
GET  /api/auth/session
POST /api/auth/login
POST /api/auth/logout
POST /api/auth/change-password
```

### UI Bootstrap

```text
GET /api/ui/bootstrap
```

This gives the frontend its initial state:

- models
- tasks
- memory
- RAG stats
- workspace
- graph stats
- security settings
- audit events
- output config
- preferences

### Tasks

```text
POST /api/tasks
POST /api/tasks/{task_id}/cancel
GET  /api/tasks
GET  /api/events
```

### Models

```text
GET  /api/model-registry
POST /api/model-registry/upsert
POST /api/model-registry/import-gguf
POST /api/model-registry/scan-gguf
POST /api/model-registry/start
POST /api/model-registry/stop
POST /api/model-registry/test
POST /api/model-registry/discover
POST /api/model-registry/repair
POST /api/model-registry/logs
```

### Workspaces

```text
GET  /api/workspace
GET  /api/workspaces
GET  /api/workspace/roots
POST /api/workspace/browse
POST /api/workspace/approve
POST /api/workspace/mount-plan
POST /api/workspace/mount-apply
POST /api/workspace/add
POST /api/workspace/remove
POST /api/workspace/select
POST /api/workspace/list
```

### Safety, Preferences, Audit

```text
GET  /api/security
POST /api/security
GET  /api/preferences
POST /api/preferences
GET  /api/audit
```

### Knowledge

```text
GET  /api/rag/stats
POST /api/rag/ingest
POST /api/rag/search
GET  /api/graph/stats
POST /api/graph/build
POST /api/graph/search
```

### Output

```text
GET  /api/output
POST /api/output
POST /api/output/export-task
```

## 8. Data Storage

Generated local state lives under:

```text
data/
workspace/
models/
testdata/
```

These should not be committed.

Important generated files include:

```text
data/models.json
data/workspace.json
data/security.json
data/preferences.json
data/audit.jsonl
data/memory.json
```

The `models/` folder is mounted read-only in Docker:

```yaml
./models:/app/models:ro
```

That is where GGUF model files can be made visible to Rasputin.

The `workspace/` folder is mounted read/write:

```yaml
./workspace:/app/workspace
```

Additional folders should go through workspace approval or mount planning.

## 9. Model Runtime Layout

Rasputin is not the model runtime itself.

It is the wrapper/hub.

Expected model layout:

```text
Rasputin wrapper container -> talks to model endpoints
vLLM container             -> main large model on port 8000
llama.cpp containers       -> optional GGUF auxiliary models
```

Default main endpoint:

```text
http://127.0.0.1:8000/v1
```

Inside Docker this becomes:

```text
http://host.docker.internal:8000/v1
```

The Models settings page lets you:

- refresh registry
- test active model
- discover vLLM models
- repair obvious model ID mismatch
- scan GGUF library
- reveal advanced registry details
- enable Testing Mode to show `dry-run`

Docker model start/stop is intentionally blocked unless Docker control is enabled.

## 10. Safety Boundaries

Important defaults:

- privacy lock on
- remote model endpoints blocked
- Docker control off
- shell execution off
- folder reorganization off
- writes/moves require approval
- new folder mounts default read-only

Path safety:

- file tools operate only inside approved workspace roots
- path traversal outside approved roots is rejected
- GGUF imports must be under the mounted model folder or an approved workspace

Internet safety:

- models do not get direct internet access
- web search should go through the broker/tool path
- suspicious outbound query patterns can be blocked by leak guard logic

## 11. Frontend State Flow

Initial boot:

```text
App starts
-> GET /api/auth/session
-> if authenticated: GET /api/ui/bootstrap
-> populate local state
-> seed React Query caches
-> connect GET /api/events
```

Repeated server state:

```text
React Query:
  model-registry
  tasks
  audit-events
```

Live task updates:

```text
GET /api/events
-> SSE message
-> update local task state
-> update React Query task cache
```

Preferences:

```text
localStorage gives instant theme/sidebar restoration
POST /api/preferences persists choices across sessions
```

## 12. Testing

Main harness:

```powershell
.\scripts\test.ps1
```

UI harness:

```powershell
.\scripts\test.ps1 -Ui
```

The UI path:

1. runs `npm run build`
2. builds a test Docker image
3. starts an isolated wrapper on `http://127.0.0.1:8877`
4. runs backend smoke tests
5. runs live API smoke
6. runs Playwright UI tests
7. shuts down the test container

UI test file:

```text
tests/ui/rasputinSmoke.spec.mjs
```

It verifies:

- home shell
- settings navigation
- model registry controls
- GGUF scan button
- workspace browser
- mount plan preview
- safety/knowledge/audit/task views
- theme switching
- sidebar collapse persistence
- dry-run send flow
- screenshot generation

Backend smoke tests:

```text
tests/testBackendSmoke.py
tests/liveSmoke.py
```

## 13. Development Commands

Install JS dependencies:

```powershell
npm install
```

Build frontend:

```powershell
npm run build
```

Run frontend dev server:

```powershell
npm run dev
```

Run backend directly:

```powershell
python server.py
```

Run wrapper in Docker:

```powershell
.\start-wrapper.ps1
```

Stop wrapper:

```powershell
.\stop-wrapper.ps1
```

Run Docker Compose directly:

```powershell
docker compose up --build
```

## 14. How To Read The Project

If you want to understand Rasputin by walking through the code, use this order:

1. `docker-compose.yml`
2. `Dockerfile`
3. `server.py`
4. `backend/main.py`
5. `frontend-src/src/main.jsx`
6. `frontend-src/src/app/App.jsx`
7. `frontend-src/src/features/chat/HomeView.jsx`
8. `backend/agent.py`
9. `backend/model_registry.py`
10. `backend/workspace.py`
11. `backend/security.py`
12. `backend/rag.py`
13. `backend/graphify.py`
14. `tests/ui/rasputinSmoke.spec.mjs`

That path follows the real runtime: Docker -> Python server -> API -> frontend shell -> agent/model/workspace systems -> tests.

## 15. Current Known Notes

The frontend build uses compiled Bootstrap CSS from the local npm package instead of compiling Bootstrap SCSS. This avoids Sass deprecation noise in normal production builds.

The current CSS bundle is larger than a fully custom minimal stylesheet because Bootstrap supplies a real component system. Rasputin-specific CSS is kept small in `rasputin.css`; Bootstrap CSS is the external styling library layer.

The current frontend is componentized and Bootstrap-based. Vite splits preview, runtime, model, workspace, task, and vendor code into separate chunks so normal app boot is not forced into one oversized bundle.
