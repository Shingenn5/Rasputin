# Rasputin UI — Full Suite Plan

**Goal:** take the GUI from "Tier 1 foundation landed" to a complete, cutting-edge suite comparable to Claude.ai / Linear / Vercel — without abandoning the vanilla-CSS + `--ras-*`/`--cc-*` token architecture.

**Branch:** `claude-branch`
**Companion docs:** [ui-upgrade-proposal.md](ui-upgrade-proposal.md) (the "what/why"), [ui-upgrade-implementation-plan.md](ui-upgrade-implementation-plan.md) (Tier 1 detail).

---

## Status so far (already landed on `claude-branch`)

| Item | State |
|------|-------|
| Design token scales (spacing/radius/type/elevation/motion) | ✅ `837e0f1` |
| Toast system + `globalStatus` bridge | ✅ `a62c668` |
| Skeleton loaders (`Skeleton*`, applied to Models + TaskDetails) | ✅ `896cba2` |
| Button loading-state component + `:disabled` treatment | ✅ `7023960` |

**Foundation primitives now available to build on:** `useToast()`, `<Skeleton*>`, `<Button>`, plus the token scales. Everything below leans on these.

---

## Working principles (apply to every phase)

1. **Additive-first.** New shared components/CSS; touch existing wiring minimally and reversibly. This is what kept Tier 1 low-risk.
2. **Verify in-browser, not just build.** The Bootstrap `.toast` collision proved build-green ≠ correct. Every phase ends with a dev-server render check + screenshot.
3. **One concern per commit**, each independently building and verified.
4. **Namespace new classes** (`.ras-*`) to avoid Bootstrap collisions.
5. **Respect `prefers-reduced-motion`** on every animation (the app already has a global block to extend).
6. **No backend changes** unless a phase explicitly calls for one (none currently do).

---

## Phase 1 — Motion & view transitions (proposal #4)

**Why first:** highest perceived-polish-per-effort; instant state changes are the single most "utilitarian" tell today. View switching is a bare `setView` ([App.jsx:598](../frontend-src/src/app/App.jsx#L598)) with no transition.

- **View crossfade/slide:** wrap the routed view container so changing `view` animates (fade + small translateY, ~180ms via `--dur`/`--ease`). Keep it CSS-driven (data-attribute or key-based remount) to avoid a heavy animation lib.
- **List enter/exit:** task list, model list, toast queue (toasts already animate in — add exit). Items animate in/out rather than popping.
- **Interactive feedback:** hover lift (shadow/scale) on cards (`w2-card`, model/warsat cards); active/press states; focus-ring consistency using `--ras-focus`.
- **Pipeline stepper:** animate the WarSat deploy stepper's progress fill between steps instead of static dot-fill.
- **Decision point:** pure CSS transitions vs. adding `framer-motion`. Recommendation: **CSS-first**; only pull in a lib if list reordering/shared-element transitions demand it (revisit in Phase 6).

**Verify:** switch views, add/remove a task, hover cards — confirm smooth, reduced-motion honored.

---

## Phase 2 — Command palette (proposal #5)

**Why:** disproportionate "modern" signal; the app has 13+ views reachable only via sidebar.

- New `CommandPalette.jsx` (Cmd/Ctrl+K), fuzzy search over: **views** (from the existing route table), **models** (registry), **tasks/sessions** (by name), and **actions** (new chat, deploy, scan for models, open a settings tab).
- Built on a new shared `Modal` primitive (see Phase 3) — focus trap, `Escape`, backdrop.
- Keyboard-first: arrow nav, Enter to execute, recent/most-used at top.
- Wire into the existing `go(view, section)` navigation and action handlers in App.jsx.

**Verify:** Cmd+K opens, fuzzy-jump to a view and a settings sub-tab, run an action, Escape closes, focus restores.

---

## Phase 3 — Modal/dialog & drawer primitive (proposal #8)

**Why:** Phase 2 needs it, and today's side panels (TaskDetailsDrawer, mode/model side-panels) are hand-positioned divs without `role="dialog"`, `aria-modal`, or focus trapping (tab can escape them).

- New `Modal.jsx` + `Drawer.jsx` primitives: focus trap on open, focus restoration on close, `Escape` to dismiss, `role="dialog" aria-modal="true"`, consistent backdrop + enter/exit animation (Phase 1 tokens).
- **Migrate existing panels onto it** one at a time: TaskDetailsDrawer first (already drawer-shaped), then the mode/model side-panels. Each migration is its own verified commit.

**Verify:** open each migrated panel — focus trapped, Escape works, focus returns to trigger, screen-reader landmarks correct.

---

## Phase 4 — Chat surface polish (proposal #6) — the marquee screen

**Why:** HomeView is what users directly compare to Claude.ai. Today the composer is a fixed `rows={3}` textarea ([HomeView.jsx:380](../frontend-src/src/features/chat/HomeView.jsx#L380)) with Enter-to-send but no growth/streaming polish.

- **Composer:** auto-resizing textarea (smooth height, min/max bounds), send disabled-when-empty, attachment chips refined, `Button` loading state on send.
- **Streaming:** typing-cursor blink at the tail of in-progress assistant text; Stop/Regenerate controls that fade in only while streaming.
- **Messages:** hover actions (copy / retry / edit) instead of always-visible; code blocks get copy-on-hover + a "copied!" toast (reuse `useToast`); syntax highlighting.
- **Avatars (proposal #10):** initials-on-gradient for the user; per-provider icon (Anthropic/OpenAI/Ollama/local) for models, especially in the multi-agent lanes — Rasputin's real differentiator.

**Verify:** type a long message (grows), send (loading), stream a response (cursor + stop), copy a code block (toast), check avatars in a multi-agent run.

---

## Phase 5 — Apply the foundation everywhere (consistency sweep)

**Why:** Tier 1 primitives were applied to representative spots only; the rest of the app still has bespoke loading/empty/feedback. This is the "full suite" connective tissue.

- **Skeletons:** WorkspacesView file browser, ArchiveView session list, TrialsView results, RuntimeViews lists, WarSat discovery.
- **`<Button>` loading:** sweep remaining async buttons (Workspaces actions, Settings saves, Trials run, Archive export). Fold WarSat's bespoke `ws-spin` buttons onto the shared component for consistency.
- **Explicit toast variants:** upgrade the highest-value `setGlobalStatus` sites from the info-bridge to explicit `toast.success`/`toast.error` (deploy, import, save, task actions) so success/error read distinctly. Then retire the legacy bottom status bar fully.
- **Status-beyond-color (proposal #11):** ensure every color-coded status (container health, approval state, model health) carries an icon/text label too.

**Verify:** spot-check each view's loading + a representative action; confirm no remaining bare "Loading…" text or color-only status.

---

## Phase 6 — Visual system hardening

- **Elevation/depth (proposal #14):** apply consistent `--elev-*` shadows tied to z-depth so cards/drawers/modals read as layered, not just background-swapped.
- **Token sweep (proposal #7 follow-through):** opportunistically replace ad-hoc inline `style={{fontSize/padding/radius}}` with the formal scales in the files already being touched (not a standalone mass rewrite — fold into other phases' edits).
- **Empty-state personality (proposal #4/illustrations):** upgrade the well-structured-but-plain empty states with a small icon/illustration + a clear primary action (e.g. "No models → Discover" CTA).
- **Reconsider `framer-motion`** here if Phase 1's CSS approach hit limits.

**Verify:** visual pass across all 13 views in 2–3 themes (default, a dark theme, a Bootswatch theme) for consistent depth/spacing/empty states.

---

## Phase 7 — Onboarding / first-run (proposal #13)

**Why:** a new user lands on a dense 13-view sidebar with no guidance.

- Detect "no models registered" → a focused first-run flow (2–3 steps) guiding to WarSat discovery or model registry, with the rest of the UI de-emphasized until the first model is live.
- Reuse Modal/Button/Toast primitives; no new infra.

**Verify:** simulate empty registry → guided flow appears, completes, dismisses; returning users never see it.

---

## Phase 8 — Accessibility & responsive hardening (proposal #15)

**Why:** part of "polished and usable"; some gaps block real users.

- `aria-expanded` on all collapsibles; `aria-current="page"` on the active nav item; focus management audited (ties into Phase 3).
- Contrast audit of `--ras-muted` (~5.5:1, borderline AA) across **all** themes, not just default; fix per-theme.
- `prefers-contrast` / high-contrast support.
- Responsive re-check of the new components (palette, modals, composer) at the existing breakpoints (760px mobile, etc.).
- Optional: a Playwright a11y/visual smoke pass (the repo already has `@playwright/test`).

**Verify:** keyboard-only walkthrough of core flows; axe/contrast check; mobile-width pass.

---

## Suggested sequencing & checkpoints

```
Phase 1 (motion) ─┐
Phase 3 (modal)  ─┴─► Phase 2 (palette)        ◄ checkpoint A: "feels modern"
Phase 4 (chat)                                  ◄ checkpoint B: marquee screen
Phase 5 (consistency sweep)                     ◄ checkpoint C: "full suite"
Phase 6 (visual hardening)
Phase 7 (onboarding)
Phase 8 (a11y/responsive)                       ◄ checkpoint D: ship-ready
```

- **Phase 3 lands before Phase 2** in practice (palette depends on the modal primitive) even though motion (Phase 1) is the natural opener.
- **Check in at each checkpoint (A–D)** for review before proceeding, mirroring how Tier 1 ran.
- Each phase = multiple small verified commits; no phase is a single mega-commit.

## Scope & risk notes

- **Effort:** this is multi-session. Phases 1–4 deliver the bulk of the visible "cutting edge" jump; 5–8 are the polish/completeness tail.
- **Biggest risk areas:** Phase 3 migrations (touching existing panels) and Phase 4 streaming (touching the live chat path) — both done incrementally, one panel/behavior per commit, verified in-browser.
- **Library decision** (`framer-motion`) is deliberately deferred to where it's justified (Phase 1 evaluate, Phase 6 revisit) rather than adopted up front.
- **No documented-rule reversal:** stays on vanilla CSS + tokens throughout; no Tailwind.
