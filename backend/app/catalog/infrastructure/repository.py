"""
Catalog Infrastructure — SQL Repository Implementations
=========================================================
Concrete implementations of domain repository ABCs using SQLAlchemy.

KEY DESIGN DECISIONS:
- ORM models tự khai báo trong catalog/infrastructure/orm_models.py
  → Catalog sở hữu hoàn toàn data layer của mình
- Map ORM model ↔ domain entity trong repository methods
- selectinload cho relationships → tránh N+1

WHY không tạo ORM models mới:
- DB schema KHÔNG thay đổi (zero-risk migration)
- Admin router (chưa migrate hoàn toàn) vẫn dùng models.py
- Khi Phase 5 hoàn tất, có thể move ORM models vào catalog/infrastructure/orm_models.py
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.domain.entities import (
    Category as DomainCategory,
    CrossSellItem as DomainCrossSell,
    Product as DomainProduct,
    ProductSize as DomainProductSize,
    ProductTopping as DomainProductTopping,
    TimeDeal as DomainTimeDeal,
    Topping as DomainTopping,
)
from app.catalog.domain.repository import (
    CategoryRepository, CrossSellRepository, ProductRepository,
    TimeDealRepository, ToppingRepository,
)
from app.catalog.domain.value_objects import LayoutType
# ORM models: import từ context sở hữu (không từ app.models)
from app.catalog.infrastructure.orm_models import (
    Category as OrmCategory,
    CrossSellItem as OrmCrossSell,
    Product as OrmProduct,
    ProductSize as OrmProductSize,
    ProductTopping as OrmProductTopping,
    TimeDeal as OrmTimeDeal,
    Topping as OrmTopping,
)

logger = logging.getLogger("ngonngon.catalog.infra")


# =============================================================================
# Mappers: ORM model ↔ Domain entity
# =============================================================================
def _orm_product_to_domain(orm: OrmProduct) -> DomainProduct:
    """Map SQLAlchemy Product → Domain Product."""
    sizes = []
    try:
        sizes = [
            DomainProductSize(label=s.label, price=s.price, id=s.id, product_id=s.product_id)
            for s in orm.sizes
        ]
    except Exception:
        pass  # Relationship not loaded

    product_toppings = []
    try:
        product_toppings = [
            DomainProductTopping(topping_id=pt.topping_id, id=pt.id, product_id=pt.product_id)
            for pt in orm.product_toppings
        ]
    except Exception:
        pass

    return DomainProduct(
        id=orm.id,
        legacy_id=orm.legacy_id,
        category_id=orm.category_id,
        name=orm.name,
        base_price=orm.base_price,
        description=orm.description,
        emoji=orm.emoji,
        image_path=orm.image_path,
        badge=orm.badge,
        bg_class=orm.bg_class,
        sold_count=orm.sold_count,
        is_drink=orm.is_drink,
        is_active=orm.is_active,
        sort_order=orm.sort_order,
        is_combo=orm.is_combo,
        combo_description=orm.combo_description,
        original_price=orm.original_price,
        save_amount=orm.save_amount,
        store_id=orm.store_id,
        sizes=sizes,
        product_toppings=product_toppings,
    )


def _orm_category_to_domain(orm: OrmCategory) -> DomainCategory:
    """Map SQLAlchemy Category → Domain Category."""
    products = []
    try:
        products = [_orm_product_to_domain(p) for p in orm.products]
    except Exception:
        pass

    return DomainCategory(
        id=orm.id,
        slug=orm.slug,
        name=orm.name,
        emoji=orm.emoji,
        layout=LayoutType(orm.layout.value if hasattr(orm.layout, "value") else orm.layout),
        sort_order=orm.sort_order,
        is_active=orm.is_active,
        store_id=orm.store_id,
        products=products,
    )


def _orm_topping_to_domain(orm: OrmTopping) -> DomainTopping:
    return DomainTopping(
        id=orm.id,
        legacy_id=orm.legacy_id,
        name=orm.name,
        emoji=orm.emoji,
        price=orm.price,
        is_active=orm.is_active,
        store_id=orm.store_id,
    )


def _orm_cross_sell_to_domain(orm: OrmCrossSell) -> DomainCrossSell:
    product = None
    try:
        if orm.product:
            product = _orm_product_to_domain(orm.product)
    except Exception:
        pass

    return DomainCrossSell(
        id=orm.id,
        product_id=orm.product_id,
        target=orm.target,
        sort_order=orm.sort_order,
        is_active=orm.is_active,
        store_id=orm.store_id,
        product=product,
    )


def _orm_time_deal_to_domain(orm: OrmTimeDeal) -> DomainTimeDeal:
    return DomainTimeDeal(
        id=orm.id,
        label=orm.label,
        title=orm.title,
        subtitle=orm.subtitle,
        start_hour=orm.start_hour,
        end_hour=orm.end_hour,
        discount_percent=orm.discount_percent,
        is_active=orm.is_active,
        store_id=orm.store_id,
    )


# =============================================================================
# SqlProductRepository
# =============================================================================
class SqlProductRepository(ProductRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_id(self, product_id: int) -> DomainProduct | None:
        stmt = (
            select(OrmProduct)
            .where(OrmProduct.id == product_id)
            .options(selectinload(OrmProduct.sizes))
            .options(selectinload(OrmProduct.product_toppings))
        )
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return _orm_product_to_domain(orm) if orm else None

    async def get_by_legacy_id(self, legacy_id: str) -> DomainProduct | None:
        stmt = (
            select(OrmProduct)
            .where(OrmProduct.legacy_id == legacy_id, OrmProduct.is_active == True)  # noqa: E712
            .options(selectinload(OrmProduct.sizes))
            .options(selectinload(OrmProduct.product_toppings))
        )
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return _orm_product_to_domain(orm) if orm else None

    async def save(self, product: DomainProduct) -> DomainProduct:
        if product.id:
            # Update existing
            orm = await self._db.get(OrmProduct, product.id)
            if not orm:
                raise ValueError(f"Product {product.id} not found for update")

            # Update scalar fields
            for field in [
                "legacy_id", "category_id", "name", "base_price", "description",
                "emoji", "image_path", "badge", "bg_class", "is_drink", "is_active",
                "sort_order", "is_combo", "combo_description", "original_price",
                "save_amount",
            ]:
                setattr(orm, field, getattr(product, field))

            # Add new sizes (old ones should be deleted via delete_sizes first)
            for s in product.sizes:
                if not s.id:  # New size
                    self._db.add(OrmProductSize(
                        product_id=product.id, label=s.label, price=s.price,
                    ))

            # Add new product_toppings (old ones deleted via delete_product_toppings)
            for pt in product.product_toppings:
                if not pt.id:  # New
                    self._db.add(OrmProductTopping(
                        product_id=product.id, topping_id=pt.topping_id,
                    ))

            await self._db.commit()

            # Re-fetch with relationships
            return await self.get_by_id(product.id)
        else:
            # Create new
            orm = OrmProduct(
                legacy_id=product.legacy_id,
                category_id=product.category_id,
                name=product.name,
                base_price=product.base_price,
                description=product.description,
                emoji=product.emoji,
                badge=product.badge,
                bg_class=product.bg_class,
                is_drink=product.is_drink,
                is_combo=product.is_combo,
                combo_description=product.combo_description,
                original_price=product.original_price,
                save_amount=product.save_amount,
            )
            # Add sizes
            for s in product.sizes:
                orm.sizes.append(OrmProductSize(label=s.label, price=s.price))
            # Add toppings
            for pt in product.product_toppings:
                orm.product_toppings.append(OrmProductTopping(topping_id=pt.topping_id))

            self._db.add(orm)
            await self._db.commit()

            # Re-fetch with relationships
            return await self.get_by_id(orm.id)

    async def delete_sizes(self, product_id: int) -> None:
        stmt = select(OrmProductSize).where(OrmProductSize.product_id == product_id)
        result = await self._db.execute(stmt)
        for orm_size in result.scalars().all():
            await self._db.delete(orm_size)
        await self._db.flush()

    async def delete_product_toppings(self, product_id: int) -> None:
        stmt = select(OrmProductTopping).where(OrmProductTopping.product_id == product_id)
        result = await self._db.execute(stmt)
        for orm_pt in result.scalars().all():
            await self._db.delete(orm_pt)
        await self._db.flush()


# =============================================================================
# SqlCategoryRepository
# =============================================================================
class SqlCategoryRepository(CategoryRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_id(self, category_id: int) -> DomainCategory | None:
        orm = await self._db.get(OrmCategory, category_id)
        return _orm_category_to_domain(orm) if orm else None

    async def get_by_slug(self, slug: str) -> DomainCategory | None:
        stmt = (
            select(OrmCategory)
            .where(OrmCategory.slug == slug, OrmCategory.is_active == True)  # noqa: E712
            .options(
                selectinload(OrmCategory.products).selectinload(OrmProduct.sizes)
            )
            .options(
                selectinload(OrmCategory.products).selectinload(OrmProduct.product_toppings)
            )
        )
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return _orm_category_to_domain(orm) if orm else None

    async def list_active_with_products(self) -> list[DomainCategory]:
        stmt = (
            select(OrmCategory)
            .where(OrmCategory.is_active == True)  # noqa: E712
            .options(
                selectinload(OrmCategory.products).selectinload(OrmProduct.sizes)
            )
            .options(
                selectinload(OrmCategory.products).selectinload(OrmProduct.product_toppings)
            )
            .order_by(OrmCategory.sort_order)
        )
        result = await self._db.execute(stmt)
        return [_orm_category_to_domain(orm) for orm in result.scalars().unique().all()]

    async def list_all(self) -> list[DomainCategory]:
        stmt = (
            select(OrmCategory)
            .options(
                selectinload(OrmCategory.products).selectinload(OrmProduct.sizes)
            )
            .options(
                selectinload(OrmCategory.products).selectinload(OrmProduct.product_toppings)
            )
            .order_by(OrmCategory.sort_order)
        )
        result = await self._db.execute(stmt)
        return [_orm_category_to_domain(orm) for orm in result.scalars().unique().all()]

    async def save(self, category: DomainCategory) -> DomainCategory:
        if category.id:
            orm = await self._db.get(OrmCategory, category.id)
            if not orm:
                raise ValueError(f"Category {category.id} not found")
            orm.name = category.name
            orm.emoji = category.emoji
            orm.sort_order = category.sort_order
            orm.is_active = category.is_active
            orm.layout = category.layout
            await self._db.commit()
            return _orm_category_to_domain(orm)
        else:
            orm = OrmCategory(
                slug=category.slug,
                name=category.name,
                emoji=category.emoji,
                layout=category.layout,
                sort_order=category.sort_order,
            )
            self._db.add(orm)
            await self._db.commit()
            await self._db.refresh(orm)
            return _orm_category_to_domain(orm)


# =============================================================================
# SqlToppingRepository
# =============================================================================
class SqlToppingRepository(ToppingRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_id(self, topping_id: int) -> DomainTopping | None:
        orm = await self._db.get(OrmTopping, topping_id)
        return _orm_topping_to_domain(orm) if orm else None

    async def list_active(self) -> list[DomainTopping]:
        stmt = (
            select(OrmTopping)
            .where(OrmTopping.is_active == True)  # noqa: E712
            .order_by(OrmTopping.id)
        )
        result = await self._db.execute(stmt)
        return [_orm_topping_to_domain(t) for t in result.scalars().all()]

    async def list_all(self) -> list[DomainTopping]:
        stmt = select(OrmTopping).order_by(OrmTopping.id)
        result = await self._db.execute(stmt)
        return [_orm_topping_to_domain(t) for t in result.scalars().all()]

    async def save(self, topping: DomainTopping) -> DomainTopping:
        if topping.id:
            orm = await self._db.get(OrmTopping, topping.id)
            if not orm:
                raise ValueError(f"Topping {topping.id} not found")
            orm.name = topping.name
            orm.emoji = topping.emoji
            orm.price = topping.price
            orm.is_active = topping.is_active
            await self._db.commit()
            return _orm_topping_to_domain(orm)
        else:
            orm = OrmTopping(
                legacy_id=topping.legacy_id,
                name=topping.name,
                emoji=topping.emoji,
                price=topping.price,
            )
            self._db.add(orm)
            await self._db.commit()
            await self._db.refresh(orm)
            return _orm_topping_to_domain(orm)


# =============================================================================
# SqlCrossSellRepository
# =============================================================================
class SqlCrossSellRepository(CrossSellRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_id(self, cs_id: int) -> DomainCrossSell | None:
        orm = await self._db.get(OrmCrossSell, cs_id)
        return _orm_cross_sell_to_domain(orm) if orm else None

    async def get_by_product_id(self, product_id: int) -> DomainCrossSell | None:
        stmt = select(OrmCrossSell).where(OrmCrossSell.product_id == product_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return _orm_cross_sell_to_domain(orm) if orm else None

    async def list_active(self) -> list[DomainCrossSell]:
        stmt = (
            select(OrmCrossSell)
            .where(OrmCrossSell.is_active == True)  # noqa: E712
            .options(selectinload(OrmCrossSell.product))
            .order_by(OrmCrossSell.sort_order)
        )
        result = await self._db.execute(stmt)
        return [_orm_cross_sell_to_domain(cs) for cs in result.scalars().all()]

    async def list_all(self) -> list[DomainCrossSell]:
        stmt = (
            select(OrmCrossSell)
            .options(selectinload(OrmCrossSell.product))
            .order_by(OrmCrossSell.sort_order)
        )
        result = await self._db.execute(stmt)
        return [_orm_cross_sell_to_domain(cs) for cs in result.scalars().all()]

    async def save(self, item: DomainCrossSell) -> DomainCrossSell:
        if item.id:
            orm = await self._db.get(OrmCrossSell, item.id)
            if not orm:
                raise ValueError(f"CrossSell {item.id} not found")
            orm.target = item.target
            orm.sort_order = item.sort_order
            orm.is_active = item.is_active
            await self._db.commit()
            return _orm_cross_sell_to_domain(orm)
        else:
            orm = OrmCrossSell(
                product_id=item.product_id,
                target=item.target,
                sort_order=item.sort_order,
            )
            self._db.add(orm)
            await self._db.commit()
            await self._db.refresh(orm)
            return _orm_cross_sell_to_domain(orm)

    async def delete(self, cs_id: int) -> None:
        orm = await self._db.get(OrmCrossSell, cs_id)
        if orm:
            await self._db.delete(orm)
            await self._db.commit()


# =============================================================================
# SqlTimeDealRepository
# =============================================================================
class SqlTimeDealRepository(TimeDealRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def list_active_at(self, hour: int) -> list[DomainTimeDeal]:
        stmt = (
            select(OrmTimeDeal)
            .where(
                OrmTimeDeal.is_active == True,  # noqa: E712
                OrmTimeDeal.start_hour <= hour,
                OrmTimeDeal.end_hour > hour,
            )
        )
        result = await self._db.execute(stmt)
        return [_orm_time_deal_to_domain(td) for td in result.scalars().all()]

    async def get_discount_at(self, hour: int) -> int:
        """Lấy % giảm giá tại giờ cụ thể (dùng bởi Ordering context)."""
        stmt = (
            select(OrmTimeDeal)
            .where(
                OrmTimeDeal.is_active == True,  # noqa: E712
                OrmTimeDeal.start_hour <= hour,
                OrmTimeDeal.end_hour > hour,
                OrmTimeDeal.discount_percent > 0,
            )
        )
        result = await self._db.execute(stmt)
        deal = result.scalar_one_or_none()
        return deal.discount_percent if deal else 0
