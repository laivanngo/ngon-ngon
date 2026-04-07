"""
Ordering Context — Promotions Port
=====================================
Interface mà Ordering cần từ Promotions để áp dụng Flash Sale discount.

DEPENDENCY RULE:
    Domain defines what it needs (port).
    Promotions provides the implementation (adapter).
    Ordering không biết Promotions' ORM, table structure, hay cả tên context.

Cùng pattern với CatalogPricingPort.

DTOs:
    ActiveFlashSaleDeal — flash sale đang active (nếu có)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ActiveFlashSaleDeal:
    """Flash sale đang active tại thời điểm hiện tại."""

    sale_id: int
    title: str
    discount_percent: int
    product_ids: list[int]    # [] = áp dụng toàn menu


class PromotionsPricingPort(ABC):
    """
    Port cho phép Ordering query flash sale discount từ Promotions.

    Adapter: promotions/infrastructure/flash_sale_pricing_adapter.SqlFlashSalePricingAdapter
    Fake:    tests/unit/fakes.FakePromotionsPricingPort (cho unit test)
    """

    @abstractmethod
    async def get_best_flash_sale(
        self, product_ids: list[int],
    ) -> ActiveFlashSaleDeal | None:
        """
        Tìm flash sale active tốt nhất cho giỏ hàng hiện tại.

        Logic:
        - Nếu có whole-cart sale (product_ids=[]) → trả về
        - Nếu có product-specific sale matching cart product_ids → trả về
        - Nếu cả hai: trả về sale có discount_percent cao hơn
        - Return None nếu không có flash sale nào đang chạy
        """
        ...

    @abstractmethod
    async def claim_flash_sale(self, sale_id: int) -> bool:
        """
        Atomic claim: tăng claimed_count + 1.
        Return True nếu claim thành công.
        Return False nếu đã hết lượt hoặc không active.
        """
        ...
