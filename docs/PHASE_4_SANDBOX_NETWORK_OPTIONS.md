# §6.2 — Skills-sandbox network isolation: options for review

*Step 2 of `docs/EXECUTION_PLAN.md`. Design note only — no code changes to the skills
path until you pick an option. Closes `THREAT_MODEL.md` §6.2.*

## The problem

`run_skill_in_sandbox` (`backend/core/sandbox.py:24`) launches each skill container with
`--network host`:

```python
"docker", "run", "-i", "--rm",
"--network", "host",   # so it can reach the wrapper API at localhost
...
```

`--network host` puts the skill container in the **host's network namespace** — agent-written
skill code can reach anything the host can reach (the LAN, other local services, link-local
metadata endpoints), not just Rasputin's own API. That's the MEDIUM finding in §6.2.

## Why it's there (the real constraint)

The only reason the container needs the network at all: the skill calls tools back on the host.
`sandbox/client.py` does exactly one host interaction beyond stdin/stdout —

```python
requests.post(f"{RASPUTIN_API_URL}/call-tool", json={"tool_id":..., "args":...},
              headers={"X-Sandbox-Token": token})
```

a **single token-authed request/response RPC** to `/api/sandbox/call-tool`. Skill input
(`skill_code`) already arrives on **stdin**; the result already returns on **stdout**.

Two facts shape every option:
- **Native mode binds the wrapper to `127.0.0.1` only** (`rasputin.ps1:180` `HOST=127.0.0.1`).
  A host service bound to loopback is **not** reachable from a container via
  `host.docker.internal` — that address routes to the host's gateway interface, not loopback.
  So "just use `host.docker.internal`" doesn't work without *also* widening the wrapper's bind.
- **It must work in both runtimes**: native (wrapper on the host) and docker (wrapper is itself
  a container, skill is a sibling). Any fix has to hold in both.

---

## Option A — Bridge network + reach the wrapper via the gateway  *(Medium)*

Swap `--network host` for Docker's normal bridge; the skill reaches the wrapper at
`host.docker.internal:8787`. To make a loopback-bound wrapper reachable, bind the sandbox API
to the Docker **gateway interface** (e.g. the `172.x.0.1` bridge gateway) or `0.0.0.0`, not just
`127.0.0.1`.

- **Closes §6.2?** Yes — container leaves the host network namespace.
- **Egress?** Still has NAT internet (bridge default). A mistaken `curl … | sh` or typosquatted
  `pip install` is **not** blocked. Add a `--internal` network or firewall for that (→ Option B).
- **Cost:** widen the wrapper's bind surface (the thing the loopback-only hardening deliberately
  avoided). Mitigated by the existing `X-Sandbox-Token` on `/api/sandbox` + the Origin/Host
  middleware (which already allows `host.docker.internal`) + an OS firewall rule on `:8787`.
- **Cross-runtime:** native needs the bind change; docker mode uses a shared/user-defined network.
- **Verdict:** the minimum that closes the *documented* gap, but it trades away a bit of the
  loopback hardening and leaves internet egress open.

## Option B — Internal bridge (egress-denied)  *(Medium+, needs validation)*

Option A on a Docker `--internal` network: the container can talk to the host gateway but has
**no external route** — no internet.

- **Closes §6.2 + egress?** Yes to both, *if* skills don't need the internet.
- **Risks / validate:** (1) does `host.docker.internal` still resolve/reach the host on an
  `--internal` network? (uncertain — Docker removes the external route; host reachability needs a
  test). (2) Skills that `pip install`/fetch at runtime break — need to know if any do, or provide
  an allowlisted mirror.
- **Verdict:** a hard egress wall, but couples us to Docker networking quirks and may break
  network-using skills.

## Option C — No network at all (`--network none`) + stdio RPC  *(Higher, recommended target)*

Remove the network entirely. Replace the one HTTP callback with a **framed stdio RPC** over the
channel we already use: the skill writes a tool-call request (a tagged JSON line) to its output;
the host's `run_skill_in_sandbox` loop reads it, dispatches to the same `McpLayer.call_tool` the
HTTP route already calls, and writes the JSON result back to the skill's stdin. The final
`---RESULT---` rides the same stream. Run the container with `--network none`.

- **Closes §6.2 + egress?** Completely — the container has **zero** network. This is the model
  Codex/Claude Code use (no network by default) and the correct answer for the accidental-fallout
  threat: exfiltration and `curl|sh` are impossible, not merely discouraged.
- **Sidesteps the loopback problem entirely:** no `host.docker.internal`, no bind widening, no
  firewall for the sandbox, no per-runtime networking differences — nothing to configure in either
  native or docker mode.
- **Cost:** a protocol rewrite in `sandbox/client.py` (HTTP → stdio frames), `sandbox/wrapper.py`,
  and a host-side dispatch loop in `backend/core/sandbox.py` replacing `process.communicate()` with
  an interleaved read/dispatch/write loop. The RPC is simple (request/response), and the host-side
  tool dispatch already exists (`/api/sandbox/call-tool` just calls `McpLayer`), so the new code is
  the framing + the loop, not new tool logic.
- **Verdict:** most secure, most aligned with the product's security thesis, and architecturally
  *simpler* at runtime despite more upfront code. Removes a whole class of networking config.

---

## Recommendation

**Target Option C**, and if you want §6.2 flipped to RESOLVED sooner, ship **Option A** first as
an interim and land C in a follow-up.

Rationale: C is the only option that actually matches the threat model (accidental egress is
*prevented*, not just namespace-isolated), it's how real coding-agent sandboxes work, and it
removes the awkward loopback-vs-`host.docker.internal` bind problem instead of working around it.
The extra code is bounded — a small framed-RPC protocol, reusing the existing tool dispatch. A is
a legitimate quick close if timing matters, but it keeps internet egress open and slightly widens
the wrapper's exposure, so it's a stepping stone, not the destination.

## If you pick C — validation checklist for implementation (Step 4)
- Frame format: length-prefixed or sentinel-tagged JSON lines that can't collide with skill
  `print()` output (use a dedicated marker/again, or a separate fd via `docker run` if we want
  stdout clean).
- Confirm `--network none` containers still start and run Python skills (they will; no network is
  needed for local execution).
- Keep the `SANDBOX_SECRET_TOKEN` as defense-in-depth even though stdio is already private to the
  parent/child, or drop it as dead weight — decide during implementation.
- Regression-test a representative skill end-to-end in both native and docker runtimes.

---

**Your call:** A (interim) → C, or straight to C? Once you pick, implementation is Step 4 (behind
its own verification gate; `THREAT_MODEL.md` §6.2 flips to RESOLVED with the chosen design recorded).
