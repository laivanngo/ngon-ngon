/**
 * KDS Auth — PIN login, session restore, lock screen
 * =====================================================
 * Bếp dùng PIN 4 số thay vì username/password — nhanh hơn khi tay ướt/bẩn.
 * Token lưu localStorage → mở lại không cần nhập lại PIN.
 */

const BASE = '/api/v1/kds';
let token = null;
let pinCode = '';

export function getToken() { return token; }
export function setToken(t) { token = t; }

/**
 * Khôi phục session từ localStorage.
 * Trả về true nếu có token hợp lệ.
 */
export function restoreSession() {
  try {
    const saved = localStorage.getItem('nn_kds_token');
    if (saved) { token = saved; return true; }
  } catch (e) {}
  return false;
}

/** Nhập 1 ký tự PIN */
export function pinKey(n) {
  if (pinCode.length >= 4) return;
  pinCode += n;
  updatePinDots();
  if (pinCode.length === 4) setTimeout(submitPin, 150);
}

/** Xóa ký tự cuối */
export function pinBackspace() {
  pinCode = pinCode.slice(0, -1);
  updatePinDots();
  document.getElementById('pinError').textContent = '';
}

/** Xóa toàn bộ PIN */
export function pinClear() {
  pinCode = '';
  updatePinDots();
  document.getElementById('pinError').textContent = '';
}

function updatePinDots() {
  const dots = document.querySelectorAll('#pinDots .pin-dot');
  dots.forEach((d, i) => {
    d.classList.toggle('filled', i < pinCode.length);
    d.classList.remove('wrong');
  });
}

/** Gửi PIN lên server để lấy JWT token */
async function submitPin() {
  try {
    const resp = await fetch(`${BASE}/auth`, { // noqa — KDS auth endpoint riêng biệt
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: pinCode }),
    });
    const data = await resp.json();

    if (!resp.ok) {
      document.querySelectorAll('#pinDots .pin-dot').forEach(d => d.classList.add('wrong'));
      document.getElementById('pinError').textContent = data.detail || 'PIN không đúng';
      setTimeout(() => { pinCode = ''; updatePinDots(); }, 500);
      return;
    }

    token = data.access_token;
    try { localStorage.setItem('nn_kds_token', token); } catch (e) {}
    document.dispatchEvent(new CustomEvent('kds-authenticated'));

  } catch (e) {
    document.getElementById('pinError').textContent = 'Không thể kết nối server';
    pinCode = ''; updatePinDots();
  }
}

/**
 * Khóa KDS — về màn hình PIN.
 * Dispatch event để main.js cleanup WS + timer.
 */
export function lockKDS() {
  token = null; pinCode = '';
  try { localStorage.removeItem('nn_kds_token'); } catch (e) {}
  document.getElementById('kdsApp').classList.remove('show');
  document.getElementById('pinScreen').style.display = '';
  updatePinDots();
  document.dispatchEvent(new CustomEvent('kds-locked'));
}
