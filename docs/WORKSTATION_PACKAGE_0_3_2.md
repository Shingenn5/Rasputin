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
| Documentation validation before this receipt | Passed, 48 Markdown files. |

The packaged checks cover popup surface consistency and viewport bounds, native
select mouse/keyboard operation, agent routing, and portalled Settings/history/folder
dialogs in both themes. Source screenshots were inspected at desktop, tablet, and phone
widths. The installer copy in Downloads was checksum-verified against the local build.

## Installation state

The installation attempt returned Windows error 1223 (canceled at Windows consent).
The installed executable still reports `0.3.1.0`; installed 0.3.2 verification has
not run. The existing application was reopened and returned health 200. A read-only
database snapshot was saved before the attempt; record counts in three existing
tables were unchanged afterward. The earlier application-state backup remains available
outside Git. Retrying installation is awaiting the user's response to that cancellation.
