"""
Identity Context — Domain Services (ABCs)
=============================================
Abstract interfaces cho authentication & authorization.

WHY Identity là Bounded Context riêng:
- Auth logic dùng chung bởi Admin router, KDS router, WS auth, middleware
- Đổi JWT → session chỉ sửa infrastructure, không ảnh hưởng consumers
- Password hashing strategy (bcrypt → argon2) thay đổi tại 1 chỗ

TRƯỚC: services/__init__.py chứa cả JWT lẫn bcrypt — flat, không có interface.
       middleware.py import trực tiếp từ services — tight coupling.
SAU: Domain define ABCs → Infrastructure implement → Consumers dùng qua interface.

DEPENDENCY RULE:
    Domain (ABCs) ← Infrastructure (bcrypt, jose) ← Presentation (router, middleware)
    Admin router, KDS router, WS auth đều dùng qua identity domain interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta


# =============================================================================
# PasswordHasher ABC
# =============================================================================
class PasswordHasher(ABC):
    """
    Interface cho password hashing.

    WHY ABC thay vì dùng bcrypt trực tiếp:
    - Đổi bcrypt → argon2: chỉ sửa implementation
    - Test: dùng PlainTextHasher (so sánh trực tiếp, không cần bcrypt lib)
    - Domain/application layer không biết thư viện hash nào đang dùng

    TRƯỚC: verify_password() và hash_password() là free functions ở services.py.
    SAU: PasswordHasher interface → BcryptPasswordHasher implementation.
    """

    @abstractmethod
    def hash(self, plain_password: str) -> str:
        """Hash password với random salt."""
        ...

    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """
        So sánh password plain với hash.
        Phải constant-time để chống timing attack.
        """
        ...


# =============================================================================
# TokenService ABC
# =============================================================================
class TokenService(ABC):
    """
    Interface cho token management (issue + verify).

    WHY ABC:
    - Đổi JWT → session token: chỉ sửa implementation
    - Test: dùng FakeTokenService (return subject ngay, không cần jose lib)
    - KDS dùng cùng TokenService nhưng custom expiry (12h thay vì 1h)

    TRƯỚC: create_access_token() và decode_access_token() là free functions.
    SAU: TokenService interface → JoseTokenService implementation.
    """

    @abstractmethod
    def create_token(
        self,
        subject: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        Tạo access token.

        Args:
            subject: identifier (username cho admin, "kds" cho bếp)
            expires_delta: custom expiry (None = dùng default từ config)

        Returns:
            Encoded token string
        """
        ...

    @abstractmethod
    def decode_token(self, token: str) -> str | None:
        """
        Decode token → trả về subject.
        Return None nếu token invalid hoặc expired.
        """
        ...
