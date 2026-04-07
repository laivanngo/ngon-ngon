"""
Promotions Context — Domain Events
======================================
Events mà Flash Sale aggregate phát ra khi state thay đổi.

WHY events:
- Admin tạo/hủy flash sale → WS broadcast tới customer + admin panel
- Khách claim flash sale → cập nhật remaining count real-time
- Hết giờ/hết lượt → tự động thông báo "Flash Sale đã kết thúc"
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class FlashSaleCreated:
    """Admin tạo flash sale mới. Broadcast tới admin panel."""

    sale_id: int
    title: str
    starts_at: datetime
    ends_at: datetime
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class FlashSaleActivated:
    """
    Flash sale bắt đầu (SCHEDULED → ACTIVE).

    Subscribers:
    - WS: broadcast banner tới customer phones
    - WS: notify admin panel
    """

    sale_id: int
    title: str
    product_ids: list[int]
    discount_percent: int
    ends_at: datetime
    max_quantity: int
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class FlashSaleClaimed:
    """
    Một đơn hàng đã claim flash sale discount.

    Subscribers:
    - WS: cập nhật remaining count cho customer banner
    """

    sale_id: int
    remaining: int
    is_sold_out: bool
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class FlashSaleEnded:
    """
    Flash sale kết thúc.

    reason: "time_expired" | "sold_out" | "cancelled"

    Subscribers:
    - WS: ẩn banner, hiện toast thông báo
    """

    sale_id: int
    reason: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
