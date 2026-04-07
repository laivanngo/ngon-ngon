"""
Test Configuration (v2 — comprehensive)
=========================================
FIXES FROM v1:
- Added aiosqlite for SQLite async support (was missing → tests crash)
- Added note about PostgreSQL-specific tests needed for ENUM
- Factory helpers now store _all_ required fields
- Added admin auth helper for testing protected endpoints
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import event

from app.database import Base, get_db
from app.main import create_app
from app.catalog.infrastructure.orm_models import Category, Product, ProductSize, Topping, LayoutType
from app.ordering.infrastructure.orm_models import Order, OrderItem
from app.identity.infrastructure.orm_models import AdminUser
from app.identity.infrastructure.auth import create_access_token, hash_password


# WHY SQLite for unit tests: fast, no setup, runs in CI without PG
# CAVEAT: SQLite has no ENUM type → OrderStatus tests may differ
# Run `make test-pg` for PostgreSQL-specific tests before deploy
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)

# WHY: SQLite doesn't enforce FK by default. This enables it.
@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    # Create all tables fresh for each test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        yield session

    # Drop all tables after test (clean slate)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# =============================================================================
# Factory Helpers
# =============================================================================

async def make_category(db, slug="test", name="Test Category", emoji="🧪", layout=LayoutType.LIST):
    cat = Category(slug=slug, name=name, emoji=emoji, layout=layout, sort_order=0)
    db.add(cat)
    await db.flush()
    return cat


async def make_product(db, category, legacy_id="t1", name="Test Product", price=20,
                       is_drink=True, is_active=True, sizes=None):
    product = Product(
        legacy_id=legacy_id, category_id=category.id, name=name,
        base_price=price, is_drink=is_drink, is_active=is_active, sort_order=0,
    )
    db.add(product)
    await db.flush()
    if sizes:
        for label, sz_price in sizes:
            db.add(ProductSize(product_id=product.id, label=label, price=sz_price))
        await db.flush()
    return product


async def make_topping(db, legacy_id="tp1", name="Trân Châu", price=5):
    tp = Topping(legacy_id=legacy_id, name=name, price=price)
    db.add(tp)
    await db.flush()
    return tp


async def make_admin(db, username="admin", password="testpass123"):
    admin = AdminUser(username=username, hashed_password=hash_password(password))
    db.add(admin)
    await db.flush()
    return admin


async def get_admin_token(client, db, username="admin", password="secret123"):
    """Create admin + login → return JWT token for authenticated requests."""
    await make_admin(db, username=username, password=password)
    await db.commit()
    resp = await client.post("/api/v1/admin/login", json={
        "username": username, "password": password,
    })
    return resp.json()["access_token"]


async def make_order(client, db, product_id, name="Test", phone="0901234567", addr="Test Addr"):
    """Create a simple order through the API."""
    resp = await client.post("/api/v1/orders", json={
        "customer_name": name, "phone": phone, "address": addr,
        "items": [{"product_id": product_id, "quantity": 1}],
    })
    return resp.json()
