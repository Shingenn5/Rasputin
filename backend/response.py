from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


def ok(data=None):
    return {"ok": True, "data": data, "error": None}


def fail(code, message, status=400):
    return JSONResponse(
        status_code=status,
        content={"ok": False, "data": None, "error": {"code": code, "message": str(message)}},
    )


async def error_handler(request: Request, exc: Exception):
    if isinstance(exc, PermissionError):
        return fail("permission_denied", exc, 403)
    if isinstance(exc, ValueError):
        return fail("bad_request", exc, 400)
    return fail("internal_error", exc, 500)


async def http_error_handler(request: Request, exc: HTTPException):
    code = "auth_required" if exc.status_code == 401 else "http_error"
    return fail(code, exc.detail, exc.status_code)
