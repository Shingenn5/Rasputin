# REAUnsloth restoration 0.3.1 installation evidence

Verified October 28, 2026 on the maintainer Windows workstation.

- Branch: `codex/restore-rea-home`.
- Application source: `781cec84db1977df1aa37bd936cd22a626f66a84`.
- Installer: `Rasputin-Setup-0.3.1.exe`, 134,050,900 bytes.
- SHA-256: `590ffe82bfcadd964f00141d967242e15bca0c21ea7042372b16e83fd9c3808a`.
- Authenticode: unsigned. NSIS installation exited 0 after Windows consent.
- Installed executable version: `0.3.1.0`.

The corrected build restores the home layout from REAUnsloth commit `415c738`,
removes the entire Chat header, and retains composer model selection, the hardware
popup, role-filtered tools, API, Training, Scheduled, and persisted sidebar resizing.
See `REA_HOME_RESTORATION.md` for provenance and the scoped source checks.

## Verification

| Surface | Result |
| --- | --- |
| Frontend build and desktop syntax | Passed. |
| Focused sidebar/shell source contracts | 11/11 passed. |
| Desktop lifecycle and packaging | 6/6 passed with required process permissions. |
| Frozen backend and bundled frontend | 12/12 browser checks passed. |
| Installed Electron-owned backend, disposable data | 12/12 browser checks passed. |
| Installed file identity | Executable, app.asar, backend, frontend entrypoint, and training worker matched the package. |
| Existing state | Read-only comparison found unchanged record counts in three existing database tables. |
| Normal installed instance | Health 200; installed Electron owns its packaged backend and uses the existing data directory; authenticated Desktop bootstrap succeeded. |

The browser suite covers the restored welcome screen and absent header, response Options,
keyboard/mouse resizing, persistence/reset, content/model navigation, model picker,
System status popup, real API key creation/revocation, training validation, and responsive
layouts. Screenshots were inspected at desktop, tablet, and phone widths. Model fixtures
do not establish real-model inference or training capability.

The first installed browser attempt could not locate Chromium because redirecting
LOCALAPPDATA also redirected Playwright's cache lookup. No interactions ran in that
attempt. Pointing Playwright at its existing browser cache fixed the harness; the full
installed run then passed. The initial packaged readiness probe also used `/health`
instead of `/api/health`; the corrected endpoint returned 200 before the passing suite.

The installer was built locally and checksum-verified after copying to Downloads.
No public tag or release was created, and no GitHub redownload is claimed. The normal
installed instance was already running when final ownership was checked and was left
running. Disposable test runtimes were closed. The pre-update database snapshot and
earlier verified application-state backup remain outside Git for recovery.
