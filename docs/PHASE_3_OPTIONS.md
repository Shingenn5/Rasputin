# Phase 3 — Shell Isolation: Options to Choose From

*Decision document, 2026-07-11. Companion to [`PHASE_3_SHELL_ISOLATION_DESIGN.md`](PHASE_3_SHELL_ISOLATION_DESIGN.md)
(which details Option A). Same goal for all options: when the agent runs a command in a trusted
native workspace, an **accidental** destructive command (`rm -rf`, `Remove-Item C:\Windows\System32`)
must not damage anything outside the approved folder. They differ in **how** they enforce that, and
in what they cost.*

---

## The axes that actually differ

- **Boundary type** — an OS-/kernel-enforced *wall*, a softer OS *guardrail*, or *detect-and-recover*.
- **Out-of-workspace damage** — is a mistaken system-wide command *impossible*, *denied*, or *only
  recoverable after the fact*?
- **Network** — is egress actually isolated?
- **Native toolchain (G3)** — does the agent use *your real* `npm`/`python`/`git`/PowerShell, or an
  approximation?
- **Dependencies** — Docker/WSL2/Hyper-V/a local account/elevation?
- **Dev friction** — per-command latency, file-ownership papercuts, toolchain breakage.
- **Build effort.**

## At a glance

| Option | Boundary | Out-of-ws damage | Network | Real host toolchain | Extra dependency | Effort |
|---|---|---|---|---|---|---|
| **A. Dedicated low-priv account** | OS ACLs (guardrail) | **Access Denied** | External denied¹ | **Yes** | 1× elevated account setup | Very Hard |
| **B. Disposable container / WSL2** | Kernel/namespace (**wall**) | **Impossible** (not mounted) | **Fully isolated** | No (container's) | Docker Engine **or** WSL2 | Medium |
| **C. Same-user, Low Integrity** | Mandatory label (soft) | Blocked (writes) | External denied¹ | **Yes** | none (no account) | Hard |
| **D. Windows Sandbox (VM)** | VM (**wall**) | **Impossible** (VM) | Configurable | Re-provisioned each run | Win **Pro** + Hyper-V | Medium–Hard |
| **E. Approve + snapshot/rollback** | Human + recover | **Not prevented** (recover) | Not isolated | **Yes** | VSS / git | Medium |

¹ Loopback (`127.0.0.1`) is never blocked by Windows Firewall — "network denied" means *external* egress only.

---

## Option A — Dedicated low-privilege account  *(the current design; recommended default)*
**Mechanism.** Run `shell_exec` as a dedicated standard user `Rasputin_sbx`. Windows' default ACLs
already deny it write to system dirs, `Program Files`, the drive root, and *your other files*; the
only thing granted is an ACL entry on the approved workspace. Job Object kills the process tree on
timeout; a firewall rule denies external egress.

- **Protects:** everything outside the workspace, OS-enforced regardless of `cd`/absolute
  paths/`bash -c` — the property the deny-list can't give. Also: the sandbox account can't read
  Rasputin's own `auth.json`/`rasputin.db`/secrets.
- **Doesn't:** the workspace's own files (`rm -rf .` still deletes the project); loopback; a
  determined adversary (it's a guardrail, not a wall).
- **Strengths:** your *real* Windows toolchain (G3); **no Docker required** (G1/G5); OS-enforced.
- **Costs:** one-time **elevated** account provisioning; per-user toolchains need a read/execute grant;
  agent-created files are **owned by `Rasputin_sbx`** (your later `git` warns "dubious ownership");
  network-deny has caveats (loopback, per-user firewall scoping needs validation); depends on
  *Bypass Traverse Checking* being present (some corporate images strip it).
- **Pick when:** single-operator desktop, you want the native toolchain, and you don't want to force
  a Docker/WSL install. **This is the balanced default.**

## Option B — Disposable container / WSL2 per command  *(the hard-wall alternative)*
**Mechanism.** Each command runs in a throwaway `docker run --rm` (or a WSL2 invocation) with **only
the workspace bind-mounted** and `--network none`, killed after. Identical to what server mode and
Codex/Claude-Code-on-Linux already do.

- **Protects:** *everything* outside the workspace mount — a kernel/namespace **wall**, not a
  guardrail. Network is genuinely isolated (real namespace, no loopback caveat).
- **Doesn't:** the workspace's own files (it's mounted RW).
- **Strengths:** the **strongest** isolation here; proven; reuses the sandbox infra we already have;
  no per-machine account/ACL/firewall fiddling; no ownership papercut.
- **Costs:** **reintroduces a container dependency** on the workstation — the very thing native mode
  set out to avoid (Docker Engine/WSL2 are free but heavier than "just run the app"). The toolchain
  is the **container's/WSL's, not your native Windows one** (no `npm.exe`/PowerShell against Windows
  paths) — dents G3. Per-command **cold-start latency** (seconds). **Bind-mount I/O tax** — the exact
  cost Phase 0 fought. Windows↔Linux path/line-ending friction.
- **Pick when:** you want a real wall and accept a containerized toolchain — or as the **opt-in
  "hardened" tier** and for the server SKU (where it's already the plan).

## Option C — Same-user, Low-Integrity confinement  *(lightest; no account)*
**Mechanism.** Run the shell **as you**, but with a **Low-integrity token** and the workspace
**mandatory-labeled Low** so tools can write there. A Low-IL process cannot write to Medium-IL
objects — which is *your* Documents, Desktop, and normal files — so those are protected without a
second account. Job Object + firewall as in A.

- **Protects:** writes to your own files and system dirs (blocked by integrity level).
- **Doesn't:** *reads* aren't confined (IL restricts writes, not reads); loopback; and IL is an even
  **softer** boundary than the account model (MS explicitly: not a security boundary).
- **Strengths:** **no account provisioning, no elevation**; keeps your identity, PATH, **git
  credentials**, and toolchain exactly; **no ownership papercut** (files stay yours).
- **Costs:** **many dev tools misbehave at Low IL** (installers, some test runners, anything that
  expects Medium-IL writes) — the biggest practical risk; the workspace label management is fiddly;
  weakest boundary of the OS-enforced options.
- **Pick when:** account creation is unacceptable and you'll tolerate tool breakage for a lighter,
  identity-preserving setup. A reasonable *fallback default* if Q4 (account creation) is a "no."

## Option D — Windows Sandbox (disposable VM)
**Mechanism.** Launch each session in **Windows Sandbox** (a lightweight throwaway Hyper-V VM via a
`.wsb` config) with the workspace mapped in.

- **Protects:** everything — a real **VM wall**; discarded on close.
- **Doesn't:** the workspace's own files.
- **Strengths:** strongest single-machine isolation short of a full VM; nothing persists.
- **Costs:** needs **Windows Pro/Enterprise + Hyper-V** (collides with G5's "runs on any machine");
  **no persistence** across a session (installed deps vanish); **re-provision the toolchain every
  cold start**; slow spin-up — painful for an interactive agent loop.
- **Pick when:** rarely — a high-assurance one-off on a Pro machine. Not a fit for a
  continuous coding loop.

## Option E — No confinement, but approval + snapshot/rollback  *(different philosophy)*
**Mechanism.** Don't confine execution; instead **require a per-command preview/approval** and take a
**filesystem snapshot** (VSS or a workspace git-stash/copy) before mutating commands, so anything can
be rolled back.

- **Protects:** *recoverability* of the workspace; a human gate before each command.
- **Doesn't:** **prevent out-of-workspace damage at all** — `Remove-Item C:\Windows` still runs if
  approved/missed. Snapshots protect the workspace, not `System32`. This **fails the core goal** for
  system-wide damage.
- **Strengths:** trivial dependencies; keeps everything native; good in-workspace undo.
- **Costs:** relies on human vigilance for the dangerous case (exactly what an autonomous loop
  erodes); VSS needs admin; snapshots are heavy for large trees.
- **Pick when:** as a **complement** to A/B/C (nice in-workspace undo), never as the sole boundary.

---

## Recommendation — tiered, not either/or

The plan already anticipates this: **native = Option A, server = Option B, hardened opt-in = Option B.**
Concretely:

1. **Default = Option A** (dedicated account). Best balance of a real OS-enforced boundary and your
   real toolchain with no forced Docker.
2. **Ship Option B as the opt-in `RASPUTIN_SHELL_SANDBOX=container|wsl2` tier** — for anyone who wants
   a hard wall, and automatically required on machines where Q4 is "no" (no local account / stripped
   traverse privilege). It's low marginal effort because server mode builds it anyway.
3. **If account creation is a hard "no" for your primary machine**, make **Option C** the native
   default instead of A, accepting the tool-breakage risk — and keep B as the hard tier.
4. **Option E's snapshot/undo** is worth adding on top of whichever wins, purely for in-workspace
   "oops" recovery. **Option D** we keep on the shelf.

**Stage 3.1 is shared by A, C, and E** — Job-Object process-tree kill + minimal env + output caps
have no account/container plumbing and fix today's orphaned-children bug immediately. So we can start
there regardless of which boundary you choose, and the boundary decision (A vs B vs C) only gates
Stages 3.3+.

## What I need from you
Rank/choose among: **A (account, recommended)**, **B (container hard-wall)**, **C (same-user Low-IL,
no account)** as the *native default* — and whether to build **B as the opt-in hard tier** alongside
it. Everything else (Q1–Q3 in the design doc) is downstream of that.
