# Rasputin UI Repair Plan

## Why This Exists

The current UI works, but it does not feel like a finished product. The biggest issue is not one broken button or one bad color. The interface still feels like a prototype dashboard:

- The sidebar is mostly icon-only, so navigation depends on tooltips and guessing.
- The default palette feels muted and uncertain instead of intentional.
- The settings modal is overloaded and visually noisy.
- The main chat view mixes conversation, task metadata, model health, workspace state, and activity in ways that make the product feel unfinished.
- Many controls are technically present, but they do not yet feel grouped into obvious workflows.

The target is a local AI workbench that feels closer to AiderDesk, Open WebUI, ChatGPT, or Gemini: calm, readable, fast, obvious, and trustworthy.

## Current Evidence

Files inspected:

- `frontend/index.html`
- `frontend/styles.css`
- `frontend/app.js`

Important current traits:

- `frontend/index.html` uses a `74px` icon rail with unlabeled SVG buttons.
- `frontend/styles.css` is one dense stylesheet with many large one-line selector groups.
- The default theme uses sage/cream colors that read soft and unfinished for this product.
- The settings experience is one modal with many tabs and nested card-heavy forms.
- The home view has a chat panel plus an activity panel, but the hierarchy does not clearly say what deserves attention.

## Product Direction

Rasputin should feel like a serious local operating console for private AI work.

Design words:

- precise
- quiet
- durable
- local-first
- security-aware
- engineer-friendly
- not decorative
- not marketing-like

Default visual direction:

- neutral light theme as the default
- dark graphite theme as a first-class option
- one restrained accent color
- low-border, low-shadow UI
- 8px to 10px radii for most surfaces
- clear labels over mystery icons
- dense but readable settings

## Phase 1: Navigation Rebuild

Goal: make the sidebar understandable in under one second.

Changes:

- Replace the pure icon rail with an expandable labeled sidebar.
- Expanded width: about `236px`.
- Collapsed width: about `72px`.
- Each nav item shows:
  - icon
  - text label in expanded mode
  - active state
  - optional count badge where useful
- Keep tooltips, but do not rely on tooltips for basic meaning.
- Add nav entries:
  - Home
  - Workspaces
  - Tasks
  - Knowledge
  - Models
  - Audit
  - Settings
- Move privacy/model/workspace status into a compact status cluster at the bottom of the sidebar.
- Make the collapse button obvious and stable.

Files:

- `frontend/index.html`
- `frontend/styles.css`
- `frontend/app.js`

Acceptance checks:

- A new user can identify every sidebar destination without hovering.
- Collapsed mode still has accessible labels and tooltips.
- The current route or active settings section is visually obvious.
- Sidebar state persists after refresh.

## Phase 2: Main Home Screen Cleanup

Goal: make the home screen feel like an AI chat/workbench, not a diagnostics board.

Changes:

- Keep the home view focused on conversation and active work.
- Move secondary task stats out of the primary visual path.
- Replace the current header metadata string with readable controls:
  - active workspace selector
  - active model selector
  - privacy lock indicator
  - settings button
- Simplify message cards:
  - user message
  - assistant response
  - compact status line only when useful
  - logs/sources/artifacts hidden in disclosure panels
- Make the composer feel like the main product surface:
  - model health indicator
  - send button
  - optional mode button
  - no noisy profile button unless it opens a useful quick panel
- Convert the activity panel into either:
  - a right drawer that can be opened when needed, or
  - a dedicated Tasks view.

Files:

- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`

Acceptance checks:

- The first screen reads as "chat with Rasputin" immediately.
- The user can send a message without parsing model internals.
- Task logs and artifacts are available, but not visually dominant.
- Mobile layout keeps the composer and latest response usable.

## Phase 3: Settings Redesign

Goal: settings should feel like a real product settings area, not a giant modal.

Changes:

- Replace the current modal-first settings shell with a full settings view or full-height side sheet.
- Keep settings isolated from Home.
- Use a two-column settings layout:
  - left: settings section navigation
  - right: focused settings content
- Sections:
  - General
  - Workspaces
  - Models
  - Safety
  - Knowledge
  - Output
  - Appearance
  - Admin
- Remove repeated card nesting.
- Use section headers, concise help text, and grouped controls.
- Keep advanced/raw controls behind an "Advanced" disclosure.
- Model settings should start with workflows:
  - Discover vLLM models
  - Scan GGUF library
  - Import selected GGUF
  - Test selected model
  - Start or stop only when Docker control is enabled
- Raw endpoint/path fields should be secondary.

Files:

- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`

Acceptance checks:

- Settings can be navigated by keyboard.
- Each settings section has one clear purpose.
- Models can be configured without manually understanding every registry field.
- Safety settings look important, not like a random checkbox grid.

## Phase 4: Visual System Reset

Goal: replace the current soft prototype palette with a professional design system.

Changes:

- Create a small token system:
  - background
  - surface
  - surface-raised
  - text
  - text-muted
  - border
  - accent
  - danger
  - success
  - warning
  - focus
- Default theme: "Rasputin Light"
  - near-white background
  - white surfaces
  - graphite text
  - cool blue or steel accent
- Dark theme: "Rasputin Dark"
  - graphite background
  - raised dark surfaces
  - pale text
  - blue/cyan accent
- Keep High Contrast.
- Remove or demote the current novelty themes:
  - sage
  - ocean
  - ember
  - iris
  - alpine
  - sandstone
- Reduce border radius across the app.
- Use shadows sparingly.
- Replace pill overload with more restrained status chips.

Files:

- `frontend/styles.css`
- `frontend/app.js`

Acceptance checks:

- Default theme no longer reads beige/green or "AI template."
- Dark mode feels first-class.
- Contrast is readable.
- Buttons, fields, tabs, and cards feel like one system.

## Phase 5: Component And State Cleanup

Goal: make the vanilla frontend easier to maintain without adding React/Vue.

Changes:

- Split large render functions into domain-oriented groups:
  - navigation
  - chat
  - tasks
  - settings
  - models
  - workspace
  - safety
  - themes
- Keep vanilla JS, but create predictable render/update functions.
- Add stable `data-testid` attributes to key controls.
- Normalize UI state:
  - active view
  - active settings section
  - sidebar collapsed
  - selected model
  - selected workspace
  - active theme
- Avoid hidden coupling between settings controls and chat controls.

Files:

- `frontend/app.js`
- optional future split:
  - `frontend/js/navigation.js`
  - `frontend/js/settings.js`
  - `frontend/js/models.js`
  - `frontend/js/chat.js`

Acceptance checks:

- Every button has an obvious handler or disabled state.
- No click-only controls that keyboard users cannot reach.
- Frontend changes become easier to test.

## Phase 6: Accessibility And Polish Pass

Goal: the app should feel finished to keyboard, screen reader, and regular mouse users.

Changes:

- Every icon button needs visible text or a strong accessible name.
- Focus states must be visible but not ugly.
- Settings navigation uses proper selected state.
- Dialogs/sheets trap focus only when they are actually modal.
- Toasts and task updates use `aria-live` without being noisy.
- Forms use real labels, not placeholder-only labels.
- Empty states should tell the user what action is available next.
- Loading states should not shift layout.

Acceptance checks:

- Full app can be used with keyboard only.
- Sidebar labels are visible in expanded mode.
- Settings can be opened, navigated, changed, and closed without mouse.
- Text does not overflow buttons or status chips.

## Phase 7: Verification Harness

Goal: stop judging UI polish only by vibes.

Tests to add:

- Playwright visual smoke:
  - login screen
  - home screen
  - expanded sidebar
  - collapsed sidebar
  - settings view
  - models settings
  - dark theme
  - mobile width
- API/UI integration smoke:
  - login
  - sidebar toggle persists
  - settings tabs work
  - theme switching works
  - model discovery button responds
  - GGUF scan button responds
  - send disabled when model unhealthy
- Accessibility smoke:
  - keyboard tab order
  - no unlabeled buttons
  - visible focus

Existing relevant files:

- `tests/ui/rasputinSmoke.spec.mjs`
- `playwright.config.mjs`
- `scripts/test.ps1`
- `scripts/test.sh`

Acceptance checks:

- Docker harness still passes.
- UI smoke test screenshots are generated for review.
- At least one screenshot per major view is inspected before calling the redesign done.

## Implementation Order

Recommended order:

1. Replace icon-only sidebar with labeled expandable navigation.
2. Replace color tokens and set new default light/dark themes.
3. Simplify the home header and composer.
4. Convert settings modal into a full settings view/sheet.
5. Redesign Models, Workspaces, and Safety settings first.
6. Clean up app.js render/state organization.
7. Add Playwright screenshot checks.
8. Run Docker harness and visual review.

## Non-Goals For This Pass

- Do not add a heavy frontend framework.
- Do not rebuild the backend.
- Do not add decorative hero sections.
- Do not add more novelty themes.
- Do not hide critical safety controls.
- Do not make the UI look like a marketing website.

## Definition Of Done

This UI repair is complete only when:

- Sidebar navigation is understandable without hovering.
- Default color scheme feels intentional and professional.
- Settings no longer feel like a half-built modal dashboard.
- Home screen is focused on conversation and active work.
- Model setup feels workflow-driven, not raw-config-driven.
- All major controls are keyboard accessible.
- Docker test harness passes.
- UI screenshot smoke tests exist and are reviewed.
