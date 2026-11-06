# Rasputin 0.3.6 installed startup-memory update

Date: 2026-11-05. Installed upgrade verified on the maintainer workstation.

## Release scope

Built from the installed 0.3.5 release source at `9598c74`, with the optional
parser-import optimization ported from `4f97652` and package metadata advanced
to 0.3.6. Build source commit: `ad8af92`. The 0.3.5 release already contained
first-visit deferred views, so its frontend architecture and model-management
features were preserved. Unrelated changes in the primary checkout were excluded.

The bootstrap parser check now discovers installed PDF/Word/Excel packages without
importing them or NumPy. Actual imports remain at document-ingestion time.
This is an Electron update; the Rust prototype is not installed.

## Build and verification

- Production frontend and PyInstaller/NSIS package builds passed. Existing Pyodide
  externalization and large-chunk build warnings remain.
- Desktop syntax passed; lifecycle/packaging tests: **6 passed**.
- Fresh-process startup/parser regression tests: **2 passed**. The first attempt
  ran before generated frontend output existed and was not counted; it passed
  after the required frontend build.
- Full backend smoke suite on the isolated release source: **168 passed**, zero
  failures/errors/skips. This is distinct from the earlier mixed-worktree suite.
- Packaged 0.3.6 executable: actual Electron UI readiness, keyboard focus, mouse
  interaction, Desktop bootstrap HTTP 200, zero observed page exceptions, owned
  frozen backend, and normal-exit descendant cleanup passed using disposable data.
- Installed updater exit code: **0**. Windows executable version: **0.3.6.0**;
  Windows uninstall registration: **Rasputin 0.3.6**.
- Installed executable, archive, backend, and all packaged frontend files matched
  the built package: **26 file hashes matched**.
- Consistent read-only snapshots of **3 SQLite databases**, plus installed binary
  rollback files and **7 configuration files**, were preserved before installation.
  All database table counts, integrity checks, and all seven configuration hashes
  matched immediately after installation, before normal application startup.
- The actual installed 0.3.6 executable passed the same disposable-data UI and
  process-ownership check. Packaged PDF, DOCX, and XLSX availability separately
  passed against the installed frozen backend.
- Normal installed application reopened with the existing data. Its visible
  Rasputin window, installed backend/owner identity, health/frontend HTTP 200,
  Desktop-only/native flags, and **22 registry entries** were verified. This count
  includes registry entries, not a claim of 22 downloaded or working models.

## Installed before/after spot checks

Each actual installed executable ran once with a fresh data store/profile and no
loaded model. CDP discovery adds startup overhead; these are spot checks, not
controlled repeated benchmarks or guarantees for a populated daily workspace.

| Measurement | Installed 0.3.5 | Installed 0.3.6 |
|---|---:|---:|
| UI ready from launch | 10.691 s | 7.632 s |
| Backend private committed memory | 592.43 MiB | 90.82 MiB |
| Whole-process private committed memory | 1,186.69 MiB | 518.70 MiB |
| Summed working set | 621.32 MiB | 525.87 MiB |

Private commit is virtual memory commitment, not physical RAM. Summed working sets
include shared pages. Document parsing will load its libraries when needed.

Local evidence directory suffixes under Windows TEMP:

- `rasputin-installed-before-035-r1g6l7j3`: actual old installed application.
- `rasputin-installed-packaged-036-f6t4poh4`: packaged candidate.
- `rasputin-installed-after-036-egwfhuuz`: actual updated installation.
- `rasputin-036-rollback-lkspsrgm`: preserved binaries/database/configuration recovery files.

Disposable app data and profiles were removed after process cleanup. Recovery
snapshots, measurements, and screenshots were retained locally. The normal
installed app remains open without a debugging port or smoke-exit timer.

## Artifact and limits

Installer: `Rasputin-Setup-0.3.6.exe`.

SHA-256: `F9BDA3B689DEA2124D69A16A36420326BB2E31BAD31B5E41C6D58BB0C74EE550`.

This is a locally built unsigned installer; electron-builder's signing log lines
are not signature proof. No public release, signing/update-channel certification,
clean-machine installation, real model inference, or training certification is
claimed. No branches were merged or release tags created.
