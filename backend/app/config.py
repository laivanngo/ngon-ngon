"""
Configuration — Type-safe settings from environment variables
==============================================================
WHY Pydantic Settings thay vì os.getenv():
1. Type validation: DATABASE_URL phải là string, không phải None
2. Default values: development-friendly defaults, production requires explicit set
3. .env file support: auto-load .env cho local dev
4. Single source of truth: import settings từ bất kỳ đâu
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://ngonngon:ngonngon@localhost:5432/ngonngon"

    # --- Security ---
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60  # Token hết hạn sau 1 giờ

    # --- CORS ---
    ALLOWED_ORIGINS: str = "http://localhost,http://localhost:3000"

    # --- Environment ---
    ENV: str = "development"  # development | staging | production

    # --- Admin seed ---
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"  # Chỉ dùng cho seed lần đầu

    # --- KDS (Kitchen Display System) ---
    KDS_PIN: str = "1234"               # PIN 4 số cho bếp — đổi trong .env
    KDS_TOKEN_EXPIRE_HOURS: int = 12    # KDS token sống lâu hơn admin (treo cả ngày)

    # --- Zalo (optional) ---
    ZALO_OA_ACCESS_TOKEN: str = ""
    ZALO_OA_PHONE: str = "0378148148"

    # --- Multi-tenant (v3: SaaS foundation) ---
    # WHY: Giai đoạn 1 chỉ có 1 quán. Mọi data gắn với store_id này.
    # Khi thêm quán mới, resolve store_id từ subdomain/header thay vì dùng default.
    DEFAULT_STORE_ID: int = 1

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated origins string thành list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True  # DATABASE_URL ≠ database_url


# Singleton instance — import settings ở bất kỳ đâu
settings = Settings()
