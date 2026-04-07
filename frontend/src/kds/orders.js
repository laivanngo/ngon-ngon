/**
 * KDS Orders — Load, render, update trạng thái đơn hàng
 * =======================================================
 * Hiển thị đơn hàng theo tab (MỚI / PHA CHẾ / GIAO / XONG).
 * Timer đếm thời gian chờ: xanh < 5 phút, vàng < 10 phút, đỏ > 10 phút.
 */
import { getToken } from './auth.js';
import { lockKDS } from './auth.js';
import { fmtP, fmtPd, esc } from '../shared/formatters.js';

const BASE = '/api/v1/kds';

/** Tất cả orders từ server */
let orders = [];
/** Tab hiện tại */
let currentTab = 'pending';
/** Timestamp lần load gần nhất — dùng tính elapsed time */
let _lastLoadTime = Date.now();
/** Timer interval ID */
let timerInterval = null;

export function getOrders() { return orders; }

// ── Load orders from API ──

export async function loadOrders() {
  try {
    const resp = await fetch(`${BASE}/orders?token=${getToken()}`); // noqa — KDS endpoint dùng query param auth
    if (resp.status === 401) { lockKDS(); return; }
    const data = await resp.json();
    orders = data.orders || [];
    _lastLoadTime = Date.now();
    renderOrders();
    updateBadges();
  } catch (e) { console.warn('[KDS] Load failed:', e); }
}

// ── Render ──

export function renderOrders() {
  const container = document.getElementById('orderContainer');
  // "pending" tab cũng hiện "confirmed" (cả hai đều là "mới" từ góc nhìn bếp)
  let filtered;
  if (currentTab === 'pending') {
    filtered = orders.filter(o => o.status === 'pending' || o.status === 'confirmed');
  } else {
    filtered = orders.filter(o => o.status === currentTab);
  }

  if (filtered.length === 0) {
    const msgs = {
      pending: ['☕', 'Chưa có đơn mới'], preparing: ['🍳', 'Không có đơn đang pha chế'],
      delivering: ['🛵', 'Không có đơn đang giao'], done: ['✅', 'Chưa có đơn hoàn thành'],
    };
    const [icon, txt] = msgs[currentTab] || ['📋', 'Trống'];
    container.innerHTML = `<div class="kds-empty"><div class="kds-empty-icon">${icon}</div><div class="kds-empty-text">${txt}</div></div>`;
    return;
  }
  container.innerHTML = filtered.map(o => renderCard(o)).join('');
}

function renderCard(o) {
  const elapsed = o.elapsed_seconds + Math.floor((Date.now() - _lastLoadTime) / 1000);
  const timerStr = formatTimer(elapsed);
  const timerClass = elapsed < 300 ? 'green' : elapsed < 600 ? 'yellow' : 'red';

  const isScheduled = o.delivery_type === 'scheduled';
  const deliveryBadgeHtml = isScheduled
    ? `<span class="kds-del-badge scheduled">🕐 Hẹn ${esc(o.scheduled_time || '')}</span>`
    : `<span class="kds-del-badge immediate">🚀 Giao liền</span>`;

  const itemsHtml = o.items.map(it => {
    const detailsHtml = it.details ? `<div class="kds-item-details">${esc(it.details)}</div>` : '';
    return `<div class="kds-item"><div class="kds-item-main"><span class="kds-item-qty">${it.quantity}×</span><span class="kds-item-name">${esc(it.name)}</span><span class="kds-item-price">${fmtP(it.unit_price * it.quantity)}</span></div>${detailsHtml}</div>`;
  }).join('');

  const noteHtml = o.note ? `<div class="kds-note">📝 ${esc(o.note)}</div>` : '';
  const actionsHtml = getActions(o.status, o.public_id);

  return `
    <div class="kds-card" data-s="${o.status}" data-id="${o.public_id}">
      <div class="kds-card-head">
        <span class="kds-order-id">#${o.public_id.substring(0, 8)}</span>
        <div style="display:flex;align-items:center;gap:6px">
          ${deliveryBadgeHtml}
          <span class="kds-timer ${timerClass}" data-created="${o.created_at}">${timerStr}</span>
        </div>
      </div>
      <div class="kds-items">${itemsHtml}</div>
      <div class="kds-customer">
        <div class="kds-cust-row"><strong>👤 ${esc(o.customer_name)}</strong></div>
        <div class="kds-cust-row">📱 <a href="tel:${o.phone}" style="color:var(--blue);font-weight:700;font-size:15px">${o.phone}</a></div>
        <div class="kds-cust-row">📍 <span style="color:var(--text);font-weight:600">${esc(o.address)}</span></div>
        ${isScheduled ? `<div class="kds-sched-alert">🕐 HẸN GIAO LÚC ${esc(o.scheduled_time || '?')}</div>` : ''}
        ${noteHtml}
      </div>
      <div class="kds-total">💰 ${fmtPd(o.total)}</div>
      ${actionsHtml ? `<div class="kds-actions">${actionsHtml}</div>` : ''}
    </div>`;
}

function getActions(status, pid) {
  const map = {
    pending: `<button class="kds-btn prepare" onclick="updateStatus('${pid}','preparing')">🍳 Bắt đầu pha chế</button><button class="kds-btn cancel-btn" onclick="cancelOrder('${pid}')">✕</button>`,
    confirmed: `<button class="kds-btn prepare" onclick="updateStatus('${pid}','preparing')">🍳 Bắt đầu pha chế</button>`,
    preparing: `<button class="kds-btn deliver" onclick="updateStatus('${pid}','delivering')">🛵 Xong — Bắt đầu giao</button>`,
    delivering: `<button class="kds-btn done-btn" onclick="updateStatus('${pid}','done')">✅ Đã giao xong</button>`,
  };
  return map[status] || '';
}

// ── Update order status ──

export async function updateStatus(publicId, newStatus) {
  try {
    const resp = await fetch(`${BASE}/orders/${publicId}/status?token=${getToken()}`, { // noqa — KDS endpoint
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    });
    if (resp.status === 401) { lockKDS(); return; }
    if (!resp.ok) { const err = await resp.json().catch(() => ({})); alert(err.detail || 'Lỗi cập nhật'); return; }
    const order = orders.find(o => o.public_id === publicId);
    if (order) order.status = newStatus;
    renderOrders(); updateBadges();
  } catch (e) { alert('Lỗi kết nối: ' + e.message); }
}

export function cancelOrder(pid) {
  if (confirm('Hủy đơn này?')) updateStatus(pid, 'cancelled');
}

// ── Tabs ──

export function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.kds-tab').forEach(t => t.classList.remove('on'));
  document.querySelector(`.kds-tab[data-s="${tab}"]`).classList.add('on');
  renderOrders();
}

export function getCurrentTab() { return currentTab; }

function updateBadges() {
  const counts = { pending: 0, preparing: 0, delivering: 0, done: 0 };
  orders.forEach(o => {
    if (o.status === 'pending' || o.status === 'confirmed') counts.pending++;
    else if (counts[o.status] !== undefined) counts[o.status]++;
  });
  Object.keys(counts).forEach(s => {
    const el = document.getElementById('badge-' + s);
    if (el) { el.textContent = counts[s]; el.style.display = counts[s] > 0 ? '' : 'none'; }
  });
}

// ── Timer ──

function formatTimer(seconds) {
  if (seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60), s = seconds % 60;
  return m + ':' + (s < 10 ? '0' : '') + s;
}

/** Cập nhật timer mỗi giây — hiện thời gian chờ từ khi đơn tạo */
export function startTimerUpdates() {
  timerInterval = setInterval(() => {
    document.querySelectorAll('.kds-timer').forEach(el => {
      const created = new Date(el.dataset.created).getTime();
      const elapsed = Math.floor((Date.now() - created) / 1000);
      el.textContent = formatTimer(elapsed);
      el.className = 'kds-timer ' + (elapsed < 300 ? 'green' : elapsed < 600 ? 'yellow' : 'red');
    });
  }, 1000);
}

export function stopTimerUpdates() {
  if (timerInterval) clearInterval(timerInterval);
}
