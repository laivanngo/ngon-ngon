"""
Unit Tests — Kitchen Domain + Shared Kernel
=============================================
Kitchen:
- KitchenOrder: projection (view) cho màn hình bếp (KDS)
- format_item_details: hiển thị "Size L • 70% đường • Ít đá"
- Tính elapsed_seconds (bếp cần biết đơn chờ bao lâu)

Shared:
- EventBus: publisher/subscriber pattern (loose coupling giữa contexts)
- Domain exceptions: lỗi nghiệp vụ → HTTP status codes phù hợp

Không cần database.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta

from app.kitchen.domain.entities import KitchenOrder, KitchenOrderItem
from app.shared.events import EventBus, DomainEvent
from app.shared.exceptions import (
    DomainError, NotFoundError, ValidationError,
    DuplicateError, InvalidStatusTransitionError,
)


# =============================================================================
# KitchenOrder — Màn hình bếp
# =============================================================================

class TestKitchenOrderFormatDetails:
    """Format chi tiết món cho bếp xem nhanh."""

    def test_full_details(self):
        """Đầy đủ thông tin: Size L • 70% đường • Ít đá • Trân Châu."""
        result = KitchenOrder.format_item_details(
            size="L", sweetness="70%", ice_level="Ít đá",
            toppings_text="Trân Châu", note=None,
        )
        assert "Size L" in result
        assert "70%" in result
        assert "Ít đá" in result
        assert "Trân Châu" in result
        assert " • " in result  # ngăn cách bằng dấu •

    def test_partial_details(self):
        """Chỉ có size → hiển thị mỗi size."""
        result = KitchenOrder.format_item_details(
            size="M", sweetness=None, ice_level=None,
            toppings_text=None, note=None,
        )
        assert result == "Size M"

    def test_empty_details(self):
        """Không có gì → chuỗi rỗng."""
        result = KitchenOrder.format_item_details(
            size=None, sweetness=None, ice_level=None,
            toppings_text=None, note=None,
        )
        assert result == ""

    def test_note_with_emoji(self):
        """Note khách ghi → hiển thị kèm emoji 📝."""
        result = KitchenOrder.format_item_details(
            size=None, sweetness=None, ice_level=None,
            toppings_text=None, note="Ít đường",
        )
        assert "📝" in result
        assert "Ít đường" in result


class TestKitchenOrderFromData:
    """Tạo KitchenOrder từ raw data + tính timer."""

    def _make_items(self):
        return [
            KitchenOrderItem(
                name="Trà Sữa", quantity=2, unit_price=25,
                details="Size L • 70% đường",
            )
        ]

    def test_basic_creation(self):
        now = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created = datetime(2025, 1, 15, 10, 25, 0, tzinfo=timezone.utc)

        ko = KitchenOrder.from_order_data(
            public_id="abc-123", status="preparing",
            customer_name="Minh", phone="0378148148",
            address="Cổng B", note=None,
            delivery_type="immediate", scheduled_time=None,
            total=50, items=self._make_items(),
            created_at=created, now=now,
        )
        assert ko.public_id == "abc-123"
        assert ko.status == "preparing"
        assert ko.item_count == 1

    def test_elapsed_seconds(self):
        """Timer: đơn tạo lúc 10:25, bây giờ 10:30 → 300 giây."""
        now = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created = datetime(2025, 1, 15, 10, 25, 0, tzinfo=timezone.utc)

        ko = KitchenOrder.from_order_data(
            public_id="abc-123", status="pending",
            customer_name="Minh", phone="0378148148",
            address="Cổng B", note=None,
            delivery_type="immediate", scheduled_time=None,
            total=50, items=self._make_items(),
            created_at=created, now=now,
        )
        assert ko.elapsed_seconds == 300  # 5 phút = 300 giây

    def test_naive_datetime_treated_as_utc(self):
        """created_at không có timezone → coi như UTC."""
        now = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        created = datetime(2025, 1, 15, 10, 28, 0)  # naive, no tz

        ko = KitchenOrder.from_order_data(
            public_id="abc-123", status="pending",
            customer_name="Minh", phone="0378148148",
            address="Cổng B", note=None,
            delivery_type="immediate", scheduled_time=None,
            total=50, items=self._make_items(),
            created_at=created, now=now,
        )
        assert ko.elapsed_seconds == 120  # 2 phút

    def test_default_delivery_type(self):
        """delivery_type None → fallback 'immediate'."""
        ko = KitchenOrder.from_order_data(
            public_id="abc-123", status="pending",
            customer_name="Minh", phone="0378148148",
            address="Cổng B", note=None,
            delivery_type=None, scheduled_time=None,
            total=50, items=self._make_items(),
            created_at=datetime.now(timezone.utc),
        )
        assert ko.delivery_type == "immediate"

    def test_created_at_iso_format(self):
        """created_at trong KitchenOrder → ISO string."""
        created = datetime(2025, 1, 15, 10, 25, 0, tzinfo=timezone.utc)
        ko = KitchenOrder.from_order_data(
            public_id="abc-123", status="pending",
            customer_name="Minh", phone="0378148148",
            address="Cổng B", note=None,
            delivery_type="immediate", scheduled_time=None,
            total=50, items=self._make_items(),
            created_at=created,
        )
        assert "2025-01-15" in ko.created_at


# =============================================================================
# EventBus — Giao tiếp giữa các context
# =============================================================================

class TestEventBus:
    """
    EventBus: khi Ordering tạo đơn mới → phát event
    → Growth lắng nghe để cập nhật customer
    → WebSocket lắng nghe để push real-time
    Hai bên không biết nhau.
    """

    def test_subscribe_and_publish(self):
        """Subscribe handler → publish event → handler được gọi."""
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe(DomainEvent, handler)
        asyncio.get_event_loop().run_until_complete(
            bus.publish(DomainEvent())
        )
        assert len(received) == 1

    def test_multiple_subscribers(self):
        """1 event type → nhiều subscriber → tất cả đều nhận."""
        bus = EventBus()
        calls = {"a": 0, "b": 0}

        async def handler_a(event):
            calls["a"] += 1

        async def handler_b(event):
            calls["b"] += 1

        bus.subscribe(DomainEvent, handler_a)
        bus.subscribe(DomainEvent, handler_b)
        asyncio.get_event_loop().run_until_complete(
            bus.publish(DomainEvent())
        )
        assert calls["a"] == 1
        assert calls["b"] == 1

    def test_no_subscribers_no_error(self):
        """Phát event mà không ai subscribe → không lỗi."""
        bus = EventBus()
        asyncio.get_event_loop().run_until_complete(
            bus.publish(DomainEvent())
        )

    def test_handler_error_does_not_break_others(self):
        """1 handler lỗi → các handler khác vẫn chạy bình thường."""
        bus = EventBus()
        calls = []

        async def bad_handler(event):
            raise RuntimeError("boom")

        async def good_handler(event):
            calls.append("ok")

        bus.subscribe(DomainEvent, bad_handler)
        bus.subscribe(DomainEvent, good_handler)
        asyncio.get_event_loop().run_until_complete(
            bus.publish(DomainEvent())
        )
        assert calls == ["ok"]  # good_handler vẫn chạy

    def test_publish_all(self):
        """Publish batch events."""
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe(DomainEvent, handler)
        asyncio.get_event_loop().run_until_complete(
            bus.publish_all([DomainEvent(), DomainEvent(), DomainEvent()])
        )
        assert len(received) == 3

    def test_different_event_types_isolated(self):
        """Subscribe type A → chỉ nhận event type A, không nhận type B."""
        bus = EventBus()
        received_a = []
        received_b = []

        class EventA(DomainEvent):
            pass

        class EventB(DomainEvent):
            pass

        async def handler_a(event):
            received_a.append(event)

        async def handler_b(event):
            received_b.append(event)

        bus.subscribe(EventA, handler_a)
        bus.subscribe(EventB, handler_b)

        asyncio.get_event_loop().run_until_complete(bus.publish(EventA()))
        assert len(received_a) == 1
        assert len(received_b) == 0


# =============================================================================
# Domain Exceptions — Lỗi nghiệp vụ
# =============================================================================

class TestDomainExceptions:
    """
    Mỗi exception → HTTP status code cụ thể:
    - NotFoundError → 404
    - ValidationError → 400
    - DuplicateError → 409
    - InvalidStatusTransitionError → 400
    """

    def test_not_found_error(self):
        err = NotFoundError("Đơn hàng")
        assert "Đơn hàng" in err.message
        assert err.code == "NOT_FOUND"

    def test_not_found_with_identifier(self):
        err = NotFoundError("Sản phẩm", "ts1")
        assert "ts1" in err.message

    def test_validation_error(self):
        err = ValidationError("SĐT không đúng format")
        assert "SĐT" in err.message
        assert err.code == "VALIDATION_ERROR"

    def test_duplicate_error(self):
        err = DuplicateError("Danh mục", "tra-sua")
        assert "tra-sua" in err.message
        assert err.code == "DUPLICATE"

    def test_invalid_status_transition(self):
        """Thông báo lỗi chỉ rõ: từ đâu, đến đâu, cho phép đi đâu."""
        err = InvalidStatusTransitionError(
            current="done", target="pending",
            allowed=[],
        )
        assert "done" in err.message
        assert "pending" in err.message
        assert err.code == "INVALID_STATUS_TRANSITION"

    def test_invalid_transition_shows_allowed(self):
        err = InvalidStatusTransitionError(
            current="pending", target="done",
            allowed=["confirmed", "preparing", "delivering", "cancelled"],
        )
        assert "confirmed" in err.message

    def test_all_inherit_from_domain_error(self):
        """Tất cả lỗi nghiệp vụ đều kế thừa DomainError → catch chung được."""
        for exc_class in [NotFoundError, ValidationError, DuplicateError]:
            assert issubclass(exc_class, DomainError)
