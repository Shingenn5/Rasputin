# Theme Sync, Settings Redesign, Recent Chats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Settings theme dropdown desync, migrate all Settings panels off react-bootstrap onto the dashboard's Tailwind/shadcn token system with a grouped section nav, and add pin + date-grouping to Recent Chats.

**Architecture:** Theme state collapses to a single source (`App.jsx`'s `theme`/`setTheme`, persisted via `localStorage` + `/api/preferences`); the separate `/api/settings` `general.theme` field and its stale 9-theme allow-list in `/api/preferences` are removed/fixed. Settings panels are rewritten to use the existing `@/components/ui/*` shadcn primitives (`Card`, `Button`, `Badge`, `Input`) plus two new primitives (`Select`, `Switch`) built in the same thin-wrapper style, all driven by the `--dash-*`/`--color-*` tokens already wired in `theme.css`. The Settings section nav becomes 4 collapsible groups wrapping the existing 11 sections, no routing changes. Recent Chats gains a `pinned` boolean on the session schema (mirroring how `folder` already works end-to-end) and renders Pinned/Today/Yesterday/This Week/Older groups as a presentation layer over the existing filtered/sorted session list.

**Tech Stack:** React 18, Tailwind v4 (CSS-first `@theme inline`), shadcn-style primitives (no Radix dependency added), Zustand (`settingsStore`), FastAPI + SQLite (`runtime_store.py`), Vite.

**User decisions (already made):**
- Theme fix: single source of truth — remove `theme` from `/api/settings`, Settings dropdown drives `App.jsx`'s live `theme`/`setTheme` directly.
- Settings redesign: both visual (migrate to dashboard tokens) and structural (group into 4 categories) — not skin-only, not IA-only.
- Settings section nav grouping: Platform (General, Models, Integrations) / Security (Security, Audit) / Operations (Runtime, Deployments, Resources, Notifications) / System (Diagnostics, About).
- Settings nav pattern: collapsible groups, matching the main app sidebar's Workspace/Fleet/Knowledge pattern.
- Settings layout: keep the existing 3-column layout (nav | content | inspector panel) — restyle only, no structural removal of the inspector.
- Recent Chats: add pin/favorite AND date grouping (not just one).
- Pinned chats render as their own group above the date groups (not an inline badge).
- Pin state is a backend field on the session object (same persistence path as `folder`), not localStorage-only.

---

## Relevant files (read before starting)

- `frontend-src/src/app/App.jsx` — owns `theme`/`setTheme` state (lines 85, 225-231, 307-327, 334-354, 387-389, 1785-1791), passes `theme`/`setTheme`/`themeOptions` to `<SettingsView>` (~lines 1726-1728), defines `assignSessionFolder` (~lines 1137-1144) and passes it + `recentSessions`/`chatFolders` to `<Sidebar>` via `sidebarProps` (~lines 1448-1469).
- `frontend-src/index.html` — `window.rasputinTheme.apply()`/`.normalize()`, the 14-theme color table, applied before React mounts.
- `frontend-src/src/lib/constants.js` — `themeOptions` (14 entries), `settingsItems` (11 entries).
- `backend/core/preferences.py` — `/api/preferences` store; `THEMES` allow-list (currently 9 of 14); `defaults()`, `_coerce()`.
- `backend/core/settings_api.py` — `/api/settings` store; `DEFAULT_SETTINGS["general"]` includes a redundant `theme` key.
- `frontend-src/src/features/settings/GeneralSettings.jsx` — the dropdown with the desync bug; template for the migration pattern.
- `frontend-src/src/features/settings/SettingsView.jsx` — outer shell, flat nav, inspector panel.
- `frontend-src/src/features/settings/{Runtime,Security,Model,Deployment,Integration,Resource,Notification,Audit,Diagnostics,About}Settings.jsx` — 10 more panels on the same react-bootstrap pattern (see Task 7 for per-file notes).
- `frontend-src/src/components/ui/{card,button,badge,input}.jsx` — existing shadcn primitives to reuse.
- `frontend-src/src/styles/theme.css` / `dashboard.css` — token definitions (`--color-*`, `--dash-*`).
- `frontend-src/src/components/Sidebar.jsx` — Recent Chats: `visibleSessions` useMemo (lines 61-80), session row JSX (lines 213-260), `sortSessions`/`sessionTime` helpers (lines 286-298).
- `backend/core/runtime_store.py` — `sessions` table schema (lines 56-67) and migration block (~line 205, where `folder` was added).
- `backend/api/agent.py` — `SessionFolderIn` model and `/api/sessions/{id}/folder` route (~lines 22-24, 62-67).
- `backend/engine/agent.py` — `assign_session_folder()` (~lines 521-536), the hub method the route calls.

---

## Task 1: Fix stale theme allow-list in `/api/preferences`

**Goal:** `backend/core/preferences.py`'s `THEMES` set includes all 14 current theme keys, so no theme silently resets to `rasputin-light` on save/load.

**Files:**
- Modify: `backend/core/preferences.py:13-23`
- Test: `tests/testBackendSmoke.py` (add a case, following existing style in that file)

**Acceptance Criteria:**
- [ ] `THEMES` contains exactly the 14 keys from `frontend-src/src/lib/constants.js`'s `themeOptions`.
- [ ] Saving preferences with `theme: "cyberpunk-neon"` (or any of the other 4 previously-missing themes) round-trips unchanged through `_coerce()`.

**Verify:** `python -m pytest tests/testBackendSmoke.py -v -k theme` → PASS

**Steps:**

- [ ] **Step 1: Write the failing test**

Add to `tests/testBackendSmoke.py` (match the existing import/fixture style already in that file — read the top of the file first to match its test client setup):

```python
def test_preferences_accepts_all_14_themes(client):
    all_themes = [
        "rasputin-light", "rasputin-dark", "contrast",
        "bootswatch-slate", "bootswatch-cyborg", "bootswatch-darkly",
        "bootswatch-lux", "bootswatch-solar", "bootswatch-superhero",
        "cyberpunk-neon", "ocean-abyss", "hacker-matrix",
        "crimson-forge", "nord-frost",
    ]
    for theme in all_themes:
        resp = client.post("/api/preferences", json={"theme": theme})
        assert resp.status_code == 200
        body = resp.json()
        saved_theme = body.get("data", body).get("theme")
        assert saved_theme == theme, f"{theme} was reset to {saved_theme}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/testBackendSmoke.py -v -k all_14_themes`
Expected: FAIL — `cyberpunk-neon`, `ocean-abyss`, `hacker-matrix`, `crimson-forge`, `nord-frost` get reset to `rasputin-light`.

- [ ] **Step 3: Fix the allow-list**

In `backend/core/preferences.py`, replace lines 13-23:

```python
THEMES = {
    "rasputin-light",
    "rasputin-dark",
    "contrast",
    "bootswatch-slate",
    "bootswatch-cyborg",
    "bootswatch-darkly",
    "bootswatch-lux",
    "bootswatch-solar",
    "bootswatch-superhero",
}
```

with:

```python
THEMES = {
    "rasputin-light",
    "rasputin-dark",
    "contrast",
    "bootswatch-slate",
    "bootswatch-cyborg",
    "bootswatch-darkly",
    "bootswatch-lux",
    "bootswatch-solar",
    "bootswatch-superhero",
    "cyberpunk-neon",
    "ocean-abyss",
    "hacker-matrix",
    "crimson-forge",
    "nord-frost",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/testBackendSmoke.py -v -k all_14_themes`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/preferences.py tests/testBackendSmoke.py
git commit -m "fix(prefs): add missing 5 themes to preferences allow-list"
```

---

## Task 2: Remove redundant `theme` from `/api/settings` general domain

**Goal:** `/api/settings`'s `general` domain no longer carries a `theme` field, eliminating the second source of theme truth.

**Files:**
- Modify: `backend/core/settings_api.py:14-22`

**Acceptance Criteria:**
- [ ] `DEFAULT_SETTINGS["general"]` no longer has a `theme` key.
- [ ] `GET /api/settings` response's `general` object has no `theme` field.
- [ ] No other code in `settings_api.py` references `general.theme` (grep clean).

**Verify:** `grep -n "theme" backend/core/settings_api.py` → no matches

**Steps:**

- [ ] **Step 1: Remove the field**

In `backend/core/settings_api.py`, change:

```python
DEFAULT_SETTINGS = {
    "general": {
        "theme": "rasputin-dark",
        "language": "en",
        "workspacePath": "/app/workspace",
        "markdownOutput": True,
        "testingMode": False,
        "telemetryEnabled": False
    },
```

to:

```python
DEFAULT_SETTINGS = {
    "general": {
        "language": "en",
        "workspacePath": "/app/workspace",
        "markdownOutput": True,
        "testingMode": False,
        "telemetryEnabled": False
    },
```

- [ ] **Step 2: Verify no other references**

Run: `grep -n "theme" backend/core/settings_api.py`
Expected: no output

- [ ] **Step 3: Commit**

```bash
git add backend/core/settings_api.py
git commit -m "fix(settings): remove redundant theme field from /api/settings general domain"
```

---

## Task 3: Wire `GeneralSettings.jsx`'s theme dropdown to the live `theme`/`setTheme` prop, not the settings store

**Goal:** The Platform Theme dropdown in Settings always shows and controls the same theme as the rest of the app — no separate save step, no drift after reload.

**Files:**
- Modify: `frontend-src/src/features/settings/GeneralSettings.jsx`
- Modify: `frontend-src/src/features/settings/SettingsView.jsx:23,102` (pass `theme` through to `GeneralSettings`)

**Acceptance Criteria:**
- [ ] `GeneralSettings` receives `theme` as a prop (in addition to existing `setTheme`) and the `<select>`'s `value` is `theme`, not `formData.theme`.
- [ ] Selecting a new theme calls `setTheme(val)` only — no `updateSetting("general", "theme", ...)` call, no entry in `formData`/`isDirty` for theme.
- [ ] After selecting a theme and reloading the page, the dropdown still shows the selected theme (manual check in Task 9).

**Verify:** `grep -n "theme" frontend-src/src/features/settings/GeneralSettings.jsx` shows only the `theme`/`setTheme` prop usage, no `formData.theme` or `handleChange("theme", ...)`.

**Steps:**

- [ ] **Step 1: Pass `theme` down from SettingsView**

In `frontend-src/src/features/settings/SettingsView.jsx`, change line 23:

```javascript
  const { view, section, setSection, setTheme, models, modeModelOverrides, setModeModelOverride } = props;
```

to:

```javascript
  const { view, section, setSection, theme, setTheme, models, modeModelOverrides, setModeModelOverride } = props;
```

And change line 102:

```javascript
          {section === "general" && <GeneralSettings setTheme={setTheme} />}
```

to:

```javascript
          {section === "general" && <GeneralSettings theme={theme} setTheme={setTheme} />}
```

- [ ] **Step 2: Update GeneralSettings.jsx to read/write theme directly**

In `frontend-src/src/features/settings/GeneralSettings.jsx`, change the function signature (line 8):

```javascript
export function GeneralSettings({ setTheme }) {
```

to:

```javascript
export function GeneralSettings({ theme, setTheme }) {
```

Change `handleChange` (lines 24-30) to stop special-casing theme into `formData`:

```javascript
  const handleChange = (key, val) => {
    setFormData(prev => ({ ...prev, [key]: val }));
    setIsDirty(true);
    if (key === "theme" && setTheme) {
      setTheme(val);
    }
  };
```

becomes:

```javascript
  const handleChange = (key, val) => {
    setFormData(prev => ({ ...prev, [key]: val }));
    setIsDirty(true);
  };
```

Change the theme `<Form.Select>` (lines 82-91) to read from the `theme` prop directly and call `setTheme` instead of `handleChange`:

```javascript
                <Form.Select 
                  size="lg"
                  className="fs-6"
                  value={formData?.theme || "rasputin-dark"}
                  onChange={(e) => handleChange("theme", e.target.value)}
                >
                  {themeOptions.map(([val, label, desc]) => (
                    <option key={val} value={val}>{label} - {desc}</option>
                  ))}
                </Form.Select>
```

becomes:

```javascript
                <Form.Select 
                  size="lg"
                  className="fs-6"
                  value={theme || "rasputin-dark"}
                  onChange={(e) => setTheme?.(e.target.value)}
                >
                  {themeOptions.map(([val, label, desc]) => (
                    <option key={val} value={val}>{label} - {desc}</option>
                  ))}
                </Form.Select>
```

(Note: this `<Form.Select>` itself gets replaced with the new `Select` primitive in Task 6 — this task only fixes the data wiring, Task 6 fixes the visual.)

- [ ] **Step 3: Confirm `useEffect` syncing `formData` from the store no longer clobbers theme**

The existing `useEffect` (lines 17-22) sets `formData` from `general` (the Zustand store value). Since `general.theme` no longer exists (Task 2), this is already safe — `formData.theme` will simply be `undefined` and is no longer read anywhere. No code change needed here; this step is a verification, not an edit.

- [ ] **Step 4: Manual verification**

Run `npm run dev`, open Settings → General, confirm the dropdown shows the currently active theme and changing it immediately re-themes the dashboard/sidebar (full reload verification happens in Task 9 after the backend changes are live).

- [ ] **Step 5: Commit**

```bash
git add frontend-src/src/features/settings/GeneralSettings.jsx frontend-src/src/features/settings/SettingsView.jsx
git commit -m "fix(settings): drive theme dropdown from live App theme state, not settings store"
```

---

## Task 4: Add `Select` and `Switch` UI primitives

**Goal:** Two new token-driven primitives exist at `frontend-src/src/components/ui/select.jsx` and `frontend-src/src/components/ui/switch.jsx`, matching the existing thin-wrapper style of `input.jsx`/`button.jsx` (no new npm dependency).

**Files:**
- Create: `frontend-src/src/components/ui/select.jsx`
- Create: `frontend-src/src/components/ui/switch.jsx`

**Acceptance Criteria:**
- [ ] `Select` renders a native `<select>` styled with the same token classes as `Input` (`bg-background`, `border-input`, `text-sm`, etc.), forwards `ref`, accepts `children` (the `<option>` elements) and `className`.
- [ ] `Switch` renders a native `<input type="checkbox">` visually styled as a toggle (track + thumb) using `--primary`/`--dash-*` tokens for the "on" state, accepts `checked`/`onChange`/`className`, forwards `ref`.

**Verify:** `npm run build` succeeds with no import errors once these are referenced (cross-checked in Task 5 onward).

**Steps:**

- [ ] **Step 1: Create `select.jsx`**

```javascript
import * as React from "react";
import { cn } from "@/lib/utils.js";

export const Select = React.forwardRef(({ className, children, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      "flex h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-sm outline-none transition-colors focus:border-primary/50 disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  >
    {children}
  </select>
));
Select.displayName = "Select";
```

- [ ] **Step 2: Create `switch.jsx`**

```javascript
import * as React from "react";
import { cn } from "@/lib/utils.js";

export const Switch = React.forwardRef(({ className, checked, onChange, ...props }, ref) => (
  <label className={cn("relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center", className)}>
    <input
      ref={ref}
      type="checkbox"
      role="switch"
      checked={checked}
      onChange={onChange}
      className="peer sr-only"
      {...props}
    />
    <span
      aria-hidden="true"
      className="absolute inset-0 rounded-full bg-muted transition-colors peer-checked:bg-primary peer-disabled:opacity-50"
    />
    <span
      aria-hidden="true"
      className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-background shadow transition-transform peer-checked:translate-x-5"
    />
  </label>
));
Switch.displayName = "Switch";
```

- [ ] **Step 3: Smoke-check imports resolve**

Run: `npm run build`
Expected: build succeeds (these files aren't imported by anything yet, so this just confirms no syntax errors).

- [ ] **Step 4: Commit**

```bash
git add frontend-src/src/components/ui/select.jsx frontend-src/src/components/ui/switch.jsx
git commit -m "feat(ui): add token-driven Select and Switch primitives"
```

---

## Task 5: Migrate `SettingsView.jsx` shell + grouped collapsible nav onto dashboard tokens

**Goal:** The Settings outer shell (header, section nav, inspector panel) uses `.tw`/`--dash-*`/shadcn tokens instead of react-bootstrap, and the flat 11-item nav is replaced with 4 collapsible groups (Platform/Security/Operations/System).

**Files:**
- Modify: `frontend-src/src/features/settings/SettingsView.jsx`
- Modify: `frontend-src/src/lib/constants.js` (add the group structure)

**Acceptance Criteria:**
- [ ] `settingsItems` in `constants.js` is reorganized (or a new `settingsGroups` export added) so the nav can render 4 named groups, each listing its member sections in the order specified in the design: Platform (General, Models, Integrations), Security (Security, Audit), Operations (Runtime, Deployments, Resources, Notifications), System (Diagnostics, About).
- [ ] Each group header is clickable and toggles that group's expanded/collapsed state (local `useState`, not persisted).
- [ ] No `react-bootstrap` imports remain in `SettingsView.jsx`.
- [ ] The inspector panel (description/validation/impact/dependencies) is visually restyled with token classes but its content/logic (`getInspectorText`) is unchanged.
- [ ] Clicking a section still calls `setSection(id)` and navigates exactly as before (no change to `#settings/<section>` routing).

**Verify:** `npm run build` → succeeds; manual check in Task 9 confirms grouped nav renders and expands/collapses.

**Steps:**

- [ ] **Step 1: Add group structure to `constants.js`**

In `frontend-src/src/lib/constants.js`, after the existing `settingsItems` array (lines 13-25), add:

```javascript
export const settingsGroups = [
  { id: "platform", label: "Platform", sections: ["general", "models", "integrations"] },
  { id: "security", label: "Security", sections: ["security", "audit"] },
  { id: "operations", label: "Operations", sections: ["runtime", "deployments", "resources", "notifications"] },
  { id: "system", label: "System", sections: ["diagnostics", "about"] },
];
```

Leave `settingsItems` as-is — `settingsGroups` references section ids that still resolve via `settingsItems` for label/description lookups.

- [ ] **Step 2: Rewrite the imports in `SettingsView.jsx`**

Replace line 1-3:

```javascript
import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Col, Form, ListGroup, Nav, Row, Stack } from "react-bootstrap";
import { CheckCircle2, Download, Upload, RefreshCw, Save, ShieldAlert, ShieldCheck, Square, Wrench, Search, Info, Settings2, Activity, BrainCircuit, Rocket, Plug, Server as ServerIcon, Bell, FileWarning, Stethoscope } from "lucide-react";
```

with:

```javascript
import React, { useEffect, useState } from "react";
import { CheckCircle2, Download, Upload, RefreshCw, ShieldAlert, ShieldCheck, Square, Search, Info, Settings2, Activity, BrainCircuit, Rocket, Plug, Server as ServerIcon, Bell, FileWarning, Stethoscope, ChevronDown } from "lucide-react";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Badge as UIBadge } from "@/components/ui/badge.jsx";
import { Input } from "@/components/ui/input.jsx";
import { cn } from "@/lib/utils.js";
import { settingsGroups } from "../../lib/constants.js";
```

Keep the existing `import { settingsItems } from "../../lib/constants.js";` line (line 5) — both `settingsItems` and `settingsGroups` are needed.

- [ ] **Step 3: Add collapsed-group state**

Inside `SettingsView`, after the existing `const [searchQuery, setSearchQuery] = useState("");` (line 25), add:

```javascript
  const [collapsedGroups, setCollapsedGroups] = useState({});
  const toggleGroup = (groupId) => setCollapsedGroups(prev => ({ ...prev, [groupId]: !prev[groupId] }));
```

- [ ] **Step 4: Rewrite the header (lines 51-76)**

Replace:

```javascript
      <header className="page-header border-bottom bg-body d-flex justify-content-between align-items-center">
        <div>
          <h1 className="mb-0 text-3xl font-bold tracking-tight">Settings</h1>
          <p className="mt-1 mb-0 text-sm text-muted-foreground">Platform configuration, governance, and deployment control plane.</p>
        </div>
        <div className="d-flex gap-2 align-items-center">
          <div className="input-group input-group-sm">
            <span className="input-group-text bg-body-tertiary"><Search size={14} /></span>
            <Form.Control 
              placeholder="Search Settings..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ width: "200px" }}
            />
          </div>
          <Button variant="outline-secondary" size="sm" onClick={() => importSettings({})} disabled={loading}>
            <Upload size={14} className="me-1" /> Import Config
          </Button>
          <Button variant="outline-secondary" size="sm" onClick={exportSettings} disabled={loading}>
            <Download size={14} className="me-1" /> Export Config
          </Button>
          <Button variant="outline-danger" size="sm" onClick={() => restoreDefaults("all")} disabled={loading}>
            <RefreshCw size={14} className="me-1" /> Restore Defaults
          </Button>
        </div>
      </header>
```

with:

```javascript
      <header className="flex items-center justify-between gap-3 border-b border-border px-6 py-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">Platform configuration, governance, and deployment control plane.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search Settings..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-[200px] pl-8"
            />
          </div>
          <UIButton variant="outline" size="sm" onClick={() => importSettings({})} disabled={loading}>
            <Upload size={14} /> Import Config
          </UIButton>
          <UIButton variant="outline" size="sm" onClick={exportSettings} disabled={loading}>
            <Download size={14} /> Export Config
          </UIButton>
          <UIButton variant="destructive" size="sm" onClick={() => restoreDefaults("all")} disabled={loading}>
            <RefreshCw size={14} /> Restore Defaults
          </UIButton>
        </div>
      </header>
```

- [ ] **Step 5: Rewrite the grouped nav (lines 80-98)**

Replace:

```javascript
        <Nav className="settings-nav flex-column bg-body-tertiary gui-sidebar" aria-label="Settings sections">
          {settingsItems.map(([id, label, small]) => {
            const Icon = iconMap[id] || Square;
            return (
              <Button
                key={id}
                type="button"
                variant={section === id ? "primary" : "light"}
                className="settings-tab text-start d-flex align-items-center gap-3"
                data-testid={`settings-${id}`}
                aria-current={section === id ? "page" : undefined}
                onClick={() => setSection(id)}
              >
                <Icon size={18} className="flex-shrink-0" />
                <span className="fw-medium">{label}</span>
              </Button>
            );
          })}
        </Nav>
```

with:

```javascript
        <nav className="settings-nav flex flex-col gap-1 border-r border-border bg-sidebar px-2 py-3 gui-sidebar" aria-label="Settings sections">
          {settingsGroups.map((group) => {
            const isCollapsed = !!collapsedGroups[group.id];
            return (
              <div key={group.id} className="mb-1">
                <button
                  type="button"
                  className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground hover:bg-accent"
                  onClick={() => toggleGroup(group.id)}
                  aria-expanded={!isCollapsed}
                >
                  {group.label}
                  <ChevronDown size={14} className={cn("transition-transform", isCollapsed && "-rotate-90")} />
                </button>
                {!isCollapsed && group.sections.map((id) => {
                  const item = settingsItems.find(([itemId]) => itemId === id);
                  if (!item) return null;
                  const [, label] = item;
                  const Icon = iconMap[id] || Square;
                  return (
                    <button
                      key={id}
                      type="button"
                      className={cn(
                        "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm font-medium transition-colors",
                        section === id ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-accent",
                      )}
                      data-testid={`settings-${id}`}
                      aria-current={section === id ? "page" : undefined}
                      onClick={() => setSection(id)}
                    >
                      <Icon size={18} className="flex-shrink-0" />
                      <span>{label}</span>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </nav>
```

- [ ] **Step 6: Rewrite the inspector panel (lines 116-138)**

Replace:

```javascript
        <aside className="settings-inspector-panel gui-inspector" aria-label="Settings inspector">
          <span className="eyebrow">Inspector</span>
          <h2>{activeSetting[1]}</h2>
          
          <div className="mt-4">
            <h6 className="text-uppercase text-muted" style={{ fontSize: "0.75rem", letterSpacing: "1px" }}>Description</h6>
            <p className="small mb-3">{getInspectorText(activeSetting[0]).desc}</p>

            <h6 className="text-uppercase text-muted" style={{ fontSize: "0.75rem", letterSpacing: "1px" }}>Validation Rules</h6>
            <p className="small mb-3 text-success"><CheckCircle2 size={12} className="me-1" />{getInspectorText(activeSetting[0]).validation}</p>

            <h6 className="text-uppercase text-muted" style={{ fontSize: "0.75rem", letterSpacing: "1px" }}>Impact Analysis</h6>
            <p className="small mb-3 text-warning"><ShieldAlert size={12} className="me-1" />{getInspectorText(activeSetting[0]).impact}</p>

            <h6 className="text-uppercase text-muted" style={{ fontSize: "0.75rem", letterSpacing: "1px" }}>Dependencies</h6>
            <div className="small">
              {getInspectorText(activeSetting[0]).deps.map(d => (
                <Badge bg="secondary" className="me-1 mb-1" key={d}>{d}</Badge>
              ))}
              {getInspectorText(activeSetting[0]).deps.length === 0 && <span className="text-muted">None</span>}
            </div>
          </div>
        </aside>
```

with:

```javascript
        <aside className="settings-inspector-panel gui-inspector border-l border-border bg-card px-5 py-5" aria-label="Settings inspector">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Inspector</span>
          <h2 className="mt-1 text-lg font-semibold text-foreground">{activeSetting[1]}</h2>

          <div className="mt-4 space-y-4">
            <div>
              <h6 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Description</h6>
              <p className="mt-1 text-sm text-foreground">{getInspectorText(activeSetting[0]).desc}</p>
            </div>

            <div>
              <h6 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Validation Rules</h6>
              <p className="mt-1 flex items-center gap-1 text-sm text-primary"><CheckCircle2 size={12} />{getInspectorText(activeSetting[0]).validation}</p>
            </div>

            <div>
              <h6 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Impact Analysis</h6>
              <p className="mt-1 flex items-center gap-1 text-sm text-destructive"><ShieldAlert size={12} />{getInspectorText(activeSetting[0]).impact}</p>
            </div>

            <div>
              <h6 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Dependencies</h6>
              <div className="mt-1 flex flex-wrap gap-1">
                {getInspectorText(activeSetting[0]).deps.map(d => (
                  <UIBadge key={d}>{d}</UIBadge>
                ))}
                {getInspectorText(activeSetting[0]).deps.length === 0 && <span className="text-sm text-muted-foreground">None</span>}
              </div>
            </div>
          </div>
        </aside>
```

- [ ] **Step 7: Remove the now-unused `PlaceholderPanel` function if nothing references it**

Run: `grep -n "PlaceholderPanel" frontend-src/src/features/settings/SettingsView.jsx`
If the only match is its own definition (lines 144-162), delete the function. If it's referenced elsewhere, leave it.

- [ ] **Step 8: Build check**

Run: `npm run build`
Expected: succeeds, no missing-import errors.

- [ ] **Step 9: Commit**

```bash
git add frontend-src/src/features/settings/SettingsView.jsx frontend-src/src/lib/constants.js
git commit -m "feat(settings): migrate Settings shell to dashboard tokens with grouped collapsible nav"
```

---

## Task 6: Migrate `GeneralSettings.jsx` to dashboard tokens (migration template)

**Goal:** `GeneralSettings.jsx` is fully rewritten on `Card`/`UIButton`/`Select`/`Switch`/`Input` primitives — this is the template the remaining 9 panels (Task 7) follow.

**Files:**
- Modify: `frontend-src/src/features/settings/GeneralSettings.jsx`

**Acceptance Criteria:**
- [ ] No `react-bootstrap` imports remain.
- [ ] All visual elements (cards, theme/language selects, workspace path input, markdown/testing-mode/telemetry switches, Save Changes button) render using the token-driven primitives and look consistent with the dashboard (dark panel backgrounds, themed accent color, no white Bootstrap cards).
- [ ] The theme dropdint still reads/writes via `theme`/`setTheme` props per Task 3 (not reintroduced into `formData`).

**Verify:** `npm run build` succeeds; visual check in Task 9.

**Steps:**

- [ ] **Step 1: Replace the full file**

Replace the entire contents of `frontend-src/src/features/settings/GeneralSettings.jsx` with:

```javascript
import React, { useState, useEffect } from "react";
import { Monitor, ShieldAlert, BookOpen, Settings2, Save } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";
import { themeOptions } from "../../lib/constants.js";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card.jsx";
import { Button as UIButton } from "@/components/ui/button.jsx";
import { Input } from "@/components/ui/input.jsx";
import { Select } from "@/components/ui/select.jsx";
import { Switch } from "@/components/ui/switch.jsx";

export function GeneralSettings({ theme, setTheme }) {
  const general = useSettingsStore(state => state.general);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.general);

  const [formData, setFormData] = useState({});
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (general) {
      setFormData(general);
      setIsDirty(false);
    }
  }, [general]);

  const handleChange = (key, val) => {
    setFormData(prev => ({ ...prev, [key]: val }));
    setIsDirty(true);
  };

  const handleToggle = (key) => {
    setFormData(prev => ({ ...prev, [key]: !prev[key] }));
    setIsDirty(true);
  };

  const handleSave = async () => {
    for (const [key, val] of Object.entries(formData)) {
      if (general?.[key] !== val) {
        await updateSetting("general", key, val);
      }
    }
    setIsDirty(false);
  };

  return (
    <section className="settings-pane active animate-fade-in space-y-5">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-semibold text-foreground">
            <Settings2 className="text-primary" size={24} />General Configuration
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">Manage platform-wide behavior, aesthetics, and workspace defaults.</p>
        </div>
        <div className="flex items-center gap-3">
          {loading && <span className="text-xs text-muted-foreground">Saving…</span>}
          <UIButton disabled={!isDirty || loading} onClick={handleSave}>
            <Save size={16} /> Save Changes
          </UIButton>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <ShieldAlert size={18} />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-primary/15 p-2 text-primary">
                <Monitor size={20} />
              </div>
              <CardTitle>Aesthetics &amp; UI</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted-foreground">Platform Theme</label>
              <Select value={theme || "rasputin-dark"} onChange={(e) => setTheme?.(e.target.value)}>
                {themeOptions.map(([val, label, desc]) => (
                  <option key={val} value={val}>{label} - {desc}</option>
                ))}
              </Select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted-foreground">Interface Language</label>
              <Select value={formData?.language || "en"} onChange={(e) => handleChange("language", e.target.value)}>
                <option value="en">English (US)</option>
                <option value="es">Español</option>
                <option value="fr">Français</option>
                <option value="ja">日本語</option>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-accent p-2 text-foreground">
                <BookOpen size={20} />
              </div>
              <CardTitle>Environment</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted-foreground">Default Workspace Path</label>
              <Input
                className="font-mono"
                value={formData?.workspacePath || ""}
                onChange={(e) => handleChange("workspacePath", e.target.value)}
                placeholder="/var/rasputin/workspace"
              />
              <p className="mt-1.5 text-xs text-muted-foreground">The root directory for new agent tasks and file outputs.</p>
            </div>

            <div className="space-y-3 rounded-lg border border-border bg-background p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">Markdown Formatting</span>
                <Switch checked={formData?.markdownOutput !== false} onChange={() => handleToggle("markdownOutput")} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">Testing Mode <span className="ml-1 rounded-full bg-accent px-2 py-0.5 text-xs text-muted-foreground">Dry-Run</span></span>
                <Switch checked={!!formData?.testingMode} onChange={() => handleToggle("testingMode")} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-2 border-primary/30 bg-primary/10">
          <CardContent className="flex items-center justify-between py-4">
            <div>
              <h6 className="text-sm font-bold text-foreground">Telemetry &amp; Analytics</h6>
              <p className="mt-0.5 text-xs text-muted-foreground">Help us improve Rasputin by sharing anonymous usage data.</p>
            </div>
            <Switch checked={!!formData?.telemetryEnabled} onChange={() => handleToggle("telemetryEnabled")} />
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Build check**

Run: `npm run build`
Expected: succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend-src/src/features/settings/GeneralSettings.jsx
git commit -m "feat(settings): migrate GeneralSettings to dashboard token primitives"
```

---

## Task 7: Migrate remaining 10 Settings panels to dashboard tokens

**Goal:** `RuntimeSettings.jsx`, `SecuritySettings.jsx`, `ModelSettings.jsx`, `DeploymentSettings.jsx`, `IntegrationSettings.jsx`, `ResourceSettings.jsx`, `NotificationSettings.jsx`, `AuditSettings.jsx`, `DiagnosticsSettings.jsx`, and `AboutSettings.jsx` are all rewritten on the same primitives as `GeneralSettings.jsx`, with no react-bootstrap left anywhere in `frontend-src/src/features/settings/`.

**Files:**
- Modify: `frontend-src/src/features/settings/RuntimeSettings.jsx`
- Modify: `frontend-src/src/features/settings/SecuritySettings.jsx`
- Modify: `frontend-src/src/features/settings/ModelSettings.jsx`
- Modify: `frontend-src/src/features/settings/DeploymentSettings.jsx`
- Modify: `frontend-src/src/features/settings/IntegrationSettings.jsx`
- Modify: `frontend-src/src/features/settings/ResourceSettings.jsx`
- Modify: `frontend-src/src/features/settings/NotificationSettings.jsx`
- Modify: `frontend-src/src/features/settings/AuditSettings.jsx`
- Modify: `frontend-src/src/features/settings/DiagnosticsSettings.jsx`
- Modify: `frontend-src/src/features/settings/AboutSettings.jsx`

**Acceptance Criteria:**
- [ ] `grep -rn "react-bootstrap" frontend-src/src/features/settings/` returns no matches.
- [ ] Every panel preserves its existing props, state shape, and `updateSetting(domain, key, value)` calls exactly as before — only the markup/styling changes, not the data flow.
- [ ] `ModelSettings.jsx` still receives and uses `models`, `modeModelOverrides`, `setModeModelOverride` exactly as before.
- [ ] `DiagnosticsSettings.jsx` and `AboutSettings.jsx` (which don't use `useSettingsStore`) keep their existing local-state/no-state behavior — only markup changes.

**Verify:** `grep -rn "react-bootstrap" frontend-src/src/features/settings/` → no output. `npm run build` → succeeds.

**Mapping table (apply this translation to every file, same rules used in Task 6):**

| react-bootstrap | Replacement |
|---|---|
| `<Card>` / `<Card.Body>` / `<Card.Header>` | `<Card>` / `<CardContent>` / `<CardHeader>` + `<CardTitle>` from `@/components/ui/card.jsx` |
| `<Row>` / `<Col md={N}>` | `<div className="grid grid-cols-1 gap-4 md:grid-cols-2">` (or `md:grid-cols-{N}` matching the original column split) with plain `<div>` children |
| `<Form.Select>` | `<Select>` from `@/components/ui/select.jsx` |
| `<Form.Control>` | `<Input>` from `@/components/ui/input.jsx` |
| `<Form.Check type="switch">` | `<Switch>` from `@/components/ui/switch.jsx` |
| `<Form.Check type="radio">` | native `<input type="radio">` styled with `className="h-4 w-4 accent-primary"` |
| `<Badge bg="...">` | `<Badge variant="...">` from `@/components/ui/badge.jsx` (map `bg="secondary"`→`variant="default"`, `bg="success"`/`"primary"`→`variant="accent"` or `"up"`, `bg="danger"`→`variant="down"`, `bg="warning"`→`variant="muted"`) |
| `<Button variant="...">` | `<UIButton variant="...">` from `@/components/ui/button.jsx` (map `outline-secondary`/`outline-danger`→`outline`, `primary`→`default`, `danger`→`destructive`) |
| `<Spinner animation="border" size="sm">` | `<span className="text-xs text-muted-foreground">Loading…</span>` or omit if purely decorative |
| `<ProgressBar now={N} />` (ResourceSettings only) | `<div className="h-2 w-full rounded-full bg-muted"><div className="h-2 rounded-full bg-primary" style={{ width: \`${N}%\` }} /></div>` |
| `<Table>` (AuditSettings only) | plain `<table className="w-full text-sm">` with `<thead>`/`<tbody>` and `className="border-b border-border"` on `<tr>` |
| `<InputGroup>` (IntegrationSettings only) | `<div className="flex items-center gap-2">` wrapping the `<Input>` and any trailing icon/button |
| `<Alert variant="...">` (DiagnosticsSettings only) | `<div className="rounded-lg border px-4 py-3 text-sm">` with border/text color matching the original variant (success→`border-primary/30 text-primary`, danger→`border-destructive/30 text-destructive`) |
| Bootstrap utility classes (`bg-body-tertiary`, `text-body-secondary`, `text-muted`, `fw-bold`, `me-2`, `d-flex`, `mb-3`, etc.) | Tailwind equivalents (`bg-card`/`bg-background`, `text-muted-foreground`, `font-bold`, `gap-2`, `flex`, `mb-3`, etc.) — match spacing/weight intent, exact pixel values don't need to match the original Bootstrap scale |

**Steps:**

- [ ] **Step 1: Migrate `RuntimeSettings.jsx`**

Read the current file in full first. Apply the mapping table above. Preserve every `useSettingsStore`/`updateSetting`/local-state call exactly — only change JSX tags and class names. Keep the `Form.Range` slider as a native `<input type="range" className="w-full accent-primary" />`.

Run: `npm run build` after this file to catch errors early rather than batching all 10.

- [ ] **Step 2: Migrate `SecuritySettings.jsx`**

Same process. Preserve the `rotateSecrets` call and the privilege-matrix table (convert to the plain `<table>` pattern from the mapping table).

- [ ] **Step 3: Migrate `ModelSettings.jsx`**

Same process. Preserve the `models`/`modeModelOverrides`/`setModeModelOverride` prop usage and the radio-button engine selector exactly (convert radios per the mapping table, keep the same `name`/`value`/`onChange` wiring).

- [ ] **Step 4: Migrate `DeploymentSettings.jsx`**

Same process. The clickable provider-selector `Card`s become `<Card className={cn("cursor-pointer", isSelected && "border-primary")} onClick={...}>` — preserve the click handler and selected-state logic exactly.

- [ ] **Step 5: Migrate `IntegrationSettings.jsx`**

Same process. Preserve `testConnection` and the conditional token-input fields exactly; convert `InputGroup` per the mapping table.

- [ ] **Step 6: Migrate `ResourceSettings.jsx`**

Same process. Convert the `Form.Range` sliders and `ProgressBar` per the mapping table; preserve `cpuLimit`/`ramLimit` state and `handleBlur` exactly.

- [ ] **Step 7: Migrate `NotificationSettings.jsx`**

Same process. Preserve all `handleToggle` calls and the conditional SMTP/webhook form sections exactly.

- [ ] **Step 8: Migrate `AuditSettings.jsx`**

Same process. Convert the `Table` per the mapping table; preserve `handleToggle`/`handleSelect` exactly.

- [ ] **Step 9: Migrate `DiagnosticsSettings.jsx`**

Same process. This file has no `useSettingsStore` usage — preserve its local `running`/`results` state and `runDiagnostics` function exactly; only convert the `Alert`/`Card`/`Button` markup.

- [ ] **Step 10: Migrate `AboutSettings.jsx`**

Same process. This is purely presentational — convert the hero `Card`, the two info `Card`s, and the link buttons (`<a className="btn btn-light ...">` → `<a className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground hover:bg-accent">`).

- [ ] **Step 11: Full verification sweep**

Run: `grep -rn "react-bootstrap" frontend-src/src/features/settings/`
Expected: no output.

Run: `npm run build`
Expected: succeeds with no errors.

- [ ] **Step 12: Commit**

```bash
git add frontend-src/src/features/settings/
git commit -m "feat(settings): migrate remaining 10 settings panels to dashboard token primitives"
```

---

## Task 8: Add `pinned` field to sessions (backend) and pin-toggle action (frontend)

**Goal:** Sessions support a `pinned` boolean end-to-end: schema migration, hub method, API route, and a frontend callback wired into `App.jsx`/`Sidebar.jsx`.

**Files:**
- Modify: `backend/core/runtime_store.py` (schema + migration, near the existing `folder` migration)
- Modify: `backend/engine/agent.py` (add `set_session_pinned` mirroring `assign_session_folder`)
- Modify: `backend/api/agent.py` (add `SessionPinnedIn` + `/api/sessions/{id}/pinned` route, mirroring the folder route)
- Modify: `frontend-src/src/app/App.jsx` (add `pinSession` function, mirroring `assignSessionFolder`; pass it to `<Sidebar>`)
- Test: `tests/testBackendSmoke.py`

**Acceptance Criteria:**
- [ ] `sessions` table has a `pinned INTEGER NOT NULL DEFAULT 0` column, added via the same migration-guard pattern used for `folder`.
- [ ] `POST /api/sessions/{id}/pinned` with `{"pinned": true}` sets the field and returns the updated session.
- [ ] `App.jsx` has a `pinSession(sessionId, pinned)` function calling that endpoint, refreshing sessions, and is passed to `<Sidebar>` via `sidebarProps`.

**Verify:** `python -m pytest tests/testBackendSmoke.py -v -k pinned` → PASS

**Steps:**

- [ ] **Step 1: Find the exact folder migration line to mirror**

Run: `grep -n "ALTER TABLE sessions ADD COLUMN folder" backend/core/runtime_store.py`

Read the 10 lines around that match to see the exact migration-guard pattern (likely a `session_columns` set check before `ALTER TABLE`).

- [ ] **Step 2: Add the `pinned` column migration**

Immediately after the `folder` migration block found in Step 1, add (adjust variable names to match what Step 1 revealed — the guard variable is likely named `session_columns` or similar):

```python
        if "pinned" not in session_columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
```

- [ ] **Step 3: Write the failing backend test**

Add to `tests/testBackendSmoke.py` (match existing fixture/client style in that file):

```python
def test_session_pin_toggle(client):
    create_resp = client.post("/api/sessions", json={"title": "Pin test session"})
    session_id = create_resp.json().get("data", create_resp.json())["id"]

    pin_resp = client.post(f"/api/sessions/{session_id}/pinned", json={"pinned": True})
    assert pin_resp.status_code == 200
    pinned_session = pin_resp.json().get("data", pin_resp.json())
    assert pinned_session["pinned"] is True

    unpin_resp = client.post(f"/api/sessions/{session_id}/pinned", json={"pinned": False})
    assert unpin_resp.status_code == 200
    unpinned_session = unpin_resp.json().get("data", unpin_resp.json())
    assert unpinned_session["pinned"] is False
```

(If `POST /api/sessions` isn't the actual session-creation route, grep for the real one — e.g. `grep -n "sessions_router.post" backend/api/agent.py` — and adjust the test's setup call accordingly before proceeding.)

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/testBackendSmoke.py -v -k pin_toggle`
Expected: FAIL — 404, no `/pinned` route exists yet.

- [ ] **Step 5: Add the hub method in `backend/engine/agent.py`**

Immediately after `assign_session_folder` (the method found at the location reported in research — confirm with `grep -n "def assign_session_folder" backend/engine/agent.py`), add:

```python
    def set_session_pinned(self, session_id, pinned=False):
        with store._lock, store.connect() as conn:
            session = conn.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not session:
                raise ValueError("session missing")
            conn.execute(
                "UPDATE sessions SET pinned=?, updated_at=? WHERE id=?",
                (1 if pinned else 0, store.now(), session_id),
            )
            conn.commit()
        return self.session(session_id)
```

- [ ] **Step 6: Add the API route in `backend/api/agent.py`**

Immediately after the `SessionFolderIn`/`session_folder_post` block (confirm exact location with `grep -n "SessionFolderIn\|session_folder_post" backend/api/agent.py`), add:

```python
class SessionPinnedIn(CamelModel):
    pinned: bool

@sessions_router.post("/sessions/{session_id}/pinned")
async def session_pinned_post(session_id: str, req: SessionPinnedIn, _user=Depends(current_user)):
    audit.log("session_pinned_changed", {"session_id": session_id, "pinned": req.pinned})
    return ok(hub.set_session_pinned(session_id, req.pinned))
```

- [ ] **Step 7: Confirm the session serializer returns `pinned`**

Run: `grep -n "def session(self" backend/engine/agent.py` and read that method. If it builds an explicit dict of fields (rather than `dict(row)`), add `"pinned": bool(row["pinned"])` to that dict, matching how `"folder"` is already included there.

- [ ] **Step 8: Run test to verify it passes**

Run: `python -m pytest tests/testBackendSmoke.py -v -k pin_toggle`
Expected: PASS

- [ ] **Step 9: Add `pinSession` to `App.jsx`**

Immediately after the existing `assignSessionFolder` function (confirm location with `grep -n "async function assignSessionFolder" frontend-src/src/app/App.jsx`), add:

```javascript
  async function pinSession(sessionId, pinned) {
    if (!sessionId) return null;
    const detail = await postJson(`/api/sessions/${sessionId}/pinned`, { pinned: !!pinned });
    await loadChatFolders();
    if (selectedSession?.session?.id === sessionId) setSelectedSession(detail);
    return detail;
  }
```

- [ ] **Step 10: Pass `pinSession` to `<Sidebar>`**

In the `sidebarProps` object passed to `<AppShell>` (confirm exact location with `grep -n "assignSessionFolder," frontend-src/src/app/App.jsx`), add `pinSession,` on its own line immediately after the existing `assignSessionFolder,` line.

- [ ] **Step 11: Commit**

```bash
git add backend/core/runtime_store.py backend/engine/agent.py backend/api/agent.py frontend-src/src/app/App.jsx tests/testBackendSmoke.py
git commit -m "feat(sessions): add pinned field with API route and frontend pinSession action"
```

---

## Task 9: Add pin-toggle button and Pinned/date grouping to `Sidebar.jsx`

**Goal:** Recent Chats renders a Pinned group above date-based groups (Today/Yesterday/This Week/Older), and each chat row has a pin/unpin icon button.

**Files:**
- Modify: `frontend-src/src/components/Sidebar.jsx`

**Acceptance Criteria:**
- [ ] `Sidebar` accepts a new `pinSession` prop.
- [ ] Each session row has a pin-toggle icon button (filled star/pin icon when `session.pinned` is true, outline when false) that calls `pinSession(session.id, !session.pinned)`.
- [ ] `visibleSessions` (or a new derived value) is grouped into Pinned / Today / Yesterday / This Week / Older; existing search/folder filtering and sort order still apply within each group.
- [ ] Empty groups are not rendered (no "Today" header with zero rows).
- [ ] The existing "no saved chats yet" empty state still shows when the fully-filtered list (across all groups) is empty.

**Verify:** `npm run build` succeeds; manual check confirms grouping and pin toggle in Task 10.

**Steps:**

- [ ] **Step 1: Add the `Pin` icon import**

In `frontend-src/src/components/Sidebar.jsx`, add `Pin` to the existing `lucide-react` import (lines 2-17):

```javascript
import {
  Activity,
  Brain,
  ChevronLeft,
  FileText,
  Folder,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  Pin,
  Plus,
  Search,
  Satellite,
  Scale,
  Settings,
  Sparkles,
} from "lucide-react";
```

- [ ] **Step 2: Accept the `pinSession` prop**

In the `Sidebar` function signature, add `pinSession,` immediately after the existing `assignSessionFolder,` parameter.

- [ ] **Step 3: Add a date-grouping helper function**

Immediately after the existing `sessionTime` function (after line 298), add:

```javascript
function groupSessions(sessions) {
  const now = Date.now();
  const startOfToday = new Date().setHours(0, 0, 0, 0);
  const startOfYesterday = startOfToday - 86400000;
  const startOfWeek = startOfToday - 6 * 86400000;

  const groups = { pinned: [], today: [], yesterday: [], thisWeek: [], older: [] };
  for (const session of sessions) {
    if (session.pinned) {
      groups.pinned.push(session);
      continue;
    }
    const time = sessionTime(session) * (sessionTime(session) < 1e12 ? 1000 : 1);
    if (time >= startOfToday) groups.today.push(session);
    else if (time >= startOfYesterday) groups.yesterday.push(session);
    else if (time >= startOfWeek) groups.thisWeek.push(session);
    else groups.older.push(session);
  }
  return groups;
}
```

(Note: `sessionTime` returns whatever unit `updatedAt`/`createdAt` are stored in. Verify the unit before relying on the `*1000` guess in this helper — run `grep -n "updated_at\|updatedAt" backend/engine/agent.py` to confirm whether the backend serializes Unix seconds or milliseconds, and adjust the multiplier in this function to match. If seconds, keep the guard as written; if already milliseconds, simplify to `const time = sessionTime(session);` with no multiplier.)

- [ ] **Step 4: Apply grouping after the existing `visibleSessions` memo**

Immediately after the `visibleSessions` useMemo (after line 80), add:

```javascript
  const sessionGroups = useMemo(() => groupSessions(visibleSessions), [visibleSessions]);
  const groupOrder = [
    ["pinned", "Pinned"],
    ["today", "Today"],
    ["yesterday", "Yesterday"],
    ["thisWeek", "This Week"],
    ["older", "Older"],
  ];
```

- [ ] **Step 5: Rewrite the session-list JSX (lines 213-260) to render grouped sections**

Replace:

```javascript
          <div className="sidebar-session-list" data-testid="sidebar-session-list">
            {visibleSessions.map((session) => {
              const active = session.id === activeSessionId;
              return (
                <div
                  key={session.id}
                  className={`sidebar-session-row ${active ? "is-active" : ""}`}
                  data-testid="sidebar-session-row"
                >
                  <button
                    className="sidebar-session"
                    type="button"
                    title={session.title}
                    aria-current={active ? "page" : undefined}
                    onClick={() => resumeSession?.(session.id)}
                  >
                    <span>{session.title || "Untitled chat"}</span>
                    <small>{session.mode || "chat"} / {displayWorkspaceName(session.workspace)}</small>
                  </button>
                  <div className="sidebar-session-actions">
                    <span className="sidebar-session-folder-badge" title={session.folder || "Unfiled"}>
                      {session.folder || "Unfiled"}
                    </span>
                    <label className="visually-hidden" htmlFor={`sessionFolder-${session.id}`}>Move chat to folder</label>
                    <select
                      id={`sessionFolder-${session.id}`}
                      className="sidebar-session-folder"
                      data-testid="sidebar-session-folder"
                      value={session.folder || ""}
                      aria-label={`Move ${session.title || "Untitled chat"} to folder`}
                      onChange={(event) => assignSessionFolder?.(session.id, event.target.value)}
                    >
                      <option value="">Move: Unfiled</option>
                      {folders.map((folder) => (
                        <option key={folder.id} value={folder.name}>Move: {folder.name}</option>
                      ))}
                    </select>
                  </div>
                </div>
              );
            })}
            {!visibleSessions.length && (
              <button className="sidebar-session is-empty" type="button" onClick={newTask}>
                <span>No saved chats yet</span>
                <small>Start with New Chat</small>
              </button>
            )}
          </div>
```

with:

```javascript
          <div className="sidebar-session-list" data-testid="sidebar-session-list">
            {groupOrder.map(([groupKey, groupLabel]) => {
              const groupSessionsList = sessionGroups[groupKey];
              if (!groupSessionsList || !groupSessionsList.length) return null;
              return (
                <div key={groupKey} className="sidebar-session-group">
                  <div className="sidebar-session-group-label">{groupLabel}</div>
                  {groupSessionsList.map((session) => {
                    const active = session.id === activeSessionId;
                    return (
                      <div
                        key={session.id}
                        className={`sidebar-session-row ${active ? "is-active" : ""}`}
                        data-testid="sidebar-session-row"
                      >
                        <button
                          className="sidebar-session"
                          type="button"
                          title={session.title}
                          aria-current={active ? "page" : undefined}
                          onClick={() => resumeSession?.(session.id)}
                        >
                          <span>{session.title || "Untitled chat"}</span>
                          <small>{session.mode || "chat"} / {displayWorkspaceName(session.workspace)}</small>
                        </button>
                        <div className="sidebar-session-actions">
                          <button
                            type="button"
                            className="sidebar-session-pin"
                            data-testid="sidebar-session-pin"
                            aria-pressed={!!session.pinned}
                            aria-label={session.pinned ? `Unpin ${session.title || "Untitled chat"}` : `Pin ${session.title || "Untitled chat"}`}
                            title={session.pinned ? "Unpin chat" : "Pin chat"}
                            onClick={() => pinSession?.(session.id, !session.pinned)}
                          >
                            <Pin size={14} fill={session.pinned ? "currentColor" : "none"} />
                          </button>
                          <span className="sidebar-session-folder-badge" title={session.folder || "Unfiled"}>
                            {session.folder || "Unfiled"}
                          </span>
                          <label className="visually-hidden" htmlFor={`sessionFolder-${session.id}`}>Move chat to folder</label>
                          <select
                            id={`sessionFolder-${session.id}`}
                            className="sidebar-session-folder"
                            data-testid="sidebar-session-folder"
                            value={session.folder || ""}
                            aria-label={`Move ${session.title || "Untitled chat"} to folder`}
                            onChange={(event) => assignSessionFolder?.(session.id, event.target.value)}
                          >
                            <option value="">Move: Unfiled</option>
                            {folders.map((folder) => (
                              <option key={folder.id} value={folder.name}>Move: {folder.name}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })}
            {!visibleSessions.length && (
              <button className="sidebar-session is-empty" type="button" onClick={newTask}>
                <span>No saved chats yet</span>
                <small>Start with New Chat</small>
              </button>
            )}
          </div>
```

- [ ] **Step 6: Add minimal CSS for the new group label and pin button**

Find the existing `.sidebar-session-folder-badge`/`.sidebar-session-actions` rules (search `grep -n "sidebar-session-folder-badge" frontend-src/src/styles/*.css` to locate the file), and add adjacent to them:

```css
.sidebar-session-group-label {
  padding: 6px 10px 4px;
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--dash-muted);
}

.sidebar-session-pin {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: var(--dash-muted);
  border-radius: 6px;
  cursor: pointer;
}

.sidebar-session-pin:hover {
  background: var(--dash-panel-hover);
  color: var(--dash-accent);
}

.sidebar-session-pin[aria-pressed="true"] {
  color: var(--dash-accent);
}
```

- [ ] **Step 7: Build check**

Run: `npm run build`
Expected: succeeds.

- [ ] **Step 8: Commit**

```bash
git add frontend-src/src/components/Sidebar.jsx frontend-src/src/styles/*.css
git commit -m "feat(sidebar): add pin toggle and Pinned/date grouping to Recent Chats"
```

---

## Task 10: End-to-end manual verification

**USER-ORDERED GATE — NON-SKIPPABLE.** This task was requested by the user in the current conversation. It MUST NOT be closed by walking around it, by declaring it "verified inline", or by substituting a cheaper check. Close only after every item in `acceptanceCriteria` has been re-validated independently, with output captured.

**Goal:** Confirm in a real running browser (not just `npm run build`) that the theme dropdown stays in sync after reload, all 14 themes visually apply to Settings, the grouped Settings nav works, and Recent Chats shows pin/date grouping correctly.

**Files:** none (verification only)

**Acceptance Criteria:**
- [ ] With `npm run dev` running and proxied to the backend (per `vite.config.mjs`'s `server.proxy["/api"]` entry), switching the Platform Theme dropdown immediately re-themes both the dashboard/sidebar AND the Settings panel itself (cards/buttons/switches pick up the new accent color).
- [ ] After selecting a non-default theme and hard-reloading the page, the Settings dropdown shows the same theme that's visually applied — no revert to "Rasputin Dark".
- [ ] The Settings section nav shows 4 collapsible groups (Platform/Security/Operations/System); clicking a group header collapses/expands it; clicking a section navigates correctly.
- [ ] `grep -rn "react-bootstrap" frontend-src/src/features/settings/` returns no matches (re-run, don't trust Task 7's earlier pass blindly).
- [ ] Pinning a chat in Recent Chats moves it into a "Pinned" group above the date groups; unpinning moves it back to its date group.
- [ ] Creating/viewing chats from different time ranges (if test data allows) shows them split across Today/Yesterday/This Week/Older correctly, or at minimum confirms today's chats land in "Today" and the grouping logic doesn't crash on the existing smoke-test session data.

**Verify:** Manual Playwright-driven walkthrough (see steps) with screenshots captured at each acceptance criterion.

**Steps:**

- [ ] **Step 1: Start the stack**

Ensure the backend container is running (`docker ps` should show `rasputin-rasputin-wrapper-1` healthy) and start the frontend dev server: `npm run dev` (background). Confirm `vite.config.mjs` still has the `server.proxy` block added during this session's earlier investigation — if it was reverted, re-add:

```javascript
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8787",
    },
  },
```

- [ ] **Step 2: Navigate and switch themes**

Use Playwright to navigate to `http://127.0.0.1:5173/static/#settings/general`, select a non-default theme (e.g. `ocean-abyss`) from the Platform Theme dropdown, and screenshot. Confirm the Settings cards/buttons/switches show the new accent color, not Bootstrap white/blue.

- [ ] **Step 3: Reload and re-check the dropdown**

Hard-navigate to the same URL again (full reload). Screenshot. Confirm the dropdown still shows `ocean-abyss` and the visual theme matches.

- [ ] **Step 4: Test the grouped nav**

Screenshot the Settings section nav. Confirm 4 group headers (Platform/Security/Operations/System) are visible, each listing the correct sections. Click a group header, confirm it collapses; click again, confirm it expands. Click into 2-3 different sections (e.g. Security, Diagnostics) and confirm each renders without errors and without any white Bootstrap card visible.

- [ ] **Step 5: Re-run the react-bootstrap grep**

Run: `grep -rn "react-bootstrap" frontend-src/src/features/settings/`
Expected: no output. If anything matches, go back and finish migrating that file before proceeding.

- [ ] **Step 6: Test Recent Chats pin + grouping**

Navigate to the dashboard. In the sidebar's Recent Chats, click the pin icon on a chat. Screenshot — confirm it now appears under a "Pinned" header above the date groups. Click again to unpin — confirm it returns to its date group (Today/Yesterday/This Week/Older).

- [ ] **Step 7: Capture and report results**

Save all screenshots from Steps 2-6. Write a short summary confirming each acceptance criterion above with a pass/fail and the corresponding screenshot filename. If any criterion fails, do not close this task — fix the underlying issue (revisit the relevant earlier task) and re-run this task's steps from the top.

```json:metadata
{"userGate": true, "tags": ["user-gate"], "files": [], "verifyCommand": "grep -rn \"react-bootstrap\" frontend-src/src/features/settings/", "acceptanceCriteria": ["Theme dropdown stays in sync after reload", "Settings panel visually re-themes with all 14 themes, not just dashboard", "Settings nav shows 4 collapsible groups and navigates correctly", "No react-bootstrap imports remain in frontend-src/src/features/settings/", "Pinned chats appear in a Pinned group above date groups", "Date grouping (Today/Yesterday/This Week/Older) renders without errors"], "modelTier": "standard"}
```

---

## Plan self-review notes

- **Spec coverage:** Theme sync fix → Tasks 1-3. Settings visual migration → Tasks 4-7. Settings structural grouping → Task 5. Recent Chats pin + date grouping → Tasks 8-9. End-to-end verification → Task 10. The spec's "Theming audit pass" (item 4, opportunistic) is intentionally not a separate task — Task 10's Step 5 grep re-check covers the Settings-specific case; broader app-wide audit was scoped as "fix opportunistically if found" in the spec, not a committed deliverable, so no task forces it.
- **Type/name consistency check:** `pinSession(sessionId, pinned)` (Task 8 Step 9, Task 9 Step 5), `setTheme`/`theme` props (Tasks 3, 5, 6), `settingsGroups` (Task 5 Step 1, consumed in Task 5 Step 5) — all consistent across tasks.
- **Placeholder scan:** no TBD/TODO markers; the one spot requiring runtime confirmation (Task 9 Step 3's timestamp unit) is flagged explicitly as a verify-before-trusting step with the exact grep to run, not a vague "handle appropriately".
