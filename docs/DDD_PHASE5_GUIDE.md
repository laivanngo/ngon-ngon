# DDD Phase 5 — Kitchen + Identity: Migration Guide

## Tổng quan

Phase 5 hoàn thành 2 context cuối cùng, kết thúc toàn bộ DDD migration.

| Context | Replaces | Endpoints |
|---------|----------|-----------|
| **Kitchen** | `routers/kds.py` (230 dòng) | POST /kds/auth, GET /kds/orders, PATCH /kds/orders/{id}/status |
| **Identity** | `services/__init__.py` + `middleware.py` | POST /admin/login + require_admin guard |

---

## Cấu trúc files

```
app/kitchen/
├── domain/
│   ├── entities.py           # KitchenOrder (read projection), KitchenOrderItem
│   └── services.py           # KitchenOrderRepository ABC, PinAuthService ABC
├── application/
│   └── use_cases.py          # GetKitchenQueueUseCase, KdsAuthUseCase
├── infrastructure/
│   └── repository.py         # SqlKitchenOrderRepository, ConfigPinAuthService
└── presentation/
    └── router.py             # Thin router (3 endpoints)

app/identity/
├── domain/
│   └── services.py           # PasswordHasher ABC, TokenService ABC
├── infrastructure/
│   └── auth.py               # BcryptPasswordHasher, JoseTokenService + singletons
└── presentation/
    ├── router.py             # POST /admin/login
    └── middleware.py          # require_admin guard
```

---

## Thay đổi quan trọng

### 1. Loại bỏ duplicate VALID_TRANSITIONS (Kitchen)

**TRƯỚC**: `kds.py` dòng 140-147 copy-paste VALID_TRANSITIONS từ `admin.py` dòng 150-157. Hai bản copy → sửa 1 quên 1 → bug.

**SAU**: KDS router gọi `Ordering's UpdateStatusUseCase` → `Order.change_status()` → `OrderStatus.can_transition_to()`. **1 chỗ duy nhất** trong `ordering/domain/value_objects.py`.

### 2. Auth qua ABCs (Identity)

**TRƯỚC**: `services/__init__.py` export free functions, mọi nơi import trực tiếp.

**SAU**: `PasswordHasher` ABC + `TokenService` ABC → implementations (`BcryptPasswordHasher`, `JoseTokenService`) → singletons. Đổi bcrypt sang argon2 chỉ sửa 1 file.

### 3. Backward compatibility

`identity/infrastructure/auth.py` export backward-compatible functions:
```python
# Các file chưa migrate vẫn dùng được:
from app.identity.infrastructure.auth import hash_password, verify_password
from app.identity.infrastructure.auth import create_access_token, decode_access_token
```

---

## Migration Steps

### Step 1: Wire routers trong main_ddd_phase5.py

```python
# Kitchen (thay kds.py)
from app.kitchen.presentation.router import router as kitchen_router
application.include_router(kitchen_router, prefix="/api/v1/kds", tags=["Kitchen"])

# Identity (thay admin login trong admin.py)
from app.identity.presentation.router import router as identity_router
application.include_router(identity_router, prefix="/api/v1/admin", tags=["Identity"])

# WS auth dùng identity singleton
from app.identity.infrastructure.auth import token_service
username = token_service.decode_token(ws_token)
```

### Step 2: Cleanup admin.py

Xóa khỏi `admin.py`:
- `POST /admin/login` → đã có ở `identity/presentation/router.py`
- Product/Category/Topping/CrossSell CRUD → đã có ở `catalog/presentation/admin_router.py`

**Giữ lại** trong `admin.py`:
- `GET /admin/orders` (pagination + filter — chưa có trong Ordering DDD router)
- `PATCH /admin/orders/{id}/status` (nên refactor sang dùng Ordering use case)
- `GET /admin/dashboard` (simple queries, chưa cần tách)

### Step 3: Verify

```bash
# KDS
curl -X POST localhost:8000/api/v1/kds/auth -d '{"pin":"1234"}'
curl "localhost:8000/api/v1/kds/orders?token=$TOKEN"
curl -X PATCH "localhost:8000/api/v1/kds/orders/$ID/status?token=$TOKEN" -d '{"status":"preparing"}'

# Admin login
curl -X POST localhost:8000/api/v1/admin/login -d '{"username":"admin","password":"admin123"}'

# Health check
curl localhost:8000/api/v1/health
```

---

## Tổng kết DDD Migration — All 5 Phases

### File count

| Phase | Context | New files | Old file replaced | Dòng cũ | Dòng mới |
|-------|---------|-----------|-------------------|---------|----------|
| 1 | Shared | 3 | database.py, config.py | ~60 | ~120 |
| 2 | Ordering | 8 | routers/orders.py | 342 | ~650 |
| 3 | Catalog | 10 | routers/menu.py + admin.py CRUD | ~400 | ~800 |
| 4 | Growth | 9 | routers/growth.py | 523 | ~750 |
| 5 | Kitchen | 5 | routers/kds.py | 230 | ~350 |
| 5 | Identity | 4 | services/ + middleware.py | 120 | ~250 |
| **Total** | **6 contexts** | **39 files** | **5 routers + 2 shared** | **~1,675** | **~2,920** |

### WHY dòng mới > dòng cũ:
- Comments, docstrings giải thích WHY (giáo dục, onboard dev mới)
- ABCs + DTOs (typed interfaces thay vì raw dict)
- Tests dễ viết hơn (domain test không cần DB)
- Mỗi file nhỏ, focused, dễ navigate

### Dependency Rule verified

```
Domain     → chỉ import từ chính nó + shared kernel
Application → import domain
Infrastructure → import domain + ORM models
Presentation → import application + infrastructure
```

Không có circular dependency. Domain layer hoàn toàn pure Python (no SQLAlchemy, no FastAPI).

### Tech debt còn lại (cập nhật)

1. ~~**admin.py orders/dashboard**: chưa refactor sang DDD use cases~~ → ✅ Đã migrate sang `ordering/presentation/admin_router.py`
2. ~~**Backward compat functions**: `app.services.*`, `app.middleware.require_admin`~~ → ✅ Đã xóa, dùng `identity/presentation/middleware.py`
3. ~~**ORM models**: tất cả contexts share `models.py`~~ → ✅ Đã tách ORM per context (xem `docs/CHANGELOG.md` v5.1.0)
4. **Event bus**: in-process — đổi sang Redis Pub/Sub khi scale workers

### Post-Phase 5 Improvements (v5.1.0)

Sau khi hoàn thành migration, 3 cải thiện chất lượng đã được thực hiện:
- 219 unit tests cho domain layer (không cần DB)
- Tách ORM models theo bounded context
- Dependency Injection tập trung (`dependencies.py` per context)

### Post-Phase 5 Improvements (v5.2.0)

- Feature flags đồng bộ admin ↔ frontend (Growth module là single source of truth)
- Admin reviews dashboard (tab ⭐ Đánh giá — xem, lọc, phân trang)
- Dọn sạch legacy duplicate (reorder, loyalty) khỏi `index.html`
- Fix luồng review: `order_public_id` resolution, `visibilitychange` re-trigger

Chi tiết: xem `docs/CHANGELOG.md`.

### Post-Phase 5 Improvements (v6.0.0 — Strict Modular Monolith)

Codebase đạt **100% ranh giới module** theo kiến trúc Ports & Adapters. Toàn bộ 18 cross-context ORM imports đã được thay thế bằng ports (interface) và adapters (implementation).

**Ports mới tạo:**

- `ordering/domain/catalog_port.py` — `CatalogPricingPort`: Ordering query giá sản phẩm từ Catalog
- `ordering/application/analytics_port.py` — `OrderAnalyticsPort`, `KitchenQueuePort`, `OrderCustomerLinkPort`: Growth và Kitchen query Ordering data
- `catalog/application/analytics_port.py` — `CatalogAnalyticsPort`: Growth và Ordering query Product metadata
- `kitchen/domain/ports.py` — `OrderStatusPort`: Kitchen yêu cầu Ordering cập nhật trạng thái đơn

**Adapters mới tạo (implement các ports trên):**

- `catalog/infrastructure/pricing_adapter.py` — `SqlCatalogPricingAdapter`
- `catalog/infrastructure/analytics_adapter.py` — `SqlCatalogAnalyticsAdapter`
- `ordering/infrastructure/kitchen_adapter.py` — `KitchenOrderStatusAdapter`
- `ordering/infrastructure/kitchen_queue_adapter.py` — `SqlKitchenQueueAdapter`
- `ordering/infrastructure/analytics_adapter.py` — `SqlOrderAnalyticsAdapter`, `SqlOrderCustomerLinkAdapter`

**Tech debt còn lại (cập nhật):**

1. ~~**admin.py orders/dashboard**~~ → ✅ Migrate sang DDD
2. ~~**ORM models tất cả share models.py**~~ → ✅ Tách per context
3. ~~**Cross-context ORM imports (18 violations)**~~ → ✅ 0 violations (v6.0.0)
4. `scripts/seed.py`, `tests/conftest.py` — vẫn dùng `app.models` shim (TODO: migrate trực tiếp)
5. **Event bus**: in-process — đổi sang Redis Pub/Sub khi scale workers

Chi tiết: xem `docs/CHANGELOG.md`.
