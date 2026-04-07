"""
Ordering Context — Domain Events
===================================
Events mà Order aggregate phát ra khi state thay đổi.

WHY events thay vì gọi trực tiếp:
- TRƯỚC: orders.py import Customer → ordering BIẾT growth
- SAU: Order phát OrderPlaced → Growth tự subscribe → ordering KHÔNG BIẾT growth
- Thêm context mới (Notification, Analytics) chỉ cần subscribe, không sửa Order

PATTERN: Aggregate collect events → use case publish sau khi persist.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class OrderPlaced:
    """
    Phát ra khi đơn hàng mới được tạo thành công.

    Subscribers hiện tại:
    - Growth: cập nhật Customer (order_count, loyalty_points, total_spent)
    - WS: broadcast tới admin panel

    Subscribers tương lai:
    - Notification: gửi Zalo message cho khách
    - Kitchen: thêm vào queue bếp
    """

    public_id: str
    phone: str
    customer_name: str
    address: str
    total: int           # Tổng sau giảm giá (đơn vị: nghìn đồng)
    item_count: int
    delivery_type: str   # immediate | scheduled
    scheduled_time: str | None
    estimated_minutes: int | None
    order_id: int | None  # DB id, available after persist
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class OrderStatusChanged:
    """
    Phát ra khi trạng thái đơn hàng thay đổi.

    Subscribers hiện tại:
    - WS: broadcast status change tới admin + KDS

    Subscribers tương lai:
    - Notification: gửi "Đang giao" cho khách
    - Kitchen: cập nhật KDS display
    """

    public_id: str
    old_status: str
    new_status: str
    updated_by: str      # "admin" | "kds" | "system"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
