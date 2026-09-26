"""Categorías del menú de la tienda."""
from fastapi import HTTPException

from ..db import get_categories, get_db
from ..schemas import CategoryIn
from ..utils import slugify


class CategoryServices:

    def get_all(self) -> list[dict]:
        with get_db() as con:
            cats = get_categories(con)
            counts = {r["category"]: r["n"] for r in con.execute("SELECT category, COUNT(*) n FROM products GROUP BY category")}
        for c in cats:
            c["products"] = counts.get(c["name"], 0)
        return cats

    def save_all(self, categories: list[CategoryIn]) -> list[dict]:
        """Guarda la lista completa y en orden. Si una categoría cambia de nombre, sus
        prendas la siguen. Las que faltan se borran, salvo que tengan prendas adentro."""
        with get_db() as con:
            existing = {r["id"]: r["name"] for r in con.execute("SELECT id, name FROM categories")}
            keep, seen = set(), set()
            for pos, c in enumerate(categories):
                name = " ".join(c.name.split())
                if not name:
                    continue
                if name.lower() in seen:
                    raise HTTPException(400, f"«{name}» está repetida.")
                seen.add(name.lower())
                if c.id is not None and c.id in existing:
                    old = existing[c.id]
                    con.execute("UPDATE categories SET name = ?, slug = ?, position = ? WHERE id = ?", (name, slugify(name), pos, c.id))
                    if old != name:
                        con.execute("UPDATE products SET category = ? WHERE category = ?", (name, old))
                    keep.add(c.id)
                else:
                    cur = con.execute("INSERT INTO categories(name, slug, position) VALUES (?, ?, ?)", (name, slugify(name), pos))
                    keep.add(cur.lastrowid)
            for cid, name in existing.items():
                if cid in keep:
                    continue
                n = con.execute("SELECT COUNT(*) FROM products WHERE category = ?", (name,)).fetchone()[0]
                if n:
                    raise HTTPException(400, f"No se puede borrar «{name}»: tiene {n} prenda{'' if n == 1 else 's'}. Movelas primero.")
                con.execute("DELETE FROM categories WHERE id = ?", (cid,))
        return self.get_all()
