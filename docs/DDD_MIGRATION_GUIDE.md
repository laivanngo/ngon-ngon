# DDD Migration — Phase 1+2: Hướng Dẫn Áp Dụng

## Tổng quan thay đổi

Phase 1+2 tạo ra **13 file mới** và **1 file main.py thay thế**:

```
backend/app/
├── shared/                          ← Phase 1: Shared Kernel (MỚI)
│   ├── __init__.py
│   ├── events.py                    ← EventBus in-process
│   └── exceptions.py               ← DomainError hierarchy
│
├── ordering/                        ← Phase 2: Ordering Context (MỚI)
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── entities.py              ← Order aggregate root (rich model)
│   │   ├── value_objects.py         ← OrderStatus + transitions, Phone, Address, Money
│   │   ├── events.py                ← OrderPlaced, OrderStatusChanged
│   │   └── services.py              ← PricingService ABC, OrderRepository ABC
│   ├── application/
│   │   ├── __init__.py
│   │   ├── use_cases.py             ← PlaceOrder, UpdateStatus, GetOrder
│   │   └── event_handlers.py        ← Customer tracking + WS broadcast
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── repository.py            ← SqlOrderRepository (ORM mapping)
│   │   └── pricing.py               ← SqlPricingService (product/topping/deal lookup)
│   └── presentation/
│       ├── __init__.py
│       ├── router.py                ← Thin router (60 dòng vs 342 dòng cũ)
│       └── schemas.py               ← OrderCreate, OrderResponse
│
├── main_ddd.py                      ← main.py mới (swap router + wire events)
│
├── routers/orders.py                ← GIỮ NGUYÊN (không xóa, không import)
├── routers/admin.py                 ← GIỮ NGUYÊN (chưa migrate)
├── routers/kds.py                   ← GIỮ NGUYÊN (chưa migrate)
├── routers/menu.py                  ← GIỮ NGUYÊN (Phase 3)
├── routers/growth.py                ← GIỮ NGUYÊN (Phase 4)
├── models.py                        ← GIỮ NGUYÊN (shared ORM)
├── schemas.py                       ← GIỮ NGUYÊN (dùng bởi admin/kds/growth)
└── ...                              ← Mọi thứ khác giữ nguyên
```

## Bước 1: Giải nén

```bash
# Từ thư mục gốc project (nơi có docker-compose.yml)
tar -xzf ddd-phase1-2.tar.gz
```

Lệnh này sẽ tạo các thư mục `shared/` và `ordering/` bên trong `backend/app/`,
và tạo file `main_ddd.py` cạnh `main.py` hiện tại.

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
# Trong container hoặc local
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Kiểm tra log phải thấy:
```
✅ Event handlers wired
🚀 Ngon-Ngon API started (DDD Phase 1+2)
```

### Test API — ordering flow

```bash
# 1. Health check
curl http://localhost:8000/api/v1/health

# 2. Menu vẫn hoạt động (old router, không thay đổi)
curl http://localhost:8000/api/v1/menu

# 3. Tạo đơn hàng (NEW DDD router)
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Test DDD",
    "phone": "0378148148",
    "address": "123 Test Street",
    "delivery_type": "immediate",
    "items": [{"product_id": 1, "quantity": 1}]
  }'

# 4. Tra cứu đơn hàng (dùng public_id từ response trên)
curl http://localhost:8000/api/v1/orders/{public_id}

# 5. Admin login vẫn hoạt động (old router)
curl -X POST http://localhost:8000/api/v1/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# 6. Growth config vẫn hoạt động (old router)
curl http://localhost:8000/api/v1/growth/config
```

### Test WebSocket — verify WS broadcast qua EventBus

Mở admin panel → tạo đơn hàng → verify admin panel nhận được notification.

## Bước 4: Rollback (nếu cần)

```bash
cd backend/app
cp main_original.py main.py
```

App sẽ quay lại dùng old ordering router. Các file mới không ảnh hưởng
(chúng chỉ là code chưa được import).

## Gì thay đổi, gì giữ nguyên?

### THAY ĐỔI (Phase 1+2):
- `POST /orders` → đi qua DDD: router → use case → pricing service → repository → events
- `GET /orders/{id}` → đi qua DDD: router → use case → repository
- `GET /orders/{id}/zalo-text` → đi qua DDD
- Customer tracking → qua EventBus (OrderPlaced event)
- WS broadcast → qua EventBus (OrderPlaced + OrderStatusChanged events)
- Status transitions → sống trong `OrderStatus.can_transition_to()` (1 chỗ duy nhất)

### GIỮ NGUYÊN (chưa migrate):
- `PATCH /admin/orders/{id}/status` → vẫn dùng admin.py trực tiếp (Phase 3+)
- `PATCH /kds/orders/{id}/status` → vẫn dùng kds.py trực tiếp (Phase 5)
- Tất cả menu endpoints → vẫn dùng menu.py (Phase 3)
- Tất cả growth endpoints → vẫn dùng growth.py (Phase 4)
- Tất cả admin CRUD endpoints → vẫn dùng admin.py (Phase 3)
- Database schema → KHÔNG thay đổi, KHÔNG cần migration
- Frontend → KHÔNG thay đổi (API contract giữ nguyên)

## Phases tiếp theo

- **Phase 3: Catalog Context** — extract menu.py + admin product CRUD
- **Phase 4: Growth Context** — extract growth.py, customer tracking handler di chuyển vào đây
- **Phase 5: Kitchen + Identity** — extract kds.py + auth middleware
