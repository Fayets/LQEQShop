"""Cuerpos de los requests (Pydantic). Los controladores los reciben y se los pasan a los servicios."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .config import SID_RE


# ---- auth
class LoginIn(BaseModel):
    pin: str = Field(max_length=100)


class NewPinIn(BaseModel):
    current_pin: str = Field(default="", max_length=100)
    new_pin: str = Field(max_length=100)


# ---- tienda pública
class EventIn(BaseModel):
    type: str = Field(pattern=r"^[a-z_]{2,40}$")
    session_id: str = Field(pattern=SID_RE)
    product_id: Optional[int] = None
    size: Optional[str] = Field(default=None, max_length=20)
    meta: Optional[dict] = None


class CartItemIn(BaseModel):
    product_id: int
    size: Optional[str] = Field(default=None, max_length=20)
    color: Optional[str] = Field(default=None, max_length=40)
    qty: int = Field(ge=1, le=20)


class CartIn(BaseModel):
    session_id: str = Field(pattern=SID_RE)
    items: list[CartItemIn] = Field(default=[], max_length=30)


class NewsletterIn(BaseModel):
    email: str = Field(max_length=120)
    name: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=40)
    session_id: Optional[str] = Field(default=None, max_length=64)


class OrderIn(BaseModel):
    items: list[CartItemIn] = Field(max_length=30)
    customer_name: str = Field(min_length=2, max_length=80)
    customer_phone: str = Field(min_length=6, max_length=40)
    delivery: str = "retiro"
    city: str = Field(default="", max_length=80)
    address: str = Field(default="", max_length=160)
    note: str = Field(default="", max_length=500)
    payment: str = "transferencia"
    session_id: Optional[str] = Field(default=None, pattern=SID_RE)


# ---- productos
class SizeIn(BaseModel):
    size: str = Field(max_length=20)
    stock: int = Field(ge=0, le=9999)


class ColorIn(BaseModel):
    name: str = Field(max_length=40)
    hex: str = Field(default="#000000", pattern=r"^#[0-9a-fA-F]{6}$")


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    category: str = Field(default="", max_length=60)
    price: float = Field(ge=0, le=99_999_999)
    compare_price: Optional[float] = Field(default=None, ge=0, le=99_999_999)
    transfer_price: Optional[float] = Field(default=None, ge=0, le=99_999_999)
    featured: bool = False
    active: bool = True
    sizes: list[SizeIn] = Field(default=[], max_length=40)
    colors: list[ColorIn] = Field(default=[], max_length=30)


class IdsIn(BaseModel):
    ids: list[int] = Field(default=[], max_length=2000)


# ---- categorías
class CategoryIn(BaseModel):
    id: Optional[int] = None
    name: str = Field(min_length=1, max_length=60)


class CategoriesIn(BaseModel):
    categories: list[CategoryIn] = Field(default=[], max_length=40)


# ---- portada
class SlideIn(BaseModel):
    title: str = Field(default="", max_length=80)
    subtitle: str = Field(default="", max_length=120)
    button: str = Field(default="", max_length=40)
    link: str = Field(default="", max_length=200)
    active: bool = True


# ---- pedidos
class StatusIn(BaseModel):
    status: str


class OrderNoteIn(BaseModel):
    admin_note: str = Field(default="", max_length=1000)
