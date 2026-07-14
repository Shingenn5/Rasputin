# Dual-Mode Architecture Plan — Streamlining Rasputin's Deployment and Use

Authored 2026-07-10 (Claude Fable 5, operator-approved direction). Companion to
[`CODING_AGENT_COMPETITIVENESS_PLAN.md`](CODING_AGENT_COMPETITIVENESS_PLAN.md) — that plan makes
the *agent* competitive; this plan makes the *application* effortless to deploy, run, and
eventually sell. Where the two touch (host-toolchain execution, Stage 6), this doc defers to
that one for agent-loop specifics.

**The one-sentence end state:** Rasputin runs natively on the operator's machine like any real
desktop tool — install, open a folder, work — while Docker remains exactly where it earns its
keep: isolating model runtimes (WarSat's fleet) and sandboxes, and providing the server
deployment mode a future team product needs.

---

## Goals — the destination we keep in mind at every phase

These are the criteria every phase is judged against. If a proposed change doesn't serve one of
these, it doesn't belong in this track.

- **G1 — One-command deployment.** A fresh Windows machine goes from nothing to a running
  Rasputin in one obvious step, without manually installing Docker Desktop, editing compose
  files, or reading a wiki page.
- **G2 — Zero-friction workspaces.** Opening a project folder works like an IDE: pick a path,
  approve it, use it. No mount requests, no compose volume edits, no restarts, no
  "restart-needed" badges.
- **G3 — The agent works on the real machine.** Coding tasks run the operator's actual
  toolchain — their `npm`, their Python env, their git — not a container's approximation of it.
  This is the structural gap between Rasputin and the CLI agents it competes with. 
- **G4 — Reliability by construction.** The two failure classes that have repeatedly cost us
  sessions — SQLite-over-bind-mount flakiness and Docker Desktop file-sharing I/O — are
  eliminated by architecture, not worked around.
- **G5 — Business-ready deployment shapes.** Workstation mode must never require Docker Desktop
  (a paid product for customers ≥250 employees / ≥$10M revenue); server mode (Docker Engine on
  Linux) stays supported and becomes the future team SKU. One codebase, two deployment modes.
- **G6 — WarSat stays the centerpiece.** Model orchestration, fit-scoring, fleet-aware
  planning, trials, and role routing remain WarSat's job in every mode. Native mode makes
  WarSat's life *simpler* (endpoints become plain `127.0.0.1:port`), never smaller.
- **G7 — Security posture never regresses.** Trusted-workspace gating, approvals, audit, and
  Privacy Lock carry over unchanged. Where this plan touches security surfaces it must *close*
  known gaps (skills sandbox `--network host`, THREAT_MODEL §6.2), not open new ones.

## Non-goals

- No rewrite of the engine, model registry, RAG/graph, frontend, or chat layout.
- No removal of Docker mode — it is the server SKU, not legacy.
- No new features riding along "while we're in there." Feature tracks (coding-agent Stages 5/6,
  WarSat enhancement tiers, business track) proceed separately.

### 2026-07-13 desktop host decision

The native daily driver is becoming **Rasputin Desktop**, with Electron owning the local FastAPI
process, application window, system tray, and lifecycle. This does not fork the product: Electron
loads the same React frontend from the same FastAPI backend on a random loopback-only port. Docker
becomes the headless server/appliance shape managed through Compose and the CLI. The foreground
`rasputin.ps1 start -Native` path remains available for development and recovery.

The first lifecycle milestone is implemented under `desktop/`: single-instance behavior, secure
renderer settings, backend health supervision, start/stop/restart tray actions, graceful shutdown,
isolated log handling, and one-time first-run credential presentation. A PyInstaller backend and
electron-builder/NSIS pipeline now produce a self-contained Windows application; signing and clean-
machine release qualification remain. Native Host adds stable-port browser operation with detached
lifecycle controls and start-at-login registration. The detailed boundary and packaging gates live
in [`DESKTOP_ARCHITECTURE.md`](DESKTOP_ARCHITECTURE.md), with all supported shapes in
[`DEPLOYMENT_MATRIX.md`](DEPLOYMENT_MATRIX.md).

### 2026-07-13 server-mode extension: accounts and HTTPS

The Docker server shape now supports simultaneous local users without changing the native
daily-driver premise. Both modes use the same account/session implementation, but retain separate
data stores unless `RASPUTIN_DATA_DIR` deliberately points them together. Personal chats, tasks,
preferences, and memory are owner-scoped. Workspace access is explicit (viewer, contributor,
developer, owner); appliance controls remain admin-only. This is one trusted appliance boundary,
not independent encrypted tenants.

Both modes can terminate HTTPS directly in Uvicorn. The repository helper invokes
FiloSottile/mkcert, stores only generated leaf material in ignored `data/tls/`, and supplies it
read-only to Docker. `-Lan` changes the bind address explicitly; the safe default remains loopback.
Native mode derives its Host/Origin allowlist from the generated SAN list. Public deployment still
requires a production certificate/reverse proxy rather than mkcert.

`setup-https` always preserves SANs for localhost, both loopback forms, and the machine hostname;
additional `-TlsName` values are additive. This prevents a friendly-name certificate from breaking
the standard native or Docker launch URL. Friendly names still require local DNS or a hosts-file
mapping; certificate generation does not change name resolution.

---

## Starting baseline (historical, verified 2026-07-10)

This section records the conditions that motivated the plan. It is **not** the current state;
Phases 0–4 completed on 2026-07-12. See the phase checklists and status log below.

- Wrapper runs in `rasputin-wrapper` (compose), port `127.0.0.1:8787`, `python -u server.py`.
- `./data` (SQLite) and `./workspace` are Docker Desktop bind mounts. Measured costs: a 327MB
  KV blob read took 20+s through the bind mount (fixed by caching, but the tax remains for all
  I/O); recurring `sqlite3.OperationalError: unable to open database file` under rapid
  up/down cycles; a lost first-boot password because credentials lived only in a removed
  container's logs (reset flow shipped `533aa9c`, but the class of problem is architectural).
- Extra project folders enter via the mount-request subsystem (`backend/core/workspace.py`):
  registry entry → compose volume line → restart → approval. Historically the most bug-dense
  subsystem in the repo (effect-loop toast spam, registry-deletion-on-approve, boot race —
  all root-caused here in July 2026).
- `shell_exec` / git tools (`backend/mcp/tools.py`) execute inside the container: Linux
  toolchain, workspace via bind mount.
- Skills sandbox: ephemeral containers with `--network host` (THREAT_MODEL §6.2, open).
- Native execution already works informally — `.claude/skills/verify/SKILL.md` boots the app
  with `RASPUTIN_DATA_DIR` isolation for verification. `runtime_store.py` and
  `workspace.py` honor `RASPUTIN_DATA_DIR`; `WRAPPER_RUNTIME` already branches
  container-vs-native behavior (e.g. WarSat `_discovery_hosts`).
- **Native-mode security caveat found during planning:** `localhost_bypass_enabled()`
  (backend/core/auth.py) intentionally never fires behind Docker (client IP is the bridge
  gateway), but in a native run on `127.0.0.1` it CAN fire. Phase 1 must decide its default
  before native mode is promoted to first-class. (G7)

## Execution isolation model — the decision that bounds an agent's blast radius

*Added 2026-07-10 after a fallout review of Phases 2–3. This is the load-bearing security
decision of the whole track; every phase below inherits it. The concern it answers: as work
moves off the throwaway container and onto the operator's real machine, how far can an automated
model's **mistake** reach, and what actually keeps it contained.*

**The reframe.** "Native wrapper" and "sandboxed shell" are *separate* decisions. Phases 0–2
make the *wrapper* run natively (G1/G2/G4/G5) regardless of how the agent's shell is isolated.
Only Phase 3's `shell_exec` runs arbitrary host commands, so it needs its own boundary. On Windows
we therefore run **the wrapper native, the agent's shell as a low-privilege sandbox account** — not
native-everything. Native non-Windows still uses the direct-process fallback documented below.

**What is and isn't already contained (verified against code, 2026-07-10):**

- The structured file tools — `fs_read/list/tree/write/patch/move/mkdir` — are hard-confined:
  every one resolves the target with `.resolve()` and rejects anything outside the workspace
  root (`_safe()`, `backend/mcp/layer.py:136`). `..`, absolute paths, and symlinks/junctions are
  all defeated because resolution happens *before* the containment check. A mistaken *file-tool*
  call cannot escape the approved folder. This is a real wall and stays one.
- `shell_exec` (`backend/mcp/layer.py:500`) is the one arbitrary-execution path and it is **not**
  confined: `cwd` is only a starting directory; an absolute path or `cd` ignores it. Its only
  current guard, `SHELL_DENY_PATTERNS` (`layer.py:37`), is a six-regex lexical filter whose own
  comment says "this is not a security boundary." It misses
  `Remove-Item C:\Windows\System32 -Recurse -Force`, `del /s /q ...`, and any indirection through
  `bash -c` / `python -c`. At the starting baseline, Docker deployment at least kept the command
  inside the long-lived wrapper container; moving the wrapper onto Windows removes even that host
  separation. Phase 3 therefore had to add a real host-side guardrail, not better regexes.

**Implemented result — how the shell is boxed in each mode:**

- **Native Windows (workstation) mode:** `shell_exec` runs under a **dedicated low-privilege local
  sandbox account**, inside a **Job Object** (whole-process-tree kill on timeout), with the
  workspace granted to that account by ACL and **external egress denied on a best-effort basis**.
  `taskkill /F /T` is the primary tree-kill because seclogon/Job Object nesting is not guaranteed;
  the Job Object is defense-in-depth. Access violations fail closed and return an explicit sandbox-
  boundary result rather than silently succeeding. Rationale:
  this is the only isolation that satisfies G1 (one-command install), G3 (the operator's real,
  machine-installed toolchain), and G5 (never requires Docker Desktop) *at once*. Against the
  risk we actually care about — *accidental* destruction — it is effective by construction:
  Windows' own ACLs already deny a separate non-admin principal any access to `System32`,
  `Program Files`, and other users' profiles, and we additionally deny it the operator's own
  profile outside the workspace. A mistaken `rm -rf` / `Remove-Item` of a system path returns
  *Access Denied* instead of executing. Stated honestly: this is a **strong guardrail against
  accidents and low-privilege mistakes, not an airtight wall against a determined adversary**
  (Microsoft does not treat integrity levels / restricted tokens as a security boundary) — which
  is the correct tradeoff for a single-operator desktop tool whose threat is fumble-fingers, not
  a hostile human at the keyboard.
- **Server (Docker Engine) mode:** `shell_exec` is a direct child of the long-lived wrapper
  container—not a new disposable container per call. The container boundary still separates it
  from the host, but the wrapper's normal bridge network and mounted workspaces remain reachable.
  This is materially different from the Skills sandbox below and must not be described as a
  per-execution hard wall.
- **Native non-Windows:** the current fallback is a direct backend subprocess with the same bounded
  output, sanitized environment, and process-tree timeout handling as Docker mode; the
  `Rasputin_sbx` account mechanism is Windows-only.
- **Opt-in hardened native (not implemented):** a VM/WSL2/container-backed shell remains a possible
  future option for operators who require a VM-grade wall.

The lexical deny-list is demoted to a **UX nicety** — a fast, friendly "are you sure?" on obvious
foot-guns — never the boundary.

**Capability split (so convenience never silently grants execution).** The former combined gate is
now split: `trusted` only auto-approves file/git edits; a *separate* per-workspace
`allow_host_shell` flag plus the global `allow_shell_execution` flag is required before shell
commands run. Host Shell enable is an explicit, strongly warned action; there is no per-command
confirmation in the current implementation.

**Toolchain caveat (recorded, not hand-waved).** Machine-wide installs (Node/Python/git in
`Program Files`, on the system PATH) are visible to the sandbox account automatically. A
*per-user* toolchain (nvm-windows, a user-local venv) is not, and must be granted read/execute to
the sandbox account at setup — a provisioning step Phase 3 owns.

**Two limits the sandbox does not remove (so we don't over-trust it):**

- It does not protect the workspace *itself*: `rm -rf .` inside the approved folder still deletes
  the project. Mitigation is git + the copy-never-move discipline, not isolation.
- Fallout is not only files: a mistaken `curl | sh`, a typosquatted `pip install`, or
  exfiltration of the workspace are all fallout, stopped only by **network-deny-by-default** —
  which is therefore first-class here, not a footnote.

## Difficulty legend

Same scale as the coding-agent checklist: **Easy** (config/wiring), **Medium** (real work, one
subsystem), **Hard** (shared/critical path), **Very Hard** (new architecture). Ratings reflect
what it takes to *verify*, not just write.

---

## Phase 0 — Data layer off the bind mount ☑

*Serves G4 directly; prerequisite for everything else. Small and shippable alone.*

> **Finding (2026-07-10, during the resolver sweep) — the data dir was SPLIT in two.**
> Modules resolved `ROOT` inconsistently: `backend/core/{auth,audit,security,preferences,telegram,
> runtime_store}`, `models/*`, `rag/*`, `engine/output`, `archive/__init__`, `mcp/skills` used
> `parents[1]` → `/app/backend/data` (host `./data/wrapper/`, incl. **`rasputin.db`, `auth.json`,
> `security.json`**), while `workspace`, `warsat`, `relay`, `trials`, `archive/service` used
> `parents[2]` → `/app/data` (host `./data/`). `docker-compose.yml` mounts BOTH
> (`./data:/app/data` and `./data/wrapper:/app/backend/data`). The shared resolver unifies all of
> them onto one dir — correct end-state — but this means **migrate-data must CONSOLIDATE
> `./data/wrapper/` into `./data/` before any Docker rebuild/cutover**, or the app boots blind to
> existing auth/registry/chats. The resolver change is therefore safe on-disk but MUST NOT be
> deployed (image rebuilt) until the consolidation + compose change below land together.
>
> **Empirical data-location map (measured 2026-07-10) — the migration MUST honor this.** Data is
> currently scattered across THREE host dirs from parents[1]/[2] × docker/native runs over time.
> Colliding filenames (`rasputin.db`, `audit.jsonl`, `memory`, `models_dev_catalog.json`,
> `warmind-context`) exist in more than one. The LIVE copies are the Docker-written ones under
> `./data/wrapper/`; the others are stale orphans. For `rasputin.db`:
> `./data/wrapper/rasputin.db` = **762 MB, modified today, has `-wal`/`-shm` (LIVE)**;
> `./backend/data/rasputin.db` = 2.3 MB, 07-06 (stale native); `./data/rasputin.db` = 425 KB,
> 06-19 (stale orphan). Consolidation rule: for any collision, **`./data/wrapper/` wins**; pull
> non-colliding top-level files (`auth.json`, `security.json`, `workspace.json`, `warsat/`,
> `mcp_relays.json`, `archive.sqlite3`, `trials.*`, `preferences.json`, …) from `./data/`; treat
> `./backend/data/` and the stale root DBs as archive-only. The 762 MB live DB also warrants a
> `VACUUM`/blob audit (cf. the 327 MB KV blob noted in the baseline) — separate task, flagged.
>
> **Simplification found 2026-07-10: the loose JSON files are LEGACY.** The running app reads its
> live state from `runtime_kv` inside `rasputin.db` — that table holds `auth`, `security`,
> `mcp_relays`, `model_secrets`, `models_registry`, `userPreferences`, `workspace_config`,
> `telegram_config`, `archive`, `output`, `rag_graph`, `rag_vector`, `warsat_deploy_grants`, …
> (the `memory_json_imported` key confirms a prior JSON→DB import). So `configured=True` even
> though `auth.json` is absent from where the container looks. **The migration's real job is to
> preserve the single live `data/wrapper/rasputin.db`** and place it where the resolver now
> expects it (`<data_dir>/rasputin.db`); the scattered `*.json` are archaeology, not sources of
> truth. Before cutover, confirm no module still falls back to JSON-when-KV-present, then the
> "carefully merge colliding JSON" worry mostly evaporates. Backup verified 2026-07-10:
> `C:\Users\elliott\RasputinBackups\pre-migration-2026-07-10\` (integrity `ok`, holds auth+chats).

- [x] Native mode default + shared resolver — **DONE 2026-07-10.** New `backend/core/datadir.py`
      `data_dir()` (RASPUTIN_DATA_DIR → `WRAPPER_RUNTIME=docker`/`<repo>/data` → native
      `%LOCALAPPDATA%\Rasputin\data` → fallback); all 21 call sites across 19 modules routed
      through it. `rg 'ROOT / "data"'` in caller modules returns empty; backend smoke = 96 tests OK.
- [x] Docker mode: **DONE 2026-07-10.** `docker-compose.yml` now mounts a single named volume
      `rasputin-data:/app/data`; both old mounts (`./data:/app/data` and the dead
      `./data/wrapper:/app/backend/data`) removed. The test/gui-test variants already used a
      single `/app/data` mount and are resolver-compatible unchanged, so they were left as-is
      (bind-mount to `./testdata` is intentional for test isolation).
- [x] `rasputin.ps1 migrate-data`: **DONE 2026-07-10.** Idempotent, copy-never-move; populates
      `rasputin_rasputin-data` from `./data/*` with `./data/wrapper/*` overlaid (live wins);
      "already migrated" keyed off `rasputin.db` presence (verified: reports already-migrated).
- [x] Validation: **DONE 2026-07-10.** Live cutover verified on data, not health — rebuilt image
      resolves `data_dir()=/app/data`, `rasputin.db` in-volume = 762,314,752 bytes,
      `integrity_check=ok`, 9 sessions / 16 messages present, `auth` configured as `admin`,
      `/api/health` ready. Backend smoke 96/96 green. Old `./data` + `./data/wrapper` left intact
      on disk for rollback.
  - Open follow-ups (not blockers): the mount-request override file
    (`data/docker-compose.mounts.yml`) now lives in the volume while `rasputin.ps1 start` still
    reads the host copy — resolve when Phase 2 reworks the mount subsystem; optional `VACUUM`/blob
    prune to reclaim the ~99%-bloat DB; note that `docker compose down -v` would delete the volume
    (named-volume tradeoff), so document "never `-v`".

**Definition of done:** `docker compose down`/`up` cycles cannot produce SQLite flakiness, and
no SQLite file is ever again read through Docker Desktop file sharing.

## Phase 1 — Native launch becomes first-class ☑

*Serves G1, G5, G6. Foundation phase — nothing user-visible changes yet.*

- [x] `rasputin.ps1 start -Native` (and `rasputin.sh --native`): venv bootstrap from
      `requirements.txt`, uvicorn launch, env defaults, port conflict check — **(Medium)**
- [x] Path audit **DONE** — all 9 `WRAPPER_RUNTIME` branches inventoried + verified native; contract
      written in [`WRAPPER_RUNTIME_CONTRACT.md`](WRAPPER_RUNTIME_CONTRACT.md). No code path assumes `/app/...` container layout when `WRAPPER_RUNTIME` is
      native; inventory every `WRAPPER_RUNTIME` branch and document the contract — **(Medium)**
- [x] **DONE** — off by default (confirmed) + loud native startup warning/audit when enabled.
      Decide + implement the `localhost_bypass_enabled()` default for native mode (recommend:
      off by default, opt-in env flag; real auth shipped 07-07 and reset flow exists, so the
      bypass is no longer needed for recoverability) — **(Medium, security-sensitive)** (G7)
- [x] **DONE** — native-gated Host + Origin allowlist in `backend/main.py` (verified: evil
      Host/foreign Origin → 403, legit → ok; Docker gated off). Reject cross-origin browser requests in native mode: native mode is a real localhost HTTP
      server any browser tab can reach, so add an `Origin`/`Host` allowlist check (a webpage must
      not be able to drive the API even with the bypass off) — **(Medium, security-sensitive)** (G7)
- [x] WarSat from the host **DONE (code-path level)** — verified natively: `_discovery_hosts()` →
      `['127.0.0.1']`, `_endpoint_for()` → host binding (not `host.docker.internal`),
      `gpu_live_metrics_via_docker()` → `[]` no-crash, model URLs stay loopback. Native drives
      Docker via the host `docker` CLI. A full GPU deploy is env-gated (hardware) and left to a
      live run — **(Medium)** (G6)

## Status log (cont.)

- 2026-07-11 — **Phase 2 backend complete.** Root-safety guard rejects drive/home/system roots +
  the data dir (`_unsafe_workspace_root`, POSIX dirs gated to non-Windows to avoid `Path('/')→C:\`
  false-positives). Native workspace approval registers host paths directly — `mount_plan` returns
  `requires_restart=False`, `save_mount_request` calls `approve()` instead of writing a compose
  override, so the pending-mounts panel + restart badges are empty in native with no frontend
  change. Docker flow unchanged; smoke exercises mount-plan in both runtimes (96 OK). Also fixed a
  Phase-1 middleware regression (TestClient loopback base_url). Remaining Phase 2: frontend copy +
  fully hiding the mount panel in native, the Docker mount-approve auto-register gap, and a
  Playwright E2E. Next big one: **Phase 3 — host-toolchain sandboxed shell (the isolation model)**.
- 2026-07-11 — **Phase 2 COMPLETE.** Frontend finished: `security.native` exposed to the UI,
  host-browse/mount-apply/mount-requests native-gated to the file-read grant (docker-control is a
  Docker concept), and the Add Folder modal branches on native (choose-a-folder copy, no
  docker-control gating, no compose/restart success screen). Verified end-to-end: native HTTP flow
  (browse/approve/register/reject) + Playwright modal render + smoke 96 OK + Docker path unchanged
  and live container healthy. Mount-approve auto-register gap re-filed as a deferred Docker-UX
  follow-up. **All of Phase 2's definition-of-done is met.** Next: Phase 3 (host-toolchain shell).
- 2026-07-11 — **Phase 3, Stage 3.1 COMPLETE** (commit 38f34b6). `shell_exec` timeout now kills
  the whole process tree, not just the parent: Windows `taskkill /F /T /PID` (bounded 10s wait),
  POSIX `os.killpg` on the session group; children spawn in a new process group
  (`CREATE_NEW_PROCESS_GROUP` / `start_new_session`) so a timed-out command can't orphan workers.
- 2026-07-11 — **Phase 3, Stage 3.2 COMPLETE** (commit 3b9d580). Capability split landed early
  (was filed under Phase 4): host command execution is now a per-workspace `allow_host_shell`
  opt-in *distinct from* Trusted Dev Mode. Trusting a folder auto-approves file writes + local git
  but no longer grants unattended host shell; `shell_exec` gates on `allow_host_shell`, exposed via
  `POST /api/workspace/host-shell` (file-write cap required, audited) with a separate UI toggle +
  strong-warning modal. Smoke proves trusted-alone is refused, then Host Shell unlocks it (96 OK);
  frontend builds clean. Next: **Stage 3.3 — dedicated low-privilege sandbox account + workspace
  ACL + run-as (Job Object), which needs a one-time elevated provisioning step on the operator's
  machine.**
- 2026-07-11 — **Historical checkpoint — Phase 3, Stage 3.3 first-pass (not yet run that day).** Two findings
  changed the plan before writing system-changing code:
  (a) **pywin32 is unnecessary** — a stdlib-only ctypes POC proved the manual pipe-capture path
  (`CreatePipe` + drain threads + `GetExitCodeProcess`) captures stdout/stderr/exit-code correctly.
  That path is required because `CreateProcessWithLogonW` bypasses asyncio's pipe plumbing; the
  whole run-as surface (advapi32 logon, kernel32 Job Objects) is reachable via ctypes, so no new
  dependency and no dependency-install in the elevated step.
  (b) **§10-Q1 logon-rights fork resolved to "defer":** `CreateProcessWithLogonW` does an
  interactive-type logon, so denying `SeDenyInteractiveLogonRight` (design §3.1) would break the
  primary mechanism. A standard user already has exactly the right it needs, so the **first-pass
  provision script touches logon rights zero**; deny-logon hardening waits on the first-run
  validation that picks the final mechanism.
  Authored `scripts/Provision-Sandbox.ps1` (idempotent create/repair/`-Remove`/`-Status`): standard
  `Rasputin_sbx` user, 40-char random password stored DPAPI-CurrentUser (owner-SID recorded so the
  backend refuses a cross-user credential), best-effort SID-scoped egress block. Parse-clean;
  `-Status` verified (reports the native `sandbox.cred` path). **Three unknowns (job-nesting via
  seclogon §9-T5, per-user firewall WFP scoping §9-T6, logon-rights) are all resolved by the first
  elevated run** — the script isolates them and defaults safe. **CHECKPOINT: creating the account +
  firewall + stored credential is a system change needing the operator's elevated go-ahead. Blocked
  on that; the run-as integration (`backend/core/sandbox_exec.py`) is authored right after, since
  its logon/job/firewall behavior can only be verified once the account exists.**
- 2026-07-12 — **Phase 3 COMPLETE (security-core scope).** The real `Rasputin_sbx` account was
  provisioned and `run_as_sandbox()` was verified end to end (`fdd6bc8`: `whoami`, exit-code
  propagation, PowerShell/cmd, bounded output, timeout tree-kill). Native Windows `shell_exec` now
  routes through that account; Host Shell grants/revokes the workspace ACL and fails closed when
  provisioning is absent (`42e68a8`). On-demand UAC provisioning and clear Access-Denied boundary
  reporting followed in `2352dad`. Honest residuals: the firewall rule is best-effort with loopback
  open, the workspace itself remains writable, Job Object assignment is defense-in-depth, and git
  tools are still direct backend children.
- 2026-07-12 — **Phase 4 COMPLETE.** Option C from the §6.2 review shipped in `5742cd6`: every Skill
  container runs `--network none`, and its only host-tool channel is a private newline-delimited
  stdio RPC. Verified with multi-call tool round-trips, a >64KB result, and a blocked outbound
  request. The host-side tool callback remains a privileged surface; §6.2 documents that residual.
- [x] **DONE** — native launch serves prebuilt `frontend/` (same as container), warns if unbuilt.
      Frontend build story in native mode (serve prebuilt `frontend/` exactly as the container
      does; document `npm run build` for dev) — **(Easy)**
- [x] Test: native boot on a clean data dir verified (health, auth, static serving, security
      enforcement); also fixed **Bug A** — `data_dir()` now `mkdir(parents=True)` so the nested
      native default is created on fresh machines. WarSat plan/deploy dry-run parity still TODO — **(Medium)**

**Definition of done:** a developer with Python + Docker Desktop can run
`.\rasputin.ps1 start -Native` and get a fully working Rasputin, WarSat included, with real auth.

## Phase 2 — Direct workspaces in native mode ☑

*Serves G2. The mount subsystem stops being load-bearing.*

- [x] **DONE (backend)** — Native mode: approving a workspace = validating + registering a host path directly; no
      mount request, no restart. Reuse the existing approval/trust flow unchanged — **(Medium)**
- [x] **DONE** — `_unsafe_workspace_root()` rejects drive/home/system roots + data dir; verified.
      Root-safety validation in `workspace.add()` (`workspace.py:801` currently checks only
      exists + is_dir): reject or require a hard, typed confirmation for drive roots (`C:\`),
      `%USERPROFILE%` itself, `%WINDIR%`, `%ProgramFiles%`/`%ProgramFiles(x86)%`, and the Rasputin
      data dir — a project folder is a subdirectory, never a system location. Prevents a one-click
      misapproval of the whole disk from becoming the shell's blast radius — **(Easy)** (G7)
- [x] **DONE** — native writes no mount-request/compose/`requires_restart`, so the pending panel +
      restart badges are empty in native; `security.native` exposed (bootstrap + `/api/security`),
      host-browse/mount-apply/mount-requests native-gated to the file-read grant, and the Add Folder
      modal branches (native copy, no docker-control gating, no compose/restart success screen). Gate
      the mount-request subsystem to Docker mode only; native UI never shows it — **(Medium)**
- [x] **RE-FILED (deferred)** — approving a *ready* pending mount already auto-registers the
      workspace (`approvePendingMount` → `approvePath`). The residual gap is only that Docker's flow
      stays two-step (mount-apply → restart → approve) instead of auto-registering ready mounts on
      boot — a Docker-mode UX nicety, not a bug, not worth destabilizing the mount subsystem now.
      Tracked as a standalone follow-up. — **(Easy)**
- [x] **DONE** — the native Add Folder modal reads "Choose a folder on your machine…" with no
      Docker/mount language (verified via Playwright). UI copy: workspace flow describes the native
      path plainly ("choose a folder") — **(Easy)**
- [x] **DONE** — native HTTP E2E (host-browse 200 without docker-control, mount-apply registers
      directly, folder in workspace list, dangerous root → 400) + Playwright (native modal renders;
      Docker copy/warning/"Generate Mount" absent; no page errors); smoke 96 OK in both runtimes.
      Test: native workspace approve → browse → index → trusted-mode gating, end to end — **(Medium)**

**Definition of done:** in native mode, opening a new project is: pick folder → approve →
working, in under ten seconds, with zero restarts.

## Phase 3 — Host-toolchain agent (Windows shell semantics) ☑

*Serves G3. Coordinates with coding-agent plan Stage 6 — do this before or with it.*

- [x] `shell_exec` on native Windows: **DONE.** Process-tree termination uses `taskkill /F /T` + a
      new process group; interpreter selection, sandbox-profile environment, and bounded output with
      a truncation marker are implemented. Output archiving was not needed for the security-core
      gate and remains a product follow-up rather than a Phase-3 blocker. — **(Hard)**
- [x] **Implement the native isolation model (see "Execution isolation model" above):** run
      `shell_exec` under the dedicated low-privilege sandbox account inside a Job Object, with the
      workspace ACL-granted, best-effort external-egress denial, and boundary violations failing
      closed into an explicit result. The deny-list remains only a UX foot-gun hint. Verified against
      the real account; this is an accident-containment guardrail, not an airtight wall. — **(Very Hard)** (G7)
- [x] Provisioning — **elevation-on-demand, not a manual checkpoint.** On the first Host Shell
      enable, the backend checks the stored credential without elevation and, if unprovisioned or
      broken, raises ONE UAC prompt via
      `Start-Process -Verb RunAs` to create/repair the account + credential + firewall. `-Verb RunAs`
      elevates the same user, which is exactly what the DPAPI-CurrentUser credential needs. The
      per-workspace ACL grant (`icacls <ws> /grant Rasputin_sbx:(OI)(CI)M`) needs **no** elevation —
      verified: a folder's owner can rewrite its DACL unelevated — so enabling Host Shell on each
      workspace stays silent. Only the one-time account/firewall creation costs a single consent
      click (later absorbed into the installer's own elevation, Phase 5). We deliberately keep that
      one UAC consent: automating it away (disabled UAC, SYSTEM scheduled task, stored admin creds)
      would dismantle the blast-radius protection this phase exists to build — **(Hard)**
- [x] Git tools against host git remain direct backend child processes and are covered by their
      existing trust/approval and structured-output tests. They do **not** inherit the
      `Rasputin_sbx` boundary; this residual is explicit in `THREAT_MODEL.md`. — **(Easy)**
- [x] Capability + approval gating verified in native mode: Trusted alone does not enable Host
      Shell, revoke-mid-session blocks the next shell action, and calls are audited. — **(Medium)** (G7)
- [x] Test: live Windows run-as proved account identity, exit-code propagation and timeout tree-kill;
      smoke covers bounded output, fail-closed unprovisioned behavior, separate capability gating,
      and revocation. The live-account test skips where `Rasputin_sbx` is not provisioned. — **(Hard to verify well)**

**Definition of done:** a `code`-mode task in a trusted native workspace runs the repo's real
test suite with the operator's real toolchain — the Stage 6 test loop gets the host machine.

## Phase 4 — Sandbox hardening ☑

*Serves G7. Native wrapper still uses Docker for sandboxes — that's the right tool.*

- [x] Skills sandbox: **`--network none` + private stdio RPC** replaced `--network host` (Option C);
      THREAT_MODEL §6.2 is RESOLVED. The skill container has no network; its host-side tool callback
      remains permissioned but privileged and is documented as residual surface. — **(Medium)**
- [x] Capability split: per-workspace `allow_host_shell` flag distinct from `trusted` — **DONE
      early in Phase 3, Stage 3.2 (3b9d580).** `shell_exec` gates on `allow_host_shell`; toggle +
      strong-warning modal in the UI. (Per-exec confirmation deferred — the deny-list + audit +
      sandbox account are the layered controls.) — **(Medium, security-sensitive)** (G7)
- [x] The Skill sandbox launch/RPC path is runtime-independent: the same `--network none` container
      and stdio protocol are used whether the wrapper is native or containerized. — **(Medium)**
- [ ] Watch item (not a commitment): Docker Sandboxes (`sbx`) microVM prototype for skills
      isolation once its beta stabilizes and licensing is understood — **(env-blocked)**

**Definition of done:** no Rasputin-spawned container runs with host networking.

## Phase 5 — Packaging & distribution ☐

*Serves G1, G5. Only meaningful after Phases 1–3; details deliberately thin until then.*

- [ ] Single-artifact install for workstation mode (winget/MSI or equivalent; tray/auto-start
      optional) — **(Hard)**
- [ ] Server mode: publish the wrapper image (GHCR) + reference compose for Docker Engine
      hosts — the team-SKU install becomes a two-line compose file — **(Medium)**
- [ ] Update channel / version surfacing in the UI — **(Medium)**
- [ ] Business prerequisite tracked outside this plan, gating public distribution only: LICENSE +
      CLA decision. Repo is private with no license — not a current exposure. **Goal is to turn
      Rasputin into a company (not necessarily sell the software itself)**, so the model must
      preserve commercial viability — avoid a permissive OSS license (MIT/Apache/BSD) that lets a
      competitor host/resell it. Viable: hosted/SaaS (AGPL core + paid hosting), open-core,
      source-available (BSL/Elastic 2.0/PolyForm), or dual-license; a CLA is load-bearing if
      outside contributions are accepted — **(decision, not code)**

**Definition of done:** "install Rasputin" is one command/download on a workstation, two lines
on a server — and neither mentions Docker Desktop.

---

## Risks and mitigations

- **Dual-mode drift** — a feature works in one mode and silently breaks in the other.
  *Mitigation:* the smoke suite runs in native mode in CI-equivalent local runs from Phase 1 on;
  any `WRAPPER_RUNTIME` branch requires a test exercising both sides.
- **Windows process semantics (Phase 3)** — child-process trees, PowerShell quoting, encoding.
  *Mitigation:* it's the only Hard-rated phase; it gets its own verification pass with
  deliberately hostile test commands before the coding agent is pointed at it.
- **Data migration (Phase 0)** — one-time, but touches everything.
  *Mitigation:* migrate-data is copy-then-verify (never move), old bind-mount data left intact
  until the operator deletes it.
- **Native localhost bypass (Phase 1)** — promoting native mode without deciding this would
  quietly disable auth for native users. *Mitigation:* explicitly scheduled, default-off
  recommendation recorded above; plus an `Origin`/`Host` allowlist so a browser tab can't drive
  the API regardless.
- **Shell isolation is a guardrail, not a wall (Phase 3)** — the dedicated-account/ACL model
  stops *accidental* machine-wide damage but is not proof against a determined adversary, and it
  does not protect the workspace's own contents. *Mitigation:* scope it honestly (the threat is
  operator/model mistakes on a single-user desktop), keep network-deny-by-default as first-class,
  rely on git + copy-never-move for in-workspace safety, and offer opt-in container/WSL2 for
  anyone wanting a hard wall.
- **Over-broad workspace root (Phase 2)** — one-click approval of `C:\` or `%USERPROFILE%` would
  make the whole disk the shell's cwd/scope. *Mitigation:* root-safety validation in
  `workspace.add()` rejecting system/home/drive roots.

## Overall success criteria — check when ALL are true

- [ ] Fresh Windows machine → running Rasputin in one command, no compose knowledge (G1)
- [ ] New project folder usable in under ten seconds with zero restarts (G2)
- [ ] A coding task runs the operator's real test suite via the host toolchain (G3)
- [ ] Zero bind-mount SQLite incidents after Phase 0 lands (G4)
- [ ] The same repo deploys as native workstation and Docker Engine server, verified (G5)
- [ ] WarSat deploys, monitors, and fleet-plans identically in both modes (G6)
- [ ] THREAT_MODEL has no open items introduced by this plan, and §6.2 is resolved (G7)

## Status log

- 2026-07-10 — Plan authored and direction approved (staged dual-mode over full cutover and
  all-Docker modernization). No phases started.
- 2026-07-10 — Fallout review folded in: added the "Execution isolation model" section
  (dedicated low-privilege sandbox account + Job Object + workspace ACLs + network-deny +
  fail-closed escalation for native shell; disposable container for server mode; deny-list
  demoted to UX). Added root-safety validation (Phase 2), Origin/CSRF check (Phase 1),
  `allow_host_shell` capability split (Phase 4), and hardened the process-tree-kill item
  (Phase 3). Beginning execution at Phase 0.
- 2026-07-10 — **Phase 0 COMPLETE.** Shared data-dir resolver shipped; live data migrated off the
  Docker Desktop bind mount into named volume `rasputin_rasputin-data`; `docker-compose.yml`
  simplified to one mount; `rasputin.ps1 migrate-data` added (idempotent). Verified on data (762MB
  DB, 9 sessions/16 messages, admin auth, health ready). Pre-flight: verified filesystem backup at
  `C:\Users\elliott\RasputinBackups\pre-migration-2026-07-10\` + git branch
  `backup/pre-migration-2026-07-10` (pushed; repo confirmed private). Rollback: `git checkout
  3eecb05 -- docker-compose.yml backend/ && docker compose up -d --build` (old code+compose reads
  the untouched `./data/wrapper`), or restore the filesystem backup. Next: Phase 1 (native launch).
- 2026-07-10 — **Phase 1 mostly complete.** Shipped `rasputin.ps1 start -Native` (venv + uvicorn +
  port-conflict check), native-gated Host/Origin hardening + `localhost_bypass` native warning
  (`backend/main.py`), native frontend serving, and fixed Bug A (native `%LOCALAPPDATA%` data dir
  now created with `parents=True`). Verified: native enforcement (evil Host / foreign Origin →
  403, legit ok, Bug A dir created) and Docker regression (rebuilt, gated off, 9 sessions + admin
  auth intact). Remaining: WarSat-from-host verification (G6) and a formal `WRAPPER_RUNTIME` path-
  audit contract doc. Verification gotcha logged: a stale native server on :8899 silently
  intercepted early smoke requests — always confirm the boot bound its port before trusting curls.
