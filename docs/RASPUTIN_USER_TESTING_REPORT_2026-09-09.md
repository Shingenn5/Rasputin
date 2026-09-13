# Rasputin user testing campaign — 2026-09-09, updated 2026-09-10

Status: **final report — testing concluded at the owner's request on September 10**.
This report combines the original campaign, the September 10 native Computer Use continuation,
and the owner's confirmation that attachment upload works. It is not exhaustive playbook or
release certification. No further tests, source fixes, or installed-app updates were performed
to finalize this document.

Implementation follow-up: [UX campaign implementation plan](RASPUTIN_UX_IMPLEMENTATION_PLAN.md)
(September 12) maps all 19 findings to source-grounded work packages and acceptance tests.
The testing campaign remains concluded; planning is not additional live-test evidence.

September 12 implementation follow-up: the plan now records source fixes for the UX-017 filter
bypass and a reproduced UX-006 metadata-precedence case, with focused unit/browser results.
Those later source results do not change the historical campaign counts or certify installed
fixes. The original UX-006 record's exact cause and remaining fit cases are still open.

## Executive summary

Rasputin completed the core native journey: discover a model, download its GGUF, register it,
load it with automatic placement, produce a completed chat response, and stop the test model.
Navigation, several menus, history, basic validation, and selected preference persistence also
worked. The weakest observed areas were model identity/readiness labels and dense Models layouts
that hide or clip controls. Clipboard copying and the installed catalog's fit filter also failed.

- **19 findings recorded.** These include reproducible defects and observations that still need
  measurement or investigation; they are not 19 fully diagnosed root causes. UX-019 was added
  during the September 10 cancellation attempt.
- **Six findings have campaign source fixes:** UX-002, UX-008, UX-009, UX-013, UX-014, UX-015.
  Relevant unit/source assertions or isolated browser regressions passed. None is verified as
  fixed in the installed application.
- **13 findings have no completed campaign fix verification.** UX-017 already has a stricter
  predicate in current source, but its source catalog behavior was not rechecked. The installed
  catalog still reproduced the defect on September 10.
- The model name being stuck on `artifact-artifact-...` is a confirmed installed-app issue,
  not evidence that the selected model cannot respond. Readable names passed source regression.
- The intentionally nonresponding `smoke-local-endpoint` is an expected negative fixture. Its
  HTTP 400 is not counted as a failure of the working Qwen model.
- **Attachment upload is owner-verified.** Elliott confirmed that he tested it and it works;
  this is recorded separately from agent-observed evidence. No additional upload test is pending.
- **Cancellation is inconclusive, not a confirmed functional failure.** The test responses
  completed before a successful cancellation was captured. The moving Stop control is a separate
  observed usability issue.

**Conclusion:** the tested local-model/chat path works, but the evidence does not establish that
every button, dropdown, device placement, attachment flow, or coding workflow works. The recorded
source improvements still require an approved installed-app update and a short regression pass.

The highest-value next work is to deliver the existing source fixes, repair copying, make fit
labels and filtering consistent, and keep catalog results and Stop controls reachable and stable.
The known limits below are an honest boundary on this report, not a requirement to continue
testing before the owner can review or use it.

## Evidence boundaries

| Evidence level | What it establishes | What it does not establish |
|---|---|---|
| Installed Desktop, native Computer Use | Actual clicks, visible outcomes, real download/load/chat/stop, and observed defects | Untouched controls, clean-machine behavior, or source fixes being installed |
| Isolated source browser tests | Readable model labels, readiness filtering, selected layout geometry and keyboard behavior with fixtures | Real model inference, native clipboard integration, physical Windows DPI scaling |
| Build and focused automated tests | The recorded source build and selected assertions pass | Exhaustive backend coverage, release readiness, or packaged/installed equivalence |
| Source inspection | Specific handlers, filters, and display logic | An unexecuted interaction working in the installed app |
| Owner-reported testing | Elliott confirms attachment upload works in his testing | Independently replayed evidence, unspecified file types/sizes, or every attachment edge case |

Results below come from the campaign record, retained artifacts, the September 10 native
Computer Use continuation, and explicitly labeled owner confirmation. In the ledger,
**selection/inspection/navigation only** is not an
end-to-end functional pass; **partial** and **unknown** are not passes.

## Baseline

- Source branch: `codex/model-ecosystem-integration`; starting commit `ab983c3`.
- Existing unrelated working-tree changes preserved; no commit, push, or application installation authorized.
- Installed About page displays `v0.2.0-beta`, x64, bundled native llama.cpp,
  Electron with bundled native backend. This UI string does not establish the packaged commit.
- Native screenshot canvases observed: 1819 × 981 and a restored 1427 × 934 window.
  Physical DPI/scaling and the native minimum window size were not measured.
- Initial post-download baseline: three downloaded GGUF models, 23 registry entries, no running
  model. This was not the final state after the user later loaded a working model.
- Previous download journey acquired `Qwen3-1.7B-Q4_K_M.gguf` through Discover.
- Test created a harmless math conversation; no project files edited through the model.

## Executed control ledger

| Control / journey | Result | Evidence / limit |
|---|---|---|
| Find a model setup CTA | Defect | Opens My Models, not discovery |
| Discover Models navigation | Pass | Catalog opens |
| Search model | Pass | Qwen3-1.7B-GGUF results visible |
| Download result | Pass with UX issue | Automatic 1.03 GB Q4_K_M download completes; variant decision opaque |
| Download completion registration | Pass | Downloaded count 2→3; registry 22→23 |
| Models navigation | Pass | My Models opens |
| Filter installed models | Pass | Qwen3-1.7B filter gives 1 of 23 and correct inspector |
| Open Load model | Pass | Placement preview appears |
| Expand Advanced | Pass | Additional controls visible |
| Memory mode dropdown: all three options | Selection only | Auto, pooled, CPU select; only auto actually loaded |
| Restore automatic memory mode | Pass | Default option restored before load |
| Load model | Pass | Preparing/warming state → READY; running count 0→1 |
| Use in New Chat | Pass with UX issue | Chat opens with selected model, but internal artifact key shown |
| Composer + Enter submit | Pass | Harmless arithmetic prompt submitted |
| Model inference | Pass | Completed response says 2 + 2 equals 4; exact requested terse format not followed |
| Response Details disclosure | Pass | Model filename, task mode, memory, reasoning, timings visible |
| Chat mode menu | Pass | Chat, Analyze, Research, Code, Write, Organize, Review visible |
| Select Code | Pass (guard) | Visible incompatibility message prevents unsupported task; no coding task run |
| Settings navigation | Pass | General section opens |
| About navigation | Pass | System information and resource links displayed; links not yet followed |
| Stop native test model | Pass | Running count restored from 1 to 0; downloaded GGUF retained |
| Recent chats search and reopen | Pass | Search finds the arithmetic test and restores its messages |
| Recipes: Explain a topic | Pass with wording issue | Required topic gates Use in composer; preview and insertion work; blank optional background leaves awkward punctuation |
| Recipe-based send / endpoint error | Expected negative test | Owner confirms smoke-local-endpoint intentionally should not respond. HTTP 400 reaches terminal ERROR state; not a failed real-model inference test |
| Reasoning menu | Partial | Medium via recipe and Off selected in the original run; High selected and used for two submissions on September 10, then restored to Off. Not every option tested |
| Memory menu | Inspection only | Auto/Include/Suppress visible; unchanged |
| Attachment picker cancellation | Pass | File dialog opens and Escape returns without attachment; no file submitted |
| Attachment upload | Pass — owner-reported | Elliott confirmed on September 10 that he tested it himself and it works. Not independently repeated by the agent; file types, sizes, and negative cases were not specified |
| Project manager empty state | Pass | RasputinLogs shows empty state |
| Folder picker and Cancel | Pass | Picker opens; canceled without granting project access |
| Settings Runtime, model defaults, Hardware, Connections, MCP | Navigation pass | Ordinary sections render; not a full settings persistence test |
| MCP connection test | Pass | Built-in relay connection test completes and lists 25 tools |
| Models Serving and Refresh | Partial | Gateway-off state renders; no key generated or access changed |
| Models Developer tab | Pass with layout issue | Connection forms and runtime card render; runtime text clipped |
| Empty local endpoint submission | Validation pass | Required Model ID receives focus; no registry entry added |
| Local endpoint role dropdown | Inspection pass | Main/Coder/Researcher/Helper/Planner/Summarizer visible; unchanged |
| Model navigation collapse / expand | Defect | Collapsed icons disappear and long status clips; expansion restores labels |
| Inventory categories | Pass | All and LLMs show 23; Text Embedding shows empty state; Home/Down keyboard selection works |
| Model overflow action | Pass | Opens inspector Actions tab |
| Pin / unpin model | Pass | Both report success; original unpinned state restored |
| Copy model ID | Fail | Visible error: Unable to copy model id |
| Inspector Info / Load / Inference / Actions | Navigation pass | Sections switch; no inference settings saved |
| Inference effort and context-overflow dropdowns | Inspection pass | Choices visible and Escape restores original selections |
| Source File disclosure | Partial | Opens; contents not fully inspected |
| Model dialog Escape | Pass | Closes and restores focus to Models navigation |
| Discover Chat category | Pass | Results change from embeddings/general models to chat models |
| Discover Most liked sort | Pass | Results reorder after request completes |
| Discover Fits safely | Fail | Original unknown-fit defect reproduced September 10; settled results also included Will not fit rows. Reset to Any fit |
| Discover Hardware disclosure | Defect | Expands correctly but consumes result area at 1427×934; collapse restores list |
| Catalog Info / Files / Fit / Source | Navigation pass | Inspector tabs show expected sections; unknown fit explains missing estimate |
| General: interface-motion preference | Pass | Reduced motion persists through close/reopen; Full motion restored |
| General: language dropdown | Inspection pass | English/Spanish/French/Japanese choices visible; English left unchanged |
| Settings Escape / keyboard reopen | Pass | Focus returns to Settings button; Enter reopens dialog |
| User-selected real model after the smoke fixture | Pass | Qwen3-1.7B-Q4_K_M.gguf response reached DONE: "Hello! I can see this, and I will respond yes." Details identified native-llamacpp |
| New Chat and final verification draft | Pass, confirmed September 10 | Previously uncertain submission was present as DONE on reopening the native window; response contains MAPLE-742 and 56. It was not resubmitted |
| Follow-up conversation context | Pass with response-format caveat | September 10 follow-up recalled MAPLE-742 and computed 57 from the previous result, then reached DONE. Extra prose/code blocks violated the requested terse format |
| Generation cancellation | Attempted, not verified | Three test responses finished as DONE. Stop was observed during active generation, but no successful cancellation or canceled terminal state was captured |
| Task queue transition | Partial | One submitted task visibly transitioned through queued/running to DONE. A second message queued behind an active task and queue ordering were not tested |

The follow-up establishes use of the preceding conversation context, not persistent memory across
new chats. Cancellation and multi-message queue handling remain unverified.

## Findings

P2 denotes a material usability or correctness issue in the tested flow; P3 denotes lower-impact
polish or layout instability. These are campaign triage priorities, not measured severity scores.

| ID | Priority | Observed issue | State |
|---|---|---|---|
| UX-001 | P2 | Model dialog uses a limited central area; advanced load dialog nearly fills height | Needs responsive measurements |
| UX-002 | P2 | “Cached locally” is zero with three downloaded GGUFs | Source label corrected to Catalog entries; installed app unchanged |
| UX-003 | P2 | Download starts without making automatic variant/size choice clear beforehand | Reproduced |
| UX-004 | P2 | Long model identifiers are truncated in selection controls | Reproduced |
| UX-005 | P3 | Progress content shifts catalog results | Reproduced during download |
| UX-006 | P2 | Embedding model appears labeled Coding; small model marked not fitting | Needs metadata/fit investigation |
| UX-007 | P2 | Find a model opens My Models | Source handler confirms routing mismatch |
| UX-008 | P2 | Header/composer/response summary expose artifact-artifact internal key | Source uses readable model names; browser regression passes. Installed defect reconfirmed September 10 |
| UX-009 | P2 | Scan GGUF / Refresh toolbar is clipped with unfiltered model list | Source prevents toolbar flex shrinking; populated-list browser regression passes |
| UX-010 | P3 | CPU load preview says “GPU cpu”; mode option text clipped | Reproduced while selecting CPU, not loading |
| UX-011 | P3 | Placement preview arrival moves load dialog/control positions | Reproduced; first Advanced click missed after layout moved |
| UX-012 | P2 | About system-information labels appear to have very low contrast | Screenshot observation; contrast ratio not yet measured |
| UX-013 | P2 | Known endpoint model-ID mismatch is offered as Running and accepts Send | Smoke endpoint failure is intentional, per owner. Readiness label remains misleading; source excludes known mismatches and displays Needs attention, regression passes |
| UX-014 | P2 | Collapsed model rail hides icon wrappers as well as labels; status overflows | Source selector preserves icons and compacts status with full tooltip; icon regression passes |
| UX-015 | P2 | Developer runtime description clips beneath its card | Reproduced in source; max-content grid rows fix verified by browser geometry |
| UX-016 | P2 | Copy model ID fails in installed Desktop | Reconfirmed September 10: Unable to copy model id. Clipboard integration not repaired |
| UX-017 | P2 | Fits safely includes unknown-fit and explicitly non-fitting models in installed Desktop | Reconfirmed September 10 after results settled. Current source predicate is stricter, but source catalog regression still needed |
| UX-018 | P2 | Expanded hardware section leaves no visible catalog result list at laptop size | Reconfirmed September 10 at 1427×934; wheel scrolling over the lower content did not reveal rows, while collapse restored them |
| UX-019 | P2 | Stop control moves vertically when the queue strip disappears | Observed September 10: Stop moved from approximately y=827 to y=862 during queued→running layout change, contributing to a coordinate-click miss. A stable cancellation target is needed; this does not establish a broken cancellation backend |

## Native Computer Use continuation — 2026-09-10

The installed `com.rasputin.desktop` window was selected from the plugin's returned app/window
inventory and operated directly. This was not a headless browser or source-server substitute.
Window canvas was 1427 × 934. The user-selected `Qwen3-1.7B-Q4_K_M.gguf` model was already loaded
and remained selected. The intentional smoke endpoint was neither selected nor modified.

### Confirmed outcomes

| Check | Result | Directly observed evidence |
|---|---|---|
| Resolve the interrupted prior test | Pass | Existing conversation showed DONE and “The test code is MAPLE-742. The result of 7 * 8 is 56.” No duplicate prompt submitted |
| Follow-up using prior context | Pass for context/arithmetic | Asked for the previous test code and previous result plus one without repeating either. Completed response recalled MAPLE-742 and calculated 57 |
| Reasoning selection/restoration | Selection and submission pass | High appeared on the composer and two requests were submitted with that selection; Off restored afterward. Actual provider reasoning-budget semantics were not measured |
| Copy model ID | Fail, UX-016 | Selected model's Actions → Copy model ID produced the visible error “Unable to copy model id.” |
| Fit filter | Fail, UX-017 | Any fit showed 100 catalog models; Fits safely showed 80. After another observation, all-MiniLM-L6-v2 still showed Fit unknown and bge-small-en-v1.5 showed Will not fit |
| Hardware/result layout | Fail, UX-018 | Expanding Hardware displayed CPU/RAM/two GPU cards and VRAM filters, leaving only the three downloaded-model receipts visible below. A downward wheel attempt over the lower content did not reveal catalog rows; collapsing restored the list |
| Dialog and preference cleanup | Pass | Any fit restored; Hardware collapsed; Escape closed Discover and visibly returned focus to its navigation button. Final chat showed the working model RUNNING and reasoning Off |

The pre-existing Maximum VRAM field was **13 GB** when Hardware was opened; it was not changed.
All types and Most popular were also preserved. The filter result is a test of the observed UI
contract, not an assertion that every catalog model would fit without those other constraints.

### Cancellation and queue limits

Three text-only prompts were tried: a 500-sentence generation request, a reasoning/counting task,
and a long fairy tale. The first completed before Stop could be exercised. The latter attempts
exposed GENERATING and Stop latest task, but no canceled terminal state was observed; all three
ultimately showed DONE.

Two element-index click attempts returned “element ... is not available in cached app state for
Rasputin.exe.” Fresh observations showed completion; these tool/input races are not evidence of
a Rasputin crash. During the fairy-tale attempt, the queued strip disappeared and moved Stop
approximately 35 pixels downward before a coordinate click, producing the UX-019 observation.
The moving target and completed responses mean **cancellation is still unverified, not passed
and not proven functionally broken**.

The fairy-tale request visibly progressed through queued and running states to DONE, but a
second request was not deliberately queued behind it. Queue ordering, clear/remove behavior,
and cancellation recovery remain outside this evidence.

### Model-output quality, separate from UI functionality

The follow-up correctly recalled the token and result in prose, but added code blocks and treated
“code” as `7 * 8` in one block. The 500-sentence request returned ten sentences and a placeholder
claiming continuation. These are bounded instruction-following observations for the selected
small model, not evidence that the composer, transport, or terminal-state UI failed. The difficult
counting problem was used to provoke a longer generation; its mathematical answer was not scored.

### Owner-verified attachment upload and state left behind

The agent did not attach or submit a file during the continuation. After the upload confirmation
request, Elliott stated that he had tested the feature himself and knew it worked, and requested
the final report instead of further testing. Attachment upload is therefore recorded as
**passed in owner testing**, not as an agent-run test or an outstanding approval blocker.
Specific file formats, size limits, invalid-file rejection, and attachment-assisted answer quality
were not described and are not inferred from that confirmation.

No project permissions, authentication, security settings, installation, or deletion were automated.

Four new text-only requests were submitted (one follow-up and three cancellation probes); their
completed responses were retained. The recent-chats badge changed from 48 to 52. The composer was
empty at the final observation, there was no active generation/queue strip, and the working model
was left loaded. No source changes, app restart, or installed-package update occurred.

## Production remediation guideline

For execution, use the [implementation plan](RASPUTIN_UX_IMPLEMENTATION_PLAN.md). Its September 12
source review refines UX-017: a missing/falsy `vramEstimateGb` can return early from `displayItems`
when VRAM bounds are empty, bypassing the strict fit predicate. The earlier observation that the
source contains `willFit === true` is therefore not proof that every row passes it. This static
finding does not explain all installed results; bounded and unbounded regression cases are planned.

This section turns the campaign into an implementation and release guide. It is intentionally
separate from the observed-results ledger: a proposed fix is not a verified fix, and a source
test is not installed-app certification.

### Recommended release posture

Treat the next production package as **no-go for the daily-driver workflow** while these installed
behavior issues remain unresolved:

- **UX-008:** internal `artifact-artifact-...` identifiers are still exposed to users.
- **UX-016:** Copy model ID still produces “Unable to copy model id.”
- **UX-017:** Fits safely still includes Fit unknown and Will not fit rows.
- **UX-018:** expanded Hardware hides the catalog result area at the observed window size.
- **UX-019:** the Stop target moves during queued-to-running layout changes, and cancellation
  itself has not reached a confirmed canceled state.

This is a product-quality gate, not a claim that the native model runtime is unusable. The core
download → load → response → stop path passed. Attachment upload is owner-verified and is not a
release blocker in this report. P3 polish items may ship only with an owner, ticket, and planned
follow-up; they must not be silently discarded.

### Remediation matrix

| Finding | Production owner | Required change | Close only when |
|---|---|---|---|
| UX-001 | Models UI | Measure and constrain the model dialog at minimum supported size; keep advanced load controls reachable | 1427×934, 1024×900, 768×900, and 390×900 checks show no clipped primary actions or page overflow |
| UX-002 | Models UI | Keep “Catalog entries” separate from downloaded/local artifact counts | The installed package labels each count according to its actual meaning and downloaded GGUF count remains truthful |
| UX-003 | Discover/download | Show the exact variant, size, quantization, and automatic-placement decision before download begins | A user can confirm what will be downloaded without opening a second diagnostic surface |
| UX-004 | Shared model identity UI | Preserve readable names in controls; expose the full identifier through intentional tooltip/copy/detail affordances | Long names remain identifiable at desktop and phone widths without horizontal overflow |
| UX-005 | Discover/catalog | Reserve or smoothly allocate progress space so result rows do not jump while a download runs | Start, progress, completion, and failure screenshots show stable controls and reachable results |
| UX-006 | Registry/catalog metadata | Separate model role, provider, format, and hardware fit; do not infer Coding from an embedding or incomplete record | Representative embedding, chat, coder, and unknown-metadata fixtures show correct labels and fit explanations |
| UX-007 | Navigation | Route “Find a model” directly to Discover Models or rename the CTA to match its destination | One click from the empty/setup state opens the intended discovery workflow |
| UX-008 | Chat + Models UI | Use the readable display-name resolver for header, composer, task metadata, response details, and model controls while retaining the raw key only as machine-readable data | Source tests pass, the package contains the fix, and the installed app shows `Qwen3-1.7B-Q4_K_M.gguf` (or equivalent readable name) instead of the artifact key in user-facing surfaces |
| UX-009 | Models UI | Prevent inventory toolbar flex shrink and preserve Scan GGUF/Refresh hit areas | Populated installed inventory keeps both controls visible and clickable at supported widths in the installed package |
| UX-010 | Load dialog | Label CPU explicitly as CPU and provide enough width or wrapping for memory-mode choices | Auto, pooled, and CPU labels are fully readable and CPU never appears as “GPU cpu” |
| UX-011 | Load dialog | Stabilize dialog geometry when placement preview arrives; preserve the active control and focus | Opening placement/Advanced does not move the next primary action away from the observed target or keyboard focus |
| UX-012 | Accessibility/UI | Measure contrast of About/system-information labels and raise it to the project accessibility bar | Contrast is measured, recorded, and passes the chosen WCAG threshold in the packaged UI |
| UX-013 | Model readiness | Keep known model-ID mismatches out of the healthy picker/send path and show a clear recovery state | Installed UI displays Needs attention, prevents doomed send, and offers a repair/retest action |
| UX-014 | Models navigation | Preserve icons, compact status safely, and expose full status through accessible name/title | Collapsed rail remains navigable by mouse and keyboard; icons and status do not disappear or overflow |
| UX-015 | Developer settings | Allow runtime description/content to size to its text or scroll within a bounded panel | Full runtime status and recovery text is readable without clipping at supported widths |
| UX-016 | Desktop + frontend | Repair copy using a trusted user-gesture path with a scoped fallback; do not broadly grant clipboard read/write permissions | Installed Copy model ID places the exact ID on the clipboard and reports success; failure state gives a usable manual-copy fallback. Security review must cover the chosen permission boundary |
| UX-017 | Fit/placement logic | Make Fits safely include only `willFit === true`; keep unknown as unknown and explain missing capacity data | Real installed catalog shows no unknown or non-fitting rows under Fits safely, while Any fit still exposes the explanatory statuses |
| UX-018 | Discover layout | Give Hardware details a bounded internal scroll or preserve a minimum result-pane height; keep filters and results independently reachable | At 1427×934 with receipt cards present, expanding Hardware still allows a user to reach catalog rows without collapsing the disclosure |
| UX-019 | Chat/composer | Keep Stop in a stable action slot through queued/running transitions, with a durable accessible name | A live generation can be stopped, reaches a documented canceled terminal state, and a subsequent message succeeds; queue-strip appearance/disappearance does not move the action unpredictably |

### Implementation order

1. Fix the correctness and trust surfaces first: UX-008, UX-013, UX-016, and UX-017.
2. Fix reachability and control stability: UX-018 and UX-019, then UX-001, UX-009, and UX-015.
3. Fix model-selection clarity and metadata: UX-002, UX-003, UX-004, UX-006, and UX-007.
4. Finish polish and accessibility measurement: UX-005, UX-010, UX-011, UX-012, and UX-014.

Do not combine clipboard permission changes with unrelated security-setting changes. Do not make
the smoke-local-endpoint respond merely to make a negative test green; preserve it as an intentional
nonresponding fixture. Do not use Docker as a validation or production workaround.

### Verification gates

Every production fix must pass these gates in order:

| Gate | Required evidence | Exit condition |
|---|---|---|
| Source | Focused unit/source assertions for the changed behavior | The relevant regression is deterministic and fails before the fix or covers the previously observed state |
| Build | `npm.cmd run build`; `npm.cmd run desktop:check`; `npm.cmd run desktop:test` | Build, Desktop syntax, and lifecycle tests pass; warnings are recorded, not hidden |
| Isolated UI | Authenticated source app in a disposable `RASPUTIN_DATA_DIR`; desktop/tablet/phone geometry where relevant | The interaction passes with real controls; synthetic model fixtures are labeled as fixtures |
| Package | `npm.cmd run desktop:package` or the approved packaging flow | The artifact contains the tested frontend/backend and package metadata; no claim is made from source files alone |
| Installed Desktop | Identify the owner from `%LOCALAPPDATA%\Rasputin\data\desktop-runtime.json`; compare installed hashes/package timestamps; test that owner URL | Installed UI demonstrates the fix in the actual native window/backend and user data remains intact |
| Native smoke | Exact compatible GGUF → load → response → stop, plus the affected control | The runtime path and the changed UI both pass; do not substitute health/HTTP 200 for inference evidence |
| Rollback/readiness | Preserve prior package/data ownership and record recovery path | A failed install or regression can be reversed without deleting models, chats, or workspace files |

The installed gate must never start a second backend against the installed Desktop's data directory.
Use the owner URL recorded by Desktop, keep loopback/authentication boundaries unchanged, and obtain
operator approval before restart, replacement, or installation. Source and package passes are
necessary evidence, but they do not close an installed-app finding.

### Closure record for each finding

When a finding is fixed, append or link a short closure record containing:

- finding ID and user-visible behavior changed;
- source commit or working-tree identifier and focused test name;
- build/package identifier and artifact hash;
- installed Desktop owner URL/verification date, with credentials and secrets omitted;
- before/after screenshot or structured assertion for the affected control;
- native smoke result if model loading or inference is in scope;
- rollback result or the exact reason rollback was not required;
- remaining limitations and whether the finding is **source-fixed**, **package-verified**, or
  **installed-verified**.

The status vocabulary is deliberate: **Observed**, **Triaged**, **Source-fixed**,
**Package-verified**, **Installed-verified**, and **Accepted residual**. “Looks fixed,” “build
passed,” and “owner expects it to work” are not sufficient closure states by themselves.

## Most useful remaining improvements

This is a prioritized handoff, not a request to restart the exhaustive campaign.

| Order | Scope | Evidence and next action | Acceptance check still needed |
|---|---|---|---|
| 1 | Readable model name and existing source fixes | Installed header/composer show an internal artifact key. Source now resolves the model filename. Earlier inspection found installed app files dated September 1, predating these changes; no update was performed | After an approved update, select the working model and verify header, composer, and completed response summary show a readable name; recheck toolbar, rail icons, runtime card, and readiness state |
| 2 | Copy model ID (UX-016) | Installed copy reports failure. Source calls `navigator.clipboard.writeText`; Desktop's permission handler currently allows only notifications. That is a plausible integration cause, not a proven exception trace. Repair copying without broadly relaxing permissions | A user-initiated Copy action places the exact ID on the clipboard and reports success; an actual failure remains understandable and recoverable |
| 3 | Fits safely (UX-017) | Installed filter includes rows labeled Fit unknown. Current source requires `willFit === true`; do not assume another code change is necessary | Known-fitting entries remain; unknown and non-fitting entries are excluded. Repeat with real installed catalog data after update |
| 4 | Hardware disclosure layout (UX-018) | At 1427 × 934, opening Hardware consumes the visible results area | With hardware details expanded and download receipts present, search/filter controls and catalog results remain reachable through a clear scrolling layout |
| 5 | Stable Stop control (UX-019) | Removing the queue strip moves the cancellation target during a live task | Keep Stop in a stable position through queued/running transitions; separately verify cancellation reaches a clear terminal state and permits another request |

Secondary backlog: improve Find a model routing (UX-007), clarify the automatic download choice
(UX-003), investigate fit/category metadata (UX-006), and measure the suspected low contrast
(UX-012). The remaining truncation, CPU labeling, dialog movement, and responsive observations
stay in the findings table; they have not been silently marked fixed.

## Source verification

These are the **previously recorded** campaign results, not new application test runs for this report.

- Frontend build passed; existing Pyodide browser-external and large-chunk warnings remain.
- Focused identity, readiness, and ecosystem Node suite: 14 passed on final rerun.
- `tests/ui/campaignModelIdentity.spec.mjs`: 2 browser tests passed against the isolated
  authenticated source server on port 8899. Model-registry fixtures are synthetic, not inference evidence.
- Chat geometry checked at 1440/1024/768/390 px; model toolbar hit targets and page overflow
  checked with 23 fixture models at 1427/1024/768/390 px. This does not prove every responsive control.
- Model ArrowDown and End navigation passed in the browser. Native Escape and category keyboard
  selection passed through Computer Use.
- The browser test initially used the wrong onboarding flag value; corrected test setup from
  `true` to `1`. A subsequent real runtime-card overflow assertion failed before the CSS fix and passed after it.
- Installed Desktop has not been rebuilt/replaced for these campaign fixes. Do not report them as
  installed fixes. Source state and the installed package were inspected separately.
- Documentation validation passes for 38 Markdown files; `git diff --check` passes.
- Isolated server stopped and disposable runtime data removed. Screenshots and the prepared
  coding fixture remain in the session evidence directory. Test cleanup did not remove installed
  app data or downloaded model files.

### Reproducible test and source references

- [Identity/readiness assertions](../tests/userFacingModelIdentity.test.mjs), plus
  `tests/launchReadiness.test.mjs` and `tests/modelEcosystem.test.mjs`: 14 passing tests in the
  recorded focused Node run.
- [Campaign browser regressions](../tests/ui/campaignModelIdentity.spec.mjs): two passing tests.
  The toolbar tests include visibility/geometry and trial-click checks; they do not establish that
  Scan GGUF or Refresh completed a real backend operation.
- [Chat display changes](../frontend-src/src/features/chat/HomeView.jsx) and
  [model display/readiness helpers](../frontend-src/src/lib/display.js).
- [Models labels/status](../frontend-src/src/features/models/ModelsView.jsx),
  [interface layout fixes](../frontend-src/src/styles/interface.css), and
  [inventory toolbar sizing](../frontend-src/src/styles/models-workspace-v3.css).
- Retained browser screenshots: `chat-1440.png`, `chat-1024.png`, `chat-768.png`, `chat-390.png`,
  `models-collapsed-1427.png`, `models-advanced-1427.png`, `models-1024.png`, `models-768.png`,
  `models-390.png`. These are isolated-source fixture images in the session's `campaign-browser`
  evidence folder, not screenshots proving that the installed application received the fixes.

## Known coverage limits

These limits are retained for future planning. They do not reopen this concluded testing run.

| Area | Not established by this campaign |
|---|---|
| Chat reliability | Generation cancellation, cancellation recovery, multi-message queue handling; same-conversation follow-up now passed |
| Attachment edge cases | Basic upload is owner-verified. Specific formats, invalid/oversized-file handling, and attachment-assisted answer quality were not separately established |
| Coding | Approved disposable workspace, model edit → test → repair → diff/review journey; a fixture was prepared but not run |
| Native model edge cases | Actual CPU/pooled loads, every advanced parameter, bad GGUF/import recovery, canceled download/retry, reopen persistence |
| Recipes/settings | Every recipe/reasoning option, comprehensive ordinary-settings save/reopen coverage |
| Accessibility/responsiveness | Full keyboard traversal, contrast measurement, physical DPI changes, native minimum-size matrix |
| Deployment | Installed regression of campaign fixes, clean-machine install/upgrade/recovery |

No completion percentage is claimed without a complete control inventory. The original
[testing playbook](RASPUTIN_USER_TESTING_PLAYBOOK.md) remains the broader coverage plan, not
evidence that its unchecked steps were executed.

Permission-gated project access and security/privacy controls were intentionally not automated.
No security settings, API keys, or external publication were changed. The authorized model download
was performed; installing a new Rasputin application build was not.

## State left behind and handoff

- The model used for the first lifecycle test was stopped successfully. **Later, the user loaded
  a working Qwen model; it was left running at the last observation.** The report does not claim
  that the installed app currently has zero running models.
- The deliberately failing external smoke endpoint was left untouched. Test conversations and
  the downloaded GGUF were retained; no model or chat deletion was performed.
- Pinning was reversed, reasoning restored to Off, interface motion restored to Full motion, and
  discovery filters restored to All types / Most popular / Any fit during their respective tests.
- The previously uncertain short verification prompt was confirmed DONE on September 10.
  The subsequent follow-up and three cancellation probes also reached DONE; no pending draft
  or active generation remained at the final observation.
- No project files were edited through a model. Disposable coding-fixture files are test setup,
  not evidence of a successful coding-agent workflow.
- Campaign source/test changes remain uncommitted and unpushed. Unrelated working-tree changes
  were preserved. Installed-app update approval was not obtained, and no installer was run.

Earlier Codex sandbox startup failures are separate from these Rasputin findings: the supplied
logs identified a deny-read ACL state JSON parse failure, and the inspected bytes were all zero.
Those failed tool starts produced no Rasputin interaction evidence. Subsequent successful native
Computer Use sessions provide the application evidence recorded above; no Windows permission
repair or sandbox change is proposed as a Rasputin UI fix.

## Final disposition

The requested testing report is complete. The tested native model/chat journey and follow-up
context worked; attachment upload is confirmed by the owner. Nineteen findings and observations
are documented, including six source fixes that have not been verified in the installed app.
Cancellation remains inconclusive, and unexecuted areas remain transparently listed rather than
being labeled passed. No further test action or attachment approval is pending in this report.

Implementation, installation, and any future exhaustive testing are separate work. The final
write-up changed documentation only; no additional app interaction was performed.
