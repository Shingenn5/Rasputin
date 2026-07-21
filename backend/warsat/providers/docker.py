import subprocess
from pathlib import Path

from .base import DeploymentProvider


class DockerProvider(DeploymentProvider):
    """
    Manages local model deployments using the Docker CLI directly.
    Currently specifically tailored for `llama.cpp` containers.
    """

    def _docker_args(self, model: dict) -> list[str]:
        if model.get("runtime") != "docker-llamacpp":
            raise ValueError("model is not a managed llama.cpp entry")

        host_path = model.get("host_model_path")
        if not host_path:
            raise ValueError("host_model_path is missing")

        file_path = Path(host_path).expanduser().resolve()
        if not file_path.exists() or not file_path.is_file():
            raise ValueError(f"Model file does not exist at: {file_path}")

        parent = str(file_path.parent)
        cmd = [
            "docker", "run", "-d",
            "--name", model.get("container") or f"ai-{model['key']}",
            "-p", f"127.0.0.1:{int(model.get('port', 8081))}:8080",
            "--security-opt", "no-new-privileges",
            "-v", f"{parent}:/models:ro",
            model.get("image") or "ghcr.io/ggml-org/llama.cpp:server",
            "-m", f"/models/{file_path.name}",
            "--host", "0.0.0.0",
            "--port", "8080",
            "-c", str(int(model.get("context", 4096))),
        ]

        gpu_layers = int(model.get("n_gpu_layers", 0))
        if gpu_layers:
            cmd.extend(["--n-gpu-layers", str(gpu_layers)])

        return cmd

    def start(self, model: dict) -> dict:
        if model.get("runtime") != "docker-llamacpp":
            # WarSat-deployed models (runtime "warsat-*") are started through
            # the WarSat deploy flow, which builds their full docker run
            # command from the protocol definition. _docker_args() below only
            # knows how to build a llama.cpp command, so route anything else
            # to a structured error instead of letting its ValueError leak.
            return {
                "ok": False,
                "message": "This model is managed by WarSat. Stop it and redeploy through WarSat instead of starting it directly.",
            }

        status = self.status(model)
        if status in {"running", "starting"}:
            return {"ok": True, "status": status, "message": "already running"}

        self.rm(model)
        cmd = self._docker_args(model)
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return {"ok": False, "cmd": cmd, "error": proc.stderr.strip() or proc.stdout.strip()}
            
        return {"ok": True, "container_id": proc.stdout.strip(), "cmd": cmd}

    def stop(self, model: dict) -> dict:
        name = model.get("container")
        if not name:
            return {"ok": False, "message": "model container name missing"}
            
        subprocess.run(["docker", "stop", name], capture_output=True, text=True, timeout=20)
        subprocess.run(["docker", "rm", name], capture_output=True, text=True, timeout=20)
        
        return {"ok": True, "status": self.status(model)}

    def rm(self, model: dict) -> None:
        name = model.get("container")
        if name:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=20)

    def status(self, model: dict) -> str:
        name = model.get("container")
        if not name:
            return "external"
            
        try:
            proc = subprocess.run(
                [
                    "docker", "inspect", "--format",
                    "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
                    name,
                ],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            return "unknown"
            
        text = proc.stdout.strip().lower()
        if not text:
            return "stopped"
        if text in {"healthy", "running"}:
            return "running"
        if text == "starting":
            return "starting"
        if text == "unhealthy":
            return "unhealthy"
        return text

    def logs(self, model: dict, limit: int = 120) -> dict:
        name = model.get("container")
        if not name:
            return {"ok": False, "message": "model container name missing", "logs": ""}
            
        safe_limit = max(1, min(int(limit), 500))
        try:
            proc = subprocess.run(
                ["docker", "logs", "--tail", str(safe_limit), name], 
                capture_output=True, text=True, timeout=15
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc), "logs": ""}
            
        return {"ok": proc.returncode == 0, "logs": proc.stdout + proc.stderr}
