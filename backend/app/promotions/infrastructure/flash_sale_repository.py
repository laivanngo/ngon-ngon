"""
Promotions Context — Flash Sale SQL Repository
==================================================
SQL implementation cho FlashSaleRepository ABC.

Critical: claim_atomically() dùng UPDATE...WHERE < max_quantity
để chống race condition — PostgreSQL row-level lock đảm bảo atomic.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.promotions.domain.flash_sale import FlashSale, FlashSaleRepository, FlashSaleStatus
from app.promotions.infrastructure.orm_models import FlashSale as ORMFlashSale, FlashSaleProduct

logger = logging.getLogger("ngonngon.promotions.flash_sale_repo")


class SqlFlashSaleRepository(FlashSaleRepository):
    """SQL implementation — map domain FlashSale ↔ ORM FlashSale."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # =========================================================================
    # Mapping helpers
    # =========================================================================
    def _to_domain(self, orm: ORMFlashSale) -> FlashSale:
        """ORM → Domain entity."""
        return FlashSale(
            id=orm.id,
            title=orm.title,
            subtitle=orm.subtitle,
            discount_percent=orm.discount_percent,
            product_ids=[fp.product_id for fp in orm.products],
            max_quantity=orm.max_quantity,
            claimed_count=orm.claimed_count,
            starts_at=orm.starts_at,
            ends_at=orm.ends_at,
            status=FlashSaleStatus(orm.status),
            store_id=orm.store_id,
            created_at=orm.created_at,
        )

    def _to_orm(self, sale: FlashSale) -> ORMFlashSale:
        """Domain entity → ORM (cho create)."""
        orm = ORMFlashSale(
            title=sale.title,
            subtitle=sale.subtitle,
            discount_percent=sale.discount_percent,
            max_quantity=sale.max_quantity,
            claimed_count=sale.claimed_count,
            starts_at=sale.starts_at,
            ends_at=sale.ends_at,
            status=sale.status.value,
            store_id=sale.store_id,
        )
        orm.products = [
            FlashSaleProduct(product_id=pid) for pid in sale.product_ids
        ]
        return orm

    # =========================================================================
    # CRUD
    # =========================================================================
    async def save(self, sale: FlashSale) -> FlashSale:
        """Persist flash sale mới hoặc cập nhật."""
        if sale.id is None:
            orm = self._to_orm(sale)
            self._db.add(orm)
            await self._db.flush()
            sale.id = orm.id
            sale.created_at = orm.created_at
            logger.info(f"✨ Flash Sale created: #{orm.id} '{sale.title}'")
        else:
            stmt = select(ORMFlashSale).where(ORMFlashSale.id == sale.id)
            result = await self._db.execute(stmt)
            orm = result.scalar_one_or_none()
            if orm:
                orm.status = sale.status.value
                orm.claimed_count = sale.claimed_count
                orm.title = sale.title
                orm.subtitle = sale.subtitle

        await self._db.commit()
        return sale

    async def find_by_id(self, sale_id: int) -> FlashSale | None:
        """Tìm flash sale theo id."""
        stmt = select(ORMFlashSale).where(ORMFlashSale.id == sale_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def find_active(self, now: datetime) -> list[FlashSale]:
        """Tìm flash sales đang ACTIVE và trong time window."""
        stmt = (
            select(ORMFlashSale)
            .where(ORMFlashSale.status == FlashSaleStatus.ACTIVE.value)
            .where(ORMFlashSale.starts_at <= now)
            .where(ORMFlashSale.ends_at > now)
            .order_by(ORMFlashSale.discount_percent.desc())
        )
        result = await self._db.execute(stmt)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def find_scheduled_ready(self, now: datetime) -> list[FlashSale]:
        """Tìm SCHEDULED sales đã tới giờ bắt đầu."""
        stmt = (
            select(ORMFlashSale)
            .where(ORMFlashSale.status == FlashSaleStatus.SCHEDULED.value)
            .where(ORMFlashSale.starts_at <= now)
        )
        result = await self._db.execute(stmt)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def find_active_expired(self, now: datetime) -> list[FlashSale]:
        """Tìm ACTIVE sales đã hết giờ."""
        stmt = (
            select(ORMFlashSale)
            .where(ORMFlashSale.status == FlashSaleStatus.ACTIVE.value)
            .where(ORMFlashSale.ends_at <= now)
        )
        result = await self._db.execute(stmt)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def list_all(
        self, limit: int = 20, offset: int = 0,
    ) -> tuple[list[FlashSale], int]:
        """Danh sách tất cả + total count (admin view)."""
        count_stmt = select(func.count(ORMFlashSale.id))
        count_result = await self._db.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(ORMFlashSale)
            .order_by(ORMFlashSale.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        sales = [self._to_domain(orm) for orm in result.scalars().all()]
        return sales, total

    # =========================================================================
    # Atomic Claim — chống race condition
    # =========================================================================
    async def claim_atomically(self, sale_id: int) -> int | None:
        """
        Atomic increment claimed_count.

        SQL: UPDATE flash_sales
             SET claimed_count = claimed_count + 1
             WHERE id = ? AND claimed_count < max_quantity AND status = 'active'
             RETURNING claimed_count

        PostgreSQL row-level lock đảm bảo chỉ 1 transaction thắng.
        Return claimed_count mới nếu thành công, None nếu hết lượt.
        """
        stmt = (
            update(ORMFlashSale)
            .where(ORMFlashSale.id == sale_id)
            .where(ORMFlashSale.claimed_count < ORMFlashSale.max_quantity)
            .where(ORMFlashSale.status == FlashSaleStatus.ACTIVE.value)
            .values(claimed_count=ORMFlashSale.claimed_count + 1)
            .returning(ORMFlashSale.claimed_count)
        )
        result = await self._db.execute(stmt)
        await self._db.commit()
        row = result.scalar_one_or_none()

        if row is not None:
            logger.info(f"🎟️ Flash Sale #{sale_id} claimed ({row}/{sale_id})")
        else:
            logger.info(f"🚫 Flash Sale #{sale_id} claim failed (sold out or inactive)")

        return row
