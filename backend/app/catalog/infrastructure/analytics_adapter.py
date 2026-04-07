"""
Catalog Context — Analytics Adapter
======================================
Implementation của catalog/application/analytics_port.CatalogAnalyticsPort.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.application.analytics_port import CatalogAnalyticsPort, ProductInfoData
from app.catalog.infrastructure.orm_models import Product


class SqlCatalogAnalyticsAdapter(CatalogAnalyticsPort):

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_active_product(self, product_id: int) -> ProductInfoData | None:
        result = await self._db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.is_active == True,  # noqa: E712
            )
        )
        orm = result.scalar_one_or_none()
        if not orm:
            return None
        return ProductInfoData(
            id=orm.id,
            legacy_id=orm.legacy_id,
            name=orm.name,
            base_price=orm.base_price,
            emoji=orm.emoji,
            is_active=orm.is_active,
        )

    async def count_active_products(self) -> int:
        result = await self._db.execute(
            select(func.count(Product.id)).where(
                Product.is_active == True  # noqa: E712
            )
        )
        return result.scalar() or 0
