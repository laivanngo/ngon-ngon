/**
 * Customer Main — Entry Point
 * =============================
 * Import tất cả customer modules và expose functions lên window
 * cho onclick="" handlers trong HTML.
 *
 * Tất cả dependencies đã là ES Modules — không còn legacy IIFE.
 * window.xxx assignments chỉ dùng cho onclick="" trong HTML (sẽ chuyển
 * sang addEventListener trong phase tối ưu sau).
 */

import { curCat, setCurCat, ctyParam } from './state.js';
import { render } from './menu.js';
import { openPD, closePD, pdSelectSize, pdSelectSweet, pdSelectIce, pdToggleTp, pdChgQty, pdAddToCart } from './product-detail.js';
import { restoreCart, updCartUI, saveCart, chgCartQty, clearCartCk } from './cart.js';
import { openCheckout, closeCheckout, renderCheckout, selectDelivery, quickAddFromCk, placeOrder, closeOrderSuccess } from './checkout.js';
import { updTimeDeal } from './time-deals.js';
import { rotSP, showToast, showToastMsg } from './social-proof.js';
import { shareMenu, copyLink } from './share.js';
import { initPWA } from './pwa.js';
import { initMenu, initCrossSellConfig, initTimeDeals } from './data-loader.js';
import { init as growthInit, isOn as growthIsOn } from './growth.js';
import { initFlashSale } from './flash-sale.js';

// ══════════════════════════════════════════════════
// EXPOSE TO WINDOW — cho onclick="" trong HTML
// ══════════════════════════════════════════════════

// Product detail
window.openPD = openPD; // legacy
window.closePD = closePD; // legacy
window.pdSelectSize = pdSelectSize; // legacy
window.pdSelectSweet = pdSelectSweet; // legacy
window.pdSelectIce = pdSelectIce; // legacy
window.pdToggleTp = pdToggleTp; // legacy
window.pdChgQty = pdChgQty; // legacy
window.pdAddToCart = pdAddToCart; // legacy

// Cart & Checkout
window.chgCartQty = chgCartQty; // legacy
window.clearCartCk = clearCartCk; // legacy
window.openCheckout = openCheckout; // legacy
window.closeCheckout = closeCheckout; // legacy
window.selectDelivery = selectDelivery; // legacy
window.quickAddFromCk = quickAddFromCk; // legacy
window.placeOrder = placeOrder; // legacy
window.closeOrderSuccess = closeOrderSuccess; // legacy

// Menu render (needed by Growth module and search)
window.render = render; // legacy

// Cart UI (needed by Growth module)
window.updCartUI = updCartUI; // legacy
window.saveCart = saveCart; // legacy

// Social proof
window.showToastMsg = showToastMsg; // legacy
window.showToast = showToast; // legacy

// Share
window.shareMenu = shareMenu; // legacy
window.copyLink = copyLink; // legacy

// ── Event listeners ──

// Cart changed (from cart.js) → re-render checkout
document.addEventListener('cart-changed', () => renderCheckout());
document.addEventListener('cart-emptied', () => closeCheckout());

// Flash sale updated → re-render menu with badges + sorting
document.addEventListener('flash-sale-updated', () => render(curCat));

// Tab click
document.getElementById('tabs').addEventListener('click', e => {
  const tab = e.target.closest('.tab'); if (!tab) return;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
  tab.classList.add('on');
  setCurCat(tab.dataset.c);
  document.getElementById('searchIn').value = '';
  render(tab.dataset.c);
  document.getElementById('tabs').scrollTo({ left: tab.offsetLeft - 16, behavior: 'smooth' });
});

// Search
let sTmr;
document.getElementById('searchIn').addEventListener('input', e => {
  clearTimeout(sTmr);
  sTmr = setTimeout(() => {
    const t = e.target.value.trim();
    if (t.length >= 1) { document.querySelectorAll('.tab').forEach(t => t.classList.remove('on')); render(null, t); }
    else { document.querySelector(`.tab[data-c="${curCat}"]`)?.classList.add('on'); render(curCat); }
  }, 200);
});

// Scroll to top button
window.addEventListener('scroll', () => { // legacy
  document.getElementById('sTop').classList.toggle('show', scrollY > 250);
});

// ── Init ──

restoreCart();
updCartUI();
updTimeDeal();
setInterval(updTimeDeal, 1000);
setInterval(rotSP, 4500);
setTimeout(() => { showToast(); setInterval(showToast, 45000); }, 15000);

// PWA install prompt
initPWA();

// Service Worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  });
}

// Save company param
if (ctyParam) { try { localStorage.setItem('nn_cty', ctyParam); } catch (e) {} }

// ── Boot (load data from API) ──
async function boot() {
  console.log('[App] Ngon-Ngon v3.0 (ES Modules — no legacy)');
  await initMenu();
  initTimeDeals();
  initCrossSellConfig();

  // Flash Sale banner — load after menu
  initFlashSale();

  // Growth features — load AFTER menu (needs M populated)
  await growthInit();
  updCartUI();
}

boot();
