"""
Catalog Context — Presentation Schemas
=========================================
Pydantic models cho HTTP request/response của Catalog context.

TRƯỚC: Re-export từ app.schemas (God-Schema dùng chung 3 context).
SAU:   Catalog sở hữu hoàn toàn response schemas của mình.

NGUYÊN TẮC:
- Mọi thay đổi schema Catalog chỉ cần sửa file này.
- app/schemas.py không còn được import từ đây nữa.
- API contract giữ nguyên 100% — frontend không cần thay đổi.
"""

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Primitive building blocks
# =============================================================================

class ProductSizeResponse(BaseModel):
    """Một size của sản phẩm (M / L / XL) kèm giá."""
    label: str   # "M", "L", "XL"
    price: int   # Giá cho size này (VNĐ)

    model_config = ConfigDict(from_attributes=True)


class ToppingResponse(BaseModel):
    id: int
    legacy_id: str
    name: str
    emoji: str
    price: int

    model_config = ConfigDict(from_attributes=True)


class TimeDealResponse(BaseModel):
    label: str
    title: str
    subtitle: str
    start_hour: int
    end_hour: int
    discount_percent: int

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Product & Category response
# =============================================================================

class ProductResponse(BaseModel):
    id: int
    legacy_id: str
    name: str
    description: str | None = None
    base_price: int
    emoji: str
    image_path: str | None = None
    badge: str | None = None
    bg_class: str = "x"
    sold_count: int = 0
    is_drink: bool = True
    is_combo: bool = False
    combo_description: str | None = None
    original_price: int | None = None
    save_amount: int | None = None
    sizes: list[ProductSizeResponse] = []
    topping_ids: list[int] = []

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        """
        Extract topping_ids từ ORM relationship khi convert từ ORM object.
        Relationship phải được eager-load trước khi gọi method này.
        """
        if hasattr(obj, "__dict__") and hasattr(obj, "product_toppings"):
            try:
                if obj.product_toppings is not None:
                    obj.__dict__["topping_ids"] = [
                        pt.topping_id for pt in obj.product_toppings
                    ]
            except Exception:
                # Relationship chưa eager-load (async MissingGreenlet) — bỏ qua
                pass
        return super().model_validate(obj, *args, **kwargs)


class CategoryResponse(BaseModel):
    id: int
    slug: str
    name: str
    emoji: str
    layout: str
    products: list[ProductResponse] = []

    model_config = ConfigDict(from_attributes=True)


class MenuResponse(BaseModel):
    """Toàn bộ menu — trả về cho frontend render."""
    categories: list[CategoryResponse]


# =============================================================================
# Admin command schemas — Product CRUD
# =============================================================================

class ProductCreateRequest(BaseModel):
    legacy_id: str = Field(min_length=1, max_length=20)
    category_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    base_price: int = Field(ge=1, description="Giá phải > 0")
    emoji: str = "🍽"
    badge: str | None = None
    bg_class: str = "x"
    is_drink: bool = True
    is_combo: bool = False
    combo_description: str | None = None
    original_price: int | None = None
    save_amount: int | None = None
    sizes: list[ProductSizeResponse] = []
    topping_ids: list[int] = []


class ProductUpdateRequest(BaseModel):
    """Partial update — chỉ gửi field cần sửa."""
    name: str | None = None
    description: str | None = None
    base_price: int | None = Field(default=None, ge=1)
    emoji: str | None = None
    image_path: str | None = None
    badge: str | None = None
    bg_class: str | None = None
    is_active: bool | None = None
    is_drink: bool | None = None
    is_combo: bool | None = None
    combo_description: str | None = None
    original_price: int | None = None
    save_amount: int | None = None
    sort_order: int | None = None
    category_id: int | None = None
    sizes: list[ProductSizeResponse] | None = None     # Gửi = replace toàn bộ sizes
    topping_ids: list[int] | None = None               # Gửi = replace toàn bộ toppings


# =============================================================================
# Re-export list
# =============================================================================
__all__ = [
    "CategoryResponse",
    "MenuResponse",
    "ProductResponse",
    "ProductSizeResponse",
    "TimeDealResponse",
    "ToppingResponse",
    "ProductCreateRequest",
    "ProductUpdateRequest",
]
