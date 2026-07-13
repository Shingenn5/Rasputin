# `WRAPPER_RUNTIME` Contract (native vs Docker)

*Authored 2026-07-11 as the Phase 1 path-audit deliverable of
[`DUAL_MODE_ARCHITECTURE_PLAN.md`](DUAL_MODE_ARCHITECTURE_PLAN.md); re-audited
2026-07-13 after Phases 3–4 completed.*

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
| `mcp/layer.py` `shell_exec()` via `workspace.is_native()` | direct subprocess inside the wrapper container | Windows: `Rasputin_sbx` run-as + workspace ACL; other native OSes: direct subprocess | execution/security |

`core/sandbox.py` is intentionally **not** runtime-branched: in both modes every Skill runs as
`docker run -i --rm --network none rasputin-sandbox ...` and calls host tools over its private
stdio RPC. Phase 4 removed the former `RASPUTIN_API_URL` / `--network host` topology.

## Verification

- `_discovery_hosts()` → `['127.0.0.1']`
- `_endpoint_for('127.0.0.1', 8001)` → `http://127.0.0.1:8001/v1` (not `host.docker.internal`)
- `gpu_live_metrics_via_docker()` → `[]` (no crash; empty when docker-control is off)
- `host_fs._in_docker()` → `False`; `registry._default_main_url()` → `http://127.0.0.1:8000/v1`;
  `_runtime_base_url(loopback)` → unchanged
- Native workspace approval returns `requires_restart=False`; Docker mode continues to produce a
  compose mount request.
- Native Windows Host Shell routes through `CreateProcessWithLogonW` as `Rasputin_sbx`; Docker mode
  keeps execution inside the wrapper container. Skills use `--network none` in both modes.

**Consequence:** WarSat is *simpler* natively — model endpoints are plain `127.0.0.1:port`, and it
drives Docker through the host `docker` CLI (`shutil.which("docker")`) with no
`host.docker.internal` indirection. This satisfies G6 (WarSat stays the centerpiece in both modes).

## Rule for future code

Any new `if WRAPPER_RUNTIME == "docker"` branch must fall into one of the four categories above.
If you find yourself writing a `/app/...` path behind such a branch, stop — route it through
`data_dir()` (or the appropriate resolver) instead. Every branch needs a test exercising **both**
sides (see the plan's dual-mode-drift risk).
