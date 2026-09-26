"""Lo que manda la tienda mientras alguien navega: eventos, carrito y newsletter."""
from fastapi import APIRouter, Request

from .. import security as sec
from ..deps import client
from ..schemas import CartIn, EventIn, NewsletterIn
from ..services.tracking_services import TrackingServices

router = APIRouter(prefix="/api")
service = TrackingServices()


@router.post("/events")
def event(body: EventIn, request: Request):
    sec.rate_limit(request, "events", limit=150, seconds=60)
    _ip, host, ua = client(request)
    service.record_event(body, host, ua)
    return {"ok": True}


@router.put("/cart")
def cart(body: CartIn, request: Request):
    sec.rate_limit(request, "cart", limit=90, seconds=60)
    _ip, host, ua = client(request)
    service.save_cart(body, host, ua)
    return {"ok": True}


@router.post("/newsletter")
def newsletter(body: NewsletterIn, request: Request):
    sec.rate_limit(request, "news", limit=5, seconds=600)
    _ip, host, ua = client(request)
    service.subscribe(body, host, ua)
    return {"ok": True}
