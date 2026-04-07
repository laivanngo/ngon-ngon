# Ngon-Ngon — Ứng dụng đặt trà sữa & đồ ăn vặt

## Kiến trúc

Strict Modular Monolith theo Domain-Driven Design với 6 Bounded Contexts và Ports & Adapters pattern. Không có context nào import ORM của context khác — mọi giao tiếp cross-context đều qua interface (port) và implementation (adapter).

| Context | Trách nhiệm |
|---------|-------------|
| **Identity** | JWT auth, bcrypt password, admin login, KDS PIN |
| **Catalog** | Menu, sản phẩm, danh mục, topping, cross-sell, time deal |
| **Ordering** | Đặt hàng, tính giá, lifecycle đơn hàng |
| **Growth** | Loyalty, referral, review, analytics, feature flags |
| **Kitchen** | KDS display, queue bếp, PIN auth |
| **Shared** | EventBus, domain exceptions, ORM base mixins, WebSocket manager |

## Quick Start

```bash
# 1. Cấu hình
cp .env.example .env
# Sửa .env: DB_PASSWORD, JWT_SECRET

# 2. Chạy
docker compose up -d

# 3. Truy cập
# Customer app: http://localhost
# Admin panel:  http://localhost/admin.html
# KDS:          http://localhost/kds.html
# API docs:     http://localhost/api/docs
```

## Chạy Unit Tests

```bash
cd backend
pip install pytest
PYTHONPATH=. python -m pytest tests/unit/ --noconftest -v
# 219 tests, ~0.6s, không cần database
```

## Cấu trúc thư mục

```
backend/app/
├── catalog/                # Menu, sản phẩm
│   ├── domain/             #   Entities, value objects, repository ABCs
│   ├── application/        #   Commands (CRUD), queries (menu), analytics_port.py
│   ├── infrastructure/     #   SQL repositories, orm_models.py,
│   │                       #   pricing_adapter.py, analytics_adapter.py
│   └── presentation/       #   Routers, schemas (self-contained), dependencies.py
├── ordering/               # Đơn hàng
│   ├── domain/             #   Order aggregate, status transitions,
│   │                       #   catalog_port.py (CatalogPricingPort)
│   ├── application/        #   Use cases, analytics_port.py
│   │                       #   (OrderAnalyticsPort, KitchenQueuePort...)
│   ├── infrastructure/     #   SQL repositories, pricing.py,
│   │                       #   kitchen_adapter.py, kitchen_queue_adapter.py,
│   │                       #   analytics_adapter.py
│   └── presentation/       #   Routers, schemas, dependencies.py
├── growth/                 # CRM, loyalty, analytics
│   ├── domain/             #   Customer aggregate, loyalty, referral
│   ├── application/        #   12 use cases
│   ├── infrastructure/     #   SQL repositories (dùng OrderAnalyticsPort,
│   │                       #   CatalogAnalyticsPort — không import ORM khác)
│   └── presentation/       #   Router, schemas, dependencies.py
├── kitchen/                # KDS bếp
│   ├── domain/             #   KitchenOrder projection, ports.py (OrderStatusPort)
│   ├── application/        #   Queue + auth use cases
│   ├── infrastructure/     #   SqlKitchenOrderRepository (dùng KitchenQueuePort)
│   └── presentation/       #   Router, dependencies.py
├── identity/               # Auth (cross-cutting concern)
│   ├── domain/             #   CurrentAdmin dataclass, PasswordHasher/TokenService ABCs
│   ├── infrastructure/     #   Auth implementation, orm_models.py (AdminUser)
│   └── presentation/       #   Login router, middleware (trả CurrentAdmin)
├── shared/                 # Dùng chung
│   ├── events.py           #   EventBus (in-process pub/sub)
│   ├── exceptions.py       #   Domain exceptions → HTTP status codes
│   ├── orm_models.py       #   Base mixins (Timestamp, Tenant), Store model
│   ├── ws_manager.py       #   WebSocket realtime (OrderWSManager singleton)
│   ├── constants.py        #   VN phone regex, shared constants
│   └── utils.py            #   sanitize_string, clean_phone
├── models.py               # Deprecation shim (chỉ dùng bởi scripts/, tests/ cũ)
├── schemas.py              # Deprecation shim (chỉ dùng bởi scripts/, tests/ cũ)
├── ws_manager.py           # Deprecation shim → shared/ws_manager.py
└── main.py                 # App factory + event wiring

backend/tests/
├── unit/                   # 219 unit tests — không cần DB
├── conftest.py             # Integration test fixtures (cần DB)
├── test_menu.py            # Integration: menu API
└── test_orders.py          # Integration: order + admin API

frontend/
├── index.html        # Customer ordering app (PWA)
├── admin.html        # Admin panel
├── kds.html          # Kitchen Display System
├── src/              # ES Modules (shared/, admin/, customer/, kds/)
├── css/              # Stylesheets
├── vite.config.js    # Vite build tool config
└── package.json      # npm dependencies
```

## Key Design Decisions

**Ports & Adapters:** Mỗi giao tiếp cross-context đều qua port (interface) và adapter (implementation). Ví dụ: khi Ordering tính giá, nó không biết Catalog tồn tại — chỉ gọi `CatalogPricingPort.get_product()`. Catalog cung cấp `SqlCatalogPricingAdapter` implement port đó.

**ORM Model Ownership:** Mỗi context sở hữu ORM models riêng trong `infrastructure/orm_models.py`. Không context nào được import ORM của context khác. `app/models.py` chỉ là deprecation shim cho scripts và tests cũ.

**Identity Boundary:** `require_admin` middleware trả `CurrentAdmin(id, username)` — pure dataclass, không phải ORM. Các context khác không biết `AdminUser` ORM tồn tại.

**Dependency Injection:** Mỗi context có `presentation/dependencies.py` — nơi duy nhất wire adapters vào ports. Router chỉ nhận `Depends()`, không biết implementation nào đang chạy.

**Event-Driven:** Ordering phát `OrderPlaced` → Growth subscribe để track customer, Shared WS subscribe để push realtime. Hai context không import lẫn nhau.

## API Endpoints (47 routes)

**Public:** `GET /api/v1/menu`, `POST /api/v1/orders`, `GET /api/v1/orders/{id}`, `GET /api/v1/growth/config`, `GET /api/v1/growth/cross-sell` và các growth endpoints khác.

**Admin (JWT required):** `POST /api/v1/admin/login`, `GET /api/v1/admin/orders`, `GET /api/v1/admin/dashboard`, `GET /api/v1/growth/analytics`, `GET /api/v1/growth/reviews/list`, CRUD products/categories/toppings/cross-sell/feature flags.

**KDS (PIN required):** `POST /api/v1/kds/auth`, `GET /api/v1/kds/orders`, `PATCH /api/v1/kds/orders/{id}/status`.

## Tech Stack

Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL | Vanilla JS, PWA, Service Worker | Docker Compose, Nginx | pytest (219 unit tests).

## Quick Start

```bash
# 1. Clone và cấu hình
cp .env.example .env
# Sửa .env: DB_PASSWORD, JWT_SECRET

# 2. Chạy
docker compose up -d

# 3. Truy cập
# Customer app: http://localhost
# Admin panel:  http://localhost/admin.html
# KDS:          http://localhost/kds.html
# API docs:     http://localhost/api/docs
```

## Chạy Unit Tests

```bash
cd backend
pip install pytest
PYTHONPATH=. python -m pytest tests/unit/ --noconftest -v
# 219 tests, ~0.6s, không cần database
```

## Cấu trúc thư mục

```
backend/app/
├── catalog/                # Menu, sản phẩm
│   ├── domain/             #   Entities, value objects, repository ABCs
│   ├── application/        #   Commands (CRUD), queries (menu)
│   ├── infrastructure/     #   SQL repositories, orm_models.py
│   └── presentation/       #   Routers, schemas, dependencies.py
├── ordering/               # Đơn hàng
│   ├── domain/             #   Order aggregate, status transitions, pricing ABC
│   ├── application/        #   PlaceOrder, UpdateStatus use cases
│   ├── infrastructure/     #   SQL repositories, pricing, orm_models.py
│   └── presentation/       #   Routers, schemas, dependencies.py
├── growth/                 # CRM, loyalty, analytics
│   ├── domain/             #   Customer aggregate, loyalty, referral
│   ├── application/        #   12 use cases (config, events, reviews, admin reviews list...)
│   ├── infrastructure/     #   SQL repositories, orm_models.py
│   └── presentation/       #   Router, schemas, dependencies.py
├── kitchen/                # KDS bếp
│   ├── domain/             #   KitchenOrder projection
│   ├── application/        #   Queue + auth use cases
│   ├── infrastructure/     #   SQL repository, orm_models (none — uses Ordering)
│   └── presentation/       #   Router, dependencies.py
├── identity/               # Auth
│   ├── domain/             #   PasswordHasher, TokenService ABCs
│   ├── infrastructure/     #   Auth implementation, orm_models.py (AdminUser)
│   └── presentation/       #   Login router, middleware
├── shared/                 # Dùng chung
│   ├── events.py           #   EventBus (in-process pub/sub)
│   ├── exceptions.py       #   Domain exceptions → HTTP status codes
│   └── orm_models.py       #   Base mixins (Timestamp, Tenant), Store model
├── models.py               # Re-export hub (backward compat cho alembic, tests cũ)
├── schemas.py              # Pydantic schemas (legacy, đang dùng bởi admin CRUD)
├── main.py                 # App factory + event wiring
└── ws_manager.py           # WebSocket realtime

backend/tests/
├── unit/                   # 219 unit tests — không cần DB
│   ├── test_ordering_value_objects.py    # Phone VN, Address XSS, Money, Status
│   ├── test_ordering_entities.py         # Order aggregate, events, lifecycle
│   ├── test_growth_domain.py             # Loyalty, referral, review, customer
│   ├── test_catalog_domain.py            # Product, category, topping, time deal
│   └── test_kitchen_and_shared.py        # KDS format, EventBus, exceptions
├── conftest.py             # Integration test fixtures (cần DB)
├── test_menu.py            # Integration: menu API
└── test_orders.py          # Integration: order + admin API

frontend/
├── index.html        # Customer ordering app (PWA)
├── admin.html        # Admin panel
├── kds.html          # Kitchen Display System
├── src/              # ES Modules (shared/, admin/, customer/, kds/)
└── css/              # Stylesheets

nginx/                # Reverse proxy + static files
docker-compose.yml    # PostgreSQL + API + Nginx
```


