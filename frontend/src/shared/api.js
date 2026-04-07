/**
 * Shared API — Centralized API layer cho Admin Panel
 * ====================================================
 * TẤT CẢ API calls phải đi qua file này. KHÔNG fetch() trực tiếp.
 *
 * Admin API khác customer API ở chỗ:
 * - Luôn gửi JWT token trong Authorization header
 * - 401 → auto logout + alert
 */
import { BASE } from './constants.js';

/** JWT token — set by auth module */
let _token = null;

export function getToken() { return _token; }
export function setToken(t) { _token = t; }

/**
 * Gọi API với JWT auth.
 * @param {string} path - Đường dẫn API (VD: '/admin/orders')
 * @param {object} options - { method, body }
 * @returns {Promise<any>} Parsed JSON response
 * @throws {Error} Nếu API trả về lỗi
 */
export async function api(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    method: options.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + _token,
    },
    body: options.body || undefined,
  });

  if (resp.status === 401) {
    alert('⏰ Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    // Import dynamically to avoid circular dependency
    const { doLogout } = await import('../admin/auth.js');
    doLogout();
    throw new Error('Session expired');
  }

  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'API Error');
  return data;
}
