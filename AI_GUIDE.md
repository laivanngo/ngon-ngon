# 📋 AI_GUIDE.md — Mandatory Guide for AI Contributors
# Ngon-Ngon: Ứng dụng đặt trà sữa & đồ ăn vặt

> **⚠️ MANDATORY: Mọi AI (Claude, ChatGPT, Gemini, Copilot...) PHẢI đọc file này
> TRƯỚC KHI viết hoặc sửa bất kỳ dòng code nào trong dự án.**
>
> Nếu chủ dự án quên nhắc, AI nên chủ động hỏi: "Dự án có file AI_GUIDE.md không?"

---

## 1. PROJECT OVERVIEW — Dự án này là gì?

Ngon-Ngon là ứng dụng đặt trà sữa & đồ ăn vặt dành cho quán nhỏ tại khu công nghiệp
Việt Nam. Khách đặt hàng qua web → quán nhận đơn qua admin panel → bếp pha chế qua
KDS (Kitchen Display System — màn hình bếp).

**Tech Stack:**
- **Backend:** Python 3.12+ / FastAPI / SQLAlchemy async / PostgreSQL / Alembic / Pytest
- **Frontend:** Vanilla HTML + JavaScript (KHÔNG dùng React/Vue) — **Vite** build tool
  - Legacy: IIFE modules (đang chuyển dần sang ES Modules)
  - Mới: ES Modules (`import`/`export`) + Vite bundler (minify, code-split, HMR)
- **Infrastructure:** Docker Compose / Nginx reverse proxy
- **Architecture:** Domain-Driven Design (DDD) — Modular Monolith

**Team Context — Rất quan trọng:**
- Dự án do AI tạo, chủ quán không biết code nhưng đóng vai trò Kiến trúc sư Kinh doanh
  (Business Architect) — người quyết định kiến trúc nghiệp vụ tổng thể
- Mọi thay đổi kỹ thuật do AI thực hiện; mọi quyết định kinh doanh do chủ quán quyết định
- Code PHẢI dễ đọc, có docstring rõ ràng, tuân thủ convention nhất quán
  để BẤT KỲ AI nào cũng tiếp quản được ngay

**Business Rules quan trọng:**
- Backend là single source of truth cho giá cả — KHÔNG TIN client gửi lên
- Target users: khách KCN dùng điện thoại 4G → cần load nhanh, ít API calls
- Khách track bằng SĐT, KHÔNG cần đăng ký account
- Online (Web App) và Offline (Quán thực tế) phải luôn đồng bộ trạng thái

**Triết lý kiến trúc:**
Dù là quán nhỏ, mọi yếu tố kinh doanh (sản phẩm, bán hàng, kho, nhân sự, tài chính...)
đều tồn tại trong vận hành thực tế — chỉ là chưa tách thành tổ chức riêng biệt.
Codebase phải phản ánh đúng kiến trúc nghiệp vụ đầy đủ ngay từ đầu, để mở rộng sau này
mà không phải đập đi xây lại. Xem Section 11 để hiểu bản thiết kế tổng thể.

---

## 2. CURRENT STATE — Trạng thái hiện tại (6 Bounded Contexts)

```
backend/app/
├── catalog/        ← Menu, Products, Categories, Toppings, Cross-Sell, Time Deals
├── ordering/       ← Đặt hàng, pricing, order lifecycle (Aggregate Root: Order)
├── crm/            ← Khách hàng, Loyalty (spend-based), Referral, Reviews, Analytics, Settings
├── promotions/     ← Feature Flags, Upsell stats, Cross-sell suggestions, Flash Sales
├── kitchen/        ← KDS queue, PIN auth cho bếp
├── identity/       ← JWT auth, password hashing cho admin
├── shared/         ← Event bus, exceptions, constants, utilities (Shared Kernel)
├── main.py         ← App factory, event wiring, CORS, middleware
├── config.py       ← Pydantic Settings (environment variables)
└── database.py     ← SQLAlchemy async engine + session factory
```

**Mỗi Bounded Context có 4 layers:**
```
context_name/
├── domain/              ← Entities, Value Objects, Events, Repository ABCs (interfaces)
│   ├── entities.py      ← Dataclass entities (KHÔNG phải ORM models)
│   ├── value_objects.py ← Immutable value objects (Phone, Money, OrderStatus...)
│   ├── events.py        ← Domain events (OrderPlaced, MenuChanged...)
│   ├── services.py      ← Repository ABCs + Domain Service interfaces
│   └── repository.py    ← (chỉ Catalog có file riêng)
├── application/         ← Use Cases, Event Handlers (orchestration logic)
│   ├── use_cases.py     ← PlaceOrderUseCase, GetFullMenu, etc.
│   ├── commands.py      ← (chỉ Catalog tách commands — CQS pattern)
│   ├── queries.py       ← (chỉ Catalog tách queries — CQS pattern)
│   └── event_handlers.py
├── infrastructure/      ← ORM Models, SQL Repositories, External Service implementations
│   ├── orm_models.py    ← SQLAlchemy ORM models (DB table definitions)
│   ├── repository.py    ← SQL implementations of Domain Repository ABCs
│   └── pricing.py       ← (chỉ Ordering có pricing service)
└── presentation/        ← FastAPI Routers, Pydantic Schemas, Dependency Injection
    ├── router.py        ← Public API endpoints
    ├── admin_router.py  ← Admin-only endpoints (nếu có)
    ├── schemas.py       ← Request/Response Pydantic models
    └── dependencies.py  ← DI factory functions (wiring layer)
```

### Dependency Rule — Quy tắc phụ thuộc

```
Domain ← Application ← Infrastructure ← Presentation
 (MŨI TÊN = "phụ thuộc vào", tức là Application ĐƯỢC import Domain)
```

| Layer | ĐƯỢC import từ | KHÔNG ĐƯỢC import từ |
|-------|---------------|---------------------|
| **Domain** | (không import layer nào) | Application, Infrastructure, Presentation |
| **Application** | Domain | Infrastructure, Presentation |
| **Infrastructure** | Domain (ABCs để implement) | Application (trừ DTOs), Presentation |
| **Presentation** | Application, Infrastructure (qua dependencies.py) | — |

---

## 3. NAMING CONVENTIONS — Quy tắc đặt tên

### Python (Backend)

| Loại | Convention | Ví dụ đúng ✅ | Ví dụ SAI ❌ |
|------|-----------|------------|-----------|
| File name | snake_case.py | `orm_models.py`, `use_cases.py` | `OrmModels.py` |
| Class | PascalCase | `PlaceOrderUseCase`, `SqlOrderRepository` | `place_order_use_case` |
| Function / Method | snake_case | `find_by_phone()`, `get_active_queue()` | `findByPhone()` |
| Variable | snake_case | `order_count`, `customer_name` | `orderCount` |
| Constant | UPPER_SNAKE_CASE | `LOYALTY_THRESHOLD`, `VN_PHONE_REGEX` | `loyaltyThreshold` |
| Private member | _prefix | `_events`, `_connections` | `events` (nếu internal) |
| Module docstring | Luôn phải có | `"""Ordering Context — Domain Entities."""` | (file trống) |
| Type hints | Luôn có trên public functions | `def get(id: int) -> Order \| None:` | `def get(id):` |

### Ubiquitous Language — Đặt tên theo nghiệp vụ F&B

> **Quy tắc áp dụng:** Trong các context HIỆN CÓ (catalog, ordering, crm, promotions, kitchen, identity),
> giữ nguyên tên đang dùng để tránh xung đột. Bảng dưới đây áp dụng khi tạo
> Bounded Context MỚI hoặc khi chủ dự án yêu cầu refactor tên cụ thể.

Khi đặt tên class, function, event — dùng từ chuyên ngành F&B, không dùng từ IT chung:

| IT chung (tránh dùng khi tạo mới) | F&B chuyên ngành (nên dùng) | Lý do |
|-----------------------------------|---------------------------|-------|
| `Product` | `MenuItem` | Quản lý quán gọi "món", không gọi "sản phẩm" |
| `DeleteOrder` | `CancelOrder` / `VoidBill` | Hủy trước khi làm ≠ Hủy hóa đơn đã in |
| `MoneyIn` / `MoneyOut` | `CashIn` / `CashDrop` / `Refund` | Ngôn ngữ thu ngân thực tế |
| `Item` / `Record` / `Data` | `Ingredient`, `Shift`, `Recipe` | Tránh từ chung chung vô nghĩa |

### Domain Events — Mẫu đặt tên

Dùng mẫu **[Danh từ] + [Quá khứ]**: `OrderPlaced`, `MenuChanged`, `StockDepleted`.
Tránh: `NewOrder`, `UpdateMenu`, `OutOfStock`.

### JavaScript (Frontend)

| Loại | Convention | Ví dụ đúng ✅ |
|------|-----------|------------|
| File name | kebab-case.js | `api.js`, `cart.js`, `product-detail.js`, `cross-sell.js` |
| Module pattern | ES Module | `export function loadOrders() { ... }` |
| Function | camelCase | `transformMenuData()`, `makeKey()` |
| Constant | UPPER_SNAKE_CASE | `STORAGE_KEY`, `BASE` |
| Import/Export | Named exports (ưu tiên) | `export { loadOrders, renderOrderCard }` |
| Entry file | `main.js` trong mỗi thư mục | `src/admin/main.js`, `src/customer/main.js` |

### Database / Alembic

| Loại | Convention | Ví dụ đúng ✅ |
|------|-----------|------------|
| Table name | snake_case, số nhiều | `orders`, `order_items`, `customers` |
| Column name | snake_case | `customer_name`, `created_at`, `is_active` |
| Migration file | `NNN_description.py` | `001_initial_schema.py`, `006_add_coupon.py` |
| Foreign key | `entity_id` | `customer_id`, `product_id` |

---

## 4. CODING RULES — Quy tắc viết code

### 4.1 Đặt code vào đúng layer

| Loại logic | Đặt ở đâu | Ví dụ |
|-----------|-----------|-------|
| Business rules | `domain/entities.py` hoặc `domain/value_objects.py` | `Order.change_status()` |
| Orchestration | `application/use_cases.py` | `PlaceOrderUseCase.execute()` |
| Database queries | `infrastructure/repository.py` | `SqlOrderRepository.save()` |
| HTTP endpoints | `presentation/router.py` | `@router.post("/orders")` |
| Request/Response | `presentation/schemas.py` | `class OrderCreate(BaseModel)` |
| DI wiring | `presentation/dependencies.py` | `def get_place_order(...)` |

**Nguyên tắc vàng:** Router CHỈ có 3 việc: parse request → gọi use case → return response.

### 4.2 Tạo Bounded Context mới

Copy structure từ `kitchen/` (context nhẹ nhất). **Khi tạo context mới, BẮT BUỘC tham khảo
Section 11 (Bản thiết kế tổng thể)** để đặt tên và xác định vị trí đúng trong kiến trúc.

Sau khi tạo xong, register router trong `main.py`.

### 4.3 Cross-Context Communication

| Cách | Khi nào dùng | Ví dụ |
|------|-------------|-------|
| **Domain Events** qua EventBus | Context A thông báo B điều đã xảy ra | Ordering phát `OrderPlaced` → CRM update |
| **Port + Adapter** | Context A cần đọc data từ B | CRM dùng `OrderAnalyticsPort` |
| **Port + Adapter** (write) | Context A cần ghi vào B | CRM dùng `OrderCustomerLinkPort` |

**Tuyệt đối không:** Import ORM model, Repository, hay Use Case của context khác.
Auth middleware là ngoại lệ (cross-cutting concern) — dùng `from app.identity.presentation.middleware`.

### 4.4 Shared Kernel

| Cần dùng | Import từ | KHÔNG tạo bản sao |
|----------|-----------|-------------------|
| VN phone regex | `app.shared.constants.VN_PHONE_REGEX` | ❌ `re.compile(...)` |
| XSS sanitize | `app.shared.utils.sanitize_string` | ❌ `def sanitize(v)` |
| Phone cleaning | `app.shared.utils.clean_phone` | ❌ `.replace(" ","")...` |
| Money value object | `app.shared.value_objects.Money` | ❌ `class Money` mới |
| Domain exceptions | `app.shared.exceptions.NotFoundError` | ❌ `raise HTTPException(404)` |
| Event bus | `app.shared.events.event_bus` | ❌ Gọi handler trực tiếp |

### 4.5 Database Migration

Mọi thay đổi DB schema PHẢI có Alembic migration: `backend/alembic/versions/NNN_description.py`.
**KHÔNG** sửa DB trực tiếp hoặc sửa migration files cũ đã chạy.

### 4.6 Legacy Files đã xóa — KHÔNG tạo lại

Ba file `app/models.py`, `app/schemas.py`, `app/ws_manager.py` đã được loại bỏ.
Tất cả imports đã chuyển sang đúng Bounded Context.

- **KHÔNG BAO GIỜ** tạo lại 3 file này. `validate.sh` sẽ báo lỗi nếu chúng xuất hiện.
- ORM models → import từ `<context>/infrastructure/orm_models.py`
- Schemas → import từ `<context>/presentation/schemas.py`
- WebSocket → import từ `app.shared.ws_manager`
- Auth utils → import từ `app.identity.infrastructure.auth`

### 4.7 Error Handling — Hiện trạng và Quy tắc

**Hiện trạng thực tế:**
- `shared/exceptions.py` có `DomainError(message, code)` với cả hai thuộc tính.
- `main.py` exception handlers trả về `{"detail": exc.message}` — thuộc tính `code` chưa được
  đưa vào response.
- `api.js` đọc `errorData.detail` — khớp với format hiện tại.
- Một số router (catalog, crm, kitchen) vẫn dùng `raise HTTPException` trực tiếp
  thay vì để Domain exceptions tự động convert. Đây là tech debt đã biết.

**Quy tắc cho code MỚI:**
- Trong Domain/Application layer: dùng exceptions từ `app.shared.exceptions`
  (NotFoundError, ValidationError, DuplicateError, InvalidStatusTransitionError).
  **KHÔNG** dùng `raise HTTPException` — nó thuộc Presentation layer.
- Trong Presentation layer: để `main.py` global exception handlers tự động convert.
  Chỉ dùng `raise HTTPException` khi xử lý lỗi đặc thù HTTP (auth, rate limit).
- **KHÔNG refactor** error handling trong code cũ trừ khi chủ dự án yêu cầu.

---

## 5. FRONTEND SOP — Quy tắc viết Frontend

### 5.1 Nguyên tắc chung
- **KHÔNG** dùng framework (React, Vue). Chỉ dùng **Vanilla JS + ES Modules + Vite**.
- **KHÔNG** lưu state quan trọng (giỏ hàng, điểm, giá) chỉ ở client.
  Backend quyết định giá cuối cùng.
- **Mỗi file JS tối đa 200 dòng.** Nếu quá → tách thành module con.
- **Mỗi module chỉ làm 1 việc** — giống triết lý DDD ở backend: orders.js quản lý đơn,
  products.js quản lý sản phẩm — KHÔNG trộn lẫn.

### 5.2 Cấu trúc thư mục Frontend — Target Architecture

```
frontend/
├── package.json              ← npm: vite + dev dependencies
├── vite.config.js            ← Multi-page app (admin, index, kds)
├── admin.html                ← Entry point admin (CHỈ HTML + 1 dòng <script type="module">)
├── index.html                ← Entry point khách đặt hàng
├── kds.html                  ← Entry point bếp
│
├── src/                      ← TẤT CẢ JavaScript nằm ở đây
│   ├── shared/               ← Dùng chung giữa admin / customer / kds
│   │   ├── api.js            ← Admin API (JWT auth, centralized)
│   │   ├── customer-api.js   ← Customer API (public endpoints, timeout, cache)
│   │   ├── formatters.js     ← fmtP(), fmtPd(), escHtml()
│   │   ├── constants.js      ← STORAGE_KEY, BASE, brand colors
│   │   └── ui.js             ← openModal(), closeModal(), showToast()
│   │
│   ├── admin/                ← Admin panel — mỗi tab/chức năng 1 file
│   │   ├── main.js           ← Entry: import modules, init tabs, gọi checkAuth
│   │   ├── auth.js           ← checkSavedAuth(), doLogin(), doLogout()
│   │   ├── dashboard.js      ← loadDashboard()
│   │   ├── orders.js         ← loadOrders(), renderOrderCard(), updateStatus()
│   │   ├── websocket.js      ← connectWS(), disconnectWS(), scheduleReconnect()
│   │   ├── notifications.js  ← handleNewOrder(), playNotifSound(), showBrowserNotification()
│   │   ├── products.js       ← loadProducts(), saveProduct(), drag/drop sort
│   │   ├── categories.js     ← loadCategoriesList(), saveCategory(), toggleCategoryActive()
│   │   ├── toppings.js       ← loadToppingsList(), saveTopping(), toggleToppingActive()
│   │   ├── cross-sell.js     ← loadCrossSellList(), saveCrossSell(), toggleCrossSellActive()
│   │   ├── analytics.js      ← loadAnalytics()
│   │   ├── reviews.js        ← loadReviews()
│   │   └── settings.js       ← loadFeatureFlags(), toggleFeature(), loadGrowthSettings()
│   │
│   ├── customer/             ← Trang đặt hàng của khách
│   │   ├── main.js           ← Entry: init menu, load data
│   │   ├── state.js          ← Shared state: M, cart, TOPPINGS, constants
│   │   ├── data-loader.js    ← Load menu/toppings từ API, transform data
│   │   ├── growth.js         ← 9 tính năng tăng doanh thu (loyalty, referral...)
│   │   ├── menu.js           ← render(), renderSection(), mkCard()
│   │   ├── product-detail.js ← openPD(), closePD(), size/sweet/ice/topping selection
│   │   ├── cart.js           ← saveCart(), updCartUI(), chgCartQty(), clearCartCk()
│   │   ├── checkout.js       ← openCheckout(), renderCheckout(), placeOrder()
│   │   ├── time-deals.js     ← updTimeDeal(), updCD()
│   │   ├── social-proof.js   ← showToast(), showToastMsg(), rotSP()
│   │   ├── pwa.js            ← PWA Add to Home Screen install prompt
│   │   └── share.js          ← shareMenu(), copyLink()
│   │
│   └── kds/                  ← Màn hình bếp
│       ├── main.js           ← Entry: PIN auth → load orders → WS
│       ├── auth.js           ← PIN login, session restore, lock
│       ├── orders.js         ← Load, render, update status, timer, tabs
│       ├── websocket.js      ← Real-time order updates, reconnect
│       └── sound.js          ← Notification sound, vibration, wake lock
│
├── css/
│   └── growth.css            ← (sẽ tách thêm khi cần)
├── sounds/
│   └── new-order.wav
├── manifest.json
└── sw.js
```

### 5.3 Quy tắc Module hóa

**5.3.1 Entry Point — HTML files:**
Sau khi migrate, mỗi file HTML chỉ chứa: HTML markup + CSS + **1 dòng** script entry:
```html
<!-- admin.html — ĐÚNG sau khi migrate -->
<script type="module" src="/src/admin/main.js"></script>
```
**KHÔNG** viết inline `<script>` dài hơn 5 dòng trong HTML.

**5.3.2 Module Communication — Cách modules nói chuyện với nhau:**

| Pattern | Khi nào dùng | Ví dụ |
|---------|-------------|-------|
| `import` trực tiếp | Module cùng thư mục (admin/*, customer/*) | `import { api } from '../shared/api.js'` |
| Custom Event (DOM) | Module cần thông báo sự kiện cho module khác | `document.dispatchEvent(new CustomEvent('cart-updated'))` |
| Shared state object | Dữ liệu cần chia sẻ giữa nhiều modules | `export const state = { menu: null, cart: [] }` |

**KHÔNG** dùng global `window.xxx` cho function mới. Legacy globals chỉ giữ khi chưa migrate.

**5.3.3 Lazy Loading — Chỉ tải cái khách cần:**
Dùng dynamic `import()` cho tính năng không cần ngay khi mở trang:
```javascript
// Trong customer/main.js — ĐÚNG
// Menu tải ngay (critical path)
import { render } from './menu.js';

// Share/referral chỉ tải khi khách bấm
document.getElementById('share-btn').addEventListener('click', async () => {
    const { shareMenu } = await import('./share.js');
    shareMenu();
});
```

### 5.4 API Calls — Tất cả phải qua `shared/api.js`

File `frontend/src/shared/api.js` là centralized API layer với:
timeout 15 giây (AbortController), error handling tiếng Việt, và caching cho menu/toppings.

**Quy tắc:** Mọi API call mới **BẮT BUỘC** thêm vào `shared/api.js` dưới dạng named export.
**KHÔNG** viết `fetch()` trực tiếp trong file JS khác.

```javascript
// src/shared/api.js — ĐÚNG: centralized
export async function getMenu() { return request('/api/v1/menu'); }
export async function createOrder(data) { return request('/api/v1/orders', { method: 'POST', body: data }); }

// src/admin/orders.js — ĐÚNG: import từ api.js
import { getAdminOrders } from '../shared/api.js';

// src/admin/orders.js — SAI ❌: fetch trực tiếp
const data = await fetch('/api/v1/admin/orders');
```

**Thư mục `frontend/js/` đã được xóa hoàn toàn.** Mọi API call đều đi qua
`src/shared/customer-api.js` (customer) hoặc `src/shared/api.js` (admin).

### 5.5 Vite — Build Tool

**5.5.1 Cài đặt:**
```bash
cd frontend && npm init -y && npm install --save-dev vite
```

**5.5.2 vite.config.js — Multi-page app:**
```javascript
import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  root: '.',
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, 'index.html'),
        admin: resolve(__dirname, 'admin.html'),
        kds: resolve(__dirname, 'kds.html'),
      }
    },
    outDir: 'dist',
    // Minify + code-split tự động
    minify: 'terser',
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',  // Proxy API calls to backend
      '/ws':  { target: 'ws://localhost:8000', ws: true },
    }
  }
});
```

**5.5.3 Quy trình phát triển:**

| Lệnh | Mục đích |
|-------|---------|
| `cd frontend && npx vite` | Chạy dev server (HMR, auto-reload) |
| `cd frontend && npx vite build` | Build production → `frontend/dist/` |
| `cd frontend && npx vite preview` | Preview bản build production |

**5.5.4 Docker integration:** Sau khi build, Nginx serve từ `frontend/dist/`
thay vì serve trực tiếp từ `frontend/`. Cập nhật `nginx.conf` khi migrate xong.

### 5.6 Đồng bộ Online ↔ Offline

Khi thiết kế tính năng liên quan đến vận hành quán:
- Nhân viên cần nút gì trên admin panel để phản ánh tình hình thực tế?
  (Ví dụ: "Hết nguyên liệu đột xuất" → khóa món trên Web App)
- Khi trạng thái đơn thay đổi ở quán → khách online phải thấy ngay
  → dùng WebSocket qua `shared/ws_manager.py`
- Xung đột Online vs Offline: Backend là nguồn sự thật,
  Frontend xử lý gracefully (hiện thông báo, gợi ý món khác)

### 5.7 Kế hoạch Migration — Từng bước, không dừng quán

> **Nguyên tắc vàng:** Migrate từng file, test kỹ trước khi chuyển file tiếp theo.
> Khách hàng không bao giờ thấy khác biệt — chỉ thấy trang tải nhanh hơn.

**Phase 1 — Tuần 1-2: Tách `admin.html` (ưu tiên vì ít traffic, an toàn hơn)**

| Bước | Công việc | Kiểm tra |
|------|-----------|---------|
| 1.1 | Cài Vite: `package.json`, `vite.config.js` | `npx vite` chạy được |
| 1.2 | Tạo `src/shared/api.js` (chuyển IIFE → ES Module) | Import thành công |
| 1.3 | Tạo `src/shared/formatters.js`, `ui.js`, `constants.js` | — |
| 1.4 | Tạo `src/admin/auth.js` (tách 3 functions login/logout/check) | Login vẫn hoạt động |
| 1.5 | Tạo từng module: dashboard → orders → websocket → ... | Từng tab hoạt động |
| 1.6 | Tạo `src/admin/main.js` — import tất cả, xóa inline script | admin.html chạy bình thường |
| 1.7 | Test toàn bộ admin panel trên browser | Mọi chức năng y như cũ |

**Phase 2 — Tuần 3-4: Tách `index.html`**

| Bước | Công việc | Kiểm tra |
|------|-----------|---------|
| 2.1 | Tạo `src/customer/menu.js`, `product-detail.js` | Menu hiển thị đúng |
| 2.2 | Tạo `src/customer/cart.js`, `checkout.js` | Đặt hàng thành công |
| 2.3 | Tạo `src/customer/time-deals.js`, `share.js` | Lazy load hoạt động |
| 2.4 | Tạo `src/customer/main.js` — import tất cả | index.html chạy bình thường |
| 2.5 | ~~Xóa `frontend/js/` (thư mục cũ)~~ | ✅ ĐÃ XÓA |
| 2.6 | Test trên điện thoại 4G thật | Trang tải < 3 giây |

**Phase 3 — Tuần 5: KDS + Production build**

| Bước | Công việc | Kiểm tra |
|------|-----------|---------|
| 3.1 | Tạo `src/kds/main.js` — tách từ kds.html | KDS hoạt động |
| 3.2 | `npx vite build` → `frontend/dist/` | Build không lỗi |
| 3.3 | Cập nhật `nginx.conf` serve từ `dist/` | Nginx serve đúng |
| 3.4 | Cập nhật `Dockerfile` thêm bước `npm run build` | Docker build xong |
| 3.5 | Test toàn bộ trên Docker Compose | Mọi thứ y như cũ, nhưng nhanh hơn |

---

## 6. TESTING STANDARDS — Quy tắc viết test

> **"Không có test = Không hoàn thành."**

### 6.1 Quy tắc bắt buộc

Khi viết Domain/Application logic mới, AI **PHẢI** tạo/cập nhật test trong `backend/tests/`.

| Layer | Loại test | Bắt buộc? |
|-------|----------|-----------|
| **Domain** (entities, value_objects) | Unit Test | ✅ BẮT BUỘC |
| **Application** (use_cases) | Unit Test + Mock | ✅ BẮT BUỘC |
| **Infrastructure** (repository) | Integration Test | Khuyến khích |
| **Presentation** (router) | API Test | Khuyến khích |

### 6.2 Cấu trúc và Quy tắc

Tests nằm trong `backend/tests/`. Unit tests trong `backend/tests/unit/`.
Chạy tests: `cd backend && python -m pytest tests/unit/ -v`.

File test: `test_<context>_<layer>.py`.
Function test: `test_<hành_động>_<kết_quả>` (ví dụ: `test_cancel_order_after_preparing_raises_error`).
Mỗi test chỉ test MỘT behavior.

---

## 7. NEVER DO LIST — Danh sách "KHÔNG BAO GIỜ"

### Backend Rules
| # | Rule | Lý do |
|---|------|-------|
| 1 | **KHÔNG tạo lại `app/models.py`, `app/schemas.py`, `app/ws_manager.py`** | Đã xóa. Import từ đúng context |
| 2 | **KHÔNG import ORM/Repository/UseCase của context khác** | Dùng Port + Adapter hoặc Domain Events |
| 3 | **KHÔNG import `AdminUser` ORM ra ngoài Identity** | Dùng `CurrentAdmin` từ identity.domain.entities |
| 4 | **KHÔNG đặt business logic trong router** | Router chỉ: parse → gọi use case → return |
| 5 | **KHÔNG import ngược layer** | Domain → Infrastructure là ❌ |
| 6 | **KHÔNG sửa DB schema mà không tạo Alembic migration** | Migration giữ DB sync |
| 7 | **KHÔNG duplicate code** | Dùng `shared/` hoặc domain service |
| 8 | **KHÔNG hardcode business values** | Đặt ở `domain/value_objects.py` hoặc `shared/constants.py` |
| 9 | **KHÔNG báo "xong" mà chưa viết test** | Domain/Application logic mới phải có pytest |
| 10 | **KHÔNG dùng `raise HTTPException` trong Domain/Application** | Dùng exceptions từ `app.shared.exceptions` |
| 11 | **KHÔNG refactor code cũ khi không được yêu cầu** | Sửa code cũ chỉ khi chủ dự án duyệt |
| 12 | **KHÔNG đổi tên module/context hiện có** | Giữ nguyên tên cho đến khi có lệnh refactor |

### Frontend Rules
| # | Rule | Lý do |
|---|------|-------|
| F1 | **KHÔNG viết `fetch()` trực tiếp trong file JS** | Thêm method mới vào `src/shared/api.js` |
| F2 | **KHÔNG viết inline `<script>` dài hơn 5 dòng trong HTML** | Tách ra file `.js` trong `src/` |
| F3 | **KHÔNG tạo IIFE module mới** | Code mới dùng ES Modules (`import`/`export`) |
| F4 | **KHÔNG đặt function vào `window.xxx` (global)** | Dùng `import` giữa modules |
| F5 | **KHÔNG viết file JS quá 200 dòng** | Tách thành module con |
| F6 | **KHÔNG tạo lại thư mục `frontend/js/`** | Đã xóa hoàn toàn. Tất cả JS trong `frontend/src/` |
| F7 | **KHÔNG install React, Vue, hoặc bất kỳ framework nào** | Vanilla JS + Vite = đủ |
| F8 | **KHÔNG tạo IIFE module (`const X = (() => { ... })()`)** | Dùng ES Module `export`/`import` |
| F9 | **KHÔNG merge nhiều modules vào 1 file "cho tiện"** | Nguyên nhân gốc của vấn đề hiện tại |
| F10 | **KHÔNG tạo file JS trong `src/` mà không `export` gì** | Mỗi file phải export rõ ràng |

---

## 8. CONTEXT MAP — Event Wiring

```
                      Identity
                     (JWT auth)
                    ↗    ↑    ↖
             Admin    Kitchen    WebSocket
                        |
                        | OrderStatusPort (adapter)
                        ↓
    Catalog ──(CatalogPricingPort)──→ Ordering ──(OrderPlaced event)──→ CRM
                                         |                              (Loyalty/Referral)
                                         |──(KitchenQueuePort)──→ Kitchen
                                         |──(OrderAnalyticsPort)──→ CRM
    Promotions ──(PromotionsPricingPort)──┘
    (Flags/Upsell/CrossSell/FlashSales)
```

**Event subscriptions (wired trong `main.py` → `_wire_events()`):**

| Publisher | Event | → Handler | Consumer |
|-----------|-------|-----------|----------|
| Catalog | `MenuChanged` | `on_menu_changed` → WS broadcast | Shared (WS) |
| Ordering | `OrderPlaced` | `on_order_placed_track_customer` | CRM (spend-based loyalty) |
| Ordering | `OrderPlaced` | `on_order_placed_broadcast_ws` | Shared (WS) |
| Ordering | `OrderStatusChanged` | `on_status_changed_broadcast_ws` | Shared (WS) |
| Promotions | `FlashSaleActivated` | `on_flash_sale_activated` → WS broadcast | Shared (WS) |
| Promotions | `FlashSaleClaimed` | `on_flash_sale_claimed` → WS broadcast | Shared (WS) |
| Promotions | `FlashSaleEnded` | `on_flash_sale_ended` → WS broadcast | Shared (WS) |

**Khi thêm event mới:**
1. Define event trong `context/domain/events.py` (kế thừa `DomainEvent`)
2. Entity phát event: `self._events.append(NewEvent(...))`
3. Tạo handler trong consumer context's `application/event_handlers.py`
4. Wire trong `main.py` → `_wire_events()`

---

## 9. API ROUTES — Danh sách đầy đủ

### Public (không cần auth)
| Method | Path | Context | Mô tả |
|--------|------|---------|-------|
| GET | /api/v1/menu | Catalog | Toàn bộ menu (cached 5 phút) |
| GET | /api/v1/menu/{slug} | Catalog | Menu theo category |
| GET | /api/v1/products/{legacy_id} | Catalog | Chi tiết sản phẩm |
| GET | /api/v1/toppings | Catalog | Danh sách topping |
| GET | /api/v1/time-deals | Catalog | Flash deals |
| GET | /api/v1/cross-sell-config | Catalog | Config gợi ý mua kèm |
| POST | /api/v1/orders | Ordering | Tạo đơn hàng |
| GET | /api/v1/orders/{public_id} | Ordering | Tra cứu đơn |
| GET | /api/v1/orders/{public_id}/zalo-text | Ordering | Format Zalo |
| GET | /api/v1/crm/config | CRM | Feature flags + customer data |
| POST | /api/v1/crm/events | CRM | Log tracking |
| GET | /api/v1/crm/reorder | CRM | Đơn gần nhất |
| GET | /api/v1/crm/customer | CRM | Loyalty info (spend-based) |
| POST | /api/v1/crm/reviews | CRM | Gửi đánh giá |
| GET | /api/v1/crm/referral | CRM | Mã giới thiệu |
| GET | /api/v1/promotions/upsell-stats | Promotions | Popularity stats |
| GET | /api/v1/promotions/cross-sell | Promotions | Gợi ý mua kèm |
| GET | /api/v1/promotions/flash-sales/active | Promotions | Flash sales đang chạy (customer banner) |
| POST | /api/v1/admin/login | Identity | Admin đăng nhập |

### Admin (cần JWT)
| Method | Path | Context | Mô tả |
|--------|------|---------|-------|
| CRUD | /api/v1/admin/products | Catalog | Quản lý sản phẩm |
| CRUD | /api/v1/admin/categories | Catalog | Quản lý danh mục |
| CRUD | /api/v1/admin/toppings | Catalog | Quản lý topping |
| CRUD | /api/v1/admin/cross-sell | Catalog | Quản lý cross-sell |
| GET | /api/v1/admin/orders | Ordering | Danh sách đơn |
| PATCH | /api/v1/admin/orders/{id}/status | Ordering | Chuyển trạng thái |
| GET | /api/v1/admin/dashboard | Ordering | Thống kê nhanh |
| GET | /api/v1/crm/analytics | CRM | Analytics dashboard |
| GET | /api/v1/crm/reviews/list | CRM | Danh sách đánh giá |
| GET | /api/v1/crm/settings | CRM | Lấy cài đặt kinh doanh (admin) |
| PATCH | /api/v1/crm/settings/{key} | CRM | Chỉnh cài đặt kinh doanh |
| PATCH | /api/v1/promotions/flags/{key} | Promotions | Bật/tắt feature flag |
| POST | /api/v1/promotions/flash-sales | Promotions | Tạo flash sale |
| GET | /api/v1/promotions/flash-sales | Promotions | Danh sách flash sales |
| PATCH | /api/v1/promotions/flash-sales/{id}/cancel | Promotions | Hủy flash sale |

### KDS (cần JWT từ PIN)
| Method | Path | Context | Mô tả |
|--------|------|---------|-------|
| POST | /api/v1/kds/auth | Kitchen | PIN → JWT |
| GET | /api/v1/kds/orders | Kitchen | Queue bếp |
| PATCH | /api/v1/kds/orders/{id}/status | Kitchen | Chuyển trạng thái |

### WebSocket
| Path | Auth | Mô tả |
|------|------|-------|
| /api/v1/ws/orders?token=xxx | JWT query | Real-time notifications |

---

## 10. PRE-COMPLETION CHECKLIST — AI tự kiểm tra trước khi nói "xong"

### Backend Checklist
```
- [ ] ĐÚNG LAYER: Business logic ở domain, orchestration ở application,
      SQL ở infrastructure, HTTP ở presentation?
- [ ] KHÔNG IMPORT CHÉO: Không import ORM/Repository/UseCase của context khác?
- [ ] ĐÚNG NAMING: snake_case (files/functions), PascalCase (classes), UPPER_SNAKE_CASE (constants)?
- [ ] KHÔNG DUPLICATE: Check shared/ trước khi tạo helper/constant mới?
- [ ] DEPENDENCY RULE: Domain không import infrastructure/presentation?
- [ ] TYPE HINTS + DOCSTRING: Có đủ trên public functions và file .py mới?
- [ ] TESTING: Viết pytest cho Domain/Application logic mới?
- [ ] ERROR HANDLING: Dùng shared exceptions, không dùng HTTPException trong Domain/Application?
- [ ] MIGRATION: Thay đổi DB schema → tạo Alembic migration?
- [ ] EVENT WIRING: Thêm event → subscribe handler trong main.py?
- [ ] LEGACY: Không tạo lại models.py / schemas.py / ws_manager.py?
```

### Frontend Checklist
```
- [ ] ĐÚNG THƯ MỤC: Code mới nằm trong src/ (KHÔNG trong js/ legacy)?
- [ ] ES MODULE: Dùng import/export (KHÔNG tạo IIFE mới)?
- [ ] API QUA api.js: Mọi fetch() mới đều đi qua src/shared/api.js?
- [ ] FILE ≤ 200 DÒNG: File JS mới không quá 200 dòng?
- [ ] EXPORT RÕ RÀNG: Mỗi file trong src/ đều export functions/constants?
- [ ] KHÔNG GLOBAL: Không thêm window.xxx mới?
- [ ] KHÔNG INLINE SCRIPT: HTML files không có <script> inline dài > 5 dòng?
- [ ] LAZY LOAD: Tính năng phụ (share, review...) dùng dynamic import()?
- [ ] VITE BUILD: `npx vite build` không lỗi (nếu đã cài Vite)?
```

### Cả hai
```
- [ ] FRONTEND API: API endpoint mới → thêm method vào src/shared/api.js?
- [ ] VALIDATE: Chạy bash validate.sh → PASS?
```

---

## 11. BẢN THIẾT KẾ TỔNG THỂ — Kiến trúc Nghiệp vụ F&B

> **Đây là bản thiết kế chính thức của dự án** — không phải tầm nhìn xa vời.
> Nó phản ánh tất cả các nghiệp vụ cần có trong một doanh nghiệp F&B hoàn chỉnh.
> Hiện tại mới triển khai 6 module (Section 2). Các module còn lại sẽ được triển khai
> theo thứ tự ưu tiên kinh doanh do chủ dự án quyết định.
> Khi tạo module mới, **BẮT BUỘC** theo bản thiết kế này.

### 11.1 Kiến trúc đích — Tất cả modules nghiệp vụ

```
backend/app/
│
│ ═══ NỀN TẢNG ═══
├── iam/                  ← Nâng cấp từ identity: Users, Roles, Permissions, Org Chart
├── menu_management/      ← Nâng cấp từ catalog: Menu, BOM/Recipe, Regional Pricing
│
│ ═══ TIỀN SẢNH & KHÁCH HÀNG ═══
├── pos/                  ← Nâng cấp từ ordering: POS, Ca làm, Két tiền
├── omnichannel/          ← Tách từ ordering: Đơn từ Grab, ShopeeFood, Web/App
├── kds/                  ← Nâng cấp từ kitchen: Station Routing, SLA tracking
├── crm/                  ← Tách từ growth: Khách hàng, Loyalty, Thẻ thành viên
├── promotions/           ← Tách từ growth: Voucher, Coupon, Flash Sale
│
│ ═══ HẬU CẦN & CHUỖI CUNG ỨNG ═══
├── inventory/            ← MỚI: Tồn kho, Trừ kho tự động, Kiểm kê
├── procurement/          ← MỚI: Mua hàng, Nhà cung cấp
├── central_kitchen/      ← MỚI: Bếp trung tâm, Bán thành phẩm
│
│ ═══ QUẢN TRỊ DOANH NGHIỆP ═══
├── finance/              ← MỚI: Thu chi, Lời/Lỗ (P&L)
├── hr/                   ← MỚI: Chấm công, Lịch ca, Lương
│
│ ═══ MỞ RỘNG ═══
└── franchise/            ← MỚI: Nhượng quyền, Multi-tenant
│
│ ═══ DỮ LIỆU (tách riêng khỏi API chính) ═══
└── [BI/Analytics → Data Warehouse riêng, không nằm trong app/]
```

### 11.2 Mapping — Tên hiện tại → Tên đích

| Hiện tại (đang dùng) | Đích (khi refactor) | Ghi chú |
|----------------------|---------------------|---------|
| `identity` | `iam` | Thêm Org Chart, Multi-store permissions |
| `catalog` | `menu_management` | Thêm BOM/Recipe |
| `ordering` | `pos` + `omnichannel` | Tách POS tại quầy và đơn từ App/Grab |
| ~~`growth`~~ | `crm` + `promotions` | ✅ ĐÃ TÁCH VÀ XÓA (Phase 6 → 7) |
| `kitchen` | `kds` | Thêm Station Routing |
| `shared` | `shared` | Giữ nguyên |

> **Việc đổi tên chỉ thực hiện khi chủ dự án ra lệnh refactor cụ thể.**
> Trước khi refactor, AI phải trình bày kế hoạch chi tiết để chủ dự án duyệt.

### 11.3 Nguyên tắc khi tạo module mới

1. Tuân thủ 4 layers DDD (Domain → Application → Infrastructure → Presentation)
2. Giao tiếp qua Domain Events — không import trực tiếp từ context khác
3. Đặt tên theo nghiệp vụ F&B (Section 3 — Ubiquitous Language)
4. Loosely Coupled: module mới lỗi → hệ thống bán hàng vẫn chạy
5. Viết test từ đầu (Section 6)
6. Tạo Alembic migration
7. Cập nhật AI_GUIDE.md (Section 2, 8, 9) sau khi hoàn thành

### 11.4 Ví dụ: Inventory Context

Khi chủ dự án yêu cầu quản lý tồn kho:

**Entities:** `Ingredient` (Nguyên liệu), `Stock` (Tồn kho), `StockTransaction` (Thẻ kho),
`Recipe` (Công thức: 1 Trà sữa L = 200ml sữa + 50g trà + 50g trân châu)

**Events phát ra:** `StockDepleted` → Catalog đánh dấu "Hết món";
`GoodsReceived` → Finance ghi nhận chi phí.

**Events lắng nghe:** `OrderCompleted` (từ Ordering) → tra Recipe → trừ kho;
`WastageReported` (từ Kitchen) → ghi nhận hao hụt.

---

## 12. USEFUL COMMANDS

### Backend
```bash
# Validate code quality (BẮT BUỘC trước khi báo "xong")
bash validate.sh

# Chạy unit tests
cd backend && python -m pytest tests/unit/ -v

# Full test suite (cần Docker)
./run_full_test.sh

# Tìm file đang import module (check trước khi xóa/rename)
grep -rn "from app.ordering.domain" backend/app/ --include="*.py"

# Xem cấu trúc backend
find backend/app -type f -name "*.py" | sort
```

### Frontend
```bash
# Cài dependencies (chỉ lần đầu)
cd frontend && npm install

# Dev server với HMR (Hot Module Replacement)
cd frontend && npx vite

# Build production (minify + code-split)
cd frontend && npx vite build

# Preview bản build
cd frontend && npx vite preview

# Xem cấu trúc frontend src/
find frontend/src -type f -name "*.js" | sort

# Tìm fetch() trực tiếp (vi phạm — phải qua api.js)
grep -rn "fetch(" frontend/src/ --include="*.js" | grep -v "api.js"

# Đếm dòng mỗi file JS (kiểm tra ≤ 200 dòng)
find frontend/src -name "*.js" -exec wc -l {} + | sort -n

# Tìm window.xxx globals (vi phạm)
grep -rn "window\." frontend/src/ --include="*.js" | grep -v "// legacy"
```

---

**Last updated:** 2026-03-30
**Project version:** 7.0.0-ddd (Frontend Modernization — Complete)
**Guide version:** V4.1 — Frontend 100% ES Modules, legacy js/ đã xóa, Vite ready
