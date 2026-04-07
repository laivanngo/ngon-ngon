"""
Unit Tests — Catalog Domain (Menu, Sản phẩm, Danh mục, Topping)
==================================================================
Kiểm tra quy tắc quản lý menu của quán:

- Sản phẩm phải có tên, giá > 0
- Soft delete (ẩn sản phẩm, không xóa thật → giữ lịch sử đơn cũ)
- Danh mục quản lý nhóm sản phẩm
- Topping thêm vào đồ uống
- Cross-sell: "Thêm cho đủ bữa?" gợi ý mua kèm
- TimeDeal: giảm giá theo khung giờ

Không cần database.
"""

import pytest
from app.catalog.domain.entities import (
    Category, Product, ProductSize, ProductTopping,
    Topping, CrossSellItem, TimeDeal,
)
from app.catalog.domain.value_objects import LayoutType, Money


# =============================================================================
# Catalog Money — Giá tiền (nghìn đồng)
# =============================================================================

class TestCatalogMoney:
    """Money value object cho Catalog: hỗ trợ +, -, ×, %."""

    def test_create(self):
        m = Money(25)
        assert m.amount == 25

    def test_negative_rejected(self):
        with pytest.raises(ValueError, match="không thể âm"):
            Money(-1)

    def test_add(self):
        assert (Money(20) + Money(5)).amount == 25

    def test_subtract(self):
        assert (Money(25) - Money(5)).amount == 20

    def test_subtract_below_zero_raises(self):
        """Catalog Money: trừ xuống âm → lỗi (khác Ordering Money clamp)."""
        with pytest.raises(ValueError):
            Money(5) - Money(10)

    def test_multiply(self):
        """25k × 2 = 50k (mua 2 ly)."""
        assert (Money(25) * 2).amount == 50

    def test_percentage(self):
        """Giảm 20% trên đơn 50k → giảm 10k."""
        assert Money(50).percentage(20).amount == 10

    def test_percentage_rounds_down(self):
        """15% của 25k = 3.75 → làm tròn xuống = 3k (có lợi cho quán)."""
        assert Money(25).percentage(15).amount == 3


# =============================================================================
# LayoutType — Cách hiển thị danh mục
# =============================================================================

class TestLayoutType:
    def test_grid(self):
        assert LayoutType.GRID.value == "grid"

    def test_list(self):
        assert LayoutType.LIST.value == "list"

    def test_combo_scroll(self):
        assert LayoutType.COMBO_SCROLL.value == "combo"

    def test_invalid_rejected(self):
        with pytest.raises(ValueError):
            LayoutType("carousel")


# =============================================================================
# Category — Danh mục menu
# =============================================================================

class TestCategory:
    def test_create(self):
        cat = Category.create(slug="tra-sua", name="Trà Sữa", emoji="🧋")
        assert cat.slug == "tra-sua"
        assert cat.name == "Trà Sữa"
        assert cat.emoji == "🧋"
        assert cat.is_active is True

    def test_create_trims_whitespace(self):
        cat = Category.create(slug="  tra-sua  ", name="  Trà Sữa  ")
        assert cat.slug == "tra-sua"
        assert cat.name == "Trà Sữa"

    def test_empty_slug_rejected(self):
        with pytest.raises(ValueError, match="Slug"):
            Category.create(slug="", name="Trà Sữa")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="Tên"):
            Category.create(slug="tra-sua", name="")

    def test_update_partial(self):
        """Chỉ update field được truyền, giữ nguyên field khác."""
        cat = Category.create(slug="tra-sua", name="Trà Sữa", emoji="🧋")
        cat.update(name="Trà Sữa Nóng", emoji="☕")
        assert cat.name == "Trà Sữa Nóng"
        assert cat.emoji == "☕"
        assert cat.slug == "tra-sua"  # không đổi

    def test_deactivate(self):
        """Soft delete: ẩn danh mục, không xóa."""
        cat = Category.create(slug="tra-sua", name="Trà Sữa")
        cat.deactivate()
        assert cat.is_active is False

    def test_active_products_filters_and_sorts(self):
        """Chỉ trả về sản phẩm active, sắp theo sort_order."""
        cat = Category.create(slug="ts", name="Trà Sữa")
        p1 = Product(
            id=1, legacy_id="p1", category_id=1, name="Trà Sữa Truyền Thống",
            base_price=20, sort_order=2, is_active=True,
        )
        p2 = Product(
            id=2, legacy_id="p2", category_id=1, name="Matcha",
            base_price=25, sort_order=1, is_active=True,
        )
        p3 = Product(
            id=3, legacy_id="p3", category_id=1, name="SP Ẩn",
            base_price=15, sort_order=0, is_active=False,
        )
        cat.products = [p1, p2, p3]

        active = cat.active_products
        assert len(active) == 2
        assert active[0].name == "Matcha"       # sort_order=1 → đầu tiên
        assert active[1].name == "Trà Sữa Truyền Thống"  # sort_order=2


# =============================================================================
# Product — Sản phẩm
# =============================================================================

class TestProduct:
    def test_create_basic(self):
        p = Product.create(
            legacy_id="ts1", category_id=1,
            name="Trà Sữa", base_price=20,
        )
        assert p.name == "Trà Sữa"
        assert p.base_price == 20
        assert p.is_active is True
        assert p.id is None  # chưa persist

    def test_create_with_sizes(self):
        """Sản phẩm có nhiều size: M, L, XL."""
        p = Product.create(
            legacy_id="ts1", category_id=1,
            name="Trà Sữa", base_price=20,
            sizes=[
                {"label": "M", "price": 20},
                {"label": "L", "price": 22},
                {"label": "XL", "price": 25},
            ],
        )
        assert len(p.sizes) == 3
        assert p.sizes[2].label == "XL"
        assert p.sizes[2].price == 25

    def test_create_with_toppings(self):
        """Sản phẩm cho phép thêm topping."""
        p = Product.create(
            legacy_id="ts1", category_id=1,
            name="Trà Sữa", base_price=20,
            topping_ids=[1, 3, 5],
        )
        assert len(p.product_toppings) == 3
        assert p.topping_ids == [1, 3, 5]

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="Tên"):
            Product.create(
                legacy_id="ts1", category_id=1,
                name="", base_price=20,
            )

    def test_zero_price_rejected(self):
        """Giá = 0 → không hợp lý → từ chối."""
        with pytest.raises(ValueError, match="Giá"):
            Product.create(
                legacy_id="ts1", category_id=1,
                name="Trà Sữa", base_price=0,
            )

    def test_empty_legacy_id_rejected(self):
        with pytest.raises(ValueError, match="Legacy ID"):
            Product.create(
                legacy_id="", category_id=1,
                name="Trà Sữa", base_price=20,
            )

    def test_update_partial(self):
        """Update 1 số field, giữ nguyên field khác."""
        p = Product.create(
            legacy_id="ts1", category_id=1,
            name="Trà Sữa", base_price=20,
        )
        p.update(name="Trà Sữa Kem Cheese", base_price=30)
        assert p.name == "Trà Sữa Kem Cheese"
        assert p.base_price == 30
        assert p.legacy_id == "ts1"  # không đổi

    def test_replace_sizes(self):
        """Đổi toàn bộ sizes (khi admin sửa menu)."""
        p = Product.create(
            legacy_id="ts1", category_id=1,
            name="Trà Sữa", base_price=20,
            sizes=[{"label": "M", "price": 20}],
        )
        p.replace_sizes([
            {"label": "L", "price": 25},
            {"label": "XL", "price": 30},
        ])
        assert len(p.sizes) == 2
        assert p.sizes[0].label == "L"

    def test_replace_toppings(self):
        p = Product.create(
            legacy_id="ts1", category_id=1,
            name="Trà Sữa", base_price=20,
            topping_ids=[1, 2],
        )
        p.replace_toppings([3, 4, 5])
        assert p.topping_ids == [3, 4, 5]

    def test_deactivate(self):
        """Soft delete sản phẩm."""
        p = Product.create(
            legacy_id="ts1", category_id=1,
            name="Trà Sữa", base_price=20,
        )
        p.deactivate()
        assert p.is_active is False


# =============================================================================
# Topping — Topping thêm vào đồ uống
# =============================================================================

class TestTopping:
    def test_create(self):
        t = Topping.create(name="Trân Châu", legacy_id="tp1", price=5)
        assert t.name == "Trân Châu"
        assert t.price == 5

    def test_create_auto_legacy_id(self):
        """Không truyền legacy_id → tự generate."""
        t = Topping.create(name="Thạch Dừa")
        assert t.legacy_id.startswith("tp")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="Tên"):
            Topping.create(name="")

    def test_update(self):
        t = Topping.create(name="Trân Châu", legacy_id="tp1", price=5)
        t.update(name="Trân Châu Đen", price=7)
        assert t.name == "Trân Châu Đen"
        assert t.price == 7

    def test_deactivate(self):
        t = Topping.create(name="Trân Châu", legacy_id="tp1")
        t.deactivate()
        assert t.is_active is False


# =============================================================================
# CrossSellItem — Gợi ý "mua thêm"
# =============================================================================

class TestCrossSellItem:
    def test_create(self):
        cs = CrossSellItem.create(product_id=1, target="drink")
        assert cs.product_id == 1
        assert cs.target == "drink"
        assert cs.is_active is True

    def test_valid_targets(self):
        for target in ["drink", "snack", "both"]:
            cs = CrossSellItem.create(product_id=1, target=target)
            assert cs.target == target

    def test_invalid_target_rejected(self):
        with pytest.raises(ValueError, match="Target"):
            CrossSellItem.create(product_id=1, target="dessert")

    def test_update(self):
        cs = CrossSellItem.create(product_id=1, target="drink")
        cs.update(target="both", sort_order=5)
        assert cs.target == "both"
        assert cs.sort_order == 5


# =============================================================================
# TimeDeal — Flash deal theo khung giờ
# =============================================================================

class TestTimeDeal:
    """VD: "Happy Hour 14h-17h: giảm 15%" → khách KCN mua buổi chiều."""

    def test_active_within_hours(self):
        """Trong khung giờ → deal đang chạy."""
        deal = TimeDeal(
            id=1, label="HH", title="Happy Hour",
            start_hour=14, end_hour=17, discount_percent=15,
            is_active=True,
        )
        assert deal.is_active_at(15) is True

    def test_inactive_outside_hours(self):
        """Ngoài khung giờ → deal không chạy."""
        deal = TimeDeal(
            id=1, label="HH", title="Happy Hour",
            start_hour=14, end_hour=17, discount_percent=15,
            is_active=True,
        )
        assert deal.is_active_at(12) is False

    def test_inactive_at_end_hour(self):
        """Đúng giờ kết thúc → hết deal (end_hour exclusive)."""
        deal = TimeDeal(
            id=1, label="HH", title="Happy Hour",
            start_hour=14, end_hour=17, discount_percent=15,
            is_active=True,
        )
        assert deal.is_active_at(17) is False

    def test_active_at_start_hour(self):
        """Đúng giờ bắt đầu → deal chạy (start_hour inclusive)."""
        deal = TimeDeal(
            id=1, label="HH", title="Happy Hour",
            start_hour=14, end_hour=17, discount_percent=15,
            is_active=True,
        )
        assert deal.is_active_at(14) is True

    def test_disabled_deal(self):
        """Deal bị tắt (is_active=False) → không chạy dù đúng giờ."""
        deal = TimeDeal(
            id=1, label="HH", title="Happy Hour",
            start_hour=14, end_hour=17, discount_percent=15,
            is_active=False,
        )
        assert deal.is_active_at(15) is False
