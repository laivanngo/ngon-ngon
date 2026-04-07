"""
CRM Context — Event Handlers
=================================
Handlers lắng nghe events từ các context khác.

THAY ĐỔI SO VỚI GROWTH:
- Loyalty tích điểm theo chi tiêu: event.total * rate (thay vì cố định +1)
- rate đọc từ growth_settings table, fallback về LOYALTY_POINTS_PER_1000

CROSS-CONTEXT COMMUNICATION:
    Ordering --(phát OrderPlaced event)--> EventBus --> CRM: update Customer
"""

import logging
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ordering.domain.events import OrderPlaced, OrderStatusChanged
from app.crm.domain.value_objects import LOYALTY_POINTS_PER_1000, LoyaltyPoints

logger = logging.getLogger("ngonngon.crm.events")


# =============================================================================
# on_order_placed → Tạo/cập nhật Customer (spend-based loyalty)
# =============================================================================
async def on_order_placed_track_customer(
    event: OrderPlaced,
    db_session_factory,
) -> None:
    """
    Khi có đơn mới → tạo/cập nhật Customer.

    MÔ HÌNH LOYALTY MỚI:
    - Tính điểm = order_total * points_rate (thay vì cố định +1)
    - points_rate đọc từ growth_settings (key='loyalty_points_per_1000')
    - Fallback về LOYALTY_POINTS_PER_1000 nếu chưa có setting
    """
    try:
        from app.crm.infrastructure.orm_models import Customer, GrowthSetting

        async with db_session_factory() as db:
            now = datetime.now(timezone.utc)

            # Đọc points_rate từ settings (admin chỉnh được)
            rate_result = await db.execute(
                select(GrowthSetting.value).where(
                    GrowthSetting.key == "loyalty_points_per_1000"
                )
            )
            points_rate = rate_result.scalar_one_or_none() or LOYALTY_POINTS_PER_1000

            # Tính điểm loyalty từ giá trị đơn hàng
            earned_points = LoyaltyPoints.points_from_spend(event.total, points_rate)

            cust_result = await db.execute(
                select(Customer).where(Customer.phone == event.phone)
            )
            customer = cust_result.scalar_one_or_none()

            if not customer:
                try:
                    customer = Customer(
                        phone=event.phone,
                        name=event.customer_name,
                        order_count=1,
                        total_spent=event.total,
                        loyalty_points=earned_points,
                        first_order_at=now,
                        last_order_at=now,
                    )
                    db.add(customer)
                    await db.flush()
                except SAIntegrityError:
                    await db.rollback()
                    cust_result = await db.execute(
                        select(Customer).where(Customer.phone == event.phone)
                    )
                    customer = cust_result.scalar_one_or_none()
                    if customer:
                        customer.order_count += 1
                        customer.total_spent += event.total
                        customer.loyalty_points += earned_points
                        customer.last_order_at = now
                        await db.flush()
            else:
                customer.name = event.customer_name
                customer.order_count += 1
                customer.total_spent += event.total
                customer.loyalty_points += earned_points
                customer.last_order_at = now
                await db.flush()

            # Link customer_id vào order
            if customer and event.order_id:
                from app.ordering.infrastructure.analytics_adapter import SqlOrderCustomerLinkAdapter
                link_adapter = SqlOrderCustomerLinkAdapter(db)
                await link_adapter.link_customer_to_order(event.order_id, customer.id)

            await db.commit()

            if earned_points > 0:
                logger.info(
                    f"🎯 {event.phone}: +{earned_points} điểm "
                    f"(đơn {event.total}k × {points_rate})"
                )

    except Exception as e:
        logger.warning(f"Customer tracking failed (order still OK): {e}")


# =============================================================================
# Factory: tạo handlers đã bind dependencies
# =============================================================================
def create_customer_tracking_handler(
    db_session_factory: Any,
) -> Callable[[OrderPlaced], Coroutine[Any, Any, None]]:
    """Tạo handler đã bind db_session_factory."""

    async def handler(event: OrderPlaced) -> None:
        await on_order_placed_track_customer(event, db_session_factory)

    handler.__name__ = "on_order_placed_track_customer"
    return handler
