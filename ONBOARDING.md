# Welcome to Rasputin

Welcome to the team! This document gets you up to speed on the **Rasputin**
architecture, the **WarSat** deployment layer, and how to start shipping
code during your first week. It was rewritten on 2026-07-06 against the
actual code (not the previous roadmap) — if something here drifts from what
you're looking at, trust the code and fix this doc.

---

## 1. Project Overview

**Rasputin** is a local-first, autonomous AI workbench: it runs agentic
tool-calling loops (chat, plan, execute, reflect), keeps a persistent
RAG + knowledge-graph memory over your workspaces, and gates every
file/shell/docker/network action behind an explicit permission model built
for one operator running this on their own machine.

**WarSat** is Rasputin's model-runtime deployment layer. It discovers,
downloads, validates, containerizes, and deploys AI models (local
llama.cpp/GGUF, vLLM, or any OpenAI-compatible endpoint) through the host's
Docker socket.

> [!IMPORTANT]
> **Core rule**: WarSat is the single source of truth for infrastructure
> changes. No model gets downloaded or deployed silently outside of it —
> every action is audit-logged, resource-estimated, and reversible.

> [!IMPORTANT]
> **Read `THREAT_MODEL.md` at the repo root before writing anything
> security-adjacent** (auth, permissions, tool dispatch, sandboxing). It's
> short, current, and includes honest residual caveats. Login/session
> enforcement is real; the execution surfaces deliberately have different
> boundaries, so read §5 before describing them as one sandbox.

---

## 2. Tech Stack

### Frontend
- **Framework**: React 18 + Vite, plain JS/JSX (not TypeScript)
- **State**: Zustand
- **Data fetching**: TanStack React Query
- **Styling**: hand-written vanilla CSS (`frontend-src/src/styles/`) —
  Tailwind/shadcn were tried and reverted; don't reintroduce them
- **Icons**: Lucide React
- **Entry point**: `frontend-src/index.html` → `frontend-src/src/app/App.jsx`

### Backend
- **Framework**: FastAPI (Python 3.12), Uvicorn
- **Model integrations**: HuggingFace Hub, OpenAI/Anthropic/Gemini-compatible
  APIs, local llama.cpp containers via WarSat
- **Data layer**: SQLite (`data/rasputin.db`) via `backend/core/runtime_store.py`
  — almost everything (sessions, messages, memory, skills, auth, mount
  requests) lives there now; legacy flat JSON files under `data/` are only
  read once as a migration seed
- **Execution surfaces**: different isolation properties — see
  `THREAT_MODEL.md` §5. Skills run in ephemeral `--network none` Docker
  containers over stdio RPC; native-Windows `shell_exec` runs as the
  low-privilege `Rasputin_sbx` account when the separate Host Shell capability
  is enabled; Docker/native-non-Windows shell and git tools follow direct
  backend-child paths with their documented gates.
- **Entry point**: `backend/main.py`

---

## 3. Directory Structure

- `frontend-src/src/features/` — UI modules: WarSat, Workspaces, Settings,
  Trials, Archive, Activity.
- `backend/`
  - `main.py` — FastAPI app assembly, startup, request-timeout middleware.
  - `api/` — route handlers, thin; real logic lives in `core`/`engine`/`rag`/`mcp`.
  - `engine/agent.py` — the agentic tool-loop (`AgentHub.governed_chat` is
    the one function every phase funnels through) and context assembly.
  - `engine/prompt_security.py` — the untrusted-content wrapper (see
    `THREAT_MODEL.md` §3) — read this before touching anything that feeds
    retrieved content into a prompt.
  - `mcp/` — Model Context Protocol relay (`relay.py`), the fixed tool
    registry (`tools.py`, 25 tool IDs), and the real tool implementations
    (`layer.py` — this is where `web_search`, `shell_exec`, `fs_*`, `git_*`
    actually live).
  - `core/security.py` / `core/approvals.py` — the permission-flag and
    per-action-approval system.
  - `core/workspace.py` — workspace records, separate Trusted Dev Mode / Host
    Shell flags, direct native folder registration, and Docker-only host-folder
    mount requests.
  - `core/host_fs.py` — browses the *host* filesystem from inside the
    (usually containerized) backend, for the folder-picker UI.
  - `core/auth.py` — password hashing, login, sessions. Real
    login/session enforcement as of 2026-07-07 (see `THREAT_MODEL.md`
    §6.1 for how it's wired and the one caveat that's left).
  - `core/sandbox.py` — spawns the ephemeral Docker sandbox for Skills.
  - `warsat/` — model acquisition/deployment providers (Docker, etc.).
  - `rag/vector.py`, `rag/graph.py` — the vector index and AST-based
    code-structure graph, each with a cached stats summary so `/stats`
    endpoints never re-read the full (potentially huge) index blob.
  - `trials/` — blind model-comparison/scoring engine.
- `data/` — SQLite DB + generated files (`docker-compose.mounts.yml`,
  first-run `auth.json` seed). Gitignored — never commit anything from here.
- `docs/` — planning/status docs. Two worth knowing:
  `docs/CODING_AGENT_COMPETITIVENESS_PLAN.md` (why we're building what
  we're building) and `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md`
  (the actual checkbox list of what's done vs. not — check this before
  assuming a feature doesn't exist yet).

---

## 4. Local Development Setup

Rasputin is **Docker-first** — that's how it's actually run day to day.

**Fastest path**, from the repo root:
```powershell
# Windows
.\rasputin.ps1 start                  # add -EnableWarSat for the Docker control layer
.\rasputin.ps1 credentials            # read first-run login if still in current logs
.\rasputin.ps1 reset-password         # generate a new login if it is not
```
```bash
# macOS/Linux
./rasputin.sh start
./rasputin.sh credentials
```
This wraps `docker compose up --build -d` and automatically layers in
`data/docker-compose.mounts.yml` if it exists (generated when someone
approves a host folder from the Workspaces tab — see `core/workspace.py`).

**Native / decoupled dev loop** (faster iteration, no rebuild-on-every-change):
```powershell
# Terminal 1 — backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8787
```
```powershell
# Terminal 2 — frontend
cd frontend-src
npm install
npm run dev
```
Point `RASPUTIN_DATA_DIR` at a scratch directory if you want a native run
that doesn't touch your real `data/` folder — several backend modules
(`workspace.py`, `runtime_store.py`, `auth.py`) read this env var and fall
back to `data/` only when it's unset.

---

## 5. Security Model — read this section, not just skim it

Full detail lives in `THREAT_MODEL.md`; the load-bearing points:

- **Operating assumption**: one trusted operator, local machine. The thing
  actively defended against is *retrieved content* trying to act as
  instructions (prompt injection), not the operator.
- **Permission flags** (`backend/core/security.py`): flat booleans —
  `allow_shell_execution` and `allow_docker_control` are **off** by
  default; `allow_remote_models` (Privacy Lock) is **off** by default.
- **Trusted Dev Mode**: a per-workspace opt-in that lets file/git writes skip
  the per-action approval queue. It does **not** unlock `shell_exec`; Host
  Shell is a separate per-workspace opt-in, and the global
  `allow_shell_execution` flag must also be on. Every call remains audited
  and shell calls still pass the deny-pattern hint; native Windows then routes
  through the `Rasputin_sbx` account and workspace ACL.
- **Untrusted-content wrapper** (`backend/engine/prompt_security.py`): RAG
  hits, graph evidence, saved memory, workspace file contents, and every
  tool-call result get fenced in a labeled
  `=== BEGIN/END UNTRUSTED CONTENT ===` block plus a standing
  do-not-obey-this policy, applied centrally in `governed_chat` so no call
  site can forget it. If you add a new source of retrieved/fetched text
  into a prompt, wrap it the same way — check `prompt_security.py`'s
  docstring for the reasoning.
- **Auth is real** (`THREAT_MODEL.md` §6.1, fixed 2026-07-07):
  `backend/core/auth.py`'s `login()` checks the password hash and rate
  limit for real, and `backend/api/core.py`'s `current_user()` — the
  `Depends(...)` gate on nearly every route — actually checks the session
  cookie via `auth.public_session()` and 403s if it's missing or invalid.
  One caveat: `localhost_bypass_enabled()` only ever fires for a native
  (non-Docker) run hit directly on `127.0.0.1` — behind the standard
  docker-compose deployment, `request.client.host` is the bridge gateway
  IP, so that bypass is a dev convenience that simply doesn't apply in
  production. `.\rasputin.ps1 credentials` can recover the generated password
  only while its original line remains in the current container logs. If that
  line is gone or the password was changed, use `.\rasputin.ps1 reset-password`
  (native: `python -m backend.tools.reset_password`).

---

## 6. Testing Conventions

```bash
python -m unittest discover tests
```
or, isolated from your real data dir (this is how CI/native test runs work):
```bash
RASPUTIN_DATA_DIR=/tmp/rasputin-test RASPUTIN_ENV=test RASPUTIN_TEST_AUTH_BYPASS=1 \
  python -m unittest tests.testBackendSmoke -v
```
`tests/testBackendSmoke.py` currently has **73 tests** (not 48 — check the
`-v` output rather than trusting a number in a doc, this one included).
Do not merge with a red suite.

Docker-based harness: `.\scripts\test.ps1` (add `-Ui` for the Playwright
E2E pass; `sh scripts/test.sh` on macOS/Linux).

For anything touching the agent tool-loop, the pattern to copy is in
`testBackendSmoke.py`: patch `backend.engine.agent._chat` with a scripted
async function, and set `hub.mcp.call_tool` to a fake dispatcher, so you
can assert on exactly what messages/tool calls the loop produces without
needing a real model endpoint.

For anything that needs to be observed running rather than unit-tested
(a new tool, a new context section, a new UI flow), drive the **real**
backend: start it natively against a scratch `RASPUTIN_DATA_DIR`, hit the
actual HTTP routes with `curl`, and use the `dry-run` model (provider
`"mock"` — it just echoes the fully composed prompt back as the reply,
which is the fastest way to see exactly what's being sent to a model
without needing a real API key).

---

## 7. Branch Topology

Check this yourself before trusting any doc (this repo's active branch
changes fast): `git log -1 --format="%ci %h %s" <branch>` on the candidates.
As of 2026-07-06: `codex/agentic-coding-loop-v1` is the active line;
`main` is a clean ancestor of it (GitHub's default branch, `origin/HEAD`),
so the normal flow is feature work on a `codex/*` branch, merged into
`main` periodically. Several stale branches exist from earlier UI
experiments (`claude-branch`, `claude-ui`, various `backup/*`) — don't
assume any of them are current without checking their last commit date
yourself.

---

## 8. Your First Week

Check `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` before picking
something — it's kept current with `[x]`/`[ ]` per item and is the real
source of truth on what's done. As of this writing, the concrete open
work is:

1. **Stage 5 — coding task UX** (`frontend-src`, task detail view): a
   per-file diff viewer, a touched-files list, a live terminal/log pane for
   shell output, and a revert-file quick action. The tool-call stream and
   step/plan list this builds on are already wired up (Stage 4b, done
   2026-07-02) — you're adding views onto data that already flows.
2. **Stage 6 — test-loop integration** (`backend/engine/agent.py`,
   workspace settings): per-workspace test/build/lint command config,
   running it after an edit, parsing pass/fail out of the output, and
   feeding failures back into the next tool-loop iteration with a bounded
   retry count separate from the general tool-call ceiling.

Both stages have detailed sub-checklists in the implementation doc,
difficulty-tagged (Easy/Medium/Hard/Very Hard) — start with an Easy item
in whichever stage looks more interesting and work up.

> [!TIP]
> Read `THREAT_MODEL.md` §5 (the two execution surfaces) before touching
> Stage 6's "run a test command" work — you're adding another path that
> executes something on the operator's behalf, so it needs to go through
> the same Trusted-Dev-Mode-gated `shell_exec`, not a new unsandboxed one.

Welcome aboard. Questions about the orchestration loop, WarSat, or the
security model — the answers are more likely to be sitting in
`THREAT_MODEL.md` or `docs/RASPUTIN_ARCHITECTURE_GUIDE.md` than anywhere
else; start there before asking.
