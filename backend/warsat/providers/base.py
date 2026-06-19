from abc import ABC, abstractmethod


class DeploymentProvider(ABC):
    """
    Abstract base interface for model deployment providers.
    Every new deployment target (Docker, K8s, Compose, etc) must implement these.
    """

    @abstractmethod
    def start(self, model: dict) -> dict:
        """
        Deploy and start the model.
        Returns a dict like {"ok": True, "container_id": "...", "cmd": [...]}
        """
        pass

    @abstractmethod
    def stop(self, model: dict) -> dict:
        """
        Stop the model deployment.
        Returns a dict like {"ok": True, "status": "stopped"}
        """
        pass

    @abstractmethod
    def rm(self, model: dict) -> None:
        """
        Remove/destroy the deployment footprint entirely.
        """
        pass

    @abstractmethod
    def status(self, model: dict) -> str:
        """
        Check the current status of the deployment.
        Returns one of: "running", "stopped", "external", "unknown", or native status.
        """
        pass

    @abstractmethod
    def logs(self, model: dict, limit: int = 120) -> dict:
        """
        Fetch logs from the deployment.
        Returns {"ok": True, "logs": "..."}
        """
        pass
