"""
Ordering Context — Event Handlers
=====================================
Handlers cho OrderPlaced và OrderStatusChanged events.

HANDLERS Ở ĐÂY:
- on_order_placed_broadcast_ws: broadcast đơn mới qua WebSocket
- on_status_changed_broadcast_ws: broadcast status change qua WebSocket

HANDLERS ĐÃ MIGRATE SANG GROWTH CONTEXT (Phase 4):
- on_order_placed_track_customer → growth/application/event_handlers.py

WHY WS broadcast ở ordering (không phải shared):
- Ordering phát event → ordering biết data format của event
- WS broadcast đính kèm order data (public_id, customer_name, total...)
- Nếu cần tách → move sang notification context tương lai
"""

import logging

from app.ordering.domain.events import OrderPlaced, OrderStatusChanged

logger = logging.getLogger("ngonngon.ordering.events")


# =============================================================================
# WS Broadcast — subscribe to OrderPlaced + OrderStatusChanged
# =============================================================================
async def on_order_placed_broadcast_ws(event: OrderPlaced) -> None:
    """
    Broadcast đơn hàng mới tới admin panel qua WebSocket.
    Fire-and-forget: đơn đã lưu DB, WS là bonus.
    """
    try:
        from app.shared.ws_manager import ws_manager

        await ws_manager.broadcast_new_order({
            "public_id": event.public_id,
            "customer_name": event.customer_name,
            "phone": event.phone,
            "address": event.address,
            "total": event.total,
            "item_count": event.item_count,
            "status": "pending",
            "delivery_type": event.delivery_type,
            "scheduled_time": event.scheduled_time,
            "estimated_minutes": event.estimated_minutes,
        })
    except Exception as e:
        logger.warning(f"WS broadcast failed (order still saved): {e}")


async def on_status_changed_broadcast_ws(event: OrderStatusChanged) -> None:
    """Broadcast status change tới admin + KDS qua WebSocket."""
    try:
        from app.shared.ws_manager import ws_manager

        await ws_manager.broadcast_status_change({
            "public_id": event.public_id,
            "old_status": event.old_status,
            "new_status": event.new_status,
            "updated_by": event.updated_by,
        })
    except Exception as e:
        logger.warning(f"WS broadcast failed: {e}")
