from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


def _camel_code(code):
    parts = str(code or "error").split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _camel_key(key):
    if not isinstance(key, str) or "_" not in key:
        return key
    parts = key.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def camelize(value):
    if isinstance(value, dict):
        return {_camel_key(k): camelize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [camelize(v) for v in value]
    return value


class AppError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = str(message)
        self.status = status


def ok(data=None):
    return {"ok": True, "data": camelize(data), "error": None}


def fail(code, message, status=400):
    return JSONResponse(
        status_code=status,
        content={"ok": False, "data": None, "error": {"code": _camel_code(code), "message": str(message)}},
    )


async def error_handler(request: Request, exc: Exception):
    if isinstance(exc, AppError):
        return fail(exc.code, exc.message, exc.status)
    if isinstance(exc, PermissionError):
        return fail("permission_denied", exc, 403)
    if isinstance(exc, ValueError):
        return fail("bad_request", exc, 400)
    return fail("internal_error", "server error", 500)


async def http_error_handler(request: Request, exc: HTTPException):
    code = "auth_required" if exc.status_code == 401 else "http_error"
    return fail(code, exc.detail, exc.status_code)
