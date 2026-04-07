"""
Ordering Context — Application Use Cases
==========================================
Use cases = orchestration logic. Mỗi use case:
1. Nhận command/query
2. Gọi domain services / repository
3. Phát domain events
4. Return result

WHY use cases tách khỏi domain:
- Domain entities chứa BUSINESS RULES (Order.change_status)
- Use cases chứa APPLICATION FLOW (load → validate → persist → publish)
- Domain không biết repository, event bus, WS
- Use case biết tất cả, nhưng chỉ orchestrate, không chứa business logic

WHY use cases tách khỏi router:
- TRƯỚC: router = 150 dòng (tính giá + persist + customer tracking + WS broadcast)
- SAU: router = 15 dòng (parse HTTP → gọi use case → return response)
- Use case có thể gọi từ CLI, test, cron job — không phụ thuộc HTTP
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ordering.domain.entities import Order, OrderItem
from app.ordering.domain.events import OrderPlaced
from app.ordering.domain.services import CartItem, OrderRepository, PricingService
from app.ordering.domain.value_objects import OrderStatus
from app.shared.events import EventBus
from app.shared.exceptions import NotFoundError

logger = logging.getLogger("ngonngon.ordering")


# =============================================================================
# PlaceOrder — Tạo đơn hàng mới
# =============================================================================
@dataclass
class PlaceOrderCommand:
    """Input cho PlaceOrderUseCase — data từ HTTP request."""

    customer_name: str
    phone: str
    address: str
    note: str | None
    delivery_type: str
    scheduled_time: str | None
    items: list[CartItem]


class PlaceOrderUseCase:
    """
    Orchestrate flow tạo đơn hàng:
    1. Tính giá (PricingService)
    2. Tạo Order aggregate (domain validation)
    3. Estimate thời gian giao
    4. Persist (OrderRepository)
    5. Publish events (EventBus → customer tracking, WS broadcast)

    TRƯỚC: Tất cả nằm trong 1 endpoint 260 dòng (routers/orders.py).
    SAU: Mỗi bước là 1 abstraction rõ ràng.
    """

    def __init__(
        self,
        pricing_service: PricingService,
        order_repo: OrderRepository,
        event_bus: EventBus,
    ) -> None:
        self._pricing = pricing_service
        self._repo = order_repo
        self._bus = event_bus

    async def execute(self, command: PlaceOrderCommand) -> Order:
        # --- 1. Tính giá ---
        # PricingService lookup product, sizes, toppings, TimeDeal từ DB
        priced_cart = await self._pricing.price_cart(command.items)

        # --- 2. Tạo domain OrderItems từ priced data ---
        order_items = [
            OrderItem(
                product_id=item.product_id,
                product_name=item.product_name,
                size=item.size,
                sweetness=item.sweetness,
                ice_level=item.ice_level,
                quantity=item.quantity,
                unit_price=item.unit_price,
                toppings_text=item.toppings_text,
                note=item.note,
            )
            for item in priced_cart.items
        ]

        # --- 3. Tạo Order aggregate (validates invariants + phát event) ---
        order = Order.place(
            customer_name=command.customer_name,
            phone=command.phone,
            address=command.address,
            note=command.note,
            delivery_type=command.delivery_type,
            scheduled_time=command.scheduled_time,
            items=order_items,
            subtotal=priced_cart.subtotal,
            discount=priced_cart.discount,
        )

        # --- 4. Estimate thời gian giao ---
        # 3 phút/đơn đang chờ, tối thiểu 10, tối đa 45
        active_count = await self._repo.count_active()
        order.estimated_minutes = min(max(10, active_count * 3 + 8), 45)

        # --- 5. Persist ---
        order = await self._repo.save(order)

        # --- 6. Publish events ---
        # Cập nhật order_id vào event (giờ đã có DB id)
        events = order.collect_events()
        for event in events:
            if isinstance(event, OrderPlaced):
                # OrderPlaced frozen → tạo mới với order_id
                events[events.index(event)] = OrderPlaced(
                    public_id=event.public_id,
                    phone=event.phone,
                    customer_name=event.customer_name,
                    address=event.address,
                    total=event.total,
                    item_count=event.item_count,
                    delivery_type=event.delivery_type,
                    scheduled_time=event.scheduled_time,
                    estimated_minutes=order.estimated_minutes,
                    order_id=order.id,
                )

        await self._bus.publish_all(events)

        logger.info(
            f"📦 New order {order.public_id[:8]}... | "
            f"{len(order.items)} items | {order.total}k | "
            f"📞 {order.phone} | 📍 {order.address}"
        )

        return order


# =============================================================================
# UpdateStatus — Chuyển trạng thái đơn hàng
# =============================================================================
@dataclass
class UpdateStatusCommand:
    """Input cho UpdateStatusUseCase."""

    public_id: str
    new_status: str       # "confirmed", "preparing", etc.
    updated_by: str       # "admin" | "kds"


class UpdateStatusUseCase:
    """
    Orchestrate chuyển trạng thái đơn hàng.

    TRƯỚC: Logic duplicate ở admin.py (dòng 124-191) VÀ kds.py (dòng 175-233).
    SAU: 1 use case, cả admin router và KDS router đều gọi chung.
    """

    def __init__(self, order_repo: OrderRepository, event_bus: EventBus) -> None:
        self._repo = order_repo
        self._bus = event_bus

    async def execute(self, command: UpdateStatusCommand) -> Order:
        # --- Load order ---
        order = await self._repo.find_by_public_id(command.public_id)
        if not order:
            raise NotFoundError("Không tìm thấy đơn hàng")

        # --- Chuyển trạng thái (domain validates transition) ---
        new_status = OrderStatus(command.new_status)
        order.change_status(new_status, updated_by=command.updated_by)

        # --- Persist ---
        order = await self._repo.save(order)

        # --- Publish events ---
        events = order.collect_events()
        await self._bus.publish_all(events)

        logger.info(
            f"📋 Order {command.public_id[:8]}... status → {command.new_status} "
            f"(by {command.updated_by})"
        )

        return order


# =============================================================================
# GetOrder — Tra cứu đơn hàng
# =============================================================================
class GetOrderUseCase:
    """Tra cứu đơn hàng bằng public_id."""

    def __init__(self, order_repo: OrderRepository) -> None:
        self._repo = order_repo

    async def execute(self, public_id: str) -> Order:
        order = await self._repo.find_by_public_id(public_id)
        if not order:
            raise NotFoundError("Không tìm thấy đơn hàng")
        return order


# =============================================================================
# ListOrders — Danh sách đơn hàng cho admin panel
# =============================================================================
@dataclass
class ListOrdersQuery:
    """Input cho ListOrdersUseCase."""

    status_filter: str | None = None
    limit: int = 20
    offset: int = 0


class ListOrdersUseCase:
    """
    Danh sách đơn hàng cho admin panel (pagination + filter).

    TRƯỚC: 25 dòng SQL inline trong admin.py GET /admin/orders.
    SAU: Use case gọi repository, router chỉ parse params.
    """

    def __init__(self, order_repo: OrderRepository) -> None:
        self._repo = order_repo

    async def execute(self, query: ListOrdersQuery) -> tuple[list[Order], int]:
        """Return (orders, total_count)."""
        return await self._repo.list_orders(
            status_filter=query.status_filter,
            limit=query.limit,
            offset=query.offset,
        )


# =============================================================================
# GetDashboard — Thống kê nhanh cho admin panel
# =============================================================================
@dataclass
class DashboardStats:
    orders_today: int
    revenue_today: int
    pending_orders: int
    active_products: int


class GetDashboardUseCase:
    """
    Thống kê cơ bản cho admin panel.

    TRƯỚC: 20 dòng SQL inline trong admin.py GET /admin/dashboard.
    SAU: Use case + DashboardQueryService (infrastructure).

    WHY vẫn ở Ordering context (không phải Growth):
    - Dashboard hiển thị orders_today, revenue_today → Ordering data
    - pending_orders → Ordering data
    - active_products → cross-context read (chấp nhận được cho dashboard)
    """

    def __init__(self, dashboard_service: "DashboardQueryService") -> None:
        self._service = dashboard_service

    async def execute(self) -> DashboardStats:
        return await self._service.get_stats()


class DashboardQueryService:
    """ABC cho dashboard queries — implementation ở infrastructure."""

    async def get_stats(self) -> DashboardStats:
        raise NotImplementedError
