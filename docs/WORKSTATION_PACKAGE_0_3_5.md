# Model architecture: installed 0.3.5

Verified October 30, 2026 on the maintainer Windows workstation.

- Main was fast-forwarded to include the prior homepage-consistency changes and the first information-architecture slice.
- Application build source: `f614708` (architecture implementation `e6ae6ad`). A subsequent test-only correction, `8f0fce2`, checks model action keys in the inspector where the actions now live.
- Installer: `Rasputin-Setup-0.3.5.exe`.
- Installer SHA-256: `7d183c41f03ad317035f447985e8991b530097e919777df71aa13545f77ca161`.
- Installer exited 0; installed executable reports `0.3.5.0`. The installer is unsigned. No public release or tag was created.
- Installed application archive and backend executable match the built package. All 23 installed frontend files match the production frontend build.
- Three existing SQLite databases were snapshotted before updating. Their table counts were unchanged after installation and before reopening the normal application.
- The normal installed application reopened. Direct IPv4 loopback health and frontend requests returned HTTP 200; Desktop bootstrap returned the administrator account and Desktop-only security mode. App and backend executable paths were verified under the installed application directory.
- The initial startup probe used a two-second timeout against localhost. Name resolution/fallback added slightly more than two seconds; direct IPv4 checks confirmed the application was healthy.

## Verification

| Check | Outcome |
| --- | --- |
| Native Windows package build | Passed, including frontend, hardware-selectable runtime manifest validation, PyInstaller backend, and NSIS installer. |
| Desktop syntax | Passed. |
| Desktop lifecycle and packaging | Six passed with writable isolated scratch storage. The first restricted attempt encountered access failures and was stopped; it is not counted as passing. |
| Model action registry-key contract | Four passed after updating the obsolete row-action assertion to check start, stop, and delete in the selected-model inspector. |
| Installed application browser suite | Ten passed using the actual installed executable with disposable data and explicit model/runtime fixtures. |
| Source UI evidence preceding packaging | Nineteen focused JavaScript tests and ten browser tests passed; four final responsive navigation checks also passed. |
| Documentation before this record | Passed, 56 Markdown files checked. |
| Repository safety CI | Passed on `8f0fce2`. |
| Windows source-regression CI | Still running on `8f0fce2` when installation verification completed. The preceding run failed on the obsolete row-action contract corrected by that commit; pending CI is not a pass. |

Installed browser coverage includes two primary model destinations, Model tools access, compact inventory selection/filtering, keyboard tabs, focus return, responsive layouts at 1440/768/390 pixels, load-profile payload preservation, connection-repair access, Chat handoff, and secondary route bounds in both themes.

The tests use real application startup and authentication with explicit model/runtime fixtures. They do not certify real-model inference, training, or a clean-machine installation. Disposable verification processes, data, and credentials were removed; pre-install recovery snapshots were retained outside the repository. The primary checkout's unrelated changes were preserved.

See [information architecture](INFORMATION_ARCHITECTURE.md) for implemented scope and the next migration slices.
