"""
Kitchen Context — Thin Router
=================================
TRƯỚC: Import trực tiếp UpdateStatusUseCase từ Ordering context (vi phạm ranh giới).
SAU:   Dùng OrderStatusPort (interface của Kitchen) — Kitchen không biết Ordering tồn tại.

CROSS-CONTEXT COMMUNICATION:
- GET /kds/orders         → Kitchen's GetKitchenQueueUseCase (Kitchen owns read model)
- PATCH /kds/orders/{id}  → OrderStatusPort (adapter trong Ordering implement port này)
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.identity.infrastructure.auth import token_service
from app.kitchen.application.use_cases import GetKitchenQueueUseCase, KdsAuthUseCase
from app.kitchen.domain.ports import OrderStatusPort
from app.kitchen.presentation.dependencies import get_kitchen_queue, get_kds_auth, get_order_status_port
from app.shared.exceptions import DomainError, InvalidStatusTransitionError, NotFoundError

logger = logging.getLogger("ngonngon.kitchen.router")
router = APIRouter()


# =============================================================================
# Dependency: verify KDS JWT token
# =============================================================================
async def require_kds_token(token: str = Query(None, alias="token")) -> str:
    """Verify JWT cho KDS API calls."""
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    subject = token_service.decode_token(token)
    if not subject:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")
    return subject


# =============================================================================
# POST /kds/auth — PIN authentication
# =============================================================================
@router.post("/auth")
async def kds_auth(
    payload: dict,
    request: Request,
    use_case: KdsAuthUseCase = Depends(get_kds_auth),
):
    """Xác thực KDS bằng PIN 4 số → JWT token (12h)."""
    pin = str(payload.get("pin", "")).strip()
    client_ip = request.client.host if request.client else "unknown"

    try:
        result = await use_case.execute(pin, client_ip)
        return {
            "access_token": result.access_token,
            "token_type": result.token_type,
            "expires_in": result.expires_in,
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


# =============================================================================
# GET /kds/orders — Kitchen queue
# =============================================================================
@router.get("/orders")
async def kds_orders(
    _auth: str = Depends(require_kds_token),
    use_case: GetKitchenQueueUseCase = Depends(get_kitchen_queue),
):
    """Tất cả đơn hàng mà KDS cần hiển thị."""
    from datetime import datetime, timezone

    orders = await use_case.execute()
    return {
        "orders": [asdict(o) for o in orders],
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# PATCH /kds/orders/{public_id}/status — Bếp chuyển trạng thái
# =============================================================================
@router.patch("/orders/{public_id}/status")
async def kds_update_status(
    public_id: str,
    payload: dict,
    _auth: str = Depends(require_kds_token),
    port: OrderStatusPort = Depends(get_order_status_port),
):
    """
    Bếp chuyển trạng thái đơn hàng qua OrderStatusPort.
    Kitchen không biết Ordering context — chỉ gọi port interface.
    """
    new_status = str(payload.get("status", ""))
    if not new_status:
        raise HTTPException(status_code=400, detail="status là bắt buộc")

    try:
        result = await port.update_status(
            public_id=public_id,
            new_status=new_status,
            updated_by="kds",
        )
        return {
            "success": True,
            "new_status": result.new_status,
        }
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    except (InvalidStatusTransitionError, DomainError) as e:
        raise HTTPException(status_code=400, detail=e.message)
