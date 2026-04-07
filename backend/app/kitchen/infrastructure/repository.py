"""
Kitchen Context — Infrastructure
====================================
SQL implementation cho KitchenOrderRepository + PinAuthService.

TRƯỚC: Import trực tiếp Order ORM từ Ordering context (vi phạm ranh giới).
SAU:   SqlKitchenOrderRepository nhận KitchenQueuePort — đọc queue qua port,
       không biết Ordering ORM tồn tại.

ConfigPinAuthService: validate PIN từ settings, rate limit in-memory, issue JWT.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.kitchen.domain.entities import KitchenOrder, KitchenOrderItem
from app.kitchen.domain.services import (
    KdsAuthResult,
    KitchenOrderRepository,
    PinAuthService,
)
from app.ordering.application.analytics_port import KitchenQueuePort

logger = logging.getLogger("ngonngon.kitchen.infra")


# =============================================================================
# SqlKitchenOrderRepository
# =============================================================================
class SqlKitchenOrderRepository(KitchenOrderRepository):
    """
    Đọc queue bếp qua KitchenQueuePort — không import Ordering ORM trực tiếp.

    TRƯỚC: Query trực tiếp Order/OrderStatus ORM từ Ordering context.
    SAU:   Nhận KitchenQueuePort → delegate query → map DTO sang domain entity.
    """

    def __init__(self, db: AsyncSession, queue_port: KitchenQueuePort) -> None:
        self._db = db
        self._queue_port = queue_port

    async def get_active_queue(self) -> list[KitchenOrder]:
        now = datetime.now(timezone.utc)
        raw_orders = await self._queue_port.get_active_queue(cutoff_minutes=10)
        return [self._to_kitchen_order(o, now) for o in raw_orders]

    @staticmethod
    def _to_kitchen_order(data, now: datetime) -> KitchenOrder:
        """Map KitchenOrderData DTO → KitchenOrder domain entity."""
        items = [
            KitchenOrderItem(
                name=it.product_name,
                quantity=it.quantity,
                unit_price=it.unit_price,
                details=KitchenOrder.format_item_details(
                    size=it.size,
                    sweetness=it.sweetness,
                    ice_level=it.ice_level,
                    toppings_text=it.toppings_text,
                    note=it.note,
                ),
            )
            for it in data.items
        ]
        return KitchenOrder.from_order_data(
            public_id=data.public_id,
            status=data.status,
            customer_name=data.customer_name,
            phone=data.phone,
            address=data.address,
            note=data.note,
            delivery_type=data.delivery_type,
            scheduled_time=data.scheduled_time,
            total=data.total,
            items=items,
            created_at=data.created_at,
            now=now,
        )


# =============================================================================
# ConfigPinAuthService — PIN auth + rate limiting + JWT
# =============================================================================
# In-memory rate limit state (giữ nguyên pattern từ kds.py)
_pin_attempts: dict[str, list[float]] = {}
_PIN_MAX_ATTEMPTS = 5
_PIN_WINDOW_SECONDS = 300  # 5 minutes


class ConfigPinAuthService(PinAuthService):
    """
    Validate PIN từ settings.KDS_PIN, rate limit in-memory, issue JWT.

    TRƯỚC: 40 dòng auth + rate limit inline trong kds.py POST /kds/auth.
    SAU: Encapsulated trong service, testable, reusable.

    WHY in-memory rate limit (không phải Redis):
    - App nhỏ, 1 worker → in-memory đủ
    - KDS có 1-2 tablets → traffic rate limit minimal
    - Khi scale → thay bằng Redis implementation
    """

    async def authenticate(self, pin: str, client_ip: str) -> KdsAuthResult:
        # --- Rate limit check ---
        now = time.time()
        attempts = _pin_attempts.get(client_ip, [])
        # Remove old attempts outside window
        attempts = [t for t in attempts if now - t < _PIN_WINDOW_SECONDS]
        _pin_attempts[client_ip] = attempts

        if len(attempts) >= _PIN_MAX_ATTEMPTS:
            raise PermissionError(
                f"Quá nhiều lần thử. Vui lòng đợi {_PIN_WINDOW_SECONDS // 60} phút."
            )

        # --- PIN check ---
        if pin.strip() != settings.KDS_PIN:
            _pin_attempts.setdefault(client_ip, []).append(now)
            raise ValueError("PIN không đúng")

        # --- Issue JWT (reuse identity service) ---
        from app.identity.infrastructure.auth import token_service

        token = token_service.create_token(
            subject="kds",
            expires_delta=timedelta(hours=settings.KDS_TOKEN_EXPIRE_HOURS),
        )

        return KdsAuthResult(
            access_token=token,
            token_type="bearer",
            expires_in=settings.KDS_TOKEN_EXPIRE_HOURS * 3600,
        )
