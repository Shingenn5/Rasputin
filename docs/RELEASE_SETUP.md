# Rasputin native setup and release guide

Updated 2026-09-01. The release target is the Windows native Desktop app with a packaged
backend and one verified llama.cpp runtime downloaded after hardware detection. Native Host is the source/browser workflow. Retired server
infrastructure and control features have no role in these steps.

## 1. Choose the correct owner

For installed use, launch Rasputin and let Electron own its Desktop Runtime. Its port is recorded
in `%LOCALAPPDATA%\Rasputin\data\desktop-runtime.json`; it need not be 8788.
For source development, use [Native Host commands](DEPLOYMENT_MATRIX.md) and a separate data
store if Desktop is running. Never share one live store between the two launchers.

## 2. Authenticate safely

Installed Desktop opens directly into the workspace. Its supervisor enables a local administrator
session for loopback requests; it does not require a login screen or a first-run password dialog.
This single-operator Desktop behavior must never be extended to LAN access.

Source Native Host uses the login screen and real session cookies. On a fresh store, it prints
generated administrator credentials once. Existing stores retain their accounts and sessions;
a restart does not generate a replacement password.

Use the supported password reset helper only when recovery is actually needed:

```powershell
$env:RASPUTIN_DATA_DIR = "$env:LOCALAPPDATA\Rasputin\data"
.\.venv\Scripts\python.exe -m backend.tools.reset_password
```

This changes credentials in the selected store; it is not a routine setup/restart step. Follow
its prompts privately and coordinate a runtime restart if required for session invalidation.
Never put passwords in Git, logs, screenshots, or documentation. Do not use legacy container
credential commands for native accounts.

## 3. Prepare the workspace and safety settings

Approve the intended host folder through Workspaces. Begin with read-only access and grant only
the capabilities needed. Native folder approval needs no mount or restart. Keep Privacy Lock,
owner/workspace boundaries, and approval/audit controls in place. Native Windows Host Shell is
unavailable until its AppContainer boundary is implemented and verified; enabling Docker is not
a workaround. Skills use declarative instructions and governed tools.

## 4. Download and load a model

Open **Discover Models**, choose a compatible GGUF variant, and download it. Wait for verification
and registration, then choose **Load** on the completed download card or **Load Model** in
**Models → My Models**. Review context and automatic device placement, then select **Load model**.
Wait for **Ready**, choose **Use in New Chat**, and send a short prompt in Chat mode. Return to the
same model and choose **Stop Model**; its installed files should remain available for another load.
The engine runs as a native `llama-server` child process.
A catalog listing or green health check alone does not prove inference or coding capability.

For an existing GGUF, use Scan GGUF/import from an approved path. For an old container-managed
entry, use **Get GGUF** or import its local GGUF. A retired runtime error indicates the wrong/stale
path. A runtime acquisition error should show a retryable download or compatibility message.
Source contributors should inspect the runtime manifest/configuration and load error. Plain
transformer weights are not directly loadable by llama.cpp.

External local OpenAI-compatible endpoints may be registered separately. They are not required
for the native GGUF workflow. Remote model endpoints remain governed by Privacy Lock.

## 5. Build a native package

Contributors need Windows x64, the repository Python environment, Node/npm, and build-time
network access for dependencies. End users do not need this toolchain.

```powershell
npm run desktop:check
npm run desktop:test
npm run desktop:package
```

Packaging builds `frontend/`, validates the pinned runtime manifest without downloading its
CPU/CUDA payloads, bundles the backend with PyInstaller, and creates the NSIS installer under
`dist/electron/`.
Each GitHub release must include the versioned installer and checksum plus stable aliases named
`Rasputin-Setup.exe` and `Rasputin-Setup.exe.sha256`. The README download button targets the stable
installer name on the latest release.
The current package remains unsigned; do not claim Authenticode or automatic-update certification.

A source backend restart does not update an installed Desktop package. Complete checks first,
then install the new package with operator approval. Quit the current Desktop owner before
replacing its binaries. Preserve the data directory and verify the new owner afterward. Never
launch Native Host against Desktop's active store to make a source change appear live.

## 6. Verify the release candidate

Use an isolated `RASPUTIN_DATA_DIR` for tests. Build and contract checks:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.testDocumentation tests.testReleaseContract
.\.venv\Scripts\python.exe scripts\verify_docs.py
npm run build
npm run checkRepoSafety
```

For an approved native endpoint, use explicit targeting:

```powershell
.\.venv\Scripts\python.exe scripts\verify_deployment_matrix.py --endpoint native=http://127.0.0.1:8788
.\.venv\Scripts\python.exe scripts\verify_release_candidate.py --endpoint native=http://127.0.0.1:8788
```

For Desktop, replace the URL with its recorded loopback URL. Older helper defaults and the
`scripts/test.ps1` harness include legacy container coverage; they are not the native startup
path. Use the isolated native workflow in [Codex onboarding](CODEX_ONBOARDING.md) for UI checks.

Record separate evidence for health/frontend, authenticated UI, model inference, a real coder
mission, voice hardware, and recovery. Do not turn historical Docker success or a mocked test
into current native release proof. See the [operator runbook](RASPUTIN_V1_OPERATOR_RUNBOOK.md).

## 7. Data and recovery

Keep application data, workspace sources, model weights, and credentials out of version control.
Use the governed backup/export flow, and restore into a separate target for rehearsal. Preserve
native ownership and data during upgrades. Test login, workspace scope, model files, and runtime
health after a restore. Model caches and external workspaces are not implicitly included in an
application-state backup.

LAN, reverse proxies, HTTPS trust, and public distribution require separate review. An ordinary
native restart or upgrade must not widen network exposure, change safety flags, or reset accounts.
