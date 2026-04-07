"""
Identity Context — ORM Models
================================
AdminUser: bảng quản trị viên (login, JWT auth).

TRƯỚC: Nằm chung trong app/models.py.
SAU:   Identity context sở hữu. Các context khác cần verify admin
       → gọi Identity service, KHÔNG truy cập bảng trực tiếp.

NOTE: Hiện tại Catalog admin_router và Ordering admin_router
      vẫn import AdminUser để check JWT. Đây là cross-context read
      chấp nhận được (read-only, cùng 1 field: username).
      Lý tưởng → tách thành shared middleware.
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.shared.orm_models import TenantMixin, TimestampMixin


# =============================================================================
# AdminUser — Quản trị viên
# =============================================================================

class AdminUser(TenantMixin, TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
