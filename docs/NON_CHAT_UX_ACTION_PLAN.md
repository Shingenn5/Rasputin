# Non-Chat UX action plan

**Prepared:** October 31, 2026 (America/Chicago)

**Status:** PLANNED — no fixes implemented by this report

**Scope:** Rasputin's non-Chat interface, using Unsloth as a workflow reference

**Starting branch / HEAD:** `codex/rust-performance-investigation` / `2604754f60577d1fd3df3e66087ba5381a3c3589`

## Outcome and boundaries

Make the next action, current capability, and result clear on every non-Chat screen. Fix misleading behavior and accessibility first; simplify workflows next; standardize presentation last.

This is the actionable backlog for the October 30 non-Chat audit. It complements the [October 28 UI audit](RASPUTIN_UI_AUDIT_2026-10-28.md) and [October 27 remediation report](RASPUTIN_UI_REMEDIATION_REPORT_2026-10-27.md); it does not replace the [active engineering checklist](CODING_AGENT_IMPLEMENTATION_CHECKLIST.md) or [v1 release contract](RASPUTIN_V1_RELEASE_CONTRACT.md). Reuse an existing fix or evidence when it meets the acceptance criteria below. Do not implement overlapping findings twice.

The audit included uncommitted work. The starting commit alone cannot reproduce that snapshot. Reproduce each issue against the current checkout before editing, and record the actual implementation commit and runtime tested when closing it.

Keep Chat's layout and composer unchanged. Preserve authentication, workspace access, approvals, process ownership, exact GGUF selection, and model-placement controls. Use existing tokens and shadcn primitives; introduce no new Bootstrap usage. A frontend task does not authorize implementing a scheduler, provisioning training dependencies, adding protocols, or changing credential policy. Read the threat model before any implementation that touches those boundaries.

## Evidence baseline

The October 30 audit established:

- A successful production source build into isolated scratch; 11 non-Chat desktop routes without browser page errors.
- Six routes at 1440, 1024, and 390 CSS pixels: 18 combinations without document-level horizontal overflow. A large mobile Library search field still impaired usability.
- Working navigation into the API gateway disclosure and Trials Datasets tab; Settings search for `theme` incorrectly reported no matches.
- Ten controls without associated labels in General Settings and Scheduled; source-backed misleading readiness and generated chart traces.
- An empty source-detector result, which did not establish absence of issues. The provisional score was 11/20, with four P1 and eight P2 findings, and no P0 established.

These are historical source-app observations, not newly rerun tests or installed-app certification. The audit did not establish full contrast compliance, screen-reader behavior, physical touch behavior, training success, schedule execution, or comparative performance. Original screenshots and JSON were session-local; this document carries the findings and reproduction steps so implementation does not depend on a maintainer's private scratch directory.

The [Unsloth workstation study](UNSLOTH_WORKSTATION_UPGRADE_STUDY.md) records the reference workflows: distinct model/content collections, visible API operations, and training configuration with a readiness preview. Its performance or capability claims do not transfer to Rasputin.

## Execution order

Effort is relative scope, not a delivery estimate: **S** = focused component repair; **M** = coordinated changes across a surface; **L** = cross-route or build/runtime investigation. All work is unassigned and planned until an implementer records otherwise.

| ID | Priority | Work package | Effort | Prerequisite | Batch |
| --- | --- | --- | --- | --- | --- |
| NC-01 | P1 | Name form controls correctly | S | Reproduce current DOM | 1 |
| NC-02 | P1 | Make schedule availability truthful | S | Confirm execution capability | 1 |
| NC-03 | P1 | Repair mobile Library search sizing | S | Reproduce at 390px | 1 |
| NC-04 | P1 | Correct readiness and chart claims | M | Confirm model-state definitions | 1 |
| NC-05 | P2 | Put API operations in the primary view | M | NC-04 state vocabulary | 2 |
| NC-06 | P2 | Put training capability before configuration | M | Confirm runtime/preflight contract | 2 |
| NC-07 | P2 | Search settings by the control users want | M | NC-01 control IDs | 2 |
| NC-08 | P2 | Simplify model discovery | M | NC-03, NC-04 | 3 |
| NC-09 | P2 | Expose secondary tools and clarify names | M | NC-08 destination names | 3 |
| NC-10 | P2 | Give empty Workspaces a useful next action | M | Existing access/indexing contracts | 3 |
| NC-11 | P2 | Standardize non-Chat visual hierarchy | M | Batches 1–3; earlier contrast findings | 4 |
| NC-12 | P2 | Profile and reduce shared frontend cost | L | Capture baseline before changes; optimize after route layouts settle | 4 |

**First implementation slice:** NC-01 and NC-03, committed separately. They have concrete reproductions and narrow scope. Complete NC-02 and NC-04 before broad layout work. Capture NC-12's baseline early, even though optimization comes later. Batch order is delivery order, not a requirement to delegate or work concurrently.

## Work packages

### NC-01 — Name form controls correctly

**Problem:** Visible labels are not associated with six General Settings controls and four Scheduled controls. Screen readers cannot reliably identify them.

**Start in:** [GeneralSettings.jsx](../frontend-src/src/features/settings/GeneralSettings.jsx), [SchedulesView.jsx](../frontend-src/src/features/runtime/SchedulesView.jsx). Related earlier finding: October 27 `UI-03`.

**Implement:**

- Give theme, language, motion, workspace path, Markdown, Testing Mode, schedule name, prompt, interval, and enabled controls stable IDs and associated labels.
- Use semantic labels or the component's supported naming prop; attach help text with `aria-describedby` where needed. Retain existing persistence and toggle behavior.

**Done when:**

- [ ] All ten controls resolve by role and meaningful accessible name; clicking each visible label focuses or toggles its control.
- [ ] Keyboard Tab/Shift+Tab and Space/Enter work with visible focus; toggles announce their state.
- [ ] Supported changes persist through the existing save flow, and immediate preferences still apply immediately. Use an isolated profile.
- [ ] No duplicate IDs or relevant control-naming violations occur in the rendered affected sections.

**Verify:** Extend the relevant settings/UI checks with behavior-based role/name queries; run `tests/settingsUiContract.test.mjs` and `tests/settingsWorkspaceV3.test.mjs`, then live-test both routes. These existing suites are regression coverage, not proof of the new accessible names by themselves.

### NC-02 — Make schedule availability truthful

**Problem:** Scheduled offers Enabled and Create Schedule while inspected code only persists definitions and future timestamps; no due-task execution consumer was found.

**Start in:** [SchedulesView.jsx](../frontend-src/src/features/runtime/SchedulesView.jsx), [schedules.py](../backend/core/schedules.py), and the schedule endpoints in [agent.py](../backend/api/agent.py).

**Implement:** Recheck for an execution consumer. If still absent, present saved task templates, explicitly say automatic execution is unavailable, and remove or disable the misleading activation control. Preserve existing saved definitions. If an executor now exists, document and verify its actual behavior rather than applying obsolete copy.

**Done when:**

- [ ] A fresh user can tell, before saving, whether the task will run automatically.
- [ ] Existing records are retained and do not acquire new execution behavior from this UI repair.
- [ ] No confirmation, badge, or next-run display implies verified execution where none exists.
- [ ] Invalid/empty inputs produce useful errors; NC-01 naming remains intact.

**Verify:** Exercise empty, saved, and invalid states; confirm a saved record remains after reload. If claiming runnable scheduling, require a real due-run/outcome test and approval-boundary tests in a separately scoped implementation. **Do not build that scheduler as part of this ticket.**

### NC-03 — Repair mobile Library search sizing

**Problem:** The toolbar switches to a column while search retains `flex: 1 1 180px`, turning a width-oriented flex basis into excessive vertical space.

**Start in:** [modelWorkspace.css](../frontend-src/src/features/models/modelWorkspace.css), [models-workspace-v3.css](../frontend-src/src/styles/models-workspace-v3.css), [ModelsView.jsx](../frontend-src/src/features/models/ModelsView.jsx).

**Implement:** Reset the search wrapper's growth/basis at the column breakpoint and use the shared compact control height. Avoid a global height override that breaks desktop layout or enlarged text.

**Done when:**

- [ ] At 390px with default text size, the single-line search wrapper stays within 44–56 CSS pixels and does not absorb remaining vertical space.
- [ ] At 1440, 1024, and 390px, search, category, scan, refresh, and model selection remain usable without page overflow.
- [ ] A populated fixture shows the first model after a compact toolbar; 200% text zoom does not clip labels or controls.
- [ ] Filtering and selection still work with keyboard and mouse; long model names wrap/truncate intentionally.

**Verify:** Run relevant `tests/modelsWorkspaceV3.test.mjs` coverage and a rendered responsive interaction check with a populated model fixture. Record before/after screenshots and actual search bounds. A mocked model establishes layout only, not inference.

### NC-04 — Correct readiness and chart claims

**Problem:** Settings labels the registry count as models ready; Dashboard traces include generated or fixed sequences that look like measured history.

**Start in:** [SettingsView.jsx](../frontend-src/src/features/settings/SettingsView.jsx), [DashboardView.jsx](../frontend-src/src/features/dashboard/DashboardView.jsx), existing [modelPresentation.js](../frontend-src/src/features/models/modelPresentation.js).

**Implement:** Reuse model-state helpers. Use registered/configured for registry totals; distinguish downloaded, loaded, and reachable only where evidence exists. Remove decorative metric traces unless backed by timestamped measurements. Missing history should say so. This is a metric display repair, not a Dashboard redesign.

**Done when:**

- [ ] An unreachable registered model increases configured count without being represented as ready.
- [ ] Stopped local, loaded local, unreachable external, and unknown states have truthful, consistent labels across affected screens.
- [ ] Every retained trend is derived from real records with a defined time window; absent history produces no fabricated trend.
- [ ] Empty data and service errors remain distinguishable; failures do not turn into zero-valued success indicators.

**Verify:** Extend `tests/modelStateLanguage.test.mjs` / `tests/modelRuntimeStatus.test.mjs` where applicable and live-test the state matrix. Use synthetic records explicitly as fixtures; do not label fixture charts as production measurements.

### NC-05 — Put API operations in the primary view

**Problem:** Routine gateway controls, readiness, and request metrics are grouped under advanced protocols; the initial screen emphasizes instructions and credentials.

**Start in:** [ApiView.jsx](../frontend-src/src/features/workstation/ApiView.jsx), [ModelServingPanel.jsx](../frontend-src/src/features/models/ModelServingPanel.jsx).

**Implement:** Promote loaded/available model, gateway readiness, base URL with Copy, next action, and recent request results. Keep credential management and uncommon protocol/MCP controls secondary. Reuse existing telemetry and configuration contracts. Explain and consolidate duplicate key-generation entry points without changing credential semantics. Display a last-updated state and explicit Refresh; polling is optional and must stop when the route is inactive.

**Done when:**

- [ ] Missing key, gateway off, no servable model, ready, and request-error states identify the blocker and a reachable next action in the main view.
- [ ] Base URL copy gives accessible success/failure feedback; unavailable clipboard has a usable manual fallback.
- [ ] Request status/latency/token information is visible without an advanced disclosure; empty and stale telemetry are explained.
- [ ] No prompt content or raw credentials appear in metrics, persisted fixtures, logs, or screenshots.
- [ ] Keyboard access, three viewport sizes, and focus restoration work; supported protocol claims match the backend.

**Verify:** Run `tests/modelsServingUi.test.mjs` and, if backend behavior changes, `tests.testModelServing`. Exercise a bounded request using an isolated key and test model endpoint. A mock proves wiring and telemetry states, not real-model performance. Key expiry, additional protocols, and broader access remain separate work.

### NC-06 — Put training capability before configuration

**Problem:** A long form asks for original weights and JSONL before users see that the runtime is unavailable; mobile stacking puts the blocker below the form.

**Start in:** [TrainingView.jsx](../frontend-src/src/features/workstation/TrainingView.jsx), [workstation.css](../frontend-src/src/features/workstation/workstation.css), existing training API contracts.

**Implement:** Show capability and blockers before inputs at every viewport. Organize Model → Dataset → Configure → Review within the current capability boundary. Add dataset row count, validation feedback, and bounded preview; keep uncommon parameters in details. Offer a supported native folder picker when available, with a clear manual path fallback. Summarize selected inputs and unresolved checks before Start. Separate current/history runs only if volume warrants it.

**Done when:**

- [ ] Missing runtime, unsupported model input, invalid dataset, ready preflight, active run, failed run, and completed adapter have distinct explanations and next actions.
- [ ] GGUF is identified as an inference format that this worker cannot train; the UI does not claim QLoRA or additional ingestion formats.
- [ ] Editing any validated input invalidates readiness; Start cannot bypass current preflight requirements.
- [ ] Dataset limits and errors are visible before submission; preview is bounded and does not leak examples into logs.
- [ ] Runtime blockers precede the form at 390px; defaults and advanced options remain keyboard accessible.

**Verify:** Run `tests.testTraining` for changed contracts and exercise the state matrix with isolated fixtures. A real successful training run is required only before claiming training capability is certified. Do not install dependencies, alter Unsloth's environment, or bundle a runtime as a side effect.

### NC-07 — Search settings by the control users want

**Problem:** Search filters section names/descriptions rather than actual settings; `theme` returns no matches while the relevant control is present.

**Start in:** [SettingsView.jsx](../frontend-src/src/features/settings/SettingsView.jsx), [GeneralSettings.jsx](../frontend-src/src/features/settings/GeneralSettings.jsx), existing settings metadata.

**Implement:** Maintain a small setting-label/alias index mapped to existing section and control IDs. Results navigate to, focus, and visibly identify the control. Preserve role/Desktop restrictions. Mark immediate preferences versus settings requiring Save consistently.

**Done when:**

- [ ] `theme`, `motion`, `workspace`, and `testing mode` return their real controls; an unknown query has an accurate empty state.
- [ ] Selecting a result opens the owning section and focuses/highlights the control without changing its value.
- [ ] Restricted settings are absent for roles that cannot access them; keyboard search, selection, and clearing work.
- [ ] Dirty state and save requirements remain visible after navigating via search.

**Verify:** Add rendered search-to-control checks alongside `tests/settingsWorkspaceV3.test.mjs` and `tests/settingsUiContract.test.mjs`; test Native Host and Desktop presentation differences explicitly.

### NC-08 — Simplify model discovery

**Problem:** Catalog modes, recommendations, navigation tabs, hardware controls, and storage information compete with finding an appropriate model. Cards expose excessive numeric precision and repeated badges.

**Start in:** [ModelsView.jsx](../frontend-src/src/features/models/ModelsView.jsx), [CatalogCard.jsx](../frontend-src/src/features/models/CatalogCard.jsx), existing discovery inspector and download components.

**Implement:** Establish Discover and On Device as clear model destinations. Present one search entry with explicit curated/remote provenance; preserve source-specific capabilities instead of pretending all sources behave alike. Keep filters/hardware details secondary and storage configuration under details. Lead cards with purpose, readable size, fit, and next action; format `9.197093888B` as a readable value such as `9.2B`, deduplicate badges, and retain precise artifact details in the inspector.

**Done when:**

- [ ] A fresh user can search, select an exact GGUF variant, and understand fit/blockers before downloading.
- [ ] Downloaded, registered, loaded, and reachable states remain distinct; existing library connections/imports stay reachable.
- [ ] Search loading, no results, offline/error, pagination, cancellation, and repeat navigation have accurate feedback.
- [ ] Long names, active downloads, and a populated library remain usable at all three widths.

**Verify:** Run the relevant model catalog/request/fit/recommendation/ecosystem tests, then live-test discovery through selection. Download/load/stop claims require a bounded real lifecycle run and resource-owner verification; screenshots do not establish that lifecycle.

### NC-09 — Expose secondary tools and clarify names

**Problem:** Trials and Artifacts are difficult to discover, and Library can be mistaken for a content collection rather than model inventory.

**Start in:** [DashSidebar.jsx](../frontend-src/src/components/shell/DashSidebar.jsx), [constants.js](../frontend-src/src/lib/constants.js), existing route and access helpers.

**Implement:** Keep primary navigation compact. Add a semantic Tools/More entry for Evaluations (Trials), Artifacts (Archive), and Activity. Use Models/Model Library for model inventory and keep route IDs/back links compatible. Reuse the existing mobile focus/menu behavior.

**Done when:**

- [ ] Each destination is discoverable using mouse or keyboard without knowing a hash route or opening recent-chat history.
- [ ] Existing deep links still work; selection, back navigation, Escape, and focus restoration are correct.
- [ ] Role and runtime visibility matches existing authorization; adding navigation grants no additional access.
- [ ] Sidebar resizing and the mobile overlay continue to work. Chat content/composer layout is unchanged.

**Verify:** Run `tests/sidebarSizing.test.mjs`, relevant shell/access tests, and live navigation across admin/member/viewer presentations. This adopts the reference's separation of model and content jobs without claiming an equivalent Unsloth content library exists.

### NC-10 — Give empty Workspaces a useful next action

**Problem:** Before file selection, a large inspector area provides little guidance; RAG/Graphify terminology obscures the outcome.

**Start in:** [WorkspacesView.jsx](../frontend-src/src/features/workspaces/WorkspacesView.jsx) and its existing knowledge/access hooks.

**Implement:** Use the empty inspector for project overview, current access, indexing state/freshness, and one relevant next action. Prefer task names such as Index project or Explore relationships; keep engine names in details. Preserve file-preview provenance and approved-folder boundaries.

**Done when:**

- [ ] No project, approved unindexed project, indexed project, indexing failure, and selected file each show a clear next action.
- [ ] Actions accurately reflect permissions; no click grants access or trust as an undocumented side effect.
- [ ] Selecting/closing a file preview returns to the correct project state; long paths fit and errors remain actionable.
- [ ] Workspace file navigation preserves keyboard operation and resolves earlier semantic findings before claiming accessibility closure.

**Verify:** Run `tests/workspacesAccessibility.test.mjs` and relevant workspace tests, then use disposable approved folders for browse/preview/index interactions. Never index the user's real project data as a test fixture.

### NC-11 — Standardize non-Chat visual hierarchy

**Problem:** Compact model headers, oversized decorative runtime headers, nested Settings introductions, and dense Trials counters create inconsistent hierarchy.

**Start in:** [RuntimePrimitives.jsx](../frontend-src/src/features/runtime/RuntimePrimitives.jsx), [TrialsView.jsx](../frontend-src/src/features/trials/TrialsView.jsx), Settings and workstation surface styles.

**Implement:** Use one title, short purpose, primary action, and task content per surface. Reduce empty statistic tiles, redundant panels, and background decoration. Apply existing spacing/color/focus tokens and primitives. Make incremental surface changes; avoid a broad CSS rewrite or theme replacement. Record the shared decisions in the existing design documentation, or a scoped design record if none owns them.

**Done when:**

- [ ] Models, API, Training, Scheduled, Workspaces, Trials, Artifacts, Activity, and Settings follow a documented hierarchy with no redundant page introductions.
- [ ] Empty, loading, error, long-content, and populated states are checked in light and dark themes.
- [ ] Measured contrast meets the applicable thresholds; prior October 27/28 contrast failures are explicitly retested, not assumed fixed by token use.
- [ ] Three widths, 200% text zoom, keyboard focus, and OS/explicit reduced-motion preferences remain usable.
- [ ] Each surface change has a scoped commit/revert path. Existing Chat layout and composer remain unchanged.

**Verify:** Run affected theme/UI tests and live visual/interaction checks. Keep screenshots tied to commit, theme, viewport, and data state. Do not mark the earlier contrast, table scrolling, tree semantics, or reduced-motion findings closed without their own evidence.

### NC-12 — Profile and reduce shared frontend cost

**Problem:** Audit build output included 936.66 kB vendor JS, 457.53 kB main JS, 232.77 kB vendor CSS, and 452.73 kB main CSS. Size indicates payload, not measured startup latency.

**Start in:** [vite.config.mjs](../vite.config.mjs), route imports, and affected legacy component/style dependencies. Related earlier finding: October 27 `UI-07`.

**Implement:** Capture initial-route resources and cold/warm navigation under a fixed build, viewport, machine, and data fixture. Then split route-specific dependencies and remove demonstrably unused payload. Migrate legacy components incrementally when touching their owning surface; do not rewrite the entire UI to chase a chunk warning.

**Done when:**

- [ ] Before/after resource inventories record raw/gzip sizes, initial-route requests, and route transitions under the same conditions.
- [ ] A feature-specific dependency outside the initial route is measurably deferred, or a measured bottleneck is reduced; results identify exactly what changed.
- [ ] Repeat timings use at least five comparable runs with median and range reported; no speed claim is made from build size alone.
- [ ] Lazy routes, workers, charts, themes, offline/error handling, and packaged asset loading pass regression checks.
- [ ] Observed timing regressions are investigated before closure; a smaller bundle alone cannot waive a broken or slower workflow.

**Verify:** Production build, affected route/worker tests, source navigation measurements, and packaged asset checks if packaging behavior changes. Set any performance target from the recorded baseline before optimization; do not invent a historical target.

## Verification and closure policy

Use the repository [verification skill](../.agents/skills/verify/SKILL.md). All live checks use an isolated `RASPUTIN_DATA_DIR`, a verified test port, and the supported authentication flow. Keep fixtures, private paths, credentials, and logs outside commits. Inspect process ownership before stopping test or product processes, and clean up only the instances/data created for the check.

Run the relevant gate for each change, rather than every command for every ticket:

```powershell
# Any frontend source change
npm.cmd run build
node --test tests/<relevant-test>.test.mjs

# Backend changes: focused suite plus smoke gate
.\.venv\Scripts\python.exe -m unittest tests.testBackendSmoke

# Desktop lifecycle/asset changes
npm.cmd run desktop:check
npm.cmd run desktop:test

# Documentation updates
.\.venv\Scripts\python.exe scripts\verify_docs.py
```

Named existing tests above are starting points; inspect their current assertions before relying on them. Add behavioral regression coverage for meaningful changed contracts, not source-string tests that merely repeat the implementation. A successful build is not an interaction check. Report failures, skips, fixture boundaries, and pre-existing failures separately.

Use **Planned → In progress → Source verified → Installed verified**. Source completion requires implemented acceptance criteria and recorded evidence. Installed completion requires verification of the built/installed artifact under the separate release workflow. A source-only fix must not be marked installed. If an issue no longer reproduces, record the resolving commit/evidence instead of silently deleting it.

Each closure entry must record:

| Field | Required entry |
| --- | --- |
| Work item / owner | NC ID and implementer |
| Scope / commit | Files, implementation commit, and verified remote branch |
| Before / after | Reproduction and resulting behavior |
| Automated evidence | Exact commands, pass/fail/skip counts, relevant pre-existing failures |
| Live evidence | Runtime owner/type, route, fixture, viewport, theme, actions and outcomes |
| Acceptance | Each criterion passed, or explicitly incomplete with reason |
| Delivery | Source/build/package/install state; no inferred deployment |
| Rollback / limits | Scoped revert, remaining risks and untested states |

Commit and push only scoped changes under the repository policy. Report completion here and reference the same NC ID in the existing engineering checklist/ledger when applicable. Do not rewrite older audit evidence as if it were current verification.

## Tracking

All entries below are initial planning states. Change them only with the closure evidence described above.

| ID | Status | Owner | Implementation / evidence |
| --- | --- | --- | --- |
| NC-01 | Planned | Unassigned | — |
| NC-02 | Planned | Unassigned | — |
| NC-03 | Planned | Unassigned | — |
| NC-04 | Planned | Unassigned | — |
| NC-05 | Planned | Unassigned | — |
| NC-06 | Planned | Unassigned | — |
| NC-07 | Planned | Unassigned | — |
| NC-08 | Planned | Unassigned | — |
| NC-09 | Planned | Unassigned | — |
| NC-10 | Planned | Unassigned | — |
| NC-11 | Planned | Unassigned | — |
| NC-12 | Planned | Unassigned | — |

**TL;DR:** Start with NC-01 labels and NC-03 mobile search. Finish truthful scheduling/readiness in NC-02/04, then improve API, Training, search, discovery, and project workflows. Close each item with behavior and runtime evidence; finish with visual consistency and measured performance work.
