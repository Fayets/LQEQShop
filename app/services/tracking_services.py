"""Lo que registra la tienda de cada visita: eventos, visitantes, carrito y newsletter.

Cada navegador tiene un id al azar (session_id). Con eso se unen "entró", "miró esta
prenda", "armó este carrito" y "mandó el pedido" en una misma fila del panel.
"""
from __future__ import annotations

import json
import re
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException

from ..config import SID_RE
from ..db import get_db
from ..schemas import CartIn, EventIn, NewsletterIn
from ..utils import clean
from .product_services import ProductServices


def classify_source(referrer: str, utm_source: str, ua: str, own_host: str) -> str:
    """De dónde vino: primero los utm, después el referrer y por último el navegador
    (el de Instagram/Facebook se delata en el user-agent aunque no mande referrer)."""
    s, ua = (utm_source or "").lower(), ua or ""
    host = (urlparse(referrer).hostname or "").lower() if referrer else ""
    if own_host and host.endswith(own_host):
        host = ""
    probe = f"{s} {host}"
    if "instagram" in probe or s == "ig" or "Instagram" in ua:
        return "Instagram"
    if "facebook" in probe or s == "fb" or "FBAN" in ua or "FBAV" in ua:
        return "Facebook"
    if "whatsapp" in probe or s == "wa":
        return "WhatsApp"
    if "tiktok" in probe:
        return "TikTok"
    if "google" in probe:
        return "Google"
    if s:
        return s[:30].capitalize()
    if host:
        return host.removeprefix("www.")[:40]
    return "Directo"


def device_of(ua: str) -> str:
    return "Celular" if re.search(r"Mobi|Android|iPhone|iPad", ua or "") else "Compu"


class TrackingServices:

    def touch_visitor(self, con, sid: str, host: str, ua: str, meta: Optional[dict] = None, new_visit: bool = False) -> None:
        if not con.execute("SELECT 1 FROM visitors WHERE session_id = ?", (sid,)).fetchone():
            meta = meta or {}
            con.execute(
                "INSERT INTO visitors(session_id, source, referrer, campaign, landing, device) VALUES (?,?,?,?,?,?)",
                (sid, classify_source(meta.get("referrer", ""), meta.get("utm_source", ""), ua, host),
                 clean(meta.get("referrer"), 300), clean(meta.get("utm_campaign"), 80), clean(meta.get("path"), 200), device_of(ua)),
            )
        else:
            con.execute("UPDATE visitors SET last_seen = datetime('now','localtime'), visits = visits + ? WHERE session_id = ?",
                        (1 if new_visit else 0, sid))

    def record_event(self, body: EventIn, host: str, ua: str) -> None:
        meta = {k: (str(v)[:300] if v is not None else None) for k, v in list((body.meta or {}).items())[:10]}
        with get_db() as con:
            self.touch_visitor(con, body.session_id, host, ua, meta, new_visit=body.type == "visit")
            con.execute("INSERT INTO events(type, product_id, size, session_id, meta) VALUES (?,?,?,?,?)",
                        (body.type, body.product_id, body.size, body.session_id, json.dumps(meta, ensure_ascii=False)))

    def save_cart(self, body: CartIn, host: str, ua: str) -> None:
        """Guarda el carrito tal como está: es lo que deja ver quién armó un carrito y no
        lo terminó. Los precios salen del catálogo, no del navegador."""
        with get_db() as con:
            by_id = {p["id"]: p for p in ProductServices().load(con)}
            items, units, total = [], 0, 0.0
            for it in body.items:
                p = by_id.get(it.product_id)
                if not p:
                    continue
                items.append({"product_id": p["id"], "name": p["name"], "size": it.size, "color": it.color, "qty": it.qty, "price": p["price"]})
                units += it.qty
                total += p["price"] * it.qty
            prev = con.execute("SELECT order_id FROM carts WHERE session_id = ?", (body.session_id,)).fetchone()
            if prev is None and not items:
                return
            self.touch_visitor(con, body.session_id, host, ua)
            payload = json.dumps(items, ensure_ascii=False)
            if prev is None:
                con.execute("INSERT INTO carts(session_id, items, units, total) VALUES (?,?,?,?)", (body.session_id, payload, units, total))
            elif prev["order_id"] and items:
                # ya había comprado y arma otro: es un carrito nuevo
                con.execute("UPDATE carts SET items=?, units=?, total=?, order_id=NULL, created_at=datetime('now','localtime'), "
                            "updated_at=datetime('now','localtime') WHERE session_id=?", (payload, units, total, body.session_id))
            elif not prev["order_id"]:
                con.execute("UPDATE carts SET items=?, units=?, total=?, updated_at=datetime('now','localtime') WHERE session_id=?",
                            (payload, units, total, body.session_id))

    def subscribe(self, body: NewsletterIn, host: str, ua: str) -> None:
        email = body.email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise HTTPException(400, "Revisá el email")
        with get_db() as con:
            con.execute(
                "INSERT INTO subscribers(email, name, phone, session_id) VALUES (?,?,?,?) ON CONFLICT(email) DO UPDATE SET "
                "name = COALESCE(NULLIF(excluded.name,''), name), phone = COALESCE(NULLIF(excluded.phone,''), phone)",
                (email, clean(body.name, 80), clean(body.phone, 40), body.session_id))
            if body.session_id and re.fullmatch(SID_RE, body.session_id):
                self.touch_visitor(con, body.session_id, host, ua)
                con.execute("INSERT INTO events(type, session_id) VALUES ('newsletter', ?)", (body.session_id,))
