"""
Promotions Context — SQL Infrastructure
==========================================
SQL implementations cho FeatureFlagRepository, UpsellStatsService, CrossSellQueryService.

Tách từ growth/infrastructure/repository.py — chỉ giữ phần promotions.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.promotions.domain.services import (
    CrossSellQueryService,
    CrossSellSuggestion,
    FeatureFlag,
    FeatureFlagRepository,
    UpsellStats,
    UpsellStatsService,
)
from app.promotions.infrastructure.orm_models import FeatureFlag as ORMFeatureFlag
from app.ordering.application.analytics_port import OrderAnalyticsPort
from app.catalog.application.analytics_port import CatalogAnalyticsPort

logger = logging.getLogger("ngonngon.promotions.infra")


# =============================================================================
# SqlFeatureFlagRepository
# =============================================================================
class SqlFeatureFlagRepository(FeatureFlagRepository):

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_all(self) -> dict[str, bool]:
        result = await self._db.execute(select(ORMFeatureFlag))
        return {f.key: f.enabled for f in result.scalars().all()}

    async def toggle(self, key: str, enabled: bool) -> FeatureFlag | None:
        stmt = select(ORMFeatureFlag).where(ORMFeatureFlag.key == key)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            return None
        orm.enabled = enabled
        await self._db.commit()
        return FeatureFlag(key=orm.key, enabled=orm.enabled, id=orm.id)


# =============================================================================
# SqlUpsellStatsService
# =============================================================================
class SqlUpsellStatsService(UpsellStatsService):
    """Thống kê topping rate và size distribution — dùng OrderAnalyticsPort."""

    def __init__(self, order_port: OrderAnalyticsPort) -> None:
        self._order_port = order_port

    async def get_stats(self) -> UpsellStats:
        raw = await self._order_port.get_upsell_raw_data()
        total = raw.total_orders_not_cancelled or 1
        topping_pct = round(raw.orders_with_toppings / total * 100)
        total_sized = sum(raw.size_counts.values()) or 1
        size_pct = {s: round(c / total_sized * 100) for s, c in raw.size_counts.items()}
        return UpsellStats(
            topping_pct=min(topping_pct, 95),
            size_pct=size_pct,
            total_orders=total,
        )


# =============================================================================
# SqlCrossSellQueryService
# =============================================================================
class SqlCrossSellQueryService(CrossSellQueryService):
    """Cross-sell algorithm: tìm SP thường đi kèm trong cùng đơn hàng."""

    def __init__(
        self,
        order_port: OrderAnalyticsPort,
        catalog_port: CatalogAnalyticsPort,
    ) -> None:
        self._order_port = order_port
        self._catalog_port = catalog_port

    async def suggest(self, product_ids: list[int]) -> list[CrossSellSuggestion]:
        items = await self._order_port.get_cross_sell_items(product_ids)
        freq: dict[int, tuple[str, int]] = {}
        for item in items:
            if item.product_id not in freq:
                freq[item.product_id] = (item.product_name, 0)
            name, count = freq[item.product_id]
            freq[item.product_id] = (name, count + 1)

        top = sorted(freq.items(), key=lambda x: x[1][1], reverse=True)[:3]
        suggestions: list[CrossSellSuggestion] = []
        for product_id, (product_name, count) in top:
            prod = await self._catalog_port.get_active_product(product_id)
            if prod:
                suggestions.append(
                    CrossSellSuggestion(
                        id=prod.id, legacy_id=prod.legacy_id, name=prod.name,
                        price=prod.base_price, emoji=prod.emoji, freq=count,
                    )
                )
        return suggestions
