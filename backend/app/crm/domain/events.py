"""
CRM Context — Domain Events
================================
Events mà CRM context phát ra hoặc lắng nghe.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class CustomerRewardEarned:
    """Phát ra khi customer tích đủ điểm loyalty."""
    phone: str
    customer_name: str | None
    loyalty_points: int
    rewards_available: int
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ReviewSubmitted:
    """Phát ra khi customer submit review."""
    order_id: int
    phone: str
    rating: int
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
