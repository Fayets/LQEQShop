"""CRUD de productos: datos, talles/stock, colores y fotos."""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from .. import images as imgproc
from ..config import ORIGINALS_DIR, PRODUCT_IMG, PRODUCTS_MEDIA
from ..db import get_db, get_settings, rows
from ..schemas import ColorIn, ProductIn, SizeIn
from ..utils import slugify
from .category_services import CategoryServices

categories = CategoryServices()


def transfer_price_for(p: dict, settings: dict) -> float:
    """Precio único por prenda: pagando con transferencia o efectivo se descuenta el % de
    Ajustes (10% por defecto). No hay precios cargados a mano por medio de pago."""
    pct = float(settings.get("transfer_discount_pct") or 0)
    return round(float(p["price"]) * (1 - pct / 100))


class ProductServices:

    # ------------------------------------------------------------ lectura
    def load(self, con, only_active: bool = True, product_id: Optional[int] = None) -> list[dict]:
        """Productos con fotos, talles, colores y precios calculados. Recibe la conexión
        para poder usarse dentro de transacciones de otros servicios (pedidos, carrito)."""
        settings = get_settings(con)
        q, args = "SELECT * FROM products WHERE 1=1", []
        if only_active:
            q += " AND active = 1"
        if product_id is not None:
            q += " AND id = ?"
            args.append(product_id)
        prods = rows(con.execute(q + " ORDER BY sort_order, id", args))
        ids = [p["id"] for p in prods] or [0]
        marks = ",".join("?" * len(ids))
        imgs, sizes, colors = {}, {}, {}
        for im in rows(con.execute(f"SELECT * FROM product_images WHERE product_id IN ({marks}) ORDER BY position, id", ids)):
            im["url"] = f"/media/products/{im['product_id']}/{im['filename']}"
            im["thumb_url"] = f"/media/products/{im['product_id']}/{im['thumb']}"
            imgs.setdefault(im["product_id"], []).append(im)
        for s in rows(con.execute(f"SELECT id, product_id, size, stock, position FROM product_sizes WHERE product_id IN ({marks}) ORDER BY position, id", ids)):
            sizes.setdefault(s["product_id"], []).append(s)
        for c in rows(con.execute(f"SELECT id, product_id, name, hex, position FROM product_colors WHERE product_id IN ({marks}) ORDER BY position, id", ids)):
            colors.setdefault(c["product_id"], []).append(c)
        for p in prods:
            p.pop("card_price", None)       # columnas viejas: el precio es único
            p.pop("transfer_price", None)
            p["images"] = imgs.get(p["id"], [])
            p["sizes"] = sizes.get(p["id"], [])
            p["colors"] = colors.get(p["id"], [])
            p["transfer_price_final"] = transfer_price_for(p, settings)
            p["total_stock"] = sum(s["stock"] for s in p["sizes"])
            # sin talles cargados, la prenda se vende sin control de stock
            p["sold_out"] = bool(p["sizes"]) and p["total_stock"] == 0
            p["off_pct"] = round((1 - p["price"] / p["compare_price"]) * 100) if p.get("compare_price") and p["compare_price"] > p["price"] else 0
        return prods

    def get_all(self) -> list[dict]:
        with get_db() as con:
            return self.load(con, only_active=False)

    def get_one(self, con, pid: int) -> dict:
        ps = self.load(con, only_active=False, product_id=pid)
        if not ps:
            raise HTTPException(404, "La prenda no existe")
        return ps[0]

    # ------------------------------------------------------------ escritura
    def create(self, body: ProductIn) -> dict:
        with get_db() as con:
            category = categories.ensure(con, body.category)
            # las nuevas van primero: aparecen arriba en el panel y en NEW IN
            con.execute("UPDATE products SET sort_order = sort_order + 1")
            cur = con.execute(
                "INSERT INTO products(slug, name, description, category, price, compare_price, featured, active, sort_order) "
                "VALUES (?,?,?,?,?,?,?,?,0)",
                (self._unique_slug(con, body.name), body.name.strip(), body.description, category, body.price,
                 body.compare_price or None, int(body.featured), int(body.active)),
            )
            pid = cur.lastrowid
            self._save_sizes(con, pid, body.sizes)
            self._save_colors(con, pid, body.colors)
            return self.get_one(con, pid)

    def update(self, pid: int, body: ProductIn) -> dict:
        with get_db() as con:
            old = con.execute("SELECT name, slug FROM products WHERE id = ?", (pid,)).fetchone()
            if not old:
                raise HTTPException(404, "La prenda no existe")
            category = categories.ensure(con, body.category)
            slug = old["slug"] if old["name"] == body.name.strip() else self._unique_slug(con, body.name, pid)
            con.execute(
                "UPDATE products SET slug=?, name=?, description=?, category=?, price=?, compare_price=?, featured=?, active=?, "
                "updated_at=datetime('now','localtime') WHERE id=?",
                (slug, body.name.strip(), body.description, category, body.price, body.compare_price or None,
                 int(body.featured), int(body.active), pid),
            )
            self._save_sizes(con, pid, body.sizes)
            self._save_colors(con, pid, body.colors)
            return self.get_one(con, pid)

    def duplicate(self, pid: int) -> dict:
        """Copia textos, precios, talles y colores (no las fotos) y la deja oculta: sirve
        para cargar rápido la misma prenda en otra estampa."""
        with get_db() as con:
            p = self.get_one(con, pid)
        return self.create(ProductIn(
            name=p["name"] + " (copia)", description=p["description"], category=p["category"], price=p["price"],
            compare_price=p["compare_price"], featured=bool(p["featured"]), active=False,
            sizes=[SizeIn(size=s["size"], stock=s["stock"]) for s in p["sizes"]],
            colors=[ColorIn(name=c["name"], hex=c["hex"]) for c in p["colors"]],
        ))

    def delete(self, pid: int) -> None:
        with get_db() as con:
            con.execute("DELETE FROM products WHERE id = ?", (pid,))
        folder = PRODUCTS_MEDIA / str(pid)   # si no, las fotos quedan ocupando disco
        if folder.is_dir():
            for f in folder.iterdir():
                f.unlink(missing_ok=True)
            folder.rmdir()

    def reorder(self, ids: list[int]) -> None:
        with get_db() as con:
            for pos, pid in enumerate(ids):
                con.execute("UPDATE products SET sort_order = ? WHERE id = ?", (pos, pid))

    # ------------------------------------------------------------ fotos
    def add_images(self, pid: int, files: list[tuple[str, bytes]], mode: str) -> list[dict]:
        mode = mode if mode in ("auto", "cover", "contain") else "auto"
        with get_db() as con:
            if not con.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone():
                raise HTTPException(404, "La prenda no existe")
            pos = con.execute("SELECT COALESCE(MAX(position),-1) FROM product_images WHERE product_id = ?", (pid,)).fetchone()[0] + 1
            out = []
            for name, data in files[:20]:
                try:
                    info = imgproc.process_upload(data, name, PRODUCTS_MEDIA / str(pid), ORIGINALS_DIR, *PRODUCT_IMG, mode)
                except ValueError as e:
                    raise HTTPException(400, str(e))
                except Exception:
                    raise HTTPException(400, f"{name}: no se pudo leer la imagen")
                cur = con.execute(
                    "INSERT INTO product_images(product_id, filename, thumb, original, width, height, position) VALUES (?,?,?,?,?,?,?)",
                    (pid, info["filename"], info["thumb"], info["original"], info["width"], info["height"], pos))
                pos += 1
                out.append({"id": cur.lastrowid, **info, "url": f"/media/products/{pid}/{info['filename']}",
                            "thumb_url": f"/media/products/{pid}/{info['thumb']}"})
            return out

    def delete_image(self, iid: int) -> None:
        with get_db() as con:
            row = con.execute("SELECT * FROM product_images WHERE id = ?", (iid,)).fetchone()
            if not row:
                raise HTTPException(404, "La foto no existe")
            for name in (row["filename"], row["thumb"]):
                (PRODUCTS_MEDIA / str(row["product_id"]) / name).unlink(missing_ok=True)
            con.execute("DELETE FROM product_images WHERE id = ?", (iid,))

    def reorder_images(self, pid: int, ids: list[int]) -> None:
        """La primera es la principal: la de la grilla y la que abre la ficha."""
        with get_db() as con:
            for pos, iid in enumerate(ids[:200]):
                con.execute("UPDATE product_images SET position = ? WHERE id = ? AND product_id = ?", (pos, iid, pid))

    def reprocess_image(self, iid: int, mode: str) -> None:
        with get_db() as con:
            row = con.execute("SELECT * FROM product_images WHERE id = ?", (iid,)).fetchone()
        if not row or not row["original"]:
            raise HTTPException(404, "No hay original guardado")
        mode = mode if mode in ("cover", "contain") else "cover"
        imgproc.reprocess(ORIGINALS_DIR / row["original"], PRODUCTS_MEDIA / str(row["product_id"]), *PRODUCT_IMG, mode, row["filename"], row["thumb"])

    # ------------------------------------------------------------ internos
    def _unique_slug(self, con, name: str, pid: Optional[int] = None) -> str:
        base = slugify(name)
        slug, i = base, 2
        while con.execute("SELECT 1 FROM products WHERE slug = ? AND id IS NOT ?", (slug, pid)).fetchone():
            slug, i = f"{base}-{i}", i + 1
        return slug

    def _save_sizes(self, con, pid: int, sizes: list[SizeIn]) -> None:
        """Cada cambio de stock hecho a mano queda en stock_moves."""
        existing = {r["size"]: dict(r) for r in con.execute("SELECT * FROM product_sizes WHERE product_id = ?", (pid,))}
        keep = set()
        for pos, s in enumerate(sizes):
            name = s.size.strip().upper()
            if not name or name in keep:
                continue
            keep.add(name)
            if name in existing:
                delta = s.stock - existing[name]["stock"]
                con.execute("UPDATE product_sizes SET stock = ?, position = ? WHERE id = ?", (s.stock, pos, existing[name]["id"]))
                if delta:
                    con.execute("INSERT INTO stock_moves(product_id, size, delta, reason) VALUES (?,?,?,?)", (pid, name, delta, "ajuste manual"))
            else:
                con.execute("INSERT INTO product_sizes(product_id, size, stock, position) VALUES (?,?,?,?)", (pid, name, s.stock, pos))
                if s.stock:
                    con.execute("INSERT INTO stock_moves(product_id, size, delta, reason) VALUES (?,?,?,?)", (pid, name, s.stock, "alta"))
        for name, row in existing.items():
            if name not in keep:
                con.execute("DELETE FROM product_sizes WHERE id = ?", (row["id"],))

    def _save_colors(self, con, pid: int, colors: list[ColorIn]) -> None:
        """Los colores viajan con el pedido; el stock lo llevan los talles."""
        con.execute("DELETE FROM product_colors WHERE product_id = ?", (pid,))
        seen = set()
        for pos, c in enumerate(colors):
            name = c.name.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            con.execute("INSERT INTO product_colors(product_id, name, hex, position) VALUES (?,?,?,?)", (pid, name, c.hex.lower(), pos))
