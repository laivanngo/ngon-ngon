"""
Unit Tests — Flash Sale Use Cases
=====================================
Test orchestration logic: Create, Cancel, Activate, End.

Dùng FakeFlashSaleRepository (in-memory) — không cần DB.
Dùng EventBus thật (in-process) — verify events published.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.promotions.application.flash_sale_use_cases import (
    ActivateScheduledSalesUseCase,
    CancelFlashSaleUseCase,
    CreateFlashSaleUseCase,
    EndExpiredSalesUseCase,
    GetActiveFlashSalesUseCase,
    ListFlashSalesUseCase,
)
from app.promotions.domain.flash_sale import FlashSale, FlashSaleRepository, FlashSaleStatus
from app.promotions.domain.events import FlashSaleActivated, FlashSaleClaimed, FlashSaleCreated, FlashSaleEnded
from app.shared.events import EventBus
from app.shared.exceptions import NotFoundError, ValidationError


# =============================================================================
# Fake Repository — in-memory
# =============================================================================

class FakeFlashSaleRepository(FlashSaleRepository):
    """In-memory repository cho unit tests."""

    def __init__(self) -> None:
        self._sales: dict[int, FlashSale] = {}
        self._next_id = 1

    async def save(self, sale: FlashSale) -> FlashSale:
        if sale.id is None:
            sale.id = self._next_id
            sale.created_at = datetime.now(timezone.utc)
            self._next_id += 1
        self._sales[sale.id] = sale
        return sale

    async def find_by_id(self, sale_id: int) -> FlashSale | None:
        return self._sales.get(sale_id)

    async def find_active(self, now: datetime) -> list[FlashSale]:
        return [
            s for s in self._sales.values()
            if s.status == FlashSaleStatus.ACTIVE
            and s.starts_at <= now < s.ends_at
        ]

    async def find_scheduled_ready(self, now: datetime) -> list[FlashSale]:
        return [
            s for s in self._sales.values()
            if s.status == FlashSaleStatus.SCHEDULED
            and s.starts_at <= now
        ]

    async def find_active_expired(self, now: datetime) -> list[FlashSale]:
        return [
            s for s in self._sales.values()
            if s.status == FlashSaleStatus.ACTIVE
            and s.ends_at <= now
        ]

    async def list_all(
        self, limit: int = 20, offset: int = 0,
    ) -> tuple[list[FlashSale], int]:
        all_sales = sorted(
            self._sales.values(),
            key=lambda s: s.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return all_sales[offset:offset + limit], len(all_sales)

    async def claim_atomically(self, sale_id: int) -> int | None:
        sale = self._sales.get(sale_id)
        if not sale or sale.status != FlashSaleStatus.ACTIVE:
            return None
        if sale.claimed_count >= sale.max_quantity:
            return None
        sale.claimed_count += 1
        return sale.claimed_count


# =============================================================================
# Helpers
# =============================================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_deps() -> tuple[FakeFlashSaleRepository, EventBus]:
    return FakeFlashSaleRepository(), EventBus()


# =============================================================================
# Test: CreateFlashSaleUseCase
# =============================================================================

class TestCreateFlashSale:

    @pytest.mark.asyncio
    async def test_create_success(self):
        repo, bus = _make_deps()
        uc = CreateFlashSaleUseCase(repo, bus)

        sale = await uc.execute(
            title="Giảm 50%",
            discount_percent=50,
            max_quantity=20,
            starts_at=_now() + timedelta(hours=1),
            ends_at=_now() + timedelta(hours=3),
        )

        assert sale.id == 1
        assert sale.title == "Giảm 50%"
        assert sale.status == FlashSaleStatus.SCHEDULED

        # Verify persisted
        saved = await repo.find_by_id(1)
        assert saved is not None
        assert saved.title == "Giảm 50%"

    @pytest.mark.asyncio
    async def test_create_with_product_ids(self):
        repo, bus = _make_deps()
        uc = CreateFlashSaleUseCase(repo, bus)

        sale = await uc.execute(
            title="Giảm 30% Trà Sữa + Cà Phê",
            discount_percent=30,
            max_quantity=10,
            starts_at=_now() + timedelta(hours=1),
            ends_at=_now() + timedelta(hours=2),
            product_ids=[42, 43],
        )

        assert sale.product_ids == [42, 43]

    @pytest.mark.asyncio
    async def test_create_invalid_discount_raises(self):
        repo, bus = _make_deps()
        uc = CreateFlashSaleUseCase(repo, bus)

        with pytest.raises(ValidationError):
            await uc.execute(
                title="Bad Sale",
                discount_percent=100,
                max_quantity=10,
                starts_at=_now() + timedelta(hours=1),
                ends_at=_now() + timedelta(hours=2),
            )

    @pytest.mark.asyncio
    async def test_create_publishes_event(self):
        repo, bus = _make_deps()
        published = []
        bus.subscribe(type(None), lambda e: None)  # dummy

        # Track events via custom handler
        from app.promotions.domain.events import FlashSaleCreated
        bus.subscribe(FlashSaleCreated, lambda e: published.append(e))

        uc = CreateFlashSaleUseCase(repo, bus)
        await uc.execute(
            title="Event Test",
            discount_percent=20,
            max_quantity=5,
            starts_at=_now() + timedelta(hours=1),
            ends_at=_now() + timedelta(hours=2),
        )

        assert len(published) == 1
        assert published[0].title == "Event Test"


# =============================================================================
# Test: CancelFlashSaleUseCase
# =============================================================================

class TestCancelFlashSale:

    @pytest.mark.asyncio
    async def test_cancel_success(self):
        repo, bus = _make_deps()
        create_uc = CreateFlashSaleUseCase(repo, bus)
        sale = await create_uc.execute(
            title="To Cancel",
            discount_percent=50,
            max_quantity=20,
            starts_at=_now() + timedelta(hours=1),
            ends_at=_now() + timedelta(hours=3),
        )

        cancel_uc = CancelFlashSaleUseCase(repo, bus)
        cancelled = await cancel_uc.execute(sale.id, admin_username="admin")

        assert cancelled.status == FlashSaleStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_raises(self):
        repo, bus = _make_deps()
        cancel_uc = CancelFlashSaleUseCase(repo, bus)

        with pytest.raises(NotFoundError):
            await cancel_uc.execute(999)


# =============================================================================
# Test: GetActiveFlashSalesUseCase
# =============================================================================

class TestGetActiveFlashSales:

    @pytest.mark.asyncio
    async def test_returns_active_sales(self):
        repo, bus = _make_deps()
        now = _now()

        # Create and manually activate a sale
        sale = FlashSale.create(
            title="Active Sale",
            discount_percent=40,
            max_quantity=10,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        sale.activate()
        sale.collect_events()
        await repo.save(sale)

        uc = GetActiveFlashSalesUseCase(repo)
        active = await uc.execute(now)

        assert len(active) == 1
        assert active[0].title == "Active Sale"

    @pytest.mark.asyncio
    async def test_excludes_scheduled_sales(self):
        repo, bus = _make_deps()
        now = _now()

        sale = FlashSale.create(
            title="Future Sale",
            discount_percent=40,
            max_quantity=10,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=3),
        )
        sale.collect_events()
        await repo.save(sale)

        uc = GetActiveFlashSalesUseCase(repo)
        active = await uc.execute(now)

        assert len(active) == 0


# =============================================================================
# Test: ActivateScheduledSalesUseCase
# =============================================================================

class TestActivateScheduledSales:

    @pytest.mark.asyncio
    async def test_activates_ready_sales(self):
        repo, bus = _make_deps()
        now = _now()

        sale = FlashSale.create(
            title="Ready Sale",
            discount_percent=30,
            max_quantity=5,
            starts_at=now - timedelta(minutes=5),
            ends_at=now + timedelta(hours=2),
        )
        sale.collect_events()
        await repo.save(sale)

        uc = ActivateScheduledSalesUseCase(repo, bus)
        count = await uc.execute(now)

        assert count == 1
        saved = await repo.find_by_id(sale.id)
        assert saved.status == FlashSaleStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_skips_future_sales(self):
        repo, bus = _make_deps()
        now = _now()

        sale = FlashSale.create(
            title="Future Sale",
            discount_percent=30,
            max_quantity=5,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=3),
        )
        sale.collect_events()
        await repo.save(sale)

        uc = ActivateScheduledSalesUseCase(repo, bus)
        count = await uc.execute(now)

        assert count == 0


# =============================================================================
# Test: EndExpiredSalesUseCase
# =============================================================================

class TestEndExpiredSales:

    @pytest.mark.asyncio
    async def test_ends_expired_sales(self):
        repo, bus = _make_deps()
        now = _now()

        sale = FlashSale.create(
            title="Expired Sale",
            discount_percent=20,
            max_quantity=10,
            starts_at=now - timedelta(hours=3),
            ends_at=now - timedelta(minutes=5),
        )
        sale.activate()
        sale.collect_events()
        await repo.save(sale)

        uc = EndExpiredSalesUseCase(repo, bus)
        count = await uc.execute(now)

        assert count == 1
        saved = await repo.find_by_id(sale.id)
        assert saved.status == FlashSaleStatus.ENDED

    @pytest.mark.asyncio
    async def test_skips_still_active_sales(self):
        repo, bus = _make_deps()
        now = _now()

        sale = FlashSale.create(
            title="Still Active",
            discount_percent=20,
            max_quantity=10,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        sale.activate()
        sale.collect_events()
        await repo.save(sale)

        uc = EndExpiredSalesUseCase(repo, bus)
        count = await uc.execute(now)

        assert count == 0


# =============================================================================
# Test: ListFlashSalesUseCase
# =============================================================================

class TestListFlashSales:

    @pytest.mark.asyncio
    async def test_list_with_pagination(self):
        repo, bus = _make_deps()
        create_uc = CreateFlashSaleUseCase(repo, bus)

        for i in range(5):
            await create_uc.execute(
                title=f"Sale {i}",
                discount_percent=10 + i * 10,
                max_quantity=10,
                starts_at=_now() + timedelta(hours=1),
                ends_at=_now() + timedelta(hours=3),
            )

        list_uc = ListFlashSalesUseCase(repo)
        sales, total = await list_uc.execute(limit=2, offset=0)

        assert total == 5
        assert len(sales) == 2


# =============================================================================
# Test: claim_atomically (T1 — trực tiếp test FakeRepo claim)
# =============================================================================

class TestClaimAtomically:

    @pytest.mark.asyncio
    async def test_claim_increments_count(self):
        """Claim thành công → claimed_count tăng 1, trả về count mới."""
        repo, bus = _make_deps()
        now = _now()

        sale = FlashSale.create(
            title="Claimable", discount_percent=30,
            max_quantity=5,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        sale.activate()
        sale.collect_events()
        await repo.save(sale)

        result = await repo.claim_atomically(sale.id)

        assert result == 1
        saved = await repo.find_by_id(sale.id)
        assert saved.claimed_count == 1

    @pytest.mark.asyncio
    async def test_claim_multiple_times(self):
        """Claim 3 lần liên tiếp → claimed_count = 3."""
        repo, bus = _make_deps()
        now = _now()

        sale = FlashSale.create(
            title="Multi Claim", discount_percent=20,
            max_quantity=10,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        sale.activate()
        sale.collect_events()
        await repo.save(sale)

        for expected in [1, 2, 3]:
            result = await repo.claim_atomically(sale.id)
            assert result == expected

        saved = await repo.find_by_id(sale.id)
        assert saved.claimed_count == 3

    @pytest.mark.asyncio
    async def test_claim_at_max_returns_none(self):
        """Claim khi đã hết suất → trả về None."""
        repo, bus = _make_deps()
        now = _now()

        sale = FlashSale.create(
            title="Full Sale", discount_percent=50,
            max_quantity=2,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        sale.activate()
        sale.collect_events()
        await repo.save(sale)

        # Claim 2 suất
        assert await repo.claim_atomically(sale.id) == 1
        assert await repo.claim_atomically(sale.id) == 2

        # Suất thứ 3 → None (hết)
        assert await repo.claim_atomically(sale.id) is None

    @pytest.mark.asyncio
    async def test_claim_non_active_returns_none(self):
        """Claim khi sale chưa active (SCHEDULED) → None."""
        repo, bus = _make_deps()

        sale = FlashSale.create(
            title="Not Active", discount_percent=30,
            max_quantity=10,
            starts_at=_now() + timedelta(hours=1),
            ends_at=_now() + timedelta(hours=2),
        )
        sale.collect_events()
        await repo.save(sale)

        assert await repo.claim_atomically(sale.id) is None

    @pytest.mark.asyncio
    async def test_claim_nonexistent_returns_none(self):
        """Claim sale_id không tồn tại → None."""
        repo, bus = _make_deps()
        assert await repo.claim_atomically(999) is None


# =============================================================================
# Test: Event publishing cho Activate, Cancel, End (T2)
# =============================================================================

class TestEventPublishing:

    @pytest.mark.asyncio
    async def test_activate_publishes_flash_sale_activated(self):
        """ActivateScheduledSalesUseCase → FlashSaleActivated event."""
        repo, bus = _make_deps()
        now = _now()
        published: list[FlashSaleActivated] = []
        bus.subscribe(FlashSaleActivated, lambda e: published.append(e))

        sale = FlashSale.create(
            title="Activate Me", discount_percent=40,
            max_quantity=10,
            starts_at=now - timedelta(minutes=5),
            ends_at=now + timedelta(hours=2),
        )
        sale.collect_events()  # Clear FlashSaleCreated
        await repo.save(sale)

        uc = ActivateScheduledSalesUseCase(repo, bus)
        await uc.execute(now)

        assert len(published) == 1
        assert published[0].title == "Activate Me"
        assert published[0].discount_percent == 40
        assert published[0].max_quantity == 10

    @pytest.mark.asyncio
    async def test_cancel_publishes_flash_sale_ended(self):
        """CancelFlashSaleUseCase → FlashSaleEnded(reason='cancelled')."""
        repo, bus = _make_deps()
        published: list[FlashSaleEnded] = []
        bus.subscribe(FlashSaleEnded, lambda e: published.append(e))

        sale = FlashSale.create(
            title="Cancel Me", discount_percent=50,
            max_quantity=20,
            starts_at=_now() + timedelta(hours=1),
            ends_at=_now() + timedelta(hours=3),
        )
        sale.collect_events()
        await repo.save(sale)

        cancel_uc = CancelFlashSaleUseCase(repo, bus)
        await cancel_uc.execute(sale.id, admin_username="admin")

        assert len(published) == 1
        assert published[0].sale_id == sale.id
        assert published[0].reason == "cancelled"

    @pytest.mark.asyncio
    async def test_end_expired_publishes_flash_sale_ended(self):
        """EndExpiredSalesUseCase → FlashSaleEnded(reason='time_expired')."""
        repo, bus = _make_deps()
        now = _now()
        published: list[FlashSaleEnded] = []
        bus.subscribe(FlashSaleEnded, lambda e: published.append(e))

        sale = FlashSale.create(
            title="Expired Sale", discount_percent=20,
            max_quantity=10,
            starts_at=now - timedelta(hours=3),
            ends_at=now - timedelta(minutes=5),
        )
        sale.activate()
        sale.collect_events()
        await repo.save(sale)

        uc = EndExpiredSalesUseCase(repo, bus)
        await uc.execute(now)

        assert len(published) == 1
        assert published[0].reason == "time_expired"

    @pytest.mark.asyncio
    async def test_activate_multiple_sales_publishes_all_events(self):
        """Nhiều sales đến giờ → mỗi sale 1 FlashSaleActivated event."""
        repo, bus = _make_deps()
        now = _now()
        published: list[FlashSaleActivated] = []
        bus.subscribe(FlashSaleActivated, lambda e: published.append(e))

        for i in range(3):
            sale = FlashSale.create(
                title=f"Sale {i}", discount_percent=10 + i * 10,
                max_quantity=5,
                starts_at=now - timedelta(minutes=1),
                ends_at=now + timedelta(hours=1),
            )
            sale.collect_events()
            await repo.save(sale)

        uc = ActivateScheduledSalesUseCase(repo, bus)
        count = await uc.execute(now)

        assert count == 3
        assert len(published) == 3
        titles = {e.title for e in published}
        assert titles == {"Sale 0", "Sale 1", "Sale 2"}
