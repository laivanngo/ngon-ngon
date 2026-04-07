"""
Promotions Context — Dependency Injection
============================================
NƠI DUY NHẤT quyết định: Promotions context dùng implementation nào.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.infrastructure.analytics_adapter import SqlCatalogAnalyticsAdapter
from app.database import get_db
from app.ordering.infrastructure.analytics_adapter import SqlOrderAnalyticsAdapter
from app.promotions.application.flash_sale_use_cases import (
    CancelFlashSaleUseCase,
    CreateFlashSaleUseCase,
    GetActiveFlashSalesUseCase,
    ListFlashSalesUseCase,
)
from app.promotions.application.use_cases import (
    GetCrossSellUseCase,
    GetUpsellStatsUseCase,
    ToggleFeatureFlagUseCase,
)
from app.promotions.infrastructure.flash_sale_repository import SqlFlashSaleRepository
from app.promotions.infrastructure.repository import (
    SqlCrossSellQueryService,
    SqlFeatureFlagRepository,
    SqlUpsellStatsService,
)
from app.shared.events import event_bus


def _order_port(db: AsyncSession) -> SqlOrderAnalyticsAdapter:
    return SqlOrderAnalyticsAdapter(db)


def _catalog_port(db: AsyncSession) -> SqlCatalogAnalyticsAdapter:
    return SqlCatalogAnalyticsAdapter(db)


def get_upsell_stats(db: AsyncSession = Depends(get_db)) -> GetUpsellStatsUseCase:
    return GetUpsellStatsUseCase(stats_service=SqlUpsellStatsService(_order_port(db)))


def get_cross_sell(db: AsyncSession = Depends(get_db)) -> GetCrossSellUseCase:
    return GetCrossSellUseCase(
        cross_sell_service=SqlCrossSellQueryService(
            order_port=_order_port(db),
            catalog_port=_catalog_port(db),
        )
    )


def get_toggle_flag(db: AsyncSession = Depends(get_db)) -> ToggleFeatureFlagUseCase:
    return ToggleFeatureFlagUseCase(flag_repo=SqlFeatureFlagRepository(db))


# =============================================================================
# Flash Sale DI
# =============================================================================

def _flash_sale_repo(db: AsyncSession) -> SqlFlashSaleRepository:
    return SqlFlashSaleRepository(db)


def get_create_flash_sale(
    db: AsyncSession = Depends(get_db),
) -> CreateFlashSaleUseCase:
    return CreateFlashSaleUseCase(repo=_flash_sale_repo(db), event_bus=event_bus)


def get_list_flash_sales(
    db: AsyncSession = Depends(get_db),
) -> ListFlashSalesUseCase:
    return ListFlashSalesUseCase(repo=_flash_sale_repo(db))


def get_active_flash_sales(
    db: AsyncSession = Depends(get_db),
) -> GetActiveFlashSalesUseCase:
    return GetActiveFlashSalesUseCase(repo=_flash_sale_repo(db))


def get_cancel_flash_sale(
    db: AsyncSession = Depends(get_db),
) -> CancelFlashSaleUseCase:
    return CancelFlashSaleUseCase(repo=_flash_sale_repo(db), event_bus=event_bus)
