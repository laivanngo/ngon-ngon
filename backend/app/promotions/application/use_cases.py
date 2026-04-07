"""
Promotions Context — Application Use Cases
=============================================
Tách từ growth/application/use_cases.py — chỉ giữ phần promotions.

Use cases:
- GetUpsellStatsUseCase: topping/size popularity
- GetCrossSellUseCase: gợi ý mua kèm
- ToggleFeatureFlagUseCase: admin bật/tắt feature flag
"""

from __future__ import annotations

import logging

from app.promotions.domain.services import (
    CrossSellQueryService,
    CrossSellSuggestion,
    FeatureFlag,
    FeatureFlagRepository,
    UpsellStats,
    UpsellStatsService,
)
from app.shared.exceptions import NotFoundError

logger = logging.getLogger("ngonngon.promotions")


# =============================================================================
# GET /upsell-stats
# =============================================================================
class GetUpsellStatsUseCase:
    """Trả về % khách thêm topping + % chọn size lớn."""

    def __init__(self, stats_service: UpsellStatsService) -> None:
        self._stats = stats_service

    async def execute(self) -> UpsellStats:
        return await self._stats.get_stats()


# =============================================================================
# GET /cross-sell
# =============================================================================
class GetCrossSellUseCase:
    """Input: product IDs trong giỏ hàng → Output: top 3 gợi ý mua kèm."""

    def __init__(self, cross_sell_service: CrossSellQueryService) -> None:
        self._cross_sell = cross_sell_service

    async def execute(self, product_ids_str: str) -> list[CrossSellSuggestion]:
        if not product_ids_str:
            return []
        try:
            cart_ids = [
                int(x.strip())
                for x in product_ids_str.split(",")
                if x.strip()
            ]
        except ValueError:
            return []
        if not cart_ids:
            return []
        return await self._cross_sell.suggest(cart_ids)


# =============================================================================
# PATCH /flags/{key}
# =============================================================================
class ToggleFeatureFlagUseCase:

    def __init__(self, flag_repo: FeatureFlagRepository) -> None:
        self._flags = flag_repo

    async def execute(self, key: str, enabled: bool, admin_username: str) -> FeatureFlag:
        flag = await self._flags.toggle(key, enabled)
        if not flag:
            raise NotFoundError(f"Feature '{key}' not found")
        logger.info(
            f"🏁 Feature '{key}' → {'ON' if enabled else 'OFF'} "
            f"(by {admin_username})"
        )
        return flag
