"""
Ordering Context — Thin Router
=================================
TRƯỚC: routers/orders.py = 342 dòng — tính giá, customer tracking, WS broadcast.
SAU: router = ~60 dòng — chỉ map HTTP request ↔ use case.

Router KHÔNG CHỨA business logic. Router chỉ:
1. Parse HTTP request → command/query
2. Gọi use case (injected via dependencies.py)
3. Convert domain result → HTTP response

WHY dependencies.py tách riêng:
- Router không biết dùng SqlOrderRepository hay InMemoryOrderRepository
- Đổi implementation → sửa dependencies.py, router nguyên vẹn
- Test → app.dependency_overrides[get_place_order] = mock_factory
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.ordering.application.use_cases import (
    GetOrderUseCase,
    PlaceOrderCommand,
    PlaceOrderUseCase,
)
from app.ordering.domain.services import CartItem
from app.ordering.presentation.dependencies import get_place_order, get_order
from app.ordering.presentation.schemas import OrderCreate, OrderResponse
from app.shared.exceptions import DomainError, NotFoundError, ValidationError

logger = logging.getLogger("ngonngon.ordering.router")
router = APIRouter()


# =============================================================================
# POST /orders — Tạo đơn hàng
# =============================================================================
@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    use_case: PlaceOrderUseCase = Depends(get_place_order),
):
    """
    Tạo đơn hàng mới.
    TRƯỚC: 260 dòng trong endpoint.
    SAU: 10 dòng — parse request → gọi use case → return response.
    """
    try:
        command = PlaceOrderCommand(
            customer_name=payload.customer_name,
            phone=payload.phone,
            address=payload.address,
            note=payload.note,
            delivery_type=payload.delivery_type,
            scheduled_time=payload.scheduled_time,
            items=[
                CartItem(
                    product_id=item.product_id,
                    size=item.size,
                    sweetness=item.sweetness,
                    ice_level=item.ice_level,
                    quantity=item.quantity,
                    toppings=item.toppings or None,
                    note=item.note,
                )
                for item in payload.items
            ],
        )
        order = await use_case.execute(command)
        return OrderResponse.from_domain(order)

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


# =============================================================================
# GET /orders/{public_id} — Tra cứu đơn hàng
# =============================================================================
@router.get("/orders/{public_id}", response_model=OrderResponse)
async def get_order_endpoint(
    public_id: str,
    use_case: GetOrderUseCase = Depends(get_order),
):
    """Khách tra cứu đơn hàng bằng public_id (UUID)."""
    try:
        order = await use_case.execute(public_id)
        return OrderResponse.from_domain(order)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn hàng",
        )


# =============================================================================
# GET /orders/{public_id}/zalo-text — Format text cho Zalo
# =============================================================================
@router.get("/orders/{public_id}/zalo-text")
async def get_order_zalo_text(
    public_id: str,
    use_case: GetOrderUseCase = Depends(get_order),
):
    """Trả về text đã format sẵn cho Zalo."""
    try:
        order = await use_case.execute(public_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    lines = [
        "📋 ĐƠN HÀNG — NGON-NGON",
        "═" * 30,
    ]
    for idx, item in enumerate(order.items, 1):
        line = f"{idx}. {item.product_name}"
        if item.size:
            line += f" (Size {item.size})"
        line += f" x{item.quantity} — {item.unit_price * item.quantity}k"
        lines.append(line)

        details = []
        if item.sweetness:
            details.append(f"🍬 {item.sweetness}")
        if item.ice_level:
            details.append(f"🧊 {item.ice_level}")
        if item.toppings_text:
            details.append(f"🧁 {item.toppings_text}")
        if item.note:
            details.append(f"📝 {item.note}")
        if details:
            lines.append("   " + " | ".join(details))

    lines.extend(
        [
            "─" * 30,
            f"💰 TỔNG: {order.total}k",
            "─" * 30,
            f"👤 {order.customer_name}",
            f"📱 {order.phone}",
            f"📍 {order.address}",
        ]
    )
    if order.note:
        lines.append(f"📝 {order.note}")
    lines.append(f"\n🆔 Mã đơn: {order.public_id[:8]}")

    return {"text": "\n".join(lines)}
