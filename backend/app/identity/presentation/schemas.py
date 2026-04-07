"""
Identity Context — Presentation Schemas
==========================================
Pydantic models cho Login endpoint.

TRƯỚC: LoginRequest + TokenResponse khai báo inline trong router.py.
SAU:   Tách ra file riêng → router.py thuần HTTP logic.
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
