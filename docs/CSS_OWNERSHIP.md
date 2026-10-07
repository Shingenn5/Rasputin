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
3. `rasputin.css` — ordered imports for the global component and feature styles.
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
| `rasputin.css` | Global stylesheet import order only | Keep rule bodies in the named files below |
| `dashboard.css` | Dashboard shell and dashboard-specific layout | Do not absorb unrelated view styling |
| `interface.css` | Shared workstation presentation | Contains later overrides; extraction requires cascade checks |
| `secondary-views.css` | Shared secondary-view layout and hierarchy | Keep shared rather than copying into features |
| `motion.css` | Motion preferences and global reduced-motion behavior | Must remain last in the global cascade |
| Feature CSS files | One feature root and its responsive states | Avoid unscoped global selectors |

## Where to edit global styles

The following files are imported in this exact order by `rasputin.css`.
The extraction preserves the original cascade; base styles and later overrides
stay separate so they do not silently change priority. Do not alphabetize imports.

| File | Edit here for |
| --- | --- |
| `overlays.css` | Shared modal and drawer primitives |
| `foundations.css` | Global defaults, loading placeholders, toast notifications |
| `shell.css` | Application frame, navigation, sidebar, shared shell controls |
| `chat-base.css` | Conversation layout, messages, composer base styles |
| `view-primitives.css` | Page headers, shared cards, task-mode controls |
| `workspace-base.css` | Workspace folders, files, graphs, mount review |
| `activity-integrations.css` | Activity tabs, task messages, MCP relay controls |
| `archive-trials.css` | Archive editor and trials panels |
| `model-runtime-base.css` | Model library, catalog, runtime and safety panels |
| `session-task-controls.css` | Session folders, streamed steps, task details, forms |
| `preview.css` | Optional design-preview screens |
| `responsive.css` | Original responsive rules and shared surface refinements |
| `workstation-layout.css` | Workstation grids, compact views, explorer and shell overrides |
| `warsat-controls.css` | Retained WarSat stepper, runtime cards, discovery and logs |
| `view-motion.css` | Original view transitions and interaction feedback |
| `chat-overlays.css` | Chat avatars, autogrow behavior and first-run onboarding |
| `chat-controls.css` | Composer pill, model indicator, attachments, queue, command menu, folder approvals |
| `assistant.css` | Assistant essential controls and advanced disclosures |

Feature-owned `models-workspace-v3.css`, `history-workspace-v3.css`, and
`settings-workspace-v3.css` still override the base styles through their original
component imports. `interface.css` and `motion.css` retain their later global positions.

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
