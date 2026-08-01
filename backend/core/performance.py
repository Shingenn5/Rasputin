"""Small in-process request timing window for local performance diagnosis."""

from collections import deque
from threading import Lock
import time


_LOCK = Lock()
_SAMPLES = deque(maxlen=240)


def record(path: str, method: str, status_code: int, duration_ms: float):
    # Query strings can carry user search terms; store only the route path.
    sample = {
        "path": str(path or "")[:180],
        "method": str(method or "GET"),
        "status": int(status_code or 0),
        "durationMs": round(max(0.0, float(duration_ms)), 1),
        "recordedAt": time.time(),
    }
    with _LOCK:
        _SAMPLES.append(sample)


def snapshot(limit: int = 80):
    with _LOCK:
        rows = list(_SAMPLES)[-max(1, min(int(limit or 80), 240)):]
    grouped = {}
    for row in rows:
        item = grouped.setdefault(row["path"], {"path": row["path"], "count": 0, "total": 0.0, "max": 0.0, "errors": 0})
        item["count"] += 1
        item["total"] += row["durationMs"]
        item["max"] = max(item["max"], row["durationMs"])
        item["errors"] += int(row["status"] >= 400)
    slowest = sorted(
        ({"path": item["path"], "count": item["count"], "avgMs": round(item["total"] / item["count"], 1), "maxMs": item["max"], "errors": item["errors"]} for item in grouped.values()),
        key=lambda item: (item["avgMs"], item["maxMs"]), reverse=True,
    )
    return {"sampleCount": len(rows), "slowest": slowest[:20], "recent": list(reversed(rows[-20:]))}
