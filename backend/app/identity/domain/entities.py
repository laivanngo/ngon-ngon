"""
Identity Context — Domain Entities
=====================================
Pure domain objects cho Identity context.

CurrentAdmin: Đại diện cho một admin đang đăng nhập (kết quả của require_admin).

WHY dataclass thay vì ORM model:
- Các context khác (Catalog, Ordering, Growth) cần biết "ai đang thao tác"
  nhưng KHÔNG cần biết schema DB của bảng admin_users.
- CurrentAdmin chỉ expose đúng data cần thiết: id + username.
- Đổi cấu trúc bảng admin_users không ảnh hưởng consumers.

TRƯỚC: AdminUser (SQLAlchemy ORM) bị leak ra 4 context khác.
SAU:   CurrentAdmin (pure dataclass) — context boundary rõ ràng.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentAdmin:
    """
    Immutable snapshot của admin đang được xác thực.

    frozen=True: không ai vô tình ghi đè id/username sau khi middleware trả về.
    """
    id: int
    username: str

    def __str__(self) -> str:
        return self.username
