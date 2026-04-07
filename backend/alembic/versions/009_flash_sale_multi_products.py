"""Flash Sale multi-product support — junction table

Revision ID: 009
Revises: 008
Create Date: 2025-04-06

Chuyển từ product_id (1 sản phẩm hoặc NULL = toàn menu)
sang flash_sale_products junction table (nhiều sản phẩm, empty = toàn menu).

Steps:
1. Tạo flash_sale_products junction table
2. Migrate existing product_id data → junction table
3. Drop cột product_id cũ trên flash_sales
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: str = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tạo junction table flash_sale_products
    op.create_table(
        "flash_sale_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "flash_sale_id",
            sa.Integer(),
            sa.ForeignKey("flash_sales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_flash_sale_products_sale",
        "flash_sale_products",
        ["flash_sale_id"],
    )

    # 2. Migrate existing data: flash_sales.product_id → junction rows
    op.execute(
        """
        INSERT INTO flash_sale_products (flash_sale_id, product_id)
        SELECT id, product_id FROM flash_sales WHERE product_id IS NOT NULL
        """
    )

    # 3. Drop cột product_id cũ
    op.drop_column("flash_sales", "product_id")


def downgrade() -> None:
    # 1. Thêm lại cột product_id
    op.add_column(
        "flash_sales",
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 2. Migrate data ngược: lấy 1 product_id đầu tiên từ junction
    op.execute(
        """
        UPDATE flash_sales SET product_id = fsp.product_id
        FROM (
            SELECT DISTINCT ON (flash_sale_id) flash_sale_id, product_id
            FROM flash_sale_products
            ORDER BY flash_sale_id, id
        ) fsp
        WHERE flash_sales.id = fsp.flash_sale_id
        """
    )

    # 3. Drop junction table
    op.drop_index("ix_flash_sale_products_sale", table_name="flash_sale_products")
    op.drop_table("flash_sale_products")
