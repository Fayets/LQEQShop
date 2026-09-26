"""Números del panel: resumen, visitas una por una, recorrido de cada visita, suscriptoras."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from ..db import get_db, rows

FUNNEL = [("visit", "Entraron a la tienda"), ("view_product", "Miraron una prenda"), ("add_to_cart", "Agregaron al carrito"),
          ("begin_checkout", "Empezaron el pedido"), ("order", "Mandaron el pedido")]

EVENT_LABELS = {"visit": "Entró a la tienda", "page": "Pasó por", "view_product": "Miró", "add_to_cart": "Agregó al carrito",
                "remove_from_cart": "Sacó del carrito", "open_cart": "Abrió el carrito", "begin_checkout": "Empezó el pedido",
                "order": "Mandó el pedido", "whatsapp_float": "Tocó el botón de WhatsApp", "newsletter": "Se suscribió al newsletter",
                "search": "Buscó"}


def date_range(days: int, month: Optional[str]) -> tuple[str, str, Optional[str]]:
    """Últimos N días, o un mes puntual (AAAA-MM)."""
    if month and re.fullmatch(r"\d{4}-\d{2}", month):
        y, m = int(month[:4]), int(month[5:])
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        return f"{y:04d}-{m:02d}-01 00:00:00", f"{ny:04d}-{nm:02d}-01 00:00:00", month
    days = max(1, min(days, 3650))
    return (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d 00:00:00"), "9999-12-31", None


class MetricsServices:

    def summary(self, days: int = 30, month: Optional[str] = None) -> dict:
        since, until, month = date_range(days, month)
        rng = (since, until)
        in_range = "SELECT DISTINCT session_id FROM events WHERE created_at >= ? AND created_at < ?"
        with get_db() as con:
            by_type = {r["type"]: r["n"] for r in con.execute(
                "SELECT type, COUNT(DISTINCT session_id) n FROM events WHERE created_at >= ? AND created_at < ? GROUP BY type", rng)}
            visitors = con.execute("SELECT COUNT(DISTINCT session_id) FROM events WHERE created_at >= ? AND created_at < ?", rng).fetchone()[0]
            new_visitors = con.execute("SELECT COUNT(*) FROM visitors WHERE first_seen >= ? AND first_seen < ?", rng).fetchone()[0]
            sources = rows(con.execute(f"SELECT source, COUNT(*) n FROM visitors WHERE session_id IN ({in_range}) GROUP BY source ORDER BY n DESC", rng))
            devices = {r["device"]: r["n"] for r in con.execute(f"SELECT device, COUNT(*) n FROM visitors WHERE session_id IN ({in_range}) GROUP BY device", rng)}
            orders_by_status = {r["status"]: {"n": r["n"], "total": r["t"]} for r in con.execute(
                "SELECT status, COUNT(*) n, COALESCE(SUM(total),0) t FROM orders WHERE created_at >= ? AND created_at < ? GROUP BY status", rng)}
            carts_open = con.execute("SELECT COUNT(*), COALESCE(SUM(total),0) FROM carts WHERE order_id IS NULL AND units > 0 "
                                     "AND updated_at >= ? AND updated_at < ?", rng).fetchone()
            daily = rows(con.execute(
                """SELECT substr(created_at,1,10) AS day, COUNT(DISTINCT session_id) AS visitas,
                          COUNT(DISTINCT CASE WHEN type='add_to_cart' THEN session_id END) AS carritos,
                          SUM(CASE WHEN type='order' THEN 1 ELSE 0 END) AS pedidos
                   FROM events WHERE created_at >= ? AND created_at < ? GROUP BY day ORDER BY day""", rng))
            per_product = rows(con.execute(
                """SELECT p.id, p.name,
                          COUNT(DISTINCT CASE WHEN e.type='view_product' THEN e.session_id END) AS vistas,
                          COUNT(DISTINCT CASE WHEN e.type='add_to_cart' THEN e.session_id END) AS carrito
                   FROM products p LEFT JOIN events e ON e.product_id = p.id AND e.created_at >= ? AND e.created_at < ?
                   GROUP BY p.id ORDER BY carrito DESC, vistas DESC, p.sort_order""", rng))
            sold = {r["product_id"]: r["n"] for r in con.execute(
                "SELECT oi.product_id, SUM(oi.qty) n FROM order_items oi JOIN orders o ON o.id = oi.order_id "
                "WHERE o.created_at >= ? AND o.created_at < ? AND o.status != 'cancelado' GROUP BY oi.product_id", rng)}
            low_stock = rows(con.execute("SELECT p.id, p.name, s.size, s.stock FROM product_sizes s JOIN products p ON p.id = s.product_id "
                                         "WHERE s.stock <= 1 AND p.active = 1 ORDER BY s.stock, p.name"))
            first = con.execute("SELECT MIN(substr(created_at,1,7)) FROM events").fetchone()[0]
            subscribers = con.execute("SELECT COUNT(*) FROM subscribers WHERE created_at >= ? AND created_at < ?", rng).fetchone()[0]
            has_demo = con.execute("SELECT 1 FROM visitors WHERE session_id LIKE 'demo-%' LIMIT 1").fetchone() is not None
        for pp in per_product:
            pp["pedidas"] = sold.get(pp["id"], 0)
        return {
            "since": since[:10], "month": month, "first_month": first or datetime.now().strftime("%Y-%m"),
            "visitors": visitors, "new_visitors": new_visitors,
            "funnel": [{"key": k, "label": l, "n": visitors if k == "visit" else by_type.get(k, 0)} for k, l in FUNNEL],
            "sources": sources, "devices": devices, "orders_by_status": orders_by_status,
            "revenue_confirmed": sum(orders_by_status.get(s, {}).get("total", 0) for s in ("confirmado", "entregado")),
            "pending": orders_by_status.get("pendiente", {"n": 0, "total": 0}),
            "carts_open": {"n": carts_open[0], "total": carts_open[1]},
            "daily": daily, "per_product": per_product, "low_stock": low_stock, "subscribers": subscribers, "has_demo": has_demo,
        }

    def visitors(self, days: int = 30, filter: str = "all") -> list[dict]:
        """Una fila por persona: de dónde vino, qué miró, qué dejó en el carrito y si pidió."""
        since, _u, _m = date_range(days, None)
        where = "v.last_seen >= ?" + {"cart": " AND c.units > 0", "order": " AND o.id IS NOT NULL",
                                      "abandoned": " AND c.units > 0 AND c.order_id IS NULL"}.get(filter, "")
        with get_db() as con:
            vs = rows(con.execute(
                f"""SELECT v.*, c.items AS cart_items, c.units AS cart_units, c.total AS cart_total, c.order_id AS cart_order,
                           c.updated_at AS cart_updated, o.code AS order_code, o.status AS order_status, o.customer_name,
                           o.customer_phone, o.total AS order_total
                    FROM visitors v
                    LEFT JOIN carts c ON c.session_id = v.session_id
                    LEFT JOIN orders o ON o.id = (SELECT MAX(id) FROM orders WHERE session_id = v.session_id)
                    WHERE {where} ORDER BY v.last_seen DESC LIMIT 300""", (since,)))
            sids = [v["session_id"] for v in vs] or [""]
            marks = ",".join("?" * len(sids))
            names = self._product_names(con)
            seen: dict[str, list] = {}
            for r in con.execute(f"SELECT session_id, product_id, MIN(id) first FROM events WHERE type='view_product' AND session_id IN ({marks}) "
                                 "GROUP BY session_id, product_id ORDER BY first", sids):
                if r["product_id"] in names:
                    seen.setdefault(r["session_id"], []).append(names[r["product_id"]])
        for v in vs:
            v["viewed"] = seen.get(v["session_id"], [])
            v["cart_items"] = json.loads(v["cart_items"]) if v["cart_items"] else []
        return vs

    def timeline(self, sid: str) -> dict:
        with get_db() as con:
            v = con.execute("SELECT * FROM visitors WHERE session_id = ?", (sid,)).fetchone()
            if not v:
                raise HTTPException(404, "No existe esa visita")
            names = self._product_names(con)
            evs = rows(con.execute("SELECT * FROM events WHERE session_id = ? ORDER BY id LIMIT 400", (sid,)))
            orders = rows(con.execute("SELECT id, code, status, total, customer_name, customer_phone, created_at FROM orders WHERE session_id = ? ORDER BY id", (sid,)))
        out = []
        for e in evs:
            meta = json.loads(e["meta"] or "{}")
            detail = names.get(e["product_id"], "") if e["product_id"] else ""
            if e["type"] == "page":
                detail = meta.get("title") or meta.get("path") or ""
            elif e["type"] == "search":
                detail = f"“{meta.get('q', '')}”"
            elif e["type"] == "order":
                detail = meta.get("code", "")
            if e["size"]:
                detail += f" · talle {e['size']}"
            out.append({"at": e["created_at"], "type": e["type"], "label": EVENT_LABELS.get(e["type"], e["type"]), "detail": detail})
        return {"visitor": dict(v), "events": out, "orders": orders}

    def subscribers(self) -> list[dict]:
        with get_db() as con:
            return rows(con.execute("SELECT * FROM subscribers ORDER BY id DESC"))

    def subscribers_csv(self) -> str:
        def cell(v):
            return '"' + str(v or "").replace('"', '""') + '"'
        subs = self.subscribers()
        # BOM para que Excel abra bien los acentos
        return "﻿email,nombre,telefono,fecha\n" + "\n".join(
            ",".join(cell(s[k]) for k in ("email", "name", "phone", "created_at")) for s in subs)

    def reset(self) -> int:
        """Borra visitas, recorridos y carritos sin pedido, más todo lo inventado por
        `seed --demo-metrics`. No toca pedidos reales, stock, prendas ni suscriptoras."""
        with get_db() as con:
            n = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            con.execute("DELETE FROM events")
            con.execute("DELETE FROM orders WHERE session_id LIKE 'demo-%'")
            con.execute("DELETE FROM carts WHERE order_id IS NULL OR session_id LIKE 'demo-%'")
            con.execute("DELETE FROM visitors WHERE session_id NOT IN (SELECT session_id FROM orders WHERE session_id IS NOT NULL)")
        return n

    def _product_names(self, con) -> dict:
        return {r["id"]: r["name"] for r in con.execute("SELECT id, name FROM products")}
