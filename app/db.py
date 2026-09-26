"""SQLite local: esquema, conexión y helpers."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("LQEQ_DB", DATA_DIR / "lqeq.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  category TEXT DEFAULT '',
  price REAL NOT NULL DEFAULT 0,
  compare_price REAL,              -- precio "antes", tachado. Vacío = sin oferta
  transfer_price REAL,             -- vacío = se aplica el % de descuento de Ajustes
  card_price REAL,                 -- vacío = se aplica el % de recargo por tarjeta de Ajustes
  featured INTEGER NOT NULL DEFAULT 0,  -- aparece en el primer carrusel de la portada
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS product_images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  thumb TEXT NOT NULL,
  original TEXT,
  width INTEGER, height INTEGER,
  position INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS product_colors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  hex TEXT NOT NULL DEFAULT '#000000',
  position INTEGER NOT NULL DEFAULT 0,
  UNIQUE(product_id, name)
);
CREATE TABLE IF NOT EXISTS product_sizes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  size TEXT NOT NULL,
  stock INTEGER NOT NULL DEFAULT 0,
  position INTEGER NOT NULL DEFAULT 0,
  UNIQUE(product_id, size)
);
-- Portada: las fotos grandes del slider (kind='hero') y los dos banners de categoría (kind='banner')
CREATE TABLE IF NOT EXISTS slides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL DEFAULT 'hero',
  filename TEXT NOT NULL,
  mobile TEXT,
  original TEXT,
  title TEXT DEFAULT '',
  subtitle TEXT DEFAULT '',
  button TEXT DEFAULT '',
  link TEXT DEFAULT '',
  position INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1
);
-- Una fila por persona que entró a la tienda (id aleatorio guardado en su navegador)
CREATE TABLE IF NOT EXISTS visitors (
  session_id TEXT PRIMARY KEY,
  first_seen TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  last_seen TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  visits INTEGER NOT NULL DEFAULT 1,
  source TEXT DEFAULT 'directo',
  referrer TEXT DEFAULT '',
  campaign TEXT DEFAULT '',
  landing TEXT DEFAULT '',
  device TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_visitors_last ON visitors(last_seen);
-- El carrito tal como lo dejó cada persona. Si no terminó el pedido, es un carrito abandonado.
CREATE TABLE IF NOT EXISTS carts (
  session_id TEXT PRIMARY KEY,
  items TEXT NOT NULL DEFAULT '[]',
  units INTEGER NOT NULL DEFAULT 0,
  total REAL NOT NULL DEFAULT 0,
  order_id INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  product_id INTEGER,
  size TEXT,
  session_id TEXT,
  meta TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_events_type_date ON events(type, created_at);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  customer_name TEXT DEFAULT '',
  customer_phone TEXT DEFAULT '',
  delivery TEXT NOT NULL DEFAULT 'retiro',
  city TEXT DEFAULT '',
  address TEXT DEFAULT '',
  note TEXT DEFAULT '',
  admin_note TEXT DEFAULT '',
  payment TEXT NOT NULL DEFAULT 'transferencia',
  status TEXT NOT NULL DEFAULT 'pendiente',
  stock_applied INTEGER NOT NULL DEFAULT 0,
  subtotal REAL NOT NULL DEFAULT 0,
  total REAL NOT NULL DEFAULT 0,
  session_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id INTEGER,
  product_name TEXT NOT NULL,
  size TEXT,
  color TEXT,
  qty INTEGER NOT NULL DEFAULT 1,
  unit_price REAL NOT NULL DEFAULT 0,
  list_price REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS stock_moves (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL,
  size TEXT,
  delta INTEGER NOT NULL,
  reason TEXT NOT NULL,
  order_id INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS subscribers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT DEFAULT '',
  phone TEXT DEFAULT '',
  session_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  expires_at TEXT NOT NULL,
  ip TEXT,
  user_agent TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_exp ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS login_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ip TEXT NOT NULL,
  ok INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_login_ip_date ON login_attempts(ip, created_at);
"""

DEFAULT_SETTINGS = {
    "brand_name": "Lo que ellas quieren",
    "brand_tagline": "by María Inés",
    "whatsapp_number": "5491100000000",
    "whatsapp_greeting": "¡Hola! Quiero hacer este pedido:",
    "transfer_discount_pct": "10",
    "installments": "3",
    "banner_text": "🤍 ENVÍOS A TODO EL PAÍS 🤍 | 🤍 10% OFF ABONANDO CON TRANSFERENCIA 🤍 | 🤍 3 CUOTAS SIN INTERÉS 🤍",
    "section_featured_title": "PREVIEW PRIMAVERA",
    "section_new_title": "NEW IN",
    "related_title": "TAMBIÉN TE PUEDE GUSTAR",
    "match_title": "PERFECT MATCH",
    "newsletter_title": "SUSCRIBITE A NUESTRO NEWSLETTER & EMPEZÁ A DISFRUTAR DE LOS BENEFICIOS DE NUESTRA COMUNIDAD",
    "newsletter_popup": "1",
    "info_payment": "Transferencia bancaria (con descuento), efectivo al retirar, o tarjeta de crédito en cuotas. Te pasamos los datos por WhatsApp al confirmar el pedido.",
    "info_shipping": "Enviamos a todo el país por correo. También podés retirar sin cargo coordinando por WhatsApp.",
    "info_store": "Coordinamos la entrega o el retiro por WhatsApp.",
    "address": "",
    "instagram": "",
    "facebook": "",
    "tiktok": "",
    "email": "",
    "color_bg": "#f9f7ef",
    "color_text": "#9b9d3a",
    "color_bar": "#890e0e",
    "color_button": "#705447",
    "color_soft": "#f5f3c4",
    "logo": "",
    "image_mode": "cover",
}


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 8000")
    con.execute("PRAGMA synchronous = NORMAL")
    return con


def init_db() -> None:
    con = connect()
    with con:
        con.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            con.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
        _migrate(con)
        _init_pin(con)
        con.execute("DELETE FROM sessions WHERE expires_at < datetime('now','localtime')")
        con.execute("DELETE FROM login_attempts WHERE created_at < datetime('now','localtime','-1 day')")
    con.close()


def _migrate(con) -> None:
    """Columnas agregadas después de la primera versión (no hay vuelta atrás)."""
    cols = {r["name"] for r in con.execute("PRAGMA table_info(products)")}
    if "card_price" not in cols:
        con.execute("ALTER TABLE products ADD COLUMN card_price REAL")
    # precio único desde el 27-09-2026: los precios por medio de pago cargados a mano
    # dejaron de usarse, se vacían para que no confundan a nadie que mire la base
    con.execute("UPDATE products SET transfer_price = NULL, card_price = NULL WHERE transfer_price IS NOT NULL OR card_price IS NOT NULL")
    con.execute("DELETE FROM settings WHERE key = 'card_surcharge_pct'")


def _init_pin(con) -> None:
    """El PIN inicial sale de LQEQ_ADMIN_PIN. Sin variable, queda '1234' marcado como
    provisorio: el panel obliga a cambiarlo antes de dejar entrar."""
    from .security import hash_pin
    if con.execute("SELECT 1 FROM settings WHERE key = 'admin_pin_hash'").fetchone():
        return
    env_pin = os.environ.get("LQEQ_ADMIN_PIN", "").strip()
    pin = env_pin or "1234"
    con.execute("INSERT INTO settings(key, value) VALUES ('admin_pin_hash', ?)", (hash_pin(pin),))
    con.execute("INSERT INTO settings(key, value) VALUES ('pin_is_default', ?)", ("0" if env_pin else "1",))


@contextmanager
def get_db():
    con = connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def get_categories(con) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT id, name, slug, position FROM categories ORDER BY position, id")]


def get_settings(con) -> dict:
    return {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM settings")}


def set_setting(con, key: str, value: str) -> None:
    con.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]
