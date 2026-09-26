"""Categorías (panel)."""
from fastapi import APIRouter, Depends

from ..deps import require_admin
from ..schemas import CategoriesIn
from ..services.category_services import CategoryServices

router = APIRouter(prefix="/api/admin/categories", dependencies=[Depends(require_admin)])
service = CategoryServices()


@router.get("")
def get_all():
    return service.get_all()


@router.put("")
def save_all(body: CategoriesIn):
    return service.save_all(body.categories)
