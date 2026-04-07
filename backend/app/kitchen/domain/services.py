"""
Kitchen Context — Domain Services & Repository ABCs
======================================================
Interfaces cho Kitchen context.

KitchenOrderRepository: read-only projection từ Order table.
PinAuthService: xác thực KDS bằng PIN 4 số.

WHY Kitchen có auth riêng (không dùng Identity context):
- KDS auth = PIN 4 số (tay ướt, nhanh) ≠ Admin auth = username/password
- Token KDS sống 12h (treo tablet cả ngày) ≠ Admin token 1h
- Brute-force protection riêng (5 attempts / 5 min per IP)
- Nếu gộp vào Identity → Identity phải biết KDS business rules → coupling
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.kitchen.domain.entities import KitchenOrder


# =============================================================================
# KitchenOrderRepository ABC — Read-only projection
# =============================================================================
class KitchenOrderRepository(ABC):
    """
    Read-only access vào Order data, formatted cho KDS.

    WHY repository thay vì trực tiếp query:
    - Kitchen domain không biết SQLAlchemy
    - Test bằng InMemoryKitchenOrderRepository → không cần DB
    - Khi tách DB → đổi implementation, domain nguyên vẹn
    """

    @abstractmethod
    async def get_active_queue(self) -> list[KitchenOrder]:
        """
        Lấy tất cả đơn KDS cần hiển thị:
        - Active: pending, confirmed, preparing, delivering (luôn hiện)
        - Recent terminal: done/cancelled trong 10 phút gần nhất

        WHY 10 phút cho done/cancelled:
        - Bếp cần thấy "đơn vừa xong" để xác nhận
        - Quá lâu → màn hình đầy đơn cũ
        """
        ...


# =============================================================================
# PinAuthService ABC — Xác thực KDS bằng PIN
# =============================================================================
@dataclass
class KdsAuthResult:
    """Kết quả xác thực KDS."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 43200  # 12h default


class PinAuthService(ABC):
    """
    Xác thực KDS bằng PIN 4 số.

    Business rules:
    1. PIN phải khớp với KDS_PIN trong config
    2. Rate limit: max 5 attempts / 5 phút per IP
    3. Token JWT, subject="kds", sống 12h

    WHY domain service (không chỉ là infrastructure):
    - Rate limiting là business rule (bảo vệ quán khỏi brute-force)
    - Domain define interface, infrastructure implement
    """

    @abstractmethod
    async def authenticate(self, pin: str, client_ip: str) -> KdsAuthResult:
        """
        Xác thực PIN, trả JWT token.
        Raise ValueError nếu PIN sai.
        Raise PermissionError nếu rate limited.
        """
        ...
