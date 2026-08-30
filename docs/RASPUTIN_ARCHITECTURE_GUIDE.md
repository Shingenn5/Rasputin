# Rasputin Architecture Guide

This guide explains how Rasputin is built, how it runs, where things are stored, and how the main pieces talk to each other.

## 1. Mental Model

Rasputin is a Windows native AI workstation. Electron owns the installed application lifecycle;
the backend governs model access, workspaces, tools, memory, and audit. A separate Native Host
supports source/browser development.

```text
Installed Electron app OR source Native Host
  -> native FastAPI backend on loopback
  -> catalog / exact GGUF acquisition / model registry / load planning
  -> native llama.cpp child process and local inference endpoint
  -> approved host workspaces, governed tools, memory, and audit
```

Models receive curated context through governed tools. Being a native process does not grant
a model arbitrary filesystem, network, or shell authority. Docker infrastructure is retired
from the current product; server-era files remain historical implementation context only.

## 2. Runtime Startup

### Installed Desktop

`desktop/main.cjs` and `desktop/backend-supervisor.cjs` start the packaged backend, wait for
health, and load the bundled frontend in a sandboxed BrowserWindow. The private port is recorded
in `desktop-runtime.json`. The tray owns restart and quit. The installed app bundles llama.cpp;
users download only the models they choose, plus any separately configured third-party tools.

Source edits do not update installed binaries. Package and install an update to change the
installed backend/frontend. Do not start a source backend against Desktop's live data store.

### Source Native Host

`backend/tools/native_host.py` owns a source-backed server, defaulting to loopback :8788, with
state in `native-host.json` and saved configuration in `native-host-config.json`. Use its start,
status, restart, and stop commands. Preserve the current owner and data when updating it.

### Isolated verification

Use a disposable `RASPUTIN_DATA_DIR`, port :8899, the repository virtual environment, and real
authentication. Never point tests at an active personal store. Detailed commands are maintained
in [Codex onboarding](CODEX_ONBOARDING.md) and [deployment guidance](DEPLOYMENT_MATRIX.md).

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

**This section is the canonical description of the frontend stack. If another doc
contradicts it (several older UI planning docs say "no Tailwind" or "vanilla JS"),
this section is correct and they are stale.** Authoritative source: root `package.json`
+ `vite.config.mjs`.

Current stack (all actually installed and used):

```text
Framework      React 18 + Vite 6   (built from frontend-src/ into frontend/)
State / data   zustand (client state) · @tanstack/react-query (server data)
Styling        HYBRID of three layers — see below:
                 1. Tailwind CSS v4   (@tailwindcss/vite plugin + `@import "tailwindcss"`)
                 2. React-Bootstrap / Bootstrap 5 CSS   (component primitives)
                 3. --ras-* / --cc-* design tokens   (11-theme system, app layout/surfaces)
UI libs        lucide-react (icons) · framer-motion (motion) · recharts (charts)
               react-markdown + rehype-sanitize (markdown)
Class utils    clsx · tailwind-merge · class-variance-authority
Heavy features pyodide (in-browser Python) · pdfjs-dist (PDF)
Fonts          @fontsource-variable/atkinson-hyperlegible-next
Testing        Playwright (npm run testUi)
```

Installed packages are the source of truth — see root `package.json` / `package-lock.json`.
Do NOT reintroduce a "no Tailwind" or "vanilla JS only" rule; React + Vite + Tailwind are the
real stack. Rationalizing the three styling layers into a cleaner primary system remains a known
cleanup goal.

### Styling: a three-layer hybrid (the honest picture)

Rasputin's styling is genuinely three systems coexisting. Knowing which does what avoids fighting them:

1. **Tailwind CSS v4** — wired via the `@tailwindcss/vite` plugin (`vite.config.mjs`:
   `plugins:[react(), tailwindcss()]`) and pulled in with `@import "tailwindcss";` at the top of
   `frontend-src/src/styles/theme.css`. Utility classes (`flex`, `gap-*`, `px-*`, `rounded-*`, …)
   are used across components (~hundreds of usages). Tailwind v4 needs no `tailwind.config.js` —
   it configures from CSS.
2. **React-Bootstrap / Bootstrap 5** — component primitives (`Button`, `Card`, `Modal`, `Form`,
   `Nav`, `Table`, …) rendered as React components; Bootstrap's CSS (`bootstrap/dist/css/
   bootstrap.min.css`) backs the `btn`/`card`/`form-control` classes they emit.
3. **The `--ras-*` / `--cc-*` design-token system** — the 11-theme engine and Rasputin-specific
   layout, spacing, and surfaces, in `frontend-src/src/styles/` (`theme.css`, `rasputin.css`,
   `dashboard.css`). Themes are applied via a root attribute/inline script in `index.html`.

**CONVENTION (decided 2026-07-12): consolidate toward Tailwind v4 + the design tokens as the ONE
primary system.** Three overlapping systems is a maintainability + consistency smell (a big part of
why the UI can "feel like a prototype"), so:

- **New and changed components use Tailwind utilities + `--ras-*`/`--cc-*` tokens** (tokens exposed
  as CSS variables Tailwind reads). Do **not** add new `react-bootstrap` usages.
- **`react-bootstrap` / Bootstrap CSS is now legacy** — retire it incrementally as components get
  touched during UI/UX work, keeping it only where a component is still
  pulling real weight and hasn't been migrated yet.
- The `--ras-*`/`--cc-*` token system stays — it's the theme engine; we build Tailwind *on top of*
  it, not instead of it.

This is a direction, executed incrementally (not a big-bang rewrite); the migration happens through
the polish phases, verified in the running app.

### Routed-view visual identity contract

The application shell exposes the current route as `data-current-view` on `#appFrame`, while each
routed screen keeps its existing `data-app-view` marker. `frontend-src/src/styles/interface.css`
uses those two stable attributes to give every tab its own accent palette, atmospheric background,
active-navigation treatment, and arrival tracer without duplicating layout code inside each view.

Keep this layer decorative and progressive: existing information architecture and interaction
patterns remain authoritative, interactive elements must retain visible keyboard focus, and all
ambient animation must be disabled by `prefers-reduced-motion`. Decorative pseudo-elements must not
contain textual `content`, because generated text can leak into the accessibility tree; use empty,
`aria-hidden` geometry or real semantic markup instead. Shared legacy runtime screens should use the
`PageHeader` / `ras-runtime-hero` pattern rather than inventing a new page header per tab.

### Workspace folder-picker contract

The Workspaces add-folder flow is mode-aware but shares one interaction model. A typed path is only
a navigation draft; it must not become the selected workspace until `/api/workspace/host-browse`
successfully verifies and lists it. The browser's clearly labeled **Current folder** is the folder
that will be submitted. Read-only access remains the default, and the selected folder, access mode,
runtime consequence, and primary action stay together in the persistent review bar.

Native mode registers the verified host path directly and reports that it is available immediately.
The retained legacy mount-request implementation belongs to the retired deployment path; it is
not part of current workspace setup and must not be offered as a native prerequisite.
Keep quick locations, manual path entry, folder drilling, and the final action fully keyboard-usable.

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

Skills are declarative `SKILL.md` instruction packages. Desktop loads their guidance through the
normal model/tool policy; it does not execute skill-authored Python or require Docker. Successful
sessions can generate a preview skill through `/api/skills/create-from-session`; saving generated
skills is explicit. The same declarative boundary applies in server mode.

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
Native Rasputin backend -> Telegram Bot API
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

The installed Desktop settings surface includes General, Model defaults, Runtime, Hardware,
Security, Connections, MCP servers, and About. Native Host also exposes administrative diagnostics,
audit, and notification settings according to role. Account provisioning is a separate flow;
retained deployment settings/components are legacy code, not part of the native model workflow.
Use Discover Models and Models for acquisition and lifecycle actions.

Raw/advanced model registry details are behind disclosures instead of being the normal path.

The settings filter is navigation-only state. It resets whenever the active section changes and
stays read-only until the operator explicitly focuses it; this prevents password managers and
browser credential autofill from injecting account usernames into the filter when credential
forms mount.

Local account provisioning is collapsed by default and opens as a dedicated flow with an
explicit role choice. Creating an account does not grant workspace access; workspace grants are
managed separately after the account exists.

The UI mirrors the server-side role model instead of showing controls that will be rejected:
administrators receive model control, account, and workspace-administration surfaces;
members receive chat, activity, and their shared workspaces; viewers receive a read-only
dashboard and shared-workspace browser. Direct hash routes are guarded as well. A signed-in
administrator cannot demote their own active role, and a workspace's final owner cannot remove
their own ownership until another owner exists; both states are explained beside the control.

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
- loopback-only Desktop administrator sessions and explicit localhost/test bypass rules

Source Native Host prints fresh-store credentials once and uses password/session authentication.
Installed Desktop opens without a login screen, supplies the local administrator identity to
loopback callers, and redacts generated secrets from persistent logs. This does not isolate the
Desktop API from other local processes; never expose Desktop mode beyond loopback.

### security.py

Stores safety flags such as:

- privacy lock
- file read permission
- file write permission
- web search permission
- model registry and native runtime permissions
- approval requirements
- audit enabled

Many backend tools call `security.require(...)` before doing sensitive work.

### audit.py

Records sensitive or important actions.

Examples:

- model registry edits
- model lifecycle actions
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

Native workspace approval registers a host folder directly and needs no mount or restart. The mount endpoints are retained server-era interfaces, not the native folder workflow.

### Model registry (`backend/models/registry.py`)

The registry stores model identity, role, artifact path, runtime, health, and compatibility
metadata. The native runtime is `native-llamacpp`; model role and runtime are distinct fields.
Existing local endpoints can be registered separately, and dry-run fixtures are test aids.

Native capabilities include exact GGUF artifact registration, approved-file import/scan,
load/stop, health checks, and measured file-size metadata for load planning. Native endpoints
remain loopback URLs without hostname rewriting. A stopped artifact stays installed.
Legacy provider records must be recovered to a compatible GGUF rather than treated as a native
executable model merely because they appear in the registry.

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

Resolve application state through `backend/core/datadir.py:data_dir()`. The Windows default is
`%LOCALAPPDATA%\Rasputin\data`; `RASPUTIN_DATA_DIR` overrides it for isolated verification.
SQLite-backed runtime state, model-download jobs, artifact metadata, preferences, accounts,
and logs belong to the selected data directory. Some JSON files exist as legacy migration
inputs; they are not a second authoritative store.

Model weights and external workspace sources are separate operational assets. Approve native
host folders directly and never require a volume mount. Do not commit runtime databases,
credentials, weights, workspace content, or generated reports. Do not run two owners against
one store. Recovery rehearsals restore into a separate target.

## 9. Model Runtime Layout

```text
Discover Models -> exact compatible GGUF files -> durable native download
               -> verified installed artifact -> native model registry
Models / Load  -> profile and hardware plan -> llama-server process
Chat / tools   -> registered local endpoint -> governed application workflow
Models / Stop  -> stop owned model process; keep installed files
```

`frontend-src/src/features/models/nativeDeployment.js` selects native acquisition for both
Desktop and Native Host. `backend/models/desktop_acquisition.py` owns durable exact-artifact
acquisition. Its historical module name does not restrict it to the Electron presentation.
`backend/models/load_profiles.py` plans settings, and
`backend/warsat/providers/native_llamacpp.py` finds and starts the native engine through the
runtime manifest/service. Native hardware requests use `native_models=true` on the existing
hardware endpoint. WarSat in a module or URL name does not imply container execution.

A fitting single GPU is preferred automatically; supported layer splitting may use multiple
GPUs when capacity and compatibility justify it. File size, context, and runtime overhead
matter. Measured runtime evidence and per-model testing remain necessary; no UI estimate
certifies every model/device combination.

If a stale build reports a retired deployment error, update the actual installed package or
recover the old model entry to a GGUF. The remedy is the correct native artifact/runtime path.

## 10. Safety Boundaries

Important defaults:

- privacy lock on
- remote model endpoints blocked
- native model lifecycle governed by administrator/model permissions
- shell execution off
- folder reorganization off
- writes/moves require approval
- newly approved workspace access starts read-only

Path safety:

- file tools operate only inside approved workspace roots
- path traversal outside approved roots is rejected
- GGUF imports must pass the approved model-path/workspace checks

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

Use the isolated native workflow in [Codex onboarding](CODEX_ONBOARDING.md). Backend smoke,
focused model/runtime tests, frontend tests, production builds, and live UI checks are separate
evidence. `tests/ui/rasputinSmoke.spec.mjs` includes older UI selectors; select relevant current
flows instead of claiming every historic browser test is a current release gate.

Verify download → registration → load → real response → stop with a small GGUF. Exercise
keyboard actions and visible retryable load errors. Use fixtures to test failure paths, and
label them as fixtures. Never substitute a mocked response for real inference evidence.

`scripts/test.ps1` is a retired infrastructure harness; it is not the native verification path.

## 13. Development Commands

```powershell
npm install
npm run build
npm run desktop:check
npm run desktop:test
```

Run a source-backed browser app with the explicitly native controller:

```powershell
.\.venv\Scripts\python.exe -m backend.tools.native_host start --port 8788
.\.venv\Scripts\python.exe -m backend.tools.native_host status --json
```

For isolated tests, set a disposable `RASPUTIN_DATA_DIR` first. For installed app updates,
use `npm run desktop:package`, verify the package, and install it with operator approval.
The launcher, store, and network configuration must match the intended target.

## 14. How To Read The Project

1. `desktop/main.cjs` and `desktop/backend-supervisor.cjs`
2. `backend/tools/native_host.py` and `server.py`
3. `backend/main.py` and `backend/api/`
4. `frontend-src/src/main.jsx` and `frontend-src/src/app/App.jsx`
5. `frontend-src/src/features/models/ModelsView.jsx`
6. `backend/models/desktop_acquisition.py`, `registry.py`, and `load_profiles.py`
7. `backend/runtime/runtime_service.py` and `backend/warsat/providers/native_llamacpp.py`
8. `backend/engine/agent.py`, `backend/core/workspace.py`, and `backend/core/security.py`
9. Relevant backend, native runtime, desktop lifecycle, and live UI tests

The ownership path is Electron/Native Host → native backend → artifact/registry/profile →
llama.cpp → governed chat/workspace tools. Older headings in this guide may retain a module's
former name; the current package paths above are the reading authority.

## 15. Current Known Notes

The frontend build uses compiled Bootstrap CSS from the local npm package instead of compiling Bootstrap SCSS. This avoids Sass deprecation noise in normal production builds.

The current CSS bundle combines Bootstrap's external component layer with a large accumulated Rasputin-specific layer. `frontend-src/src/styles/rasputin.css` is a maintenance hotspot and should be split by feature behind visual and interaction tests; do not treat its current size as an intentional architecture boundary.

The current frontend is componentized and Bootstrap-based. Vite splits preview, runtime, model, workspace, task, and vendor code into separate chunks so normal app boot is not forced into one oversized bundle.
