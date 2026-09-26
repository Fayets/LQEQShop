"""Ajustes de la tienda (textos, contacto, colores)."""
from __future__ import annotations

import re

from fastapi import HTTPException

from ..db import get_db, get_settings, set_setting

PUBLIC_KEYS = ["brand_name", "brand_tagline", "whatsapp_number", "transfer_discount_pct", "card_surcharge_pct", "installments", "banner_text",
               "section_featured_title", "section_new_title", "related_title", "match_title", "newsletter_title",
               "newsletter_popup", "info_payment", "info_shipping", "info_store", "address", "instagram", "facebook",
               "tiktok", "email"]
COLOR_KEYS = ("color_bg", "color_text", "color_bar", "color_button", "color_soft")
EDITABLE_KEYS = PUBLIC_KEYS + ["whatsapp_greeting", "image_mode", *COLOR_KEYS]


def logo_url(s: dict) -> str:
    return f"/media/brand/{s['logo']}" if s.get("logo") else ""


class SettingsServices:

    def public(self, con) -> dict:
        """Lo que puede ver cualquiera: nunca el hash del PIN ni nada interno."""
        s = get_settings(con)
        return {**{k: s.get(k, "") for k in PUBLIC_KEYS}, "logo_url": logo_url(s)}

    def get_editable(self) -> dict:
        with get_db() as con:
            s = get_settings(con)
        return {**{k: s.get(k, "") for k in EDITABLE_KEYS}, "logo_url": logo_url(s)}

    def update(self, values: dict) -> None:
        with get_db() as con:
            for k, v in values.items():
                if k not in EDITABLE_KEYS or v is None:
                    continue
                v = str(v).strip()[:2000]
                if k == "whatsapp_number":
                    v = re.sub(r"\D", "", v)
                if k in COLOR_KEYS and not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                    raise HTTPException(400, "Los colores van en formato #RRGGBB")
                if k in ("instagram", "tiktok", "facebook"):
                    # aceptan @usuario o el link entero: se guarda solo el usuario
                    v = v.lstrip("@").split("?")[0].rstrip("/").split("/")[-1].lstrip("@")
                set_setting(con, k, v)

    def theme_css(self, s: dict) -> str:
        """Los colores de Ajustes pisan las variables CSS de la tienda."""
        parts = [f"--{k.replace('color_', '')}:{s[k]}" for k in COLOR_KEYS if re.fullmatch(r"#[0-9a-fA-F]{6}", s.get(k) or "")]
        return ":root{" + ";".join(parts) + "}"
