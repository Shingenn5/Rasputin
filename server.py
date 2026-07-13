import os

import uvicorn


HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8787"))


def _tls_config():
    enabled = os.environ.get("RASPUTIN_HTTPS", "0").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return {}
    cert_file = os.environ.get("RASPUTIN_TLS_CERT_FILE", "").strip()
    key_file = os.environ.get("RASPUTIN_TLS_KEY_FILE", "").strip()
    if not cert_file or not key_file:
        raise RuntimeError("RASPUTIN_HTTPS requires RASPUTIN_TLS_CERT_FILE and RASPUTIN_TLS_KEY_FILE")
    if not os.path.isfile(cert_file) or not os.path.isfile(key_file):
        raise RuntimeError(f"HTTPS certificate files were not found: {cert_file}, {key_file}")
    return {"ssl_certfile": cert_file, "ssl_keyfile": key_file}


if __name__ == "__main__":
    tls = _tls_config()
    scheme = "https" if tls else "http"
    print(f"Rasputin: {scheme}://{HOST}:{PORT}")
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        log_level=os.environ.get("LOG_LEVEL", "info"),
        **tls,
    )
