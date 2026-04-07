"""Product-specific toppings + configurable cross-sell

Revision ID: 003
Revises: 002
Create Date: 2025-03-15

2 bảng mới:
- product_toppings: junction table cho phép gắn topping cụ thể vào từng sản phẩm
- cross_sell_items: admin cấu hình món trong "Thêm cho đủ bữa?" thay vì hardcode
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: str = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- product_toppings junction table ---
    op.create_table(
        "product_toppings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topping_id", sa.Integer(), sa.ForeignKey("toppings.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_product_toppings_product", "product_toppings", ["product_id"])

    # --- cross_sell_items table ---
    op.create_table(
        "cross_sell_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False, unique=True),
        sa.Column("target", sa.String(20), server_default="both"),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_table("cross_sell_items")
    op.drop_index("ix_product_toppings_product", table_name="product_toppings")
    op.drop_table("product_toppings")
