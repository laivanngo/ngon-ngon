"""
Promotions Context — Flash Sale Entity & Repository ABC
==========================================================
Flash Sale: chương trình giảm giá giới hạn thời gian + số lượng.

VD: "Giảm 50% Trà Sữa + Cà Phê từ 14h-16h hôm nay, chỉ 20 đơn đầu tiên"
product_ids=[] → toàn menu, product_ids=[1,2,3] → chỉ áp dụng cho sản phẩm cụ thể.

FlashSale là Aggregate Root:
- Tự validate invariants (discount 1-90, ends > starts, max_quantity >= 1)
- Tự quản lý status lifecycle (SCHEDULED → ACTIVE → ENDED/CANCELLED)
- Phát domain events khi state thay đổi

WHY dataclass (không dùng ORM model):
- Domain entity KHÔNG phụ thuộc DB
- Test được mà không cần DB connection
- Repository map giữa domain ↔ ORM
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.promotions.domain.events import (
    FlashSaleActivated,
    FlashSaleCreated,
    FlashSaleEnded,
)
from app.shared.exceptions import InvalidStatusTransitionError, ValidationError


# =============================================================================
# FlashSaleStatus — Enum quản lý lifecycle
# =============================================================================
class FlashSaleStatus(str, Enum):
    """
    Lifecycle: SCHEDULED → ACTIVE → ENDED
                    ↘         ↘
                   CANCELLED  CANCELLED

    SCHEDULED: admin đã tạo, chưa tới giờ bắt đầu
    ACTIVE: đang chạy (trong time window, chưa hết lượt)
    ENDED: hết giờ hoặc hết lượt
    CANCELLED: admin hủy trước khi kết thúc
    """

    SCHEDULED = "scheduled"
    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """ENDED và CANCELLED là trạng thái cuối — không thể chuyển tiếp."""
        return self in (FlashSaleStatus.ENDED, FlashSaleStatus.CANCELLED)


# =============================================================================
# FlashSale — Aggregate Root
# =============================================================================
@dataclass
class FlashSale:
    """
    Flash Sale aggregate root.

    Invariants:
    1. discount_percent: 1-90 (không cho 100% — quán lỗ)
    2. max_quantity >= 1
    3. ends_at > starts_at
    4. Status transitions hợp lệ (xem FlashSaleStatus)
    5. claimed_count <= max_quantity (enforced bởi atomic SQL)
    """

    title: str
    discount_percent: int
    max_quantity: int
    starts_at: datetime
    ends_at: datetime
    status: FlashSaleStatus = FlashSaleStatus.SCHEDULED
    product_ids: list[int] = field(default_factory=list)
    subtitle: str | None = None
    claimed_count: int = 0
    store_id: int = 1
    id: int | None = None
    created_at: datetime | None = None

    _events: list[Any] = field(default_factory=list, repr=False)

    # =========================================================================
    # Factory Method
    # =========================================================================
    @classmethod
    def create(
        cls,
        title: str,
        discount_percent: int,
        max_quantity: int,
        starts_at: datetime,
        ends_at: datetime,
        product_ids: list[int] | None = None,
        subtitle: str | None = None,
        store_id: int = 1,
    ) -> FlashSale:
        """
        Tạo Flash Sale mới. Validate invariants + phát FlashSaleCreated event.

        WHY factory thay vì __init__:
        - __init__ chỉ gán field (dùng khi load từ DB)
        - Factory enforce business rules + phát event
        """
        if not title or not title.strip():
            raise ValidationError("Tên flash sale không được để trống")

        if not (1 <= discount_percent <= 90):
            raise ValidationError(
                f"Phần trăm giảm giá phải từ 1-90%, nhận được {discount_percent}%"
            )

        if max_quantity < 1:
            raise ValidationError("Số lượng tối đa phải >= 1")

        if ends_at <= starts_at:
            raise ValidationError(
                "Thời gian kết thúc phải sau thời gian bắt đầu"
            )

        sale = cls(
            title=title.strip(),
            discount_percent=discount_percent,
            max_quantity=max_quantity,
            starts_at=starts_at,
            ends_at=ends_at,
            product_ids=product_ids or [],
            subtitle=subtitle.strip() if subtitle else None,
            store_id=store_id,
            created_at=datetime.now(timezone.utc),
        )

        sale._events.append(
            FlashSaleCreated(
                sale_id=0,  # Chưa có DB id, sẽ update sau persist
                title=sale.title,
                starts_at=sale.starts_at,
                ends_at=sale.ends_at,
            )
        )

        return sale

    # =========================================================================
    # Status Transitions
    # =========================================================================
    def activate(self) -> None:
        """SCHEDULED → ACTIVE. Gọi khi tới giờ bắt đầu."""
        if self.status != FlashSaleStatus.SCHEDULED:
            raise InvalidStatusTransitionError(
                current=self.status.value,
                target="active",
                allowed=["scheduled"],
            )

        self.status = FlashSaleStatus.ACTIVE
        self._events.append(
            FlashSaleActivated(
                sale_id=self.id or 0,
                title=self.title,
                product_ids=self.product_ids,
                discount_percent=self.discount_percent,
                ends_at=self.ends_at,
                max_quantity=self.max_quantity,
            )
        )

    def end(self, reason: str) -> None:
        """ACTIVE → ENDED. reason: "time_expired" | "sold_out"."""
        if self.status != FlashSaleStatus.ACTIVE:
            raise InvalidStatusTransitionError(
                current=self.status.value,
                target="ended",
                allowed=["active"],
            )

        self.status = FlashSaleStatus.ENDED
        self._events.append(
            FlashSaleEnded(sale_id=self.id or 0, reason=reason)
        )

    def cancel(self) -> None:
        """Hủy flash sale (từ bất kỳ trạng thái non-terminal nào)."""
        if self.status.is_terminal:
            raise InvalidStatusTransitionError(
                current=self.status.value,
                target="cancelled",
                allowed=[],
            )

        self.status = FlashSaleStatus.CANCELLED
        self._events.append(
            FlashSaleEnded(sale_id=self.id or 0, reason="cancelled")
        )

    # =========================================================================
    # Properties
    # =========================================================================
    @property
    def is_sold_out(self) -> bool:
        """Đã hết lượt claim."""
        return self.claimed_count >= self.max_quantity

    @property
    def remaining(self) -> int:
        """Số lượt còn lại."""
        return max(0, self.max_quantity - self.claimed_count)

    def is_within_time_window(self, now: datetime) -> bool:
        """Kiểm tra thời gian hiện tại nằm trong window."""
        return self.starts_at <= now < self.ends_at

    # =========================================================================
    # Event Collection
    # =========================================================================
    def collect_events(self) -> list[Any]:
        """Thu thập và clear events. Gọi SAU KHI persist thành công."""
        events = list(self._events)
        self._events.clear()
        return events


# =============================================================================
# FlashSaleRepository ABC
# =============================================================================
class FlashSaleRepository(ABC):
    """
    Interface cho Flash Sale persistence.

    claim_atomically() là method quan trọng nhất:
    Dùng SQL UPDATE...WHERE claimed_count < max_quantity
    để chống race condition khi nhiều khách đặt cùng lúc.
    """

    @abstractmethod
    async def save(self, sale: FlashSale) -> FlashSale:
        """Persist flash sale mới hoặc cập nhật. Return với id đã generate."""
        ...

    @abstractmethod
    async def find_by_id(self, sale_id: int) -> FlashSale | None:
        """Tìm flash sale theo id."""
        ...

    @abstractmethod
    async def find_active(self, now: datetime) -> list[FlashSale]:
        """Tìm tất cả flash sales đang ACTIVE tại thời điểm now."""
        ...

    @abstractmethod
    async def find_scheduled_ready(self, now: datetime) -> list[FlashSale]:
        """Tìm SCHEDULED sales đã tới giờ bắt đầu (starts_at <= now)."""
        ...

    @abstractmethod
    async def find_active_expired(self, now: datetime) -> list[FlashSale]:
        """Tìm ACTIVE sales đã hết giờ (ends_at <= now)."""
        ...

    @abstractmethod
    async def list_all(
        self, limit: int = 20, offset: int = 0,
    ) -> tuple[list[FlashSale], int]:
        """Danh sách tất cả (admin view) + total count."""
        ...

    @abstractmethod
    async def claim_atomically(self, sale_id: int) -> int | None:
        """
        Atomic increment claimed_count.
        Return claimed_count mới nếu thành công.
        Return None nếu đã hết lượt hoặc không ACTIVE.
        """
        ...
