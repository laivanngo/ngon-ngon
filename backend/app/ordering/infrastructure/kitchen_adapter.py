"""
Ordering Context — Kitchen Adapter
=====================================
Implementation của kitchen/domain/ports.OrderStatusPort.

Ordering context sở hữu đơn hàng và logic thay đổi trạng thái.
Kitchen muốn thay đổi trạng thái → gọi qua adapter này.

PATTERN: Outbound Adapter (Driven Adapter)
    Kitchen Port (interface) ← [KitchenOrderStatusAdapter] ← Ordering UseCase

WHY adapter nằm trong ordering/ (không phải kitchen/):
    - Adapter implement port bằng cách dùng Ordering internals
    - Ordering infrastructure mới có quyền dùng SqlOrderRepository, event_bus
    - Kitchen không biết, không cần biết chi tiết implementation
"""

from __future__ import annotations

from app.kitchen.domain.ports import OrderStatusPort, StatusUpdateResult
from app.ordering.application.use_cases import UpdateStatusCommand, UpdateStatusUseCase
from app.ordering.infrastructure.repository import SqlOrderRepository
from app.shared.events import event_bus
from app.shared.exceptions import NotFoundError, InvalidStatusTransitionError, DomainError


class KitchenOrderStatusAdapter(OrderStatusPort):
    """
    Adapter: translate Kitchen's OrderStatusPort calls
             → Ordering's UpdateStatusUseCase.

    Lifecycle: 1 instance per HTTP request (tạo trong DI factory).
    """

    def __init__(self, use_case: UpdateStatusUseCase) -> None:
        self._use_case = use_case

    async def update_status(
        self,
        public_id: str,
        new_status: str,
        updated_by: str = "kds",
    ) -> StatusUpdateResult:
        """
        Gọi UpdateStatusUseCase của Ordering, convert result sang port DTO.
        Exceptions từ domain được re-raise trực tiếp (cùng exception hierarchy).
        """
        command = UpdateStatusCommand(
            public_id=public_id,
            new_status=new_status,
            updated_by=updated_by,
        )
        order = await self._use_case.execute(command)
        return StatusUpdateResult(
            public_id=order.public_id,
            new_status=order.status.value,
        )
