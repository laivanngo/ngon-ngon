"""
Catalog Context — Dependency Injection
=========================================
NƠI DUY NHẤT quyết định: Catalog context dùng implementation nào.

TRƯỚC: Catalog admin_router tạo SqlProductRepository(...) inline trong endpoint.
       Catalog public router có factory nhưng nằm trong router file.
SAU:   Tất cả factory nằm ở đây. Router chỉ Depends(get_full_menu).

ADMIN CRUD pattern:
- Admin commands (Create/Update/Delete) nhận repository qua factory
- Mỗi command = 1 factory function
- Router không biết dùng SQL hay InMemory
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

# --- Queries (public menu) ---
from app.catalog.application.queries import (
    GetCategoryMenu, GetCrossSellConfig, GetFullMenu,
    GetProduct, GetTimeDeals, GetToppings,
    ListAllCategories, ListAllCrossSell, ListAllProducts, ListAllToppings,
)

# --- Commands (admin CRUD) ---
from app.catalog.application.commands import (
    CreateCategory, CreateCrossSell, CreateProduct, CreateTopping,
    DeleteCategory, DeleteCrossSell, DeleteProduct, DeleteTopping,
    UpdateCategory, UpdateCrossSell, UpdateProduct, UpdateTopping,
)

# --- Infrastructure (SQL implementations) ---
from app.catalog.infrastructure.repository import (
    SqlCategoryRepository, SqlCrossSellRepository,
    SqlProductRepository, SqlTimeDealRepository, SqlToppingRepository,
)


# =============================================================================
# Public Menu Queries
# =============================================================================

def get_full_menu(db: AsyncSession = Depends(get_db)) -> GetFullMenu:
    return GetFullMenu(SqlCategoryRepository(db))


def get_category_menu(db: AsyncSession = Depends(get_db)) -> GetCategoryMenu:
    return GetCategoryMenu(SqlCategoryRepository(db))


def get_product(db: AsyncSession = Depends(get_db)) -> GetProduct:
    return GetProduct(SqlProductRepository(db))


def get_toppings(db: AsyncSession = Depends(get_db)) -> GetToppings:
    return GetToppings(SqlToppingRepository(db))


def get_time_deals(db: AsyncSession = Depends(get_db)) -> GetTimeDeals:
    return GetTimeDeals(SqlTimeDealRepository(db))


def get_cross_sell_config(db: AsyncSession = Depends(get_db)) -> GetCrossSellConfig:
    return GetCrossSellConfig(SqlCrossSellRepository(db))


# =============================================================================
# Admin Queries (list all)
# =============================================================================

def get_list_products(db: AsyncSession = Depends(get_db)) -> ListAllProducts:
    return ListAllProducts(SqlCategoryRepository(db))


def get_list_categories(db: AsyncSession = Depends(get_db)) -> ListAllCategories:
    return ListAllCategories(SqlCategoryRepository(db))


def get_list_toppings(db: AsyncSession = Depends(get_db)) -> ListAllToppings:
    return ListAllToppings(SqlToppingRepository(db))


def get_list_cross_sell(db: AsyncSession = Depends(get_db)) -> ListAllCrossSell:
    return ListAllCrossSell(SqlCrossSellRepository(db))


# =============================================================================
# Admin Commands (CRUD)
# =============================================================================

def get_create_product(db: AsyncSession = Depends(get_db)) -> CreateProduct:
    return CreateProduct(SqlProductRepository(db))


def get_update_product(db: AsyncSession = Depends(get_db)) -> UpdateProduct:
    return UpdateProduct(SqlProductRepository(db))


def get_delete_product(db: AsyncSession = Depends(get_db)) -> DeleteProduct:
    return DeleteProduct(SqlProductRepository(db))


def get_create_category(db: AsyncSession = Depends(get_db)) -> CreateCategory:
    return CreateCategory(SqlCategoryRepository(db))


def get_update_category(db: AsyncSession = Depends(get_db)) -> UpdateCategory:
    return UpdateCategory(SqlCategoryRepository(db))


def get_delete_category(db: AsyncSession = Depends(get_db)) -> DeleteCategory:
    return DeleteCategory(SqlCategoryRepository(db))


def get_create_topping(db: AsyncSession = Depends(get_db)) -> CreateTopping:
    return CreateTopping(SqlToppingRepository(db))


def get_update_topping(db: AsyncSession = Depends(get_db)) -> UpdateTopping:
    return UpdateTopping(SqlToppingRepository(db))


def get_delete_topping(db: AsyncSession = Depends(get_db)) -> DeleteTopping:
    return DeleteTopping(SqlToppingRepository(db))


def get_create_cross_sell(db: AsyncSession = Depends(get_db)) -> CreateCrossSell:
    return CreateCrossSell(SqlCrossSellRepository(db), SqlProductRepository(db))


def get_update_cross_sell(db: AsyncSession = Depends(get_db)) -> UpdateCrossSell:
    return UpdateCrossSell(SqlCrossSellRepository(db))


def get_delete_cross_sell(db: AsyncSession = Depends(get_db)) -> DeleteCrossSell:
    return DeleteCrossSell(SqlCrossSellRepository(db))
