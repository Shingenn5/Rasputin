# CSS Ownership and Extraction Map

This document records Rasputin's stylesheet cascade and the ownership rules for
breaking up the legacy CSS safely. It is a refactoring contract, not permission
to change visual behavior. Every extraction must preserve selector text,
declaration text, cascade position where relevant, responsive rules, and reduced
motion behavior.

## Current cascade

`frontend-src/src/main.jsx` loads the global styles in this order:

1. `theme.css` — design tokens, Tailwind bridge, and theme-specific variables.
2. Bootstrap's compiled CSS — external legacy component layer.
3. `rasputin.css` — accumulated global shell, feature, chat, WarSat, and
   primitive rules.
4. `dashboard.css` — dashboard shell and current typography adjustments.
5. `interface.css` — late-cascade workstation and legacy-surface refinement.
6. `secondary-views.css` — shared secondary-view consolidation.
7. `motion.css` — final motion-mode and reduced-motion policy.

Feature-owned styles are imported by their owning React modules:

| Stylesheet | Owner |
| --- | --- |
| `models-workspace-v3.css` | `features/models/ModelsView.jsx` |
| `history-workspace-v3.css` | `features/tasks/TasksView.jsx` |
| `settings-workspace-v3.css` | `features/settings/SettingsView.jsx` |

Feature-local styles must remain scoped under a stable feature root such as
`.models-workspace-v3`; otherwise lazy chunk timing can create accidental
cascade differences.

## File ownership

| File | Intended responsibility | Current warning |
| --- | --- | --- |
| `theme.css` | Tokens and theme mappings only | Do not add feature layout |
| `rasputin.css` | Transitional global compatibility layer | Largest maintenance hotspot; no new feature blocks |
| `dashboard.css` | Dashboard shell and dashboard-specific layout | Do not absorb unrelated view styling |
| `interface.css` | Shared workstation presentation | Contains later overrides; extraction requires cascade checks |
| `secondary-views.css` | Shared secondary-view layout and hierarchy | Keep shared rather than copying into features |
| `motion.css` | Motion preferences and global reduced-motion behavior | Must remain last in the global cascade |
| Feature CSS files | One feature root and its responsive states | Avoid unscoped global selectors |

## `rasputin.css` extraction boundaries

The line numbers below describe the 2026-08-28 baseline. Run
`scripts/audit_repository.py` and re-inspect section markers before moving a
later block because earlier extractions will shift these numbers.

| Baseline range | Boundary | Target |
| --- | --- | --- |
| 1–10,602 | Tokens, shell, legacy feature views, chat, responsive rules | Split only after selector-family inventory |
| 10,603–10,856 | Command Center foundation | `command-center.css` |
| 10,857–11,150 | Workstation v2 foundations and per-view grids | `workstation-layout.css` |
| 11,151–11,230 | Trials and workspace explorer adjustments | Feature-owned files after overlap review |
| 11,231–12,133 | WarSat deployment/runtime/discovery dashboards | `warsat.css` |
| 12,134–12,222 | View/list motion additions | Merge into `motion.css` after reduced-motion comparison |
| 12,223–12,413 | Modal and drawer primitives | `overlays.css` — first extraction |
| 12,414–12,465 | Chat autogrow and avatar polish | Future chat primitive file |
| 12,466–12,588 | First-run onboarding overlay | `onboarding.css` |
| 12,589–13,283 | Header model state, composer tools, attachments, queue, command menu | `chat-controls.css` |
| 13,284–end | Assistant control plane and responsive adjustments | `assistant.css` after selector review |

## Extraction rules

1. Move complete blocks, including their keyframes and media queries. Never
   split an open `@media` block or move only the desktop half of a component.
2. Preserve the global import order. A new file must occupy the same effective
   cascade position unless every selector is uniquely namespaced and the changed
   position is explicitly verified.
3. Search every moved selector in all stylesheets and JSX. Record any duplicate
   or later override before moving it.
4. Build with Vite and compare the generated CSS for missing rules or unresolved
   imports.
5. Verify the affected interface in the running isolated app at desktop and
   narrow widths, using keyboard and mouse for interactive primitives.
6. Keep `motion.css` last and verify `prefers-reduced-motion` plus the
   application motion preference.
7. Do not mix visual redesign with extraction. Styling changes require a
   separate reviewed commit after the structural move is proven equivalent.

## First extraction acceptance

The modal/drawer block is first because its selectors are namespaced
`.ras-modal*` and `.ras-drawer*`, and its component ownership is explicit in
`components/Modal.jsx`, `components/Drawer.jsx`, and `hooks/useFocusTrap.js`.

Status: extracted to `frontend-src/src/styles/overlays.css`; verification
evidence is recorded in the commit that introduces the file.

The extraction is accepted only when:

- the original block no longer exists in `rasputin.css`;
- every moved selector and declaration appears exactly once in `overlays.css`;
- `npm.cmd run build` passes;
- modal and drawer focus containment, Escape handling, close controls, and
  visible layout work in an isolated running app;
- desktop and narrow-width screenshots show no regression;
- the repository safety and relevant UI contract tests pass.
