"""
Ordering Context — Dependency Injection
==========================================
NƠI DUY NHẤT quyết định: Ordering context dùng implementation nào.

TRƯỚC: Mỗi router tự import SqlOrderRepository, SqlPricingService rồi tự lắp ráp.
       → Router biết quá nhiều về infrastructure, khó swap cho test.

SAU:   Router chỉ gọi Depends(get_place_order) — không biết bên trong là SQL hay gì.
       → Muốn test? Override 1 chỗ: app.dependency_overrides[get_place_order] = mock_factory

VÍ DỤ override cho test (không cần database):
    from app.ordering.presentation.dependencies import get_place_order
    app.dependency_overrides[get_place_order] = lambda: PlaceOrderUseCase(
        pricing_service=FakePricingService(),
        order_repo=InMemoryOrderRepository(),
        event_bus=EventBus(),
    )

WHY file riêng (không để trong router):
- 1 nơi duy nhất quyết định wiring → đổi implementation sửa 1 file
- Router chỉ lo HTTP request/response
- Nhiều router có thể share cùng factory (VD: admin + KDS đều dùng UpdateStatus)
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.ordering.application.use_cases import (
    GetDashboardUseCase,
    GetOrderUseCase,
    ListOrdersUseCase,
    PlaceOrderUseCase,
    UpdateStatusUseCase,
)
from app.catalog.infrastructure.analytics_adapter import SqlCatalogAnalyticsAdapter
from app.catalog.infrastructure.pricing_adapter import SqlCatalogPricingAdapter
from app.ordering.infrastructure.pricing import SqlPricingService
from app.ordering.infrastructure.repository import SqlDashboardQueryService, SqlOrderRepository
from app.promotions.infrastructure.flash_sale_pricing_adapter import SqlFlashSalePricingAdapter
from app.shared.events import event_bus


# =============================================================================
# Use Case Factories — mỗi request tạo 1 instance mới (stateless)
# =============================================================================

def get_place_order(db: AsyncSession = Depends(get_db)) -> PlaceOrderUseCase:
    """Tạo đơn hàng mới: tính giá → validate → persist → phát event."""
    return PlaceOrderUseCase(
        pricing_service=SqlPricingService(
            catalog_port=SqlCatalogPricingAdapter(db),
            promotions_port=SqlFlashSalePricingAdapter(db),
        ),
        order_repo=SqlOrderRepository(db),
        event_bus=event_bus,
    )


def get_order(db: AsyncSession = Depends(get_db)) -> GetOrderUseCase:
    """Tra cứu đơn hàng bằng public_id."""
    return GetOrderUseCase(order_repo=SqlOrderRepository(db))


def get_update_status(db: AsyncSession = Depends(get_db)) -> UpdateStatusUseCase:
    """
    Chuyển trạng thái đơn hàng.
    Dùng chung bởi admin router VÀ KDS router → 1 chỗ duy nhất.
    """
    return UpdateStatusUseCase(
        order_repo=SqlOrderRepository(db),
        event_bus=event_bus,
    )


def get_list_orders(db: AsyncSession = Depends(get_db)) -> ListOrdersUseCase:
    """Danh sách đơn cho admin panel (pagination + filter)."""
    return ListOrdersUseCase(order_repo=SqlOrderRepository(db))


def get_dashboard(db: AsyncSession = Depends(get_db)) -> GetDashboardUseCase:
    """Thống kê nhanh cho admin panel."""
    return GetDashboardUseCase(
        dashboard_service=SqlDashboardQueryService(
            db,
            catalog_port=SqlCatalogAnalyticsAdapter(db),
        )
    )
