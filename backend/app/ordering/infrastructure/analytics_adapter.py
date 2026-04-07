"""
Ordering Context — Analytics Adapter
=======================================
Implementation của ordering/application/analytics_port.OrderAnalyticsPort.

Ordering sở hữu Order, OrderItem, OrderStatus.
Growth muốn query analytics → gọi qua adapter này.

SQL giữ nguyên 100% từ growth/infrastructure/repository.py cũ.
Chỉ khác: trả DTO thay vì ORM object.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Date, and_, case, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ordering.application.analytics_port import (
    CrossSellOrderItemData,
    DailyRevenueData,
    OrderAnalyticsPort,
    OrderItemData,
    OrderStatsData,
    OrderWithItemsData,
    PeakHourData,
    TopProductData,
    UpsellRawData,
)
from app.ordering.infrastructure.orm_models import Order, OrderItem, OrderStatus

logger = logging.getLogger("ngonngon.ordering.analytics_adapter")


class SqlOrderAnalyticsAdapter(OrderAnalyticsPort):

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_last_completed_order_by_phone(
        self, phone: str
    ) -> OrderWithItemsData | None:
        stmt = (
            select(Order)
            .where(
                Order.phone == phone,
                Order.status.in_([OrderStatus.DONE, OrderStatus.DELIVERING]),
            )
            .options(selectinload(Order.items))
            .order_by(desc(Order.created_at))
            .limit(1)
        )
        result = await self._db.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            return None
        return OrderWithItemsData(
            public_id=order.public_id,
            total=order.total,
            status=order.status.value,
            created_at=order.created_at.isoformat(),
            items=[
                OrderItemData(
                    product_id=it.product_id,
                    product_name=it.product_name,
                    size=it.size,
                    sweetness=it.sweetness,
                    ice_level=it.ice_level,
                    quantity=it.quantity,
                    unit_price=it.unit_price,
                    toppings_text=it.toppings_text,
                )
                for it in order.items
            ],
        )

    async def get_revenue_by_day(self, since: datetime) -> list[DailyRevenueData]:
        day_col = cast(Order.created_at, Date).label("day")
        stmt = (
            select(
                day_col,
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            )
            .where(Order.created_at >= since, Order.status == OrderStatus.DONE)
            .group_by(day_col)
            .order_by(day_col)
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            DailyRevenueData(day=str(r.day), order_count=r.order_count, revenue=r.revenue)
            for r in rows
        ]

    async def get_top_products(self, since: datetime, limit: int = 10) -> list[TopProductData]:
        stmt = (
            select(
                OrderItem.product_name,
                func.sum(OrderItem.quantity).label("qty"),
                func.sum(OrderItem.unit_price * OrderItem.quantity).label("rev"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .where(Order.created_at >= since, Order.status == OrderStatus.DONE)
            .group_by(OrderItem.product_name)
            .order_by(desc("rev"))
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).all()
        return [TopProductData(name=r.product_name, quantity=r.qty, revenue=r.rev) for r in rows]

    async def get_peak_hours(self, since: datetime) -> list[PeakHourData]:
        hour_col = func.extract("hour", Order.created_at).label("hour")
        stmt = (
            select(hour_col, func.count().label("cnt"))
            .where(Order.created_at >= since, Order.status != OrderStatus.CANCELLED)
            .group_by(hour_col)
            .order_by(hour_col)
        )
        rows = (await self._db.execute(stmt)).all()
        return [PeakHourData(hour=int(r.hour), order_count=r.cnt) for r in rows]

    async def get_order_stats(self, since: datetime) -> OrderStatsData:
        total = (
            await self._db.execute(
                select(func.count(Order.id)).where(Order.created_at >= since)
            )
        ).scalar() or 0

        cancelled = (
            await self._db.execute(
                select(func.count(Order.id)).where(
                    Order.created_at >= since,
                    Order.status == OrderStatus.CANCELLED,
                )
            )
        ).scalar() or 0

        return OrderStatsData(total_in_period=total, cancelled_in_period=cancelled)

    async def get_upsell_raw_data(self) -> UpsellRawData:
        total = (
            await self._db.execute(
                select(func.count(Order.id)).where(Order.status != OrderStatus.CANCELLED)
            )
        ).scalar() or 1

        with_toppings = (
            await self._db.execute(
                select(func.count(func.distinct(OrderItem.order_id))).where(
                    OrderItem.toppings_text.isnot(None),
                    OrderItem.toppings_text != "",
                )
            )
        ).scalar() or 0

        size_result = await self._db.execute(
            select(OrderItem.size, func.count())
            .where(OrderItem.size.isnot(None), OrderItem.size != "")
            .group_by(OrderItem.size)
        )
        size_counts = {row[0]: row[1] for row in size_result.all()}

        return UpsellRawData(
            total_orders_not_cancelled=total,
            orders_with_toppings=with_toppings,
            size_counts=size_counts,
        )

    async def get_cross_sell_items(
        self, product_ids: list[int]
    ) -> list[CrossSellOrderItemData]:
        if not product_ids:
            return []
        order_ids_stmt = select(func.distinct(OrderItem.order_id)).where(
            OrderItem.product_id.in_(product_ids)
        )
        stmt = (
            select(OrderItem.order_id, OrderItem.product_id, OrderItem.product_name)
            .where(
                OrderItem.order_id.in_(order_ids_stmt),
                ~OrderItem.product_id.in_(product_ids),
            )
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            CrossSellOrderItemData(
                order_id=r.order_id,
                product_id=r.product_id,
                product_name=r.product_name,
            )
            for r in rows
        ]

    async def get_order_id_by_public_id(self, public_id: str) -> int | None:
        result = await self._db.execute(
            select(Order.id).where(Order.public_id == public_id)
        )
        return result.scalar_one_or_none()


class SqlOrderCustomerLinkAdapter:
    """
    Adapter để Growth context ghi customer_id vào Order
    mà không cần import Order ORM trực tiếp.
    """
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def link_customer_to_order(self, order_id: int, customer_id: int) -> None:
        result = await self._db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if order:
            order.customer_id = customer_id
