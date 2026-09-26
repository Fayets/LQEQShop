"""Tienda pública: el catálogo completo en una llamada y el HTML de cada página."""
from __future__ import annotations

import html

from ..config import STATIC_DIR
from ..db import get_categories, get_db, get_settings
from .product_services import ProductServices
from .settings_services import SettingsServices
from .slide_services import SlideServices

products = ProductServices()
slides = SlideServices()
settings_svc = SettingsServices()


class StoreServices:

    def catalog(self) -> dict:
        """El catálogo de una marca chica entra entero: así la navegación entre páginas
        no vuelve a pedir nada al servidor."""
        with get_db() as con:
            prods = products.load(con)
            used = {p["category"] for p in prods}
            return {
                "settings": settings_svc.public(con),
                "categories": [c for c in get_categories(con) if c["name"] in used],
                "hero": slides.load(con, "hero"),
                "banners": slides.load(con, "banner"),
                "products": prods,
            }

    def product_meta(self, slug: str) -> tuple[str, str, str] | None:
        """Título, descripción e imagen para compartir el link de una prenda."""
        with get_db() as con:
            row = con.execute("SELECT id, name, description FROM products WHERE slug = ? AND active = 1", (slug,)).fetchone()
            if not row:
                return None
            img = con.execute("SELECT filename FROM product_images WHERE product_id = ? ORDER BY position, id LIMIT 1", (row["id"],)).fetchone()
        return row["name"], (row["description"] or "")[:160], f"/media/products/{row['id']}/{img['filename']}" if img else ""

    def render_page(self, version: str, title: str = "", description: str = "", image: str = "") -> str:
        with get_db() as con:
            s = get_settings(con)
        brand = s.get("brand_name", "")
        full = f"{title} · {brand}" if title else f"{brand} {s.get('brand_tagline', '')}".strip()
        page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        return (page.replace("{{v}}", version)
                    .replace("{{theme}}", settings_svc.theme_css(s))
                    .replace("{{title}}", html.escape(full))
                    .replace("{{description}}", html.escape(description or f"Tienda online de {brand}. Hacé tu pedido y lo coordinamos por WhatsApp."))
                    .replace("{{image}}", html.escape(image)))

    def render_admin(self, version: str) -> str:
        return (STATIC_DIR / "admin.html").read_text(encoding="utf-8").replace("{{v}}", version)
