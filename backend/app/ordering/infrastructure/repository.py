"""
Ordering Context — SQL Order Repository
==========================================
Implementation của OrderRepository ABC dùng SQLAlchemy async.

TRÁCH NHIỆM DUY NHẤT: map giữa domain Order ↔ ORM Order (models.py).
Không chứa business logic — chỉ persistence.

WHY reuse ORM models từ models.py (không tạo riêng):
- Tránh duplicate table mapping → migration conflict
- models.py vẫn dùng bởi admin.py, kds.py, growth.py (chưa migrate)
- Khi tất cả contexts migrate xong → mỗi context có ORM riêng
"""

from __future__ import annotations

import logging
from datetime import timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# ORM models: import từ context sở hữu (không từ app.models)
from app.ordering.infrastructure.orm_models import Order as ORMOrder
from app.ordering.infrastructure.orm_models import OrderItem as ORMOrderItem
from app.ordering.infrastructure.orm_models import OrderStatus as ORMOrderStatus
from app.ordering.domain.entities import Order, OrderItem
from app.ordering.domain.services import OrderRepository
from app.ordering.domain.value_objects import OrderStatus

logger = logging.getLogger("ngonngon.ordering.repo")


class SqlOrderRepository(OrderRepository):
    """
    SQLAlchemy implementation của OrderRepository.

    Maps:
    - Domain Order ↔ ORM Order (app.models.Order)
    - Domain OrderItem ↔ ORM OrderItem (app.models.OrderItem)
    - Domain OrderStatus ↔ ORM OrderStatus enum
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # =========================================================================
    # save — Persist order (create or update)
    # =========================================================================
    async def save(self, order: Order) -> Order:
        """
        Persist domain Order vào DB.
        Nếu order.id is None → INSERT (đơn mới).
        Nếu order.id is not None → UPDATE (đổi status, etc.).
        """
        if order.id is None:
            return await self._insert(order)
        else:
            return await self._update(order)

    async def _insert(self, order: Order) -> Order:
        """Tạo đơn hàng mới trong DB."""
        orm_order = ORMOrder(
            public_id=order.public_id,
            customer_name=order.customer_name,
            phone=order.phone,
            address=order.address,
            note=order.note,
            delivery_type=order.delivery_type,
            scheduled_time=order.scheduled_time,
            subtotal=order.subtotal,
            discount=order.discount,
            total=order.total,
            status=ORMOrderStatus(order.status.value),
            estimated_minutes=order.estimated_minutes,
            store_id=order.store_id,
            items=[
                ORMOrderItem(
                    product_id=item.product_id,
                    product_name=item.product_name,
                    size=item.size,
                    sweetness=item.sweetness,
                    ice_level=item.ice_level,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    toppings_text=item.toppings_text,
                    note=item.note,
                    store_id=order.store_id,
                )
                for item in order.items
            ],
        )

        self._db.add(orm_order)
        await self._db.commit()
        await self._db.refresh(orm_order)

        # Update domain entity với DB-generated values
        order.id = orm_order.id
        order.created_at = orm_order.created_at
        for domain_item, orm_item in zip(order.items, orm_order.items):
            domain_item.id = orm_item.id

        return order

    async def _update(self, order: Order) -> Order:
        """Update đơn hàng đã tồn tại (VD: đổi status)."""
        stmt = select(ORMOrder).where(ORMOrder.id == order.id)
        result = await self._db.execute(stmt)
        orm_order = result.scalar_one_or_none()

        if not orm_order:
            raise ValueError(f"Order id={order.id} not found in DB")

        # Map domain fields → ORM
        orm_order.status = ORMOrderStatus(order.status.value)
        orm_order.customer_id = order.customer_id
        orm_order.estimated_minutes = order.estimated_minutes
        orm_order.completed_at = order.completed_at

        await self._db.commit()
        return order

    # =========================================================================
    # find_by_public_id — Tìm order bằng UUID
    # =========================================================================
    async def find_by_public_id(self, public_id: str) -> Order | None:
        """
        Load order từ DB, convert sang domain entity.
        Dùng selectinload để tránh N+1 (giống code cũ).
        """
        stmt = (
            select(ORMOrder)
            .where(ORMOrder.public_id == public_id)
            .options(selectinload(ORMOrder.items))
        )
        result = await self._db.execute(stmt)
        orm_order = result.scalar_one_or_none()

        if not orm_order:
            return None

        return self._to_domain(orm_order)

    # =========================================================================
    # count_active — Đếm đơn active cho estimate time
    # =========================================================================
    async def count_active(self) -> int:
        """Đếm đơn đang pending/confirmed/preparing."""
        active_statuses = [
            ORMOrderStatus.PENDING,
            ORMOrderStatus.CONFIRMED,
            ORMOrderStatus.PREPARING,
        ]
        result = await self._db.execute(
            select(func.count(ORMOrder.id)).where(
                ORMOrder.status.in_(active_statuses)
            )
        )
        return result.scalar() or 0

    # =========================================================================
    # list_orders — Admin panel: danh sách đơn + pagination
    # =========================================================================
    async def list_orders(
        self,
        status_filter: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Order], int]:
        """Danh sách đơn hàng (mới nhất trước) + total count."""
        from sqlalchemy import and_

        conditions = []
        if status_filter:
            conditions.append(ORMOrder.status == status_filter)

        # Count total
        count_stmt = select(func.count(ORMOrder.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await self._db.execute(count_stmt)).scalar() or 0

        # Fetch orders
        stmt = (
            select(ORMOrder)
            .options(selectinload(ORMOrder.items))
            .order_by(ORMOrder.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await self._db.execute(stmt)
        orms = result.scalars().unique().all()

        return [self._to_domain(o) for o in orms], total

    # =========================================================================
    # count_by_status — Đếm đơn theo trạng thái
    # =========================================================================
    async def count_by_status(self, status: str) -> int:
        result = await self._db.execute(
            select(func.count(ORMOrder.id)).where(ORMOrder.status == status)
        )
        return result.scalar() or 0

    # =========================================================================
    # Mapping: ORM → Domain
    # =========================================================================
    @staticmethod
    def _to_domain(orm: ORMOrder) -> Order:
        """Convert ORM Order → Domain Order."""
        items = [
            OrderItem(
                id=oi.id,
                product_id=oi.product_id,
                product_name=oi.product_name,
                size=oi.size,
                sweetness=oi.sweetness,
                ice_level=oi.ice_level,
                quantity=oi.quantity,
                unit_price=oi.unit_price,
                toppings_text=oi.toppings_text,
                note=oi.note,
            )
            for oi in orm.items
        ]

        return Order(
            id=orm.id,
            public_id=orm.public_id,
            customer_name=orm.customer_name,
            phone=orm.phone,
            address=orm.address,
            note=orm.note,
            delivery_type=orm.delivery_type or "immediate",
            scheduled_time=orm.scheduled_time,
            items=items,
            subtotal=orm.subtotal,
            discount=orm.discount,
            total=orm.total,
            status=OrderStatus(orm.status.value),
            store_id=orm.store_id,
            customer_id=orm.customer_id,
            estimated_minutes=orm.estimated_minutes,
            created_at=orm.created_at,
            completed_at=orm.completed_at,
        )


# =============================================================================
# SqlDashboardQueryService — Dashboard stats queries
# =============================================================================
class SqlDashboardQueryService:
    """
    Dashboard queries — tổng hợp stats cho admin panel.

    TRƯỚC: Import trực tiếp ORMProduct từ Catalog (vi phạm ranh giới).
    SAU:   Nhận CatalogAnalyticsPort để đếm active_products — Ordering
           không biết Product table structure.

    WHY dashboard nằm trong Ordering context:
    - orders_today, revenue_today, pending_orders đều là Ordering data
    - active_products là Catalog data — cross bằng port, không bằng ORM
    """

    def __init__(
        self,
        db: AsyncSession,
        catalog_port: "CatalogAnalyticsPort | None" = None,
    ) -> None:
        self._db = db
        self._catalog_port = catalog_port

    async def get_stats(self) -> "DashboardStats":
        from datetime import datetime, timezone
        from app.ordering.application.use_cases import DashboardStats

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        orders_today = (await self._db.execute(
            select(func.count(ORMOrder.id)).where(ORMOrder.created_at >= today_start)
        )).scalar() or 0

        revenue_today = (await self._db.execute(
            select(func.coalesce(func.sum(ORMOrder.total), 0)).where(
                ORMOrder.created_at >= today_start,
                ORMOrder.status == ORMOrderStatus.DONE,
            )
        )).scalar() or 0

        pending_count = (await self._db.execute(
            select(func.count(ORMOrder.id)).where(
                ORMOrder.status == ORMOrderStatus.PENDING
            )
        )).scalar() or 0

        # Query số sản phẩm active qua port — không import Catalog ORM
        active_products = 0
        if self._catalog_port:
            active_products = await self._catalog_port.count_active_products()

        return DashboardStats(
            orders_today=orders_today,
            revenue_today=revenue_today,
            pending_orders=pending_count,
            active_products=active_products,
        )
