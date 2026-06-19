import asyncio
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from threading import Lock

from backend.core import audit as audit
from backend.core import approvals as approvals

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIG_FILE = DATA_DIR / "telegram.json"

_lock = Lock()
_poller = None


def defaults():
    return {
        "enabled": False,
        "bot_token": "",
        "allowed_chat_id": "",
        "redaction_mode": "summary",
        "last_update_id": 0,
        "last_error": "",
        "last_poll_at": None,
    }


def _load_raw():
    DATA_DIR.mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(defaults(), indent=2), encoding="utf-8")
    with _lock:
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = defaults()
    merged = defaults()
    merged.update(data)
    return merged


def _save(data):
    merged = defaults()
    merged.update(data)
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        CONFIG_FILE.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return public_config(merged)


def public_config(data=None):
    cfg = data or _load_raw()
    return {
        "enabled": bool(cfg.get("enabled")),
        "configured": bool(cfg.get("bot_token") and cfg.get("allowed_chat_id")),
        "allowed_chat_id": str(cfg.get("allowed_chat_id") or ""),
        "redaction_mode": cfg.get("redaction_mode", "summary"),
        "last_error": cfg.get("last_error", ""),
        "last_poll_at": cfg.get("last_poll_at"),
    }


def configure(bot_token=None, allowed_chat_id=None, enabled=True, redaction_mode="summary"):
    cfg = _load_raw()
    if bot_token is not None:
        cfg["bot_token"] = str(bot_token).strip()
    if allowed_chat_id is not None:
        cfg["allowed_chat_id"] = str(allowed_chat_id).strip()
    cfg["enabled"] = bool(enabled)
    cfg["redaction_mode"] = redaction_mode or "summary"
    cfg["last_error"] = ""
    audit.log("telegram_configured", {
        "enabled": cfg["enabled"],
        "allowed_chat_id": cfg["allowed_chat_id"],
        "redaction_mode": cfg["redaction_mode"],
    })
    return _save(cfg)


def disable():
    cfg = _load_raw()
    cfg["enabled"] = False
    audit.log("telegram_disabled", {})
    return _save(cfg)


def _url(token, method):
    return f"https://api.telegram.org/bot{token}/{method}"


def _post(method, payload):
    cfg = _load_raw()
    token = cfg.get("bot_token")
    if not token:
        raise ValueError("telegram bot token missing")
    req = urllib.request.Request(
        _url(token, method),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    raw = urllib.request.urlopen(req, timeout=12).read().decode("utf-8")
    return json.loads(raw)


def _get(method, payload):
    cfg = _load_raw()
    token = cfg.get("bot_token")
    if not token:
        raise ValueError("telegram bot token missing")
    req = urllib.request.Request(
        _url(token, method),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    raw = urllib.request.urlopen(req, timeout=35).read().decode("utf-8")
    return json.loads(raw)


def send_message(text, chat_id=None):
    cfg = _load_raw()
    if not cfg.get("enabled"):
        return {"skipped": True, "reason": "disabled"}
    target = str(chat_id or cfg.get("allowed_chat_id") or "").strip()
    if not target:
        return {"skipped": True, "reason": "chat missing"}
    return _post("sendMessage", {
        "chat_id": target,
        "text": text[:3800],
        "disable_web_page_preview": True,
    })


def approval_message(approval):
    detail = approval.get("redacted_detail") or {}
    paths = []
    for key in ("path", "source", "target"):
        if detail.get(key):
            paths.append(f"{key}: {detail[key]}")
    path_text = "\n".join(paths) if paths else "paths: none"
    return (
        "Rasputin approval needed\n"
        f"Code: {approval.get('code')}\n"
        f"Action: {approval.get('action_type')}\n"
        f"Risk: {approval.get('risk_level')}\n"
        f"Workspace: {approval.get('workspace')}\n"
        f"{path_text}\n\n"
        f"Approve: /approve {approval.get('code')}\n"
        f"Deny: /deny {approval.get('code')}"
    )


def notify_approval(approval):
    cfg = _load_raw()
    if not cfg.get("enabled") or not cfg.get("bot_token") or not cfg.get("allowed_chat_id"):
        return {"skipped": True}
    out = send_message(approval_message(approval))
    audit.log("telegram_approval_sent", {"approval_id": approval.get("id"), "code": approval.get("code")})
    return out


def test_message():
    out = send_message("Rasputin Telegram approval test. No private content included.")
    audit.log("telegram_test_sent", {})
    return {"sent": not out.get("skipped"), "result": public_config()}


def _authorized(chat_id):
    cfg = _load_raw()
    return str(chat_id) == str(cfg.get("allowed_chat_id"))


def handle_command(text, chat_id):
    if not _authorized(chat_id):
        audit.log("telegram_rejected_chat", {"chat_id": str(chat_id)})
        return "This chat is not authorized for Rasputin."
    parts = str(text or "").strip().split()
    if not parts:
        return ""
    cmd = parts[0].lower()
    if cmd == "/status":
        pending = approvals.list_approvals("pending", 20)["approvals"]
        return f"Rasputin is online. Pending approvals: {len(pending)}."
    if cmd in {"/approve", "/deny"} and len(parts) >= 2:
        approval = approvals.get_by_code(parts[1])
        if not approval:
            return "Approval code not found."
        if cmd == "/approve":
            updated = approvals.approve(approval["id"], source="telegram")
            return f"Approved {updated['code']}."
        updated = approvals.deny(approval["id"], source="telegram")
        return f"Denied {updated['code']}."
    return "Use /approve CODE, /deny CODE, or /status."


async def _poll_once():
    cfg = _load_raw()
    if not cfg.get("enabled") or not cfg.get("bot_token"):
        await asyncio.sleep(5)
        return
    offset = int(cfg.get("last_update_id") or 0) + 1
    try:
        payload = await asyncio.to_thread(_get, "getUpdates", {"timeout": 25, "offset": offset, "allowed_updates": ["message"]})
        updates = payload.get("result", [])
        for update in updates:
            cfg["last_update_id"] = max(int(cfg.get("last_update_id") or 0), int(update.get("update_id") or 0))
            msg = update.get("message") or {}
            text = msg.get("text") or ""
            chat_id = msg.get("chat", {}).get("id")
            if text:
                reply = handle_command(text, chat_id)
                if reply:
                    await asyncio.to_thread(send_message, reply, chat_id)
        cfg["last_error"] = ""
        cfg["last_poll_at"] = time.time()
        _save(cfg)
    except Exception as exc:
        cfg["last_error"] = str(exc)
        cfg["last_poll_at"] = time.time()
        _save(cfg)
        audit.log("telegram_poll_failed", {"error": str(exc)})
        await asyncio.sleep(10)


async def poll_loop():
    while True:
        await _poll_once()


def start_polling():
    global _poller
    if _poller and not _poller.done():
        return _poller
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    _poller = loop.create_task(poll_loop())
    return _poller
