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

---

## Current baseline (verified 2026-07-10)

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
Only Phase 3's `shell_exec` runs arbitrary commands, so only it needs a box. We therefore run
**the wrapper native, the agent's shell in a sandbox** — not native-everything.

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
  `bash -c` / `python -c`. Today this is safe **only** because the command runs inside the
  throwaway container. Phase 3 removes that container — so Phase 3 must replace the container's
  wall with a new one, not with better regexes.

**The decision — how the shell is boxed in each mode:**

- **Native (workstation) mode:** `shell_exec` runs under a **dedicated low-privilege local
  sandbox account**, inside a **Job Object** (whole-process-tree kill on timeout), with the
  workspace granted to that account by ACL and **network denied by default**, and any access
  violation **failing closed into an approval prompt** rather than a silent success. Rationale:
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
- **Server (Docker Engine) mode:** `shell_exec` runs in a disposable workspace-only container
  with no host networking — the same model Codex and Claude Code use on Linux. This is a hard
  wall and is the right tool where Docker is already present.
- **Opt-in hardened native:** operators who want a VM-grade wall on the workstation can enable
  WSL2- or container-backed shell execution. It is *offered, not required*, so G5 holds for
  everyone who doesn't opt in.

The lexical deny-list is demoted to a **UX nicety** — a fast, friendly "are you sure?" on obvious
foot-guns — never the boundary.

**Capability split (so convenience never silently grants execution).** Today a single `trusted`
flag (`workspace.py:886`) both auto-approves file edits *and* satisfies the `shell_exec` gate
(`layer.py:507`). Natively that means "stop nagging me about edits" would also mean "run
unattended host shell." Phase 3/4 split these: `trusted` keeps auto-approving edits; a *separate*
per-workspace `allow_host_shell` flag (plus a per-exec confirmation) is required before any
command runs on the host.

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

## Phase 0 — Data layer off the bind mount ☐

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

## Phase 1 — Native launch becomes first-class ☐

*Serves G1, G5, G6. Foundation phase — nothing user-visible changes yet.*

- [x] `rasputin.ps1 start -Native` (and `rasputin.sh --native`): venv bootstrap from
      `requirements.txt`, uvicorn launch, env defaults, port conflict check — **(Medium)**
- [~] Path audit (partial — native boot validated end-to-end for core paths; WarSat/model
      discovery paths not yet exercised natively; formal contract doc TODO): no code path assumes `/app/...` container layout when `WRAPPER_RUNTIME` is
      native; inventory every `WRAPPER_RUNTIME` branch and document the contract — **(Medium)**
- [x] **DONE** — off by default (confirmed) + loud native startup warning/audit when enabled.
      Decide + implement the `localhost_bypass_enabled()` default for native mode (recommend:
      off by default, opt-in env flag; real auth shipped 07-07 and reset flow exists, so the
      bypass is no longer needed for recoverability) — **(Medium, security-sensitive)** (G7)
- [x] **DONE** — native-gated Host + Origin allowlist in `backend/main.py` (verified: evil
      Host/foreign Origin → 403, legit → ok; Docker gated off). Reject cross-origin browser requests in native mode: native mode is a real localhost HTTP
      server any browser tab can reach, so add an `Origin`/`Host` allowlist check (a webpage must
      not be able to drive the API even with the bypass off) — **(Medium, security-sensitive)** (G7)
- [ ] WarSat from the host: verify deploy/status/logs/discovery against Docker Desktop from a
      native wrapper; `_discovery_hosts()` already returns `127.0.0.1` natively — confirm
      endpoints, health probes, and the fleet VRAM probe (`gpu_live_metrics_via_docker`) all
      work without `host.docker.internal` — **(Medium)** (G6)
- [x] **DONE** — native launch serves prebuilt `frontend/` (same as container), warns if unbuilt.
      Frontend build story in native mode (serve prebuilt `frontend/` exactly as the container
      does; document `npm run build` for dev) — **(Easy)**
- [x] Test: native boot on a clean data dir verified (health, auth, static serving, security
      enforcement); also fixed **Bug A** — `data_dir()` now `mkdir(parents=True)` so the nested
      native default is created on fresh machines. WarSat plan/deploy dry-run parity still TODO — **(Medium)**

**Definition of done:** a developer with Python + Docker Desktop can run
`.\rasputin.ps1 start -Native` and get a fully working Rasputin, WarSat included, with real auth.

## Phase 2 — Direct workspaces in native mode ☐

*Serves G2. The mount subsystem stops being load-bearing.*

- [ ] Native mode: approving a workspace = validating + registering a host path directly; no
      mount request, no restart. Reuse the existing approval/trust flow unchanged — **(Medium)**
- [ ] Root-safety validation in `workspace.add()` (`workspace.py:801` currently checks only
      exists + is_dir): reject or require a hard, typed confirmation for drive roots (`C:\`),
      `%USERPROFILE%` itself, `%WINDIR%`, `%ProgramFiles%`/`%ProgramFiles(x86)%`, and the Rasputin
      data dir — a project folder is a subdirectory, never a system location. Prevents a one-click
      misapproval of the whole disk from becoming the shell's blast radius — **(Easy)** (G7)
- [ ] Gate the mount-request subsystem (pending-mounts panel, compose volume generation,
      restart-needed badges) to Docker mode only; native UI never shows it — **(Medium)**
- [ ] Close the mount-approve auto-register gap *in Docker mode* while in there (open register
      item), or explicitly re-file it — **(Easy)**
- [ ] UI copy: workspace flow describes the native path plainly ("choose a folder") — **(Easy)**
- [ ] Test: native workspace approve → browse → index → trusted-mode gating, end to end,
      no mount tables touched — **(Medium)**

**Definition of done:** in native mode, opening a new project is: pick folder → approve →
working, in under ten seconds, with zero restarts.

## Phase 3 — Host-toolchain agent (Windows shell semantics) ☐

*Serves G3. Coordinates with coding-agent plan Stage 6 — do this before or with it.*

- [ ] `shell_exec` on native Windows: shell selection (PowerShell vs cmd), **process-tree
      termination on timeout (Job Object / `taskkill /T /F` — `proc.kill()` at `layer.py:557`
      terminates only the parent on Windows, orphaning children)**, minimal-env construction,
      output caps — same guarantees as the Linux path — **(Hard)**
- [ ] **Implement the native isolation model (see "Execution isolation model" above):** run
      `shell_exec` under the dedicated low-privilege sandbox account inside a Job Object, with the
      workspace ACL-granted, network denied by default, and boundary violations failing closed
      into an approval prompt. This replaces the deny-list-as-boundary; keep `SHELL_DENY_PATTERNS`
      only as a UX foot-gun hint — **(Very Hard)** (G7)
- [ ] Provisioning: create/repair the sandbox account and workspace ACLs at setup; grant any
      per-user toolchain dir read/execute to that account (machine-wide installs work already) — **(Hard)**
- [ ] Git tools against host git (path forms, `safe.directory` not needed natively,
      CRLF/UTF-8 as encountered) — **(Easy)**
- [ ] Trusted-workspace + approval gating verified identical in native mode (audit rows,
      revoke-mid-session) — **(Medium)** (G7)
- [ ] Test: timeout kills a child-spawning command cleanly on Windows; output cap + archive
      path works; untrusted workspace still refuses — **(Hard to verify well)**

**Definition of done:** a `code`-mode task in a trusted native workspace runs the repo's real
test suite with the operator's real toolchain — the Stage 6 test loop gets the host machine.

## Phase 4 — Sandbox hardening ☐

*Serves G7. Native wrapper still uses Docker for sandboxes — that's the right tool.*

- [ ] Skills sandbox: isolated bridge network + explicit allowlist instead of
      `--network host`; update THREAT_MODEL §6.2 to RESOLVED with the design — **(Medium)**
- [ ] Capability split: introduce a per-workspace `allow_host_shell` flag distinct from
      `trusted`, so auto-approving file edits never implicitly grants unattended host shell; gate
      `shell_exec` on it plus a per-exec confirmation (`layer.py:507` today keys off `trusted`
      alone) — **(Medium, security-sensitive)** (G7)
- [ ] Sandbox works identically whether the wrapper is native or containerized — **(Medium)**
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
- [ ] Blocking business prerequisite tracked outside this plan: LICENSE + CLA decision (repo is
      currently public with no license) — **(decision, not code)**

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
