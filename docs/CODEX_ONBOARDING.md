# Codex Onboarding — Rasputin

*Written 2026-08-10 for a cold Codex session joining this project alongside Elliott (the
operator/owner) and Claude Code sessions. If anything here drifts from the code, trust the
code and fix this doc.*

> **Note on `AGENTS.md`:** the repo-root `AGENTS.md` is a **Claude Code–specific orchestration
> policy** (Fable orchestrator dispatching Sonnet subagents). Its model-tiering instructions do
> **not** apply to you. Its "Project gotchas" section applies to **everyone** — those gotchas
> are repeated in §4 below.

---

## 1. What Rasputin is

Rasputin is a Windows native AI workstation for local chat, governed coding, and a bounded
personal Assistant. The installed Electron app owns a packaged FastAPI backend, React frontend,
SQLite state, and hardware-selected llama.cpp acquisition. The source Native Host is a separate browser/headless
workflow. Both load GGUF models as native processes. Docker infrastructure is retired from the
product direction; do not suggest it as a requirement, feature, fallback, or troubleshooting step.

**Current direction, confirmed 2026-08-29:**

- The installed Windows app is the daily-driver product; Python/Node are build tools, not end-user requirements.
- Discover Models → exact GGUF variant → download/import → verify/register → Load → infer → Stop.
- Filesystem tools operate on approved host folders. Skills are declarative instructions.
- Keep owner/workspace controls, authentication, native process ownership, and audit boundaries intact.
- Retained server-era code and historical evidence do not define the current product.

See `docs/DEPLOYMENT_MATRIX.md` for launch/upgrade ownership and
`docs/WRAPPER_RUNTIME_CONTRACT.md` for native runtime behavior.

## 2. Repo map

| Path | What it is |
|---|---|
| `server.py` | Backend entrypoint (FastAPI app) |
| `backend/api/` | HTTP endpoints (e.g. `warsat_api.py` also hosts workspace/git endpoints) |
| `backend/engine/agent.py` | The agent loop (`governed_chat`): tool loop, budgets, test-loop |
| `backend/models/providers.py` | Model I/O: `chat_sync`, streaming, tools-degradation retry |
| `backend/warsat/` | Shared hardware/runtime services; native provider plus retained legacy adapters |
| `backend/mcp/layer.py` | Tool implementations + trust/approval gating (fs, git, shell) |
| `backend/core/workspace.py` | Workspace registry incl. per-workspace test/build/lint commands |
| `frontend-src/src/` | React source — **the only frontend you edit** |
| `frontend/` | Vite build output — **never hand-edit** |
| `tests/testBackendSmoke.py` | Backend smoke suite; test counts change with the current checkout |
| `tests/ui/`, `playwright.config.mjs` | Playwright UI tests |
| `docs/` | Plans and findings — see §6 for which ones are current |
| `docs/MAINTAINER_HANDOFF.md` | First-day maintainer workflow, ownership map, and handoff acceptance |
| `THREAT_MODEL.md` | **Read before any security-adjacent change** |

## 3. Build, run, test

```bash
# Backend tests (the main gate — run after any backend change):
python -m unittest tests.testBackendSmoke        # or: python tests/testBackendSmoke.py

# Frontend: edit frontend-src/, then build (from repo root):
npm run build                                     # vite build → frontend/

# Documentation contract check (from repo root):
C:\Users\elliott\OneDrive\Documents\WrapperProject\.venv\Scripts\python.exe scripts\verify_docs.py

# Tracked maintenance surface and documentation-coverage inputs:
C:\Users\elliott\OneDrive\Documents\WrapperProject\.venv\Scripts\python.exe scripts\audit_repository.py

# Release-candidate evidence (isolated tests plus the explicitly selected native endpoint):
C:\Users\elliott\OneDrive\Documents\WrapperProject\.venv\Scripts\python.exe scripts\verify_release_candidate.py --endpoint native=http://127.0.0.1:8788

# Run an isolated dev instance (never point at real data):
RASPUTIN_DATA_DIR=<temp-dir> PORT=8899 python server.py
# App: http://127.0.0.1:8899/#chat   (hash routes: #home, #chat, #models, #settings/...)
```

- `RASPUTIN_DATA_DIR` redirects all runtime storage. Native data defaults to
  `%LOCALAPPDATA%\Rasputin\data`; tests always use an isolated directory.
- Source Native Host uses real auth: `POST /api/auth/login` and its httponly session cookie.
  Fresh-store credentials are printed once; never publish them. Installed Desktop instead sets
  `RASPUTIN_DESKTOP_ONLY=1` and supplies a local administrator session to loopback callers, so it
  opens without a login screen. Never use that mode for LAN access. Use the native password-reset
  helper only for explicitly requested Native Host recovery.
- UI verification patterns (Playwright + testids + isolated server) live in
  `.claude/skills/verify/SKILL.md`.
- **Native Host accounts are local and multi-user** (2026-07-13); Desktop is a single-operator
  surface. `backend/core/auth.py` persists appliance
  users plus hashed, restart-safe login sessions. Chats/tasks/preferences/memory are owner-scoped;
  workspaces use viewer/contributor/developer/owner membership. Appliance-wide models, security,
  settings, providers, approvals, and WarSat mutations require the `admin` role. The original
  administrator automatically inherits pre-migration records and workspaces.
- **HTTPS delegates certificate trust to mkcert.** `scripts/setup_https.py` invokes the installed
  official `mkcert` binary; `rasputin.ps1 setup-https` writes only the leaf certificate/key and SAN
  list to ignored `data/tls/`. `server.py` enables Uvicorn TLS only when `RASPUTIN_HTTPS=1` and both
  paths exist. Never copy mkcert's `rootCA-key.pem`; mkcert certificates are not a public-Internet
  deployment strategy.

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
   Do not trust a branch name captured in a doc; check `git branch --show-current` at the start.
7. Verify UI claims **in the running app**, not by reading code. "Renders" ≠ "works" — drive
   the primary action before calling something done.
8. Temp/scratch files go outside the repo (session temp dir), never in the repo or `/tmp`.

## 5. Current evidence and remaining work

The active implementation queue is in `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md`;
its older dated sections are historical evidence, not current deployment instructions.

- On 2026-08-30, the isolated source Native Host on :8902 completed the real UI workflow:
  Discover search for `bartowski/SmolLM2-135M-Instruct-GGUF` → select Q4_K_M (100.6 MB) →
  download/register → Load with automatic defaults → Rasputin Chat task `done` → Stop.
  The response was “I'm ready to help! What's your question?” Load became available again after
  stopping. No page errors or retired infrastructure API requests occurred; body overflow was zero
  at widths 1440, 1024, and 390 pixels. This proves one small-model lifecycle, not coder capability.
- Regression verification passed: 44 frontend tests, the authenticated source/Desktop browser
  fixture test, 5 Desktop lifecycle tests, 101 focused Python tests plus 4 subtests, and a backend
  smoke run with 164 passes and 1 legacy-infrastructure skip. Scope and local proof location are in
  `docs/RASPUTIN_IMPLEMENTATION_LEDGER.md`; browser fixtures are not installed-app certification.
- The current workstation's installed Desktop was updated and verified on 2026-08-30. Installer
  build/install succeeded; installed application, package, backend, and frontend hashes matched
  the tested build. The isolated packaged UI also completed real GGUF download → automatic Load →
  Chat task `done` → Stop. Live installed health/frontend returned 200, catalog search worked,
  `#warsat` redirected to `#models`, and the library retained 21 models. The bundled CUDA 12.4
  engine reported ready without repair. Test listeners/model processes were cleaned up afterward.
- Installed UI checks used a browser served by the actual Desktop backend; native window/owner
  identity was confirmed with read-only OS checks. Computer-use was blocked by a sandbox ACL,
  so native-window UI Automation was not performed. Rollback files and proof JSON are under
  `%TEMP%\rasputin-native-finish-01a0540b`; see the ledger for exact evidence and scope.
  Source restarts still do not update installed binaries; this update included installation.
- Existing tool-loop, workspace/Git, memory, voice, and Assistant contracts remain bounded by
  their own tests and live evidence. Native Windows Host Shell remains unavailable pending
  a verified AppContainer runner.

Open release work includes a certified local coder edit → test → repair → review mission,
clean-machine installation and upgrade/recovery evidence, real voice hardware checks,
and signing/update-channel evidence. The proposal Word document's visual layout also remains
unverified (its PDF has recorded visual review). Do not revive retired infrastructure to satisfy those rows.

## 6. Doc freshness map

| Doc | Status |
|---|---|
| `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` | Current queue with explicitly historical implementation records |
| `docs/RASPUTIN_ARCHITECTURE_GUIDE.md` | Native runtime and frontend architecture; legacy code names are marked where retained |
| `docs/README.md` | Canonical documentation map and source-of-truth rules |
| `docs/RASPUTIN_V1_RELEASE_CONTRACT.md` | Frozen ten-slice v1 finish line, evidence matrix, and non-goals |
| `docs/RASPUTIN_APPLICATION_READINESS_GAP_REPORT.md` | Current release residuals and evidence report; reconcile against code and the implementation ledger |
| `docs/DEPLOYMENT_MATRIX.md`, `docs/DESKTOP_ARCHITECTURE.md` | Current runtime and packaging guidance |
| `THREAT_MODEL.md`, `docs/WRAPPER_RUNTIME_CONTRACT.md` | Current security and runtime contracts |
| `.agents/skills/verify/SKILL.md`, `.claude/skills/verify/SKILL.md` | Current — isolated native verification with real-auth login/cookie flow |

## 7. Working with Elliott

- **Honest reporting over optimism.** Distinguish "verified in the running app" from
  "compiles/renders". If something wasn't verified, say so explicitly — unverified claims get
  marked `[~]` in the checklist, not checked off.
- **Ask before irreversible or outward-facing actions** (deletes, pushes, deploys to his real
  instance). Propose before large refactors.
- **Identify the actual owner before changing a running app.** Installed Desktop records its
  private URL and owner PID in `desktop-runtime.json`; Native Host records `native-host.json`
  and defaults to :8788. Port :8899 is for isolated verification only. Never run both against
  one data directory. Existing approval to update the selected app remains valid; inspect a
  changed owner before acting, rather than assuming a familiar port is still the target.
- Product direction is native. Preserve historical evidence as history; never turn it into
  current setup, permission, or model-deployment advice.
