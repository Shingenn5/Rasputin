# Rasputin Fresh-User Release-Gate Report

> Historical evidence only. This report records an earlier server-era revision and is not current setup or deployment advice. The current product is Windows native with GGUF/llama.cpp. Follow [native deployment](DEPLOYMENT_MATRIX.md); obsolete runtime blockers and commands below do not apply to current model loading.

**Assessment date:** 2026-08-18
**Assessed revision:** 07f796f9289bdb903da36a2ba2ceee7e0d0ebf02 (codex/coding-safety-upgrades)
**Assessment type:** independent, read-only fresh-user acceptance audit
**Primary environment:** isolated native instance on http://127.0.0.1:8904 with a new data directory and fresh browser context
**Deployment smoke checks:** rebuilt native :8788 and Docker :8787

## Executive conclusion

Rasputin's main first-user journey is functional and substantially more understandable than the prior implementation. A new operator can log in, recover from having no configured model, use Testing Mode safely, inspect model choices, configure a workspace, understand task identity, review completed activity, and navigate the main surfaces without insider knowledge.

No P0 failure was found. The audit originally found one P1 request/notification loop and one P2 misleading hardware-readiness state. Both defects have now been fixed, regression-tested, and independently re-verified in a fresh browser against a second isolated native instance.

**Release-gate outcome: PASS FOR THE AUDITED FRESH-USER SCOPE. Real-model deployment and inference remain separately unverified.**

## Evidence boundaries

This report distinguishes these evidence levels:

- **Live verified:** driven in a fresh browser against the isolated running application.
- **Rebuilt-instance smoke verified:** logged-out native and Docker entry pages and health endpoints responded successfully.
- **Code-grounded cause:** observed behavior is directly explained by current source.
- **Unverified:** intentionally excluded because the audit was read-only or required a real installed model.

The audit did not alter source, deploy a model, confirm destructive settings reset, or touch the real native/Docker application data.

## Release scorecard

| Area | Outcome | Evidence |
| --- | --- | --- |
| Fresh login and first-run entry | Pass | Live verified |
| No-model recovery and Testing Mode | Pass | Live verified |
| Chat completion and runtime identity | Pass | Live verified |
| Workspace setup and recheck | Pass | Live verified |
| Guided Models experience and catalog browsing | Pass; P2 fixed and re-verified | Live verified |
| Settings safety | Pass | Live verified without confirming destructive actions |
| Activity and task details | Pass | Live verified |
| Assistant preview and safety blocking | Pass | Live verified |
| WarSat safety and navigation | Pass; P1 fixed and re-verified | Live verified and regression-tested |
| Keyboard navigation | Pass for audited core paths | Live verified |
| 1024 px responsiveness | Pass with minor cramped overlays | Live verified |
| Native/Docker rebuilt entry pages | Pass | Smoke verified |
| Real-model install, deployment, inference, and benchmark | Not verified | Outside read-only audit scope |

## Findings

### Resolved P1 - WarSat could create a sustained model-catalog request and toast storm

**Observed interaction**

1. Log in to the fresh instance.
2. Open WarSat after visiting Assistant/Models.
3. Leave the page open while inspecting Safety and the 1024 px layout.

**Observed result**

- /api/model-catalog?fit=true repeated continuously.
- Browser network entries 56 through 276 contained 221 repeated successful GET requests over approximately four minutes.
- Each completed cycle emitted another "Model catalog loaded." notification.
- Four duplicate success notifications were visibly stacked at 1024 px.
- Requests returned HTTP 200 and the browser reported zero console errors, so ordinary error monitoring does not expose the defect.

**Impact**

- Unnecessary backend work, CPU use, network traffic, and log volume.
- Persistent notification noise that obscures meaningful status.
- Risk of degraded local-workstation performance while model runtimes are active.
- A successful response loop can evade health and error alarms.

**Confirmed code-grounded cause**

- frontend-src/src/features/warsat/WarsatView.jsx:271-275 calls loadModelCatalog whenever WarSat is active, the catalog contains no items, and loading is false.
- The effect includes loadModelCatalog in its dependency list.
- frontend-src/src/app/App.jsx:585-604 defines loadModelCatalog as a normal function inside App, so it receives a new identity on every render.
- When the backend legitimately returns an empty catalog, the condition remains true. Loading-state changes render App again, the callback dependency changes, and the effect starts another request.
- loadModelCatalog emits "Model catalog loaded." after every non-refresh request, converting the request loop into a toast loop.

**Required remediation**

1. Memoize loadModelCatalog with useCallback or remove unstable callback identity from the effect contract.
2. Add an in-flight/request-generation guard so only one catalog request can be active.
3. Treat an empty catalog response as a valid terminal state, not an automatic retry signal.
4. Abort or ignore superseded work on unmount or route change.
5. Show success notifications only for deliberate user refreshes or meaningful state transitions.
6. If automatic retry is required, use bounded retries and backoff with visible status.

**Acceptance outcome**

On a fresh WarSat route with an empty catalog, no user interaction, and a 60-second observation window:

- at most one GET /api/model-catalog?fit=true occurs;
- no catalog requests overlap;
- at most one catalog success notification appears;
- leaving and returning does not reuse abandoned work or create an unbounded loop;
- the empty catalog displays a stable explanation and next action.

**Resolution and re-verification**

- The shared catalog loader now has stable callback identity, in-flight request deduplication, and a one-shot automatic-attempt guard.
- A successful empty response is terminal, automatic loads are silent, and only deliberate loads or refreshes produce success notifications.
- WarSat uses the guarded automatic-load contract rather than retriggering on each render.
- Focused regression tests cover automatic-load stability, in-flight deduplication, and explicit notification behavior.
- In a fresh browser on isolated native :8905, the WarSat route produced exactly one successful catalog GET and zero automatic success toasts over more than 60 seconds. Navigating away and returning produced no second request or late repeat.

### Resolved P2 - Models reported that it was waiting for hardware after the snapshot arrived

**Observed interaction**

1. Open Models -> Library -> Recommended for this computer.
2. Allow hardware detection to complete.

**Observed result**

- /api/warsat/hardware returned HTTP 200 with detected hardware and a capability profile.
- Deployment remained blocked because Docker control was disabled and the model folder was empty.
- The UI continued to display "Waiting for a hardware snapshot before requesting recommendations..." and "No profile is available yet."
- Browse-all catalog controls remained usable.

**Impact**

- Detection appears hung when it has completed.
- The operator is not told which prerequisite to fix.
- A valid safety block looks like an application failure.

**Confirmed code-grounded cause**

- frontend-src/src/features/models/ModelsView.jsx:555-559 assigns the generic waiting advisor state when either the catalog is empty or hardware is absent.
- frontend-src/src/features/models/ModelsView.jsx:1275-1284 maps that shared waiting state to hardware-specific copy.
- An empty or non-deployable catalog after a received hardware snapshot is therefore described as missing hardware.

**Required remediation**

1. Represent hardware loading, hardware blocked, catalog empty, catalog loading, advisor loading, and advisor blocked as distinct states.
2. Preserve and display backend blocker reasons after a successful hardware response.
3. Provide next actions for Docker control and model-folder availability without weakening safety.
4. Keep Browse all models usable when recommendations cannot be produced.

**Acceptance outcome**

- After an HTTP 200 blocked hardware response, the UI says the snapshot was received.
- The actual blockers and safe next actions are visible.
- Waiting language remains only while a request is in flight.
- Recommendation actions remain blocked until requirements are satisfied.

**Resolution and re-verification**

- Models now distinguishes catalog loading, hardware loading, hardware error, received-but-blocked hardware, empty catalog, and no-deployable-candidate states.
- A blocked HTTP 200 hardware snapshot preserves the backend blocker reasons and checks, suppresses invalid advisor work, and keeps deployment actions disabled.
- Regression tests cover blocked snapshot normalization, distinct readiness copy, and safe action blocking.
- In a fresh browser on isolated native :8905, Models stated that the hardware snapshot was received, identified disabled Docker control and the empty model folder, and showed next actions. The former waiting/no-profile copy was absent.
- Browse all models remained usable, while every audited deployment action remained disabled.

## Verified fresh-user flows

### Login, readiness, and Chat

- Fresh administrator login succeeded and Dashboard rendered.
- Chat showed SETUP REQUIRED when no healthy model was configured.
- Find model, Connect endpoint, and Try Testing Mode actions were present.
- Testing Mode completed a Chat task from queued to done without manual stop.
- The final response explicitly stated that no inference or tools were used.
- Task identity showed Model dry-run, Mode chat, Workspace Project Root, and Runtime mock.
- Activity agreed with Chat completion.

### Workspaces and Models

- Project Root loaded and workspace refresh/recheck succeeded.
- Guided recommendations and Browse all models rendered.
- Hugging Face search for Qwen3-8B, Chat filtering, and pagination to page 2 of 5 worked.
- Fit and blocker explanations remained visible.
- No installation or deployment was initiated.

### Settings and Activity

- Essentials and All settings views were accessible.
- Reset opened an explicit destructive confirmation; Cancel left state unchanged.
- Import opened a chooser and cancellation caused no import.
- Activity showed the completed Testing Mode run.
- Inspect exposed execution logs, artifacts, and full details.

### Assistant and WarSat

- Assistant displayed capability readiness.
- Previewing Check Docker status stayed preview-only and explained the allow_docker_control block.
- WarSat Planner and Safety showed local-only protection, GPU hardware, and Docker/model-mount blockers.
- Arrow-key tab navigation and keyboard navigation back to Chat worked.

### Accessibility, responsiveness, and rebuilt instances

- The document remained 1024 px wide without page-level horizontal overflow.
- WarSat's intentionally scrollable tab list remained keyboard-operable.
- Footer and toast stacking was cramped but usable.
- Logged-out :8788 and :8787 pages rendered with zero console errors.
- /api/auth/session returned HTTP 200 on both rebuilt instances.

## Non-blocking observations

- Recharts emitted zero-width/height warnings: 26 early and 189 after the prolonged request storm. No console errors occurred. Re-measure after fixing P1 before opening a separate chart-layout defect.
- Docker remained in standard mode. Privileged WarSat Docker control was intentionally not enabled.
- Native :8788 and Docker :8787 health and frontend checks returned HTTP 200; Docker was healthy.

## Explicitly unverified

- Real-model installation and deployment.
- Real local-model inference and tool calling.
- Hardware benchmark bakeoff and measured recommendation quality.
- Importing an actual settings JSON file.
- Confirming destructive all-settings reset.
- Write-capable Assistant or WarSat actions.

These are not failures, but they must not be presented as completed evidence.

## Completed remediation sequence

1. Fixed the P1 catalog request and toast loop.
2. Added focused regressions for automatic-load stability and request deduplication.
3. Fixed the P2 readiness state model and blocker presentation.
4. Re-ran the isolated WarSat and Models paths at desktop and 1024 px.
5. Confirmed zero console errors; six existing Recharts size warnings remained and were not caused by request churn.
6. Real-model install -> deploy -> benchmark -> inference acceptance remains a separate evidence track.

## Final acceptance checklist

- [x] P1 catalog request/toast loop fixed and regression-tested.
- [x] P2 blocked-hardware copy fixed and regression-tested.
- [x] Fresh WarSat route remains stable for 60 seconds with an empty catalog.
- [x] Fresh Models route shows exact blockers after hardware HTTP 200.
- [x] Desktop and 1024 px live re-verification passes with zero console errors.
- [x] Native :8788 and Docker :8787 remain HTTP 200 and Docker remains healthy.
- [ ] Real-model acceptance remains separately labeled until live evidence exists.

## Cleanup and data-safety record

- The isolated :8904 server was stopped.
- Its temporary data directory was permanently removed and is not recoverable.
- The fresh browser tab was closed.
- Real native and Docker data stores were not modified.
