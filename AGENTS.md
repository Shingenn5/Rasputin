# AGENTS.md — Model Orchestration Policy

> **If you are Codex (or any non–Claude Code agent):** this file's orchestration policy is
> Claude Code–specific and does not apply to you. Read **`docs/CODEX_ONBOARDING.md`** instead —
> it covers the project, build/test commands, and the hard rules. The one section here that
> applies to everyone is "Project gotchas" below (also repeated in that doc).

This project runs Claude Code with **Fable as the orchestrator** and **Sonnet as the execution
tier**. The goal: Fable's tokens are the expensive, scarce resource — spend them on planning,
judgment, and verification; push bulk reading, editing, and mechanical work down to Sonnet
subagents. Similar output quality, materially lower cost.

## Roles

- **Fable (this session):** understands the request, does *minimal* recon, writes the plan,
  decomposes it into work orders, dispatches Sonnet agents, verifies results, integrates, and
  reports to the user. Fable does not bulk-read large files or grind through mechanical edits
  when a worker can.
- **Sonnet workers (Agent tool, `model: "sonnet"`):** execute one self-contained work order
  each. They start cold — they know nothing this conversation knows unless the work order says
  it. They return a compact report, not a transcript.

## Workflow for every non-trivial prompt

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

## When Fable handles it directly (do NOT delegate)

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

## Work-order template (the prompt for each Sonnet agent)

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

## Choosing the worker tier: Sonnet vs Haiku

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

## Token-economy rules (both tiers)

- Workers return **summaries and diffs, not file dumps**. Fable requests specific chunks if
  needed.
- Fable reads with `offset`/`limit` and Grep with `head_limit`; whole-file reads only when the
  file is the deliverable.
- One verification pass per work order; don't re-verify what a passing test already proves.
- Escalate models, don't default: if a worker's task turns out to need deep architectural
  judgment, it should stop and report back — Fable decides, then re-dispatches. Workers never
  spawn their own agents.

## Project gotchas every work order must respect

- **Never bulk-edit source files with PowerShell `Get-Content`/`Set-Content`** — PS 5.1
  mangles UTF-8 and adds BOMs. Use the Edit/Write tools, or Python.
- Temp/scratch files go to the session scratchpad directory, never the repo or `/tmp`.
- Frontend verification workflow is documented in `.claude/skills/verify/SKILL.md`
  (isolated `RASPUTIN_DATA_DIR` server, Playwright patterns, useful testids).
- Do not restructure the chat page layout; upgrade components in place.
- Commit/push only when the user asks; branch off `main` first if on the default branch.

## What this policy does not change

Plan mode, permission prompts, and user confirmation for irreversible or outward-facing
actions all apply as normal at both tiers. If the user's request is genuinely ambiguous,
Fable asks before dispatching — a fleet of workers executing the wrong plan is the most
expensive failure mode there is.
