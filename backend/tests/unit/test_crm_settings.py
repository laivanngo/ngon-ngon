"""
Unit Tests — Growth Settings (admin-configurable business values)
===================================================================
Kiểm tra:

- GrowthSettingDTO tạo đúng, có đủ field
- GetGrowthSettingsUseCase trả danh sách settings
- UpdateGrowthSettingUseCase cập nhật + validate min/max
- GetReferralUseCase đọc discount từ settings (không hardcode)

Không cần database — mock repository.
"""

import pytest

from app.crm.domain.services import GrowthSettingDTO, GrowthSettingsRepository
from app.crm.domain.value_objects import REFERRAL_DISCOUNT
from app.crm.application.use_cases import (
    GetGrowthSettingsUseCase,
    GetReferralUseCase,
    UpdateGrowthSettingUseCase,
)
from app.shared.exceptions import NotFoundError, ValidationError


# =============================================================================
# In-Memory Mock Repository
# =============================================================================

class InMemoryGrowthSettingsRepository(GrowthSettingsRepository):
    """Mock repository cho tests — lưu trong dict."""

    def __init__(self, settings: list[GrowthSettingDTO] | None = None) -> None:
        self._data: dict[str, GrowthSettingDTO] = {}
        for s in (settings or []):
            self._data[s.key] = s

    async def get_all(self) -> list[GrowthSettingDTO]:
        return list(self._data.values())

    async def get_value(self, key: str, default: int = 0) -> int:
        s = self._data.get(key)
        return s.value if s else default

    async def update(self, key: str, value: int) -> GrowthSettingDTO | None:
        s = self._data.get(key)
        if not s:
            return None
        if value < s.min_value or value > s.max_value:
            raise ValidationError(
                f"Giá trị phải từ {s.min_value} đến {s.max_value}{s.unit}"
            )
        updated = GrowthSettingDTO(
            key=s.key, value=value, label=s.label,
            description=s.description, min_value=s.min_value,
            max_value=s.max_value, unit=s.unit,
        )
        self._data[key] = updated
        return updated


# =============================================================================
# Mock cho CustomerRepository và ReferralRepository (dùng trong GetReferralUseCase)
# =============================================================================

class MockCustomerRepo:
    """Minimal mock — chỉ cần cho GetReferralUseCase test."""

    def __init__(self, customer=None):
        self._customer = customer

    async def find_by_phone(self, phone):
        return self._customer

    async def save(self, customer):
        return customer


class MockReferralRepo:
    """Minimal mock — trả count cố định."""

    def __init__(self, count: int = 0):
        self._count = count

    async def count_by_referrer(self, phone):
        return self._count


# =============================================================================
# Fixtures
# =============================================================================

def _default_settings() -> list[GrowthSettingDTO]:
    """3 settings mặc định — giống seed trong migration 006."""
    return [
        GrowthSettingDTO(
            key="referral_discount", value=5, label="Giảm giá giới thiệu",
            description="Số tiền giảm cho cả 2 bên",
            min_value=0, max_value=50, unit="k",
        ),
        GrowthSettingDTO(
            key="loyalty_threshold", value=10, label="Số đơn tích điểm",
            description="Mua đủ bao nhiêu đơn thì được thưởng",
            min_value=3, max_value=50, unit="đơn",
        ),
        GrowthSettingDTO(
            key="loyalty_reward_value", value=25, label="Giá trị thưởng",
            description="Giá trị tối đa của phần thưởng loyalty",
            min_value=5, max_value=100, unit="k",
        ),
    ]


# =============================================================================
# GrowthSettingDTO — Value Object Tests
# =============================================================================

class TestGrowthSettingDTO:
    """DTO có đủ field để admin UI render form."""

    def test_create_with_all_fields(self):
        s = GrowthSettingDTO(
            key="referral_discount", value=5, label="Giảm giá",
            description="Mô tả", min_value=0, max_value=50, unit="k",
        )
        assert s.key == "referral_discount"
        assert s.value == 5
        assert s.min_value == 0
        assert s.max_value == 50
        assert s.unit == "k"

    def test_defaults(self):
        """Tạo minimal DTO → defaults hợp lý."""
        s = GrowthSettingDTO(key="test", value=10)
        assert s.label == ""
        assert s.min_value == 0
        assert s.max_value == 1000


# =============================================================================
# GetGrowthSettingsUseCase
# =============================================================================

class TestGetGrowthSettings:

    @pytest.mark.asyncio
    async def test_returns_all_settings(self):
        """Trả đúng 3 settings mặc định."""
        repo = InMemoryGrowthSettingsRepository(_default_settings())
        uc = GetGrowthSettingsUseCase(settings_repo=repo)
        result = await uc.execute()
        assert len(result) == 3
        keys = [s.key for s in result]
        assert "referral_discount" in keys
        assert "loyalty_threshold" in keys

    @pytest.mark.asyncio
    async def test_empty_repo(self):
        """Repo rỗng → trả list rỗng, không lỗi."""
        repo = InMemoryGrowthSettingsRepository([])
        uc = GetGrowthSettingsUseCase(settings_repo=repo)
        result = await uc.execute()
        assert result == []


# =============================================================================
# UpdateGrowthSettingUseCase
# =============================================================================

class TestUpdateGrowthSetting:

    @pytest.mark.asyncio
    async def test_update_valid_value(self):
        """Cập nhật referral_discount từ 5 lên 10 → thành công."""
        repo = InMemoryGrowthSettingsRepository(_default_settings())
        uc = UpdateGrowthSettingUseCase(settings_repo=repo)
        result = await uc.execute("referral_discount", 10, "admin")
        assert result.value == 10
        assert result.key == "referral_discount"

    @pytest.mark.asyncio
    async def test_update_nonexistent_key_raises_not_found(self):
        """Key không tồn tại → NotFoundError."""
        repo = InMemoryGrowthSettingsRepository(_default_settings())
        uc = UpdateGrowthSettingUseCase(settings_repo=repo)
        with pytest.raises(NotFoundError, match="không tồn tại"):
            await uc.execute("nonexistent", 10, "admin")

    @pytest.mark.asyncio
    async def test_update_value_above_max_raises_validation(self):
        """Giá trị vượt max → ValidationError."""
        repo = InMemoryGrowthSettingsRepository(_default_settings())
        uc = UpdateGrowthSettingUseCase(settings_repo=repo)
        with pytest.raises(ValidationError):
            await uc.execute("referral_discount", 999, "admin")

    @pytest.mark.asyncio
    async def test_update_value_below_min_raises_validation(self):
        """Giá trị dưới min → ValidationError."""
        repo = InMemoryGrowthSettingsRepository(_default_settings())
        uc = UpdateGrowthSettingUseCase(settings_repo=repo)
        # loyalty_threshold min=3
        with pytest.raises(ValidationError):
            await uc.execute("loyalty_threshold", 1, "admin")

    @pytest.mark.asyncio
    async def test_update_boundary_values_ok(self):
        """Giá trị đúng min hoặc max → OK."""
        repo = InMemoryGrowthSettingsRepository(_default_settings())
        uc = UpdateGrowthSettingUseCase(settings_repo=repo)
        # referral_discount: min=0, max=50
        r1 = await uc.execute("referral_discount", 0, "admin")
        assert r1.value == 0
        r2 = await uc.execute("referral_discount", 50, "admin")
        assert r2.value == 50


# =============================================================================
# GetReferralUseCase — đọc discount từ settings thay vì hardcode
# =============================================================================

class TestGetReferralWithSettings:

    @pytest.mark.asyncio
    async def test_uses_db_discount_value(self):
        """Khi settings_repo có giá trị → dùng giá trị từ DB."""
        from app.crm.domain.entities import Customer

        customer = Customer.create_from_order(
            phone="0399920878", name="Test", order_total=50,
        )
        settings = [GrowthSettingDTO(
            key="referral_discount", value=15,
            min_value=0, max_value=50, unit="k",
        )]

        uc = GetReferralUseCase(
            customer_repo=MockCustomerRepo(customer),
            referral_repo=MockReferralRepo(3),
            settings_repo=InMemoryGrowthSettingsRepository(settings),
        )
        result = await uc.execute("0399920878")

        assert result is not None
        assert result["discount_per_referral"] == 15
        assert result["referral_count"] == 3

    @pytest.mark.asyncio
    async def test_fallback_to_constant_without_settings(self):
        """Không có settings_repo → fallback về REFERRAL_DISCOUNT constant."""
        from app.crm.domain.entities import Customer

        customer = Customer.create_from_order(
            phone="0399920878", name="Test", order_total=50,
        )

        uc = GetReferralUseCase(
            customer_repo=MockCustomerRepo(customer),
            referral_repo=MockReferralRepo(0),
            settings_repo=None,
        )
        result = await uc.execute("0399920878")

        assert result is not None
        assert result["discount_per_referral"] == REFERRAL_DISCOUNT

    @pytest.mark.asyncio
    async def test_no_customer_returns_none(self):
        """Không tìm thấy customer → None."""
        uc = GetReferralUseCase(
            customer_repo=MockCustomerRepo(None),
            referral_repo=MockReferralRepo(0),
        )
        result = await uc.execute("0000000000")
        assert result is None
