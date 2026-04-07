/**
 * Customer Cart — Lưu, hiển thị, thay đổi số lượng giỏ hàng
 * ============================================================
 * Cart lưu trong localStorage key 'nn_cart2'.
 * Backend là source of truth cho giá — client chỉ hiển thị.
 */
import { cart, setCart } from './state.js';
import { fmtPd } from '../shared/formatters.js';

/** Lưu cart vào localStorage */
export function saveCart() {
  try { localStorage.setItem('nn_cart2', JSON.stringify(cart)); } catch (e) {}
}

/** Cập nhật cart bar (floating bar ở dưới cùng) */
export function updCartUI() {
  const bar = document.getElementById('cartBar');
  let cnt = 0, tot = 0;
  for (const it of Object.values(cart)) {
    cnt += it.q;
    let ip = it.p * it.q;
    if (it.tp) it.tp.forEach(t => ip += t.p * it.q);
    tot += ip;
  }
  document.getElementById('cartCnt').textContent = cnt;
  document.getElementById('cartTot').innerHTML = fmtPd(tot);
  cnt > 0 ? bar.classList.add('show') : bar.classList.remove('show');
}

/** Thay đổi số lượng món trong giỏ (từ checkout sheet) */
export function chgCartQty(key, d) {
  if (!cart[key]) return;
  cart[key].q += d;
  if (cart[key].q <= 0) delete cart[key];
  saveCart();
  updCartUI();
  // renderCheckout sẽ được gọi từ checkout.js
  document.dispatchEvent(new CustomEvent('cart-changed'));
  if (Object.keys(cart).length === 0) {
    document.dispatchEvent(new CustomEvent('cart-emptied'));
  }
}

/** Xóa toàn bộ giỏ hàng */
export function clearCartCk() {
  if (!confirm('Xóa tất cả món đã chọn?')) return;
  // Reset cart object in-place
  for (const key in cart) delete cart[key];
  saveCart();
  updCartUI();
  document.dispatchEvent(new CustomEvent('cart-emptied'));
}

/** Khôi phục giỏ hàng từ localStorage khi trang tải */
export function restoreCart() {
  try {
    const s = localStorage.getItem('nn_cart2');
    if (s) {
      const parsed = JSON.parse(s);
      for (const key in parsed) cart[key] = parsed[key];
    }
  } catch (e) {}
}
