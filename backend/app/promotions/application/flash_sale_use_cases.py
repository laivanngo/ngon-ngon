"""
Promotions Context — Flash Sale Use Cases
=============================================
Orchestration logic cho Flash Sale feature.

Use cases:
- CreateFlashSaleUseCase: admin tạo flash sale mới
- ListFlashSalesUseCase: admin xem danh sách
- GetActiveFlashSalesUseCase: customer lấy flash sales đang chạy
- CancelFlashSaleUseCase: admin hủy flash sale
- ActivateScheduledSalesUseCase: background task activate sales đến giờ
- EndExpiredSalesUseCase: background task end sales hết giờ
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.promotions.domain.flash_sale import FlashSale, FlashSaleRepository
from app.shared.events import EventBus
from app.shared.exceptions import NotFoundError

logger = logging.getLogger("ngonngon.promotions.flash_sale")


# =============================================================================
# POST /flash-sales — Admin tạo flash sale
# =============================================================================
class CreateFlashSaleUseCase:
    """Tạo Flash Sale mới. Validate → persist → publish event."""

    def __init__(self, repo: FlashSaleRepository, event_bus: EventBus) -> None:
        self._repo = repo
        self._event_bus = event_bus

    async def execute(
        self,
        title: str,
        discount_percent: int,
        max_quantity: int,
        starts_at: datetime,
        ends_at: datetime,
        product_ids: list[int] | None = None,
        subtitle: str | None = None,
        admin_username: str = "system",
    ) -> FlashSale:
        sale = FlashSale.create(
            title=title,
            discount_percent=discount_percent,
            max_quantity=max_quantity,
            starts_at=starts_at,
            ends_at=ends_at,
            product_ids=product_ids,
            subtitle=subtitle,
        )

        sale = await self._repo.save(sale)

        logger.info(
            f"🎯 Flash Sale created: #{sale.id} '{sale.title}' "
            f"({sale.discount_percent}% off, {sale.max_quantity} slots) "
            f"by {admin_username}"
        )

        events = sale.collect_events()
        await self._event_bus.publish_all(events)

        return sale


# =============================================================================
# GET /flash-sales — Admin xem danh sách
# =============================================================================
class ListFlashSalesUseCase:
    """Danh sách tất cả flash sales (admin view, paginated)."""

    def __init__(self, repo: FlashSaleRepository) -> None:
        self._repo = repo

    async def execute(
        self, limit: int = 20, offset: int = 0,
    ) -> tuple[list[FlashSale], int]:
        return await self._repo.list_all(limit=limit, offset=offset)


# =============================================================================
# GET /flash-sales/active — Customer lấy flash sales đang chạy
# =============================================================================
class GetActiveFlashSalesUseCase:
    """Trả về flash sales đang ACTIVE cho customer banner."""

    def __init__(self, repo: FlashSaleRepository) -> None:
        self._repo = repo

    async def execute(self, now: datetime) -> list[FlashSale]:
        return await self._repo.find_active(now)


# =============================================================================
# PATCH /flash-sales/{id}/cancel — Admin hủy
# =============================================================================
class CancelFlashSaleUseCase:
    """Hủy flash sale. Transition → CANCELLED → publish event."""

    def __init__(self, repo: FlashSaleRepository, event_bus: EventBus) -> None:
        self._repo = repo
        self._event_bus = event_bus

    async def execute(self, sale_id: int, admin_username: str = "system") -> FlashSale:
        sale = await self._repo.find_by_id(sale_id)
        if not sale:
            raise NotFoundError("Flash Sale", str(sale_id))

        sale.cancel()
        await self._repo.save(sale)

        logger.info(f"🚫 Flash Sale #{sale_id} cancelled by {admin_username}")

        events = sale.collect_events()
        await self._event_bus.publish_all(events)

        return sale


# =============================================================================
# Background: Activate SCHEDULED sales đến giờ
# =============================================================================
class ActivateScheduledSalesUseCase:
    """Tìm SCHEDULED sales đã tới starts_at → activate → publish events."""

    def __init__(self, repo: FlashSaleRepository, event_bus: EventBus) -> None:
        self._repo = repo
        self._event_bus = event_bus

    async def execute(self, now: datetime) -> int:
        """Return số lượng sales đã activate."""
        sales = await self._repo.find_scheduled_ready(now)
        count = 0

        for sale in sales:
            sale.activate()
            await self._repo.save(sale)
            events = sale.collect_events()
            await self._event_bus.publish_all(events)
            count += 1
            logger.info(f"🟢 Flash Sale #{sale.id} '{sale.title}' activated")

        return count


# =============================================================================
# Background: End ACTIVE sales hết giờ
# =============================================================================
class EndExpiredSalesUseCase:
    """Tìm ACTIVE sales đã hết giờ (ends_at <= now) → end → publish events."""

    def __init__(self, repo: FlashSaleRepository, event_bus: EventBus) -> None:
        self._repo = repo
        self._event_bus = event_bus

    async def execute(self, now: datetime) -> int:
        """Return số lượng sales đã end."""
        sales = await self._repo.find_active_expired(now)
        count = 0

        for sale in sales:
            sale.end("time_expired")
            await self._repo.save(sale)
            events = sale.collect_events()
            await self._event_bus.publish_all(events)
            count += 1
            logger.info(f"🔴 Flash Sale #{sale.id} '{sale.title}' ended (time expired)")

        return count
