"""
Identity Context — Infrastructure: Auth Implementation
=========================================================
Concrete implementations dùng bcrypt (password) + python-jose (JWT).

BcryptPasswordHasher: wrap passlib CryptContext.
JoseTokenService: wrap python-jose JWT encode/decode.

WHY giữ nguyên libraries (passlib + jose):
- Codebase hiện tại đã dùng, migration không cần đổi dependencies
- passlib tự handle salt, cost factor, deprecated scheme auto-upgrade
- jose lightweight, đủ cho HS256 JWT

BACKWARD COMPATIBILITY:
- hash_password() và verify_password() free functions vẫn hoạt động
  (delegate sang singleton instances)
- create_access_token() và decode_access_token() tương tự
- Các file chưa migrate (admin.py) vẫn import từ app.services → vẫn work

SINGLETONS:
- password_hasher: BcryptPasswordHasher (global instance)
- token_service: JoseTokenService (global instance)
Dùng qua import: `from app.identity.infrastructure.auth import token_service`
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.identity.domain.services import PasswordHasher, TokenService


# =============================================================================
# BcryptPasswordHasher
# =============================================================================
class BcryptPasswordHasher(PasswordHasher):
    """
    Password hashing dùng bcrypt via passlib.

    WHY deprecated="auto": tự động upgrade hash scheme khi cần.
    VD: nếu sau này đổi sang argon2, passlib tự re-hash khi user login.
    """

    def __init__(self) -> None:
        self._ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash(self, plain_password: str) -> str:
        return self._ctx.hash(plain_password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return self._ctx.verify(plain_password, hashed_password)


# =============================================================================
# JoseTokenService
# =============================================================================
class JoseTokenService(TokenService):
    """
    JWT token management dùng python-jose.

    Token payload:
    - sub: subject (username hoặc "kds")
    - exp: expiration time
    - iat: issued at

    Default expiry: settings.JWT_EXPIRE_MINUTES (60 phút).
    KDS override: settings.KDS_TOKEN_EXPIRE_HOURS (12 giờ).
    """

    def __init__(
        self,
        secret: str,
        algorithm: str,
        default_expire_minutes: int,
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._default_expire = timedelta(minutes=default_expire_minutes)

    def create_token(
        self,
        subject: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        expire = datetime.now(timezone.utc) + (expires_delta or self._default_expire)
        payload = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=[self._algorithm]
            )
            return payload.get("sub")
        except JWTError:
            return None


# =============================================================================
# Singletons — import từ bất kỳ đâu
# =============================================================================

# Password hasher (dùng bởi admin login, seed script)
password_hasher = BcryptPasswordHasher()

# Token service (dùng bởi admin login, KDS auth, middleware, WS auth)
token_service = JoseTokenService(
    secret=settings.JWT_SECRET,
    algorithm=settings.JWT_ALGORITHM,
    default_expire_minutes=settings.JWT_EXPIRE_MINUTES,
)


# =============================================================================
# Backward-compatible free functions
# =============================================================================
# Các file chưa migrate (admin.py, middleware.py ban đầu) vẫn dùng:
# Khi tất cả migrate xong → xóa free functions, import singleton trực tiếp.

def hash_password(plain: str) -> str:
    """Backward compat — delegate sang singleton."""
    return password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Backward compat — delegate sang singleton."""
    return password_hasher.verify(plain, hashed)


def create_access_token(
    subject: str, expires_delta: timedelta | None = None
) -> str:
    """Backward compat — delegate sang singleton."""
    return token_service.create_token(subject, expires_delta)


def decode_access_token(token: str) -> str | None:
    """Backward compat — delegate sang singleton."""
    return token_service.decode_token(token)
