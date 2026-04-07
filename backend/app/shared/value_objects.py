"""
Shared Kernel — Value Objects
================================
Value objects dùng chung giữa nhiều Bounded Contexts.

Money nằm ở đây vì cả Catalog (giá sản phẩm) lẫn Ordering (tổng đơn)
đều cần cùng 1 concept tiền. Đơn vị: nghìn đồng (25 = 25.000 VNĐ).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    """
    Giá tiền (đơn vị: nghìn đồng, giống codebase hiện tại).

    WHY value object thay vì raw int:
    - Tránh nhầm lẫn đơn vị (nghìn vs đồng)
    - Đảm bảo không âm
    - Operator overloading cho phép Money(25) + Money(10) = Money(35)

    Examples:
        price = Money(25)        # 25k = 25.000 VNĐ
        total = price * 2        # Money(50)
        discount = price.percentage(20)  # Money(5) = 20% of 25k
    """

    amount: int

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError(f"Số tiền không thể âm: {self.amount}")

    def __add__(self, other: Money) -> Money:
        if isinstance(other, Money):
            return Money(self.amount + other.amount)
        return NotImplemented

    def __sub__(self, other: Money) -> Money:
        if isinstance(other, Money):
            result = self.amount - other.amount
            return Money(max(0, result))  # Không cho phép âm
        return NotImplemented

    def __mul__(self, factor: int) -> Money:
        return Money(self.amount * factor)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self.amount == other.amount
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.amount)

    def __int__(self) -> int:
        return self.amount

    def __repr__(self) -> str:
        return f"Money({self.amount}k)"

    def percentage(self, pct: int) -> Money:
        """Tính phần trăm (làm tròn xuống — có lợi cho quán)."""
        return Money(self.amount * pct // 100)
