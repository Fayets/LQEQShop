"""Portada: fotos grandes del slider (kind='hero'), cuadros de categoría (kind='banner') y logo."""
from __future__ import annotations

from fastapi import HTTPException

from .. import images as imgproc
from ..config import BANNER_SIZE, BRAND_MEDIA, HERO_MOBILE, HERO_SIZE, ORIGINALS_DIR, SLIDES_MEDIA
from ..db import get_db, get_settings, rows, set_setting
from ..schemas import SlideIn


class SlideServices:

    def load(self, con, kind: str, only_active: bool = True) -> list[dict]:
        q = "SELECT * FROM slides WHERE kind = ?" + (" AND active = 1" if only_active else "") + " ORDER BY position, id"
        out = rows(con.execute(q, (kind,)))
        for s in out:
            s["url"] = f"/media/slides/{s['filename']}"
            s["mobile_url"] = f"/media/slides/{s['mobile']}" if s.get("mobile") else s["url"]
        return out

    def get_all(self) -> dict:
        with get_db() as con:
            return {"hero": self.load(con, "hero", False), "banner": self.load(con, "banner", False)}

    def add(self, kind: str, filename: str, data: bytes) -> list[dict]:
        """El slider guarda dos recortes (compu apaisado, celular vertical); el cuadro de
        categoría, uno solo vertical."""
        kind = "banner" if kind == "banner" else "hero"
        try:
            info = imgproc.process_slide(data, filename, SLIDES_MEDIA, ORIGINALS_DIR,
                                         HERO_SIZE if kind == "hero" else BANNER_SIZE, HERO_MOBILE if kind == "hero" else None)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception:
            raise HTTPException(400, "No se pudo leer la imagen")
        with get_db() as con:
            pos = con.execute("SELECT COALESCE(MAX(position),-1) FROM slides WHERE kind = ?", (kind,)).fetchone()[0] + 1
            con.execute("INSERT INTO slides(kind, filename, mobile, original, button, position) VALUES (?,?,?,?,?,?)",
                        (kind, info["filename"], info["mobile"], info["original"], "VER COLECCIÓN" if kind == "hero" else "COMPRAR AHORA", pos))
            return self.load(con, kind, False)

    def update(self, sid: int, body: SlideIn) -> None:
        link = body.link.strip()
        if link and not (link.startswith("/") or link.startswith("https://")):
            raise HTTPException(400, "El link tiene que empezar con / (una página de la tienda) o con https://")
        with get_db() as con:
            con.execute("UPDATE slides SET title=?, subtitle=?, button=?, link=?, active=? WHERE id=?",
                        (body.title.strip(), body.subtitle.strip(), body.button.strip(), link, int(body.active), sid))

    def reorder(self, kind: str, ids: list[int]) -> None:
        with get_db() as con:
            for pos, sid in enumerate(ids[:50]):
                con.execute("UPDATE slides SET position = ? WHERE id = ? AND kind = ?", (pos, sid, kind))

    def delete(self, sid: int) -> None:
        with get_db() as con:
            row = con.execute("SELECT * FROM slides WHERE id = ?", (sid,)).fetchone()
            if not row:
                raise HTTPException(404, "La foto no existe")
            for name in (row["filename"], row["mobile"]):
                if name:
                    (SLIDES_MEDIA / name).unlink(missing_ok=True)
            con.execute("DELETE FROM slides WHERE id = ?", (sid,))

    # ------------------------------------------------------------ logo
    def set_logo(self, filename: str, data: bytes) -> str:
        try:
            name = imgproc.process_logo(data, filename, BRAND_MEDIA)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception:
            raise HTTPException(400, "No se pudo leer la imagen")
        self._replace_logo(name)
        return f"/media/brand/{name}"

    def delete_logo(self) -> None:
        self._replace_logo("")

    def _replace_logo(self, name: str) -> None:
        with get_db() as con:
            old = get_settings(con).get("logo")
            set_setting(con, "logo", name)
        if old:
            (BRAND_MEDIA / old).unlink(missing_ok=True)
