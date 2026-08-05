"""Rasputin's personality, context, and orchestration contracts.

The assistant package is intentionally side-effect light.  It can describe a
model fleet, delegated work, and host-control requests without starting a
model or opening an application.  The broker currently exposes only an
approval-backed, read-only Docker status adapter; mutating adapters remain
explicit future work.
"""
