"""Tienda pública: catálogo y páginas HTML."""
from fastapi import APIRouter, Response
from fastapi.responses import FileResponse, RedirectResponse

from ..config import ASSET_VERSION
from ..services.store_services import StoreServices

router = APIRouter()
service = StoreServices()


def _html(body: str) -> Response:
    return Response(body, media_type="text/html; charset=utf-8")


@router.get("/api/store")
def store():
    return service.catalog()


@router.get("/")
def home():
    return _html(service.render_page(ASSET_VERSION))


@router.get("/productos")
def products_page():
    return _html(service.render_page(ASSET_VERSION, "Productos"))


@router.get("/c/{slug}")
def category_page(slug: str):
    return _html(service.render_page(ASSET_VERSION))


@router.get("/buscar")
def search_page():
    return _html(service.render_page(ASSET_VERSION, "Buscar"))


@router.get("/p/{slug}")
def product_page(slug: str):
    meta = service.product_meta(slug)
    return _html(service.render_page(ASSET_VERSION, *meta) if meta else service.render_page(ASSET_VERSION))


@router.get("/favicon")
@router.get("/favicon.ico")
def favicon():
    path, media_type = service.favicon()
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-cache"})


@router.get("/admin")
def admin_page():
    return _html(service.render_admin(ASSET_VERSION))


@router.get("/admin/")
def admin_slash():
    return RedirectResponse("/admin")
