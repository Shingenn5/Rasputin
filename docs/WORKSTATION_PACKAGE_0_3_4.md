# Homepage consistency: installed 0.3.4

Verified October 29, 2026 on the maintainer Windows workstation.

- Branch: `codex/homepage-consistency-20261029`.
- Main implementation: `a969ab5`; a final scoped correction aligns the phone
  load dialog's Cancel and Load buttons on one row.
- Installer: `Rasputin-Setup-0.3.4.exe`.
- Final installer SHA-256:
  `5cf83d2a598cef4c5963087bbf9c87eeee3eb95b2dd2499e0c5336f575d3085d`.
- Installer exited 0; installed executable reports `0.3.4.0`.
- Installed application archive, backend executable, and frontend entrypoint
  hashes match the final built package.
- Three existing databases were snapshotted before installation. Their table
  counts were unchanged before reopening the normal updated application.
- The normal application reopened with health and frontend HTTP 200 responses,
  authenticated Desktop bootstrap, and verified installed Electron/backend ownership.
- No public release or tag was created. The installer is unsigned.

## Verification

| Check | Evidence |
| --- | --- |
| Frontend production build | Passed; existing Pyodide externalization and chunk-size warnings remain. |
| Source UI | All 30 test cases passed across the complete run and focused reruns. The full run ended with 29 passes and an outdated internal-scroll assertion; its corrected keyboard-scroll check passed separately. |
| Responsive model loading | Three focused passes at 1440, 768, and 390 pixels after the final footer correction. Hidden Advanced values remained in the submitted load profile. |
| Installed Desktop UI, disposable data | 29/29 passed. The Native Host-only Discover scroll test is excluded from Desktop coverage. |
| Final installed phone load dialog | One additional focused pass against the final installer, including button alignment, bounds, advanced-value preservation, and profile submission. |
| Desktop syntax and lifecycle/packaging | Syntax passed; six tests passed with writable isolated scratch storage. |
| Documentation | Passed; 55 Markdown files checked. |
| Design detector | No findings on the checked UI targets. |
| JavaScript source contracts | 152 passed; the same five failures already present on main remain. Browser-only declarations were skipped in this Node invocation. |

The five existing JavaScript failures concern launch readiness, event connection
status, sidebar naming, model identity counts, and workspace tree markup. This
update does not represent the entire repository regression suite as clean.

The UI suites use real isolated authentication with explicit model/runtime
fixtures. They exercise rendering, routing, controls, keyboard operation,
responsive layouts, themes, API-key management, and load-profile payloads.
They do not certify real-model inference, training, voice hardware, or a clean
machine installation. The primary checkout's unrelated uncommitted work was
preserved and excluded.

See [the workspace style notes](WORKSPACE_STYLE_2026-10-29.md) for scope and rollback.
