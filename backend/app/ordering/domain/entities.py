"""
Ordering Context — Domain Entities
=====================================
TRƯỚC: Order trong models.py chỉ là data container — không có method nào.
SAU: Order là Aggregate Root — tự validate, tự phát event, tự bảo vệ invariants.

AGGREGATE ROOT PATTERN:
- Order là entry point duy nhất để thay đổi OrderItem
- Bên ngoài KHÔNG ĐƯỢC sửa OrderItem trực tiếp
- Mọi state change đều qua method của Order → đảm bảo business rules

WHY dataclass thay vì SQLAlchemy model:
- Domain entity KHÔNG phụ thuộc vào DB library
- Test được mà không cần DB connection
- Repository chịu trách nhiệm map giữa domain ↔ ORM
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.ordering.domain.events import OrderPlaced, OrderStatusChanged
from app.ordering.domain.value_objects import (
    Address,
    DeliveryOption,
    Money,
    OrderStatus,
    Phone,
)
from app.shared.exceptions import InvalidStatusTransitionError, ValidationError


# =============================================================================
# OrderItem — Một món trong đơn hàng
# =============================================================================
@dataclass
class OrderItem:
    """
    Chi tiết 1 món trong đơn.

    WHY lưu product_name, unit_price riêng (snapshot):
    - product_name: khi product đổi tên, đơn cũ vẫn hiển thị đúng
    - unit_price: giá có thể thay đổi, đơn cũ giữ giá tại thời điểm đặt
    """

    product_id: int
    product_name: str
    size: str | None
    sweetness: str | None
    ice_level: str | None
    quantity: int
    unit_price: int         # Đã bao gồm giá topping
    toppings_text: str | None
    note: str | None
    id: int | None = None   # DB id, None khi chưa persist

    @property
    def line_total(self) -> int:
        """Tổng tiền cho dòng này = đơn giá × số lượng."""
        return self.unit_price * self.quantity


# =============================================================================
# Order — Aggregate Root
# =============================================================================
@dataclass
class Order:
    """
    Order Aggregate Root — trung tâm của Ordering context.

    Invariants mà Order tự bảo vệ:
    1. Đơn hàng phải có ít nhất 1 món
    2. total = subtotal - discount (luôn đúng)
    3. Status transition phải hợp lệ (không thể done → pending)
    4. Phone phải đúng format VN
    5. Address phải được sanitize XSS
    """

    # --- Identity ---
    public_id: str
    customer_name: str
    phone: str              # Đã validated bởi Phone value object
    address: str            # Đã sanitized bởi Address value object

    # --- Order details ---
    note: str | None
    delivery_type: str      # "immediate" | "scheduled"
    scheduled_time: str | None
    items: list[OrderItem]

    # --- Money ---
    subtotal: int           # Tổng trước giảm giá
    discount: int           # Giảm giá (từ TimeDeal, loyalty, etc.)
    total: int              # Tổng sau giảm giá

    # --- State ---
    status: OrderStatus = OrderStatus.PENDING

    # --- Metadata ---
    id: int | None = None
    store_id: int = 1
    customer_id: int | None = None
    estimated_minutes: int | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None

    # --- Events (internal, không persist) ---
    _events: list[Any] = field(default_factory=list, repr=False)

    # =========================================================================
    # Factory Method — tạo đơn hàng mới
    # =========================================================================
    @classmethod
    def place(
        cls,
        customer_name: str,
        phone: str,
        address: str,
        note: str | None,
        delivery_type: str,
        scheduled_time: str | None,
        items: list[OrderItem],
        subtotal: int,
        discount: int,
    ) -> Order:
        """
        Factory method — tạo đơn hàng mới.
        Validate invariants + phát OrderPlaced event.

        WHY factory thay vì __init__:
        - __init__ chỉ gán field
        - Factory enforce business rules + phát event
        - Load từ DB dùng __init__ (không phát event lại)
        """
        # --- Validate invariants ---
        if not items:
            raise ValidationError("Đơn hàng phải có ít nhất 1 món")

        # Validate phone (sẽ raise ValueError nếu sai format)
        validated_phone = Phone(phone)

        # Validate address (sẽ sanitize XSS)
        validated_address = Address(address)

        # Sanitize customer_name
        import html as _html
        import re as _re

        clean_name = _re.sub(r"<[^>]+>", "", customer_name.strip())
        clean_name = _html.escape(clean_name, quote=True)
        if not clean_name:
            raise ValidationError("Tên không được để trống")

        # Sanitize note
        clean_note = None
        if note:
            clean_note = _re.sub(r"<[^>]+>", "", note.strip())
            clean_note = _html.escape(clean_note, quote=True)

        # Validate delivery
        if delivery_type not in ("immediate", "scheduled"):
            raise ValidationError("delivery_type phải là 'immediate' hoặc 'scheduled'")

        effective_scheduled = scheduled_time if delivery_type == "scheduled" else None

        total = subtotal - discount
        if total < 0:
            total = 0

        # --- Create order ---
        order = cls(
            public_id=str(uuid.uuid4()),
            customer_name=clean_name,
            phone=str(validated_phone),
            address=str(validated_address),
            note=clean_note,
            delivery_type=delivery_type,
            scheduled_time=effective_scheduled,
            items=items,
            subtotal=subtotal,
            discount=discount,
            total=total,
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        # --- Phát event ---
        order._events.append(
            OrderPlaced(
                public_id=order.public_id,
                phone=order.phone,
                customer_name=order.customer_name,
                address=order.address,
                total=order.total,
                item_count=len(order.items),
                delivery_type=order.delivery_type,
                scheduled_time=order.scheduled_time,
                estimated_minutes=order.estimated_minutes,
                order_id=None,  # Chưa có DB id
            )
        )

        return order

    # =========================================================================
    # Status Transition — 1 chỗ duy nhất validate
    # =========================================================================
    def change_status(self, new_status: OrderStatus, updated_by: str = "system") -> None:
        """
        Chuyển trạng thái đơn hàng.
        Raise InvalidStatusTransitionError nếu không hợp lệ.

        TRƯỚC: Logic này duplicate ở admin.py (dòng 150-157) VÀ kds.py (dòng 197-204).
        SAU: 1 chỗ duy nhất — ai muốn đổi status đều gọi method này.
        """
        if not self.status.can_transition_to(new_status):
            raise InvalidStatusTransitionError(
                current=self.status.value,
                target=new_status.value,
                allowed=[s.value for s in self.status.allowed_transitions],
            )

        old_status = self.status
        self.status = new_status

        # Mark completed_at khi done
        if new_status == OrderStatus.DONE:
            self.completed_at = datetime.now(timezone.utc)

        self._events.append(
            OrderStatusChanged(
                public_id=self.public_id,
                old_status=old_status.value,
                new_status=new_status.value,
                updated_by=updated_by,
            )
        )

    # =========================================================================
    # Event Collection
    # =========================================================================
    def collect_events(self) -> list[Any]:
        """
        Thu thập và clear events.
        Use case gọi SAU KHI persist thành công → publish events.

        WHY collect sau persist: nếu persist fail → không phát event → consistency.
        """
        events = list(self._events)
        self._events.clear()
        return events
