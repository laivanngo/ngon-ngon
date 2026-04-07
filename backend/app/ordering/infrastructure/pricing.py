"""
Ordering Context — SQL Pricing Service
=========================================
Implementation của PricingService ABC — tính giá giỏ hàng.

TRƯỚC: Import trực tiếp Product, TimeDeal, Topping ORM từ Catalog (vi phạm ranh giới).
SAU:   Dùng CatalogPricingPort (interface do Ordering định nghĩa).
       Catalog implement port, Ordering không biết ORM Catalog tồn tại.

NGUYÊN TẮC: Server-side pricing — không tin giá từ client.

Flash Sale integration:
    Tính cả time deal + flash sale → chọn deal tốt hơn cho khách.
    Nếu flash sale thắng nhưng claim fail → fallback về time deal.
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.ordering.domain.catalog_port import CatalogPricingPort
from app.ordering.domain.promotions_port import PromotionsPricingPort
from app.ordering.domain.services import CartItem, PricedCart, PricedLineItem, PricingService
from app.shared.exceptions import ValidationError

logger = logging.getLogger("ngonngon.ordering.pricing")


class SqlPricingService(PricingService):
    """
    Tính giá giỏ hàng bằng cách query Catalog qua CatalogPricingPort.

    TRƯỚC: Trực tiếp import Catalog ORM → coupling chặt.
    SAU:   Nhận CatalogPricingPort qua constructor → decoupled, testable.

    Flash Sale: Nhận thêm PromotionsPricingPort (optional) để query flash sale.
    Để test: inject FakeCatalogPricingPort + FakePromotionsPricingPort, không cần DB.
    """

    def __init__(
        self,
        catalog_port: CatalogPricingPort,
        promotions_port: PromotionsPricingPort | None = None,
    ) -> None:
        self._catalog = catalog_port
        self._promotions = promotions_port

    async def price_cart(self, items: list[CartItem]) -> PricedCart:
        """
        Tính giá toàn bộ giỏ hàng.

        Flow cho mỗi item:
        1. Lookup product qua CatalogPricingPort → check is_active
        2. Xác định unit_price (base_price hoặc size price)
        3. Validate size hợp lệ
        4. Lookup toppings → cộng giá (deduplicated)
        5. Snapshot product_name, toppings_text

        Sau đó:
        6. Tính subtotal = sum(all line totals)
        7. Check TimeDeal → tính discount
        8. Check Flash Sale → tính discount
        9. Chọn deal tốt hơn (best deal wins, no stacking)
        10. total = subtotal - discount
        """
        priced_items: list[PricedLineItem] = []
        subtotal = 0
        product_ids: list[int] = []

        for cart_item in items:
            priced = await self._price_single_item(cart_item)
            priced_items.append(priced)
            subtotal += priced.unit_price * priced.quantity
            product_ids.append(priced.product_id)

        # --- Tính cả hai loại discount ---
        time_deal_discount, time_deal_label = await self._calculate_time_deal_discount(subtotal)
        flash_sale_discount, flash_sale_label, flash_sale_id = (
            await self._calculate_flash_sale_discount(subtotal, product_ids)
        )

        # --- Best deal wins ---
        if flash_sale_discount > 0 and flash_sale_discount >= time_deal_discount:
            # Flash sale thắng → claim
            claimed = False
            if self._promotions and flash_sale_id:
                claimed = await self._promotions.claim_flash_sale(flash_sale_id)

            if claimed:
                discount = flash_sale_discount
                discount_source = "flash_sale"
                discount_label = flash_sale_label
            else:
                # Claim fail (hết lượt giữa chừng) → fallback time deal
                discount = time_deal_discount
                discount_source = "time_deal" if time_deal_discount > 0 else "none"
                discount_label = time_deal_label
        elif time_deal_discount > 0:
            discount = time_deal_discount
            discount_source = "time_deal"
            discount_label = time_deal_label
        else:
            discount = 0
            discount_source = "none"
            discount_label = ""

        return PricedCart(
            items=priced_items,
            subtotal=subtotal,
            discount=discount,
            total=subtotal - discount,
            discount_source=discount_source,
            discount_label=discount_label,
        )

    async def _price_single_item(self, cart_item: CartItem) -> PricedLineItem:
        """Tính giá 1 món trong giỏ hàng."""

        product = await self._catalog.get_product(cart_item.product_id)

        if not product or not product.is_active:
            raise ValidationError(
                f"Sản phẩm ID {cart_item.product_id} không tồn tại hoặc đã ngừng bán"
            )

        unit_price = product.base_price

        if cart_item.size and product.sizes:
            size_match = next(
                (s for s in product.sizes if s.label == cart_item.size), None
            )
            if not size_match:
                valid_sizes = [s.label for s in product.sizes]
                raise ValidationError(
                    f"Size '{cart_item.size}' không hợp lệ cho {product.name}. "
                    f"Sizes hợp lệ: {', '.join(valid_sizes)}"
                )
            unit_price = size_match.price
        elif product.sizes and not cart_item.size:
            unit_price = product.sizes[0].price

        topping_names: list[str] = []
        topping_total = 0

        if cart_item.toppings:
            unique_ids = list(dict.fromkeys(cart_item.toppings))
            toppings = await self._catalog.get_toppings_by_legacy_ids(unique_ids)
            for tp in toppings:
                topping_names.append(f"{tp.emoji} {tp.name}")
                topping_total += tp.price

        unit_price += topping_total

        return PricedLineItem(
            product_id=product.id,
            product_name=product.name,
            size=cart_item.size,
            sweetness=cart_item.sweetness,
            ice_level=cart_item.ice_level,
            quantity=cart_item.quantity,
            unit_price=unit_price,
            toppings_text=", ".join(topping_names) if topping_names else None,
            note=cart_item.note,
        )

    async def _calculate_time_deal_discount(
        self, subtotal: int,
    ) -> tuple[int, str]:
        """Check TimeDeal đang active → tính discount. Return (amount, label)."""
        try:
            current_hour = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).hour

            deal = await self._catalog.get_active_time_deal(current_hour)

            if deal:
                discount = subtotal * deal.discount_percent // 100
                label = f"{deal.title} -{deal.discount_percent}%"
                logger.info(
                    f"🏷️ Time Deal applied: {deal.title} "
                    f"(-{deal.discount_percent}% = -{discount}đ)"
                )
                return discount, label

        except Exception as e:
            logger.warning(f"Time Deal check failed (order still OK): {e}")

        return 0, ""

    async def _calculate_flash_sale_discount(
        self, subtotal: int, product_ids: list[int],
    ) -> tuple[int, str, int | None]:
        """Check Flash Sale đang active → tính discount. Return (amount, label, sale_id)."""
        if not self._promotions:
            return 0, "", None

        try:
            deal = await self._promotions.get_best_flash_sale(product_ids)

            if deal:
                discount = subtotal * deal.discount_percent // 100
                label = f"{deal.title} -{deal.discount_percent}%"
                logger.info(
                    f"⚡ Flash Sale found: {deal.title} "
                    f"(-{deal.discount_percent}% = -{discount}đ)"
                )
                return discount, label, deal.sale_id

        except Exception as e:
            logger.warning(f"Flash Sale check failed (order still OK): {e}")

        return 0, "", None
