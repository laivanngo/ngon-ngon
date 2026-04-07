"""
Kitchen Context — Dependency Injection
=========================================
NƠI DUY NHẤT quyết định: Kitchen context dùng implementation nào.

TRƯỚC:
  - get_update_status: import từ ordering/presentation/dependencies (vi phạm tầng)
  - SqlKitchenOrderRepository(db): trực tiếp dùng Ordering ORM (vi phạm boundary)

SAU:
  - OrderStatusPort: Kitchen biết interface, Ordering cung cấp adapter
  - KitchenQueuePort: Kitchen biết interface, Ordering cung cấp adapter
  - Kitchen router/repository không biết Ordering tồn tại

WIRING MAP:
  OrderStatusPort    ← KitchenOrderStatusAdapter ← UpdateStatusUseCase
  KitchenQueuePort   ← SqlKitchenQueueAdapter    ← Order ORM (Ordering owns)
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.kitchen.application.use_cases import GetKitchenQueueUseCase, KdsAuthUseCase
from app.kitchen.domain.ports import OrderStatusPort
from app.kitchen.infrastructure.repository import ConfigPinAuthService, SqlKitchenOrderRepository
from app.ordering.application.use_cases import UpdateStatusUseCase
from app.ordering.infrastructure.kitchen_adapter import KitchenOrderStatusAdapter
from app.ordering.infrastructure.kitchen_queue_adapter import SqlKitchenQueueAdapter
from app.ordering.infrastructure.repository import SqlOrderRepository
from app.shared.events import event_bus


# =============================================================================
# Kitchen's Own Use Cases
# =============================================================================

def get_kitchen_queue(db: AsyncSession = Depends(get_db)) -> GetKitchenQueueUseCase:
    """
    Queue bếp: danh sách đơn cần pha chế.

    SqlKitchenOrderRepository nhận KitchenQueuePort — không import Ordering ORM.
    SqlKitchenQueueAdapter implement port đó, nằm trong Ordering context.
    """
    return GetKitchenQueueUseCase(
        kitchen_repo=SqlKitchenOrderRepository(
            db=db,
            queue_port=SqlKitchenQueueAdapter(db),
        )
    )


def get_kds_auth() -> KdsAuthUseCase:
    """Xác thực KDS bằng PIN 4 số."""
    return KdsAuthUseCase(auth_service=ConfigPinAuthService())


# =============================================================================
# Cross-context: Kitchen cần cập nhật trạng thái đơn
# =============================================================================

def get_order_status_port(db: AsyncSession = Depends(get_db)) -> OrderStatusPort:
    """
    Wire OrderStatusPort cho Kitchen context.

    Pattern: Port (Kitchen biết) ← Adapter (Ordering implement) ← UseCase
    Kitchen router chỉ type-hint OrderStatusPort — không biết gì về Ordering.
    """
    use_case = UpdateStatusUseCase(
        order_repo=SqlOrderRepository(db),
        event_bus=event_bus,
    )
    return KitchenOrderStatusAdapter(use_case=use_case)
