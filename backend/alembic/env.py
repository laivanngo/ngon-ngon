"""
Alembic Environment — Migration runtime configuration
=======================================================
WHY override sqlalchemy.url từ env var:
- alembic.ini có URL hardcode cho local dev
- Production đọc từ DATABASE_URL env var (set bởi Docker)
- Cùng 1 codebase chạy ở mọi môi trường

WHY import models ở đây:
- Alembic autogenerate cần biết tất cả models để so sánh với DB
- Nếu thiếu import → autogenerate sẽ không detect model mới
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database import Base

# Import tất cả ORM models theo context sở hữu
# → Alembic "thấy" toàn bộ tables khi autogenerate migration
# Shared
from app.shared.orm_models import Store, TimestampMixin, TenantMixin  # noqa: F401
# Catalog
from app.catalog.infrastructure.orm_models import (  # noqa: F401
    Category, Product, ProductSize, Topping, TimeDeal,
    ProductTopping, CrossSellItem, LayoutType,
)
# Ordering
from app.ordering.infrastructure.orm_models import (  # noqa: F401
    Order, OrderItem, OrderStatus,
)
# CRM
from app.crm.infrastructure.orm_models import (  # noqa: F401
    Customer, Event, Review,
    PushSubscription, LoyaltyReward, Referral,
    GrowthSetting,
)
# Promotions
from app.promotions.infrastructure.orm_models import FeatureFlag  # noqa: F401
# Identity
from app.identity.infrastructure.orm_models import AdminUser  # noqa: F401

config = context.config

# Override URL từ environment (production/Docker)
database_url = os.getenv("DATABASE_URL", "").replace(
    "postgresql+asyncpg://", "postgresql://"  # Alembic dùng sync driver
)
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Chạy migration ở chế độ offline (tạo SQL script, không connect DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Chạy migration online (connect thẳng vào DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
