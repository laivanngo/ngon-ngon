"""
CRM Context — Dependency Injection
========================================
NƠI DUY NHẤT quyết định: Growth context dùng implementation nào.

TRƯỚC: SqlUpsellStatsService(db), SqlReorderService(db)... — dùng ORM trực tiếp.
SAU:   Inject OrderAnalyticsPort + CatalogAnalyticsPort → Growth không biết ORM context khác.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.crm.application.use_cases import (
    GetAnalyticsUseCase,
    GetCustomerInfoUseCase,
    GetGrowthConfigUseCase,
    GetGrowthSettingsUseCase,
    GetReorderUseCase,
    GetReferralUseCase,
    GetReviewsUseCase,
    LogTrackingEventUseCase,
    SubmitReviewUseCase,
    UpdateGrowthSettingUseCase,
)
from app.crm.infrastructure.repository import (
    SqlAnalyticsService,
    SqlCustomerRepository,
    SqlGrowthSettingsRepository,
    SqlReferralRepository,
    SqlReorderService,
    SqlReviewRepository,
    SqlTrackingEventRepository,
)
from app.ordering.infrastructure.analytics_adapter import SqlOrderAnalyticsAdapter
from app.promotions.infrastructure.flag_adapter import SqlFeatureFlagReadAdapter


# =============================================================================
# Port factories — tạo 1 lần, inject vào nhiều services trong cùng request
# =============================================================================

def _order_port(db: AsyncSession) -> SqlOrderAnalyticsAdapter:
    return SqlOrderAnalyticsAdapter(db)


# =============================================================================
# Public Use Cases
# =============================================================================

def get_growth_config(db: AsyncSession = Depends(get_db)) -> GetGrowthConfigUseCase:
    """Config trang chủ: feature flags + customer data."""
    return GetGrowthConfigUseCase(
        flag_port=SqlFeatureFlagReadAdapter(db),
        customer_repo=SqlCustomerRepository(db),
    )


def get_log_event(db: AsyncSession = Depends(get_db)) -> LogTrackingEventUseCase:
    return LogTrackingEventUseCase(event_repo=SqlTrackingEventRepository(db))
def get_reorder(db: AsyncSession = Depends(get_db)) -> GetReorderUseCase:
    return GetReorderUseCase(reorder_service=SqlReorderService(_order_port(db)))
def get_customer_info(db: AsyncSession = Depends(get_db)) -> GetCustomerInfoUseCase:
    return GetCustomerInfoUseCase(customer_repo=SqlCustomerRepository(db))


def get_submit_review(db: AsyncSession = Depends(get_db)) -> SubmitReviewUseCase:
    return SubmitReviewUseCase(review_repo=SqlReviewRepository(db))


def get_referral(db: AsyncSession = Depends(get_db)) -> GetReferralUseCase:
    return GetReferralUseCase(
        customer_repo=SqlCustomerRepository(db),
        referral_repo=SqlReferralRepository(db),
        settings_repo=SqlGrowthSettingsRepository(db),
    )


# =============================================================================
# Admin Use Cases
# =============================================================================

def get_analytics(db: AsyncSession = Depends(get_db)) -> GetAnalyticsUseCase:
    return GetAnalyticsUseCase(
        analytics_service=SqlAnalyticsService(db, order_port=_order_port(db))
    )
def get_reviews_list(db: AsyncSession = Depends(get_db)) -> GetReviewsUseCase:
    return GetReviewsUseCase(review_repo=SqlReviewRepository(db))


def get_growth_settings(db: AsyncSession = Depends(get_db)) -> GetGrowthSettingsUseCase:
    """Lấy tất cả cài đặt kinh doanh cho admin panel."""
    return GetGrowthSettingsUseCase(settings_repo=SqlGrowthSettingsRepository(db))


def get_update_setting(db: AsyncSession = Depends(get_db)) -> UpdateGrowthSettingUseCase:
    """Cập nhật 1 cài đặt kinh doanh."""
    return UpdateGrowthSettingUseCase(settings_repo=SqlGrowthSettingsRepository(db))
