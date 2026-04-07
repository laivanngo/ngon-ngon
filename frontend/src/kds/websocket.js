/**
 * KDS WebSocket — Nhận đơn hàng mới real-time
 * ==============================================
 * Khi có đơn mới → reload orders, phát âm thanh, rung điện thoại, flash card.
 * Auto reconnect với exponential backoff khi mất kết nối.
 */
import { getToken } from './auth.js';
import { lockKDS } from './auth.js';
import { loadOrders, switchTab, getCurrentTab } from './orders.js';
import { playSound, vibrate } from './sound.js';

let ws = null;
let wsRetry = 0;
let wsTimer = null;

export function connectWS() {
  if (!getToken()) return;
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/api/v1/ws/orders?token=${getToken()}`;

  try { ws = new WebSocket(url); } catch (e) { scheduleReconnect(); return; }

  ws.onopen = () => {
    wsRetry = 0;
    document.getElementById('wsDot').className = 'kds-ws on';
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'new_order') {
        loadOrders().then(() => {
          playSound();
          vibrate();
          const card = document.querySelector(`[data-id="${msg.data.public_id}"]`);
          if (card) card.classList.add('flash');
          if (getCurrentTab() !== 'pending') switchTab('pending');
        });
      } else if (msg.type === 'status_change') {
        loadOrders();
      } else if (msg.type === 'ping') {
        try { ws.send('pong'); } catch (e) {}
      }
    } catch (e) {}
  };

  ws.onclose = (e) => {
    document.getElementById('wsDot').className = 'kds-ws';
    if (e.code === 4001) { lockKDS(); return; }
    if (getToken()) scheduleReconnect();
  };

  ws.onerror = () => {
    document.getElementById('wsDot').className = 'kds-ws';
  };
}

function scheduleReconnect() {
  if (wsTimer) clearTimeout(wsTimer);
  const delay = Math.min(1000 * Math.pow(2, wsRetry), 30000);
  wsRetry++;
  document.getElementById('wsDot').className = 'kds-ws reconnecting';
  wsTimer = setTimeout(() => { if (getToken()) connectWS(); }, delay);
}

export function disconnectWS() {
  if (wsTimer) clearTimeout(wsTimer);
  if (ws) { ws.onclose = null; ws.close(); ws = null; }
}
