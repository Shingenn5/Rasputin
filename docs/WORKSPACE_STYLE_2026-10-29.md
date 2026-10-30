# Workspace consistency with the homepage

The existing Chat welcome screen is the visual reference for Rasputin's other
pages: warm neutral surfaces, one UI typeface, modest headings, quiet borders,
and the configured theme accent for actions and selection. The Chat layout and
composer are preserved.

## Changes

- Model Hub uses a page heading, a single tab row, a compact storage disclosure,
  and a selectable model list with a separate inspector. Normal document flow
  prevents tall panels from collapsing the heading or covering navigation.
- Model rows, the inspector, and load dialogs use the same friendly model name.
  Format, size, and context appear together in the inspector. Technical details
  and existing recovery controls remain available.
- Loading starts with context length and memory mode. GPU layers, CPU threads,
  batch sizes, cache settings, and other tuning controls move under Advanced.
  Hiding that section preserves its values in the submitted load profile.
- API, Training, Library, Assistant, Schedules, Skills, and other secondary
  routes inherit the homepage's spacing, typography, neutral canvas, controls,
  and panel treatment. Runtime headers lose their decorative orbits and kickers.
- Settings retains its dialog and navigation behavior with more readable form
  controls and less nested panel decoration.

The shared layer is `frontend-src/src/styles/studio-workspace.css`. Feature
handlers, authentication, model placement validation, and runtime ownership
remain in their existing modules. No new frontend dependencies were added.

## Verification

`tests/ui/workspaceConsistency.spec.mjs` exercises model filtering and selection,
keyboard inspector tabs, load-profile submission after hiding Advanced, all five
Model Hub areas, and secondary routes at desktop, tablet, and phone widths.
The route matrix also checks the light theme. Model/runtime responses in these
tests are explicit fixtures; authentication and routing use an isolated server.
They do not certify real inference or hardware fit.

The existing Studio, workstation, download-folder, and UI-audit browser suites
remain part of the verification gate. The reduced-motion test now checks the
actual page animation and confirms that the removed decorative elements are absent.

Revert the scoped UI-consistency commit for a complete rollback. Removing the
`studio-workspace.css` import in `main.jsx` rolls back the shared visual layer;
the scoped markup and load-form organization changes require the commit revert.
