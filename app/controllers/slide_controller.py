"""Portada: slider, cuadros de categoría y logo (panel)."""
from fastapi import APIRouter, Depends, File, Form, UploadFile

from ..deps import read_upload, require_admin
from ..schemas import IdsIn, SlideIn
from ..services.slide_services import SlideServices

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
service = SlideServices()


@router.get("/slides")
def get_all():
    return service.get_all()


@router.post("/slides")
async def add(kind: str = Form("hero"), file: UploadFile = File(...)):
    return service.add(kind, *(await read_upload(file)))


@router.put("/slides/{kind}/reorder")
def reorder(kind: str, body: IdsIn):
    service.reorder(kind, body.ids)
    return {"ok": True}


@router.put("/slides/{sid}")
def update(sid: int, body: SlideIn):
    service.update(sid, body)
    return {"ok": True}


@router.delete("/slides/{sid}")
def delete(sid: int):
    service.delete(sid)
    return {"ok": True}


@router.post("/logo")
async def set_logo(file: UploadFile = File(...)):
    return {"ok": True, "logo_url": service.set_logo(*(await read_upload(file)))}


@router.delete("/logo")
def delete_logo():
    service.delete_logo()
    return {"ok": True}
