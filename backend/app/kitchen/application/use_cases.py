"""
Kitchen Context — Application Use Cases
==========================================
Use cases cho KDS (Kitchen Display System).

GetKitchenQueueUseCase: lấy danh sách đơn cho màn hình bếp.
KdsAuthUseCase: xác thực PIN → JWT token.

WHY Kitchen KHÔNG có UpdateStatusUseCase riêng:
- Status transition là business rule của Ordering context
- Kitchen reuse Ordering's UpdateStatusUseCase
- KDS router gọi trực tiếp ordering use case (cross-context read)
- Đúng DDD: Kitchen chỉ đọc queue, write qua Ordering

CROSS-CONTEXT INTERACTION:
    KDS router → (GET queue) → Kitchen's GetKitchenQueueUseCase
    KDS router → (PATCH status) → Ordering's UpdateStatusUseCase
    Cả 2 direction đều hợp lệ trong DDD (shared kernel / open host)
"""

from __future__ import annotations

import logging

from app.kitchen.domain.entities import KitchenOrder
from app.kitchen.domain.services import (
    KdsAuthResult,
    KitchenOrderRepository,
    PinAuthService,
)

logger = logging.getLogger("ngonngon.kitchen")


# =============================================================================
# GetKitchenQueue — Lấy danh sách đơn cho KDS
# =============================================================================
class GetKitchenQueueUseCase:
    """
    Lấy tất cả đơn hàng mà KDS cần hiển thị.

    TRƯỚC: 30 dòng SQL inline trong kds.py GET /kds/orders.
    SAU: Use case gọi repository, repository chứa SQL.
    """

    def __init__(self, kitchen_repo: KitchenOrderRepository) -> None:
        self._repo = kitchen_repo

    async def execute(self) -> list[KitchenOrder]:
        return await self._repo.get_active_queue()


# =============================================================================
# KdsAuth — Xác thực PIN 4 số
# =============================================================================
class KdsAuthUseCase:
    """
    Xác thực KDS bằng PIN.

    TRƯỚC: 30 dòng auth logic + rate limiting inline trong kds.py POST /kds/auth.
    SAU: Use case gọi PinAuthService (infrastructure chứa rate limit + JWT).
    """

    def __init__(self, auth_service: PinAuthService) -> None:
        self._auth = auth_service

    async def execute(self, pin: str, client_ip: str) -> KdsAuthResult:
        """
        Raise ValueError nếu PIN sai.
        Raise PermissionError nếu rate limited.
        """
        result = await self._auth.authenticate(pin, client_ip)
        logger.info("🍳 KDS authenticated")
        return result
