"""Allowlisted, read-only adapters for the assistant broker boundary.

The broker owns the final adapter lookup, while the assistant runtime owns
plan/approval validation and durable handoff state.  Adapters in this module
must be observational only until an operation receives its own explicit
security and approval contract.
"""

from __future__ import annotations

from typing import Any

from backend import warsat
from backend.core.response import AppError


DISPATCH_CONTRACT_VERSION = "0.1"
READ_ONLY_OPERATIONS = {"docker_status"}


def supported_operations() -> list[str]:
    return sorted(READ_ONLY_OPERATIONS)


def dispatch(operation: str) -> dict[str, Any]:
    """Run one allowlisted read-only adapter and return a bounded result."""

    clean_operation = str(operation or "").strip().lower()
    if clean_operation not in READ_ONLY_OPERATIONS:
        raise AppError("assistant_broker_adapter_unavailable", "No executable adapter is registered for that operation.", 409)
    if clean_operation == "docker_status":
        result = warsat.containers()
        return {
            "contract_version": DISPATCH_CONTRACT_VERSION,
            "operation": clean_operation,
            "adapter": "warsat.containers",
            "result": result,
            "side_effects": False,
            "host_mutation": False,
            "execution_started": False,
        }
    raise AppError("assistant_broker_adapter_unavailable", "No executable adapter is registered for that operation.", 409)
