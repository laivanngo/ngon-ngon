/**
 * Admin WebSocket — Real-time order notifications
 * ==================================================
 * WHY reconnect logic:
 * - Mạng KCN hay bị ngắt quãng → cần tự reconnect
 * - Exponential backoff: 1s → 2s → 4s → 8s → ... → max 30s
 * - Tránh spam reconnect khi server down
 */
import { getToken } from '../shared/api.js';
import { handleNewOrder } from './notifications.js';
import { loadDashboard } from './dashboard.js';
import { loadOrders, getCurrentFilter } from './orders.js';
import { loadProducts } from './products.js';
import { loadFlashSales } from './flash-sales.js';

let ws = null;
let wsReconnectTimer = null;
let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT_DELAY = 30000;

/**
 * Kết nối WebSocket tới server.
 */
export function connectWS() {
  const token = getToken();
  if (!token) return;

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${location.host}/api/v1/ws/orders?token=${token}`;

  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    console.warn('[WS] Failed to create WebSocket:', e);
    updateWSStatus('off');
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    console.log('[WS] Connected');
    wsReconnectAttempts = 0;
    updateWSStatus('on');
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);

      if (msg.type === 'new_order') {
        handleNewOrder(msg.data);
      } else if (msg.type === 'status_change') {
        console.log('[WS] Status change:', msg.data.public_id, msg.data.old_status, '→', msg.data.new_status);
        loadDashboard();
        if (document.getElementById('tabOrders').style.display !== 'none') {
          loadOrders(getCurrentFilter());
        }
      } else if (msg.type === 'menu_updated') {
        console.log('[WS] Menu updated by admin');
        if (document.getElementById('tabProducts')?.style.display !== 'none') {
          loadProducts();
        }
        loadDashboard();
      } else if (msg.type === 'flash_sale_started' || msg.type === 'flash_sale_update' || msg.type === 'flash_sale_ended') {
        console.log('[WS] Flash Sale event:', msg.type, msg.data);
        if (document.getElementById('tabFlashSales')?.style.display !== 'none') {
          loadFlashSales();
        }
      } else if (msg.type === 'ping') {
        try { ws.send('pong'); } catch (e) {}
      } else if (msg.type === 'connected') {
        console.log('[WS]', msg.message);
      }
    } catch (e) {
      console.warn('[WS] Invalid message:', e);
    }
  };

  ws.onclose = (event) => {
    console.log(`[WS] Closed: code=${event.code} reason=${event.reason || 'none'}`);
    updateWSStatus('off');
    if (event.code === 4001) {
      console.log('[WS] Auth failed, not reconnecting');
      return;
    }
    if (getToken()) scheduleReconnect();
  };

  ws.onerror = () => {
    updateWSStatus('off');
  };
}

/**
 * Lên lịch reconnect với exponential backoff.
 */
export function scheduleReconnect() {
  if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
  const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), WS_MAX_RECONNECT_DELAY);
  wsReconnectAttempts++;
  updateWSStatus('reconnecting');
  console.log(`[WS] Reconnecting in ${delay / 1000}s (attempt ${wsReconnectAttempts})...`);
  wsReconnectTimer = setTimeout(() => {
    if (getToken()) connectWS();
  }, delay);
}

/**
 * Ngắt WebSocket (khi logout).
 */
export function disconnectWS() {
  if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
  if (ws) {
    ws.onclose = null;
    ws.close();
    ws = null;
  }
  updateWSStatus('off');
}

/**
 * Cập nhật UI indicator trạng thái WebSocket.
 */
function updateWSStatus(state) {
  const dot = document.getElementById('wsDot');
  const label = document.getElementById('wsLabel');
  if (!dot || !label) return;

  dot.className = 'ws-dot';
  if (state === 'on') {
    dot.classList.add('on');
    label.textContent = 'Trực tuyến';
  } else if (state === 'reconnecting') {
    dot.classList.add('reconnecting');
    label.textContent = 'Đang kết nối lại...';
  } else {
    label.textContent = 'Mất kết nối';
  }
}
