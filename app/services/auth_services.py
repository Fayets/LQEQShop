"""Acceso al panel con PIN. El hash, las sesiones y el límite de intentos viven en security.py."""
from __future__ import annotations

from fastapi import HTTPException

from .. import security as sec
from ..db import get_db, get_settings, set_setting


class AuthServices:

    def login(self, pin: str, ip: str, user_agent: str) -> tuple[str, bool]:
        """Devuelve (token de sesión, hay que cambiar el PIN provisorio)."""
        # El intento fallido se confirma en su propia transacción: si fuera en la misma que
        # termina en HTTPException, el rollback lo borraría y el bloqueo nunca subiría.
        with get_db() as con:
            locked = sec.login_locked_for(con, ip)
        if locked:
            raise HTTPException(429, f"Demasiados intentos fallidos. Probá de nuevo en {locked // 60 + 1} min.")
        with get_db() as con:
            s = get_settings(con)
            ok = sec.verify_pin(pin.strip(), s.get("admin_pin_hash", ""))
            sec.record_login(con, ip, ok)
            token = sec.issue_session(con, ip, user_agent) if ok else ""
        if not ok:
            raise HTTPException(401, "PIN incorrecto")
        return token, s.get("pin_is_default", "0") == "1"

    def logout(self, token: str) -> None:
        with get_db() as con:
            sec.revoke_session(con, token)

    def is_valid(self, token: str) -> bool:
        with get_db() as con:
            return sec.session_valid(con, token)

    def must_change_pin(self) -> bool:
        with get_db() as con:
            return get_settings(con).get("pin_is_default", "0") == "1"

    def change_pin(self, current: str, new: str, ip: str, user_agent: str) -> str:
        """Cambiar el PIN cierra todas las sesiones y deja viva solo una nueva, la de acá."""
        new = new.strip()
        problem = sec.pin_problem(new)
        if problem:
            raise HTTPException(400, problem)
        with get_db() as con:
            s = get_settings(con)
            if s.get("pin_is_default", "0") != "1" and not sec.verify_pin(current.strip(), s.get("admin_pin_hash", "")):
                raise HTTPException(401, "El PIN actual no es correcto.")
            set_setting(con, "admin_pin_hash", sec.hash_pin(new))
            set_setting(con, "pin_is_default", "0")
            sec.revoke_all_sessions(con)
            return sec.issue_session(con, ip, user_agent)
