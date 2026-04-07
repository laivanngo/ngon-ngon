"""
Promotions Context — ORM Models
===================================
FeatureFlag — bật/tắt từng tính năng khuyến mãi.
FlashSale — chương trình giảm giá giới hạn thời gian + số lượng.

Tách từ growth/infrastructure/orm_models.py.
Bảng "feature_flags" giữ nguyên tên trong DB — không cần migration đổi tên.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.shared.orm_models import TenantMixin


class FeatureFlag(TenantMixin, Base):
    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(String(200), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


class FlashSale(TenantMixin, Base):
    """
    Flash Sale — giảm giá giới hạn thời gian + số lượng.

    status lifecycle: scheduled → active → ended / cancelled
    claimed_count: atomic increment bằng SQL UPDATE...WHERE < max_quantity
    products: many-to-many qua flash_sale_products junction table.
              Empty = toàn menu, có items = chỉ áp dụng cho sản phẩm cụ thể.
    """
    __tablename__ = "flash_sales"
    __table_args__ = (
        Index("ix_flash_sales_status_time", "status", "starts_at", "ends_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(300), nullable=True)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    max_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="scheduled", server_default="scheduled",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # Many-to-many: sản phẩm áp dụng (empty = toàn menu)
    products: Mapped[list["FlashSaleProduct"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan",
    )


class FlashSaleProduct(Base):
    """
    Junction table: flash_sale ↔ product (many-to-many).
    Empty = áp dụng toàn menu. Có rows = chỉ áp dụng cho sản phẩm cụ thể.
    """
    __tablename__ = "flash_sale_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flash_sale_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("flash_sales.id", ondelete="CASCADE"), nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False,
    )
