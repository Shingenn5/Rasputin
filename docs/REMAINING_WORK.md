# Rasputin — Remaining Work Report

*Snapshot refreshed 2026-07-13 · dual-mode/security core through Phase 4 is complete*

This is the current status roll-up for the dual-mode and security work. The sandbox-account and
Phase-4 network work have shipped; only residual caveats and productization work remain.

---

## Where we are

- **Phases 0–2 — COMPLETE.** Runtime state uses the Docker named volume or native
  `%LOCALAPPDATA%`; native launch is first-class; native workspaces register directly with no
  mount request/restart. Docker mode keeps its compose mount-request flow.
- **Phase 3 security core — COMPLETE.** Native Windows Host Shell runs as the dedicated standard
  user `Rasputin_sbx` through `CreateProcessWithLogonW`, with an explicit workspace ACL, bounded
  output, process-tree timeout handling, and a Job Object as defense-in-depth. First enable can
  auto-provision with one UAC prompt; missing or cross-user credentials fail closed. Trusted Dev
  Mode and Host Shell are separate capabilities.
- **Phase 4 — COMPLETE.** Skill containers use `--network none` and reach host tools only over a
  private stdio RPC. `THREAT_MODEL.md` §6.2 is RESOLVED.
- **Phase 5 — OPEN / eventual.** Single-artifact workstation packaging, a published server image,
  update/version UX, and the licensing/company decision have not started.

The dual-mode security work has **no active provisioning blocker**. Phase 5 remains intentionally
behind daily-driver polish.

---

## Completed Phase 3 — Host-toolchain shell

| Item | Current implementation / evidence |
|---|---|
| Process-tree timeout | `taskkill /F /T` is primary on Windows; Job Object kill-on-close is defense-in-depth (`38f34b6`, `fdd6bc8`). |
| Capability split | `allow_host_shell` is independent of Trusted Dev Mode; the global `allow_shell_execution` flag is still required (`3b9d580`). |
| Sandbox account + run-as | `Rasputin_sbx` execution, output/exit capture, interpreter handling, cap/truncation, and timeout verified against a real account (`fdd6bc8`). |
| Workspace boundary | Host Shell enable/revoke grants/removes the inherited Modify ACL; absent provisioning fails closed (`42e68a8`). |
| Provisioning + reporting | First enable can raise one UAC prompt; SID/DPAPI mismatch is rejected; Access Denied results are labeled as sandbox-boundary failures (`2352dad`). |
| Gating tests | Smoke covers global permission, Trusted-vs-Host-Shell separation, revoke-mid-session, deny-pattern precheck, and unprovisioned fail-closed behavior. The live-account run-as test skips on machines without the account. |

This completion means the native-Windows shell no longer runs as the operator. It does **not**
mean every execution surface uses `Rasputin_sbx`: git tools are direct backend children, and
Docker/native-non-Windows shell execution follows the direct backend path described in
`THREAT_MODEL.md` §5.

---

## Completed Phase 4 — Skills sandbox network isolation

The selected sandbox-network design shipped in `5742cd6`:

- each Skill runs in a fresh `docker run -i --rm --network none` container;
- the old HTTP callback was replaced by newline-delimited JSON over private stdio;
- skill stdout is separated from RPC framing, stderr remains observable as logs;
- multi-call round-trips, a large (>64KB) result, and blocked outbound access were verified.

The residual surface is explicit: the host side still dispatches the Skill's requested tools with
the backend's authority. Permission checks still apply, and native-Windows `shell_exec` is itself
sandboxed, but Skill tool IDs are not separately allowlisted. The old HTTP callback route/token is
unreachable dead code and can be removed in routine cleanup.

---

## Residual caveats (not Phase 3/4 blockers)

1. **Native account isolation is an accident-containment guardrail, not an airtight security
   boundary.** `Rasputin_sbx` can modify the explicitly granted workspace. Git remains the recovery
   mechanism for destructive in-workspace mistakes.
2. **Native external-egress blocking is best-effort.** The SID-scoped Windows Firewall rule can
   fail to install and deliberately leaves loopback reachable. Do not summarize it as “no network.”
3. **Job Object assignment is defense-in-depth.** The seclogon-created process may not join it;
   the verified primary timeout path is `taskkill /F /T`.
4. **Per-user toolchains may be unavailable to `Rasputin_sbx`.** Machine-wide tools are the reliable
   path; user-profile installs may need explicit ACL/PATH work.
5. **Docker shell is not per-exec disposable.** It runs as a child inside the long-lived wrapper
   container, which retains its mounted workspaces and normal bridge network.
6. **Output overflow is truncated, not archived.** The current 20,000-character cap preserves
   bounded execution; an archive-on-overflow UX remains an optional product enhancement.

---

## Phase 5 — Packaging & distribution (remaining)

| Item | Status |
|---|---|
| Single-artifact workstation install (winget/MSI or equivalent; tray/auto-start optional) | Open |
| Publish wrapper image to GHCR + reference Docker Engine compose | Open |
| Update channel / version surfacing in the UI | Open |
| LICENSE/company model + CLA decision before public distribution | Open — business decision; repo remains private |

Phase 5 is not a prerequisite for local development or the current GUI/daily-driver work. It is
the eventual productization track.

---

## Deferred / explicitly deprioritized

- **Docker mount-approve auto-register.** Docker's flow remains mount apply → restart → approve.
  This is a UX improvement, not a native-mode or security-core blocker.
- **VM-grade hardened native shell.** WSL2/VM/container-backed Host Shell is not implemented. It is
  an optional future mode for operators whose threat model exceeds the low-privilege-account
  guardrail.
- **Docker Sandboxes (`sbx`) microVM watch item.** Deferred until the product/licensing/runtime
  trade-offs justify it.

## Recommended sequence from here

Use `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` for current UI/agent work. Return to this track
only for a specific residual hardening item or Phase-5 packaging; do not redo Phases 0–4.
