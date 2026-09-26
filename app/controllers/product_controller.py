"""CRUD de productos y sus fotos (panel)."""
from fastapi import APIRouter, Depends, File, Form, UploadFile

from ..deps import read_upload, require_admin
from ..schemas import IdsIn, ProductIn
from ..services.product_services import ProductServices

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
service = ProductServices()


@router.get("/products")
def get_all():
    return service.get_all()


@router.post("/products")
def create(body: ProductIn):
    return service.create(body)


# va antes que /products/{pid} para que "reorder" no se tome como un id
@router.put("/products/reorder")
def reorder(body: IdsIn):
    service.reorder(body.ids)
    return {"ok": True}


@router.put("/products/{pid}")
def update(pid: int, body: ProductIn):
    return service.update(pid, body)


@router.post("/products/{pid}/duplicate")
def duplicate(pid: int):
    return service.duplicate(pid)


@router.delete("/products/{pid}")
def delete(pid: int):
    service.delete(pid)
    return {"ok": True}


@router.post("/products/{pid}/images")
async def add_images(pid: int, files: list[UploadFile] = File(...), mode: str = Form("cover")):
    return service.add_images(pid, [await read_upload(f) for f in files[:20]], mode)


@router.put("/products/{pid}/images/reorder")
def reorder_images(pid: int, body: IdsIn):
    service.reorder_images(pid, body.ids)
    return {"ok": True}


@router.delete("/images/{iid}")
def delete_image(iid: int):
    service.delete_image(iid)
    return {"ok": True}


@router.post("/images/{iid}/reprocess")
def reprocess_image(iid: int, mode: str = Form("cover")):
    service.reprocess_image(iid, mode)
    return {"ok": True}
