/**
 * Customer API Client — Centralized API cho trang khách đặt hàng
 * ================================================================
 * Migrated from js/api.js (IIFE → ES Module).
 *
 * Mọi API call của customer phải đi qua file này.
 * Có timeout 15 giây (AbortController), error handling tiếng Việt,
 * và caching cho menu/toppings.
 *
 * KHÁC với shared/api.js (admin):
 * - Admin API dùng JWT Bearer token trong header
 * - Customer API KHÔNG cần auth (public endpoints)
 */

const BASE = '/api/v1';
let _menuCache = null;
let _toppingsCache = null;

/**
 * Generic fetch wrapper.
 * Timeout 15 giây — mạng 4G ở KCN hay chậm.
 * Error handling trả message tiếng Việt cho showToastMsg.
 */
async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (options.token) headers['Authorization'] = 'Bearer ' + options.token;

  const fetchOptions = { method: options.method || 'GET', headers };
  if (options.body) fetchOptions.body = options.body;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  fetchOptions.signal = controller.signal;

  try {
    const resp = await fetch(BASE + path, fetchOptions); // noqa — centralized API
    clearTimeout(timeoutId);

    if (!resp.ok) {
      const errorData = await resp.json().catch(() => ({}));
      const error = new Error(errorData.detail || 'API Error ' + resp.status);
      error.status = resp.status;
      error.data = errorData;
      throw error;
    }
    return await resp.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') throw new Error('Kết nối quá chậm. Kiểm tra mạng và thử lại.');
    if (err.status) throw err;
    console.error('[API] Network error: ' + path, err);
    throw new Error('Không thể kết nối server. Kiểm tra mạng và thử lại.');
  }
}

// ── Public API functions (named exports) ──

export async function getMenu() {
  if (_menuCache) return _menuCache;
  const data = await request('/menu');
  _menuCache = data;
  return data;
}

export async function getCategoryMenu(slug) {
  return request('/menu/' + slug);
}

export async function getProduct(legacyId) {
  return request('/products/' + legacyId);
}

export async function getToppings() {
  if (_toppingsCache) return _toppingsCache;
  const data = await request('/toppings');
  _toppingsCache = data;
  return data;
}

export async function getTimeDeals() {
  return request('/time-deals');
}

export async function getCrossSellConfig() {
  return request('/cross-sell-config');
}

/**
 * Tạo đơn hàng.
 * Server tính giá từ DB (chống cheat). Client gửi product_id + quantity.
 */
export async function createOrder(orderData) {
  return request('/orders', { method: 'POST', body: JSON.stringify(orderData) });
}

export async function getOrder(publicId) {
  return request('/orders/' + publicId);
}

export async function getOrderZaloText(publicId) {
  return request('/orders/' + publicId + '/zalo-text');
}

export async function getActiveFlashSales() {
  return request('/promotions/flash-sales/active');
}

export function clearCache() {
  _menuCache = null;
  _toppingsCache = null;
}
