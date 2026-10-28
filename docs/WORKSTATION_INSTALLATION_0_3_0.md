# Workstation preview 0.3.0 installation evidence

Verified October 27, 2026 on the maintainer Windows workstation.

## Source and installer identity

- Branch: `codex/unsloth-workstation-upgrade`.
- Built application source: `cf98ec5de9e5b9a77629057ad34a974647a9e745`.
- Installer: `Rasputin-Setup-0.3.0.exe`.
- SHA-256: `38cbfaf14fadbcdf5bc73a59fe1eab90fa9b672f9c5ace74061dc8015ce5c455`.
- Authenticode status: unsigned.
- Installer version 0.3.0 supersedes the previously installed 0.2.4.

The build used a clean managed checkout of the pushed source. Existing unrelated changes
in the maintainer's primary checkout were excluded. Electron uses built-ins and local host
modules; Vite bundles the frontend. The before-build hook avoids collecting frontend-only
node_modules into the application. A runtime-import guard covers this packaging boundary.

## Evidence

| Surface | Result |
| --- | --- |
| Desktop lifecycle and dependency packaging gate | 6/6 passed. |
| Release documentation contracts | 8/8 passed. |
| Frozen backend and bundled frontend browser checks | 11/11 passed. |
| Installed Electron-owned runtime browser checks, isolated data | 11/11 passed. |
| NSIS installation | Exit 0. |
| Installed version | 0.3.0.0 executable; 0.3.0 app metadata. |
| Installed file identity | Executable, app.asar, backend, frontend entrypoint and standalone training worker matched the built package. |
| Normal installed startup | Healthy; local Desktop session authenticated; Electron owns the installed packaged backend. |

The browser checks exercised mouse/keyboard sidebar resizing, persistence/reset, navigation,
model picker, system-status popup, real named API key creation/revocation, training validation,
and desktop/tablet/phone layouts. They used disposable data and deterministic model fixtures;
they do not prove real-model inference, training quality, or clean-machine compatibility.

A verified application-state backup was created before installation: 106 files, archive
integrity verified. Model weights were excluded from the backup and not replaced by the
installer. Read-only comparison with the snapshot found no record-count decline in the three
existing runtime tables checked. Test runtimes were closed before opening the normal app.

## Delivery boundary

The installed artifact came from a checksum-verified local build copied into Downloads.
It was not redownloaded from GitHub. Automatic approval review rejected public release/tag
creation and installer upload because that publication needed explicit authorization beyond
the installation request. Publication remains pending approval; no public release was created
as part of this receipt.

Training still requires a separate compatible CUDA training environment and original local
safetensors weights. The bundled inference engine is not a trainer. The UI correctly blocks
the absent/incompatible training runtime. Scheduled exposes stored definitions, not a running
recurring-task dispatcher. Automatic updates and signing are not provided.
