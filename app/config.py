"""Rutas y constantes compartidas por servicios y controladores."""
import os

from .db import BASE_DIR

MEDIA_DIR = BASE_DIR / "media"
PRODUCTS_MEDIA = MEDIA_DIR / "products"
SLIDES_MEDIA = MEDIA_DIR / "slides"
BRAND_MEDIA = MEDIA_DIR / "brand"
ORIGINALS_DIR = MEDIA_DIR / "originals"
STATIC_DIR = BASE_DIR / "static"

ADMIN_COOKIE = "lqeq_admin"
PUBLIC_HOSTS = [h.strip() for h in os.environ.get("LQEQ_HOSTS", "").split(",") if h.strip()]
HTTPS_ONLY = os.environ.get("LQEQ_HTTPS", "0") == "1"
MAX_UPLOAD_MB = 25

PRODUCT_IMG = (1200, 1600)
HERO_SIZE, HERO_MOBILE = (2000, 1100), (1000, 1400)
BANNER_SIZE = (1000, 1250)

SID_RE = r"^[A-Za-z0-9_-]{8,64}$"
ORDER_STATUSES = ("pendiente", "confirmado", "entregado", "cancelado")
HOLDS_STOCK = ("confirmado", "entregado")   # estados en los que el pedido ya descontó stock

# cambia en cada arranque: fuerza al navegador a bajar el CSS/JS nuevo
from datetime import datetime as _dt
ASSET_VERSION = str(int(_dt.now().timestamp()))
