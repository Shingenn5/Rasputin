# Rasputin UI/UX Plan — to a daily-driver you love

*2026-07-12. The single source of truth for the UI/UX push. It consolidates and replaces the
five fragmented prior UI docs (since removed — they contradicted each other and the real stack)
and reconciles them into one plan. For the authoritative frontend stack, see
`docs/RASPUTIN_ARCHITECTURE_GUIDE.md` §4. Plan first, per your ask; nothing is implemented yet.*

## What we're actually building for

- **Primary goal:** a tool **you personally use every day and love** — polished to a completely
  different level than today. Going public / self-hosted SaaS is an *eventual option*
  (`saas-product-direction`), **not** the near-term driver, so we do **not** spend effort on
  multi-tenancy/billing here — we spend it on daily-driver quality.
- **The bar:** Claude.ai / Linear / Vercel-grade — the "delight layer" (how the app responds to
  every action) plus a real visual-polish jump.
- **Where you live day-to-day** (polish these first): **Chat / task execution**, **Models &
  WarSat**, and the **Dashboard / settings / surrounding surfaces**.

## Guiding decisions (reconciling the old docs)

1. **Not a bottom-up rebuild.** A prior (now-removed) redesign plan floated rebuilding the frontend
   on Bootstrap from scratch. We reject that: it throws away real strengths (an 11-theme `--ras-*`/`--cc-*`
   token system, broad responsive coverage, designed empty states) and risks months of churn. We
   **elevate in place**, not rebuild.
2. **Consolidate the styling, don't add a fourth system.** The real stack (verified in
   `package.json` / `vite.config.mjs`, canonical in the architecture guide §4) is a **three-layer
   hybrid**: Tailwind v4 (wired + used), React-Bootstrap/Bootstrap 5, and the `--ras-*`/`--cc-*`
   token system. Older docs claiming "no Tailwind / vanilla CSS only" are stale. The polish work's
   job here is to **rationalize toward a primary system — Tailwind v4 + the tokens exposed as CSS
   variables Tailwind reads — retiring ad-hoc Bootstrap where it fights the look**, not to keep all
   three fighting. framer-motion is already available for the motion work.
3. **Layout may change — but only with a restorable backup first.** New rule
   (`chat-layout-preference`, updated 2026-07-12): structural changes are allowed *if* the prior
   version is backed up (a `-legacy` file / an isolated git commit of the prior state) so it can be
   restored. Default is still upgrade-components-in-place; keep the composer pill.
4. **Working before beautiful.** You said the app isn't yet at a point you can use daily. So Phase 0
   is a real live audit + get-it-working baseline. Polish on top of a broken flow is wasted.
5. **Verify in the running app, every phase.** Use the `verify` skill (isolated
   `RASPUTIN_DATA_DIR`, Playwright) — no UI change is "done" until it's confirmed in the real app.

---

## Phase 0 — Working baseline + honest live audit  *(do first)*

The foundation. Until this is done, everything below is provisional.

- **Launch the app** (verify skill) and drive the core daily loops end-to-end: start a chat/task,
  run a code task, browse a workspace, enable Host Shell, deploy/inspect a model in WarSat, open the
  dashboard/settings.
- **Catalog reality** into three buckets: *broken* (blocks daily use), *rough* (works but feels
  prototype), *fine*. This becomes the concrete backlog that grounds Phases 1–4 — replacing the old
  docs' assumptions with what's actually true now.
- **Fix the blocking-functional issues** so the app is genuinely daily-usable for you.
- **Deliverable:** a defect + polish inventory, and an app you can actually run a real task in.
- **Gate:** you complete a real end-to-end task in the running app without hitting a wall.

## Phase 1 — The delight layer  *(highest perceived-quality-per-effort)*

The dozen behaviors that separate "prototype" from "product." Confirm in Phase 0 what already landed
(memory says a "Tier 1" pass was partly done) vs what's missing.

- **Toast system** — stacked, dismissible, per-toast timers, success/error/info, `aria-live`.
  Replaces the single clobbering status bar. Highest-leverage single change.
- **Skeleton loading states** — shimmer placeholders shaped like the final content (model catalog,
  task list, file tree, chat history). Biggest *perceived*-speed win available.
- **In-button loading states** — every async action (deploy, import, save, cancel, run) gets a
  spinner/label swap and stays disabled to resolution; optimistic where safe.
- **Micro-interactions** — view/list enter-exit transitions, hover/press lift on cards, animated
  deploy stepper. 150–200ms, `prefers-reduced-motion` respected.
- **⌘K command palette** — fast keyboard nav to any view/model/task. The signature "feels modern"
  feature.
- **Gate:** each behavior verified live across the three priority areas.

## Phase 2 — Visual polish pass  *(the aesthetic jump)*

Elevate the look itself, component-by-component, in place (layout changes only with a backup).

- **Typography** — a deliberate type scale, weight/tracking discipline, readable measure; make text
  hierarchy carry the page.
- **Spacing & rhythm** — consistent spacing scale; fix cramped/loose areas; let layout breathe.
- **Color & tokens** — refine the neutral/accent tokens so surfaces, borders, and states read as
  *chosen*, not default; audit all 11 themes for contrast + polish (or narrow to a few first-class
  themes and mark the rest "experimental").
- **Surfaces & components** — cards, panels, inputs, chips, menus, tables to a finished bar; unify
  radius/shadow/border language.
- **Gate:** a before/after on the priority areas that reads as a clear tier jump.

## Phase 3 — Per-area deep polish  *(your daily surfaces)*

Each priority area gets a focused pass to a finished-product feel. Order by where you live:

- **Chat / task execution** — the composer pill stays; upgrade chips/menus/indicators, streaming
  and tool-run affordances, task progress, run history. *(Layout tweaks allowed with a backup.)*
- **Models & WarSat** — model registry, deploy pipeline/stepper, health, orchestration views — make
  the local-model story (your product's core) feel first-class.
- **Dashboard / settings / everything else** — dashboard information design, settings clarity,
  knowledge/RAG, audit, runtime.
- **Gate:** each area individually feels finished, not prototype.

## Phase 4 — Consistency, accessibility & responsive sweep

The final 10% that makes it cohere.

- Cross-app consistency audit (same component = same behavior/look everywhere).
- Accessibility: visible focus states, `aria` correctness, keyboard paths, reduced-motion,
  color-contrast — building on the existing semantic-HTML base.
- Responsive check across breakpoints; full empty/loading/error-state coverage.
- **Gate:** a clean pass on a consistency + a11y + responsive checklist.

---

## How we'll work (quality bar)

- **Verify each phase in the running app** (verify skill); Playwright for interaction proofs.
- **Back up before any layout change** (prior version restorable); keep the composer pill.
- **Vanilla CSS + tokens**; no new heavy dependencies without a decision.
- **Respect `prefers-reduced-motion`**; every interactive element gets a visible focus state.
- **Frontend build discipline:** edit `frontend-src/`, `npm run build`, verify the built bundle;
  never hand-edit `frontend/`.
- **Commit per stage** with before/after notes.

## Open decisions for you (before I start building)

1. **Styling consolidation target** — I recommend **Tailwind v4 + the `--ras-*`/`--cc-*` tokens as
   the primary system**, progressively retiring ad-hoc react-bootstrap where it fights the look
   (keep it where its components are pulling weight). Confirm, or say if you'd rather stay a hybrid.
2. **Themes** — polish all 11, or promote 2–3 to first-class and mark the rest experimental? (Fewer,
   better themes usually reads as more finished.)
3. **Start point** — I recommend **Phase 0 (live audit + get-it-working)** first, since you can't
   use it daily yet. Confirm, or tell me a specific area to attack first.
4. **The "look" you want** — any references you love (Claude.ai, Linear, Vercel, Raycast, something
   else)? A target aesthetic sharpens Phase 2.

Answer these and I'll start at Phase 0 — launch the app, give you the honest audit, and we go from there.
