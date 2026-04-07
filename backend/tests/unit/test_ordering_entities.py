"""
Unit Tests — Order Entity (Aggregate Root)
=============================================
Order là "trái tim" của hệ thống — mỗi khi khách đặt hàng,
tất cả business rules được kiểm tra tại đây:

- Phải có ít nhất 1 món
- SĐT VN hợp lệ
- Tên + địa chỉ tự động chống hack (XSS)
- Tổng tiền = subtotal - discount (không âm)
- Chuyển trạng thái phải hợp lệ (không đi ngược)
- Mỗi thay đổi quan trọng → phát event thông báo

Không cần database — test thuần logic nghiệp vụ.
"""

import pytest
from app.ordering.domain.entities import Order, OrderItem
from app.ordering.domain.events import OrderPlaced, OrderStatusChanged
from app.ordering.domain.value_objects import OrderStatus


# =============================================================================
# Helpers — Tạo data mẫu cho test
# =============================================================================

def _sample_items(count: int = 1) -> list[OrderItem]:
    """Tạo danh sách OrderItem mẫu."""
    return [
        OrderItem(
            product_id=i + 1,
            product_name=f"Trà Sữa {i + 1}",
            size="L",
            sweetness="70%",
            ice_level="Ít đá",
            quantity=2,
            unit_price=25,
            toppings_text="Trân Châu",
            note=None,
        )
        for i in range(count)
    ]


def _place_order(**overrides) -> Order:
    """Tạo đơn hàng mẫu, cho phép override bất kỳ field nào."""
    defaults = dict(
        customer_name="Anh Minh",
        phone="0378148148",
        address="Cty Pouchen - Cổng B",
        note=None,
        delivery_type="immediate",
        scheduled_time=None,
        items=_sample_items(),
        subtotal=50,
        discount=0,
    )
    defaults.update(overrides)
    return Order.place(**defaults)


# =============================================================================
# OrderItem — Tính tiền từng dòng
# =============================================================================

class TestOrderItem:
    def test_line_total(self):
        """2 ly × 25k = 50k."""
        item = OrderItem(
            product_id=1, product_name="Trà Sữa", size="L",
            sweetness=None, ice_level=None, quantity=2,
            unit_price=25, toppings_text=None, note=None,
        )
        assert item.line_total == 50

    def test_line_total_single(self):
        """1 ly × 30k = 30k."""
        item = OrderItem(
            product_id=1, product_name="Matcha", size="XL",
            sweetness=None, ice_level=None, quantity=1,
            unit_price=30, toppings_text=None, note=None,
        )
        assert item.line_total == 30


# =============================================================================
# Order.place() — Tạo đơn hàng mới
# =============================================================================

class TestOrderPlace:
    """Kiểm tra factory method Order.place() — tạo đơn + validate."""

    def test_create_basic_order(self):
        """Tạo đơn bình thường → thành công."""
        order = _place_order()
        assert order.customer_name == "Anh Minh"
        assert order.phone == "0378148148"
        assert order.status == OrderStatus.PENDING
        assert order.total == 50
        assert len(order.items) == 1

    def test_public_id_is_uuid(self):
        """Mỗi đơn có 1 UUID riêng, không ai đoán được."""
        order = _place_order()
        assert len(order.public_id) == 36  # UUID v4 format
        assert "-" in order.public_id

    def test_two_orders_different_ids(self):
        """Hai đơn → hai UUID khác nhau."""
        o1 = _place_order()
        o2 = _place_order()
        assert o1.public_id != o2.public_id

    def test_created_at_set(self):
        """Thời gian tạo đơn → tự động gán."""
        order = _place_order()
        assert order.created_at is not None

    def test_initial_status_pending(self):
        """Đơn mới luôn bắt đầu ở trạng thái pending."""
        order = _place_order()
        assert order.status == OrderStatus.PENDING

    # --- Validate tên khách ---

    def test_customer_name_stripped(self):
        """Tên khách có khoảng trắng đầu/cuối → tự xóa."""
        order = _place_order(customer_name="  Chị Hương  ")
        assert order.customer_name == "Chị Hương"

    def test_customer_name_xss_stripped(self):
        """Tên khách chứa <script> → bị xóa tag, escape ký tự."""
        order = _place_order(customer_name='<script>alert(1)</script>Minh')
        assert "<script>" not in order.customer_name
        assert "Minh" in order.customer_name

    def test_customer_name_empty_rejected(self):
        """Tên rỗng → từ chối."""
        with pytest.raises(Exception):  # ValidationError
            _place_order(customer_name="")

    def test_customer_name_only_tags_rejected(self):
        """Tên chỉ gồm HTML tags → sau khi strip = rỗng → từ chối."""
        with pytest.raises(Exception):
            _place_order(customer_name="<b></b>")

    # --- Validate SĐT ---

    def test_valid_phone(self):
        """SĐT chuẩn VN → chấp nhận."""
        order = _place_order(phone="0901234567")
        assert order.phone == "0901234567"

    def test_phone_cleaned(self):
        """SĐT có dấu chấm → tự clean."""
        order = _place_order(phone="0378.148.148")
        assert order.phone == "0378148148"

    def test_invalid_phone_rejected(self):
        """SĐT sai format → từ chối."""
        with pytest.raises(ValueError, match="không hợp lệ"):
            _place_order(phone="12345")

    # --- Validate địa chỉ ---

    def test_address_xss_sanitized(self):
        """Địa chỉ chứa mã độc → bị sanitize."""
        order = _place_order(address='Test<img onerror=alert(1)>')
        assert "<img" not in order.address

    # --- Validate đơn hàng ---

    def test_empty_items_rejected(self):
        """Đơn không có món → từ chối."""
        with pytest.raises(Exception, match="ít nhất 1 món"):
            _place_order(items=[])

    def test_multiple_items(self):
        """Đơn 3 món → OK."""
        order = _place_order(items=_sample_items(3), subtotal=150)
        assert len(order.items) == 3

    # --- Validate delivery type ---

    def test_delivery_immediate(self):
        order = _place_order(delivery_type="immediate")
        assert order.delivery_type == "immediate"
        assert order.scheduled_time is None

    def test_delivery_scheduled(self):
        order = _place_order(
            delivery_type="scheduled", scheduled_time="12:00"
        )
        assert order.delivery_type == "scheduled"
        assert order.scheduled_time == "12:00"

    def test_delivery_scheduled_time_ignored_for_immediate(self):
        """Giao liền mà gửi scheduled_time → bị bỏ qua."""
        order = _place_order(
            delivery_type="immediate", scheduled_time="12:00"
        )
        assert order.scheduled_time is None

    def test_invalid_delivery_type_rejected(self):
        with pytest.raises(Exception, match="delivery_type"):
            _place_order(delivery_type="asap")

    # --- Tính tiền ---

    def test_total_equals_subtotal_minus_discount(self):
        """Tổng = subtotal - discount."""
        order = _place_order(subtotal=100, discount=10)
        assert order.total == 90

    def test_total_no_discount(self):
        """Không giảm giá → tổng = subtotal."""
        order = _place_order(subtotal=50, discount=0)
        assert order.total == 50

    def test_total_never_negative(self):
        """Giảm giá nhiều hơn subtotal → tổng = 0 (miễn phí)."""
        order = _place_order(subtotal=20, discount=50)
        assert order.total == 0

    # --- Note sanitization ---

    def test_note_sanitized(self):
        """Note chứa HTML → bị escape."""
        order = _place_order(note='<b>Ít đường</b>')
        assert "<b>" not in order.note

    def test_note_none_ok(self):
        """Không có note → OK."""
        order = _place_order(note=None)
        assert order.note is None

    # --- Event phát ra ---

    def test_order_placed_event_emitted(self):
        """Khi tạo đơn → phát 1 event OrderPlaced."""
        order = _place_order()
        events = order.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], OrderPlaced)

    def test_order_placed_event_data(self):
        """Event OrderPlaced chứa đủ thông tin đơn hàng."""
        order = _place_order(
            customer_name="Chị Hương", phone="0901234567", subtotal=50
        )
        event = order.collect_events()[0]
        assert event.customer_name == "Chị Hương"
        assert event.phone == "0901234567"
        assert event.total == 50
        assert event.item_count == 1
        assert event.delivery_type == "immediate"

    def test_collect_events_clears(self):
        """Sau khi collect → event list rỗng (không phát lại)."""
        order = _place_order()
        order.collect_events()
        assert order.collect_events() == []


# =============================================================================
# Order.change_status() — Chuyển trạng thái
# =============================================================================

class TestOrderChangeStatus:
    """Kiểm tra luồng chuyển trạng thái đơn hàng."""

    def test_pending_to_confirmed(self):
        """Xác nhận đơn → OK."""
        order = _place_order()
        order.collect_events()  # clear OrderPlaced
        order.change_status(OrderStatus.CONFIRMED)
        assert order.status == OrderStatus.CONFIRMED

    def test_status_change_emits_event(self):
        """Đổi trạng thái → phát event OrderStatusChanged."""
        order = _place_order()
        order.collect_events()  # clear
        order.change_status(OrderStatus.CONFIRMED, updated_by="admin")
        events = order.collect_events()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, OrderStatusChanged)
        assert evt.old_status == "pending"
        assert evt.new_status == "confirmed"
        assert evt.updated_by == "admin"

    def test_full_lifecycle(self):
        """Luồng hoàn chỉnh: pending → confirmed → preparing → delivering → done."""
        order = _place_order()
        order.collect_events()

        for status in [
            OrderStatus.CONFIRMED,
            OrderStatus.PREPARING,
            OrderStatus.DELIVERING,
            OrderStatus.DONE,
        ]:
            order.change_status(status)

        assert order.status == OrderStatus.DONE

    def test_skip_step_allowed(self):
        """Quán nhỏ: pending → delivering (skip 2 bước)."""
        order = _place_order()
        order.change_status(OrderStatus.DELIVERING)
        assert order.status == OrderStatus.DELIVERING

    def test_cancel_from_any_active_state(self):
        """Có thể hủy từ bất kỳ trạng thái nào (trước done)."""
        for start_status in [
            OrderStatus.PENDING,
            OrderStatus.CONFIRMED,
            OrderStatus.PREPARING,
            OrderStatus.DELIVERING,
        ]:
            order = _place_order()
            if start_status != OrderStatus.PENDING:
                order.change_status(start_status)
            order.change_status(OrderStatus.CANCELLED)
            assert order.status == OrderStatus.CANCELLED

    def test_backward_transition_rejected(self):
        """Không thể đi ngược: confirmed → pending."""
        order = _place_order()
        order.change_status(OrderStatus.CONFIRMED)
        with pytest.raises(Exception, match="Không thể chuyển"):
            order.change_status(OrderStatus.PENDING)

    def test_done_is_final(self):
        """Đã xong → không đổi được nữa."""
        order = _place_order()
        order.change_status(OrderStatus.DELIVERING)
        order.change_status(OrderStatus.DONE)
        with pytest.raises(Exception):
            order.change_status(OrderStatus.PENDING)

    def test_cancelled_is_final(self):
        """Đã hủy → không đổi được nữa."""
        order = _place_order()
        order.change_status(OrderStatus.CANCELLED)
        with pytest.raises(Exception):
            order.change_status(OrderStatus.CONFIRMED)

    def test_done_sets_completed_at(self):
        """Khi đơn done → ghi nhận thời gian hoàn thành."""
        order = _place_order()
        assert order.completed_at is None
        order.change_status(OrderStatus.DELIVERING)
        order.change_status(OrderStatus.DONE)
        assert order.completed_at is not None

    def test_non_done_status_no_completed_at(self):
        """Chưa done → completed_at vẫn None."""
        order = _place_order()
        order.change_status(OrderStatus.CONFIRMED)
        assert order.completed_at is None

    def test_multiple_status_changes_emit_multiple_events(self):
        """Mỗi lần đổi trạng thái → 1 event."""
        order = _place_order()
        order.collect_events()  # clear OrderPlaced

        order.change_status(OrderStatus.CONFIRMED)
        order.change_status(OrderStatus.PREPARING)

        events = order.collect_events()
        assert len(events) == 2
        assert events[0].new_status == "confirmed"
        assert events[1].new_status == "preparing"

    def test_change_status_tracks_updater(self):
        """Event ghi nhận ai đổi trạng thái (admin hay KDS)."""
        order = _place_order()
        order.collect_events()

        order.change_status(OrderStatus.CONFIRMED, updated_by="kds")
        event = order.collect_events()[0]
        assert event.updated_by == "kds"
