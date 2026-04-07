"""
Shared Kernel — Domain Exceptions
====================================
Các exception dùng chung giữa tất cả Bounded Contexts.

WHY custom exceptions thay vì raise ValueError:
- Router có thể catch DomainError → trả HTTP 400
- Phân biệt lỗi domain (business rule) vs lỗi hệ thống (500)
- Error message tiếng Việt, thân thiện với end user
"""


class DomainError(Exception):
    """Base class cho tất cả lỗi business logic."""

    def __init__(self, message: str = "Lỗi domain", code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainError):
    """Entity không tồn tại. Router map → 404."""

    def __init__(self, message_or_entity: str = "Không tìm thấy", identifier: str = ""):
        if identifier:
            message = f"{message_or_entity} '{identifier}' không tìm thấy"
        else:
            message = message_or_entity
        super().__init__(message, code="NOT_FOUND")


class ValidationError(DomainError):
    """Input không hợp lệ (business rule violation)."""

    def __init__(self, message: str = "Dữ liệu không hợp lệ"):
        super().__init__(message, code="VALIDATION_ERROR")


class DuplicateError(DomainError):
    """Entity đã tồn tại. Router map → 409."""

    def __init__(self, entity: str = "Entity", identifier: str = ""):
        detail = f"{entity} đã tồn tại"
        if identifier:
            detail = f"{entity} '{identifier}' đã tồn tại"
        super().__init__(detail, code="DUPLICATE")


class InvalidStatusTransitionError(DomainError):
    """Chuyển trạng thái đơn hàng không hợp lệ."""

    def __init__(self, current: str, target: str, allowed: list[str]):
        allowed_str = ", ".join(allowed) if allowed else "không có"
        message = (
            f"Không thể chuyển từ '{current}' sang '{target}'. "
            f"Cho phép: {allowed_str}"
        )
        super().__init__(message, code="INVALID_STATUS_TRANSITION")
