# Menu upgrade 0.3.2 package evidence

Verified October 28, 2026 on the maintainer Windows workstation.

- Application source: `d6739d8a184a96f4dcd0a8dc8dc66522c0d63fcd`.
- Branch: `codex/restore-rea-home`.
- Local installer: `Rasputin-Setup-0.3.2.exe`.
- SHA-256: `d4660984bc3aac3c97f6018d800a7539282a235414ab8d6db271465febcbada5`.
- Authenticode status: unsigned. No public tag or release was created.

## Verification

| Surface | Result |
| --- | --- |
| Frontend build and desktop syntax | Passed. |
| Sidebar/shell source contracts | 11/11 passed. |
| Desktop lifecycle/packaging | 6/6 passed. |
| Isolated source workstation browser suite | 16/16 passed. |
| Packaged Electron-owned backend menu checks | 4/4 passed. |
| Installed Electron-owned backend, disposable data | 16/16 browser checks passed. |
| Installed file identity | Executable, app.asar, backend, frontend entrypoint, and training worker matched the verified package. |
| Documentation validation before this receipt | Passed, 48 Markdown files. |

The packaged checks cover popup surface consistency and viewport bounds, native
select mouse/keyboard operation, agent routing, and portalled Settings/history/folder
dialogs in both themes. Source screenshots were inspected at desktop, tablet, and phone
widths. The installer copy in Downloads was checksum-verified against the local build.

## Installation state

The initial attempt returned Windows error 1223 (canceled at Windows consent).
After an explicit retry request, launching the same checksum-verified installer with
direct Windows elevation succeeded with exit 0. The installed executable reports
`0.3.2.0`. All 16 workstation browser checks passed against its Electron-owned backend
using disposable application and runtime data.

A fresh read-only database snapshot was saved before retrying; record counts in three
existing tables were unchanged afterward. The earlier application-state backup and
database snapshots remain outside Git. The normal updated app was reopened, returned
health 200, and supplied its authenticated Desktop bootstrap. Ownership checks confirmed
the installed executable owns the packaged backend and uses the existing data directory.
