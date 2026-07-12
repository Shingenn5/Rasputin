# Rasputin — Execution Plan (remainder of the roadmap)

*Created 2026-07-11 · branch `codex/agentic-coding-loop-v1`*

The ordered *how* for finishing the goals in `docs/DUAL_MODE_ARCHITECTURE_PLAN.md`.
`docs/REMAINING_WORK.md` is the *what* (status inventory); this is the sequence, the
verification gates, and exactly where the operator is in the loop.

**North stars this plan is optimized for:** (1) blast-radius safety — an agent must not be
able to damage the host by accident; (2) no dual-mode drift — every change stays green in
*both* native and Docker; (3) company-compatible — nothing forecloses the future
commercial/hosted model (repo stays private until a license is chosen).

---

## Quality bar (applied to every step)

- **A verification gate + its own commit per stage.** No stage is "done" on a worker's say-so;
  it's done when its named check passes. Default gate = `python tests/testBackendSmoke.py`
  **96+ OK in both runtimes** (native and `WRAPPER_RUNTIME=docker`), plus a targeted check for
  the stage's specific claim.
- **Design-then-review before any security-sensitive or hard-to-reverse change** (the §6.2
  network change, the run-as path). Same format as the Phase 3 options docs you reviewed.
- **Advisor pressure-test at each design juncture and before declaring a phase done** — catches
  the wrong-approach-before-building-on-it failures cheaply.
- **Frontend changes:** edit source in `frontend-src/`, `npm run build`, verify the built bundle;
  never hand-edit `frontend/`. No chat-layout restructures.
- **Never bulk-edit source with PowerShell Get/Set-Content** (UTF-8/BOM corruption) — Edit/Write
  or Python only. Scratch files to the session scratchpad, never the repo.
- **Fail closed, not open:** if a guard can't prove it's safe, it refuses and asks — it never
  silently proceeds.

---

## The shape

Five steps. Steps 1–2 need nothing from you and start immediately. Step 3 is the heart of
Phase 3 and now **auto-provisions** (one UAC click inside the app, no manual admin shell). Steps
4–5 finish hardening and productization. Your total involvement: **one consent click** and
**two decisions** (a §6.2 option, and eventually the company/licensing model).

Dependencies matter here: Step 3 (host-shell run-as) needs only Step 1 — it is **not** gated by
the §6.2 review, which is orthogonal skills-container networking. The §6.2 review gates only Step 4.

```
Step 1  Phase 3 account-independent ──► Step 3  Phase 3 run-as + auto-provision ──┐  (one UAC click in Step 3)
Step 2  §6.2 design note ──(you pick an option)───────────────────────────────────┤
                                                                                  ▼
                                                    Step 4  Phase 4 hardening (implements §6.2)
                                                                                  ▼
                                                    Step 5  Phase 5 productization
                                                            (company/licensing decision — gates public release only)
```

---

## Step 1 — Phase 3 account-independent items  ⚙️ *(start now, no blocker)*

These need no sandbox account, so they land while §6.2 is in design and before you provision.

- **3.6 Shell mechanics parity** — interpreter selection (PowerShell default, `cmd` selectable,
  honor an explicit interpreter in the command), minimal-env construction (`_safe_shell_env()` +
  needed toolchain PATH), output cap + archive-on-overflow (`MAX_SHELL_OUTPUT_CHARS`), matching
  the Linux path's guarantees.
- **3.7 Host git tools** — path forms, CRLF/UTF-8 as encountered; confirm `safe.directory` is a
  no-op natively.
- **3.8 Gating parity** — Trusted + approval behavior identical in native mode: audit rows written,
  revoke-mid-session actually blocks the next action, no-Host-Shell workspace refuses.

**Gate:** smoke 96+ OK in both runtimes; a native HTTP/E2E exercise of a real git + shell command
in a Host-Shell-off workspace refuses, and (temporarily, via the test's capability enable) runs.
Each of 3.6/3.7/3.8 commits separately.
 
---

## Step 2 — §6.2 skills-sandbox isolation — **design note only**  ⚙️→🔑 *(no blocker)*

`backend/core/sandbox.py:24` runs skill containers with `--network host` so they can reach the
loopback-bound wrapper API. I write a short options note covering the real trade-offs:

- isolated bridge network + `host.docker.internal` (+ `--add-host …:host-gateway` on Linux) vs a
  dedicated published port back to the wrapper;
- interaction with the loopback-only binding hardening (a service bound to `127.0.0.1` is *not*
  reachable via `host.docker.internal`);
- an optional egress allowlist for a package mirror.

**🔑 You review and pick an option.** No code touches the working skills path until then. Deferring
the *implementation* to Step 4 (while designing now) is deliberate: a wrong network edit silently
breaks all skills execution, so it goes behind an approved design + a gate.

---

## Step 3 — Phase 3 run-as + **auto-provision**  ⚙️ + one 🔑 click *(the heart of Phase 3)*

This is where commands actually start running as the low-privilege `Rasputin_sbx` account. The POC
already proved the hard part (manual pipe capture via ctypes; no pywin32). Built in this order so
each layer is verifiable:

- **3.3c-i — Auto-provision (elevation-on-demand).** On first Host Shell enable (and native-startup
  self-heal), the backend runs `Provision-Sandbox.ps1 -Status` (no elevation); if unprovisioned or
  broken, it raises **one** UAC prompt via `Start-Process -Verb RunAs` to create/repair the account
  + DPAPI credential + firewall. Idempotent/self-healing. **Credential-identity guard (matters for
  the company goal):** when the operator is a local admin — the common case, and true for this
  machine today — UAC elevates the *same* user, so the DPAPI-CurrentUser credential is decryptable by
  the unelevated backend. When the operator is a *standard* user, `-Verb RunAs` prompts for a
  *different* admin's credentials and the elevated script would encrypt the blob under that admin's
  profile, which the backend can't read. The provision script already records `ownerSid`, so the
  backend detects this SID mismatch and **fails closed** with a clear message ("sandbox credential
  belongs to a different Windows user — re-provision as the account that runs Rasputin") plus the
  documented `CreateProcessAsUser`/service fallback, rather than silently storing an undecryptable
  credential. Declining the UAC prompt likewise leaves Host Shell cleanly off, not half-broken.
- **3.3c-ii — Run-as executor** (`backend/core/sandbox_exec.py`): `CreateProcessWithLogonW`
  (ctypes/advapi32) with `CREATE_SUSPENDED`, assign to a Job Object
  (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` + active-process/memory caps), **start the pipe-drain
  threads, then `ResumeThread`** (POC-proven order — drain before resume avoids a full-buffer
  deadlock). `cwd` = workspace; minimal env. `shell_exec` routes through this when the workspace has
  Host Shell on.
- **3.3c-iii — Per-workspace ACL grant/revoke** (silent, no elevation — verified): on Host Shell
  enable, `icacls <ws> /grant Rasputin_sbx:(OI)(CI)M`; on disable/untrust/remove, `icacls … /remove`.
  Refuse to grant on a root that failed Phase-2 root-safety (defense in depth).
- **3.4 — Finalize network deny + job nesting** from the first real run's results (resolves §9-T5
  seclogon job-nesting and §9-T6 per-user firewall scoping); adjust `Provision-Sandbox.ps1` to match
  what the machine actually enforced, and update its honesty notes.
- **3.5 — Fail-closed boundary reporting**: detect Access-Denied / network-blocked in command output
  and surface "blocked: tried to act outside the workspace / reach the network → approve?" instead of
  a raw errno. Demote `SHELL_DENY_PATTERNS` from a boundary to a UX foot-gun hint (the account + ACL
  + Job Object are now the real boundary).

### Design-review refinements (advisor, 2026-07-12)

Baked into the build order above before writing the logon core:

- **Tree-kill does NOT depend on the Job Object.** `CreateProcessWithLogonW` creates the child via
  the seclogon service, so `AssignProcessToJobObject` on our handle is the single most likely thing
  to misbehave (§9-T5). Make Stage 3.1's proven `_kill_process_tree` (`taskkill /F /T /PID`) the
  **primary** timeout kill for the run-as path; `KILL_ON_JOB_CLOSE` is defense-in-depth. §9-T5 then
  degrades from "blocks the mechanism" to "belt we may find redundant."
- **Env block:** pass `CREATE_UNICODE_ENVIRONMENT` if handing a Unicode block, else **NULL** for v1
  so the sandbox account gets *its own* profile env (`LOGON_WITH_PROFILE`). Do NOT reuse the
  operator's `_safe_shell_env()` PATH — it points at the operator's per-user tool installs the
  sandbox account can't read. PATH/toolchain augmentation is a **first-run validation item**, not
  hard-coded now.
- **Sequencing (avoids rework):** the only unverifiable piece is `run_as_sandbox` itself. Build the
  rest first (credential guard, ACL wiring, `shell_exec` routing, fail-closed, cmdline building) —
  all unit-testable now. Then **provision once** (a single manual elevated `Provision-Sandbox.ps1`
  run is fine for dev — the auto-provision UX is NOT needed yet) to unblock writing `run_as_sandbox`
  against a real `Rasputin_sbx`. Build the auto-provision/UAC-from-backend UX (3.3c-i) **after** the
  executor works.
- **seclogon check — PASSED** on this machine (`Get-Service seclogon` → Running). Primary mechanism
  is alive; no forced `CreateProcessAsUser` fallback.
- **Command line:** `CreateProcessWithLogonW` takes one `lpCommandLine` string — build it with
  `subprocess.list2cmdline()` (correct Windows quoting), never a hand-join.
- **Async:** the inner `WaitForSingleObject` is the **sole** finite timeout for the run-as path
  (drop the outer `asyncio.wait_for` there — `to_thread` can't be cancelled, so a double timeout
  would strand the thread on a hung child). The auto-provision `Start-Process -Verb RunAs -Wait`
  also runs via `asyncio.to_thread`, and its API request needs a patient/long response (user is
  clicking UAC + account creation takes seconds).

**🔑 Your one action:** the single elevated provisioning run (manual once during the build, later a
one-click UAC prompt via the auto-provision UX). Everything else is silent.

**Gate (closes Phase 3):** on a trusted, Host-Shell-on native workspace — a `code`-mode task runs the
repo's real test suite under `Rasputin_sbx`; a timeout kills a child-spawning command's whole tree; a
write outside the workspace is denied and surfaced as an approval prompt, not a crash; a Host-Shell-off
workspace still refuses. Smoke 96+ OK both runtimes.

---

## Step 4 — Phase 4 sandbox hardening  ⚙️ *(implements Step 2's approved design)*

- Replace `--network host` with the option you approved; mark `THREAT_MODEL.md` §6.2 **RESOLVED**
  with the design recorded.
- Verify sandbox behaves identically native vs containerized.

**Gate:** no Rasputin-spawned container runs with host networking; a representative skill still
executes end-to-end in both runtimes; §6.2 flipped to RESOLVED.

---

## Step 5 — Phase 5 productization  ⚙️ + 🔑 *(the company track)*

- **Installer** (winget/MSI or equivalent): during install (already elevated) create the account +
  firewall; defer the DPAPI credential to first user-run (the installer may be SYSTEM, but the
  credential must be *yours*). This absorbs even the one UAC click into the install you already
  consented to.
- **Server SKU**: publish the wrapper image to GHCR + a reference compose (team install = two lines).
  This is also the natural paid/hosted monetization seam.
- **Version/update surfacing** in the UI.
- **🔑 Company/licensing decision** — *the only thing gating public distribution.* Goal is to build a
  company (not necessarily sell the software), so the model must preserve commercial viability:
  hosted/SaaS (AGPL core + paid hosting), open-core, source-available (BSL/Elastic 2.0/PolyForm), or
  dual-license — **not** a permissive OSS license a competitor could host/resell. A CLA becomes
  load-bearing if outside contributions are accepted. **Repo stays private until this is chosen** —
  that preserves every option. I can write a business-model options note (design-then-review) whenever
  you want it; nothing forces the decision until you're near release.

**Gate:** "install Rasputin" is one command/download on a workstation, two lines on a server — neither
mentions Docker Desktop.

---

## Open validation items (all resolve on the first real run in Step 3)

Why Step 3's provisioning was authored as a first pass, not a final one:

1. **§9-T5 — job-object nesting via seclogon.** `CreateProcessWithLogonW` routes through the
   secondary-logon service; confirm the tree is actually killed on timeout. Fallback if it fails:
   `CreateProcessAsUser` + batch logon (needs an elevated runtime — a documented alt path).
2. **§9-T6 — per-user firewall (WFP) egress scoping** holds on this build. Loopback is exempt by
   Windows design regardless; honest claim stays "external egress denied (if the rule holds); loopback
   open."
3. **Logon-rights hardening.** v1 touches logon rights zero (denying interactive logon would break
   `CreateProcessWithLogonW`); the correct hardening depends on which mechanism survives T5, so it's
   deferred until after the first run.

---

## Your involvement, consolidated

1. 🔑 Review the §6.2 design option (Step 2) — a reading + a choice.
2. 🔑 One UAC "Yes" the first time you enable Host Shell (Step 3).
3. 🔑 The company/licensing decision (Step 5) — latest possible; gates public release only.

Everything else is mine, each stage behind a verification gate and its own commit.

---

## Recommended start

Begin **Step 1** (account-independent Phase 3 work) and draft **Step 2** (§6.2 design) in parallel —
both need nothing from you. That keeps momentum until you're ready to enable Host Shell, at which
point Step 3's one-click provisioning takes over. I'll checkpoint with you at each 🔑 and at every
phase-closing gate.
