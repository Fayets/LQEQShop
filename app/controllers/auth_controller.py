"""Login del panel."""
from fastapi import APIRouter, Depends, Request, Response

from ..config import ADMIN_COOKIE
from ..deps import client, require_admin, set_session_cookie
from ..schemas import LoginIn, NewPinIn
from ..services.auth_services import AuthServices

router = APIRouter(prefix="/api/admin")
service = AuthServices()


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    ip, _host, ua = client(request)
    token, must_change = service.login(body.pin, ip, ua)
    set_session_cookie(response, token)
    return {"ok": True, "must_change_pin": must_change}


@router.post("/logout")
def logout(request: Request, response: Response):
    service.logout(request.cookies.get(ADMIN_COOKIE, ""))
    response.delete_cookie(ADMIN_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(_: bool = Depends(require_admin)):
    return {"ok": True, "must_change_pin": service.must_change_pin()}


@router.post("/pin")
def change_pin(body: NewPinIn, request: Request, response: Response, _: bool = Depends(require_admin)):
    ip, _host, ua = client(request)
    set_session_cookie(response, service.change_pin(body.current_pin, body.new_pin, ip, ua))
    return {"ok": True}
