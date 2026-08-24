# Rasputin Threat Model

This document describes what Rasputin trusts, what it doesn't, where the
boundaries are enforced in code, and — honestly — where they currently
aren't. It's written for whoever is deciding whether to expose an instance
beyond their own machine, and for whoever picks up the next piece of
security work.

It is a snapshot as of 2026-07-13. Verify file:line citations against
current code before relying on them; this system moves fast.

---

## 1. Operating assumption

Rasputin is built to run as **one locally administered appliance**. It may now
serve several authenticated local users simultaneously, but the machine/data
directory administrator remains the ultimate trust boundary. Account isolation
protects users from accidental cross-account access through the application;
it is not cryptographic tenant isolation from the host administrator.

- Web pages, RAG'd files, and tool output the agent fetches on the
  operator's behalf may contain adversarial text ("ignore previous
  instructions...") — this is an active, in-scope threat (see §3).
- The appliance administrator themself is not an adversary. Trusted Dev Mode (§4),
  Privacy Lock, and the approval system all exist to let the *operator*
  control what an *agentic loop running on their behalf* can do — not to
  protect Rasputin from someone who already has legitimate access to it.
- Anyone who can reach the API surface must now present real credentials
  (§6.1) — a login screen, password verification, and session cookie all
  actually enforce this as of 2026-07-07. Before that date this was
  enforced only by network topology (don't expose the port); don't assume
  that's still the only backstop without re-reading §6.1.
- Private chats, tasks, preferences, memory, and login sessions carry an owner.
  Workspaces have explicit membership roles. Appliance-wide settings, model
  control, security, approvals, and WarSat mutations require an administrator.
  Archive/trials and host filesystem access remain trusted appliance surfaces,
  not hard multi-tenant boundaries.

## 2. Roles & permission flags

`backend/core/security.py` holds one flat set of boolean flags, checked via
`security.require(flag)` at each sensitive call site. Defaults:

| Flag | Default | Gates |
|---|---|---|
| `allow_file_read` | on | RAG ingest, graph build, file preview |
| `allow_file_write` | on* | `fs_write`/`fs_patch` — *also subject to the approval queue unless the workspace is Trusted (§4) |
| `allow_file_reorganize` | off | `fs_mkdir`/`fs_move` |
| `allow_shell_execution` | **off** | `shell_exec` — also requires the workspace's separate Host Shell capability; Native/Desktop Windows is currently fail-closed pending AppContainer isolation |
| `allow_web_search` | on | `web_search` (DuckDuckGo scrape, brokered — see §3) |
| `allow_docker_control` | **off** | WarSat deploys, host folder browsing, mount requests |
| `allow_remote_models` | **off** | "Privacy Lock" — routing to any non-local model endpoint |
| `allow_model_tests` / `allow_model_registry_edit` | on | Trials engine, model registry edits |

There is no per-tool self-escalation path: no registered tool can flip its own or any
other flag. Changing these flags is a UI/API action gated the same way as
anything else, not something the agent's own tool loop can reach.

## 3. The untrusted-content boundary

Two kinds of text reach a model call: what the operator (or Rasputin's own
task/mode logic) authored, and what Rasputin *retrieved* on the operator's
behalf. Only the first kind should be treated as instructions — the second
kind (RAG chunks, graph evidence, saved memory, workspace file contents, and
every tool call's result) is data the agent should read and quote, never
obey. `web_search` is the sharpest edge here: it's a real, unstubbed
DuckDuckGo scrape (`backend/mcp/layer.py`, `web_search`), so page titles are
live, attacker-influenceable text.

**Mechanism** (`backend/engine/prompt_security.py`): a labeled
`=== BEGIN/END UNTRUSTED CONTENT (<label>) ===` wrapper, plus a standing
policy string (`UNTRUSTED_CONTEXT_POLICY`) telling the model to treat
anything inside that wrapper strictly as data. `governed_chat`
(`backend/engine/agent.py`) prepends the policy as a required,
priority-0 context section for every phase (`chat_reply`, `plan`, `execute`,
`reflect`) centrally, so it can't be dropped by a call site forgetting it,
and wraps every successful tool-call result before it goes back into the
message list.

**Wrapped:** `format_context` (RAG search), `format_graph` /
`format_task_graph` (knowledge graph), `format_memory` (saved memory),
`format_workspace_snippets` (file contents), and the generic tool-result
message path (covers all 25 tools, most importantly `web_search`).

**Deliberately not wrapped:**
- `format_task_sources` — pure structured metadata (`source#chunk score=X`),
  no free text to inject through.
- `format_conversation` — the operator's own prior turns; already trusted.
- Tool-call **errors** (`Error executing {tool}: {exc}`) — Rasputin's own
  generated string, not fetched content.
- **Skills** (`backend/mcp/skills.py`) — Desktop skills are declarative `SKILL.md`
  instructions, not agent-authored Python code. Their guidance is handled through
  the normal model/tool policy and the same capability, approval, and audit
  checks as other model context in every supported runtime.

Covered by tests in `tests/testBackendSmoke.py` —
`testGovernedChatPrependsUntrustedContentPolicyToEveryPhase`,
`testGovernedChatWrapsToolResultsAsUntrustedContentButNotToolErrors`,
`testFormatHelpersWrapRetrievedContentButNotEmptyFallbacks`.

## 4. Trusted Dev Mode

An explicit, per-workspace opt-in (`workspace.py`'s `trusted` flag on a
workspace record). Trusted:
- `fs_write` / `fs_patch` / `fs_mkdir` / `fs_move` / `git_add` skip the
  per-action approval queue (untrusted workspaces still hit
  `approvals.mutation_preview(...)` and need a human click every time).
- `git_commit` always requires a fresh one-time approval, even in a Trusted
  Dev workspace. A commit changes durable repository history and is therefore
  deliberately separate from the edit/test-loop trust grant.
- Every call is still audit-logged (`audit.log(..., trusted=True/False)`).

Trusted Dev Mode does **not** grant shell execution. Host Shell is a second,
separate per-workspace opt-in (`allow_host_shell`), and the global
`allow_shell_execution` flag must also be enabled. Every shell call is
audit-logged and still runs through `SHELL_DENY_PATTERNS`. In packaged
Desktop/native Windows, Host Shell is currently fail-closed: it is unavailable
until a proven AppContainer runner exists, with no dedicated-account or
operator-account fallback.

Privacy Lock (`allow_remote_models`) is independent of Trusted Dev Mode —
trusting a workspace for local shell/file access has no effect on whether
model traffic can leave the machine. Actions that are inherently
externally-visible (`git push` and friends) are not in the current tool
list at all, so there's nothing to gate yet — add this to Known Gaps if a
push-capable tool is ever added.

## 5. Execution surfaces — explicit runtime boundaries

Rasputin does not claim one isolation level for every execution surface. The
packaged Desktop path is deliberately conservative while Windows process
isolation is being migrated.

**Desktop Skills** (`backend/mcp/skills.py`): skills are declarative `SKILL.md`
instructions. They are supplied to the model as governed guidance; they do not
execute skill-authored Python, launch a child interpreter, or require Docker.
Tool calls remain subject to server-side capability checks, workspace policy,
approvals, and audit logging in every supported runtime.

**`shell_exec`** (`backend/mcp/layer.py`) has a runtime-specific boundary:

- **Packaged Desktop/native Windows:** Host Shell is unavailable and fail-closed
  until a proven Windows AppContainer runner is implemented and verified. It
  never runs as the operator account and does not create a dedicated Rasputin
  Windows account as a fallback.
- **Docker wrapper / native non-Windows:** the existing direct subprocess path
  remains a deployment-specific legacy boundary with sanitized environment,
  bounded output, process-tree timeout handling, and the deny-pattern guardrail.
  Docker shell commands run inside the long-lived wrapper container, not a fresh
  disposable container per call.

**Git tools** run as direct backend child processes. They retain their workspace
containment/trust/approval checks, but they are not an arbitrary-code sandbox.
Do not describe every agent execution surface as having the same isolation level.

### 5.1 Opt-in isolated Code tasks

Code mode offers an explicit **Isolate repo** option for a single general
agent. Rasputin first requires a clean, approved, top-level Git checkout and
a data directory that does not overlap that checkout. It then creates a
dedicated task branch and worktree under its data directory. If any preflight
check fails, the task is visibly blocked; it never falls back to editing the
source working tree.

During planning, source-repository access is read-only. During execution,
available file and Git tools are pinned server-side to the task worktree; the
agent cannot override the workspace path. The phase capability set is also
enforced server-side, so a fabricated tool call cannot invoke a withheld tool.
Host Shell, automatic test commands, `git add`, and `git commit` are excluded
because the current shell boundary is not worktree-confined. Linked-worktree
`.git` metadata is protected from mutation; task-worktree Git calls suppress
hooks, external diffs, and fsmonitor, and worktree provisioning strips
inherited `GIT_*` routing/config overrides.

The worktree is retained for review after the task. This protects the source
working tree and its checked-out branch (Git necessarily records the linked
worktree and task branch in repository metadata); it is not a sandbox for
arbitrary code, and v1 intentionally
does not auto-apply, merge, or delete the retained changes.

## 6. Known gaps

Ranked by how much they should change what you're willing to expose.

### 6.1 — RESOLVED 2026-07-07 — the login/session boundary was a no-op

Found 2026-07-06: `backend/core/auth.py`'s `login()`, `public_session()`,
and `require_user()` unconditionally returned an authenticated admin
session regardless of any password or cookie, and `backend/api/core.py`'s
`current_user()` — the actual `Depends(...)` gate on nearly every API
route — was an even more direct version of the same stub, entirely
disconnected from `auth.py`. Real PBKDF2-HMAC-SHA256 password hashing, a
real first-run credential bootstrap, login rate-limiting/lockout, and
session TTL pruning all existed in the same file but weren't wired to any
of those three functions.

**Fixed by reconnecting the existing infrastructure, not building new
infrastructure:**
- `login()` now calls `_check_login_rate` / `_verify()` against the stored
  hash, records failures (`_record_login_failure`), and on success mints a
  real token and populates `_sessions`.
- `public_session()` now checks `test_bypass_enabled()` and
  `localhost_bypass_enabled()` (both still explicit, env-gated opt-ins —
  see §1) before falling through to a real `session_info(token)` lookup;
  no token or an invalid one now correctly returns
  `{"authenticated": False}`.
- `current_user()` (`backend/api/core.py`) now reads the session cookie,
  calls `auth.public_session(token, host)`, and raises `PermissionError`
  (→ HTTP 403, matching every other permission-style failure in this
  codebase) when not authenticated — this is the change that actually
  closes the gap, since it's the dependency every protected route uses.

**Why this didn't brick the app:** the frontend (`LoginShell.jsx`,
gated rendering in `App.jsx`) was already fully built against real
session semantics — it just never had a reason to fail before. Verified
end-to-end against a live server: session check before login reports
`authenticated: false`, a protected route 403s, wrong password 403s,
correct password (the real bootstrap-printed one) succeeds and sets a
working cookie, the same protected route then returns 200, and logout
immediately locks it back out. Covered by three new tests in
`testBackendSmoke.py` (`testLoginRejectsWrongPasswordAndAcceptsCorrectOne`,
`testLoginRateLimitLocksOutAfterRepeatedFailures`,
`testCurrentUserEnforcesRealSessionWhenBypassesDisabled`).

**Credential recovery:** the generated password is printed only when the
admin record is first created. `rasputin.ps1 credentials` can recover it only
while that original line still exists in the current container logs. After a
container replacement/log loss—or after the password was changed—use
`rasputin.ps1 reset-password`; for a native run use
`python -m backend.tools.reset_password`. A reset changes the stored hash and
clears sessions in the resetting process; restart the running server/container
if you need to invalidate sessions it already holds in memory immediately.

**Caveat carried forward, not fixed:** `localhost_bypass_enabled()` checks
`request.client.host` against a literal loopback set. Behind the standard
docker-compose deployment that's the bridge gateway IP, not `127.0.0.1` —
so this bypass is a native-dev convenience only and simply never fires in
the primary deployment mode. That's intentional (conservative), not a gap,
but don't extend it to trust proxy headers without real thought.

### 6.2 — Desktop skill migration and fail-closed shell

The packaged Desktop skill path now treats `SKILL.md` files as declarative
instructions. It does not execute arbitrary Python skill code or depend on a
Docker daemon. Tool calls requested during a skill-guided task still pass
through the normal server-side capability, workspace, approval, and audit
separate compatibility path until that deployment is retired.

The former dedicated-account native Windows shell path has also been retired
from Desktop. Host Shell remains unavailable until an AppContainer runner is
proven to provide the required workspace, process, and network boundaries.

### 6.3 — Residual execution caveats

The Desktop Host Shell migration is not complete: AppContainer process creation,
workspace access, toolchain availability, network denial, and cleanup all need
implementation and verification before shell execution can be re-enabled. Until
then, Desktop fails closed and relies on governed file/Git tools. Docker/POSIX
direct shell and Git processes retain the deployment-specific privileges
described in §5. Operators needing a VM-grade native boundary still need an
external VM/WSL/container arrangement.

### 6.4 — Prompt-injection wrapper is a mitigation, not a guarantee

Labeling content as untrusted and instructing the model not to obey it
reduces the odds a model acts on injected instructions; it does not
eliminate the possibility a sufficiently capable adversarial payload gets a
model to act anyway. Tool-level guardrails (approval queues, Trusted Dev
Mode/Host-Shell scoping, the native low-privilege account, approval gates, and
deny-pattern shell filters remain the actual backstops, not
the prompt wrapper.

## 7. What this document is not

Not a penetration-test report, not exhaustive, and not a substitute for
re-reading the code before relying on any specific claim here — see the
per-section file:line citations and verify them directly. Update this file
when the boundaries it describes change, especially §6.1.

## Unattended mode (implemented)

Setting `unattended_mode` in Security, or `RASPUTIN_UNATTENDED=1` for a
dedicated process, applies a server-side deny-by-default tool allowlist. Local
read/search, memory, graph/RAG, bounded workspace inspection, local Git
inspection, and approved file edits remain available. Shell execution, web
search, external MCP tools, workspace reorganization, Git staging/commit/
restore, and newly registered tools are blocked before their implementation
receives model-authored arguments. File edits additionally require a Trusted
Dev workspace. Rejected calls are not retried by changing syntax, and blocked
tools are removed from model capability schemas.
