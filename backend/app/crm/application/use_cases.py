"""
CRM Context — Application Use Cases
==========================================
9 use cases extracted từ routers/growth.py (~523 dòng → 9 use cases nhỏ).

Mỗi use case:
1. Nhận command/query
2. Gọi domain services / repository
3. Return result (DTO hoặc domain entity)

MAPPING: growth.py endpoint → use case:
- GET  /config         → GetGrowthConfigUseCase
- POST /events         → LogTrackingEventUseCase
- GET  /upsell-stats   → GetUpsellStatsUseCase
- GET  /reorder        → GetReorderUseCase
- GET  /cross-sell     → GetCrossSellUseCase
- GET  /customer       → GetCustomerInfoUseCase
- POST /reviews        → SubmitReviewUseCase
- GET  /referral       → GetReferralUseCase
- GET  /analytics      → GetAnalyticsUseCase (admin)
- PATCH /flags/{key}   → ToggleFeatureFlagUseCase (admin)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.crm.domain.entities import Customer, Review, TrackingEvent
from app.crm.domain.services import (
    FeatureFlagReadPort,
    AnalyticsReport,
    AnalyticsService,
    CustomerRepository,
    GrowthSettingDTO,
    GrowthSettingsRepository,
    ReorderData,
    ReorderService,
    ReferralRepository,
    ReviewRepository,
    TrackingEventRepository,
)
from app.crm.domain.value_objects import REFERRAL_DISCOUNT
from app.shared.exceptions import NotFoundError, ValidationError
from app.shared.utils import clean_phone

logger = logging.getLogger("ngonngon.growth")


# =============================================================================
# GET /config — Feature flags + customer data (1 call khi load trang)
# =============================================================================
class GetGrowthConfigUseCase:
    """
    Frontend gọi 1 lần khi load → biết tính năng nào bật + khách là ai.

    WHY 1 endpoint thay vì 9 calls: giảm latency trên 4G KCN.
    Use case gom 2 queries (flags + customer) thành 1 response.

    TRƯỚC: 30 dòng trong router endpoint — query flags, query customer,
           tính points_to_reward inline.
    SAU: Use case orchestrate, Customer.to_summary() format data.
    """

    def __init__(
        self,
        flag_port: FeatureFlagReadPort,
        customer_repo: CustomerRepository,
    ) -> None:
        self._flags = flag_port
        self._customers = customer_repo

    async def execute(self, phone: str | None = None) -> dict:
        flags = await self._flags.get_all_flags()

        customer_data = None
        if phone:
            clean = clean_phone(phone)
            customer = await self._customers.find_by_phone(clean)
            if customer:
                customer_data = customer.to_summary()

        return {"flags": flags, "customer": customer_data}


# =============================================================================
# POST /events — Log tracking event
# =============================================================================
@dataclass
class LogEventCommand:
    event_type: str = "unknown"
    feature: str = "unknown"
    data: dict | None = None
    phone: str | None = None
    order_id: int | None = None
    value: int = 0


class LogTrackingEventUseCase:
    """
    Frontend gửi event khi user tương tác với growth features.
    Fire-and-forget — không trả error nếu thiếu field.

    TRƯỚC: 10 dòng trong router, tạo Event ORM trực tiếp.
    SAU: Use case + TrackingEvent.create() domain factory.
    """

    def __init__(self, event_repo: TrackingEventRepository) -> None:
        self._events = event_repo

    async def execute(self, command: LogEventCommand) -> TrackingEvent:
        data_str = json.dumps(command.data) if command.data else None
        event = TrackingEvent.create(
            event_type=command.event_type,
            feature=command.feature,
            data=data_str,
            phone=command.phone,
            order_id=command.order_id,
            value=command.value,
        )
        await self._events.save(event)
        return event
# =============================================================================
class GetReorderUseCase:
    """
    Trả về đơn hoàn thành gần nhất theo SĐT.
    Frontend hiện nút "Đặt lại".

    TRƯỚC: 25 dòng SQL + format trong router.
    SAU: ReorderService (infrastructure) query + format.
    """

    def __init__(self, reorder_service: ReorderService) -> None:
        self._reorder = reorder_service

    async def execute(self, phone: str) -> ReorderData | None:
        clean = clean_phone(phone)
        return await self._reorder.get_last_order(clean)
# =============================================================================
class GetCustomerInfoUseCase:
    """
    Trả về loyalty info cho 1 customer.

    TRƯỚC: 15 dòng trong router, tính points_to_reward inline (duplicate với /config).
    SAU: Customer.to_summary() — 1 chỗ duy nhất format data.
    """

    def __init__(self, customer_repo: CustomerRepository) -> None:
        self._customers = customer_repo

    async def execute(self, phone: str) -> dict | None:
        clean = clean_phone(phone)
        customer = await self._customers.find_by_phone(clean)
        if not customer:
            return None
        return customer.to_summary()


# =============================================================================
# POST /reviews — Gửi đánh giá
# =============================================================================
@dataclass
class SubmitReviewCommand:
    order_id: int | None = None
    phone: str = ""
    rating: int = 0
    comment: str | None = None


class SubmitReviewUseCase:
    """
    Gửi đánh giá sau khi nhận hàng.

    Business rules (giữ nguyên từ growth.py):
    1. Rating 1-5
    2. 1 order chỉ review 1 lần → trả "Đã đánh giá rồi" (không raise error)

    TRƯỚC: 20 dòng trong router, validate + duplicate check + persist.
    SAU: Use case orchestrate, Review.create() validate, repo check duplicate.
    """

    def __init__(self, review_repo: ReviewRepository) -> None:
        self._reviews = review_repo

    async def execute(self, command: SubmitReviewCommand) -> Review | dict:
        # Check duplicate (business rule: 1 order = 1 review)
        if command.order_id:
            already = await self._reviews.exists_for_order(command.order_id)
            if already:
                return {"ok": True, "message": "Đã đánh giá rồi", "duplicate": True}

        # Create review via domain factory (validates rating 1-5)
        review = Review.create(
            order_id=command.order_id or 0,
            phone=command.phone,
            rating=command.rating,
            comment=command.comment,
        )

        await self._reviews.save(review)

        logger.info(f"⭐ Review: {'⭐' * review.rating} by {review.phone}")
        return review


# =============================================================================
# GET /admin/reviews — Admin xem danh sách đánh giá
# =============================================================================
class GetReviewsUseCase:
    """
    Lấy danh sách reviews cho admin dashboard.
    Hỗ trợ phân trang (limit/offset) và lọc theo rating.
    """

    def __init__(self, review_repo: ReviewRepository) -> None:
        self._reviews = review_repo

    async def execute(
        self, limit: int = 50, offset: int = 0, rating: int | None = None,
    ) -> dict:
        reviews, total = await self._reviews.list_all(
            limit=limit, offset=offset, rating=rating,
        )
        return {
            "reviews": [
                {
                    "id": r.id,
                    "order_id": r.order_id,
                    "order_public_id": getattr(r, "_order_public_id", None),
                    "phone": r.phone,
                    "rating": r.rating,
                    "comment": r.comment,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in reviews
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


# =============================================================================
# GET /referral — Lấy hoặc tạo mã giới thiệu
# =============================================================================
class GetReferralUseCase:
    """
    Lấy mã giới thiệu + đếm số lượt giới thiệu.

    TRƯỚC: 25 dòng — find customer, generate code if null, count referrals, format.
    SAU: Customer.ensure_referral_code() + repo.count_by_referrer().

    V2: Đọc referral_discount từ GrowthSettingsRepository (admin chỉnh được)
    thay vì hardcode REFERRAL_DISCOUNT constant.
    """

    def __init__(
        self,
        customer_repo: CustomerRepository,
        referral_repo: ReferralRepository,
        settings_repo: GrowthSettingsRepository | None = None,
    ) -> None:
        self._customers = customer_repo
        self._referrals = referral_repo
        self._settings = settings_repo

    async def execute(self, phone: str) -> dict | None:
        clean = clean_phone(phone)
        customer = await self._customers.find_by_phone(clean)

        if not customer:
            return None

        # Generate code nếu chưa có → save
        code = customer.ensure_referral_code()
        await self._customers.save(customer)

        # Đếm số lượt giới thiệu thành công
        ref_count = await self._referrals.count_by_referrer(clean)

        # Đọc discount từ DB (admin chỉnh), fallback về constant
        discount = REFERRAL_DISCOUNT
        if self._settings:
            discount = await self._settings.get_value(
                "referral_discount", REFERRAL_DISCOUNT,
            )

        return {
            "referral_code": code,
            "referral_count": ref_count,
            "discount_per_referral": discount,
            "share_text": customer.share_text,
        }


# =============================================================================
# GET /analytics — Admin dashboard (cần JWT)
# =============================================================================
class GetAnalyticsUseCase:
    """
    Comprehensive analytics cho chủ quán.

    TRƯỚC: 100+ dòng SQL queries inline trong router endpoint.
    SAU: AnalyticsService (infrastructure) chứa SQL, use case chỉ gọi 1 method.

    WHY service thay vì repository: analytics query across nhiều bảng
    (Order, OrderItem, Customer, Event, Review) — không thuộc entity nào.
    """

    def __init__(self, analytics_service: AnalyticsService) -> None:
        self._analytics = analytics_service

    async def execute(self, days: int = 7) -> AnalyticsReport:
        return await self._analytics.generate_report(days)
# =============================================================================
class GetGrowthSettingsUseCase:
    """
    Trả về tất cả cài đặt kinh doanh cho admin panel.
    Mỗi setting kèm label, description, min/max, unit → admin UI render form.
    """

    def __init__(self, settings_repo: GrowthSettingsRepository) -> None:
        self._settings = settings_repo

    async def execute(self) -> list[GrowthSettingDTO]:
        return await self._settings.get_all()


# =============================================================================
# PATCH /admin/settings/{key} — Admin chỉnh giá trị setting
# =============================================================================
class UpdateGrowthSettingUseCase:
    """
    Cập nhật 1 cài đặt kinh doanh.
    Validate min/max ở infrastructure layer (repository biết constraint từ DB).

    Ví dụ: chủ quán muốn tăng referral_discount từ 5k lên 10k
    → PATCH /growth/settings/referral_discount {"value": 10}
    """

    def __init__(self, settings_repo: GrowthSettingsRepository) -> None:
        self._settings = settings_repo

    async def execute(
        self, key: str, value: int, admin_username: str,
    ) -> GrowthSettingDTO:
        result = await self._settings.update(key, value)
        if not result:
            raise NotFoundError(f"Setting '{key}' không tồn tại")

        logger.info(
            f"⚙️ Setting '{key}' → {value}{result.unit} "
            f"(by {admin_username})"
        )
        return result
