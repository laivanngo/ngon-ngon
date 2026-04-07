# Changelog

## v7.0.0 — Frontend Modernization: ES Modules + Vite

Frontend chuyển từ **inline scripts + IIFE** sang **ES Modules + Vite build tool**.
Khách hàng không thấy thay đổi gì — chỉ trang tải nhanh hơn nhờ minify + code-split.

**Không thay đổi backend. Không thay đổi API. Không thay đổi database.**

---

### Vấn đề trước khi refactor

Frontend nhồi toàn bộ JavaScript inline trong HTML:
- `admin.html`: 2,295 dòng (72 functions trộn lẫn HTML + CSS + JS)
- `index.html`: 1,524 dòng (40 functions inline + 4 file IIFE trong js/)
- `kds.html`: 631 dòng (toàn bộ logic inline)
- Thêm 1 tính năng nhỏ → rủi ro vô tình làm hỏng chỗ khác
- Không thể minify hay code-split → trang tải chậm trên mạng 4G

---

### Thay đổi — 36 ES modules mới, 3 HTML files slimmed, js/ xóa hoàn toàn

**Phase 1 — Tách admin.html:**
Tạo `src/shared/` (api.js, formatters.js, constants.js, ui.js) dùng chung.
Tạo `src/admin/` (14 modules: auth, dashboard, orders, websocket, notifications,
products, product-modal, categories, toppings, cross-sell, analytics, reviews,
settings, main). admin.html giảm 2,295 → 472 dòng.

**Phase 2 — Tách index.html:**
Tạo `src/customer/` (11 modules: state, data-loader, menu, product-detail,
cart, checkout, social-proof, time-deals, pwa, share, main).
index.html giảm 1,524 → 730 dòng.

**Phase 3 — Tách kds.html:**
Tạo `src/kds/` (5 modules: auth, orders, websocket, sound, main).
kds.html giảm 631 → 200 dòng.

**Phase 4 — Xóa legacy js/:**
Migrate js/api.js → src/shared/customer-api.js (ES Module).
Migrate js/growth.js → src/customer/growth.js (ES Module).
Xóa hoàn toàn thư mục frontend/js/ (api.js, app.js, cart.js, growth.js).
Cập nhật tất cả imports — không còn window.API / window.Growth globals.

**Infra:**
Tạo package.json + vite.config.js (multi-page app: admin, index, kds).
Cập nhật AI_GUIDE.md V4.1 (frontend architecture, 10 frontend rules, migration plan).
Cập nhật validate.sh V3.0 (thêm 11 frontend checks: structure, fetch, IIFE, globals...).
Bump sw.js cache version → nn-v3.0-20260330 (force browser cache invalidation).
Cập nhật README.md, PROMPT_TEMPLATES.md, run_full_test.sh.

### Kết quả

| Metric | Trước | Sau |
|--------|-------|-----|
| HTML files tổng | 4,450 dòng | 1,402 dòng (−68%) |
| JS modules | 4 IIFE + inline | 36 ES Modules |
| File trung bình | ~1,800 dòng | ~100 dòng |
| Legacy js/ | 4 files | 0 (đã xóa) |
| validate.sh checks | 10 backend | 21 (backend + frontend) |

---

## v6.0.0 — Strict Modular Monolith: Ports & Adapters (Boundary Refactor)

Codebase đạt 100% ranh giới module theo kiến trúc **Strict Modular Monolith với Ports & Adapters**. Không có context nào còn import ORM, repository, hay infrastructure của context khác. Mọi giao tiếp cross-context đều qua port (interface) và adapter (implementation).

**Không thay đổi database schema. Không cần chạy migration. API contract giữ nguyên 100%.**

---

### Vấn đề trước khi refactor

Codebase đã có cấu trúc DDD đúng hướng (6 bounded contexts, 4 tầng domain/application/infrastructure/presentation) nhưng có 18 cross-context ORM imports vi phạm ranh giới module:

- `ordering/infrastructure/pricing.py` import `Product, TimeDeal, Topping` ORM từ Catalog
- `growth/infrastructure/repository.py` import `Order, OrderItem, OrderStatus` từ Ordering và `Product` từ Catalog (4 imports trực tiếp)
- `kitchen/infrastructure/repository.py` import `Order, OrderStatus` ORM từ Ordering
- `kitchen/presentation/router.py` import `UpdateStatusUseCase` trực tiếp từ Ordering
- `ordering/infrastructure/repository.py` import `Product` ORM từ Catalog (dashboard query)
- Tất cả routers (ordering, catalog, growth) import `AdminUser` ORM từ Identity
- `catalog/presentation/schemas.py` import từ `app/schemas.py` (God-Schema)
- `app/ws_manager.py` đứng ngoài tất cả contexts

---

### Thay đổi — 12 files mới, 16 files sửa

**Phase 1 — Nền móng sạch:**

`identity/domain/entities.py` tạo mới với `CurrentAdmin(id, username)` — pure dataclass, frozen, immutable. `identity/presentation/middleware.py` đổi return type từ `AdminUser` ORM sang `CurrentAdmin`. Bốn routers cập nhật type-hint theo. `identity/presentation/schemas.py` tạo mới chứa `LoginRequest`, `TokenResponse`. `catalog/presentation/schemas.py` viết lại tự sở hữu hoàn toàn, không còn import từ `app/schemas.py`. `app/schemas.py` và `app/ws_manager.py` trở thành deprecation shims. `shared/ws_manager.py` tạo mới — đúng nơi cho shared infrastructure.

**Phase 2 — Ports & Adapters cho Pricing và KDS:**

`ordering/domain/catalog_port.py` định nghĩa `CatalogPricingPort` với 3 methods và DTOs (`PricingProductData`, `PricingSizeData`, `PricingToppingData`, `ActiveTimeDeal`). `catalog/infrastructure/pricing_adapter.py` implement port. `ordering/infrastructure/pricing.py` viết lại — nhận `CatalogPricingPort` qua constructor, xóa toàn bộ Catalog ORM imports. `kitchen/domain/ports.py` định nghĩa `OrderStatusPort`. `ordering/infrastructure/kitchen_adapter.py` implement port. Kitchen router và dependencies dùng port, không biết Ordering tồn tại.

**Phase 3 — Growth tách hoàn toàn + Dashboard:**

`ordering/application/analytics_port.py` định nghĩa 4 ports: `OrderAnalyticsPort` (analytics queries), `KitchenQueuePort` (queue bếp), `OrderCustomerLinkPort` (ghi customer_id), cùng 10+ DTOs thuần Python. `ordering/infrastructure/analytics_adapter.py` implement toàn bộ. `catalog/application/analytics_port.py` định nghĩa `CatalogAnalyticsPort` với `get_active_product()` và `count_active_products()`. `catalog/infrastructure/analytics_adapter.py` implement. `growth/infrastructure/repository.py` viết lại hoàn toàn 5 service classes nhận ports qua constructor. `growth/presentation/dependencies.py` wire adapters. `ordering/infrastructure/kitchen_queue_adapter.py` tạo mới cho `KitchenQueuePort`. `kitchen/infrastructure/repository.py` viết lại — nhận `KitchenQueuePort`, không còn import Ordering ORM. `alembic/env.py` import ORM trực tiếp từ context owners, không qua `app/models.py`.

---

### Kết quả đo lường

| Chỉ số | Trước | Sau |
|--------|-------|-----|
| Cross-context ORM imports | 18 | 0 |
| Ranh giới module | 50% | 100% |
| Phân tầng (layering) | 90% | 100% |
| Files mới | — | 12 |
| Files sửa | — | 16 |

---

## v5.2.0 — Feature Flags Sync + Reviews Dashboard + Legacy Cleanup

Sửa lỗi feature flags không đồng bộ giữa admin và frontend, bổ sung dashboard đánh giá cho admin, dọn sạch code legacy trùng lặp, và fix luồng review từ đầu đến cuối.

---

### 1. Feature Flags — Backend + Admin UI

**Vấn đề:** Bật/tắt tính năng trên trang Admin gây lỗi 500 (thiếu tham số `admin_username`). Danh sách flags bị xáo trộn thứ tự mỗi lần toggle vì PostgreSQL trả về không có ORDER BY.

**Sửa:**
- `growth/presentation/router.py`: Thêm `admin.username` vào `ToggleFeatureFlagUseCase.execute()`.
- `growth/infrastructure/repository.py`: Thêm `.order_by(ORMFeatureFlag.id)` trong `get_all()`.
- `frontend/admin.html`: Dùng thứ tự cố định từ `descriptions` thay vì `Object.keys(flags)`.

---

### 2. Feature Flags — Frontend Sync

**Vấn đề:** Khi admin tắt một tính năng (reorder, loyalty, cross-sell, estimated_time), frontend khách hàng vẫn hiện vì code legacy trong `index.html` không biết feature flags.

**Sửa:** Xóa toàn bộ legacy duplicate, để Growth module (`growth.js`) là single source of truth:
- Xóa legacy HTML: `#reorderBar`, `#loyalty` (Growth tạo element riêng).
- Xóa legacy CSS: 21 rules `.reorder-*` và `.loyalty-*`.
- Xóa legacy JS: 6 functions (`saveOrder`, `checkReorder`, `selectReorder`, `doReorder`, `incrLoyalty`, `updLoyalty`).
- Giữ flag guard cho cross-sell và estimated_time (Growth chỉ expose method, legacy là implementation duy nhất).

---

### 3. Admin Reviews Dashboard (tính năng mới)

**Vấn đề:** Khách đánh giá và góp ý sau khi nhận hàng, nhưng data lưu vào DB mà admin không có cách nào xem — chỉ thấy `avg_rating` trong Phân tích.

**Thêm mới (đúng kiến trúc DDD):**
- Domain: `list_all()` trong `ReviewRepository` ABC — hỗ trợ phân trang và lọc theo rating.
- Infrastructure: `SqlReviewRepository.list_all()` — join orders để lấy public_id.
- Application: `GetReviewsUseCase` — format response có pagination.
- Presentation: `GET /growth/reviews/list` (admin auth required), `get_reviews_list` factory.
- Frontend: Tab "⭐ Đánh giá" trên admin — hiển thị sao, comment, SĐT, mã đơn, lọc theo rating, phân trang.

---

### 4. Review Flow Fix (3 bugs)

**Bug 1 — Data type mismatch:** `index.html` lưu `resp.public_id` (UUID string) vào localStorage, nhưng `growth.js` gửi `parseInt(UUID)` = NaN → review không link được đơn hàng.
- Sửa frontend: gửi `order_public_id` (string) thay vì `order_id: parseInt(...)`.
- Sửa backend: thêm field `order_public_id` vào `ReviewCreate` schema, router resolve UUID → integer FK.

**Bug 2 — Popup không hiện:** `initReviewPrompt()` chỉ check 1 lần khi page load. Nếu lúc đó chưa đủ 30 phút → return, không có cơ chế chạy lại.
- Sửa: tách logic thành `_tryShowReview()`, đăng ký `visibilitychange` listener để re-check khi khách quay lại tab.

**Bug 3 — Thời gian chờ quá dài:** 30 phút là quá lâu, đơn hàng thường giao trong 15-20 phút.
- Sửa: giảm thời gian chờ xuống 20 phút.

---

### Tổng kết thay đổi

| Layer | Files changed | Nội dung |
|-------|---------------|----------|
| Domain | `growth/domain/services.py` | +1 method `list_all()` trên ReviewRepository ABC |
| Application | `growth/application/use_cases.py` | +1 use case `GetReviewsUseCase` (tổng: 12) |
| Infrastructure | `growth/infrastructure/repository.py` | +`list_all()` impl, fix `order_by` |
| Presentation | `router.py`, `dependencies.py`, `schemas.py` | +1 endpoint, +1 factory, fix review submit |
| Frontend admin | `admin.html` | Fix flag order, +tab Reviews, +loadReviews() |
| Frontend customer | `index.html`, `js/app.js`, `js/growth.js` | Xóa legacy, fix review flow |

**Không thay đổi database schema. Không cần chạy migration.**

---

## v5.1.0 — DDD Hardening (3 cải thiện chất lượng)

Ba cải thiện dưới đây được thực hiện sau khi hoàn thành DDD migration Phase 5. Mục tiêu: tăng test coverage, giảm coupling giữa contexts, và chuẩn hóa dependency injection.

**Không thay đổi database schema. Không cần chạy migration. Không ảnh hưởng frontend.**

---

### 1. Unit Tests cho Domain Layer (219 tests)

**Vấn đề:** DDD tách domain entities khỏi database (pure dataclass), nhưng chưa có test nào kiểm tra domain logic mà không cần DB.

**Giải pháp:** 5 file test trong `backend/tests/unit/`, chạy trong 0.6 giây không cần PostgreSQL.

| File | Tests | Kiểm tra |
|------|-------|----------|
| `test_ordering_value_objects.py` | 46 | SĐT VN, địa chỉ chống XSS, Money, trạng thái đơn hàng |
| `test_ordering_entities.py` | 34 | Order aggregate: tạo đơn, validate, tính tiền, event |
| `test_growth_domain.py` | 53 | Loyalty tích điểm, mã giới thiệu, review, referral |
| `test_catalog_domain.py` | 43 | Sản phẩm, danh mục, topping, time deal, cross-sell |
| `test_kitchen_and_shared.py` | 43 | KDS format, timer, EventBus, domain exceptions |

```bash
cd backend && PYTHONPATH=. python -m pytest tests/unit/ --noconftest -v
```

---

### 2. Tách ORM Models theo Bounded Context

**Vấn đề:** 18 ORM models nằm chung 1 file `models.py` (468 dòng). Mọi context import từ đây → coupling ngầm.

**Giải pháp:** Mỗi context sở hữu `infrastructure/orm_models.py` riêng. File `models.py` gốc thành re-export hub (468 dòng → 66 dòng) giữ backward compat cho alembic + tests cũ.

| File mới | Context | Models |
|----------|---------|--------|
| `shared/orm_models.py` | Shared | TimestampMixin, TenantMixin, Store |
| `catalog/infrastructure/orm_models.py` | Catalog | Category, Product, ProductSize, Topping, ProductTopping, CrossSellItem, TimeDeal |
| `ordering/infrastructure/orm_models.py` | Ordering | Order, OrderItem, OrderStatus |
| `growth/infrastructure/orm_models.py` | Growth | Customer, FeatureFlag, Event, Review, PushSubscription, LoyaltyReward, Referral |
| `identity/infrastructure/orm_models.py` | Identity | AdminUser |

12 file đã cập nhật import. Cross-context reads đều có comment `# cross-context: <context> owns <Model>`.

---

### 3. Dependency Injection tập trung

**Vấn đề:** 24 factory functions rải rác trong 6 file router. Mỗi router tự tạo `SqlOrderRepository(db)` inline → biết quá nhiều về infrastructure, khó swap cho test.

**Giải pháp:** Mỗi context có `presentation/dependencies.py` — nơi duy nhất quyết định dùng implementation nào.

| File mới | Factories | Ví dụ |
|----------|-----------|-------|
| `ordering/presentation/dependencies.py` | 5 | `get_place_order`, `get_update_status` |
| `catalog/presentation/dependencies.py` | 18 | `get_full_menu`, `get_create_product` |
| `growth/presentation/dependencies.py` | 10 | `get_growth_config`, `get_analytics` |
| `kitchen/presentation/dependencies.py` | 2+1 | `get_kitchen_queue`, reuse Ordering's `get_update_status` |

6 router files refactored: `Sql*` imports trong router giảm từ 24 → 0. Test giờ có thể override 1 dòng thay vì mock toàn bộ DB.

---

## v5.0.0 — DDD Phase 5: All Contexts Complete

Tất cả 6 Bounded Contexts đã migrate từ flat routers sang DDD layers. Xem `docs/DDD_PHASE5_GUIDE.md`.
