# `WRAPPER_RUNTIME` Contract (native vs Docker)

*Authored 2026-07-11 as the Phase 1 path-audit deliverable of
[`DUAL_MODE_ARCHITECTURE_PLAN.md`](DUAL_MODE_ARCHITECTURE_PLAN.md).*

`WRAPPER_RUNTIME` is the single switch that tells the wrapper whether it is running **inside the
Docker container** (`WRAPPER_RUNTIME=docker`, set by the Dockerfile) or **natively on the host**
(unset, or `native`). The rule every branch obeys:

> A `WRAPPER_RUNTIME` branch may ONLY change **network reachability**, **filesystem access mode**,
> or **telemetry**. It must NEVER encode a `/app/...` container path or otherwise assume the
> container layout. All data locations go through `backend/core/datadir.py` (`data_dir()`), never
> through a runtime branch.

## Why the branch exists at all

Inside the container, `127.0.0.1` is the wrapper itself; host-published container ports (the
model runtimes WarSat manages, an external vLLM) are reachable only via `host.docker.internal`.
Natively, the wrapper *is* the host, so everything is plain loopback. Filesystem access is the
mirror image: the container reaches host folders through bind mounts / a helper container, while
a native wrapper touches the host FS directly.

## Complete inventory (audited 2026-07-11)

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
| `core/sandbox.py` skills sandbox | `RASPUTIN_API_URL` default loopback; `--network host` | same | network (Phase 4 hardens `--network host`) |

## Verification (2026-07-11, native process, `WRAPPER_RUNTIME` unset)

- `_discovery_hosts()` → `['127.0.0.1']`
- `_endpoint_for('127.0.0.1', 8001)` → `http://127.0.0.1:8001/v1` (not `host.docker.internal`)
- `gpu_live_metrics_via_docker()` → `[]` (no crash; empty when docker-control is off)
- `host_fs._in_docker()` → `False`; `registry._default_main_url()` → `http://127.0.0.1:8000/v1`;
  `_runtime_base_url(loopback)` → unchanged

**Consequence:** WarSat is *simpler* natively — model endpoints are plain `127.0.0.1:port`, and it
drives Docker through the host `docker` CLI (`shutil.which("docker")`) with no
`host.docker.internal` indirection. This satisfies G6 (WarSat stays the centerpiece in both modes).

## Rule for future code

Any new `if WRAPPER_RUNTIME == "docker"` branch must fall into one of the three categories above.
If you find yourself writing a `/app/...` path behind such a branch, stop — route it through
`data_dir()` (or the appropriate resolver) instead. Every branch needs a test exercising **both**
sides (see the plan's dual-mode-drift risk).
