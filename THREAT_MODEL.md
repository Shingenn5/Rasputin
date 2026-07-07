# Rasputin Threat Model

This document describes what Rasputin trusts, what it doesn't, where the
boundaries are enforced in code, and — honestly — where they currently
aren't. It's written for whoever is deciding whether to expose an instance
beyond their own machine, and for whoever picks up the next piece of
security work.

It is a snapshot as of 2026-07-06. Verify file:line citations against
current code before relying on them; this system moves fast.

---

## 1. Operating assumption

Rasputin is built to run **on one operator's own machine, for that operator**.
Nearly every design decision downstream of this document assumes a single
trusted human is sitting at the keyboard (or SSH'd into their own box) and
that the thing to defend against is *content*, not *the operator*:

- Web pages, RAG'd files, and tool output the agent fetches on the
  operator's behalf may contain adversarial text ("ignore previous
  instructions...") — this is an active, in-scope threat (see §3).
- The operator themself is not an adversary. Trusted Dev Mode (§4),
  Privacy Lock, and the approval system all exist to let the *operator*
  control what an *agentic loop running on their behalf* can do — not to
  protect Rasputin from someone who already has legitimate access to it.
- Anyone who can reach the API surface at all is currently a different
  question — see the Known Gaps section (§6), specifically 6.1. That gap
  means the "single trusted operator" assumption is presently enforced by
  network topology (don't expose the port), not by the app itself.

## 2. Roles & permission flags

`backend/core/security.py` holds one flat set of boolean flags, checked via
`security.require(flag)` at each sensitive call site. Defaults:

| Flag | Default | Gates |
|---|---|---|
| `allow_file_read` | on | RAG ingest, graph build, file preview |
| `allow_file_write` | on* | `fs_write`/`fs_patch` — *also subject to the approval queue unless the workspace is Trusted (§4) |
| `allow_file_reorganize` | off | `fs_mkdir`/`fs_move` |
| `allow_shell_execution` | **off** | `shell_exec` — additionally hard-requires Trusted Dev Mode regardless of this flag |
| `allow_web_search` | on | `web_search` (DuckDuckGo scrape, brokered — see §3) |
| `allow_docker_control` | **off** | WarSat deploys, host folder browsing, mount requests |
| `allow_remote_models` | **off** | "Privacy Lock" — routing to any non-local model endpoint |
| `allow_model_tests` / `allow_model_registry_edit` | on | Trials engine, model registry edits |

There is no per-tool self-escalation path: no tool in `backend/mcp/tools.py`
(25 registered IDs, confirmed by direct listing) can flip its own or any
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
- **Skills** (`backend/mcp/skills.py`, `backend/core/sandbox.py`) — these
  are Python *code* the agent writes and runs, not prompt text. Wrapping
  doesn't apply; the relevant boundary is execution sandboxing (§5), a
  different risk category.

Covered by tests: `tests/testBackendSmoke.py` —
`testGovernedChatPrependsUntrustedContentPolicyToEveryPhase`,
`testGovernedChatWrapsToolResultsAsUntrustedContentButNotToolErrors`,
`testFormatHelpersWrapRetrievedContentButNotEmptyFallbacks`. Full suite
73/73 passing as of this writing.

## 4. Trusted Dev Mode

An explicit, per-workspace opt-in (`workspace.py`'s `trusted` flag on a
workspace record). Trusted:
- `shell_exec` becomes available at all (untrusted: blocked outright,
  regardless of the `allow_shell_execution` flag).
- `fs_write` / `fs_patch` / `fs_mkdir` / `fs_move` / `git_add` /
  `git_commit` skip the per-action approval queue (untrusted workspaces
  still hit `approvals.mutation_preview(...)` and need a human click every
  time).
- Every call is still audit-logged (`audit.log(..., trusted=True/False)`)
  and still runs through `SHELL_DENY_PATTERNS` guardrails.

Privacy Lock (`allow_remote_models`) is independent of Trusted Dev Mode —
trusting a workspace for local shell/file access has no effect on whether
model traffic can leave the machine. Actions that are inherently
externally-visible (`git push` and friends) are not in the current tool
list at all, so there's nothing to gate yet — add this to Known Gaps if a
push-capable tool is ever added.

## 5. Execution surfaces — two different isolation levels

It's easy to read the README's "isolated ephemeral Docker sandboxes" line
and assume it covers all agent-executed code. It covers one of two
surfaces:

**Skills** (`backend/core/sandbox.py`, `run_skill_in_sandbox`): each run is
a fresh `docker run -i --rm rasputin-sandbox python /sandbox/wrapper.py`,
destroyed after. No host filesystem bind mount. **Known weakness:** it runs
with `--network host` (see §6.2) rather than an isolated bridge network.

**`shell_exec` / git tools** (`backend/mcp/layer.py`): run via
`asyncio.create_subprocess_shell`/`create_subprocess_exec` directly in
Rasputin's own backend process — **not** a fresh disposable container per
call. This is a deliberate trade, not an oversight: Trusted Dev Mode is
explicitly meant to behave "the same way a real terminal works" for a
workspace the operator has already vouched for, scoped to that workspace's
directory (`cwd=str(base)`), with a sanitized environment and deny-pattern
guardrails. Anyone who can trigger `shell_exec` in a Trusted workspace has
the same reach as a terminal opened in that directory — no more, no less,
and no additional container wall.

## 6. Known gaps

Ranked by how much they should change what you're willing to expose.

### 6.1 — HIGH — the login/session boundary is currently a no-op

`backend/core/auth.py`'s `login()`, `public_session()`, and `require_user()`
unconditionally return an authenticated admin session regardless of any
password or cookie:

```python
def login(username, password, client="local"):
    return "mock-token", {"username": "admin", "role": "admin"}

def public_session(token=None, client_host=""):
    return {"authenticated": True, "username": "admin", "role": "admin"}
```

`login()` never calls `_verify()` against the stored password hash and
never populates `_sessions`. `public_session()` never consults `_sessions`
either (that's what `session_info()` does — correctly — but nothing calls
it). `require_user()`'s failure branch (`if not session.get("authenticated")`)
can therefore never trigger. `backend/api/core.py`'s `current_user()` is an
even more direct version of the same stub.

This sits next to **real** infrastructure that suggests it was meant to be
wired up, not that no-auth was the plan: correct PBKDF2-HMAC-SHA256
password hashing (`_hash_password`/`_verify`, 180k iterations), a real
first-run bootstrap that generates and prints genuine admin credentials,
login rate-limiting/lockout state (`_check_login_rate`,
`_record_login_failure`), a session TTL/pruning mechanism
(`_prune_sessions`), and `change_password()`, which *does* correctly call
`_verify()`. The separate, explicit `RASPUTIN_LOCALHOST_BYPASS` /
`RASPUTIN_TEST_AUTH_BYPASS` env flags — which look like the *intended*,
narrow, opt-in bypass mechanism — aren't even what's causing this; the
unconditional stub bypasses everything regardless of those flags' values.

**Practical effect:** as shipped today, any request that reaches the API —
with any password, any cookie, or none at all — is treated as authenticated
admin. The login screen is decorative. This is fine if Rasputin never
listens on anything but `127.0.0.1` on a single-user machine; it stops
being fine the moment the port is reachable from anywhere else (a LAN, a
VPN peer, a container network shared with something less trusted).

This was **not fixed** as part of this pass — deciding whether real login
should be wired up (the pieces to do it are ~90% already in the file) or
whether localhost-only-no-auth is the accepted design is a call for
whoever owns this instance's exposure, not a unilateral code change.

### 6.2 — MEDIUM — Skills sandbox shares the host network namespace

`run_skill_in_sandbox` (`backend/core/sandbox.py:24`) launches the
ephemeral skill container with `--network host`. Code the agent wrote and
is running as a "Skill" can therefore reach anything the host machine can
reach on the network — not just Rasputin's own sandbox API. The comment in
the code (`# Use host network so it can reach localhost if running
natively`) explains why, but an isolated bridge network with an explicit
published port back to Rasputin would remove the need for full host
networking.

### 6.3 — Sandboxing is otherwise an open design problem, not solved here

Per the coding-agent-competitiveness plan, this was deliberately deferred
rather than rushed. §5 above describes the current, real behavior of both
execution surfaces so that deferral is an informed one, not an assumed one.

### 6.4 — Prompt-injection wrapper is a mitigation, not a guarantee

Labeling content as untrusted and instructing the model not to obey it
reduces the odds a model acts on injected instructions; it does not
eliminate the possibility a sufficiently capable adversarial payload gets a
model to act anyway. Tool-level guardrails (approval queues, Trusted Dev
Mode scoping, deny-pattern shell filters) remain the actual backstop, not
the prompt wrapper.

## 7. What this document is not

Not a penetration-test report, not exhaustive, and not a substitute for
re-reading the code before relying on any specific claim here — see the
per-section file:line citations and verify them directly. Update this file
when the boundaries it describes change, especially §6.1.
