"""
Shared ORM Foundations — Base, Mixins, Store
==============================================
Các "viên gạch nền" mà tất cả bounded contexts đều dùng.

NẰM Ở ĐÂY (shared) vì:
- TimestampMixin, TenantMixin: mọi table đều cần created_at, store_id
- Store: platform-level entity, không thuộc context nào cụ thể
- Base: SQLAlchemy declarative base, import từ database.py

MỌI CONTEXT import mixins TỪ ĐÂY, không từ models.py nữa.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# =============================================================================
# Mixins — Dùng chung cho tất cả models
# =============================================================================

class TimestampMixin:
    """Tự động ghi created_at + updated_at cho mọi bảng."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class TenantMixin:
    """
    Multi-tenant foundation: mỗi row thuộc 1 quán (store_id).
    Giai đoạn 1: default=1 (1 quán). Giai đoạn 2: bật RLS.
    """
    store_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stores.id"), nullable=False, default=1, index=True,
    )


# =============================================================================
# Store — Platform-level, không thuộc bounded context nào
# =============================================================================

class Store(TimestampMixin, Base):
    """Mỗi quán = 1 row. Nền móng multi-tenant."""
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict | None] = mapped_column(JSON, default=dict)

    def __repr__(self) -> str:
        return f"<Store {self.slug}: {self.name}>"
