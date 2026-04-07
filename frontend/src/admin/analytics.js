/**
 * Admin Analytics — Dashboard phân tích kinh doanh
 * ==================================================
 * Doanh thu theo ngày, top sản phẩm, giờ cao điểm, hiệu quả tính năng.
 */
import { api } from '../shared/api.js';
import { fmtP, esc } from '../shared/formatters.js';

export async function loadAnalytics() {
  const content = document.getElementById('analyticsContent');
  if (!content) return;
  content.innerHTML = '<div class="loading"><span class="spinner"></span>Đang tải...</div>';

  const days = document.getElementById('analyticsDays').value || 30;

  try {
    const data = await api(`/crm/analytics?days=${days}`);

    const maxRev = Math.max(...data.revenue_by_day.map(d => d.revenue), 1);
    const revenueHtml = data.revenue_by_day.map(d => {
      const pct = Math.round(d.revenue / maxRev * 100);
      const dayStr = d.day.split('-').slice(1).join('/');
      return `<div style="display:flex;align-items:center;gap:8px;margin:3px 0">
        <span style="width:40px;font-size:11px;color:var(--text2);text-align:right">${dayStr}</span>
        <div style="flex:1;background:var(--bg);border-radius:4px;height:20px;overflow:hidden">
          <div style="height:100%;background:var(--brand);width:${pct}%;border-radius:4px;min-width:2px"></div>
        </div>
        <span style="width:60px;font-size:11px;font-weight:700;text-align:right">${fmtP(d.revenue)}</span>
        <span style="width:30px;font-size:10px;color:var(--text2)">${d.orders}đ</span>
      </div>`;
    }).join('');

    const topHtml = data.top_products.slice(0, 8).map((p, i) => `
      <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--bdr);font-size:13px">
        <span>${i + 1}. ${esc(p.name)}</span>
        <span><strong>${fmtP(p.revenue)}</strong> <span style="color:var(--text2)">(${p.quantity} món)</span></span>
      </div>
    `).join('');

    const maxH = Math.max(...data.peak_hours.map(h => h.orders), 1);
    const hourHtml = data.peak_hours.map(h => {
      const pct = Math.round(h.orders / maxH * 100);
      return `<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
        <span style="width:30px;font-size:11px;color:var(--text2);text-align:right">${h.hour}h</span>
        <div style="flex:1;background:var(--bg);border-radius:3px;height:16px;overflow:hidden">
          <div style="height:100%;background:var(--green);width:${pct}%;border-radius:3px;min-width:2px"></div>
        </div>
        <span style="width:28px;font-size:11px;font-weight:600;text-align:right">${h.orders}</span>
      </div>`;
    }).join('');

    const featureNames = { upsell: 'Upsell', reorder: 'Đặt lại', cross_sell: 'Mua kèm', referral: 'Giới thiệu' };
    const featHtml = Object.keys(data.feature_stats).map(k => {
      const f = data.feature_stats[k];
      return `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--bdr);font-size:13px">
        <span>${featureNames[k] || k}</span>
        <span>Hiện ${f.shown} • Chấp nhận ${f.accepted} • <strong>${f.conversion}%</strong> • +${fmtP(f.total_value)}</span>
      </div>`;
    }).join('');

    content.innerHTML = `
      <div style="margin-bottom:20px">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:16px">
          <div class="stat-card"><div class="stat-num">${data.total_customers}</div><div class="stat-label">Tổng khách</div></div>
          <div class="stat-card"><div class="stat-num">${data.repeat_rate}%</div><div class="stat-label">Khách quay lại</div></div>
          <div class="stat-card"><div class="stat-num" style="color:${data.cancel_rate > 10 ? '#C62828' : 'var(--green)'}">${data.cancel_rate}%</div><div class="stat-label">Tỷ lệ hủy</div></div>
          ${data.avg_rating ? `<div class="stat-card"><div class="stat-num" style="color:var(--green)">⭐${data.avg_rating}</div><div class="stat-label">Đánh giá TB</div></div>` : ''}
        </div>
      </div>
      <div style="background:var(--card);border-radius:var(--r);padding:16px;margin-bottom:12px">
        <div style="font-size:14px;font-weight:700;margin-bottom:10px">💰 Doanh thu ${days} ngày</div>
        ${revenueHtml || '<div style="color:var(--hint);font-size:13px">Chưa có dữ liệu</div>'}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
        <div style="background:var(--card);border-radius:var(--r);padding:16px">
          <div style="font-size:14px;font-weight:700;margin-bottom:10px">🏆 Top sản phẩm</div>
          ${topHtml || '<div style="color:var(--hint);font-size:13px">Chưa có</div>'}
        </div>
        <div style="background:var(--card);border-radius:var(--r);padding:16px">
          <div style="font-size:14px;font-weight:700;margin-bottom:10px">⏰ Giờ cao điểm</div>
          ${hourHtml || '<div style="color:var(--hint);font-size:13px">Chưa có</div>'}
        </div>
      </div>
      <div style="background:var(--card);border-radius:var(--r);padding:16px;margin-bottom:12px">
        <div style="font-size:14px;font-weight:700;margin-bottom:10px">🏁 Hiệu quả tính năng</div>
        ${featHtml || '<div style="color:var(--hint);font-size:13px">Chưa có dữ liệu tracking</div>'}
      </div>`;
  } catch (err) {
    content.innerHTML = `<div class="empty-state">Lỗi: ${err.message}</div>`;
  }
}
