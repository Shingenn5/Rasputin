"""Rasputin's personality, context, and orchestration contracts.

The assistant package is intentionally side-effect light.  It can describe a
model fleet, delegated work, and host-control requests without starting a
model, running a command, or opening an application.  Execution belongs to a
future local-control broker.
"""

