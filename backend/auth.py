import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from threading import Lock

from . import audit

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUTH_FILE = DATA_DIR / "auth.json"
COOKIE_NAME = "rasputin_session"

_lock = Lock()
_sessions = {}
_failed_logins = {}
_boot_password = None


def _hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 180_000)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def _verify(password, salt, expected):
    salt_bytes = base64.b64decode(salt.encode("ascii"))
    expected_bytes = base64.b64decode(expected.encode("ascii"))
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 180_000)
    return hmac.compare_digest(actual, expected_bytes)


def bootstrap():
    global _boot_password
    DATA_DIR.mkdir(exist_ok=True)
    if AUTH_FILE.exists():
        return load_public()
    username = os.environ.get("RASPUTIN_ADMIN_USER", "admin")
    password = os.environ.get("RASPUTIN_ADMIN_PASSWORD") or secrets.token_urlsafe(18)
    hashed = _hash_password(password)
    data = {
        "version": 1,
        "created_at": time.time(),
        "users": [
            {
                "username": username,
                "role": "admin",
                "salt": hashed["salt"],
                "password_hash": hashed["hash"],
            }
        ],
    }
    with _lock:
        AUTH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if not os.environ.get("RASPUTIN_ADMIN_PASSWORD"):
        _boot_password = password
        print("")
        print("Rasputin first-run admin credentials")
        print(f"  username: {username}")
        print(f"  password: {password}")
        print("Change this after first login if you expose the app beyond localhost.")
        print("")
    return load_public()


def load():
    bootstrap()
    with _lock:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))


def load_public():
    if not AUTH_FILE.exists():
        return {
            "configured": False,
            "username": "admin",
            "localhost_bypass": localhost_bypass_enabled(),
            "test_bypass": test_bypass_enabled(),
        }
    data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    user = data.get("users", [{}])[0]
    return {
        "configured": True,
        "username": user.get("username", "admin"),
        "role": user.get("role", "admin"),
        "localhost_bypass": localhost_bypass_enabled(),
        "test_bypass": test_bypass_enabled(),
    }


def localhost_bypass_enabled():
    return os.environ.get("RASPUTIN_LOCALHOST_BYPASS", "0").lower() in {"1", "true", "yes"}


def test_bypass_enabled():
    is_test_env = os.environ.get("RASPUTIN_ENV", "").lower() == "test"
    wants_bypass = os.environ.get("RASPUTIN_TEST_AUTH_BYPASS", "0").lower() in {"1", "true", "yes"}
    return is_test_env and wants_bypass


def _env_int(name, default, minimum):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, value)


def session_ttl_seconds():
    return _env_int("RASPUTIN_SESSION_TTL_SECONDS", 60 * 60 * 12, 300)


def _login_limit():
    return _env_int("RASPUTIN_LOGIN_MAX_FAILURES", 8, 3)


def _login_window():
    return _env_int("RASPUTIN_LOGIN_WINDOW_SECONDS", 300, 60)


def _login_lockout():
    return _env_int("RASPUTIN_LOGIN_LOCKOUT_SECONDS", 300, 60)


def _login_key(username, client):
    return f"{client or 'local'}:{username or 'admin'}"


def _prune_sessions():
    ttl = session_ttl_seconds()
    now = time.time()
    for token, session in list(_sessions.items()):
        if now - float(session.get("created_at", now)) > ttl:
            _sessions.pop(token, None)


def _check_login_rate(username, client):
    key = _login_key(username, client)
    state = _failed_logins.get(key)
    if not state:
        return
    now = time.time()
    if state.get("locked_until", 0) > now:
        raise PermissionError("too many failed login attempts; wait before trying again")
    if now - state.get("first_seen", now) > _login_window():
        _failed_logins.pop(key, None)


def _record_login_failure(username, client):
    key = _login_key(username, client)
    now = time.time()
    state = _failed_logins.get(key)
    if not state or now - state.get("first_seen", now) > _login_window():
        state = {"count": 0, "first_seen": now, "locked_until": 0}
    state["count"] += 1
    if state["count"] >= _login_limit():
        state["locked_until"] = now + _login_lockout()
    _failed_logins[key] = state


def _clear_login_failures(username, client):
    _failed_logins.pop(_login_key(username, client), None)


def cookie_secure():
    return os.environ.get("RASPUTIN_COOKIE_SECURE", "0").lower() in {"1", "true", "yes"}


def login(username, password, client="local"):
    _prune_sessions()
    _check_login_rate(username, client)
    data = load()
    for user in data.get("users", []):
        if user.get("username") == username and _verify(password, user.get("salt", ""), user.get("password_hash", "")):
            token = secrets.token_urlsafe(32)
            _sessions[token] = {
                "username": username,
                "role": user.get("role", "admin"),
                "created_at": time.time(),
                "last_seen": time.time(),
            }
            _clear_login_failures(username, client)
            audit.log("auth_login", {"username": username, "client": client}, actor=username)
            return token, session_info(token)
    _record_login_failure(username, client)
    audit.log("auth_login_failed", {"username": username, "client": client})
    raise PermissionError("invalid username or password")


def logout(token):
    if token:
        session = _sessions.pop(token, None)
        if session:
            audit.log("auth_logout", {"username": session.get("username")}, actor=session.get("username", "local-user"))
    return {"logged_out": True}


def change_password(username, current_password, new_password):
    if len(str(new_password or "")) < 10:
        raise ValueError("new password must be at least 10 characters")
    data = load()
    for user in data.get("users", []):
        if user.get("username") != username:
            continue
        if not _verify(current_password, user.get("salt", ""), user.get("password_hash", "")):
            audit.log("auth_password_change_failed", {"username": username}, actor=username)
            raise PermissionError("current password is incorrect")
        hashed = _hash_password(new_password)
        user["salt"] = hashed["salt"]
        user["password_hash"] = hashed["hash"]
        user["password_changed_at"] = time.time()
        with _lock:
            AUTH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        audit.log("auth_password_changed", {"username": username}, actor=username)
        return {"changed": True, "username": username}
    raise ValueError("user missing")


def session_info(token):
    _prune_sessions()
    session = _sessions.get(token)
    if not session:
        return None
    session["last_seen"] = time.time()
    return {
        "authenticated": True,
        "username": session.get("username"),
        "role": session.get("role"),
        "created_at": session.get("created_at"),
    }


def public_session(token=None, client_host=""):
    if test_bypass_enabled():
        return {"authenticated": True, "username": "test", "role": "admin", "test_bypass": True}
    if localhost_bypass_enabled() and client_host in {"127.0.0.1", "::1", "localhost"}:
        return {"authenticated": True, "username": "localhost", "role": "admin", "bypass": True}
    info = session_info(token)
    if info:
        return info
    public = load_public()
    return {"authenticated": False, "auth": public}


def require_user(token=None, client_host=""):
    session = public_session(token, client_host)
    if not session.get("authenticated"):
        raise PermissionError("login required")
    return session
