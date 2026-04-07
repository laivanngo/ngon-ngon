"""
Unit Tests — CRM Domain (Spend-based Loyalty)
================================================
Kiểm tra mô hình loyalty mới: tích điểm theo chi tiêu.

- Đơn 35k → +35 điểm (rate=1)
- Đơn 150k → +150 điểm
- Tích đủ 200 điểm → reward 20k
- Khách chi nhiều tích nhanh hơn → công bằng hơn stamp card

Không cần database — test thuần business logic.
"""

import pytest
from app.crm.domain.entities import Customer, Review, Referral
from app.crm.domain.value_objects import (
    LoyaltyPoints, ReferralCode, Rating,
    LOYALTY_THRESHOLD, LOYALTY_POINTS_PER_1000,
)


# =============================================================================
# LoyaltyPoints — Spend-based
# =============================================================================

class TestLoyaltyPointsSpendBased:
    """Mô hình mới: 1.000đ chi tiêu = 1 điểm (configurable rate)."""

    def test_points_from_spend_basic(self):
        """Đơn 35k → 35 điểm (rate=1)."""
        assert LoyaltyPoints.points_from_spend(35, rate=1) == 35

    def test_points_from_spend_large_order(self):
        """Đơn 150k → 150 điểm."""
        assert LoyaltyPoints.points_from_spend(150, rate=1) == 150

    def test_points_from_spend_custom_rate(self):
        """Rate=2: đơn 35k → 70 điểm (x2)."""
        assert LoyaltyPoints.points_from_spend(35, rate=2) == 70

    def test_points_from_spend_zero_order(self):
        """Đơn 0đ → 0 điểm."""
        assert LoyaltyPoints.points_from_spend(0, rate=1) == 0

    def test_points_from_spend_default_rate(self):
        """Default rate = LOYALTY_POINTS_PER_1000."""
        result = LoyaltyPoints.points_from_spend(50)
        assert result == 50 * LOYALTY_POINTS_PER_1000

    def test_points_to_reward_spend_model(self):
        """200 điểm threshold: 150 điểm → cần 50 nữa."""
        lp = LoyaltyPoints(150)
        assert lp.points_to_reward == 50

    def test_has_reward_at_threshold(self):
        """Đúng 200 điểm → có reward."""
        lp = LoyaltyPoints(LOYALTY_THRESHOLD)
        assert lp.has_reward is True

    def test_no_reward_below_threshold(self):
        """199 điểm → chưa có reward."""
        lp = LoyaltyPoints(LOYALTY_THRESHOLD - 1)
        assert lp.has_reward is False

    def test_available_rewards(self):
        """450 điểm, threshold=200 → 2 rewards."""
        lp = LoyaltyPoints(450)
        assert lp.available_rewards == 2

    def test_create_negative_rejected(self):
        with pytest.raises(ValueError, match="không thể âm"):
            LoyaltyPoints(-1)

    def test_redeem(self):
        lp = LoyaltyPoints(250)
        new = lp.redeem(200)
        assert new.value == 50

    def test_redeem_insufficient(self):
        lp = LoyaltyPoints(50)
        with pytest.raises(ValueError, match="Không đủ điểm"):
            lp.redeem(200)


# =============================================================================
# Customer — Spend-based loyalty
# =============================================================================

class TestCustomerSpendBased:
    """Customer tích điểm theo chi tiêu, không theo số đơn."""

    def test_create_from_order_spend_points(self):
        """Đơn đầu 45k, rate=1 → 45 điểm (không phải 1 điểm)."""
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=45, points_rate=1,
        )
        assert c.loyalty_points == 45
        assert c.order_count == 1
        assert c.total_spent == 45

    def test_record_order_spend_points(self):
        """Đơn tiếp 80k → +80 điểm."""
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=45, points_rate=1,
        )
        c.record_order("Minh", 80, points_rate=1)
        assert c.loyalty_points == 125  # 45 + 80
        assert c.order_count == 2
        assert c.total_spent == 125

    def test_custom_rate(self):
        """Rate=2: đơn 35k → 70 điểm."""
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=35, points_rate=2,
        )
        assert c.loyalty_points == 70

    def test_multiple_orders_accumulate(self):
        """3 đơn tích dần: 30 + 50 + 120 = 200 điểm → reward."""
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=30, points_rate=1,
        )
        c.record_order("Minh", 50, points_rate=1)
        c.record_order("Minh", 120, points_rate=1)
        assert c.loyalty_points == 200
        assert c.has_reward is True
        assert c.order_count == 3

    def test_has_reward_with_default_threshold(self):
        """LOYALTY_THRESHOLD=200: cần >=200 điểm → reward."""
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=200, points_rate=1,
        )
        assert c.loyalty_points == 200
        assert c.has_reward is True

    def test_points_to_reward(self):
        """120 điểm, threshold=200 → cần 80 nữa."""
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=120, points_rate=1,
        )
        assert c.points_to_reward == 80

    def test_redeem_reward(self):
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=250, points_rate=1,
        )
        c.redeem_reward(LOYALTY_THRESHOLD)
        assert c.loyalty_points == 50

    def test_to_summary_has_all_fields(self):
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=45, points_rate=1,
        )
        s = c.to_summary()
        assert s["phone"] == "0399920878"
        assert s["loyalty_points"] == 45
        assert "points_to_reward" in s
        assert "has_reward" in s

    # --- Referral (unchanged) ---

    def test_ensure_referral_code(self):
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=30,
        )
        code = c.ensure_referral_code()
        assert code.startswith("NG")
        assert len(code) == 6

    def test_share_text(self):
        c = Customer.create_from_order(
            phone="0399920878", name="Minh", order_total=30,
        )
        text = c.share_text
        assert c.referral_code in text


# =============================================================================
# ReferralCode, Rating, Review — unchanged from growth
# =============================================================================

class TestReferralCodeCRM:
    def test_from_phone(self):
        code = ReferralCode.from_phone("0399920878")
        assert str(code).startswith("NG")
        assert len(str(code)) == 6

    def test_deterministic(self):
        c1 = ReferralCode.from_phone("0399920878")
        c2 = ReferralCode.from_phone("0399920878")
        assert c1 == c2


class TestRatingCRM:
    def test_valid_ratings(self):
        for r in range(1, 6):
            assert Rating(r).value == r

    def test_invalid_rejected(self):
        with pytest.raises(ValueError):
            Rating(0)
        with pytest.raises(ValueError):
            Rating(6)


class TestReviewCRM:
    def test_create(self):
        r = Review.create(order_id=1, phone="0399920878", rating=5)
        assert r.rating == 5

    def test_comment_truncated(self):
        r = Review.create(order_id=1, phone="0399920878", rating=3, comment="x" * 600)
        assert len(r.comment) == 500
