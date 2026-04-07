"""Add growth_settings table — configurable business values from admin panel

Revision ID: 006
Revises: 005
Create Date: 2026-03-28

WHY: REFERRAL_DISCOUNT, LOYALTY_THRESHOLD, LOYALTY_REWARD_VALUE đang hardcode
trong value_objects.py. Chủ quán cần chỉnh từ admin panel mà không cần sửa code.

Bảng growth_settings lưu key-value + description + min/max để validate.
Seed 3 giá trị mặc định giữ nguyên từ value_objects.py gốc.
"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "growth_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(50), unique=True, nullable=False),
        sa.Column("value", sa.Integer, nullable=False),
        sa.Column("label", sa.String(100), nullable=False, server_default=""),
        sa.Column("description", sa.String(300), nullable=False, server_default=""),
        sa.Column("min_value", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_value", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        sa.Column(
            "store_id",
            sa.Integer,
            sa.ForeignKey("stores.id"),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Seed default values — giữ nguyên giá trị từ value_objects.py
    op.execute(
        """
        INSERT INTO growth_settings (key, value, label, description, min_value, max_value, unit, store_id)
        VALUES
            ('referral_discount', 5, 'Giảm giá giới thiệu',
             'Số tiền giảm (nghìn đồng) cho cả người giới thiệu và người được giới thiệu',
             0, 50, 'k', 1),
            ('loyalty_threshold', 10, 'Số đơn tích điểm',
             'Mua đủ bao nhiêu đơn thì được 1 phần thưởng',
             3, 50, 'đơn', 1),
            ('loyalty_reward_value', 25, 'Giá trị thưởng',
             'Giá trị tối đa (nghìn đồng) của phần thưởng loyalty',
             5, 100, 'k', 1)
        """
    )


def downgrade() -> None:
    op.drop_table("growth_settings")
