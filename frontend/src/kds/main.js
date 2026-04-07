/**
 * KDS Main — Entry Point
 * ========================
 * Kitchen Display System: PIN login → WebSocket real-time orders → timer.
 * Expose functions lên window cho onclick="" handlers trong HTML.
 */
import { restoreSession, pinKey, pinBackspace, pinClear, lockKDS, getToken } from './auth.js';
import { loadOrders, switchTab, updateStatus, cancelOrder, startTimerUpdates, stopTimerUpdates } from './orders.js';
import { connectWS, disconnectWS } from './websocket.js';
import { toggleSound, restoreSoundPreference, requestWakeLock } from './sound.js';

// ══════════════════════════════════════════════════
// EXPOSE TO WINDOW — cho onclick="" trong HTML
// ══════════════════════════════════════════════════
window.pinKey = pinKey; // legacy
window.pinBackspace = pinBackspace; // legacy
window.pinClear = pinClear; // legacy
window.switchTab = switchTab; // legacy
window.updateStatus = updateStatus; // legacy
window.cancelOrder = cancelOrder; // legacy
window.toggleSound = toggleSound; // legacy
window.lockKDS = lockKDS; // legacy

// ── Show KDS after authentication ──

function showKDS() {
  document.getElementById('pinScreen').style.display = 'none';
  document.getElementById('kdsApp').classList.add('show');
  loadOrders();
  connectWS();
  startTimerUpdates();
  requestWakeLock();
}

// ── Event Listeners ──

// Auth event từ auth.js khi PIN login thành công
document.addEventListener('kds-authenticated', () => showKDS());

// Lock event từ auth.js — cleanup WS và timer
document.addEventListener('kds-locked', () => {
  disconnectWS();
  stopTimerUpdates();
});

// Re-acquire wake lock khi page visible lại + refresh orders
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && getToken()) {
    requestWakeLock();
    loadOrders();
  }
});

// Fallback polling mỗi 60 giây (WS có thể disconnect)
setInterval(() => { if (getToken()) loadOrders(); }, 60000);

// ── Init ──

restoreSoundPreference();

// Restore session nếu có token lưu trong localStorage
if (restoreSession()) {
  showKDS();
}

export { showKDS };
