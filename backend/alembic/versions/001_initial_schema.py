"""Initial schema — all tables

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

WHY hand-written thay vì autogenerate:
- Migration đầu tiên cần chính xác 100%, autogenerate hay miss index/constraint
- Sau migration này, dùng `alembic revision --autogenerate` cho các thay đổi tiếp theo
- Có cả upgrade() VÀ downgrade() → rollback được nếu cần
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Categories ---
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("emoji", sa.String(10), server_default="📦"),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("layout", sa.Enum("grid", "list", "combo", name="layouttype"), server_default="list"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Products ---
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("legacy_id", sa.String(20), unique=True, nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_price", sa.Integer(), nullable=False),
        sa.Column("emoji", sa.String(10), server_default="🍽"),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("badge", sa.String(20), nullable=True),
        sa.Column("bg_class", sa.String(10), server_default="x"),
        sa.Column("sold_count", sa.Integer(), server_default="0"),
        sa.Column("is_drink", sa.Boolean(), server_default="true"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("is_combo", sa.Boolean(), server_default="false"),
        sa.Column("combo_description", sa.Text(), nullable=True),
        sa.Column("original_price", sa.Integer(), nullable=True),
        sa.Column("save_amount", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # WHY composite index: "lấy sản phẩm active theo category" là query #1
    op.create_index("ix_products_category_active", "products", ["category_id", "is_active"])

    # --- Product Sizes ---
    op.create_table(
        "product_sizes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("label", sa.String(10), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
    )

    # --- Toppings ---
    op.create_table(
        "toppings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("legacy_id", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("emoji", sa.String(10), server_default="🍡"),
        sa.Column("price", sa.Integer(), server_default="5"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Time Deals ---
    op.create_table(
        "time_deals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subtitle", sa.String(200), server_default=""),
        sa.Column("start_hour", sa.Integer(), nullable=False),
        sa.Column("end_hour", sa.Integer(), nullable=False),
        sa.Column("discount_percent", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Admin Users ---
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Orders ---
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), unique=True, nullable=False),
        sa.Column("customer_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(15), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("discount", sa.Integer(), server_default="0"),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum(
            "pending", "confirmed", "preparing", "delivering", "done", "cancelled",
            name="orderstatus",
        ), server_default="pending", nullable=False),
        sa.Column("zalo_sent", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # WHY index: admin filter "đơn pending hôm nay" là thao tác phổ biến nhất
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"])

    # --- Order Items ---
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("size", sa.String(10), nullable=True),
        sa.Column("sweetness", sa.String(20), nullable=True),
        sa.Column("ice_level", sa.String(20), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("toppings_text", sa.String(500), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Rollback: xóa tất cả bảng theo thứ tự ngược (tránh FK constraint)."""
    op.drop_table("order_items")
    op.drop_index("ix_orders_status_created", table_name="orders")
    op.drop_table("orders")
    op.drop_table("admin_users")
    op.drop_table("time_deals")
    op.drop_table("toppings")
    op.drop_table("product_sizes")
    op.drop_index("ix_products_category_active", table_name="products")
    op.drop_table("products")
    op.drop_table("categories")
    # Clean up enum types
    op.execute("DROP TYPE IF EXISTS orderstatus")
    op.execute("DROP TYPE IF EXISTS layouttype")
