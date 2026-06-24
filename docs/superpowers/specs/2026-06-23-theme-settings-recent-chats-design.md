# Theme Sync, Settings Redesign, Recent Chats — Design

## Context

The `claude-ui` branch migrated the dashboard/sidebar to Tailwind v4 + shadcn (CSS-first tokens in `theme.css`/`dashboard.css`, driven by `--base-bg`/`--base-text`/`--base-accent` injected per-theme by `frontend-src/index.html`). The Settings panel never migrated and is still built in react-bootstrap, so it doesn't pick up theme colors at all. Separately, theme state is split across two backend stores that can silently drift.

Confirmed live via Playwright against `npm run dev` (proxied to the existing Docker backend on :8787):
- Switching to a non-default theme (Cyberpunk Neon) re-themes the sidebar/dashboard correctly but leaves Settings' cards/buttons/badges in plain Bootstrap white/blue.
- After a hard reload, the sidebar stays on the selected theme (reads `localStorage`) but the Settings dropdown reverts to "Rasputin Dark" (reads a separate, stale `/api/settings` store that only updates on explicit Save).
- `backend/core/preferences.py`'s theme allow-list has only 9 of the 14 current theme keys; the 5 missing ones (`cyberpunk-neon`, `ocean-abyss`, `hacker-matrix`, `crimson-forge`, `nord-frost`) get silently reset to `rasputin-light` if they round-trip through that store.

## 1. Theme sync fix — single source of truth

**Problem:** `App.jsx` owns live `theme`/`setTheme` state, persisted to `localStorage` and POSTed to `/api/preferences`. `GeneralSettings.jsx` independently reads/writes `general.theme` via the Zustand `settingsStore` against `/api/settings`, only on explicit Save. Two stores, two triggers, guaranteed drift.

**Fix:**
- Remove `theme` from `DEFAULT_SETTINGS["general"]` in `backend/core/settings_api.py`.
- Remove `theme` handling from `GeneralSettings.jsx`'s form state entirely (`formData.theme`, and its participation in the dirty/`isDirty` tracking that gates the Save Changes button). The Platform Theme control becomes a direct, uncommitted consumer of the `theme`/`setTheme` props already passed down from `App.jsx` — selecting an option calls `setTheme(val)` immediately, same as if changed elsewhere. It no longer factors into Save Changes at all; Save Changes only commits the remaining `general` fields (language, workspace path, toggles).
- Fix `THEMES` in `backend/core/preferences.py` to include all 14 current theme keys from `frontend-src/src/lib/constants.js`'s `themeOptions`.

**Result:** one state (`App.jsx`'s `theme`), one persistence path (`localStorage` + `/api/preferences`). The Settings dropdown always reflects the live theme; no separate desync path exists.

## 2. Settings redesign

### Structure: grouped section nav

Replace the flat 11-item section list with 4 collapsible groups, mirroring the main sidebar's existing Workspace/Fleet/Knowledge grouping pattern:

- **Platform** — General, Models, Integrations
- **Security** — Security, Audit
- **Operations** — Runtime, Deployments, Resources, Notifications
- **System** — Diagnostics, About

Groups are independently collapsible/expandable (local UI state, not persisted). Clicking a section within a group navigates as today (`settingsSection` state, `#settings/<section>` hash route) — no change to the routing/data model, only to how the nav list is grouped and rendered.

### Visual: migrate off react-bootstrap onto dashboard tokens

All Settings section components (`GeneralSettings.jsx`, `RuntimeSettings.jsx`, `SecuritySettings.jsx`, `ModelSettings.jsx`, `DeploymentSettings.jsx`, `IntegrationSettings.jsx`, `ResourceSettings.jsx`, `NotificationSettings.jsx`, `AuditSettings.jsx`, `DiagnosticsSettings.jsx`, `AboutSettings.jsx`) currently use `react-bootstrap` (`Card`, `Form.Select`, `Form.Control`, `Badge`, `Button`, Bootstrap utility classes like `bg-body-tertiary`, `text-body-secondary`).

Replace with the same `.tw`/`--dash-*` token-driven markup/classes used by the dashboard surfaces (`dash-panel`, `dash-border`, native `<select>`/`<input>` styled via the token system or existing shadcn primitives where available). `SettingsView.jsx`'s outer shell, the inspector panel, and the grouped nav also move onto the token system so the whole Settings surface is visually one app with the dashboard, themed identically across all 14 themes.

### Layout: unchanged structurally

Keep the existing 3-column layout — grouped section nav | content | inspector panel (description / validation rules / impact analysis / dependencies). Only the visual skin and the nav grouping change; the inspector panel's content and behavior are preserved as-is.

## 3. Recent Chats: pin + date grouping

**Data model:** add `pinned: boolean` (default `false`) to the session object, persisted the same way `folder` already is (backend session store, same API surface used for folder assignment).

**Rendering order in the sidebar list:**
1. **Pinned** group — all chats with `pinned: true`, regardless of `updatedAt`.
2. **Today**
3. **Yesterday**
4. **This Week** (last 7 days, excluding today/yesterday)
5. **Older**

Within each group, existing sort order (newest/oldest/A-Z) and the existing search/folder filters still apply — grouping is a presentation layer on top of the already-filtered `visibleSessions` list, not a replacement for filtering.

**UI:** add a pin/unpin icon button per chat row, consistent placement and styling with the existing per-row folder-assignment control. Toggling calls a new `pinSession`/equivalent API action mirroring how folder assignment is already wired.

## 4. Theming audit pass

After the Settings migration lands, do a quick sweep (not a separate large effort) for any other surfaces — modals, toasts, dialogs — still hard-coded to Bootstrap defaults and silently ignoring the 14-theme system. Fix opportunistically as part of this work if anything turns up; don't scope-expand into a standalone migration if nothing does.

## Out of scope

- No new themes added.
- No change to the chat/folder data model beyond adding `pinned`.
- No change to the Settings inspector panel's content/logic, only its visual skin.
- No backend auth changes (the `RASPUTIN_LOCALHOST_BYPASS` dev flag used for local verification during this work is unrelated to the shipped feature set).
