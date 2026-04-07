"""Growth features — customers, feature flags, events, reviews, referrals, push

Revision ID: 002
Revises: 001
Create Date: 2025-01-15

9 tính năng cần 6 bảng mới + 3 cột mới trên orders.
Tất cả optional — app chạy bình thường nếu bảng trống.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: str = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Feature Flags ---
    # Bật/tắt từng tính năng từ admin panel
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(50), unique=True, nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false"),
        sa.Column("description", sa.String(200), server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Seed default flags
    op.execute("""
        INSERT INTO feature_flags (key, enabled, description) VALUES
        ('upsell', true, 'Gợi ý thêm topping/size lớn khi chọn món'),
        ('reorder', true, 'Nút đặt lại đơn trước trên trang chủ'),
        ('cross_sell', true, 'Gợi ý mua kèm trong giỏ hàng'),
        ('estimated_time', true, 'Hiện thời gian giao ước tính'),
        ('loyalty', true, 'Chương trình tích điểm mua 10 tặng 1'),
        ('analytics', true, 'Dashboard phân tích cho chủ quán'),
        ('reviews', true, 'Đánh giá sau khi nhận hàng'),
        ('push_notifications', false, 'Push notification cho deal giờ vàng'),
        ('referral', true, 'Giới thiệu bạn bè được giảm giá')
    """)

    # --- Customers ---
    # Theo dõi khách qua SĐT (không cần đăng ký)
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(15), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=True),  # Lấy từ đơn gần nhất
        sa.Column("order_count", sa.Integer(), server_default="0"),
        sa.Column("total_spent", sa.Integer(), server_default="0"),  # Tổng chi tiêu (nghìn)
        sa.Column("loyalty_points", sa.Integer(), server_default="0"),  # Điểm tích lũy
        sa.Column("referral_code", sa.String(10), unique=True, nullable=True),
        sa.Column("referred_by", sa.String(10), nullable=True),  # referral_code của người giới thiệu
        sa.Column("first_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customers_phone", "customers", ["phone"])

    # --- Events ---
    # Generic event log cho tracking hiệu quả mỗi tính năng
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),  # upsell_shown, reorder_clicked...
        sa.Column("feature", sa.String(30), nullable=False),     # upsell, reorder, cross_sell...
        sa.Column("data", sa.Text(), nullable=True),             # JSON metadata
        sa.Column("phone", sa.String(15), nullable=True),        # Khách nào
        sa.Column("order_id", sa.Integer(), nullable=True),      # Đơn nào (nếu có)
        sa.Column("value", sa.Integer(), server_default="0"),    # Giá trị (VD: thêm 5k topping)
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_events_feature_type", "events", ["feature", "event_type"])
    op.create_index("ix_events_created", "events", ["created_at"])

    # --- Reviews ---
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("phone", sa.String(15), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),  # 1-5
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Push Subscriptions ---
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("endpoint", sa.Text(), unique=True, nullable=False),
        sa.Column("keys_json", sa.Text(), nullable=False),  # p256dh + auth
        sa.Column("phone", sa.String(15), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Loyalty Rewards ---
    # Lịch sử đổi thưởng (mua 10 tặng 1)
    op.create_table(
        "loyalty_rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("reward_type", sa.String(50), server_default="free_drink"),
        sa.Column("points_used", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Referrals ---
    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referrer_phone", sa.String(15), nullable=False),
        sa.Column("referred_phone", sa.String(15), nullable=False),
        sa.Column("referrer_discount_used", sa.Boolean(), server_default="false"),
        sa.Column("referred_discount_used", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Add columns to orders ---
    op.add_column("orders", sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True))
    op.add_column("orders", sa.Column("estimated_minutes", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "completed_at")
    op.drop_column("orders", "estimated_minutes")
    op.drop_column("orders", "customer_id")
    op.drop_table("referrals")
    op.drop_table("loyalty_rewards")
    op.drop_table("push_subscriptions")
    op.drop_table("reviews")
    op.drop_index("ix_events_created", table_name="events")
    op.drop_index("ix_events_feature_type", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_table("customers")
    op.drop_table("feature_flags")
