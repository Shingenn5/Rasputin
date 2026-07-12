# Rasputin — Remaining Work Report

*Snapshot: 2026-07-11 · branch `codex/agentic-coding-loop-v1`*

This is a status report of what's left on the dual-mode architecture plan
(`docs/DUAL_MODE_ARCHITECTURE_PLAN.md`), not a new plan. It rolls up the open
checkboxes across Phases 3–5 plus the deferred items, with the current blocker
called out.

---

## Where we are

- **Phases 0, 1, 2 — COMPLETE.** Data layer off the bind mount (named volume +
  `%LOCALAPPDATA%` native default + `migrate-data`); native launch is first-class
  (`rasputin.ps1 start -Native`); native workspaces register directly (pick → approve →
  working, no mounts/restarts). Verified: smoke 96 OK in both runtimes, native HTTP E2E,
  Playwright.
- **Phase 3 (host-toolchain shell) — IN PROGRESS, paused at one checkpoint.**
  - Stage 3.1 process-tree kill on timeout — **done** (`38f34b6`).
  - Stage 3.2 capability split (`allow_host_shell` separate from Trusted Dev Mode) —
    **done** (`3b9d580`).
  - Stage 3.3 sandbox account + run-as — **authored, not yet run** (`e420802`).
- **Phases 4, 5 — not started** (Phase 4's capability-split item was pulled forward into
  Stage 3.2 and is done).

**The single blocker right now:** Stage 3.3 needs a one-time *elevated* run of
`scripts/Provision-Sandbox.ps1` on your machine (creates the `Rasputin_sbx` account +
firewall rule + stored credential). Everything downstream in Phase 3 waits on that. It is
paused by your choice, not stuck.

---

## Phase 3 — Host-toolchain shell (the active phase)

| # | Item | Status | Effort | Blocked on |
|---|------|--------|--------|------------|
| 3.3b | **Run `Provision-Sandbox.ps1` elevated** — create/repair `Rasputin_sbx`, store DPAPI credential, install best-effort egress block | Script ready; **not run** | You: 1 elevated run | **You** |
| 3.3c | `backend/core/sandbox_exec.py` — run commands as the sandbox account via `CreateProcessWithLogonW` + Job Object + hand-rolled pipe pump (POC-proven); wire `icacls` ACL grant/remove into the Host Shell enable/disable toggle | Not started | Very Hard | 3.3b |
| 3.4 | Validate + finalize network egress deny (per-user WFP scoping, §9-T6) and job-object nesting through seclogon (§9-T5); adjust the provision script based on first-run results | Not started | Hard | 3.3b |
| 3.5 | Boundary violations **fail closed** into an approval prompt (detect Access-Denied / network-blocked in output); demote `SHELL_DENY_PATTERNS` from a boundary to a UX hint; git-as-sandbox review | Not started | Hard | 3.3c |
| 3.6 | Shell mechanics parity: interpreter selection (PowerShell vs `cmd`), minimal-env construction, output caps + archive-on-overflow — same guarantees as the Linux path | Not started (3.1 did the kill half) | Hard | — |
| 3.7 | Git tools against host git (path forms, CRLF/UTF-8 as encountered; `safe.directory` not needed natively) | Not started | Easy | — |
| 3.8 | Verify Trusted-workspace + approval gating is identical in native mode (audit rows, revoke-mid-session) | Not started | Medium | — |
| 3.9 | Test: timeout kills a child-spawning command cleanly on Windows; output cap + archive works; untrusted/no-Host-Shell workspace still refuses | Not started | Hard to verify well | 3.3c |

**Definition of done:** a `code`-mode task in a trusted native workspace runs the repo's
real test suite with your real toolchain — the coding-agent Stage 6 loop gets the host
machine.

**Note:** 3.6/3.7/3.8 do **not** need the sandbox account and could proceed independently
of the provisioning checkpoint if you want Phase-3 progress without the elevated step.

---

## Phase 4 — Sandbox hardening

| Item | Status | Effort |
|------|--------|--------|
| **§6.2 — Skills sandbox network isolation.** Replace `--network host` (`backend/core/sandbox.py:24`) with an isolated bridge + explicit allowlist so a skill container can't reach the whole host network; mark THREAT_MODEL §6.2 RESOLVED | Open — **needs a design pass first** (loopback-bound wrapper vs `host.docker.internal` + published port; Docker Desktop vs Linux `host-gateway` differ; a wrong edit silently breaks all skills) | Medium |
| Capability split (`allow_host_shell` ≠ `trusted`) | **DONE early** in Stage 3.2 | — |
| Sandbox behaves identically whether the wrapper is native or containerized | Open | Medium |
| Watch item (not a commitment): Docker Sandboxes (`sbx`) microVM for skills isolation once its beta stabilizes | Deferred | env-blocked |

**Definition of done:** no Rasputin-spawned container runs with host networking.

---

## Phase 5 — Packaging & distribution

*Only meaningful after Phases 1–3; details deliberately thin until then.*

| Item | Status | Effort |
|------|--------|--------|
| Single-artifact workstation install (winget/MSI or equivalent; tray/auto-start optional) | Open | Hard |
| Server mode: publish the wrapper image to GHCR + reference compose (team SKU = two-line compose) | Open | Medium |
| Update channel / version surfacing in the UI | Open | Medium |
| **LICENSE + CLA decision** — repo is private with no license. Goal is to turn Rasputin into a **company** (not necessarily sell the software itself), so the model must preserve commercial viability — a permissive OSS license (MIT/Apache/BSD) that lets a competitor host/resell it is the thing to avoid. Viable: **hosted/SaaS** (core could be AGPL + paid managed hosting), **open-core**, **source-available** (BSL / Elastic 2.0 / PolyForm), or **dual-license**. A CLA becomes load-bearing if outside contributions are accepted. Prerequisite before any public distribution, not a current exposure | Open — **business decision, not code; blocking for distribution only** | Decision |

**Definition of done:** "install Rasputin" is one command/download on a workstation, two
lines on a server — and neither mentions Docker Desktop.

---

## Open validation items (all resolve on the first elevated provisioning run)

These are why Stage 3.3 was authored as a deliberate *first pass* rather than a final one —
each can only be settled by running on a real machine:

1. **§9-T5 — Job-object nesting via seclogon.** `CreateProcessWithLogonW` routes through the
   secondary-logon service; the child may land in a pre-existing job. Nested jobs are fine on
   Win8+, but confirm the process tree is actually killed on timeout. Fallback if it fails:
   `CreateProcessAsUser` + batch logon (needs an elevated runtime).
2. **§9-T6 — Per-user firewall (WFP) egress scoping.** Whether the SID-scoped outbound block
   holds on this build. Loopback (`127.0.0.1`/`::1`) is exempt by Windows design regardless, so
   the honest claim is "external egress denied (if the rule holds); loopback open," not "no
   network."
3. **Logon-rights hardening.** v1 touches logon rights zero (denying interactive logon would
   break `CreateProcessWithLogonW`). The correct hardening depends on which run-as mechanism
   survives T5, so it's deferred until after the first run.

---

## Deferred / explicitly deprioritized

- **Docker mount-approve auto-register.** Approving a *ready* pending mount already
  auto-registers the workspace; the residual gap is only that Docker's flow stays two-step
  (mount-apply → restart → approve). The plan itself tags this "a Docker-mode UX nicety, not a
  bug… not worth destabilizing the mount subsystem now."

---

## Recommended sequence from here

1. **Safe, no blocker:** a short §6.2 resolution options note (design-then-review, like the
   Phase 3 options doc) — closes the last open security item on the plan without touching the
   working skills path yet. *Or* knock out Phase 3's account-independent items (3.6 shell
   mechanics, 3.7 git tools, 3.8 gating parity).
2. **When you're ready for the elevated step:** run `Provision-Sandbox.ps1` as yourself → I
   verify the account/credential/firewall and build 3.3c (run-as integration) + 3.4 validation
   against the real account. This unblocks the rest of Phase 3.
3. **Then:** Phase 3.5 fail-closed reporting → Phase 4 §6.2 → Phase 5 packaging, with the
   LICENSE/CLA decision resolved before any public distribution.
