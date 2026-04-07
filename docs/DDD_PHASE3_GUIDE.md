# DDD Migration — Phase 3: Catalog Context — Hướng Dẫn Áp Dụng

## Tổng quan thay đổi

Phase 3 tạo ra **Catalog Bounded Context** — tách toàn bộ menu, product, category, topping, cross-sell, và time-deal ra khỏi `menu.py` và `admin.py`.

### Files mới: 20 files

```
backend/app/
├── shared/                                    ← Phase 1: Shared Kernel
│   ├── __init__.py
│   ├── events.py                              ← EventBus in-process
│   └── exceptions.py                          ← DomainError, NotFoundError, DuplicateError
│
├── catalog/                                   ← Phase 3: Catalog Context (MỚI)
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── entities.py                        ← Product, Category, Topping, CrossSellItem, TimeDeal
│   │   ├── value_objects.py                   ← Money, LayoutType
│   │   ├── repository.py                      ← ABCs: ProductRepo, CategoryRepo, ToppingRepo, etc.
│   │   ├── services.py                        ← CrossSellService (gợi ý logic)
│   │   └── events.py                          ← MenuChanged, ProductCreated, ProductUpdated
│   ├── application/
│   │   ├── __init__.py
│   │   ├── queries.py                         ← GetFullMenu, GetProduct, GetToppings, etc. + cache
│   │   ├── commands.py                        ← CreateProduct, UpdateProduct, CRUD commands
│   │   └── event_handlers.py                  ← on_menu_changed → WS broadcast
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   └── repository.py                      ← SqlProductRepo, SqlCategoryRepo (ORM mapping)
│   └── presentation/
│       ├── __init__.py
│       ├── router.py                          ← Public: GET /menu, /products, /toppings, etc.
│       ├── admin_router.py                    ← Admin: CRUD products/categories/toppings/cross-sell
│       └── schemas.py                         ← Pydantic request/response schemas
│
├── main_ddd.py                                ← main.py mới (swap routers + wire events)
│
├── routers/menu.py                            ← GIỮ NGUYÊN (không xóa, không import)
├── routers/admin.py                           ← GIỮ NGUYÊN (chưa xóa catalog CRUD — backward compat)
├── routers/orders.py                          ← GIỮ NGUYÊN (Phase 2)
├── routers/kds.py                             ← GIỮ NGUYÊN (Phase 5)
├── routers/growth.py                          ← GIỮ NGUYÊN (Phase 4)
├── models.py                                  ← GIỮ NGUYÊN (shared ORM)
├── schemas.py                                 ← GIỮ NGUYÊN (dùng bởi mọi context)
└── ...                                        ← Mọi thứ khác giữ nguyên
```

## Bước 1: Copy files

```bash
# Từ thư mục gốc project (nơi có docker-compose.yml)
# Nếu dùng tarball:
tar -xzf ddd-phase3.tar.gz

# Hoặc copy thủ công các thư mục shared/ và catalog/ vào backend/app/
```

## Bước 2: Swap main.py

```bash
cd backend/app

# Backup main.py cũ
cp main.py main_original.py

# Dùng main mới
cp main_ddd.py main.py
```

## Bước 3: Test

### Test nhanh — verify app khởi động

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Kiểm tra log phải thấy:
```
✅ Event handlers wired (Phase 3: Catalog)
🚀 Ngon-Ngon API started (DDD Phase 3)
```

### Test API — menu flow (NEW DDD router)

```bash
# 1. Health check
curl http://localhost:8000/api/v1/health

# 2. Menu (DDD) — giữ nguyên API contract
curl http://localhost:8000/api/v1/menu

# 3. Menu theo danh mục
curl http://localhost:8000/api/v1/menu/tra-sua

# 4. Chi tiết sản phẩm
curl http://localhost:8000/api/v1/products/ts1

# 5. Toppings
curl http://localhost:8000/api/v1/toppings

# 6. Time deals
curl http://localhost:8000/api/v1/time-deals

# 7. Cross-sell config
curl http://localhost:8000/api/v1/cross-sell-config
```

### Test API — admin catalog CRUD (NEW DDD router)

```bash
# Login (vẫn dùng admin.py cũ)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | jq -r .access_token)

# List products (DDD)
curl http://localhost:8000/api/v1/admin/products \
  -H "Authorization: Bearer $TOKEN"

# Create product (DDD)
curl -X POST http://localhost:8000/api/v1/admin/products \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"legacy_id": "test_ddd1", "category_id": 1, "name": "Test DDD", "base_price": 25}'

# List categories (DDD)
curl http://localhost:8000/api/v1/admin/categories \
  -H "Authorization: Bearer $TOKEN"

# List toppings (DDD)
curl http://localhost:8000/api/v1/admin/toppings \
  -H "Authorization: Bearer $TOKEN"

# List cross-sell (DDD)
curl http://localhost:8000/api/v1/admin/cross-sell \
  -H "Authorization: Bearer $TOKEN"
```

### Test — các route CHƯA migrate vẫn hoạt động

```bash
# Orders (old router — Phase 2)
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Test","phone":"0378148148","address":"123 Test","items":[{"product_id":1,"quantity":1}]}'

# Dashboard (old admin.py)
curl http://localhost:8000/api/v1/admin/dashboard \
  -H "Authorization: Bearer $TOKEN"

# Growth config (old growth.py)
curl http://localhost:8000/api/v1/growth/config
```

### Test WebSocket — menu change broadcast

1. Mở admin panel (kết nối WS)
2. Tạo/sửa sản phẩm qua DDD admin router
3. Verify admin panel nhận được `menu_update` notification

## Bước 4: Rollback (nếu cần)

```bash
cd backend/app
cp main_original.py main.py
```

App sẽ quay lại dùng old menu.py + admin.py. Files mới không ảnh hưởng.

---

## Gì thay đổi, gì giữ nguyên?

### THAY ĐỔI (Phase 3):
| Endpoint | Trước | Sau |
|----------|-------|-----|
| `GET /menu` | `menu.py` (inline SQL) | `catalog/presentation/router.py` → query → repo |
| `GET /menu/{slug}` | `menu.py` | catalog DDD |
| `GET /products/{id}` | `menu.py` | catalog DDD |
| `GET /toppings` | `menu.py` | catalog DDD |
| `GET /time-deals` | `menu.py` | catalog DDD |
| `GET /cross-sell-config` | `menu.py` | catalog DDD |
| `POST/PATCH/DELETE /admin/products` | `admin.py` | `catalog/presentation/admin_router.py` |
| `GET /admin/products` | `admin.py` | catalog DDD |
| `GET/POST/PATCH/DELETE /admin/categories` | `admin.py` | catalog DDD |
| `GET/POST/PATCH/DELETE /admin/toppings` | `admin.py` | catalog DDD |
| `GET/POST/PATCH/DELETE /admin/cross-sell` | `admin.py` | catalog DDD |
| Menu cache invalidation | `menu.py:invalidate_menu_cache()` | `catalog/application/queries.py` + EventBus |
| WS menu broadcast | `admin.py:_broadcast_menu_update()` | `MenuChanged` event → `on_menu_changed` handler |

### GIỮ NGUYÊN (chưa migrate):
- `POST /orders`, `GET /orders/{id}` → vẫn `orders.py` (Phase 2)
- `POST /admin/login` → vẫn `admin.py`
- `GET /admin/orders`, `PATCH /admin/orders/{id}/status` → vẫn `admin.py`
- `GET /admin/dashboard` → vẫn `admin.py`
- Tất cả KDS endpoints → vẫn `kds.py` (Phase 5)
- Tất cả growth endpoints → vẫn `growth.py` (Phase 4)
- Database schema → **KHÔNG thay đổi, KHÔNG cần migration**
- Frontend → **KHÔNG thay đổi** (API contract giữ nguyên)

---

## Kiến trúc DDD — Catalog Context

```
                    ┌─────────────────────────┐
                    │   Presentation Layer     │
                    │  router.py (public)      │
                    │  admin_router.py (CRUD)  │
                    │  schemas.py              │
                    └──────────┬──────────────┘
                               │ calls
                    ┌──────────▼──────────────┐
                    │   Application Layer      │
                    │  queries.py (reads)      │
                    │  commands.py (writes)    │
                    │  event_handlers.py       │
                    └──────────┬──────────────┘
                               │ uses ABCs
                    ┌──────────▼──────────────┐
                    │   Domain Layer           │
                    │  entities.py (behavior)  │
                    │  value_objects.py        │
                    │  repository.py (ABCs)    │
                    │  services.py             │
                    │  events.py               │
                    └──────────┬──────────────┘
                               │ implemented by
                    ┌──────────▼──────────────┐
                    │   Infrastructure Layer   │
                    │  repository.py (SQL)     │
                    │  (reuses app/models.py)  │
                    └─────────────────────────┘
```

**Dependency Rule:** Mũi tên chỉ đi XUỐNG. Domain không import presentation hay infrastructure.

---

## NOTE: admin.py duplicate routes

Vì admin.py vẫn được include, và catalog admin_router.py cũng được include
dưới cùng prefix `/api/v1/admin`, sẽ có 2 bộ routes cho catalog CRUD.
FastAPI sẽ dùng route được register **trước** (catalog DDD router đăng ký trước admin.py).

Khi Phase 3 ổn định, bạn có thể xóa các endpoint catalog CRUD khỏi admin.py
hoặc comment chúng ra. Hiện tại giữ cả hai để an toàn khi rollback.

---

## Phases tiếp theo

- **Phase 2: Ordering Context** — extract orders.py → ordering/
- **Phase 4: Growth Context** — extract growth.py → growth/
- **Phase 5: Kitchen + Identity** — extract kds.py + auth middleware
