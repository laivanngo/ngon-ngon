"""
Catalog Presentation — Admin Router (CRUD)
=============================================
TRƯỚC: Mỗi endpoint tự tạo SqlProductRepository(db) inline → 15 chỗ hardcode.
SAU:   Import từ dependencies.py → router thuần HTTP. Sửa implementation → 1 chỗ.

Endpoints:
  Product CRUD  (GET/POST/PATCH/DELETE /admin/products)
  Category CRUD (GET/POST/PATCH/DELETE /admin/categories)
  Topping CRUD  (GET/POST/PATCH/DELETE /admin/toppings)
  Cross-sell CRUD (GET/POST/PATCH/DELETE /admin/cross-sell)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.application.commands import (
    CreateCategory, CreateCrossSell, CreateProduct, CreateTopping,
    DeleteCategory, DeleteCrossSell, DeleteProduct, DeleteTopping,
    UpdateCategory, UpdateCrossSell, UpdateProduct, UpdateTopping,
)
from app.catalog.application.queries import (
    ListAllCategories, ListAllCrossSell, ListAllProducts, ListAllToppings,
)
from app.catalog.infrastructure.orm_models import Product as OrmProduct
from app.catalog.presentation.dependencies import (
    get_list_products, get_create_product, get_update_product, get_delete_product,
    get_list_categories, get_create_category, get_update_category, get_delete_category,
    get_list_toppings, get_create_topping, get_update_topping, get_delete_topping,
    get_list_cross_sell, get_create_cross_sell, get_update_cross_sell, get_delete_cross_sell,
)
from app.catalog.presentation.schemas import ProductCreateRequest, ProductResponse, ProductUpdateRequest
from app.database import get_db
from app.identity.presentation.middleware import require_admin
from app.identity.domain.entities import CurrentAdmin
from app.shared.exceptions import DomainError, DuplicateError, NotFoundError

router = APIRouter()


# =============================================================================
# Exception → HTTP status mapping
# =============================================================================
def _handle_domain_error(e: DomainError):
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=e.message)
    elif isinstance(e, DuplicateError):
        raise HTTPException(status_code=400, detail=e.message)
    else:
        raise HTTPException(status_code=400, detail=e.message)


# =============================================================================
# Product CRUD
# =============================================================================
@router.get("/products")
async def list_products(
    admin: CurrentAdmin = Depends(require_admin),
    query: ListAllProducts = Depends(get_list_products),
):
    return await query.execute()


@router.post("/products", status_code=201)
async def create_product(
    payload: ProductCreateRequest,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: CreateProduct = Depends(get_create_product),
    db: AsyncSession = Depends(get_db),
):
    try:
        product = await cmd.execute(
            legacy_id=payload.legacy_id,
            category_id=payload.category_id,
            name=payload.name,
            base_price=payload.base_price,
            sizes=[s.model_dump() for s in payload.sizes],
            topping_ids=payload.topping_ids,
            changed_by=admin.username,
            description=payload.description,
            emoji=payload.emoji,
            badge=payload.badge,
            bg_class=payload.bg_class,
            is_drink=payload.is_drink,
            is_combo=payload.is_combo,
            combo_description=payload.combo_description,
            original_price=payload.original_price,
            save_amount=payload.save_amount,
        )
        stmt = (
            select(OrmProduct).where(OrmProduct.id == product.id)
            .options(selectinload(OrmProduct.sizes))
            .options(selectinload(OrmProduct.product_toppings))
        )
        result = await db.execute(stmt)
        orm_product = result.scalar_one()
        return ProductResponse.model_validate(orm_product)
    except DomainError as e:
        _handle_domain_error(e)


@router.patch("/products/{product_id}")
async def update_product(
    product_id: int,
    payload: ProductUpdateRequest,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: UpdateProduct = Depends(get_update_product),
    db: AsyncSession = Depends(get_db),
):
    try:
        update_data = payload.model_dump(exclude_unset=True)
        sizes = None
        if "sizes" in update_data:
            raw_sizes = update_data.pop("sizes")
            if raw_sizes is not None:
                sizes = [{"label": s["label"], "price": s["price"]} for s in raw_sizes]
        topping_ids = update_data.pop("topping_ids", None)

        product = await cmd.execute(
            product_id=product_id,
            changed_by=admin.username,
            sizes=sizes,
            topping_ids=topping_ids,
            **update_data,
        )

        stmt = (
            select(OrmProduct).where(OrmProduct.id == product.id)
            .options(selectinload(OrmProduct.sizes))
            .options(selectinload(OrmProduct.product_toppings))
        )
        result = await db.execute(stmt)
        orm_product = result.scalar_one()
        return ProductResponse.model_validate(orm_product)
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: DeleteProduct = Depends(get_delete_product),
):
    try:
        product = await cmd.execute(product_id, changed_by=admin.username)
        return {"success": True, "message": f"Đã ẩn sản phẩm '{product.name}'"}
    except DomainError as e:
        _handle_domain_error(e)


# =============================================================================
# Category CRUD
# =============================================================================
@router.get("/categories")
async def list_categories(
    admin: CurrentAdmin = Depends(require_admin),
    query: ListAllCategories = Depends(get_list_categories),
):
    return await query.execute()


@router.post("/categories", status_code=201)
async def create_category(
    payload: dict,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: CreateCategory = Depends(get_create_category),
):
    slug = str(payload.get("slug", "")).strip()
    name = str(payload.get("name", "")).strip()
    if not slug or not name:
        raise HTTPException(status_code=400, detail="slug và name là bắt buộc")
    try:
        category = await cmd.execute(
            slug=slug, name=name,
            emoji=str(payload.get("emoji", "📦")),
            layout=payload.get("layout", "list"),
            sort_order=int(payload.get("sort_order", 0)),
            changed_by=admin.username,
        )
        return {"id": category.id, "slug": category.slug, "name": category.name}
    except DomainError as e:
        _handle_domain_error(e)


@router.patch("/categories/{category_id}")
async def update_category(
    category_id: int,
    payload: dict,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: UpdateCategory = Depends(get_update_category),
):
    try:
        category = await cmd.execute(category_id, changed_by=admin.username, **payload)
        return {"success": True, "id": category.id, "name": category.name}
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: DeleteCategory = Depends(get_delete_category),
):
    try:
        category = await cmd.execute(category_id, changed_by=admin.username)
        return {"success": True, "message": f"Đã ẩn danh mục '{category.name}'"}
    except DomainError as e:
        _handle_domain_error(e)


# =============================================================================
# Topping CRUD
# =============================================================================
@router.get("/toppings")
async def list_toppings(
    admin: CurrentAdmin = Depends(require_admin),
    query: ListAllToppings = Depends(get_list_toppings),
):
    return await query.execute()


@router.post("/toppings", status_code=201)
async def create_topping(
    payload: dict,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: CreateTopping = Depends(get_create_topping),
):
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tên topping là bắt buộc")
    try:
        topping = await cmd.execute(
            name=name, legacy_id=payload.get("legacy_id"),
            emoji=str(payload.get("emoji", "🍡")),
            price=int(payload.get("price", 5)),
            changed_by=admin.username,
        )
        return {"id": topping.id, "name": topping.name}
    except DomainError as e:
        _handle_domain_error(e)


@router.patch("/toppings/{topping_id}")
async def update_topping(
    topping_id: int,
    payload: dict,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: UpdateTopping = Depends(get_update_topping),
):
    try:
        await cmd.execute(topping_id, changed_by=admin.username, **payload)
        return {"success": True}
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/toppings/{topping_id}")
async def delete_topping(
    topping_id: int,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: DeleteTopping = Depends(get_delete_topping),
):
    try:
        await cmd.execute(topping_id, changed_by=admin.username)
        return {"success": True}
    except DomainError as e:
        _handle_domain_error(e)


# =============================================================================
# Cross-Sell CRUD
# =============================================================================
@router.get("/cross-sell")
async def list_cross_sell(
    admin: CurrentAdmin = Depends(require_admin),
    query: ListAllCrossSell = Depends(get_list_cross_sell),
):
    return await query.execute()


@router.post("/cross-sell", status_code=201)
async def create_cross_sell(
    payload: dict,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: CreateCrossSell = Depends(get_create_cross_sell),
):
    product_id = payload.get("product_id")
    if not product_id:
        raise HTTPException(status_code=400, detail="product_id là bắt buộc")
    try:
        item = await cmd.execute(
            product_id=product_id,
            target=str(payload.get("target", "both")),
            sort_order=int(payload.get("sort_order", 0)),
            changed_by=admin.username,
        )
        product_name = item.product.name if item.product else "?"
        return {"id": item.id, "product_name": product_name}
    except DomainError as e:
        _handle_domain_error(e)


@router.patch("/cross-sell/{cs_id}")
async def update_cross_sell(
    cs_id: int,
    payload: dict,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: UpdateCrossSell = Depends(get_update_cross_sell),
):
    try:
        await cmd.execute(cs_id, changed_by=admin.username, **payload)
        return {"success": True}
    except DomainError as e:
        _handle_domain_error(e)


@router.delete("/cross-sell/{cs_id}")
async def delete_cross_sell(
    cs_id: int,
    admin: CurrentAdmin = Depends(require_admin),
    cmd: DeleteCrossSell = Depends(get_delete_cross_sell),
):
    try:
        await cmd.execute(cs_id, changed_by=admin.username)
        return {"success": True}
    except DomainError as e:
        _handle_domain_error(e)
