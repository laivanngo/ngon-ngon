"""
Promotions Context — Flash Sale Router
==========================================
Endpoints cho Flash Sale feature.

Public: GET /flash-sales/active (customer banner)
Admin:  POST /flash-sales, GET /flash-sales, PATCH /flash-sales/{id}/cancel
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.identity.domain.entities import CurrentAdmin
from app.identity.presentation.middleware import require_admin
from app.promotions.application.flash_sale_use_cases import (
    CancelFlashSaleUseCase,
    CreateFlashSaleUseCase,
    GetActiveFlashSalesUseCase,
    ListFlashSalesUseCase,
)
from app.promotions.presentation.dependencies import (
    get_active_flash_sales,
    get_cancel_flash_sale,
    get_create_flash_sale,
    get_list_flash_sales,
)
from app.promotions.presentation.schemas import (
    FlashSaleCreate,
    flash_sale_to_public,
    flash_sale_to_response,
)

logger = logging.getLogger("ngonngon.promotions.flash_sale_router")
router = APIRouter()


# =============================================================================
# PUBLIC — Customer banner
# =============================================================================

@router.get("/flash-sales/active")
async def get_active(
    use_case: GetActiveFlashSalesUseCase = Depends(get_active_flash_sales),
):
    """Flash sales đang chạy — cho customer banner + countdown."""
    now = datetime.now(timezone.utc)
    sales = await use_case.execute(now)
    return {"flash_sales": [flash_sale_to_public(s) for s in sales]}


# =============================================================================
# ADMIN — CRUD
# =============================================================================

@router.post("/flash-sales")
async def create_flash_sale(
    payload: FlashSaleCreate,
    admin: CurrentAdmin = Depends(require_admin),
    use_case: CreateFlashSaleUseCase = Depends(get_create_flash_sale),
):
    """Admin tạo flash sale mới."""
    sale = await use_case.execute(
        title=payload.title,
        discount_percent=payload.discount_percent,
        max_quantity=payload.max_quantity,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        product_ids=payload.product_ids,
        subtitle=payload.subtitle,
        admin_username=admin.username,
    )
    return flash_sale_to_response(sale)


@router.get("/flash-sales")
async def list_flash_sales(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin: CurrentAdmin = Depends(require_admin),
    use_case: ListFlashSalesUseCase = Depends(get_list_flash_sales),
):
    """Admin xem danh sách tất cả flash sales."""
    sales, total = await use_case.execute(limit=limit, offset=offset)
    return {
        "flash_sales": [flash_sale_to_response(s) for s in sales],
        "total": total,
    }


@router.patch("/flash-sales/{sale_id}/cancel")
async def cancel_flash_sale(
    sale_id: int,
    admin: CurrentAdmin = Depends(require_admin),
    use_case: CancelFlashSaleUseCase = Depends(get_cancel_flash_sale),
):
    """Admin hủy flash sale."""
    sale = await use_case.execute(sale_id, admin_username=admin.username)
    return flash_sale_to_response(sale)
