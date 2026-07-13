import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from threading import Lock

from backend.core import audit as audit
from backend.core import runtime_store as store
from backend.core.datadir import data_dir

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = data_dir()
AUTH_FILE = DATA_DIR / "auth.json"
COOKIE_NAME = "rasputin_session"
# request.client.host is only ever a real loopback address for a native
# (non-Docker) run hit directly on 127.0.0.1 -- behind the standard
# docker-compose deployment it's the bridge gateway IP, so this bypass is a
# native-dev convenience only and simply never fires in production.
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

_lock = Lock()
_sessions = {}
_failed_logins = {}
_boot_password = None

ALLOWED_ROLES = {"admin", "member", "viewer"}
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,47}$")


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


def _token_hash(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _normalize_auth_data(data):
    data = dict(data or {})
    users = []
    changed = data.get("version") != 2
    for raw in data.get("users", []):
        user = dict(raw or {})
        username = str(user.get("username") or "").strip()
        if not username:
            continue
        role = str(user.get("role") or "member").lower()
        if role not in ALLOWED_ROLES:
            role = "member"
            changed = True
        if "id" not in user:
            user["id"] = f"usr_{hashlib.sha256(username.casefold().encode()).hexdigest()[:16]}"
            changed = True
        if "enabled" not in user:
            user["enabled"] = True
            changed = True
        user["username"] = username
        user["role"] = role
        users.append(user)
    data["version"] = 2
    data["users"] = users
    return data, changed


def _claim_legacy_user_data(username):
    store.claim_legacy_ownership(username)
    from backend.core import workspace
    workspace.claim_legacy_membership(username)
    for source, target in (
        ("userPreferences", f"userPreferences:{username}"),
        ("chat_folder_registry", f"chat_folder_registry:{username}"),
    ):
        if store.get_kv(target) is None:
            legacy = store.get_kv(source)
            if legacy is not None:
                store.set_kv(target, legacy)


def bootstrap():
    global _boot_password
    data = store.get_kv("auth")
    if data:
        data, changed = _normalize_auth_data(data)
        if changed:
            store.set_kv("auth", data)
        if data.get("users"):
            _claim_legacy_user_data(data["users"][0].get("username", "admin"))
        return load_public()
        
    DATA_DIR.mkdir(exist_ok=True)
    if AUTH_FILE.exists():
        with _lock:
            try:
                data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
                data, _ = _normalize_auth_data(data)
                store.set_kv("auth", data)
                if data.get("users"):
                    _claim_legacy_user_data(data["users"][0].get("username", "admin"))
                return load_public()
            except Exception:
                pass
                
    username = os.environ.get("RASPUTIN_ADMIN_USER", "admin")
    password = os.environ.get("RASPUTIN_ADMIN_PASSWORD") or secrets.token_urlsafe(18)
    hashed = _hash_password(password)
    data = {
        "version": 2,
        "created_at": time.time(),
        "users": [
            {
                "username": username,
                "id": f"usr_{hashlib.sha256(username.casefold().encode()).hexdigest()[:16]}",
                "role": "admin",
                "enabled": True,
                "salt": hashed["salt"],
                "password_hash": hashed["hash"],
            }
        ],
    }
    with _lock:
        store.set_kv("auth", data)
        _claim_legacy_user_data(username)
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
        return store.get_kv("auth")


def load_public():
    data = store.get_kv("auth")
    if not data:
        return {
            "configured": False,
            "username": "admin",
            "localhost_bypass": localhost_bypass_enabled(),
            "test_bypass": test_bypass_enabled(),
        }
    user = data.get("users", [{}])[0]
    return {
        "configured": True,
        "username": user.get("username", "admin"),
        "role": user.get("role", "admin"),
        "user_count": len(data.get("users", [])),
        "localhost_bypass": localhost_bypass_enabled(),
        "test_bypass": test_bypass_enabled(),
    }


def list_users():
    data = load()
    return [
        {
            "id": user.get("id"),
            "username": user.get("username"),
            "role": user.get("role", "member"),
            "enabled": bool(user.get("enabled", True)),
            "created_at": user.get("created_at"),
            "password_changed_at": user.get("password_changed_at"),
        }
        for user in data.get("users", [])
    ]


def create_user(username, password, role="member"):
    username = str(username or "").strip()
    role = str(role or "member").strip().lower()
    if not _USERNAME_RE.fullmatch(username):
        raise ValueError("username must be 2-48 characters using letters, numbers, dot, dash, or underscore")
    if len(str(password or "")) < 10:
        raise ValueError("password must be at least 10 characters")
    if role not in ALLOWED_ROLES:
        raise ValueError("role must be admin, member, or viewer")
    data = load()
    if any(str(user.get("username", "")).casefold() == username.casefold() for user in data.get("users", [])):
        raise ValueError("username already exists")
    hashed = _hash_password(password)
    user = {
        "id": store.new_id("usr"),
        "username": username,
        "role": role,
        "enabled": True,
        "salt": hashed["salt"],
        "password_hash": hashed["hash"],
        "created_at": time.time(),
    }
    data.setdefault("users", []).append(user)
    with _lock:
        store.set_kv("auth", data)
    audit.log("auth_user_created", {"username": username, "role": role})
    return next(item for item in list_users() if item["username"] == username)


def update_user(username, role=None, enabled=None):
    data = load()
    user = next((item for item in data.get("users", []) if item.get("username") == username), None)
    if not user:
        raise ValueError("unknown user")
    if role is not None:
        role = str(role).strip().lower()
        if role not in ALLOWED_ROLES:
            raise ValueError("role must be admin, member, or viewer")
        if user.get("role") == "admin" and role != "admin" and sum(1 for item in data["users"] if item.get("role") == "admin" and item.get("enabled", True)) <= 1:
            raise ValueError("cannot demote the last enabled administrator")
        user["role"] = role
    if enabled is not None:
        enabled = bool(enabled)
        if user.get("role") == "admin" and not enabled and sum(1 for item in data["users"] if item.get("role") == "admin" and item.get("enabled", True)) <= 1:
            raise ValueError("cannot disable the last enabled administrator")
        user["enabled"] = enabled
    with _lock:
        store.set_kv("auth", data)
    revoke_user_sessions(username)
    audit.log("auth_user_updated", {"username": username, "role": user.get("role"), "enabled": user.get("enabled", True)})
    return next(item for item in list_users() if item["username"] == username)


def delete_user(username):
    data = load()
    user = next((item for item in data.get("users", []) if item.get("username") == username), None)
    if not user:
        raise ValueError("unknown user")
    if user.get("role") == "admin" and sum(1 for item in data["users"] if item.get("role") == "admin" and item.get("enabled", True)) <= 1:
        raise ValueError("cannot delete the last enabled administrator")
    data["users"] = [item for item in data["users"] if item.get("username") != username]
    with store._lock, store.connect() as conn:
        owned = conn.execute("SELECT COUNT(*) AS count FROM sessions WHERE owner_id=?", (username,)).fetchone()
    if owned and int(owned["count"]):
        raise ValueError("disable users with existing data instead of deleting them")
    with _lock:
        store.set_kv("auth", data)
    revoke_user_sessions(username)
    audit.log("auth_user_deleted", {"username": username})
    return {"deleted": True, "username": username}


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
    with store._lock, store.connect() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE expires_at<=?", (now,))
        conn.commit()


def revoke_user_sessions(username):
    for token, session in list(_sessions.items()):
        if session.get("username") == username:
            _sessions.pop(token, None)
    with store._lock, store.connect() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE username=?", (username,))
        conn.commit()


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
    explicit = os.environ.get("RASPUTIN_COOKIE_SECURE")
    if explicit is not None:
        return explicit.lower() in {"1", "true", "yes"}
    return os.environ.get("RASPUTIN_HTTPS", "0").lower() in {"1", "true", "yes", "on"}


def login(username, password, client="local"):
    _check_login_rate(username, client)
    data = load()
    user = next((u for u in data.get("users", []) if u.get("username") == username), None)
    if not user or not user.get("enabled", True) or not _verify(password, user.get("salt", ""), user.get("password_hash", "")):
        _record_login_failure(username, client)
        audit.log("auth_login_failed", {"username": username}, actor=username or "unknown")
        raise PermissionError("invalid username or password")
    _clear_login_failures(username, client)
    token = secrets.token_urlsafe(32)
    created_at = time.time()
    expires_at = created_at + session_ttl_seconds()
    with _lock:
        _prune_sessions()
        _sessions[token] = {
            "username": user.get("username"),
            "role": user.get("role", "admin"),
            "created_at": created_at,
        }
        with store._lock, store.connect() as conn:
            conn.execute(
                "INSERT INTO auth_sessions(id,token_hash,username,role,created_at,last_seen,expires_at) VALUES(?,?,?,?,?,?,?)",
                (store.new_id("auths"), _token_hash(token), user.get("username"), user.get("role", "admin"), created_at, created_at, expires_at),
            )
            conn.commit()
    audit.log("auth_login", {"username": user.get("username")}, actor=user.get("username"))
    return token, {"username": user.get("username"), "role": user.get("role", "admin")}


def logout(token):
    if token:
        session = _sessions.pop(token, None)
        if session:
            audit.log("auth_logout", {"username": session.get("username")}, actor=session.get("username", "local-user"))
        with store._lock, store.connect() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash=?", (_token_hash(token),))
            conn.commit()
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
            store.set_kv("auth", data)
        revoke_user_sessions(username)
        audit.log("auth_password_changed", {"username": username}, actor=username)
        return {"changed": True, "username": username}
    raise ValueError("user missing")


def reset_password(username=None, new_password=None):
    bootstrap()
    data = load()
    users = data.get("users", [])
    if username:
        user = next((u for u in users if u.get("username") == username), None)
        if not user:
            raise ValueError(f"unknown user: {username}")
    else:
        user = next((u for u in users if u.get("role") == "admin"), None)
        if not user:
            raise ValueError("no admin user found to reset")
        username = user.get("username")

    if new_password is None:
        new_password = secrets.token_urlsafe(18)
    elif len(str(new_password)) < 10:
        raise ValueError("new password must be at least 10 characters")

    hashed = _hash_password(new_password)
    user["salt"] = hashed["salt"]
    user["password_hash"] = hashed["hash"]
    user["password_changed_at"] = time.time()
    with _lock:
        store.set_kv("auth", data)
    revoke_user_sessions(username)
    audit.log("auth_password_reset", {"username": username}, actor=username)
    return {"username": username, "password": new_password}


def session_info(token):
    _prune_sessions()
    session = _sessions.get(token)
    if not session:
        with store._lock, store.connect() as conn:
            row = conn.execute(
                "SELECT username,role,created_at,expires_at FROM auth_sessions WHERE token_hash=? AND expires_at>?",
                (_token_hash(token), time.time()),
            ).fetchone()
            if row:
                session = dict(row)
                _sessions[token] = session
    if not session:
        return None
    now = time.time()
    session["last_seen"] = now
    with store._lock, store.connect() as conn:
        conn.execute("UPDATE auth_sessions SET last_seen=? WHERE token_hash=?", (now, _token_hash(token)))
        conn.commit()
    return {
        "authenticated": True,
        "username": session.get("username"),
        "role": session.get("role"),
        "created_at": session.get("created_at"),
    }


def public_session(token=None, client_host=""):
    # Both bypasses are explicit, env-gated opt-ins (see load_public()) --
    # neither is on unless someone deliberately set the env var.
    if test_bypass_enabled():
        return {"authenticated": True, "username": "admin", "role": "admin"}
    if localhost_bypass_enabled() and client_host in _LOOPBACK_HOSTS:
        public = load_public()
        if public.get("user_count", 1) == 1:
            return {"authenticated": True, "username": public.get("username", "admin"), "role": "admin"}
    if token:
        info = session_info(token)
        if info:
            return info
    return {"authenticated": False, "username": None, "role": None}


def require_user(token=None, client_host=""):
    session = public_session(token, client_host)
    if not session.get("authenticated"):
        raise PermissionError("login required")
    return session
