/**
 * Shared Constants — Dùng chung giữa admin / customer / kds
 * ==========================================================
 */

/** Base URL cho tất cả API calls */
export const BASE = '/api/v1';

/** Status labels tiếng Việt — dùng trong admin, KDS, customer */
export const STATUS_LABELS = {
  pending: '⏳ Chờ xác nhận',
  confirmed: '✅ Đã xác nhận',
  preparing: '🍳 Đang pha chế',
  delivering: '🛵 Đang giao',
  done: '✅ Hoàn thành',
  cancelled: '❌ Đã hủy',
};

/** Status labels ngắn cho action buttons */
export const STATUS_ACTION_LABELS = {
  confirmed: 'xác nhận',
  preparing: 'pha chế',
  delivering: 'giao hàng',
  done: 'hoàn thành',
  cancelled: 'hủy',
};
