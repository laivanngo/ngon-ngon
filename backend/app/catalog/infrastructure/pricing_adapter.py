"""
Catalog Context — Pricing Adapter
=====================================
Implementation của ordering/domain/catalog_port.CatalogPricingPort.

Catalog context sở hữu Product, Topping, TimeDeal.
Ordering muốn query để tính giá → gọi qua adapter này.

PATTERN: Outbound Adapter (Driven Adapter)
    Ordering Port (interface) ← [SqlCatalogPricingAdapter] ← SQLAlchemy ORM

WHY adapter nằm trong catalog/ (không phải ordering/):
    - Adapter implement port bằng cách dùng Catalog's ORM models
    - Chỉ Catalog infrastructure mới có quyền import Catalog ORM
    - Ordering không biết gì về Product table structure
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.infrastructure.orm_models import Product, TimeDeal, Topping
from app.ordering.domain.catalog_port import (
    ActiveTimeDeal,
    CatalogPricingPort,
    PricingProductData,
    PricingSizeData,
    PricingToppingData,
)


class SqlCatalogPricingAdapter(CatalogPricingPort):
    """
    Query Catalog ORM models, convert sang Ordering's pricing DTOs.

    Logic SQL giữ nguyên 100% từ SqlPricingService cũ.
    Chỉ khác: trả DTO thay vì ORM object trực tiếp.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_product(self, product_id: int) -> PricingProductData | None:
        stmt = (
            select(Product)
            .where(Product.id == product_id)
            .options(selectinload(Product.sizes))
        )
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        return PricingProductData(
            id=orm.id,
            name=orm.name,
            base_price=orm.base_price,
            is_active=orm.is_active,
            sizes=[
                PricingSizeData(label=s.label, price=s.price)
                for s in orm.sizes
            ],
        )

    async def get_toppings_by_legacy_ids(
        self,
        legacy_ids: list[str],
    ) -> list[PricingToppingData]:
        if not legacy_ids:
            return []

        stmt = select(Topping).where(
            Topping.legacy_id.in_(legacy_ids),
            Topping.is_active == True,  # noqa: E712
        )
        result = await self._db.execute(stmt)
        orms = result.scalars().all()

        return [
            PricingToppingData(
                legacy_id=t.legacy_id,
                name=t.name,
                emoji=t.emoji,
                price=t.price,
            )
            for t in orms
        ]

    async def get_active_time_deal(self, current_hour_vn: int) -> ActiveTimeDeal | None:
        stmt = select(TimeDeal).where(
            TimeDeal.is_active == True,  # noqa: E712
            TimeDeal.start_hour <= current_hour_vn,
            TimeDeal.end_hour > current_hour_vn,
            TimeDeal.discount_percent > 0,
        )
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        return ActiveTimeDeal(
            title=orm.title,
            discount_percent=orm.discount_percent,
        )
