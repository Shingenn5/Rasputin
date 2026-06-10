# Rasputin Autonomous Pass Runbook

This runbook defines how Codex should continue building Rasputin without requiring a fresh plan prompt every time. It is intentionally bounded: one pass, one branch, one validation cycle, one commit, then stop.

Use this when the operator says something like:

```text
Run the next Rasputin pass from the pass queue.
```

Do not use this runbook to perform unattended destructive work, deploy models, download large files, push to `main`, or mutate user data.

## Operating Model

Rasputin development should move through small production passes.

Each pass must:

- read `docs/PASS_QUEUE.md`
- select the first unchecked pass with status `queued`
- create or switch to the pass branch
- implement only the stated scope
- preserve existing user changes
- run required validation
- commit only clean source/docs/test changes
- update `docs/PASS_QUEUE.md`
- stop with a concise report

The pass runner must not silently continue into the next pass.

## Status Values

Use these statuses in `docs/PASS_QUEUE.md`:

- `[ ] queued`: ready to implement
- `[~] running`: active in the current branch
- `[!] blocked`: cannot continue without operator decision
- `[x] complete`: implemented, tested, and committed
- `[-] deferred`: intentionally not active yet

Only one pass should be marked `[~] running` at a time.

## Required Workflow

### 1. Preflight

Run:

```powershell
git status --short --branch
```

Stop if:

- there are uncommitted changes from another pass
- the current branch is wrong and switching would risk losing work
- runtime data, secrets, model files, logs, or generated indexes are staged

If the worktree is clean, read:

- `docs/PASS_QUEUE.md`
- `docs/STAGED_IMPLEMENTATION_BACKLOG.md`
- any docs linked by the selected pass

### 2. Select The Pass

Choose the first pass in `docs/PASS_QUEUE.md` marked `[ ] queued`.

Do not reorder the queue unless the operator explicitly asks.

Before implementing, update the selected pass to `[~] running`.

### 3. Branch

Use the branch listed in the pass queue.

Preferred command:

```powershell
git checkout -b codex/example-pass-name
```

If the branch already exists:

```powershell
git checkout codex/example-pass-name
```

Do not work directly on `main` unless the operator explicitly says to.

### 4. Scope Control

Implement only the selected pass.

Allowed by default:

- source files under `backend/`
- source files under `frontend-src/`
- tests under `tests/`
- protocol/config templates that are intended for source control
- docs under `docs/`

Not allowed without explicit operator approval:

- broad file deletion
- real user data mutation
- Docker socket mounting
- Docker model deployment
- large model downloads
- system package installation
- API key creation or storage
- remote MCP registration
- pushing or replacing `main`

### 5. Accessibility Baseline

Every UI pass must preserve these minimums:

- keyboard reachable controls
- visible focus state
- meaningful accessible names for icon buttons
- no click-only interactions
- no hidden status text using zero-size hacks
- no text overflow in supported desktop, split-screen, tablet, or mobile widths
- `aria-live` for async error/status updates where relevant
- contrast must remain readable in the default theme and light theme

If a pass changes navigation, panels, modals, drawers, tabs, forms, or task controls, add or update UI smoke coverage.

### 6. Validation

Run the pass-specific checks from `docs/PASS_QUEUE.md`.

Default validation set:

```powershell
npm.cmd run build
docker compose -f docker-compose.test.yml up --build -d
docker compose -f docker-compose.test.yml exec -T rasputin-wrapper-test python -m unittest tests.testBackendSmoke
npx.cmd playwright test tests/ui/rasputinSmoke.spec.mjs --project=chromium --reporter=list
git diff --check
powershell.exe -ExecutionPolicy Bypass -File .\scripts\check-repo-safety.ps1
```

If a UI suite fails once but the failure appears unrelated or timing-based, rerun the single failing test once. If the same failure repeats, fix it or mark the pass blocked.

Do not hide failing tests.

### 7. Commit

Before committing:

```powershell
git status --short
git diff --check
powershell.exe -ExecutionPolicy Bypass -File .\scripts\check-repo-safety.ps1
```

Stage only intended source/docs/test files.

Commit with the message listed in the pass queue.

After commit, update the pass queue entry to `[x] complete` and include:

- commit hash
- date
- validation summary

Commit that queue update as either:

- part of the feature commit, if practical
- a second docs-only commit, if the feature commit already exists

### 8. Stop

End the run after one pass.

The final report must include:

- branch
- commit hash
- what changed
- validation results
- whether anything remains blocked
- the next queued pass

Do not begin the next pass automatically.

## Stop Conditions

Stop and report `[!] blocked` if any of these occur:

- the same test failure repeats after one focused retry
- implementation requires destructive file operations
- implementation requires Docker socket access
- implementation requires downloading models or large external assets
- implementation requires storing secrets
- implementation requires changing system settings
- implementation would expand model internet access
- implementation would expose local file contents externally
- unclear product decision would materially change UI/UX direction
- branch history or merge state is unsafe

## GitHub Policy

Default behavior:

- create local feature branch
- commit locally
- do not push
- do not open PR
- do not merge to `main`

Push only when the operator explicitly asks.

If pushing is approved:

- push the feature branch, not `main`, unless explicitly requested
- never force-push without explicit approval
- never push runtime data, `data/`, `testdata/`, `models/`, logs, screenshots, indexes, local configs, or secrets

## Manual Trigger Prompt

Use this prompt to start the next pass:

```text
Run the next Rasputin pass from docs/PASS_QUEUE.md using docs/AUTONOMOUS_PASS_RUNBOOK.md. Implement one pass only, run required validation, commit the result, update the queue, and stop. Do not push, deploy models, mount Docker socket, download large files, delete broad paths, or mutate user data without explicit approval.
```

## Future Automation

Once three consecutive passes complete cleanly with this runbook, it is reasonable to add a Codex automation that runs the manual trigger prompt on demand.

Do not schedule unattended recurring execution until:

- MCP local stdio support is stable
- Warsat deployment approval gates are stable
- repo safety checks are reliable
- pass queue entries have precise stop conditions
- the operator has approved the automation behavior
