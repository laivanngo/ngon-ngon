"""
Identity Context — Presentation: Login Router
=================================================
POST /admin/login — Admin đăng nhập → JWT token.

TRƯỚC: Login endpoint nằm trong admin.py (dòng 30-50) cùng với Order CRUD.
SAU: Login tách riêng vào Identity context.
     admin.py chỉ còn Order management + dashboard.

WHY login ở Identity (không phải Admin context):
- Authentication là cross-cutting concern
- Cùng token service dùng bởi admin, KDS, WS
- Đổi auth strategy (JWT → OAuth2) chỉ sửa Identity, không ảnh hưởng admin/kds
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.identity.infrastructure.auth import password_hasher, token_service
from app.identity.infrastructure.orm_models import AdminUser
from app.identity.presentation.schemas import LoginRequest, TokenResponse

logger = logging.getLogger("ngonngon.identity.router")
router = APIRouter()


# =============================================================================
# POST /admin/login
# =============================================================================
@router.post("/login", response_model=TokenResponse)
async def admin_login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Admin đăng nhập → nhận JWT token.

    WHY generic error message: không nói "user không tồn tại" vs "sai password"
    → attacker không biết username nào valid.
    """
    stmt = select(AdminUser).where(AdminUser.username == payload.username)
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()

    if not admin or not password_hasher.verify(payload.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng",
        )

    token = token_service.create_token(subject=admin.username)
    logger.info(f"🔐 Admin '{admin.username}' logged in")

    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )
