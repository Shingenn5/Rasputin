# Rasputin — Master Execution Roadmap

*2026-07-12. The single top-level "what we do next, and in what order" doc. It sequences
everything discussed this session into a doable order and points to the detailed sub-plans
rather than duplicating them. Where this conflicts with a sub-plan's internal ordering, **this
roadmap wins on order.***

## Status — read this first (cold-start handoff)

**As of 2026-07-13.** Written so this plan survives a fresh session with zero chat context.

- **Current work:** the GUI redesign is in progress on `codex/gui-redesign`. It is applying the
  Phase-B design vocabulary and the first Phase-C chat/task slice across the existing components.
  The working tree is modified but **not committed, released, or verified complete yet**; finish
  build + isolated running-app desktop/mobile/keyboard/mouse QA before calling this pass done.
- **Done (don't redo):**
  - Phase A1 recon/audit completed in the running app (`docs/PHASE_A1_FINDINGS.md`).
  - Phase A2's real-local-model blocker was found and fixed: conversational fallback works, a
    parser-configured Qwen/vLLM deployment completed a genuine tool-calling task, and tool-less
    execution now fails visibly instead of reporting a silent success.
  - Security core Phases 0–4 are complete (dual-mode; native-Windows Host Shell as low-priv
    `Rasputin_sbx`; Skills run `--network none` over stdio RPC; THREAT_MODEL §6.2 RESOLVED).
  - Tailwind+tokens is the locked styling convention; the security/dual-mode docs are current.
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
- **Continue from B/C below, then D → E → F.** Phase 5 packaging remains open inside the eventual
  Phase-F product track; it is not part of the current uncommitted GUI pass.

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

1. **The functional baseline is now proven.** A1 launched and audited the app; A2 found the real
   vLLM/tool-parser failure and closed it with live local-model and genuine tool-calling proof.
   Remaining near-term work is product-quality GUI/UX, not an unscoped broken agent loop.
2. **You're effectively a solo builder.** So phases are sized to be finishable, and we work in
   **vertical slices** (one area fully done) rather than endless horizontal passes — the first real
   milestone is your most-used surface (chat/task) genuinely good, not "everything at 60%."
3. **The uncertainty is now bounded by evidence.** A1's written audit and A2's real-model tests are
   the baseline. B–E can be sized from observed UI debt; Phase F stays intentionally deferred until
   the daily-driver experience is polished.

---

## Done (starting point, not to redo)

- **Security core — Phases 0–4 complete.** Dual-mode (native + Docker); sandboxed host shell as
  the low-priv `Rasputin_sbx` account (blast radius contained, verified); skills run `--network
  none` over a stdio RPC (THREAT_MODEL §6.2 RESOLVED). All committed.
- **Phase A1 complete.** Isolated running-app audit covered 15+ views, light/dark, auth, routing,
  chat/task, workspaces, models, and the existing primitive/theme inventory. Findings are recorded
  in `docs/PHASE_A1_FINDINGS.md`.
- **Phase A2 functional gate complete.** Real vLLM chat works; the tool parser is opt-in per deploy;
  Qwen2.5 completed a real agentic tool call; execution without tool support fails visibly. Small
  cosmetic cleanups found by A1 are folded into B–E rather than treated as functional blockers.
- **Docs made accurate + Tailwind+tokens consolidation locked** as the convention; 5 stale UI docs
  removed. Committed.
- **Direction decided:** self-hosted, local open-source models, for teams that can't send data out
  / want to cut API cost. Repo stays private.

---

## The executable sequence

Each phase: **goal · key work · depends on · done-when (gate)**. Verify every phase in the running
app (verify skill); back up any layout before changing it; commit per stage.

### Phase A1 — Recon launch + audit  ✅ COMPLETE (2026-07-12)
- **Outcome:** isolated running-app audit + broken/rough/fine backlog + primitives/themes inventory.
  See `docs/PHASE_A1_FINDINGS.md`; do not repeat this recon unless the baseline materially changes.

### Phase A2 — Fix to daily-usable  ✅ FUNCTIONAL GATE COMPLETE (2026-07-13)
- **Outcome:** the real local-model 400 was traced to tool advertisement/parser mismatch and fixed
  without imposing a model-incompatible global parser. Real chat and genuine tool-calling execution
  were verified; unsupported-tool execution now fails visibly. Remaining visual cleanups belong to
  B–E.

### Phase B — *Minimal* design-system foundation  🚧 IN PROGRESS
- **Goal:** the shared vocabulary — but only as much as chat/task needs first, adapting what exists.
- **Work:** confirm/finish the token→Tailwind `@theme` bridge; lock a type scale + spacing/radius/
  shadow language; **adapt the existing shadcn primitives** (`Button`, `Card`, `Input`, `Select`,
  `Switch`, `Dialog`, `Toast`, `Skeleton`) to the chosen look — don't rebuild what `0cbe103` already
  added. Enough to build one area well, not a whole catalog up front.
- **Depends on:** A1 (the inventory) + the **theme + target-look decisions** (see Inputs).
- **Gate:** the primitives chat/task needs render in the chosen look, light/dark + first-class themes.

### Phase C — Chat / task vertical slice  🚧 IN PROGRESS (uncommitted GUI branch)
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
| Target look / references you love (Claude.ai, Linear, Vercel, Raycast…) | Phase B | Elliott delegated the current pass to Codex's taste; judge it in running-app review before commit |
| The one-line product wedge (#5 from the SaaS report) | Phase F (not near-term) | Defer — doesn't block A–E |

These inputs do not block finishing the current GUI prototype and presenting it for running-app
review. They can still change the direction before the branch is committed.

## How we work (applies to every phase)

- **Verify in the running app** every phase (verify skill; Playwright for interaction proofs) —
  build-green is not enough.
- **Back up any layout before changing it** (restorable prior version); keep the composer pill.
- **Tailwind v4 + tokens** for all new/changed UI; no new react-bootstrap; retire it incrementally.
- **Advisor pressure-test** at each design juncture (design system, per-area approach) and before
  declaring a phase done.
- **Commit per stage** with before/after notes; scratch files to the scratchpad.

## Recommended immediate next step
Finish the **uncommitted `codex/gui-redesign` B/C pass**, run `npm run build`, and verify it in an
isolated running instance across desktop/mobile plus keyboard-only and mouse-only paths. Present the
result for review before committing. After B/C is accepted, continue the remaining areas in D, then
the consistency/a11y sweep in E. Keep Phase-5 packaging inside F until the daily-driver GUI is
finished.
