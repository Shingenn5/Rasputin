# `WRAPPER_RUNTIME` Contract (native vs Docker)

*Authored 2026-07-11 and re-audited 2026-07-13 after the dual-mode security work completed.*

`WRAPPER_RUNTIME` is the single switch that tells the wrapper whether it is running **inside the
Docker container** (`WRAPPER_RUNTIME=docker`, set by the Dockerfile) or **natively on the host**
(unset, or `native`). The rule every branch obeys:

> A `WRAPPER_RUNTIME` branch may only change **network reachability**, **filesystem access mode**,
> **execution/security topology**, or **telemetry**. It must NEVER encode a `/app/...` data path or
> otherwise bypass the repository's resolvers. All runtime-state locations go through
> `backend/core/datadir.py` (`data_dir()`), never through an ad-hoc runtime branch.

## Why the branch exists at all

Inside the container, `127.0.0.1` is the wrapper itself; host-published container ports (the
model runtimes WarSat manages, an external vLLM) are reachable only via `host.docker.internal`.
Natively, the wrapper *is* the host, so everything is plain loopback. Filesystem access is the
mirror image: the container reaches host folders through bind mounts / a helper container, while
a native wrapper touches the host FS directly.

## Complete inventory (audited 2026-07-13)

| Site | Docker branch | Native branch | Category |
|---|---|---|---|
| `core/datadir.py:data_dir()` | `<repo>/data` (the named volume) | `%LOCALAPPDATA%\Rasputin\data` | data path (resolver) |
| `warsat/__init__.py` `_discovery_hosts()` | `["host.docker.internal","127.0.0.1"]` | `["127.0.0.1"]` | network |
| `warsat/__init__.py` `_endpoint_for()` | `host.docker.internal` | the model's host binding | network |
| `warsat/__init__.py` preflight (`runtime`,`insideDocker`) | reports `docker`/`true` | reports `native`/`false` | telemetry |
| `warsat/__init__.py` `gpu_live_metrics_via_docker()` | `docker exec` into GPU container | same — host `docker` CLI | telemetry |
| `models/registry.py` `_default_main_url()` | `host.docker.internal:8000` | `127.0.0.1:8000` | network |
| `models/registry.py` `_runtime_base_url()` | rewrites loopback → `host.docker.internal` | returns URL unchanged | network |
| `core/host_fs.py` `_in_docker()` | browse host FS via helper container | browse host FS directly | filesystem |
| `core/workspace.py` `mount_plan()` / `save_mount_request()` | compose bind-mount request + restart | register the approved host path directly; no mount/restart | filesystem |
| `main.py` localhost-bypass startup warning | bypass cannot match the bridge client; no native warning | warns + audits when the explicit bypass is enabled | security |
| `main.py` `_origin_host_reject()` | skipped (compose binds the public port to host loopback) | enforces loopback/allowlisted Host and Origin | security |
| `mcp/layer.py` `shell_exec()` via `workspace.is_native()` | direct subprocess inside the wrapper container | Windows Desktop/native: blocked pending AppContainer isolation; other native OSes: direct subprocess | execution/security |

Skills are declarative `SKILL.md` instructions in every runtime. They use the normal model/tool
policy and do not execute skill-authored Python or launch Docker. The former container image,
Python wrapper, and private stdio RPC runner have been removed.

## Verification

### Hardware capability profile

`GET /api/warsat/hardware` now includes a versioned `capabilityProfile` alongside
the legacy `detectedHardware` payload. The profile keeps device identity and
installed capacity under `devices[].static`, volatile memory/utilization under
`devices[].volatile`, and backend evidence under `backends`. Backend status is
`available`, `observed`, or `unknown`; `observed` is not a runtime/model
compatibility certificate. Unknown acceleration must remain unknown rather than
being presented as supported. The placement hint is
`all_compatible_gpus_first`, and combined VRAM is explicitly marked as
runtime-dependent. llama.cpp/GGUF can layer-shard across heterogeneous cards;
vLLM uses all matching cards automatically and requires exact fresh evidence
before combining a mixed device set.

The resource broker in `backend/warsat/resource_broker.py` is the next safety
boundary: it accounts for active per-device reservations with a bounded
heartbeat/expiry, and returns `ready`, `queued`, `blocked`, `degraded`, or
`unmeasured` without launching a worker. Launch paths must use this decision
before creating a model container. Runtime placement is also explicit: vLLM defaults to all matching
Docker-visible GPUs, respects an explicit single-GPU override, and requires an
exact fresh device-set certificate before mixed-card tensor parallelism.
llama.cpp GGUF defaults to all visible GPUs through its `--fit` layer-sharding
path. Every plan reports the selected devices and any fallback reason for
review.

- `_discovery_hosts()` → `['127.0.0.1']`
- `_endpoint_for('127.0.0.1', 8001)` → `http://127.0.0.1:8001/v1` (not `host.docker.internal`)
- `gpu_live_metrics_via_docker()` → `[]` (no crash; empty when docker-control is off)
- `host_fs._in_docker()` → `False`; `registry._default_main_url()` → `http://127.0.0.1:8000/v1`;
  `_runtime_base_url(loopback)` → unchanged
- Native workspace approval returns `requires_restart=False`; Docker mode continues to produce a
  compose mount request.
- Native Windows/Desktop Host Shell is fail-closed pending a proven AppContainer runner; it never
  falls back to the operator account or creates a dedicated Rasputin Windows account. Docker/server
  mode retains its legacy wrapper-container shell path. Desktop skills do not require Docker.

**Consequence:** WarSat is *simpler* natively — model endpoints are plain `127.0.0.1:port`, and it
drives Docker through the host `docker` CLI (`shutil.which("docker")`) with no
`host.docker.internal` indirection. This satisfies G6 (WarSat stays the centerpiece in both modes).

## Rule for future code

Any new `if WRAPPER_RUNTIME == "docker"` branch must fall into one of the four categories above.
If you find yourself writing a `/app/...` path behind such a branch, stop — route it through
`data_dir()` (or the appropriate resolver) instead. Every branch needs a test exercising **both**
sides (see the plan's dual-mode-drift risk).
