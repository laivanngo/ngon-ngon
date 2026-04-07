"""
Identity Context — Presentation: Auth Middleware
====================================================
require_admin dependency — bảo vệ tất cả admin endpoints.

Logic xác thực giữ nguyên 100%:
1. Extract Bearer token từ Authorization header
2. Decode JWT → lấy username (subject)
3. Query DB → verify admin vẫn tồn tại (tránh revoke lag)
4. Return CurrentAdmin — pure domain object, KHÔNG trả ORM model

THAY ĐỔI SO VỚI TRƯỚC:
- Return type: AdminUser (ORM) → CurrentAdmin (domain dataclass)
- Các context khác type-hint vào CurrentAdmin thay vì AdminUser
- Ranh giới rõ ràng: Identity sở hữu AdminUser ORM, chỉ expose CurrentAdmin

WHY vẫn query DB mỗi request:
- Admin bị xóa/deactivate → JWT vẫn valid cho đến khi expire
- 1 query nhỏ, có index trên username → <1ms, chấp nhận được
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.identity.domain.entities import CurrentAdmin
from app.identity.infrastructure.auth import token_service
from app.identity.infrastructure.orm_models import AdminUser

security = HTTPBearer(auto_error=False)


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentAdmin:
    """
    FastAPI dependency: xác thực JWT → trả CurrentAdmin.

    Raise HTTP 401 nếu:
    - Không có token (không đăng nhập)
    - Token invalid hoặc đã hết hạn
    - Admin không còn tồn tại trong DB
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần đăng nhập để truy cập",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = token_service.decode_token(credentials.credentials)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(AdminUser).where(AdminUser.username == username)
    result = await db.execute(stmt)
    admin_orm = result.scalar_one_or_none()

    if not admin_orm:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản admin không tồn tại",
        )

    # Convert ORM → domain entity trước khi trả ra ngoài Identity boundary
    return CurrentAdmin(id=admin_orm.id, username=admin_orm.username)
