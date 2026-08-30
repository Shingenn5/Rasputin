# Rasputin native deployment and lifecycle

Updated 2026-08-29. Rasputin's current direction is a Windows native application with
local llama.cpp inference. Docker infrastructure is retired from the product. Application startup,
skills, and model loading use native processes and governed tools.

| Shape | Lifecycle owner | Address | Use |
| --- | --- | --- | --- |
| Installed Windows Desktop | Electron and its tray | Private loopback port selected at launch | Packaged daily-driver; bundled backend, frontend, and llama.cpp |
| Native Host from source | `backend.tools.native_host` | `http://localhost:8788` by default | Browser/headless development with approved host folders |
| Isolated verification | Test-owned native process | `http://127.0.0.1:8899` by convention | Disposable data; never the active installation's store |

## Installed Windows Desktop

Launch Rasputin from its installed shortcut. Electron starts the packaged backend and
waits for `/api/health`. Use the tray to restart its Desktop Runtime or quit the app.
Closing the window may only minimize it to the tray.

The installed application does **not** read backend or frontend changes from a source
checkout. Rebuild and install the updated package to apply source fixes; restarting an
old installed package only restarts that old code. See [release setup](RELEASE_SETUP.md).

`desktop-runtime.json` records the backend PID, Electron owner PID, URL, and data directory.
Inspect that record when identifying the active instance; do not assume the desktop app
uses port 8788. Do not kill a live Desktop owner to make another launcher take its store.

## Native Host from source

Use the repository virtual environment and a built frontend. From PowerShell:

```powershell
npm run build
.\.venv\Scripts\python.exe -m backend.tools.native_host start --port 8788
.\.venv\Scripts\python.exe -m backend.tools.native_host status --json
.\.venv\Scripts\python.exe -m backend.tools.native_host restart
.\.venv\Scripts\python.exe -m backend.tools.native_host stop
```

The equivalent PowerShell manager commands are `native-host-start`, `native-host-status`,
`native-host-restart`, and `native-host-stop`. Do not use the manager's bare `start`,
`stop`, `restart`, or `native-rebuild` as substitutes without inspecting their implementation;
legacy launcher branches still exist. The module commands above identify the native owner explicitly.

Native Host preserves its saved port/LAN configuration, waits for health, and attempts
an orderly shutdown before its process-tree fallback. A restart does not migrate or erase
model weights, chats, or preferences. First-run credentials are shown only for a fresh store.

## Data ownership

Both native launchers default to `%LOCALAPPDATA%\Rasputin\data`.
`RASPUTIN_DATA_DIR` selects a different store. Never run Desktop and Native Host simultaneously
against the same store. Use separate stores for parallel development and verification.

Native Host ownership is recorded in `native-host.json`; its saved settings are in
`native-host-config.json`. Respect either launcher's live ownership record. Before restarting
an existing installation, identify its actual owner, preserve its settings, and obtain the
operator's approval. Approval already given in the current task remains valid.

Back up application data using the governed backup flow. Model weights and external workspace
files need their own backup plan; an application-state backup is not a full machine backup.
Never remove ownership files to bypass a running owner or use volume-deletion commands.

## Native model deployment

1. Open **Discover Models** and choose an exact compatible GGUF variant.
2. Download it, or import an existing approved GGUF file from **Models**.
3. Wait for verification and registration to complete.
4. Choose **Load** on the completed download or **Load Model** in **Models → My Models**.
   Review context, memory mode, and automatic device placement, then choose **Load model**.
5. Rasputin starts a native `llama-server` process and registers its local endpoint.
6. Wait for **Ready**, choose **Use in New Chat**, and confirm a response in Chat mode.
7. Choose **Stop Model** in the model's inspector when finished. Installed files remain available
   for the next load; no repeat download is needed. A download card's **Stop** cancels acquisition.

`native-llamacpp` is the managed runtime. Installed files and loaded processes are separate
states. Native Host uses this path even when `RASPUTIN_DESKTOP_ONLY` is false. Native hardware
inspection uses `/api/warsat/hardware?native_models=true`; the route name is retained for
compatibility and does not imply Docker is required.

If an obsolete build reports a retired runtime error, check for an old installed
package or an old managed registry entry. Use **Get GGUF** to select a native artifact,
or import its existing GGUF file. If the bundled engine is missing, update or reinstall a verified
Desktop package. Source contributors should check the runtime manifest/configuration and load error.
Raw transformer weights are not directly loadable by native llama.cpp.

## Verification and remote access

Verify only the endpoint that actually owns the installation:

```powershell
.\.venv\Scripts\python.exe scripts\verify_deployment_matrix.py --endpoint native=http://127.0.0.1:8788
.\.venv\Scripts\python.exe scripts\verify_release_candidate.py --endpoint native=http://127.0.0.1:8788
```

For Desktop, substitute the URL recorded in `desktop-runtime.json`. Explicit endpoints avoid
the legacy multi-runtime defaults of older verification helpers. Health/frontend probes do not
prove model inference: complete download → load → response → stop separately with a small model.

Desktop binds to loopback. Private LAN/reverse-proxy access is a separate, explicitly reviewed
Native Host configuration, not an installation prerequisite. Preserve Host/Origin checks,
authentication, HTTPS requirements, and firewall boundaries. Never enable LAN or public access
as part of an ordinary restart.

## Retained legacy code

Docker Server, Compose assets, and container-oriented WarSat providers remain in the repository
for historical implementation context. They are outside the current Windows native
product and must not appear as setup instructions or an alternative model workflow. Older Linux/macOS Docker evidence is historical, not a
claim that those platforms are currently packaged or release-certified.
