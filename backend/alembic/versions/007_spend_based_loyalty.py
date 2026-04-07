"""Update growth_settings for spend-based loyalty model

Revision ID: 007
Revises: 006
Create Date: 2026-03-28

WHY: Chuyển từ stamp-based (1 đơn = 1 điểm) sang spend-based (1.000đ = N điểm).
- loyalty_threshold: 10 → 200 (200 điểm = ~200k chi tiêu)
- loyalty_reward_value: 25 → 20 (thưởng 20k — ~10% hoàn lại)
- Thêm loyalty_points_per_1000: rate tích điểm per 1k chi tiêu

Cập nhật description cho phù hợp mô hình mới.
"""

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cập nhật loyalty_threshold: 10 đơn → 200 điểm
    op.execute(
        """
        UPDATE growth_settings
        SET value = 200,
            label = 'Điểm đổi thưởng',
            description = 'Tích đủ bao nhiêu điểm thì được 1 phần thưởng (VD: 200 điểm ≈ 200k chi tiêu)',
            min_value = 50,
            max_value = 1000,
            unit = 'điểm'
        WHERE key = 'loyalty_threshold'
        """
    )

    # Cập nhật loyalty_reward_value: 25k → 20k
    op.execute(
        """
        UPDATE growth_settings
        SET value = 20,
            description = 'Giá trị tối đa (nghìn đồng) của phần thưởng khi đổi điểm'
        WHERE key = 'loyalty_reward_value'
        """
    )

    # Thêm loyalty_points_per_1000: tỉ lệ tích điểm
    op.execute(
        """
        INSERT INTO growth_settings (key, value, label, description, min_value, max_value, unit, store_id)
        VALUES (
            'loyalty_points_per_1000', 1, 'Tỉ lệ tích điểm',
            'Bao nhiêu điểm cho mỗi 1.000đ chi tiêu (VD: 1 điểm → đơn 35k = 35 điểm)',
            1, 10, 'điểm/1k', 1
        )
        """
    )


def downgrade() -> None:
    # Xóa loyalty_points_per_1000
    op.execute("DELETE FROM growth_settings WHERE key = 'loyalty_points_per_1000'")

    # Revert loyalty_threshold
    op.execute(
        """
        UPDATE growth_settings
        SET value = 10,
            label = 'Số đơn tích điểm',
            description = 'Mua đủ bao nhiêu đơn thì được 1 phần thưởng',
            min_value = 3,
            max_value = 50,
            unit = 'đơn'
        WHERE key = 'loyalty_threshold'
        """
    )

    # Revert loyalty_reward_value
    op.execute(
        """
        UPDATE growth_settings
        SET value = 25,
            description = 'Giá trị tối đa (nghìn đồng) của phần thưởng loyalty'
        WHERE key = 'loyalty_reward_value'
        """
    )
