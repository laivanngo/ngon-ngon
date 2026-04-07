/**
 * Admin Orders — Quản lý đơn hàng
 * =================================
 * Load, render, filter, update status đơn hàng.
 */
import { api } from '../shared/api.js';
import { fmtP, fmtPd, esc } from '../shared/formatters.js';
import { STATUS_LABELS } from '../shared/constants.js';
import { loadDashboard } from './dashboard.js';

/** Filter hiện tại ('' = tất cả, 'pending', 'confirmed', ...) */
let currentFilter = '';

export function getCurrentFilter() { return currentFilter; }

/**
 * Tải danh sách đơn hàng, có thể filter theo status.
 */
export async function loadOrders(statusFilter) {
  if (statusFilter !== undefined) currentFilter = statusFilter;
  const list = document.getElementById('orderList');
  list.innerHTML = '<div class="loading"><span class="spinner"></span>Đang tải...</div>';

  try {
    let url = '/admin/orders?limit=50';
    if (currentFilter) url += `&status=${currentFilter}`;
    const data = await api(url);

    if (!data.items || data.items.length === 0) {
      list.innerHTML = '<div class="empty-state"><div class="icon">📭</div>Không có đơn hàng nào</div>';
      return;
    }
    list.innerHTML = data.items.map(order => renderOrderCard(order)).join('');
  } catch (err) {
    list.innerHTML = `<div class="empty-state">Lỗi: ${err.message}</div>`;
  }
}

/**
 * Render 1 order card HTML.
 */
function renderOrderCard(o) {
  const statusClass = `status-${o.status}`;

  const itemsHtml = o.items.map(it => {
    let desc = it.product_name;
    if (it.size) desc += ` (${it.size})`;
    desc += ` ×${it.quantity}`;
    const lineTotal = it.unit_price * it.quantity;
    return `<div class="order-item-row"><span>${desc}</span><span>${fmtP(lineTotal)}</span></div>`;
  }).join('');

  const deliveryBadge = o.delivery_type === 'scheduled'
    ? `<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:#FFF3E0;color:#E65100">🕐 Hẹn ${esc(o.scheduled_time || '')}</span>`
    : `<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:#E8F5E9;color:#2E7D32">🚀 Giao liền</span>`;

  const actionsHtml = getAvailableActions(o.status, o.public_id);

  const time = new Date(o.created_at).toLocaleString('vi-VN', {
    hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit',
  });

  return `
    <div class="order-card" id="order-${o.public_id}">
      <div class="order-head" onclick="toggleOrder('${o.public_id}')">
        <div>
          <div class="order-id">#${o.public_id.substring(0, 8)} — ${fmtPd(o.total)}</div>
          <div class="order-meta">${time} • ${o.customer_name} • ${o.phone} ${deliveryBadge}</div>
        </div>
        <span class="order-status ${statusClass}">${STATUS_LABELS[o.status] || o.status}</span>
      </div>
      <div class="order-body" id="body-${o.public_id}">
        <div class="order-items">${itemsHtml}</div>
        <div class="order-customer">
          👤 ${esc(o.customer_name)}<br>
          📱 <a href="tel:${o.phone}">${o.phone}</a><br>
          📍 ${esc(o.address)}<br>
          ${o.delivery_type === 'scheduled'
            ? '🕐 <strong style="color:#E65100">Hẹn giao lúc ' + esc(o.scheduled_time || '') + '</strong>'
            : '🚀 Giao liền'}
          ${o.note ? '<br>📝 ' + esc(o.note) : ''}
        </div>
        ${actionsHtml ? `<div class="order-actions">${actionsHtml}</div>` : ''}
      </div>
    </div>`;
}

/**
 * Tạo HTML cho action buttons dựa trên status hiện tại.
 */
function getAvailableActions(status, publicId) {
  const pid = publicId;
  const map = {
    pending: `
      <button class="action-btn confirm" onclick="updateStatus('${pid}','confirmed')">✅ Xác nhận</button>
      <button class="action-btn cancel" onclick="updateStatus('${pid}','cancelled')">❌ Hủy</button>`,
    confirmed: `
      <button class="action-btn prepare" onclick="updateStatus('${pid}','preparing')">🍳 Bắt đầu pha chế</button>
      <button class="action-btn cancel" onclick="updateStatus('${pid}','cancelled')">❌ Hủy</button>`,
    preparing: `
      <button class="action-btn deliver" onclick="updateStatus('${pid}','delivering')">🛵 Bắt đầu giao</button>`,
    delivering: `
      <button class="action-btn done" onclick="updateStatus('${pid}','done')">✅ Hoàn thành</button>`,
  };
  return map[status] || '';
}

/**
 * Toggle mở/đóng chi tiết đơn hàng.
 */
export function toggleOrder(publicId) {
  const body = document.getElementById(`body-${publicId}`);
  body.classList.toggle('show');
}

/**
 * Cập nhật trạng thái đơn hàng.
 */
export async function updateStatus(publicId, newStatus) {
  if (newStatus === 'cancelled' && !confirm('Bạn có chắc muốn hủy đơn này?')) return;

  try {
    await api(`/admin/orders/${publicId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: newStatus }),
    });
    loadOrders();
    loadDashboard();
  } catch (err) {
    alert('Lỗi: ' + err.message);
  }
}

/**
 * Filter đơn hàng theo status (từ filter buttons).
 */
export function filterOrders(btn, status) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  loadOrders(status);
}

/**
 * Khởi tạo auto-refresh đơn hàng mỗi 60 giây.
 * WHY giữ polling: WS có thể bị ngắt (proxy timeout, mạng yếu).
 * 60s thay vì 30s vì WS đã handle real-time.
 */
export function initOrderAutoRefresh() {
  setInterval(() => {
    import('../shared/api.js').then(({ getToken }) => {
      if (getToken() && document.getElementById('tabOrders').style.display !== 'none') {
        loadOrders();
      }
    });
  }, 60000);
}
