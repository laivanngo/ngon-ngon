"""
Unit Tests — v5.2.0 Changes (merged)
=======================================
Gộp từ 2 file:
  - test_v520_changes.py (phiên hiện tại — 53 tests)
  - test_growth_use_cases.py (phiên trước — 16 tests)
Loại bỏ trùng lặp, giữ tất cả tests unique → tổng 59 tests.

Bao gồm:
1. GetReviewsUseCase — admin xem danh sách reviews (tính năng mới)
2. ToggleFeatureFlagUseCase — fix thêm admin_username param
3. ReviewCreate schema — thêm field order_public_id
4. Review entity — _order_public_id attribute (set bởi list_all impl)
5. ReviewRepository.list_all() — abstract method mới trên ABC
6. FeatureFlagRepository.get_all() — verify interface (order_by fix ở infra)

Pattern: pure unit tests, mock repos, KHÔNG cần DB.
Chạy: PYTHONPATH=. python -m pytest tests/unit/test_v520_changes.py --noconftest -v
"""

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.crm.domain.entities import Review
from app.crm.domain.services import ReviewRepository
from app.promotions.domain.services import (
    FeatureFlag,
    FeatureFlagRepository,
)
from app.crm.application.use_cases import GetReviewsUseCase
from app.promotions.application.use_cases import ToggleFeatureFlagUseCase
from app.crm.presentation.schemas import ReviewCreate
from app.promotions.presentation.schemas import FlagToggle
from app.shared.exceptions import NotFoundError


# =============================================================================
# Helpers — Fake repos & async test runner
# =============================================================================

def _run(coro):
    """Chạy coroutine trong sync test — không cần pytest-asyncio."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_review(
    id: int = 1,
    order_id: int = 100,
    phone: str = "0901234567",
    rating: int = 5,
    comment: str | None = "Ngon lắm!",
    created_at: datetime | None = None,
    order_public_id: str | None = None,
) -> Review:
    """Factory tạo Review entity cho test, có thể gắn _order_public_id."""
    r = Review(
        id=id,
        order_id=order_id,
        phone=phone,
        rating=rating,
        comment=comment,
        created_at=created_at or datetime(2025, 6, 15, 10, 30, tzinfo=timezone.utc),
    )
    if order_public_id:
        r._order_public_id = order_public_id
    return r


class FakeReviewRepository(ReviewRepository):
    """
    In-memory ReviewRepository cho testing.
    list_all() trả reviews đã seed, hỗ trợ filter + pagination.
    Sort mới nhất trước (by id descending) giống SQL impl.
    """

    def __init__(self, reviews: list[Review] | None = None):
        self._reviews = reviews or []
        self._total = len(self._reviews)

    async def save(self, review: Review) -> Review:
        review.id = len(self._reviews) + 1
        review.created_at = datetime.now(timezone.utc)
        self._reviews.append(review)
        return review

    async def exists_for_order(self, order_id: int) -> bool:
        return any(r.order_id == order_id for r in self._reviews)

    async def avg_rating_since(self, since_days: int) -> float | None:
        if not self._reviews:
            return None
        return sum(r.rating for r in self._reviews) / len(self._reviews)

    async def list_all(
        self, limit: int = 50, offset: int = 0, rating: int | None = None,
    ) -> tuple[list[Review], int]:
        filtered = self._reviews
        if rating is not None:
            filtered = [r for r in filtered if r.rating == rating]
        total = len(filtered)
        # Sort mới nhất trước (by id desc) — giống SqlReviewRepository impl
        filtered = sorted(filtered, key=lambda r: r.id or 0, reverse=True)
        page = filtered[offset : offset + limit]
        return page, total


class FakeFeatureFlagRepository(FeatureFlagRepository):
    """In-memory FeatureFlagRepository cho testing."""

    def __init__(self, flags: dict[str, FeatureFlag] | None = None):
        self._flags = flags or {}

    async def get_all(self) -> dict[str, bool]:
        return {k: f.enabled for k, f in self._flags.items()}

    async def toggle(self, key: str, enabled: bool) -> FeatureFlag | None:
        if key not in self._flags:
            return None
        self._flags[key].enabled = enabled
        return self._flags[key]


# =============================================================================
# 1. GetReviewsUseCase — Use case mới cho admin reviews dashboard
# =============================================================================

class TestGetReviewsUseCase:
    """
    GetReviewsUseCase lấy danh sách reviews từ repo,
    format response dict có reviews/total/limit/offset.

    Gộp: 13 tests gốc + 6 tests unique từ test_growth_use_cases.py
    (newest_first, filter_1_star, pagination_offset disjoint, last_page).
    """

    def test_returns_formatted_response_with_reviews(self):
        """Happy path: có reviews → trả list đúng format."""
        reviews = [
            _make_review(id=1, rating=5, comment="Tuyệt vời", order_public_id="abc-123"),
            _make_review(id=2, rating=3, comment="Bình thường", phone="0909999888"),
        ]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(limit=50, offset=0, rating=None))

        assert result["total"] == 2
        assert result["limit"] == 50
        assert result["offset"] == 0
        assert len(result["reviews"]) == 2

    def test_review_item_has_all_required_fields(self):
        """Mỗi review item phải có đủ fields cho admin dashboard."""
        reviews = [_make_review(id=7, order_public_id="uuid-xyz")]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute())
        item = result["reviews"][0]

        # Tất cả fields admin dashboard cần hiển thị
        assert item["id"] == 7
        assert item["order_id"] == 100
        assert item["order_public_id"] == "uuid-xyz"
        assert item["phone"] == "0901234567"
        assert item["rating"] == 5
        assert item["comment"] == "Ngon lắm!"
        assert item["created_at"] is not None

    def test_order_public_id_none_when_not_attached(self):
        """Review không có _order_public_id → trả None (backward compat)."""
        review = Review(
            id=1, order_id=100, phone="0901234567",
            rating=4, comment="OK",
            created_at=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )
        # KHÔNG set _order_public_id
        repo = FakeReviewRepository([review])
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute())
        assert result["reviews"][0]["order_public_id"] is None

    def test_empty_results(self):
        """Không có reviews → trả list rỗng, total = 0."""
        repo = FakeReviewRepository([])
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute())
        assert result["reviews"] == []
        assert result["total"] == 0

    def test_rating_filter_passed_to_repo(self):
        """Rating filter được truyền đúng xuống repo.list_all()."""
        reviews = [
            _make_review(id=1, rating=5),
            _make_review(id=2, rating=3),
            _make_review(id=3, rating=5),
        ]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(rating=5))
        assert result["total"] == 2
        assert all(r["rating"] == 5 for r in result["reviews"])

    def test_rating_filter_none_returns_all(self):
        """rating=None → không lọc, trả tất cả."""
        reviews = [
            _make_review(id=i, rating=r)
            for i, r in enumerate([1, 2, 3, 4, 5], start=1)
        ]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(rating=None))
        assert result["total"] == 5

    def test_filter_by_rating_1_star(self):
        """Lọc 1 sao → xem reviews tiêu cực để cải thiện chất lượng.
        (Từ test_growth_use_cases.py — scenario thực tế cho chủ quán.)
        """
        reviews = [
            _make_review(id=i, rating=(i % 5) + 1)
            for i in range(10)
        ]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(rating=1))
        assert result["total"] == 2
        assert all(r["rating"] == 1 for r in result["reviews"])

    def test_pagination_limit_offset(self):
        """Phân trang: limit=2, offset=1 → bỏ review đầu, lấy 2 review tiếp."""
        reviews = [_make_review(id=i) for i in range(1, 6)]  # 5 reviews
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(limit=2, offset=1))
        assert len(result["reviews"]) == 2
        assert result["total"] == 5  # total không bị ảnh hưởng bởi pagination
        assert result["limit"] == 2
        assert result["offset"] == 1

    def test_pagination_two_pages_disjoint(self):
        """Trang 1 và trang 2 không trùng nhau — mỗi review chỉ xuất hiện 1 lần.
        (Từ test_growth_use_cases.py — đảm bảo offset hoạt động đúng.)
        """
        reviews = [_make_review(id=i, rating=5) for i in range(1, 13)]  # 12 reviews
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        page1 = _run(uc.execute(limit=5, offset=0))
        page2 = _run(uc.execute(limit=5, offset=5))

        ids_page1 = {r["id"] for r in page1["reviews"]}
        ids_page2 = {r["id"] for r in page2["reviews"]}
        # Hai trang phải hoàn toàn khác nhau
        assert ids_page1.isdisjoint(ids_page2)

    def test_pagination_last_page_fewer_items(self):
        """Trang cuối có ít hơn limit items.
        (Từ test_growth_use_cases.py — edge case trang cuối.)
        """
        reviews = [_make_review(id=i) for i in range(1, 8)]  # 7 reviews
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(limit=5, offset=5))
        assert len(result["reviews"]) == 2  # 7 - 5 = 2 remaining
        assert result["total"] == 7

    def test_offset_beyond_total_returns_empty(self):
        """Offset vượt quá tổng số reviews → trả list rỗng nhưng total vẫn đúng."""
        reviews = [_make_review(id=1)]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(offset=100))
        assert result["reviews"] == []
        assert result["total"] == 1  # vẫn biết có 1 review

    def test_default_params(self):
        """Gọi execute() không tham số → dùng defaults (limit=50, offset=0, rating=None)."""
        repo = FakeReviewRepository([])
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute())
        assert result["limit"] == 50
        assert result["offset"] == 0

    def test_created_at_serialized_as_isoformat(self):
        """created_at phải được serialize thành ISO 8601 string."""
        dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        review = _make_review(id=1, created_at=dt)
        repo = FakeReviewRepository([review])
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute())
        assert result["reviews"][0]["created_at"] == dt.isoformat()

    def test_created_at_none_serialized_as_none(self):
        """Review chưa có created_at (trước khi persist) → None."""
        review = Review(
            id=1, order_id=100, phone="0901234567",
            rating=4, comment="OK", created_at=None,
        )
        repo = FakeReviewRepository([review])
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute())
        assert result["reviews"][0]["created_at"] is None

    def test_rating_filter_no_match(self):
        """Lọc rating mà không có review nào match → empty list, total=0."""
        reviews = [_make_review(id=1, rating=5)]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(rating=1))
        assert result["reviews"] == []
        assert result["total"] == 0

    def test_execute_calls_repo_list_all(self):
        """Verify execute() gọi repo.list_all() đúng params (dùng mock)."""
        mock_repo = AsyncMock(spec=ReviewRepository)
        mock_repo.list_all.return_value = ([], 0)

        uc = GetReviewsUseCase(review_repo=mock_repo)
        _run(uc.execute(limit=20, offset=5, rating=3))

        mock_repo.list_all.assert_called_once_with(
            limit=20, offset=5, rating=3,
        )

    def test_newest_first(self):
        """Reviews sắp xếp mới nhất trước — admin muốn xem review mới nhất đầu tiên.
        (Từ test_growth_use_cases.py — đảm bảo sort order đúng.)
        """
        reviews = [_make_review(id=i, rating=(i % 5) + 1) for i in range(1, 6)]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute())
        ids = [r["id"] for r in result["reviews"]]
        # ids phải giảm dần (mới nhất trước, vì id lớn hơn = tạo sau)
        assert ids == sorted(ids, reverse=True)

    def test_reviews_preserve_comment_none(self):
        """Khách không viết góp ý → comment = None (không phải empty string)."""
        review = _make_review(id=1, comment=None)
        repo = FakeReviewRepository([review])
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute())
        assert result["reviews"][0]["comment"] is None


# =============================================================================
# 2. ToggleFeatureFlagUseCase — Fix thêm admin_username param
# =============================================================================

class TestToggleFeatureFlagUseCase:
    """
    v5.2.0 fix: execute() nhận 3 tham số (key, enabled, admin_username).
    Trước đó thiếu admin_username → lỗi 500.

    Gộp: 8 tests gốc + 2 tests unique từ test_growth_use_cases.py
    (requires_admin_username TypeError, each_flag_independent).
    """

    def test_execute_signature_has_three_params(self):
        """execute() phải nhận đúng 3 params: key, enabled, admin_username."""
        sig = inspect.signature(ToggleFeatureFlagUseCase.execute)
        params = list(sig.parameters.keys())
        # self + key + enabled + admin_username = 4
        assert "key" in params
        assert "enabled" in params
        assert "admin_username" in params
        assert len(params) == 4  # self, key, enabled, admin_username

    def test_requires_admin_username_or_raises_type_error(self):
        """Regression test: gọi execute() THIẾU admin_username → TypeError.
        Đây là bug gốc gây lỗi 500. Nếu ai đó vô tình xóa tham số này,
        test sẽ fail ngay → bảo vệ khỏi lặp lại bug.
        (Từ test_growth_use_cases.py — test quan trọng nhất cho bug này.)
        """
        flags = {"upsell": FeatureFlag(key="upsell", enabled=True, id=1)}
        repo = FakeFeatureFlagRepository(flags)
        uc = ToggleFeatureFlagUseCase(flag_repo=repo)

        with pytest.raises(TypeError):
            _run(uc.execute("upsell", True))  # type: ignore — thiếu admin_username

    def test_toggle_on_success(self):
        """Bật flag thành công → trả FeatureFlag đã updated."""
        flags = {
            "cross_sell": FeatureFlag(key="cross_sell", enabled=False, id=1),
        }
        repo = FakeFeatureFlagRepository(flags)
        uc = ToggleFeatureFlagUseCase(flag_repo=repo)

        result = _run(uc.execute("cross_sell", True, "admin1"))
        assert result.enabled is True

    def test_toggle_off_success(self):
        """Tắt flag thành công."""
        flags = {
            "loyalty": FeatureFlag(key="loyalty", enabled=True, id=2),
        }
        repo = FakeFeatureFlagRepository(flags)
        uc = ToggleFeatureFlagUseCase(flag_repo=repo)

        result = _run(uc.execute("loyalty", False, "admin1"))
        assert result.enabled is False

    def test_toggle_nonexistent_key_raises_not_found(self):
        """Key không tồn tại → raise NotFoundError."""
        repo = FakeFeatureFlagRepository({})
        uc = ToggleFeatureFlagUseCase(flag_repo=repo)

        with pytest.raises(NotFoundError, match="not found"):
            _run(uc.execute("nonexistent", True, "admin1"))

    def test_each_flag_independent(self):
        """Toggle 1 flag không ảnh hưởng flag khác.
        Giống ngoài quán: tắt tính năng "Đặt lại đơn" không được tắt luôn "Gợi ý mua kèm".
        (Từ test_growth_use_cases.py — scenario thực tế.)
        """
        flags = {
            "upsell": FeatureFlag(key="upsell", enabled=True, id=1),
            "reorder": FeatureFlag(key="reorder", enabled=True, id=2),
            "cross_sell": FeatureFlag(key="cross_sell", enabled=True, id=3),
        }
        repo = FakeFeatureFlagRepository(flags)
        uc = ToggleFeatureFlagUseCase(flag_repo=repo)

        # Tắt reorder
        _run(uc.execute("reorder", False, "admin"))

        # upsell và cross_sell vẫn ON
        all_flags = _run(repo.get_all())
        assert all_flags["upsell"] is True
        assert all_flags["reorder"] is False
        assert all_flags["cross_sell"] is True

    def test_log_message_includes_admin_username(self):
        """Log message phải chứa admin_username — đây là bug đã fix."""
        flags = {
            "reorder": FeatureFlag(key="reorder", enabled=False, id=3),
        }
        repo = FakeFeatureFlagRepository(flags)
        uc = ToggleFeatureFlagUseCase(flag_repo=repo)

        with patch("app.promotions.application.use_cases.logger") as mock_logger:
            _run(uc.execute("reorder", True, "quanly01"))
            mock_logger.info.assert_called_once()
            log_msg = mock_logger.info.call_args[0][0]
            assert "quanly01" in log_msg

    def test_log_message_shows_on_off_state(self):
        """Log message hiện ON/OFF đúng trạng thái mới."""
        flags = {
            "estimated_time": FeatureFlag(key="estimated_time", enabled=True, id=4),
        }
        repo = FakeFeatureFlagRepository(flags)
        uc = ToggleFeatureFlagUseCase(flag_repo=repo)

        with patch("app.promotions.application.use_cases.logger") as mock_logger:
            _run(uc.execute("estimated_time", False, "admin"))
            log_msg = mock_logger.info.call_args[0][0]
            assert "OFF" in log_msg
            assert "estimated_time" in log_msg

    def test_log_message_on_state(self):
        """Khi bật flag → log chứa 'ON'."""
        flags = {"f": FeatureFlag(key="f", enabled=False, id=5)}
        repo = FakeFeatureFlagRepository(flags)
        uc = ToggleFeatureFlagUseCase(flag_repo=repo)

        with patch("app.promotions.application.use_cases.logger") as mock_logger:
            _run(uc.execute("f", True, "boss"))
            log_msg = mock_logger.info.call_args[0][0]
            assert "ON" in log_msg

    def test_returns_feature_flag_object(self):
        """Return type phải là FeatureFlag (không phải dict)."""
        flags = {"x": FeatureFlag(key="x", enabled=False, id=6)}
        repo = FakeFeatureFlagRepository(flags)
        uc = ToggleFeatureFlagUseCase(flag_repo=repo)

        result = _run(uc.execute("x", True, "admin"))
        assert isinstance(result, FeatureFlag)
        assert result.key == "x"


# =============================================================================
# 3. ReviewCreate Schema — Thêm field order_public_id
# =============================================================================

class TestReviewCreateSchema:
    """
    v5.2.0 thêm order_public_id: str | None vào ReviewCreate.
    Frontend gửi UUID string thay vì parseInt(UUID) = NaN.
    """

    def test_order_public_id_accepted(self):
        """Schema chấp nhận order_public_id string."""
        data = ReviewCreate(
            rating=5,
            order_public_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            phone="0901234567",
        )
        assert data.order_public_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_order_public_id_default_none(self):
        """order_public_id mặc định là None (backward compat)."""
        data = ReviewCreate(rating=4)
        assert data.order_public_id is None

    def test_backward_compat_order_id_still_works(self):
        """order_id (integer) vẫn hoạt động cho backward compatibility."""
        data = ReviewCreate(rating=3, order_id=42, phone="0909876543")
        assert data.order_id == 42
        assert data.order_public_id is None

    def test_both_order_id_and_public_id(self):
        """Gửi cả hai field → cả hai đều accepted."""
        data = ReviewCreate(
            rating=5, order_id=99, order_public_id="uuid-here",
        )
        assert data.order_id == 99
        assert data.order_public_id == "uuid-here"

    def test_neither_order_id_nor_public_id(self):
        """Không gửi order_id lẫn order_public_id → cả hai đều None."""
        data = ReviewCreate(rating=2)
        assert data.order_id is None
        assert data.order_public_id is None

    def test_rating_validation_range(self):
        """Rating phải 1-5, ngoài range → lỗi."""
        with pytest.raises(Exception):
            ReviewCreate(rating=0)
        with pytest.raises(Exception):
            ReviewCreate(rating=6)

    def test_rating_valid_boundary(self):
        """Rating 1 và 5 đều hợp lệ (inclusive)."""
        r1 = ReviewCreate(rating=1)
        r5 = ReviewCreate(rating=5)
        assert r1.rating == 1
        assert r5.rating == 5

    def test_comment_max_length(self):
        """Comment dài quá 500 ký tự → Pydantic reject."""
        with pytest.raises(Exception):
            ReviewCreate(rating=5, comment="x" * 501)

    def test_comment_at_limit(self):
        """Comment đúng 500 ký tự → OK."""
        data = ReviewCreate(rating=5, comment="x" * 500)
        assert len(data.comment) == 500

    def test_order_public_id_max_length(self):
        """order_public_id quá 50 ký tự → reject (field has max_length=50)."""
        with pytest.raises(Exception):
            ReviewCreate(rating=5, order_public_id="x" * 51)

    def test_phone_default_empty(self):
        """Phone mặc định là empty string."""
        data = ReviewCreate(rating=4)
        assert data.phone == ""


# =============================================================================
# 4. FlagToggle Schema — Request body cho PATCH /flags/{key}
# =============================================================================

class TestFlagToggleSchema:
    """FlagToggle schema chỉ cần field enabled: bool."""

    def test_enabled_true(self):
        ft = FlagToggle(enabled=True)
        assert ft.enabled is True

    def test_enabled_false(self):
        ft = FlagToggle(enabled=False)
        assert ft.enabled is False

    def test_default_false(self):
        ft = FlagToggle()
        assert ft.enabled is False


# =============================================================================
# 5. Review Entity — _order_public_id attribute (used by list_all)
# =============================================================================

class TestReviewOrderPublicId:
    """
    Infrastructure layer (SqlReviewRepository.list_all) join orders
    để lấy public_id rồi gắn vào review._order_public_id.
    GetReviewsUseCase dùng getattr(r, '_order_public_id', None).
    """

    def test_can_attach_order_public_id(self):
        """Review entity cho phép gắn _order_public_id attribute."""
        review = Review.create(
            order_id=100, phone="0901234567", rating=5, comment="Ngon",
        )
        review._order_public_id = "abc-123-def"
        assert review._order_public_id == "abc-123-def"

    def test_getattr_default_none(self):
        """Review mới tạo, chưa gắn _order_public_id → getattr trả None."""
        review = Review.create(
            order_id=100, phone="0901234567", rating=4,
        )
        assert getattr(review, "_order_public_id", None) is None

    def test_review_create_factory_still_works(self):
        """Review.create() factory vẫn hoạt động bình thường."""
        review = Review.create(
            order_id=42, phone="0909876543", rating=3, comment="Tạm ổn",
        )
        assert review.order_id == 42
        assert review.rating == 3
        assert review.comment == "Tạm ổn"
        assert review.phone == "0909876543"

    def test_review_create_validates_rating(self):
        """Review.create() vẫn validate rating 1-5."""
        with pytest.raises(ValueError):
            Review.create(order_id=1, phone="0901234567", rating=0)
        with pytest.raises(ValueError):
            Review.create(order_id=1, phone="0901234567", rating=6)

    def test_review_create_truncates_comment(self):
        """Comment dài hơn 500 → bị cắt."""
        long_comment = "A" * 600
        review = Review.create(
            order_id=1, phone="0901234567", rating=5, comment=long_comment,
        )
        assert len(review.comment) <= 500


# =============================================================================
# 6. ReviewRepository ABC — list_all() method mới
# =============================================================================

class TestReviewRepositoryABC:
    """Verify abstract method list_all() tồn tại trên ABC."""

    def test_list_all_is_abstract_method(self):
        """list_all phải là abstract method trên ReviewRepository."""
        assert hasattr(ReviewRepository, "list_all")
        # Kiểm tra nó nằm trong __abstractmethods__
        assert "list_all" in ReviewRepository.__abstractmethods__

    def test_list_all_signature(self):
        """list_all() nhận limit, offset, rating params."""
        sig = inspect.signature(ReviewRepository.list_all)
        params = list(sig.parameters.keys())
        assert "limit" in params
        assert "offset" in params
        assert "rating" in params

    def test_list_all_default_values(self):
        """Params có defaults: limit=50, offset=0, rating=None."""
        sig = inspect.signature(ReviewRepository.list_all)
        assert sig.parameters["limit"].default == 50
        assert sig.parameters["offset"].default == 0
        assert sig.parameters["rating"].default is None

    def test_cannot_instantiate_without_list_all(self):
        """Nếu subclass không implement list_all → TypeError khi tạo instance."""

        class IncompleteRepo(ReviewRepository):
            async def save(self, review):
                pass

            async def exists_for_order(self, order_id):
                pass

            async def avg_rating_since(self, since_days):
                pass

            # Thiếu list_all() → phải lỗi

        with pytest.raises(TypeError, match="list_all"):
            IncompleteRepo()


# =============================================================================
# 7. FeatureFlagRepository ABC — get_all() interface
# =============================================================================

class TestFeatureFlagRepositoryABC:
    """get_all() trả dict[str, bool] — infra đã fix thêm order_by."""

    def test_get_all_is_abstract(self):
        assert "get_all" in FeatureFlagRepository.__abstractmethods__

    def test_toggle_is_abstract(self):
        assert "toggle" in FeatureFlagRepository.__abstractmethods__


# =============================================================================
# 8. FeatureFlag DTO
# =============================================================================

class TestFeatureFlagDTO:
    """FeatureFlag dataclass — simple DTO cho flag data."""

    def test_create_with_defaults(self):
        flag = FeatureFlag(key="reorder", enabled=True)
        assert flag.key == "reorder"
        assert flag.enabled is True
        assert flag.description == ""
        assert flag.id is None

    def test_create_full(self):
        flag = FeatureFlag(
            key="loyalty", enabled=False,
            description="Loyalty program", id=42,
        )
        assert flag.description == "Loyalty program"
        assert flag.id == 42


# =============================================================================
# 9. Edge Cases — Pagination & Filtering
# =============================================================================

class TestEdgeCases:
    """Edge cases cho GetReviewsUseCase với các combinations lạ."""

    def test_limit_1_returns_single_review(self):
        """limit=1 → chỉ lấy 1 review."""
        reviews = [_make_review(id=i) for i in range(1, 4)]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(limit=1))
        assert len(result["reviews"]) == 1
        assert result["total"] == 3

    def test_all_ratings_filter(self):
        """Lọc từng rating 1-5 → chỉ trả đúng rating đó."""
        reviews = [_make_review(id=i, rating=i) for i in range(1, 6)]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        for r in range(1, 6):
            result = _run(uc.execute(rating=r))
            assert result["total"] == 1
            assert result["reviews"][0]["rating"] == r

    def test_large_offset_with_filter(self):
        """Offset lớn + filter → empty nhưng total đúng."""
        reviews = [_make_review(id=i, rating=5) for i in range(1, 4)]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        result = _run(uc.execute(rating=5, offset=100))
        assert result["reviews"] == []
        assert result["total"] == 3

    def test_multiple_pages(self):
        """Duyệt qua nhiều trang — tổng items đúng."""
        reviews = [_make_review(id=i, rating=(i % 5) + 1) for i in range(1, 11)]
        repo = FakeReviewRepository(reviews)
        uc = GetReviewsUseCase(review_repo=repo)

        page1 = _run(uc.execute(limit=3, offset=0))
        page2 = _run(uc.execute(limit=3, offset=3))
        page3 = _run(uc.execute(limit=3, offset=6))
        page4 = _run(uc.execute(limit=3, offset=9))

        all_ids = [
            r["id"] for page in [page1, page2, page3, page4]
            for r in page["reviews"]
        ]
        assert len(all_ids) == 10
        assert all(p["total"] == 10 for p in [page1, page2, page3, page4])
