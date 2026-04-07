"""
Catalog Context — ORM Models
===============================
Tất cả bảng liên quan đến MENU nằm ở đây:
Category, Product, ProductSize, Topping, ProductTopping, CrossSellItem, TimeDeal.

TRƯỚC: Nằm chung trong app/models.py (468 dòng, 18 models lẫn lộn).
SAU:   Catalog sở hữu ORM models của mình. Context khác KHÔNG import từ đây
       trực tiếp — nếu cần đọc Product table (VD: Ordering tính giá),
       dùng cross-context read qua service hoặc import có ý thức.

NGUYÊN TẮC:
- Cùng Base (từ database.py) → SQLAlchemy metadata thấy tất cả
- ForeignKey dùng string ("categories.id") → không phụ thuộc Python class
- Schema DB giữ nguyên 100% → KHÔNG cần migration
"""

from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Enum, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.shared.orm_models import TenantMixin, TimestampMixin


# =============================================================================
# Enums
# =============================================================================

class LayoutType(str, PyEnum):
    """Cách hiển thị danh mục trên frontend."""
    GRID = "grid"
    LIST = "list"
    COMBO_SCROLL = "combo"


# =============================================================================
# Category — Danh mục menu (Trà Sữa, Cà Phê, Combo...)
# =============================================================================

class Category(TenantMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str] = mapped_column(String(10), default="📦")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    layout: Mapped[LayoutType] = mapped_column(
        Enum(LayoutType, values_callable=lambda x: [e.value for e in x]),
        default=LayoutType.LIST,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    products: Mapped[list["Product"]] = relationship(
        back_populates="category", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Category {self.slug}: {self.name}>"


# =============================================================================
# Product — Sản phẩm
# =============================================================================

class Product(TenantMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_category_active", "category_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legacy_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_price: Mapped[int] = mapped_column(Integer, nullable=False)

    emoji: Mapped[str] = mapped_column(String(10), default="🍽")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    badge: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bg_class: Mapped[str] = mapped_column(String(10), default="x")
    sold_count: Mapped[int] = mapped_column(Integer, default=0)
    is_drink: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    is_combo: Mapped[bool] = mapped_column(Boolean, default=False)
    combo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    save_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)

    category: Mapped["Category"] = relationship(back_populates="products")
    sizes: Mapped[list["ProductSize"]] = relationship(
        back_populates="product", lazy="selectin", cascade="all, delete-orphan",
    )
    product_toppings: Mapped[list["ProductTopping"]] = relationship(
        back_populates="product", lazy="selectin", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Product {self.legacy_id}: {self.name} ({self.base_price}k)>"


# =============================================================================
# ProductSize — Size variants (M/L/XL)
# =============================================================================

class ProductSize(Base):
    __tablename__ = "product_sizes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(10), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="sizes")


# =============================================================================
# Topping — Topping options (Trân Châu, Thạch Dừa...)
# =============================================================================

class Topping(TenantMixin, TimestampMixin, Base):
    __tablename__ = "toppings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legacy_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str] = mapped_column(String(10), default="🍡")
    price: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# =============================================================================
# ProductTopping — Junction table: Product ↔ Topping
# =============================================================================

class ProductTopping(Base):
    __tablename__ = "product_toppings"
    __table_args__ = (
        Index("ix_product_toppings_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    topping_id: Mapped[int] = mapped_column(ForeignKey("toppings.id", ondelete="CASCADE"), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="product_toppings")


# =============================================================================
# CrossSellItem — Gợi ý "Thêm cho đủ bữa?"
# =============================================================================

class CrossSellItem(TenantMixin, Base):
    __tablename__ = "cross_sell_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, unique=True)
    target: Mapped[str] = mapped_column(String(20), default="both")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped["Product"] = relationship()


# =============================================================================
# TimeDeal — Flash deals theo khung giờ
# =============================================================================

class TimeDeal(TenantMixin, TimestampMixin, Base):
    __tablename__ = "time_deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(200), default="")
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
