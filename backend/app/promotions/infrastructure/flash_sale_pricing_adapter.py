"""
Promotions Context — Flash Sale Pricing Adapter
===================================================
Implement PromotionsPricingPort (defined by Ordering domain).
Ordering gọi qua port interface → không biết Promotions' ORM tồn tại.

Cùng pattern với catalog/infrastructure/pricing_adapter.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ordering.domain.promotions_port import ActiveFlashSaleDeal, PromotionsPricingPort
from app.promotions.domain.events import FlashSaleClaimed
from app.promotions.domain.flash_sale import FlashSaleStatus
from app.promotions.infrastructure.orm_models import FlashSale as ORMFlashSale
from app.shared.events import event_bus

logger = logging.getLogger("ngonngon.promotions.pricing_adapter")


class SqlFlashSalePricingAdapter(PromotionsPricingPort):
    """SQL adapter — query flash_sales table cho Ordering pricing."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_best_flash_sale(
        self, product_ids: list[int],
    ) -> ActiveFlashSaleDeal | None:
        """
        Tìm flash sale active tốt nhất.

        Priority: highest discount_percent wins.
        Matches: whole-cart (products empty) OR product-specific (intersection with cart).
        """
        now = datetime.now(timezone.utc)

        stmt = (
            select(ORMFlashSale)
            .options(selectinload(ORMFlashSale.products))
            .where(ORMFlashSale.status == FlashSaleStatus.ACTIVE.value)
            .where(ORMFlashSale.starts_at <= now)
            .where(ORMFlashSale.ends_at > now)
            .where(ORMFlashSale.claimed_count < ORMFlashSale.max_quantity)
            .order_by(ORMFlashSale.discount_percent.desc())
        )

        result = await self._db.execute(stmt)
        rows = result.scalars().unique().all()

        # Tìm deal matching tốt nhất: so sánh TẤT CẢ sales phù hợp,
        # pick discount cao nhất (không return sớm khi gặp whole-cart).
        best: ActiveFlashSaleDeal | None = None

        for row in rows:
            sale_product_ids = [fp.product_id for fp in row.products]

            if not sale_product_ids:
                # Whole-cart sale (empty products) — áp dụng cho mọi đơn
                matches = True
            elif set(sale_product_ids) & set(product_ids):
                # Product-specific sale — áp dụng nếu có ít nhất 1 product trùng
                matches = True
            else:
                matches = False

            if matches:
                if best is None or row.discount_percent > best.discount_percent:
                    best = ActiveFlashSaleDeal(
                        sale_id=row.id,
                        title=row.title,
                        discount_percent=row.discount_percent,
                        product_ids=sale_product_ids,
                    )

        return best

    async def claim_flash_sale(self, sale_id: int) -> bool:
        """
        Atomic claim — tăng claimed_count bằng SQL UPDATE...WHERE.
        PostgreSQL row-level lock đảm bảo không oversell.

        Sau khi claim thành công → publish FlashSaleClaimed event
        để WS broadcast remaining count tới admin panel.
        """
        stmt = (
            update(ORMFlashSale)
            .where(ORMFlashSale.id == sale_id)
            .where(ORMFlashSale.claimed_count < ORMFlashSale.max_quantity)
            .where(ORMFlashSale.status == FlashSaleStatus.ACTIVE.value)
            .values(claimed_count=ORMFlashSale.claimed_count + 1)
            .returning(ORMFlashSale.claimed_count, ORMFlashSale.max_quantity)
        )
        result = await self._db.execute(stmt)
        row = result.one_or_none()

        if row is not None:
            new_claimed, max_qty = row
            remaining = max_qty - new_claimed
            is_sold_out = remaining <= 0

            logger.info(
                f"🎟️ Flash Sale #{sale_id} claimed "
                f"(count: {new_claimed}, remaining: {remaining})"
            )

            # Publish event → WS broadcast remaining count to admin
            await event_bus.publish(FlashSaleClaimed(
                sale_id=sale_id,
                remaining=remaining,
                is_sold_out=is_sold_out,
            ))

            return True

        logger.info(f"🚫 Flash Sale #{sale_id} claim failed (sold out or inactive)")
        return False
