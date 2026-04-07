/**
 * Admin Reviews — Đánh giá từ khách hàng
 * ========================================
 */
import { api } from '../shared/api.js';
import { esc } from '../shared/formatters.js';

let reviewsPage = 0;
const REVIEWS_PER_PAGE = 20;

export async function loadReviews(reset) {
  const content = document.getElementById('reviewsContent');
  if (!content) return;
  if (reset !== false) reviewsPage = 0;
  content.innerHTML = '<div class="loading"><span class="spinner"></span>Đang tải...</div>';

  const filter = document.getElementById('reviewsFilter').value;
  const offset = reviewsPage * REVIEWS_PER_PAGE;
  let url = `/crm/reviews/list?limit=${REVIEWS_PER_PAGE}&offset=${offset}`;
  if (filter) url += `&rating=${filter}`;

  try {
    const data = await api(url);
    const reviews = data.reviews || [];
    const total = data.total || 0;
    const totalPages = Math.ceil(total / REVIEWS_PER_PAGE);

    if (!reviews.length) {
      content.innerHTML = '<div class="empty-state">Chưa có đánh giá nào</div>';
      return;
    }

    const summaryHtml = `
      <div style="background:var(--card);border-radius:var(--r);padding:16px;margin-bottom:12px;display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <div style="font-size:24px;font-weight:700">⭐ ${total} đánh giá</div>
        <div style="font-size:13px;color:var(--text2)">Trang ${reviewsPage + 1}/${totalPages || 1}</div>
      </div>`;

    const cardsHtml = reviews.map(r => {
      const stars = '⭐'.repeat(r.rating) + '<span style="opacity:0.2">' + '⭐'.repeat(5 - r.rating) + '</span>';
      const date = r.created_at ? new Date(r.created_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
      const orderId = r.order_public_id ? '#' + r.order_public_id.substring(0, 8).toUpperCase() : '—';
      const ratingColor = r.rating >= 4 ? 'var(--green)' : r.rating >= 3 ? '#FF9800' : '#C62828';
      return `
        <div class="flag-card" style="flex-direction:column;align-items:stretch;gap:8px">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div><span style="font-size:14px">${stars}</span><span style="font-size:12px;font-weight:700;color:${ratingColor};margin-left:6px">${r.rating}/5</span></div>
            <div style="font-size:11px;color:var(--text2)">${date}</div>
          </div>
          ${r.comment ? `<div style="font-size:13px;line-height:1.5;color:var(--text);padding:8px 12px;background:var(--bg);border-radius:8px">"${esc(r.comment)}"</div>` : '<div style="font-size:12px;color:var(--hint);font-style:italic">Không có góp ý</div>'}
          <div style="display:flex;gap:12px;font-size:11px;color:var(--text2)"><span>📱 ${esc(r.phone || '—')}</span><span>🆔 Đơn ${orderId}</span></div>
        </div>`;
    }).join('');

    let paginationHtml = '';
    if (totalPages > 1) {
      paginationHtml = `<div style="display:flex;justify-content:center;gap:8px;margin-top:16px">
        <button onclick="reviewsPrev()" ${reviewsPage === 0 ? 'disabled' : ''} style="padding:8px 16px;border:1.5px solid var(--bdr);border-radius:8px;background:var(--card);cursor:pointer;font-family:inherit;font-size:12px">← Trước</button>
        <span style="padding:8px 12px;font-size:12px;color:var(--text2)">${reviewsPage + 1} / ${totalPages}</span>
        <button onclick="reviewsNext()" ${reviewsPage >= totalPages - 1 ? 'disabled' : ''} style="padding:8px 16px;border:1.5px solid var(--bdr);border-radius:8px;background:var(--card);cursor:pointer;font-family:inherit;font-size:12px">Tiếp →</button>
      </div>`;
    }

    content.innerHTML = summaryHtml + cardsHtml + paginationHtml;
  } catch (err) {
    content.innerHTML = `<div class="empty-state">Lỗi: ${err.message}</div>`;
  }
}

export function reviewsPrev() { reviewsPage = Math.max(0, reviewsPage - 1); loadReviews(false); }
export function reviewsNext() { reviewsPage++; loadReviews(false); }
