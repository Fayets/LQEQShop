"""Dependencias compartidas por los controladores."""
from fastapi import HTTPException, Request, Response, UploadFile

from . import security as sec
from .config import ADMIN_COOKIE, HTTPS_ONLY, MAX_UPLOAD_MB
from .services.auth_services import AuthServices

_auth = AuthServices()


def require_admin(request: Request) -> bool:
    if not _auth.is_valid(request.cookies.get(ADMIN_COOKIE, "")):
        raise HTTPException(401, "No autorizado")
    return True


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(ADMIN_COOKIE, token, httponly=True, secure=HTTPS_ONLY, samesite="lax",
                        max_age=60 * 60 * 24 * sec.SESSION_DAYS, path="/")


def client(request: Request) -> tuple[str, str, str]:
    """(ip, host, user-agent) del que hace el pedido."""
    return sec.client_ip(request), request.url.hostname or "", request.headers.get("user-agent", "")


async def read_upload(f: UploadFile) -> tuple[str, bytes]:
    data = await f.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"{f.filename}: la foto pesa más de {MAX_UPLOAD_MB} MB")
    return f.filename or "foto.jpg", data
