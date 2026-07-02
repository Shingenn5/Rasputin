# Coding-Agent Competitiveness — Implementation Checklist

Companion to [`CODING_AGENT_COMPETITIVENESS_PLAN.md`](CODING_AGENT_COMPETITIVENESS_PLAN.md). That doc is the narrative/rationale; this doc is the actionable, checkable task list derived from it. Keep both in sync — when a box here is checked, update the corresponding Status line in the plan doc too.

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
- [ ] Fix hardcoded `--bs-primary-rgb` so Bootstrap components follow the selected theme's accent (UI Bug Fix 1)
- [ ] Configure a real model endpoint for verification (Stage 4a follow-up)
- [ ] Identify/confirm SSE extension point at `frontend-src/src/app/App.jsx:589` (Stage 4b)
- [ ] Quick action: view diff for a file (Stage 5)
- [ ] Reuse existing `TaskDetailsDrawer.jsx` structure (Stage 5)
- [ ] Parse pass/fail from test command output (Stage 6)
- [ ] Bounded retry count distinct from tool-call ceiling (Stage 6)
- [ ] Confirm zero-cost/offline path once local model routed (Stage 8)
- [x] Confirm role-pin takes effect immediately (Stage 9) — done 2026-07-01

### Medium
- [ ] Consolidate Recent Chats into the sidebar's single scroll region instead of its own nested scrollbar (UI Bug Fix 2)
- [ ] Run one real multi-file bug-fix task end-to-end (Stage 4a follow-up)
- [ ] Stream tool-call events to UI (Stage 4b)
- [ ] Add lightweight step/plan list to task view (Stage 4b)
- [ ] Update step/plan list in real time (Stage 4b)
- [ ] Wire frontend task view to consume incremental events (Stage 4b)
- [ ] Touched-files list in task detail view (Stage 5)
- [ ] Per-file syntax-highlighted diff viewer (Stage 5)
- [ ] Live terminal/log pane for shell output (Stage 5)
- [ ] Revert-file quick action (Stage 5)
- [ ] Per-workspace test/build/lint command settings (Stage 6)
- [ ] Run configured test command after an edit (Stage 6)
- [ ] Feed test failures back into next iteration (Stage 6)
- [x] Expose dedicated code-structure query tool to `code` mode with citations (Stage 7) — done 2026-07-01
- [x] One-click route `code` mode to local model (Stage 8) — done 2026-07-01 (zero clicks: coder-role auto-suggestion + existing role routing)
- [x] Specialize Trials for coding subtasks (Stage 9) — done 2026-07-01
- [x] Let operator pin trial winner to `coder` role (Stage 9) — done 2026-07-01

### Hard
- [ ] Thread streamed deltas through `_chat()`/`governed_chat()` without breaking tool-loop accumulation (Stage 4b)
- [ ] Stream model output tokens to UI end-to-end (Stage 4b, depends on provider streaming below)
- [ ] Test: reconnect/resume mid-stream doesn't duplicate/drop events (Stage 4b)
- [x] Add dedicated relation-query verbs ("what calls X" / "where used" / "what imports") (Stage 7) — done 2026-07-01
- [x] Extend Warsat fit-scoring to flag coding-capable local models for `coder` role (Stage 8) — done 2026-07-01
- [ ] Test: local-routed `code` mode completes a real task **(env-blocked — needs a deployed local model)** (Stage 8)
- [x] Blind-compare models on a real coding subtask (Stage 9) — done 2026-07-01

### Very Hard
- [x] Add real provider-level token streaming to `backend/models/providers.py` for OpenAI/Anthropic/Gemini/local-OpenAI-compatible adapters (Stage 4b) — done 2026-07-02, incl. fixing a pre-existing break where local providers (vllm/llamacpp) couldn't chat at all
- [ ] Replace regex-based entity/call extraction in `backend/rag/graph.py` with AST-based parsing — current regex matches any `identifier(` as a "calls" edge, including keywords/builtins, so call-graph edges are noisy (Stage 7)

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

**⚠️ Open gap (standing caveat, not fully closed):** no real model endpoint configured in this environment (no local vLLM, no API keys). Stage 4a verified at the mechanics level with a scripted mock model only.

- [ ] Configure a real model endpoint (local vLLM or API key) in a test environment — **(Easy** — config only, gated on having credentials/GPU access, not code**)**
- [ ] Run one real multi-file bug-fix task end-to-end through Stage 0-4a, confirm no ceiling/context-corruption issues — **(Medium)**

---

## Stage 4b: Stream Model Output and Tool Events to the UI — ☐ PENDING (next up)

Branch: `codex/agentic-coding-ux-streaming-v1` (not yet started)

**Verification note — plan doc understates this stage's true size.** The plan's Grounding section says "No streaming, no prompt caching" but Stage 4b's scope reads like a UI-only task. It isn't: `backend/models/providers.py:289` hardcodes `"stream": False` in the OpenAI-format request builder used for OpenAI and local OpenAI-compatible endpoints, and there is no chunked/SSE response parsing anywhere in the provider layer. There *is* an existing generic SSE channel (`new EventSource("/api/events")` at `frontend-src/src/app/App.jsx:589`) that Stage 4b can extend for delivery, but token-level streaming has to be built into the provider layer first — that's the Very Hard item below, and it's a prerequisite, not a parallel task.

- [x] Add real provider-level token streaming — done 2026-07-02: `chat(model, ..., on_delta=None)` — `None` keeps the exact previous non-streaming behavior; a callback opts into SSE streaming with `{"type":"text"}` / `{"type":"tool_call"}` events, and the `(text, tool_calls)` return contract is identical either way (tool-call fragments assembled across chunks, crashing consumers can't abort the request). Implemented for OpenAI-format (API + all local runtimes), Anthropic (content_block events incl. `input_json_delta`), and Gemini (`:streamGenerateContent?alt=sse`).
- [x] **Pre-existing break found and fixed while in there:** `chat_sync` raised "Provider vllm is not supported" for every local provider — the default `main-vllm` model could never chat at all (masked by the no-live-model env-block). All non-Anthropic/Gemini providers now route through the OpenAI-format path, with auth optional for local runtimes (API providers still require a key). Regression test added.
- [ ] Thread streamed deltas through `_chat()` / `governed_chat()` (`backend/engine/agent.py`) without breaking the existing tool-loop message accumulation from Stage 4a — **(Hard** — note: `on_delta` is invoked from a worker thread; marshal to the event loop before touching asyncio state**)**
- [ ] Identify/confirm the existing SSE extension point (`/api/events`, `App.jsx:589`) as the delivery channel — **(Easy)**
- [ ] Stream model output tokens to the UI as generated (depends on the two items above) — **(Hard)**
- [ ] Stream tool-call events (tool name, args, start/end, result summary) to the UI as they happen — **(Medium** — tool calls are already logged server-side, this is mostly plumbing over the existing channel**)**
- [ ] Add a lightweight step/plan list to the task view — **(Medium)**
- [ ] Update step/plan list as steps complete, in real time — **(Medium)**
- [ ] Wire frontend task view to consume the new incremental events — **(Medium)**
- [ ] Test: streamed events arrive incrementally in a live task view (not just at completion) — **(Medium)**
- [ ] Test: reconnect/resume mid-stream doesn't duplicate or drop events — **(Hard)**
- [ ] Validation: backend smoke suite passes, frontend build, repo safety check — **(Easy)**
- [ ] Validation: live browser pass watching a real/scripted task stream tokens + tool events + step list update in real time — **(Medium)**

**Definition of done (Stage 4 overall, once 4b lands):** a real multi-file bug fix completes in one task without an artificial ceiling, and the operator can watch it happen live.

---

## Stage 5: Coding-Oriented Task UX — ☐ NOT STARTED (verified)

Branch: `codex/coding-ux-v1`

**Verification note:** confirmed `frontend-src/src/features/tasks/TaskDetailsDrawer.jsx` still renders only `ReactMarkdown` (`:157-158,226-227`) and a raw `<pre className="log-box">` (`:210`) — no diff viewer, no file list, no terminal pane exist yet. `CodeSandbox.jsx` exists as a pattern to extend.

- [ ] Reuse existing `TaskDetailsDrawer.jsx` structure rather than building a new view — **(Easy)**
- [ ] Add touched-files list to task detail view — **(Medium)**
- [ ] Per-file unified diff viewer, syntax-highlighted — **(Medium)**
- [ ] Live terminal/log pane for shell output (extend `CodeSandbox.jsx` patterns) — **(Medium)**
- [ ] Quick action: view diff for a given file — **(Easy)**
- [ ] Quick action: revert a single file's change (`git checkout -- <path>` inside trusted workspace) — **(Medium** — needs care around trust/approval gating for a destructive-ish local action**)**
- [ ] Test: diff viewer renders correctly for add/modify/delete/rename — **(Medium)**
- [ ] Test: terminal pane updates live during a running shell command — **(Medium)**
- [ ] Test: revert action restores the file and is reflected in the diff view — **(Medium)**
- [ ] Validation: backend smoke suite passes, frontend build, repo safety check — **(Easy)**

**Definition of done:** reviewing what a coding task did feels like reviewing a PR, not scrolling a chat log.

---

## Stage 6: Test-Loop Integration — ☐ NOT STARTED (verified)

Branch: `codex/test-loop-v1`

**Verification note:** no per-workspace test/build/lint command configuration or auto-run-after-edit logic exists anywhere in `backend/` today (only unrelated hit was Warsat's own deploy test-mode plumbing). Confirmed genuinely not started.

- [ ] Per-workspace settings for test/build/lint commands (operator-configured once per repo) — **(Medium)**
- [ ] In `code` mode, `execute()` (`backend/engine/agent.py:888` area) optionally runs configured test command after an edit — **(Medium)**
- [ ] Parse pass/fail result from test command output — **(Easy)**
- [ ] Feed failures back into the next planning iteration within Stage 4 budget — **(Medium)**
- [ ] Bounded retry count distinct from the raw tool-call ceiling — **(Easy)**
- [ ] Test: configured test command runs after an edit and result is captured — **(Medium)**
- [ ] Test: a failing test feeds back into the next iteration's context — **(Medium)**
- [ ] Test: retry ceiling stops the loop and reports the last failure clearly instead of looping forever — **(Medium)**
- [ ] Validation: backend smoke suite passes, frontend build, repo safety check — **(Easy)**

**Definition of done:** "fix this bug" can mean edit → test → see it fail → fix → test → pass, autonomously, inside one task.

---

## Stage 7 (Differentiator): Code-Structure-Aware Graph — ☐ PARTIALLY IMPLEMENTED (revised after verification)

Branch: `codex/code-aware-rag-v1`

**Verification note — this stage is materially ahead of what the plan doc claims ("not started").** `backend/rag/graph.py` already:
- extracts typed nodes: `function`, `class`, `file`, `folder`, `document`, `concept` (`_kind`, `:81-90`)
- extracts typed edges: `imports` (`:189-195`), `defines` (`:198-206`), `calls` (`:209-217`), `references`, `located_in`, `mentions`, `related_to`
- is exposed as a `graph_search` MCP tool (`backend/mcp/tools.py:48`, dispatch `:709`) already usable by any mode, with evidence/citations attached to every node and edge

What's actually still missing (the real remaining gap):
- [x] ~~Extend graph ingestion with typed function/class/module nodes~~ — already exists
- [x] ~~Extend graph ingestion with typed imports/calls/defines edges~~ — already exists
- [ ] Replace regex-based entity/call extraction with AST-based parsing — **(Very Hard)**. Current `_call_edges` (`graph.py:209-217`) treats *any* `identifier(` as a "calls" edge, including Python keywords/builtins that happen to precede `(` in unrelated contexts — this makes the call graph noisy/low-precision, not the accurate structural graph Stage 7 is meant to deliver.
- [x] Add dedicated relation-query verbs — done 2026-07-01: `graph.query_relations(entity, relation, direction)` traverses typed edges (direction-aware, basename matching for paths) instead of keyword scoring; "what calls X" = `relation=calls, direction=in`, "what does Y import" = `relation=imports, direction=out`
- [x] Expose a dedicated code-structure query tool — done 2026-07-01: `graph_relations` tool (in `TOOL_DEFINITIONS`, so offered to the model in every tool-loop phase) + `POST /api/graph/relations`, evidence/citations on every edge
- [x] Keep workspace-scoped and local-only (already true — confirmed via `rag.chunks_for_path(path)` scoping)
- [x] Test: structural queries return correct results — `testGraphRelationsAnswersStructuralQueries` covers what-calls/what-imports/where-used/unknown-entity against a built fixture graph
- [x] Validation: backend smoke 56/56, repo safety check passed (2026-07-01)

**Definition of done:** the agent (and operator, via chat) can answer structural codebase questions instantly and *accurately* from the graph instead of paying tool-call round trips to re-search every time.

---

## Stage 8 (Differentiator): Local-Model Coding Routes via WarSat — ☐ NOT STARTED (verified, with a head start noted)

Branch: extends existing Warsat fit-scoring work

**Verification note:** `backend/models/registry.py:23` already lists `"coder"` as a first-class entry in `MODEL_ROLES`, and `key_for_role()` (`:334`) already does role-based model lookup with fallback — so the routing plumbing Stage 8 needs already exists. What's missing is the actual capability-flagging logic: no `fit`/`score`/`coder`-detection logic exists anywhere in `backend/warsat/` today (checked `__init__.py`, `protocols/`, `providers/`).

- [x] Extend Warsat model fit scoring to flag coding-capable local models for the `coder` role — done 2026-07-01: `registry.suggest_role()` (token + collapsed-name matching for Qwen-Coder/DeepSeek-Coder/CodeLlama/StarCoder/Codestral/granite-code-class names, conservative `helper` otherwise) wired into `scan_gguf` suggestions, `import_gguf` default role, and Warsat `make_plan` (explicit role still wins; falls back to protocol default)
- [x] Route `code` mode to a local model once deployed — done via existing plumbing: `execution_role("code") → "coder"` → `key_for_role("coder")` picks the first reachable coder-role model, and Warsat-deployed coding models now register with role `coder` automatically. No extra click needed at all.
- [ ] Confirm zero API cost / fully offline path when local model is selected — **(Easy, env-blocked** — needs a deployed local model**)**
- [ ] Test: `code` mode routed to local model completes a real coding task end to end — **(Hard, env-blocked** — needs an actual deployed local coding model to verify**)**
- [x] Validation: backend smoke 56/56 (incl. `testCodingModelsSuggestCoderRole`), repo safety check passed (2026-07-01)

**Definition of done:** a real coding task can run entirely against a local model with zero tokens spent and zero data leaving the machine, end to end through the Stage 0-6 pipeline.

---

## Stage 9 (Differentiator): Coding-Task Trials — ☐ NOT STARTED (verified, with a head start noted)

Branch: extends existing Trials feature (`docs/STAGED_IMPLEMENTATION_BACKLOG.md`)

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
- [ ] Re-verify collapsed/hover-expand sidebar states still look correct after the scroll-region change — desktop expanded state verified; collapsed-rail hover-expand and mobile overlay not yet exercised
- [x] Test: sidebar scrolls as one region — verified live via Playwright with 14 seeded sessions: exactly one scrollable element in the `<aside>` (contains both nav and chat items, `scrollHeight` 1137 > `clientHeight` 635), scrolling it brings the last recent chat fully into view
- [ ] Validation: live browser check on a narrow/mobile viewport — desktop (1440×900) verified; mobile viewport still pending

---

## Explicitly Out of Scope / Unchanged (carried from plan doc, not tasks)

- Everything in `docs/STAGED_IMPLEMENTATION_BACKLOG.md`'s "Explicitly Deferred" section (Mail Relay, Timeline Sync, Visual Relay, Field Console PWA, Local Admin 2FA)
- Non-trusted workspaces keep full per-action approval — unchanged by this plan
- Privacy Lock, remote model gating, web-broker approval/redaction behavior — unchanged by every stage
- `docker_control` stays a disabled stub (confirmed still `"enabled": False` at `backend/mcp/tools.py:534`) — out of scope; Warsat's existing approval-gated deploy path untouched

---

## Overall Success Criteria (from plan doc — check when ALL are true)

- [ ] A multi-file bug fix (edit, run tests, iterate, commit) completes in one task with zero manual per-action approval clicks
- [ ] The operator can review what changed like a PR (diff view, not chat scrollback) before or after commit
- [ ] A coding task doesn't stall against the old 15-call ceiling or go silent for minutes with no visible progress
- [ ] At least one real coding session runs entirely on a local model through Warsat with no API spend
- [ ] The operator's own unprompted judgment: "I opened Rasputin instead of Codex for this," happening more than once
