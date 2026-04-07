"""
Ordering Context — Analytics Port (Outbound)
=============================================
Interface cho phép Growth context query dữ liệu phân tích từ Ordering,
mà không cần truy cập trực tiếp vào ORM hay schema DB của Ordering.

DEPENDENCY RULE:
    Growth defines what it needs.
    Ordering provides the data (via adapter).
    Growth không import bất kỳ thứ gì từ ordering.*

DTOs: plain dataclasses — không có ORM, không có SQLAlchemy dependency.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime


# =============================================================================
# DTOs
# =============================================================================

@dataclass
class OrderSummaryData:
    """Tóm tắt 1 đơn hàng — đủ để Growth context cập nhật customer record."""
    id: int
    public_id: str
    phone: str
    customer_name: str
    total: int
    status: str
    created_at: datetime


@dataclass
class OrderItemData:
    """1 dòng trong đơn hàng."""
    product_id: int
    product_name: str
    size: str | None
    sweetness: str | None
    ice_level: str | None
    quantity: int
    unit_price: int
    toppings_text: str | None


@dataclass
class OrderWithItemsData:
    """Đơn hàng đầy đủ kèm các món — dùng cho reorder feature."""
    public_id: str
    total: int
    status: str
    created_at: str   # ISO string
    items: list[OrderItemData] = field(default_factory=list)


@dataclass
class DailyRevenueData:
    """Doanh thu theo ngày — dùng cho analytics report."""
    day: str           # "2024-01-15"
    order_count: int
    revenue: int


@dataclass
class TopProductData:
    """Sản phẩm bán chạy — dùng cho analytics report."""
    product_name: str
    quantity: int
    revenue: int


@dataclass
class PeakHourData:
    """Giờ cao điểm — dùng cho analytics report."""
    hour: int          # 0-23
    order_count: int


@dataclass
class OrderStatsData:
    """Thống kê tổng hợp — dùng cho analytics report."""
    total_in_period: int
    cancelled_in_period: int


@dataclass
class UpsellRawData:
    """Dữ liệu thô cho upsell stats."""
    total_orders_not_cancelled: int
    orders_with_toppings: int
    size_counts: dict[str, int]   # {"M": 120, "L": 80}


@dataclass
class CrossSellOrderItemData:
    """Item data cho cross-sell algorithm."""
    order_id: int
    product_id: int
    product_name: str


# =============================================================================
# OrderAnalyticsPort
# =============================================================================

class OrderAnalyticsPort(ABC):
    """
    Port cho phép Growth context query Ordering data.

    Adapter:  ordering/infrastructure/analytics_adapter.SqlOrderAnalyticsAdapter
    """

    @abstractmethod
    async def get_last_completed_order_by_phone(
        self, phone: str
    ) -> OrderWithItemsData | None:
        """Lấy đơn hoàn thành gần nhất của khách — dùng cho reorder."""
        ...

    @abstractmethod
    async def get_revenue_by_day(
        self, since: datetime
    ) -> list[DailyRevenueData]:
        """Doanh thu theo ngày trong khoảng thời gian — dùng cho analytics."""
        ...

    @abstractmethod
    async def get_top_products(
        self, since: datetime, limit: int = 10
    ) -> list[TopProductData]:
        """Sản phẩm bán chạy nhất — dùng cho analytics."""
        ...

    @abstractmethod
    async def get_peak_hours(self, since: datetime) -> list[PeakHourData]:
        """Phân bố đơn hàng theo giờ trong ngày — dùng cho analytics."""
        ...

    @abstractmethod
    async def get_order_stats(self, since: datetime) -> OrderStatsData:
        """Thống kê tổng số đơn và số đơn hủy — dùng cho analytics."""
        ...

    @abstractmethod
    async def get_upsell_raw_data(self) -> UpsellRawData:
        """Dữ liệu thô cho upsell statistics (topping rate, size distribution)."""
        ...

    @abstractmethod
    async def get_cross_sell_items(
        self, product_ids: list[int]
    ) -> list[CrossSellOrderItemData]:
        """
        Lấy tất cả order items từ các đơn có chứa ít nhất 1 product trong product_ids.
        Dùng để tính cross-sell suggestions.
        """
        ...

    @abstractmethod
    async def get_order_id_by_public_id(self, public_id: str) -> int | None:
        """Resolve public_id (UUID string) → internal integer id."""
        ...


# =============================================================================
# OrderCustomerLinkPort — Growth cần ghi customer_id vào Order
# =============================================================================

class OrderCustomerLinkPort(ABC):
    """
    Port cho phép Growth context ghi customer_id vào Order sau khi tạo customer.

    Đây là write-back cross-context duy nhất từ Growth → Ordering.
    Sử dụng port để tránh Growth import Order ORM trực tiếp.
    """

    @abstractmethod
    async def link_customer_to_order(
        self, order_id: int, customer_id: int
    ) -> None:
        """Gán customer_id cho đơn hàng có id=order_id."""
        ...


# =============================================================================
# KitchenQueuePort — Kitchen cần đọc queue đơn hàng
# =============================================================================

@dataclass
class KitchenOrderData:
    """Projection của Order dành riêng cho Kitchen Display System."""
    public_id: str
    status: str
    customer_name: str
    phone: str
    address: str
    note: str | None
    delivery_type: str
    scheduled_time: str | None
    total: int
    created_at: datetime
    items: list["KitchenOrderItemData"] = field(default_factory=list)


@dataclass
class KitchenOrderItemData:
    """Một dòng món trong đơn bếp cần làm."""
    product_name: str
    quantity: int
    unit_price: int
    size: str | None
    sweetness: str | None
    ice_level: str | None
    toppings_text: str | None
    note: str | None


class KitchenQueuePort(ABC):
    """
    Port cho Kitchen context đọc danh sách đơn hàng cần xử lý.

    Thay thế việc Kitchen import trực tiếp Order ORM từ Ordering.
    Adapter: ordering/infrastructure/kitchen_queue_adapter.SqlKitchenQueueAdapter
    """

    @abstractmethod
    async def get_active_queue(self, cutoff_minutes: int = 10) -> list[KitchenOrderData]:
        """
        Trả danh sách đơn KDS cần hiển thị:
        - Active: pending, confirmed, preparing, delivering
        - Terminal gần đây: done/cancelled trong cutoff_minutes phút qua
        """
        ...
