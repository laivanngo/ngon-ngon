"""
CRM Context — Value Objects
================================
LoyaltyPoints, ReferralCode, Rating + business constants.

THAY ĐỔI SO VỚI GROWTH:
- Loyalty chuyển từ "1 đơn = 1 điểm" sang "1.000đ chi tiêu = 1 điểm"
- LOYALTY_THRESHOLD giờ = số ĐIỂM (không phải số đơn) cần để đổi thưởng
- Mặc định: 200 điểm = reward 20k (tương đương ~200k chi tiêu = 20k back = 10%)
- Constants là FALLBACK — giá trị thực tế đọc từ growth_settings table (admin chỉnh)
"""

import hashlib


# =============================================================================
# Business Constants — Fallback khi chưa có giá trị trong DB
# =============================================================================
# Giá trị thực tế đọc từ bảng growth_settings (admin chỉnh từ panel).
# Constants ở đây chỉ dùng khi DB chưa seed hoặc test không có DB.

LOYALTY_POINTS_PER_1000 = 1  # 1.000đ chi tiêu = 1 điểm
LOYALTY_THRESHOLD = 200      # Tích đủ 200 điểm → 1 phần thưởng
LOYALTY_REWARD_VALUE = 20    # Giá trị thưởng tối đa (20k)
REFERRAL_DISCOUNT = 5        # Giảm 5k cho cả người giới thiệu và được giới thiệu


# =============================================================================
# LoyaltyPoints — Tích điểm theo chi tiêu
# =============================================================================
class LoyaltyPoints:
    """
    Value object cho điểm loyalty.

    MÔ HÌNH MỚI (spend-based):
    - Mỗi 1.000đ chi tiêu = 1 điểm (configurable qua settings)
    - Đơn 35k → 35 điểm. Đơn 150k → 150 điểm.
    - Khách chi nhiều = tích nhanh hơn → công bằng hơn stamp card.

    MÔ HÌNH CŨ (stamp-based):
    - Mỗi đơn = 1 điểm, bất kể giá trị → không công bằng.
    """

    __slots__ = ("_points",)

    def __init__(self, points: int) -> None:
        if points < 0:
            raise ValueError(f"Điểm loyalty không thể âm: {points}")
        self._points = points

    @property
    def value(self) -> int:
        return self._points

    @property
    def points_to_reward(self) -> int:
        """Bao nhiêu điểm nữa để đổi reward tiếp theo."""
        return max(0, LOYALTY_THRESHOLD - (self._points % LOYALTY_THRESHOLD))

    @property
    def has_reward(self) -> bool:
        """Đã tích đủ để đổi reward chưa."""
        return self._points >= LOYALTY_THRESHOLD

    @property
    def available_rewards(self) -> int:
        """Số lần reward có thể đổi."""
        return self._points // LOYALTY_THRESHOLD

    def add(self, points: int = 1) -> "LoyaltyPoints":
        """Tạo instance mới với điểm đã cộng (immutable pattern)."""
        return LoyaltyPoints(self._points + points)

    @staticmethod
    def points_from_spend(order_total: int, rate: int = LOYALTY_POINTS_PER_1000) -> int:
        """
        Tính điểm từ giá trị đơn hàng.
        order_total tính bằng nghìn đồng (VD: 35 = 35k).
        rate: bao nhiêu điểm per 1k chi tiêu (mặc định 1).
        """
        return max(0, order_total * rate)

    def redeem(self, points: int) -> "LoyaltyPoints":
        """Trừ điểm khi đổi reward."""
        if points > self._points:
            raise ValueError(
                f"Không đủ điểm: cần {points}, hiện có {self._points}"
            )
        return LoyaltyPoints(self._points - points)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LoyaltyPoints):
            return self._points == other._points
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._points)

    def __int__(self) -> int:
        return self._points

    def __repr__(self) -> str:
        return f"LoyaltyPoints({self._points})"


# =============================================================================
# ReferralCode — Mã giới thiệu, tự generate từ SĐT
# =============================================================================
class ReferralCode:
    """
    Value object cho mã giới thiệu.
    Format: "NG" + 4 hex viết hoa. VD: "NG3FA1"
    Deterministic — cùng phone luôn ra cùng code.
    """

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        if not code or len(code) != 6 or not code.startswith("NG"):
            raise ValueError(f"Mã giới thiệu không hợp lệ: {code}")
        self._code = code

    @classmethod
    def from_phone(cls, phone: str) -> "ReferralCode":
        """Generate mã giới thiệu từ SĐT."""
        from app.shared.utils import clean_phone
        clean = clean_phone(phone)
        hex_part = hashlib.md5(clean.encode()).hexdigest()[:4].upper()
        return cls(f"NG{hex_part}")

    @property
    def value(self) -> str:
        return self._code

    def __str__(self) -> str:
        return self._code

    def __repr__(self) -> str:
        return f"ReferralCode({self._code!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ReferralCode):
            return self._code == other._code
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._code)


# =============================================================================
# Rating — Đánh giá 1-5 sao
# =============================================================================
class Rating:
    """Value object cho rating. Validate 1-5."""

    __slots__ = ("_value",)

    def __init__(self, value: int) -> None:
        if not (1 <= value <= 5):
            raise ValueError(f"Rating phải từ 1-5, nhận được: {value}")
        self._value = value

    @property
    def value(self) -> int:
        return self._value

    def __int__(self) -> int:
        return self._value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Rating):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"Rating({'⭐' * self._value})"
