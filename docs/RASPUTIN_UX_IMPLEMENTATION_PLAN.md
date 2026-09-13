# Rasputin UX campaign implementation plan

Planning baseline: **2026-09-12**. Execution status: **first source implementation slice verified;
installed verification and remaining packages are open**. See the execution record below.

This is the scoped engineering backlog for the 19 findings in the
[testing report](RASPUTIN_USER_TESTING_REPORT_2026-09-09.md). The report remains the historical
test record; this plan owns proposed work, dependencies, and acceptance criteria. It does not
replace the wider [v1 release contract](RASPUTIN_V1_RELEASE_CONTRACT.md) or claim that every
control in the [testing playbook](RASPUTIN_USER_TESTING_PLAYBOOK.md) was exercised.

## 1. Outcome and scope

Make model selection trustworthy, keep primary actions reachable, repair installed Desktop
copying, and make Stop stable and verifiably effective. Deliver small, reviewable changes to
existing components, followed by evidence from the actual packaged/installed application.

- Preserve automatic native GGUF selection and placement. Show the decision without requiring
  users to understand GPU configuration or choose every advanced setting.
- Preserve model keys, saved sessions, downloaded weights, workspaces, authentication, and
  runtime ownership. A display-name fix must not rename persisted model IDs.
- Upgrade Chat in place; retain the composer pill and existing page structure.
- No Docker, redesign campaign, schema migration, new permission framework, or broad refactor
  is required by these findings. Backend edits are conditional on reproduced backend defects.
- Attachment upload remains owner-verified. Do not reopen it as unfinished campaign work.
  `smoke-local-endpoint` remains an intentionally nonresponding negative fixture, not the model
  used to prove successful inference or cancellation.
- Work-package owners below are responsible disciplines, not assigned people. Implementation,
  publication, and installation remain separate actions. The initial planning request performed
  none; the subsequent implementation request authorized the source work recorded below.

## 2. Reconciled starting point

Current source was inspected on `codex/model-ecosystem-integration` in a mixed, uncommitted
working tree. Record a fresh commit plus scoped working-tree diff when execution starts;
a branch name alone cannot identify this baseline. Preserve unrelated edits.

Six findings already have campaign source changes: **UX-002, UX-008, UX-009, UX-013, UX-014,
UX-015**. Their earlier tests are historical evidence, not a fresh September 12 rerun and not
installed-fix certification. Carry these changes forward; do not implement them again unless
a targeted regression demonstrates a remaining gap.

Two source observations sharpen the remaining investigation:

1. **UX-017 is not merely a packaging question.** In `ModelsView.jsx`, the `displayItems`
   filter returns `!hasMin && !hasMax` for a missing/falsy `vramEstimateGb` *before* reaching
   `catalogPlacementAssessment(...).willFit === true`. Thus, with both VRAM bounds empty,
   that branch can admit an unknown/non-fitting row under Fits safely. This is a source
   control-flow finding, not a live reproduction. It does not explain all September 10 results,
   especially the run with a retained 13 GB maximum. Test both bounded and unbounded cases.
2. **UX-006 has a plausible metadata precedence problem.** `_normalize_hf_model` first maps
   `pipeline_tag`, then lets a broad `code`/`coder`/`coding` substring override that purpose
   before considering embeddings. Capture the affected record before deciding whether this
   explains the observed embedding label. Do not weaken fit rules because a model is small.

### Complete finding-to-work mapping

Each finding has one primary package. Other packages may exercise it as a regression.

| Finding | Primary package | Starting disposition |
| --- | --- | --- |
| UX-001 dialog sizing/reachability | WP-03 | Measure, then correct constrained layout |
| UX-002 misleading catalog count | WP-00 | Existing source fix; verify and carry forward |
| UX-003 opaque automatic download choice | WP-05 | Implement pre-download decision summary |
| UX-004 truncated model identities | WP-05 | Implement readable/full-identity affordances |
| UX-005 download progress moves results | WP-06 | Implement stable progress placement |
| UX-006 role and fit metadata | WP-01 | Diagnose normalization and fit separately |
| UX-007 Find a model destination | WP-05 | Correct CTA routing without changing Manage models |
| UX-008 artifact keys in visible labels | WP-00 | Existing source fix; verify installed surfaces |
| UX-009 clipped inventory toolbar | WP-00 | Existing source fix; retain populated-list regression |
| UX-010 CPU naming/mode truncation | WP-06 | Correct device label and option layout |
| UX-011 placement preview moves controls | WP-06 | Stabilize asynchronous dialog layout |
| UX-012 suspected low About contrast | WP-07 | Measure first; remediate demonstrated failure |
| UX-013 mismatch shown as healthy | WP-00 | Existing source fix; verify send prevention and recovery |
| UX-014 collapsed rail icons/status | WP-00 | Existing source fix; verify keyboard/status access |
| UX-015 clipped runtime card | WP-00 | Existing source fix; retain geometry regression |
| UX-016 installed clipboard failure | WP-02 | Diagnose Desktop path, then repair narrowly |
| UX-017 Fits safely includes unsafe/unknown | WP-01 | Fix filter bypass; reconcile remaining data paths |
| UX-018 Hardware obscures catalog | WP-03 | Correct scroll ownership and result reachability |
| UX-019 moving Stop target | WP-04 | Stabilize action; separately prove cancellation |

## 3. Execution order and dependencies

| Sequence | Deliverable | Dependencies / scheduling |
| --- | --- | --- |
| 0 | WP-00: preserve and establish the existing-fix baseline | First; no installed update needed to begin source work |
| 1 | WP-01: truthful fit filtering and metadata; WP-02: reliable copy | Both follow baseline; serialize overlapping `ModelsView.jsx` edits |
| 2 | WP-03: reachable Models layout; WP-04: stable Stop/cancellation | WP-03 follows fit changes in Models; WP-04 can proceed independently of them |
| 3 | WP-05: selection clarity; WP-06: stable asynchronous UI; WP-07: contrast | WP-05 uses WP-01 fit semantics; WP-06 follows WP-03 layout; WP-07 is independent |
| 4 | Integrated package and installed verification | Candidate's relevant source gates pass; preserve rollback artifact |

The first implementation slice is **WP-00 followed by WP-01's fit-filter regression and fix**.
Clipboard diagnosis can run alongside it, but edits to the shared Models file must be serialized.
Do not parallel-edit `ModelsView.jsx`, `HomeView.jsx`, or their shared stylesheets in one worktree.

Sequences 1–2 address the report's highest-impact trust/reachability concerns. Sequence 3 is
still part of the 19-finding backlog, not silently deferred. Shipping a partial batch requires
an explicit residual list; source completion alone does not change the installed defect status.

## 4. Reviewable work packages

### WP-00 — Retain and verify the six existing source fixes

**Owner:** frontend, with Desktop QA at integration. **Findings:** 002, 008, 009, 013, 014, 015.

**Source:** [display.js](../frontend-src/src/lib/display.js),
[HomeView.jsx](../frontend-src/src/features/chat/HomeView.jsx),
[ModelsView.jsx](../frontend-src/src/features/models/ModelsView.jsx),
[interface.css](../frontend-src/src/styles/interface.css), and
[models-workspace-v3.css](../frontend-src/src/styles/models-workspace-v3.css).
Anchors: `displayModelName`, `isModelHealthy`, `modelMismatchLine`, `models-rail-status`,
`.models-inventory-toolbar`, and `.models-developer-panel`.

1. Preserve the current resolver, mismatch exclusion, Catalog entries label, toolbar non-shrink,
   collapsed-icon selector, and max-content runtime rows. Record the scoped diff as baseline.
2. Rerun existing identity/readiness and populated-inventory regressions. Extend behavioral
   coverage for rendered response/task metadata, not just source-string assertions.
3. Check the mismatch recovery path: Needs attention must lead to model settings/retest or a
   usable repair instruction. If missing, add that small affordance without treating an empty
   discovery response as a proven mismatch.

**Acceptance:** header, composer, response/task details use a readable GGUF name while requests
retain the exact registry key; known mismatches cannot submit; a repaired matching endpoint
becomes selectable. Catalog/local counts have distinct meanings. With 23 models, Scan GGUF,
Refresh, rail icons, keyboard navigation, full status text, and runtime details remain usable.
Existing tests: `tests/userFacingModelIdentity.test.mjs`, `tests/launchReadiness.test.mjs`,
`tests/ui/campaignModelIdentity.spec.mjs`. Installed acceptance is still required at sequence 4.

### WP-01 — Make fit filtering and model roles trustworthy

**Owner:** Models frontend; catalog backend only for demonstrated normalization errors.
**Findings:** 006, 017. **Risk:** misleading capacity claims; do not relax placement safety.

**Source:** `ModelsView.jsx` — `displayItems`, `catalogPlacementAssessment`, rendered fit labels;
[catalog.py](../backend/models/catalog.py) — `_purpose`, `_normalize_hf_model`,
`_hf_purpose_from_pipeline`, `fitWillFit` mapping.

1. Save sanitized fixture payloads for the affected embedding rows, a fitting GGUF, a blocked
   row, and missing hardware/estimate data. Record active filters and displayed reasons.
2. Add a failing filter regression for missing estimate with empty VRAM bounds. Compose VRAM
   eligibility and fit eligibility so neither can bypass the other; use the same normalized
   assessment for row status and filtering. Extract a small pure helper only if it reduces
   duplication or allows direct behavioral testing.
3. Cover both curated catalog and Hugging Face results, filter changes after loading, hardware
   refresh, pagination, zero results, and a retained 13 GB maximum. Separate stale installed
   assets from source data-contract mismatches using the same captured fixtures.
4. For purpose classification, prioritize authoritative task metadata over incidental text;
   preserve explicit embedding/reranker purpose when an incidental tag contains `code`.
   Keep capability labels, native-format compatibility, and capacity assessment distinct.
   If the actual record disproves this hypothesis, document its real cause before editing.

**Acceptance:** every visible Fits safely row has normalized `willFit === true`. Unknown and
blocked rows remain available under Any fit when other active filters permit them. Missing
estimates never bypass the fit filter. A genuinely positive backend fit assessment without a
top-level estimate is handled consistently, not automatically mislabeled unknown. Embedding,
chat, coder, reranker, and incomplete-metadata fixtures have explainable labels. A small model
may remain blocked for a valid runtime/memory reason; size alone is not proof of compatibility.

**Tests:** add focused filter/normalization cases and a rendered catalog regression. Existing
`tests/modelCatalogRequest.test.mjs` is request-loading coverage, not proof of safe filtering.
Run relevant Python catalog tests plus backend smoke only if backend behavior changes.

### WP-02 — Repair Copy model ID in installed Desktop

**Owner:** Desktop integration + frontend. **Finding:** 016.

**Source:** `ModelsView.jsx` — `copyValue`;
[ModelServingPanel.jsx](../frontend-src/src/features/models/ModelServingPanel.jsx) — `copyText`;
[desktop/main.cjs](../desktop/main.cjs) — BrowserWindow settings and permission handler.
Read [THREAT_MODEL.md](../THREAT_MODEL.md) before changing this boundary.

1. Reproduce via a real user click in the packaged app. Capture the exception name, secure
   context/focus state, and requested permission/origin without logging clipboard contents.
   The notifications-only permission handler is a hypothesis, not a confirmed root cause.
2. Prefer the existing browser write path where it works. Choose the narrowest remedy supported
   by the failure evidence. Do not enable clipboard reads, blanket permission approval,
   Node integration, or disable sandbox/context isolation/web security.
3. If a Desktop bridge is necessary, expose only bounded text writing from the trusted main
   application frame/owner origin; reject unrelated frames/origins. Do not add a generic IPC
   executor. Reuse a small copy helper for the affected model-copy controls where appropriate.
4. On failure, offer selectable exact text and a clear manual-copy action; preserve focus and
   selection. Announce success only after the write succeeds.

**Acceptance:** installed Actions → Copy model ID copies the exact ID, checked by pasting into
a disposable test field. Keyboard activation works. Simulated rejection gives usable fallback
and no false success. No clipboard-read capability is added. Browser mocks alone cannot close
this issue. Test the Desktop boundary if changed, including rejection outside the trusted frame.

### WP-03 — Keep Models controls and results reachable

**Owner:** Models frontend. **Findings:** 001, 018; regressions: 009, 014, 015.

**Source:** `ModelsView.jsx` — `.model-hardware-filters`, `.models-catalog-advanced`, result and
receipt containers; `models-workspace-v3.css`; [Modal.jsx](../frontend-src/src/components/Modal.jsx)
and [ModelLoadDialog.jsx](../frontend-src/src/features/models/ModelLoadDialog.jsx) for sizing.

1. Reproduce with 23 registered models, three completed receipts, CPU/RAM/two GPU cards, Hardware
   and Filters expanded, and long names. Measure scroll containers and clipped controls.
2. Give the result pane usable space and explicit scroll ownership. Bound Hardware's desktop
   disclosure if needed; use a reachable single-column flow at narrow widths. Avoid nested
   scroll traps or solving the issue by automatically collapsing the user's disclosure.
3. Constrain dialogs to the viewport, scroll long content internally, and keep actions reachable.
   Reuse Modal focus trapping/restoration. Prefer scoped styles over changing every modal.

**Acceptance:** at 1427×934, a catalog row and its primary action are reachable with Hardware
open and receipts present, without closing Hardware. At 1024×900, 768×900, and 390×900,
all filters/results/dialog actions are reachable by mouse and keyboard, with no page-level
horizontal overflow. Check 200% zoom on a desktop viewport. Save before/after geometry and
screenshots; test scrolling and actual benign controls, not visibility assertions alone.

### WP-04 — Stabilize Stop and prove cancellation recovery

**Owner:** Chat frontend; task engine only if the controlled test exposes a defect.
**Finding:** 019. **Important:** the report proves movement, not a broken cancellation backend.

**Source:** `HomeView.jsx` — conditional `queue-strip`, `handleCancelTask`, Stop latest task;
[App.jsx](../frontend-src/src/app/App.jsx) — `cancelTask`;
[backend/api/agent.py](../backend/api/agent.py) — `/tasks/{task_id}/cancel`;
[backend/engine/agent.py](../backend/engine/agent.py) — `cancel` and terminal-state handling.

1. Use a controlled, slow stream fixture that waits for explicit test release/cancellation.
   Avoid timing races with a two-word response or repeated expensive prompts. Keep a separate
   working local model for the final native check; do not repurpose `smoke-local-endpoint`.
2. Stabilize the existing composer action slot while the queue strip appears/disappears. Keep
   its accessible name and focus; reserve space within the current layout, not a Chat redesign.
3. Check requested → acknowledged → terminal UI states. The current API path uses `cancelled`;
   do not rename the protocol state. Test cancellation rejection and done-before-click races
   without claiming that an already completed response was canceled.
4. Verify a later message succeeds. If the backend keeps streaming, overwrites the terminal
   state, or remains busy, trace that specific behavior through the cancel route/engine/provider
   before expanding the patch. Preserve task ownership checks.

**Acceptance:** with viewport and composer text unchanged, the action target stays in the same
slot across queued→running and queue-strip removal (geometry tolerance: 1 CSS pixel). Clicking
or keyboard-activating Stop on an active controlled stream requests the correct task, reaches
`cancelled`, stops visible output, and allows the next request. Repeat with a real local model
in the packaged/installed app. Controlled fixture success and native cancellation are separate
evidence. This package does not certify every multi-request queue-ordering case.

### WP-05 — Explain model selection before taking action

**Owner:** Models + Chat frontend. **Findings:** 003, 004, 007. **Depends on:** WP-01 semantics.

**Source:** `ModelsView.jsx` — `downloadCatalogItem`, `preferredDownloadVariant`, `startDownload`,
inspector variant selection; `HomeView.jsx` — Find a model and `ModelSidePanel`;
`App.jsx` — `onOpenModels={() => go("models")}`; `display.js` for readable identity.

1. Keep automatic recommendation, but resolve the exact GGUF before download. Show filename,
   quantization, known bytes (or explicit size unavailable), compatibility/fit reason, and
   automatic placement intent in the existing selection surface. Offer one primary Download
   action and optional Change variant; do not silently start while details are still resolving.
2. Ensure confirmation submits the same selected variant/revision shown to the user; refresh
   the summary if selection changes. Existing-artifact lookup must not load a different variant.
   A placement estimate is not a promise of a completed load.
3. Retain readable model names in narrow controls. Expose full identity through keyboard- and
   pointer-accessible details/copy, not a hover-only tooltip. Use WP-02 copy behavior when ready.
4. Give Find a model a Discover-specific callback or destination. Do not globally redirect
   `onOpenModels`, because the same callback also serves the legitimate Manage models action.

**Acceptance:** no download request occurs before the user sees and confirms its exact variant;
cancel/close produces none. Confirmation sends the displayed identity; incompatible choices
remain blocked. Long names are distinguishable without overflow. Find a model opens Discover;
Manage models still opens My Models. Extend `tests/modelEcosystem.test.mjs` and rendered route/
selection tests; preserve existing explicit-variant matching behavior.

### WP-06 — Stabilize progress and load-preview presentation

**Owner:** Models frontend. **Findings:** 005, 010, 011. **Depends on:** WP-03 sizing.

**Source:** `ModelsView.jsx` — `ModelDownloadProgress`, global progress/receipt placement;
`ModelLoadDialog.jsx` — `previewPending`, planned device allocation, Advanced, footer;
associated scoped Models styles.

1. Put progress in a stable bounded region or reserve its space while active. Retain truthful
   unknown-size/progress states and existing completed-receipt semantics; do not leave an empty
   permanent progress wall or hide errors to prevent motion.
2. Render CPU devices explicitly as CPU, preserving real GPU names and device IDs. Allow memory
   mode labels to fit/wrap without making Auto or pooled choices ambiguous.
3. Keep a stable preview/status area through pending, ready, blocked, and error states. Prevent
   the Load/Advanced target moving when asynchronous preview arrives; retain focus and ensure
   a stale preview cannot authorize loading after settings change.

**Acceptance:** controlled delayed preview and download fixtures cover start, progress,
completion, failure, and retry. Buttons remain reachable and a pending click is not displaced
to a different action. CPU never displays as GPU cpu; mode labels are readable at the WP-03
sizes. Test keyboard focus across updates. Extend `tests/modelDownloadVisibility.test.mjs`
and rendered geometry tests. Actual CPU inference is not required to prove a CPU label fix.

### WP-07 — Measure and correct About label contrast

**Owner:** frontend/accessibility. **Finding:** 012. **No dependency on Models changes.**

**Source:** [AboutSettings.jsx](../frontend-src/src/features/settings/AboutSettings.jsx) —
System Information labels using `text-dark`/`text-muted`; existing theme tokens and overrides.

1. Measure rendered foreground/background contrast, including opacity, in the campaign theme
   and supported light/dark variants. Record actual ratios before claiming a contrast failure.
2. Replace inappropriate hardcoded utility colors with existing semantic text tokens; avoid a
   global Bootstrap override or unrelated Settings redesign.
3. Use **4.5:1 for these ordinary-sized informational labels** as the acceptance target. If the
   measured labels already pass, retain the evidence and document any separate readability issue
   rather than making an unnecessary color patch.

**Acceptance:** all affected labels meet the recorded target in tested themes and remain
readable at desktop/phone widths and 200% zoom. Confirm computed styles and visual appearance
in the packaged UI. A screenshot alone is not a contrast measurement.

## 5. Verification and release handoff

These are execution gates, **not tests run while writing this plan**. Scale checks to each
package: copy changes need Desktop proof; label-only changes do not need a full backend suite.

### Per-change source gates

1. Add a behavioral regression that exercises the issue or, for suspected defects, records the
   measurement that resolves it. Prefer rendered output and API effects over source-text matches.
2. Run relevant existing/new unit tests and `npm.cmd run build` for frontend changes.
3. Follow [.agents/skills/verify/SKILL.md](../.agents/skills/verify/SKILL.md) for an isolated,
   authenticated source UI. Use a separate `RASPUTIN_DATA_DIR` and an explicit QA port; never
   start a second backend against the installed app's data. Capture viewport, fixture and build.
4. Set `RASPUTIN_TEST_BASE_URL` to that QA endpoint and supply `RASPUTIN_TEST_PASSWORD` privately
   before running Playwright. Missing-credential skipped tests are not passes.
5. Run `npm.cmd run desktop:check` and `npm.cmd run desktop:test` when Desktop code changes.
   For backend changes, use `.venv\Scripts\python.exe`, clear inherited `PYTHONHOME`/`PYTHONPATH`,
   and run focused tests plus `tests.testBackendSmoke` against isolated state.

Existing campaign baseline commands, from the repository root:

```powershell
node --test tests/userFacingModelIdentity.test.mjs tests/launchReadiness.test.mjs tests/modelEcosystem.test.mjs
npm.cmd run build
# Only after the isolated authenticated QA endpoint/environment is ready:
npx.cmd playwright test tests/ui/campaignModelIdentity.spec.mjs --project=chromium
```

Run newly added package tests as well; these baseline commands alone do not cover all 19 rows.

### Integrated candidate and installed closure

1. Integrate passing work packages without absorbing unrelated dirty-tree changes. Record the
   exact candidate source/diff. Use the existing `desktop:package` workflow for an authorized
   release build; follow [DEPLOYMENT_MATRIX.md](DEPLOYMENT_MATRIX.md) for ownership and upgrades.
2. Verify packaged assets contain the intended changes and run the changed interactions against
   an isolated packaged app. Preserve the previous known-good installer and its identity.
3. When installation is authorized, inspect the target's `desktop-runtime.json`, identify its
   owner URL/process, and follow the normal upgrade workflow. Do not delete ownership records,
   share the data directory with a source server, or overwrite live user/model state.
4. Record installed/package identity or hashes and exercise the report's failed interactions
   through the actual native window. If Computer Use is unavailable, state which browser or
   manual checks were used; do not relabel them as native-window automation.
5. Run one integrated native GGUF selection/download → registration → automatic Load → completed
   chat → Stop-model smoke, plus the separate Stop-generation test from WP-04. Use a small
   compatible model and preserve existing models/data. Record deliberate test additions.
6. If the candidate regresses a core journey or loses a required control, stop rollout and
   restore the previous application package through the supported workflow. Preserve data and
   diagnostics; do not reset databases or delete weights. No data migration is planned here.

The report's recommendation to hold an unqualified daily-driver UX sign-off for unresolved
008/016/017/018/019 remains a **recommendation**, not a claim that this plan replaces broader
release authority. Finish all scoped rows or explicitly accept named residuals with Elliott.

## 6. Closure record and next action

For each finding, record: source change/commit or scoped diff, reproduced case, test command
and result, evidence path, package identity, installed verification date/runtime, remaining
limitation, and rollback reference. Do not include secrets or clipboard contents.

Use the report's statuses: **Observed → Triaged → Source-fixed → Package-verified →
Installed-verified**. A measured non-defect or accepted residual needs its rationale and owner
decision; neither is silently counted as a fix. The work-package specifications above describe
the full intended scope; the execution record below, not their presence here, establishes progress.

### Execution record — September 12, first slice

Two **GPT-5.6 Luna** subagents implemented the disjoint fit-filter and purpose-normalization
patches. The parent reviewed both, requested reranker-preservation corrections, repaired test
selectors for the actual Desktop table, added curated Native Host coverage, and ran integration
checks. Baseline HEAD: `ab983c3ec91f6376ac41a089b98dace007adf9e5`, plus the pre-existing mixed
working-tree changes. Nothing was committed, pushed, packaged, or installed.

| Scope | Delivered evidence | Remaining boundary |
| --- | --- | --- |
| WP-00 baseline | 14 identity/readiness/ecosystem and 8 catalog/download Node checks passed; both existing authenticated browser regressions passed again, including 23-model inventory and narrow widths | Does not close every WP-00 acceptance item or any installed defect; additional rendered task/recovery coverage remains |
| UX-017 / WP-01 | Added `catalogFitFilter.js`; composed normalized VRAM eligibility with the existing row assessment, eliminating missing-estimate bypass. Four new Node regressions and three rendered catalog regressions pass | Source-fixed for covered cases; live installed catalog, hardware-refresh/pagination transitions, and original retained-13-GB payload reconciliation remain open |
| UX-006 / WP-01 | Known non-generation pipeline purpose survives incidental code tags; text-classification rerankers retain their refinement. Six Python tests pass, covering embeddings, rerankers, vision/speech, generation, and unknown metadata | A synthetic real-function reproduction, not proof of the original September 10 record's exact cause; small-model fit investigation remains open |
| WP-02 through WP-07 | Not implemented in this slice | Clipboard, reachability, Stop, selection, asynchronous layout and contrast work remain queued |

Changed source/tests in this slice:

- `frontend-src/src/features/models/ModelsView.jsx` — `displayItems` delegates composed filtering.
- `frontend-src/src/features/models/catalogFitFilter.js` — new small filter helper; uses existing
  `catalogVramEstimateGb` and `catalogPlacementAssessment`, not a second fit calculation.
- `backend/models/catalog.py` — pipeline-purpose precedence and specific reranker refinement.
- `tests/modelCatalogFitFilter.test.mjs`, `tests/testCatalogPurposePrecedence.py`, and
  `tests/ui/campaignCatalogFit.spec.mjs` — focused regressions. The browser fixtures exercise
  native GGUF rows without downloading or running models.

Final focused results: **26 Node tests passed, six Python tests passed, five Playwright tests
passed (no skips)**. The browser total comprises three new fit tests plus the two existing
identity/inventory tests. `npm.cmd run build` passed; existing Pyodide externalization and
large-chunk warnings remain. Initial browser-spec failures were ambiguous heading/obsolete card
selectors, corrected before the final pass; they were not presented as application failures.

The full backend smoke suite ran **168 tests: 162 passed, six failed**. The same six failures
reproduced with pre-change `catalog.py` loaded in memory, leaving the mixed worktree untouched:
`testCodingTrialBlindCompareScoresAndPinsCoderRole`,
`testStage6CodeLoopUsesApprovedCapsuleDuringEditTestRepair`,
`testStage6TestLoopPassFirstRunNoReopen`, `testStage6TestLoopReopensOnFailureThenStopsOnPass`,
`testStage6TestLoopSkipsWhenNoCommandOrShellDenied`, and
`testStage6TestLoopStopsAtRetryBudget`. These existing execution/trials failures are not fixed
or waived here. The full suite is **not green**; preserve that distinction from focused success.

Final browser evidence is machine-local under
`C:\Users\elliott\.codex\visualizations\2026\09\08\01a08255-6d2c-7c62-8261-32f6892170ad\ux-slice-evidence-NcOFqR`.
It contains screenshots and backend diagnostics from an isolated authenticated source server.
These are **headless Chromium source-app checks**, not installed/native-window interaction.
Test servers were stopped; installed application state and downloaded models were untouched.

**Next action:** WP-02 clipboard reproduction and narrow repair, alongside the remaining WP-01
real-payload investigation. Then continue WP-03/WP-04 and subsequent packages in sequence.
Do not redo the already-passing source filter fix or classify the entire 19-finding campaign
as complete. Record installed closure only after a separately authorized update and verification.
