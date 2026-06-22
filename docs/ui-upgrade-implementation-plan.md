# UI Upgrade — Implementation Plan (Tier 1 Foundation Pass)

**Branch:** `claude-branch` (already created from `antigravity-branch`)
**Styling approach:** Vanilla CSS + existing `--ras-*` / `--cc-*` token system. **No Tailwind.** (Decision recorded after evaluating tradeoffs — Tailwind reverses a documented architecture rule for no functional gain on these specific upgrades.)
**Source of truth:** [docs/ui-upgrade-proposal.md](ui-upgrade-proposal.md)

This plan covers **Tier 1 only** (items #1, #2, #3, #7 from the proposal). Tiers 2–3 are deliberately out of scope for this pass and will be planned separately once the foundation lands.

---

## Why this ordering

Reading the codebase confirmed the foundation is the right place to start:

- **`setGlobalStatus` is called ~70 times across 8 files** ([App.jsx](../frontend-src/src/app/App.jsx) alone has ~65), and it's the app's *only* feedback channel. It shows one message at a time in a single bottom bar (auto-clears at 5.5s — [App.jsx:220-224](../frontend-src/src/app/App.jsx#L220)), with no success/error distinction except the string contents. Sequential actions clobber each other. **A toast system replacing this is the highest-leverage single change and everything else benefits from it.**
- **Zero skeleton loaders exist** and async buttons don't show in-progress state. These are pure-additive (nothing removed) and low regression risk.
- **Design tokens are ad-hoc** (type spans `.78rem`–`1rem`, radius is 6/8/999px, spacing is `.75/.85/.9/1rem` with no scale). Formalizing these *first* means the toast/skeleton components are built on the real scale rather than perpetuating the ad-hoc values.

So the build order is: **tokens → toast → skeleton → button loading**, because each later step consumes the earlier one.

---

## Step 0 — Verify clean baseline (no code change)

- `git status` clean on `claude-branch`; confirm `npm run build` is green before touching anything (so any later breakage is attributable).
- Capture 2–3 "before" screenshots (HomeView, ModelsView, a loading state) for visual regression reference.

**Verify:** build passes, branch clean.

---

## Step 1 — Formalize design tokens (#7)

**File:** [frontend-src/src/styles/rasputin.css](../frontend-src/src/styles/rasputin.css) (`:root` block, currently lines 1–50)

Add **new** token scales alongside the existing `--ras-*` vars (additive — do not rename or remove existing tokens, since 12k lines of CSS reference them):

- **Spacing** (4px base): `--sp-1: 4px` … `--sp-12: 48px` (1,2,3,4,6,8,12 → 4,8,12,16,24,32,48)
- **Radius:** `--radius-sm: 6px`, `--radius: 8px`, `--radius-lg: 12px`, `--radius-xl: 16px`, `--radius-pill: 999px`
- **Type scale:** `--fs-xs: 0.75rem` … `--fs-2xl: 1.5rem` (12/13/14/16/18/20/24)
- **Elevation:** `--elev-1`, `--elev-2`, `--elev-3` (reuse/extend existing `--ras-shadow`)
- **Motion:** `--dur-fast: 120ms`, `--dur: 180ms`, `--dur-slow: 260ms`, `--ease: cubic-bezier(.2,.8,.2,1)`

**Scope guard:** This step **adds** variables only. It does **not** sweep the codebase to replace existing ad-hoc values — that's a Tier 2 cleanup. New components (Steps 2–4) use these tokens; existing CSS is left untouched.

**Verify:** `npm run build` green; no visual change expected (nothing consumes the new vars yet).

---

## Step 2 — Toast notification system (#1)

**New files:**
- `frontend-src/src/components/Toast.jsx` — `<ToastProvider>` (context + queue state) + `<ToastViewport>` (renders the stack) + `useToast()` hook exposing `toast.success(msg)`, `toast.error(msg)`, `toast.info(msg)`.
- CSS for toasts added to `rasputin.css` (new section, using Step-1 tokens), variants keyed off theme vars (`--ras-safe`, `--ras-danger`, `--ras-blue`).

**Behavior:**
- Stacked, individually-timed (success ~4s, error sticky until dismissed), dismissible, max ~4 visible with overflow collapse.
- Each toast `role="status"` / `aria-live="polite"` (errors `aria-live="assertive"`), `Escape`/click to dismiss, respects `prefers-reduced-motion` (already handled globally at rasputin.css:9721).
- Enter/exit animation via Step-1 motion tokens.

**Wiring (incremental — this is the careful part):**
1. Mount `<ToastProvider>` at the App root and `<ToastViewport>` in [AppShell.jsx](../frontend-src/src/components/AppShell.jsx).
2. **Keep `globalStatus` working.** Bridge it: the existing `setGlobalStatus(msg)` continues to function, but route it through a toast (info variant) so all ~70 existing call sites light up immediately with zero per-site edits. The legacy bottom bar can stay or be removed once the bridge is verified.
3. **Then** opportunistically upgrade the highest-value call sites to use `toast.success`/`toast.error` explicitly (deploy flow, model import, task actions) where the success/error distinction matters — but this is gravy, not required for the step to be "done."

**Why the bridge:** editing 70 call sites by hand is exactly the high-risk churn we want to avoid. The bridge gets the visible win (stacked, themed, non-clobbering toasts) for a ~5-line change, and explicit upgrades happen gradually.

**Verify:** trigger several actions in quick succession (e.g. refresh + deploy) and confirm they stack instead of overwriting; build green; screenshot.

---

## Step 3 — Skeleton loading primitive (#2)

**New file:** `frontend-src/src/components/Skeleton.jsx` — `<Skeleton>` (configurable w/h/radius), `<SkeletonText lines={n}>`, `<SkeletonCard>`. Shimmer animation via a CSS keyframe (new section in rasputin.css, motion-token driven, `prefers-reduced-motion` → static dimmed block).

**Apply to 3 representative loading states** (proof-of-pattern, not exhaustive):
- Model registry list ([ModelsView.jsx](../frontend-src/src/features/models/ModelsView.jsx)) — uses `modelCatalogLoading` already in App state.
- Task list ([TasksView.jsx](../frontend-src/src/features/tasks/TasksView.jsx)).
- Task details drawer ([TaskDetailsDrawer.jsx](../frontend-src/src/features/tasks/TaskDetailsDrawer.jsx)) — already receives a `loading` prop.

**Scope guard:** Wire these 3; leave a documented pattern so remaining views adopt it later. Not every loading state in the app gets converted in this pass.

**Verify:** throttle network / simulate load, confirm skeletons render with correct shape and swap cleanly to content; build green.

---

## Step 4 — Inline button loading states (#3)

**New file:** `frontend-src/src/components/Button.jsx` — a thin wrapper over the existing `.w2-button`/button classes adding a `loading` prop (swaps leading icon → spinner, disables, optional `loadingLabel`). Spinner is a small CSS-animated element or `lucide-react`'s `Loader2` with a spin class.

**Apply to the async actions most visible to users:**
- WarSat: Deploy / Generate Plan / Scan for Models ([WarsatView.jsx](../frontend-src/src/features/warsat/WarsatView.jsx)).
- Models: Import / Test health / Connect ([ModelsView.jsx](../frontend-src/src/features/models/ModelsView.jsx)).
- Task actions: Cancel / Pause / Resume.

**Scope guard:** Introduce the component and convert the above high-traffic buttons. A full sweep of every button is explicitly *not* in this pass — the component exists so future work is a one-line swap.

**Verify:** click each converted action, confirm spinner + disabled-during-flight + restore-on-complete; build green.

---

## Step 5 — Documentation + close-out

- Update [docs/ui-upgrade-proposal.md](ui-upgrade-proposal.md): mark Tier 1 items #1/#2/#3/#7 as "foundation landed," note the bridge strategy for `globalStatus`.
- Update the architecture/context doc's CSS rule note: clarify that vanilla-CSS-with-tokens remains the approach (no Tailwind), and point to the new token scales + shared components (`Toast`, `Skeleton`, `Button`) as the canonical building blocks going forward.
- Final `npm run build`, capture "after" screenshots, commit each step as its own commit (token / toast / skeleton / button / docs) so the history is reviewable and bisectable.

---

## Out of scope for this pass (tracked for later)

- Micro-interactions / view transitions (#4), command palette (#5), chat composer polish (#6) — Tier 1 but larger; planned next.
- All of Tier 2/3 (modal primitive, progressive disclosure, avatars, onboarding, a11y hardening, elevation system).
- Sweeping the ~70 `setGlobalStatus` call sites or replacing ad-hoc CSS values app-wide — intentionally deferred; the bridge + new-components-only approach keeps this pass low-risk.

## Risk notes

- **Lowest-risk possible ordering:** every step is additive (new components, new tokens). The only edit to existing wiring is mounting the provider and bridging `globalStatus` — one file, reversible.
- Each step builds + visually verifies before the next, and lands as its own commit, so any regression is isolated and bisectable.
- No backend changes. No dependency additions required (spinner/shimmer are CSS; `lucide-react` already present if we want `Loader2`).
