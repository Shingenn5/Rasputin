# Rasputin UI remediation report

**Date:** October 27, 2026 (America/Chicago)

**Status:** PLANNED — findings recorded; fixes have not been implemented or installed

**Basis:** Impeccable technical audit of the source application on `codex/unsloth-workstation-upgrade`, including existing uncommitted changes

## What needs to change

Rasputin needs targeted accessibility, theme, and startup improvements. The most urgent work is making the Library inspector readable in light mode and giving form controls proper accessible names. These problems affect basic use; they should be addressed before cosmetic refinement.

The audit identified **eight grouped issues: five P1 major fixes and three P2 follow-ups**. No P0 task-blocking issue was established in the tested states. The **11/20 audit score** describes the sampled source UI, not release certification.

| Area | Score | Main gap |
| --- | --- | --- |
| Accessibility | 2/4 | Contrast, control names, keyboard scrolling, and tree semantics |
| Performance | 2/4 | Large eager payload; startup timing still needs profiling |
| Theming | 2/4 | Fixed pale text colors fail on light backgrounds |
| Responsive design | 3/4 | Tested pages fit; a local table scroll region lacks keyboard access |
| Implementation integrity | 2/4 | Repeated form omissions and retired deployment claims |

## Prioritized fix list

| ID | Priority | Required outcome | Completion evidence |
| --- | --- | --- | --- |
| UI-01 | P1 | Library inspector remains readable in light and dark themes | Rendered contrast checks for model name, headings, selected tabs, and actions |
| UI-02 | P1 | Shared labels, status text, and primary actions meet contrast requirements | Measured foreground/background pairs on affected routes |
| UI-03 | P1 | Forms expose accurate accessible names | Role/name queries, label activation, and no relevant axe naming violations |
| UI-04 | P1 | Dashboard table can be scrolled with a keyboard | Focus the region and reach the clipped columns without a mouse |
| UI-05 | P1 | Workspace navigation has valid semantics | Correct tree children and verified keyboard selection |
| UI-06 | P2 | Reduced-motion defaults honor the operating system | Fresh-profile and explicit-override checks |
| UI-07 | P2 | Initial route loads only the UI it needs | Before/after cold-launch measurements and resource inventories |
| UI-08 | P2 | Login messaging matches the supported product | Source-host login shows current native-runtime information |

All items remain open. P1 means address before release; P2 means address in the next improvement pass unless further evidence raises the priority.

## UI-01 — Fix Library inspector readability

**Problem and evidence:** In the rendered light theme, the model name measured **1.05:1** contrast, the section heading **1.02:1**, and the selected Overview tab **1.27:1**. The affected text needs at least 4.5:1 at its measured size. The light panel changes correctly, but its fixed pale foregrounds do not.

**Source:** [models-workspace-v3.css](../frontend-src/src/styles/models-workspace-v3.css), especially `.models-inspector-title strong` (audit line 325), the selected inspector tab (334), and section headings (337).

**Required changes:**

- Replace fixed pale foregrounds with semantic text, muted-text, and selected-control tokens that resolve appropriately in each theme.
- Check the complete inspector: model identity, status, tabs, descriptions, connection fields, and action buttons.
- Inspect the hard-coded dropdown option palette around audit line 818 in the actual platform dropdown before deciding how to change it.

**Acceptance:** In light and dark modes, the affected text meets WCAG 1.4.3 contrast thresholds, selected tabs remain identifiable, and connection/edit actions remain usable. Check with a selected model and an error state; an empty library alone cannot prove this fix. Preserve the existing model workflow and layout.

## UI-02 — Correct shared contrast failures

**Problem and evidence:** Dark-theme examples include sidebar “Local AI” at **3.88:1**, “Runtime” at **2.74:1**, the Library description at **3.83:1**, and the Dashboard assistant action at **3.87:1**. Login kicker text measured 4.12:1 and 3.95:1; the local-credentials note measured 3.75:1. These small-text examples fall below 4.5:1. Light-mode shared text also produced failures, so changing only the inspector is insufficient.

**Source:** [DashSidebar.jsx](../frontend-src/src/components/shell/DashSidebar.jsx), [dashboard.css](../frontend-src/src/styles/dashboard.css), [interface.css](../frontend-src/src/styles/interface.css), [theme.css](../frontend-src/src/styles/theme.css), and [LoginShell.jsx](../frontend-src/src/features/auth/LoginShell.jsx).

**Required changes:**

- Define readable foreground/background pairs for muted text, small labels, statuses, and primary actions.
- Review opacity-based text styles against their actual composited backgrounds.
- Repair the owning token or component rule rather than adding unrelated overrides to every page.

**Acceptance:** Recheck the named failures in both themes and inspect hover, selected, and focus states. Relevant axe contrast violations should be cleared; incomplete checks require manual assessment. Disabled-control exceptions must not be used to dismiss failures on enabled actions. Keep the current visual identity and semantic status distinctions.

## UI-03 — Connect visible labels to form controls

**Problem and evidence:** Several forms display labels that are not programmatically associated with the corresponding control. Visual proximity does not create an accessible name.

| Surface | Controls needing changes | Source |
| --- | --- | --- |
| General Settings | Theme, language, and motion selects; Markdown Formatting and Testing Mode switches; workspace path label association | [GeneralSettings.jsx](../frontend-src/src/features/settings/GeneralSettings.jsx) |
| Skills | Session selector | [SkillsView.jsx](../frontend-src/src/features/runtime/SkillsView.jsx) |
| Scheduled tasks | Interval input and enabled switch; associate Name and Prompt labels rather than relying on placeholders | [SchedulesView.jsx](../frontend-src/src/features/runtime/SchedulesView.jsx) |
| Model Hub | Page-size selector once catalog results appear | [ModelsView.jsx](../frontend-src/src/features/models/ModelsView.jsx), [ModelCatalogRows.jsx](../frontend-src/src/features/models/ModelCatalogRows.jsx) |

**Required changes:** Give controls stable IDs and connect labels with `htmlFor` or React Bootstrap `controlId`. Give switches explicit names. Label pagination “Models per page” or equivalent clear wording. Inspect both pagination implementations, even though the measured violation came from the native pagination path.

**Acceptance:** Each control can be located by its role and meaningful accessible name. Clicking its visible label focuses or toggles it as appropriate. Values and checked states remain exposed. Re-run the forms with `label` and `select-name` checks and manually inspect names that axe accepted only because a placeholder existed. Do not change settings persistence or task scheduling behavior as part of this wiring fix.

## UI-04 — Make Dashboard table scrolling keyboard accessible

**Problem and evidence:** At 390 CSS px, the scroll wrapper measured **236 px** wide around **440 px** content. It had `tabIndex = -1` and no focusable descendants. Axe reported `scrollable-region-focusable` at 390 and 768 px. Page-level overflow was zero, but local clipped content still needs a usable keyboard path.

**Source:** [DashboardView.jsx](../frontend-src/src/features/dashboard/DashboardView.jsx), the `.overflow-x-auto` table wrapper around audit line 350.

**Required changes:** Add an accessible name, an appropriate tab stop, and a visible focus indicator to the scroll region. Retain the table's row and column semantics.

**Acceptance:** At 390 and 768 px, a keyboard user can focus the region, scroll to the clipped columns, and leave it with Tab. Mouse scrolling still works. There is no new page-level overflow. Test the actual scrolling interaction; fitting the page into a screenshot is insufficient.

## UI-05 — Repair Workspace tree structure

**Problem and evidence:** The “Approved workspace folders” tree contains ordinary “Open Project” action-button content alongside `treeitem` children. Axe reported `aria-required-children` at all tested widths.

**Source:** [WorkspacesView.jsx](../frontend-src/src/features/workspaces/WorkspacesView.jsx), tree around audit line 397 and action around 422.

**Required changes:** Move the action outside the tree and keep its relationship to approved folders clear. Review the empty state and keyboard handling. If the control is simply a flat collection of actions, consider whether a list of buttons expresses its behavior more accurately than a tree; choose based on the interaction it actually supports.

**Acceptance:** No disallowed direct children remain. Verify empty and populated folders, selected state, opening a folder, and keyboard focus movement. Preserve workspace approvals, membership checks, and folder-selection behavior.

## UI-06 — Honor OS reduced-motion preferences

**Problem and evidence:** With `prefers-reduced-motion: reduce` emulated, a fresh app profile still used `data-motion="full"`. Skills retained decorative pulse/orbit and surface-reveal animations. Several safeguards respond only to the app-specific attribute.

**Source:** [motion.js](../frontend-src/src/lib/motion.js), [App.jsx](../frontend-src/src/app/App.jsx), and [interface.css](../frontend-src/src/styles/interface.css).

**Required changes:** Use the OS preference when there is no explicit app override. Distinguish an absent preference from an explicit choice of full motion. Keep the setting understandable and persistent. Replace decorative movement with a static alternative while retaining useful state and progress feedback.

**Acceptance:** Verify four combinations: fresh profile with OS reduce, fresh profile with OS full, explicit app reduce with OS full, and explicit app full with OS reduce. Reload and confirm the intended preference persists. Test visible pulse/orbit components, not only sidebar transitions. This finding is a preference-handling defect; it is not a blanket claim that every animation violates WCAG AA.

## UI-07 — Profile and reduce eager startup payload

**Problem and evidence:** Build output included **936.66 kB vendor JavaScript** (281.62 kB gzip), **457.86 kB app JavaScript** (121.99 kB gzip), **452.50 kB main CSS**, and **232.77 kB vendor CSS**. Shared model, task, workspace, runtime, and preview chunks were fetched. Most views are statically imported; API and Training already use `React.lazy`.

**Source:** [App.jsx](../frontend-src/src/app/App.jsx) and [vite.config.mjs](../vite.config.mjs).

**Required changes:** Establish a cold-launch baseline, identify costly secondary routes, and extend the existing lazy-loading pattern where measurements justify it. Inspect the single vendor grouping and unused route styles. Investigate the Pyodide browser-externalization warnings separately if the corresponding feature fails; a build warning alone is not proof of a broken feature.

**Acceptance:** Record before/after initial-route bytes, requested resources, and repeated cold-launch timing under the same conditions. Secondary views still open and render with clear loading/error behavior. The build passes. No new dependencies are needed merely to defer an existing import. Do not claim a speed improvement from a smaller bundle without measuring the affected startup path.

## UI-08 — Remove retired deployment claims from login

**Problem and evidence:** The source Native Host login advertises “Docker server” and deployment “as infrastructure,” contradicting the current Windows-native product direction.

**Source:** [LoginShell.jsx](../frontend-src/src/features/auth/LoginShell.jsx), the login-principles content around audit line 35.

**Required changes:** Replace that claim with accurate information about the supported source Native Host and local-account workflow. Check adjacent recovery text against [DEPLOYMENT_MATRIX.md](DEPLOYMENT_MATRIX.md). Preserve the distinction between source-host authentication and the installed Desktop's local session.

**Acceptance:** The source login accurately describes supported operation and recovery without recommending retired infrastructure. Authentication and recovery behavior remain unchanged. Verify the rendered source-host screen; the installed Desktop normally follows a different entry path.

## Implementation order and verification

1. **Readability:** Complete UI-01 and UI-02 together so shared tokens and inspector overrides agree.
2. **Accessibility:** Complete UI-03, UI-04, and UI-05 with focused interaction tests.
3. **Motion and copy:** Complete UI-06 and UI-08 without changing runtime ownership or authentication.
4. **Performance:** Profile UI-07, implement only justified changes, and compare measurements.
5. **Closure:** Run a final polish pass and repeat the audit against the resulting source build. Verify the packaged and installed application separately before claiming installed fixes.

For UI changes, follow the [verification skill](../.agents/skills/verify/SKILL.md): use an isolated data directory and test port, authenticate through the supported flow, and clean up the test process and data. Preserve the Chat layout and composer pill. Any layout change outside Chat needs the repository's rollback and live responsive verification safeguards.

Relevant gates are the frontend build, focused JavaScript/UI regressions, and the live checks listed for each item. Desktop syntax/lifecycle checks apply if the Electron shell changes. Backend smoke tests apply if backend behavior changes. Run the documentation validator when updating this report. Source, packaged, installed, and clean-machine evidence are separate outcomes.

## Evidence, limits, and changes to avoid

The prior audit passed the frontend build and retained **48 route/theme/viewport scans** across 12 routes: dark mode at 1440, 768, and 390 px, plus full light-theme application at desktop width. Login was checked separately. Five routes received 320 px reflow checks; General Settings received a 200% root-font-size check. None of those checks measured page-level horizontal overflow. Root-font scaling is not a complete browser-zoom audit.

Command-palette initial focus, Shift+Tab containment, Escape close, and asynchronous focus restoration passed. Mobile sidebar Escape handling passed. No uncaught page errors were recorded. Preserve those behaviors.

The audit used headless Chromium, axe-core 4.10.3, and a fresh authenticated source runtime. Some catalog data arrived asynchronously, so early loading-state scans did not cover every populated control. Findings describe the working tree at the time of the audit, including changes that were not committed; a repository commit alone cannot reproduce that exact application state.

The installed Electron app, native window controls, physical touch, screen-reader output, every theme, every modal, populated task/chat histories, model lifecycle, cold-launch latency, and frame rate were not certified. A fresh manual verification is required before closing findings after concurrent source changes.

The completed CSS detector produced **13 matches**: ten side-tab borders, two decorative grid backgrounds, and one gradient-text match. These are not thirteen additional defects. The gradient belongs to a Google publisher mark; borders can indicate status or selection; grid backgrounds are stylistic advisories. Do not remove them wholesale. Compact controls and visually hidden file inputs also need exception/spacing checks before being called target-size failures.

Session-local evidence consisted of `audit-evidence.json` (dark records), `supplement-evidence.json` (complete light-theme application and supplemental checks), `keyboard-evidence.json`, `detector.json`, and screenshot captures. Raw test output and runtime data are not part of this repository report. The measurements and source locations above make the required work reviewable without publishing machine-specific paths or credentials.

**TL;DR:** Fix light-mode readability, shared contrast, form labels, keyboard scrolling, and Workspace semantics first. Follow with OS motion preferences, measured startup optimization, and accurate login copy. Recheck the source build and installed product separately before marking the work complete.
