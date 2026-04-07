/**
 * Customer Data Loader — Load menu, toppings, cross-sell từ API
 * ===============================================================
 * Migrated from js/app.js IIFE. Loads API data into shared state (M, TOPPINGS).
 * Falls back to localStorage cache khi API lỗi (mạng 4G KCN không ổn định).
 */
import { M, TOPPINGS, CS_DRINK, CS_SNACK } from './state.js';
import { render } from './menu.js';
import { updCartUI } from './cart.js';
import { getMenu, getToppings, getTimeDeals, getCrossSellConfig } from '../shared/customer-api.js';

/**
 * Transform API menu response → M format (legacy compact format).
 * WHY keep compact format: render functions dùng M.catSlug.items[].n, .p, .e...
 * Đổi format → phải sửa 200+ chỗ trong render. Sẽ làm trong phase sau.
 */
function transformMenuData(apiResponse) {
  const menuData = {};
  for (const cat of apiResponse.categories) {
    const isCombo = cat.layout === 'combo';
    const items = cat.products.map(p => {
      const item = {
        id: p.legacy_id, _dbId: p.id, n: p.name, d: p.description || '',
        p: p.base_price, e: p.emoji, b: p.badge || undefined,
        bg: p.bg_class, sold: p.sold_count || 0, isDrink: p.is_drink,
      };
      if (p.image_path) item.img = p.image_path;
      if (p.sizes && p.sizes.length > 0) item.sz = p.sizes.map(s => ({ s: s.label, p: s.price }));
      if (p.is_combo) { item.desc = p.combo_description; item.old = p.original_price; item.sv = p.save_amount; }
      if (p.topping_ids && p.topping_ids.length > 0) item.toppingIds = p.topping_ids;
      return item;
    });
    menuData[cat.slug] = {
      t: cat.name, em: cat.emoji,
      bg: (cat.products[0] && cat.products[0].bg_class) || 'x',
      isCombo: isCombo ? 1 : undefined, items,
    };
  }
  return menuData;
}

function transformToppings(apiToppings) {
  return apiToppings.map(t => ({ id: t.legacy_id, _dbId: t.id, n: t.name, e: t.emoji, p: t.price }));
}

/**
 * Init menu — load from API, fallback to cache.
 * WHY cache: mạng KCN hay chập chờn, khách vẫn cần xem menu.
 */
export async function initMenu() {
  try {
    const mc = document.getElementById('mc');
    if (mc) mc.innerHTML = '<div class="empty-st"><div class="ee">⏳</div>Đang tải menu...</div>';

    const results = await Promise.all([
      getMenu(),
      getToppings(),
    ]);

    const newM = transformMenuData(results[0]);
    Object.keys(newM).forEach(k => { M[k] = newM[k]; });

    const newToppings = transformToppings(results[1]);
    TOPPINGS.length = 0;
    newToppings.forEach(t => TOPPINGS.push(t));

    try {
      localStorage.setItem('nn_menu_cache', JSON.stringify(newM));
      localStorage.setItem('nn_toppings_cache', JSON.stringify(newToppings));
    } catch (e) {}

    console.log('[App] Menu loaded: ' + Object.keys(newM).length + ' categories');
  } catch (err) {
    console.warn('[App] API failed, trying cache:', err.message);
    try {
      const cachedMenu = JSON.parse(localStorage.getItem('nn_menu_cache'));
      const cachedToppings = JSON.parse(localStorage.getItem('nn_toppings_cache'));
      if (cachedMenu) Object.keys(cachedMenu).forEach(k => { M[k] = cachedMenu[k]; });
      if (cachedToppings) { TOPPINGS.length = 0; cachedToppings.forEach(t => TOPPINGS.push(t)); }
      console.log('[App] Using cached data');
    } catch (e) { console.error('[App] No cache. Menu empty.'); }
  }

  render('all');
  updCartUI();
}

/**
 * Load cross-sell config from API (override hardcoded defaults).
 */
export async function initCrossSellConfig() {
  try {
    const data = await getCrossSellConfig();
    if (data.drink && data.drink.length > 0) { CS_DRINK.length = 0; data.drink.forEach(item => CS_DRINK.push(item)); }
    if (data.snack && data.snack.length > 0) { CS_SNACK.length = 0; data.snack.forEach(item => CS_SNACK.push(item)); }
    console.log('[App] Cross-sell config loaded: ' + CS_DRINK.length + ' drink, ' + CS_SNACK.length + ' snack');
  } catch (e) { console.warn('[App] Cross-sell config failed, using defaults:', e.message); }
}

/**
 * Load time deals from API.
 */
export async function initTimeDeals() {
  try {
    const deals = await getTimeDeals();
    if (deals.length > 0) {
      const deal = deals[0];
      const label = document.getElementById('tdLabel');
      const title = document.getElementById('tdTitle');
      if (label) label.textContent = deal.label;
      if (title) title.textContent = deal.title;
    }
  } catch (e) { /* Non-critical, fail silently */ }
}

// patchAddToCart removed — product-detail.js (ES module) already injects _dbId directly
