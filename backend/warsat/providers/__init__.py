import os

from .base import DeploymentProvider
from .docker import DockerProvider
from .native_llamacpp import NativeLlamaCppProvider, NATIVE_RUNTIME

_docker_provider = DockerProvider()


def _native_hardware_snapshot(model=None):
    # Import lazily to avoid a package-initialization cycle. Native launches
    # always plan against current host capacity, not a stale download-time
    # snapshot.
    from backend import warsat

    snapshot = dict(warsat.hardware_probe())
    headroom = (model or {}).get("host_memory_headroom_mb")
    if headroom is not None:
        snapshot["host_memory_headroom_mb"] = headroom
    return snapshot


_native_llamacpp_provider = NativeLlamaCppProvider(
    hardware_snapshot_provider=_native_hardware_snapshot,
)

def get_provider(model: dict) -> DeploymentProvider:
    """
    Returns the appropriate deployment provider for the given model runtime.
    Raises ValueError if the runtime is unsupported or unmanaged.
    """
    if not model.get("managed"):
        raise ValueError("Model is external/unmanaged and has no deployment provider.")

    runtime = model.get("runtime")
    desktop_only = str(os.environ.get("RASPUTIN_DESKTOP_ONLY", "")).strip().lower() in {"1", "true", "yes", "on"}
    if desktop_only and (runtime == "docker-llamacpp" or str(runtime or "").startswith("warsat-")):
        raise ValueError("Desktop mode supports only native llama.cpp deployments.")
    if runtime == NATIVE_RUNTIME:
        return _native_llamacpp_provider
    # WarSat registers deployed models with runtime f"warsat-{protocol['runtime']}"
    # (e.g. "warsat-vllm", "warsat-llama.cpp", "warsat-ollama"). All of them are
    # plain Docker containers under the hood, same as the standalone
    # "docker-llamacpp" runtime used by the local-model quick-deploy path.
    if runtime == "docker-llamacpp" or str(runtime or "").startswith("warsat-"):
        return _docker_provider

    raise ValueError(f"Unsupported deployment runtime: {runtime}")
