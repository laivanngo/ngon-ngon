"""
Catalog Application — Queries (Read Operations)
==================================================
Queries = read-only operations, không thay đổi state.
Tách riêng khỏi commands (CQS pattern nhẹ).

WHY use case layer thay vì gọi repo trực tiếp từ router:
- Router chỉ biết HTTP, không biết business logic
- Use case orchestrate: cache check → repo call → format response
- Dễ test: mock repo, test use case logic
"""

import logging
import time
from datetime import datetime

from app.catalog.domain.repository import (
    CategoryRepository, CrossSellRepository, ProductRepository,
    TimeDealRepository, ToppingRepository,
)
from app.catalog.domain.services import CrossSellService

logger = logging.getLogger("ngonngon.catalog.queries")


# =============================================================================
# Menu Cache — giữ nguyên logic cache 5 phút từ codebase cũ
# =============================================================================
CACHE_TTL_SECONDS = 300  # 5 phút

_menu_cache: dict | None = None
_menu_cache_time: float = 0


def invalidate_menu_cache() -> None:
    """Gọi khi admin thay đổi menu. Export cho các context khác dùng."""
    global _menu_cache, _menu_cache_time
    _menu_cache = None
    _menu_cache_time = 0
    logger.info("Menu cache invalidated")


# =============================================================================
# GetFullMenu — Toàn bộ menu (categories + products + sizes + toppings)
# =============================================================================
class GetFullMenu:
    """Query: Lấy toàn bộ menu, có cache."""

    def __init__(self, category_repo: CategoryRepository):
        self._category_repo = category_repo

    async def execute(self) -> dict:
        global _menu_cache, _menu_cache_time

        # Serve from cache nếu còn fresh
        if _menu_cache and (time.time() - _menu_cache_time) < CACHE_TTL_SECONDS:
            return _menu_cache

        categories = await self._category_repo.list_active_with_products()

        result = {
            "categories": [
                {
                    "id": cat.id,
                    "slug": cat.slug,
                    "name": cat.name,
                    "emoji": cat.emoji,
                    "layout": cat.layout.value,
                    "products": [
                        _product_to_dict(p) for p in cat.active_products
                    ],
                }
                for cat in categories
            ]
        }

        # Update cache
        _menu_cache = result
        _menu_cache_time = time.time()

        return result


# =============================================================================
# GetCategoryMenu — Menu theo slug
# =============================================================================
class GetCategoryMenu:
    def __init__(self, category_repo: CategoryRepository):
        self._category_repo = category_repo

    async def execute(self, slug: str) -> dict | None:
        category = await self._category_repo.get_by_slug(slug)
        if not category or not category.is_active:
            return None
        return {
            "id": category.id,
            "slug": category.slug,
            "name": category.name,
            "emoji": category.emoji,
            "layout": category.layout.value,
            "products": [_product_to_dict(p) for p in category.active_products],
        }


# =============================================================================
# GetProduct — Chi tiết 1 sản phẩm
# =============================================================================
class GetProduct:
    def __init__(self, product_repo: ProductRepository):
        self._product_repo = product_repo

    async def execute(self, legacy_id: str) -> dict | None:
        product = await self._product_repo.get_by_legacy_id(legacy_id)
        if not product or not product.is_active:
            return None
        return _product_to_dict(product)


# =============================================================================
# GetToppings — Danh sách toppings active (public)
# =============================================================================
class GetToppings:
    def __init__(self, topping_repo: ToppingRepository):
        self._topping_repo = topping_repo

    async def execute(self) -> list[dict]:
        toppings = await self._topping_repo.list_active()
        return [
            {
                "id": t.id, "legacy_id": t.legacy_id, "name": t.name,
                "emoji": t.emoji, "price": t.price,
            }
            for t in toppings
        ]


# =============================================================================
# GetTimeDeals — Deals active tại giờ hiện tại
# =============================================================================
class GetTimeDeals:
    def __init__(self, time_deal_repo: TimeDealRepository):
        self._time_deal_repo = time_deal_repo

    async def execute(self) -> list[dict]:
        current_hour = datetime.now().hour
        deals = await self._time_deal_repo.list_active_at(current_hour)
        return [
            {
                "label": d.label, "title": d.title, "subtitle": d.subtitle,
                "start_hour": d.start_hour, "end_hour": d.end_hour,
                "discount_percent": d.discount_percent,
            }
            for d in deals
        ]


# =============================================================================
# GetCrossSellConfig — Config cho "Thêm cho đủ bữa?"
# =============================================================================
class GetCrossSellConfig:
    def __init__(self, cross_sell_repo: CrossSellRepository):
        self._cross_sell_repo = cross_sell_repo

    async def execute(self) -> dict:
        items = await self._cross_sell_repo.list_active()
        return CrossSellService.build_config(items)


# =============================================================================
# Admin Queries — list all (bao gồm inactive)
# =============================================================================
class ListAllProducts:
    """Admin: tất cả sản phẩm, nhóm theo category."""

    def __init__(self, category_repo: CategoryRepository):
        self._category_repo = category_repo

    async def execute(self) -> dict:
        categories = await self._category_repo.list_all()
        return {
            "categories": [
                {
                    "id": cat.id, "slug": cat.slug, "name": cat.name,
                    "emoji": cat.emoji,
                    "layout": cat.layout.value,
                    "sort_order": cat.sort_order,
                    "is_active": cat.is_active,
                    "products": [
                        _admin_product_to_dict(p)
                        for p in sorted(cat.products, key=lambda p: p.sort_order)
                    ],
                }
                for cat in categories
            ]
        }


class ListAllCategories:
    def __init__(self, category_repo: CategoryRepository):
        self._category_repo = category_repo

    async def execute(self) -> dict:
        categories = await self._category_repo.list_all()
        return {
            "categories": [
                {
                    "id": c.id, "slug": c.slug, "name": c.name,
                    "emoji": c.emoji,
                    "layout": c.layout.value,
                    "sort_order": c.sort_order, "is_active": c.is_active,
                }
                for c in categories
            ]
        }


class ListAllToppings:
    def __init__(self, topping_repo: ToppingRepository):
        self._topping_repo = topping_repo

    async def execute(self) -> dict:
        toppings = await self._topping_repo.list_all()
        return {
            "toppings": [
                {
                    "id": t.id, "legacy_id": t.legacy_id, "name": t.name,
                    "emoji": t.emoji, "price": t.price, "is_active": t.is_active,
                }
                for t in toppings
            ]
        }


class ListAllCrossSell:
    def __init__(self, cross_sell_repo: CrossSellRepository):
        self._cross_sell_repo = cross_sell_repo

    async def execute(self) -> dict:
        items = await self._cross_sell_repo.list_all()
        return {
            "items": [
                {
                    "id": cs.id,
                    "product_id": cs.product_id,
                    "product_name": cs.product.name if cs.product else "?",
                    "product_emoji": cs.product.emoji if cs.product else "?",
                    "product_price": cs.product.base_price if cs.product else 0,
                    "product_legacy_id": cs.product.legacy_id if cs.product else "?",
                    "target": cs.target,
                    "sort_order": cs.sort_order,
                    "is_active": cs.is_active,
                }
                for cs in items
            ]
        }


# =============================================================================
# Helpers — convert entity → dict (giữ nguyên API contract)
# =============================================================================
def _product_to_dict(p) -> dict:
    return {
        "id": p.id,
        "legacy_id": p.legacy_id,
        "name": p.name,
        "description": p.description,
        "base_price": p.base_price,
        "emoji": p.emoji,
        "image_path": p.image_path,
        "badge": p.badge,
        "bg_class": p.bg_class,
        "sold_count": p.sold_count,
        "is_drink": p.is_drink,
        "is_combo": p.is_combo,
        "combo_description": p.combo_description,
        "original_price": p.original_price,
        "save_amount": p.save_amount,
        "sizes": [{"label": s.label, "price": s.price} for s in p.sizes],
        "topping_ids": p.topping_ids,
    }


def _admin_product_to_dict(p) -> dict:
    """Admin view — gồm thêm is_active, sort_order."""
    d = _product_to_dict(p)
    d["is_active"] = p.is_active
    d["sort_order"] = p.sort_order
    return d
