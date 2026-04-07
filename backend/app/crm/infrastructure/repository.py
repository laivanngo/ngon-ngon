"""
CRM Context — SQL Infrastructure
=======================================
SQLAlchemy implementations cho tất cả repository ABCs và services.

TRƯỚC: Import trực tiếp ORM của Ordering và Catalog (4 cross-context imports).
SAU:   Nhận OrderAnalyticsPort và CatalogAnalyticsPort qua constructor injection.
       Growth không biết ORM schema của bất kỳ context nào khác.

FILE NÀY LỚN (~400 dòng) vì gom nhiều repositories + services.
WHY không tách file: tất cả cùng 1 pattern (query ORM → map DTO).
Nếu cần tách → tách theo service, không theo layer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import Date, and_, case, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crm.domain.entities import Customer, Review, Referral, TrackingEvent
from app.crm.domain.services import (
    AnalyticsReport,
    AnalyticsService,
    CustomerRepository,
    FeatureEffectiveness,
    GrowthSettingDTO,
    GrowthSettingsRepository,
    PeakHour,
    ReorderData,
    ReorderItem,
    ReorderService,
    ReferralRepository,
    RevenueByDay,
    ReviewRepository,
    TopProduct,
    TrackingEventRepository,
)
# Growth chỉ import ORM của chính mình
from app.crm.infrastructure.orm_models import Customer as ORMCustomer
from app.crm.infrastructure.orm_models import Event as ORMEvent
from app.crm.infrastructure.orm_models import Referral as ORMReferral
from app.crm.infrastructure.orm_models import Review as ORMReview
from app.crm.infrastructure.orm_models import GrowthSetting as ORMGrowthSetting
# Cross-context: dùng ports thay vì import ORM trực tiếp
from app.ordering.application.analytics_port import OrderAnalyticsPort

logger = logging.getLogger("ngonngon.growth.infra")


# =============================================================================
# SqlCustomerRepository
# =============================================================================
class SqlCustomerRepository(CustomerRepository):

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_phone(self, phone: str) -> Customer | None:
        stmt = select(ORMCustomer).where(ORMCustomer.phone == phone)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            return None
        return self._to_domain(orm)

    async def save(self, customer: Customer) -> Customer:
        if customer.id is None:
            return await self._insert(customer)
        return await self._update(customer)

    async def _insert(self, customer: Customer) -> Customer:
        orm = ORMCustomer(
            phone=customer.phone,
            name=customer.name,
            order_count=customer.order_count,
            total_spent=customer.total_spent,
            loyalty_points=customer.loyalty_points,
            referral_code=customer.referral_code,
            referred_by=customer.referred_by,
            first_order_at=customer.first_order_at,
            last_order_at=customer.last_order_at,
            store_id=customer.store_id,
        )
        self._db.add(orm)
        await self._db.commit()
        await self._db.refresh(orm)
        customer.id = orm.id
        customer.created_at = orm.created_at
        return customer

    async def _update(self, customer: Customer) -> Customer:
        stmt = select(ORMCustomer).where(ORMCustomer.id == customer.id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            raise ValueError(f"Customer id={customer.id} not found in DB")

        orm.name = customer.name
        orm.order_count = customer.order_count
        orm.total_spent = customer.total_spent
        orm.loyalty_points = customer.loyalty_points
        orm.referral_code = customer.referral_code
        orm.referred_by = customer.referred_by
        orm.last_order_at = customer.last_order_at

        await self._db.commit()
        return customer

    @staticmethod
    def _to_domain(orm: ORMCustomer) -> Customer:
        return Customer(
            id=orm.id,
            phone=orm.phone,
            name=orm.name,
            order_count=orm.order_count,
            total_spent=orm.total_spent,
            loyalty_points=orm.loyalty_points,
            referral_code=orm.referral_code,
            referred_by=orm.referred_by,
            first_order_at=orm.first_order_at,
            last_order_at=orm.last_order_at,
            store_id=orm.store_id,
            created_at=orm.created_at,
        )


# =============================================================================
# SqlReviewRepository
# =============================================================================
class SqlReviewRepository(ReviewRepository):

    def __init__(self, db: AsyncSession, order_port: OrderAnalyticsPort | None = None) -> None:
        self._db = db
        self._order_port = order_port

    async def save(self, review: Review) -> Review:
        orm = ORMReview(
            order_id=review.order_id,
            phone=review.phone,
            rating=review.rating,
            comment=review.comment,
            store_id=review.store_id,
        )
        self._db.add(orm)
        await self._db.commit()
        await self._db.refresh(orm)
        review.id = orm.id
        review.created_at = orm.created_at
        return review

    async def exists_for_order(self, order_id: int) -> bool:
        result = await self._db.execute(
            select(ORMReview.id).where(ORMReview.order_id == order_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def avg_rating_since(self, since_days: int) -> float | None:
        since = datetime.now(timezone.utc) - timedelta(days=since_days)
        result = await self._db.execute(
            select(func.avg(ORMReview.rating)).where(
                ORMReview.created_at >= since
            )
        )
        return result.scalar()

    async def list_all(
        self, limit: int = 50, offset: int = 0, rating: int | None = None,
    ) -> tuple[list[Review], int]:
        where = []
        if rating is not None:
            where.append(ORMReview.rating == rating)

        count_stmt = select(func.count(ORMReview.id))
        if where:
            count_stmt = count_stmt.where(*where)
        total = (await self._db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(ORMReview)
            .order_by(desc(ORMReview.created_at))
            .limit(limit)
            .offset(offset)
        )
        if where:
            stmt = stmt.where(*where)
        result = await self._db.execute(stmt)
        orm_reviews = result.scalars().all()

        reviews = []
        for orm_review in orm_reviews:
            r = Review(
                order_id=orm_review.order_id,
                phone=orm_review.phone,
                rating=orm_review.rating,
                comment=orm_review.comment,
                id=orm_review.id,
                store_id=orm_review.store_id,
                created_at=orm_review.created_at,
            )
            # Resolve public_id via port (optional — nếu không có port thì bỏ qua)
            if self._order_port and orm_review.order_id:
                try:
                    # Không có reverse-lookup port method → để None (acceptable)
                    r._order_public_id = None
                except Exception:
                    r._order_public_id = None
            reviews.append(r)

        return reviews, total


# =============================================================================
# SqlReferralRepository
# =============================================================================
class SqlReferralRepository(ReferralRepository):

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save(self, referral: Referral) -> Referral:
        orm = ORMReferral(
            referrer_phone=referral.referrer_phone,
            referred_phone=referral.referred_phone,
            referrer_discount_used=referral.referrer_discount_used,
            referred_discount_used=referral.referred_discount_used,
            store_id=referral.store_id,
        )
        self._db.add(orm)
        await self._db.commit()
        await self._db.refresh(orm)
        referral.id = orm.id
        referral.created_at = orm.created_at
        return referral

    async def count_by_referrer(self, referrer_phone: str) -> int:
        result = await self._db.execute(
            select(func.count(ORMReferral.id)).where(
                ORMReferral.referrer_phone == referrer_phone
            )
        )
        return result.scalar() or 0


# =============================================================================
# SqlTrackingEventRepository
# =============================================================================
class SqlTrackingEventRepository(TrackingEventRepository):

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save(self, event: TrackingEvent) -> TrackingEvent:
        orm = ORMEvent(
            event_type=event.event_type,
            feature=event.feature,
            data=event.data,
            phone=event.phone,
            order_id=event.order_id,
            value=event.value,
            store_id=event.store_id,
        )
        self._db.add(orm)
        await self._db.commit()
        await self._db.refresh(orm)
        event.id = orm.id
        event.created_at = orm.created_at
        return event
# =============================================================================
class SqlReorderService(ReorderService):
    """Lấy đơn gần nhất của khách để reorder — dùng OrderAnalyticsPort."""

    def __init__(self, order_port: OrderAnalyticsPort) -> None:
        self._order_port = order_port

    async def get_last_order(self, phone: str) -> ReorderData | None:
        data = await self._order_port.get_last_completed_order_by_phone(phone)
        if not data:
            return None
        return ReorderData(
            public_id=data.public_id,
            total=data.total,
            items=[
                ReorderItem(
                    product_name=it.product_name,
                    product_id=it.product_id,
                    size=it.size,
                    sweetness=it.sweetness,
                    ice_level=it.ice_level,
                    quantity=it.quantity,
                    toppings_text=it.toppings_text,
                )
                for it in data.items
            ],
            created_at=data.created_at,
        )
# =============================================================================
class SqlAnalyticsService(AnalyticsService):
    """Analytics tổng hợp cho chủ quán — dùng OrderAnalyticsPort."""

    def __init__(self, db: AsyncSession, order_port: OrderAnalyticsPort) -> None:
        self._db = db
        self._order_port = order_port

    async def generate_report(self, days: int = 7) -> AnalyticsReport:
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)

        revenue_data = await self._order_port.get_revenue_by_day(since)
        revenue_by_day = [
            RevenueByDay(day=r.day, order_count=r.order_count, revenue=r.revenue)
            for r in revenue_data
        ]

        top_data = await self._order_port.get_top_products(since)
        top_products = [
            TopProduct(name=r.name, quantity=r.quantity, revenue=r.revenue)
            for r in top_data
        ]

        peak_data = await self._order_port.get_peak_hours(since)
        peak_hours = [
            PeakHour(hour=r.hour, order_count=r.order_count)
            for r in peak_data
        ]

        stats = await self._order_port.get_order_stats(since)
        total_period = stats.total_in_period or 1
        cancel_rate = round(stats.cancelled_in_period / total_period * 100, 1)

        # Customer stats từ Growth's own DB
        total_customers = (
            await self._db.execute(select(func.count(ORMCustomer.id)))
        ).scalar() or 0
        repeat_customers = (
            await self._db.execute(
                select(func.count(ORMCustomer.id)).where(ORMCustomer.order_count >= 2)
            )
        ).scalar() or 0

        # Feature effectiveness từ Growth's own Event table
        feature_stats: dict[str, FeatureEffectiveness] = {}
        for f in ["upsell", "reorder", "cross_sell", "referral"]:
            shown = (await self._db.execute(
                select(func.count(ORMEvent.id)).where(
                    ORMEvent.feature == f,
                    ORMEvent.event_type.like("%shown%"),
                    ORMEvent.created_at >= since,
                )
            )).scalar() or 0
            accepted = (await self._db.execute(
                select(func.count(ORMEvent.id)).where(
                    ORMEvent.feature == f,
                    ORMEvent.event_type.like("%accepted%"),
                    ORMEvent.created_at >= since,
                )
            )).scalar() or 0
            total_value = (await self._db.execute(
                select(func.coalesce(func.sum(ORMEvent.value), 0)).where(
                    ORMEvent.feature == f,
                    ORMEvent.event_type.like("%accepted%"),
                    ORMEvent.created_at >= since,
                )
            )).scalar() or 0
            feature_stats[f] = FeatureEffectiveness(
                shown=shown,
                accepted=accepted,
                conversion=round(accepted / shown * 100, 1) if shown > 0 else 0,
                total_value=total_value,
            )

        avg_rating = (await self._db.execute(
            select(func.avg(ORMReview.rating)).where(ORMReview.created_at >= since)
        )).scalar()

        return AnalyticsReport(
            period_days=days,
            revenue_by_day=revenue_by_day,
            top_products=top_products,
            peak_hours=peak_hours,
            total_customers=total_customers,
            repeat_customers=repeat_customers,
            repeat_rate=(
                round(repeat_customers / total_customers * 100, 1)
                if total_customers > 0 else 0
            ),
            cancel_rate=cancel_rate,
            feature_stats=feature_stats,
            avg_rating=round(avg_rating, 1) if avg_rating else None,
        )


# =============================================================================
# SqlGrowthSettingsRepository — Cài đặt kinh doanh từ admin panel
# =============================================================================
class SqlGrowthSettingsRepository(GrowthSettingsRepository):
    """
    Đọc/ghi growth settings từ bảng growth_settings.
    Chủ quán chỉnh REFERRAL_DISCOUNT, LOYALTY_THRESHOLD... từ admin panel.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_all(self) -> list[GrowthSettingDTO]:
        """Lấy tất cả settings, order by id."""
        result = await self._db.execute(
            select(ORMGrowthSetting).order_by(ORMGrowthSetting.id)
        )
        return [self._to_dto(orm) for orm in result.scalars().all()]

    async def get_value(self, key: str, default: int = 0) -> int:
        """Lấy giá trị 1 setting. Fallback về default nếu không tìm thấy."""
        result = await self._db.execute(
            select(ORMGrowthSetting.value).where(ORMGrowthSetting.key == key)
        )
        value = result.scalar_one_or_none()
        return value if value is not None else default

    async def update(self, key: str, value: int) -> GrowthSettingDTO | None:
        """Cập nhật giá trị. Validate min/max trước khi lưu."""
        result = await self._db.execute(
            select(ORMGrowthSetting).where(ORMGrowthSetting.key == key)
        )
        orm = result.scalar_one_or_none()
        if not orm:
            return None

        # Validate min/max
        from app.shared.exceptions import ValidationError
        if value < orm.min_value or value > orm.max_value:
            raise ValidationError(
                f"Giá trị phải từ {orm.min_value} đến {orm.max_value}{orm.unit}"
            )

        orm.value = value
        await self._db.commit()
        await self._db.refresh(orm)
        return self._to_dto(orm)

    @staticmethod
    def _to_dto(orm: ORMGrowthSetting) -> GrowthSettingDTO:
        return GrowthSettingDTO(
            key=orm.key,
            value=orm.value,
            label=orm.label,
            description=orm.description,
            min_value=orm.min_value,
            max_value=orm.max_value,
            unit=orm.unit,
        )
