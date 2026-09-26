"""Carga inicial de muestra: prendas, portada y categorías con fotos libres de Unsplash
(seed_img/). Solo carga lo que falta, así que se puede correr las veces que haga falta.

    python -m app.seed                 # catálogo y portada de muestra
    python -m app.seed --demo-metrics  # además, visitas/carritos/pedidos inventados para ver el panel

Todo lo inventado por --demo-metrics lleva session_id "demo-..." y el botón
"Borrar métricas" del panel lo saca entero (pedidos de demo incluidos).
"""
import json
import random
import sys
from datetime import datetime, timedelta

from . import images as imgproc
from .db import BASE_DIR, get_db, init_db
from .config import BANNER_SIZE, HERO_MOBILE, HERO_SIZE
from .utils import slugify

SEED_IMG = BASE_DIR / "seed_img"
MEDIA = BASE_DIR / "media"

CATEGORIES = ["Vestidos", "Conjuntos", "Tops & Blusas"]

# (nombre, categoría, precio, precio antes, destacado, fotos, talles, colores, descripción)
CATALOG = [
    ("Vestido Aurora", "Vestidos", 89000, None, 1, ["p01", "p06"], [("S", 2), ("M", 3), ("L", 1)], [("Lavanda", "#b9a7d4")],
     "Vestido largo de gasa con breteles finos y cintura marcada. Forrado hasta la rodilla."),
    ("Vestido Girasol", "Vestidos", 82000, 98000, 1, ["p02"], [("S", 1), ("M", 2), ("L", 2)], [("Mostaza", "#e0a526"), ("Rojo", "#b8322a")],
     "Vestido midi con escote en V y mangas cortas. Estampa de lunares chiquitos."),
    ("Vestido Lila", "Vestidos", 76000, None, 1, ["p03"], [("S", 2), ("M", 2)], [("Fucsia", "#c2458f")],
     "Vestido camisero largo con botones al frente y cinto del mismo género."),
    ("Vestido Marea", "Vestidos", 94000, None, 1, ["p06", "p07"], [("S", 1), ("M", 1), ("L", 1)], [],
     "Vestido de viscosa estampado, escote cruzado y volados en el ruedo."),
    ("Vestido Ámbar", "Vestidos", 71000, 88000, 0, ["p05", "p16"], [("S", 0), ("M", 0), ("L", 0)], [("Amarillo", "#e8c43a")],
     "Vestido largo con espalda descubierta y tiras cruzadas. Tela liviana ideal para el verano."),
    ("Vestido Rosa Antigua", "Vestidos", 86000, None, 1, ["p08"], [("S", 2), ("M", 3), ("L", 2)], [("Rosa", "#e7a9b4")],
     "Vestido midi con volados, breteles regulables y estampa floral."),
    ("Vestido Sol", "Vestidos", 69000, None, 0, ["p09"], [("S", 1), ("M", 2)], [],
     "Vestido corto con hombros descubiertos y elástico en la cintura."),
    ("Vestido Tulum", "Vestidos", 92000, None, 1, ["p10"], [("S", 2), ("M", 1), ("L", 1)], [],
     "Vestido camisero con estampa geométrica y lazo en la cintura."),
    ("Conjunto Coral", "Conjuntos", 99000, None, 1, ["p11"], [("S", 1), ("M", 2), ("L", 1)], [],
     "Conjunto de top y falda larga con tajo. Se venden juntos."),
    ("Vestido Carmín", "Vestidos", 105000, None, 0, ["p12"], [("S", 1), ("M", 1)], [("Rojo", "#b3122a")],
     "Vestido largo de lino con escote cuadrado y breteles anchos."),
    ("Mono Duna", "Conjuntos", 64000, 79000, 0, ["p13"], [("S", 2), ("M", 2), ("L", 1)], [("Crudo", "#efe8d8")],
     "Mono corto de lino con botones y bolsillos al frente."),
    ("Vestido Brisa", "Vestidos", 78000, None, 0, ["p14", "p19"], [("S", 2), ("M", 2), ("L", 2)], [("Blanco", "#ffffff")],
     "Vestido de algodón blanco con espalda cruzada y ruedo con puntilla."),
    ("Vestido Luna", "Vestidos", 88000, None, 0, ["p15"], [("M", 1), ("L", 2)], [],
     "Vestido asimétrico de bambula con volado en el ruedo."),
    ("Top Palmera", "Tops & Blusas", 42000, None, 0, ["p20"], [("S", 3), ("M", 3), ("L", 2)], [("Negro", "#1d1d1d")],
     "Musculosa larga estampada con breteles finos."),
    ("Blusa Nube", "Tops & Blusas", 48000, None, 0, ["p18"], [("S", 2), ("M", 2)], [("Celeste", "#b7cfe4")],
     "Blusa de fibrana amplia, mangas cortas y botones de nácar."),
    ("Top Tiki", "Tops & Blusas", 39000, None, 0, ["p17"], [("S", 2), ("M", 1)], [],
     "Top halter con estampa, se ata en el cuello."),
]

HERO = [("l01", "A CORAZÓN ABIERTO", "PREVIEW PRIMAVERA ’27", "VER COLECCIÓN", "/productos"),
        ("l04", "LA TEMPORADA DEL SOL", "NUEVOS INGRESOS", "COMPRAR AHORA", "/productos"),
        ("l06", "HECHO PARA ELLAS", "BY MARÍA INÉS", "VER TODO", "/productos")]
BANNERS = [("p04", "VESTIDOS", "COMPRAR AHORA", "/c/vestidos"),
           ("p13", "CONJUNTOS", "COMPRAR AHORA", "/c/conjuntos")]


def seed_catalog() -> None:
    init_db()
    with get_db() as con:
        for pos, name in enumerate(CATEGORIES):
            if not con.execute("SELECT 1 FROM categories WHERE name = ?", (name,)).fetchone():
                con.execute("INSERT INTO categories(name, slug, position) VALUES (?,?,?)", (name, slugify(name), pos))
        for order, (name, cat, price, before, feat, photos, sizes, colors, desc) in enumerate(CATALOG):
            slug = slugify(name)
            if con.execute("SELECT 1 FROM products WHERE slug = ?", (slug,)).fetchone():
                continue
            cur = con.execute(
                "INSERT INTO products(slug, name, description, category, price, compare_price, featured, sort_order) VALUES (?,?,?,?,?,?,?,?)",
                (slug, name, desc, cat, price, before, feat, order))
            pid = cur.lastrowid
            for i, (size, stock) in enumerate(sizes):
                con.execute("INSERT INTO product_sizes(product_id, size, stock, position) VALUES (?,?,?,?)", (pid, size, stock, i))
            for i, (cname, hexv) in enumerate(colors):
                con.execute("INSERT INTO product_colors(product_id, name, hex, position) VALUES (?,?,?,?)", (pid, cname, hexv, i))
            for i, ph in enumerate(photos):
                data = (SEED_IMG / f"{ph}.jpg").read_bytes()
                info = imgproc.process_upload(data, f"{ph}.jpg", MEDIA / "products" / str(pid), MEDIA / "originals", 1200, 1600, "cover")
                con.execute("INSERT INTO product_images(product_id, filename, thumb, original, width, height, position) VALUES (?,?,?,?,?,?,?)",
                            (pid, info["filename"], info["thumb"], info["original"], 1200, 1600, i))
            print("prenda:", name)
        if not con.execute("SELECT 1 FROM slides").fetchone():
            for pos, (ph, title, sub, btn, link) in enumerate(HERO):
                info = imgproc.process_slide((SEED_IMG / f"{ph}.jpg").read_bytes(), f"{ph}.jpg", MEDIA / "slides", MEDIA / "originals", HERO_SIZE, HERO_MOBILE)
                con.execute("INSERT INTO slides(kind, filename, mobile, original, title, subtitle, button, link, position) VALUES ('hero',?,?,?,?,?,?,?,?)",
                            (info["filename"], info["mobile"], info["original"], title, sub, btn, link, pos))
            for pos, (ph, title, btn, link) in enumerate(BANNERS):
                info = imgproc.process_slide((SEED_IMG / f"{ph}.jpg").read_bytes(), f"{ph}.jpg", MEDIA / "slides", MEDIA / "originals", BANNER_SIZE)
                con.execute("INSERT INTO slides(kind, filename, original, title, button, link, position) VALUES ('banner',?,?,?,?,?,?)",
                            (info["filename"], info["original"], title, btn, link, pos))
            print("portada lista")


def seed_demo_metrics(n: int = 140) -> None:
    """Tráfico inventado de los últimos 30 días para ver el panel con datos."""
    rnd = random.Random(7)
    with get_db() as con:
        if con.execute("SELECT 1 FROM visitors WHERE session_id LIKE 'demo-%'").fetchone():
            print("ya había métricas de demo")
            return
        prods = [dict(r) for r in con.execute("SELECT id, name, price FROM products WHERE active = 1")]
        sizes = {}
        for r in con.execute("SELECT product_id, size FROM product_sizes WHERE stock > 0"):
            sizes.setdefault(r["product_id"], []).append(r["size"])
        sources = ["Instagram"] * 9 + ["WhatsApp"] * 4 + ["Directo"] * 3 + ["Facebook"] * 2 + ["Google"]
        names = ["Carla Méndez", "Sofía Ruiz", "Lucía Gómez", "Valentina Paz", "Julieta Ríos", "Micaela Sosa", "Florencia Díaz", "Agustina Vera"]
        now = datetime.now()
        fmt = lambda d: d.strftime("%Y-%m-%d %H:%M:%S")
        for i in range(n):
            sid = f"demo-{i:04d}-{rnd.randrange(1 << 30):x}"
            start = now - timedelta(days=rnd.random() ** 1.3 * 29, hours=rnd.randrange(0, 12), minutes=rnd.randrange(60))
            t = start
            src, dev = rnd.choice(sources), rnd.choice(["Celular"] * 4 + ["Compu"])
            con.execute("INSERT INTO visitors(session_id, first_seen, last_seen, source, device, landing) VALUES (?,?,?,?,?,?)",
                        (sid, fmt(start), fmt(start), src, dev, "/"))
            ev = lambda typ, pid=None, size=None, meta=None: con.execute(
                "INSERT INTO events(type, product_id, size, session_id, meta, created_at) VALUES (?,?,?,?,?,?)",
                (typ, pid, size, sid, json.dumps(meta or {}), fmt(t)))
            ev("visit")
            ev("page", meta={"path": "/", "title": "Inicio"})
            if rnd.random() < 0.72:
                viewed = rnd.sample(prods, rnd.randint(1, 4))
                for p in viewed:
                    t += timedelta(seconds=rnd.randint(15, 140))
                    ev("view_product", p["id"])
                if rnd.random() < 0.36:
                    p = rnd.choice(viewed)
                    sz = rnd.choice(sizes.get(p["id"], [None]))
                    t += timedelta(seconds=rnd.randint(10, 90))
                    ev("add_to_cart", p["id"], sz)
                    items = [{"product_id": p["id"], "name": p["name"], "size": sz, "color": None, "qty": 1, "price": p["price"]}]
                    con.execute("INSERT INTO carts(session_id, items, units, total, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                                (sid, json.dumps(items, ensure_ascii=False), 1, p["price"], fmt(t), fmt(t)))
                    if rnd.random() < 0.55:
                        t += timedelta(seconds=rnd.randint(20, 120))
                        ev("begin_checkout")
                        if rnd.random() < 0.6:
                            t += timedelta(seconds=rnd.randint(40, 200))
                            total = round(p["price"] * 0.9)
                            status = rnd.choice(["pendiente", "confirmado", "entregado", "entregado"])
                            cur = con.execute(
                                "INSERT INTO orders(code, customer_name, customer_phone, payment, status, subtotal, total, session_id, created_at, updated_at) "
                                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (sid, rnd.choice(names) + " (demo)", "11 5555 0000", "transferencia", status, p["price"], total, sid, fmt(t), fmt(t)))
                            oid = cur.lastrowid
                            code = f"LQ-{oid:04d}"
                            con.execute("UPDATE orders SET code = ? WHERE id = ?", (code, oid))
                            con.execute("INSERT INTO order_items(order_id, product_id, product_name, size, qty, unit_price, list_price) VALUES (?,?,?,?,?,?,?)",
                                        (oid, p["id"], p["name"], sz, 1, total, p["price"]))
                            con.execute("UPDATE carts SET order_id = ? WHERE session_id = ?", (oid, sid))
                            ev("order", meta={"code": code, "total": total})
            con.execute("UPDATE visitors SET last_seen = ? WHERE session_id = ?", (fmt(t), sid))
    print(f"{n} visitas de demo cargadas")


if __name__ == "__main__":
    seed_catalog()
    if "--demo-metrics" in sys.argv:
        seed_demo_metrics()
