"""
Shared Kernel — Utilities
============================
Utility functions dùng chung giữa nhiều Bounded Contexts.

WHY tập trung tại đây:
- sanitize_string: trước đây duplicate ở 3 nơi → 1 source of truth
- clean_phone: trước đây duplicate ở 8 nơi → 1 source of truth
"""

import html
import re


def sanitize_string(value: str | None) -> str | None:
    """
    Strip HTML tags + escape special chars from user input.
    XSS prevention — defense in depth.

    Args:
        value: Raw user input string

    Returns:
        Sanitized string, or None if input is None/empty.
    """
    if not value:
        return value
    clean = re.sub(r"<[^>]+>", "", value)
    return html.escape(clean.strip(), quote=True)


def clean_phone(phone: str) -> str:
    """
    Chuẩn hóa SĐT: bỏ dấu chấm, khoảng trắng, gạch ngang.

    "0378.148.148" → "0378148148"
    "0378 148 148" → "0378148148"
    "0378-148-148" → "0378148148"

    WHY tập trung tại đây:
    Logic này trước đây copy-paste ở 8 nơi trong dự án.
    Sửa 1 nơi = đúng khắp nơi.
    """
    return phone.replace(" ", "").replace(".", "").replace("-", "")
