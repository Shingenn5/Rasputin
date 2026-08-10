"""Certify a registered local coder model and report whether Code is safe to run.

This command never deploys or starts a model. It only invokes the existing
bounded compatibility probes for a named registry entry, which keeps model
selection and model execution separate and auditable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def certify(key: str) -> tuple[dict, int]:
    from backend.models import registry

    model = registry.get_model(key)
    if not model:
        return {
            "key": key,
            "status": "blocked",
            "reason": "model_not_registered",
            "nextAction": "Register and test a local coder-capable model first.",
        }, 2
    if model.get("runtime_status") not in {"reachable", "healthy", "ready", "running"}:
        return {
            "key": key,
            "status": "blocked",
            "reason": "model_not_reachable",
            "runtimeStatus": model.get("runtime_status") or "unknown",
            "nextAction": "Start the local model and run its health test before certification.",
        }, 2
    result = registry.certify_model(key)
    profile = result.get("compatibility") or {}
    code_ready = (
        profile.get("status") == "certified"
        and "code" in (profile.get("supportedModes") or [])
        and profile.get("toolSupport") == "agentic"
    )
    result.update({
        "status": "ready" if code_ready else "limited",
        "readyForLiveCoding": code_ready,
        "nextAction": None if code_ready else "Use Chat or choose a model with certified context retention and tool calling.",
    })
    return result, 0 if code_ready else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", help="registered model key")
    parser.add_argument("--json", action="store_true", help="emit machine-readable evidence")
    parser.add_argument("--data-dir", help="isolated RASPUTIN_DATA_DIR for a controlled run")
    args = parser.parse_args(argv)
    if args.data_dir:
        os.environ["RASPUTIN_DATA_DIR"] = str(Path(args.data_dir).resolve())
    result, code = certify(args.key)
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
