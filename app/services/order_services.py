"""Pedidos web: se crean desde la tienda y se gestionan desde el panel.

Como en Coquetines, un pedido web es una intención de compra: al crearse NO toca el
stock. El stock se descuenta cuando la dueña lo pasa a confirmado/entregado y vuelve si
el pedido regresa a pendiente o se cancela. `stock_applied` evita descontar dos veces.
Los precios se recalculan siempre acá contra el catálogo: el navegador no manda precios.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional
from urllib.parse import quote

from fastapi import HTTPException

from ..config import HOLDS_STOCK, ORDER_STATUSES
from ..db import get_db, get_settings, rows
from ..schemas import OrderIn
from ..utils import clean, money
from .product_services import ProductServices
from .tracking_services import TrackingServices

products = ProductServices()
tracking = TrackingServices()


class OrderServices:

    # ------------------------------------------------------------ tienda
    def create(self, body: OrderIn, host: str, user_agent: str) -> dict:
        if not body.items:
            raise HTTPException(400, "El carrito está vacío")
        payment = body.payment if body.payment in ("transferencia", "efectivo", "tarjeta") else "transferencia"
        delivery = "envio" if body.delivery == "envio" else "retiro"
        if delivery == "envio" and (len(body.address.strip()) < 4 or len(body.city.strip()) < 2):
            raise HTTPException(400, "Completá la dirección y la localidad para el envío")
        with get_db() as con:
            settings = get_settings(con)
            items, subtotal, total = self._price_items(con, body, payment)
            cur = con.execute(
                "INSERT INTO orders(code, customer_name, customer_phone, delivery, city, address, note, payment, subtotal, total, session_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, clean(body.customer_name, 80), clean(body.customer_phone, 40), delivery,
                 clean(body.city, 80), clean(body.address, 160), body.note.strip()[:500], payment, subtotal, total, body.session_id),
            )
            oid = cur.lastrowid
            code = f"LQ-{oid:04d}"
            con.execute("UPDATE orders SET code = ? WHERE id = ?", (code, oid))
            for it in items:
                con.execute(
                    "INSERT INTO order_items(order_id, product_id, product_name, size, color, qty, unit_price, list_price) VALUES (?,?,?,?,?,?,?,?)",
                    (oid, it["product_id"], it["product_name"], it["size"], it["color"], it["qty"], it["unit_price"], it["list_price"]))
            if body.session_id:
                tracking.touch_visitor(con, body.session_id, host, user_agent)
                con.execute("UPDATE carts SET order_id = ?, updated_at = datetime('now','localtime') WHERE session_id = ?", (oid, body.session_id))
                con.execute("INSERT INTO events(type, session_id, meta) VALUES ('order', ?, ?)",
                            (body.session_id, json.dumps({"order_id": oid, "code": code, "total": total})))
            order = {"id": oid, "code": code, "payment": payment, "total": total, "delivery": delivery,
                     "city": clean(body.city, 80), "address": clean(body.address, 160),
                     "customer_name": clean(body.customer_name, 80), "note": body.note.strip()[:500]}
        return {"ok": True, "order": order, "whatsapp_url": self._whatsapp_url(settings, order, items)}

    def _price_items(self, con, body: OrderIn, payment: str) -> tuple[list[dict], float, float]:
        by_id = {p["id"]: p for p in products.load(con)}
        out, subtotal, total = [], 0.0, 0.0
        for it in body.items:
            p = by_id.get(it.product_id)
            if not p:
                raise HTTPException(409, "Una de las prendas ya no está disponible. Actualizá la página.")
            size = None
            if p["sizes"]:
                row = next((s for s in p["sizes"] if s["size"] == it.size), None)
                if not row:
                    raise HTTPException(400, f"Elegí un talle para {p['name']}")
                if row["stock"] < it.qty:
                    raise HTTPException(409, f"De {p['name']} talle {it.size} quedan {row['stock']}.")
                size = row["size"]
            color = None
            if p["colors"]:
                color = next((c["name"] for c in p["colors"] if c["name"] == it.color), None)
                if not color:
                    raise HTTPException(400, f"Elegí un color para {p['name']}")
            unit_list = float(p["price"])
            unit = p["transfer_price_final"] if payment in ("transferencia", "efectivo") else unit_list
            out.append({"product_id": p["id"], "product_name": p["name"], "size": size, "color": color,
                        "qty": it.qty, "unit_price": unit, "list_price": unit_list})
            subtotal += unit_list * it.qty
            total += unit * it.qty
        return out, subtotal, total

    def _whatsapp_url(self, settings: dict, order: dict, items: list[dict]) -> str:
        lines = [settings.get("whatsapp_greeting") or "¡Hola! Quiero hacer este pedido:", ""]
        for it in items:
            det = "".join([f" · Talle {it['size']}" if it.get("size") else "", f" · {it['color']}" if it.get("color") else ""])
            lines.append(f"• {it['qty']} x {it['product_name']}{det} — {money(it['unit_price'] * it['qty'])}")
        lines += ["", f"Total: {money(order['total'])} ({order['payment']})"]
        lines.append(f"Envío a: {order['address']}, {order['city']}" if order["delivery"] == "envio" else "Retiro / coordino la entrega")
        if order.get("note"):
            lines.append(f"Nota: {order['note']}")
        lines += [f"Nombre: {order['customer_name']}", f"Pedido N° {order['code']}"]
        return f"https://wa.me/{settings['whatsapp_number']}?text={quote(chr(10).join(lines))}"

    # ------------------------------------------------------------ panel
    def get_all(self, status: Optional[str] = None) -> list[dict]:
        with get_db() as con:
            q, args = "SELECT o.*, v.source FROM orders o LEFT JOIN visitors v ON v.session_id = o.session_id", []
            if status in ORDER_STATUSES:
                q += " WHERE o.status = ?"
                args.append(status)
            orders = rows(con.execute(q + " ORDER BY o.id DESC LIMIT 500", args))
            ids = [o["id"] for o in orders] or [0]
            items: dict[int, list] = {}
            for it in rows(con.execute(f"SELECT * FROM order_items WHERE order_id IN ({','.join('?' * len(ids))}) ORDER BY id", ids)):
                items.setdefault(it["order_id"], []).append(it)
        for o in orders:
            o["items"] = items.get(o["id"], [])
        return orders

    def set_status(self, oid: int, status: str) -> None:
        if status not in ORDER_STATUSES:
            raise HTTPException(400, "Estado inválido")
        with get_db() as con:
            con.execute("BEGIN IMMEDIATE")
            o = con.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
            if not o:
                raise HTTPException(404, "El pedido no existe")
            items = rows(con.execute("SELECT * FROM order_items WHERE order_id = ? AND size IS NOT NULL", (oid,)))
            want = status in HOLDS_STOCK
            if want and not o["stock_applied"]:
                for it in items:
                    row = con.execute("SELECT stock FROM product_sizes WHERE product_id = ? AND size = ?", (it["product_id"], it["size"])).fetchone()
                    if row is not None and row["stock"] < it["qty"]:
                        raise HTTPException(409, f"No alcanza el stock de {it['product_name']} talle {it['size']} (quedan {row['stock']}). Ajustalo en Productos o cancelá el pedido.")
                self._move_stock(con, oid, items, -1, f"pedido {status}")
                con.execute("UPDATE orders SET stock_applied = 1 WHERE id = ?", (oid,))
            elif not want and o["stock_applied"]:
                self._move_stock(con, oid, items, +1, f"pedido vuelto a {status}")
                con.execute("UPDATE orders SET stock_applied = 0 WHERE id = ?", (oid,))
            con.execute("UPDATE orders SET status = ?, updated_at = datetime('now','localtime') WHERE id = ?", (status, oid))

    def _move_stock(self, con, oid: int, items: list[dict], sign: int, reason: str) -> None:
        for it in items:
            con.execute("UPDATE product_sizes SET stock = stock + ? WHERE product_id = ? AND size = ?", (sign * it["qty"], it["product_id"], it["size"]))
            con.execute("INSERT INTO stock_moves(product_id, size, delta, reason, order_id) VALUES (?,?,?,?,?)",
                        (it["product_id"], it["size"], sign * it["qty"], reason, oid))

    def set_note(self, oid: int, note: str) -> None:
        with get_db() as con:
            con.execute("UPDATE orders SET admin_note = ?, updated_at = datetime('now','localtime') WHERE id = ?", (note, oid))
