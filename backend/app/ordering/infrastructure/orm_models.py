"""
Ordering Context — ORM Models
================================
Bảng đơn hàng: Order + OrderItem.

TRƯỚC: Nằm chung trong app/models.py.
SAU:   Ordering context sở hữu ORM models đơn hàng.
       Kitchen/Growth ĐỌC bảng này (cross-context read) nhưng KHÔNG sở hữu.

FK cross-context:
- Order.customer_id → "customers.id" (Growth context sở hữu bảng customers)
  Dùng string FK → không cần import Growth ORM class.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.shared.orm_models import TenantMixin, TimestampMixin


# =============================================================================
# Enum
# =============================================================================

class OrderStatus(str, PyEnum):
    """Lifecycle: pending → confirmed → preparing → delivering → done."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    DELIVERING = "delivering"
    DONE = "done"
    CANCELLED = "cancelled"


# =============================================================================
# Order — Đơn hàng (bảng quan trọng nhất về mặt business)
# =============================================================================

class Order(TenantMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, values_callable=lambda x: [e.value for e in x]),
        default=OrderStatus.PENDING, nullable=False,
    )

    delivery_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="immediate",
        comment="immediate = giao liền, scheduled = hẹn giờ",
    )
    scheduled_time: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="Giờ hẹn giao VD: 12:00. Chỉ khi delivery_type=scheduled",
    )

    # Cross-context FK: Growth context sở hữu bảng customers
    # Dùng string "customers.id" → Ordering không import Growth ORM
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True,
    )
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", lazy="selectin", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Order {self.public_id[:8]}... {self.status.value} {self.total}k>"


# =============================================================================
# OrderItem — Chi tiết từng món trong đơn
# =============================================================================

class OrderItem(TenantMixin, Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    # Cross-context FK: Catalog context sở hữu bảng products
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False,
    )

    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    size: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sweetness: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ice_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    toppings_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")

    @property
    def line_total(self) -> int:
        return self.unit_price * self.quantity
