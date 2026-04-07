"""
CRM Context — Domain Entities
=================================
Customer (Aggregate Root), Review, Referral, TrackingEvent.

THAY ĐỔI SO VỚI GROWTH:
- Customer.record_order() giờ tích điểm theo chi tiêu (order_total * rate)
  thay vì cố định +1 điểm/đơn.
- Customer.create_from_order() cũng tích điểm theo chi tiêu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.crm.domain.value_objects import (
    LOYALTY_POINTS_PER_1000,
    LOYALTY_THRESHOLD,
    REFERRAL_DISCOUNT,
    LoyaltyPoints,
    Rating,
    ReferralCode,
)


# =============================================================================
# Customer — Aggregate Root
# =============================================================================
@dataclass
class Customer:
    """
    Customer Aggregate Root — trung tâm của CRM context.

    MÔ HÌNH LOYALTY MỚI (spend-based):
    - Mỗi 1.000đ chi tiêu = N điểm (N configurable, mặc định 1)
    - Đơn 35k → +35 điểm. Đơn 150k → +150 điểm.
    - Khách chi nhiều tích nhanh hơn → công bằng, khuyến khích upsell.
    """

    phone: str
    name: str | None = None

    # --- Order tracking ---
    order_count: int = 0
    total_spent: int = 0

    # --- Loyalty (spend-based) ---
    loyalty_points: int = 0

    # --- Referral ---
    referral_code: str | None = None
    referred_by: str | None = None

    # --- Timestamps ---
    first_order_at: datetime | None = None
    last_order_at: datetime | None = None

    # --- Identity ---
    id: int | None = None
    store_id: int = 1
    created_at: datetime | None = None

    # --- Events (internal) ---
    _events: list[Any] = field(default_factory=list, repr=False)

    # =========================================================================
    # Factory — tạo customer mới khi đặt hàng lần đầu
    # =========================================================================
    @classmethod
    def create_from_order(
        cls,
        phone: str,
        name: str,
        order_total: int,
        points_rate: int = LOYALTY_POINTS_PER_1000,
    ) -> Customer:
        """
        Factory: tạo customer mới từ đơn hàng đầu tiên.
        Tích điểm theo chi tiêu: order_total (nghìn đồng) * rate.
        """
        now = datetime.now(timezone.utc)
        points = LoyaltyPoints.points_from_spend(order_total, points_rate)
        return cls(
            phone=phone,
            name=name,
            order_count=1,
            total_spent=order_total,
            loyalty_points=points,
            first_order_at=now,
            last_order_at=now,
            created_at=now,
        )

    # =========================================================================
    # record_order — Cập nhật khi có đơn hàng mới
    # =========================================================================
    def record_order(
        self, name: str, total: int,
        points_rate: int = LOYALTY_POINTS_PER_1000,
    ) -> None:
        """
        Ghi nhận đơn hàng mới.

        MÔ HÌNH MỚI: tích điểm = order_total * rate.
        VD: đơn 45k, rate=1 → +45 điểm.
        """
        self.name = name
        self.order_count += 1
        self.total_spent += total
        self.loyalty_points += LoyaltyPoints.points_from_spend(total, points_rate)
        self.last_order_at = datetime.now(timezone.utc)

    # =========================================================================
    # Loyalty
    # =========================================================================
    @property
    def loyalty(self) -> LoyaltyPoints:
        return LoyaltyPoints(self.loyalty_points)

    @property
    def points_to_reward(self) -> int:
        return self.loyalty.points_to_reward

    @property
    def has_reward(self) -> bool:
        return self.loyalty.has_reward

    def redeem_reward(self, points: int = LOYALTY_THRESHOLD) -> None:
        new_loyalty = self.loyalty.redeem(points)
        self.loyalty_points = int(new_loyalty)

    # =========================================================================
    # Referral
    # =========================================================================
    def ensure_referral_code(self) -> str:
        if not self.referral_code:
            self.referral_code = str(ReferralCode.from_phone(self.phone))
        return self.referral_code

    @property
    def share_text(self) -> str:
        code = self.ensure_referral_code()
        return (
            f"Dùng mã {code} tại Ngon-Ngon để được giảm "
            f"{REFERRAL_DISCOUNT}k đơn đầu tiên! 🧋"
        )

    # =========================================================================
    # Customer view — format cho API response
    # =========================================================================
    def to_summary(self) -> dict:
        return {
            "phone": self.phone,
            "name": self.name,
            "order_count": self.order_count,
            "loyalty_points": self.loyalty_points,
            "points_to_reward": self.points_to_reward,
            "has_reward": self.has_reward,
            "referral_code": self.referral_code,
            "total_spent": self.total_spent,
        }

    def collect_events(self) -> list[Any]:
        events = list(self._events)
        self._events.clear()
        return events


# =============================================================================
# Review — Đánh giá sau khi nhận hàng
# =============================================================================
@dataclass
class Review:
    """Đánh giá đơn hàng. Rating 1-5, 1 order = 1 review."""

    order_id: int
    phone: str
    rating: int
    comment: str | None = None
    id: int | None = None
    store_id: int = 1
    created_at: datetime | None = None

    @classmethod
    def create(
        cls, order_id: int, phone: str, rating: int,
        comment: str | None = None, store_id: int = 1,
    ) -> Review:
        validated = Rating(rating)
        clean_comment = str(comment)[:500] or None if comment else None
        return cls(
            order_id=order_id, phone=str(phone)[:15],
            rating=validated.value, comment=clean_comment, store_id=store_id,
        )


# =============================================================================
# Referral — Theo dõi giới thiệu bạn bè
# =============================================================================
@dataclass
class Referral:
    """Theo dõi 1 lượt giới thiệu (referrer → referred)."""

    referrer_phone: str
    referred_phone: str
    referrer_discount_used: bool = False
    referred_discount_used: bool = False
    id: int | None = None
    store_id: int = 1
    created_at: datetime | None = None

    @classmethod
    def create(cls, referrer_phone: str, referred_phone: str) -> Referral:
        return cls(referrer_phone=referrer_phone, referred_phone=referred_phone)

    def use_referrer_discount(self) -> None:
        if self.referrer_discount_used:
            raise ValueError("Discount đã được sử dụng")
        self.referrer_discount_used = True

    def use_referred_discount(self) -> None:
        if self.referred_discount_used:
            raise ValueError("Discount đã được sử dụng")
        self.referred_discount_used = True


# =============================================================================
# TrackingEvent — Log event cho analytics
# =============================================================================
@dataclass
class TrackingEvent:
    """Generic tracking event — đo hiệu quả growth features."""

    event_type: str
    feature: str
    data: str | None = None
    phone: str | None = None
    order_id: int | None = None
    value: int = 0
    id: int | None = None
    store_id: int = 1
    created_at: datetime | None = None

    @classmethod
    def create(
        cls, event_type: str = "unknown", feature: str = "unknown",
        data: str | None = None, phone: str | None = None,
        order_id: int | None = None, value: int = 0,
    ) -> TrackingEvent:
        return cls(
            event_type=str(event_type)[:50], feature=str(feature)[:30],
            data=data, phone=str(phone)[:15] if phone else None,
            order_id=order_id, value=int(value),
        )
