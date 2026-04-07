"""Add stores table and store_id to all tenant-scoped tables (SaaS foundation)

Revision ID: 005
Revises: 004
Create Date: 2025-03-17

WHY: Nền móng multi-tenant. Mỗi quán = 1 row trong stores.
Mọi bảng tenant-scoped có store_id FK → biết data thuộc quán nào.
Giai đoạn 1: default store_id = 1 (1 quán).
Giai đoạn 2: bật RLS policies.
"""

from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


# Tất cả bảng cần thêm store_id
TENANT_TABLES = [
    "categories",
    "products",
    "toppings",
    "time_deals",
    "cross_sell_items",
    "admin_users",
    "orders",
    "order_items",
    "customers",
    "feature_flags",
    "events",
    "reviews",
    "push_subscriptions",
    "loyalty_rewards",
    "referrals",
]


def upgrade() -> None:
    # 1. Tạo bảng stores
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("config", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. Insert default store TRƯỚC khi thêm FK
    op.execute(
        "INSERT INTO stores (id, slug, name, phone) "
        "VALUES (1, 'default', 'Ngon-Ngon', '0378148148')"
    )

    # 3. Thêm store_id vào mọi bảng tenant-scoped
    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("store_id", sa.Integer(), nullable=True))
        # Set default cho rows đã tồn tại
        op.execute(f"UPDATE {table} SET store_id = 1")
        # Set NOT NULL sau khi fill data
        op.alter_column(table, "store_id", nullable=False)
        # Thêm FK
        op.create_foreign_key(
            f"fk_{table}_store_id", table, "stores",
            ["store_id"], ["id"],
        )
        # Thêm index
        op.create_index(f"ix_{table}_store_id", table, ["store_id"])

    # 4. Drop unique constraint trên categories.slug (multi-tenant: 2 quán có thể cùng slug)
    # và tạo compound unique (store_id, slug) thay thế
    try:
        op.drop_constraint("categories_slug_key", "categories", type_="unique")
    except Exception:
        pass  # Constraint name có thể khác tùy DB
    op.create_index("ix_categories_store_slug", "categories", ["store_id", "slug"], unique=True)

    # 5. Composite indexes cho query phổ biến
    op.create_index("ix_orders_store_status_created", "orders", ["store_id", "status", "created_at"])
    op.create_index("ix_customers_store_phone", "customers", ["store_id", "phone"])


def downgrade() -> None:
    # Drop composite indexes
    op.drop_index("ix_customers_store_phone", "customers")
    op.drop_index("ix_orders_store_status_created", "orders")
    try:
        op.drop_index("ix_categories_store_slug", "categories")
    except Exception:
        pass

    # Remove store_id from all tables
    for table in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table}_store_id", table)
        op.drop_constraint(f"fk_{table}_store_id", table, type_="foreignkey")
        op.drop_column(table, "store_id")

    # Restore unique on categories.slug
    op.create_unique_constraint("categories_slug_key", "categories", ["slug"])

    # Drop stores table
    op.drop_table("stores")
