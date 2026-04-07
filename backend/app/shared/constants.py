"""
Shared Kernel — Constants
============================
Hằng số dùng chung giữa nhiều Bounded Contexts.

WHY tập trung constants tại đây:
- VN_PHONE_REGEX trước đây duplicate ở 3 nơi:
  app/schemas.py, ordering/presentation/schemas.py, ordering/domain/value_objects.py
- 1 chỗ duy nhất → sửa 1 lần, đúng khắp nơi
"""

import re

# =============================================================================
# Regex: Số điện thoại Việt Nam
# =============================================================================
# 0[3|5|7|8|9]xxxxxxxx — 10 chữ số, bắt đầu bằng 03/05/07/08/09
VN_PHONE_REGEX = re.compile(r"^0[35789]\d{8}$")
