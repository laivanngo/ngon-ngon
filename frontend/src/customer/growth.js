/**
 * Customer Growth Module — 9 tính năng tăng doanh thu
 * =====================================================
 * Migrated from js/growth.js (IIFE → ES Module).
 *
 * FEATURES:
 * ① Upsell popup (gợi ý topping/size)
 * ② Reorder banner (đặt lại đơn cũ)
 * ③ Cross-sell (gợi ý mua kèm trong giỏ)
 * ④ Estimated time (thời gian giao ước tính)
 * ⑤ Loyalty (tích điểm spend-based)
 * ⑦ Review (đánh giá sau khi nhận)
 * ⑨ Referral (giới thiệu bạn bè)
 */
import { M, cart } from './state.js';
import { esc } from '../shared/formatters.js';
import { saveCart, updCartUI } from './cart.js';
import { showToastMsg } from './social-proof.js';

const BASE = '/api/v1/crm';
const PROMO_BASE = '/api/v1/promotions';
let _flags = {};
let _customer = null;
let _phone = '';
let _upsellStats = null;

// ── Init ──────────────────────────────────────────────

export async function init() {
  try { _phone = localStorage.getItem('nn_phone') || ''; } catch (e) {}
  try {
    const url = _phone ? `${BASE}/config?phone=${_phone}` : `${BASE}/config`;
    const resp = await fetch(url); // noqa — Growth config endpoint
    if (resp.ok) { const data = await resp.json(); _flags = data.flags || {}; _customer = data.customer || null; }
  } catch (e) { console.warn('[Growth] Config load failed:', e); }

  if (isOn('reorder')) initReorder();
  if (isOn('loyalty')) initLoyaltyBadge();
  if (isOn('reviews')) initReviewPrompt();
  if (isOn('referral')) initReferralButton();
  console.log('[Growth] Init done. Flags:', Object.keys(_flags).filter(k => _flags[k]).join(', '));
}

export function isOn(key) { return _flags[key] === true; }

// ── Event Tracking ────────────────────────────────────

export function track(type, feature, data, value) {
  try {
    fetch(`${BASE}/events`, { // noqa — fire-and-forget tracking
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, feature, data: data || null, phone: _phone || null, value: value || 0 }),
    }).catch(() => {});
  } catch (e) {}
}

// ── ① Upsell ──────────────────────────────────────────

export async function injectUpsell(popup, item) {
  if (!isOn('upsell') || !item) return;
  if (!_upsellStats) {
    try { const resp = await fetch(`${PROMO_BASE}/upsell-stats`); if (resp.ok) _upsellStats = await resp.json(); } catch (e) { return; } // noqa
  }
  if (!_upsellStats) return;
  track('upsell_shown', 'upsell', { product: item.id });

  if (item.isDrink && _upsellStats.topping_pct > 50) {
    const hint = document.createElement('div'); hint.className = 'growth-hint';
    hint.innerHTML = `🔥 <strong>${_upsellStats.topping_pct}%</strong> khách thêm topping — Bạn thử chưa?`;
    const tpSection = popup.querySelector('.pd-toppings, .pd-tp');
    if (tpSection) tpSection.parentNode.insertBefore(hint, tpSection);
  }
  if (item.sz && item.sz.length > 1) {
    const biggest = item.sz[item.sz.length - 1], smallest = item.sz[0];
    if (biggest && smallest && biggest.p > smallest.p) {
      const diff = biggest.p - smallest.p;
      const hint = document.createElement('div'); hint.className = 'growth-hint';
      hint.innerHTML = `📏 Size ${biggest.s} chỉ <strong>+${diff}k</strong> — đáng thử!`;
      const szSection = popup.querySelector('.pd-sizes, .pd-sz');
      if (szSection) szSection.parentNode.insertBefore(hint, szSection.nextSibling);
    }
  }
}

export function onUpsellAccepted(type, value) {
  track('upsell_accepted', 'upsell', { type }, value);
}

// ── ② Reorder ─────────────────────────────────────────

async function initReorder() {
  if (!_phone) return;
  try {
    const resp = await fetch(`${BASE}/reorder?phone=${_phone}`); // noqa
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data.order) return;
    const order = data.order;
    const itemNames = order.items.slice(0, 2).map(i => i.product_name + (i.quantity > 1 ? ' ×' + i.quantity : '')).join(', ');
    const extra = order.items.length > 2 ? ` +${order.items.length - 2} món` : '';

    const banner = document.createElement('div');
    banner.className = 'growth-reorder'; banner.id = 'reorderBanner';
    banner.innerHTML = `<div class="growth-reorder-content"><div class="growth-reorder-text"><span class="growth-reorder-label">📋 Đặt lại đơn trước</span><span class="growth-reorder-items">${esc(itemNames)}${extra} — ${order.total}k</span></div><button class="growth-reorder-btn" id="reorderBtn">Đặt lại</button><button class="growth-reorder-close" onclick="this.parentNode.parentNode.remove()">✕</button></div>`;
    const mc = document.getElementById('mc');
    if (mc) mc.parentNode.insertBefore(banner, mc);
    document.getElementById('reorderBtn').onclick = () => reorderFromPrev(order);
    track('reorder_shown', 'reorder', { total: order.total });
  } catch (e) { console.warn('[Growth] Reorder failed:', e); }
}

function reorderFromPrev(order) {
  track('reorder_clicked', 'reorder', { total: order.total }, order.total);
  order.items.forEach(item => {
    for (const catKey in M) {
      const found = (M[catKey].items || []).find(p => p._dbId === item.product_id);
      if (found) {
        const key = `${found.id}|${item.size || ''}|${item.sweetness || ''}|${item.ice_level || ''}||`;
        cart[key] = { id: found.id, _dbId: found._dbId, n: found.n, p: item.unit_price || found.p, e: found.e, q: item.quantity, sz: item.size || null, sweet: item.sweetness || null, ice: item.ice_level || null };
        break;
      }
    }
  });
  saveCart(); updCartUI(); showToastMsg('✅', 'Đã thêm đơn trước vào giỏ!');
  const banner = document.getElementById('reorderBanner');
  if (banner) banner.remove();
}

// ── ③ Cross-sell ──────────────────────────────────────

export async function injectCrossSell(cartPanel) {
  if (!isOn('cross_sell') || !cartPanel) return;
  const ids = [];
  for (const key in cart) { if (cart[key] && cart[key]._dbId) ids.push(cart[key]._dbId); }
  if (ids.length === 0) return;
  try {
    const resp = await fetch(`${PROMO_BASE}/cross-sell?product_ids=${ids.join(',')}`); // noqa
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data.suggestions || data.suggestions.length === 0) return;
    track('crosssell_shown', 'cross_sell', { count: data.suggestions.length });
    const container = document.createElement('div'); container.className = 'growth-crosssell';
    container.innerHTML = `<div class="growth-crosssell-title">🧁 Mua kèm phổ biến</div><div class="growth-crosssell-items">${data.suggestions.map(s => `<button class="growth-crosssell-item" data-id="${s.legacy_id}" data-dbid="${s.id}" data-name="${esc(s.name)}" data-price="${s.price}" data-emoji="${s.emoji}"><span>${s.emoji} ${esc(s.name)}</span><span class="growth-crosssell-price">+${s.price}k</span></button>`).join('')}</div>`;
    const checkoutBtn = cartPanel.querySelector('.ck-btn, .checkout-btn, [onclick*="checkout"]');
    if (checkoutBtn) checkoutBtn.parentNode.insertBefore(container, checkoutBtn);
    else cartPanel.appendChild(container);
    container.querySelectorAll('.growth-crosssell-item').forEach(btn => {
      btn.onclick = () => {
        const id = btn.dataset.id, dbid = parseInt(btn.dataset.dbid), name = btn.dataset.name, price = parseInt(btn.dataset.price), emoji = btn.dataset.emoji;
        cart[`${id}|||||`] = { id, _dbId: dbid, n: name, p: price, e: emoji, q: 1 };
        saveCart(); updCartUI(); showToastMsg('✅', `Đã thêm ${name}!`);
        track('crosssell_accepted', 'cross_sell', { product: id }, price);
        btn.style.opacity = '0.5'; btn.disabled = true; btn.innerHTML = '✅ Đã thêm';
      };
    });
  } catch (e) { console.warn('[Growth] Cross-sell failed:', e); }
}

// ── ④ Estimated time ──────────────────────────────────

export function showEstimatedTime(orderResp) {
  if (!isOn('estimated_time') || !orderResp) return;
  const mins = orderResp.estimated_minutes;
  if (!mins) return;
  showToastMsg('⏱️', `Ước tính ${mins}–${mins + 5} phút nữa nhận hàng`);
  try { localStorage.setItem('nn_last_est_minutes', mins); } catch (e) {}
}

// ── ⑤ Loyalty ─────────────────────────────────────────

function initLoyaltyBadge() {
  if (!_customer) return;
  const c = _customer;
  if (c.order_count < 2) return;
  const badge = document.createElement('div'); badge.className = 'growth-loyalty';
  if (c.has_reward) { badge.innerHTML = `🎉 Bạn có thưởng! Được tặng 1 ly (≤25k) — Nhập SĐT khi đặt`; badge.classList.add('growth-loyalty-reward'); }
  else { badge.innerHTML = `⭐ ${c.loyalty_points}/${c.points_to_reward + c.loyalty_points} ly — Còn ${c.points_to_reward} ly nữa được tặng!`; }
  const mc = document.getElementById('mc');
  if (mc) mc.parentNode.insertBefore(badge, mc);
}

export function getLoyaltyInfo() { return _customer; }

// ── ⑦ Review ──────────────────────────────────────────

let _reviewShown = false;

function initReviewPrompt() {
  _tryShowReview();
  document.addEventListener('visibilitychange', () => { if (!document.hidden && isOn('reviews')) _tryShowReview(); });
}

function _tryShowReview() {
  if (_reviewShown) return;
  try {
    const lastOrderId = localStorage.getItem('nn_last_order_id');
    const reviewed = localStorage.getItem('nn_reviewed_' + lastOrderId);
    if (!lastOrderId || reviewed) return;
    const orderTime = localStorage.getItem('nn_last_order_time');
    if (orderTime && (Date.now() - parseInt(orderTime)) < 20 * 60 * 1000) return;
    _reviewShown = true;
    setTimeout(() => showReviewPopup(lastOrderId), 2000);
  } catch (e) {}
}

function showReviewPopup(orderId) {
  const overlay = document.createElement('div'); overlay.className = 'growth-review-overlay';
  overlay.innerHTML = `<div class="growth-review-box"><div class="growth-review-title">Bạn thấy đơn hàng thế nào? 🧋</div><div class="growth-review-stars" id="reviewStars">${[1, 2, 3, 4, 5].map(n => `<button class="growth-star" data-n="${n}">⭐</button>`).join('')}</div><div class="growth-review-selected" id="reviewLabel"></div><textarea class="growth-review-comment" id="reviewComment" placeholder="Góp ý thêm (tùy chọn)..." rows="2"></textarea><div class="growth-review-actions"><button class="growth-review-skip" onclick="this.closest('.growth-review-overlay').remove()">Bỏ qua</button><button class="growth-review-submit" id="reviewSubmitBtn" disabled>Gửi đánh giá</button></div></div>`;
  document.body.appendChild(overlay);

  let selectedRating = 0;
  const labels = ['', 'Tệ 😞', 'Chưa ổn 😐', 'Bình thường 🙂', 'Ngon 😊', 'Tuyệt vời! 🤩'];
  overlay.querySelectorAll('.growth-star').forEach(star => {
    star.onclick = () => {
      selectedRating = parseInt(star.dataset.n);
      overlay.querySelectorAll('.growth-star').forEach((s, i) => { s.style.opacity = i < selectedRating ? '1' : '0.3'; s.style.transform = i < selectedRating ? 'scale(1.2)' : 'scale(1)'; });
      document.getElementById('reviewLabel').textContent = labels[selectedRating];
      document.getElementById('reviewSubmitBtn').disabled = false;
    };
  });

  document.getElementById('reviewSubmitBtn').onclick = async () => {
    const comment = document.getElementById('reviewComment').value.trim();
    try {
      await fetch(`${BASE}/reviews`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ order_public_id: orderId || null, phone: _phone, rating: selectedRating, comment }) }); // noqa
      track('review_submitted', 'reviews', { rating: selectedRating }, selectedRating);
      localStorage.setItem('nn_reviewed_' + orderId, '1');
      overlay.innerHTML = '<div class="growth-review-box"><div style="text-align:center;font-size:32px;padding:24px">🙏</div><div style="text-align:center;font-size:15px;color:#666;padding:0 16px 24px">Cảm ơn bạn đã đánh giá!</div></div>';
      setTimeout(() => overlay.remove(), 1500);
    } catch (e) { overlay.remove(); }
  };
}

// ── ⑨ Referral ────────────────────────────────────────

function initReferralButton() {
  if (!_customer || !_customer.referral_code) return;
}

export async function showReferralShare() {
  if (!isOn('referral') || !_phone) return;
  try {
    const resp = await fetch(`${BASE}/referral?phone=${_phone}`); // noqa
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data.referral_code) return;
    track('referral_shown', 'referral');
    if (navigator.share) {
      navigator.share({ title: 'Ngon-Ngon — Trà sữa & Ăn vặt', text: data.share_text, url: window.location.origin + '?ref=' + data.referral_code }).then(() => track('referral_shared', 'referral')).catch(() => {}); // legacy
    } else {
      try { await navigator.clipboard.writeText(data.share_text); showToastMsg('📋', 'Đã copy link giới thiệu!'); track('referral_copied', 'referral'); } catch (e) {}
    }
  } catch (e) {}
}

// ── Utils ─────────────────────────────────────────────

export function savePhone(phone) {
  if (phone) { _phone = phone.replace(/[\s.\-]/g, ''); try { localStorage.setItem('nn_phone', _phone); } catch (e) {} }
}

export function saveOrderTime() {
  try { localStorage.setItem('nn_last_order_time', Date.now().toString()); } catch (e) {}
}
