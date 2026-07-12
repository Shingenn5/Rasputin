# Phase A1 — Recon Launch + Audit (findings)

*2026-07-12. The roadmap's Phase A1 gate: "a written broken/rough backlog + a
primitives/themes inventory." This is that artifact. It replaces the guesswork in
`docs/ROADMAP.md` (A2–F) with facts from actually running the app.*

## How this was produced

- Built `frontend-src/` → `frontend/` (`npm run build`, green) and launched `server.py`
  on port 8899 with an isolated `RASPUTIN_DATA_DIR` (real data untouched).
- **Auth is no longer stubbed** — the verify skill doc is stale on this. The API now
  enforces login (`/api/auth/login` sets an httponly `rasputin_session` cookie). Logged
  in with the printed first-run admin password; drove the UI via Playwright with the
  session cookie injected.
- Registered a **mock OpenAI-compatible model** (streaming SSE) as the selected `main`
  model. Drove every core loop, captured screenshots + console/page/HTTP errors per view
  (15+ views, light and dark), and **triggered primary actions** on the surfaces where that
  was cheap (send a chat message, open the `/` command menu, change + save a setting,
  launch a workspace task).

### ⚠️ Two honesty caveats — read these before trusting the table

1. **Mock model, not a real one.** Everything was verified against a *mock* OpenAI-compatible
   endpoint, not a real local model (vLLM / llama.cpp / Ollama / a WarSat deployment). The
   app's model plumbing — register → reachability test → select → **streamed chat** — works
   through a standard OpenAI-compatible endpoint. But *"does a real local model actually load,
   run, and stream a useful answer for a real task"* is **unverified** (no GPU / weights here).
   **This is the single likeliest home of any real "not working for daily use" pain, and it
   is what Phase A2 must close first.**
2. **"Renders cleanly" ≠ "works."** A view mounting with zero console errors and a polished
   screenshot proves it *rendered* — not that its primary action functions. The table below
   is split accordingly: surfaces I **drove end-to-end** vs. surfaces I only saw **render**.
   Don't read "renders cleanly" as "works."

---

## Audit — driven / renders / rough / broken

Headline: **this is not a broken app.** The UI shell, routing, auth, theming, and the full
chat/task loop are solid and genuinely polished; **zero** console / page-error / HTTP-4xx-5xx
events fired across 15+ views in light and dark. But **daily usability turns on real model
workflows this recon could not exercise** — so the reported "not working" most likely lives
there, not in the shell.

### ✅ Driven end-to-end — confirmed working
| Surface | What I triggered → result |
|---|---|
| **Login** | username/password → httponly cookie session; authenticated API access. |
| **Chat / task loop** | typed → sent → **streamed reply** rendered in a thread (user/model avatars, "done" badge, "Details" expander, "Task started" toast, Activity badge +1). |
| **Chat `/` command menu** | "/" on an empty composer opens the menu with **11 commands** (`/mode`, `/model`, `/reasoning`, `/attach`, `/queue`, `/prompts`, …). |
| **Settings save** | changed Platform Theme → Save fired `POST /api/preferences` + `POST /api/settings/general` (both 200); **persisted across reload.** *(Caveat: no success toast — see rough.)* |
| **Theme switching** | picker change applies **live** and persists. *(Caveat: initial value bug — see rough.)* |
| **Workspace task launcher** | "Summarize Directory" → **stages a prompt** into the composer ("Workspace analysis prompt loaded"). It loads, it doesn't auto-run — and it silently switches mode (see rough). |

### 🖼️ Renders cleanly — NOT driven (mounted without errors; primary action untested)
| Surface | Rendered content (not proof it works) |
|---|---|
| **Dashboard** (`#home`) | Modern analytics landing (Tailwind + shadcn + **Recharts**): KPI cards w/ sparklines, run-activity chart, "No runs yet" empty state. *(Charts render; data is empty.)* |
| **Models Center** | Stat tiles, Library/Installed/Running/Settings tabs, catalog cards w/ VRAM+fit badges, "Deploy via Warsat". **Did not deploy a model.** |
| **WarSat Command** | Mission Planner form, Safety Status panel, 8 tabs. **Did not launch a mission.** |
| **Workspaces (rest)** | File explorer, approved-folders, RAG/Graph knowledge ops, agent-capability routing, **Host Shell** toggle (Off). **Did not index, run knowledge ops, or enable Host Shell** (side-effectful — left observed-only intentionally). |
| **Settings (rest)** | 12 sections all mount. **Only General was driven.** |
| **Security Center** | "Privacy Lock Active" hero + Privilege & Approval Matrix. **Did not toggle a privilege.** |

### 🟡 Rough — works, but thin or inconsistent
| Item | Note | Size |
|---|---|---|
| **Real-local-model loop unverified** | Not observed broken — *not observed at all.* The gating unknown. | Unknown (gating) |
| **Mode-switch silently breaks model selection** | Launching a workspace task switched mode to "Write", which re-routed the selected model from the healthy `mock-local` to an unreachable role model → header flipped to **STOPPED**. Documented `chooseTaskMode` gotcha, but it's a real daily foot-gun: staging a task can silently leave you on a dead model. | Small–med |
| **Theme picker shows the wrong active theme** | **Confirmed** (was "maybe"): picker read `rasputin-dark` while the active theme was `rasputin-light`. It defaults to `rasputin-dark` instead of initializing from the live theme; syncs only after a manual save. `GeneralSettings.jsx:85` (`value={formData?.theme \|\| "rasputin-dark"}`). | Trivial |
| **Save gives no confirmation** | Save persists correctly but shows **no success toast** — user can't tell it worked. | Trivial |
| **Blue "Save Changes" button** | Not an arbitrary color — it's react-bootstrap `Button variant="primary"` (`GeneralSettings.jsx:55`) leaking bootstrap's default blue through an un-migrated screen. Fixing it *is* the react-bootstrap retirement, in miniature. | Trivial (or Phase D) |
| **Thin secondary views** | Agents, Activity, Memory, Approvals, Archive render but are content-light / informational stubs with large empty regions. | Small each |
| **`Button` duplicated, both live** | `components/Button.jsx` (vanilla) *and* `components/ui/button.jsx` (shadcn) imported side-by-side at `ModelsView.jsx:43-44`. Needs a canonical pick. | Small |
| **Two parallel component systems** | Inventory §4 — a real ~50/50 split. Not visibly broken today, but coherence/maintenance debt that drifts as polish lands on one side only. | Medium (Phases C–E) |

### 🔴 Broken
**Nothing observed broken** in any core loop at the mock-model level. The only red-flag
region is the *untested* real-model path — an unknown, not a known break.

---

## Inventory — what already exists to build on

*(Independently re-verified against source: react-bootstrap footprint, `Button` duplication,
Modal/Sidebar dead-code, `@theme inline` token count, theme count.)*

### shadcn/ui primitives — `frontend-src/src/components/ui/` (all Tailwind + `cva`/`cn()`)
`badge.jsx` (5 variants), `button.jsx` (5 variants × 5 sizes incl. `pill`),
`card.jsx` (Card/Header/Title/Description/Content/Footer), `input.jsx`. **These four are
the complete `ui/` set.** Phase B's "adapt the existing primitives" starts from *four* and
must *add* Select, Switch, Dialog, Toast, Skeleton in the shadcn idiom (today those exist
only as vanilla-CSS `components/*` or as react-bootstrap).

### Older/custom `components/` (mostly vanilla CSS)
`Toast.jsx` (app-wide provider, `.ras-toast*`), `Skeleton.jsx`, `Drawer.jsx` (live),
`Avatar.jsx` (chat), `CodeSandbox.jsx` (Pyodide runner, chat), `Onboarding.jsx`,
`AppShell.jsx` (mixed Tailwind+legacy), `shell/DashSidebar.jsx` (**the live sidebar** —
Tailwind + framer-motion), `fx/CountUp.jsx`.
- **Dead code (no importers — don't budget migration):** `components/Modal.jsx` (superseded
  by react-bootstrap Modal), `components/Sidebar.jsx` (superseded by `DashSidebar.jsx`).
- **`Button` is duplicated and both copies are live** (see rough backlog).

### Token → Tailwind bridge (`styles/theme.css`)
Real but **deliberately narrow**: `@theme inline` (theme.css:59) maps **36 tokens = 32 color
+ 4 radius** into Tailwind utilities (`bg-card`, `text-muted-foreground`, …) via a 3-layer
chain: `index.html` inline theme script → `dashboard.css` (`--dash-*`) → `theme.css`
(shadcn-named vars). Scoped to a `.tw` class so it won't disturb legacy views — **the
Tailwind migration is intentionally partial.** No spacing/shadow/typography tokens are
bridged yet; the larger `rasputin.css` scale (`--ras-*`, `--cc-*`, `--bs-*`, `--sp-*`,
`--fs-*`, …; 77 declarations, ~13k lines of component CSS) is a separate older system
consumed via vanilla CSS / inline styles → components on it (Toast, Skeleton, Avatar,
CodeSandbox) need **re-tokenization**, not a file swap.

### Themes — **14 total** (roadmap's "11" = the dark subset)
`themeOptions` (constants.js:27-42) lists 14; `darkThemes` Set (constants.js:44-56) has 11.
3 light: `rasputin-light`, `bootswatch-lux`, `contrast`. Applied pre-React by `index.html`'s
`apply()` → sets `<html data-theme=…>`, toggles `.dark` (drives Tailwind's dark variant),
sets `data-bs-theme`. **Hazard:** theme colors live in `index.html` while picker metadata +
dark/light flags live in `constants.js` — a two-place sync point worth collapsing later.

### react-bootstrap footprint — **16 files** (the legacy-retirement scope)
- **Settings ×12** (every settings screen), **Workspaces**, **runtime/RuntimeViews**,
  **audit/AuditView**, **auth/LoginShell**.
- **Zero** in chat, tasks, models, warsat, dashboard — already on the modern stack. Global
  `bootstrap.min.css` imported at `main.jsx:7`.
- **Key planning fact:** not "settings is legacy, rest is modern" — a real **~50/50 split by
  feature area**, using the *same primitive names* (Card/Badge/Button) that already exist in
  `ui/`. Retirement = swap imports + re-style, area by area. (The blue Save button above is
  this debt made visible.)

---

## Proposed Phase A2 — sized by what A1 found

A1 changes the premise: there is **no broken agent loop at the app level**, so A2 is small and
has one real unknown to close.

**A2.0 (gating) — Verify the real-local-model daily loop.** Point the registry at a real local
endpoint (Ollama is lowest-friction: `ollama serve` exposes an OpenAI-compatible API on
`:11434/v1`), and run **one real end-to-end task** in chat and one workspace task. Watch for
streaming, tool-runs, and errors the mock can't surface. **This is the honest "get it working"
step; the rest of A2 is contingent on what it reveals.** If it Just Works (plausible — same code
path the mock exercised), A2 is nearly done. If it breaks, *that* is the real A2 scope, sized then.

**A2.1 (trivial cleanups, only if A2.0 is clean) —** the confirmed no-brainers, batched and
verified in the running app: fix the theme-picker initial value (`GeneralSettings.jsx:85`); add
a save-success toast; recolor the blue Save button to the accent; pick the canonical `Button` and
drop the duplicate `ModelsView` import; decide whether the mode-switch→STOPPED foot-gun gets a
guard/warning now or in Phase C. ~half a day.

**What A2 is explicitly NOT:** the thin secondary views and the react-bootstrap 50/50 split are
**real** but they are **Phase C–E work** (design-system + per-area polish), not "blocking daily
use." Folding them into A2 re-expands the scope the roadmap deliberately deferred.

**A2 gate (unchanged):** you complete a real end-to-end task in the running app, comfortably —
now specifically **with a real local model.** Whether the next move after that is more A2 fixes or
straight into Phase B/C is a decision A2.0's result should make, not this document.

---

## A2.0 RESULT (2026-07-12) — ran it against real vLLM; found the blocker

Ran A2.0 against a **real** model: `microsoft/Phi-3.5-mini-instruct` served by Rasputin's own
**WarSat managed vLLM deploy** (`vllmCudaOpenai` protocol, Docker, host `127.0.0.1:8000`).

**✅ Confirmed working with a real model:**
- WarSat managed deploy launches vLLM cleanly; endpoint reachable (Rasputin test: 191ms).
- **Warm inference is fine on this hardware:** measured **~47 tok/s** decode, **0.06s** time-to-
  first-token (direct benchmark). The earlier "0.8 tok/s" in the vLLM log was a **JIT-warmup
  artifact**, not steady state — disregard it. Cold start is ~3 min/launch (weight load + compile).
- Answers are coherent (Phi-3.5-mini handles simple prompts well).

**🔴 BLOCKER — every real chat/task 400s (root-caused, primary-source):**
Sending a plain chat message ("what is 17×23") returns **`HTTP 400 Bad Request`** in the UI even
though the model shows RUNNING. Direct probe against vLLM isolated the exact cause — vLLM's own body:
> `"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`

- **Client side:** `backend/engine/agent.py` sends `tools=tool_relay.TOOL_DEFINITIONS` on **every**
  turn — chat (`:975`), planning (`:1022`), execution (`:1054`). So every request advertises the
  full tool catalog.
- **Server side:** `backend/warsat/protocols/vllmCudaOpenai.json` `defaultArguments` do **not**
  include `--enable-auto-tool-choice --tool-call-parser`, so vLLM rejects any request carrying tools.
- **Net:** a healthy, fast, correctly-deployed local model is **100% unusable through Rasputin's
  chat/task loop.** The mock accepted anything, which is exactly why A1 never saw this.

**🟡 Latent foot-gun (same probe):** `max_tokens > max_model_len` also 400s
(`max_tokens=8192 cannot be greater than max_model_len=4096`). Rasputin should clamp output tokens
to the model's context; a long-generation task will hit this.

**Fix directions (a real fork — tool-calling is core to an agentic tool, so this needs a decision):**
- **A. Server-side:** add tool-call flags to the vLLM deploy protocol. Unblocks the 400, but
  Phi-3.5-mini has no first-class vLLM tool parser, so tool-call *reliability* stays weak on small
  local models.
- **B. Client-side graceful degradation (the robust fix):** detect/omit `tools` when the runtime
  can't accept them, or catch the specific 400 and retry once without tools — a chat that needs no
  tools must not hard-fail because tools were advertised. Add a per-model `supportsTools` flag.
- **C. Both** (correct long-term): enable tool flags where the parser supports the model, and make
  the client degrade gracefully everywhere else. Plus clamp `max_tokens` to context.

**This IS the real A2 scope.** It's a genuine daily-use blocker, now with a concrete root cause
instead of a guess — which is exactly what A2.0 was for.

### FIX APPLIED (2026-07-12) — client-side graceful degradation ✅ verified

Chosen approach: **Both**, but scoped to what's correct (per advisor pressure-test).

- **Client-side (done + verified) — `backend/models/providers.py` `chat_sync`:** for **local
  runtimes only** (`not is_api_provider(model)`; remote anthropic/gemini/openai untouched), any
  `400` while the payload carries tools → **drop tools and retry once**, and cache the model key in
  an in-process `_TOOLS_UNSUPPORTED` set so later calls skip tools proactively (no repeated failed
  round-trip). Trigger is **structural, not string-matched** (any tools-bearing 400), so it holds
  across llama.cpp / LM Studio / other vLLM versions. Also **clamps `max_tokens`** to the model's
  context on the `max_model_len` 400 (latent guard; default 1024 < 4096 so not otherwise exercised).
  Retry is clean because the 400 fires before any SSE (verified: single, non-duplicated reply).
- **Verification (running app, real model):** re-sent "what is 17×23" against the live vLLM
  Phi-3.5-mini deploy → assistant returned **"391 …"** with a "done" badge, **no 400, no console
  errors, single clean response.** The A2 gate (real end-to-end task with a real local model) is met.
- **Scope of the claim (honest):** this makes **conversational chat** (mode = chat, the primary
  daily surface) work end-to-end. It does **not** make **agentic tool-execution** work: in
  planning/execution phases tools *are* the work, so dropping them makes the model return prose and
  `governed_chat` treats empty `tool_calls` as "done" (`agent.py:890-892`) — a silent no-op. Phi-3.5-
  mini wouldn't reliably tool-call regardless. Real agentic execution needs a tool-capable model +
  the matching server-side parser (below), and ideally a UI signal when tools were unavailable.
- **Server-side (deliberately NOT done globally):** adding `--enable-auto-tool-choice
  --tool-call-parser <x>` to `vllmCudaOpenai.json` was rejected as a global default — the parser is
  **model-specific**, and a mismatched parser silently corrupts tool parsing for every other vLLM
  deploy. So "Both" resolves to **client-side now + server-side per-deploy when a tool-capable model
  (e.g. a Hermes/Qwen tool model) is deployed with its matching parser.** Handed back to the user.
- **Status:** committed on `codex/agentic-coding-loop-v1` (`3c653c1`). Files touched:
  `backend/models/providers.py` (added `import re`, `_TOOLS_UNSUPPORTED`, `_http_error_body`,
  `_parse_context_limit`, `_build_chat_payload`; rewrote `chat_sync`).

### AGENTIC EXECUTION — the loop works; the gap is model+parser (2026-07-12)

**Diagnostic:** to separate "does the agent loop work" from "can a small local model tool-call,"
I pointed Rasputin at a **controllable mock** that emits a valid streaming OpenAI `tool_call` for
`rag_search` on turn 1, then final text once it sees a `role:tool` result. Ran a `mode=code`
(agentic) task.

**Result — the plan→execute tool loop is fully functional.** Task `9297f546` logs:
`started → tool: rag_search → plan made → tool: rag_search → executed → done`. Mock request log
confirms the round-trip in **both** planning and execution phases: turn 1 `roles=[user]` → emit
tool_call; turn 2 `roles=[user, assistant, tool]` → tool result fed back → final text. So Rasputin
correctly **parses streaming tool_calls, executes the real tool (`mcp.call_tool`), appends the
result, and re-prompts** — `_stream_openai` + `_finalize_tool_calls` + the `governed_chat` loop all
work. **The agent loop is not the blocker.**

**So agentic execution fails with the user's vLLM for exactly two model-layer reasons:**
1. The model must emit valid tool calls → needs a genuinely **tool-capable** model. Phi-3.5-mini
   (3.8B) isn't a reliable tool-caller.
2. vLLM must run with the **matching `--tool-call-parser`**. Today `warsat/__init__.py:744`
   **hardcodes `hermes`** for every vLLM deploy — wrong for non-Hermes models (silently mis-parses
   their tool calls) — and the user's *running* container predates that line entirely (it has no
   tool flags at all, hence the 400 the client fix now absorbs).

**Remaining work to make agentic execution real (well-scoped now):**
- **A. ✅ DONE — vLLM `--tool-call-parser` is now model-configurable** (`warsat/__init__.py`).
  Replaced the hardcoded global `hermes` with a sanitized, opt-in per-deploy `toolCallParser`
  (`_tool_call_parser` + a `_build_tuning` field): a parser is emitted only when the deploy sets
  one (`--enable-auto-tool-choice --tool-call-parser <parser>`); with none, tool flags are omitted
  and the chat engine's degradation handles the resulting tool-less runtime. Unit-verified: default
  emits no flags, an explicit parser is emitted + sanitized to `[a-z0-9_-]`. Committed.
- **B. ✅ DONE — proven end-to-end with a real tool-capable model (2026-07-12).** Deployed
  **Qwen/Qwen2.5-3B-Instruct** through WarSat on the isolated instance with `toolCallParser=hermes`.
  Verified: the generated `docker run` carried `--enable-auto-tool-choice --tool-call-parser hermes`
  (my fix, through the real plan/deploy path); container came up healthy on `127.0.0.1:8001`; a
  plain chat returned "42" with **no 400**; and a `mode=code` agentic task logged
  `started → tool: rag_search → plan made → tool: rag_search → executed → done` — **the real Qwen
  model emitted tool calls in both planning and execution phases, vLLM's hermes parser extracted
  them, and Rasputin executed the tool and fed results back.** (Result text was empty only because
  this instance's RAG index is unpopulated; the tool *executed* — that's the proof.) Also required
  adding `tool_call_parser` to `WarsatPlanIn` (the API model stripped it). Committed (`3c26a25`,
  `100a905`). **Remaining nicety:** a deploy-form field for the parser (frontend) + optional
  per-catalog-model parser hint, so it isn't API-only.
- **C. (lower priority)** Guard the silent no-op: when tools were unavailable and an execution phase
  returns prose with empty `tool_calls`, surface "tools unavailable — ran as plain chat" instead of
  reporting the prose as a completed task (`agent.py:890`). Lower priority now the loop is proven.
