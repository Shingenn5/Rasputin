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

## Difficulty legend

Same scale as the coding-agent checklist: **Easy** (config/wiring), **Medium** (real work, one
subsystem), **Hard** (shared/critical path), **Very Hard** (new architecture). Ratings reflect
what it takes to *verify*, not just write.

---

## Phase 0 — Data layer off the bind mount ☐

*Serves G4 directly; prerequisite for everything else. Small and shippable alone.*

- [ ] Docker mode: replace the `./data` bind mount with a named volume in
      `docker-compose.yml` (and the test/gui-test compose variants) — **(Easy)**
- [ ] `rasputin.ps1 migrate-data`: one-time copy of existing `./data` contents into the named
      volume, idempotent, with a clear "already migrated" message — **(Medium)**
- [ ] Native mode: default `RASPUTIN_DATA_DIR` to `%LOCALAPPDATA%\Rasputin\data` when unset and
      not running in Docker (`WRAPPER_RUNTIME` check); repo `./data` remains an explicit
      override for dev — **(Easy)**
- [ ] Grep-audit: every module that touches the data dir goes through the shared resolver —
      no residual hardcoded `ROOT / "data"` (the `workspace.py` lesson of 2026-07-06) — **(Easy)**
- [ ] Test: fresh boot with empty named volume bootstraps cleanly; migration preserves auth,
      registry, sessions — **(Medium)**
- [ ] Validation: backend smoke green in both modes; live Docker boot + login after migration

**Definition of done:** `docker compose down`/`up` cycles cannot produce SQLite flakiness, and
no SQLite file is ever again read through Docker Desktop file sharing.

## Phase 1 — Native launch becomes first-class ☐

*Serves G1, G5, G6. Foundation phase — nothing user-visible changes yet.*

- [ ] `rasputin.ps1 start -Native` (and `rasputin.sh --native`): venv bootstrap from
      `requirements.txt`, uvicorn launch, env defaults, port conflict check — **(Medium)**
- [ ] Path audit: no code path assumes `/app/...` container layout when `WRAPPER_RUNTIME` is
      native; inventory every `WRAPPER_RUNTIME` branch and document the contract — **(Medium)**
- [ ] Decide + implement the `localhost_bypass_enabled()` default for native mode (recommend:
      off by default, opt-in env flag; real auth shipped 07-07 and reset flow exists, so the
      bypass is no longer needed for recoverability) — **(Medium, security-sensitive)** (G7)
- [ ] WarSat from the host: verify deploy/status/logs/discovery against Docker Desktop from a
      native wrapper; `_discovery_hosts()` already returns `127.0.0.1` natively — confirm
      endpoints, health probes, and the fleet VRAM probe (`gpu_live_metrics_via_docker`) all
      work without `host.docker.internal` — **(Medium)** (G6)
- [ ] Frontend build story in native mode (serve prebuilt `frontend/` exactly as the container
      does; document `npm run build` for dev) — **(Easy)**
- [ ] Test: native boot on a clean data dir passes the same smoke suite; WarSat plan/deploy
      dry-run paths behave identically — **(Medium)**

**Definition of done:** a developer with Python + Docker Desktop can run
`.\rasputin.ps1 start -Native` and get a fully working Rasputin, WarSat included, with real auth.

## Phase 2 — Direct workspaces in native mode ☐

*Serves G2. The mount subsystem stops being load-bearing.*

- [ ] Native mode: approving a workspace = validating + registering a host path directly; no
      mount request, no restart. Reuse the existing approval/trust flow unchanged — **(Medium)**
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

- [ ] `shell_exec` on native Windows: shell selection (PowerShell vs cmd), process-tree
      termination on timeout (kill children, not just the parent), minimal-env construction,
      output caps — same guarantees as the Linux path — **(Hard)**
- [ ] Deny-list review for Windows-equivalent catastrophic patterns — **(Medium)**
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
  recommendation recorded above.

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
