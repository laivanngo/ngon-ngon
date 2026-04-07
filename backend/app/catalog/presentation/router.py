"""
Catalog Presentation — Public Router (Menu API)
==================================================
Replaces: routers/menu.py (223 dòng → ~60 dòng)

TRƯỚC: Factory functions nằm ngay trong file router.
SAU:   Import từ dependencies.py → router thuần HTTP mapping.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.catalog.application.queries import (
    GetCategoryMenu, GetCrossSellConfig, GetFullMenu,
    GetProduct, GetTimeDeals, GetToppings,
)
from app.catalog.presentation.dependencies import (
    get_full_menu, get_category_menu, get_product,
    get_toppings, get_time_deals, get_cross_sell_config,
)

router = APIRouter()


@router.get("/menu")
async def full_menu(query: GetFullMenu = Depends(get_full_menu)):
    return await query.execute()


@router.get("/menu/{slug}")
async def category_menu(slug: str, query: GetCategoryMenu = Depends(get_category_menu)):
    result = await query.execute(slug)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Danh mục '{slug}' không tồn tại",
        )
    return result


@router.get("/products/{legacy_id}")
async def product_detail(legacy_id: str, query: GetProduct = Depends(get_product)):
    result = await query.execute(legacy_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm '{legacy_id}' không tồn tại",
        )
    return result


@router.get("/toppings")
async def toppings_list(query: GetToppings = Depends(get_toppings)):
    return await query.execute()


@router.get("/time-deals")
async def time_deals_list(query: GetTimeDeals = Depends(get_time_deals)):
    return await query.execute()


@router.get("/cross-sell-config")
async def cross_sell_config(query: GetCrossSellConfig = Depends(get_cross_sell_config)):
    return await query.execute()
