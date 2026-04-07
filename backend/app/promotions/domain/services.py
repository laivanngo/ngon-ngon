"""
Promotions Context — Domain Services & ABCs
===============================================
Feature Flags, Upsell Stats, Cross-sell — công cụ khuyến mãi.

TÁCH TỪ GROWTH:
- FeatureFlag: bật/tắt tính năng khuyến mãi
- UpsellStats: thống kê topping/size popularity cho gợi ý
- CrossSell: gợi ý mua kèm dựa trên lịch sử đơn hàng
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


# =============================================================================
# FeatureFlag — Bật/tắt tính năng
# =============================================================================
@dataclass
class FeatureFlag:
    """Simple DTO cho feature flag."""
    key: str
    enabled: bool
    description: str = ""
    id: int | None = None


class FeatureFlagRepository(ABC):
    """Interface cho FeatureFlag persistence."""

    @abstractmethod
    async def get_all(self) -> dict[str, bool]:
        """Return {key: enabled} cho tất cả flags."""
        ...

    @abstractmethod
    async def toggle(self, key: str, enabled: bool) -> FeatureFlag | None:
        """Bật/tắt 1 flag. Return None nếu key không tồn tại."""
        ...


# =============================================================================
# UpsellStats — Topping/size popularity
# =============================================================================
@dataclass
class UpsellStats:
    topping_pct: int
    size_pct: dict[str, int]
    total_orders: int


class UpsellStatsService(ABC):
    """Tính % khách thêm topping + % chọn size lớn."""

    @abstractmethod
    async def get_stats(self) -> UpsellStats:
        ...


# =============================================================================
# CrossSell — Gợi ý mua kèm
# =============================================================================
@dataclass
class CrossSellSuggestion:
    id: int
    legacy_id: str
    name: str
    price: int
    emoji: str
    freq: int


class CrossSellQueryService(ABC):
    """Gợi ý mua kèm dựa trên giỏ hàng hiện tại."""

    @abstractmethod
    async def suggest(self, product_ids: list[int]) -> list[CrossSellSuggestion]:
        ...
