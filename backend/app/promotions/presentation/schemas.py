"""
Promotions Context — Presentation Schemas
============================================
Pydantic models + response helpers cho Promotions endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.promotions.domain.flash_sale import FlashSale
from app.promotions.domain.services import (
    CrossSellSuggestion,
    UpsellStats,
)


class FlagToggle(BaseModel):
    """Request body cho PATCH /flags/{key}."""
    enabled: bool = False


# =============================================================================
# Flash Sale Schemas
# =============================================================================

class FlashSaleCreate(BaseModel):
    """Request body cho POST /flash-sales."""
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: str | None = Field(None, max_length=300)
    discount_percent: int = Field(..., ge=1, le=90)
    product_ids: list[int] = []
    max_quantity: int = Field(..., ge=1)
    starts_at: datetime
    ends_at: datetime


class FlashSaleResponse(BaseModel):
    """Full response cho admin."""
    id: int
    title: str
    subtitle: str | None
    discount_percent: int
    product_ids: list[int]
    max_quantity: int
    claimed_count: int
    remaining: int
    starts_at: datetime
    ends_at: datetime
    status: str
    created_at: datetime | None


class ActiveFlashSalePublic(BaseModel):
    """Customer-facing response (minimal info cho banner)."""
    id: int
    title: str
    subtitle: str | None
    discount_percent: int
    product_ids: list[int]
    remaining: int
    max_quantity: int
    ends_at: datetime


def flash_sale_to_response(sale: FlashSale) -> dict:
    """Domain entity → full response dict."""
    return FlashSaleResponse(
        id=sale.id,
        title=sale.title,
        subtitle=sale.subtitle,
        discount_percent=sale.discount_percent,
        product_ids=sale.product_ids,
        max_quantity=sale.max_quantity,
        claimed_count=sale.claimed_count,
        remaining=sale.remaining,
        starts_at=sale.starts_at,
        ends_at=sale.ends_at,
        status=sale.status.value,
        created_at=sale.created_at,
    ).model_dump(mode="json")


def flash_sale_to_public(sale: FlashSale) -> dict:
    """Domain entity → customer-facing dict."""
    return ActiveFlashSalePublic(
        id=sale.id,
        title=sale.title,
        subtitle=sale.subtitle,
        discount_percent=sale.discount_percent,
        product_ids=sale.product_ids,
        remaining=sale.remaining,
        max_quantity=sale.max_quantity,
        ends_at=sale.ends_at,
    ).model_dump(mode="json")


def upsell_stats_to_dict(stats: UpsellStats) -> dict:
    return {
        "topping_pct": stats.topping_pct,
        "size_pct": stats.size_pct,
        "total_orders": stats.total_orders,
    }


def cross_sell_to_dict(suggestions: list[CrossSellSuggestion]) -> dict:
    return {
        "suggestions": [
            {
                "id": s.id,
                "legacy_id": s.legacy_id,
                "name": s.name,
                "price": s.price,
                "emoji": s.emoji,
                "freq": s.freq,
            }
            for s in suggestions
        ]
    }
