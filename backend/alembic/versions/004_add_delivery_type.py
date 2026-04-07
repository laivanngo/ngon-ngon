"""Add delivery_type and scheduled_time to orders

Revision ID: 004
Revises: 003
Create Date: 2025-03-16

WHY: Cho phép khách chọn "Giao liền" hoặc "Hẹn giờ giao" khi đặt hàng.
Barista nhìn KDS thấy ngay cần giao ngay hay chờ → không cần gọi hỏi khách.
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "delivery_type",
            sa.String(20),
            nullable=False,
            server_default="immediate",
            comment="immediate = giao liền, scheduled = hẹn giờ",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "scheduled_time",
            sa.String(10),
            nullable=True,
            comment="Giờ hẹn giao, VD: 12:00, 14:30. Chỉ có giá trị khi delivery_type=scheduled",
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "scheduled_time")
    op.drop_column("orders", "delivery_type")
