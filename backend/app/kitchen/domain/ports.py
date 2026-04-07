"""
Kitchen Context — Domain Ports (Inbound/Outbound)
====================================================
Ports là các interface mà Kitchen domain cần từ thế giới bên ngoài.

DEPENDENCY RULE:
    Domain defines the port (interface).
    Infrastructure (hoặc context khác) provides the adapter (implementation).
    Domain không bao giờ import infrastructure.

OrderStatusPort — Kitchen cần cập nhật trạng thái đơn hàng.
WHY port thay vì import trực tiếp Ordering use case:
    - Kitchen không biết Ordering context tồn tại
    - Ordering có thể thay đổi internal implementation mà không vỡ Kitchen
    - Test Kitchen mà không cần Ordering: dùng FakeOrderStatusPort
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StatusUpdateResult:
    """Kết quả sau khi cập nhật trạng thái đơn hàng."""
    public_id: str
    new_status: str   # "confirmed", "preparing", "delivering", "done", "cancelled"


class OrderStatusPort(ABC):
    """
    Port cho phép Kitchen context yêu cầu thay đổi trạng thái đơn.

    Adapter: ordering/infrastructure/kitchen_adapter.KitchenOrderStatusAdapter
    Fake:    kitchen/tests/fakes.FakeOrderStatusPort (cho unit test)
    """

    @abstractmethod
    async def update_status(
        self,
        public_id: str,
        new_status: str,
        updated_by: str = "kds",
    ) -> StatusUpdateResult:
        """
        Cập nhật trạng thái đơn hàng.

        Args:
            public_id:  UUID string của đơn hàng
            new_status: trạng thái mới (phải hợp lệ theo domain rules)
            updated_by: actor thực hiện ("kds", "admin")

        Raises:
            NotFoundError:              đơn không tồn tại
            InvalidStatusTransitionError: transition không hợp lệ
            DomainError:                lỗi business khác
        """
        ...
