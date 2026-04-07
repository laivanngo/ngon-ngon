"""
Catalog Domain — Value Objects
================================
Value Objects = immutable, so sánh bằng giá trị (không phải identity).
Dùng cho các khái niệm nhỏ có validation riêng.
"""

from __future__ import annotations

from enum import Enum as PyEnum


class LayoutType(str, PyEnum):
    """Cách hiển thị danh mục trên frontend."""
    GRID = "grid"
    LIST = "list"
    COMBO_SCROLL = "combo"


# Money: import từ Shared Kernel (single source of truth)
from app.shared.value_objects import Money  # noqa: E402
