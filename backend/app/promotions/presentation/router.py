"""
Promotions Context — Thin Router
====================================
Endpoints cho Upsell, Cross-sell, Feature Flags.
Tách từ growth router — chỉ giữ phần promotions.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.identity.presentation.middleware import require_admin
from app.identity.domain.entities import CurrentAdmin
from app.promotions.application.use_cases import (
    GetCrossSellUseCase,
    GetUpsellStatsUseCase,
    ToggleFeatureFlagUseCase,
)
from app.promotions.presentation.dependencies import (
    get_upsell_stats,
    get_cross_sell,
    get_toggle_flag,
)
from app.promotions.presentation.schemas import (
    FlagToggle,
    upsell_stats_to_dict,
    cross_sell_to_dict,
)
from app.shared.exceptions import NotFoundError

logger = logging.getLogger("ngonngon.promotions.router")
router = APIRouter()


# =============================================================================
# PUBLIC ENDPOINTS
# =============================================================================

@router.get("/upsell-stats")
async def upsell_stats(
    phone: str = Query(None, description="SĐT khách (reserved for future personalization)"),
    use_case: GetUpsellStatsUseCase = Depends(get_upsell_stats),
):
    result = await use_case.execute()
    return upsell_stats_to_dict(result)


@router.get("/cross-sell")
async def cross_sell(
    cart_ids: str = Query("", description="Comma-separated product IDs in cart"),
    use_case: GetCrossSellUseCase = Depends(get_cross_sell),
):
    suggestions = await use_case.execute(cart_ids)
    return cross_sell_to_dict(suggestions)


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@router.patch("/flags/{key}")
async def toggle_flag(
    key: str,
    payload: FlagToggle,
    admin: CurrentAdmin = Depends(require_admin),
    use_case: ToggleFeatureFlagUseCase = Depends(get_toggle_flag),
):
    try:
        flag = await use_case.execute(key, payload.enabled, admin.username)
        return {"key": flag.key, "enabled": flag.enabled}
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Flag '{key}' không tồn tại")
