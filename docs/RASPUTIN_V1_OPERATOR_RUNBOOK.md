# Rasputin v1 operator evidence runbook

**Status:** release-candidate evidence checklist

This runbook is the final human verification companion to
[`RASPUTIN_V1_RELEASE_CONTRACT.md`](RASPUTIN_V1_RELEASE_CONTRACT.md). It does
not turn an automated contract check into a live claim. Record only what you
actually observe, and keep credentials, audio, memory contents, and private
workspace paths out of issue reports.

## 1. Prepare an isolated operator session

1. Confirm the checkout is clean or that any local changes are intentionally in
   scope: `git status --short`.
2. Run the read-only installation check:

   - Windows PowerShell:
     `.\.venv\Scripts\python.exe scripts\check_installation.py`
   - Linux/macOS:
     `./.venv/bin/python scripts/check_installation.py`

3. Choose installed Windows Desktop or an isolated source Native Host. Identify its live owner
   and recorded URL; never run both on the same store. Follow
   [`DEPLOYMENT_MATRIX.md`](DEPLOYMENT_MATRIX.md) and remain on loopback.
   The current product has no container deployment step.
4. Installed Desktop should open directly into the workspace with its loopback-only local
   administrator session. Source Native Host requires the local login screen and a session cookie.
   Do not paste a password or token into a terminal transcript.

## 2. Workstation and Assistant separation

From the Dashboard, verify with keyboard and mouse that both entry points are
visible and independently usable:

- **Workstation:** open chat/coding, choose a registered model, and inspect the
  workspace and task controls.
- **Assistant:** open the Assistant surface and confirm the profile, context,
  voice readiness, MCP capability, and command-preview cards load without
  starting a process.

Confirm that switching between the two surfaces does not silently change the
selected workspace, owner, safety policy, or approval state. The UI should make
the separation understandable without relying on hidden developer labels.

## 3. Model fit and launch admission

1. In Models, inspect a catalog entry that fits and one that does not. Confirm
   the UI explains “Why it fits?” or the concrete `blockedReasons` before a
   launch action is available.
2. Select a compatible GGUF and open its native Load dialog. Inspect context, memory mode,
   placement, runtime compatibility, and any blocking reasons before launch.
3. Verify impossible settings stay blocked before a model process starts. With an approved
   small model, complete download → register → load → actual response → stop. Record the
   artifact/runtime/device configuration; do not call this a coder certification.

## 4. Governed Assistant command

1. Enter “start coding task” and submit **Preview**. Confirm the operation is allowlisted,
   no task starts, and the response explains any missing workspace/model capability.
   This is a preview check, not authorization to dispatch the task.
2. Enter a host-action request such as “open vscode”. Confirm it is marked for
   review/approval and does not run.
3. Enter a compound unsafe request containing a shell separator. Confirm it is
   rejected and no side effect occurs.

Record the approval code and status only; never include private command output.

## 5. Lasting memory and context

1. Save a non-sensitive preference in Memory with the intended workspace scope.
2. Search for it and open **Why was this recalled?**. Confirm matched terms,
   scope reason, ranking factors, and source metadata are shown.
3. Save a corrected value. Confirm the original is marked superseded and the
   correction retains provenance. Verify the other owner/workspace cannot see
   the item.
4. Exercise the task-level memory mode (`auto`, `include`, and `suppress`) in a
   disposable conversation. Confirm suppression is visible in the task trace.
5. If performing a restart rehearsal, use a copied/isolated data directory;
   never stop the active installation or overwrite its store during this pass.

## 6. Local voice turn (operator hardware boundary)

This is the only step that requires hardware and authenticated browser state.
Use the supported local STT/TTS pair documented in
[`LOCAL_VOICE_MODEL_READINESS.md`](LOCAL_VOICE_MODEL_READINESS.md).

1. Confirm the Assistant card reports the registered STT and TTS endpoints and
   their health/readiness without starting an unapproved model.
2. Click push-to-talk and grant microphone permission only for the loopback
   origin. Record a short, non-sensitive phrase.
3. Confirm the turn completes local STT -> Assistant -> TTS, shows a transcript
   and response, and plays bounded audio.
4. Stop/abort a recording and wait past the timeout boundary once. Confirm the
   UI returns to an idle/error state without leaving the microphone active.
5. Revoke the browser permission after the pass if this is a shared machine.

If speech models, browser permission, or audio hardware are unavailable, mark
this row **open**; do not substitute a mocked response and call it a live turn.

## 7. Coder mission and recovery

With a reachable, certified local coder model only:

1. Run the bounded multi-file edit -> failing test -> repair -> diff review
   mission in a disposable workspace.
2. Confirm the test failure and repair are both recorded, the diff is reviewable,
   and no host mutation occurs without approval.
3. Run the documented backup/restore rehearsal into a separate clean target and
   verify integrity, login, workspace ownership, and frontend health.

When no local coder model is registered, mark the coder row **blocked**. When
the service is still running on the active data directory, mark active-data
upgrade as **open** even if a separate-target restore passes.

## 8. Record evidence and stop at the v1 boundary

| Evidence row | Status (`verified`, `partial`, `open`, `blocked`) | Date/runtime | Redacted note or artifact path |
| --- | --- | --- | --- |
| Automated regression and docs |  |  |  |
| Native Desktop/Host deployment |  |  |  |
| Model placement/admission |  |  |  |
| Live coder mission |  |  |  |
| Live voice turn |  |  |  |
| Lasting memory |  |  |  |
| Safe orchestration |  |  |  |
| Recovery |  |  |  |
| Operator UX |  |  |  |

The automated command is:

- Windows: `.\.venv\Scripts\python.exe scripts\verify_release_candidate.py --endpoint native=http://127.0.0.1:8788`
For Desktop, substitute its recorded loopback URL. Supply the endpoint explicitly so older helper defaults do not select retired infrastructure.

The report is **candidate_with_boundaries** until every required live row is
green. New capabilities belong in the post-v1 backlog; v1 maintenance is
limited to regressions, security issues, data-loss risks, and deployment
failures.
