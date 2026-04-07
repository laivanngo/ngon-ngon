/**
 * Customer Checkout — Giỏ hàng, thông tin giao hàng, đặt hàng
 * ==============================================================
 * Full checkout flow: render cart items, cross-sell, delivery info, place order.
 */
import { cart, CS_DRINK, CS_SNACK, deliveryType, setDeliveryType, ctyParam, findIt, findDbId, cartKey, curCat } from './state.js';
import { fmtP, fmtPd, esc } from '../shared/formatters.js';
import { saveCart, updCartUI } from './cart.js';
import { showToastMsg } from './social-proof.js';
import { render } from './menu.js';
import { createOrder } from '../shared/customer-api.js';
import { isOn, savePhone, saveOrderTime, showEstimatedTime, showReferralShare } from './growth.js';

export function selectDelivery(type, el) {
  setDeliveryType(type);
  document.querySelectorAll('.ck-del-opt').forEach(o => o.classList.remove('on'));
  el.classList.add('on');
  document.getElementById('ckSchedRow').style.display = type === 'scheduled' ? 'block' : 'none';
}

export function openCheckout() {
  if (Object.keys(cart).length === 0) return;
  setDeliveryType('immediate');
  renderCheckout();
  document.getElementById('ckOverlay').classList.add('show');
  setTimeout(() => document.getElementById('ckSheet').classList.add('show'), 10);
  document.body.style.overflow = 'hidden';
  document.querySelectorAll('.ck-del-opt').forEach(o => o.classList.remove('on'));
  document.querySelector('.ck-del-opt[data-type="immediate"]').classList.add('on');
  document.getElementById('ckSchedRow').style.display = 'none';
  try {
    const saved = JSON.parse(localStorage.getItem('nn_ckinfo') || '{}');
    if (saved.name) document.getElementById('ckName').value = saved.name;
    if (saved.phone) document.getElementById('ckPhone').value = saved.phone;
    if (saved.addr) document.getElementById('ckAddr').value = saved.addr;
  } catch (e) {}
  if (ctyParam && !document.getElementById('ckAddr').value) {
    document.getElementById('ckAddr').value = decodeURIComponent(ctyParam);
  }
}

export function closeCheckout() {
  document.getElementById('ckSheet').classList.remove('show');
  setTimeout(() => { document.getElementById('ckOverlay').classList.remove('show'); document.body.style.overflow = ''; }, 350);
  render(curCat);
}

export function renderCheckout() {
  const itemsEl = document.getElementById('ckItems');
  itemsEl.innerHTML = '';
  let total = 0, itemCount = 0;

  for (const [key, it] of Object.entries(cart)) {
    let lineP = it.p * it.q;
    if (it.tp) it.tp.forEach(t => lineP += t.p * it.q);
    total += lineP; itemCount += it.q;

    let details = [];
    if (it.sz) details.push('Size: ' + it.sz);
    if (it.sweet) details.push('Ngọt: ' + it.sweet);
    if (it.ice) {
      const iceLabel = { bt: 'Bình thường', it: 'Ít đá', nhieu: 'Nhiều đá', khong: 'Không đá' }[it.ice] || it.ice;
      details.push('Đá: ' + iceLabel);
    }
    if (it.tp && it.tp.length) details.push('Topping: ' + it.tp.map(t => t.n).join(', '));
    if (it.note) details.push('📝 ' + esc(it.note));

    itemsEl.innerHTML += `
      <div class="ck-item">
        <div class="ck-item-em">${it.e}</div>
        <div class="ck-item-info">
          <div class="ck-item-name">${it.n}</div>
          ${details.length ? `<div class="ck-item-detail">${details.join(' • ')}</div>` : ''}
          <div class="ck-item-bottom">
            <div class="ck-item-price">${fmtPd(lineP)}</div>
            <div class="ck-item-qty">
              <button class="ck-item-qbtn" onclick="chgCartQty('${key.replace(/'/g, "\\'")}', -1)">−</button>
              <span class="ck-item-qnum">${it.q}</span>
              <button class="ck-item-qbtn" onclick="chgCartQty('${key.replace(/'/g, "\\'")}', 1)">+</button>
            </div>
          </div>
        </div>
      </div>`;
  }

  // Cross-sell upsell section
  const upsell = document.getElementById('ckUpsell');
  const upsellItems = document.getElementById('ckUpsellItems');
  if (!isOn('cross_sell')) {
    upsell.style.display = 'none';
  } else {
    const cartIds = new Set(Object.values(cart).map(v => v.id));
    const hasDrink = [...cartIds].some(id => !id.startsWith('av') && !id.startsWith('dc'));
    const hasSnack = [...cartIds].some(id => id.startsWith('av') || id.startsWith('dc'));
    let suggestions = hasDrink && !hasSnack ? CS_DRINK : hasSnack && !hasDrink ? CS_SNACK : [...CS_DRINK.slice(0, 2), ...CS_SNACK.slice(0, 1)];
    suggestions = suggestions.filter(s => !cartIds.has(s.id));
    if (suggestions.length) {
      upsell.style.display = 'block';
      upsellItems.innerHTML = suggestions.map(s => `<div class="ck-upsell-item" onclick="quickAddFromCk('${s.id}')">${s.e} ${s.n} <b style="color:var(--brand)">+${fmtP(s.p)}</b></div>`).join('');
    } else { upsell.style.display = 'none'; }
  }

  // Summary
  document.getElementById('ckSummary').innerHTML = `
    <div class="ck-summary-row"><span>Số lượng món</span><span>${itemCount} món</span></div>
    <div class="ck-summary-row"><span>Phí giao hàng</span><span style="color:var(--green);font-weight:700">MIỄN PHÍ 🎉</span></div>
    <div class="ck-summary-total"><span>Tổng cộng</span><span class="ck-summary-total-price">${fmtPd(total)}</span></div>`;
  const orderPriceEl = document.getElementById('ckOrderPrice');
  if (orderPriceEl) orderPriceEl.textContent = fmtPd(total);
}

export function quickAddFromCk(id) {
  const it = findIt(id); if (!it) return;
  const p = it.sz ? it.sz[0].p : it.p;
  const sz = it.sz ? it.sz[0].s : '';
  const key = cartKey(id, sz, '', '', [], '');
  if (cart[key]) cart[key].q++;
  else cart[key] = { id, n: it.n, p, q: 1, e: it.e, sz, tp: [], sweet: '', ice: '', note: '', _dbId: it._dbId || 0 };
  saveCart(); updCartUI(); renderCheckout();
}

let _isOrdering = false;

export async function placeOrder() {
  if (_isOrdering) return;
  const name = document.getElementById('ckName').value.trim();
  const phone = document.getElementById('ckPhone').value.trim();
  const addr = document.getElementById('ckAddr').value.trim();
  const note = document.getElementById('ckNote').value.trim();

  if (!name) { showToastMsg('⚠️', 'Vui lòng nhập tên người nhận'); document.getElementById('ckName').focus(); return; }
  if (!phone) { showToastMsg('⚠️', 'Vui lòng nhập số điện thoại'); document.getElementById('ckPhone').focus(); return; }
  const cleanPhone = phone.replace(/[\s.\-]/g, '');
  if (!/^0[35789]\d{8}$/.test(cleanPhone)) {
    showToastMsg('⚠️', 'Số điện thoại không hợp lệ. VD: 0901234567');
    document.getElementById('ckPhone').focus(); return;
  }
  if (!addr) { showToastMsg('⚠️', 'Vui lòng nhập địa chỉ giao hàng'); document.getElementById('ckAddr').focus(); return; }
  if (deliveryType === 'scheduled') {
    const sched = document.getElementById('ckSchedTime').value;
    if (!sched) { showToastMsg('⚠️', 'Vui lòng chọn giờ giao'); document.getElementById('ckSchedTime').focus(); return; }
  }

  try { localStorage.setItem('nn_ckinfo', JSON.stringify({ name, phone: cleanPhone, addr })); } catch (e) {}

  const items = [];
  for (const key in cart) {
    const it = cart[key];
    items.push({
      product_id: it._dbId || findDbId(it.id), size: it.sz || null,
      sweetness: it.sweet || null, ice_level: it.ice || null,
      quantity: it.q, toppings: (it.tp || []).map(t => t.id), note: it.note || null,
    });
  }
  const payload = {
    customer_name: name, phone: cleanPhone, address: addr, note: note || null,
    delivery_type: deliveryType,
    scheduled_time: deliveryType === 'scheduled' ? document.getElementById('ckSchedTime').value : null,
    items,
  };

  _isOrdering = true;
  const btn = document.getElementById('ckOrderBtn');
  const origHTML = btn.innerHTML;
  btn.disabled = true; btn.innerHTML = '<span>⏳ Đang gửi đơn...</span>';

  try {
    const resp = await createOrder(payload);
    console.log('[App] Order created:', resp.public_id);
    try { localStorage.setItem('nn_last_order_id', resp.public_id); } catch (e) {}

    savePhone(cleanPhone); saveOrderTime(); showEstimatedTime(resp);
    setTimeout(() => showReferralShare(), 3000);

    document.getElementById('osOrderId').textContent = '#' + resp.public_id.substring(0, 8).toUpperCase();
    const estMin = resp.estimated_minutes || 18;
    if (!isOn('estimated_time')) {
      document.getElementById('osEstRow').style.display = 'none';
    } else {
      document.getElementById('osEstRow').style.display = '';
      document.getElementById('osEstTime').textContent = estMin + '-' + (estMin + 5) + ' phút';
    }

    if (deliveryType === 'scheduled') {
      document.getElementById('osSchedRow').style.display = 'flex';
      document.getElementById('osSchedTime').textContent = document.getElementById('ckSchedTime').value;
    } else { document.getElementById('osSchedRow').style.display = 'none'; }

    for (const key in cart) delete cart[key];
    saveCart(); updCartUI(); closeCheckout(); render(curCat);
    document.getElementById('orderSuccess').classList.add('show');
    if (navigator.vibrate) navigator.vibrate([100, 50, 100]);

  } catch (err) {
    console.error('[App] Order failed:', err);
    let msg = 'Không thể gửi đơn hàng. Vui lòng thử lại.';
    if (err.data && err.data.detail) {
      msg = Array.isArray(err.data.detail) ? err.data.detail.map(e => (e.msg || '')).join('. ') : (typeof err.data.detail === 'string' ? err.data.detail : msg);
    } else if (err.message) { msg = err.message; }
    showToastMsg('❌', msg);
  } finally { _isOrdering = false; btn.disabled = false; btn.innerHTML = origHTML; }
}

export function closeOrderSuccess() {
  document.getElementById('orderSuccess').classList.remove('show');
}
