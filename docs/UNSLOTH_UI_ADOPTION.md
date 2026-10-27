# Unsloth reference: desktop chrome and overlays

Status: IMPLEMENTED in source. The central Chat workspace and composer structure are preserved.

The installed Unsloth study in [the application report](UNSLOTH_REVERSE_ENGINEERING_2026-10-26.md)
provides the reference for shared surfaces, soft active states, searchable model selection,
and native control semantics. The separate frontend study identifies the same installed
frontend inventory as SHA-256
`3b88819dec802b0a7349419b0c43379fb405f5fca82acfff6385a7d48b621a95`.
Relevant artifacts are `components.json` (shadcn radix-maia), `button-CBfshBaK.js`,
`card-BHanq9o-.js`, `index-CabIqzvv.css`, and `hub-page-CnkUbzTL.js`.
The implementation uses original Rasputin code and existing dependencies.

## Scope

- Softer navigation rows, themed surfaces, quieter borders, and a sidebar search shortcut.
- Visible recent-conversation rows below projects and a bottom settings entry; recent chats
  no longer require opening a drawer just to see their titles.
- A contrasting neutral New chat action and a lighter rail make the sidebar treatment visible
  in the default dark palette. The center and composer keep their existing layout.
- Search opens the existing command palette through its existing event.
- Command search and recent chats reuse the shared focus trap and restore trigger focus.
- The model dialog has a labelled filter, clear action, result count, and selected check.
- All visual changes are scoped in `studio-chrome.css`; the sidebar keeps its 220px/54px widths.
- No Chat layout, composer markup, inference, authentication, or model lifecycle changes.

## Verification and rollback

`npm run build`, the theme catalog checks, and `tests/ui/studioChrome.spec.mjs` cover
the build, keyboard interactions, filtering, selection, responsive containment, and focus return.
Model inventory in the browser tests is a deterministic UI fixture, not live inference.
Baseline and updated measurements matched for five central regions at 1440×1000,
1024×768, and 390×844. Light-palette, collapsed-rail, and mobile-search checks are included.

Remove the `studio-chrome.css` import to roll back the visual treatment, or revert the
scoped adoption commit to roll back the UI behavior changes as well. Installed application
packaging and installation are separate from this source/browser verification.
