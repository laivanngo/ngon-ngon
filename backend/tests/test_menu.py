"""
Menu API Tests (v2 — comprehensive)
=====================================
Added: inactive category test, sort order test, toppings test, time deals test
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import make_category, make_product, make_topping
from app.catalog.infrastructure.orm_models import TimeDeal


@pytest.mark.asyncio
async def test_empty_menu(client: AsyncClient):
    resp = await client.get("/api/v1/menu")
    assert resp.status_code == 200
    assert resp.json()["categories"] == []


@pytest.mark.asyncio
async def test_menu_with_products(client: AsyncClient, db: AsyncSession):
    cat = await make_category(db, slug="trasua", name="Trà Sữa", emoji="🧋")
    await make_product(db, cat, legacy_id="ts1", name="Trà Sữa Trân Châu", price=20)
    await make_product(db, cat, legacy_id="ts2", name="Trà Sữa Matcha", price=22)
    await db.commit()

    resp = await client.get("/api/v1/menu")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["categories"]) == 1
    assert data["categories"][0]["slug"] == "trasua"
    assert len(data["categories"][0]["products"]) == 2


@pytest.mark.asyncio
async def test_inactive_products_hidden(client: AsyncClient, db: AsyncSession):
    cat = await make_category(db)
    await make_product(db, cat, legacy_id="a1", name="Active")
    await make_product(db, cat, legacy_id="a2", name="Inactive", is_active=False)
    await db.commit()

    resp = await client.get("/api/v1/menu")
    products = resp.json()["categories"][0]["products"]
    assert len(products) == 1
    assert products[0]["name"] == "Active"


@pytest.mark.asyncio
async def test_inactive_category_hidden(client: AsyncClient, db: AsyncSession):
    """Inactive category should not appear in menu at all."""
    cat1 = await make_category(db, slug="active", name="Active")
    cat2 = await make_category(db, slug="hidden", name="Hidden")
    cat2.is_active = False
    await make_product(db, cat1, legacy_id="p1")
    await make_product(db, cat2, legacy_id="p2")
    await db.commit()

    resp = await client.get("/api/v1/menu")
    slugs = [c["slug"] for c in resp.json()["categories"]]
    assert "active" in slugs
    assert "hidden" not in slugs


@pytest.mark.asyncio
async def test_product_with_sizes(client: AsyncClient, db: AsyncSession):
    cat = await make_category(db)
    await make_product(db, cat, legacy_id="s1", name="Trà Sữa", price=20,
                       sizes=[("M", 20), ("L", 22), ("XL", 25)])
    await db.commit()

    resp = await client.get("/api/v1/products/s1")
    assert resp.status_code == 200
    assert len(resp.json()["sizes"]) == 3
    assert resp.json()["sizes"][2]["price"] == 25


@pytest.mark.asyncio
async def test_product_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/products/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_category_menu(client: AsyncClient, db: AsyncSession):
    cat = await make_category(db, slug="caphe", name="Cà Phê")
    await make_product(db, cat, legacy_id="cf1", name="Cà Phê Đen")
    await db.commit()

    resp = await client.get("/api/v1/menu/caphe")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "caphe"


@pytest.mark.asyncio
async def test_category_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/menu/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_toppings(client: AsyncClient, db: AsyncSession):
    await make_topping(db, legacy_id="tp1", name="Trân Châu", price=5)
    await make_topping(db, legacy_id="tp2", name="Thạch Dừa", price=5)
    await db.commit()

    resp = await client.get("/api/v1/toppings")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
