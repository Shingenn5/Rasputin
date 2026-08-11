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
     `\.venv\Scripts\python.exe scripts\check_installation.py`
   - Linux/macOS:
     `./.venv/bin/python scripts/check_installation.py`

3. Choose exactly one runtime for the first pass. Docker is the cross-platform
   path; the native server is the Windows direct-folder path. Use the commands
   in [`DEPLOYMENT_MATRIX.md`](DEPLOYMENT_MATRIX.md) and do not expose the
   service beyond loopback while validating.
4. Sign in through the local login screen. Do not paste a password or token into
   a terminal transcript.

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
2. In WarSat, create a preview only. Confirm resource admission, runtime,
   placement, parser, and approval state are visible in the plan.
3. Verify an over-capacity or contradictory placement remains blocked before
   any container/model process starts. Do not enable privileged Docker control
   for this evidence pass.

## 4. Governed Assistant command

1. Enter a harmless read-only request such as “check docker status” and submit
   **Preview**. Confirm the route is allowlisted, execution is not started, and
   the preview explains its operation.
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
| Native/Docker deployment |  |  |  |
| Model placement/admission |  |  |  |
| Live coder mission |  |  |  |
| Live voice turn |  |  |  |
| Lasting memory |  |  |  |
| Safe orchestration |  |  |  |
| Recovery |  |  |  |
| Operator UX |  |  |  |

The automated command is:

- Windows: `\.venv\Scripts\python.exe scripts\verify_release_candidate.py`
- Linux/macOS: `./.venv/bin/python scripts/verify_release_candidate.py`

The report is **candidate_with_boundaries** until every required live row is
green. New capabilities belong in the post-v1 backlog; v1 maintenance is
limited to regressions, security issues, data-loss risks, and deployment
failures.
