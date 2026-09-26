"""Helpers chicos sin dependencias de FastAPI."""
import re
import unicodedata
from typing import Optional


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "producto"


def money(v: float) -> str:
    return "$" + f"{v:,.0f}".replace(",", ".")


def clean(text: Optional[str], n: int) -> str:
    """Colapsa espacios y corta al largo máximo."""
    return " ".join((text or "").split())[:n]
