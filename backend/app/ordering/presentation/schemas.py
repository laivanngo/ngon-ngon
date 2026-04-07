"""
Ordering Context — Presentation Schemas
==========================================
Pydantic models cho HTTP request/response.

ĐÂY LÀ CÁC SCHEMAS TỪ schemas.py LIÊN QUAN ĐẾN ORDERING.
Giữ nguyên validation logic (phone regex, XSS sanitize, etc.)
nhưng scoped vào ordering context.

schemas.py gốc vẫn tồn tại (dùng bởi admin.py, kds.py chưa migrate).
Khi tất cả contexts migrate xong → xóa schemas.py gốc.
"""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ordering.domain.entities import Order, OrderItem


# =============================================================================
# Sanitize helper — import from shared kernel
# =============================================================================
from app.shared.utils import sanitize_string as _sanitize
from app.shared.utils import clean_phone as _clean_phone
from app.shared.constants import VN_PHONE_REGEX as _VN_PHONE_REGEX


class OrderItemCreate(BaseModel):
    """Một món trong giỏ hàng khi đặt."""

    product_id: int
    size: str | None = None
    sweetness: str | None = None
    ice_level: str | None = None
    quantity: int = Field(ge=1, le=99, description="Số lượng từ 1-99")
    toppings: list[str] = Field(default=[], description="Danh sách topping legacy_id")
    note: str | None = Field(default=None, max_length=500)


class OrderCreate(BaseModel):
    """Request body khi khách đặt hàng."""

    customer_name: str = Field(
        min_length=1,
        max_length=100,
        description="Tên người nhận",
        examples=["Anh Minh"],
    )
    phone: str = Field(
        min_length=10,
        max_length=15,
        description="Số điện thoại VN (chấp nhận dấu chấm, khoảng trắng)",
        examples=["0378148148", "0378.148.148"],
    )
    address: str = Field(
        min_length=1,
        max_length=500,
        description="Địa chỉ giao hàng",
        examples=["Cty Pouchen - Cổng B"],
    )
    note: str | None = Field(default=None, max_length=1000)
    delivery_type: str = Field(
        default="immediate",
        description="immediate = giao liền, scheduled = hẹn giờ giao",
    )
    scheduled_time: str | None = Field(
        default=None,
        max_length=10,
        description="Giờ hẹn giao, VD: 12:00 (chỉ khi delivery_type=scheduled)",
    )
    items: list[OrderItemCreate] = Field(min_length=1, description="Ít nhất 1 món")

    @field_validator("delivery_type")
    @classmethod
    def validate_delivery_type(cls, v: str) -> str:
        if v not in ("immediate", "scheduled"):
            raise ValueError("delivery_type phải là 'immediate' hoặc 'scheduled'")
        return v

    @field_validator("scheduled_time")
    @classmethod
    def validate_scheduled_time(cls, v: str | None) -> str | None:
        if not v:
            return v
        clean = v.strip()
        if not re.match(r"^\d{1,2}:\d{2}$", clean):
            raise ValueError("Giờ hẹn giao phải theo format HH:MM, VD: 12:00")
        return clean

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean = _clean_phone(v)
        if not _VN_PHONE_REGEX.match(clean):
            raise ValueError("Số điện thoại không hợp lệ. VD: 0378148148")
        return clean

    @field_validator("customer_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Tên không được để trống")
        return _sanitize(stripped)

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Địa chỉ không được để trống")
        return _sanitize(stripped)

    @field_validator("note")
    @classmethod
    def validate_note(cls, v: str | None) -> str | None:
        return _sanitize(v) if v else v


class OrderStatusUpdate(BaseModel):
    status: str = Field(description="pending|confirmed|preparing|delivering|done|cancelled")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"pending", "confirmed", "preparing", "delivering", "done", "cancelled"}
        if v not in valid:
            raise ValueError(f"Status phải là một trong: {', '.join(valid)}")
        return v


# =============================================================================
# Response Schemas
# =============================================================================
class OrderItemResponse(BaseModel):
    product_name: str
    size: str | None
    sweetness: str | None
    ice_level: str | None
    quantity: int
    unit_price: int
    toppings_text: str | None
    note: str | None

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    public_id: str
    customer_name: str
    phone: str
    address: str
    note: str | None
    subtotal: int
    discount: int
    total: int
    status: str
    delivery_type: str = "immediate"
    scheduled_time: str | None = None
    items: list[OrderItemResponse]
    created_at: datetime
    estimated_minutes: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, order: Order) -> "OrderResponse":
        """
        Convert domain Order → HTTP response.
        Dùng thay cho model_validate(orm_object).
        """
        return cls(
            public_id=order.public_id,
            customer_name=order.customer_name,
            phone=order.phone,
            address=order.address,
            note=order.note,
            subtotal=order.subtotal,
            discount=order.discount,
            total=order.total,
            status=order.status.value if hasattr(order.status, "value") else order.status,
            delivery_type=order.delivery_type,
            scheduled_time=order.scheduled_time,
            items=[
                OrderItemResponse(
                    product_name=item.product_name,
                    size=item.size,
                    sweetness=item.sweetness,
                    ice_level=item.ice_level,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    toppings_text=item.toppings_text,
                    note=item.note,
                )
                for item in order.items
            ],
            created_at=order.created_at,
            estimated_minutes=order.estimated_minutes,
        )
