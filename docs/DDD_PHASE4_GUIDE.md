# DDD Phase 4 — Growth Context: Migration Guide

## Tổng quan

Phase 4 chuyển toàn bộ `routers/growth.py` (523 dòng, 9 features) sang Growth Bounded Context theo DDD pattern.

**Kết quả:**
- `routers/growth.py` (523 dòng) → 9 files DDD (~750 dòng tổng cộng)
- Customer tracking handler migrate từ `ordering/application/event_handlers.py` → `growth/application/event_handlers.py`
- Frontend **KHÔNG ĐỔI** — response format giữ nguyên 100%

---

## Cấu trúc files mới

```
app/growth/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── entities.py           # Customer (aggregate root), Review, Referral, TrackingEvent
│   ├── value_objects.py      # LoyaltyPoints, ReferralCode, Rating + business constants
│   ├── events.py             # CustomerRewardEarned, ReviewSubmitted
│   └── services.py           # Repository ABCs + Service ABCs + DTOs
├── application/
│   ├── __init__.py
│   ├── use_cases.py          # 10 use cases (1 per endpoint)
│   └── event_handlers.py     # on_order_placed_track_customer (từ ordering)
├── infrastructure/
│   ├── __init__.py
│   └── repository.py         # SQL implementations cho tất cả ABCs
└── presentation/
    ├── __init__.py
    ├── router.py             # Thin FastAPI router (~120 dòng)
    └── schemas.py            # Pydantic schemas + response helpers
```

---

## Migration steps

### Step 1: Copy files
```bash
# Giả sử growth context đã nằm trong app/growth/
# Verify cấu trúc:
find app/growth -type f -name "*.py" | sort
```

### Step 2: Update main_ddd.py

**Thay đổi cần làm trong `main_ddd.py`:**

```python
# --- THÊM imports ---
from app.growth.application.event_handlers import create_customer_tracking_handler
from app.ordering.domain.events import OrderPlaced
from app.ordering.application.event_handlers import (
    on_order_placed_broadcast_ws,
    on_status_changed_broadcast_ws,
)
from app.ordering.domain.events import OrderStatusChanged

# --- UPDATE _wire_events() ---
def _wire_events():
    """Subscribe event handlers — called once at startup."""
    from app.database import async_session

    # Catalog events
    event_bus.subscribe(MenuChanged, on_menu_changed)

    # Ordering events → Growth (Phase 4: handler ĐÃ MOVE sang growth context)
    event_bus.subscribe(
        OrderPlaced,
        create_customer_tracking_handler(async_session)
    )

    # Ordering events → WS broadcast (vẫn ở ordering/event_handlers)
    event_bus.subscribe(OrderPlaced, on_order_placed_broadcast_ws)
    event_bus.subscribe(OrderStatusChanged, on_status_changed_broadcast_ws)

    logger.info("✅ Event handlers wired (Phase 4: Growth)")

# --- UPDATE router registration ---
# THAY:
#     from app.routers import growth
#     application.include_router(growth.router, prefix="/api/v1/growth", tags=["Growth"])
# BẰNG:
    from app.growth.presentation.router import router as growth_router
    application.include_router(growth_router, prefix="/api/v1/growth", tags=["Growth"])
```

### Step 3: Cleanup ordering event handlers

Trong `ordering/application/event_handlers.py`:
- **XÓA** `on_order_placed_track_customer` và `create_customer_tracking_handler`
  (đã move sang `growth/application/event_handlers.py`)
- **GIỮ** `on_order_placed_broadcast_ws` và `on_status_changed_broadcast_ws`
  (WS broadcast thuộc shared concern, chưa có notification context)

### Step 4: Verify

```bash
# API contract test — response phải giống hệt growth.py gốc
curl localhost:8000/api/v1/growth/config
curl localhost:8000/api/v1/growth/config?phone=0378148148
curl localhost:8000/api/v1/growth/upsell-stats
curl localhost:8000/api/v1/growth/customer?phone=0378148148
curl localhost:8000/api/v1/growth/referral?phone=0378148148
curl localhost:8000/api/v1/growth/cross-sell?product_ids=1,2,3
curl localhost:8000/api/v1/growth/reorder?phone=0378148148
curl -X POST localhost:8000/api/v1/growth/events -d '{"type":"test","feature":"test"}'
curl -X POST localhost:8000/api/v1/growth/reviews -d '{"rating":5,"order_id":1,"phone":"0378148148"}'

# Admin (cần JWT token):
curl -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/growth/analytics?days=7
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  localhost:8000/api/v1/growth/flags/upsell -d '{"enabled": true}'
```

---

## Mapping chi tiết: growth.py → DDD

| growth.py code | DDD location | Ghi chú |
|---|---|---|
| `LOYALTY_THRESHOLD = 10` | `domain/value_objects.py` | Constants tập trung |
| `REFERRAL_DISCOUNT = 5` | `domain/value_objects.py` | Constants tập trung |
| GET /config (30 dòng) | `use_cases.GetGrowthConfigUseCase` | Customer.to_summary() |
| POST /events (10 dòng) | `use_cases.LogTrackingEventUseCase` | TrackingEvent.create() |
| GET /upsell-stats (30 dòng) | `SqlUpsellStatsService` | SQL giữ nguyên |
| GET /reorder (25 dòng) | `SqlReorderService` | SQL giữ nguyên |
| GET /cross-sell (40 dòng) | `SqlCrossSellQueryService` | Algorithm giữ nguyên |
| GET /customer (15 dòng) | `use_cases.GetCustomerInfoUseCase` | Customer.to_summary() |
| POST /reviews (20 dòng) | `use_cases.SubmitReviewUseCase` | Review.create() validates |
| GET /referral (25 dòng) | `use_cases.GetReferralUseCase` | Customer.ensure_referral_code() |
| GET /analytics (100 dòng) | `SqlAnalyticsService` | SQL giữ nguyên 100% |
| PATCH /flags/{key} (15 dòng) | `use_cases.ToggleFeatureFlagUseCase` | Simple toggle |
| Customer tracking (orders.py) | `event_handlers.on_order_placed_track_customer` | Move từ ordering context |

---

## Rollback

Nếu cần rollback:
```python
# main_ddd.py — revert router registration:
from app.routers import growth
application.include_router(growth.router, prefix="/api/v1/growth", tags=["Growth"])

# Revert event handler wiring:
# Dùng lại ordering/application/event_handlers.py customer tracking handler
```

---

## Sau Phase 4: Ordering context cleanup

Sau khi Growth context hoạt động ổn định, cần cleanup `ordering/application/event_handlers.py`:

1. Xóa `on_order_placed_track_customer` (đã có bản chính ở growth)
2. Xóa `create_customer_tracking_handler` (đã có bản chính ở growth)
3. Giữ `on_order_placed_broadcast_ws` + `on_status_changed_broadcast_ws`

---

## Tiếp theo: Phase 5 — Kitchen + Identity

- **Kitchen**: thin context, chủ yếu reads (KDS display, queue management)
- **Identity**: extract JWT + bcrypt vào infrastructure, define service ABCs
- Ước tính: 1-2 ngày
