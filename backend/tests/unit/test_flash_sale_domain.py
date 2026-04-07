"""
Unit Tests — Flash Sale Domain Entity
=========================================
Test business rules của Flash Sale aggregate root:

- Tạo flash sale hợp lệ / không hợp lệ
- Status lifecycle (SCHEDULED → ACTIVE → ENDED / CANCELLED)
- Domain events phát ra đúng thời điểm
- Properties (remaining, is_sold_out)

Không cần database — test thuần logic nghiệp vụ.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.promotions.domain.flash_sale import FlashSale, FlashSaleStatus
from app.promotions.domain.events import (
    FlashSaleActivated,
    FlashSaleCreated,
    FlashSaleEnded,
)
from app.shared.exceptions import InvalidStatusTransitionError, ValidationError


# =============================================================================
# Helpers
# =============================================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_sale(**overrides) -> FlashSale:
    """Tạo Flash Sale mẫu, cho phép override bất kỳ field nào."""
    defaults = dict(
        title="Giảm 50% Trà Sữa",
        discount_percent=50,
        max_quantity=20,
        starts_at=_now() + timedelta(hours=1),
        ends_at=_now() + timedelta(hours=3),
        product_ids=[],
        subtitle="Chỉ hôm nay!",
    )
    defaults.update(overrides)
    return FlashSale.create(**defaults)


# =============================================================================
# Test: Factory Method — tạo flash sale
# =============================================================================

class TestFlashSaleCreate:

    def test_create_valid(self):
        sale = _create_sale()
        assert sale.title == "Giảm 50% Trà Sữa"
        assert sale.discount_percent == 50
        assert sale.max_quantity == 20
        assert sale.claimed_count == 0
        assert sale.status == FlashSaleStatus.SCHEDULED
        assert sale.product_ids == []

    def test_create_emits_event(self):
        sale = _create_sale()
        events = sale.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], FlashSaleCreated)
        assert events[0].title == "Giảm 50% Trà Sữa"

    def test_create_with_single_product(self):
        sale = _create_sale(product_ids=[42])
        assert sale.product_ids == [42]

    def test_create_with_multiple_products(self):
        sale = _create_sale(product_ids=[1, 2, 3])
        assert sale.product_ids == [1, 2, 3]
        assert len(sale.product_ids) == 3

    def test_create_discount_zero_raises(self):
        with pytest.raises(ValidationError, match="1-90%"):
            _create_sale(discount_percent=0)

    def test_create_discount_100_raises(self):
        with pytest.raises(ValidationError, match="1-90%"):
            _create_sale(discount_percent=100)

    def test_create_discount_negative_raises(self):
        with pytest.raises(ValidationError, match="1-90%"):
            _create_sale(discount_percent=-5)

    def test_create_max_quantity_zero_raises(self):
        with pytest.raises(ValidationError, match=">= 1"):
            _create_sale(max_quantity=0)

    def test_create_ends_before_starts_raises(self):
        now = _now()
        with pytest.raises(ValidationError, match="sau thời gian bắt đầu"):
            _create_sale(
                starts_at=now + timedelta(hours=3),
                ends_at=now + timedelta(hours=1),
            )

    def test_create_ends_equals_starts_raises(self):
        now = _now()
        with pytest.raises(ValidationError, match="sau thời gian bắt đầu"):
            _create_sale(starts_at=now, ends_at=now)

    def test_create_empty_title_raises(self):
        with pytest.raises(ValidationError, match="không được để trống"):
            _create_sale(title="")

    def test_create_whitespace_title_raises(self):
        with pytest.raises(ValidationError, match="không được để trống"):
            _create_sale(title="   ")

    def test_create_boundary_discount_1_percent(self):
        sale = _create_sale(discount_percent=1)
        assert sale.discount_percent == 1

    def test_create_boundary_discount_90_percent(self):
        sale = _create_sale(discount_percent=90)
        assert sale.discount_percent == 90


# =============================================================================
# Test: Status Transitions
# =============================================================================

class TestFlashSaleStatusTransitions:

    def test_activate_from_scheduled(self):
        sale = _create_sale()
        sale.collect_events()  # clear creation event
        sale.activate()
        assert sale.status == FlashSaleStatus.ACTIVE

        events = sale.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], FlashSaleActivated)
        assert events[0].discount_percent == 50

    def test_activate_from_active_raises(self):
        sale = _create_sale()
        sale.activate()
        with pytest.raises(InvalidStatusTransitionError):
            sale.activate()

    def test_activate_from_ended_raises(self):
        sale = _create_sale()
        sale.activate()
        sale.end("time_expired")
        with pytest.raises(InvalidStatusTransitionError):
            sale.activate()

    def test_end_from_active(self):
        sale = _create_sale()
        sale.activate()
        sale.collect_events()

        sale.end("time_expired")
        assert sale.status == FlashSaleStatus.ENDED

        events = sale.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], FlashSaleEnded)
        assert events[0].reason == "time_expired"

    def test_end_sold_out(self):
        sale = _create_sale()
        sale.activate()
        sale.collect_events()

        sale.end("sold_out")
        events = sale.collect_events()
        assert events[0].reason == "sold_out"

    def test_end_from_scheduled_raises(self):
        sale = _create_sale()
        with pytest.raises(InvalidStatusTransitionError):
            sale.end("time_expired")

    def test_cancel_from_scheduled(self):
        sale = _create_sale()
        sale.collect_events()

        sale.cancel()
        assert sale.status == FlashSaleStatus.CANCELLED

        events = sale.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], FlashSaleEnded)
        assert events[0].reason == "cancelled"

    def test_cancel_from_active(self):
        sale = _create_sale()
        sale.activate()
        sale.collect_events()

        sale.cancel()
        assert sale.status == FlashSaleStatus.CANCELLED

    def test_cancel_from_ended_raises(self):
        sale = _create_sale()
        sale.activate()
        sale.end("time_expired")
        with pytest.raises(InvalidStatusTransitionError):
            sale.cancel()

    def test_cancel_from_cancelled_raises(self):
        sale = _create_sale()
        sale.cancel()
        with pytest.raises(InvalidStatusTransitionError):
            sale.cancel()


# =============================================================================
# Test: Properties
# =============================================================================

class TestFlashSaleProperties:

    def test_remaining_full(self):
        sale = _create_sale(max_quantity=20)
        assert sale.remaining == 20

    def test_remaining_after_claims(self):
        sale = _create_sale(max_quantity=20)
        sale.claimed_count = 15
        assert sale.remaining == 5

    def test_remaining_zero(self):
        sale = _create_sale(max_quantity=20)
        sale.claimed_count = 20
        assert sale.remaining == 0

    def test_is_sold_out_false(self):
        sale = _create_sale(max_quantity=20)
        sale.claimed_count = 19
        assert sale.is_sold_out is False

    def test_is_sold_out_true(self):
        sale = _create_sale(max_quantity=20)
        sale.claimed_count = 20
        assert sale.is_sold_out is True

    def test_is_within_time_window(self):
        now = _now()
        sale = _create_sale(
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        assert sale.is_within_time_window(now) is True

    def test_is_not_within_time_window_before(self):
        now = _now()
        sale = _create_sale(
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=3),
        )
        assert sale.is_within_time_window(now) is False

    def test_is_not_within_time_window_after(self):
        now = _now()
        sale = _create_sale(
            starts_at=now - timedelta(hours=3),
            ends_at=now - timedelta(hours=1),
        )
        assert sale.is_within_time_window(now) is False

    def test_is_terminal_ended(self):
        assert FlashSaleStatus.ENDED.is_terminal is True

    def test_is_terminal_cancelled(self):
        assert FlashSaleStatus.CANCELLED.is_terminal is True

    def test_is_not_terminal_scheduled(self):
        assert FlashSaleStatus.SCHEDULED.is_terminal is False

    def test_is_not_terminal_active(self):
        assert FlashSaleStatus.ACTIVE.is_terminal is False


# =============================================================================
# Test: Event Collection
# =============================================================================

class TestFlashSaleEventCollection:

    def test_collect_events_clears_list(self):
        sale = _create_sale()
        events1 = sale.collect_events()
        events2 = sale.collect_events()
        assert len(events1) == 1
        assert len(events2) == 0

    def test_full_lifecycle_events(self):
        """SCHEDULED → ACTIVE → ENDED emits 3 events total."""
        sale = _create_sale()
        sale.activate()
        sale.end("time_expired")

        events = sale.collect_events()
        assert len(events) == 3
        assert isinstance(events[0], FlashSaleCreated)
        assert isinstance(events[1], FlashSaleActivated)
        assert isinstance(events[2], FlashSaleEnded)
