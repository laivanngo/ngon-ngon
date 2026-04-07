"""
CRM Context — Presentation Schemas
=========================================
Pydantic models cho HTTP request/response.

WHY minimal schemas cho Growth context:
- Hầu hết endpoints nhận query params hoặc raw dict → không cần schema phức tạp.
- Response schemas chủ yếu dùng dict (giữ nguyên contract với frontend).
- Chỉ tạo schema khi CẦN validation (review, event).

Giữ response format 100% tương thích với growth.py gốc → frontend không đổi.
"""

from dataclasses import asdict

from pydantic import BaseModel, Field, field_validator

from app.crm.domain.services import (
    AnalyticsReport,
    FeatureEffectiveness,
    ReorderData,
)


# =============================================================================
# Request Schemas
# =============================================================================
class ReviewCreate(BaseModel):
    """Request body cho POST /reviews."""

    rating: int = Field(ge=1, le=5, description="Đánh giá 1-5 sao")
    order_id: int | None = None
    order_public_id: str | None = Field(default=None, max_length=50, description="UUID public_id từ frontend")
    phone: str = Field(default="", max_length=15)
    comment: str | None = Field(default=None, max_length=500)


class EventCreate(BaseModel):
    """Request body cho POST /events. Flexible — không cần tất cả fields."""

    event_type: str = Field(default="unknown", max_length=50, alias="type")
    feature: str = Field(default="unknown", max_length=30)

    model_config = {"populate_by_name": True}
    data: dict | None = None
    phone: str | None = Field(default=None, max_length=15)
    order_id: int | None = None
    value: int = 0


class SettingUpdate(BaseModel):
    """Request body cho PATCH /settings/{key}."""

    value: int = Field(ge=0, description="Giá trị mới")


# =============================================================================
# Response Helpers — Convert DTOs sang JSON-friendly dicts
# =============================================================================
def reorder_to_dict(data: ReorderData | None) -> dict:
    if not data:
        return {"order": None}
    return {
        "order": {
            "public_id": data.public_id,
            "total": data.total,
            "items": [
                {
                    "product_name": it.product_name,
                    "product_id": it.product_id,
                    "size": it.size,
                    "sweetness": it.sweetness,
                    "ice_level": it.ice_level,
                    "quantity": it.quantity,
                    "toppings_text": it.toppings_text,
                }
                for it in data.items
            ],
            "created_at": data.created_at,
        }
    }


def analytics_to_dict(report: AnalyticsReport) -> dict:
    """
    Convert AnalyticsReport DTO → dict.
    Giữ nguyên 100% JSON structure với growth.py gốc → frontend không đổi.
    """
    return {
        "period_days": report.period_days,
        "revenue_by_day": [
            {"day": r.day, "orders": r.order_count, "revenue": r.revenue}
            for r in report.revenue_by_day
        ],
        "top_products": [
            {"name": p.name, "quantity": p.quantity, "revenue": p.revenue}
            for p in report.top_products
        ],
        "peak_hours": [
            {"hour": h.hour, "orders": h.order_count}
            for h in report.peak_hours
        ],
        "total_customers": report.total_customers,
        "repeat_customers": report.repeat_customers,
        "repeat_rate": report.repeat_rate,
        "cancel_rate": report.cancel_rate,
        "feature_stats": {
            k: {
                "shown": v.shown,
                "accepted": v.accepted,
                "conversion": v.conversion,
                "total_value": v.total_value,
            }
            for k, v in report.feature_stats.items()
        },
        "avg_rating": report.avg_rating,
    }
