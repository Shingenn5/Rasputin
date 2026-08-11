"""Certify the selected local main/coder model fleet without deploying it.

The command performs only bounded local health/capability probes and records a
latency-only runtime certificate from the observed health request.  It never
starts a container, changes placement, or contacts a remote model provider.
Missing or unreachable role assignments are reported as explicit blockers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOCAL_PROVIDER_HINTS = {
    "vllm",
    "llama.cpp",
    "ollama",
    "custom-local",
    "openai-compatible",
    "mock",
    "hash-vector",
}
READY_STATUSES = {"reachable", "healthy", "ready", "running"}


def _local_endpoint(model: dict) -> bool:
    provider = str(model.get("provider") or "").strip().lower()
    base_url = str(model.get("base_url") or model.get("baseUrl") or "").strip()
    host = (urlparse(base_url).hostname or "").lower() if base_url else ""
    return (
        provider in LOCAL_PROVIDER_HINTS
        and (not base_url or host in {"127.0.0.1", "localhost", "::1", "host.docker.internal"})
    )


def _protocol(model: dict) -> str:
    runtime = str(model.get("runtime") or model.get("provider") or "").lower()
    if "llama" in runtime:
        return "llamaCppGgufServer"
    if "ollama" in runtime:
        return "ollamaOpenaiServer"
    if "vllm" in runtime:
        return "vllmCudaOpenai"
    return "openaiCompatibleLocal"


def _model_view(model: dict | None) -> dict:
    model = model or {}
    return {
        "key": model.get("key"),
        "name": model.get("name"),
        "model": model.get("model"),
        "provider": model.get("provider"),
        "runtime": model.get("runtime") or model.get("provider"),
        "role": model.get("role"),
    }


def _blocked(role: str, key: str | None, reason: str, next_action: str, model: dict | None = None) -> dict:
    return {
        "role": role,
        "key": key,
        "model": _model_view(model),
        "status": "blocked",
        "readyForCoding": False,
        "reason": reason,
        "nextAction": next_action,
    }


def _select(models: list[dict], role: str, key: str | None) -> tuple[dict | None, dict | None]:
    if key:
        model = next((item for item in models if item.get("key") == key), None)
        if not model:
            return None, _blocked(
                role,
                key,
                "model_not_registered",
                f"Register the selected {role} model before certification.",
            )
        if str(model.get("role") or "") != role:
            return None, _blocked(
                role,
                key,
                "model_role_mismatch",
                f"Assign model '{key}' the {role} role or select a model already assigned to that role.",
                model,
            )
    else:
        candidates = sorted(
            (
                item
                for item in models
                if item.get("role") == role
                and item.get("enabled", True)
                and _local_endpoint(item)
            ),
            key=lambda item: str(item.get("key") or ""),
        )
        model = candidates[0] if candidates else None
        if not model:
            return None, _blocked(
                role,
                None,
                "local_model_not_registered",
                f"Register an enabled local model with the {role} role, then run certification again.",
            )
    if not _local_endpoint(model):
        return None, _blocked(
            role,
            model.get("key"),
            "non_local_model",
            "Use a local vLLM, llama.cpp, Ollama, or OpenAI-compatible loopback endpoint.",
            model,
        )
    return model, None


def _certificate(model: dict, health: dict, owner: str):
    from backend.warsat import benchmarks

    latency = health.get("latency_ms")
    if latency is None:
        return None
    sample = {
        "status": "ok" if health.get("ok") else "error",
        "totalLatencyMs": max(0, float(latency)),
        "promptTokens": 0,
        "outputTokens": 0,
    }
    certificate = benchmarks.build_certificate(
        {
            "modelId": model.get("model") or model.get("key"),
            "modelRevision": model.get("checksum") or model.get("sha"),
            "runtime": model.get("runtime") or model.get("provider") or "unknown",
            "protocolId": _protocol(model),
            "deviceIds": model.get("device_ids") or model.get("deviceIds") or [],
            "contextWindow": model.get("context_window") or model.get("contextWindow"),
            "quantization": model.get("quantization"),
            "placementMode": "single-gpu",
        },
        [sample],
        owner=owner,
    )
    return benchmarks.save_certificate(certificate)


def _certify_one(model: dict, role: str, owner: str) -> dict:
    from backend.models import registry

    key = str(model.get("key") or "")
    runtime_status = str(model.get("runtime_status") or "unknown")
    if runtime_status not in READY_STATUSES and model.get("provider") not in {"mock", "hash-vector"}:
        return _blocked(
            role,
            key,
            "model_not_reachable",
            "Start the local model and run its health test before certification.",
            model,
        ) | {"runtimeStatus": runtime_status}
    try:
        health = registry.test_model(key)
    except Exception as exc:  # noqa: BLE001 - report the bounded probe failure
        return _blocked(
            role,
            key,
            "health_probe_failed",
            "Inspect the local endpoint, model id, and runtime logs, then retry.",
            model,
        ) | {"error": str(exc)[:280]}
    if not health.get("ok") or health.get("status") not in READY_STATUSES:
        return _blocked(
            role,
            key,
            "model_not_reachable",
            "Start the local model and resolve its health error before certification.",
            model,
        ) | {
            "runtimeStatus": health.get("status") or "unknown",
            "error": str(health.get("error") or health.get("message") or "")[:280],
        }
    refreshed = registry.get_model(key) or model
    compatibility = health.get("compatibility") or (refreshed.get("compatibility") if refreshed else None) or {}
    if not compatibility:
        try:
            compatibility = (registry.certify_model(key) or {}).get("compatibility") or {}
        except Exception as exc:  # noqa: BLE001 - preserve explicit evidence
            compatibility = {"status": "unmeasured", "error": str(exc)[:280]}
    certificate = _certificate(refreshed, health, owner)
    code_ready = (
        compatibility.get("status") == "certified"
        and "code" in (compatibility.get("supportedModes") or [])
        and compatibility.get("toolSupport") == "agentic"
    )
    chat_ready = compatibility.get("status") in {"certified", "limited"} and "chat" in (compatibility.get("supportedModes") or [])
    status = "ready" if (code_ready if role == "coder" else chat_ready) else "limited"
    return {
        "role": role,
        "key": key,
        "model": _model_view(refreshed),
        "status": status,
        "readyForCoding": code_ready,
        "runtimeStatus": health.get("status") or "reachable",
        "health": {
            "latencyMs": health.get("latency_ms"),
            "modelId": refreshed.get("model"),
        },
        "compatibility": compatibility,
        "benchmark": {
            "certificateId": certificate.get("certificateId") if certificate else None,
            "fresh": bool(certificate),
            "scope": "latency-only health sample; no TPS or semantic quality claim",
        },
        "nextAction": None if status == "ready" else (
            "Use this model for Chat only, or provide a certified tool-capable coder model."
            if role == "coder"
            else "Use Chat with the recorded limitation and collect a richer runtime certificate."
        ),
    }


def certify_fleet(*, main_key: str | None = None, coder_key: str | None = None, owner: str = "admin") -> tuple[dict, int]:
    from backend.models import registry

    models = [dict(item) for item in registry.all_models()]
    selected = []
    results = []
    for role, key in (("main", main_key), ("coder", coder_key)):
        model, blocked = _select(models, role, key)
        if blocked:
            results.append(blocked)
            continue
        selected.append(model.get("key"))
        results.append(_certify_one(model, role, owner))
    statuses = [item.get("status") for item in results]
    overall = "ready" if statuses and all(status == "ready" for status in statuses) else "partial" if any(status in {"ready", "limited"} for status in statuses) else "blocked"
    code = 0 if overall == "ready" else 2
    return {
        "schemaVersion": "rasputin.model-fleet-certification.v1",
        "createdAt": time.time(),
        "owner": str(owner or "admin"),
        "overallStatus": overall,
        "selectedKeys": selected,
        "roles": results,
        "nextActions": [item["nextAction"] for item in results if item.get("nextAction")],
        "policy": {
            "localOnly": True,
            "deploymentsStarted": False,
            "remoteProvidersContacted": False,
            "approvalBypassed": False,
            "benchmarkLimitations": "Certificates contain one observed health latency sample; throughput, memory, and semantic quality remain unmeasured.",
        },
    }, code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-key", help="explicit registered main-model key")
    parser.add_argument("--coder-key", help="explicit registered coder-model key")
    parser.add_argument("--owner", default="admin", help="owner scope for the saved certificate")
    parser.add_argument("--data-dir", help="isolated RASPUTIN_DATA_DIR for a controlled run")
    args = parser.parse_args(argv)
    if args.data_dir:
        os.environ["RASPUTIN_DATA_DIR"] = str(Path(args.data_dir).resolve())
    report, code = certify_fleet(main_key=args.main_key, coder_key=args.coder_key, owner=args.owner)
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
