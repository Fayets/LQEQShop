"""Lo que ellas quieren · tienda + carrito a WhatsApp + panel de gestión.

Acá solo se arma la app: cabeceras de seguridad, arranque y routers. La lógica vive en
app/services/ y los endpoints en app/controllers/ (que solo llaman a los servicios).
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BRAND_MEDIA, HTTPS_ONLY, MAX_UPLOAD_MB, MEDIA_DIR, ORIGINALS_DIR, PRODUCTS_MEDIA, PUBLIC_HOSTS, SLIDES_MEDIA, STATIC_DIR
from .controllers import (auth_controller, category_controller, metrics_controller, order_controller, product_controller,
                          settings_controller, slide_controller, store_controller, tracking_controller)
from .db import init_db

app = FastAPI(title="Lo que ellas quieren", docs_url=None, redoc_url=None, openapi_url=None)

if PUBLIC_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=PUBLIC_HOSTS + ["localhost", "127.0.0.1"])

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; form-action 'self'; "
       "frame-ancestors 'none'; base-uri 'self'")


@app.middleware("http")
async def headers_and_cache(request: Request, call_next):
    """Cabeceras de seguridad, tope de tamaño y que el navegador no se quede con CSS/JS viejos."""
    length = request.headers.get("content-length")
    if request.method in ("POST", "PUT") and length and length.isdigit() and int(length) > MAX_UPLOAD_MB * 4 * 1024 * 1024:
        return Response("Archivo demasiado grande", status_code=413)
    response = await call_next(request)
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "strict-origin-when-cross-origin"
    h["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    h["Content-Security-Policy"] = CSP
    if HTTPS_ONLY:
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    path = request.url.path
    if path.startswith(("/api/admin", "/admin")):
        h["Cache-Control"] = "no-store"
    elif path.startswith("/media"):
        h["Cache-Control"] = "public, max-age=86400"   # los nombres de archivo son únicos
    elif not path.startswith("/api"):
        h["Cache-Control"] = "no-cache, must-revalidate"
    return response


@app.on_event("startup")
def startup() -> None:
    init_db()
    for d in (PRODUCTS_MEDIA, SLIDES_MEDIA, BRAND_MEDIA, ORIGINALS_DIR):
        d.mkdir(parents=True, exist_ok=True)


for module in (auth_controller, store_controller, tracking_controller, order_controller, product_controller,
               category_controller, slide_controller, metrics_controller, settings_controller):
    app.include_router(module.router)

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
