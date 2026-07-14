from urllib.parse import urlsplit

from backend.core import audit
from backend.core import runtime_store as store

PROVIDERS = {
    "gmail": {
        "name": "Gmail",
        "auth": "oauth2",
        "capabilities": ["read_mail", "draft_mail", "send_mail"],
        "required": ["clientId", "clientSecret"],
    },
    "outlook": {
        "name": "Outlook",
        "auth": "oauth2",
        "capabilities": ["read_mail", "draft_mail", "send_mail", "calendar"],
        "required": ["clientId", "clientSecret", "tenantId"],
    },
    "teams": {
        "name": "Microsoft Teams",
        "auth": "oauth2",
        "capabilities": ["read_channels", "draft_message", "send_message"],
        "required": ["clientId", "clientSecret", "tenantId"],
    },
    "webhook": {
        "name": "Generic webhook",
        "auth": "secret",
        "capabilities": ["send_event"],
        "required": ["url"],
    },
}

SECRET_FIELDS = {"clientSecret", "secret", "token", "accessToken", "refreshToken"}


def _public(row):
    item = dict(row)
    config = store._loads(item.pop("config", "{}"), {})
    credentials = store._loads(item.pop("credentials", "{}"), {})
    item["config"] = config
    item["hasCredentials"] = any(bool(value) for value in credentials.values())
    item["credentialFields"] = sorted(key for key, value in credentials.items() if value)
    item["capabilities"] = PROVIDERS.get(item["provider"], {}).get("capabilities", [])
    return item


def provider_catalog():
    return [{"id": key, **value} for key, value in PROVIDERS.items()]


def list_connectors(owner_id):
    store.init_db()
    with store._lock, store.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM connectors WHERE owner_id=? ORDER BY updated_at DESC",
            (str(owner_id or "admin"),),
        ).fetchall()
    return [_public(row) for row in rows]


def save_connector(owner_id, provider, display_name="", config=None, credentials=None, connector_id=None):
    provider = str(provider or "").lower()
    if provider not in PROVIDERS:
        raise ValueError("unsupported connector provider")
    config = dict(config or {})
    credentials = {key: value for key, value in dict(credentials or {}).items() if key in SECRET_FIELDS and value}
    if provider == "webhook":
        parsed = urlsplit(str(config.get("url") or ""))
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("webhook URL must be a valid HTTPS URL")
    stamp = store.now()
    owner = str(owner_id or "admin")
    connector_id = connector_id or store.new_id("connector")
    with store._lock, store.connect() as conn:
        existing = conn.execute("SELECT credentials FROM connectors WHERE id=? AND owner_id=?", (connector_id, owner)).fetchone()
        if existing:
            saved_credentials = store._loads(existing["credentials"], {})
            saved_credentials.update(credentials)
            credentials = saved_credentials
        conn.execute(
            """
            INSERT INTO connectors(id,owner_id,provider,display_name,status,config,credentials,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              display_name=excluded.display_name,config=excluded.config,credentials=excluded.credentials,
              status='configured',last_error='',updated_at=excluded.updated_at
            """,
            (
                connector_id,
                owner,
                provider,
                str(display_name or PROVIDERS[provider]["name"]),
                "configured",
                store._json(config),
                store._json(credentials),
                stamp,
                stamp,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM connectors WHERE id=?", (connector_id,)).fetchone()
    audit.log("connector_configured", {"id": connector_id, "provider": provider}, actor=owner)
    return _public(row)


def remove_connector(owner_id, connector_id):
    with store._lock, store.connect() as conn:
        cursor = conn.execute("DELETE FROM connectors WHERE id=? AND owner_id=?", (connector_id, str(owner_id or "admin")))
        conn.commit()
    return cursor.rowcount > 0


def test_connector(owner_id, connector_id):
    owner = str(owner_id or "admin")
    with store._lock, store.connect() as conn:
        row = conn.execute("SELECT * FROM connectors WHERE id=? AND owner_id=?", (connector_id, owner)).fetchone()
        if not row:
            raise ValueError("connector missing")
        provider = row["provider"]
        config = store._loads(row["config"], {})
        credentials = store._loads(row["credentials"], {})
        required = PROVIDERS[provider]["required"]
        combined = {**config, **credentials}
        missing = [key for key in required if not combined.get(key)]
        status = "needs_configuration" if missing else "ready_for_authorization" if PROVIDERS[provider]["auth"] == "oauth2" else "ready"
        message = (
            f"Missing required fields: {', '.join(missing)}."
            if missing
            else "OAuth application settings are valid. Authorize this account before data can sync."
            if status == "ready_for_authorization"
            else "Webhook configuration is valid. No external payload was sent during this check."
        )
        stamp = store.now()
        conn.execute(
            "UPDATE connectors SET status=?,last_tested_at=?,last_error=?,updated_at=? WHERE id=?",
            (status, stamp, message if missing else "", stamp, connector_id),
        )
        conn.commit()
    audit.log("connector_tested", {"id": connector_id, "provider": provider, "status": status}, actor=owner)
    return {"id": connector_id, "status": status, "message": message, "missing": missing}
