"""
CRM Context — Thin Router
================================
TRƯỚC: 10 factory functions + 10 endpoints = 250 dòng trộn lẫn DI + HTTP.
SAU:   Factories → dependencies.py. Router thuần HTTP mapping.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.identity.presentation.middleware import require_admin
from app.identity.domain.entities import CurrentAdmin

from app.crm.application.use_cases import (
    GetAnalyticsUseCase,
    GetCustomerInfoUseCase,
    GetGrowthConfigUseCase,
    GetGrowthSettingsUseCase,
    GetReorderUseCase,
    GetReferralUseCase,
    GetReviewsUseCase,
    LogEventCommand,
    LogTrackingEventUseCase,
    SubmitReviewCommand,
    SubmitReviewUseCase,
    UpdateGrowthSettingUseCase,
)
from app.crm.presentation.dependencies import (
    get_growth_config, get_log_event,
    get_reorder, get_customer_info,
    get_submit_review, get_referral, get_analytics,
    get_reviews_list, get_growth_settings, get_update_setting,
)
from app.crm.presentation.schemas import (
    EventCreate,
    ReviewCreate,
    SettingUpdate,
    analytics_to_dict,
    reorder_to_dict,
)
from app.shared.exceptions import DomainError, NotFoundError

logger = logging.getLogger("ngonngon.crm.router")
router = APIRouter()


# =============================================================================
# PUBLIC ENDPOINTS
# =============================================================================

@router.get("/config")
async def get_config(
    phone: str = Query(None),
    use_case: GetGrowthConfigUseCase = Depends(get_growth_config),
):
    return await use_case.execute(phone)


@router.post("/events")
async def log_event(
    payload: EventCreate,
    use_case: LogTrackingEventUseCase = Depends(get_log_event),
):
    cmd = LogEventCommand(
        event_type=payload.event_type,
        feature=payload.feature,
        data=payload.data,
        phone=payload.phone,
        order_id=payload.order_id,
        value=payload.value,
    )
    event = await use_case.execute(cmd)
    return {"success": True, "event_id": event.id}
@router.get("/reorder")
async def reorder(
    phone: str = Query(...),
    use_case: GetReorderUseCase = Depends(get_reorder),
):
    result = await use_case.execute(phone)
    if not result:
        return {"has_history": False, "items": []}
    return reorder_to_dict(result)
@router.get("/customer")
async def customer_info(
    phone: str = Query(...),
    use_case: GetCustomerInfoUseCase = Depends(get_customer_info),
):
    result = await use_case.execute(phone)
    if not result:
        return {"found": False}
    return {"found": True, **result}


@router.post("/reviews")
async def submit_review(
    payload: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    use_case: SubmitReviewUseCase = Depends(get_submit_review),
):
    try:
        order_id = payload.order_id
        if not order_id and payload.order_public_id:
            # Resolve public_id → integer id qua OrderAnalyticsPort
            from app.ordering.infrastructure.analytics_adapter import SqlOrderAnalyticsAdapter
            order_id = await SqlOrderAnalyticsAdapter(db).get_order_id_by_public_id(
                payload.order_public_id
            )

        cmd = SubmitReviewCommand(
            order_id=order_id,
            phone=payload.phone,
            rating=payload.rating,
            comment=payload.comment,
        )
        result = await use_case.execute(cmd)

        if isinstance(result, dict):
            return {"success": True, "message": result.get("message", "OK")}
        return {"success": True, "review_id": result.id}
    except DomainError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/referral")
async def referral(
    phone: str = Query(...),
    use_case: GetReferralUseCase = Depends(get_referral),
):
    result = await use_case.execute(phone)
    if not result:
        return {"found": False}
    return {"found": True, **result}


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@router.get("/analytics")
async def analytics(
    admin: CurrentAdmin = Depends(require_admin),
    use_case: GetAnalyticsUseCase = Depends(get_analytics),
):
    report = await use_case.execute()
    return analytics_to_dict(report)


@router.get("/reviews/list")
async def list_reviews(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    rating: int = Query(None, ge=1, le=5),
    admin: CurrentAdmin = Depends(require_admin),
    use_case: GetReviewsUseCase = Depends(get_reviews_list),
):
    return await use_case.execute(limit=limit, offset=offset, rating=rating)
@router.get("/settings")
async def get_settings(
    admin: CurrentAdmin = Depends(require_admin),
    use_case: GetGrowthSettingsUseCase = Depends(get_growth_settings),
):
    """Lấy tất cả cài đặt kinh doanh cho admin panel."""
    settings = await use_case.execute()
    return {
        "settings": [
            {
                "key": s.key,
                "value": s.value,
                "label": s.label,
                "description": s.description,
                "min_value": s.min_value,
                "max_value": s.max_value,
                "unit": s.unit,
            }
            for s in settings
        ]
    }


@router.patch("/settings/{key}")
async def update_setting(
    key: str,
    payload: SettingUpdate,
    admin: CurrentAdmin = Depends(require_admin),
    use_case: UpdateGrowthSettingUseCase = Depends(get_update_setting),
):
    """Cập nhật 1 cài đặt kinh doanh."""
    try:
        result = await use_case.execute(key, payload.value, admin.username)
        return {"key": result.key, "value": result.value, "unit": result.unit}
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' không tồn tại")
