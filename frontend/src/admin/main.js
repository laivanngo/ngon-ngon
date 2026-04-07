/**
 * Admin Main — Entry Point
 * ==========================
 * Import tất cả modules và expose functions lên window
 * cho onclick="" handlers trong HTML.
 *
 * WHY window.xxx: HTML hiện tại dùng onclick="functionName()".
 * Chuyển sang addEventListener sẽ làm trong phase sau.
 * Tất cả window assignments đánh dấu "// legacy" cho validate.sh.
 */

// ── Shared ──
import { initModalEscapeKey, closeModal } from '../shared/ui.js';

// ── Admin Modules ──
import { checkSavedAuth, doLogin, doLogout } from './auth.js';
import { loadDashboard } from './dashboard.js';
import { loadOrders, toggleOrder, updateStatus, filterOrders, initOrderAutoRefresh } from './orders.js';
import { connectWS } from './websocket.js';
import { toggleSound, restoreSoundPreference, requestNotificationPermission } from './notifications.js';
import { loadProducts, renderProductsList, filterProductsList, toggleProductActive, switchSubTab,
  catDragStart, catDragOver, catDragEnd, catDrop,
  prodDragStart, prodDragOver, prodDragEnd, prodDrop } from './products.js';
import { openProductModal, addSizeRow, toggleComboFields, previewProductImage } from './product-modal.js';
import { loadCategoriesList, openCategoryModal, softDeleteCategory, restoreCategory, toggleCategoryActive } from './categories.js';
import { loadToppingsList, openToppingModal, toggleToppingActive } from './toppings.js';
import { loadCrossSellList, openCrossSellModal, openCrossSellEditModal, deleteCrossSell, toggleCrossSellActive } from './cross-sell.js';
import { loadAnalytics } from './analytics.js';
import { loadReviews, reviewsPrev, reviewsNext } from './reviews.js';
import { loadFeatureFlags, toggleFeature, loadGrowthSettings, onSettingInput, updateGrowthSetting } from './settings.js';
import { loadFlashSales, openFlashSaleModal, createFlashSale, cancelFlashSale } from './flash-sales.js';

// ── Tab Switching ──

function switchTab(tab) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('on'));
  document.querySelector(`.nav-tab[data-tab="${tab}"]`).classList.add('on');

  ['Dashboard', 'Orders', 'Products', 'Analytics', 'Reviews', 'Features', 'FlashSales'].forEach(t => {
    const el = document.getElementById('tab' + t);
    if (el) el.style.display = t.toLowerCase() === tab ? '' : 'none';
  });

  if (tab === 'dashboard') loadDashboard();
  if (tab === 'orders') loadOrders();
  if (tab === 'products') loadProducts();
  if (tab === 'analytics') loadAnalytics();
  if (tab === 'reviews') loadReviews();
  if (tab === 'features') { loadFeatureFlags(); loadGrowthSettings(); }
  if (tab === 'flashsales') loadFlashSales();
}

// ── App Init (gọi sau khi login thành công) ──

export function initApp() {
  loadDashboard();
  connectWS();
  requestNotificationPermission();
}

// ── Event Listeners ──

// Auth event từ auth.js (tránh circular dependency)
document.addEventListener('admin-authenticated', () => initApp());

// Tab switch event từ notifications.js (toast click → switch tab)
document.addEventListener('admin-switch-tab', (e) => switchTab(e.detail));

// Sub-tab changed → lazy load data
document.addEventListener('admin-subtab-changed', (e) => {
  const tab = e.detail;
  if (tab === 'products') loadProducts();
  if (tab === 'categories') loadCategoriesList();
  if (tab === 'toppings') loadToppingsList();
  if (tab === 'crossSell') loadCrossSellList();
});

// ══════════════════════════════════════════════════
// EXPOSE TO WINDOW — cho onclick="" trong HTML
// Sẽ chuyển sang addEventListener trong phase sau.
// ══════════════════════════════════════════════════
// Auth
window.doLogin = doLogin; // legacy
window.doLogout = doLogout; // legacy

// Tabs
window.switchTab = switchTab; // legacy

// Orders
window.toggleOrder = toggleOrder; // legacy
window.updateStatus = updateStatus; // legacy
window.filterOrders = filterOrders; // legacy

// Sound
window.toggleSound = toggleSound; // legacy

// Products sub-tabs
window.switchSubTab = switchSubTab; // legacy
window.filterProductsList = filterProductsList; // legacy
window.toggleProductActive = toggleProductActive; // legacy

// Product modal
window.openProductModal = openProductModal; // legacy
window.addSizeRow = addSizeRow; // legacy
window.toggleComboFields = toggleComboFields; // legacy
window.previewProductImage = previewProductImage; // legacy

// Category drag & drop
window.catDragStart = catDragStart; // legacy
window.catDragOver = catDragOver; // legacy
window.catDragEnd = catDragEnd; // legacy
window.catDrop = catDrop; // legacy

// Product drag & drop
window.prodDragStart = prodDragStart; // legacy
window.prodDragOver = prodDragOver; // legacy
window.prodDragEnd = prodDragEnd; // legacy
window.prodDrop = prodDrop; // legacy

// Categories
window.openCategoryModal = openCategoryModal; // legacy
window.softDeleteCategory = softDeleteCategory; // legacy
window.restoreCategory = restoreCategory; // legacy
window.toggleCategoryActive = toggleCategoryActive; // legacy

// Toppings
window.openToppingModal = openToppingModal; // legacy
window.toggleToppingActive = toggleToppingActive; // legacy

// Cross-sell
window.openCrossSellModal = openCrossSellModal; // legacy
window.openCrossSellEditModal = openCrossSellEditModal; // legacy
window.deleteCrossSell = deleteCrossSell; // legacy
window.toggleCrossSellActive = toggleCrossSellActive; // legacy

// Analytics
window.loadAnalytics = loadAnalytics; // legacy

// Reviews
window.loadReviews = loadReviews; // legacy
window.reviewsPrev = reviewsPrev; // legacy
window.reviewsNext = reviewsNext; // legacy

// Feature flags & settings
window.toggleFeature = toggleFeature; // legacy
window.onSettingInput = onSettingInput; // legacy
window.updateGrowthSetting = updateGrowthSetting; // legacy

// Flash Sales
window.loadFlashSales = loadFlashSales; // legacy
window.openFlashSaleModal = openFlashSaleModal; // legacy
window.createFlashSale = createFlashSale; // legacy
window.cancelFlashSale = cancelFlashSale; // legacy

// Modal
window.closeModal = closeModal; // legacy

// ── Bootstrap ──
initModalEscapeKey();
restoreSoundPreference();
initOrderAutoRefresh();

// Enter key to login
document.getElementById('loginPass').addEventListener('keydown', e => {
  if (e.key === 'Enter') doLogin();
});

// Check saved auth (auto-login nếu có token)
checkSavedAuth();
