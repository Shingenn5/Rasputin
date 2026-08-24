# Rasputin Desktop

Rasputin is a Windows desktop AI workstation for local model inference and agentic coding.
It is shaped to be used like LM Studio: install a normal application, browse a model catalog,
download an exact model variant, load it with native llama.cpp, and use it in chat or coding tasks.

The packaged application is the daily-driver path. You do not launch a terminal, manage a
localhost server, start Docker, install Python or Node, or deploy downloaded models into
containers.

![Windows](https://img.shields.io/badge/platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)
![Electron](https://img.shields.io/badge/desktop-Electron-47848F?style=for-the-badge&logo=electron&logoColor=white)
![llama.cpp](https://img.shields.io/badge/inference-llama.cpp-111318?style=for-the-badge)
![AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-orange?style=for-the-badge)

## Current desktop capabilities

- Rasputin launches as a self-contained Electron desktop application.
- The packaged app boots directly to the main user workspace; there is no login screen in the
  desktop-only path.
- Electron owns the bundled backend process, its lifecycle, crash recovery, tray controls, and
  shutdown.
- The installer includes the Python backend runtime, the React frontend, and pinned native CPU/CUDA
  llama.cpp binaries. End users do not install those components separately.
- Desktop inference uses native llama.cpp and GGUF model artifacts. Desktop model deployment is
  not Docker-backed.
- Models has a local catalog and Hugging Face search, hardware-aware fit guidance, exact variant
  selection, durable download jobs, and load controls.
- The load planner supports automatic placement plus advanced llama.cpp settings such as context,
  GPU layers, layer/tensor split, tensor proportions, main GPU, KV-cache offload, KV-cache types,
  flash attention, batch sizing, and CPU MoE controls when the selected runtime supports them.
- MCP Servers and integrations are available inside Settings, including local stdio servers,
  Streamable HTTP servers, guarded tool discovery, approvals, and GitHub repository context.
- Rasputin has its own application identity and icon instead of presenting as a generic Electron app.

## Product boundary

| Area | Desktop behavior |
| --- | --- |
| Normal launch | Open Rasputin from the Start menu or installed shortcut |
| User-managed server | None; the internal loopback backend is started and owned by Electron |
| Inference engine | Bundled native llama-server from llama.cpp |
| Model format | GGUF-first for local native inference |
| Model deployment | Native child processes; no Docker containers |
| Network exposure | Loopback-only by default; no LAN listener |
| Data | Local application data and a user-owned model library |
| Supported packaged platform | Windows x64 |

The backend still communicates with the Electron renderer over an authenticated loopback HTTP
connection. This is an internal implementation boundary, not a server that the user needs to
launch, configure, or keep running separately.

## Install and run

### Using the Windows installer

Run the Rasputin-Setup-<version>.exe installer and launch Rasputin from the installed shortcut.
The installer includes the application runtime and bundled llama.cpp; Docker, WSL, Python, Node,
and a separate llama.cpp installation are not prerequisites.

The current local build artifact is produced at:

~~~text
dist/electron/Rasputin-Setup-0.2.0.exe
~~~

This branch does not yet publish a signed public release or an automatic update channel. The
current installer is unsigned, so Windows may show a publisher warning during installation.

### First launch

1. Open Rasputin normally.
2. The application starts its private Desktop Runtime and opens the main workspace directly.
3. Open **Models** to choose a model, or open **Settings** to configure integrations, MCP servers,
   workspaces, and safety controls.

The default native data directory is:

~~~text
%LOCALAPPDATA%\Rasputin\data
~~~

It contains application state, the model library, durable model-download jobs, installed-artifact
metadata, preferences, audit data, and local configuration. Electron settings and desktop logs are
kept in the user-local Rasputin application directories. Application upgrades do not delete model
weights or user data.

## Model workflow

Rasputin's desktop model flow is designed around the same user journey as a local model manager.

### 1. Browse the catalog

Open **Models → Library**. The catalog can show locally cached models or search Hugging Face. It
supports:

- model-purpose and runtime filters;
- popularity sorting by downloads, likes, trending, or recent updates;
- VRAM range filters and a “use my largest GPU” shortcut;
- exact model IDs or Hugging Face URLs;
- hardware-aware fit results with blockers and next actions.

The fit advisor prefers a single fitting GPU. It only treats combined VRAM as a valid multi-GPU
option when the model, GGUF artifact, hardware snapshot, and native llama.cpp placement evidence
support layer sharding.

### 2. Select an exact variant

Open a model result and choose the exact GGUF quantization and required companion files. Rasputin
keeps model identity, revision, quantization, file set, size, compatibility, and integrity data
separate from the running model process.

### 3. Download and install

Start the download from the selected variant. Desktop downloads are durable and expose progress,
pause, resume, cancel, retry, verification, and installation states. Completed artifacts are
registered in the local model library and can be loaded without re-downloading them.

### 4. Plan and load with llama.cpp

Load the completed artifact from the download card or Models library. Automatic placement considers
the model size, context length, KV-cache cost, available GPU memory, and compatible devices before
starting the native llama.cpp process.

Advanced load profiles can express:

- context and fit context;
- CPU-only, single-GPU, or multi-GPU execution;
- GPU layer count and preferred main GPU;
- layer, row, or explicitly validated tensor split;
- tensor-split proportions;
- KV-cache placement and K/V cache precision;
- flash attention, batch, and micro-batch sizes;
- MoE CPU placement where the model and runtime support it.

Rasputin keeps “installed” and “loaded” separate. A model can be present in the library without
running, and each running instance has its own health, endpoint, device allocation, resolved
settings, and lifecycle state.

## Chat and agentic coding

Once a model is loaded, use it from the main workspace for:

- normal local chat;
- code generation, refactoring, repair, and review tasks;
- approved workspace access and direct native folders;
- task planning, durable task state, worktrees, approvals, and audit history;
- capability-aware routing that avoids starting tool-dependent work against an incompatible model.

Desktop mode keeps the existing Rasputin safety boundaries: workspace approval, explicit capability
permissions, audit events, Host Shell isolation, and visible recovery errors. Docker-backed model
deployment and Docker control are not part of the packaged desktop workflow.

## MCP Servers

Open **Settings → MCP Servers** to register and manage MCP availability for agentic coding.

Supported desktop flows include:

- local stdio MCP servers;
- Streamable HTTP MCP endpoints;
- working-directory and approved-workspace checks;
- environment-variable secret references rather than plaintext secret values;
- server start, stop, restart, discovery, and protocol tests;
- tool, resource, and prompt discovery;
- tool classification, approval gates, audit events, and guarded execution.

Rasputin's installer contains Rasputin, its backend, and llama.cpp. It does not bundle every
third-party MCP server package. A stdio server must already be available as a local executable or
package-manager command, or the server must expose a reachable Streamable HTTP endpoint.

## GitHub and other connections

Open **Settings → Integrations** to configure connectors. GitHub support is intentionally bounded:

1. Save a GitHub token in Connector Center; credentials are stored locally and masked from the UI.
2. Use **Settings → Security** to enable GitHub read access explicitly.
3. Check the connection before using it.
4. Load read-only repository context from task details, including repository metadata, pull
   requests, issues, and checks where available.

GitHub credentials stay in the backend. Rasputin only exposes the supported read operations to the
agent and records the relevant audit events.

## Security and privacy

- The packaged desktop runtime binds to loopback only.
- Electron removes inherited Docker and TLS server settings from the desktop backend environment.
- The renderer has no Node.js integration and uses context isolation and sandboxing.
- The desktop process owns only the backend process it launched.
- External access, remote models, GitHub, MCP tools, Host Shell, and other privileged capabilities
  remain policy- and approval-controlled.
- Closing the window can minimize Rasputin to the tray; the tray can restart or quit the runtime.
- Uninstall preserves user data by default.

## Build the installer from source

The following commands are for contributors and release work. An installed user does not need this
toolchain.

### Prerequisites

- Windows x64;
- Python 3.12+;
- Node.js 22+ and npm;
- a working virtual environment with the backend requirements installed;
- network access during the build to fetch the pinned llama.cpp assets and Python/Node packages.

### Development desktop

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
npm run desktop
~~~

The development desktop reuses the repository Python environment. Keep development data isolated
from any personal installation by setting RASPUTIN_DATA_DIR before launch.

### Package the Windows installer

~~~powershell
npm run desktop:package
~~~

Packaging performs these steps:

1. builds the production React frontend;
2. stages and verifies the pinned CPU/CUDA llama.cpp runtime;
3. builds the standalone PyInstaller backend;
4. packages Electron, the backend, llama.cpp, and the Rasputin icon with electron-builder;
5. produces an NSIS installer under dist/electron/.

For an unpacked directory useful for local smoke testing:

~~~powershell
npm run desktop:package:dir
~~~

## Verification commands

Run the focused desktop checks before distributing a build:

~~~powershell
node --check .\desktop\main.cjs
npm run desktop:check
npm run desktop:test
npm run build
~~~

The release candidate should also pass the backend tests, documentation check, and repository
safety check used by this branch:

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\verify_docs.py
npm run checkRepoSafety
~~~

Verify the actual packaged executable, not only the source build: install the generated NSIS
artifact, launch the installed Rasputin.exe, confirm the main workspace appears without a login
screen, and exercise the model/catalog surface in an isolated test data directory.

## Current status and honest boundaries

### Implemented on this branch

- Electron desktop lifecycle and tray ownership;
- direct desktop boot with Rasputin branding and icon;
- packaged PyInstaller backend;
- bundled, pinned native llama.cpp runtime selection;
- desktop-only native model registry and GGUF artifact flow;
- model catalog, Hugging Face search, exact-variant download controls, and durable job state;
- hardware-aware placement planning and advanced llama.cpp load-profile validation;
- local chat, workspaces, tasks, approvals, memory, and agentic coding surfaces;
- MCP stdio and Streamable HTTP registration, discovery, policy, and audit plumbing;
- locally stored GitHub connector and read-only repository-context flow.

### Still a release task

The branch is application-ready for continued daily-driver testing, but it is not yet a signed,
publicly distributed LM Studio replacement. The remaining release gates are:

- clean-machine install, upgrade, migration, and uninstall certification;
- Authenticode signing and a trusted update channel;
- live inference certification across representative CPU/CUDA hardware and model sizes;
- end-to-end third-party MCP server certification;
- end-to-end agentic coding certification using a real local coder model;
- a public release artifact and release notes.

These boundaries do not change the desktop product shape: the packaged app remains the supported
daily-driver path, and Docker is not required for it.

## Repository map

| Path | Purpose |
| --- | --- |
| desktop/ | Electron main process, backend supervisor, settings, and application assets |
| frontend-src/ | React source; generated production output is written to frontend/ |
| backend/ | FastAPI services, model catalog/acquisition, llama.cpp integration, MCP, and connectors |
| runtime/llama/ | Pinned llama.cpp manifest and bundled-runtime staging documentation |
| scripts/ | Desktop runtime, backend, installer, packaging, and verification scripts |
| tests/ | Backend, desktop lifecycle, branding, UI, and integration tests |

## License

Rasputin is licensed under the GNU Affero General Public License v3.0 or later. See
[LICENSE](LICENSE) for the complete terms.
