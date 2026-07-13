# Rasputin Coding-Agent Competitiveness Plan

Goal: get Rasputin to a point where the operator reaches for it instead of Codex CLI or Gemini CLI for real day-to-day LLM prompting and coding. 

Last reviewed: 2026-06-30

> **Security-model update (2026-07-13):** this plan's original Trusted Dev Mode decision was
> narrowed during dual-mode Phases 3–4. Trusted now auto-approves file/git mutations only;
> `shell_exec` requires the separate per-workspace Host Shell capability plus the global shell
> permission. Native Windows executes it as `Rasputin_sbx`. Treat the 2026-06-30 “Current State”
> below as historical; `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` is the live status source.

## Framing

This is not a feature-parity checklist. Cloning what Codex/Gemini already do produces, at best, a worse Codex. Two things have to be true at once:

1. **Close the concrete daily-coding blockers** that currently make Rasputin unusable for real iteration (below).
2. **Lean into what a hosted CLI structurally cannot offer**: this is Rasputin's own product, running against the operator's own machine, with persistent memory/graph of the operator's codebases, free/offline local-model routing, and full inspectability. A plan that only closes gaps gives no reason to switch once it's "as good as." The differentiator stages (7-9) are not polish — they're the actual answer to "why Rasputin."

Stages are ordered by daily friction removed, not by architectural neatness. Stage 0 gates everything after it.

## Grounding: Current State (verified 2026-06-30)

- Agent tool loop exists (`backend/engine/agent.py:754`, `governed_chat`), hard-capped at **15 tool iterations** — too low for a real multi-file edit/test/fix cycle.
- Read tools are solid and already used: `rag_search`, `graph_search`, `fs_tree`, `fs_read`, `fs_search`, `workspace_browse` (`backend/mcp/tools.py`).
- `fs_write`, `fs_mkdir`, `fs_move` exist but each call requires a **separate one-time human approval** (`backend/core/approvals.py`) — no batch or session trust. A 20-file refactor means 20+ clicks.
- `fs_write` replaces whole file content — no diff/patch application.
- `shell_exec` and `docker_control` are **defined but explicitly disabled stubs**: `"enabled": False, "implemented": False` (`backend/mcp/tools.py:374-400`). No shell access exists today, at all.
- No git tool of any kind. No diff viewer, file-tree, or terminal pane in the chat/task UI — task output renders as markdown text and raw `<pre>` log blocks (`TaskDetailsDrawer.jsx`).
- Model providers (`backend/models/providers.py`) already cover OpenAI, Anthropic, Gemini, and local OpenAI-compatible endpoints (vLLM/llama.cpp) with native per-provider tool-calling. No streaming, no prompt caching.
- The repo itself was built via bounded autonomous "Codex passes" (`docs/PASS_QUEUE.md`) that explicitly deferred shell execution, remote MCP, and batch approval as "higher risk than local-file read paths." Nothing in the existing backlog (`docs/STAGED_IMPLEMENTATION_BACKLOG.md`) targets agentic coding velocity — it's aimed at a general safety-first AI workbench.

## Trust Model Decision (operator-approved, 2026-06-30)

Per-workspace **Trusted Dev Mode** was originally approved as one combined no-click mode for
`shell_exec`, file mutations, and git. **Current implementation supersedes the shell part:** Trusted
still removes per-action approval for file/git mutations, while Host Shell is a distinct explicit
opt-in and native Windows runs it through the low-privilege account.

- Privacy Lock stays on regardless: no effect on remote model routing, network egress, or Docker control.
- Opt-in per workspace, not global. New/non-trusted workspaces keep full per-action approval as they do today.
- Every action still fully audited and traced — trusted mode removes the click, not the log.
- A persistent, unmissable UI indicator shows trusted mode is active, with one-click revoke.
- `git push` (and any other externally-visible action) stays approval-gated even inside trusted mode, since its effects leave the local machine.

This decision gates every stage below — none of Stages 1-6 are worth building without it.

## Ranked Blockers (from direct code inspection, worst first)

1. Per-call approval friction on every write — kills iteration speed even where writes already work.
2. No shell execution at all — blocks running tests, builds, linters, or any CLI tool.
3. No git tooling — can't diff, stage, or commit; can't show the operator what changed.
4. 15-iteration hard cap — too low for edit → run tests → fix → re-run loops.
5. No diff/terminal/file-tree UX — output is markdown text, hard to review changes at a glance.
6. Whole-file overwrite instead of patch/anchored edits — expensive and risky on large files.

## Stage 0: Trusted Dev Workspace Foundation

Status: **complete** (2026-07-01, commit `1122020`, branch `codex/trusted-dev-workspace-v1`)

Validation: backend smoke 48/48 (native and Docker), frontend build, repo safety check, and a live Playwright-driven browser pass through toggle → confirm modal → persistent banner across views → revoke → toggle reset, with zero console errors.

Branch: `codex/trusted-dev-workspace-v1`

Goal: implement the trust model decision above as the substrate everything else builds on.

Scope:
- Add `trusted: bool` (default `False`) to workspace root records (`backend/core/workspace.py`).
- Add an explicit confirm-to-enable flow: modal states plainly what trusted mode grants (unattended shell + file mutation inside this folder), requires typed/clicked confirmation, is revocable in one click.
- Extend the permission/approval check (`backend/core/security.py`, `backend/core/approvals.py`) so that when `tool.category in {"workspace", "system"}` and the resolved path is inside a `trusted` root, the `one_time_approval` step is skipped — but the tool call is still recorded through the existing audit/trace path unchanged.
- No change to `privacy_lock`, remote model gating, or web broker approval behavior.

Security requirements:
- Trust is per-workspace-root, never global.
- Persistent, always-visible banner/badge while any active session is operating in a trusted workspace.
- Revoking trust takes effect immediately for new tool calls.
- Audit log entries are unchanged in shape; only the human-approval step is skipped.

Tests required:
- Untrusted workspace: `fs_write` still requires approval (regression guard).
- Trusted workspace: `fs_write`/`fs_mkdir`/`fs_move` execute without an approval record blocking them, but still produce an audit/tool_call row.
- Revoking trust mid-session blocks the next call.
- Path traversal outside the trusted root is still rejected regardless of trust.

Definition of done: a designated local repo can have files written/moved without a human clicking approve on each call, while every other workspace behaves exactly as it does today.

## Stage 1: Real Shell Execution

Status: **complete** (2026-07-01, commit `9a6d796`, branch `codex/shell-exec-v1`)

Validation: backend smoke 49/49 (native and Docker), frontend build, repo safety check, and a direct `on_log` wiring check confirming streamed stdout/stderr lines reach the task log as the command runs.

Branch: `codex/shell-exec-v1`

Goal: turn `shell_exec` from a disabled stub into a working tool, scoped to trusted workspaces.

Scope:
- Implement async subprocess execution with `cwd` pinned to the workspace root (never escapable), inheriting a minimal safe environment (no host secrets injected).
- Stream stdout/stderr into the task log/trace incrementally, not just as a final blob, so the UI can show output as it happens.
- Per-call timeout (configurable, sane default e.g. 120s) and output size cap with archival for overflow (reuse existing `archive_expand` pattern already in `agent.py:920-930`).
- Only callable when the resolved workspace is `trusted`; otherwise stays approval-required/disabled as today.

Security requirements:
- Command text is fully audited verbatim (shell commands are not "sensitive" like file content, but still logged).
- No network-egress bypass of Privacy Lock — this is host-command execution, not a new internet channel, and should be documented as such to the operator during the trust-enable confirmation.
- Soft guardrail deny-list for obviously catastrophic patterns (e.g. recursive delete of the workspace root or above) as a backstop, not a security boundary — trusted mode is understood to mean full local user-level execution.

Tests required:
- Command runs, streams output, respects cwd.
- Timeout kills a long-running command cleanly and reports it.
- Untrusted workspace: call is rejected/stubbed as before.
- Output over the size cap archives correctly and remains retrievable.

Definition of done: the agent can run `npm test`, `pytest`, `git status`, a linter, etc. inside a trusted workspace and see real output.

## Stage 2: Git-Aware Tools

Status: **complete** (2026-07-01, commit `ba85940`, branch `codex/git-tools-v1`)

Validation: backend smoke 50/50 (native and Docker), repo safety check. Also discovered and fixed a real deployment gap along the way: the Docker runtime image had no `git` binary at all, so none of this would have worked outside native dev. Added `git` plus a system-wide `safe.directory '*'` config (bind-mounted host workspaces run under a different UID than the container user, which trips git's dubious-ownership guard otherwise).

Branch: `codex/git-tools-v1`

Goal: give the agent and the UI first-class git visibility, not just raw shell access.

Scope:
- Add `git_status`, `git_diff`, `git_log`, `git_add`, `git_commit` as typed tools (can be implemented as thin wrappers over Stage 1's shell execution with structured output parsing, rather than a new execution path).
- `git_commit` runs without per-click approval inside a trusted workspace (it's local); `git push` (and any remote-touching command) stays approval-required regardless of trust, since it leaves the machine.
- Parse `git diff` output into structured hunks for the UI diff viewer (Stage 5) rather than raw text only.

Security requirements:
- Same trusted-workspace gating as Stage 1 for local operations.
- Remote operations (`push`, `fetch`, `pull`, `clone` from network) remain approval-required and Privacy-Lock-aware.

Tests required:
- `git_diff`/`git_status` return structured, parseable results.
- `git_commit` executes without approval in a trusted workspace; `git push` still requires approval.
- Non-git directory returns a clean structured error, not a crash.

Definition of done: the agent can inspect, stage, and commit its own changes locally, and the operator can see exactly what changed before it's committed.

## Stage 3: Patch-Based File Edits

Status: **complete** (2026-07-01, commit `bed3281`, branch `codex/fs-patch-v1`)

Validation: backend smoke 51/51 (native and Docker), frontend build, repo safety check.

Branch: `codex/fs-patch-v1`

Goal: replace "resend the whole file" with anchored find/replace or unified-diff patch application, mirroring how Claude Code/Codex actually edit files.

Scope:
- Add `fs_patch` tool: old-text/new-text anchored replacement with a uniqueness check (fails loudly if the anchor isn't unique, same failure mode Claude Code's own Edit tool uses), or unified-diff apply as a fallback for multi-hunk changes.
- Keep `fs_write` for whole-file creation/replacement; `fs_patch` becomes the default for editing existing files.
- Both remain trusted-workspace-gated per Stage 0.

Note: this stage is not a hard blocker for Stage 1/2 to be useful — the agent can bootstrap by writing edit scripts through `shell_exec` in the meantime — but it materially reduces token cost and edit risk on large files, so it should land early.

Tests required:
- Ambiguous anchor (matches 2+ locations) is rejected with a clear error instead of silently patching the wrong spot.
- Multi-hunk diff applies atomically (all-or-nothing).
- Patch failure doesn't corrupt the file.

Definition of done: multi-file edits touch only the changed lines, not full-file rewrites.

## Stage 4: Agentic Coding Loop (iteration cap, streaming, plan tracking)

Split into 4a (backend loop mechanics) and 4b (UI streaming) after review: raising the iteration cap without bounding in-loop message accumulation is a latent context-window bug given how much content Stage 1-3's tools return per call, and UI streaming is a large enough architectural change (touches the SSE pipeline everything else rides on) that it shouldn't be bundled with a control-flow fix.

### Stage 4a: Mode-Aware Iteration Ceiling + In-Loop Context Bounding

Status: **complete** (2026-07-01, commit `5000e0d`, branch `codex/agentic-coding-loop-v1`)

Scope actually implemented:
- Replaced the hardcoded `for attempt in range(15)` with a mode-aware budget: `code` mode gets 80 iterations / 900s wall-clock, other modes keep 15/180s. A genuinely runaway loop still terminates, just later, on whichever limit hits first.
- Added `_bound_tool_loop_messages`: every iteration, checks the running message list against the model's real context budget (`context_governor.needs_compaction`) and, only when over budget, archives older large tool-result messages into `eviction_log` (same pattern `reflect()` already uses for oversized work products) and replaces them with a short `archive_expand`-retrievable pointer. The archive step is defensive — a DB failure there logs and skips rather than aborting an otherwise-working loop.

Validation: backend smoke 54/54 (native and Docker), frontend build, repo safety check, plus three tests built around a scripted mock of `_chat` (dry-run/mock models never emit `tool_calls`, so a real model or a scripted one is the only way to exercise the loop) confirming: `code` mode runs past 15 iterations while other modes still stop at 15; archiving actually fires under simulated context pressure with messages replaced by retrievable pointers; the wall-clock budget stops the loop under a mocked clock instead of hanging.

**Open gap, stated plainly:** no real model endpoint is configured in this environment (no local vLLM running, no API keys present). Stage 4a is verified at the mechanics level with scripted tool-call sequences, not behaviorally verified end-to-end with a live model actually orchestrating shell/git/patch toward a real fix. That is the actual test of this whole plan's premise and remains open. Do not treat later stages' "definition of done" language (e.g. Stage 6: "a real multi-file bug fix... autonomously") as met until this has been run against a real model.

### Stage 4b: Stream Model Output and Tool Events to the UI

Status: **pending**

Branch: `codex/agentic-coding-ux-streaming-v1` (not yet started)

**Verified 2026-07-01: this stage is larger than it looks.** `backend/models/providers.py:289` hardcodes `"stream": False` in the OpenAI-format request builder (used for OpenAI + local OpenAI-compatible endpoints), and there is no chunked/SSE response parsing anywhere in the provider layer for any provider. Provider-level token streaming does not exist today and is a prerequisite for this stage, not a detail within it. See `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` Stage 4b for the expanded task breakdown.

Scope:
- Add real provider-level token streaming to `backend/models/providers.py` (OpenAI, Anthropic, Gemini, local OpenAI-compatible) — new work, not present today.
- Stream model output tokens and tool-call events to the UI as they happen instead of only at phase completion — the frontend already has a working SSE channel (`new EventSource("/api/events")`, `frontend-src/src/app/App.jsx:589`) to extend for delivery once provider streaming exists.
- Surface a lightweight step/plan list in the task view (what the agent intends to do, updated as steps complete) so a long-running coding task doesn't look frozen.

Tests required:
- Streamed events arrive incrementally in a live task view (not just at completion).

Definition of done (for Stage 4 overall, once 4b lands): a real multi-file bug fix (edit, run tests, see failure, fix, re-run, pass) completes in one task without hitting an artificial ceiling, and the operator can watch it happen live.

## Stage 5: Coding-Oriented Task UX

Branch: `codex/coding-ux-v1`

Goal: give coding tasks a layout built for reviewing code changes, not just reading a markdown transcript.

Scope:
- Task detail view gains: a touched-files list, a per-file unified diff viewer (syntax-highlighted), and a live terminal/log pane for shell output (extend patterns already used in `CodeSandbox.jsx`).
- Quick actions per file: view diff, revert this file's change (calls `git checkout -- <path>` inside trusted workspace).
- Reuse existing task-detail drawer structure (`TaskDetailsDrawer.jsx`) rather than a new view.

Tests required:
- Diff viewer renders correctly for add/modify/delete/rename.
- Terminal pane updates live during a running shell command.
- Revert action restores the file and is reflected in the diff view.

Definition of done: reviewing what a coding task did feels like reviewing a PR, not scrolling a chat log.

## Stage 6: Test-Loop Integration

Branch: `codex/test-loop-v1`

Goal: close the loop so the agent runs the workspace's own test/build/lint commands automatically between edit attempts, instead of the operator manually re-triggering.

Scope:
- Per-workspace settings for test/build/lint commands (operator-configured once per repo, e.g. `npm test`, `pytest -q`).
- In `code` mode, `execute()` (`backend/engine/agent.py:888`) optionally runs the configured test command after an edit, parses pass/fail, and feeds failures back into the next planning iteration within the Stage 4 budget.
- Bounded retry count distinct from the raw tool-call ceiling, so a flaky/failing loop doesn't silently burn the whole budget on one broken approach.

Tests required:
- Configured test command runs after an edit and result is captured.
- A failing test feeds back into the next iteration's context.
- Retry ceiling stops the loop and reports the last failure clearly instead of looping forever.

Definition of done: "fix this bug" can mean edit → test → see it fail → fix → test → pass, autonomously, inside one task.

## Stage 7 (Differentiator): Code-Structure-Aware Graph

Status: **complete** (2026-07-03 — AST-based extraction landed; relation queries landed 2026-07-01)

Branch: `codex/code-aware-rag-v1`

Goal: turn Graphify into a real code-navigation advantage a hosted CLI doesn't have out of the box — persistent, queryable structure of the operator's own codebase instead of re-grepping fresh every session.

**Verified 2026-07-01:** `backend/rag/graph.py` already extracts typed nodes (`function`, `class`, `file`, `folder`, `concept`) and typed edges (`imports`, `defines`, `calls`, `references`) and is exposed as a `graph_search` MCP tool with citations. This is ahead of "not started." What's missing: the extraction is regex-based, not AST-based (`_call_edges` treats any `identifier(` as a call, including keywords/builtins — noisy), and there's no dedicated relation-traversal query ("what calls X") distinct from the current generic fuzzy keyword `search()`. See `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` Stage 7 for the full breakdown.

Scope:
- ~~Replace regex-based entity/call extraction with AST-based parsing for precision.~~ Done 2026-07-03: Python files are parsed whole-file from disk with `ast` (guarded by the indexed `mtime` so chunk line-ranges still line up); a call edge now means an actual `ast.Call`, with builtins filtered. Regex remains only as a fallback for non-Python scripts and unparseable/changed files (now with a keyword deny-list), and prose/markup files no longer emit calls/defines/imports edges at all.
- Support direct "what calls X" / "where is X used" / "what does this file import" queries answered from the graph via relation traversal (not keyword scoring) with citations, without a full re-scan.
- Keep it workspace-scoped and local-only, consistent with existing RAG/Graphify privacy posture (already true today).

Definition of done: the agent (and the operator, via chat) can answer structural codebase questions instantly from the graph instead of paying tool-call round trips to re-search every time.

## Stage 8 (Differentiator): Local-Model Coding Routes via WarSat

Branch: extends existing Warsat fit-scoring work.

Goal: make free/offline agentic coding on the operator's own hardware a real option, not just a chat fallback — something a hosted CLI structurally cannot offer.

**Verified 2026-07-01:** `backend/models/registry.py` already lists `coder` as a first-class `MODEL_ROLES` entry with working role-based lookup (`key_for_role`) — the routing plumbing this stage needs already exists. No fit-scoring/coding-capability-detection logic exists anywhere in `backend/warsat/` yet; that part is genuinely unstarted.

Scope:
- Extend Warsat model fit scoring to flag coding-capable local models (e.g. Qwen2.5-Coder-class, DeepSeek-Coder-class) explicitly for the `coder` role.
- Let the operator route `code` mode to a local model with one click once Warsat reports it deployed and healthy, no API cost, fully offline.

Definition of done: a real coding task can run entirely against a local model with zero tokens spent and zero data leaving the machine, end to end through the Stage 0-6 pipeline.

## Stage 9 (Differentiator): Coding-Task Trials

Branch: extends existing Trials feature (`docs/STAGED_IMPLEMENTATION_BACKLOG.md`, already `existing`/`missing` per harvest matrix — this specializes it).

Goal: let the operator blind-compare models on an actual coding subtask (not just chat) and pin the winner to the `coder` role — a capability neither Codex CLI nor Gemini CLI expose, since each is locked to its own backend model.

**Verified 2026-07-01:** `backend/trials/models.py` already defines a `model` experiment type and includes `code` in `ROUTABLE_MODES` — the general Trials scaffold exists and already knows about `code` mode. No coding-subtask-specific blind comparison or pin-to-`coder` flow exists yet.

Definition of done: operator can, from inside Rasputin, decide "which model is actually best at fixing bugs in this codebase" with evidence, and have that decision take effect immediately.

## Explicitly Out of Scope / Unchanged

- Everything in `docs/STAGED_IMPLEMENTATION_BACKLOG.md`'s "Explicitly Deferred" section (Mail Relay, Timeline Sync, Visual Relay, Field Console PWA, Local Admin 2FA) stays deferred — unrelated to coding competitiveness.
- Non-trusted workspaces keep today's full per-action approval behavior — this plan adds a trust tier, it does not weaken the default.
- Privacy Lock, remote model gating, and web-broker approval/redaction behavior are unchanged by every stage above.
- `docker_control` stays a disabled stub — out of scope here; Warsat's existing approval-gated deploy path is untouched.

## Success Criteria

Rasputin is "there" when, for a real trusted local repo:

- A multi-file bug fix (edit, run tests, iterate, commit) completes in one task with zero manual per-action approval clicks.
- The operator can review what changed the way they'd review a PR (diff view, not chat scrollback) before or after commit.
- A coding task doesn't stall against the old 15-call ceiling or go silent for minutes with no visible progress.
- At least one real coding session runs entirely on a local model through Warsat with no API spend.
- The operator's own judgment: "I opened Rasputin instead of Codex for this" happening unprompted, more than once.
