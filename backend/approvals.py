import time

from . import audit


def mutation_preview(kind, detail, actor="local-user"):
    event = {
        "preview": True,
        "kind": kind,
        "detail": detail,
        "created_at": time.time(),
        "message": "Approval required before this mutation is applied.",
    }
    audit.log("approval_preview", event, actor=actor)
    return event
