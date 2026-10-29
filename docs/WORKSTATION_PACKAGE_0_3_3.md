# Workstation 0.3.3 integration and installation

Verified October 29, 2026 on the maintainer workstation.

- Application source: `490e2d0`; merged workstation upgrade, REA home/menu,
  October UI audit remediation, model runtime selection, and download-folder work.
- Installer: `Rasputin-Setup-0.3.3.exe`; Windows installer exit 0.
- Installer SHA-256: `a987ed6094715eb32d7481f5c68c8350e3cd3ca846486f665355280e1bcfd064`.
- Installed executable version: `0.3.3.0`; installed application archive and backend
  executable hashes match the built package.
- Normal installed application reopened, health returned HTTP 200, and authenticated
  Desktop bootstrap succeeded. Installed Electron owns the packaged backend.
- Recovery snapshots cover three existing databases; all table counts were unchanged
  before reopening the normal application. No model files were moved or deleted.
- Pre-existing uncommitted work in the primary checkout was preserved and excluded.

## Verification and limits

- Frontend build, documentation, 360 backend tests, five desktop lifecycle tests,
  and two source browser-fixture tests passed.
- JavaScript: 152 passed, five failed. The same five failures reproduce on the
  original `codex/ui-audit-remediation` checkout: launch readiness, event connection
  status, sidebar naming, model identity count, and workspace tree markup contracts.
  The full source gate and Windows source CI therefore remain failing.
- Focused model storage/API/settings tests: 14 passed. Desktop packaging: one passed.
- Isolated authenticated source UI: 22 passed, including desktop/tablet/phone checks.
- Installed Electron-owned backend with disposable data: 21 passed, one failed.
  The remaining combined dashboard/workspace test attempts to focus Native Host
  Discover's `Model discovery details` region, which Desktop does not render.
  That Native Host behavior passed in the source run; the installed run is not
  represented as a clean 22-test pass.
- Initial installed harness attempts failed before meaningful UI coverage because
  the isolated environment changed browser discovery and reused generated credentials.
  The final run used the existing browser and a fresh disposable account store.
- Repository-safety CI initially flagged the public SQLite storage label
  `inference_api_keys_v1`. `.gitleaksignore` records only that exact historical
  fingerprint; it is not a credential or a general API-key exclusion.

No public release or tag was created. This update does not certify clean-machine
installation, signing, real-model inference, coding missions, training, or voice.
