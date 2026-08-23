# Rasputin Desktop + llama.cpp Daily-Driver Execution Plan

**Branch:** `codex/desktop-llamacpp`
**Plan date:** 2026-08-22
**Scope:** Planning only. This document does not authorize implementation, deletion, commit, push, packaging, or release work.
**Target:** A Windows desktop application that can replace LM Studio for local GGUF discovery, download, model loading, inference, and agentic coding, with MCP support added after the core model workflow is dependable.

## 1. Outcome

The finished Rasputin edition is installed and launched like a normal Windows application. It owns its backend and llama.cpp processes, stores its data under the user's application-data directory, and never requires the user to launch a terminal, run a web server, install Python or Node, or manage Docker.

The primary journey is:

1. Install Rasputin.
2. Let Rasputin detect the machine and install the correct pinned llama.cpp runtime.
3. Browse or search a useful GGUF catalog.
4. Open a model, compare exact quantization variants, see fit and capability information, and choose a file.
5. Download with visible progress and pause, resume, cancel, and retry controls.
6. Load the installed model with an automatic profile or advanced llama.cpp settings.
7. Watch the load transition to Ready, then use the model in Chat, coding tasks, or an optional local API.
8. Later, register MCP servers, inspect their capabilities and permissions, and make approved tools available to capable models and coding tasks.

## 2. Product boundaries

### Required

- Electron is the only user-facing launch surface.
- Electron owns an app-private backend process and every llama.cpp child process.
- All app-owned network listeners bind to loopback by default. They are implementation details, not terminal-launched services.
- Inference uses `llama-server` from a Rasputin-managed, versioned llama.cpp installation.
- The desktop model path is GGUF-first. Model downloads are not deployed to containers.
- The packaged application works without Docker, WSL, Python, Node, or a separately installed llama.cpp.
- Downloaded models and user data survive application upgrades.
- A failed runtime install, download, model load, or MCP launch produces a visible explanation and recovery action.
- Automatic settings are safe on mixed and unequal GPUs; advanced settings remain available to the user.

### Explicitly out of scope for the desktop edition

- Docker or Compose model deployment.
- vLLM, Ollama, or container-backed inference in the primary product flow.
- A terminal command as the normal launch or recovery path.
- Binding the inference API to the LAN without an explicit opt-in and authentication warning.
- Training, fine-tuning, or GGUF conversion in the first release.
- macOS and Linux packaging before the Windows daily-driver release is proven.

### Important architectural clarification

“Desktop app, not a localhost server” should mean no user-managed localhost server. The current Electron architecture can continue to use an invisible, randomly authenticated loopback backend between the renderer and the packaged Python service. That service must be spawned, monitored, and stopped by Electron; bind only to `127.0.0.1`; use an ephemeral secret; and never require a terminal. Replacing that internal boundary with pure Electron IPC is optional future work and is not a prerequisite for the daily-driver outcome.

## 3. Current branch baseline

Status legend: **Implemented** means code exists on this branch; **Partial** means useful code exists but does not satisfy the product outcome; **Missing** means the product capability needs a new implementation. “Verified” must only be assigned after the listed acceptance proof is run.

| Area | Branch state | Evidence | Main gap |
|---|---|---|---|
| Electron lifecycle | Implemented | `desktop/main.cjs`, `desktop/backend-supervisor.cjs`, `desktop/preload.cjs` | Clean-machine and failure-recovery proof |
| Desktop-only mode | Implemented | `RASPUTIN_DESKTOP_ONLY` is set by Electron and surfaced by `backend/api/core.py` | Remove remaining Docker vocabulary and unreachable desktop controls |
| Native llama.cpp provider | Partial | `backend/warsat/providers/native_llamacpp.py` | Runtime installation, richer flags, robust process supervision, progress, and real-engine proof |
| Packaged runtime lookup | Partial | `runtime/llama/README.md`, `package.json` extra resources | No pinned `llama-server.exe` installation or update mechanism |
| Hugging Face catalog | Partial | `backend/models/catalog.py`, `frontend-src/src/features/models/ModelsView.jsx` | Model-detail and exact-file/quantization selection are missing |
| Hardware fit advisor | Partial | `backend/models/resource_manifest.py`, catalog placement logic | Must use exact artifact size, context, KV cache, concurrency, and current free VRAM |
| Model acquisition | Partial | `backend/models/acquisition.py` | Downloads whole snapshots, jobs are memory-only, and pause/cancel/retry are absent |
| GGUF registry/import | Implemented | `backend/models/registry.py` | Installed artifact and loaded instance are still conflated in places |
| Load/unload UI | Partial | Native Start/Stop in `ModelsView.jsx` | No load-profile editor, load progress, instance identity, TTL, or eviction policy |
| Chat and coding | Partial | Existing Chat, Assistant, Workspaces, tasks, tools, approvals, and review surfaces | Model auto-load, capability certification, and end-to-end coding proof |
| MCP relay | Partial | `backend/mcp/relay.py`, `backend/api/mcp_routes.py` | Local stdio exists; Streamable HTTP, secrets UX, packaging, compatibility, and end-to-end agent proof remain |
| Installer | Partial | PyInstaller + electron-builder NSIS scripts in `package.json` | Product icon, signing, updates, runtime bootstrap, migration, and clean-VM proof |

### Branch verification ledger (2026-08-22)

This ledger records bounded branch evidence; it does not replace or expand the roadmap
acceptance gates.

- **Implemented:** pinned b10586 Windows CPU, CUDA 12.4, and CUDA 13.3 llama.cpp manifests
  with cudart companion assets; runtime bootstrap/install/repair primitives; durable exact
  model artifact, download, and registry integration; native llama.cpp lifecycle with
  `mmproj` handling, stable failures, process-group isolation, and stale recovery; Models UI
  variant download/progress/load flow; MCP stdio plus Streamable HTTP policy, secrets, and
  audit contracts; and Electron/PyInstaller packaging.
- **Verified:** 44 focused backend tests; 210 existing backend tests with one intentional
  skip; 24 focused Node tests; 5 desktop lifecycle tests; compilation of 110 backend modules;
  the production frontend build; native health, frontend, and login on isolated port 8899; a
  desktop package directory; and a byte-identical packaged runtime manifest.
- **Boundary:** live model-loading/inference smoke was paused after an application crash, so
  live model loading/inference and CUDA live inference are not verified. Clean-machine/VM
  install, upgrade/migration, signed NSIS installer, real third-party MCP, and end-to-end
  agentic coding/MCP certification are also not verified. These remain roadmap acceptance
  work; this ledger does not claim a full LM Studio replacement.

This plan preserves those foundations and replaces only the parts that prevent a dependable desktop workflow.

## 4. Target architecture

```text
Electron main process
  ├─ window, tray, protocol links, file/folder dialogs
  ├─ app update manager
  ├─ packaged backend supervisor
  └─ crash/restart and shutdown ownership
          │ authenticated loopback, app-owned
          ▼
Rasputin backend
  ├─ hardware probe + placement planner
  ├─ catalog and model metadata service
  ├─ persistent download manager
  ├─ installed-artifact store and index
  ├─ llama.cpp runtime installer/version manager
  ├─ model instance scheduler and process supervisor
  ├─ chat, coding agent, tools, approvals, and audit
  └─ MCP client manager
          │ child process / loopback
          ▼
Versioned llama-server runtime(s)
          │
          ▼
GGUF artifacts in user-selected model library
```

### Storage layout

Use distinct roots so application updates cannot corrupt models or mutable state:

```text
%LOCALAPPDATA%\Rasputin\
  app-state\                 database, logs, migrations, crash recovery
  runtimes\llama.cpp\       versioned engine installations and manifests
  cache\downloads\          resumable partial downloads
  mcp\                       server registry and non-secret metadata

<user-selected model library>\
  <publisher>\<model>\
    manifest.json
    *.gguf
    mmproj-*.gguf            when required
```

Secrets such as Hugging Face tokens and MCP credentials must use Windows Credential Manager or an equivalent encrypted secret store, never plaintext model manifests or MCP registry records.

## 5. Canonical product contracts

Define these contracts before expanding the UI. UI components and API routes must consume them rather than inventing parallel model representations.

### `RuntimeInstallation`

- Engine name and semantic role (`llama.cpp`).
- Exact upstream tag/build and Rasputin manifest version.
- Platform, architecture, accelerator flavor, CUDA runtime compatibility, and file hashes.
- Install state, install path, install time, last verification time, and health result.
- Active/default flag and rollback predecessor.

### `CatalogModel`

- Stable repository identity, publisher, display name, description, tags, license, gated status, update timestamp, downloads, and likes.
- Architecture, parameter count, native context, model type, task/capability hints, chat template/tool-use evidence, and multimodal requirements.
- Catalog origin and last refresh time so offline/stale results are visibly labeled.

### `ModelVariant`

- Exact Hugging Face revision, exact files, LFS object identifiers/hashes, total bytes, quantization, bits per weight, shard set, and optional `mmproj` pairing.
- Estimated RAM/VRAM envelope at selected context and concurrency.
- Compatibility state: supported, experimental, blocked, or unknown, with reasons and next actions.

### `DownloadJob`

- Durable job ID, model/variant identity, destination, temporary files, byte counts, speed, ETA, state, error code, retries, timestamps, and integrity results.
- States: `queued → resolving → downloading ↔ paused → verifying → installing → completed` with terminal `cancelled` and recoverable `failed` branches.
- App restart must reconstruct jobs from storage and resume only after destination and remote revision are revalidated.

### `InstalledArtifact`

- Stable artifact ID independent of any running process.
- Exact source/revision, local files, hashes, size, capabilities, compatibility, and last integrity scan.
- User alias, favorite/pin state, and default load profile ID.

### `LoadProfile`

- Profile ID, artifact ID, profile name, simple/advanced origin, and all user overrides.
- Resolved settings are stored separately from requested settings so the UI can explain what automatic fit changed.
- Profiles can be default, duplicated, reset, exported, and imported without moving model files.

### `ModelInstance`

- Unique instance ID, artifact ID, profile ID, process ID, loopback endpoint, allocated devices, resolved settings, health, timestamps, activity count, and crash information.
- States: `stopped → planning → loading → ready → busy → unloading → stopped`, with `blocked` and `crashed` branches.
- “Installed” and “loaded” must never be synonyms.

### `McpServerRegistration`

- Stable server ID, display name, transport, command or URL, non-secret environment references, working directory, capabilities, protocol version, status, and policy.
- Secret values are referenced by secret-store IDs.
- Tool/resource/prompt discovery snapshots include timestamps and server version.

## 6. Product decisions to freeze before implementation

These defaults keep the project moving without preventing later expansion.

1. **Windows and NVIDIA first.** Ship CPU fallback and current NVIDIA CUDA support first. Treat AMD/Vulkan and non-Windows packages as later compatibility tracks, not blockers for the first daily-driver release.
2. **Bootstrap runtime installation.** Keep the NSIS installer reasonably small. On first launch, the app hardware probe selects and downloads a pinned llama.cpp CPU/CUDA bundle into the versioned runtime directory. Add a larger offline installer only after the online path is proven.
3. **GGUF-only catalog by default.** Hide unsupported formats from the primary catalog. A future conversion workflow must not be implied by cards that cannot load.
4. **Exact-file acquisition.** Never use a full Hugging Face snapshot as the normal model download operation. Resolve and download only the selected GGUF file set plus required projection/config files.
5. **Automatic placement first.** Prefer one fitting GPU, preserving combined VRAM for models that need it. Use multi-GPU layer splitting for oversized models only when the engine and hardware probe say it is viable.
6. **One active instance per artifact for v1.** Support multiple different loaded artifacts if memory permits, but postpone duplicate instances of the same artifact until scheduling and API consumers require them.
7. **App-owned inference endpoint.** Each instance gets an app-reserved loopback port. The user sees model state, not port management.
8. **MCP after model reliability.** Keep the existing guarded local-stdio foundation, but do not make MCP a release blocker for the first catalog/download/load milestone.

## 7. Advanced llama.cpp load model

The settings UI needs two layers: a safe **Automatic** view and an explicit **Advanced** drawer. The app must preview the resolved command and memory plan without requiring users to understand flags.

### Automatic controls

- Context length.
- Performance profile: Conservative, Balanced, Maximum throughput.
- GPU use: Auto, CPU only, selected GPU, multi-GPU auto.
- KV cache: GPU preferred or RAM.
- Idle unload: Never or a selectable TTL.
- Estimated RAM/VRAM before load, with fit confidence and margin.

### Advanced controls

| Product control | llama.cpp mapping | Rules |
|---|---|---|
| GPU layers | `--gpu-layers` | Default `auto`; exact value is expert-only |
| Device fit | `--fit`, `--fit-target`, `--fit-ctx` | Record every automatic adjustment |
| GPU split mode | `--split-mode none/layer/row/tensor` | `tensor` is experimental; show a warning and version gate |
| Tensor split | `--tensor-split` | Auto from measured free VRAM or explicit proportions |
| Main GPU | `--main-gpu` | Device IDs come from the backend probe, never UI list order alone |
| KV cache offload | `--kv-offload` / `--no-kv-offload` | This is the main “KV cache to GPU” switch |
| K/V cache type | `--cache-type-k`, `--cache-type-v` | Start with `f16`, `q8_0`, and `q4_0`; gate other types by runtime version |
| Flash attention | `--flash-attn` | Auto by model/runtime compatibility, with a visible resolved value |
| Context | `--ctx-size` | Validate against model metadata and memory plan |
| Eval batch | `--batch-size`, `--ubatch-size` | Advanced only; provide safe presets |
| Parallel slots | `--parallel` | Default 1 until scheduler and KV estimates account for concurrency |
| CPU threads | `--threads`, `--threads-batch` | Default from hardware probe |
| Memory/load mode | current llama.cpp load-mode controls | Version-gate deprecated mmap/mlock flags |
| MoE CPU placement | `--cpu-moe`, `--n-cpu-moe` | Expert, architecture-gated |

Do not describe all of these as “KV cache splitting.” llama.cpp distinguishes KV cache GPU offload and cache data types from multi-GPU model split modes. Current llama.cpp documents `layer` as splitting layers and KV across GPUs and `tensor` as splitting weights and KV experimentally. The UI must describe the engine's actual behavior for the pinned version and avoid promising arbitrary per-GPU KV placement that the runtime cannot guarantee.

Every load attempt produces a `ResolvedLoadPlan` containing:

- requested settings;
- final flags;
- devices and expected allocations;
- free-memory snapshot and safety margin;
- warnings and automatic changes;
- reason the plan is accepted or blocked.

## 8. Milestone and dependency map

```text
M0 contracts and deterministic fixtures
 ├─ M1 runtime installer
 ├─ M2 catalog + exact variants
 │    └─ M3 persistent downloader
 └─ M4 load profiles + instance scheduler
          ▲       ▲
          └── M1 ─┘

M1 + M2 + M3 + M4
          └─ M5 desktop Models experience
                    └─ M6 Chat and coding integration
                              ├─ M7 installer, update, recovery, release proof
                              └─ M8 MCP productization
                                        └─ M9 daily-driver release gate
```

Do not start M5 as a large visual rewrite while the contracts in M0–M4 are still changing. UI prototypes may run in parallel, but production wiring follows stable contracts.

## 9. Execution milestones

### M0 — Freeze contracts and create deterministic fixtures

**Objective:** Establish one model lifecycle vocabulary, durable schemas, and test doubles before adding product behavior.

**Work packages**

- **M0.1 State contracts:** Add typed schemas and database migrations for runtime installations, catalog models/variants, download jobs, installed artifacts, load profiles, model instances, and MCP registrations.
- **M0.2 API contracts:** Define routes/events for catalog detail, variant listing, download commands, runtime installation, load planning, load/unload, instance logs, and model lifecycle events. Keep compatibility adapters for existing callers during migration.
- **M0.3 Fake Hugging Face fixture:** Create a local fixture with a normal GGUF, a sharded GGUF, an `mmproj`, gated metadata, hash mismatch, interrupted transfer, and changed revision.
- **M0.4 Fake llama-server fixture:** Simulate version/help output, load progress, health, inference, OOM, unsupported flag, crash, and graceful/forced stop.
- **M0.5 Event stream:** Pick one backend-to-renderer lifecycle event mechanism and define monotonic sequence IDs so the UI can recover after sleep or reconnect.

**Likely code areas**

- `backend/models/`
- `backend/runtime_store.py` or the current persistence layer
- `backend/api/core.py`
- new targeted test fixtures under existing backend test conventions

**Acceptance gate**

- Migrations upgrade a copy of an existing data directory without losing model registry records.
- Every state transition rejects invalid predecessor states.
- Contract tests prove that an interrupted event client can fetch a snapshot and resume from a sequence ID.
- No UI implementation is required for this milestone.

### M1 — Build the llama.cpp runtime installer and version manager

**Objective:** Make a fresh Rasputin installation able to acquire, verify, select, repair, upgrade, and roll back its own llama.cpp engine.

**Work packages**

- **M1.1 Signed runtime manifest:** Pin an upstream llama.cpp release/build and list Windows x64 CPU and supported CUDA assets, required companion DLL bundles, sizes, hashes, and licenses. Generate and sign the manifest in Rasputin release CI.
- **M1.2 Hardware/driver selection:** Extend the hardware probe to select CPU, CUDA 12/13, or later Vulkan flavor based on actual adapter/driver capabilities. Return a reasoned recommendation and fallback.
- **M1.3 Durable installer:** Download to a temporary version directory, verify every hash, extract safely, run `llama-server --version` and a health smoke test, then atomically activate the installation.
- **M1.4 Repair and rollback:** Preserve the previous known-good runtime. A failed update never replaces it. Add Repair, Switch version, and Remove unused version actions.
- **M1.5 First-run UX:** Show one guided engine setup card with download size, selected acceleration, progress, license attribution, and a CPU fallback action.
- **M1.6 Supervisor integration:** Replace ad hoc path discovery as the default with `RuntimeInstallation` resolution. Keep environment/PATH overrides as developer-only diagnostics.

**Likely code areas**

- new `backend/runtime/llamacpp_installer.py` and manifest models
- `backend/warsat/providers/native_llamacpp.py`
- `backend/api/core.py` or a dedicated runtime router
- `desktop/backend-supervisor.cjs`
- `frontend-src/src/features/models/ModelSettings.jsx`
- `package.json`, `electron-builder.yml`, release workflows

**Acceptance gate**

- On a clean Windows VM with no Python, Node, Docker, or llama.cpp, the installed app selects and installs a runtime without a terminal.
- Corrupt archives, missing DLLs, low disk space, interrupted downloads, and unsupported drivers produce recoverable errors.
- A deliberately bad runtime update leaves the previous runtime active.
- Real `llama-server --version`, health, and tiny-model inference pass on CPU and the target NVIDIA machine.

### M2 — Replace coarse search with a proper GGUF catalog and variant resolver

**Objective:** Let users browse supported models and make an informed exact-file choice before downloading.

**Work packages**

- **M2.1 Catalog source adapter:** Keep Hugging Face as the live source, add pagination and caching, and default to GGUF-capable text-generation and embedding models. Preserve popularity order as downloads then likes.
- **M2.2 Offline seed catalog:** Ship a small signed starter catalog so Discover remains useful offline and visibly mark its snapshot date.
- **M2.3 Model detail resolver:** Fetch repository metadata, README summary, license/gating state, sibling files, revisions, architecture, parameters, context, chat template, and capability hints.
- **M2.4 Variant grouping:** Parse quantization names, multipart shard families, split GGUFs, and `mmproj` pairings into selectable `ModelVariant` records. Never show one shard as a complete model.
- **M2.5 Exact fit planner:** Combine exact bytes, quantization, context, KV type, parallel slots, current free VRAM/RAM, and runtime overhead. Show Fits GPU, Fits with split, Fits RAM/partial offload, Does not fit, or Unknown.
- **M2.6 Suitability and trust:** Show model type, tool-use confidence, coding suitability, multimodal requirements, license, gated access, uploader, update recency, and a direct source link. Unknown evidence remains Unknown.
- **M2.7 Auth flow:** Store the Hugging Face token in the OS secret store and support gated-model acceptance/error recovery without logging credentials.

**Likely code areas**

- `backend/models/catalog.py`
- `backend/models/resource_manifest.py`
- new catalog/variant schema modules and tests
- `backend/api/core.py`
- `frontend-src/src/features/models/ModelsView.jsx`

**Acceptance gate**

- Search supports keywords, `publisher/model`, and full Hugging Face URLs.
- A model-detail response deterministically groups representative single-file, sharded, and multimodal fixtures.
- The selected variant's exact files and total bytes are displayed before Download is enabled.
- Pagination, refresh, filter accuracy, keyboard navigation, and scroll reset have automated UI coverage.
- Cards never offer Download/Load for unsupported formats without a clear alternative.

### M3 — Build a persistent, resumable model download manager

**Objective:** Download only the selected model variant and make acquisition dependable across pauses, failures, and app restarts.

**Work packages**

- **M3.1 Replace snapshot downloads:** Move the normal path from `snapshot_download` to exact-file transfers based on `ModelVariant`. Download all required shards and optional projection files, nothing else.
- **M3.2 Durable job queue:** Persist jobs and transitions in the database. Limit concurrency, reserve disk space, and allow queued jobs to be reordered later without changing correctness.
- **M3.3 Transfer controls:** Implement pause, resume, cancel, retry, and app-restart recovery using range requests or the supported Hugging Face client primitives.
- **M3.4 Integrity and atomic install:** Write `.part` files, verify source revision and LFS/hash identity, then atomically move a complete artifact into the model library and write its manifest.
- **M3.5 Destination management:** Let users choose a model library, validate writability and free space, migrate or relink an existing library, and safely clean abandoned partials.
- **M3.6 Progress events:** Report per-file and aggregate bytes, speed, ETA, phase, and actionable errors without polling every card independently.
- **M3.7 Sideload/index:** Retain GGUF import and scanning, but index imported artifacts through the same `InstalledArtifact` contract and integrity workflow.

**Likely code areas**

- replace/refactor `backend/models/acquisition.py`
- `backend/models/registry.py`
- dedicated download API/event routes
- `frontend-src/src/features/models/ModelsView.jsx` or extracted download components

**Acceptance gate**

- A repository containing ten quantizations downloads only the selected variant.
- Pausing and restarting the app resumes without redownloading completed bytes.
- Cancel removes uncommitted partials after confirmation; retry preserves reusable verified parts.
- Hash mismatch, changed upstream revision, disk-full, lost network, expired auth, and moved destination are covered by deterministic tests.
- Completed jobs create exactly one valid `InstalledArtifact`; incomplete jobs never appear as loadable models.

### M4 — Build load profiles, placement planning, and the native model instance scheduler

**Objective:** Turn an installed GGUF into a supervised, observable llama.cpp instance with automatic or advanced settings.

**Work packages**

- **M4.1 Load-profile schema/API:** Add profile CRUD, duplication, reset, import/export, default assignment, requested settings, and resolved settings.
- **M4.2 Placement planner:** Re-probe free resources immediately before load. Prefer a fitting single GPU; use layer split plus fit for oversized GGUFs; account for context, KV cache, parallelism, currently loaded models, and safety margins.
- **M4.3 Flag capability probe:** Parse the installed runtime's version/help output and maintain a compatibility map. Never pass a flag solely because a newer upstream README documents it.
- **M4.4 Process lifecycle:** Reserve a loopback port, spawn with a minimal environment, stream logs/progress, wait for health, register the instance, and stop gracefully before force termination.
- **M4.5 Readiness and failure mapping:** Convert common load errors—OOM, unsupported architecture, corrupt GGUF, invalid split, missing mmproj, driver/backend failure—into stable error codes and recovery actions.
- **M4.6 Scheduler:** Enforce memory reservations, model load concurrency, optional idle TTL, auto-eviction policy, and app-sleep/shutdown behavior.
- **M4.7 Crash recovery:** Reconcile PID records on startup, clear stale ownership, preserve crash logs, and offer Reload with previous settings or Safe settings.
- **M4.8 Telemetry:** Capture load time, prompt/decode speed, actual device allocations, peak memory where available, context/KV configuration, and runtime build. Keep telemetry local unless the user explicitly opts in to export.

**Likely code areas**

- `backend/warsat/providers/native_llamacpp.py`
- `backend/models/registry.py`
- `backend/models/resource_manifest.py`
- `backend/models/providers.py`
- new scheduler/profile/instance modules and API routes

**Acceptance gate**

- The fake engine covers every state and error transition.
- A real small GGUF loads, serves a streamed completion, and unloads with no orphan process.
- On the mixed-GPU target, a fitting model chooses one GPU; an oversized supported model uses a measured multi-GPU plan; an impossible plan is blocked before spawn.
- Automatic and manual load plans echo exact resolved settings and command arguments.
- App close, crash, sleep/wake, and backend restart leave no hidden llama.cpp process or stale Ready state.

### M5 — Deliver the LM Studio-style Models desktop experience

**Objective:** Make Discover → Download → Library → Load → Running understandable and fast without exposing internal deployment concepts.

**Work packages**

- **M5.1 Navigation language:** Use Discover, Downloads, My Models, and Running. Remove WarSat/container/deploy language from the desktop edition.
- **M5.2 Discover page:** Curated starter rows, search, filters, pagination, fit badges, format/quantization summary, source/trust information, and clear empty/error/offline states.
- **M5.3 Model detail:** Add a detail view/drawer with model card summary, license, capabilities, variants table, exact file set, size, fit estimate, quantization explanation, destination, and Download action.
- **M5.4 Download center:** Persistent global tray with queue, progress, speed, ETA, destination, pause/resume/cancel/retry, and post-download Load action.
- **M5.5 My Models:** Installed artifacts grouped by model, with variants, disk usage, favorite, reveal in Explorer, verify, relink, delete, default profile, and Load.
- **M5.6 Load dialog:** Automatic settings first; Advanced controls in a reviewable drawer; resolved memory/device preview; warnings; Save profile; Load.
- **M5.7 Running page:** Instance state, model/profile, context, device allocation, memory, tokens/second, active clients, logs, TTL, Open Chat, and Unload.
- **M5.8 Desktop polish:** Keyboard shortcuts, accessible dialogs, screen-reader status updates, compact/comfortable density, optimistic actions only where rollback is safe, and no layout restructuring of the existing Chat page.

**Likely code areas**

- split `frontend-src/src/features/models/ModelsView.jsx` into focused components/hooks while preserving the current app shell
- `frontend-src/src/features/models/ModelSettings.jsx`
- shared desktop state/event client
- targeted Playwright specs

**Acceptance gate**

- A keyboard-only user can search, inspect a variant, download, load, open Chat, unload, and delete.
- UI state remains correct after backend restart and app relaunch.
- Every long operation shows progress and remains cancellable where safe.
- The production frontend is rebuilt from `frontend-src/`; generated `frontend/` files are never hand-edited.
- Playwright proves pagination scroll reset, filter refresh, filter accuracy, dialog focus, download recovery, load progress, and failure recovery.

### M6 — Integrate model lifecycle with Chat and agentic coding

**Objective:** Make installed local models useful as a daily driver, not merely manageable from a Models screen.

**Work packages**

- **M6.1 Unified model picker:** Chat, Assistant, task launch, trials, and role settings consume installed artifacts and running instances from one query contract.
- **M6.2 Auto-load:** Selecting an installed but stopped model prompts or automatically loads its default profile, streams load events, and continues the original request without losing draft input.
- **M6.3 Capability certification:** Test chat template, streaming, reasoning output handling, tool-call format, structured output, context, and coding suitability per artifact/runtime/profile combination.
- **M6.4 Safe task routing:** Tool-dependent modes require a passing tool certificate and available tool providers. Otherwise show the reason and offer Chat-only or another capable model before the task starts.
- **M6.5 Coding workflow proof:** Select workspace → ask for an edit → inspect plan → edit → run tests → repair failure → show diff → request approval before commit/push.
- **M6.6 Context and memory:** Keep chat history, workspace context, and bounded memory independent from model process lifetime so unload/reload does not lose the session.
- **M6.7 Optional developer API:** Expose OpenAI-compatible loopback endpoints only when enabled in Settings. Add token auth, visible endpoint/port, loaded-model mapping, and LAN warnings. This is app-managed and not required for ordinary Chat.

**Likely code areas**

- `frontend-src/src/features/chat/`
- `frontend-src/src/features/assistant/`
- task/model routing modules in `backend/`
- `backend/models/providers.py`
- capability certification and scorecard modules/tests

**Acceptance gate**

- Chat can select a stopped model, load it, stream a response, and later unload it without losing the conversation.
- A non-tool-capable model cannot enter a tool-required coding task silently.
- The live coder-model workflow completes edit → test → repair → diff review on a disposable repository.
- No Docker/WSL process or Docker-facing API is invoked during desktop model or coding flows.

### M7 — Finish installer, update, migration, and recovery productization

**Objective:** Turn the working branch into a clean-machine, upgradeable, recoverable Windows application.

**Work packages**

- **M7.1 Package closure:** Ensure PyInstaller includes every backend dependency, Electron includes the correct frontend/backend artifacts, and the first-run runtime installer needs no development checkout.
- **M7.2 Branding and metadata:** Final icons, executable metadata, protocol name, Start Menu shortcut, Add/Remove Programs metadata, diagnostics bundle, and license notices.
- **M7.3 Code signing:** Authenticode-sign the installer and packaged executables in CI. Keep credentials outside the repository.
- **M7.4 Auto-update:** Add `electron-updater`, signed release metadata, update checks, progress, defer/restart actions, staged rollout support, and rollback/recovery documentation.
- **M7.5 Data migrations:** Version app data, runtime manifests, installed artifacts, load profiles, and MCP records. Back up before migration and never delete model files as an automatic migration side effect.
- **M7.6 Uninstall choices:** Default to preserving model library and user data. Offer an explicit, separately confirmed cleanup path that lists exact paths and sizes.
- **M7.7 Diagnostics/recovery:** One-click checks for backend, runtime hash/version, driver, model library, partial downloads, stale processes, loopback ports, database migrations, and MCP child processes.

**Acceptance gate**

- Clean install, first launch, runtime install, model download/load/chat, in-place upgrade, rollback from a bad update, uninstall-preserve, and reinstall-relink pass on clean Windows VMs.
- Windows shows the expected verified publisher for the installer and executable.
- Update signature mismatch is rejected.
- The packaged application works after the source checkout and development runtimes are removed.
- An installer failure or app update never deletes the model library.

### M8 — Productize MCP server availability

**Objective:** Make MCP servers discoverable and safely usable by local models and coding tasks without Docker.

The current branch already has a guarded local-stdio relay with registration approval, process start/stop/restart/test, tool/resource/prompt discovery, tool classification, execution approval, and audit. Extend that foundation instead of replacing it blindly.

**Work packages**

- **M8.1 SDK-backed protocol layer:** Move protocol parsing/lifecycle to the official MCP SDK where practical. Retain stable Rasputin policy and audit contracts around it.
- **M8.2 Transport support:** Keep stdio for app-launched local servers. Add authenticated Streamable HTTP for remote servers. Treat legacy HTTP+SSE as compatibility-only; do not make it the new default.
- **M8.3 Registry UX:** Add server by command/package recipe or URL; name it; choose workspace/session scope; reference secrets; review command, cwd, network target, and permissions; then Test and Enable.
- **M8.4 Secrets/environment:** Pass a minimal allow-listed environment to stdio children and inject only explicitly selected secret references. Redact logs and exported diagnostics.
- **M8.5 Discovery and compatibility:** Paginate and cache tools/resources/prompts, show server/protocol version, refresh on change, validate schemas, and preserve unsupported capability explanations.
- **M8.6 Policy:** Per-server and per-tool enablement, read/write/network risk classification, one-time or session approvals, unattended-mode denial, workspace boundaries, timeout/output limits, and audit events.
- **M8.7 Agent bridge:** Add approved MCP tools to the tool catalog only when the selected model/profile has a passing tool certificate. Preserve tool-call IDs, cancellation, structured content, errors, and progress.
- **M8.8 Packaging recipes:** Provide optional vetted install recipes for common local servers, but never silently install Node/Python package managers. A recipe must show dependencies, command, source, permissions, and uninstall steps.
- **M8.9 End-to-end proof:** Use deterministic fixture servers plus at least one real read-only filesystem or Git MCP server and one Streamable HTTP server.

**Likely code areas**

- `backend/mcp/relay.py`
- `backend/api/mcp_routes.py`
- tool hub, approvals, audit, unattended policy, and task routing
- Connector/Integration settings UI and dedicated MCP management components

**Acceptance gate**

- A local stdio server can be registered, approved, started, discovered, safely called, stopped, and recovered after app restart.
- A Streamable HTTP server works with authentication, TLS validation, timeouts, and cancellation.
- Secrets do not appear in logs, API payloads, exports, or crash reports.
- Disabled/unclassified tools cannot execute, and approval-required tools cannot bypass approval.
- A certified local model completes an MCP-assisted task; an uncertified model is blocked before task start with a safe fallback.

### M9 — Daily-driver release gate

**Objective:** Prove the full product outcome on real hardware and a clean installation before calling the desktop edition complete.

**Release scenario**

1. Install the signed Rasputin package on a clean Windows account.
2. Complete first-run runtime setup with the recommended NVIDIA llama.cpp build.
3. Search the catalog, inspect model details, compare quantizations, and select a fitting coding GGUF.
4. Pause the download, close Rasputin, reopen, resume, and complete integrity verification.
5. Load with Automatic settings and confirm the resolved single-GPU plan.
6. Run Chat streaming and record prompt/decode performance.
7. Unload, choose an oversized test model, review a multi-GPU layer-split plan, load if it fits, and verify both adapters' actual allocations.
8. Execute the full coding workflow against a disposable repository, including an induced test failure and repair.
9. Add and use one approved MCP server, then prove an unapproved MCP tool cannot execute.
10. Upgrade Rasputin, verify models/profiles/chats/MCP records persist, then uninstall while preserving model data.

**Release gate**

- No terminal, Docker, WSL, Python, Node, or manual `llama-server` installation is used.
- No orphan child process remains after unload, app exit, crash simulation, or uninstall.
- Model source, exact variant, license, files, hashes, runtime version, resolved load settings, and test results are inspectable.
- Every failure in the scenario has an actionable in-app recovery path.
- The real coding loop and MCP tool path have saved evidence, not only unit-test claims.

## 10. Luuna execution protocol

Run one work package or one tightly coupled package group at a time. Do not ask Luuna to “build the whole LM Studio replacement” in one pass.

Each Luuna work order should use this structure:

```text
Objective
One outcome-focused sentence using the work-package ID.

Context
- Branch: codex/desktop-llamacpp
- Current contracts and exact files involved
- Prior milestone conclusions that this work depends on

Constraints
- Desktop-only; no Docker model path
- llama.cpp is the inference engine
- Preserve unrelated dirty-tree changes
- Source frontend changes only in frontend-src/
- No commit or push unless separately authorized
- Match current code style; no drive-by refactors

Acceptance criteria
- Exact commands and expected states from this document
- Targeted unit/integration/UI tests
- Real-engine or clean-VM proof only where the milestone requires it

Report
- Files changed and key line ranges
- Test commands, exit codes, and concise output
- Any contract or assumption contradicted by the code
- Remaining proof boundary
```

### Recommended execution batches

| Batch | Work packages | Can run in parallel? | Merge/proof condition |
|---|---|---|---|
| A | M0.1–M0.5 | Partly; schemas and API contracts should be serialized | All contract/fixture tests pass |
| B | M1.1–M1.3 and M2.1–M2.4 | Runtime and catalog tracks can run in parallel | Signed manifest fixture and variant fixtures pass |
| C | M1.4–M1.6, M2.5–M2.7, M3.1–M3.4 | Parallel by subsystem, then integration | Fresh runtime and exact-file download both work |
| D | M3.5–M3.7 and M4.1–M4.4 | Parallel until artifact/profile integration | Installed artifact can produce a resolved load plan |
| E | M4.5–M4.8 | Mostly serialized around scheduler state | Real model lifecycle gate passes |
| F | M5.1–M5.8 | Component work can split after API contracts freeze | Full Playwright model journey passes |
| G | M6.1–M6.7 | Split Chat, certification, and optional API carefully | Live coding workflow passes |
| H | M7.1–M7.7 | CI/signing and recovery UI can parallelize | Clean-VM install/upgrade matrix passes |
| I | M8.1–M8.9 | Transport and UI can parallelize after policy contract | MCP end-to-end proof passes |
| J | M9 | No; run as one release qualification | Evidence bundle approved |

After every batch:

1. Review changed hunks against the contracts in sections 5–7.
2. Run targeted tests, then the backend smoke suite and frontend build where relevant.
3. Run the native verification workflow for runtime/UI integration changes.
4. Record what was implemented, what was actually verified, and what remains hardware- or installer-unverified.
5. Do not begin the next dependent batch with a red gate.

## 11. Test strategy

### Always-on automated tests

- Schema migration and state-machine unit tests.
- Catalog parsing/variant grouping against saved metadata fixtures.
- Download interruption, resume, integrity, disk-full, auth, and revision-change tests.
- Runtime-manifest selection and safe extraction tests.
- llama.cpp command construction and version/flag compatibility tests.
- Scheduler reservation, eviction, crash reconciliation, and port ownership tests.
- MCP transport, schema, policy, approval, timeout, cancellation, and redaction tests.
- Frontend component tests for state and accessibility.
- Playwright for the complete user journeys.

### Required native integration tests

- Real llama.cpp CPU tiny-model inference in CI or a controlled runner.
- Real NVIDIA single-GPU model load/inference/unload.
- Mixed/unequal NVIDIA GPU placement on the target workstation.
- App close/crash/sleep/wake process cleanup.
- Model library on a secondary drive and a temporarily disconnected drive.
- Offline launch with an installed runtime and model.

### Installer matrix

- Clean Windows account.
- Existing older Rasputin data directory.
- No internet during first launch.
- Interrupted runtime install and interrupted model download.
- Insufficient disk space.
- Unsigned/tampered update fixture.
- Upgrade, downgrade/rollback, uninstall-preserve, uninstall-clean, and reinstall/relink.

## 12. Risk register

| Risk | Why it matters | Mitigation/gate |
|---|---|---|
| llama.cpp flags change rapidly | A pinned runtime may not match current upstream docs | Pin build, parse local help/version, capability-gate every advanced option |
| CUDA asset/runtime mismatch | `llama-server.exe` may start but fail to load CUDA DLLs | Manifest exact companion assets; first-run executable and tiny-model smoke |
| Unequal GPUs produce unstable splits | Naive ratios can OOM or use the wrong device order | Probe runtime-visible devices, prefer one GPU, use fit margins, save actual allocation evidence |
| Catalog metadata is incomplete | Fit/capability claims can mislead | Confidence labels, exact file analysis, Unknown state, post-load certification |
| Huge or sharded downloads corrupt easily | Users lose hours and disk space | Durable parts, exact revision, hashes, atomic finalize, restart tests |
| Background processes survive app failure | Hidden VRAM use makes the app untrustworthy | Parent ownership, process groups/job objects, PID reconciliation, shutdown/crash tests |
| Desktop still exposes legacy Docker concepts | Product feels like a wrapped server, not a native tool | Desktop feature flags first, then remove dead UI/API paths after migration tests |
| MCP servers can execute arbitrary code | A convenient connector can become a local compromise | Command review, secret isolation, minimal env, policy classification, approval, audit, unattended denial |
| Signing/update work is postponed | The app cannot become a dependable daily driver | M7 is a release gate, not optional cleanup |

## 13. Definition of done

Rasputin Desktop is done for the requested outcome only when all of the following are true:

- A non-developer can install and launch it from Windows without a terminal.
- The app installs and repairs its own compatible llama.cpp runtime.
- Discover shows a credible, filterable, paginated GGUF catalog with exact variants and device-fit explanations.
- Downloads are exact-file, persistent, resumable, cancellable, integrity-checked, and recoverable after restart.
- Installed artifacts can be loaded and unloaded through automatic or advanced profiles, including GPU/KV/cache/split controls supported by the pinned engine.
- The app clearly separates downloaded models from loaded instances and shows live state, memory allocation, logs, and performance.
- Chat and a full agentic coding loop work with a locally loaded model and safe capability routing.
- The packaged app is signed, updateable, migration-safe, and proven on a clean Windows machine.
- MCP stdio and Streamable HTTP servers can eventually be registered and safely used with approvals, capability checks, and secret isolation.
- No required daily-driver path depends on Docker, WSL, Python, Node, or a terminal.

## 14. External behavior references

These are behavioral references, not code dependencies. Re-check them when each related milestone begins because the products and runtimes evolve quickly.

- [LM Studio: Download an LLM](https://lmstudio.ai/docs/app/basics/download-model)
- [LM Studio: Download model API](https://lmstudio.ai/docs/developer/rest/download)
- [LM Studio: Load model API](https://lmstudio.ai/docs/developer/rest/load)
- [LM Studio: Local model API and lifecycle](https://lmstudio.ai/docs/developer/rest)
- [LM Studio Bionic: model formats, fit, and download controls](https://lmstudio.ai/docs/bionic/models/download-local-models)
- [llama.cpp server options](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases)
- [MCP standard transports](https://modelcontextprotocol.io/specification/draft/basic/transports)
- [Official MCP Python client transports](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/client/transports.md)
- [electron-builder auto-update](https://www.electron.build/docs/features/auto-update/)
- [electron-builder Windows signing](https://www.electron.build/docs/features/code-signing/code-signing-win/)
