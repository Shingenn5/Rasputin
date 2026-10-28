"""Named, owner-bound credentials for the local inference gateway.

Secrets are returned only by create_key; the runtime store retains SHA-256
digests of cryptographically random tokens. These keys never grant UI sessions
or host-tool access.
"""

import hashlib
import secrets
import time
from threading import RLock

from backend.core import audit, auth
from backend.core import runtime_store as store
from backend.core.response import AppError

_STORE_KEY = "inference_api_keys_v1"
_lock = RLock()
_PUBLIC_FIELDS = ("id", "name", "prefix", "owner_id", "created_at", "last_used_at", "revoked_at", "scope")


def _public(record):
    return {field: record.get(field) for field in _PUBLIC_FIELDS}


def list_keys(owner_id, is_admin=False):
    with _lock:
        records = store.get_kv(_STORE_KEY, {})
    return [
        _public(record) for record in records.values()
        if is_admin or record["owner_id"] == owner_id
    ]


def has_active_keys():
    with _lock:
        return any(not item.get("revoked_at") for item in store.get_kv(_STORE_KEY, {}).values())


def create_key(owner_id, name):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise ValueError("Key name must be between 1 and 80 characters.")
    if not owner_id:
        raise PermissionError("An authenticated owner is required.")
    owner = next((user for user in auth.list_users() if user["username"] == owner_id), None)
    if not owner or not owner.get("enabled") or owner.get("role") not in {"member", "admin"}:
        raise PermissionError("An enabled member or administrator account is required.")
    key_id = store.new_id("key")
    secret = f"ras_sk_{key_id}.{secrets.token_urlsafe(32)}"
    record = {
        "id": key_id, "name": name.strip(), "prefix": f"ras_sk_{key_id}",
        "owner_id": owner_id, "created_at": time.time(), "last_used_at": None,
        "owner_user_id": owner.get("id"),
        "revoked_at": None, "scope": "local-inference",
        "token_hash": hashlib.sha256(secret.encode("utf-8")).hexdigest(),
    }
    with _lock:
        records = store.get_kv(_STORE_KEY, {})
        if sum(1 for item in records.values() if item["owner_id"] == owner_id and not item.get("revoked_at")) >= 32:
            raise ValueError("Revoke an existing key before creating more than 32 active keys.")
        records[key_id] = record
        store.set_kv(_STORE_KEY, records)
    audit.log("inference_api_key_created", {"key_id": key_id, "scope": record["scope"]}, actor=owner_id)
    return {"key": _public(record), "api_key": secret}


def revoke_key(key_id, owner_id, is_admin=False):
    with _lock:
        records = store.get_kv(_STORE_KEY, {})
        record = records.get(key_id)
        if not record or (record["owner_id"] != owner_id and not is_admin):
            raise AppError("key_not_found", "API key not found.", 404)
        if not record.get("revoked_at"):
            record["revoked_at"] = time.time()
            store.set_kv(_STORE_KEY, records)
    audit.log("inference_api_key_revoked", {"key_id": key_id}, actor=owner_id)
    return _public(record)


def authenticate(secret):
    if not isinstance(secret, str) or not secret.startswith("ras_sk_") or len(secret) > 160:
        return None
    key_id = secret[7:].split(".", 1)[0]
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    with _lock:
        records = store.get_kv(_STORE_KEY, {})
        record = records.get(key_id)
        if not record or record.get("revoked_at") or not secrets.compare_digest(digest, record["token_hash"]):
            return None
        owner = next((user for user in auth.list_users() if user["username"] == record["owner_id"]), None)
        if (not owner or owner.get("id") != record.get("owner_user_id")
                or not owner.get("enabled") or owner.get("role") not in {"member", "admin"}):
            return None
        record["last_used_at"] = time.time()
        store.set_kv(_STORE_KEY, records)
        return _public(record)
