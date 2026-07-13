# Codex Onboarding — Rasputin

*Written 2026-07-13 for a cold Codex session joining this project alongside Elliott (the
operator/owner) and Claude Code sessions. If anything here drifts from the code, trust the
code and fix this doc.*

> **Note on `AGENTS.md`:** the repo-root `AGENTS.md` is a **Claude Code–specific orchestration
> policy** (Fable orchestrator dispatching Sonnet subagents). Its model-tiering instructions do
> **not** apply to you. Its "Project gotchas" section applies to **everyone** — those gotchas
> are repeated in §4 below.

---

## 1. What Rasputin is

A **local-first, privacy-first AI workbench**: agentic tool-calling loops (chat / plan /
execute / reflect), persistent RAG + knowledge-graph memory over workspaces, and an explicit
permission model gating every file/shell/docker/network action. **WarSat** is its model-runtime
deployment layer — it downloads, containerizes, and deploys local models (vLLM, llama.cpp/GGUF,
or any OpenAI-compatible endpoint) through the host Docker socket.

**Product direction (locked — don't relitigate):**
- Rasputin is **first a daily-driver** Elliott uses himself, polished to a high bar; going
  public is an eventual option.
- Eventual product = **self-hosted, local open-source models on the customer's own hardware**
  (data-can't-leave + API-cost-cutting teams). Not hosted SaaS.
- The repo stays **private**; licensing/packaging must preserve commercial viability.

**Stack:** FastAPI backend (`server.py` + `backend/`), React + Vite frontend
(`frontend-src/` source → `frontend/` build output), SQLite storage, Docker for model
containers and sandboxed skills. Python 3.12, Node with root-level `package.json`.

## 2. Repo map

| Path | What it is |
|---|---|
| `server.py` | Backend entrypoint (FastAPI app) |
| `backend/api/` | HTTP endpoints (e.g. `warsat_api.py` also hosts workspace/git endpoints) |
| `backend/engine/agent.py` | The agent loop (`governed_chat`): tool loop, budgets, test-loop |
| `backend/models/providers.py` | Model I/O: `chat_sync`, streaming, tools-degradation retry |
| `backend/warsat/` | Model deploy layer (`_build_tuning`, `_runtime_arguments`, protocols) |
| `backend/mcp/layer.py` | Tool implementations + trust/approval gating (fs, git, shell) |
| `backend/core/workspace.py` | Workspace registry incl. per-workspace test/build/lint commands |
| `frontend-src/src/` | React source — **the only frontend you edit** |
| `frontend/` | Vite build output — **never hand-edit** |
| `tests/testBackendSmoke.py` | The backend suite (unittest; 107 test methods; environment-dependent sandbox tests may skip) |
| `tests/ui/`, `playwright.config.mjs` | Playwright UI tests |
| `docs/` | Plans and findings — see §6 for which ones are current |
| `THREAT_MODEL.md` | **Read before any security-adjacent change** |

## 3. Build, run, test

```bash
# Backend tests (the main gate — run after any backend change):
python -m unittest tests.testBackendSmoke        # or: python tests/testBackendSmoke.py

# Frontend: edit frontend-src/, then build (from repo root):
npm run build                                     # vite build → frontend/

# Run an isolated dev instance (never point at real data):
RASPUTIN_DATA_DIR=<temp-dir> PORT=8899 python server.py
# App: http://127.0.0.1:8899/#chat   (hash routes: #home, #chat, #models, #settings/...)
```

- `RASPUTIN_DATA_DIR` redirects all sqlite/kv storage; without it native mode uses
  `%LOCALAPPDATA%\Rasputin\data` and Docker uses its `/app/data` named volume. Always set an
  isolated override for test instances.
- **Auth is real** (no longer stubbed — fixed 2026-07-07). Log in via
  `POST /api/auth/login`; the session is an httponly `rasputin_session` cookie. First-run
  admin credentials are printed to the server console. Some older docs (root
  `ONBOARDING.md` §5, `.claude/skills/verify/SKILL.md`) still claim auth is a no-op — stale.
- UI verification patterns (Playwright + testids + isolated server) live in
  `.claude/skills/verify/SKILL.md`.

## 4. Hard rules (apply to every change)

1. **Never hand-edit `frontend/`.** Edit `frontend-src/`, then `npm run build`.
2. **Never bulk-edit source files with PowerShell `Get-Content`/`Set-Content`** — PS 5.1
   mangles UTF-8 and adds BOMs. Use your editor tools or Python.
3. **Styling = Tailwind v4 + design tokens** (`--ras-*`/`--cc-*`; `@theme inline` bridge in
   `theme.css`; shadcn primitives in `frontend-src/src/components/ui/`). react-bootstrap is
   legacy (16 files) — retire incrementally, never add new usage. Canonical:
   `docs/RASPUTIN_ARCHITECTURE_GUIDE.md` §4.
4. **Accessibility bar (non-negotiable, all UI work):** every feature fully usable with
   **keyboard only** and with **mouse only**. Real `<button>`s, visible focus, WCAG tablist
   patterns where tabs exist, no hover-only or shortcut-only paths.
5. **Do not restructure the chat page layout**; upgrade components in place. Any layout change
   elsewhere requires a restorable backup of the prior version. Keep the composer pill.
6. **Commit only when Elliott asks.** Branch off `main` first if you're on the default branch.
   Current working branch: `codex/agentic-coding-loop-v1` (`main` is its clean ancestor).
7. Verify UI claims **in the running app**, not by reading code. "Renders" ≠ "works" — drive
   the primary action before calling something done.
8. Temp/scratch files go outside the repo (session temp dir), never in the repo or `/tmp`.

## 5. Current state (as of 2026-07-13)

The active effort is making Rasputin a **competitive coding agent**, tracked in
`docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` (the working plan — read it before picking up
work). Position:

- **App baseline is healthy** (`docs/PHASE_A1_FINDINGS.md`): zero console/HTTP errors across
  15+ views, light+dark; polish gaps are cosmetic, not structural.
- **Real local-model inference works end-to-end.** Qwen2.5-3B-Instruct deployed through WarSat
  (vLLM, `toolCallParser=hermes`) ran real chat and a `mode=code` agentic task with genuine
  tool calls. Two fixes made this work: `chat_sync` drops tools + retries once on a
  tools-bearing 400 from local runtimes (`backend/models/providers.py`), and the vLLM
  tool-call parser is **opt-in per deploy** (`toolCallParser` tuning field), never a global
  hardcode — the parser is model-specific and a wrong one silently corrupts tool calls.
- **Stage 6 (test loop) backend done:** per-workspace test/build/lint commands
  (`POST /api/workspace/commands`), edit→test→fix reopens inside `governed_chat`'s single
  wall-clock budget, 3-reopen cap, skips loudly when no command/shell denied.
- **Stage 5 (coding review UX) implemented:** backend `POST /api/workspace/git-status` /
  `git-diff` / `git-restore` (approval-gated), frontend Changes + Terminal tabs on
  `TaskDetailsDrawer` (touched files → diff viewer → per-file revert). **Verification gap:**
  Playwright render/interaction tests for those tabs and the keyboard-only/mouse-only passes
  are not written yet — the drawer only opens from an ACTIVE task ("Open Details",
  `TasksView.jsx:263,374`).
- **Tool-less agentic runs now fail visibly:** conversational chat still retries without tools when
  a local runtime rejects them, but an execution phase records `tools_unavailable` and stops as an
  error instead of reporting plain prose as completed work. The model catalog now supplies the
  conservative, non-binding `toolCallParserHint=hermes` for the proven Qwen2.5/vLLM family; parser
  selection remains opt-in per deploy.

**Open queue (roughly in order):** Stage 5 render/a11y Playwright tests → Stage 6 settings-UI
form (per-workspace command entry) → daily-driver UI fixes (theme-picker init bug
`GeneralSettings.jsx:85`, save toast, Button dedup `ModelsView.jsx:43-44`, mode-switch→STOPPED
foot-gun) → deploy-form `tool_call_parser` field consuming the catalog hint → real file-editing
coding task on a coder model (e.g. Qwen2.5-Coder).

## 6. Doc freshness map

| Doc | Status |
|---|---|
| `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` | **Current** — the working plan; honest `[~]` markers |
| `docs/PHASE_A1_FINDINGS.md` | Current — audit + real-model findings |
| `docs/ROADMAP.md` | Mostly current; its "Status" block predates A1 completion (says A1 is next — it's done) |
| `docs/RASPUTIN_ARCHITECTURE_GUIDE.md` | §4 is current/canonical; later backend path maps still contain pre-package-layout names |
| `ONBOARDING.md` (root) | Good general architecture intro, but §5's "auth is a no-op" is **stale** |
| `CLAUDE_HANDOVER.md` | **Stale** (old `claude-ui` branch era) — ignore |
| `docs/REMAINING_WORK.md` | **Stale** — predates completion of sandbox-account execution and `--network none` |
| `docs/CURRENT_BASELINE.md` | **Stale** — June baseline; useful history, not current direction |
| `.agents/skills/verify/SKILL.md`, `.claude/skills/verify/SKILL.md` | Current — isolated native verification with real-auth login/cookie flow |

## 7. Working with Elliott

- **Honest reporting over optimism.** Distinguish "verified in the running app" from
  "compiles/renders". If something wasn't verified, say so explicitly — unverified claims get
  marked `[~]` in the checklist, not checked off.
- **Ask before irreversible or outward-facing actions** (deletes, pushes, deploys to his real
  instance). Propose before large refactors.
- **His real instance** runs in Docker on **:8787** — never test against it. Use an isolated
  `RASPUTIN_DATA_DIR` instance (convention: **:8899**). Model containers WarSat spawns land on
  their own ports (e.g. Qwen on :8001). Confusing the two instances has burned a session
  before — check which port you're talking to.
- Locked decisions in §1 and the rules in §4 are settled; spend effort on execution, not on
  reopening them.
