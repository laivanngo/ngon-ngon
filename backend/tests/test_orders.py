"""
Order + Admin API Tests (v2 — comprehensive)
==============================================
FIXES FROM v1:
- Added edge cases: deactivated product, single-size product, unicode input
- Added ALL admin endpoint tests (v1 had zero)
- Added status transition tests including relaxed skip-step transitions
- Added XSS sanitization test
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import (
    make_category, make_product, make_topping, make_admin,
    get_admin_token, make_order,
)


# =============================================================================
# ORDER CREATION
# =============================================================================

@pytest.mark.asyncio
async def test_create_order_success(client: AsyncClient, db: AsyncSession):
    cat = await make_category(db)
    product = await make_product(db, cat, legacy_id="ts1", name="Trà Sữa", price=20)
    await db.commit()

    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Anh Minh",
        "phone": "0378148148",
        "address": "Cty Pouchen - Cổng B",
        "items": [{"product_id": product.id, "quantity": 2}],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["customer_name"] == "Anh Minh"
    assert data["total"] == 40
    assert data["status"] == "pending"
    assert len(data["public_id"]) == 36


@pytest.mark.asyncio
async def test_order_price_from_size(client: AsyncClient, db: AsyncSession):
    cat = await make_category(db)
    p = await make_product(db, cat, legacy_id="ts1", price=20,
                           sizes=[("M", 20), ("L", 22), ("XL", 25)])
    await db.commit()

    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Test", "phone": "0901234567", "address": "Test",
        "items": [{"product_id": p.id, "size": "XL", "quantity": 1}],
    })
    assert resp.status_code == 201
    assert resp.json()["total"] == 25


@pytest.mark.asyncio
async def test_order_single_size_no_selection(client: AsyncClient, db: AsyncSession):
    """Edge case: product has 1 size, client sends empty size → use base_price."""
    cat = await make_category(db)
    p = await make_product(db, cat, legacy_id="ts1", price=20, sizes=[("L", 22)])
    await db.commit()

    # Client sends size="" (UI hides size section when only 1 size)
    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Test", "phone": "0901234567", "address": "Test",
        "items": [{"product_id": p.id, "size": "", "quantity": 1}],
    })
    assert resp.status_code == 201
    # Empty size doesn't match "L" → falls back to base_price 20
    assert resp.json()["total"] == 20


@pytest.mark.asyncio
async def test_order_with_toppings(client: AsyncClient, db: AsyncSession):
    cat = await make_category(db)
    p = await make_product(db, cat, legacy_id="ts1", price=20)
    await make_topping(db, legacy_id="tp1", name="Trân Châu", price=5)
    await make_topping(db, legacy_id="tp2", name="Thạch Dừa", price=5)
    await db.commit()

    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Test", "phone": "0901234567", "address": "Test",
        "items": [{"product_id": p.id, "quantity": 1, "toppings": ["tp1", "tp2"]}],
    })
    assert resp.status_code == 201
    assert resp.json()["total"] == 30


@pytest.mark.asyncio
async def test_order_invalid_phone(client: AsyncClient, db: AsyncSession):
    cat = await make_category(db)
    p = await make_product(db, cat)
    await db.commit()

    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Test", "phone": "12345", "address": "Test",
        "items": [{"product_id": p.id, "quantity": 1}],
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_order_phone_with_dots(client: AsyncClient, db: AsyncSession):
    """Phone like 0378.148.148 should be cleaned and accepted."""
    cat = await make_category(db)
    p = await make_product(db, cat)
    await db.commit()

    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Test", "phone": "0378.148.148", "address": "Test",
        "items": [{"product_id": p.id, "quantity": 1}],
    })
    assert resp.status_code == 201
    assert resp.json()["phone"] == "0378148148"


@pytest.mark.asyncio
async def test_order_empty_cart(client: AsyncClient):
    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Test", "phone": "0901234567", "address": "Test",
        "items": [],
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_order_nonexistent_product(client: AsyncClient):
    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Test", "phone": "0901234567", "address": "Test",
        "items": [{"product_id": 99999, "quantity": 1}],
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_order_deactivated_product(client: AsyncClient, db: AsyncSession):
    """Product deactivated between cart add and checkout → reject."""
    cat = await make_category(db)
    p = await make_product(db, cat, is_active=False)
    await db.commit()

    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Test", "phone": "0901234567", "address": "Test",
        "items": [{"product_id": p.id, "quantity": 1}],
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_order_unicode_name(client: AsyncClient, db: AsyncSession):
    """Vietnamese names with diacritics should work."""
    cat = await make_category(db)
    p = await make_product(db, cat)
    await db.commit()

    resp = await client.post("/api/v1/orders", json={
        "customer_name": "Nguyễn Thị Hương", "phone": "0901234567",
        "address": "Công ty TNHH Việt Phát — Cổng B",
        "items": [{"product_id": p.id, "quantity": 1}],
    })
    assert resp.status_code == 201
    assert "Nguyễn" in resp.json()["customer_name"]


@pytest.mark.asyncio
async def test_order_xss_sanitization(client: AsyncClient, db: AsyncSession):
    """HTML in user input should be stripped/escaped."""
    cat = await make_category(db)
    p = await make_product(db, cat)
    await db.commit()

    resp = await client.post("/api/v1/orders", json={
        "customer_name": '<script>alert("xss")</script>Minh',
        "phone": "0901234567",
        "address": "Test<img onerror=alert(1)>",
        "items": [{"product_id": p.id, "quantity": 1}],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "<script>" not in data["customer_name"]
    assert "<img" not in data["address"]


@pytest.mark.asyncio
async def test_lookup_order(client: AsyncClient, db: AsyncSession):
    cat = await make_category(db)
    p = await make_product(db, cat, legacy_id="ts1", price=15)
    await db.commit()

    create_resp = await client.post("/api/v1/orders", json={
        "customer_name": "Chị Hương", "phone": "0901234567", "address": "VP Tầng 3",
        "items": [{"product_id": p.id, "quantity": 1}],
    })
    public_id = create_resp.json()["public_id"]

    lookup_resp = await client.get(f"/api/v1/orders/{public_id}")
    assert lookup_resp.status_code == 200
    assert lookup_resp.json()["customer_name"] == "Chị Hương"


@pytest.mark.asyncio
async def test_lookup_nonexistent_order(client: AsyncClient):
    resp = await client.get("/api/v1/orders/nonexistent-uuid")
    assert resp.status_code == 404


# =============================================================================
# ADMIN AUTH
# =============================================================================

@pytest.mark.asyncio
async def test_admin_login(client: AsyncClient, db: AsyncSession):
    await make_admin(db, username="admin", password="secret123")
    await db.commit()

    resp = await client.post("/api/v1/admin/login", json={
        "username": "admin", "password": "secret123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_admin_login_wrong_password(client: AsyncClient, db: AsyncSession):
    await make_admin(db, username="admin", password="correct")
    await db.commit()

    resp = await client.post("/api/v1/admin/login", json={
        "username": "admin", "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_generic_error_message(client: AsyncClient, db: AsyncSession):
    """Error message should NOT reveal whether username or password is wrong."""
    resp = await client.post("/api/v1/admin/login", json={
        "username": "nonexistent", "password": "anything",
    })
    assert resp.status_code == 401
    assert "tên đăng nhập hoặc mật khẩu" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_unauthorized_access(client: AsyncClient):
    resp = await client.get("/api/v1/admin/orders")
    assert resp.status_code == 401


# =============================================================================
# ADMIN DASHBOARD
# =============================================================================

@pytest.mark.asyncio
async def test_admin_dashboard(client: AsyncClient, db: AsyncSession):
    token = await get_admin_token(client, db)

    resp = await client.get("/api/v1/admin/dashboard",
                            headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "orders_today" in data
    assert "revenue_today" in data
    assert "pending_orders" in data
    assert "active_products" in data


# =============================================================================
# ADMIN ORDER MANAGEMENT
# =============================================================================

@pytest.mark.asyncio
async def test_admin_list_orders(client: AsyncClient, db: AsyncSession):
    token = await get_admin_token(client, db)
    cat = await make_category(db, slug="cat1")
    p = await make_product(db, cat, legacy_id="p1")
    await db.commit()
    await make_order(client, db, p.id)

    resp = await client.get("/api/v1/admin/orders",
                            headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_admin_update_order_status(client: AsyncClient, db: AsyncSession):
    token = await get_admin_token(client, db)
    cat = await make_category(db, slug="cat1")
    p = await make_product(db, cat, legacy_id="p1")
    await db.commit()
    order = await make_order(client, db, p.id)

    resp = await client.patch(
        f"/api/v1/admin/orders/{order['public_id']}/status",
        json={"status": "confirmed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "confirmed"


@pytest.mark.asyncio
async def test_admin_skip_step_transition(client: AsyncClient, db: AsyncSession):
    """v2 FIX: allow skipping steps (pending → delivering directly)."""
    token = await get_admin_token(client, db)
    cat = await make_category(db, slug="cat1")
    p = await make_product(db, cat, legacy_id="p1")
    await db.commit()
    order = await make_order(client, db, p.id)

    resp = await client.patch(
        f"/api/v1/admin/orders/{order['public_id']}/status",
        json={"status": "delivering"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "delivering"


@pytest.mark.asyncio
async def test_admin_invalid_transition(client: AsyncClient, db: AsyncSession):
    """Cannot go backwards: done → pending."""
    token = await get_admin_token(client, db)
    cat = await make_category(db, slug="cat1")
    p = await make_product(db, cat, legacy_id="p1")
    await db.commit()
    order = await make_order(client, db, p.id)

    # Move to done first
    await client.patch(
        f"/api/v1/admin/orders/{order['public_id']}/status",
        json={"status": "delivering"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.patch(
        f"/api/v1/admin/orders/{order['public_id']}/status",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Try backwards
    resp = await client.patch(
        f"/api/v1/admin/orders/{order['public_id']}/status",
        json={"status": "pending"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


# =============================================================================
# ADMIN PRODUCT CRUD
# =============================================================================

@pytest.mark.asyncio
async def test_admin_soft_delete_product(client: AsyncClient, db: AsyncSession):
    token = await get_admin_token(client, db)
    cat = await make_category(db, slug="cat1")
    p = await make_product(db, cat, legacy_id="p1", name="To Delete")
    await db.commit()

    resp = await client.delete(f"/api/v1/admin/products/{p.id}",
                               headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # Product should be hidden from menu now
    menu_resp = await client.get("/api/v1/menu")
    all_products = []
    for c in menu_resp.json()["categories"]:
        all_products.extend(c["products"])
    assert all(p["legacy_id"] != "p1" for p in all_products)
