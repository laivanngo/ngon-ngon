"""
Ordering Context — Admin Router
===================================
Admin endpoints cho quản lý đơn hàng:
  GET   /admin/orders                → Danh sách đơn (filter, paginate)
  PATCH /admin/orders/{id}/status    → Chuyển trạng thái
  GET   /admin/dashboard             → Thống kê nhanh

TRƯỚC: Factory functions nằm ngay trong file này.
SAU:   Import từ dependencies.py → router chỉ lo HTTP.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.identity.presentation.middleware import require_admin
from app.identity.domain.entities import CurrentAdmin
from app.ordering.application.use_cases import (
    DashboardStats,
    GetDashboardUseCase,
    ListOrdersQuery,
    ListOrdersUseCase,
    UpdateStatusCommand,
    UpdateStatusUseCase,
)
from app.ordering.presentation.dependencies import get_dashboard, get_list_orders, get_update_status
from app.ordering.presentation.schemas import OrderResponse
from app.shared.exceptions import DomainError, InvalidStatusTransitionError, NotFoundError

logger = logging.getLogger("ngonngon.ordering.admin")
router = APIRouter()


# =============================================================================
# GET /admin/orders — Danh sách đơn hàng
# =============================================================================
@router.get("/orders")
async def list_orders(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin: CurrentAdmin = Depends(require_admin),
    use_case: ListOrdersUseCase = Depends(get_list_orders),
):
    """Danh sách đơn hàng, mới nhất trước."""
    query = ListOrdersQuery(status_filter=status_filter, limit=limit, offset=offset)
    orders, total = await use_case.execute(query)

    return {
        "items": [OrderResponse.from_domain(o) for o in orders],
        "total": total,
        "has_more": (offset + limit) < total,
    }


# =============================================================================
# PATCH /admin/orders/{public_id}/status — Chuyển trạng thái
# =============================================================================
@router.patch("/orders/{public_id}/status")
async def update_order_status(
    public_id: str,
    payload: dict,
    admin: CurrentAdmin = Depends(require_admin),
    use_case: UpdateStatusUseCase = Depends(get_update_status),
):
    """
    Cập nhật trạng thái đơn hàng.
    Cả admin và KDS đều gọi chung Ordering's UpdateStatusUseCase
    → 1 chỗ duy nhất validate transitions.
    """
    new_status = str(payload.get("status", ""))
    if not new_status:
        raise HTTPException(status_code=400, detail="status là bắt buộc")

    try:
        command = UpdateStatusCommand(
            public_id=public_id,
            new_status=new_status,
            updated_by="admin",
        )
        order = await use_case.execute(command)
        return {
            "success": True,
            "old_status": "",
            "new_status": order.status.value,
        }
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    except (InvalidStatusTransitionError, DomainError) as e:
        raise HTTPException(status_code=400, detail=e.message)


# =============================================================================
# GET /admin/dashboard — Thống kê nhanh
# =============================================================================
@router.get("/dashboard")
async def dashboard(
    admin: CurrentAdmin = Depends(require_admin),
    use_case: GetDashboardUseCase = Depends(get_dashboard),
):
    """Thống kê cơ bản cho admin panel."""
    stats = await use_case.execute()
    return {
        "orders_today": stats.orders_today,
        "revenue_today": stats.revenue_today,
        "pending_orders": stats.pending_orders,
        "active_products": stats.active_products,
    }
