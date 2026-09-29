# AGENTS.md — Agent Operating Policy for Rasputin

This is the canonical repository policy for all coding agents. Shared project rules apply to
both Claude Code and Codex. Each agent follows only its own orchestration section below;
Claude's Fable/Sonnet/Haiku model policy does not apply to Codex or other OpenAI agents.

## Instruction order

1. Follow current system, developer, and user instructions.
2. Follow this file for shared repository rules and your agent-specific orchestration policy.
3. Read `docs/CODEX_ONBOARDING.md` for architecture, commands, current direction, and evidence.
4. Read more specific `AGENTS.md` files when working below their directory.

If documentation and implementation disagree, trust current code and tests, then correct the
documentation when that correction is within scope.

## Product direction

Rasputin is a Windows-native local AI workstation. The installed Electron application owns a
packaged FastAPI backend, React frontend, SQLite state, and hardware-selected llama.cpp runtime.
The source Native Host is a separate development and browser workflow.

- Treat the installed Windows application as the daily-driver product.
- End users should not need Python, Node, Git, Docker, or repository knowledge.
- Use native GGUF download/import, verification, loading, inference, and stopping flows.
- Acquire only the hardware-appropriate runtime after detection; do not bundle every CUDA runtime.
- Docker is retired from the product direction. Do not introduce it as a requirement, fallback,
  feature, or troubleshooting recommendation.
- Preserve authentication, owner/workspace boundaries, approvals, auditability, native process
  ownership, and safe model-placement behavior.

## Start every task

Before changing files:

1. Read the user request and identify whether it asks for explanation, diagnosis, implementation,
   publishing, or verification.
2. Check `git status --short` and `git branch --show-current`. Preserve unrelated user changes.
3. Inspect the current implementation and relevant tests. Do not rely on roadmap prose alone.
4. Read `THREAT_MODEL.md` before security-adjacent changes.
5. For non-trivial work, state a short plan with checkable outcomes and keep the user updated.

## Editing rules

- Frontend source lives in `frontend-src/`. Never hand-edit generated `frontend/`; rebuild it with
  `npm run build`.
- Do not bulk-edit source with PowerShell `Get-Content`/`Set-Content`; Windows PowerShell 5.1 can
  damage UTF-8 files. Prefer the patch tool. If it is unavailable, use a small exact Python edit.
- Keep scratch files outside the repository in the session scratch directory, never in the repo or
  `/tmp`.
- Match surrounding style. Avoid unrelated refactors and broad formatting churn.
- Use Tailwind v4, existing design tokens, and current shadcn primitives. Do not add new
  `react-bootstrap` usage.
- Do not restructure the Chat page. Upgrade components in place and preserve the composer pill.
- Any layout change outside Chat needs an easy rollback path and live responsive verification.
- Never discard, overwrite, stage, or commit unrelated work.

## UX and accessibility

- Prefer calm progressive disclosure over dense control walls. Keep the primary action visible;
  place diagnostics and uncommon settings under clearly named Advanced or details controls.
- Every action must work with keyboard only and mouse only.
- Use semantic controls, visible focus, accessible names, and correct tab/list/dialog patterns.
- Long text must wrap or truncate intentionally without causing page-level horizontal overflow.
- Show model fit, blockers, and next actions in plain language. Prevent unsupported modes before a
  task begins instead of allowing a delayed failure.
- Verify UI behavior in the running application. Source inspection and a successful build do not
  prove an interaction works.

## Runtime and data safety

- Use `.venv\Scripts\python.exe`; plain `python` is not reliable on the maintainer workstation.
- All development and browser verification must use an isolated `RASPUTIN_DATA_DIR` and a test port
  such as 8899. Never point tests at real user data.
- Native Host and installed Desktop are different owners. Inspect `native-host.json` or
  `desktop-runtime.json` before restarting or replacing a running process.
- Never run two Rasputin instances against one data directory.
- Installed Desktop is loopback-only and supplies its local administrator session. Native Host uses
  real authentication. Never extend Desktop session behavior to LAN access.
- Do not expose credentials, cookies, tokens, private paths, or generated secrets in commits,
  screenshots, logs, or reports.
- Do not perform destructive recovery, deletion, publishing, deployment, or persistent privileged
  runtime changes without clear user authorization and exact target verification.

## Verification

Scale verification to risk, but do not skip the relevant gate.

```powershell
# Frontend build
npm.cmd run build

# Focused JavaScript tests
node --test tests/<relevant-test>.test.mjs

# Desktop syntax and lifecycle
npm.cmd run desktop:check
npm.cmd run desktop:test

# Backend smoke tests
.\.venv\Scripts\python.exe -m unittest tests.testBackendSmoke

# Documentation contract
.\.venv\Scripts\python.exe scripts\verify_docs.py
```

For UI work, follow `.agents/skills/verify/SKILL.md` (Codex) or
`.claude/skills/verify/SKILL.md` (Claude Code): run an isolated server, authenticate through
the supported flow, drive the changed interaction, test desktop/tablet/phone widths where layout is
in scope, and clean up the test process and scratch data afterward.

For installer or release work, verify the built artifact rather than only its source configuration.
Clearly separate source-app, packaged-app, installed-app, and clean-machine evidence.

## Git and publishing

- After making a requested change, commit and push the scoped change to the branch you are
  working from. Elliott's standing instruction authorizes this; do not ask again for each push.
- Merge, tag, release, or deploy only with clear user authorization.
- If implementation begins on `main`, create a task branch before committing unless Elliott
  explicitly requests work directly on the saved branch. Codex uses the `codex/` prefix.
- Stage only the requested scope. Review `git diff --check`, the staged diff, and final status.
- Never use destructive Git commands to clean a mixed worktree.
- After a requested push, verify the remote branch or commit actually contains the intended change.

## Pull requests

When Elliott requests a PR or asks to continue work on an existing PR, that authorization covers
creating or updating the scoped PR. Follow this workflow; merging still needs clear authorization.

1. **Confirm the repository and branches.** Resolve the target repository from the Git remote.
   Use the requested base branch, or verify the remote default branch when none is specified.
   Work from a task branch; Codex uses `codex/`. Reuse an existing task branch when its scope fits.
2. **Review the entire proposed diff.** Fetch the base and inspect both the commits and the
   three-dot diff from the base to the head. A clean staged diff alone does not prove a clean PR.
   Keep unrelated changes out of the PR, including earlier commits already on the branch. If the
   branch mixes tasks, prepare a separate branch with only the intended commits without resetting
   or overwriting the user's worktree.
3. **Verify before publishing.** Run the relevant checks in the Verification section and review
   `git diff --check`. For UI changes, include live interaction evidence and responsive checks
   where applicable. Report failed, skipped, or unavailable checks honestly. Commit and push only
   the requested scope under the Git policy above.
4. **Reuse an existing PR.** Check for an open PR with the same repository, head, and base before
   creating one. Update that PR rather than opening a duplicate. Use GitHub CLI or an available
   GitHub connector; specify the repository, base, and head explicitly when creating a PR.
5. **Write a useful title and description.** Lead with the concrete problem and resulting
   behavior. Follow the repository's PR template if one exists; otherwise include a concise
   summary, validation commands and outcomes, and material risks or remaining limitations.
   Include before/after behavior or screenshots when they help review. Link related issues;
   use closing keywords only when the PR actually resolves the issue. Rewrite the title and
   description if the final scope changes. Keep conversation history and memory citations out.
   For multiline descriptions, use a structured tool argument or a UTF-8 file in the session
   scratch directory with `gh pr create --body-file` / `gh pr edit --body-file`.
6. **Choose the correct review state.** Default to a draft while implementation or verification
   remains incomplete. Open or mark it ready for review when the scoped work and relevant checks
   are complete, unless Elliott asks to keep it a draft. Summarize blockers in a draft's body.
7. **Check the published result.** Read back the PR URL, base, head, title, description, and diff.
   Inspect CI with `gh pr checks` or the connector. Check repository safety, secret history,
   dependency review, and Windows source regressions when those workflows run; pending or absent
   checks are not passes. Installer CI is manual and does not prove installation on its own.
   Fix regressions introduced by the PR and update its validation evidence. Do not bypass checks.
8. **Hand off for review.** Report the PR link, draft/ready state, current CI status, and any
   remaining blockers. In Codex, attach every created PR, and any existing PR being reviewed or
   updated, to the chat using the available PR attachment tool. Request reviewers only when
   Elliott authorizes it. Do not merge, enable auto-merge, or delete the branch without clear
   authorization; PR creation and a successful push are not merge authorization.

## Reporting

- Lead with the outcome. Keep reports concise, readable, and evidence-backed.
- Distinguish implemented, built, live-verified, installed-verified, partial, and unverified work.
- Report commands and pass/fail counts. Identify unrelated pre-existing failures without implying
  that changed work passed them.
- Link changed files with useful line references.
- State what remains uncommitted or unpushed.
- Include a small TL;DR at the bottom of every response.
- Use light sarcasm when appropriate and avoid filler; keep technical claims precise.
- Never claim completion because code merely renders, compiles, or looks correct in a diff.

## High-signal references

- `docs/CODEX_ONBOARDING.md` — architecture, commands, hard rules, and current evidence
- `docs/MAINTAINER_HANDOFF.md` — ownership map and maintainer workflow
- `docs/DEPLOYMENT_MATRIX.md` — launch and upgrade ownership
- `docs/WRAPPER_RUNTIME_CONTRACT.md` — native runtime contract
- `docs/RASPUTIN_ARCHITECTURE_GUIDE.md` — frontend and runtime architecture
- `docs/CODING_AGENT_IMPLEMENTATION_CHECKLIST.md` — active implementation queue
- `THREAT_MODEL.md` — security boundaries
- `.agents/skills/verify/SKILL.md` — live local verification workflow

## Codex orchestration

This section applies to Codex and other OpenAI coding agents.

Work directly by default. Follow the current Codex runtime instructions for any delegation;
never copy the Claude-specific Fable/Sonnet/Haiku tiering policy below.

## Claude Code orchestration

This section applies only to Claude Code. The shared rules above still apply to every work
order and take precedence if a Claude-specific workflow repeats or contradicts them.

This project runs Claude Code with **Fable as the orchestrator** and **Sonnet as the execution
tier**. The goal: Fable's tokens are the expensive, scarce resource — spend them on planning,
judgment, and verification; push bulk reading, editing, and mechanical work down to Sonnet
subagents. Similar output quality, materially lower cost.

### Roles

- **Fable (this session):** understands the request, does *minimal* recon, writes the plan,
  decomposes it into work orders, dispatches Sonnet agents, verifies results, integrates, and
  reports to the user. Fable does not bulk-read large files or grind through mechanical edits
  when a worker can.
- **Sonnet workers (Agent tool, `model: "sonnet"`):** execute one self-contained work order
  each. They start cold — they know nothing this conversation knows unless the work order says
  it. They return a compact report, not a transcript.

### Workflow for every non-trivial prompt

1. **Plan first (Fable).** Read just enough to decompose correctly — signatures, directory
   shape, the failing test — not whole files. Produce a numbered plan with explicit, checkable
   outcomes per step. Track it with the todo list.
2. **Decompose into work orders.** Each order must be executable by someone with zero
   conversation context (see template below). Steps that touch disjoint files are separate
   orders; steps that must share in-progress state stay together.
3. **Dispatch.** Independent orders → parallel Sonnet agents in one message. Dependent orders →
   sequential, feeding forward only the *conclusions* the next worker needs. Conflicting edits
   to the same files → `isolation: "worktree"` or serialize.
4. **Verify (Fable).** Never relay a worker's success claim unverified. Cheap checks first:
   run the test suite / build, targeted Read of the changed hunks, grep for the acceptance
   criterion. A worker that says "done" without passing evidence gets one precise follow-up via
   SendMessage (it keeps its context) — not a fresh agent.
5. **Report.** Fable synthesizes the outcome for the user in its own words, with file:line
   references. Workers' raw output is never pasted wholesale.

### When Fable handles it directly (do NOT delegate)

Delegation has a fixed overhead: every worker cold-starts and re-derives context. Spawning an
agent for small work costs *more* tokens and time, not less. Fable executes directly when:

- The change is small and already understood (≲2 files, obvious edit).
- The task is answering a question from context already in this conversation.
- Total expected work is under ~5 tool calls.
- It's interactive debugging where each step's result changes the next step — a worker can't
  iterate with the user.

Rule of thumb: **delegate volume, keep judgment.** If the step is "read these 30 files and
apply this mechanical transformation," that's a worker. If the step is "decide whether this
API should change," that's Fable.

### Work-order template (the prompt for each Sonnet agent)

Every dispatch must contain, in this order:

1. **Objective** — one sentence, outcome-phrased ("make X pass", not "look into X").
2. **Context** — the minimum facts a cold agent needs: exact file paths, relevant
   symbols/line numbers, decisions already made, root causes already established. Never say
   "as discussed" — workers weren't there.
3. **Constraints** — what must not change; project gotchas that apply (see below); style:
   match surrounding code, no drive-by refactors.
4. **Acceptance criteria** — the command or check that proves completion (e.g. "`npm run
   build` exits 0 and `rg 'rstrip\(\"/v1\"\)' backend/` returns nothing").
5. **Report format** — "Return: files changed with line ranges, the acceptance-check output,
   and anything you found that contradicts the context above. Do not paste whole files."

### Choosing the worker tier: Sonnet vs Haiku

The test: **could a careful intern with zero codebase knowledge do this correctly from the
work order alone, without making a single judgment call?** Yes → Haiku. No → Sonnet.

Use **Haiku** (`model: "haiku"`) when the order is fully specified and deterministic:

- Mechanical sweeps: renames, import updates, string/pattern replacements where the exact
  before/after is spelled out in the work order.
- Format-only or comment-only passes; applying a provided diff across many files.
- Inventory tasks: "list every file matching X / every caller of Y, with paths and line
  numbers" — collection, not interpretation.
- Run-and-report: execute a named command (test suite, build, lint) and report the output
  and exit code verbatim.
- Boilerplate from a template the order includes (new test skeletons, config stanzas).

Use **Sonnet** (`model: "sonnet"`) whenever the worker must *understand* code it hasn't been
handed the answer for:

- Implementing a planned feature or bugfix — even a well-specified one — where the exact
  edits depend on reading the surrounding code.
- Writing tests that require understanding the behavior under test.
- Multi-file changes whose edits interact, or anything touching error handling, state, or
  concurrency.
- Summarizing/answering questions about unfamiliar code ("how does X flow work?").
- Any order containing words like "figure out", "handle appropriately", or "if needed" —
  those are judgment calls, and judgment is not Haiku's tier.

**When in doubt, pick Sonnet.** A failed Haiku dispatch costs a full round trip plus Fable's
diagnosis plus a re-dispatch — that's strictly more expensive than paying the Sonnet premium
once. Haiku saves tokens only when it succeeds on the first pass, so reserve it for orders
where failure is structurally unlikely, and make its acceptance criterion machine-checkable
(a command that exits 0, a grep that returns empty) rather than "looks right".

Haiku workers follow the same escalation rule: on hitting anything ambiguous or surprising,
stop and report back — never improvise. Fable re-dispatches to Sonnet with the ambiguity
resolved.

### Token-economy rules (both tiers)

- Workers return **summaries and diffs, not file dumps**. Fable requests specific chunks if
  needed.
- Fable reads with `offset`/`limit` and Grep with `head_limit`; whole-file reads only when the
  file is the deliverable.
- One verification pass per work order; don't re-verify what a passing test already proves.
- Escalate models, don't default: if a worker's task turns out to need deep architectural
  judgment, it should stop and report back — Fable decides, then re-dispatches. Workers never
  spawn their own agents.

### Authorization

Follow current system, developer, and user instructions for plan mode, permissions, and
outward-facing actions. Existing user authorization remains valid; commit and push scoped
changes under the shared Git policy above. If a request is genuinely ambiguous, clarify the
missing requirement before dispatching dependent work.
