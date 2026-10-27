# Unsloth reference: home, navigation, and overlays

The 2026-10-27 home revision supersedes the earlier sidebar-only scope below. Elliott
explicitly requested an Unsloth-like home and preservation of Rasputin's unique functions.

## Home revision

Live inspection and the shipped frontend establish the reference: a greeting above a rounded
composer, a model selector at upper left, and projects/recent chats in the sidebar.
`chat-Jo18weNp.js` SHA-256
`5d1db7a2b7e0a4091addc71b419797010664e1be70b7c22a1c4532357a83e7c7`
has welcome padding `27.5dvh` at UTF-8 byte 2137158, a 36px greeting/composer gap at
2137384, and a 46rem content maximum at 2138429. The heading uses 30px text, weight 500.
`index-CabIqzvv.css` SHA-256
`92c6fb6b2d782a3917f7762cc1a031352be0999f3d3f5c22e34fcb595d78a357`
defines the composer surface at byte 713790 (28px radius, 10px padding), and textarea
at 715858 (15px text, 24px line height). Sidebar defaults to 280px in
`settings-BNhHYgyP.js` byte 27933.

Rasputin now follows that welcome hierarchy with its own logo, components and dependencies.
The large decorative logo, recipe cards and setup banner give way to a small greeting,
736px composer and compact model-setup actions. Existing conversations keep the scrollable
thread and bottom composer. Expanded sidebar width is 280px; collapsed width remains 54px.

Model hub, Library and Assistant are visible. More exposes role-filtered History and tasks,
Memory, Skills, Agents, Approvals, Schedules, Telegram and Trials. These tools also have
command-palette entries, repairing previously missing discovery paths to working pages.

Preserved functions include all seven task modes, per-mode models, reasoning, memory choices,
approved context capsules, recipes, attachments and retention, coding isolation, agent roles
and helpers, queued tasks, pause/resume/stop, project trust, file browsing, indexing/Graphify,
knowledge retrieval, Assistant, integrations, approvals and audit evidence. Reasoning/memory/
coding controls live under Options; mode/agent configuration stays in the header. Runtime,
workspace and privacy facts are available in the status disclosure. Backend execution,
authentication, model lifecycle and inference code are unchanged.

The browser suite covers the new greeting geometry, recipes, mode menu, memory choice,
additional navigation, model selection and containment at desktop/tablet/phone widths.
Model inventory is a deterministic UI fixture; this does not establish actual inference.
Browser, packaged and installed results must be reported separately. Revert the scoped home
revision to roll back its composition and navigation changes.

Verification on 2026-10-27: frontend build passed; all six focused browser tests passed;
four theme catalog tests, five desktop lifecycle tests, eight documentation/release tests,
desktop syntax checks and the 42-file documentation validator passed. The packaged 0.2.4
executable was launched with an isolated profile and verified for home rendering, navigation,
search focus/dismissal and model-filter/clear behavior. These results do not imply installed
application replacement or real inference verification.

## Earlier chrome revision (historical)

The following describes the earlier 0.2.3 sidebar-only implementation, before the home revision.

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
