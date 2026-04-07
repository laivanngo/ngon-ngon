/**
 * Customer Flash Sale — Banner + Countdown
 * ============================================
 * Hiển thị Flash Sale đang chạy trên đầu trang khách đặt hàng.
 * Banner nổi bật: tên sale, discount %, countdown, remaining badge.
 * Khi chọn sản phẩm cụ thể → hiện tên + emoji sản phẩm trên banner.
 *
 * Real-time: polling-on-focus (re-fetch khi khách quay lại tab).
 * Phù hợp 4G ở KCN — không cần persistent WebSocket.
 */

import { getActiveFlashSales } from '../shared/customer-api.js';
import { escapeHtml } from '../shared/ui.js';
import { fmtP } from '../shared/formatters.js';
import { M } from './state.js';

let _countdownTimer = null;
let _currentSales = [];

/**
 * Init flash sale banner: load data + start polling-on-focus.
 * Gọi 1 lần từ customer/main.js khi load trang.
 */
export async function initFlashSale() {
  await _loadAndRender();

  // Polling-on-focus: re-fetch khi khách quay lại tab
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) _loadAndRender();
  });
}

/**
 * Trả về Set chứa database IDs của các sản phẩm đang flash sale.
 * menu.js dùng để sort + badge.
 */
export function getFlashSaleProductIds() {
  if (!_currentSales.length) return new Set();
  const ids = new Set();
  for (const sale of _currentSales) {
    for (const pid of (sale.product_ids || [])) ids.add(pid);
  }
  return ids;
}

/**
 * Trả về flash sale info: ids (Set of _dbId) + discount percent.
 * menu.js dùng để hiển thị giá sale trên product cards.
 */
export function getFlashSaleInfo() {
  if (!_currentSales.length) return { ids: new Set(), discount: 0 };
  const ids = new Set();
  const discount = _currentSales[0].discount_percent || 0;
  for (const sale of _currentSales) {
    for (const pid of (sale.product_ids || [])) ids.add(pid);
  }
  return { ids, discount };
}

/** Fetch active flash sales + render banner.
 *  Giữ banner cũ cho đến khi data mới load xong (tránh flash of no content trên 4G).
 */
async function _loadAndRender() {
  try {
    const data = await getActiveFlashSales();
    _currentSales = data.flash_sales || [];
    _renderBanner();

    // Notify menu.js to re-render with flash sale badges + sorting
    document.dispatchEvent(new CustomEvent('flash-sale-updated'));
  } catch (e) {
    // Giữ nguyên banner hiện tại nếu fetch fail — không clear
    console.warn('[FlashSale] Load failed, keeping current banner:', e.message);
  }
}

/** Render banner HTML vào #flashSaleBanner */
function _renderBanner() {
  const container = document.getElementById('flashSaleBanner');
  if (!container) return;

  // Clear previous countdown
  if (_countdownTimer) {
    clearInterval(_countdownTimer);
    _countdownTimer = null;
  }

  if (!_currentSales.length) {
    container.innerHTML = '';
    container.style.display = 'none';
    return;
  }

  // Show the best (first) sale
  const sale = _currentSales[0];
  const remainPct = Math.round((sale.remaining / sale.max_quantity) * 100);
  const urgency = remainPct <= 20 ? 'flash-sale-urgent' : '';

  // Lookup sản phẩm từ menu state → hiển thị ảnh + giá sale trên banner
  let productsHtml = '';
  if (sale.product_ids && sale.product_ids.length > 0) {
    const cards = [];
    for (const cat of Object.values(M)) {
      for (const item of (cat.items || [])) {
        if (sale.product_ids.includes(item._dbId)) {
          const pr = item.sz ? item.sz[0].p : item.p;
          const salePrice = pr - Math.floor(pr * sale.discount_percent / 100);
          const imgH = item.img
            ? `<img src="${item.img}" alt="${escapeHtml(item.n)}" loading="lazy">`
            : `<span class="fs-item-emoji">${item.e}</span>`;
          cards.push(`<div class="fs-item" onclick="openPD('${item.id}')"><div class="fs-item-img">${imgH}</div><div class="fs-item-name">${escapeHtml(item.n)}</div><div class="fs-item-price"><span class="fs-old">${fmtP(pr)}</span><span class="fs-new">${fmtP(salePrice)}</span></div></div>`);
        }
      }
    }
    if (cards.length > 0) {
      productsHtml = `<div class="fs-items">${cards.join('')}</div>`;
    }
  }

  container.style.display = 'block';
  container.innerHTML = `
    <div class="flash-sale-banner ${urgency}">
      <div class="flash-sale-top">
        <span class="flash-sale-badge">⚡ FLASH SALE</span>
        <span class="flash-sale-countdown" id="fsCountdown"></span>
      </div>
      <div class="flash-sale-title">
        ${escapeHtml(sale.title)} — Giảm ${sale.discount_percent}%
      </div>
      ${sale.subtitle ? `<div class="flash-sale-subtitle">${escapeHtml(sale.subtitle)}</div>` : ''}
      ${productsHtml}
      <div class="flash-sale-remaining">
        <div class="flash-sale-bar-bg">
          <div class="flash-sale-bar" style="width:${100 - remainPct}%"></div>
        </div>
        <span class="flash-sale-count">Còn ${sale.remaining}/${sale.max_quantity} suất</span>
      </div>
    </div>
  `;

  // Start countdown
  _startCountdown(new Date(sale.ends_at));
}

/** Countdown timer — update mỗi giây */
function _startCountdown(endsAt) {
  const el = document.getElementById('fsCountdown');
  if (!el) return;

  function update() {
    const now = new Date();
    const diff = endsAt - now;

    if (diff <= 0) {
      el.textContent = 'Đã kết thúc';
      clearInterval(_countdownTimer);
      _countdownTimer = null;
      // Re-fetch to update UI
      setTimeout(_loadAndRender, 1000);
      return;
    }

    const h = Math.floor(diff / 36e5);
    const m = Math.floor((diff % 36e5) / 6e4);
    const s = Math.floor((diff % 6e4) / 1e3);

    if (h > 0) {
      el.textContent = `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    } else {
      el.textContent = `${m}:${String(s).padStart(2, '0')}`;
    }
  }

  update();
  _countdownTimer = setInterval(update, 1000);
}
