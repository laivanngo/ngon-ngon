"""
Catalog Application — Commands (Write Operations)
====================================================
Commands = operations that change state.
Mỗi command: validate → execute → invalidate cache → publish events.

WHY tách commands khỏi queries:
- Write path cần transaction, cache invalidation, event publishing
- Read path chỉ cần query + optional cache
- CQS: Command-Query Separation (nhẹ, không phải full CQRS)
"""

import logging

from app.catalog.application.queries import invalidate_menu_cache
from app.catalog.domain.entities import (
    Category, CrossSellItem, Product, Topping,
)
from app.catalog.domain.events import MenuChanged
from app.catalog.domain.repository import (
    CategoryRepository, CrossSellRepository, ProductRepository,
    ToppingRepository,
)
from app.shared.events import event_bus
from app.shared.exceptions import DuplicateError, NotFoundError

logger = logging.getLogger("ngonngon.catalog.commands")


# =============================================================================
# Helper: invalidate + broadcast menu change
# =============================================================================
async def _notify_menu_changed(change_type: str, changed_by: str = "admin"):
    """Invalidate cache + publish MenuChanged event."""
    invalidate_menu_cache()
    await event_bus.publish(MenuChanged(changed_by=changed_by, change_type=change_type))


# =============================================================================
# Product Commands
# =============================================================================
class CreateProduct:
    def __init__(self, product_repo: ProductRepository):
        self._product_repo = product_repo

    async def execute(
        self,
        legacy_id: str,
        category_id: int,
        name: str,
        base_price: int,
        sizes: list[dict] | None = None,
        topping_ids: list[int] | None = None,
        changed_by: str = "admin",
        **kwargs,
    ) -> Product:
        product = Product.create(
            legacy_id=legacy_id,
            category_id=category_id,
            name=name,
            base_price=base_price,
            sizes=sizes,
            topping_ids=topping_ids,
            **kwargs,
        )
        product = await self._product_repo.save(product)

        await _notify_menu_changed("product_created", changed_by)
        logger.info(f"➕ Product created: {product.name} (by {changed_by})")

        return product


class UpdateProduct:
    def __init__(self, product_repo: ProductRepository):
        self._product_repo = product_repo

    async def execute(
        self,
        product_id: int,
        changed_by: str = "admin",
        sizes: list[dict] | None = None,
        topping_ids: list[int] | None = None,
        **kwargs,
    ) -> Product:
        product = await self._product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundError("Sản phẩm", str(product_id))

        # Handle sizes replacement
        if sizes is not None:
            await self._product_repo.delete_sizes(product.id)
            product.replace_sizes(sizes)

        # Handle toppings replacement
        if topping_ids is not None:
            await self._product_repo.delete_product_toppings(product.id)
            product.replace_toppings(topping_ids)

        # Update scalar fields
        product.update(**kwargs)

        product = await self._product_repo.save(product)

        await _notify_menu_changed("product_updated", changed_by)
        logger.info(f"✏️ Product updated: {product.name} (by {changed_by})")

        return product


class DeleteProduct:
    """Soft delete product."""

    def __init__(self, product_repo: ProductRepository):
        self._product_repo = product_repo

    async def execute(self, product_id: int, changed_by: str = "admin") -> Product:
        product = await self._product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundError("Sản phẩm", str(product_id))

        product.deactivate()
        product = await self._product_repo.save(product)

        await _notify_menu_changed("product_deleted", changed_by)
        logger.info(f"🗑️ Product soft-deleted: {product.name} (by {changed_by})")

        return product


# =============================================================================
# Category Commands
# =============================================================================
class CreateCategory:
    def __init__(self, category_repo: CategoryRepository):
        self._category_repo = category_repo

    async def execute(
        self,
        slug: str,
        name: str,
        emoji: str = "📦",
        layout: str = "list",
        sort_order: int = 0,
        changed_by: str = "admin",
    ) -> Category:
        # Check duplicate slug
        existing = await self._category_repo.get_by_slug(slug)
        if existing:
            raise DuplicateError("Slug", slug)

        category = Category.create(
            slug=slug, name=name, emoji=emoji,
            layout=layout, sort_order=sort_order,
        )
        category = await self._category_repo.save(category)

        await _notify_menu_changed("category_created", changed_by)
        logger.info(f"📁 Category created: {category.name} (by {changed_by})")

        return category


class UpdateCategory:
    def __init__(self, category_repo: CategoryRepository):
        self._category_repo = category_repo

    async def execute(
        self, category_id: int, changed_by: str = "admin", **kwargs,
    ) -> Category:
        category = await self._category_repo.get_by_id(category_id)
        if not category:
            raise NotFoundError("Danh mục", str(category_id))

        category.update(**kwargs)
        category = await self._category_repo.save(category)

        await _notify_menu_changed("category_updated", changed_by)
        logger.info(f"📁 Category updated: {category.name} (by {changed_by})")

        return category


class DeleteCategory:
    def __init__(self, category_repo: CategoryRepository):
        self._category_repo = category_repo

    async def execute(self, category_id: int, changed_by: str = "admin") -> Category:
        category = await self._category_repo.get_by_id(category_id)
        if not category:
            raise NotFoundError("Danh mục", str(category_id))

        category.deactivate()
        category = await self._category_repo.save(category)

        await _notify_menu_changed("category_deleted", changed_by)
        logger.info(f"📁 Category hidden: {category.name} (by {changed_by})")

        return category


# =============================================================================
# Topping Commands
# =============================================================================
class CreateTopping:
    def __init__(self, topping_repo: ToppingRepository):
        self._topping_repo = topping_repo

    async def execute(
        self,
        name: str,
        legacy_id: str | None = None,
        emoji: str = "🍡",
        price: int = 5,
        changed_by: str = "admin",
    ) -> Topping:
        topping = Topping.create(
            name=name, legacy_id=legacy_id, emoji=emoji, price=price,
        )
        topping = await self._topping_repo.save(topping)

        await _notify_menu_changed("topping_created", changed_by)
        logger.info(f"🧁 Topping created: {topping.name} (by {changed_by})")

        return topping


class UpdateTopping:
    def __init__(self, topping_repo: ToppingRepository):
        self._topping_repo = topping_repo

    async def execute(
        self, topping_id: int, changed_by: str = "admin", **kwargs,
    ) -> Topping:
        topping = await self._topping_repo.get_by_id(topping_id)
        if not topping:
            raise NotFoundError("Topping", str(topping_id))

        topping.update(**kwargs)
        topping = await self._topping_repo.save(topping)

        await _notify_menu_changed("topping_updated", changed_by)
        logger.info(f"🧁 Topping updated: {topping.name} (by {changed_by})")

        return topping


class DeleteTopping:
    def __init__(self, topping_repo: ToppingRepository):
        self._topping_repo = topping_repo

    async def execute(self, topping_id: int, changed_by: str = "admin") -> Topping:
        topping = await self._topping_repo.get_by_id(topping_id)
        if not topping:
            raise NotFoundError("Topping", str(topping_id))

        topping.deactivate()
        topping = await self._topping_repo.save(topping)

        await _notify_menu_changed("topping_deleted", changed_by)
        logger.info(f"🧁 Topping hidden: {topping.name} (by {changed_by})")

        return topping


# =============================================================================
# Cross-Sell Commands
# =============================================================================
class CreateCrossSell:
    def __init__(
        self,
        cross_sell_repo: CrossSellRepository,
        product_repo: ProductRepository,
    ):
        self._cross_sell_repo = cross_sell_repo
        self._product_repo = product_repo

    async def execute(
        self,
        product_id: int,
        target: str = "both",
        sort_order: int = 0,
        changed_by: str = "admin",
    ) -> CrossSellItem:
        # Check product exists
        product = await self._product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundError("Sản phẩm", str(product_id))

        # Check duplicate
        existing = await self._cross_sell_repo.get_by_product_id(product_id)
        if existing:
            raise DuplicateError("Cross-sell", product.name)

        item = CrossSellItem.create(
            product_id=product_id, target=target, sort_order=sort_order,
        )
        item = await self._cross_sell_repo.save(item)
        item.product = product  # For response

        await _notify_menu_changed("cross_sell_created", changed_by)
        logger.info(f"🛒 Cross-sell added: {product.name} (by {changed_by})")

        return item


class UpdateCrossSell:
    def __init__(self, cross_sell_repo: CrossSellRepository):
        self._cross_sell_repo = cross_sell_repo

    async def execute(
        self, cs_id: int, changed_by: str = "admin", **kwargs,
    ) -> CrossSellItem:
        item = await self._cross_sell_repo.get_by_id(cs_id)
        if not item:
            raise NotFoundError("Cross-sell item", str(cs_id))

        item.update(**kwargs)
        item = await self._cross_sell_repo.save(item)

        await _notify_menu_changed("cross_sell_updated", changed_by)
        logger.info(f"🛒 Cross-sell updated: id={cs_id} (by {changed_by})")

        return item


class DeleteCrossSell:
    def __init__(self, cross_sell_repo: CrossSellRepository):
        self._cross_sell_repo = cross_sell_repo

    async def execute(self, cs_id: int, changed_by: str = "admin") -> None:
        item = await self._cross_sell_repo.get_by_id(cs_id)
        if not item:
            raise NotFoundError("Cross-sell item", str(cs_id))

        await self._cross_sell_repo.delete(cs_id)

        await _notify_menu_changed("cross_sell_deleted", changed_by)
        logger.info(f"🛒 Cross-sell removed: id={cs_id} (by {changed_by})")
