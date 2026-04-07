"""
Promotions Context — Flash Sale Scheduler
=============================================
Background async loop: tự động activate/end flash sales dựa trên thời gian.

Chạy mỗi 10 giây:
1. Tìm SCHEDULED sales đã tới starts_at → activate
2. Tìm ACTIVE sales đã hết ends_at → end

WHY 10s interval: Flash sale thường ngắn (5–60 phút). 30s quá chậm —
khách chờ tới 30s mới thấy banner. 10s đủ nhanh, overhead DB negligible
(2 lightweight queries mỗi 10s).

WHY background task thay vì cron:
- App chạy single process → asyncio task đủ nhẹ, đủ tin cậy
- Không cần thêm dependency (celery, APScheduler)
- Tích hợp event bus sẵn → broadcast WS ngay khi activate/end
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.promotions.application.flash_sale_use_cases import (
    ActivateScheduledSalesUseCase,
    EndExpiredSalesUseCase,
)
from app.promotions.infrastructure.flash_sale_repository import SqlFlashSaleRepository
from app.shared.events import EventBus

logger = logging.getLogger("ngonngon.promotions.scheduler")

TICK_INTERVAL_SECONDS = 10

# Consecutive failure tracking — alert ops khi scheduler gặp vấn đề liên tục
_MAX_CONSECUTIVE_FAILURES = 5


async def flash_sale_tick_loop(
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
) -> None:
    """
    Background loop — chạy liên tục, tick mỗi 10s.
    Gọi trong main.py lifespan: asyncio.create_task(flash_sale_tick_loop(...))
    """
    logger.info("⏰ Flash Sale scheduler started (interval: %ds)", TICK_INTERVAL_SECONDS)

    consecutive_failures = 0

    while True:
        try:
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
            await _tick(session_factory, event_bus)
            consecutive_failures = 0  # Reset on success
        except asyncio.CancelledError:
            logger.info("⏰ Flash Sale scheduler stopped")
            break
        except Exception as e:
            consecutive_failures += 1
            logger.error(
                f"⏰ Flash Sale scheduler error ({consecutive_failures}/"
                f"{_MAX_CONSECUTIVE_FAILURES}): {e}",
                exc_info=True,
            )

            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                logger.critical(
                    f"🚨 Flash Sale scheduler: {_MAX_CONSECUTIVE_FAILURES} "
                    f"consecutive failures — scheduler may be broken! "
                    f"Check DB connection and logs."
                )
                # Reset counter để không spam critical log
                consecutive_failures = 0


async def _tick(
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
) -> None:
    """Một tick: activate scheduled + end expired."""
    now = datetime.now(timezone.utc)

    async with session_factory() as db:
        repo = SqlFlashSaleRepository(db)

        activate_uc = ActivateScheduledSalesUseCase(repo, event_bus)
        activated = await activate_uc.execute(now)

        end_uc = EndExpiredSalesUseCase(repo, event_bus)
        ended = await end_uc.execute(now)

        if activated or ended:
            logger.info(
                f"⏰ Flash Sale tick: {activated} activated, {ended} ended"
            )
