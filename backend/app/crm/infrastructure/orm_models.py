"""
CRM Context — ORM Models
==============================
Tất cả bảng liên quan đến CRM / tăng trưởng / giữ chân khách:
Customer, Event, Review, PushSubscription, LoyaltyReward, Referral, GrowthSetting.

TRƯỚC: Nằm chung trong app/models.py.
SAU:   Growth context sở hữu ORM models của mình.

FK cross-context:
- Review.order_id → "orders.id" (Ordering sở hữu bảng orders)
- LoyaltyReward.order_id → "orders.id"
  Dùng string FK → Growth không import Ordering ORM class.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.shared.orm_models import TenantMixin


# =============================================================================
# Customer — Khách hàng (track theo SĐT, không cần đăng ký)
# =============================================================================

class Customer(TenantMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[int] = mapped_column(Integer, default=0)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0)
    referral_code: Mapped[str | None] = mapped_column(String(10), unique=True, nullable=True)
    referred_by: Mapped[str | None] = mapped_column(String(10), nullable=True)
    first_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
# =============================================================================
# Event — Generic event log cho analytics
# =============================================================================

class Event(TenantMixin, Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    feature: Mapped[str] = mapped_column(String(30), nullable=False)
    data: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# Review — Đánh giá sau khi nhận hàng
# =============================================================================

class Review(TenantMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Cross-context FK: Ordering sở hữu bảng orders
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# PushSubscription — Web Push notification
# =============================================================================

class PushSubscription(TenantMixin, Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    keys_json: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# LoyaltyReward — Lịch sử đổi thưởng tích điểm
# =============================================================================

class LoyaltyReward(TenantMixin, Base):
    __tablename__ = "loyalty_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    reward_type: Mapped[str] = mapped_column(String(50), default="free_drink")
    points_used: Mapped[int] = mapped_column(Integer, nullable=False)
    # Cross-context FK: Ordering sở hữu bảng orders
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# Referral — Giới thiệu bạn bè
# =============================================================================

class Referral(TenantMixin, Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_phone: Mapped[str] = mapped_column(String(15), nullable=False)
    referred_phone: Mapped[str] = mapped_column(String(15), nullable=False)
    referrer_discount_used: Mapped[bool] = mapped_column(Boolean, default=False)
    referred_discount_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# GrowthSetting — Cài đặt kinh doanh có thể chỉnh từ admin panel
# =============================================================================

class GrowthSetting(TenantMixin, Base):
    """
    Key-value settings cho Growth context.
    Thay thế hardcode constants: REFERRAL_DISCOUNT, LOYALTY_THRESHOLD, etc.
    Chủ quán chỉnh trực tiếp từ admin panel.
    """
    __tablename__ = "growth_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(String(300), default="")
    min_value: Mapped[int] = mapped_column(Integer, default=0)
    max_value: Mapped[int] = mapped_column(Integer, default=1000)
    unit: Mapped[str] = mapped_column(String(20), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
