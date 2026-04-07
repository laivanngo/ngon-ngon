"""
Ordering Context — Domain Services & Repository ABCs
======================================================
Abstract interfaces mà domain cần — implementation ở infrastructure layer.

WHY ABC (Abstract Base Class):
- Domain KHÔNG biết DB là gì (SQLAlchemy, MongoDB, in-memory)
- Domain KHÔNG biết pricing lấy data từ đâu
- Test domain logic bằng mock implementation → nhanh, không cần DB
- Đổi infrastructure (VD: PostgreSQL → DynamoDB) chỉ sửa implementation, domain nguyên vẹn

DEPENDENCY RULE (Clean Architecture):
    Domain ← Application ← Infrastructure ← Presentation
    Mũi tên = "phụ thuộc vào"
    Domain KHÔNG import từ bất kỳ layer nào khác
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ordering.domain.entities import Order


# =============================================================================
# DTOs — Data đi vào/ra PricingService
# =============================================================================
@dataclass
class CartItem:
    """
    Input cho PricingService: 1 món trong giỏ hàng từ client.
    Chưa có giá — PricingService sẽ tính.
    """

    product_id: int
    size: str | None = None
    sweetness: str | None = None
    ice_level: str | None = None
    quantity: int = 1
    toppings: list[str] | None = None   # legacy_id list (VD: ["tp1", "tp3"])
    note: str | None = None


@dataclass
class PricedLineItem:
    """
    Output từ PricingService: 1 món đã tính giá.
    Bao gồm snapshot data (product_name, toppings_text) để lưu vào OrderItem.
    """

    product_id: int
    product_name: str       # Snapshot tên tại thời điểm đặt
    size: str | None
    sweetness: str | None
    ice_level: str | None
    quantity: int
    unit_price: int         # Đã bao gồm size upgrade + topping
    toppings_text: str | None
    note: str | None


@dataclass
class PricedCart:
    """Kết quả tính giá toàn bộ giỏ hàng."""

    items: list[PricedLineItem]
    subtotal: int           # Tổng trước giảm giá
    discount: int           # Giảm giá (TimeDeal, Flash Sale, etc.)
    total: int              # Tổng sau giảm giá
    discount_source: str = "none"   # "time_deal", "flash_sale", "none"
    discount_label: str = ""        # "Flash Sale -50%!" hoặc "Deal Buổi Trưa -20%"


# =============================================================================
# PricingService ABC — Domain không biết giá lấy từ đâu
# =============================================================================
class PricingService(ABC):
    """
    Tính giá cho giỏ hàng.

    TRƯỚC: 80 dòng tính giá nằm TRONG router endpoint (orders.py:48-120).
    SAU: Logic tách riêng, router chỉ gọi 1 method.

    Implementation (ở infrastructure) sẽ:
    1. Lookup product từ DB → lấy base_price
    2. Check size → adjust price
    3. Lookup toppings → cộng thêm
    4. Check TimeDeal → tính discount
    """

    @abstractmethod
    async def price_cart(self, items: list[CartItem]) -> PricedCart:
        """Tính giá toàn bộ giỏ hàng."""
        ...


# =============================================================================
# OrderRepository ABC — Domain không biết persist ở đâu
# =============================================================================
class OrderRepository(ABC):
    """
    Interface cho persistence layer.

    WHY repository pattern:
    - Domain gọi repo.save(order) — không biết SQLAlchemy, db.add(), db.commit()
    - Test dùng InMemoryOrderRepository → không cần PostgreSQL
    """

    @abstractmethod
    async def save(self, order: "Order") -> "Order":
        """
        Persist order mới hoặc cập nhật order hiện có.
        Return order với id đã được DB generate.
        """
        ...

    @abstractmethod
    async def find_by_public_id(self, public_id: str) -> "Order | None":
        """Tìm order bằng public UUID."""
        ...

    @abstractmethod
    async def count_active(self) -> int:
        """
        Đếm đơn đang active (pending/confirmed/preparing).
        Dùng để estimate thời gian giao hàng.
        """
        ...

    @abstractmethod
    async def list_orders(
        self,
        status_filter: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list["Order"], int]:
        """
        Danh sách đơn hàng (mới nhất trước) + total count.
        Return: (orders, total_count)
        Dùng cho admin panel pagination.
        """
        ...

    @abstractmethod
    async def count_by_status(self, status: str) -> int:
        """Đếm đơn theo trạng thái cụ thể."""
        ...
