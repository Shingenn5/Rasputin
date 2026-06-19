from fastapi import APIRouter, Depends, Request, Response
from backend.core import auth
from backend.core.response import ok
from backend.api.common import CamelModel, current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginIn(CamelModel):
    username: str = "admin"
    password: str

class PasswordChangeIn(CamelModel):
    current_password: str
    new_password: str

@router.get("/session")
async def auth_session(request: Request):
    host = request.client.host if request.client else ""
    token = request.cookies.get(auth.COOKIE_NAME)
    return ok(auth.public_session(token, host))

@router.post("/login")
async def auth_login(req: LoginIn, response: Response, request: Request):
    host = request.client.host if request.client else "local"
    token, info = auth.login(req.username, req.password, host)
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        httponly=True,
        secure=auth.cookie_secure(),
        samesite="strict",
        max_age=60 * 60 * 12,
        path="/",
    )
    return ok(info)

@router.post("/logout")
async def auth_logout(response: Response, request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    out = auth.logout(token)
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return ok(out)

@router.post("/change-password")
async def auth_change_password(req: PasswordChangeIn, request: Request, user=Depends(current_user)):
    username = user.get("username")
    if username == "localhost":
        username = auth.load_public().get("username", "admin")
    return ok(auth.change_password(username, req.current_password, req.new_password))
