# Ngon-Ngon — Architecture Constitution

> **AI phải đọc file này TRƯỚC KHI viết code.**

## Stack

Python 3.12 + FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16. JWT (python-jose) + bcrypt | Pydantic v2 | Alembic | Nginx | Docker Compose.

## Cấu trúc — Strict Modular Monolith với 6 Bounded Contexts

```
backend/app/
├── config.py                   ← Settings từ .env
├── database.py                 ← Engine + session (async)
├── models.py                   ← Deprecation shim (xem ghi chú)
├── schemas.py                  ← Deprecation shim (xem ghi chú)
├── ws_manager.py               ← Deprecation shim → shared/ws_manager.py
├── main.py                     ← App factory + event wiring
│
├── shared/                     ← Shared Kernel — dùng chung giữa tất cả contexts
│   ├── orm_models.py           ←   Base mixins (Timestamp, Tenant), Store model
│   ├── events.py               ←   EventBus (in-process pub/sub)
│   ├── exceptions.py           ←   Domain exceptions → HTTP status codes
│   ├── constants.py            ←   VN phone regex, shared constants
│   ├── utils.py                ←   sanitize_string, clean_phone
│   ├── value_objects.py        ←   Phone, Address, Money (shared value objects)
│   └── ws_manager.py           ←   WebSocket realtime (OrderWSManager singleton)
│
├── identity/                   ← Context: Auth (cross-cutting)
│   ├── domain/
│   │   ├── entities.py         ←   CurrentAdmin(id, username) — domain entity
│   │   └── services.py         ←   PasswordHasher, TokenService ABCs
│   ├── infrastructure/
│   │   ├── orm_models.py       ←   AdminUser (owned by Identity)
│   │   └── auth.py             ←   BcryptPasswordHasher, JoseTokenService
│   └── presentation/
│       ├── router.py           ←   POST /admin/login
│       ├── schemas.py          ←   LoginRequest, TokenResponse
│       └── middleware.py       ←   require_admin → returns CurrentAdmin
│
├── catalog/                    ← Context: Menu, sản phẩm
│   ├── domain/                 ←   Entities, value objects, repository ABCs, events
│   ├── application/
│   │   ├── commands.py         ←   Product/Category/Topping CRUD commands
│   │   ├── queries.py          ←   Menu queries
│   │   ├── event_handlers.py   ←   MenuChanged → WS broadcast
│   │   └── analytics_port.py   ←   CatalogAnalyticsPort (outbound port)
│   ├── infrastructure/
│   │   ├── orm_models.py       ←   Category, Product, Topping, TimeDeal...
│   │   ├── repository.py       ←   SQL implementations
│   │   ├── pricing_adapter.py  ←   SqlCatalogPricingAdapter (implements ordering port)
│   │   └── analytics_adapter.py ←  SqlCatalogAnalyticsAdapter (implements analytics port)
│   └── presentation/
│       ├── dependencies.py     ←   Use case factories
│       ├── router.py           ←   Public menu endpoints
│       ├── admin_router.py     ←   Admin CRUD (uses CurrentAdmin)
│       └── schemas.py          ←   ProductResponse, MenuResponse... (self-contained)
│
├── ordering/                   ← Context: Đơn hàng
│   ├── domain/
│   │   ├── entities.py         ←   Order aggregate root
│   │   ├── value_objects.py    ←   OrderStatus, Phone, Address
│   │   ├── events.py           ←   OrderPlaced, OrderStatusChanged
│   │   ├── services.py         ←   PricingService ABC, OrderRepository ABC
│   │   └── catalog_port.py     ←   CatalogPricingPort (outbound port)
│   ├── application/
│   │   ├── use_cases.py        ←   PlaceOrder, UpdateStatus, GetOrder, Dashboard
│   │   ├── event_handlers.py   ←   WS broadcast handlers
│   │   └── analytics_port.py   ←   OrderAnalyticsPort, KitchenQueuePort,
│   │                           ←   OrderCustomerLinkPort, KitchenOrderData DTOs
│   ├── infrastructure/
│   │   ├── orm_models.py       ←   Order, OrderItem, OrderStatus
│   │   ├── repository.py       ←   SqlOrderRepository, SqlDashboardQueryService
│   │   ├── pricing.py          ←   SqlPricingService (uses CatalogPricingPort)
│   │   ├── kitchen_adapter.py  ←   KitchenOrderStatusAdapter (implements kitchen port)
│   │   ├── kitchen_queue_adapter.py ← SqlKitchenQueueAdapter (implements KitchenQueuePort)
│   │   └── analytics_adapter.py ←  SqlOrderAnalyticsAdapter + SqlOrderCustomerLinkAdapter
│   └── presentation/
│       ├── dependencies.py     ←   Use case factories (wires adapters)
│       ├── router.py           ←   POST /orders, GET /orders/{id}
│       ├── admin_router.py     ←   Admin: list, update status, dashboard
│       └── schemas.py          ←   OrderCreate, OrderResponse (self-contained)
│
├── growth/                     ← Context: CRM, loyalty, analytics
│   ├── domain/                 ←   Customer, Review, Referral aggregates
│   ├── application/            ←   12 use cases
│   ├── infrastructure/
│   │   ├── orm_models.py       ←   Customer, Event, Review, FeatureFlag...
│   │   └── repository.py       ←   SQL implementations (uses OrderAnalyticsPort,
│   │                           ←   CatalogAnalyticsPort — không import ORM khác)
│   └── presentation/
│       ├── dependencies.py     ←   Use case factories (wires analytics adapters)
│       ├── router.py           ←   9 growth endpoints
│       └── schemas.py
│
└── kitchen/                    ← Context: KDS bếp
    ├── domain/
    │   ├── entities.py         ←   KitchenOrder projection
    │   ├── services.py         ←   KitchenOrderRepository, PinAuthService ABCs
    │   └── ports.py            ←   OrderStatusPort (inbound port)
    ├── application/            ←   GetKitchenQueue, KdsAuth use cases
    ├── infrastructure/
    │   └── repository.py       ←   SqlKitchenOrderRepository (uses KitchenQueuePort),
    │                           ←   ConfigPinAuthService
    └── presentation/
        ├── dependencies.py     ←   Wires OrderStatusPort + KitchenQueuePort adapters
        └── router.py           ←   GET /kds/orders, PATCH status, POST auth
```

## Ports & Adapters — Ranh Giới Giữa Contexts

**Nguyên tắc cốt lõi:** Không context nào được import ORM, repository, hay infrastructure của context khác. Mọi giao tiếp cross-context đều qua ports (interface) và adapters (implementation).

```
Context A              Port/Adapter Layer              Context B
─────────────         ──────────────────────         ─────────────
Ordering              CatalogPricingPort               Catalog
  SqlPricingService ──→ (ordering/domain)            ←── SqlCatalogPricingAdapter
                                                          (catalog/infrastructure)

Growth                OrderAnalyticsPort               Ordering
  SqlAnalyticsService ──→ (ordering/application)     ←── SqlOrderAnalyticsAdapter
  SqlReorderService   ──→                            ←── (ordering/infrastructure)
  SqlCrossSellService ──→                            ←──

Growth                CatalogAnalyticsPort             Catalog
  SqlCrossSellService ──→ (catalog/application)      ←── SqlCatalogAnalyticsAdapter
                                                          (catalog/infrastructure)

Kitchen               OrderStatusPort                  Ordering
  router              ──→ (kitchen/domain/ports.py)   ←── KitchenOrderStatusAdapter
                                                          (ordering/infrastructure)

Kitchen               KitchenQueuePort                 Ordering
  SqlKitchenOrderRepo ──→ (ordering/application)      ←── SqlKitchenQueueAdapter
                                                          (ordering/infrastructure)
```

## ORM Model Ownership

M��i bounded context sở hữu ORM models trong `infrastructure/orm_models.py`. **Không context nào được import ORM của context khác trực tiếp.**

| Context | orm_models.py chứa |
|---------|---------------------|
| **Shared** | TimestampMixin, TenantMixin, Store |
| **Catalog** | Category, Product, ProductSize, Topping, ProductTopping, CrossSellItem, TimeDeal |
| **Ordering** | Order, OrderItem, OrderStatus |
| **Growth** | Customer, FeatureFlag, Event, Review, PushSubscription, LoyaltyReward, Referral |
| **Identity** | AdminUser |

**`app/models.py`** và **`app/schemas.py`** là deprecation shims — chỉ còn dùng bởi `scripts/seed.py` và `tests/` cũ. Không được import trong bất kỳ context nào.

## Identity — Cross-Cutting Auth

`require_admin` dependency trong `identity/presentation/middleware.py` trả về `CurrentAdmin(id, username)` — một pure domain entity, không phải ORM model. Các routers trong Catalog, Ordering, Growth type-hint vào `CurrentAdmin`. Không có context nào được import `AdminUser` ORM.

## Dependency Injection

M��i context có `presentation/dependencies.py` — nơi duy nhất wire implementations vào interfaces. Router chỉ nhận Depends(), không biết class nào đang chạy bên dưới.

```python
# Ví dụ wiring trong ordering/presentation/dependencies.py
def get_place_order(db: AsyncSession = Depends(get_db)) -> PlaceOrderUseCase:
    return PlaceOrderUseCase(
        pricing_service=SqlPricingService(
            catalog_port=SqlCatalogPricingAdapter(db),  # Catalog adapter
        ),
        order_repo=SqlOrderRepository(db),
        event_bus=event_bus,
    )
```

## Event Bus — Cross-Context Communication

Ordering phát `OrderPlaced` → EventBus → Growth lắng nghe. Ordering không biết Growth tồn tại. Wiring ở `main.py`:

```
OrderPlaced        → on_order_placed_track_customer  (Growth: CRM)
OrderPlaced        → on_order_placed_broadcast_ws    (Shared: WS)
OrderStatusChanged → on_status_changed_broadcast_ws  (Shared: WS)
MenuChanged        → on_menu_changed                 (Shared: WS)
```

## Multi-Tenant (SaaS Foundation)

Bảng `stores` chứa thông tin quán. `TenantMixin` tự động thêm `store_id` FK. Giai đoạn 1: store_id default = 1. Giai đoạn 2: bật RLS + thêm tenant middleware.

## Quy Tắc Cho AI

Khi thêm tính năng mới, tuân thủ nghiêm ngặt:

1. **Thêm model mới** → thêm vào `infrastructure/orm_models.py` của context phù hợp. Tuyệt đối KHÔNG thêm vào `models.py`.
2. **Thêm use case mới** → thêm factory vào `presentation/dependencies.py`. Router KHÔNG import `Sql*` trực tiếp.
3. **Cross-context data** → tạo port (ABC) trong context cần data, tạo adapter trong context sở hữu data. KHÔNG import ORM trực tiếp.
4. **Auth** → dùng `require_admin` từ `identity/presentation/middleware.py`, type-hint vào `CurrentAdmin`.
5. **Schemas** → mỗi context có `presentation/schemas.py` riêng. KHÔNG import từ `app/schemas.py`.
6. **WebSocket** → import từ `app.shared.ws_manager`, không từ `app.ws_manager`.
7. Comment **WHY**, không comment WHAT.
8. KHÔNG refactor nếu không có bug hoặc requirement mới.

## Best Practices Bất Biến

Server-side pricing (không tin giá client) | XSS sanitization (domain layer) | Soft delete (is_active) | UUID public order ID | Menu cache 5 phút + selectinload (chống N+1) | Docker resource limits | Nginx rate limiting + security headers + gzip | Entrypoint migration + retry loop | PWA + Service Worker offline.

## Testing

Unit tests (219): `tests/unit/` — test domain entities, không cần DB, chạy trong ~0.6s.

```bash
# Unit tests
cd backend && PYTHONPATH=. python -m pytest tests/unit/ --noconftest -v

# Integration tests (cần Docker + DB)
PYTHONPATH=. python -m pytest tests/ -v
```
