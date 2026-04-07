"""
Promotions — Flag Read Adapter
==================================
Adapter cho CRM context đọc feature flags từ Promotions.

CRM cần flags cho /config endpoint (1 API call khi load trang).
Adapter implement CRM's FeatureFlagReadPort interface.

PATTERN: Port+Adapter cho cross-context communication.
CRM domain define interface (FeatureFlagReadPort).
Promotions infrastructure provide implementation.
CRM presentation wire qua dependencies.py.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crm.domain.services import FeatureFlagReadPort
from app.promotions.infrastructure.orm_models import FeatureFlag as ORMFeatureFlag


class SqlFeatureFlagReadAdapter(FeatureFlagReadPort):
    """Adapter: đọc feature flags từ Promotions DB cho CRM context."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_all_flags(self) -> dict[str, bool]:
        result = await self._db.execute(select(ORMFeatureFlag))
        return {f.key: f.enabled for f in result.scalars().all()}
