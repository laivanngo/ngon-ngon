"""
Catalog Context — Analytics Port (Outbound)
============================================
Interface cho phép các context khác query thông tin sản phẩm từ Catalog
mà không truy cập trực tiếp vào ORM hay schema DB của Catalog.

Consumers:
  Growth   → get_active_product() cho cross-sell
  Ordering → count_active_products() cho dashboard stats
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProductInfoData:
    """Thông tin sản phẩm đủ để hiển thị cross-sell card."""
    id: int
    legacy_id: str
    name: str
    base_price: int
    emoji: str
    is_active: bool


class CatalogAnalyticsPort(ABC):
    """
    Port cho phép các context khác query Product metadata từ Catalog.

    Adapter: catalog/infrastructure/analytics_adapter.SqlCatalogAnalyticsAdapter
    """

    @abstractmethod
    async def get_active_product(self, product_id: int) -> ProductInfoData | None:
        """
        Lấy thông tin sản phẩm nếu đang active.
        Return None nếu không tồn tại hoặc đã ngừng bán.
        """
        ...

    @abstractmethod
    async def count_active_products(self) -> int:
        """
        Đếm tổng số sản phẩm đang active (is_active=True).
        Dùng cho dashboard stats của Ordering context.
        """
        ...
