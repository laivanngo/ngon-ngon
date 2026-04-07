"""
Integration Tests — Growth Features (Feature Flags, Reviews)
================================================================
Full API flow tests cho những tính năng đã sửa/thêm:

1. Feature Flags toggle — endpoint PATCH /flags/{key} (fix 500 error)
2. Reviews list — endpoint GET /reviews/list (tính năng mới)
3. Review submit — endpoint POST /reviews (fix order_public_id)
4. Growth config — endpoint GET /config (flag order stability)

Dùng SQLite in-memory + httpx AsyncClient — test actual HTTP flow.

CAVEATS:
- SQLite không có ENUM type → một số OrderStatus behavior khác PG.
- Test file này cần running app (create_app) + seeded feature_flags.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    db, client, make_admin, get_admin_token,
    make_category, make_product, make_order,
)


# =============================================================================
# Helpers
# =============================================================================

async def seed_feature_flags(db: AsyncSession):
    """Seed feature flags giống migration 002 — cần cho mọi test dùng /growth/."""
    await db.execute(text("""
        INSERT INTO feature_flags (key, enabled, description, store_id)
        VALUES
            ('upsell', 1, 'Gợi ý topping/size', 1),
            ('reorder', 1, 'Đặt lại đơn', 1),
            ('cross_sell', 1, 'Mua kèm', 1),
            ('estimated_time', 1, 'Thời gian giao', 1),
            ('loyalty', 1, 'Tích điểm', 1),
            ('analytics', 1, 'Dashboard', 1),
            ('reviews', 1, 'Đánh giá', 1),
            ('push_notifications', 0, 'Push', 1),
            ('referral', 1, 'Giới thiệu', 1)
    """))
    await db.commit()


async def seed_store(db: AsyncSession):
    """Seed default store — cần cho multi-tenant tables."""
    await db.execute(text("""
        INSERT OR IGNORE INTO stores (id, name, slug, phone, address)
        VALUES (1, 'Test Store', 'test', '0378148148', 'Test')
    """))
    await db.commit()


async def submit_review(client: AsyncClient, rating: int, phone: str = "0901234567",
                         comment: str | None = None, order_public_id: str | None = None):
    """Helper: submit review qua API."""
    body = {"rating": rating, "phone": phone}
    if comment:
        body["comment"] = comment
    if order_public_id:
        body["order_public_id"] = order_public_id
    return await client.post("/api/v1/growth/reviews", json=body)


# =============================================================================
# Feature Flags — Toggle
# =============================================================================

class TestFeatureFlagToggle:
    """
    PATCH /growth/flags/{key}
    BUG gốc: thiếu admin_username → 500 Internal Server Error.
    FIX: thêm admin.username vào use_case.execute().
    """

    @pytest.mark.asyncio
    async def test_toggle_flag_success(self, db, client):
        """Admin bật/tắt flag → 200, không còn 500 error."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        # Tắt upsell
        resp = await client.patch(
            "/api/v1/growth/flags/upsell",
            json={"enabled": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "upsell"
        assert data["enabled"] is False

    @pytest.mark.asyncio
    async def test_toggle_flag_on(self, db, client):
        """Bật flag đang tắt → enabled = True."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        # push_notifications mặc định là OFF → bật lên
        resp = await client.patch(
            "/api/v1/growth/flags/push_notifications",
            json={"enabled": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    @pytest.mark.asyncio
    async def test_toggle_independent(self, db, client):
        """Toggle 1 flag → các flag khác không bị ảnh hưởng."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        # Tắt reorder
        await client.patch(
            "/api/v1/growth/flags/reorder",
            json={"enabled": False},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Kiểm tra config → upsell vẫn ON, reorder OFF
        resp = await client.get(
            "/api/v1/growth/config",
            headers={"Authorization": f"Bearer {token}"},
        )
        flags = resp.json()["flags"]
        assert flags["upsell"] is True
        assert flags["reorder"] is False
        assert flags["cross_sell"] is True

    @pytest.mark.asyncio
    async def test_toggle_nonexistent_flag_404(self, db, client):
        """Toggle flag không tồn tại → 404."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        resp = await client.patch(
            "/api/v1/growth/flags/nonexistent_feature",
            json={"enabled": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_toggle_requires_auth(self, db, client):
        """Toggle không có token → 401."""
        await seed_store(db)
        await seed_feature_flags(db)

        resp = await client.patch(
            "/api/v1/growth/flags/upsell",
            json={"enabled": False},
        )
        assert resp.status_code == 401


# =============================================================================
# Growth Config — Flag Order Stability
# =============================================================================

class TestGrowthConfig:
    """
    GET /growth/config
    BUG gốc: flags trả về không ORDER BY → thứ tự xáo trộn mỗi lần.
    FIX: thêm .order_by(FeatureFlag.id).
    """

    @pytest.mark.asyncio
    async def test_config_returns_all_flags(self, db, client):
        """Config trả về tất cả 9 flags."""
        await seed_store(db)
        await seed_feature_flags(db)

        resp = await client.get("/api/v1/growth/config")
        assert resp.status_code == 200
        flags = resp.json()["flags"]
        assert len(flags) == 9

        # Verify all expected flags exist
        expected = {"upsell", "reorder", "cross_sell", "estimated_time",
                    "loyalty", "analytics", "reviews", "push_notifications", "referral"}
        assert set(flags.keys()) == expected

    @pytest.mark.asyncio
    async def test_flag_order_stable_after_toggle(self, db, client):
        """Toggle 1 flag → gọi config lại → thứ tự keys giống nhau."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        # Lấy thứ tự ban đầu
        resp1 = await client.get("/api/v1/growth/config")
        keys_before = list(resp1.json()["flags"].keys())

        # Toggle reorder
        await client.patch(
            "/api/v1/growth/flags/reorder",
            json={"enabled": False},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Lấy thứ tự sau toggle
        resp2 = await client.get("/api/v1/growth/config")
        keys_after = list(resp2.json()["flags"].keys())

        # Thứ tự phải giống nhau (fix ORDER BY)
        assert keys_before == keys_after


# =============================================================================
# Reviews — Submit + List
# =============================================================================

class TestReviewSubmit:
    """
    POST /growth/reviews
    BUG gốc: frontend gửi parseInt(UUID) = NaN → order_id = null.
    FIX: nhận order_public_id (string), resolve → integer FK.
    """

    @pytest.mark.asyncio
    async def test_submit_review_basic(self, db, client):
        """Gửi review cơ bản (không có order) → 200."""
        await seed_store(db)
        await seed_feature_flags(db)

        resp = await submit_review(client, rating=5, phone="0901234567",
                                    comment="Trà sữa ngon!")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_submit_review_with_order_public_id(self, db, client):
        """Gửi review kèm order_public_id → resolve đúng FK."""
        await seed_store(db)
        await seed_feature_flags(db)

        # Tạo đơn hàng thật
        cat = await make_category(db)
        product = await make_product(db, cat)
        await db.commit()
        order_resp = await make_order(client, db, product.id)
        public_id = order_resp["public_id"]

        # Submit review với order_public_id
        resp = await submit_review(
            client, rating=4, phone="0901234567",
            comment="Giao nhanh lắm!",
            order_public_id=public_id,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_rating_rejected(self, db, client):
        """Rating ngoài 1-5 → 422 validation error."""
        await seed_store(db)

        resp = await submit_review(client, rating=0)
        assert resp.status_code == 422

        resp = await submit_review(client, rating=6)
        assert resp.status_code == 422


class TestReviewsList:
    """
    GET /growth/reviews/list
    Tính năng mới: admin xem danh sách đánh giá.
    """

    @pytest.mark.asyncio
    async def test_list_reviews_empty(self, db, client):
        """Chưa có review → trả list rỗng."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        resp = await client.get(
            "/api/v1/growth/reviews/list",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviews"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_reviews_with_data(self, db, client):
        """Submit 3 reviews → admin thấy cả 3."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        # Submit 3 reviews
        for i in range(3):
            await submit_review(client, rating=i + 3, phone=f"090123456{i}",
                                 comment=f"Review {i + 1}")

        resp = await client.get(
            "/api/v1/growth/reviews/list",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["reviews"]) == 3

    @pytest.mark.asyncio
    async def test_list_reviews_filter_by_rating(self, db, client):
        """Lọc theo 5 sao → chỉ trả reviews 5 sao."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        # Submit reviews với rating khác nhau
        await submit_review(client, rating=5, comment="Tuyệt vời!")
        await submit_review(client, rating=3, comment="Bình thường")
        await submit_review(client, rating=5, comment="Rất ngon!")

        resp = await client.get(
            "/api/v1/growth/reviews/list?rating=5",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        assert data["total"] == 2
        assert all(r["rating"] == 5 for r in data["reviews"])

    @pytest.mark.asyncio
    async def test_list_reviews_pagination(self, db, client):
        """Phân trang: limit=2, offset=0 → 2 reviews, total đúng."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        # Submit 5 reviews
        for i in range(5):
            await submit_review(client, rating=(i % 5) + 1, phone=f"090123456{i}")

        resp = await client.get(
            "/api/v1/growth/reviews/list?limit=2&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        assert len(data["reviews"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_reviews_requires_auth(self, db, client):
        """Xem reviews không có token → 401."""
        await seed_store(db)

        resp = await client.get("/api/v1/growth/reviews/list")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_review_has_complete_fields(self, db, client):
        """Mỗi review trả về đủ field cho admin UI."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        await submit_review(client, rating=4, phone="0901234567",
                             comment="Ngon nhưng giao hơi chậm")

        resp = await client.get(
            "/api/v1/growth/reviews/list",
            headers={"Authorization": f"Bearer {token}"},
        )
        r = resp.json()["reviews"][0]
        assert r["rating"] == 4
        assert r["phone"] == "0901234567"
        assert r["comment"] == "Ngon nhưng giao hơi chậm"
        assert r["created_at"] is not None

    @pytest.mark.asyncio
    async def test_review_linked_to_order(self, db, client):
        """Review gửi kèm order_public_id → admin thấy mã đơn."""
        await seed_store(db)
        await seed_feature_flags(db)
        token = await get_admin_token(client, db)

        # Tạo đơn hàng
        cat = await make_category(db)
        product = await make_product(db, cat)
        await db.commit()
        order_resp = await make_order(client, db, product.id)
        public_id = order_resp["public_id"]

        # Submit review kèm order
        await submit_review(client, rating=5, order_public_id=public_id)

        # Admin xem → thấy order_public_id
        resp = await client.get(
            "/api/v1/growth/reviews/list",
            headers={"Authorization": f"Bearer {token}"},
        )
        r = resp.json()["reviews"][0]
        assert r["order_public_id"] == public_id
