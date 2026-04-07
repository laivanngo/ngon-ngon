/**
 * Admin Flash Sales — CRUD management
 * =======================================
 * Admin tạo, xem danh sách, hủy flash sales.
 * Hỗ trợ chọn nhiều sản phẩm cụ thể hoặc toàn menu.
 */

import { api } from '../shared/api.js';
import { closeModal, escapeHtml } from '../shared/ui.js';
import { _productData, loadProducts } from './products.js';

const STATUS_BADGE = {
  scheduled: '<span class="badge badge-info">Lên lịch</span>',
  active: '<span class="badge badge-success">Đang chạy</span>',
  ended: '<span class="badge badge-secondary">Đã kết thúc</span>',
  cancelled: '<span class="badge badge-danger">Đã hủy</span>',
};

/** Load + render danh sách flash sales */
export async function loadFlashSales() {
  const el = document.getElementById('flashSalesList');
  if (!el) return;

  try {
    const data = await api('/promotions/flash-sales');
    const sales = data.flash_sales || [];

    if (!sales.length) {
      el.innerHTML = '<p style="text-align:center;color:#888">Chưa có Flash Sale nào</p>';
      return;
    }

    el.innerHTML = sales.map(s => {
      const start = new Date(s.starts_at).toLocaleString('vi-VN');
      const end = new Date(s.ends_at).toLocaleString('vi-VN');
      const badge = STATUS_BADGE[s.status] || s.status;
      const canCancel = s.status === 'scheduled' || s.status === 'active';

      // Hiển thị sản phẩm áp dụng
      const productLabel = s.product_ids && s.product_ids.length
        ? ` · ${s.product_ids.length} sản phẩm`
        : ' · Toàn menu';

      return `
        <div class="flash-sale-card" style="border:1px solid #ddd;border-radius:8px;padding:12px;margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <strong>${escapeHtml(s.title)}</strong> ${badge}
              <div style="font-size:13px;color:#666;margin-top:4px">
                ⚡ Giảm ${s.discount_percent}% · ${s.claimed_count}/${s.max_quantity} đã dùng
                ${productLabel}
              </div>
              <div style="font-size:12px;color:#999;margin-top:2px">
                ${start} → ${end}
              </div>
            </div>
            ${canCancel ? `<button onclick="cancelFlashSale(${s.id})" class="btn btn-sm btn-danger">Hủy</button>` : ''}
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    el.innerHTML = `<p style="color:red">Lỗi: ${e.message}</p>`;
  }
}

/** Mở modal tạo flash sale mới */
export async function openFlashSaleModal() {
  const modal = document.getElementById('flashSaleModal');
  if (!modal) return;

  // Reset form
  document.getElementById('fsTitle').value = '';
  document.getElementById('fsSubtitle').value = '';
  document.getElementById('fsDiscount').value = '50';
  document.getElementById('fsMaxQty').value = '20';

  // Default: start in 10 min, end in 2 hours
  const now = new Date();
  const start = new Date(now.getTime() + 10 * 60000);
  const end = new Date(now.getTime() + 2 * 3600000);
  document.getElementById('fsStartsAt').value = _toLocalISOString(start);
  document.getElementById('fsEndsAt').value = _toLocalISOString(end);

  modal.style.display = 'flex';

  // Load product checkboxes (ensure product data available)
  await _loadProductCheckboxes();
}

/**
 * Render product checkboxes cho multi-select.
 * Pattern giống loadToppingCheckboxes() trong product-modal.js.
 */
async function _loadProductCheckboxes() {
  const container = document.getElementById('fsProductCheckboxes');
  if (!container) return;

  // Đảm bảo product data đã load
  if (!_productData) {
    container.innerHTML = '<span style="color:#999;font-size:12px">Đang tải sản phẩm...</span>';
    await loadProducts();
  }

  // Gom tất cả sản phẩm active từ mọi danh mục
  const allProducts = [];
  for (const cat of (_productData || [])) {
    for (const p of cat.products) {
      if (p.is_active) {
        allProducts.push({ ...p, catEmoji: cat.emoji, catName: cat.name });
      }
    }
  }

  if (!allProducts.length) {
    container.innerHTML = '<span style="color:#999;font-size:12px">Chưa có sản phẩm nào</span>';
    return;
  }

  container.innerHTML = allProducts.map(p =>
    `<label style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;border:1.5px solid var(--bdr);border-radius:6px;cursor:pointer;font-size:12px;transition:all .15s" title="${escapeHtml(p.catName)}">
      <input type="checkbox" value="${p.id}" style="accent-color:var(--brand)" onchange="this.parentElement.style.borderColor=this.checked?'var(--brand)':'var(--bdr)';this.parentElement.style.background=this.checked?'var(--brand-lt)':''">
      ${escapeHtml(p.emoji)} ${escapeHtml(p.name)}
    </label>`
  ).join('');
}

/** Tạo flash sale */
export async function createFlashSale() {
  const title = document.getElementById('fsTitle').value.trim();
  const subtitle = document.getElementById('fsSubtitle').value.trim() || null;
  const discount_percent = parseInt(document.getElementById('fsDiscount').value);
  const max_quantity = parseInt(document.getElementById('fsMaxQty').value);
  const starts_at = document.getElementById('fsStartsAt').value;
  const ends_at = document.getElementById('fsEndsAt').value;

  // Thu thập product IDs từ checkboxes
  const productChecks = document.querySelectorAll('#fsProductCheckboxes input[type=checkbox]:checked');
  const product_ids = [...productChecks].map(cb => parseInt(cb.value));

  if (!title) return alert('Vui lòng nhập tên Flash Sale');
  if (!starts_at || !ends_at) return alert('Vui lòng chọn thời gian');

  try {
    await api('/promotions/flash-sales', {
      method: 'POST',
      body: JSON.stringify({
        title, subtitle, discount_percent, max_quantity,
        product_ids,
        starts_at: new Date(starts_at).toISOString(),
        ends_at: new Date(ends_at).toISOString(),
      }),
    });
    closeModal('flashSaleModal');
    loadFlashSales();
  } catch (e) {
    alert('Lỗi: ' + e.message);
  }
}

/** Hủy flash sale */
export async function cancelFlashSale(id) {
  if (!confirm('Bạn có chắc muốn hủy Flash Sale này?')) return;

  try {
    await api(`/promotions/flash-sales/${id}/cancel`, { method: 'PATCH' });
    loadFlashSales();
  } catch (e) {
    alert('Lỗi: ' + e.message);
  }
}

/** Helper: Date → "YYYY-MM-DDTHH:mm" cho input[type=datetime-local] */
function _toLocalISOString(d) {
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
