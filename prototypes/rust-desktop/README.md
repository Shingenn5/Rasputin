# Rust desktop prototype

**Experimental source prototype.** A Tauri/Rust process displays the existing React
application using Windows WebView2 and owns the existing Python/FastAPI backend.
It does not replace the installed Electron application or migrate its database.

The first experiment isolates the desktop shell's contribution to startup and
memory. Python and llama.cpp remain separate processes. A smaller shell does not
establish faster inference or justify a complete backend rewrite.

## Build and run

Requirements: Windows, Rust stable with the MSVC target, Visual Studio C++ build
tools/Windows SDK, and Microsoft Edge WebView2. The source-backend mode also needs
the repository `.venv` and built frontend. These are prototype developer tools;
this is not an end-user installer.

From the repository root:

```powershell
npm.cmd run build
cargo test --locked --manifest-path prototypes/rust-desktop/Cargo.toml
.\prototypes\rust-desktop\run.ps1
```

To test an already built PyInstaller backend instead:

```powershell
.\prototypes\rust-desktop\run.ps1 -Backend .\dist\desktop-backend\rasputin-backend\rasputin-backend.exe
```

`run.ps1` builds release mode and accepts `-Cargo <cargo.exe>` and `-BuildOnly`.
Use `-Executable <existing-prototype.exe>` to run a prebuilt executable without
invoking Cargo or requiring the Rust toolchain at launch.
`CARGO_TARGET_DIR` can put build output outside the checkout. The executable also
accepts `--source-root <repository>` or `--backend <executable>`, and optionally
`--exit-after-ms <milliseconds>` for a normal-exit smoke check. The timer starts
after backend readiness/window creation, not at process launch.

Every launch creates a unique `rasputin-rust-*` directory in the Windows temporary
directory. It contains isolated SQLite data, a WebView profile, temporary owner
metadata, and `startup.json`. It ignores the live `RASPUTIN_DATA_DIR` setting and
never attaches to another Desktop or Native Host. Source mode explicitly uses
`.venv/Scripts/python.exe`; packaged mode uses the selected executable's embedded
frontend, which may be older than source.

## Ownership and boundaries

- The Rust process joins a private Windows Job Object before spawning the backend
  or WebView. Kill-on-close owns descendants across ordinary exit and shell crash.
  Failure to establish the job aborts startup. No existing process is adopted or
  killed. Closing the prototype quits it; there is no background tray mode.
- The backend binds only to `127.0.0.1` on a dynamically selected port. The existing
  Desktop administrator session applies only to this isolated loopback backend.
  Other local processes share the existing Desktop trust boundary.
- Health readiness checks both the Rasputin response and the listener's membership
  in this prototype's private job. A port-selection race cannot attach to an
  unrelated listener. There is a 90-second startup deadline.
- The WebView has no registered Rust commands, remote capabilities, or shell/file
  plugins. Top-level navigation is restricted to the selected backend origin;
  new windows are denied. Backend authorization and approval rules remain in force.
- Backend console output is discarded so first-run credentials do not enter logs.
  This intentionally limits crash diagnostics in this early prototype.
- Test data remains under TEMP for inspection. Remove only the exact stopped run's
  directory when finished; no automated recursive deletion targets user stores.

## Compare startup and memory

The benchmark requires repository Python with `psutil`, Node, and the repository
Playwright package. It connects to the actual WebViews using temporary loopback
CDP debugging ports. **Do not enable those ports for daily use.**

Install the repository's Electron developer runtime if necessary, then prepare
an isolated copy. The helper refuses a production `app.asar` and grants Chromium's
restricted GPU process read/execute access only to its new temporary runtime copy:

```powershell
node node_modules/electron/install.js
$electron = .\prototypes\rust-desktop\prepare-baseline.ps1
.\.venv\Scripts\python.exe prototypes/rust-desktop/benchmark.py `
  --rust prototypes/rust-desktop/target/release/rasputin-rust-prototype.exe `
  --electron $electron --repeats 3 --seconds 10
```

Adjust `--rust` if `CARGO_TARGET_DIR` was set. Add `--backend <executable>` to give
both shells the **same packaged backend**; without it both use the same source
backend and built frontend. The Electron fixture reuses the current supervisor,
but omits tray/updater work, giving Electron a conservative baseline. It is not
an installed-app benchmark. Repetitions alternate order; all use fresh profiles
and stores, but OS filesystem/antivirus caches are not reset.

Evidence goes into a fresh `rasputin-shell-benchmark-*` TEMP directory:

- UI readiness: the actual app's `body[data-ready='true']`, timed from launch.
  CDP discovery adds measurement overhead. Navigation completion alone is not app
  readiness. Probe completion separately includes interaction and screenshot time.
- Authenticated Desktop bootstrap, keyboard focus, a mouse click, and a screenshot
  run inside each actual WebView. Observed page errors fail the probe.
- Private committed bytes and working set are sampled across shell, browser, and
  backend descendants. Working-set sums include shared pages; private committed
  bytes are not equivalent to physical RAM. No model is loaded.
- Startup peak private bytes and steady sample medians are recorded separately.
  The steady sample follows the same UI probe in both shells.
- Rust is force-terminated to exercise its crash cleanup. Electron gets explicit
  fixture-tree cleanup. Either leaving tracked descendants alive fails the run.

`startup.json` also records backend health and WebView navigation completion.
The benchmark's `results.json` is local evidence, not committed user/machine data.
After verifying process cleanup, the benchmark removes only its own isolated data
and browser profile, retaining measurements and screenshots. Standalone launches
retain their TEMP data for inspection.
Do not compare a debug Rust build with a release Electron build for a speed claim.

Add `--extended-ui` for a separate interaction run that opens Settings with the
mouse, returns to Chat with the keyboard, and checks blocked external navigation
and popups. Keep those runs separate from the basic comparison: opening extra
pages changes memory use.

## Remaining product work

This prototype has no installer, signed updater, tray controls, production profile
migration, external-link opening, backend restart UI, or feature-parity certification.
Clipboard, notifications, microphone, file downloads, real model lifecycle, and
accessibility beyond the focused probe still need actual WebView testing. Backend
failure after startup needs a recovery surface. Fresh empty stores do not reproduce
an existing user's indexing, background jobs, or loaded models.

Keep the Electron launcher as the rollback. Measure representative populated-store
and model workloads before selecting a replacement or rewriting backend services.
