# Rasputin implementation evidence ledger

Last reconciled: 2026-08-10

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
| Model capability certification | IMPLEMENTED / VERIFIED | Bounded probes and persisted profiles in `backend/models/compatibility.py` (`certify`) and `backend/models/registry.py` (`_store_compatibility`, `certify_model`); regression coverage in `tests/testBackendSmoke.py` (`testCompatibilityCertificationDowngradesContextWeakModel`, `testCompatibilityCertificationRecognizesAgenticModel`, `testCompatibilityFallsBackWhenModelExposesUnclosedThinking`). | A real file-editing coder mission is not yet release evidence. |
| Coding-mode preflight and fallback | IMPLEMENTED / VERIFIED | `backend/api/agent.py:create_task` checks certified modes and tool support before task start; `backend/engine/agent.py` records `tools_unavailable` rather than accepting tool-less execution. Covered by `tests/testBackendSmoke.py:testToollessManagedModelFallsBackToChatBeforeTaskStarts` and `testGovernedChatFailsWhenLocalRuntimeDroppedRequiredTools`. | Fallback is safe, but a fallback is not proof that the selected model is suitable for Coding. |
| WarSat parser configuration | IMPLEMENTED / VERIFIED | API fields in `backend/api/warsat_api.py`; per-deploy tuning in `backend/warsat/__init__.py`; catalog hints in `backend/models/catalog.py`; operator field and hint-prefill in `frontend-src/src/features/warsat/WarsatView.jsx` around the `toolCallParser` field; regression coverage in `tests/testBackendSmoke.py:testWarsatVllmToolCallParserIsOptInPerDeploy`. | Parser/model compatibility still needs live coder-model acceptance evidence. |
| Workspace validation commands | IMPLEMENTED / VERIFIED | Persistence in `backend/core/workspace.py:set_workspace_commands/get_workspace_commands`; API in `backend/api/warsat_api.py:/workspace/commands`; operator form in `frontend-src/src/features/workspaces/WorkspacesView.jsx`; UI persistence coverage in `tests/ui/rasputinSmoke.spec.mjs` (`workspace validation commands persist through the operator UI`). | Broader keyboard/mouse review coverage remains part of the task-review quality bar. |
| Memory duplicate detection and supersession | IMPLEMENTED / VERIFIED | Duplicate hashing and conflict/supersession handling in `backend/rag/memory.py:add_item/update_item`; `tests/testBackendSmoke.py:testMemoryDeduplicatesAndResolvesCanonicalConflicts` covers duplicate identity, canonical replacement, scope checks, and superseded status. | A complete owner-facing memory review workflow remains unfinished. |
| Per-task memory inclusion and suppression | IMPLEMENTED / VERIFIED | `backend/engine/agent.py` normalizes `auto/include/suppress`, bounds recall, and records trace status; `tests/testBackendSmoke.py:testTaskMemoryModeSuppressesRecallAndPersists` and `testSuppressedMemoryIsOmittedFromChatPrompt` cover persistence and prompt omission. | Cross-chat memory UX and controls still need live user-flow verification. |
| Recall explanations and provenance | IMPLEMENTED / VERIFIED | `backend/engine/agent.py:_recall_memory` emits explanation records; provenance fields are managed in `backend/rag/memory.py`; coverage includes `tests/testBackendSmoke.py:testMemoryRecallIsOwnerScopedAndContextBudgeted` and memory lifecycle/provenance tests. | A dedicated user-facing “why was this recalled?” surface is not yet complete. |
| Assistant workflow separation | IMPLEMENTED / VERIFIED | `backend/assistant/contracts.py:WORKFLOW_DEFINITIONS` defines independent Assistant and Coding entry points; `tests/testAssistantContracts.py` verifies the workflow contract. | Shared identity/context exists, but the complete conversational-to-coding journey is still partial. |
| Assistant readiness contracts | IMPLEMENTED / VERIFIED | Readiness and voice-role contracts are exposed by `backend/api/assistant.py` and `backend/assistant/voice.py`; `frontend-src/src/features/assistant/AssistantView.jsx` renders the contract state; `tests/testAssistantContracts.py` covers capability and voice-preview contracts. | No complete profile/personality editor or end-to-end voice turn exists yet. |
| Assistant command preview | IMPLEMENTED / VERIFIED | `POST /api/assistant/command-preview` in `backend/api/assistant.py` delegates to the allowlisted preview router; `tests/testAssistantContracts.py:test_command_router_is_allowlisted_preview_only_and_approval_explicit` covers preview-only and approval behavior. | Interactive preview-to-plan execution is still partial. |
| Local voice adapters | IMPLEMENTED / VERIFIED | Device-free HTTP adapters in `backend/assistant/voice.py` and authenticated routes in `backend/api/assistant.py`; transport contract is documented in `docs/LOCAL_VOICE_ADAPTER.md`; bounded adapter tests are in `tests/testAssistantContracts.py:test_local_voice_http_adapters_are_bounded_role_checked_and_device_free`. | Browser microphone capture, playback UI, and hardware verification are not implemented. |
| Internal MCP capability contract | IMPLEMENTED / VERIFIED | Versioned callable capability surface is documented in `docs/MCP_CAPABILITY_CONTRACT.md` and exposed through the existing MCP layer and Assistant readiness surface. | A standalone external MCP server remains conditional and is not part of this ledger's completed work. |
| Real file-editing local coder mission | PARTIAL | Existing code/test loop and local model certification foundations are present; the checklist and readiness report both identify the missing multi-file edit → failing test → repair → passing test → diff review run. | Requires a live coder-capable local model and an isolated acceptance fixture. |
| Diagnostics, backup/restore, and release recovery | PLANNED | The gaps are documented in `docs/RASPUTIN_APPLICATION_READINESS_GAP_REPORT.md`; no current evidence supports calling these workflows complete. | Requires separate implementation and recovery rehearsals. |

## Evidence boundary

The statuses above are source/test-grounded. They do not claim that native,
Docker, authenticated browser, microphone, speaker, or live local-model checks
were performed during this documentation reconciliation. Those checks remain
explicit acceptance work in the readiness report.
