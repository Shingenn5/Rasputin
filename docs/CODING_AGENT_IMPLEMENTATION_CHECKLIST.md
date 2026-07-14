# Coding-Agent Competitiveness — Implementation Checklist

This is the actionable, checkable source of truth for the coding-agent competitiveness track.

Last derived from plan doc: 2026-07-01.
**Last verified against actual repo code: 2026-07-01** (see "Verification notes" callouts below — this pass re-read the source files themselves, not just commit messages/plan-doc claims, and found the plan understates two things: Stage 7 already has a real partial implementation, and Stage 4b has a hidden prerequisite the plan doc didn't call out).

Scope note: this checklist stays scoped to the coding-agent competitiveness track. It does not absorb unrelated backlog items (UI-upgrade track, deferred Mail Relay/Timeline Sync/etc.) — those live in their own docs.

## Difficulty Legend

- **Easy** — config/wiring/small well-scoped change, low risk of touching shared code paths.
- **Medium** — real implementation work, single subsystem, existing patterns to follow.
- **Hard** — touches a shared/critical path (agent loop, provider layer, approval/trust gating) or requires new non-trivial logic.
- **Very Hard** — new architecture, no existing pattern to extend, and/or high blast radius if done wrong.
- **(env-blocked)** appended where the task's difficulty is inflated by needing something outside pure code (a live model endpoint, deployed local model, credentials) — these are rated by what it takes to actually verify them, not just write the code.

---

## Quick Reference: Remaining Work Sorted by Difficulty

Stage order still matters for *when* to do these (Stage 4b gates 5/6 in spirit, though not as strictly as Stage 0 gated 1-3) — this table is a difficulty-sorted index into the detailed, dependency-ordered task lists below, not a replacement execution order.

### Easy
- [x] Fix hardcoded `--bs-primary-rgb` so Bootstrap components follow the selected theme's accent (UI Bug Fix 1) — done 2026-07-01
- [x] Configure a real model endpoint for verification (Stage 4a follow-up) — done 2026-07-12 (Qwen2.5-3B-Instruct deployed via WarSat; see Session 2026-07-12 below)
- [x] Identify/confirm SSE extension point at `frontend-src/src/app/App.jsx:589` (Stage 4b) — done 2026-07-02
- [x] Quick action: view diff for a file (Stage 5) — done 2026-07-12
- [x] Reuse existing `TaskDetailsDrawer.jsx` structure (Stage 5) — done 2026-07-12
- [x] Parse pass/fail from test command output (Stage 6) — done 2026-07-12
- [x] Bounded retry count distinct from tool-call ceiling (Stage 6) — done 2026-07-12
- [x] Confirm zero-cost/offline path once local model routed (Stage 8) — done 2026-07-12 (local vLLM, no API spend, privacy lock on)
- [x] Confirm role-pin takes effect immediately (Stage 9) — done 2026-07-01

### Medium
- [x] Consolidate Recent Chats into the sidebar's single scroll region instead of its own nested scrollbar (UI Bug Fix 2) — done 2026-07-01
- [ ] Run one real multi-file bug-fix task end-to-end (Stage 4a follow-up)
- [x] Stream tool-call events to UI (Stage 4b) — done 2026-07-02
- [x] Add lightweight step/plan list to task view (Stage 4b) — done 2026-07-02
- [x] Update step/plan list in real time (Stage 4b) — done 2026-07-02
- [x] Wire frontend task view to consume incremental events (Stage 4b) — done 2026-07-02
- [x] Touched-files list in task detail view (Stage 5) — done 2026-07-12
- [x] Per-file syntax-highlighted diff viewer (Stage 5) — done 2026-07-12
- [x] Live terminal/log pane for shell output (Stage 5) — done 2026-07-12
- [x] Revert-file quick action (Stage 5) — done 2026-07-12
- [x] Per-workspace test/build/lint command settings (Stage 6) — backend + API done 2026-07-12 (settings-UI form pending)
- [x] Run configured test command after an edit (Stage 6) — done 2026-07-12
- [x] Feed test failures back into next iteration (Stage 6) — done 2026-07-12
- [x] Expose dedicated code-structure query tool to `code` mode with citations (Stage 7) — done 2026-07-01
- [x] One-click route `code` mode to local model (Stage 8) — done 2026-07-01 (zero clicks: coder-role auto-suggestion + existing role routing)
- [x] Specialize Trials for coding subtasks (Stage 9) — done 2026-07-01
- [x] Let operator pin trial winner to `coder` role (Stage 9) — done 2026-07-01

### Hard
- [x] Thread streamed deltas through `_chat()`/`governed_chat()` without breaking tool-loop accumulation (Stage 4b) — done 2026-07-02
- [x] Stream model output tokens to UI end-to-end (Stage 4b) — done 2026-07-02
- [x] Test: reconnect/resume mid-stream doesn't duplicate/drop events (Stage 4b) — done 2026-07-02 (full-snapshot design makes this structural)
- [x] Add dedicated relation-query verbs ("what calls X" / "where used" / "what imports") (Stage 7) — done 2026-07-01
- [x] Extend Warsat fit-scoring to flag coding-capable local models for `coder` role (Stage 8) — done 2026-07-01
- [x] Test: local-routed `code` mode completes a real task **(env-block RESOLVED 2026-07-12)** (Stage 8) — a `mode=code` agentic task ran end-to-end on the local Qwen model with 2 real `rag_search` tool executions (plan + execute phases); a *file-editing* coding task specifically is the remaining validation
- [x] Blind-compare models on a real coding subtask (Stage 9) — done 2026-07-01

### Very Hard
- [x] Add real provider-level token streaming to `backend/models/providers.py` for OpenAI/Anthropic/Gemini/local-OpenAI-compatible adapters (Stage 4b) — done 2026-07-02, incl. fixing a pre-existing break where local providers (vllm/llamacpp) couldn't chat at all
- [x] Replace regex-based entity/call extraction in `backend/rag/graph.py` with AST-based parsing (Stage 7) — done 2026-07-03: whole-file `ast.parse` from disk (mtime-guarded against stale indexes), call edges only from real `ast.Call` nodes with builtins filtered; regex kept solely as fallback for non-Python scripts/unparseable files, and docs/CSS/HTML no longer emit structural edges

---

## Stage 0: Trusted Dev Workspace Foundation — ✅ COMPLETE (verified)

Branch: `codex/trusted-dev-workspace-v1` · Commit: `1122020`

- [x] Add `trusted: bool` (default `False`) to workspace root records (`backend/core/workspace.py`)
- [x] Confirm-to-enable modal (states what trusted mode grants, requires explicit confirmation)
- [x] One-click revoke
- [x] Extend approval check (`backend/core/security.py`, `backend/core/approvals.py`) to skip `one_time_approval` for `workspace`/`system` tool categories inside a trusted root
- [x] Audit/trace path unchanged — only the human-approval step is skipped
- [x] No change to `privacy_lock`, remote model gating, or web broker approval behavior
- [x] Persistent, always-visible banner/badge while a session is in a trusted workspace
- [x] Test: untrusted workspace — `fs_write` still requires approval (regression guard)
- [x] Test: trusted workspace — `fs_write`/`fs_mkdir`/`fs_move` execute without approval but still produce an audit/tool_call row
- [x] Test: revoking trust mid-session blocks the next call
- [x] Test: path traversal outside the trusted root is rejected regardless of trust
- [x] Validation: backend smoke 48/48 (native + Docker), frontend build, repo safety check, live Playwright pass

**Verification note:** confirmed live — `backend/core/workspace.py:38,125,201,225,730,772,779` implements `trusted`/`set_trusted`/`is_trusted` exactly as described. Test `testTrustedWorkspaceBypassesFileWriteApproval` exists in `tests/testBackendSmoke.py:1474`.

---

## Stage 1: Real Shell Execution — ✅ COMPLETE (verified)

Branch: `codex/shell-exec-v1` · Commit: `9a6d796`

- [x] Async subprocess execution, `cwd` pinned to workspace root (non-escapable)
- [x] Minimal safe environment (no host secrets injected)
- [x] Stream stdout/stderr incrementally into task log/trace
- [x] Per-call timeout (configurable, default ~120s)
- [x] Output size cap with archival for overflow (reuse `archive_expand` pattern)
- [x] Callable only when workspace is `trusted`; otherwise stays disabled/approval-required
- [x] Soft guardrail deny-list for catastrophic patterns
- [x] Command text fully audited verbatim
- [x] Test: command runs, streams output, respects cwd
- [x] Test: timeout kills a long-running command cleanly and reports it
- [x] Test: untrusted workspace — call rejected/stubbed as before
- [x] Test: output over size cap archives correctly and remains retrievable
- [x] Validation: backend smoke 49/49 (native + Docker), frontend build, repo safety check

**Verification note:** `backend/mcp/tools.py:401-408` — `shell_exec` has `"enabled": True, "implemented": True` (not the disabled stub the original grounding section described pre-Stage-1). `docker_control` (`:528-535`) is still correctly `"enabled": False` — matches "explicitly out of scope" in the plan. Test `testShellExecRequiresPermissionFlagAndTrustedWorkspace` exists at `tests/testBackendSmoke.py:1526`.

---

## Stage 2: Git-Aware Tools — ✅ COMPLETE (verified)

Branch: `codex/git-tools-v1` · Commit: `ba85940`

- [x] `git_status` tool
- [x] `git_diff` tool (structured hunks, not just raw text)
- [x] `git_log` tool
- [x] `git_add` tool
- [x] `git_commit` tool — runs without approval in trusted workspace
- [x] `git push` (and any remote-touching command) stays approval-required regardless of trust
- [x] Docker runtime image: add `git` binary
- [x] Docker runtime image: `safe.directory '*'` config
- [x] Test: `git_diff`/`git_status` return structured, parseable results
- [x] Test: `git_commit` executes without approval in trusted workspace; `git push` still requires approval
- [x] Test: non-git directory returns clean structured error, not a crash
- [x] Validation: backend smoke 50/50 (native + Docker), repo safety check

**Verification note:** all five tool IDs confirmed registered and dispatched in `backend/mcp/tools.py` (definitions at `:423,442,463,484,506`; dispatch at `:771,779,788,796`). Test `testGitToolsRespectTrustAndParseStructuredOutput` exists at `tests/testBackendSmoke.py:1586`.

---

## Stage 3: Patch-Based File Edits — ✅ COMPLETE (verified)

Branch: `codex/fs-patch-v1` · Commit: `bed3281`

- [x] `fs_patch` tool: old-text/new-text anchored replacement with uniqueness check
- [x] Unified-diff apply fallback for multi-hunk changes
- [x] Ambiguous anchor (2+ matches) rejected with clear error, not silent wrong-spot patch
- [x] Multi-hunk diff applies atomically (all-or-nothing)
- [x] Patch failure doesn't corrupt the file
- [x] `fs_write` retained for whole-file creation/replacement; `fs_patch` becomes default for edits
- [x] Both remain trusted-workspace-gated (Stage 0)
- [x] Validation: backend smoke 51/51 (native + Docker), frontend build, repo safety check

**Verification note:** `fs_patch` registered at `backend/mcp/tools.py:309`; `fs_write`'s own description (`:288`) now explicitly says "Prefer fs_patch when editing part of an existing file," confirming the intended default actually shipped. Test `testFsPatchRequiresUniqueMatchAndRespectsTrust` exists at `tests/testBackendSmoke.py:1646`.

---

## Stage 4a: Mode-Aware Iteration Ceiling + In-Loop Context Bounding — ✅ COMPLETE (verified)

Branch: `codex/agentic-coding-loop-v1` · Commit: `5000e0d`

- [x] Replace hardcoded `for attempt in range(15)` with mode-aware budget
- [x] `code` mode: 80 iterations / 900s wall-clock
- [x] Other modes: keep 15 iterations / 180s
- [x] `_bound_tool_loop_messages`: check running message list against `context_governor.needs_compaction` each iteration
- [x] Archive older large tool-result messages into `eviction_log` when over budget
- [x] Replace archived messages with short `archive_expand`-retrievable pointer
- [x] Archive step is defensive — DB failure logs and skips rather than aborting the loop
- [x] Test: `code` mode runs past 15 iterations while other modes still stop at 15
- [x] Test: archiving fires under simulated context pressure, messages replaced by retrievable pointers
- [x] Test: wall-clock budget stops the loop under a mocked clock instead of hanging
- [x] Validation: backend smoke 54/54 (native + Docker), frontend build, repo safety check

**Verification note:** confirmed line-for-line in `backend/engine/agent.py:742-819` — `_tool_loop_budget` returns exactly `{"max_attempts": 80, "max_seconds": 900}` for `code` mode and `{15, 180}` otherwise; `_bound_tool_loop_messages` archives to `eviction_log` with an `archive_expand`-style pointer message, wrapped in a try/except that logs-and-skips on DB failure. Tests `testGovernedChatArchivesOldToolResultsUnderContextPressure` and `testGovernedChatStopsOnTimeBudgetWithoutHanging` exist at `tests/testBackendSmoke.py:1750,1779`. All plan-doc line citations still match current code.

**✅ Open gap RESOLVED 2026-07-12** (was: no real model endpoint; Stage 4a had only been verified against a scripted mock). A real local model is now deployed and driven end-to-end — see **Session 2026-07-12** below.

- [x] Configure a real model endpoint (local vLLM or API key) in a test environment — done 2026-07-12: Qwen2.5-3B-Instruct deployed via WarSat (`--tool-call-parser hermes`), healthy on `127.0.0.1:8001`, registered role `main`
- [ ] Run one real multi-file bug-fix task end-to-end through Stage 0-4a, confirm no ceiling/context-corruption issues — **(Medium)** — *de-risked but not yet run:* the loop, real-model tool-calling, and tool execution are now proven; what remains is a task that actually *edits files* (our 2026-07-12 task was search/summarize)

---

## Stage 4b: Stream Model Output and Tool Events to the UI — ✅ COMPLETE (2026-07-02)

Branch: `codex/agentic-coding-ux-streaming-v1` (not yet started)

**Verification note — plan doc understates this stage's true size.** The plan's Grounding section says "No streaming, no prompt caching" but Stage 4b's scope reads like a UI-only task. It isn't: `backend/models/providers.py:289` hardcodes `"stream": False` in the OpenAI-format request builder used for OpenAI and local OpenAI-compatible endpoints, and there is no chunked/SSE response parsing anywhere in the provider layer. There *is* an existing generic SSE channel (`new EventSource("/api/events")` at `frontend-src/src/app/App.jsx:589`) that Stage 4b can extend for delivery, but token-level streaming has to be built into the provider layer first — that's the Very Hard item below, and it's a prerequisite, not a parallel task.

- [x] Add real provider-level token streaming — done 2026-07-02: `chat(model, ..., on_delta=None)` — `None` keeps the exact previous non-streaming behavior; a callback opts into SSE streaming with `{"type":"text"}` / `{"type":"tool_call"}` events, and the `(text, tool_calls)` return contract is identical either way (tool-call fragments assembled across chunks, crashing consumers can't abort the request). Implemented for OpenAI-format (API + all local runtimes), Anthropic (content_block events incl. `input_json_delta`), and Gemini (`:streamGenerateContent?alt=sse`).
- [x] **Pre-existing break found and fixed while in there:** `chat_sync` raised "Provider vllm is not supported" for every local provider — the default `main-vllm` model could never chat at all (masked by the no-live-model env-block). All non-Anthropic/Gemini providers now route through the OpenAI-format path, with auth optional for local runtimes (API providers still require a key). Regression test added.
- [x] Thread streamed deltas through `_chat()` / `governed_chat()` — done 2026-07-02: `_stream_delta_handler` appends to `task.stream_text` (GIL-safe field writes from the provider worker thread) and triggers throttled broadcasts (150ms, immediate on tool_call) via the already-thread-safe `_trigger_broadcast`; Stage 4a's message accumulation untouched (all three existing scripted `_chat` mocks updated for the new kwarg)
- [x] SSE delivery channel — done: existing `/api/events` + full-task-snapshot push reused. **Pre-existing break found and fixed:** producers pushed *raw* snapshots but the frontend event handler only dispatches on wrapped keys (`data.task`), so live task updates were silently dead on the client; payloads are now wrapped `{"task": snapshot}`
- [x] Stream model output tokens to the UI as generated — done: `task.streamText` (capped 4k) rides every snapshot; drawer paints it live
- [x] Stream tool-call events to the UI — done: phase + tool steps with running/done/error status
- [x] Lightweight step/plan list in the task view — done: "Live Activity" block in `TaskDetailsDrawer` overview (step list + live text pane)
- [x] Update step list in real time — done: broadcasts on step add/finish
- [x] Wire frontend to consume incremental events — done: `App.jsx` merges live snapshots straight into the open drawer (full detail refetch only on terminal status, instead of a REST refetch per event)
- [x] Test: streamed events arrive incrementally — `testGovernedChatStreamsTokensAndStepsToListeners`: partial text observable mid-stream, step list advances live, listener queue receives wrapped snapshots
- [x] Test: reconnect/resume — every SSE message is a self-contained full snapshot, so a reconnecting client rebuilds state from any single message; asserted in the same test (no incremental deltas exist to duplicate/drop)
- [x] Validation: backend smoke 60/60, frontend build, repo safety check (2026-07-02)
- [x] Validation: live browser pass — dry-run task streamed status/steps into the open drawer purely via SSE (5/5 checks, zero console errors); screenshots in session scratchpad

**Definition of done (Stage 4 overall, once 4b lands):** a real multi-file bug fix completes in one task without an artificial ceiling, and the operator can watch it happen live.

---

## Stage 5: Coding-Oriented Task UX — ✅ IMPLEMENTED 2026-07-12 (frontend render tests pending)

Branch: `codex/agentic-coding-loop-v1` · Commits: `9726922` (backend), `77976f2` (frontend)

**Implementation note:** built as two new tabs on the existing `TaskDetailsDrawer` (not a new view),
backed by three new endpoints (`POST /api/workspace/git-status` · `/git-diff` · `/git-restore`,
reusing the MCP git layer). Diff colours are semantic (+/- green/red, hunk blue), theme-independent.
`git-restore` carries git_commit's trust/approval gating; in an untrusted workspace the UI shows an
"approve it, then retry" notice rather than silently no-op'ing.

- [x] Reuse existing `TaskDetailsDrawer.jsx` structure rather than building a new view — done (Changes + Terminal tabs added in place)
- [x] Add touched-files list to task detail view — done (Changes tab, from git-status entries)
- [x] Per-file unified diff viewer, syntax-highlighted — done (`DiffView`, +/- and hunk colouring)
- [x] Live terminal/log pane for shell output — done (Terminal tab: shell_exec output + live `streamText`)
- [x] Quick action: view diff for a given file — done (click a file → its diff loads)
- [x] Quick action: revert a single file's change (`git checkout -- <path>`) — done, with trust/approval gating
- [~] Test: diff viewer renders correctly for add/modify/delete/rename — **backend endpoints smoke-tested** (`testStage5GitReviewEndpoints`); the frontend *render* is build-verified + loads with zero console errors, but a Playwright render assertion isn't written yet (opening the drawer was flaky to script in-session)
- [~] Test: terminal pane updates live during a running shell command — not automated yet
- [~] Test: revert action restores the file and is reflected in the diff view — backend gating tested; the frontend revert→refresh flow isn't Playwright-asserted yet
- [x] Validation: backend smoke **104 passed**, frontend build green

**Dual-input a11y (the non-negotiable bar):** tablist now has full keyboard nav (Arrow/Home/End move
+ focus); every action is a real `<button>` (keyboard + mouse), the diff pane is focusable/scrollable,
no hover-only or shortcut-only paths. A dedicated keyboard-only + mouse-only Playwright pass over the
drawer is the remaining a11y verification (pairs with the render tests above).

**Definition of done:** reviewing what a coding task did feels like reviewing a PR, not scrolling a
chat log. **Implemented + backend-verified;** remaining = the frontend render/interaction + a11y
Playwright tests.

---

## Stage 6: Test-Loop Integration — ✅ BACKEND COMPLETE 2026-07-12 (settings UI pending)

Branch: `codex/agentic-coding-loop-v1` · Commit: `0825a22`

**Implementation note:** the loop runs *inside* `governed_chat`'s existing tool loop (not a wrapper
around `execute()`), so the reopens share its one wall-clock budget rather than each getting a fresh
900s — this is what keeps it "within Stage 4 budget" — and they keep full edit-history context
(matters for weak local models). Only fires after a real file-mutating tool (`fs_patch`/`fs_write`/
`fs_move`), and skips loudly + inspectably (`task.log` + `task.seen("test_skipped", …)`) when no
command is set or shell isn't permitted.

- [x] Per-workspace settings for test/build/lint commands (operator-configured once per repo) — **backend + API done** (`workspace.set_workspace_commands`/`get_workspace_commands`, `POST /api/workspace/commands`, surfaced in `_public_item`); **settings-UI form still pending** (belongs to the UI/UX pass, under the dual-input a11y bar)
- [x] In `code` mode, execution runs the configured test command after an edit — done (`governed_chat`, gated on an actual file mutation)
- [x] Parse pass/fail result from test command output — done (`_parse_test_result`, exit code; no fragile scraping)
- [x] Feed failures back into the next iteration within Stage 4 budget — done (reopen injects the test output as a message and `continue`s the same loop)
- [x] Bounded retry count distinct from the raw tool-call ceiling — done (`_test_loop_budget` = 3 reopens, separate from the 80 tool-call ceiling)
- [x] Test: configured test command runs after an edit and result is captured — `testStage6TestLoopReopensOnFailureThenStopsOnPass`, `…PassFirstRunNoReopen`
- [x] Test: a failing test feeds back into the next iteration's context — `testStage6TestLoopReopensOnFailureThenStopsOnPass`
- [x] Test: retry ceiling stops the loop instead of looping forever — `testStage6TestLoopStopsAtRetryBudget` + `…TimeBudgetHaltsReopens`
- [x] Validation: backend smoke **103 passed, 1 skipped** (incl. 6 new Stage 6 tests) 2026-07-12; frontend build n/a (no UI change yet)

**Definition of done:** "fix this bug" can mean edit → test → see it fail → fix → test → pass,
autonomously, inside one task. **Backend mechanics complete + tested;** a real end-to-end run needs
the settings-UI form (or an API call) to set the command + a file-editing coder model (the open
Stage 4a/8 validation).

---

## Stage 7 (Differentiator): Code-Structure-Aware Graph — ✅ COMPLETE (2026-07-03)

Branch: `codex/code-aware-rag-v1`

**Verification note — this stage is materially ahead of what the plan doc claims ("not started").** `backend/rag/graph.py` already:
- extracts typed nodes: `function`, `class`, `file`, `folder`, `document`, `concept` (`_kind`, `:81-90`)
- extracts typed edges: `imports` (`:189-195`), `defines` (`:198-206`), `calls` (`:209-217`), `references`, `located_in`, `mentions`, `related_to`
- is exposed as a `graph_search` MCP tool (`backend/mcp/tools.py:48`, dispatch `:709`) already usable by any mode, with evidence/citations attached to every node and edge

What's actually still missing (the real remaining gap):
- [x] ~~Extend graph ingestion with typed function/class/module nodes~~ — already exists
- [x] ~~Extend graph ingestion with typed imports/calls/defines edges~~ — already exists
- [x] Replace regex-based entity/call extraction with AST-based parsing — done 2026-07-03. Design: chunks are 80-line overlapping/stripped/truncated fragments (not parseable alone), so `build()` parses the **full file from disk** per source (`_workspace_file_text` → `_python_ast_facts`), guarded by the chunk's indexed `mtime` so AST line numbers still match chunk line ranges; each fact (import/define/call, with lineno) is attached to the first chunk covering its line, so evidence cites the chunk actually containing the statement (overlap deduped via an emitted-fact set). Calls come only from real `ast.Call` nodes (`Name`/`Attribute` targets), with Python builtins filtered — docstring/comment/string `identifier(` text no longer produces edges. Fallbacks: unparseable/changed/missing Python and non-Python scripts (.js/.jsx/.ts/.tsx) keep the regex path, now with a control-flow-keyword deny-list; prose/markup (.md/.html/.css/docs) no longer emit calls/defines/imports edges at all (mentions/references only — `rgba(...)` in CSS is no longer a "call"). Test: `testGraphBuildUsesAstNotRegexForPythonCallEdges`.
- [x] Add dedicated relation-query verbs — done 2026-07-01: `graph.query_relations(entity, relation, direction)` traverses typed edges (direction-aware, basename matching for paths) instead of keyword scoring; "what calls X" = `relation=calls, direction=in`, "what does Y import" = `relation=imports, direction=out`
- [x] Expose a dedicated code-structure query tool — done 2026-07-01: `graph_relations` tool (in `TOOL_DEFINITIONS`, so offered to the model in every tool-loop phase) + `POST /api/graph/relations`, evidence/citations on every edge
- [x] Keep workspace-scoped and local-only (already true — confirmed via `rag.chunks_for_path(path)` scoping)
- [x] Test: structural queries return correct results — `testGraphRelationsAnswersStructuralQueries` covers what-calls/what-imports/where-used/unknown-entity against a built fixture graph
- [x] Test: AST precision — `testGraphBuildUsesAstNotRegexForPythonCallEdges` asserts phantom calls in docstrings/comments/strings and builtins produce zero edges while the real call, imports, and defines still resolve with citations
- [x] Validation: backend smoke 61/61 (2026-07-03); earlier relation-verb pass validated at 56/56 (2026-07-01)

**Definition of done:** the agent (and operator, via chat) can answer structural codebase questions instantly and *accurately* from the graph instead of paying tool-call round trips to re-search every time.

---

## Stage 8 (Differentiator): Local-Model Coding Routes via WarSat — ◐ FUNCTIONALLY IMPLEMENTED (file-edit validation pending)

Branch: extends existing Warsat fit-scoring work

**Verification note:** `backend/models/registry.py:23` already lists `"coder"` as a first-class entry in `MODEL_ROLES`, and `key_for_role()` (`:334`) already does role-based model lookup with fallback — so the routing plumbing Stage 8 needs already exists. What's missing is the actual capability-flagging logic: no `fit`/`score`/`coder`-detection logic exists anywhere in `backend/warsat/` today (checked `__init__.py`, `protocols/`, `providers/`).

- [x] Extend Warsat model fit scoring to flag coding-capable local models for the `coder` role — done 2026-07-01: `registry.suggest_role()` (token + collapsed-name matching for Qwen-Coder/DeepSeek-Coder/CodeLlama/StarCoder/Codestral/granite-code-class names, conservative `helper` otherwise) wired into `scan_gguf` suggestions, `import_gguf` default role, and Warsat `make_plan` (explicit role still wins; falls back to protocol default)
- [x] Route `code` mode to a local model once deployed — done via existing plumbing: `execution_role("code") → "coder"` → `key_for_role("coder")` picks the first reachable coder-role model, and Warsat-deployed coding models now register with role `coder` automatically. No extra click needed at all.
- [x] Confirm zero API cost / fully offline path when local model is selected — done 2026-07-12: ran chat + a `mode=code` agentic task entirely against local Qwen2.5-3B (privacy lock on, no API spend, no data leaving the machine)
- [x] Test: `code` mode routed to local model completes a real task end to end — **(env-block RESOLVED 2026-07-12)**: local Qwen `mode=code` task completed with 2 real `rag_search` tool executions. *Caveat:* it was a search/summarize task; a file-editing *coding* task (write/patch a file, run tests) is the remaining specific validation — the model was deployed with role `main`, not `coder`, so pin a coder-capable model (e.g. Qwen2.5-Coder) for that run
- [x] Validation: backend smoke 56/56 (incl. `testCodingModelsSuggestCoderRole`), repo safety check passed (2026-07-01)

**Definition of done:** a real coding task can run entirely against a local model with zero tokens spent and zero data leaving the machine, end to end through the Stage 0-6 pipeline.

---

## Stage 9 (Differentiator): Coding-Task Trials — ✅ COMPLETE (2026-07-01)

Implemented in the existing Trials subsystem.

**Verification note:** `backend/trials/models.py` already defines a `"model"` experiment type and includes `"code"` in `ROUTABLE_MODES` (`:50`) — the general Trials scaffold this stage extends already exists and already knows about `code` mode. No coding-subtask-specific blind-comparison or pin-to-`coder`-role flow exists yet.

- [x] Specialize Trials for coding subtasks — done 2026-07-01: `backend/trials/coding.py` `coding_compare()` builds a code-oriented prompt (objective + optional starting code), extracts the fenced candidate from each response, and scores objectively: syntax check (`ast.parse`), expected-content hits, and real test execution (operator asserts run against each candidate in an isolated `python -I` subprocess, gated behind the existing `allow_shell_execution` permission — static scoring otherwise)
- [x] Blind-compare on an actual coding subtask — done: model identity hidden behind A-D labels until reveal (reuses the legacy blind-run store, so existing reveal flow applies); per-label objective scores are visible while blind, plus a `suggestedLabel` for the top score. `POST /api/trials/coding-compare` + a new "Coding Trial" tab in TrialsView (form → blind scored outputs → reveal → pin)
- [x] Pin winner to `coder` role — done: `POST /api/trials/{run_id}/pin-role` → new `registry.set_role()` (registry-level, unlike the preference-only `save_routing`); requires reveal first, records previous role, audited
- [x] Role change takes effect immediately — verified in test: after pin, `key_for_role("coder")` resolves to the pinned model with no restart, which is exactly what code mode's execution phase calls
- [x] Test: `testCodingTrialBlindCompareScoresAndPinsCoderRole` — scripted two-model trial (good vs syntactically-broken candidate): correct scoring, blind-until-reveal, reproducible scores across reruns, pin-before-reveal rejected, immediate role routing
- [x] Validation: backend smoke 57/57, frontend build, repo safety check passed (2026-07-01)

**Definition of done:** operator can, from inside Rasputin, decide "which model is actually best at fixing bugs in this codebase" with evidence, and have that decision take effect immediately.

---

## Additional UI/UX Bug Fixes (reported 2026-07-01)

**Scope note:** these two are unrelated to coding-agent competitiveness — they belong to the separate UI-upgrade track — but are tracked here per explicit user request rather than split into another doc. Both root-caused by reading the actual source, not guessed from the screenshot.

### UI Bug Fix 1: Theme switch doesn't change the accent color on Bootstrap-based views

Reported: selecting a different platform theme (e.g. "Cyberpunk Neon") correctly changes the background, but buttons/highlights/active-nav accents stay the original orange (`rasputin-light`'s accent) no matter which theme is selected. Reproduced in the Settings view (`Save Changes` button, active sidebar item, "Strict type checking" validation text).

**Root cause, confirmed in code:** `frontend-src/index.html`'s inline theme script (`apply()`, `:38-60`) correctly sets `--base-accent` (and `--base-bg`/`--base-text`/aurora vars) per theme on `document.documentElement`, and that flows correctly through `--dash-accent` → `--ras-accent` → `--bs-primary` (`frontend-src/src/styles/rasputin.css:21,42`). But `frontend-src/src/styles/rasputin.css:43` hardcodes:
```css
--bs-primary-rgb: 189, 74, 40;   /* = rasputin-light's accent, #bd4a28, as a static RGB triple */
```
This never updates when the theme changes. Bootstrap 5 components (used throughout `features/settings/*.jsx` via `react-bootstrap`) rely heavily on `rgba(var(--bs-primary-rgb), alpha)` for hover/active/subtle-background states — those stay locked to `rgb(189, 74, 40)` regardless of which theme sets `--bs-primary` correctly. That's the exact orange seen in every theme in the screenshot.

- [x] Add a hex→rgb conversion in `frontend-src/index.html`'s `apply()` function and `root.style.setProperty("--bs-primary-rgb", ...)` alongside the existing `--base-accent` line — done 2026-07-01
- [x] Visually verify Bootstrap-driven accents follow the selected theme — verified live via Playwright against a fresh isolated instance: cyberpunk-neon → `255, 0, 153` (Save Changes button renders `rgb(255, 0, 153)`), ocean-abyss → `0, 204, 255`, rasputin-light → back to `189, 74, 40`, rasputin-dark → `#2fe3a0`; accent survives reload via the boot script. Screenshots in session scratchpad `shots/`.
- [x] Grep for other hardcoded `-rgb`/hex duplicates of theme colors — only `--bs-light-rgb` remains, which is a theme-independent neutral, left as is; `--bs-primary-rgb` in `rasputin.css` kept as documented fallback

### UI Bug Fix 2: Recent Chats has its own nested scrollbar instead of one sidebar scrollbar

Reported: the sidebar's "Recent Chats" section scrolls independently in its own boxed region, rather than the sidebar as a whole having a single scrollbar that reveals Recent Chats as you scroll down.

**Root cause, confirmed in code:** `frontend-src/src/components/shell/DashSidebar.jsx` — the outer sidebar `<aside>` is `overflow-hidden` (`:127`), so the sidebar itself never scrolls. The Recent Chats list is a separate inner container with its own `overflow-y-auto` (`:224`, `flex min-h-0 flex-1 ... overflow-y-auto`), making it the *only* scrollable region, boxed off from the pinned nav items and pinned Settings entry above/around it. This was a deliberate original design (pinned nav + pinned Settings + independently-scrolling Recent Chats, per prior UI-upgrade work), but the result reads as an awkward nested scrollbar rather than one natural sidebar scroll.

- [x] Decide pinned vs. scrolling regions — Brand + New Chat pinned at top, privacy chip pinned at bottom, nav + Settings + Recent Chats scroll as one region
- [x] Restructure `DashSidebar.jsx` so nav + Recent Chats share a single `overflow-y-auto` region — done 2026-07-01
- [ ] Re-verify collapsed/hover-expand sidebar states still look correct after the scroll-region change — desktop expanded state verified; mobile overlay exercised 2026-07-03 (see UI regression pass below); collapsed-rail hover-expand still not explicitly exercised
- [x] Test: sidebar scrolls as one region — verified live via Playwright with 14 seeded sessions: exactly one scrollable element in the `<aside>` (contains both nav and chat items, `scrollHeight` 1137 > `clientHeight` 635), scrolling it brings the last recent chat fully into view
- [x] Validation: live browser check on a narrow/mobile viewport — done 2026-07-03 as part of a full UI regression pass (see UI Regression Pass below)

### UI Regression Pass (2026-07-03): full desktop + mobile sweep, 4 real bugs found and fixed

Playwright sweep of all 11 views at 1440×900 and 390×844 against a live instance (auth-bypass test mode): console/page errors, horizontal overflow, and per-view screenshots. Desktop was clean everywhere. Mobile surfaced real breakage:

- [x] **Mobile nav completely dead** — legacy `body.mobile-sidebar-open::before` backdrop (z-1050, no click handler) in `rasputin.css` sat above the new DashSidebar drawer (z-30) and its scrim (z-20), eating every tap once the drawer opened; invisible in dark mode. Removed — DashSidebar renders its own scrim with a close handler.
- [x] **Sessions view count mismatch** — "All"/header showed the fetched list length (capped at 100) while "Unfiled" showed the true DB count (e.g. All 100 vs Unfiled 160). `AgentHub.sessions()` now returns `total` (real table count); the view uses it and notes "Showing the N most recent."
- [x] **Dashboard/Activity/Models/Warsat/Trials/Archive clipped on mobile** — two causes: `grid gap-5 lg:grid-cols-[…]` without a base template (implicit auto column sizes to content; a Recharts inline width then locks the whole column wide), and inline `gridTemplateColumns` styles on `w2-main-grid` that override the ≤800px single-column media query. Fixed with explicit `grid-cols-1` bases, per-view `w2-main-grid` column CSS (media-query collapsible), `w-full min-w-0` on the `mx-auto` root columns (cross-axis auto margins cancel flex stretch), flex-wrap on the Activity/stat headers, and KPI row 1-col below `sm`.
- [x] Re-verified after fixes: all 9 nav views + sessions + settings fit at 390px with zero console errors; desktop two/three-column layouts confirmed intact by screenshot; backend smoke 61/61.

---

## Session 2026-07-12: Real-Model Verification + Local-Provider Tool-Calling Fixes

Branch: `codex/agentic-coding-loop-v1`. Resolved the standing "no real model endpoint"
env-block (Stage 4a/8) by deploying and driving a real local model — and, doing so, found
and fixed **two pre-existing local-provider breaks** (in the same spirit as the Stage 4b
`chat_sync` fix at line 182: local models that looked healthy couldn't actually be used).

**Real-model verification (env-block resolved):**
- [x] Deployed **Qwen2.5-3B-Instruct through WarSat** end-to-end (plan → approval → pull → start →
  probe → registered), healthy on `127.0.0.1:8001`, registered role `main`.
- [x] Proved the **agent tool loop works** with a controllable mock emitting valid streaming
  `tool_call`s (parses → executes the real tool → feeds result back → completes, in both plan and
  execute phases). The loop was never the blocker.
- [x] Proved it **with the real model**: a `mode=code` task ran `tool: rag_search → plan made →
  tool: rag_search → executed → done` — Qwen itself emitted the tool calls, vLLM's hermes parser
  extracted them, Rasputin executed them. Plain chat returned a correct answer with no error.

**Fix 1 — local runtimes degrade gracefully when they reject tools** (`backend/models/providers.py`,
commit `3c653c1`). vLLM started without `--enable-auto-tool-choice` returns **HTTP 400 on every
tool-bearing chat request**; since the agent sends `TOOL_DEFINITIONS` on every turn, a healthy local
model was 100% unusable. `chat_sync` now (local runtimes only; remote APIs untouched) retries once
without tools on any tools-bearing 400 and caches the model key so later calls skip tools; also
clamps `max_tokens` to the model context on the `max_model_len` 400. Fixes conversational chat on
tool-less deploys; agentic tool-execution still needs a parser (Fix 2).
- [x] Implemented + unit-checked + verified in the running app (real chat returned "391", no 400).

**Fix 2 — vLLM `--tool-call-parser` is per-deploy, not hardcoded `hermes`** (`backend/warsat/__init__.py`
+ `backend/api/warsat_api.py`, commits `3c26a25`, `100a905`). WarSat hardcoded `--tool-call-parser
hermes` for *every* vLLM deploy — wrong for non-Hermes models (silently corrupts their tool calls).
Now opt-in per deploy: a sanitized `toolCallParser` enables `--enable-auto-tool-choice
--tool-call-parser <parser>`; with none set, tool flags are omitted and Fix 1 handles the tool-less
runtime. Also added `tool_call_parser` to `WarsatPlanIn` (the API model was stripping it).
- [x] Unit-verified (default → no flags; explicit parser → emitted + sanitized) and verified through
  the real plan/deploy path (the Qwen deploy's docker command carried the flags).

**Still open (the real remaining coding-agent validation):**
- [ ] Run a real *file-editing* coding task on a local model (write/patch a file, run tests, iterate)
  — deploy a **coder-role** model (e.g. Qwen2.5-Coder) with its parser and run in a **trusted**
  workspace. This is what fully closes Stage 4a's bug-fix item, Stage 8's coding-task test, and the
  "real coding session on local model" success criterion.

---

## UI/UX Work

Tracked here per the same "fold UI items in on request" precedent as the *Additional UI/UX Bug
Fixes* section above. Split into coding-agent-adjacent UI and the broader daily-driver UI/UX track.

### ⛔ Non-negotiable requirement: dual input independence (applies to ALL UI work below)

**Every screen must be fully usable with a keyboard alone** (for someone who cannot use a mouse)
**AND fully usable with a mouse alone** (for someone who cannot use a keyboard). This is a hard
acceptance bar on *every* item in this section and every new/migrated component, dialog, drawer,
menu, and the Warsat deploy form — not a separate phase to defer. If a control fails either pass,
the work isn't done. (WCAG 2.1.1 Keyboard, 2.1.2 No Keyboard Trap, 2.4.7 Focus Visible, 2.5.1
Pointer Gestures.)

**Keyboard-only (no mouse):**
- [ ] Every interactive element is reachable and operable via Tab / Shift+Tab + Enter/Space, with
  arrow-key movement inside menus, lists, chip groups, side panels, and the `/` command menu.
- [ ] A visible focus ring on every focusable element — never `outline: none` without an equal-or-
  better replacement.
- [ ] Logical DOM-ordered focus sequence; **no keyboard traps**; `Esc` closes any menu/dialog/drawer
  and returns focus to the control that opened it (focus trapped while open — `useFocusTrap` already
  exists and should be used everywhere, not just `Drawer`).
- [ ] Skip-to-main-content link (already present) is the first tab stop and works.
- [ ] Core actions have discoverable keyboard paths (send message, new chat, open `/` command menu,
  switch view, submit/cancel in dialogs) and are documented where non-obvious.

**Mouse-only (no keyboard):**
- [ ] **No feature is reachable only by keyboard.** Every keyboard shortcut has an equivalent
  visible, clickable control — e.g. the `/` command menu must also open via its composer button
  (keep that parity as the composer evolves); Enter-to-send must always coexist with the send button.
- [ ] No action depends on a hover-only reveal or a keyboard modifier (no shift/ctrl-click-only
  paths); any hover affordance also responds to plain click/tap.
- [ ] All controls are pointer-operable at comfortable hit-target sizes; nothing needs the keyboard
  to *navigate*. (Raw text entry is served by the OS on-screen keyboard / dictation — the app must
  not block those, but must never *require* a physical keyboard to reach a feature.)

**Verification — run BOTH passes every UI phase (build-green is not enough):**
- [ ] Keyboard-only Playwright pass: drive each core flow with keyboard events only (no `.click()`),
  asserting every step is reachable, focus is visible, and focus is trapped/restored correctly.
- [ ] Mouse-only pass: drive each core flow with pointer only, asserting there are no shortcut-only
  dead ends and no hover-only critical actions.
- [ ] Screen-reader sanity (correct aria role/name/state on every custom widget) rides along with
  the keyboard pass.

### A. Coding-agent / WarSat deploy UI (from Session 2026-07-12)
- [ ] **Deploy-form tool-call-parser field** — the backend/API accept `toolCallParser` now, but the
  Warsat deploy form has no field for it, so enabling tool-calling for a model is currently API-only.
  Add a parser input (with a "none / disable tools" option) to the deploy UI. **(Easy–Medium)**
- [~] **Per-catalog-model parser hint** — backend catalog metadata now emits the conservative,
  non-binding `toolCallParserHint=hermes` for the proven Qwen2.5/vLLM family (including cached
  catalog entries). The deploy GUI still needs to prefill its parser field from that hint. **(GUI pending)**
- [x] **Surface tool-unavailable state** — done in the engine: when a local runtime rejects tools,
  conversational chat may still degrade, but an execution phase records `tools_unavailable`, marks
  the phase step errored, and stops the task instead of accepting tool-less prose as completed work.
  Regression coverage verifies both provider fallback and the agentic fail-visible path.
- [ ] **Per-workspace test/build/lint command settings form** — Stage 6's backend + `POST
  /api/workspace/commands` are done; add a UI (per-workspace settings) to set these commands so
  the edit→test→fix loop is configurable without an API call. **(Medium)**
- [~] Stage 5 (*Coding-Oriented Task UX* above) is implemented (diff viewer, touched-files list,
  live terminal pane); frontend render/interaction plus keyboard-only/mouse-only Playwright passes remain.

### B. Daily-driver UI/UX track
The app was launched + audited 2026-07-12: shell/routing/auth/theming/chat are solid and polished
(zero console errors across 15+ views, light + dark). This is the polish backlog. The design-system
contract is `docs/RASPUTIN_ARCHITECTURE_GUIDE.md` §4. Confirmed near-term items:
- [ ] Theme picker shows the wrong active theme on load — defaults to `rasputin-dark` instead of the
  live theme (`GeneralSettings.jsx:85`). **(Trivial)**
- [ ] Settings "Save" gives no success toast (it does persist). **(Trivial)**
- [ ] Blue Settings "Save Changes" button — it's react-bootstrap `variant="primary"` leaking through
  an un-migrated screen; recolor to the accent (a mini-instance of the react-bootstrap retirement).
  **(Trivial)**
- [ ] `Button` is duplicated and both copies are live (`ModelsView.jsx:43-44`, vanilla vs shadcn) —
  pick the canonical one. **(Small)**
- [ ] Mode-switch silently re-routes the selected model to an unhealthy role model → header shows
  STOPPED (a daily foot-gun). **(Small–Medium)**
- [ ] Retire **react-bootstrap** (16 files: 12 settings screens + workspaces/runtime/audit/auth) onto
  the shadcn primitives + `@theme inline` token bridge (`theme.css`, 36 tokens); remove the global
  `bootstrap.min.css` import — the ~50/50 legacy/modern split is the main coherence debt. **(Large;
  Phases C–E of the roadmap)**
- [ ] Flesh out thin secondary views (Agents / Activity / Memory / Approvals / Archive). **(Medium)**

---

## Explicitly Out of Scope / Unchanged (carried from plan doc, not tasks)

- Deferred product areas: Mail Relay, Timeline Sync, Visual Relay, Field Console PWA, and Local Admin 2FA
- Non-trusted workspaces keep full per-action approval — unchanged by this plan
- Privacy Lock, remote model gating, web-broker approval/redaction behavior — unchanged by every stage
- `docker_control` stays a disabled stub (confirmed still `"enabled": False` at `backend/mcp/tools.py:534`) — out of scope; Warsat's existing approval-gated deploy path untouched

---

## Overall Success Criteria (from plan doc — check when ALL are true)

- [ ] A multi-file bug fix (edit, run tests, iterate, commit) completes in one task with zero manual per-action approval clicks
- [ ] The operator can review what changed like a PR (diff view, not chat scrollback) before or after commit
- [ ] A coding task doesn't stall against the old 15-call ceiling or go silent for minutes with no visible progress
- [~] At least one real coding session runs entirely on a local model through Warsat with no API spend — **substantially met 2026-07-12**: a `mode=code` agentic task ran entirely on a WarSat-deployed local Qwen2.5-3B with real tool execution and zero API spend; full [x] awaits a session that actually *edits code and runs tests*
- [ ] The operator's own unprompted judgment: "I opened Rasputin instead of Codex for this," happening more than once
