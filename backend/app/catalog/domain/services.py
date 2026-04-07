"""
Catalog Domain — Services
===========================
Domain services = logic thuộc về domain nhưng không thuộc entity nào cụ thể.
- CrossSellService: logic gợi ý sản phẩm
- TimeDealService: logic deal theo giờ (dùng bởi cả Catalog lẫn Ordering context)
"""

from app.catalog.domain.entities import CrossSellItem, Product


class CrossSellService:
    """
    Logic phân loại cross-sell items thành 2 nhóm: drink và snack.
    Frontend gọi → nhận 2 list → hiển thị gợi ý theo giỏ hàng.
    """

    @staticmethod
    def build_config(items: list[CrossSellItem]) -> dict:
        """
        Từ list CrossSellItem (đã có product populated) → tạo config cho frontend.
        Format giữ nguyên API contract cũ.
        """
        drink_items = []
        snack_items = []

        for cs in items:
            if not cs.product or not cs.product.is_active:
                continue
            entry = {
                "id": cs.product.legacy_id,
                "n": cs.product.name,
                "p": cs.product.base_price,
                "e": cs.product.emoji,
            }
            if cs.target in ("drink", "both"):
                drink_items.append(entry)
            if cs.target in ("snack", "both"):
                snack_items.append(entry)

        return {"drink": drink_items, "snack": snack_items}
