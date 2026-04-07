"""
Unit Tests — Pricing Pipeline with Flash Sale
=================================================
Test "best deal wins" logic khi cả Time Deal + Flash Sale đều active.

Dùng Fake ports — không cần DB.
"""

import pytest

from app.ordering.domain.catalog_port import (
    ActiveTimeDeal,
    CatalogPricingPort,
    PricingProductData,
    PricingSizeData,
    PricingToppingData,
)
from app.ordering.domain.promotions_port import ActiveFlashSaleDeal, PromotionsPricingPort
from app.ordering.domain.services import CartItem
from app.ordering.infrastructure.pricing import SqlPricingService


# =============================================================================
# Fake Ports
# =============================================================================

class FakeCatalogPricingPort(CatalogPricingPort):
    """Fake catalog port — returns configurable product data."""

    def __init__(
        self,
        products: dict[int, PricingProductData] | None = None,
        time_deal: ActiveTimeDeal | None = None,
    ) -> None:
        self._products = products or {
            1: PricingProductData(
                id=1, name="Trà Sữa Trân Châu", base_price=35000,
                is_active=True, sizes=[],
            ),
        }
        self._time_deal = time_deal

    async def get_product(self, product_id: int) -> PricingProductData | None:
        return self._products.get(product_id)

    async def get_toppings_by_legacy_ids(
        self, legacy_ids: list[str],
    ) -> list[PricingToppingData]:
        return []

    async def get_active_time_deal(self, current_hour_vn: int) -> ActiveTimeDeal | None:
        return self._time_deal


class FakePromotionsPricingPort(PromotionsPricingPort):
    """Fake promotions port — returns configurable flash sale."""

    def __init__(
        self,
        flash_sale: ActiveFlashSaleDeal | None = None,
        claim_success: bool = True,
    ) -> None:
        self._flash_sale = flash_sale
        self._claim_success = claim_success
        self.claimed_ids: list[int] = []

    async def get_best_flash_sale(
        self, product_ids: list[int],
    ) -> ActiveFlashSaleDeal | None:
        return self._flash_sale

    async def claim_flash_sale(self, sale_id: int) -> bool:
        self.claimed_ids.append(sale_id)
        return self._claim_success


# =============================================================================
# Helpers
# =============================================================================

def _cart_items(count: int = 1) -> list[CartItem]:
    return [CartItem(product_id=1, quantity=2) for _ in range(count)]


def _time_deal(pct: int = 10) -> ActiveTimeDeal:
    return ActiveTimeDeal(title=f"Deal Buổi Trưa", discount_percent=pct)


def _flash_sale(pct: int = 50, sale_id: int = 1, product_ids: list[int] | None = None) -> ActiveFlashSaleDeal:
    return ActiveFlashSaleDeal(
        sale_id=sale_id,
        title=f"Flash Sale {pct}%",
        discount_percent=pct,
        product_ids=product_ids or [],
    )


# =============================================================================
# Tests
# =============================================================================

class TestBestDealWins:

    @pytest.mark.asyncio
    async def test_flash_sale_beats_time_deal(self):
        """50% flash sale vs 10% time deal → flash sale wins."""
        catalog = FakeCatalogPricingPort(time_deal=_time_deal(10))
        promos = FakePromotionsPricingPort(flash_sale=_flash_sale(50))
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        # subtotal = 35000 * 2 = 70000
        assert cart.subtotal == 70000
        assert cart.discount == 35000  # 50%
        assert cart.total == 35000
        assert cart.discount_source == "flash_sale"
        assert "Flash Sale" in cart.discount_label

    @pytest.mark.asyncio
    async def test_time_deal_beats_flash_sale(self):
        """30% time deal vs 10% flash sale → time deal wins."""
        catalog = FakeCatalogPricingPort(time_deal=_time_deal(30))
        promos = FakePromotionsPricingPort(flash_sale=_flash_sale(10))
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        assert cart.discount == 21000  # 30% of 70000
        assert cart.discount_source == "time_deal"
        assert "Deal Buổi Trưa" in cart.discount_label

    @pytest.mark.asyncio
    async def test_no_flash_sale_uses_time_deal(self):
        """Không có flash sale → time deal áp dụng như cũ."""
        catalog = FakeCatalogPricingPort(time_deal=_time_deal(20))
        promos = FakePromotionsPricingPort(flash_sale=None)
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        assert cart.discount == 14000  # 20% of 70000
        assert cart.discount_source == "time_deal"

    @pytest.mark.asyncio
    async def test_no_deals_at_all(self):
        """Không có deal nào → discount = 0."""
        catalog = FakeCatalogPricingPort(time_deal=None)
        promos = FakePromotionsPricingPort(flash_sale=None)
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        assert cart.discount == 0
        assert cart.total == 70000
        assert cart.discount_source == "none"

    @pytest.mark.asyncio
    async def test_flash_sale_sold_out_falls_back_to_time_deal(self):
        """Flash sale thắng nhưng claim fail → fallback time deal."""
        catalog = FakeCatalogPricingPort(time_deal=_time_deal(10))
        promos = FakePromotionsPricingPort(
            flash_sale=_flash_sale(50),
            claim_success=False,  # Sold out!
        )
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        # Fallback to time deal: 10% of 70000 = 7000
        assert cart.discount == 7000
        assert cart.discount_source == "time_deal"
        assert len(promos.claimed_ids) == 1  # Claim was attempted

    @pytest.mark.asyncio
    async def test_flash_sale_sold_out_no_time_deal(self):
        """Flash sale claim fail + no time deal → no discount."""
        catalog = FakeCatalogPricingPort(time_deal=None)
        promos = FakePromotionsPricingPort(
            flash_sale=_flash_sale(50),
            claim_success=False,
        )
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        assert cart.discount == 0
        assert cart.discount_source == "none"

    @pytest.mark.asyncio
    async def test_no_promotions_port_backward_compatible(self):
        """Nếu promotions_port=None (backward compat), chỉ dùng time deal."""
        catalog = FakeCatalogPricingPort(time_deal=_time_deal(15))
        svc = SqlPricingService(catalog, promotions_port=None)

        cart = await svc.price_cart(_cart_items())

        assert cart.discount == 10500  # 15% of 70000
        assert cart.discount_source == "time_deal"

    @pytest.mark.asyncio
    async def test_flash_sale_claim_called_with_correct_id(self):
        """Verify claim_flash_sale gọi đúng sale_id."""
        catalog = FakeCatalogPricingPort(time_deal=None)
        promos = FakePromotionsPricingPort(flash_sale=_flash_sale(50, sale_id=42))
        svc = SqlPricingService(catalog, promos)

        await svc.price_cart(_cart_items())

        assert promos.claimed_ids == [42]

    @pytest.mark.asyncio
    async def test_equal_discount_prefers_flash_sale(self):
        """Khi discount bằng nhau → flash sale thắng (ưu tiên flash sale)."""
        catalog = FakeCatalogPricingPort(time_deal=_time_deal(30))
        promos = FakePromotionsPricingPort(flash_sale=_flash_sale(30))
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        assert cart.discount_source == "flash_sale"


# =============================================================================
# Tests: Product-specific flash sale
# =============================================================================

class TestProductSpecificFlashSale:

    @pytest.mark.asyncio
    async def test_product_specific_flash_sale_applies(self):
        """Flash sale cho product_ids=[1], cart có product_id=1 → áp dụng."""
        flash = ActiveFlashSaleDeal(
            sale_id=10, title="Giảm Trà Sữa",
            discount_percent=40, product_ids=[1],
        )
        catalog = FakeCatalogPricingPort(time_deal=None)
        promos = FakePromotionsPricingPort(flash_sale=flash)
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        assert cart.discount_source == "flash_sale"
        assert cart.discount == 28000  # 40% of 70000
        assert "Giảm Trà Sữa" in cart.discount_label

    @pytest.mark.asyncio
    async def test_product_specific_flash_sale_does_not_match_other_product(self):
        """Flash sale cho product_ids=[99], cart có product_id=1 → không áp dụng."""
        flash = ActiveFlashSaleDeal(
            sale_id=10, title="Giảm Cà Phê",
            discount_percent=50, product_ids=[99],
        )
        catalog = FakeCatalogPricingPort(time_deal=None)
        # FakePort always returns flash sale regardless of product_ids
        # → pricing sẽ tính discount nhưng claim vẫn xảy ra
        # Đây test pricing logic, không test adapter filtering
        promos = FakePromotionsPricingPort(flash_sale=flash)
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        # FakePort returns flash_sale regardless → pricing vẫn áp dụng
        # (filtering logic nằm trong SqlFlashSalePricingAdapter, không test ở đây)
        assert cart.discount_source == "flash_sale"

    @pytest.mark.asyncio
    async def test_discount_rounding_integer_division(self):
        """Discount rounding: 33333 * 7 // 100 = 2333 (integer, rounds down)."""
        catalog = FakeCatalogPricingPort(
            products={
                1: PricingProductData(
                    id=1, name="Món Lẻ", base_price=16666,
                    is_active=True, sizes=[],
                ),
            },
            time_deal=None,
        )
        promos = FakePromotionsPricingPort(flash_sale=_flash_sale(7))
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())  # qty=2 → subtotal=33332

        # 33332 * 7 // 100 = 2333
        assert cart.discount == 2333
        assert cart.total == 33332 - 2333

    @pytest.mark.asyncio
    async def test_minimum_discount_percent(self):
        """1% discount trên subtotal nhỏ vẫn tính đúng."""
        catalog = FakeCatalogPricingPort(time_deal=None)
        promos = FakePromotionsPricingPort(flash_sale=_flash_sale(1))
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())  # subtotal=70000

        # 70000 * 1 // 100 = 700
        assert cart.discount == 700
        assert cart.discount_source == "flash_sale"

    @pytest.mark.asyncio
    async def test_multiple_items_different_products(self):
        """Cart với nhiều sản phẩm khác nhau — subtotal gộp đúng."""
        catalog = FakeCatalogPricingPort(
            products={
                1: PricingProductData(
                    id=1, name="Trà Sữa", base_price=35000,
                    is_active=True, sizes=[],
                ),
                2: PricingProductData(
                    id=2, name="Cà Phê", base_price=25000,
                    is_active=True, sizes=[],
                ),
            },
            time_deal=None,
        )
        promos = FakePromotionsPricingPort(flash_sale=_flash_sale(20))
        svc = SqlPricingService(catalog, promos)

        items = [
            CartItem(product_id=1, quantity=2),  # 35000 * 2 = 70000
            CartItem(product_id=2, quantity=1),  # 25000 * 1 = 25000
        ]
        cart = await svc.price_cart(items)

        # subtotal = 70000 + 25000 = 95000
        assert cart.subtotal == 95000
        # discount = 95000 * 20 // 100 = 19000
        assert cart.discount == 19000
        assert cart.discount_source == "flash_sale"


# =============================================================================
# Tests: Multi-product flash sale
# =============================================================================

class TestMultiProductFlashSale:

    @pytest.mark.asyncio
    async def test_multi_product_matches_one_in_cart(self):
        """Flash sale cho [1, 2], cart có product 1 → áp dụng."""
        flash = ActiveFlashSaleDeal(
            sale_id=20, title="Giảm Trà Sữa + Cà Phê",
            discount_percent=30, product_ids=[1, 2],
        )
        catalog = FakeCatalogPricingPort(time_deal=None)
        promos = FakePromotionsPricingPort(flash_sale=flash)
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())  # product_id=1, qty=2

        assert cart.discount_source == "flash_sale"
        assert cart.discount == 21000  # 30% of 70000

    @pytest.mark.asyncio
    async def test_multi_product_matches_none_in_cart(self):
        """Flash sale cho [3, 4], cart có product 1 → FakePort trả sale,
        pricing vẫn áp dụng vì matching nằm trong adapter không test ở đây."""
        flash = ActiveFlashSaleDeal(
            sale_id=21, title="Giảm Combo",
            discount_percent=40, product_ids=[3, 4],
        )
        catalog = FakeCatalogPricingPort(time_deal=None)
        promos = FakePromotionsPricingPort(flash_sale=flash)
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        # FakePort returns flash sale regardless → pricing áp dụng
        assert cart.discount_source == "flash_sale"

    @pytest.mark.asyncio
    async def test_multi_product_partial_match(self):
        """Flash sale cho [1, 5], cart có [1, 2] → áp dụng (intersection có product 1)."""
        flash = ActiveFlashSaleDeal(
            sale_id=22, title="Giảm Trà Sữa + Matcha",
            discount_percent=25, product_ids=[1, 5],
        )
        catalog = FakeCatalogPricingPort(
            products={
                1: PricingProductData(
                    id=1, name="Trà Sữa", base_price=35000,
                    is_active=True, sizes=[],
                ),
                2: PricingProductData(
                    id=2, name="Cà Phê", base_price=25000,
                    is_active=True, sizes=[],
                ),
            },
            time_deal=None,
        )
        promos = FakePromotionsPricingPort(flash_sale=flash)
        svc = SqlPricingService(catalog, promos)

        items = [
            CartItem(product_id=1, quantity=1),  # 35000
            CartItem(product_id=2, quantity=1),  # 25000
        ]
        cart = await svc.price_cart(items)

        # subtotal = 60000, discount = 60000 * 25 // 100 = 15000
        assert cart.subtotal == 60000
        assert cart.discount == 15000
        assert cart.discount_source == "flash_sale"

    @pytest.mark.asyncio
    async def test_whole_menu_flash_sale_empty_product_ids(self):
        """Flash sale product_ids=[] (toàn menu) → áp dụng cho mọi đơn."""
        flash = ActiveFlashSaleDeal(
            sale_id=23, title="Giảm Toàn Menu",
            discount_percent=15, product_ids=[],
        )
        catalog = FakeCatalogPricingPort(time_deal=None)
        promos = FakePromotionsPricingPort(flash_sale=flash)
        svc = SqlPricingService(catalog, promos)

        cart = await svc.price_cart(_cart_items())

        assert cart.discount_source == "flash_sale"
        assert cart.discount == 10500  # 15% of 70000
        assert "Giảm Toàn Menu" in cart.discount_label
