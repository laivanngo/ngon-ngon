"""
Ordering Context — Kitchen Queue Adapter
==========================================
Implementation của ordering/application/analytics_port.KitchenQueuePort.

Ordering sở hữu Order và OrderStatus.
Kitchen muốn đọc queue để hiển thị trên KDS → gọi qua adapter này.

SQL query giữ nguyên 100% từ SqlKitchenOrderRepository cũ.
Chỉ khác: trả KitchenOrderData DTO thay vì ORM object.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ordering.application.analytics_port import (
    KitchenOrderData,
    KitchenOrderItemData,
    KitchenQueuePort,
)
from app.ordering.infrastructure.orm_models import Order, OrderStatus


class SqlKitchenQueueAdapter(KitchenQueuePort):

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_active_queue(self, cutoff_minutes: int = 10) -> list[KitchenOrderData]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=cutoff_minutes)

        active_statuses = [
            OrderStatus.PENDING,
            OrderStatus.CONFIRMED,
            OrderStatus.PREPARING,
            OrderStatus.DELIVERING,
        ]

        stmt = (
            select(Order)
            .options(selectinload(Order.items))
            .where(
                or_(
                    Order.status.in_(active_statuses),
                    and_(
                        Order.status.in_([OrderStatus.DONE, OrderStatus.CANCELLED]),
                        Order.updated_at >= cutoff,
                    ),
                )
            )
            .order_by(Order.created_at.asc())
        )

        result = await self._db.execute(stmt)
        orders = result.scalars().unique().all()

        return [self._to_dto(o) for o in orders]

    @staticmethod
    def _to_dto(orm: Order) -> KitchenOrderData:
        items = [
            KitchenOrderItemData(
                product_name=it.product_name,
                quantity=it.quantity,
                unit_price=it.unit_price,
                size=it.size,
                sweetness=it.sweetness,
                ice_level=it.ice_level,
                toppings_text=it.toppings_text,
                note=it.note,
            )
            for it in orm.items
        ]
        return KitchenOrderData(
            public_id=orm.public_id,
            status=orm.status.value if hasattr(orm.status, "value") else orm.status,
            customer_name=orm.customer_name,
            phone=orm.phone,
            address=orm.address,
            note=orm.note,
            delivery_type=getattr(orm, "delivery_type", "immediate") or "immediate",
            scheduled_time=getattr(orm, "scheduled_time", None),
            total=orm.total,
            created_at=orm.created_at,
            items=items,
        )
