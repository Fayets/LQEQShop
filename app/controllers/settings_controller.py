"""Ajustes de la tienda (panel)."""
from fastapi import APIRouter, Depends

from ..deps import require_admin
from ..services.settings_services import SettingsServices

router = APIRouter(prefix="/api/admin/settings", dependencies=[Depends(require_admin)])
service = SettingsServices()


@router.get("")
def get():
    return service.get_editable()


@router.put("")
def update(body: dict):
    service.update(body)
    return {"ok": True}
