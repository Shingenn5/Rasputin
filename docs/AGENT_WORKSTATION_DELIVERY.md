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
Native command execution and automatic validation remain disabled.

The first implementation in this track is `backend/core/windows_sandbox.py`, an
explicitly development-only AppContainer probe. It has no API route, agent tool,
readiness override, or host-shell fallback. Its result says `production_ready: false`.
It is not an execution authorization.

The probe creates a unique temporary AppContainer profile with no network
capabilities, a disposable directory, and a copy of a trusted self-contained
executable. Only the disposable directory receives a profile-specific modify ACL
and low-integrity label. No source checkout or application data is mounted. The
child receives an explicit environment and inherited-handle list. Suspended
creation allows assignment to a Windows job before executing instructions. The
job limits aggregate memory to 1 GiB and active processes to 16, kills processes
on owner-handle closure, and is terminated on completion, timeout, cancellation,
or output overflow. Output is bounded; cleanup waits for the job to empty.

The standard AppContainer boundary still allows access to OS resources granted to
ALL APPLICATION PACKAGES and creates private profile storage. It is not a claim
that absolutely all filesystem reads outside scratch are impossible. LPAC was
investigated but prevented the local Node fixture from initializing Winsock; the
committed probe explicitly uses standard AppContainer, with no runtime downgrade.

Five actual Windows integration tests passed with the local Node toolchain:

- Write two fixture files, observe a failing check, repair the implementation,
  and observe a passing check, entirely inside scratch.
- Reject reads and writes to an unrelated sentinel and omit a host environment
  secret; the original sentinel remains unchanged.
- Reject external TCP access with a permission error. A loopback connection cannot
  reach a controlled listening endpoint which a host control can reach. Windows
  reports a socket timeout for that loopback denial on this workstation.
- Terminate on timeout, cancellation, and output overflow, with bounded output.
- Kill a background descendant when its parent fixture exits.

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

## Remaining acceptance gates, in dependency order

1. **Production execution boundary.** Prove containment and cleanup on abrupt
   backend death; recover abandoned scratch/profile resources after restart;
   test junction/symlink and handle escape attempts; prove resource limits;
   support pinned immutable packaged toolchains and common runner subprocesses.
   A prototype's scratch-local writable executable is not an immutable toolchain.
2. **Execution admission and evidence.** Bind task, owner, workspace, approved
   executable/argv, environment policy, and snapshot identities to each request.
   Recheck permissions and approvals at execution. Persist bounded output,
   termination reason, actual exit status, and changed-file hashes as receipts.
   Cancellation, refusal, and interruption must never be reported as passing.
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
capability was enabled by the initial prototype.

## Platform references

- [Microsoft AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)
- [Process security-capability attributes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
- [Temporary AppContainer profiles](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile)
