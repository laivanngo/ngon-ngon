"""Add flash_sales table for time-limited promotions

Revision ID: 008
Revises: 007
Create Date: 2026-04-06

WHY: Flash Sale — chương trình giảm giá giới hạn thời gian + số lượng.
Admin tạo flash sale (VD: "Giảm 50% từ 14h-16h, chỉ 20 đơn đầu").
Backend tự áp dụng discount khi checkout, chống oversell bằng atomic SQL.
"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flash_sales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subtitle", sa.String(300), nullable=True),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("max_quantity", sa.Integer(), nullable=False),
        sa.Column("claimed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="scheduled", nullable=False),
        sa.Column(
            "store_id",
            sa.Integer(),
            sa.ForeignKey("stores.id"),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Index cho query active flash sales hiệu quả
    op.create_index(
        "ix_flash_sales_status_time",
        "flash_sales",
        ["status", "starts_at", "ends_at"],
    )

    # Thêm feature flag cho flash_sale
    op.execute(
        """
        INSERT INTO feature_flags (key, enabled, description, store_id)
        VALUES ('flash_sale', false, 'Bật/tắt tính năng Flash Sale', 1)
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM feature_flags WHERE key = 'flash_sale'")
    op.drop_index("ix_flash_sales_status_time", table_name="flash_sales")
    op.drop_table("flash_sales")
