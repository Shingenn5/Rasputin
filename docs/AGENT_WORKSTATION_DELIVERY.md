# Agent workstation delivery

## Target

Rasputin combines local model download/serving, governed coding tasks, restricted
command execution, reviewable changes, and local training in its installed Windows
application. A user should complete these workflows without a source checkout or
separately installing developer tools. Existing approvals, owner/workspace access,
audit history, and model privacy policy remain part of every workflow.

## Source inspection and evidence — 2026-10-30

The checkout already contains model lifecycle UI, streaming agent tool loops,
workspace capabilities, approval handling, task worktrees, diffs, configured
validation commands, and LoRA training/preflight/adapter-export code. Their presence
does not certify the installed application or a full coding/training workflow.
Native Host Shell and the automatic workspace-validation loop remain disabled.
Explicit snapshot execution now has an experimental authenticated API and task-bound
agent tools; these require an administrator-pinned self-contained executable.

`backend/core/windows_sandbox.py` supplies the low-level AppContainer boundary.
`backend/core/sandbox_execution.py` supplies authorization, snapshot admission, and
owner-scoped durable receipts. The low-level runner still reports
`production_ready: false`: the installed toolchain and complete workflow are not
certified. A low-level runner call is never an execution authorization.

The probe creates a unique temporary AppContainer profile with no network
capabilities, a disposable directory, and a copy of a trusted self-contained
executable. The workspace receives a profile-specific modify ACL and low-integrity
label; the separate toolchain receives read/execute access. The lease directory
remains host-only. No source checkout or application data is mounted. The child
receives an explicit environment and inherited-handle list. A process-creation
job attribute attaches the Windows job atomically, closing the orphaned suspended
process window if the backend dies during launch. The job defaults to aggregate
memory of 1 GiB and 16 active processes, kills processes
on owner-handle closure, and is terminated on completion, timeout, cancellation,
or output overflow. Output is bounded; cleanup waits for the job to empty.

The standard AppContainer boundary still allows access to OS resources granted to
ALL APPLICATION PACKAGES and creates private profile storage. It is not a claim
that absolutely all filesystem reads outside scratch are impossible. LPAC was
investigated but prevented the local Node fixture from initializing Winsock; the
committed probe explicitly uses standard AppContainer, with no runtime downgrade.

Ten actual Windows integration tests passed with the local Node toolchain:

- Write two fixture files, observe a failing check, repair the implementation,
  and observe a passing check, entirely inside scratch.
- Reject reads and writes to an unrelated sentinel and omit a host environment
  secret; the original sentinel remains unchanged.
- Reject external TCP access with a permission error. A loopback connection cannot
  reach a controlled listening endpoint which a host control can reach. Windows
  reports a socket timeout for that loopback denial on this workstation.
- Terminate on timeout, cancellation, and output overflow, with bounded output.
- Kill a background descendant when its parent fixture exits.
- Reject creation/replacement in the toolchain and reads/writes of host-only leases.
- Kill parent and child fixtures when their separate owning backend is forcibly
  terminated; recover the abandoned scratch/profile afterward while preserving
  an unrelated sentinel. Recovery leaves a live owner's resources intact.
- Permit a small allocation under a 128 MiB job allowance but refuse a 256 MiB
  allocation, and reject spawning beyond a one-process ceiling. Limits may be
  lowered for fixtures, never raised beyond the defaults.
- Reject an attempted junction escape to an unrelated sentinel.
- Retain malformed recovery records and directory junctions without following
  them or acting on an unvalidated process identity.

Each probe writes a host-only lease before creating its profile. The lease binds
the generated directory/profile identity to the owner PID and Windows process
creation time, so a reused PID cannot claim an old run. `recover_abandoned` is an
diagnostic over an operator-selected scratch root. The execution service now calls
it on its own scratch directory at application startup. It derives deletion targets from validated generated
directory names and retains inaccessible or malformed resources for inspection.

Run explicitly with an approved external scratch directory:

```powershell
$env:RASPUTIN_SANDBOX_PROBE_ROOT='<absolute external scratch directory>'
.\.venv\Scripts\python.exe -m unittest tests.testWindowsSandbox -v
```

These tests are opt-in and skip by default. They require Windows and a maintainer
Node installation; they do not demonstrate a packaged or installed toolchain.
The fixture needs `--preserve-symlinks` and `--preserve-symlinks-main` because
Node's ordinary path canonicalization inspects ancestors outside the granted root.
Node subprocess fixtures inherit existing handles; compatibility with ordinary
test-runner pipe creation remains unverified.

The broader backend smoke gate ran 168 tests: 162 passed and six failed. The
failures were the coding-Trials execution assertion and five Stage 6 automatic
test-loop assertions. They expect execution where the checkout's existing native
validation changes refuse it. None of these paths imports the new probe. The
documentation contract check passed (50 Markdown files). This is not a clean
full-suite certification, and no installed application was rebuilt or updated.
After lifecycle hardening, the combined backend smoke and native-validation gate
ran 174 tests: 168 passed and the same six smoke assertions failed. All six
existing native-validation tests passed. The ten AppContainer integration tests
also passed in their separate opt-in run.

## Approval-bound execution and agent tools

The `/api/execution` API exposes capability discovery, administrator-only toolchain
pinning, request preparation, owner-scoped request/receipt retrieval, execution,
and cancellation. Ordinary Native Host authentication and Desktop's existing
loopback session rules apply. Pinning hashes executable bytes without running a
version probe on the host. Package acquisition remains open; the current API
expects a maintainer-provisioned self-contained executable.

A request captures explicitly selected workspace files (at most 256 files and
8 MiB), a bounded argument vector, a timeout up to 60 seconds, toolchain identity,
owner, optional task identity, and snapshot/plan hashes. Reparse points, path
traversal, Windows filename/device aliases, Git administration files, common
credential directories, environment files, and private-key files are refused.
The snapshot is read from checked file handles and retained in application data;
it is not a live mount of the original workspace.

Each request gets its own approval. Execution rechecks the current local account,
workspace membership/read capability, global shell policy, task state/binding,
snapshot hashes, plan identity, and configured toolchain. The approval is consumed
atomically only when its owner, task, workspace, action, plan digest, status, and
expiry match. The copied executable is hashed again before process creation.
Replays and cross-request approvals are rejected. Trusted Dev Mode does not skip
this approval.

The agent's `sandbox_prepare` tool pins the workspace to the persisted task,
ignoring model-authored workspace overrides. `sandbox_run` waits for that request's
approval, checks task cancellation, and returns the actual execution receipt.
Neither tool is offered without a pinned Windows toolchain or in unattended mode;
isolated-task planning excludes both tools. Model guidance scopes passing claims
to the approved snapshot. A repair requires new source edits, snapshot, and approval.
This explicitly requested workflow is separate from the legacy automatic test loop.

Receipts retain approved identities/arguments, timing, actual exit status, bounded
output, termination reason, and bounded changed-file hashes. Incomplete file
evidence cannot produce `passed: true`. Admission refusals and cancellation before
launch record `ran: false`; a runner error or process restart may leave `ran: null`
when actual execution cannot be established, and always records `passed: false`.
Source files are never updated from sandbox output. Tool/audit summaries omit code
and output text; receipt retrieval requires the owning account.

Startup recovers abandoned scratch/profile leases and marks interrupted requests
without replaying them. Shutdown signals running executions to stop. Pending
snapshot retention and workspace/profile disk quotas still need production policy;
the file-evidence ceiling is not a hard disk-write quota.

Validation for this integration: 23 focused tests passed (13 service/API/agent-tool
tests and 10 Windows containment tests). This includes a real local login, member
request, administrator approval, AppContainer execution, saved-receipt retrieval,
and replay refusal through the application API. The combined backend smoke and
native-validation gate remains 168 passes and the same six pre-existing failures
out of 174 tests. Documentation validation passed. No real local-model coding
mission, packaged application, or installed application was certified by these tests.

## Operator review in the source application

The existing Approvals page now has a snapshot review for execution requests.
Operators inspect the captured workspace, requester, pinned runtime, exact quoted
arguments, file list, and selected captured file contents before approving. Tabs,
line breaks, and empty arguments remain explicit in the argument display. Binary
files and truncated text previews are labeled; full snapshot/runtime hashes stay
under a disclosure. Changing a source file after submission does not change the
captured preview or execution input.

Approving a task-bound request releases the waiting agent tool. For a taskless
request owned by the current operator, **Approve and run snapshot** starts it;
an already-approved request has a separate run control. Owners can stop a running
execution. Receipts distinguish passing, non-passing, unexecuted, and unconfirmed
execution, show actual termination/exit details, and expose available output and
changed-file names. Failed loads and file-integrity errors remain visible.

Administrator-only review endpoints bind the approval to its immutable plan and
allow inspection of selected captured files, including requests from another
account. This does not grant execution/cancellation of another owner's request.
Other owners' output and generated-file evidence stay private, while the approval
operator can see the execution outcome. The original owner-only request API is
unchanged.

Verification passed: frontend build; 16 focused backend execution/review tests;
one live Playwright scenario covering real authentication, captured-file inspection,
approval/execution, denial, stopping, and output ownership. Keyboard and mouse
controls worked; there was no page overflow at 1440, 1024, 390, or 320 pixels, and
the changed screens were visually inspected. The design detector reported no
findings. The broader gate remains 168 passes and the same six pre-existing failures
out of 174 backend/native-validation tests. Existing Vite dependency/chunk warnings
remain. This is source Native Host evidence, not packaged or installed evidence.

The live check is repeatable after `npm run build`:

```powershell
.\.venv\Scripts\python.exe scripts/verify_sandbox_review.py --scratch-dir <absolute-external-scratch-directory>
```

It checks that the test port is free, creates isolated accounts/state/workspace,
runs actual AppContainer fixtures, saves browser evidence outside the checkout,
and removes its owned server and temporary data. It requires a maintainer Node
installation; end-user toolchain provisioning is still outstanding. The prior
Approvals layout can be restored by reverting the scoped UI integration; Chat
layout and composer are unchanged.

## Remaining acceptance gates, in dependency order

1. **Production execution boundary.** Broaden symlink and inherited-handle escape coverage; support pinned
   packaged toolchains and common runner subprocesses. The fixture toolchain is
   now read-only to the sandbox, but package identity/acquisition and ordinary
   test-runner pipe compatibility remain unproven. Disk growth and large-file
   workloads also need bounds before arbitrary repository execution is admitted.
2. **Execution admission and evidence.** Verify the implemented service in an
   isolated packaged application; finish snapshot retention/resource policy and
   user-facing runtime provisioning. Confirm receipts survive actual application
   interruption and remain accessible through the product review workflow.
3. **Coding workflow.** Connect the proven runner to the existing workspace
   test/repair loop and Trials. Run a real local coder through multi-file edits,
   an actual failing test, repair, passing test, final diff review, and explicit
   application of accepted changes. Verify the original checkout remains intact.
4. **Training workflow.** Verify the current ML dependency stack against an actual
   compatible local base model and dataset. Complete LoRA training, cancellation,
   adapter export, evaluation, and supported inference use. Report format/runtime
   incompatibilities before work starts; source preflight is not training proof.
5. **Installed daily driver.** Build the native toolchain resources into the
   installation flow; test the coding and training workflows in an isolated
   packaged application, then verify installation/upgrade on the intended target
   when authorized. End users must not need Python, Node, Git, or a repository.

This document tracks the combined product objective. The existing coding checklist
and native validation design retain their narrower scope. No production execution
capability was enabled by the initial prototype; the subsequent source API and
agent-tool integration is explicit, approval-bound, and still experimental.

## Platform references

- [Microsoft AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)
- [Process security-capability attributes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
- [Temporary AppContainer profiles](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile)
