"""
Kitchen Context — Domain Entities
=====================================
KitchenOrder: read projection từ Order, tối ưu cho KDS display.

WHY KitchenOrder KHÔNG PHẢI là Order:
- Kitchen context KHÔNG SỞ HỮU Order aggregate (Ordering sở hữu)
- KitchenOrder là "view" — chỉ chứa data bếp cần thấy
- Thêm field riêng: elapsed_seconds (timer), details (formatted string)
- Không có method change_status() — status change qua Ordering use case

PATTERN: Projection (CQRS-lite)
- Kitchen READ từ Order table (shared DB, chưa tách)
- Kitchen WRITE status qua Ordering's UpdateStatusUseCase
- Khi cần tách DB → Kitchen có event handler tạo KitchenOrder riêng
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class KitchenOrderItem:
    """
    1 món cần pha chế — format sẵn cho KDS display.
    details = "Size L • 70% đường • Ít đá • Trân Châu"
    """

    name: str
    quantity: int
    unit_price: int
    details: str     # Pre-formatted string cho KDS hiển thị nhanh


@dataclass
class KitchenOrder:
    """
    Read projection — đơn hàng qua góc nhìn bếp.

    Bếp quan tâm:
    - Pha gì? (items + details)
    - Cho ai? (customer_name, phone)
    - Giao đâu? (address)
    - Bao lâu rồi? (elapsed_seconds — timer)
    - Giao liền hay hẹn giờ? (delivery_type, scheduled_time)

    Bếp KHÔNG quan tâm:
    - subtotal, discount (tài chính)
    - customer_id, loyalty_points (growth)
    """

    public_id: str
    status: str
    customer_name: str
    phone: str
    address: str
    note: str | None
    delivery_type: str
    scheduled_time: str | None
    total: int
    items: list[KitchenOrderItem]
    item_count: int
    created_at: str       # ISO format
    elapsed_seconds: int   # Timer — bao lâu kể từ khi đặt

    @classmethod
    def from_order_data(
        cls,
        public_id: str,
        status: str,
        customer_name: str,
        phone: str,
        address: str,
        note: str | None,
        delivery_type: str,
        scheduled_time: str | None,
        total: int,
        items: list[KitchenOrderItem],
        created_at: datetime,
        now: datetime | None = None,
    ) -> KitchenOrder:
        """Factory: tạo KitchenOrder từ raw data, tính elapsed_seconds."""
        if now is None:
            now = datetime.now(timezone.utc)

        created_utc = (
            created_at.replace(tzinfo=timezone.utc)
            if created_at.tzinfo is None
            else created_at
        )
        elapsed = int((now - created_utc).total_seconds())

        return cls(
            public_id=public_id,
            status=status,
            customer_name=customer_name,
            phone=phone,
            address=address,
            note=note,
            delivery_type=delivery_type or "immediate",
            scheduled_time=scheduled_time,
            total=total,
            items=items,
            item_count=len(items),
            created_at=created_at.isoformat(),
            elapsed_seconds=elapsed,
        )

    @staticmethod
    def format_item_details(
        size: str | None,
        sweetness: str | None,
        ice_level: str | None,
        toppings_text: str | None,
        note: str | None,
    ) -> str:
        """
        Format item details cho KDS: "Size L • 70% đường • Ít đá • Trân Châu"

        TRƯỚC: Logic nằm trong _serialize_kds_order() ở kds.py.
        SAU: Entity method — reuse ở bất kỳ đâu cần format cho bếp.
        """
        details = []
        if size:
            details.append(f"Size {size}")
        if sweetness:
            details.append(sweetness)
        if ice_level:
            details.append(ice_level)
        if toppings_text:
            details.append(toppings_text)
        if note:
            details.append(f"📝 {note}")
        return " • ".join(details) if details else ""
