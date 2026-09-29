# Rasputin user testing and improvement playbook

Version: 2026-09-08. Status: reusable execution guide; the full campaign has not yet run.

## Purpose

When Elliott asks Codex to use Rasputin, act like an ordinary user: navigate the installed
application, make choices from its UI, complete useful work, and check the result. Find the
weakest interactions, reproduce them, and, when asked to test and improve, implement and
verify focused fixes. A successful click is not a successful feature.

This guide defines a full campaign, not a claim that every existing control has already been
enumerated or tested. Build a fresh inventory against the selected build each time. It is
subordinate to [AGENTS.md](../AGENTS.md), current user authorization, and the
active tool permissions.

## How to invoke this guide

For the complete campaign:

> Use docs/RASPUTIN_USER_TESTING_PLAYBOOK.md. Run a full user-level audit of Rasputin with
> Computer Use, inventory every reachable button and dropdown, complete the model and chat
> journeys, find the weakest workflows, and implement and verify focused improvements.
> Use disposable test data for destructive and failure scenarios. Keep a coverage ledger and
> report what passed, failed, was fixed, or remains blocked. Do not publish or update my
> installed copy unless I explicitly authorize that step.

For observation only:

> Follow the playbook in audit-only mode. Use the app and report reproducible defects without
> editing the implementation.

For a targeted pass:

> Follow the playbook for Discover Models and My Models, including every dropdown option,
> download controls, responsive layouts, keyboard navigation, and a complete model lifecycle.

For continuation:

> Resume the latest campaign ledger, recheck the app build, and continue the unfinished tests
> and fixes. Preserve earlier evidence and retest anything affected by new changes.

Writing this guide does not start the campaign. A later test-and-improve request authorizes
normal scoped source fixes and isolated verification, but does not automatically authorize
publishing, changes to real user data, or changes to security policy.

## Working method

1. Establish the target build and safe test environment.
2. Explore as a new user before using implementation knowledge to explain the UI.
3. Build the control and state inventory; reconcile it against current source routes.
4. Complete end-to-end journeys, then exercise controls and their alternate states.
5. Test responsive behavior, keyboard access, feedback, persistence, and recovery.
6. Rank failures by user impact and recurrence; reproduce the highest-impact issues.
7. Implement small coherent fixes when authorized and verify the original failure again.
8. Reconcile coverage, deliver evidence and remaining gaps, and clean up owned test resources.

Computer Use is the primary evidence for installed Windows interactions. Use the current
Computer Use skill: select an actual returned Rasputin window, observe, perform one
state-dependent action, and refresh. Never reuse stale coordinates or element indexes.
Do not operate Codex itself, authentication prompts, security settings, or terminals through
Computer Use. If a tool prohibits an interaction, record it as blocked for that tool and use
an allowed isolated test or explicit user handoff; do not bypass the restriction.

Code, logs, API checks, and Playwright explain failures and strengthen regression tests. They
must not silently replace the user journey or be reported as installed-window evidence.

## Environment and evidence boundaries

| Target | Purpose | What its evidence proves |
| --- | --- | --- |
| Installed Windows Desktop | Primary daily-driver UX and native window interactions | Behavior of the identified installed build |
| Isolated source Native Host | Controlled fixtures, debugging, responsive browser tests | Source behavior with real Native Host authentication |
| Isolated packaged Desktop | Packaged backend/frontend and lifecycle regression | Behavior of the tested package with separate data |
| Clean Windows profile or machine | First installation, prerequisites, upgrade/recovery | Only the specifically exercised clean-environment scenarios |

Record app version, executable identity, source branch/commit and dirty status when relevant,
runtime owner, dataset, model identity, hardware, window dimensions, Windows scaling, theme,
and test time. Store sensitive details only in private scratch evidence; redact shared reports.
Source and installed binaries may differ. A source fix does not update the installed app.

Use the installed app for authorized ordinary workflows. Use a separate data directory and
disposable project for destructive, invalid-input, failure-injection, and recovery scenarios.
Follow [the local verification workflow](../.agents/skills/verify/SKILL.md), identify
`desktop-runtime.json` or `native-host.json` ownership, and never run two instances against
one data directory. Do not restart a process merely because its port looks familiar.

Fixture set: an empty project, a small disposable Git project with a known test failure,
long filenames and Unicode text, a few harmless attachment files, empty and populated chat
history, a small real GGUF model, and controlled unavailable/slow model endpoints. Keep mocks
explicitly labeled. A mock response never certifies real local model capability.

At startup, test tool availability separately from Rasputin. If shell or Computer Use fails
before reaching the app, record a harness blocker. The September 8 zero-filled Codex sandbox
state file was such a blocker; it was not a Rasputin defect. Do not turn its one-time recovery
into an automatic permission reset or file-deletion routine.

## What "every button and dropdown" means

Create one stable inventory ID per control location and meaningful behavior, such as
`DISCOVER.SEARCH.SUBMIT` or `MODELS.LOAD.PLACEMENT`. A shared label in two locations is two
inventory entries until both paths have been exercised. Runtime accessibility indexes are
not stable inventory IDs.

Discover controls by opening every navigation section, tab, drawer, modal, overflow menu,
accordion, context menu, empty state, and advanced panel. Include icon-only actions, links,
toggles, sliders, file pickers, row actions, pagination, splitters, keyboard shortcuts, and
controls revealed only while work is busy or failing. Reconcile the live inventory with
rendered source branches, role restrictions, runtime variants, and feature gates.

For every control, record:

| Field | Required record |
| --- | --- |
| Identity | Stable ID, visible name, type, location, build/environment |
| Reachability | Exact navigation path, prerequisites, role/runtime/feature conditions |
| Exercise | Input, selected option, initial state, action sequence |
| Expected | Visible feedback plus actual state or artifact expected |
| Observed | Actual result, persistence/reopen result, timing if relevant |
| Evidence | Screenshot/state reference and, when useful, task or request identifier |
| Disposition | Not run, passed, failed, blocked, or not applicable; reason and defect ID |

For each dropdown, enumerate every fixed option and select each supported option in an
isolated fixture. Verify selected label, downstream behavior, persistence, keyboard access,
and default restoration. For unbounded data lists such as model IDs, inventory the options
present in the test dataset and exercise representative classes: healthy, unavailable,
incompatible, long-name, and newly added/removed items. Do not claim every possible model
was tested. Exercise boundary values for numeric fields and sliders.

Test normal, empty, loading, disabled, error, cancelled, and completed states where relevant.
Check hover/focus affordances, repeat clicks, cancel without mutation, navigation away/back,
and refresh or relaunch persistence. Inapplicable states need an explicit reason.

Coverage is finite and reported against the inventoried build:

- Control execution coverage = distinct controls exercised / all in-scope controls inventoried.
- Case execution coverage = (passed + failed) cases / all applicable planned cases.
- Pass rate = passed cases / (passed + failed) cases.
- Report blocked and not-run counts separately; do not remove them to inflate completion.
- Record excluded surfaces and reasons. An inaccessible control is blocked, not passed.
- Retest affected controls when fixes add options or change reachability; update the denominator.

One successful option does not pass the whole dropdown. Use pairwise combinations for
independent settings, plus every known high-risk combination; do not claim exhaustive testing
of an unlimited Cartesian product.

## Campaign coverage map

These are seed areas from current source and the observed installed UI. They are not a frozen
control count. Add newly discovered controls and distinguish hidden legacy surfaces from
supported product features.

| Area | Controls and journeys | Acceptance focus |
| --- | --- | --- |
| Startup and shell | Launch, close/reopen, minimize/restore/maximize, sidebar collapse, navigation, project switching, status indicators | App usable without developer tools; correct active context; preserved state; no orphaned owned runtime |
| First use | No model, no project, find/choose model, import/download guidance, testing-mode guidance | Clear next step; setup action lands in the appropriate workflow; simulated mode is unmistakable |
| Discover Models | Browse/Search, text/ID/URL search, clear/no matches, type/sort/fit filters, pagination/page size, hardware details, row/inspector selection, Info/Files/Fit/Source tabs | Accurate identity and ordering; filter refresh; page/scroll reset; no stale inspector or result set |
| Model acquisition | Variant/quantization choice, file size/destination, Download, progress, Pause/Resume/Stop, retry, import picker and cancel | Exact artifact identifiable before transfer; progress truthful; no duplicate jobs; verified artifact registered once |
| My Models | All/library filters, search, My Models/Loaded/Serving/Developer tabs when present, row menus, details, Manage and Use in New Chat | Downloaded/registered/reachable/loaded counts have consistent definitions; correct item selected |
| Model loading | Load/Cancel, basic/advanced controls, automatic placement, CPU/hybrid/GPU, context and cache options, fit blockers, Stop | Settings reach runtime; viable defaults; clear unsupported choices; resources released by Stop |
| Chat | New Chat, composer, Send/Enter, multiline, model/mode/reasoning/memory dropdowns, attachments, recipes, command menu, stop/queue/retry and response actions where present | Visible response and terminal task state; routing stays correct; drafts and attachments behave predictably |
| Projects | Open Project/file picker, Manage, refresh, selection, tree/breadcrumbs, search, indexing/graph, role-model defaults and validation settings where exposed | Correct project identity and file results; no cross-project leakage; user can complete picker/cancel flows |
| Recent chats/activity | List/search/filter/sort, select/reopen, title and row actions, archive/delete confirmation where present, task details | Correct conversation restored; streaming/history agree; destructive actions bounded to fixtures |
| Settings | Every visible section and control, save/cancel/reset where exposed, validation and persistence | Applied settings match UI; failed saves are visible; switching sections does not inject or retain unrelated filter text |
| Connections and MCP | Setup/test/status, registration and lifecycle options, tool discovery, unavailable connection, allowed fixture calls | Setup produces a useful result or clear blocker; no false connected state; approval boundaries respected |
| Assistant and extended tools | Assistant, agents, sessions, approvals, memory, skills, schedules, trials, archive and audit where reachable | Inventory runtime-specific availability; complete supported flows; label blocked or retained-only surfaces honestly |
| Help and diagnostics | About/version, help/source links, diagnostics/export where exposed, errors and notifications | Correct destinations/build identity, useful redacted evidence, no dead actions |

Installed Desktop currently limits Settings to General, Model defaults, Connections, MCP
servers, Runtime, Hardware, Security, and About. Source Native Host exposes additional
sections depending on role. Inspect current [SettingsView.jsx](../frontend-src/src/features/settings/SettingsView.jsx)
and [App.jsx](../frontend-src/src/app/App.jsx) at execution time. A source file or route alone
does not prove a supported installed feature. Record retired routes as exclusions or accidental
exposure defects; do not revive retired infrastructure to satisfy coverage.

## End-to-end missions

### A. A new user gets a working local model

Start with an isolated empty library. Discover a hardware-fitting GGUF, inspect identity,
variant and size, download, verify registration, load using defaults, send a harmless prompt,
observe a real response and completed task, then stop the model. Reopen the app and confirm
the artifact remains available without unnecessary redownload. Repeat import with a known
local fixture and cancel the file picker once.

Acceptance: every transition is understandable; model identity remains consistent; the
downloaded artifact and running model match; errors provide a next action. A tiny model proves
the lifecycle, not coding quality. Track wall-clock download/load/first-token/completion times.

### B. A returning user completes normal work

Open a disposable project, ask for a summary grounded in its files, follow a cited file,
attach harmless text, send a follow-up, stop one generation, and reopen the chat from history.
Switch projects and verify drafts/history/context follow their intended scope. Test each
exposed mode and ensure unsupported tool-dependent modes are blocked before waiting for a run.

Acceptance: useful result, correct project/model/mode, working cancellation and history,
readable output, and no claim that a tool ran when it did not.

### C. A coding user fixes a real fixture bug

Use a fitting tool-capable model and a disposable repository with a known failing test.
Request a bounded fix through Rasputin. Observe inspect -> edit -> test -> repair if needed ->
diff review. Confirm the actual file change and test result independently. Keep commit/push
outside the mission unless explicitly authorized. If the native validation runner or a needed
tool is unavailable, record the blocker; do not substitute a mocked success.

Acceptance: the original failure is fixed, a meaningful test passes, unrelated files remain
unchanged, and approvals/workspace boundaries hold. Read the threat model before related fixes.

### D. A user recovers from an interrupted operation

With isolated fixtures, test cancelled/failed download, invalid GGUF, unreachable model,
slow response, invalid setting, and app relaunch after completed work. Inject failures through
controlled endpoints or owned test processes; do not interrupt the user's network, kill an
unrelated process, fill the real disk, or intentionally exhaust the workstation.

Acceptance: no permanent spinner, misleading success, duplicate registration, or lost recovery
action. Retry is bounded and understandable. A partial download is never offered as healthy.

### E. A user manages configuration and integrations

Change each permitted ordinary setting in isolated data, reopen its page, and relaunch to
check persistence; restore the baseline. Test a local fixture connection and each exposed
MCP status/action. Authentication, security-setting changes, external messages, scheduling,
and deletion follow current tool restrictions and user authorization. Record user-assisted
checks separately from autonomous checks.

## Responsive layout and accessibility pass

Record physical window size, effective content size, display scaling, and zoom separately.
Use native-window resizing for installed evidence. Browser viewport emulation is supplemental;
it does not prove Windows DPI or Electron title-bar behavior. Windows scaling changes require
an allowed operator action; record unsupported configurations as untested.

| Configuration | Required inspection |
| --- | --- |
| Large desktop, e.g. 1920 x 1080 at 100% | Does content use available space? Are table and inspector proportions sensible? |
| Laptop, e.g. 1366 x 768 at 100% | Can primary actions and dialog footers be reached? Is vertical space dominated by headers? |
| Windows 125%, 150%, 200% where available | Clipping, effective minimum size, readable labels, icons, popovers and pointer alignment |
| Narrow restored window and minimum supported size | Panel reflow, sidebar behavior, intentional internal scrolling, no inaccessible actions |
| Source browser widths 1440, 1024, 768, 390 | Supplemental reflow; phone width is stress evidence, not a promise of mobile Desktop support |
| Short window; browser 200% zoom where supported | Dialog and dropdown reachability, usable reading order, no lost close/submit controls |
| Available themes and reduced motion | Contrast, focus visibility, disabled states, status distinction, restrained animation |

Open each dialog near viewport edges; test longest model names, dense lists, empty results,
expanded advanced settings, errors, tooltips, and a download in progress. Check nested scroll
traps, sticky overlays hiding content, layout shifts and offscreen menus. Preserve the Chat
layout and composer pill; improve components in place. Non-Chat layout fixes need an easy
rollback and responsive verification.

Complete the primary journeys with keyboard only as well as mouse only. Check Tab/Shift+Tab,
Enter/Space, dropdown arrow navigation, Escape, visible focus, accessible names, semantic
tabs, modal focus containment and restoration, and status announcements. Use accessibility
inspection plus a screen-reader pass when available; otherwise mark that evidence missing.
Do not require hover to discover the only path to an action. Treat a 44 x 44 CSS-pixel target
as a usability goal, not an unsupported claim of formal accessibility certification.

## Reliability, feedback, and perceived speed

For local actions, target visible acknowledgement within 200 ms and flag repeated delays over
500 ms for investigation. These are proposed UX targets, not measured current performance.
For long work, distinguish acknowledgement, start, progress, and completion. Show bounded
loading, cancel/retry where meaningful, and an actionable error when dependencies fail.

Measure at least three comparable repetitions for suspected latency defects. Record workload,
cold/warm state and hardware contention. Keep network download speed separate from UI
responsiveness. Check rapid repeat clicks, switching tabs during work, stale filters, reopening
dialogs, duplicate tasks, and mismatches between toast, counter, list, and backend outcome.

## Initial hypotheses from the September 8 walkthrough

The installed app successfully downloaded Unsloth Qwen3-1.7B-Q4_K_M.gguf (about 1.03 GB).
Computer Use verified navigation, download progress and the final Downloaded state. Loading,
inference, resizing, keyboard-only use and the full inventory were not tested in that session.
The following are reproduction targets, not confirmed root causes or approved redesigns:

| ID | Observation | Next check and candidate improvement |
| --- | --- | --- |
| UX-001 | Large window, relatively small Discover modal, few visible model rows | Measure usable content at multiple sizes; consider adaptive modal dimensions or a maximizable view |
| UX-002 | Cached locally showed 0 while the downloaded list showed 3 | Trace each counter's definition; align values or clarify different concepts |
| UX-003 | Row Download immediately acquired an automatically selected variant | Confirm file/quantization/size visibility before click; make defaults explicit without adding needless steps |
| UX-004 | Important model/repository identifiers were truncated | Check wrap, tooltip, focus and resizable inspector behavior |
| UX-005 | Progress panel displaced the result list | Test stable reserved space or a compact download tray |
| UX-006 | Some small embedding models said Will not fit; embedding purpose showed Coding | Inspect metadata and fit inputs; validate intended workload/support before changing labels |
| UX-007 | Setup Find a model opened My Models | Verify first-use routing; choose the destination or label that matches user intent |

## Defects, prioritization, and improvement loop

Use P0 for data loss or a security boundary failure, P1 for a blocked core journey, P2 for
significant friction or misleading state, and P3 for polish. Include frequency, affected users,
workaround, evidence confidence, dependency and repair cost. Repeated failures across several
journeys outrank an isolated cosmetic problem. Keep reproducible observations separate from
suspected causes and design proposals.

Each defect record must include: ID/title, build/environment, starting state, minimal steps,
expected versus actual result, evidence reference, repeatability, severity, likely owning
component, proposed fix, acceptance test, and status. Use Open -> Reproduced -> Implemented ->
Source verified -> Package/installed verified as applicable. Reopen if the original case fails.

When authorized to improve:

1. Reproduce before editing; inspect source and relevant tests to establish the cause.
2. Choose the smallest coherent repair, preserving unrelated dirty-worktree changes.
3. Edit frontend source only in `frontend-src/`; rebuild generated assets with `npm.cmd run build`.
4. Add meaningful regression tests for behavior, state or data contracts. Do not add tests
   that merely restate cosmetic implementation details.
5. Replay the original UI failure and adjacent paths, including responsive/keyboard states.
6. For backend changes run focused tests and the required smoke gate; for desktop changes run
   `npm.cmd run desktop:check` and `npm.cmd run desktop:test`. Follow current verification policy.
7. Record source-only fixes honestly. Updating the installed application is a distinct,
   explicitly authorized packaging/install step with owner verification and rollback.

Consult [verification instructions](../.agents/skills/verify/SKILL.md) before launching tests.
Use `.venv\Scripts\python.exe`, isolated data, and relevant current suites. Existing files such
as `tests/ui/modelEcosystem.spec.mjs` and `tests/ui/integrationSetup.spec.mjs` are candidates;
inspect their assumptions first. Legacy harnesses or stale tests do not define product behavior.

## Campaign records and completion gates

Keep raw screenshots/logs in the session scratch directory. Maintain a sanitized campaign
report in `docs/reviews/` when requested, with a private evidence-location reference as needed.
Never commit real chat contents, model weights, credentials, or runtime data.

The campaign record contains:

1. Environment/build manifest and fixture ownership.
2. Control inventory, planned state/option cases and coverage totals.
3. Journey results and timing observations.
4. Responsive/keyboard matrix and evidence references.
5. Ranked defect register, implemented changes and regression results.
6. Explicit exclusions, blocked/user-assisted checks, cleanup and resume checkpoint.

Use a compact ledger row:

```text
Case ID | Control ID | Build/target | State/option | Expected | Actual |
Status | Evidence | Defect ID | Retest build/result
```

Checkpoint after each major surface and fix batch. Before resuming, compare build identities,
restore the documented fixture state, and invalidate evidence affected by intervening changes.
Do not repeatedly redo completed unrelated checks.

The full campaign is complete only when every in-scope inventoried control and applicable
option/state case has a disposition, all required missions have results, and all blockers and
exclusions are visible. Full coverage is not the same as a passing release gate. A release-ready
recommendation additionally requires passing core real-model journeys, no unresolved P0/P1,
and verified fixes in the intended delivery artifact. Unavailable hardware, permissions,
screen-reader or clean-machine tests remain explicit gaps; never report them as passed.

Finish with the weakest workflows, changes made, evidence-backed coverage counts, outstanding
defects and installation boundary. Restore altered ordinary fixture settings and stop owned
test processes. Inventory downloaded artifacts and test data; obtain any required deletion
confirmation rather than silently removing them. Leave the user's live model/session state
as agreed and report any remaining resource use.
