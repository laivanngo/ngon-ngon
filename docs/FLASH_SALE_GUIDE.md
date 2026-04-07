# Hướng Dẫn Sử Dụng Flash Sale
## Ngon-Ngon — Chương Trình Khuyến Mãi Giới Hạn Thời Gian & Số Lượng

---

## FLASH SALE LÀ GÌ?

Flash Sale là chương trình **giảm giá có thời hạn cụ thể và giới hạn số lượng đơn**,
do chủ quán tạo thủ công cho các dịp đặc biệt.

**Ví dụ thực tế:**
- _"Giảm 30% toàn menu, chỉ 20 đơn đầu tiên, từ 14h–16h hôm nay"_ — xả hàng buổi chiều
- _"Giảm 50% Trà Sữa + Cà Phê Sữa + Matcha, 10 suất, mừng khai trương"_ — event đặc biệt
- _"Giảm 20% tất cả đồ uống, 50 suất, từ 11h–12h thứ 6 hàng tuần"_ — kéo khách giờ trưa

**Flash Sale khác Time Deal như thế nào?**

| | Time Deal | Flash Sale |
|---|---|---|
| **Lặp lại** | Mỗi ngày (VD: giờ trưa nào cũng giảm) | Không lặp — chỉ chạy 1 lần |
| **Giới hạn lượt** | Không có | Có — VD: chỉ 20 đơn đầu |
| **Ai tạo** | Cố định trong hệ thống | Chủ quán tạo lúc nào muốn |
| **Dùng cho** | Khuyến khích giờ thấp điểm | Event, khai trương, xả hàng |

**Khi cả hai cùng áp dụng:** Hệ thống tự chọn deal có lợi hơn cho khách — chỉ áp 1 loại,
không cộng dồn.

---

## PHẦN 1 — HƯỚNG DẪN CHO CHỦ QUÁN

### 1.1. Mở trang quản lý

Vào **ngon-ngon.com/admin.html** → đăng nhập → chọn tab **"Flash Sales"** trên thanh điều hướng.

---

### 1.2. Tạo Flash Sale mới

Nhấn nút **"+ Tạo Flash Sale"** → điền form:

| Trường | Bắt buộc | Hướng dẫn |
|--------|----------|-----------|
| **Tên chương trình** | ✅ | VD: "Flash Sale Khai Trương Tháng 9" — hiển thị trên banner khách |
| **Mô tả thêm** | Không | Dòng phụ nhỏ hơn, VD: "Áp dụng cho 20 khách đầu tiên" |
| **Giảm giá (%)** | ✅ | Từ 1% đến 90% — nhập số nguyên |
| **Sản phẩm áp dụng** | Không | Bỏ trống = **toàn menu**. Hoặc chọn **nhiều sản phẩm cụ thể** bằng cách tick checkbox |
| **Số lượng tối đa** | ✅ | Bao nhiêu đơn được hưởng giảm giá — VD: 20 |
| **Bắt đầu lúc** | ✅ | Ngày giờ bắt đầu — VD: 2024-09-15 14:00 |
| **Kết thúc lúc** | ✅ | Ngày giờ kết thúc — phải sau giờ bắt đầu |

**Lưu ý quan trọng:**
- Thời gian nhập theo **múi giờ Việt Nam (UTC+7)**
- Thời gian kết thúc phải **sau** thời gian bắt đầu ít nhất vài phút
- Số lượng tối đa **tối thiểu là 1**

Nhấn **"Tạo Flash Sale"** → hệ thống lưu ngay, trạng thái ban đầu là **Đã lên lịch**.

---

### 1.3. Hiểu các trạng thái Flash Sale

```
Đã lên lịch ──→ Đang chạy ──→ Đã kết thúc
(chưa tới giờ)  (trong giờ,    (hết giờ hoặc
                còn lượt)       hết lượt)

Bất kỳ lúc nào (trừ Đã kết thúc) ──→ Đã hủy
```

| Trạng thái | Màu sắc | Ý nghĩa |
|-----------|---------|---------|
| **Đã lên lịch** | 🔵 Xanh dương | Đã tạo, chờ đến giờ tự động bật |
| **Đang chạy** | 🟢 Xanh lá | Khách đang thấy banner, giảm giá đang áp dụng |
| **Đã kết thúc** | ⚫ Xám | Hết giờ hoặc hết lượt — tự động dừng |
| **Đã hủy** | 🔴 Đỏ | Chủ quán hủy thủ công |

**Hệ thống tự động cập nhật trạng thái mỗi 10 giây** — không cần thao tác thêm.

---

### 1.4. Hủy Flash Sale đang chạy

Trên danh sách Flash Sales, tìm chương trình muốn dừng → nhấn **"Hủy"** → xác nhận.

> ⚠️ **Không thể hoàn tác** sau khi hủy. Những đơn đã được giảm giá trước khi hủy vẫn giữ nguyên.

---

### 1.5. Xem thống kê

Trong danh sách Flash Sales, mỗi dòng hiển thị:
- **Đã dùng / Tối đa** — VD: `12 / 20 suất` → còn 8 suất
- **Thời gian** — khoảng thời gian áp dụng
- **Trạng thái hiện tại**

---

### 1.6. Màn hình real-time (Admin)

Khi đang mở tab Flash Sales, bảng tự cập nhật ngay khi:
- Hệ thống tự động kích hoạt 1 Flash Sale đến giờ
- Hệ thống tự động kết thúc 1 Flash Sale hết giờ/lượt
- Có đơn hàng được dùng Flash Sale (số lượng còn lại giảm)

---

## PHẦN 2 — TRẢI NGHIỆM KHÁCH HÀNG

### 2.1. Khách thấy gì khi có Flash Sale đang chạy?

Một **banner nổi bật xuất hiện đầu trang menu**, hiển thị:

```
┌─────────────────────────────────────────┐
│  ⚡ FLASH SALE          🕐  01:45:30   │
│  Flash Sale Khai Trương — Giảm 30%      │
│  Áp dụng cho 20 khách đầu tiên          │
│  ████████████░░░░  Còn 8/20 suất        │
└─────────────────────────────────────────┘
```

- **Đồng hồ đếm ngược** — cập nhật mỗi giây
- **Thanh tiến trình** — thể hiện % suất đã dùng
- **Khi còn ≤ 20% suất** → banner chuyển màu đỏ + nhấp nháy để tạo urgency

### 2.2. Giảm giá áp dụng thế nào?

Giảm giá tự động tính khi khách **đặt hàng** — không cần nhập mã voucher.

**Ví dụ:**
- Khách chọn 2 ly trà sữa × 30.000đ = **60.000đ**
- Flash Sale đang chạy giảm 30%
- Hệ thống tự tính: 60.000đ × 70% = **42.000đ**

> Khách không cần làm gì thêm — giảm giá áp dụng tự động khi checkout.

### 2.3. Khi Flash Sale hết suất

Nếu khách đang xem menu nhưng suất cuối cùng vừa hết:
- Banner biến mất khi khách quay lại tab (polling-on-focus)
- Đơn của khách vẫn đặt được — chỉ là không được giảm giá Flash Sale
- Nếu có Time Deal đang chạy, Time Deal vẫn áp dụng bình thường

---

## PHẦN 3 — CÁC TÌNH HUỐNG THƯỜNG GẶP

### Tình huống 1: Muốn chạy Flash Sale ngay lập tức

Điền thời gian **bắt đầu = thời điểm hiện tại** (hoặc 1–2 phút sau).
Hệ thống kích hoạt trong vòng 10 giây.

### Tình huống 2: Lên lịch Flash Sale trước cho sự kiện tương lai

Điền thời gian bắt đầu trong tương lai → nhấn tạo → quên đi.
Hệ thống tự động bật đúng giờ, không cần nhớ hay làm gì thêm.

### Tình huống 3: Flash Sale chạy quá nhanh (hết suất trong vài phút)

Suất quá ít so với lượng khách. Lần sau hãy tăng số lượng tối đa.
Không thể sửa suất của Flash Sale đang chạy — hãy tạo Flash Sale mới.

### Tình huống 4: Muốn dừng sớm hơn giờ kết thúc

Nhấn **"Hủy"** trên danh sách. Flash Sale dừng ngay, banner biến mất.

### Tình huống 5: Khách phản ánh không thấy giảm giá

Kiểm tra:
1. Flash Sale có đang **"Đang chạy"** không?
2. Còn **suất** không? (Đã dùng / Tối đa)
3. Sản phẩm khách mua có thuộc Flash Sale không? (nếu bạn chọn sản phẩm cụ thể — cần ít nhất 1 sản phẩm trùng)
4. Thời gian đặt hàng có **trong khoảng bắt đầu–kết thúc** không?

---

## PHẦN 4 — MẸO KINH DOANH

### Tạo urgency hiệu quả

- **Số suất ít + thời gian ngắn** → tạo cảm giác khan hiếm → khách quyết định nhanh hơn
- VD tốt: 10 suất × 2 tiếng → hợp lý
- VD kém: 500 suất × 1 tuần → không tạo được urgency

### Thời điểm chạy tốt nhất

| Thời điểm | Lý do |
|-----------|-------|
| **11h30–13h30** | Giờ nghỉ trưa — khách KCN đặt đông nhất |
| **17h–18h30** | Tan ca — khách đặt về nhà |
| **Thứ 2 đầu tuần** | Tâm lý "bắt đầu tuần mới" |
| **Cuối tháng** | Gần ngày lương — khách sẵn sàng chi hơn |

### Kết hợp với thông báo Zalo

Trước khi bật Flash Sale ~10 phút, nhắn Zalo cho nhóm khách quen:
> _"⚡ 11h30 hôm nay FLASH SALE giảm 30%, chỉ 20 suất đầu. Đặt sớm kẻo hết!"_

---

## PHẦN 5 — TECHNICAL REFERENCE (Dành cho developer)

### 5.1. Kiến trúc

Flash Sale thuộc **Promotions Bounded Context**, tích hợp với Ordering qua port pattern:

```
Promotions Context          Ordering Context
─────────────────          ──────────────────
FlashSale (entity)    ←── PromotionsPricingPort (ABC định nghĩa ở Ordering domain)
FlashSaleRepository        SqlFlashSalePricingAdapter (implement ở Promotions infra)
scheduler.py               SqlPricingService (nhận promotions_port optional)
```

**Pricing logic** (`ordering/infrastructure/pricing.py`):
1. Tính `time_deal_discount` như cũ
2. Tính `flash_sale_discount` qua `promotions_port.get_best_flash_sale()`
3. Chọn `discount = max(time_deal_discount, flash_sale_discount)`
4. Nếu flash sale thắng → `claim_flash_sale(sale_id)` atomic
5. Nếu claim thất bại (race condition) → fallback về time deal

### 5.2. Race condition prevention

Atomic SQL — PostgreSQL row-level lock:
```sql
UPDATE flash_sales
SET claimed_count = claimed_count + 1
WHERE id = :sale_id
  AND claimed_count < max_quantity
  AND status = 'active'
RETURNING claimed_count
```
Không cần Redis. Không thể oversell.

### 5.3. API Endpoints

**Public (không cần auth):**
```
GET  /api/v1/promotions/flash-sales/active
```
Response: danh sách flash sales đang `ACTIVE`, trả về title, discount_percent,
remaining, ends_at.

**Admin (cần JWT Bearer token):**
```
POST   /api/v1/promotions/flash-sales          → Tạo mới
GET    /api/v1/promotions/flash-sales           → Danh sách tất cả
PATCH  /api/v1/promotions/flash-sales/{id}/cancel  → Hủy
```

**Request body tạo mới:**
```json
{
  "title": "Flash Sale Khai Trương",
  "subtitle": "Chỉ 20 suất đầu tiên",
  "discount_percent": 30,
  "product_ids": [1, 5, 12],
  "max_quantity": 20,
  "starts_at": "2024-09-15T07:00:00Z",
  "ends_at": "2024-09-15T09:00:00Z"
}
```
> `product_ids: []` (mảng rỗng) = áp dụng toàn menu. `product_ids: [1, 5]` = chỉ áp dụng cho sản phẩm có ID 1 và 5. Thời gian là **UTC** (hệ thống tự convert từ form admin).

### 5.4. WebSocket Events (Real-time admin)

| Event type | Khi nào | Payload |
|-----------|---------|---------|
| `flash_sale_started` | Flash sale được kích hoạt | `{sale_id, title, discount_percent, ends_at}` |
| `flash_sale_update` | Có đơn dùng flash sale | `{sale_id, remaining, is_sold_out}` |
| `flash_sale_ended` | Hết giờ / hết lượt / bị hủy | `{sale_id, reason}` |

### 5.5. Database Schema

Bảng `flash_sales` + junction table `flash_sale_products` (migrations `008` + `009`):

```sql
CREATE TABLE flash_sales (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(200) NOT NULL,
    subtitle        VARCHAR(500),
    discount_percent INTEGER NOT NULL,        -- 1–90
    max_quantity    INTEGER NOT NULL,
    claimed_count   INTEGER NOT NULL DEFAULT 0,
    starts_at       TIMESTAMP WITH TIME ZONE NOT NULL,
    ends_at         TIMESTAMP WITH TIME ZONE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    store_id        INTEGER REFERENCES stores(id),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Junction table: nhiều sản phẩm per flash sale (empty = toàn menu)
CREATE TABLE flash_sale_products (
    id              SERIAL PRIMARY KEY,
    flash_sale_id   INTEGER NOT NULL REFERENCES flash_sales(id) ON DELETE CASCADE,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE
);

CREATE INDEX ix_flash_sales_status_time ON flash_sales (status, starts_at, ends_at);
CREATE INDEX ix_flash_sale_products_sale ON flash_sale_products (flash_sale_id);
```

### 5.6. Background Scheduler

`promotions/infrastructure/scheduler.py` — asyncio task chạy trong FastAPI lifespan:
- **Interval:** mỗi 10 giây
- **Tick 1:** Tìm `SCHEDULED` sales có `starts_at <= now` → activate → emit events
- **Tick 2:** Tìm `ACTIVE` sales có `ends_at <= now` → end(reason="time_expired") → emit events
- **Graceful shutdown:** task bị cancel khi app shutdown, không để lại orphan tasks

### 5.7. Files liên quan

```
backend/
├── alembic/versions/008_flash_sales.py
├── alembic/versions/009_flash_sale_multi_products.py
├── app/promotions/
│   ├── domain/
│   │   ├── flash_sale.py          ← Entity + Repo ABC
│   │   └── events.py              ← Domain events
│   ├── application/
│   │   ├── flash_sale_use_cases.py
│   │   └── event_handlers.py      ← WS broadcast
│   ├── infrastructure/
│   │   ├── flash_sale_repository.py
│   │   ├── flash_sale_pricing_adapter.py
│   │   └── scheduler.py
│   └── presentation/
│       └── flash_sale_router.py
├── app/ordering/domain/
│   └── promotions_port.py         ← Port ABC
└── tests/unit/
    ├── test_flash_sale_domain.py
    ├── test_flash_sale_use_cases.py
    └── test_pricing_with_flash_sale.py

frontend/
├── src/admin/flash-sales.js       ← Admin CRUD + real-time
├── src/customer/flash-sale.js     ← Banner + countdown
├── admin.html                     ← Tab Flash Sales + modal
└── index.html                     ← Banner placeholder + CSS
```

---

## PHỤ LỤC — CÂU HỎI THƯỜNG GẶP

**Q: Flash Sale có áp dụng cho đơn giao hàng không?**
A: Có. Flash Sale áp dụng cho cả đơn tại quán lẫn đơn giao hàng, không phân biệt.

**Q: Khách có thể đặt nhiều đơn để hưởng Flash Sale nhiều lần không?**
A: Về kỹ thuật có thể. Flash Sale giới hạn theo số đơn, không theo khách.
Nếu cần giới hạn 1 lần/khách, đây là tính năng nâng cấp cho phiên bản sau.

**Q: Có thể chạy 2 Flash Sale cùng lúc không?**
A: Có thể tạo nhiều Flash Sale, nhưng hệ thống chỉ áp dụng 1 deal tốt nhất cho mỗi đơn.
Không nên chạy 2 Flash Sale cùng lúc vì sẽ gây nhầm lẫn cho khách.

**Q: Chỉnh sửa Flash Sale sau khi tạo được không?**
A: Hiện tại không. Nếu cần thay đổi, hãy hủy Flash Sale cũ và tạo mới.

**Q: Cập nhật banner cho khách đang xem menu mất bao lâu?**
A: Khi khách chuyển qua app khác rồi quay lại tab menu (trong vòng vài giây).
Hệ thống dùng "polling-on-focus" — phù hợp mạng 4G, không tốn pin.
