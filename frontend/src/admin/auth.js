/**
 * Admin Auth — Đăng nhập, đăng xuất, khôi phục phiên
 * =====================================================
 * WHY check localStorage on load: admin refresh page → auto re-login
 * mà không cần nhập lại mật khẩu.
 */
import { BASE } from '../shared/constants.js';
import { setToken } from '../shared/api.js';
import { disconnectWS } from './websocket.js';

/**
 * Kiểm tra token đã lưu trong localStorage.
 * Chạy tự động khi trang tải xong.
 */
export function checkSavedAuth() {
  try {
    const saved = localStorage.getItem('nn_admin_token');
    if (saved) {
      setToken(saved);
      showApp();
    }
  } catch (e) { /* localStorage blocked */ }
}

/**
 * Xử lý đăng nhập khi bấm nút "Đăng nhập".
 */
export async function doLogin() {
  const user = document.getElementById('loginUser').value.trim();
  const pass = document.getElementById('loginPass').value;
  const errorEl = document.getElementById('loginError');
  errorEl.textContent = '';

  if (!user || !pass) { errorEl.textContent = 'Vui lòng nhập đầy đủ'; return; }

  try {
    const resp = await fetch(`${BASE}/admin/login`, { // noqa — login endpoint không cần JWT
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pass }),
    });
    const data = await resp.json();

    if (!resp.ok) {
      errorEl.textContent = data.detail || 'Đăng nhập thất bại';
      return;
    }

    setToken(data.access_token);
    try { localStorage.setItem('nn_admin_token', data.access_token); } catch (e) {}
    showApp();

  } catch (err) {
    errorEl.textContent = 'Không thể kết nối server';
  }
}

/**
 * Đăng xuất: ngắt WebSocket, xóa token, về màn hình login.
 */
export function doLogout() {
  disconnectWS();
  setToken(null);
  try { localStorage.removeItem('nn_admin_token'); } catch (e) {}
  document.getElementById('adminApp').classList.remove('show');
  document.getElementById('loginScreen').style.display = '';
  document.getElementById('loginPass').value = '';
}

/**
 * Hiện admin app sau khi login thành công.
 * Dispatch event để main.js bắt và khởi tạo app.
 * WHY event: tránh circular dependency giữa auth.js ↔ main.js
 */
function showApp() {
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('adminApp').classList.add('show');
  document.getElementById('adminName').textContent = '👤 Admin';

  // main.js lắng nghe event này để gọi loadDashboard(), connectWS()
  document.dispatchEvent(new CustomEvent('admin-authenticated'));
}
