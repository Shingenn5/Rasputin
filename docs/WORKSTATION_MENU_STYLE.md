# Shared workstation menus

The restored home palette now lives on the document root so dialogs portalled to
`document.body` inherit the same colors as controls inside the application frame.
`studio-menus.css` supplies shared tokens and scoped styles for dialogs, drawers,
command menus, response Options, workspace access popovers, Bootstrap modal content,
dropdown menus, and native select controls. Removing its import rolls back this skin.

The treatment uses neutral surfaces and selections, 14px surface corners, 8px control
corners, a quiet border, consistent headings, and visible keyboard focus. Existing
positioning, dismissal, focus management, role filtering, values, and form handlers
remain owned by their components. Options aligns to the trigger's right edge above
phone widths, fixing its overflow at a 768px viewport.

Chromium's `appearance: base-select` styles the native picker without introducing a
JavaScript select implementation. Bootstrap's background arrow is removed in that
supported mode to avoid duplicate arrows. Unsupported browsers retain their native
picker with themed controls and options. Native operating-system file pickers and
window menus remain operating-system surfaces.

Verification: frontend build and 11 focused sidebar/shell contracts passed. All 16
workstation browser checks passed on an isolated authenticated server. New coverage
compares actual popup surfaces and borders, checks 1440/768/390px bounds, exercises
mouse and keyboard select changes, opens the routing panel, and checks dark/light
Settings, history, and Bootstrap folder dialogs. Rendered captures were inspected.
Initial checks caught the tablet Options overflow; two harness errors used a nonexistent
memory option and omitted the folder-opening button, and were corrected before the
passing run. This source evidence is separate from package/installation verification.
