"""
Catalog Domain — Repository Interfaces (ABCs)
================================================
WHY ABC thay vì concrete class:
- Domain layer KHÔNG biết về SQLAlchemy, PostgreSQL, hay bất kỳ DB nào
- Infrastructure layer implement ABC → dependency inversion
- Test: inject InMemoryProductRepo thay vì real DB

Mỗi aggregate root có 1 repository riêng.
"""

from abc import ABC, abstractmethod

from app.catalog.domain.entities import (
    Category, CrossSellItem, Product, TimeDeal, Topping,
)


class ProductRepository(ABC):
    """Repository cho Product aggregate."""

    @abstractmethod
    async def get_by_id(self, product_id: int) -> Product | None:
        ...

    @abstractmethod
    async def get_by_legacy_id(self, legacy_id: str) -> Product | None:
        ...

    @abstractmethod
    async def save(self, product: Product) -> Product:
        """Create hoặc update (upsert based on id)."""
        ...

    @abstractmethod
    async def delete_sizes(self, product_id: int) -> None:
        ...

    @abstractmethod
    async def delete_product_toppings(self, product_id: int) -> None:
        ...


class CategoryRepository(ABC):
    """Repository cho Category."""

    @abstractmethod
    async def get_by_id(self, category_id: int) -> Category | None:
        ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Category | None:
        ...

    @abstractmethod
    async def list_active_with_products(self) -> list[Category]:
        """Lấy tất cả category active + products active (eager load sizes, toppings)."""
        ...

    @abstractmethod
    async def list_all(self) -> list[Category]:
        """Lấy tất cả categories (admin view, kể cả inactive)."""
        ...

    @abstractmethod
    async def save(self, category: Category) -> Category:
        ...


class ToppingRepository(ABC):

    @abstractmethod
    async def get_by_id(self, topping_id: int) -> Topping | None:
        ...

    @abstractmethod
    async def list_active(self) -> list[Topping]:
        ...

    @abstractmethod
    async def list_all(self) -> list[Topping]:
        ...

    @abstractmethod
    async def save(self, topping: Topping) -> Topping:
        ...


class CrossSellRepository(ABC):

    @abstractmethod
    async def get_by_id(self, cs_id: int) -> CrossSellItem | None:
        ...

    @abstractmethod
    async def get_by_product_id(self, product_id: int) -> CrossSellItem | None:
        ...

    @abstractmethod
    async def list_active(self) -> list[CrossSellItem]:
        ...

    @abstractmethod
    async def list_all(self) -> list[CrossSellItem]:
        ...

    @abstractmethod
    async def save(self, item: CrossSellItem) -> CrossSellItem:
        ...

    @abstractmethod
    async def delete(self, cs_id: int) -> None:
        """Hard delete — cross-sell không cần soft delete."""
        ...


class TimeDealRepository(ABC):

    @abstractmethod
    async def list_active_at(self, hour: int) -> list[TimeDeal]:
        """Lấy deals đang active tại giờ cụ thể."""
        ...

    @abstractmethod
    async def get_discount_at(self, hour: int) -> int:
        """Lấy % giảm giá tại giờ cụ thể (0 nếu không có deal)."""
        ...
