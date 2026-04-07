"""
Shared Kernel — In-Process Event Bus
======================================
WHY EventBus thay vì direct import giữa contexts:
- Ordering không cần biết Growth tồn tại (loose coupling)
- Catalog thay đổi menu → broadcast event, ai quan tâm thì subscribe
- Dễ thêm subscriber mới mà không sửa publisher

WHY in-process (không dùng Redis/RabbitMQ):
- App chạy single process → in-memory đủ nhanh, đủ tin cậy
- Khi scale multi-process → swap sang Redis Pub/Sub, interface giữ nguyên

PATTERN: Observer + async handlers
- Publisher: entity._events.append(SomeEvent(...))
- Use case: sau khi commit, gọi event_bus.publish_all(entity.events)
- Subscriber: event_bus.subscribe(SomeEvent, handler_fn)
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger("ngonngon.events")


# =============================================================================
# Base Event — tất cả domain events kế thừa từ đây
# =============================================================================
@dataclass
class DomainEvent:
    """
    Base class cho mọi domain event.
    occurred_at tự set → consumer biết event xảy ra khi nào.
    """
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# EventBus — singleton, wire tại main.py
# =============================================================================
# Type alias cho handler: async function nhận 1 DomainEvent
EventHandler = Callable[[Any], Coroutine[Any, Any, None]]


class EventBus:
    """
    In-process event bus. Subscribe handlers, publish events.
    Handlers chạy fire-and-forget: nếu 1 handler fail, các handler khác vẫn chạy.
    """

    def __init__(self):
        # dict[EventType] → list[handler_fn]
        self._handlers: dict[type, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        """Đăng ký handler cho 1 loại event."""
        self._handlers[event_type].append(handler)
        logger.debug(f"📡 Subscribed {handler.__name__} → {event_type.__name__}")

    async def publish(self, event: DomainEvent) -> None:
        """
        Phát 1 event → tất cả handlers đã subscribe sẽ được gọi.
        Fire-and-forget: handler fail không ảnh hưởng flow chính.
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                # Log nhưng KHÔNG raise — event handler fail không nên break main flow
                logger.error(
                    f"Event handler {handler.__name__} failed for {event_type.__name__}: {e}",
                    exc_info=True,
                )

    async def publish_all(self, events: list[DomainEvent]) -> None:
        """Publish một batch events (thường là entity._events sau khi commit)."""
        for event in events:
            await self.publish(event)


# Singleton instance — import từ đây
event_bus = EventBus()
