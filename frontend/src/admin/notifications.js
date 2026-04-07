/**
 * Admin Notifications — Âm thanh, toast, browser notification
 * =============================================================
 * Xử lý khi nhận đơn hàng mới qua WebSocket:
 * 1. Phát âm thanh thông báo
 * 2. Hiện toast notification (trong app)
 * 3. Browser notification (khi tab ẩn)
 * 4. Cập nhật dashboard + order list
 */
import { fmtPd, esc } from '../shared/formatters.js';
import { loadDashboard } from './dashboard.js';
import { loadOrders, getCurrentFilter } from './orders.js';

/** Trạng thái bật/tắt âm thanh */
let soundEnabled = true;

/**
 * Xử lý đơn hàng mới từ WebSocket.
 */
export function handleNewOrder(order) {
  console.log('[WS] New order:', order.public_id);
  playNotifSound();
  showToast(order);
  loadDashboard();
  if (document.getElementById('tabOrders').style.display !== 'none') {
    loadOrders(getCurrentFilter());
  }
  showBrowserNotification(order);
}

/**
 * Bật/tắt âm thanh thông báo.
 */
export function toggleSound() {
  soundEnabled = !soundEnabled;
  const btn = document.getElementById('soundToggle');
  btn.textContent = soundEnabled ? '🔔' : '🔕';
  btn.classList.toggle('off', !soundEnabled);
  btn.title = soundEnabled ? 'Tắt âm thanh thông báo' : 'Bật âm thanh thông báo';
  try { localStorage.setItem('nn_admin_sound', soundEnabled ? '1' : '0'); } catch (e) {}
  if (soundEnabled) playNotifSound();
}

/**
 * Phát âm thanh thông báo đơn mới.
 */
export function playNotifSound() {
  if (!soundEnabled) return;
  const audio = document.getElementById('notifSound');
  if (!audio) return;
  audio.currentTime = 0;
  audio.play().catch(err => {
    console.warn('[Sound] Autoplay blocked:', err.message);
  });
}

/**
 * Khôi phục preference âm thanh từ localStorage.
 * Gọi 1 lần khi init.
 */
export function restoreSoundPreference() {
  try {
    const saved = localStorage.getItem('nn_admin_sound');
    if (saved === '0') {
      soundEnabled = false;
      const btn = document.getElementById('soundToggle');
      if (btn) { btn.textContent = '🔕'; btn.classList.add('off'); }
    }
  } catch (e) {}
}

/**
 * Hiện toast notification trong app khi có đơn mới.
 */
export function showToast(order) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const time = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `
    <div class="toast-title">🛎️ Đơn hàng mới!</div>
    <div class="toast-body">
      <strong>${esc(order.customer_name)}</strong> — ${fmtPd(order.total)} (${order.item_count} món)<br>
      📱 ${order.phone} • 📍 ${esc(order.address || '')}
    </div>
    <div class="toast-time">${time}</div>
  `;

  // Click toast → chuyển sang tab đơn hàng
  toast.onclick = () => {
    // Import dynamically to avoid pulling in switchTab dependency chain
    document.dispatchEvent(new CustomEvent('admin-switch-tab', { detail: 'orders' }));
    toast.classList.add('hide');
    setTimeout(() => toast.remove(), 300);
  };

  container.prepend(toast);

  // Auto dismiss sau 10 giây
  setTimeout(() => {
    if (toast.parentNode) {
      toast.classList.add('hide');
      setTimeout(() => toast.remove(), 300);
    }
  }, 10000);

  // Tối đa 5 toasts
  while (container.children.length > 5) {
    container.lastChild.remove();
  }
}

/**
 * Browser notification khi tab ẩn.
 * WHY: nhân viên có thể đang ở tab khác, vẫn cần biết có đơn mới.
 */
function showBrowserNotification(order) {
  if (document.visibilityState !== 'hidden') return;
  if (!('Notification' in window)) return;

  if (Notification.permission === 'granted') {
    new Notification('🛎️ Ngon-Ngon — Đơn hàng mới!', {
      body: `${order.customer_name} — ${fmtPd(order.total)} (${order.item_count} món)\n📱 ${order.phone}`,
      icon: '/manifest.json',
      tag: 'new-order-' + order.public_id,
    });
  } else if (Notification.permission === 'default') {
    Notification.requestPermission();
  }
}

/**
 * Yêu cầu quyền browser notification (gọi 1 lần khi login).
 */
export function requestNotificationPermission() {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }
}
