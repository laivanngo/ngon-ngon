/**
 * Customer State — Dữ liệu chia sẻ giữa các modules
 * =====================================================
 * WHY centralized state: nhiều modules cần đọc/ghi M, cart, TOPPINGS.
 * Export mutable objects — modules import tham chiếu, không copy.
 */

/** Menu data — populated by data-loader.js from API */
export const M = {};

/** Topping options — populated by data-loader.js from API */
export const TOPPINGS = [];

/** Cart — { cartKey: { id, n, p, q, e, sz, tp:[], sweet, ice, note, _dbId } } */
export let cart = {};
export function setCart(c) { cart = c; }

/** Current category tab */
export let curCat = 'all';
export function setCurCat(c) { curCat = c; }

/** "Show all" flags per category */
export const showAll = {};
export const SHOW_LIMIT = 6;

/** Sweetness levels */
export const SWEET_OPTS = [
  { label: '100% ngọt', val: '100%' }, { label: '70% ngọt', val: '70%' },
  { label: '50% ngọt', val: '50%' }, { label: '30% ngọt', val: '30%' },
  { label: 'Không đường', val: '0%' },
];

/** Ice levels */
export const ICE_OPTS = [
  { label: 'Bình thường', val: 'bt' }, { label: 'Ít đá', val: 'it' },
  { label: 'Nhiều đá', val: 'nhieu' }, { label: 'Không đá', val: 'khong' },
];

/** Cross-sell defaults — overridden by API /cross-sell-config */
export let CS_DRINK = [
  { n: 'Khoai Tây Chiên', p: 20, e: '🍟', id: 'dc4' },
  { n: 'Xúc Xích Chiên', p: 12, e: '🌭', id: 'dc1' },
  { n: 'Bánh Flan', p: 15, e: '🍮', id: 'mk1' },
];
export let CS_SNACK = [
  { n: 'Trà Tắc Mật Ong', p: 20, e: '🍋', id: 'h1' },
  { n: 'Trà Đào', p: 20, e: '🍑', id: 'h2' },
  { n: 'Cà Phê Sữa Đá', p: 15, e: '☕', id: 'h5' },
];

/** Social proof messages */
export const SP_MSGS = [
  '142 đơn hôm nay • 8 người đang chọn',
  'Anh Minh (Cty Pouchen) vừa đặt 3 ly trà sữa 🧋',
  'Combo Team 5 Người đang bán chạy nhất 🔥',
  '95% khách hàng đặt lại lần 2 ❤️',
  'Chị Hương (VP Tầng 3) vừa đặt Combo Giải Khát 🍑',
  'Chân Gà Sốt Thái — Hết sớm mỗi ngày!',
  'Giao hàng trung bình chỉ 18 phút ⚡',
  'Đội nhóm Cty ABC vừa đặt 8 ly 👥',
];

export const TOASTS = [
  { e: '🧋', m: 'Anh Tuấn vừa đặt 2 Trà Sữa Full Topping' },
  { e: '🍗', m: '3 suất Chân Gà Sốt Thái vừa được đặt' },
  { e: '☕', m: 'Chị Lan vừa đặt Combo Văn Phòng' },
  { e: '👥', m: 'Nhóm 5 người Cty DEF đang đặt chung' },
  { e: '🥑', m: 'Sinh Tố Bơ — Món được yêu thích nhất tuần' },
];

/** Delivery type */
export let deliveryType = 'immediate';
export function setDeliveryType(t) { deliveryType = t; }

/** URL param: công ty */
export const ctyParam = new URLSearchParams(location.search).get('cty') || '';

// ── Helper functions dùng chung ──

export function isDrinkItem(item) {
  if (item.isDrink === false) return false;
  const id = item.id;
  if (id.startsWith('av') || id.startsWith('dc') || id.startsWith('nn') || id.startsWith('tp')) return false;
  return true;
}

export function cartKey(id, sz, sweet, ice, tp, note) {
  const tpIds = (tp || []).map(t => t.id).sort().join(',');
  return `${id}|${sz || ''}|${sweet || ''}|${ice || ''}|${tpIds}|${note || ''}`;
}

export function findIt(id) {
  for (const c of Object.values(M)) {
    const i = (c.items || []).find(x => x.id === id);
    if (i) return i;
  }
  return null;
}

export function findCatBg(id) {
  for (const [k, c] of Object.entries(M)) {
    const i = (c.items || []).find(x => x.id === id);
    if (i) return i.bg || c.bg || 'x';
  }
  return 'x';
}

export function findDbId(legacyId) {
  for (const catKey in M) {
    const items = M[catKey].items || [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].id === legacyId && items[i]._dbId) return items[i]._dbId;
    }
  }
  return 0;
}
