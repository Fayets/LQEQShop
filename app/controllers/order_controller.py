"""Pedidos: alta desde la tienda y gestión desde el panel."""
from typing import Optional

from fastapi import APIRouter, Depends, Request

from .. import security as sec
from ..deps import client, require_admin
from ..schemas import OrderIn, OrderNoteIn, StatusIn
from ..services.order_services import OrderServices

router = APIRouter()
service = OrderServices()


@router.post("/api/orders")
def create(body: OrderIn, request: Request):
    sec.rate_limit(request, "orders", limit=8, seconds=3600)
    _ip, host, ua = client(request)
    return service.create(body, host, ua)


@router.get("/api/admin/orders")
def get_all(status: Optional[str] = None, _: bool = Depends(require_admin)):
    return service.get_all(status)


@router.put("/api/admin/orders/{oid}/status")
def set_status(oid: int, body: StatusIn, _: bool = Depends(require_admin)):
    service.set_status(oid, body.status)
    return {"ok": True}


@router.put("/api/admin/orders/{oid}")
def set_note(oid: int, body: OrderNoteIn, _: bool = Depends(require_admin)):
    service.set_note(oid, body.admin_note)
    return {"ok": True}
