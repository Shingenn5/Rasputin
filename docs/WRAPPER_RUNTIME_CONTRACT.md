# Native runtime contract

Updated 2026-08-29. Windows Desktop and Native Host run the backend directly on the host;
managed model inference uses native llama.cpp child processes and GGUF artifacts. Neither
path uses retired infrastructure. [Deployment and ownership](DEPLOYMENT_MATRIX.md) is the
operational authority.

## Runtime identity and ownership

`workspace.is_native()` identifies a host backend when `WRAPPER_RUNTIME` is unset or native.
`RASPUTIN_DESKTOP_ONLY` additionally selects packaged Desktop restrictions and presentation;
it is not the switch deciding whether native models can run. The frontend uses
`security.native || security.desktopOnly` for native model actions.

| Concern | Desktop | Native Host |
| --- | --- | --- |
| Backend owner | Electron supervisor | Native Host controller |
| Runtime artifact | Packaged backend | Source checkout and repository Python environment |
| Address | Private selected loopback port | Saved listener, default 8788 |
| Registry runtime | `native-llamacpp` | `native-llamacpp` |
| Model execution | Bundled native llama.cpp | Manifest-discovered/configured native llama.cpp |
| State | `data_dir()` | `data_dir()` |

One live owner may use a data directory. Never delete a live ownership record, attach a second
backend to the same store, or restart a different runtime because it happens to use a familiar port.
A source rebuild does not update an installed package.

## Native acquisition and model lifecycle

`backend/models/catalog.py` resolves exact GGUF variants, revisions, companion files, sizes,
and integrity metadata. Download through `/api/models/download`; jobs are durable and completed
artifacts become native registry entries. Exact filename keys in `fileSizes` and `fileHashes`
must survive API camel-casing unchanged. Existing GGUFs use `/api/model-registry/import-gguf`.

`backend/models/registry.py` exposes measured local GGUF sizes, including complete split files
and companions, for planning. Missing or unmeasured files must not produce fabricated capacity.
`backend/models/load_profiles.py` resolves the requested settings and compatibility evidence;
`backend/warsat/providers/native_llamacpp.py` launches the native engine. It discovers the same
manifest used by the runtime service and preserves explicit profile choices over legacy defaults.

The UI distinguishes downloading, installed, loaded, stopped, and failed. A failed start must not
report success. Old managed entries need GGUF recovery/import into the native registry. Raw weights without a compatible GGUF variant are blocked before acquisition.

## Hardware and placement

Native model views request `/api/warsat/hardware?native_models=true`. The backend honors this
host path only for native execution; it does not require a Docker CLI or a container GPU probe.
The `capabilityProfile` separates static device capacity, volatile availability, and backend
observations. Unknown compatibility stays unknown.

Automatic native placement prefers a fitting single GPU, considers RAM/VRAM and context costs,
and uses supported layer splitting only when the model/runtime/device evidence allows it. Total
VRAM alone is not a compatibility certificate. Planning previews and resource-broker contracts
are not proof of cross-process reservation or successful inference.

## Filesystem, security, and skills

- Resolve all runtime state through `backend/core/datadir.py:data_dir()` and honor an isolated
  `RASPUTIN_DATA_DIR`; never hardcode container paths into host code.
- Approved host folders are registered directly. No bind mount or application restart is needed
  to approve a native workspace. Workspace, owner, file-access, and path-traversal checks still apply.
- Model endpoints use loopback without `host.docker.internal` rewriting.
- Preserve Native Host password/session authentication and Desktop's loopback-only local
  administrator session. Both retain Host/Origin, capability, workspace, and audit checks;
  Desktop auto-login is not isolation from other local processes and must never serve LAN users.
- Native Windows Host Shell remains fail-closed until a proven AppContainer runner exists.
  Native model loading does not grant arbitrary shell access or bypass model-registry permissions.
- Skills are declarative `SKILL.md` instructions using the normal governed tools. They do not
  execute skill-authored Python or require a container runner.
- Retired infrastructure settings must not become native prerequisites or operator-facing features.
  Legacy state does not override the native product boundary.

## Legacy compatibility boundary

`WRAPPER_RUNTIME=docker` and container providers remain compatibility code, not the current
product direction. Their branches may change network reachability, filesystem topology,
execution/security boundaries, or telemetry. They must not bypass shared state resolvers or
weaken authorization. A legacy provider test is not native release evidence; label it accordingly.
Do not route a native model action to a container provider to work around a failed native load.

## Verification

Use an isolated store and real authentication. Test exact-variant acquisition, registration,
load-plan preview, native launch, actual inference, stop, and visible retryable failures with
native-only execution. `backend/models/test_native_acquisition.py`, the native provider suite,
and `tests/nativeDeployment.test.mjs` cover key regressions. Keep live model proof distinct from
mocked contract tests and from packaged clean-machine release certification.
