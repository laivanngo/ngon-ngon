"""
Ordering Context — Value Objects
==================================
Value objects: immutable, được so sánh bằng VALUE (không phải identity).

WHY value objects thay vì raw string/int:
- Phone("abc") → raise ngay, không đợi đến DB layer
- OrderStatus.can_transition_to() → 1 chỗ duy nhất validate transition
- Domain tự bảo vệ invariants, không phụ thuộc vào caller

NGUYÊN TẮC: Nếu dữ liệu có validation rule → nó là value object.
"""

import html
import re
from enum import Enum as PyEnum


# =============================================================================
# OrderStatus — Lifecycle đơn hàng + transition rules
# =============================================================================
class OrderStatus(str, PyEnum):
    """
    Lifecycle: pending → confirmed → preparing → delivering → done
    Có thể cancelled từ bất kỳ trạng thái nào trước "done".

    WHY transition rules SỐNG Ở ĐÂY thay vì ở router:
    - Trước: duplicate ở admin.py (dòng 150) VÀ kds.py (dòng 197)
    - Sau: 1 chỗ duy nhất, Order.change_status() gọi can_transition_to()
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    DELIVERING = "delivering"
    DONE = "done"
    CANCELLED = "cancelled"

    def can_transition_to(self, target: "OrderStatus") -> bool:
        """
        Kiểm tra transition có hợp lệ không.

        WHY linh hoạt (cho phép skip bước):
        Quán nhỏ hay skip: nhận đơn → pha xong → giao luôn.
        Chỉ block: backward transitions (done→pending) và re-cancel.
        """
        return target in _VALID_TRANSITIONS.get(self, set())

    @property
    def allowed_transitions(self) -> list["OrderStatus"]:
        """Danh sách trạng thái có thể chuyển tới."""
        return list(_VALID_TRANSITIONS.get(self, set()))

    @property
    def is_terminal(self) -> bool:
        """done và cancelled là terminal — không chuyển tiếp được."""
        return self in (OrderStatus.DONE, OrderStatus.CANCELLED)


# Tách ra constant để dễ đọc (giống bảng trong admin.py dòng 150-157)
_VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {
        OrderStatus.CONFIRMED,
        OrderStatus.PREPARING,
        OrderStatus.DELIVERING,
        OrderStatus.CANCELLED,
    },
    OrderStatus.CONFIRMED: {
        OrderStatus.PREPARING,
        OrderStatus.DELIVERING,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PREPARING: {
        OrderStatus.DELIVERING,
        OrderStatus.DONE,
        OrderStatus.CANCELLED,
    },
    OrderStatus.DELIVERING: {
        OrderStatus.DONE,
        OrderStatus.CANCELLED,
    },
    OrderStatus.DONE: set(),       # Terminal state
    OrderStatus.CANCELLED: set(),  # Terminal state
}


# =============================================================================
# DeliveryOption — Giao liền hay hẹn giờ
# =============================================================================
class DeliveryOption(str, PyEnum):
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"


# =============================================================================
# Phone — Số điện thoại VN, tự validate + clean
# =============================================================================
from app.shared.constants import VN_PHONE_REGEX as _VN_PHONE_REGEX
from app.shared.utils import clean_phone as _clean_phone


class Phone:
    """
    Value object cho SĐT Việt Nam.
    Tự clean (bỏ dấu chấm, khoảng trắng) + validate format.

    WHY validation ở đây thay vì chỉ ở schema:
    - Schema validate input từ HTTP request
    - Phone validate ở domain level → dù tạo Order từ đâu (API, CLI, test)
      đều được validate
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        clean = _clean_phone(value)
        if not _VN_PHONE_REGEX.match(clean):
            raise ValueError("Số điện thoại không hợp lệ. VD: 0378148148")
        self._value = clean

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"Phone({self._value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Phone):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)


# =============================================================================
# Address — Địa chỉ giao hàng, tự sanitize XSS
# =============================================================================
class Address:
    """
    Value object cho địa chỉ.
    Tự strip HTML tags + escape special chars (XSS prevention).

    WHY sanitize ở domain: defense in depth.
    Frontend escHtml() có thể bị bypass (curl/Postman).
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Địa chỉ không được để trống")
        # Strip HTML tags rồi escape special chars
        clean = re.sub(r"<[^>]+>", "", stripped)
        self._value = html.escape(clean.strip(), quote=True)

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"Address({self._value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Address):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)


# =============================================================================
# Money — Import từ Shared Kernel (single source of truth)
# =============================================================================
from app.shared.value_objects import Money  # noqa: E402, F401
