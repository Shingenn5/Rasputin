# Rasputin GUI Upgrade Proposal — Closing the Gap to Claude.ai / Cutting-Edge AI Products

## Where Rasputin stands today

Rasputin's frontend is **functional and coherent but utilitarian**. It has real strengths worth preserving:

- A genuine multi-theme design-token system (11 themes: dark, cyberpunk-neon, ocean-abyss, hacker-matrix, etc.)
- Extensive responsive breakpoint coverage (209 media queries — most hand-rolled apps have far less)
- Designed empty states (not blank screens) via `EmptyCard`/`EmptyInline` patterns
- Semantic HTML basics: skip links, `role="status"`, labeled form inputs, real `<button>`/`<a>` elements
- A clean icon language via `lucide-react`

What it's missing is the **"delight layer"** — the dozen small behaviors that make Claude.ai, Linear, or Vercel's dashboard feel alive rather than static. None of these gaps are about raw feature count; they're about *response to user action*. Below is a prioritized list, grouped by effort and impact.

---

## Tier 1 — High impact, low-to-medium effort (do these first)

### 1. Toast notification system
**Gap:** There is no toast library. All feedback funnels through a single global status bar (bottom-right, one message at a time, auto-dismiss at 5.5s). Two things happening in sequence (e.g. "model imported" then "container starting") will clobber each other.
**Upgrade:** Stacked, dismissible toast queue (success/error/info variants) anchored bottom-right or top-right, each with its own timer, an undo affordance where applicable, and `aria-live="polite"` per toast. This is the single highest-leverage change — almost every async action in the app (deploy, import, save settings, cancel task) currently has nowhere good to report its result.

### 2. Skeleton loading states
**Gap:** Zero skeleton screens exist (confirmed: 0 matches for "skeleton" in the codebase). Loading currently means blank panels or disabled buttons — the model catalog, workspace file browser, and task list all have this problem.
**Upgrade:** Shimmer/pulse skeleton placeholders matching the final layout's shape (card outlines, text-line bars) for: model registry list, task list, workspace file tree, chat history load. This alone makes the app *feel* an order of magnitude faster even with identical network timing — it's the single biggest perceived-performance win available.

### 3. Inline button/action loading states
**Gap:** Buttons that trigger async work (Deploy, Import, Save, Cancel Task) don't appear to show in-button spinners — they just become disabled or nothing visibly changes until the result arrives.
**Upgrade:** Every action button gets a loading variant: icon swaps to a spinner, label optionally changes ("Deploying…"), button stays disabled until resolution. Pair with optimistic UI where safe (e.g. task cancel can show "Cancelling…" immediately).

### 4. Micro-interactions & transitions
**Gap:** State changes are instant — no transition on view switches, list insertions/removals, sidebar collapse easing is the only animation found (`.2s ease`).
**Upgrade:**
- Fade/slide transitions on view changes (150–200ms, respecting `prefers-reduced-motion`, which is already partially handled)
- List item enter/exit animations (task list, model list) — items should animate in/out, not just appear/disappear
- Hover/press states with subtle scale or shadow lift on interactive cards (the WarSat deploy cards, model cards)
- The deploy pipeline stepper (just added) is the perfect candidate for an animated progress fill between steps instead of a static dot-fill

### 5. Command palette (Cmd/Ctrl+K)
**Gap:** Navigation is sidebar-only; there's no fast keyboard-driven way to jump to a view, model, or task. Claude.ai, Linear, Vercel, Raycast all anchor their "feels modern" reputation partly on this single feature.
**Upgrade:** A fuzzy-searchable command palette: jump to any view, search models/tasks/sessions by name, trigger common actions (new chat, deploy model, open settings tab). This is disproportionately high-impact for power-user perception of polish.

### 6. Chat composer polish (HomeView)
**Gap:** HomeView is the primary surface (882 lines) — this is the screen most directly compared to Claude.ai's chat UI.
**Upgrade:**
- Auto-resizing textarea with smooth height animation (not a jump)
- Streaming response with a typing-cursor blink at the tail of in-progress text, not just raw token append
- Stop/regenerate controls that fade in only while relevant
- Markdown code blocks with copy-button-on-hover, syntax highlighting, and a subtle "copied!" confirmation
- Message-level actions on hover (copy, retry, edit) rather than always-visible clutter

---

## Tier 2 — Medium impact, medium effort

### 7. Formalize the design token scale
**Gap:** Typography spans `.78rem` to `1rem` with no documented scale; border-radius is inconsistently 6px/8px/999px; spacing uses ad-hoc values like `.85rem`, `.9rem` interchangeably with no rationale.
**Upgrade:** Define and document an explicit type scale (e.g. 12/13/14/16/18/20/24/32px), spacing scale (4px base unit: 4/8/12/16/24/32/48), and radius scale (4/8/12/16/full) as CSS custom properties. This doesn't require Tailwind — just discipline in the existing variable system — and pays off every time a new component is built.

### 8. Modal/dialog system with real ARIA semantics
**Gap:** No `<dialog>` elements; side panels are custom-positioned divs without `role="dialog"`, `aria-modal`, or focus trapping. Tab order can currently escape an open drawer.
**Upgrade:** A shared `Modal`/`Drawer` primitive component with: focus trap on open, focus restoration on close, `Escape` to dismiss, `role="dialog" aria-modal="true"`, and a consistent backdrop/animation. Every existing side-panel (TaskDetailsDrawer, mode-side-panel, model-side-panel) should be rebuilt on top of this one primitive instead of each hand-rolling its own positioning.

### 9. Progressive disclosure for dense panels
**Gap:** WorkspacesView (3-column dense layout) and the WarSat deploy form present everything at once.
**Upgrade:** Collapse advanced/rare options behind "Advanced settings" disclosure by default; use staged reveal (form step 1 → step 2) for genuinely multi-stage flows like deployment, mirroring how Claude.ai's settings hide complexity until asked for.

### 10. Avatar / identity layer
**Gap:** No avatars anywhere — not for the user, not for agent "personas," not for different models in multi-agent lanes.
**Upgrade:** Lightweight generated avatars (initials-on-gradient, or a small icon per model provider — OpenAI/Anthropic/Ollama/local) in chat messages and the agent-lane tabs in HomeView. This is a cheap way to add visual distinction between "who said what" in multi-agent conversations, which is one of Rasputin's actual differentiators over plain chat UIs.

### 11. Status communicated beyond color
**Gap:** Audit notes status dots (green=safe, red=danger) rely on color alone in places.
**Upgrade:** Pair every status color with an icon or text label (already partially done via badges like "localhost only" / "review binding" — extend this pattern everywhere status is shown, e.g. container health, approval state).

---

## Tier 3 — Higher effort, strategic bets

### 12. Real-time collaborative feel for multi-agent lanes
Rasputin's agent-lane tabs (parallel reasoning) are a genuine differentiator versus Claude.ai's single-thread chat. Leaning into this with side-by-side animated lane updates, lane-to-lane "handoff" visual cues, and a live activity indicator per lane (similar to typing indicators) would make this *feel* ahead of the competition rather than just functionally ahead.

### 13. Onboarding / first-run experience
**Gap:** No evidence of a guided first-run flow — a new user lands on a dense sidebar with 13+ views immediately.
**Upgrade:** A minimal first-run flow: detect no models registered → guide to WarSat discovery or model registry in 2–3 steps, with the rest of the UI dimmed/de-emphasized until the first model is live. Cutting-edge AI tools (Claude, Cursor, Linear) all invest here because day-one experience disproportionately drives retention.

### 14. Visual hierarchy via depth, not just borders
The CSS already has a 4-layer panel depth system (`--ras-bg/canvas/panel/panel-2`) — push further with consistent elevation (subtle shadows tied to z-depth, not just background swaps) so cards, drawers, and modals read at a glance as "floating above" their context, the way Claude.ai's modals and Linear's panels do.

### 15. Accessibility hardening
Add `aria-expanded` to all collapsibles, `aria-current="page"` to the active nav item, focus trapping (ties into #8), and audit the `--ras-muted` color (~5.5:1 contrast — borderline AA) against all theme variants, not just the default.

---

## Suggested sequencing

If executing incrementally (recommended given the codebase size — 31 JSX files, 12,000-line CSS):

1. **Foundation pass:** toast system + skeleton primitive + button loading states + design token formalization (#1, #2, #3, #7) — these are infrastructure other upgrades depend on.
2. **Chat surface pass:** HomeView composer polish + avatars + micro-interactions (#6, #10, #4) — highest visibility screen.
3. **Structural pass:** modal/dialog primitive + WarSat/Workspaces progressive disclosure (#8, #9) — reduces density on the most complex screens.
4. **Power-user pass:** command palette (#5).
5. **Strategic bets:** multi-agent lane polish, onboarding flow, elevation system, accessibility hardening (#11–15) — done opportunistically or in a dedicated follow-up phase.

None of the above requires abandoning the current CSS-variable/theme architecture. Every item can be built in vanilla CSS exactly as the project's existing conventions specify — the gap to "cutting edge" is about *interaction design and motion*, not about which styling framework writes the rules.
