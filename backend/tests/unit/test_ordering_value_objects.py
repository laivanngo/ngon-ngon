"""
Unit Tests — Ordering Value Objects
======================================
Test các "quy tắc nhỏ" mà quán đặt ra:
- SĐT phải đúng format VN (10 số, đầu 0)
- Địa chỉ không được chứa mã độc (XSS)
- Tiền không được âm
- Đơn hàng chỉ được chuyển trạng thái theo đúng luồng

Không cần database, không cần server — chạy cực nhanh.
"""

import pytest
from app.ordering.domain.value_objects import (
    Phone, Address, Money, OrderStatus, DeliveryOption,
)


# =============================================================================
# Phone — Số điện thoại VN
# =============================================================================

class TestPhone:
    """SĐT hợp lệ = 10 chữ số, bắt đầu bằng 03/05/07/08/09."""

    def test_valid_phone(self):
        """SĐT chuẩn 10 số → chấp nhận."""
        p = Phone("0378148148")
        assert str(p) == "0378148148"

    def test_phone_with_dots_cleaned(self):
        """Khách hay ghi SĐT có dấu chấm → tự động xóa chấm."""
        p = Phone("0378.148.148")
        assert str(p) == "0378148148"

    def test_phone_with_spaces_cleaned(self):
        """SĐT có khoảng trắng → tự động xóa."""
        p = Phone("0378 148 148")
        assert str(p) == "0378148148"

    def test_phone_with_dashes_cleaned(self):
        """SĐT có gạch ngang → tự động xóa."""
        p = Phone("0378-148-148")
        assert str(p) == "0378148148"

    def test_phone_mixed_separators(self):
        """SĐT trộn lẫn dấu chấm, khoảng trắng, gạch → vẫn clean được."""
        p = Phone("037.8 148-148")
        assert str(p) == "0378148148"

    def test_phone_all_head_prefixes(self):
        """Tất cả đầu số VN hợp lệ: 03x, 05x, 07x, 08x, 09x."""
        valid_prefixes = ["03", "05", "07", "08", "09"]
        for prefix in valid_prefixes:
            p = Phone(f"{prefix}12345678")
            assert str(p) == f"{prefix}12345678"

    def test_phone_invalid_prefix_rejected(self):
        """Đầu số 01, 02, 04, 06 → không hợp lệ."""
        with pytest.raises(ValueError, match="không hợp lệ"):
            Phone("0112345678")

    def test_phone_too_short(self):
        """Ít hơn 10 số → từ chối."""
        with pytest.raises(ValueError):
            Phone("037814")

    def test_phone_too_long(self):
        """Hơn 10 số → từ chối."""
        with pytest.raises(ValueError):
            Phone("03781481481")

    def test_phone_letters_rejected(self):
        """Chứa chữ cái → từ chối."""
        with pytest.raises(ValueError):
            Phone("037abc8148")

    def test_phone_empty_rejected(self):
        """Rỗng → từ chối."""
        with pytest.raises(ValueError):
            Phone("")

    def test_phone_equality(self):
        """Hai Phone cùng số → bằng nhau (value object)."""
        assert Phone("0378148148") == Phone("0378.148.148")

    def test_phone_different_not_equal(self):
        """Hai Phone khác số → không bằng nhau."""
        assert Phone("0378148148") != Phone("0901234567")

    def test_phone_hashable(self):
        """Phone dùng được làm key trong dict/set."""
        phone_set = {Phone("0378148148"), Phone("0378.148.148")}
        assert len(phone_set) == 1  # cùng 1 SĐT


# =============================================================================
# Address — Địa chỉ giao hàng (chống XSS)
# =============================================================================

class TestAddress:
    """Địa chỉ phải được sanitize: bỏ HTML, escape ký tự đặc biệt."""

    def test_valid_address(self):
        """Địa chỉ bình thường → giữ nguyên."""
        a = Address("Cty Pouchen - Cổng B")
        assert str(a) == "Cty Pouchen - Cổng B"

    def test_address_stripped(self):
        """Khoảng trắng đầu/cuối → tự động xóa."""
        a = Address("  Cổng B  ")
        assert str(a) == "Cổng B"

    def test_address_xss_script_removed(self):
        """Tag <script> → bị xóa hoàn toàn."""
        a = Address('<script>alert("hack")</script>Cổng B')
        assert "<script>" not in str(a)
        assert "Cổng B" in str(a)

    def test_address_xss_img_removed(self):
        """Tag <img onerror=...> → bị xóa."""
        a = Address('Cổng B<img onerror=alert(1)>')
        assert "<img" not in str(a)

    def test_address_html_entities_escaped(self):
        """Ký tự đặc biệt (< > & ") → escaped thành HTML entities."""
        a = Address('Cty A & B "VIP"')
        result = str(a)
        assert "&amp;" in result   # & → &amp;
        assert "&quot;" in result  # " → &quot;

    def test_address_empty_rejected(self):
        """Địa chỉ rỗng → từ chối."""
        with pytest.raises(ValueError, match="không được để trống"):
            Address("")

    def test_address_whitespace_only_rejected(self):
        """Chỉ có khoảng trắng → từ chối."""
        with pytest.raises(ValueError, match="không được để trống"):
            Address("   ")

    def test_address_equality(self):
        """Hai Address cùng giá trị → bằng nhau."""
        assert Address("Cổng B") == Address("Cổng B")

    def test_address_unicode_preserved(self):
        """Tiếng Việt có dấu → giữ nguyên."""
        a = Address("Công ty TNHH Việt Phát — Cổng B")
        assert "Việt Phát" in str(a)


# =============================================================================
# Money — Tiền (đơn vị: nghìn đồng)
# =============================================================================

class TestMoney:
    """Tiền: 25 = 25.000 VNĐ. Không được âm, hỗ trợ cộng/trừ."""

    def test_create_valid(self):
        """Tạo Money bình thường."""
        m = Money(25)
        assert m.amount == 25

    def test_zero_allowed(self):
        """0 đồng → hợp lệ (đơn miễn phí)."""
        m = Money(0)
        assert m.amount == 0

    def test_negative_rejected(self):
        """Tiền âm → từ chối."""
        with pytest.raises(ValueError, match="không thể âm"):
            Money(-5)

    def test_add(self):
        """25k + 10k = 35k."""
        assert (Money(25) + Money(10)).amount == 35

    def test_subtract(self):
        """25k - 10k = 15k."""
        assert (Money(25) - Money(10)).amount == 15

    def test_subtract_below_zero_clamps(self):
        """10k - 25k = 0 (không cho phép âm, trả về 0)."""
        result = Money(10) - Money(25)
        assert result.amount == 0

    def test_equality(self):
        """Cùng số tiền → bằng nhau."""
        assert Money(25) == Money(25)

    def test_int_conversion(self):
        """Chuyển về int để tính toán."""
        assert int(Money(25)) == 25


# =============================================================================
# OrderStatus — Trạng thái đơn hàng + luồng chuyển đổi
# =============================================================================

class TestOrderStatus:
    """
    Luồng đơn hàng: pending → confirmed → preparing → delivering → done
    Có thể hủy (cancelled) từ bất kỳ bước nào trước done.
    Cho phép skip bước (quán nhỏ hay skip: nhận → pha → giao luôn).
    """

    # --- Luồng chuẩn ---
    def test_pending_to_confirmed(self):
        assert OrderStatus.PENDING.can_transition_to(OrderStatus.CONFIRMED)

    def test_confirmed_to_preparing(self):
        assert OrderStatus.CONFIRMED.can_transition_to(OrderStatus.PREPARING)

    def test_preparing_to_delivering(self):
        assert OrderStatus.PREPARING.can_transition_to(OrderStatus.DELIVERING)

    def test_delivering_to_done(self):
        assert OrderStatus.DELIVERING.can_transition_to(OrderStatus.DONE)

    # --- Skip bước (quán nhỏ hay làm) ---
    def test_pending_can_skip_to_preparing(self):
        """Quán nhỏ: nhận đơn → pha luôn (skip confirmed)."""
        assert OrderStatus.PENDING.can_transition_to(OrderStatus.PREPARING)

    def test_pending_can_skip_to_delivering(self):
        """Quán nhỏ: nhận đơn → giao luôn (skip confirmed + preparing)."""
        assert OrderStatus.PENDING.can_transition_to(OrderStatus.DELIVERING)

    def test_confirmed_can_skip_to_delivering(self):
        """Xác nhận xong → giao luôn (skip preparing)."""
        assert OrderStatus.CONFIRMED.can_transition_to(OrderStatus.DELIVERING)

    def test_preparing_can_skip_to_done(self):
        """Pha xong → xong luôn (khách nhận tại quán, skip delivering)."""
        assert OrderStatus.PREPARING.can_transition_to(OrderStatus.DONE)

    # --- Hủy đơn ---
    def test_cancel_from_pending(self):
        assert OrderStatus.PENDING.can_transition_to(OrderStatus.CANCELLED)

    def test_cancel_from_confirmed(self):
        assert OrderStatus.CONFIRMED.can_transition_to(OrderStatus.CANCELLED)

    def test_cancel_from_preparing(self):
        assert OrderStatus.PREPARING.can_transition_to(OrderStatus.CANCELLED)

    def test_cancel_from_delivering(self):
        assert OrderStatus.DELIVERING.can_transition_to(OrderStatus.CANCELLED)

    # --- Không cho phép đi ngược ---
    def test_cannot_go_back_done_to_pending(self):
        """Đã xong → không thể quay lại pending."""
        assert not OrderStatus.DONE.can_transition_to(OrderStatus.PENDING)

    def test_cannot_go_back_done_to_anything(self):
        """Đã xong → không chuyển đi đâu được nữa."""
        for status in OrderStatus:
            assert not OrderStatus.DONE.can_transition_to(status)

    def test_cancelled_is_terminal(self):
        """Đã hủy → không chuyển đi đâu được nữa."""
        for status in OrderStatus:
            assert not OrderStatus.CANCELLED.can_transition_to(status)

    # --- Terminal states ---
    def test_done_is_terminal(self):
        assert OrderStatus.DONE.is_terminal is True

    def test_cancelled_is_terminal(self):
        assert OrderStatus.CANCELLED.is_terminal is True

    def test_pending_is_not_terminal(self):
        assert OrderStatus.PENDING.is_terminal is False

    def test_preparing_is_not_terminal(self):
        assert OrderStatus.PREPARING.is_terminal is False

    # --- Allowed transitions list ---
    def test_pending_allowed_transitions(self):
        """Từ pending có thể đi: confirmed, preparing, delivering, cancelled."""
        allowed = {s.value for s in OrderStatus.PENDING.allowed_transitions}
        assert allowed == {"confirmed", "preparing", "delivering", "cancelled"}

    def test_done_allowed_transitions_empty(self):
        assert OrderStatus.DONE.allowed_transitions == []


# =============================================================================
# DeliveryOption — Giao liền hay hẹn giờ
# =============================================================================

class TestDeliveryOption:
    def test_immediate(self):
        assert DeliveryOption.IMMEDIATE.value == "immediate"

    def test_scheduled(self):
        assert DeliveryOption.SCHEDULED.value == "scheduled"

    def test_invalid_rejected(self):
        with pytest.raises(ValueError):
            DeliveryOption("asap")
