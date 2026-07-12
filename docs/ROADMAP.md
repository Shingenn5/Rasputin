# Rasputin — Master Execution Roadmap

*2026-07-12. The single top-level "what we do next, and in what order" doc. It sequences
everything discussed this session into a doable order and points to the detailed sub-plans
rather than duplicating them. Where this conflicts with a sub-plan's internal ordering, **this
roadmap wins on order.***

## Status — read this first (cold-start handoff)

**As of 2026-07-12.** Written so this plan survives a fresh session with zero chat context.

- **Immediate next action:** **Phase A1 — launch the app** (verify skill) and audit. The app has
  **not been launched** this session; "not working for daily use" is unscoped until A1 runs. Nothing
  past A1 has started.
- **Done (don't redo):** security core — Phases 0–4 (dual-mode; sandboxed host shell as low-priv
  `Rasputin_sbx`; skills run `--network none` over stdio RPC; THREAT_MODEL §6.2 RESOLVED) — all
  committed. Docs made accurate + the Tailwind+tokens consolidation locked; 5 stale UI docs removed.
- **Decisions locked (don't relitigate):**
  - Rasputin is **first a daily-driver you love, polished to a high bar**; going public is an
    *eventual option*, not the near-term driver.
  - Eventual product = **self-hosted, local open-source models on the customer's own hardware**, for
    teams that can't send data out / want to cut API cost. Repo stays **private**.
  - Styling = **Tailwind v4 + `--ras-*`/`--cc-*` tokens** as the one system; **react-bootstrap is
    legacy, retired incrementally** (canonical: architecture guide §4). shadcn primitives + a
    `@theme inline` bridge already exist (commit `0cbe103`) — adapt, don't rebuild.
  - **Layout may change, but only with a restorable backup** of the prior version; keep the composer pill.
- **Constraints:** verify UI in the running app (verify skill); edit `frontend-src/` then
  `npm run build`, never hand-edit `frontend/`; never bulk-edit source with PowerShell
  Get/Set-Content (UTF-8/BOM) — use Edit/Write or Python; commit only when asked.
- **Then follow the phase sequence below (A1 → F).**

---

**Sub-plans (detail lives here):**
- `docs/UI_UX_PLAN.md` — the UI/UX work (the near-term core).
- `docs/RASPUTIN_ARCHITECTURE_GUIDE.md` §4 — canonical frontend stack + the Tailwind+tokens convention.
- `docs/SAAS_ROADMAP.md` — the business/product direction (the eventual "going public" track).
- `docs/DUAL_MODE_ARCHITECTURE_PLAN.md` + `docs/EXECUTION_PLAN.md` — the security core (done).

---

## The through-line (why the order is what it is)

Rasputin is **first a tool you use every day and want polished to a much higher bar** — so the
daily-driver polish comes first. Turning it into a **self-hosted, local-model product** for
data-sensitive / cost-cutting teams is an **eventual option**, sequenced last. Two hard realities
shape the order:

1. **The app isn't at a working daily-use state yet.** Nothing else matters until that's fixed —
   so a working baseline + honest audit is Phase 0.
2. **You're effectively a solo builder.** So phases are sized to be finishable, and we work in
   **vertical slices** (one area fully done) rather than endless horizontal passes — the first real
   milestone is your most-used surface (chat/task) genuinely good, not "everything at 60%."
3. **This plan is honest about its own uncertainty.** The app has never been launched this session,
   so we don't yet know if "not working" means rough edges or a broken agent loop. **Everything
   past Phase A1 is provisional until A1 (the recon launch) lands** — its depth can't be known
   until we see it run. The *order* is right; the *sizing* of B–F firms up after A1.

---

## Done (starting point, not to redo)

- **Security core — Phases 0–4 complete.** Dual-mode (native + Docker); sandboxed host shell as
  the low-priv `Rasputin_sbx` account (blast radius contained, verified); skills run `--network
  none` over a stdio RPC (THREAT_MODEL §6.2 RESOLVED). All committed.
- **Docs made accurate + Tailwind+tokens consolidation locked** as the convention; 5 stale UI docs
  removed. Committed.
- **Direction decided:** self-hosted, local open-source models, for teams that can't send data out
  / want to cut API cost. Repo stays private.

---

## The executable sequence

Each phase: **goal · key work · depends on · done-when (gate)**. Verify every phase in the running
app (verify skill); back up any layout before changing it; commit per stage.

### Phase A1 — Recon launch + audit  *(bounded — hours, not weeks; do this FIRST)*
- **Goal:** find out what "not working" actually means, and what already exists — replace the
  guesswork below with facts.
- **Work:** launch via the verify skill; drive every core loop (chat/task, workspace + Host Shell,
  models/WarSat, dashboard/settings); **catalog broken / rough / fine**; and **inventory what's
  already built** — the shadcn/ui primitives + the Tailwind `@theme inline` bridge in `theme.css`
  (adopted in commit `0cbe103`), the 11 themes, existing components — so later phases *finish/adapt*
  instead of rebuilding.
- **Depends on:** nothing. **This is the immediate next action — before B–F are treated as committed.**
- **Gate:** a written broken/rough backlog + a primitives/themes inventory. This is what makes the
  rest of the plan real.

### Phase A2 — Fix to daily-usable  *(size unknown until A1 — could be a day or the main event)*
- **Goal:** you can run your real daily workflows end-to-end without hitting a wall.
- **Work:** fix the *blocking* functional issues A1 found. This is where "get it working" lives; its
  scope is whatever A1 reveals (rough edges vs. a broken agent loop — we don't know yet).
- **Depends on:** A1.
- **Gate:** you complete a real end-to-end task in the running app, comfortably.

> ⚠️ **Everything below (B–F) is provisional until A1 lands.** The order holds; the *depth/sizing*
> firms up once we've actually seen the app run.

### Phase B — *Minimal* design-system foundation  *(just enough for the first slice)*
- **Goal:** the shared vocabulary — but only as much as chat/task needs first, adapting what exists.
- **Work:** confirm/finish the token→Tailwind `@theme` bridge; lock a type scale + spacing/radius/
  shadow language; **adapt the existing shadcn primitives** (`Button`, `Card`, `Input`, `Select`,
  `Switch`, `Dialog`, `Toast`, `Skeleton`) to the chosen look — don't rebuild what `0cbe103` already
  added. Enough to build one area well, not a whole catalog up front.
- **Depends on:** A1 (the inventory) + the **theme + target-look decisions** (see Inputs).
- **Gate:** the primitives chat/task needs render in the chosen look, light/dark + first-class themes.

### Phase C — Chat / task vertical slice  *(THE first real milestone)*
- **Goal:** your most-used surface is genuinely usable, polished, and delightful — end to end.
- **Work:** take chat/task fully to the bar: migrate its react-bootstrap to the Phase B primitives,
  apply the visual polish, wire the delight behaviors it needs (toasts, in-button loading, streaming/
  tool-run affordances, transitions), tighten copy, keep the composer pill (layout changes **with a
  backup**). Proves the whole approach on the surface you feel most.
- **Depends on:** B.
- **Gate:** you'd happily use chat/task every day; it feels finished. **First milestone — a real one.**

### Phase D — Generalize to the remaining areas  *(vertical slices, in priority order)*
- **Goal:** extend the validated approach to the rest; retire react-bootstrap as you go.
- **Work, one area at a time:** **② Models & WarSat → ③ Dashboard / settings → ④ everything else.**
  Grow the design system only as each area demands it. Per slice: swap react-bootstrap for the
  primitives, apply polish, wire delight behaviors. (Settings has a token-primitive migration sketch
  in `docs/superpowers/plans/` — reuse it for ③.)
- **Depends on:** C (the pattern proven on chat/task).
- **Gate per slice:** that area matches the design system and feels finished; shipped to your daily use.

### Phase E — Consistency, accessibility & responsive sweep  *(coherence + final cleanup)*
- **Goal:** it holds together as one product, and the styling is truly consolidated.
- **Work:** cross-app consistency audit; a11y (focus states, aria, keyboard, reduced-motion,
  contrast); responsive across breakpoints; empty/loading/error coverage. **Retire the last
  react-bootstrap stragglers and remove Bootstrap's global CSS import.** Note: Bootstrap and Tailwind
  *coexist* through Phases C–D (you hit a Bootstrap `.toast` class collision once), so a
  mid-migration visual glitch is expected, not a regression, until this cleanup.
- **Depends on:** D done for the priority areas.
- **Gate:** clean consistency + a11y + responsive pass; `grep react-bootstrap` effectively empty; the
  Bootstrap CSS import is gone.

### Phase F — The "going public" product track  *(eventual; only after the daily-driver is polished)*
- **Goal:** turn the polished daily-driver into the self-hosted, local-model product.
- **Work (its own detailed planning when we get here — see `SAAS_ROADMAP.md`):** local OSS-model
  serving quality (WarSat routing/quantization/perf), the **self-hosted installer + server SKU**
  (the old "Phase 5" — GHCR image, version/update UI), on-prem **licensing/entitlements**, and
  **security-as-a-product** (a public security page built on the Phase 3/4 sandbox work).
- **Depends on:** a daily-driver you'd actually put in front of someone (Phases A–E).
- **Gate:** "install Rasputin" is one command on a workstation / two lines on a server; a design-
  sensitive customer could run it locally with capable local models.

---

## Inputs still needed (and where they gate)

| Decision | Gates | Default if you don't pick |
|---|---|---|
| Themes: polish all 11, or promote 2–3 to first-class + mark rest experimental | Phase B | Promote 3, mark rest experimental (reads as more finished) |
| Target look / references you love (Claude.ai, Linear, Vercel, Raycast…) | Phase B | I propose a direction in Phase B for your sign-off |
| The one-line product wedge (#5 from the SaaS report) | Phase F (not near-term) | Defer — doesn't block A–E |

Nothing above blocks **Phase A**, which is why we start there regardless.

## How we work (applies to every phase)

- **Verify in the running app** every phase (verify skill; Playwright for interaction proofs) —
  build-green is not enough.
- **Back up any layout before changing it** (restorable prior version); keep the composer pill.
- **Tailwind v4 + tokens** for all new/changed UI; no new react-bootstrap; retire it incrementally.
- **Advisor pressure-test** at each design juncture (design system, per-area approach) and before
  declaring a phase done.
- **Commit per stage** with before/after notes; scratch files to the scratchpad.

## Recommended immediate next step
**Phase A1 — launch the app.** We've done a lot of planning and zero launching; the single
highest-value thing now is to *see it run*. I'll start it via the verify skill, drive your real
workflows, and hand you an honest broken-vs-rough backlog + an inventory of the primitives/themes
that already exist. That turns the rest of this plan from provisional into real. The theme + look
inputs can wait — they gate Phase B, not A1.
