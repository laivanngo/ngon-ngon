/**
 * Shared Formatters — Format giá, escape HTML
 * =============================================
 * Dùng chung cho cả admin lẫn customer.
 */

/**
 * Format giá từ đơn vị k (nghìn) → "19.000"
 * WHY đơn vị k: Backend lưu giá dạng 19 (= 19.000đ) để tránh lỗi làm tròn.
 */
export function fmtP(v) {
  return v != null && !isNaN(v)
    ? (v * 1000).toLocaleString('vi-VN')
    : '0';
}

/** Format giá có đuôi "đ": "19.000đ" */
export function fmtPd(v) {
  return fmtP(v) + 'đ';
}

/**
 * Escape HTML entities — chống XSS khi hiển thị user input.
 * WHY cần: customer_name, address, note đều là user input.
 */
export function esc(s) {
  if (!s) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return s.replace(/[&<>"']/g, c => map[c]);
}
