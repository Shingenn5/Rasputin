# First Windows prototype results

Date: 2026-11-05. This is a source-worktree experiment, not installed-app
certification. The checkout contained unrelated edits, which were preserved and
are excluded from the prototype commit. Both comparison shells used the same
current source backend and frontend build, fresh stores/profiles, and no model.

## Three paired runs

Release Rust/Tauri versus Electron 43.1.0 with its existing backend supervisor.
Tauri used WebView2 156.0.4314.58. The Electron fixture omitted production tray and
updater work. Order alternated between repetitions; each idle sample lasted ten
seconds after the same basic UI probe. No filesystem-cache flush was performed.

Medians across three runs per shell:

| Measurement | Rust/Tauri | Electron fixture |
|---|---:|---:|
| App ready, from launch | 8.543 s | 8.672 s |
| Process-tree private committed memory | 1,134.63 MiB | 1,163.28 MiB |
| Summed process-tree working set | 666.43 MiB | 614.90 MiB |

The private-commit reduction was **28.65 MiB (2.5%)**. Median readiness was
**0.129 seconds (1.5%)** faster, too small in this limited experiment to establish
a reliable startup improvement. Summed working set was **51.53 MiB higher** in
Tauri. Working sets include shared pages; private commit measures committed virtual
memory, not physical RAM. Neither should be silently substituted for the other.

Raw app-ready times, in per-shell run order:

- Rust: 9.002, 8.543, 8.015 seconds.
- Electron: 9.139, 8.614, 8.672 seconds.

One earlier Rust smoke sample broke down approximately as 7 MiB private commit in
the Rust shell, 537 MiB across WebView processes, and 590 MiB in Python. This is a
single diagnostic snapshot, not an independently benchmarked subsystem result.
The small Rust executable does not imply a small complete application.

## Verification

- `cargo test --locked --manifest-path prototypes/rust-desktop/Cargo.toml`:
  **3 passed**, covering fresh isolated roots, rejection of unrelated HTTP health,
  and Windows listener-owner identity.
- `cargo build --release --locked --manifest-path prototypes/rust-desktop/Cargo.toml`:
  passed. Executable size: 8,410,112 bytes, excluding Python, frontend assets and
  the system WebView runtime. This is not an installer-size comparison.
- Frontend production build passed, with existing Pyodide externalization and
  chunk-size warnings.
- `npm.cmd run desktop:check`: passed.
- `node --test tests/desktopLifecycle.test.cjs tests/desktopUpdates.test.cjs`:
  **11 passed** outside the sandbox. The sandbox attempt failed on filesystem and
  subprocess operations and was stopped; its failures are not product regressions.
- Documentation validator: **53 Markdown files passed**. The prototype Markdown
  files are outside that validator's root/docs coverage and were reviewed directly.
- Six comparison launches: actual WebView app readiness, Desktop bootstrap HTTP
  200, keyboard focus, mouse interaction, and zero observed page exceptions.
- Separate extended Rust source run: Settings opened by mouse, Chat selected by
  keyboard, external popup and top-level external navigation both blocked.
- Rust with the existing packaged backend: actual WebView/desktop bootstrap/UI
  smoke passed. This was a separate smoke check, not a packaged performance
  comparison or installed-app verification.
- Forced Rust-shell termination cleaned up tracked descendants in every completed
  Rust benchmark. Electron fixture cleanup explicitly terminated its test tree.
- Normal Rust shutdown returned exit code 0 and stopped all **9** tracked
  descendants in its separate source run.

Local evidence directory suffixes (under Windows TEMP):

- `rasputin-shell-benchmark-7yy8kr5v`: all six comparison results/screenshots.
- `rasputin-shell-benchmark-k8ir_4vo`: extended navigation evidence.
- `rasputin-shell-benchmark-trwgcrbi`: packaged-backend smoke evidence.

Release executable SHA-256:
`FB52722B52631EA3AC45AECFD3FA78E23CBAA3517DB82C7043AA8883EEEA4B45`.

## Decision

The Rust shell is viable as a prototype. **This experiment does not support a
claim of a major whole-app startup or RAM improvement from replacing Electron
alone.** Keep the prototype and benchmark, then profile backend initialization,
Python imports/background services, and frontend startup/rendering before choosing
the next Rust migration boundary. Populated stores, real model lifecycles, native
permissions, updates, and installed-product parity remain unverified.
