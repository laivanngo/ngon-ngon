"""
Ordering Context — Catalog Port
==================================
Interface mà Ordering cần từ Catalog để tính giá giỏ hàng.

DEPENDENCY RULE:
    Domain defines what it needs (port).
    Catalog provides the implementation (adapter).
    Ordering không biết Catalog's ORM, table structure, hay cả tên context.

DTOs:
    PricingProductData  — thông tin 1 sản phẩm cần để tính giá
    PricingSizeData     — thông tin 1 size
    PricingToppingData  — thông tin 1 topping
    ActiveTimeDeal      — time deal đang áp dụng (nếu có)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# =============================================================================
# Data Transfer Objects — plain dataclasses, không có ORM dependency
# =============================================================================

@dataclass
class PricingSizeData:
    """Một size option của sản phẩm."""
    label: str    # "M", "L", "XL"
    price: int    # Giá cho size này (VNĐ)


@dataclass
class PricingToppingData:
    """Thông tin topping cần để tính giá."""
    legacy_id: str
    name: str
    emoji: str
    price: int


@dataclass
class PricingProductData:
    """
    Snapshot thông tin sản phẩm tại thời điểm đặt hàng.
    Đủ để tính giá và lưu lịch sử — không cần query lại Catalog.
    """
    id: int
    name: str
    base_price: int
    is_active: bool
    sizes: list[PricingSizeData] = field(default_factory=list)


@dataclass
class ActiveTimeDeal:
    """Time deal đang active tại thời điểm hiện tại."""
    title: str
    discount_percent: int


# =============================================================================
# CatalogPricingPort — interface Ordering dùng để tính giá
# =============================================================================

class CatalogPricingPort(ABC):
    """
    Port cho phép Ordering query thông tin giá từ Catalog.

    Adapter: catalog/infrastructure/pricing_adapter.SqlCatalogPricingAdapter
    Fake:    ordering/tests/fakes.FakeCatalogPricingPort (cho unit test)
    """

    @abstractmethod
    async def get_product(self, product_id: int) -> PricingProductData | None:
        """
        Lấy thông tin sản phẩm + sizes để tính giá.
        Return None nếu sản phẩm không tồn tại.
        """
        ...

    @abstractmethod
    async def get_toppings_by_legacy_ids(
        self,
        legacy_ids: list[str],
    ) -> list[PricingToppingData]:
        """
        Lấy danh sách toppings theo legacy_id.
        Chỉ trả về toppings đang active.
        Thứ tự không đảm bảo — caller không nên phụ thuộc vào order.
        """
        ...

    @abstractmethod
    async def get_active_time_deal(self, current_hour_vn: int) -> ActiveTimeDeal | None:
        """
        Lấy time deal đang active tại giờ hiện tại (giờ Việt Nam, 0-23).
        Return None nếu không có deal nào đang chạy.
        """
        ...
