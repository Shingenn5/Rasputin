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
    if runtime == "docker-llamacpp":
        return _docker_provider
        
    raise ValueError(f"Unsupported deployment runtime: {runtime}")
