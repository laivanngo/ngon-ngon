"""
CRM Context — Domain Services & Repository ABCs
=====================================================
Abstract interfaces cho Growth domain.
Implementation ở infrastructure layer (SQL, cache, etc.).

WHY tách ABC:
- Domain KHÔNG biết DB (SQLAlchemy, PostgreSQL)
- Test domain logic bằng mock/in-memory → nhanh, không cần DB
- Đổi storage chỉ sửa infrastructure, domain nguyên vẹn

REPOSITORIES:
- CustomerRepository: CRUD + find_by_phone (natural key)
- ReviewRepository: save + check duplicate + avg rating
- ReferralRepository: save + count by referrer
- TrackingEventRepository: save (fire-and-forget)
- FeatureFlagRepository: get all + toggle

SERVICES:
- AnalyticsService: queries phức tạp cho admin dashboard
- UpsellStatsService: tính % topping/size popularity
- ReorderService: tìm đơn gần nhất để đặt lại
- CrossSellService: gợi ý mua kèm dựa trên giỏ hàng
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.crm.domain.entities import (
        Customer,
        Referral,
        Review,
        TrackingEvent,
    )


# =============================================================================
# CustomerRepository ABC
# =============================================================================
class CustomerRepository(ABC):
    """
    Interface cho Customer persistence.

    WHY find_by_phone là method chính (không phải find_by_id):
    Ngon-Ngon track customer bằng SĐT, không cần account.
    Phone là natural key — mọi lookup đều qua phone.
    """

    @abstractmethod
    async def find_by_phone(self, phone: str) -> "Customer | None":
        """Tìm customer bằng SĐT (đã clean)."""
        ...

    @abstractmethod
    async def save(self, customer: "Customer") -> "Customer":
        """
        Insert hoặc update customer.
        Return customer với id đã được DB generate.

        WHY upsert-style: đơn hàng đầu tiên → insert.
        Đơn tiếp theo → update. Cùng 1 method, caller không cần biết.
        """
        ...


# =============================================================================
# ReviewRepository ABC
# =============================================================================
class ReviewRepository(ABC):

    @abstractmethod
    async def save(self, review: "Review") -> "Review":
        """Persist review mới."""
        ...

    @abstractmethod
    async def exists_for_order(self, order_id: int) -> bool:
        """
        Check xem order đã được review chưa.
        Business rule: 1 order chỉ review 1 lần.
        """
        ...

    @abstractmethod
    async def avg_rating_since(self, since_days: int) -> float | None:
        """Rating trung bình trong N ngày gần nhất."""
        ...

    @abstractmethod
    async def list_all(
        self, limit: int = 50, offset: int = 0, rating: int | None = None,
    ) -> tuple[list["Review"], int]:
        """
        Danh sách reviews cho admin, mới nhất trước.
        Returns: (reviews, total_count) để phân trang.
        rating: lọc theo số sao (1-5), None = tất cả.
        """
        ...


# =============================================================================
# ReferralRepository ABC
# =============================================================================
class ReferralRepository(ABC):

    @abstractmethod
    async def save(self, referral: "Referral") -> "Referral":
        ...

    @abstractmethod
    async def count_by_referrer(self, referrer_phone: str) -> int:
        """Đếm số lượt giới thiệu thành công của 1 customer."""
        ...


# =============================================================================
# TrackingEventRepository ABC
# =============================================================================
class TrackingEventRepository(ABC):

    @abstractmethod
    async def save(self, event: "TrackingEvent") -> "TrackingEvent":
        """
        Persist tracking event. Fire-and-forget — không block UX.
        Return entity with DB-generated id.
        """
        ...


# =============================================================================
# FeatureFlagRepository ABC
# =============================================================================
@dataclass
# =============================================================================
# AnalyticsService ABC — Queries phức tạp cho admin dashboard
# =============================================================================
@dataclass
class RevenueByDay:
    day: str
    order_count: int
    revenue: int


@dataclass
class TopProduct:
    name: str
    quantity: int
    revenue: int


@dataclass
class PeakHour:
    hour: int
    order_count: int


@dataclass
class FeatureEffectiveness:
    shown: int
    accepted: int
    conversion: float  # percentage
    total_value: int


@dataclass
class AnalyticsReport:
    """
    Tất cả data cho admin analytics dashboard.
    Gom lại 1 DTO thay vì 8 queries rời rạc trả về dict.

    TRƯỚC: /analytics endpoint trả dict lồng dict, khó maintain.
    SAU: Typed DTO, IDE autocomplete, dễ test.
    """

    period_days: int
    revenue_by_day: list[RevenueByDay]
    top_products: list[TopProduct]
    peak_hours: list[PeakHour]
    total_customers: int
    repeat_customers: int
    repeat_rate: float
    cancel_rate: float
    feature_stats: dict[str, FeatureEffectiveness]
    avg_rating: float | None


class AnalyticsService(ABC):
    """
    Analytics queries — giữ ở infrastructure vì chứa SQL phức tạp.
    Domain chỉ define interface + DTOs.

    WHY service thay vì repository:
    Analytics KHÔNG thuộc entity nào cụ thể — nó query across
    Order, OrderItem, Customer, Event, Review.
    Service pattern phù hợp hơn repository (repository = per aggregate).
    """

    @abstractmethod
    async def generate_report(self, days: int = 7) -> AnalyticsReport:
        """Tạo analytics report cho N ngày gần nhất."""
        ...


# =============================================================================
# UpsellStatsService ABC — Topping/size popularity
# =============================================================================
@dataclass
# =============================================================================
# ReorderService ABC — Đơn gần nhất để đặt lại
# =============================================================================
@dataclass
class ReorderItem:
    product_name: str
    product_id: int
    size: str | None
    sweetness: str | None
    ice_level: str | None
    quantity: int
    toppings_text: str | None


@dataclass
class ReorderData:
    public_id: str
    total: int
    items: list[ReorderItem]
    created_at: str  # ISO format


class ReorderService(ABC):
    """
    Tìm đơn hoàn thành gần nhất theo SĐT.
    Frontend dùng để hiện nút "Đặt lại".

    WHY service thay vì CustomerRepository method:
    Reorder query Order + OrderItem — thuộc Ordering context.
    Nhưng dùng bởi Growth context → cross-context read service.
    """

    @abstractmethod
    async def get_last_order(self, phone: str) -> ReorderData | None:
        ...


# =============================================================================
# CrossSellQueryService ABC — Gợi ý mua kèm (data-driven)
# =============================================================================
@dataclass
# =============================================================================
# GrowthSettingsRepository ABC — Cài đặt kinh doanh chỉnh từ admin
# =============================================================================
@dataclass
class GrowthSettingDTO:
    """
    DTO cho 1 cài đặt kinh doanh.
    Chứa đủ info để admin UI render form: label, min/max, unit.
    """

    key: str
    value: int
    label: str = ""
    description: str = ""
    min_value: int = 0
    max_value: int = 1000
    unit: str = ""


class GrowthSettingsRepository(ABC):
    """
    Interface cho Growth business settings persistence.

    WHY tách riêng (không dùng FeatureFlagRepository):
    - FeatureFlags = bật/tắt tính năng (boolean)
    - GrowthSettings = giá trị kinh doanh (integer) với min/max validation
    - Khác concept, khác UI, khác validation logic.
    """

    @abstractmethod
    async def get_all(self) -> list[GrowthSettingDTO]:
        """Lấy tất cả settings."""
        ...

    @abstractmethod
    async def get_value(self, key: str, default: int = 0) -> int:
        """Lấy giá trị 1 setting theo key. Return default nếu không tìm thấy."""
        ...

    @abstractmethod
    async def update(self, key: str, value: int) -> GrowthSettingDTO | None:
        """
        Cập nhật giá trị 1 setting.
        Return None nếu key không tồn tại.
        Raise ValidationError nếu value ngoài min/max.
        """
        ...


# =============================================================================
# FeatureFlagReadPort — Đọc feature flags từ Promotions context
# =============================================================================
class FeatureFlagReadPort(ABC):
    """
    Port để CRM đọc feature flags từ Promotions context.
    CRM cần flags cho /config endpoint (1 API call khi load trang).
    Implementation ở Promotions infrastructure.
    """

    @abstractmethod
    async def get_all_flags(self) -> dict[str, bool]:
        """Return {key: enabled} cho tất cả flags."""
        ...
