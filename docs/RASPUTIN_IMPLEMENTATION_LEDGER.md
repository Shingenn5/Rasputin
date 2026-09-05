# Rasputin implementation evidence ledger

Native runtime verification updated 2026-08-30. Older evidence retains its original verification scope.

This ledger is a compact source-of-truth checkpoint for the workstation and
Assistant tracks. It records what the repository currently proves; it does not
replace the detailed checklist or readiness report.

## Status vocabulary

- **IMPLEMENTED** — the behavior exists in current source code.
- **VERIFIED** — current automated tests or a recorded live check cover the behavior.
- **PARTIAL** — an important part exists, but the release or user workflow still has a named gap.
- **PLANNED** — the repository describes the work, but implementation evidence is absent.
- **BLOCKED** — implementation or verification cannot proceed until a named dependency changes.

## Current evidence

| Area | Status | Evidence | Remaining boundary |
| --- | --- | --- | --- |
| Hardware/runtime capability profile | IMPLEMENTED / VERIFIED | `backend/warsat/capabilities.py` normalizes host, CPU, GPU static identity, volatile capacity, backend evidence, and conservative placement defaults; `GET /api/warsat/hardware` exposes the versioned profile while preserving the legacy detection payload; regression coverage is in `tests/testHardwareCapabilities.py`. | Runtime/model compatibility probes, measured memory envelopes, and broker leases are the next slices; an observed backend is not yet a launch certificate. |
| v1 release contract and scope lock | IMPLEMENTED / VERIFIED | `docs/RASPUTIN_V1_RELEASE_CONTRACT.md` freezes the ten-slice completion boundary, supported deployment paths, evidence matrix, stop rule, and explicit non-goals; `tests/testReleaseContract.py` machine-checks the document and `scripts/verify_release_candidate.py` includes it in the isolated release gate. | The contract defines the finish line; its live coder, voice, recovery, and browser evidence rows remain open until their later slices pass. |
| Resource lease/admission core | IMPLEMENTED / PARTIAL | `backend/warsat/resource_broker.py` accounts for per-device VRAM, safe headroom, active owner-scoped leases, heartbeat/expiry, release, and ready/queued/blocked/degraded decisions; `backend/warsat/admission.py` now feeds those decisions into side-effect-free model-pack and WarSat launch previews; `tests/testResourceBroker.py` and `tests/testWarsatAdmission.py` cover mixed capacity, explicit combined-VRAM opt-in, CPU fallback, owner scope, preview decisions, and the deploy re-check. | Cross-process atomicity, active lease receipts, and measured runtime certificates remain open; preview admission never starts a model process or reserves a lease. |
| Native runtime placement and lifecycle | IMPLEMENTED / VERIFIED (bounded) | `backend/models/load_profiles.py`, `backend/models/registry.py`, and `backend/warsat/providers/native_llamacpp.py` plan native GGUF loads, expose measured file sizes, preserve explicit profile settings, discover the bundled manifest, and manage the engine process. The 2026-08-30 isolated source UI run downloaded SmolLM2-135M Q4_K_M, loaded it with automatic defaults, completed a real Rasputin chat task, and stopped it with Load available again. | One small-model lifecycle is proven; broad architecture/device compatibility, large-model performance, and coder certification remain separate evidence. |
| Native GGUF acquisition | IMPLEMENTED / VERIFIED (bounded) | `backend/models/desktop_acquisition.py`, `/api/models/download`, and Models/Discover use exact GGUF variants and durable jobs. Exact filenames/sizes survive transport; completed downloads register for native loading. The 2026-08-30 source UI run selected and acquired the 100.6 MB Q4_K_M artifact directly from Discover. `tests/nativeDeployment.test.mjs` and `backend/models/test_native_acquisition.py` cover native routing and metadata regressions. | Raw weights without compatible GGUF variants cannot be loaded; gated repositories and companion-file compatibility retain their own requirements. |
| Chat controls, message TPS, and honest progress | IMPLEMENTED / VERIFIED | The composer groups message actions (`Attach`, `Commands`) separately from response settings with accessible labels; message and task details expose estimated output tokens and tokens/second; generation metrics persist with task snapshots; model-download cards render a percentage bar only when byte totals and the backend `progressTrusted` flag agree, otherwise they show `percentage unavailable`. Coverage is in `tests/testBackendSmoke.py`, `tests/testModelAcquisition.py`, and `tests/testChatUiContract.py`; isolated browser checks verified both trusted and unavailable download states plus a dry-run message details panel. | TPS is intentionally labeled estimated because provider usage metadata is not consistently available across local runtimes; exact provider-reported token counts remain a future runtime-adapter enhancement. |
| Model resource manifest | IMPLEMENTED / PARTIAL | `backend/models/resource_manifest.py` emits the versioned `rasputin.model-resource.v1` schema for catalog entries; weights, quantization, runtime envelope, KV-cache evidence, backend declarations, placement policy, role fit, and dynamic headroom are exposed through `resourceManifest`; model-pack and WarSat previews now carry the manifest and broker decision; `tests/testModelResourceManifest.py` and `tests/testWarsatAdmission.py` cover validation, legacy enrichment, and mixed-GPU fit evidence. | KV-cache values remain unmeasured until benchmark certificates land, and non-WarSat external/provider launch paths remain outside this admission boundary. |
| Runtime benchmark certificates | IMPLEMENTED / PARTIAL | `backend/warsat/benchmarks.py` normalizes exact model/runtime/device/context/concurrency observations into `rasputin.runtime-benchmark.v1`, computes p50/p95 latency and throughput summaries, persists owner-scoped records, and exposes approval-safe `/api/warsat/benchmarks` endpoints; `tests/testWarsatBenchmarks.py` covers aggregation, validation, freshness, ownership, and API transport. | Runtime adapters still need to collect live vLLM/llama.cpp counters; certificates do not yet authorize placement or claim semantic quality. |
| Adaptive context and child throughput budgets | IMPLEMENTED / PARTIAL | `backend/engine/context.py:adaptive_profile` consumes only explicitly attached fresh benchmark/resource evidence, caps context from measured KV envelopes and tested windows, and bounds child work to tested concurrency; `AgentHub.start` records requested/resolved child counts in an `adaptive_budget` trace. `tests/testAdaptiveBudgets.py` covers measured, stale, and slow/partial evidence. | Registry/model-pack flows do not yet attach live certificates automatically, and sustained throughput still needs hardware/runtime trials. |
| Model capability certification | IMPLEMENTED / VERIFIED | Bounded probes and persisted profiles in `backend/models/compatibility.py` (`certify`) and `backend/models/registry.py` (`_store_compatibility`, `certify_model`); `scripts/certify_local_coder.py` and `scripts/certify_model_fleet.py` emit explicit ready/limited/blocked evidence, with the fleet command recording a latency-only owner-scoped certificate for each reachable local main/coder role without deploying a model; regression coverage in `tests/testBackendSmoke.py`, `tests/test_coder_certification_cli.py`, and `tests/test_model_fleet_certification.py`. | A real file-editing coder mission and throughput/memory certificate are not yet release evidence; this ledger does not establish a currently certified local coder. |
| Coding-mode preflight and fallback | IMPLEMENTED / VERIFIED | `backend/api/agent.py:create_task` checks certified modes and tool support before task start; `backend/engine/agent.py` records `tools_unavailable` rather than accepting tool-less execution. Covered by `tests/testBackendSmoke.py:testToollessManagedModelFallsBackToChatBeforeTaskStarts` and `testGovernedChatFailsWhenLocalRuntimeDroppedRequiredTools`. | Fallback is safe, but a fallback is not proof that the selected model is suitable for Coding. |
| Retired provider parser records | Historical implementation evidence | Older vLLM parser fields/tests remain in server-era adapter code. | They are not the native GGUF loading workflow and must not imply a current product deployment feature. |
| Workspace validation commands | IMPLEMENTED / VERIFIED | Persistence in `backend/core/workspace.py:set_workspace_commands/get_workspace_commands`; API in `backend/api/warsat_api.py:/workspace/commands`; operator form in `frontend-src/src/features/workspaces/WorkspacesView.jsx`; UI persistence coverage in `tests/ui/rasputinSmoke.spec.mjs` (`workspace validation commands persist through the operator UI`). | Broader keyboard/mouse review coverage remains part of the task-review quality bar. |
| Coding task review and recovery | IMPLEMENTED / PARTIAL | Task Details now presents a completion-evidence panel that distinguishes model response, file mutations, test runs, and the required review action; Changes exposes per-file revert for added/modified/deleted/untracked entries; `git_restore` removes only explicitly selected untracked paths behind the existing trust/approval gate. Backend regression coverage is in `tests/testBackendSmoke.py`; UI contract coverage is in `tests/ui/repositoryAwareness.spec.mjs`. | Full live keyboard-only and mouse-only review certification remains open, and rename/binary diff behavior needs a dedicated browser pass. |
| Operational diagnostics | IMPLEMENTED / PARTIAL | Native operations use owner/URL records, health/frontend probes, Inference Engine state, GGUF metadata, load-plan errors, and model-process status. Settings diagnostics and `tests/testDiagnostics.py` retain additional older server-era checks. | Remove stale user-facing legacy diagnostics separately where they remain; they are not native setup prerequisites. Clean-machine and authenticated operator evidence remains bounded. |
| Memory duplicate detection and supersession | IMPLEMENTED / VERIFIED | Duplicate hashing and conflict/supersession handling in `backend/rag/memory.py:add_item/update_item`; `tests/testBackendSmoke.py:testMemoryDeduplicatesAndResolvesCanonicalConflicts` covers duplicate identity, canonical replacement, scope checks, and superseded status. `scripts/rehearse_memory_restart.py` and `tests/testMemoryRestart.py` prove the saved correction, superseded original, provenance, and owner boundary from a fresh Python process in an isolated store. | A complete owner-facing memory review workflow remains unfinished. |
| Per-task memory inclusion and suppression | IMPLEMENTED / VERIFIED | `backend/engine/agent.py` normalizes `auto/include/suppress`, bounds recall, and records trace status; `tests/testBackendSmoke.py:testTaskMemoryModeSuppressesRecallAndPersists` and `testSuppressedMemoryIsOmittedFromChatPrompt` cover persistence and prompt omission; Chat and Memory views explain the active boundary. | Cross-chat memory UX and controls still need live user-flow verification. |
| Recall explanations and provenance | IMPLEMENTED / VERIFIED | `backend/engine/agent.py:_recall_memory` emits explanation records; provenance fields are managed in `backend/rag/memory.py`; the task inspector and Memory view expose matched terms, scope reason, ranking factors, and source metadata; coverage includes `tests/testBackendSmoke.py:testMemoryRecallIsOwnerScopedAndContextBudgeted`, memory lifecycle/provenance tests, `tests/testMemoryRestart.py`, and `tests/testMemoryUiContract.py`. | Correction history and live authenticated user-flow verification remain open. |
| Assistant workflow separation | IMPLEMENTED / PARTIAL | `backend/assistant/contracts.py:WORKFLOW_DEFINITIONS` defines independent Assistant and Coding entry points; the Dashboard now provides separate accessible Workstation and Assistant launch points; approved broker handoffs start exactly one governed Code task and the Assistant UI displays the resulting task receipt; `tests/testAssistantContracts.py`, `tests/testAssistantUiContract.py`, and `tests/testWorkModeUiContract.py` cover the contract. | A live end-to-end journey with a real local coder model remains blocked until Slice 1 is unblocked. |
| Assistant readiness contracts | IMPLEMENTED / PARTIAL | Readiness and voice-role contracts are exposed by `backend/api/assistant.py`, `backend/assistant/voice.py`, and `backend/assistant/voice_models.py`; `GET /api/assistant/voice/models` classifies registered speech endpoints as ready, health-check-needed, or blocked without starting models or audio I/O. `AssistantView.jsx` now renders bounded personality controls, contract state, and per-role speech-model readiness; `tests/testAssistantContracts.py` and `tests/testAssistantUiContract.py` cover capability, profile, voice-preview, and redacted voice-model readiness contracts. | End-to-end voice turns and authenticated browser/hardware verification remain open. |
| Assistant command preview | IMPLEMENTED / VERIFIED | `POST /api/assistant/command-preview` in `backend/api/assistant.py` delegates to the allowlisted preview router; `AssistantView.jsx` exposes the preview form; `tests/testAssistantContracts.py:test_command_router_is_allowlisted_preview_only_and_approval_explicit` covers recognized, blocked, unsafe, and non-executing behavior. | Preview-to-plan execution remains deliberately approval-gated and partial. |
| Local voice conversation | IMPLEMENTED / PARTIAL | Device-free HTTP adapters in `backend/assistant/voice.py` plus `POST /api/assistant/voice/turn` now run STT → local Assistant → TTS, persist an owner-scoped Assistant chat turn, and return bounded transcript/response/audio evidence without host actions; `GET /api/assistant/voice/models` now reports redacted registration/readiness evidence. `AssistantView.jsx` uses the turn route after an explicit 60-second push-to-talk action. Transport, turn, readiness, and UI contract tests are in `tests/testAssistantContracts.py` and `tests/testAssistantUiContract.py`; the contract is documented in `docs/LOCAL_VOICE_ADAPTER.md` and `docs/LOCAL_VOICE_MODEL_READINESS.md`. | Browser permissions, microphone/speaker hardware, and a real live voice turn remain unverified. |
| Internal MCP capability contract | IMPLEMENTED / VERIFIED | Versioned callable capability surface is documented in `docs/MCP_CAPABILITY_CONTRACT.md` and exposed through the existing MCP layer and Assistant readiness surface. `scripts/certify_mcp_safety.py` and `tests/testMcpSafety.py` certify fail-closed discovery, allowlisted routing, dry-run mutation, approval previews, and audit evidence in an isolated fixture. | A standalone external MCP server remains conditional and is not part of this ledger's completed work. |
| Real file-editing local coder mission | PARTIAL / BLOCKED | The deterministic acceptance fixture proves the orchestration path; `scripts/certify_local_coder.py` reports the live prerequisite explicitly. | The small native inference proof does not establish coder capability; a fresh certified native coder and a live edit → test → repair → diff review mission are still required. |
| Deterministic coding acceptance fixture | VERIFIED | `scripts/run_coding_acceptance.py` creates an isolated two-file Git fixture, drives the real MCP patch path through the governed execution loop, records a failing test followed by a passing repair, and emits JSON evidence; `tests/test_coding_acceptance.py` is the regression gate. | The scripted model is deterministic; it does not replace live local-model certification. |
| Diagnostics, backup/restore, and release recovery | IMPLEMENTED / PARTIAL | `backend/core/diagnostics.py` provides live redacted checks; `backend/core/backup.py` and `/api/recovery/*` provide immutable staged backups, SQLite online snapshots, separate-target restore, archive integrity verification, dry-run restore, owner-safe metadata export, and explicit owner deletion confirmation; `scripts/rehearse_restore.py --rehearse`, `tests/testDiagnostics.py`, and `tests/testBackup.py` cover the contracts. | Restore remains separate-target only while the service runs; isolated clean-instance migration is verified, but a stopped active-data upgrade rehearsal and workspace source/model caches/TLS recovery remain open. |
| Installation verification | VERIFIED on current workstation / PARTIAL release | The 2026-08-30 native installer built and installed successfully; installed executable/package/backend/frontend hashes matched the tested build. The live installed owner passed health/frontend, catalog-search, route-recovery, and bundled-engine checks while preserving 21 registered models. `scripts/check_installation.py` remains a legacy checkout inventory, not an installed-user prerequisites guide. | Windows clean-machine install/upgrade/uninstall, broader GPU-driver compatibility, signing, native-window interaction, and hardware/audio certification remain separate release evidence. |
| Release-candidate certification | IMPLEMENTED / PARTIAL | `scripts/verify_source_regressions.py` runs isolated backend/JavaScript/Desktop/browser/build/docs gates; `scripts/verify_release_candidate.py` probes explicitly selected native owners and uses versioned, hash-bound evidence from `scripts/release_evidence.py` to compute readiness. See `docs/RELEASE_EVIDENCE.md`. | Source tests and fixture evidence do not certify an installed package, clean-machine recovery, real coder mission, or voice hardware. These require matching current operator evidence; signing/update channels retain their separate public-distribution scope. |

## Latest native workflow verification — 2026-08-30

**VERIFIED in an isolated source Native Host on loopback :8902:** the operator UI searched
`bartowski/SmolLM2-135M-Instruct-GGUF`, selected Q4_K_M (100.6 MB), downloaded and registered it,
and loaded it with the default native settings. A real Rasputin Chat task reached `done` with
“I'm ready to help! What's your question?” The UI then stopped the model and restored its Load
action. There were no page errors or requests to retired infrastructure APIs. Body overflow was
zero at viewport widths 1440, 1024, and 390 pixels.

Recorded checks passed: 44 frontend tests, the authenticated source/Desktop browser fixture test,
5 Desktop lifecycle tests, and 101 focused Python tests plus 4 subtests. The backend smoke run
passed 164 tests with 1 legacy-infrastructure test skipped. These counts describe separate runs;
fixture coverage is not a second live-model or installed-package certification.

Local evidence: `%TEMP%\rasputin-native-finish-01a0540b\source-lifecycle-proof.json`.
The source lifecycle and native routing/load/UI regression fixes are verified within that scope.

**VERIFIED on the current workstation:** the isolated packaged backend/UI also downloaded the
same 105,454,432-byte artifact through the balanced one-click Q4_K_M selection, loaded it with
automatic defaults, completed a real Chat task, and stopped the model. Its browser checks recorded
no page errors, retired API requests, or body overflow at the same three viewport widths.

The native installer build and current-user silent installation both exited successfully. The
1,125,346,547-byte installer updated Desktop; the installed executable, `resources/app.asar`,
backend executable, and bundled frontend index hashes matched the tested build. The running
installed owner/backend were confirmed; its recorded loopback URL returned HTTP 200 for health
and frontend. The installed app's real catalog search worked, `#warsat` redirected to `#models`,
and the existing library retained 21 models. No page errors or retired API calls were observed.
The installed CUDA 12.4 llama.cpp engine reported bundled/ready with no repair required.

Installed UI checks used a browser connected to the actual app's backend. The native window,
title, and process ownership were confirmed through read-only OS inspection; native UI Automation
was unavailable because the computer-use helper was blocked by the sandbox ACL. This is not a
claim of native-window interaction testing. Disposable test listeners on :8899–:8903 and all test
`llama-server` processes were absent after cleanup; the installed application remained running.

Package and installed evidence is beside the source proof in `packaged-acquisition-proof.json`,
`packaged-lifecycle-proof.json`, and `installed-proof.json`. A rollback copy is in the same session
folder's `pre-update-backup` directory. These local scratch artifacts are not distributed releases.

**PARTIAL release boundaries:** clean-machine install/upgrade/uninstall, signing/update channels,
a real coder edit → test → repair → review mission, and broad model/hardware certification remain
open. The proposal PDF has a recorded 12-page visual review; its Word document remains structurally
verified only, with visual rendering unavailable. Source restarts do not update installed binaries;
this workstation's update was proven through packaging, installation, hashes, and live ownership.

## 2026-08-30 first-request timing cleanup

**IMPLEMENTED / VERIFIED in isolated source:** message details and the task drawer separate
runtime-reported generation speed, first visible token, prompt processing, and request time.
Whole-request throughput remains explicitly labeled and keeps its exact/estimated count source;
small positive rates display as `0.04 tok/s` or `<0.01 tok/s`, never rounded zero. Old records
without native timing retain their historical throughput and show unavailable for missing timings.
Per-call measurements reset between turns and survive task persistence.

New native loads perform a synthetic prompt and two decode tokens before reporting ready.
Warm-up is bounded to 120 seconds, does not create a chat/task, and disables reuse of a prior
prompt cache for the synthetic request. Failed warm-up returns an actionable load failure and stops the newly launched process.
Load and Stop run off the HTTP event loop; the loading dialog explains the warm-up period.
This moves some first-request initialization into loading, not a guarantee against every later
kernel/context-specific startup cost.

The isolated source UI on :8904 loaded the real SmolLM2-135M Q4_K_M model on CPU, completed
warm-up, ran Chat, displayed native metrics in both details surfaces, and stopped the model.
The health endpoint responded in 18 ms during loading. No page errors or horizontal overflow
occurred at widths 1440, 1024, and 390. Proof and screenshots are under
`%TEMP%/rasputin-timing-cleanup-01a0540b/` (`source-proof.json`, `timing-details.png`).
Backend coverage includes native readiness/failure handling, timing persistence and fallback,
invalid values, and HTTP event-loop responsiveness. Formatter tests cover low rates and absent
native timings. The existing 27B model in the installed app was not restarted or unloaded.

The rebuilt packaged Desktop backend on :8905 repeated the real CPU GGUF Load → warm-up →
Chat → details → Stop flow with exact native metrics. Warm-up completed in 0.375 seconds;
first visible text took 0.165 seconds in that small-model check. This does not certify the
27B mixed-GPU startup improvement. Packaged proof is in `packaged-proof.json`; browser checks
again found no page errors or overflow at all three widths. `npm run desktop:package` produced
`dist/electron/Rasputin-Setup-0.2.0.exe`. The test listeners/models were stopped after validation.

**Deployment boundary:** source/package verification does not update the installed Desktop app.
The updated installer must be applied and checked before this cleanup is live there; doing so
requires closing the app and unloading its active model.

## 2026-08-31 Discover completed-download flow cleanup

**IMPLEMENTED / VERIFIED in isolated source:** completed and cancelled download receipts no
longer remain in the global progress rail above Discover's independently scrolling catalog.
In-progress, paused, and failed jobs remain visible there because they still need status or an
operator action. A completed model stays in its catalog row with `Manage`; its inspector retains
the direct `Load model` action, so removing the stale receipt does not remove deployment access.

The authenticated Desktop browser fixture rendered 40 catalog rows, scrolled the catalog by 600
pixels, and verified that an active download remained actionable while the completed-only state
had no progress rail. The completed row opened its inspector with an enabled `Load model` action.
No page errors or horizontal overflow occurred at widths 1440, 1024, and 390. Focused model UI
coverage passed 53 tests, and the production frontend build completed. The rebuilt packaged
backend/UI repeated the same active and completed states, catalog scroll, inspector action, and
three-width checks with no page errors. `npm run desktop:package` produced
`dist/electron/Rasputin-Setup-0.2.0.exe`. Local proof is under
`%TEMP%/rasputin-discover-scroll-01a0540b/` (`proof.json`, `packaged-proof.json`, and screenshots).

**VERIFIED installed on the current workstation:** the silent current-user update exited zero;
the installed executable, `resources/app.asar`, and backend executable hashes match the tested
package. The restarted installed backend returned HTTP 200 and the installed UI repeated the
completed-download flow with no page errors or overflow at all three widths. The previously loaded
Qwen model was intentionally unloaded for the approved update and was not automatically reloaded.
Installed proof is in the same scratch folder as `installed-proof.json` and
`installed-completed-download-flow.png`; the prior installed binaries are preserved under
`pre-discover-update/` for rollback.

## Evidence boundary

The 2026-08-29 native lifecycle and UI checks used isolated data, real authentication, a real
GGUF, and the bundled llama.cpp engine. The corresponding 197 backend and 36 frontend tests
passed. Desktop dialog layout checks used browser fixtures; these are not a packaged installer
or clean-machine certification. Older rows retain their own limited source/test scope. Historical
server-era test results do not define native setup or prove the current installed app is updated.

## First reliability wave — 2026-09-04

The source implementation now includes immutable backup staging and SQLite online snapshots,
archive verification before publication, Windows restore-rehearsal cleanup, honest Trials
scorecards, and native release evidence evaluation. See [RELEASE_EVIDENCE.md](RELEASE_EVIDENCE.md)
for commands, schema, scope, and proof boundaries.

- **IMPLEMENTED / VERIFIED — recovery:** the 20 focused backup/reliability tests pass, including
  source changes after hashing, active writers, secondary database WAL state, failed publication,
  preserved restore boundaries, and the actual Windows subprocess rehearsal with strict cleanup.
  Each database is consistent independently; database/sidecar snapshots are not one transaction.
- **IMPLEMENTED / VERIFIED in isolated source UI — scorecards:** generic cards keep unmeasured
  dimensions empty, show request-completion provenance, exclude absent values from averages,
  and hide unsupported legacy scores. Twelve focused scoring/Trials backend tests pass.
  The authenticated browser fixture creates a real dry-run experiment through the API,
  generates its scorecard through the UI, checks keyboard details and sparse radar output,
  and verifies legacy fallback. Desktop and narrow-card screenshots were visually reviewed.
- **IMPLEMENTED / VERIFIED by fixtures — release reporting:** the versioned evaluator binds
  selected source/package/model identities, checks attachment hashes, enforces seven-day
  freshness, and distinguishes source, installed, clean-machine, and live-model evidence.
  Native targets are explicit; there are no default production endpoint probes.
  Full release readiness remains open until the actual required evidence is supplied.
- **IMPLEMENTED / locally verified — source CI:** the Windows source workflow runs isolated
  Python modules, the full top-level JavaScript suite, Desktop checks, a build, and authenticated
  browser fixtures. Existing source assertions were reconciled with current minimal navigation,
  model-action options, fit disclosures, and cosmetic wording/tokens; no application behavior
  was changed to satisfy obsolete literals. Hosted CI has not run for these unpushed changes.
  Verification children enter retained Windows Jobs before execution. Regression checks cover
  exited launchers, timeouts, ownership failures, preservation of unrelated processes, and
  browser reports with zero or skipped tests. This is verification process cleanup, not a
  native Host Shell capability or a filesystem/network sandbox.

Scope-isolated pre-publication verification passed all 39 source checks: 360 backend tests (359 passed,
one Windows symlink-permission skip), 132 JavaScript tests, five Desktop lifecycle tests,
three Desktop syntax checks, the frontend build, documentation validation, and both authenticated
browser fixtures. That is 499 tests reported, with 498 passed and one skipped. The detached
checkout included only this wave, excluding pending model-workspace edits. It also proved
that generated frontend assets must be built before backend imports on a fresh checkout;
the runner now enforces that order and blocks dependent checks after a failed build. The same
full run exercised retained Windows Job ownership, including nested test processes.

Source fixtures are not installed-package, clean-machine, actual-coder, or audio-hardware
certification.
The reviewed screenshot artifacts are under the session scratch folder
`%TEMP%/rasputin-improvements-01a06fab/`.

The next substantial dependency is the governed native validation runner and its real
edit/test/repair/review mission. Capability-specific model certification, broader state
consolidation, recovery journals, and the remaining review recommendations retain their own
follow-up scope. Nothing in this wave enables native Host Shell or changes the installed app.
