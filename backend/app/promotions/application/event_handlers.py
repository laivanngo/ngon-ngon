"""
Promotions Context — Event Handlers
=======================================
Handlers broadcast flash sale events qua WebSocket.

Admin + KDS nhận real-time updates khi flash sale bắt đầu/cập nhật/kết thúc.
Customer frontend dùng polling-on-focus (không cần WS cho 4G phones).
"""

import logging

from app.promotions.domain.events import (
    FlashSaleActivated,
    FlashSaleClaimed,
    FlashSaleEnded,
)
from app.shared.ws_manager import ws_manager

logger = logging.getLogger("ngonngon.promotions.events")


async def on_flash_sale_activated(event: FlashSaleActivated) -> None:
    """Flash sale bắt đầu → broadcast tới admin panel."""
    await ws_manager._broadcast_raw(
        __import__("json").dumps({
            "type": "flash_sale_started",
            "data": {
                "sale_id": event.sale_id,
                "title": event.title,
                "product_id": event.product_id,
                "discount_percent": event.discount_percent,
                "ends_at": event.ends_at.isoformat(),
                "max_quantity": event.max_quantity,
            },
            "timestamp": event.occurred_at.isoformat(),
        })
    )
    logger.info(f"📡 Broadcast flash_sale_started #{event.sale_id}")


async def on_flash_sale_claimed(event: FlashSaleClaimed) -> None:
    """Claim update → broadcast remaining count."""
    await ws_manager._broadcast_raw(
        __import__("json").dumps({
            "type": "flash_sale_update",
            "data": {
                "sale_id": event.sale_id,
                "remaining": event.remaining,
                "is_sold_out": event.is_sold_out,
            },
            "timestamp": event.occurred_at.isoformat(),
        })
    )


async def on_flash_sale_ended(event: FlashSaleEnded) -> None:
    """Flash sale kết thúc → broadcast để ẩn banner."""
    await ws_manager._broadcast_raw(
        __import__("json").dumps({
            "type": "flash_sale_ended",
            "data": {
                "sale_id": event.sale_id,
                "reason": event.reason,
            },
            "timestamp": event.occurred_at.isoformat(),
        })
    )
    logger.info(f"📡 Broadcast flash_sale_ended #{event.sale_id} ({event.reason})")
