# Project Prometheus — Phase 0 Execution Status

> **Branch:** `codex/project-prometheus-phase-0`
> **Baseline:** `bdb06f7`
> **Status:** Implementation checkpoint — owner reviewable, not committed

## What is now working

| Baseline promise | Result | Evidence |
|---|---|---|
| Desktop process lifecycle | Pass | Full desktop lifecycle suite: 5/5 tests passed. The earlier abandoned-process failure was a sandbox permission artifact, not a product defect. |
| Workspace validation commands | Pass | Administrators can edit and persist test, build, and lint commands from Workspaces. A focused browser test saved all three and confirmed the active workspace API state. |
| Coding review inspection | Pass | The task drawer exposes Changes and Terminal views. Mouse navigation and WCAG arrow-key tab navigation were exercised live; automated checks cover both panels, repository state, keyboard selection, and approval-gated Revert. |
| Governed diff and restore | Pass | Backend smoke coverage verifies structured git status/diff and approval-gated restore. A focused browser test proves Revert requests approval without changing the file. |
| GitHub repository foundation | Pass | Local-only metadata reports branch, upstream, ahead/behind counts, commit, sanitized remotes, and detected GitHub repository without fetching or requiring credentials. |
| WarSat parser selection | Pass | Manual deployment plans expose an opt-in model-specific parser with safe suggestions and a mismatch warning. |
| Multi-GPU manual planning | Pass | A live plan used llama.cpp layer sharding across the detected RTX 3060 and RTX 5060 Ti, with automatic fitting. |
| Production frontend | Pass | Vite production build completed successfully. |

## Defect found and fixed during live verification

The current WarSat form did not render a `gpuLayers` field, but its submit
handler converted that missing field to numeric `0`. The backend correctly
interpreted `gpuLayers=0` as CPU-only, which conflicted with the form's default
“Use all detected GPUs” selection.

The submit handler now leaves an absent or blank GPU-layer value unspecified.
WarSat can therefore apply its existing automatic multi-GPU fit policy. The
same live parser-aware plan that failed before the fix now generates
successfully across both GPUs.

## Verification snapshot

| Check | Result |
|---|---|
| `npm run build` | Pass — 3,153 modules transformed in 10.97 s |
| Backend and multi-user suites | Pass — 145 tests in 40.571 s; 1 skipped |
| Desktop lifecycle suite | Pass — 5 tests in 4.643 s |
| Targeted workspace-command browser test | Pass — 1 test in 4.1 s |
| Targeted repository/Revert browser test | Pass — 1 test in 5.4 s |
| Targeted backend feature checks | Pass — 4 tests in 0.987 s |
| Live workspace command save/reload | Pass |
| Live WarSat parser + combined-GPU plan | Pass |
| Live task Changes/Terminal mouse navigation | Pass |
| Live task Changes/Terminal arrow-key navigation | Pass |
| Git whitespace/error check | Pass |

The production build's largest JavaScript chunk is currently about 932 KB
(281 KB gzip), and Vite continues to emit its existing large-chunk warning.

## Remaining before the Phase 0 owner gate

1. Run the definitive coding mission with a real local coding model: multi-file
   edit, intentional test failure, repair, passing validation, and final diff.
2. Decide whether to modernize the older broad
   `tests/ui/rasputinSmoke.spec.mjs` selectors. The repository's verification
   guide already records that much of that suite predates the current chat
   layout, so it is not a reliable all-UI release gate yet.

## Current external blocker

No healthy local coding model is available in the verification runtime.
`main-vllm` points to `127.0.0.1:8000`, but that port currently belongs to
Portainer and returns HTTP 404 for the model API. Docker has no model-serving
container running. Dry Run is healthy, but it cannot prove real coding ability.

The definitive local-model mission should remain blocked rather than be
misrepresented with the mock provider.

## Recommended next checkpoint

Start or register the intended local coder, verify its parser and context
settings, then execute the definitive mission without changing the acceptance
scenario. If it passes, close Phase 0 and present the owner gate before starting
direct Odysseus source adoption under the selected Rasputin license.
