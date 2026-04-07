"""
Catalog Domain — Entities (Rich Models)
=========================================
Product, Category, Topping, CrossSellItem, TimeDeal — không còn là data containers.
Mỗi entity tự bảo vệ invariants, có behavior rõ ràng.

WHY dataclass thay vì SQLAlchemy model trực tiếp:
- Domain layer KHÔNG phụ thuộc vào ORM
- Unit test được mà không cần DB
- Infrastructure layer map entity ↔ ORM model
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.catalog.domain.value_objects import LayoutType, Money


# =============================================================================
# Category — Danh mục menu
# =============================================================================
@dataclass
class Category:
    id: int | None
    slug: str
    name: str
    emoji: str = "📦"
    layout: LayoutType = LayoutType.LIST
    sort_order: int = 0
    is_active: bool = True
    store_id: int = 1

    # Relationships (populated by repository)
    products: list[Product] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        slug: str,
        name: str,
        emoji: str = "📦",
        layout: str = "list",
        sort_order: int = 0,
        store_id: int = 1,
    ) -> Category:
        """Factory method — validate rồi mới tạo."""
        slug = slug.strip()
        name = name.strip()
        if not slug:
            raise ValueError("Slug danh mục không được để trống")
        if not name:
            raise ValueError("Tên danh mục không được để trống")
        return cls(
            id=None,
            slug=slug,
            name=name,
            emoji=emoji,
            layout=LayoutType(layout),
            sort_order=sort_order,
            store_id=store_id,
        )

    def update(self, **kwargs) -> None:
        """Partial update — chỉ set field được truyền vào."""
        if "name" in kwargs:
            name = str(kwargs["name"]).strip()
            if name:
                self.name = name
        if "emoji" in kwargs:
            self.emoji = str(kwargs["emoji"]).strip()
        if "sort_order" in kwargs:
            self.sort_order = int(kwargs["sort_order"])
        if "is_active" in kwargs:
            self.is_active = bool(kwargs["is_active"])
        if "layout" in kwargs:
            self.layout = LayoutType(kwargs["layout"])

    def deactivate(self) -> None:
        """Soft delete."""
        self.is_active = False

    @property
    def active_products(self) -> list[Product]:
        """Sản phẩm active, đã sort."""
        return sorted(
            [p for p in self.products if p.is_active],
            key=lambda p: p.sort_order,
        )


# =============================================================================
# ProductSize — Value-like nhưng có identity (id) cho ORM mapping
# =============================================================================
@dataclass
class ProductSize:
    label: str      # M, L, XL
    price: int      # Giá cho size này
    id: int | None = None
    product_id: int | None = None


# =============================================================================
# ProductTopping — Junction record
# =============================================================================
@dataclass
class ProductTopping:
    topping_id: int
    id: int | None = None
    product_id: int | None = None


# =============================================================================
# Product — Sản phẩm (Aggregate Root trong Catalog context)
# =============================================================================
@dataclass
class Product:
    id: int | None
    legacy_id: str
    category_id: int
    name: str
    base_price: int
    description: str | None = None
    emoji: str = "🍽"
    image_path: str | None = None
    badge: str | None = None
    bg_class: str = "x"
    sold_count: int = 0
    is_drink: bool = True
    is_active: bool = True
    sort_order: int = 0
    is_combo: bool = False
    combo_description: str | None = None
    original_price: int | None = None
    save_amount: int | None = None
    store_id: int = 1

    # Relationships
    sizes: list[ProductSize] = field(default_factory=list)
    product_toppings: list[ProductTopping] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        legacy_id: str,
        category_id: int,
        name: str,
        base_price: int,
        sizes: list[dict] | None = None,
        topping_ids: list[int] | None = None,
        store_id: int = 1,
        **kwargs,
    ) -> Product:
        """Factory method — validate + tạo product với sizes và toppings."""
        if not name or not name.strip():
            raise ValueError("Tên sản phẩm không được để trống")
        if base_price < 1:
            raise ValueError("Giá sản phẩm phải > 0")
        if not legacy_id or not legacy_id.strip():
            raise ValueError("Legacy ID không được để trống")

        product = cls(
            id=None,
            legacy_id=legacy_id.strip(),
            category_id=category_id,
            name=name.strip(),
            base_price=base_price,
            store_id=store_id,
            description=kwargs.get("description"),
            emoji=kwargs.get("emoji", "🍽"),
            badge=kwargs.get("badge"),
            bg_class=kwargs.get("bg_class", "x"),
            is_drink=kwargs.get("is_drink", True),
            is_combo=kwargs.get("is_combo", False),
            combo_description=kwargs.get("combo_description"),
            original_price=kwargs.get("original_price"),
            save_amount=kwargs.get("save_amount"),
        )

        # Add sizes
        if sizes:
            for s in sizes:
                product.sizes.append(ProductSize(label=s["label"], price=s["price"]))

        # Add toppings
        if topping_ids:
            for tid in topping_ids:
                product.product_toppings.append(ProductTopping(topping_id=tid))

        return product

    def update(self, **kwargs) -> None:
        """Partial update scalar fields."""
        scalar_fields = {
            "name", "description", "base_price", "emoji", "image_path",
            "badge", "bg_class", "is_active", "is_drink", "is_combo",
            "combo_description", "original_price", "save_amount",
            "sort_order", "category_id",
        }
        for key, value in kwargs.items():
            if key in scalar_fields:
                setattr(self, key, value)

    def replace_sizes(self, sizes: list[dict]) -> None:
        """Replace toàn bộ sizes."""
        self.sizes = [ProductSize(label=s["label"], price=s["price"]) for s in sizes]

    def replace_toppings(self, topping_ids: list[int]) -> None:
        """Replace toàn bộ product_toppings."""
        self.product_toppings = [ProductTopping(topping_id=tid) for tid in topping_ids]

    def deactivate(self) -> None:
        """Soft delete."""
        self.is_active = False

    @property
    def topping_ids(self) -> list[int]:
        return [pt.topping_id for pt in self.product_toppings]


# =============================================================================
# Topping — Topping option
# =============================================================================
@dataclass
class Topping:
    id: int | None
    legacy_id: str
    name: str
    emoji: str = "🍡"
    price: int = 5
    is_active: bool = True
    store_id: int = 1

    @classmethod
    def create(
        cls,
        name: str,
        legacy_id: str | None = None,
        emoji: str = "🍡",
        price: int = 5,
        store_id: int = 1,
    ) -> Topping:
        name = name.strip()
        if not name:
            raise ValueError("Tên topping không được để trống")
        if not legacy_id:
            import time
            legacy_id = f"tp{int(time.time()) % 10000}"
        return cls(
            id=None,
            legacy_id=legacy_id,
            name=name,
            emoji=emoji,
            price=price,
            store_id=store_id,
        )

    def update(self, **kwargs) -> None:
        if "name" in kwargs:
            self.name = str(kwargs["name"]).strip()
        if "emoji" in kwargs:
            self.emoji = str(kwargs["emoji"]).strip()
        if "price" in kwargs:
            self.price = int(kwargs["price"])
        if "is_active" in kwargs:
            self.is_active = bool(kwargs["is_active"])

    def deactivate(self) -> None:
        self.is_active = False


# =============================================================================
# CrossSellItem — Gợi ý "Thêm cho đủ bữa?"
# =============================================================================
@dataclass
class CrossSellItem:
    id: int | None
    product_id: int
    target: str = "both"        # "drink" | "snack" | "both"
    sort_order: int = 0
    is_active: bool = True
    store_id: int = 1

    # Populated by repository
    product: Product | None = None

    @classmethod
    def create(
        cls,
        product_id: int,
        target: str = "both",
        sort_order: int = 0,
        store_id: int = 1,
    ) -> CrossSellItem:
        if target not in ("drink", "snack", "both"):
            raise ValueError("Target phải là 'drink', 'snack', hoặc 'both'")
        return cls(
            id=None,
            product_id=product_id,
            target=target,
            sort_order=sort_order,
            store_id=store_id,
        )

    def update(self, **kwargs) -> None:
        if "target" in kwargs:
            self.target = str(kwargs["target"])
        if "sort_order" in kwargs:
            self.sort_order = int(kwargs["sort_order"])
        if "is_active" in kwargs:
            self.is_active = bool(kwargs["is_active"])


# =============================================================================
# TimeDeal — Flash deal theo khung giờ
# =============================================================================
@dataclass
class TimeDeal:
    id: int | None
    label: str
    title: str
    subtitle: str = ""
    start_hour: int = 0
    end_hour: int = 24
    discount_percent: int = 0
    is_active: bool = True
    store_id: int = 1

    def is_active_at(self, hour: int) -> bool:
        """Check xem deal có đang chạy ở giờ này không."""
        return self.is_active and self.start_hour <= hour < self.end_hour
