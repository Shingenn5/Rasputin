# Rasputin Frontend Redesign Plan

## Goal

Rebuild the Rasputin frontend from the bottom up into a professional local AI workbench while keeping CSS small and relying on a mature external styling system.

The target should feel closer to a serious desktop-grade web app than a prototype dashboard:

- chat-first home screen
- clear left navigation
- focused settings pages
- readable model and workspace controls
- strong accessibility defaults
- minimal custom CSS
- boring, reliable component primitives

## Current State

Current repo evidence:

- `frontend-src/` already uses React and Vite.
- `frontend-src/src/main.jsx` is about 39 KB and contains API helpers, state, routing, layout, views, settings, and form logic in one file.
- `frontend-src/src/styles.css` is about 17 KB and carries almost the entire visual system by hand.
- `package.json` currently includes React, React DOM, Vite, Playwright, and lucide icons.
- `frontend/` is the built static output served by FastAPI under `/static/`.
- The UI smoke tests depend on stable selectors such as `#homeView`, `#model`, `#settingsShell`, `data-testid="nav-home"`, and `data-testid="workspace-browser"`.

The main problem is not that the repo lacks a framework. The problem is that the current frontend is not yet a real component system.

## Stack Decision

Recommended stack:

```text
React + Vite + Bootstrap 5.3 + React-Bootstrap + lucide-react
```

Supporting libraries:

```text
@tanstack/react-query      API loading/cache/mutations
react-markdown            assistant output rendering
rehype-sanitize           safe markdown HTML handling
bootstrap-icons           optional Bootstrap-native icons
```

Keep `lucide-react` for navigation and action icons unless Bootstrap Icons visually fits better after the first design pass.

Do not move to Svelte or Vue right now. They are good frameworks, but switching framework would mostly rewrite working integration code without solving the real issue: visual system, information architecture, component boundaries, and settings ergonomics.

## Why Bootstrap

Bootstrap is the best fit for the stated preference:

- It gives layout, spacing, forms, buttons, navs, offcanvas panels, tabs, cards, tables, badges, alerts, modals, and responsive utilities without writing much CSS.
- Bootstrap 5.3 has built-in color mode support through `data-bs-theme`.
- React-Bootstrap provides Bootstrap 5 components as React components.
- It is less likely than a custom Tailwind pass to drift into an "AI dashboard template" look because Bootstrap gives plain product primitives first.

Tailwind is useful for custom design systems, but it usually moves styling into long class strings. That would reduce CSS files, but not necessarily reduce styling complexity. For Rasputin, Bootstrap is the cleaner default.

## Target Architecture

New source layout:

```text
frontend-src/
  index.html
  src/
    main.jsx
    app/
      App.jsx
      AppProviders.jsx
      routes.js
    api/
      client.js
      auth.js
      tasks.js
      models.js
      workspaces.js
      security.js
      knowledge.js
      audit.js
    components/
      AppShell.jsx
      Sidebar.jsx
      TopBar.jsx
      StatusPill.jsx
      EmptyState.jsx
      ConfirmAction.jsx
      RuntimeBadge.jsx
    features/
      chat/
        ChatView.jsx
        Composer.jsx
        MessageList.jsx
        MessageBubble.jsx
        MessageDetails.jsx
      settings/
        SettingsLayout.jsx
        GeneralSettings.jsx
        WorkspaceSettings.jsx
        ModelSettings.jsx
        SafetySettings.jsx
        KnowledgeSettings.jsx
        OutputSettings.jsx
        AppearanceSettings.jsx
        AdminSettings.jsx
      workspaces/
        WorkspaceBrowser.jsx
        WorkspaceCard.jsx
        MountPlanPanel.jsx
      models/
        ActiveModelCard.jsx
        ModelDiscoveryPanel.jsx
        AdvancedRegistry.jsx
      tasks/
        TasksView.jsx
        TaskRow.jsx
        TaskDetails.jsx
      audit/
        AuditView.jsx
        AuditEventRow.jsx
    state/
      preferences.js
      uiState.js
    styles/
      bootstrap.scss
      rasputin.css
```

`rasputin.css` should stay small. Its job is branding and app-specific layout only, not replacing Bootstrap.

Target custom CSS budget:

```text
Phase 1: under 8 KB
Final: under 5 KB if practical
```

## Dependency Plan

Add:

```powershell
npm install bootstrap react-bootstrap @tanstack/react-query react-markdown rehype-sanitize
```

Optional after visual pass:

```powershell
npm install bootstrap-icons
```

Import Bootstrap once:

```jsx
import "bootstrap/dist/css/bootstrap.min.css";
```

If we need small token overrides, create:

```text
frontend-src/src/styles/rasputin.css
```

Use Bootstrap color mode:

```js
document.documentElement.setAttribute("data-bs-theme", theme === "rasputin-dark" ? "dark" : "light");
```

Keep Rasputin-specific theme names in preferences, but map them to Bootstrap's `light` and `dark` modes.

## Design Direction

Default light theme:

- white and near-white surfaces
- graphite text
- muted blue primary
- minimal shadows
- Bootstrap spacing scale
- Bootstrap form controls
- cards only where a boundary is useful

Dark theme:

- Bootstrap dark mode as the base
- small Rasputin token overrides only where necessary
- no separate custom dark stylesheet

High contrast:

- keep existing preference
- implement with a small `data-contrast="true"` override or Bootstrap variable overrides

Avoid:

- decorative gradients
- oversized cards
- random badges
- raw model registry details on the main path
- custom controls when Bootstrap already has one

## Product Structure

### Home

Home should become a clean chat surface:

- persistent sidebar
- top bar with active workspace, active model, privacy state
- centered empty state when no local conversation is active
- composer pinned at bottom
- latest user and assistant messages in a readable thread
- model logs, artifacts, sources, and traces inside collapsed details

Bootstrap components:

- `Container`
- `Stack`
- `Button`
- `Form.Control`
- `Dropdown`
- `Badge`
- `Accordion`
- `Alert`

### Sidebar

Use a Bootstrap `Nav` inside an app shell:

- Home
- Workspaces
- Tasks
- Knowledge
- Models
- Audit
- Settings

Expanded/collapsed state must persist.

Keep existing `data-testid` attributes during migration.

### Settings

Settings should be full-page, not modal-first:

- left settings nav
- right content panel
- Bootstrap tabs or nav pills
- each settings section owns one workflow

Sections:

- General
- Workspaces
- Models
- Safety
- Knowledge
- Output
- Appearance
- Admin

Advanced fields stay inside `Accordion` or `Collapse`.

### Models

Normal model UI should show:

- active model
- health
- endpoint status
- refresh/test
- use discovered model

Advanced registry should show:

- key
- provider
- runtime
- model ID
- base URL
- discovered models
- raw error

No registry tags in the normal path.

### Workspaces

Workspace UI should use Bootstrap list groups and cards:

- approved folders
- folder browser
- breadcrumb navigation
- add folder/mount plan flow
- read-only/read-write state

Manual paths stay under Advanced.

## Migration Phases

### Phase 0: Freeze Contracts

Tasks:

- list all current UI test selectors
- keep compatibility IDs through the migration
- add missing `data-testid` markers before moving components
- capture screenshots of current login, home, settings, models, workspaces, tasks, and mobile

Done when:

- existing UI tests still pass before visual rewrite begins
- screenshot baseline exists

### Phase 1: Install Bootstrap Foundation

Tasks:

- add Bootstrap and React-Bootstrap dependencies
- import Bootstrap CSS in `main.jsx`
- remove broad custom resets that Bootstrap already handles
- map Rasputin theme values to `data-bs-theme`
- keep only tiny brand CSS for app shell dimensions

Done when:

- app builds
- light/dark theme switching still works
- UI tests still pass

### Phase 2: Split The Monolith

Tasks:

- move API helpers into `src/api/client.js`
- move shell into `components/AppShell.jsx`
- move views into `features/*`
- keep `main.jsx` as a tiny boot file
- introduce React Query for server state
- keep local UI state separate from server data

Done when:

- `main.jsx` is mostly imports and `createRoot`
- views are testable by component boundary
- no feature file owns unrelated state

### Phase 3: Rebuild App Shell

Tasks:

- create Bootstrap-based sidebar
- create top bar
- create mobile offcanvas navigation
- remove custom nav/button styling where Bootstrap handles it
- ensure keyboard focus and aria labels

Done when:

- desktop navigation is clear
- mobile opens a drawer instead of crushing the first viewport
- sidebar collapse persists

### Phase 4: Rebuild Chat Home

Tasks:

- replace custom chat cards with Bootstrap stacks and cards
- build a proper empty state
- rebuild composer using Bootstrap input group/form controls
- add markdown rendering with sanitation
- collapse task details by default

Done when:

- home reads as the primary product
- sending a dry-run task still works
- assistant output renders markdown safely

### Phase 5: Rebuild Settings Workflows

Tasks:

- Settings layout with Bootstrap nav pills
- Model settings with active model card and advanced registry accordion
- Workspace settings with browser and mount-plan cards
- Safety settings grouped by permission category
- Appearance settings using Bootstrap color modes

Done when:

- a normal user can change model/workspace/theme without seeing raw internals
- advanced controls remain available but secondary
- all existing settings tests pass

### Phase 6: Tasks, Knowledge, Audit

Tasks:

- Tasks view becomes a table/list hybrid with status badges
- Knowledge view separates RAG and Graphify panels
- Audit view uses tables/list groups with filters
- output/export actions are grouped as commands

Done when:

- debug-heavy surfaces are not on Home
- task and audit data are scannable
- controls have clear empty/error/loading states

### Phase 7: CSS Reduction

Tasks:

- delete replaced custom CSS
- keep only app shell, brand mark, chat sizing, and rare overrides
- prefer Bootstrap utility classes for spacing, borders, typography, and responsive behavior
- document when custom CSS is allowed

Done when:

- `rasputin.css` is under the agreed budget
- no custom CSS recreates Bootstrap buttons/forms/cards/navs

### Phase 8: Verification

Commands:

```powershell
npm run build
.\scripts\test.ps1 -Ui
```

Checks:

- login renders
- home renders
- sidebar expanded/collapsed
- dark mode
- mobile home
- settings models
- workspaces browser
- dry-run task send
- no white-screen reload issue
- no unlabeled icon buttons
- no random punctuation labels

Done when:

- test harness passes
- screenshots are reviewed
- manual browser refresh works without stale assets

## Acceptance Criteria

The redesign plan is implemented only when:

- React remains the app framework unless there is a specific blocker.
- Bootstrap/React-Bootstrap owns most visual primitives.
- custom CSS is substantially reduced from the current 17 KB file.
- `main.jsx` is no longer the whole app.
- Home is chat-first.
- Settings are full-page workflow screens.
- model setup hides raw registry fields by default.
- workspace selection is GUI-first.
- theme preference persists.
- Docker/FastAPI still serve the Vite build from `frontend/`.
- existing backend APIs remain compatible.
- UI tests and Docker harness pass.

## Rollback Strategy

Keep the current React build available on the branch until the Bootstrap version passes the harness.

Migration should happen in slices:

1. add dependencies
2. split files without changing visuals
3. replace shell
4. replace home
5. replace settings
6. delete old CSS

If a slice fails badly, revert only that slice.

## Recommended First Implementation Slice

Start with the least risky slice:

1. add `bootstrap`, `react-bootstrap`, and `@tanstack/react-query`
2. import Bootstrap CSS
3. create `src/api/client.js`
4. create `src/components/AppShell.jsx`
5. move sidebar/topbar out of `main.jsx`
6. keep existing markup mostly intact
7. run `npm run build`
8. run `.\scripts\test.ps1 -Ui`

This makes the next visual pass much safer because it separates architecture cleanup from visual redesign.

## Reference Notes

- Vite production builds use `vite build` and rewrite asset URLs according to the configured `base` path.
- React-Bootstrap maps Bootstrap 5 components into React components; Bootstrap 5 uses React-Bootstrap 2.x.
- Bootstrap 5.3 supports color modes through the `data-bs-theme` attribute.
