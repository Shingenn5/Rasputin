# Phase 3 Design — Host-Toolchain Sandboxed Shell

*Drafted for operator review, 2026-07-11 (Claude Fable 5); retained as the historical design record
for the "Execution isolation model" in
[`DUAL_MODE_ARCHITECTURE_PLAN.md`](DUAL_MODE_ARCHITECTURE_PLAN.md). The core shipped 2026-07-12:
`Rasputin_sbx` run-as, workspace ACL grant/revoke, primary `taskkill /F /T`, Job Object
defense-in-depth, and on-demand provisioning. Implementation deliberately differs from this draft
in three places: no per-command confirmation, git tools stay direct backend children, and overflow
is truncated rather than archived. External-egress denial is best-effort with loopback open.*

---

## 1. What we are protecting against (and what we are not)

**The threat is an accidental destructive command from an automated model** running the operator's
real toolchain in a trusted native workspace — the "`rm -rf` / `Remove-Item C:\Windows\System32`"
class. The goal:

> A mistaken command can freely do whatever it wants **inside the approved workspace**, but
> anything it touches **outside** that folder — system files, Program Files, the operator's other
> projects and documents, the network — **fails with Access Denied**, by construction, not by a
> filter guessing which commands are bad.

**Non-goals (stated plainly):**
- This is a **strong guardrail against mistakes, not an airtight wall against a determined human
  adversary.** Microsoft does not treat account/integrity boundaries as a security boundary against
  local privilege escalation. That's the right trade for a single-operator desktop tool whose real
  threat is fumble-fingers.
- It does **not** protect the workspace's own contents: `rm -rf .` inside the approved folder still
  deletes the project. Mitigation is git + backups, not isolation.
- For a VM-grade wall, the **opt-in container/WSL2 path** (§8) exists.

---

## 2. Why this works on Windows — the load-bearing insight

Today `shell_exec` runs as the operator, so it can write anything the operator can. The fix is to
**run it as a different, low-privilege local account.** Windows' *default* ACLs then do most of the
work for free — a standard (non-admin) account that does not own a resource cannot:

- write to `C:\Windows`, `System32`, `C:\Program Files(*)`, or the drive root `C:\` (admin/TrustedInstaller only);
- read or write **another user's profile** — `C:\Users\<operator>` grants SYSTEM, Administrators,
  and the operator; the generic *Users* group has no access. So the operator's Documents, Desktop,
  and other projects are invisible and untouchable to the sandbox account.

So `Remove-Item C:\Windows\System32 -Recurse -Force` run as the sandbox account returns **Access
Denied** with **no custom rules** — and critically, this holds regardless of `cd`, absolute paths,
symlinks, or indirection through `bash -c`/`python -c`. That is exactly the property the lexical
deny-list could never provide. The deny-list becomes a UX nicety, never the boundary.

The **only** thing we must explicitly grant is the workspace itself.

**Two Windows specifics that make or break this:**
- The sandbox account can open `C:\Users\<operator>\projects\myapp` *despite* having no rights on the
  intermediate `C:\Users\<operator>` only because **Bypass Traverse Checking**
  (`SeChangeNotifyPrivilege`) is granted to *Everyone* by default — that lets a process reach a deep
  path without permissions on the parents. If T1 (write-inside-workspace) ever fails inexplicably,
  check this first, not the ACE syntax. Some locked-down corporate images **strip** this privilege,
  which breaks the whole model there (see Q4).
- **Bonus the account model buys us:** Rasputin's own data (`%LOCALAPPDATA%\Rasputin` — `auth.json`,
  `rasputin.db`, model secrets) lives in the operator's profile, so the sandbox account **cannot read
  it** — a sandboxed shell can't reach the app's own credentials or DB, which running as the operator
  could. Phase-2 root-safety already refuses to approve that dir as a workspace, so the two guards
  compose.

---

## 3. Components

### 3.1 The sandbox account
- A dedicated local standard user, e.g. **`Rasputin_sbx`**, created once at install/first-run
  (requires elevation that one time).
- Random 32+ char password, stored in **Windows Credential Manager** protected by **the operator's
  DPAPI** (not per-machine DPAPI, which any local account could decrypt), never on disk in cleartext,
  never logged.
- Denied interactive/RDP logon rights (`SeDenyInteractiveLogonRight`, `SeDenyRemoteInteractiveLogonRight`);
  used only programmatically.
- A helper (`rasputin.ps1 provision-sandbox`, elevated) creates/repairs the account, sets the
  password, stores it, and applies the deny-logon rights. Idempotent; re-runnable to self-heal.

### 3.2 Workspace ACL grant (the one hole we open)
- When a workspace is switched to **host-shell-enabled** (see §3.7), add an inherited ACE granting
  `Rasputin_sbx` **Modify** on that folder tree (`icacls <ws> /grant Rasputin_sbx:(OI)(CI)M`).
- On disable/untrust/remove, **remove the ACE** (`icacls <ws> /remove Rasputin_sbx`).
- Because ACEs inherit down but not up, the sandbox account reaches the workspace subtree and
  nothing above or beside it (not `C:\Users\<operator>`, not sibling projects).
- Refuse to grant on a root that failed the Phase-2 root-safety check (defense in depth — it already
  can't be a workspace, but assert it here too).

### 3.3 Running the command as the sandbox account
- Primary mechanism: **`CreateProcessWithLogonW`** (pywin32 `win32process.CreateProcessWithLogonW`)
  with the stored credentials. Works **without** elevating the wrapper at runtime — the elevation
  cost is paid once at provisioning.
- **Always spawn with `CREATE_SUSPENDED`, assign the process to the Job Object (§3.4), *then*
  resume.** Without this, a fast command spawns children before the job is attached and they escape
  kill-on-close — the exact orphan bug Stage 3.1 exists to fix. This applies to the primary path, not
  just the alternative.
- `cwd` = the workspace; env = minimal safe set (§3.6).
- Alternative if we accept an elevated wrapper: `LogonUser` → `CreateProcessAsUser` with
  `CREATE_SUSPENDED`, which gives cleaner Job-Object attachment. **Decision needed** (§10-Q1).

### 3.4 Job Object — process-tree kill + resource caps
- Wrap the child in a **Job Object** (`win32job`) with
  `JOBOBJECT_EXTENDED_LIMIT_INFORMATION.LimitFlags |= JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
- On timeout **or** normal completion, closing the job handle kills the **entire tree** — fixes
  today's bug where `proc.kill()` orphans children on Windows (THREAT/Finding-2).
- Also set: active-process cap, job memory cap, and optionally `JOB_OBJECT_UILIMIT_*` to block the
  sandboxed process from messing with the operator's desktop/clipboard.
- Validation risk: `CreateProcessWithLogonW` routes through the seclogon service and the child may
  land in a pre-existing job; nested jobs are fine on Win8+, but this needs an explicit test
  (§9-T5). If nesting fails, fall back to the `CreateProcessAsUser` + suspended path (§3.3 alt).

### 3.5 Network deny-by-default
- A mistaken `curl … | sh`, a typosquatted `pip install`, or workspace exfiltration are "fallout"
  too, stopped only by denying egress. Mechanism: a **Windows Firewall outbound-block rule scoped to
  the sandbox account's SID** (WFP user-ID condition), created at provisioning, with an
  **env-configurable allowlist** (`RASPUTIN_SANDBOX_ALLOWED_HOSTS`) for e.g. a local package mirror.
- **Known hole — loopback is not blocked.** Windows exempts `127.0.0.1`/`::1` from the WFP ALE
  layers, so even with the block active the sandbox account can still reach **local** services (the
  wrapper's own API, local model servers). Fine for the accidental-fallout threat, but it means the
  honest claim is **"external egress denied; loopback not blocked,"** not "no network."
- **Honesty flag:** per-process/per-user firewall scoping via WFP needs validation (§9-T6). If it
  proves unreliable, the clean answer for hard network isolation is the container/WSL2 path (§8);
  network-deny would then be "best-effort on native, guaranteed in the sandboxed-runtime opt-in."

### 3.6 Shell selection, minimal env, output caps (*mechanics* parity with the Linux path)
*Parity here means env/caps/timeout mechanics — not isolation. The native isolation is deliberately a
guardrail (§1), weaker than the container wall.*
- Shell: PowerShell by default on Windows, `cmd` selectable; honor an explicit interpreter in the
  command. Same output cap + archive-on-overflow as today (`MAX_SHELL_OUTPUT_CHARS`).
- Env: reuse `_safe_shell_env()`, plus the toolchain PATH entries the sandbox account needs (§7).
- These are testable **independently of the account** and ship first (Stage 3.1).

### 3.7 Capability split — `allow_host_shell` distinct from `trusted`
- Problem at design time: one `trusted` flag both auto-approved file edits **and** unlocked `shell_exec`. So
  "stop nagging me about edits" silently means "run unattended host shell."
- New per-workspace boolean **`allow_host_shell`**, separate from `trusted`:
  - `trusted` → auto-approve file *edits* (unchanged).
  - `allow_host_shell` → permit host command execution in this workspace.
- `shell_exec` (native) requires **all** of: global `allow_shell_execution`, the workspace's
  `allow_host_shell`, **and** a per-exec confirmation (or an explicit "unattended in this workspace"
  the operator turned on, shown with a stronger warning than the edit-trust toggle).
- UI: a second toggle in the workspace header ("Host Shell"), with copy that names the real stake —
  "runs commands on your actual machine as a confined sandbox account; a mistake can still delete
  this project's files." Enabling it is what applies the §3.2 ACL grant.

### 3.8 Git tools
- The git tools (`git_status/diff/add/commit/…`) run as the sandbox account too, for a consistent
  boundary. Consequence (a feature, not a bug): git runs with the **sandbox account's** identity,
  not the operator's, so `git push` / remote ops have no operator credentials — leaving-the-machine
  actions stay gated, matching the isolation model. Local ops work via a workspace-scoped identity;
  set `safe.directory` for the sandbox account on the workspace. **Decision needed** (§10-Q2):
  sandbox git vs. keep git tools as the operator (they're already arg-vector + approval-gated).

---

## 4. Fail-closed, precisely
There is no "approve this specific escape" for shell — that would defeat the boundary. The model is:
- **Gate** (before running): `allow_host_shell` + per-exec confirm. This is where human judgment lives.
- **Boundary** (during): ACLs + Job Object + firewall. A command that hits it **fails closed** with
  the OS error; we detect Access-Denied / network-blocked patterns in the output and surface a clear
  "blocked: tried to act outside the workspace / reach the network" message instead of a raw errno.
- The lexical deny-list only fires *before* spawning, as a friendly "are you sure?" on obvious
  foot-guns — demoted from boundary to hint.

---

## 5. Alternatives considered and rejected
- **Restricted token of the operator (`CreateRestrictedToken`, deny-only SIDs):** keeps the
  operator's toolchain/PATH intact, but also keeps the operator's SID — so it can still delete the
  operator's *own* files. Fails the core requirement. Rejected.
- **AppContainer / low-integrity:** strong isolation but breaks most real toolchains (per-capability
  brokered access) and is not a security boundary per MS. Rejected for the default path.
- **Windows Sandbox (disposable VM):** a real wall, but needs Win Pro + Hyper-V (collides with G5's
  "runs on any machine"), doesn't persist across a session, and re-provisions the toolchain each cold
  start. Kept only as inspiration for the opt-in path. Rejected as default.
- **Perfecting `SHELL_DENY_PATTERNS`:** unwinnable over a Turing-complete shell; the code already
  concedes it "is not a security boundary." Rejected as the boundary.

---

## 6. Server (Docker Engine) mode
Unchanged from the isolation model: `shell_exec` runs in a **disposable workspace-only container
with no host networking** — a hard wall, the same model Codex/Claude Code use on Linux. Native's
account/ACL model and server's container model are the two supported boundaries.

## 7. Toolchain provisioning (the main UX cost — surface it)
- **Machine-wide installs** (Node/Python/git in `Program Files`, on the system PATH) are readable +
  executable by the sandbox account automatically. Nothing to do.
- **Per-user toolchains** (nvm-windows, a user-local venv under the operator's profile) are **not**
  visible to the sandbox account. At setup, grant the sandbox account **read/execute** on the
  specific toolchain dirs the operator names (`provision-sandbox -ToolchainPaths …`), or document
  that per-user toolchains must be made machine-wide. This is the honest cost of a dedicated account.
- **Ownership papercut (a real day-to-day cost):** files the sandboxed shell creates in the workspace
  are **owned by `Rasputin_sbx`**, not the operator. The operator can still open them (they own the
  dir / are admin), but their *own* later `git` will warn "detected dubious ownership," and some
  editors show permission friction on agent-created files. Mitigate by setting the workspace's default
  (inheritable) ACL so new files also grant the operator full control, and by documenting
  `safe.directory` for **both** identities. Weigh this against Q2 (git-as-sandbox vs git-as-operator).

## 8. Opt-in hardened native
Operators who want a VM-grade wall (or reliable network isolation) can flip
`RASPUTIN_SHELL_SANDBOX=container|wsl2` to run the shell in a disposable container / WSL2 namespace
instead of the account model. Offered, not required, so G5 (no forced Docker Desktop) holds for
everyone else.

---

## 9. Verification / test matrix (must all pass before Phase 3 is "done")
- **T1** write inside workspace → succeeds.
- **T2** `Remove-Item C:\Windows\System32 -Recurse -Force`, `del /s /q C:\`, write to
  `C:\Users\<operator>\Documents\x` → **Access Denied** (each, as the sandbox account).
- **T3** absolute path, `cd ..\..`, symlink-out, `bash -c "rm -rf /c/Windows"`, `python -c` file
  write outside → all **denied** (proves the boundary isn't lexical).
- **T4** read of operator's other profile files → denied; read of workspace files → allowed.
- **T5** timeout on a child-spawning command (`start /b` loop, a forking test runner) → Job Object
  kills the whole tree, **no orphans** (verify with a process snapshot).
- **T6** outbound `curl https://example.com` as sandbox account → blocked; allowlisted host → allowed.
- **T7** `allow_host_shell` off (but `trusted` on) → shell **refused**; on → allowed after per-exec confirm.
- **T8** output cap + archive path; untrusted workspace refuses.
- **T9** Docker/server path unchanged (regression); backend smoke green in both runtimes.
- **T10** revoke host-shell → ACE removed, subsequent write inside workspace by sandbox account denied.

## 10. Open questions / decisions needed from you
- **Q1 — runtime privilege:** primary `CreateProcessWithLogonW` (no runtime elevation, trickier job
  attach) vs. `CreateProcessAsUser` (clean job control, needs an elevated wrapper or specific
  privileges)? Recommend **CreateProcessWithLogonW** to keep the wrapper unelevated at runtime.
- **Q2 — git identity:** run git tools as the sandbox account (consistent boundary, no operator push
  creds) or keep them as the operator (already arg-vector + approval-gated)? Recommend **sandbox
  account** for consistency, with local git identity configured.
- **Q3 — network default:** ship native network-deny via the firewall rule as default-on, or
  default-off with the container opt-in as the "hard" answer, pending the WFP validation (T6)?
- **Q4 — provisioning UX (the decision that shapes the default):** a one-time elevated
  `provision-sandbox` at install is required to create the account. Acceptable on your machines? If
  creating a local user is disallowed anywhere (locked-down corporate — also the images most likely to
  have **stripped Bypass Traverse Checking**, §2, which would break the account model regardless), the
  container/WSL2 path stops being an opt-in and becomes **required** for those, reshaping the default.
  A "no-account" fallback would be container-only or simply refuse host shell there.

## 11. Staged implementation (each stage independently shippable + testable)
1. **3.1 Mechanics parity** — Job-Object process-tree kill, minimal env, output caps, shell
   selection. No account yet; fixes the orphaned-children bug immediately. (T5, T8)
2. **3.2 Capability split** — `allow_host_shell` flag + UI toggle + per-exec confirm, gating
   `shell_exec`. (T7)
3. **3.3 Sandbox account + ACL provisioning** — `provision-sandbox`, run-as, workspace ACE on
   enable / removal on disable. The core boundary. (T1–T4, T10)
4. **3.4 Network deny** — firewall rule + allowlist, pending WFP validation. (T6)
5. **3.5 Fail-closed reporting + deny-list demotion + git-as-sandbox.** (T2/T3 messaging, T9)

Ordering rationale: 3.1 is a pure win with no account plumbing; 3.2 makes the dangerous capability
explicit before we make it powerful; 3.3 is the boundary; 3.4/3.5 harden. We do **not** point the
coding agent at host shell until 3.1–3.3 pass their tests.
