"""
Catalog Domain — Events
=========================
Events mà Catalog context phát ra khi có thay đổi.
Subscribers (VD: frontend cache invalidation via WS) lắng nghe events này.
"""

from dataclasses import dataclass

from app.shared.events import DomainEvent


@dataclass
class MenuChanged(DomainEvent):
    """
    Phát ra khi bất kỳ thay đổi nào ảnh hưởng đến menu:
    - Product CRUD
    - Category CRUD
    - Topping CRUD
    - Cross-sell CRUD

    Subscriber: WS broadcast để frontend invalidate cache.
    """
    changed_by: str = "system"
    change_type: str = ""  # "product_created", "category_updated", etc.


@dataclass
class ProductCreated(DomainEvent):
    product_id: int = 0
    product_name: str = ""


@dataclass
class ProductUpdated(DomainEvent):
    product_id: int = 0
    product_name: str = ""
