from .base import DeploymentProvider
from .docker import DockerProvider

_docker_provider = DockerProvider()

def get_provider(model: dict) -> DeploymentProvider:
    """
    Returns the appropriate deployment provider for the given model runtime.
    Raises ValueError if the runtime is unsupported or unmanaged.
    """
    if not model.get("managed"):
        raise ValueError("Model is external/unmanaged and has no deployment provider.")

    runtime = model.get("runtime")
    # WarSat registers deployed models with runtime f"warsat-{protocol['runtime']}"
    # (e.g. "warsat-vllm", "warsat-llama.cpp", "warsat-ollama"). All of them are
    # plain Docker containers under the hood, same as the standalone
    # "docker-llamacpp" runtime used by the local-model quick-deploy path.
    if runtime == "docker-llamacpp" or str(runtime or "").startswith("warsat-"):
        return _docker_provider

    raise ValueError(f"Unsupported deployment runtime: {runtime}")
