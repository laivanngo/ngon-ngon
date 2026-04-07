"""
Catalog Application — Event Handlers
========================================
Handles events published by catalog commands.
Primary handler: broadcast menu changes via WebSocket.
"""

import logging

from app.catalog.domain.events import MenuChanged

logger = logging.getLogger("ngonngon.catalog.events")


async def on_menu_changed(event: MenuChanged) -> None:
    """
    Khi menu thay đổi → broadcast qua WebSocket để frontend invalidate cache.
    WHY fire-and-forget: nếu WS fail thì menu change vẫn đã lưu DB rồi.
    Frontend sẽ tự refresh sau TTL cache (5 phút).
    """
    try:
        from app.shared.ws_manager import ws_manager
        await ws_manager.broadcast_menu_update()
        logger.debug(f"📡 Menu change broadcasted: {event.change_type}")
    except Exception as e:
        logger.warning(f"WS broadcast failed for menu change: {e}")
