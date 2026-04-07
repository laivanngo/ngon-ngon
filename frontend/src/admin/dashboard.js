/**
 * Admin Dashboard — Thống kê tổng quan
 * ======================================
 * Hiển thị: đơn hôm nay, doanh thu, đơn chờ, sản phẩm đang bán.
 */
import { api } from '../shared/api.js';
import { fmtPd } from '../shared/formatters.js';

/**
 * Tải và hiển thị dashboard stats.
 * Gọi khi: mở tab Dashboard, sau khi cập nhật đơn, nhận đơn mới qua WS.
 */
export async function loadDashboard() {
  const grid = document.getElementById('dashboardGrid');
  try {
    const d = await api('/admin/dashboard');
    grid.innerHTML = `
      <div class="stat-card"><div class="stat-num">${d.orders_today}</div><div class="stat-label">Đơn hôm nay</div></div>
      <div class="stat-card"><div class="stat-num">${fmtPd(d.revenue_today)}</div><div class="stat-label">Doanh thu hôm nay</div></div>
      <div class="stat-card"><div class="stat-num" style="color:#E65100">${d.pending_orders}</div><div class="stat-label">Đơn chờ xử lý</div></div>
      <div class="stat-card"><div class="stat-num" style="color:var(--green)">${d.active_products}</div><div class="stat-label">Sản phẩm đang bán</div></div>
    `;
  } catch (err) {
    grid.innerHTML = '<div class="empty-state">Không thể tải dữ liệu</div>';
  }
}
