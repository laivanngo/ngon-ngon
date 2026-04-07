/**
 * Customer Product Detail — Bottom sheet cho chọn size/đường/đá/topping
 * ======================================================================
 * GrabFood-style bottom sheet: swipe up, chọn options, add to cart.
 */
import { M, TOPPINGS, SWEET_OPTS, ICE_OPTS, cart, isDrinkItem, cartKey, findIt, findCatBg, curCat } from './state.js';
import { fmtP, fmtPd } from '../shared/formatters.js';
import { saveCart, updCartUI } from './cart.js';
import { showToastMsg } from './social-proof.js';
import { render } from './menu.js';

/** Product detail state */
let pdItem = null, pdSz = '', pdSzPrice = 0, pdSweet = '', pdIce = '';
let pdTp = [], pdQty = 1, pdNote = '';

export function openPD(id) {
  const it = findIt(id); if (!it) return;
  pdItem = it; pdQty = 1; pdTp = []; pdSweet = ''; pdIce = ''; pdNote = '';

  const bg = it.bg || findCatBg(id);
  const hero = document.getElementById('pdHero');
  hero.className = 'pd-hero pd-hero-bg-' + bg;

  let bdgHtml = '';
  if (it.b === 'hot') bdgHtml = '<span class="pd-hero-badge hot">🔥 HOT</span>';
  else if (it.b === 'best') bdgHtml = '<span class="pd-hero-badge best">⭐ Best Seller</span>';
  let soldHtml = it.sold ? `<span class="pd-sold">Đã bán ${it.sold}+</span>` : '';
  let heroImgHtml = it.img ? `<img src="${it.img}" alt="${it.n}">` : `<span style="font-size:72px;position:relative;z-index:1">${it.e}</span>`;
  hero.innerHTML = `${heroImgHtml}${bdgHtml}${soldHtml}`;

  document.getElementById('pdName').textContent = it.n;
  document.getElementById('pdDesc').textContent = it.d || it.desc || '';

  const oldPriceEl = document.getElementById('pdOldPrice');
  if (it.old) { oldPriceEl.textContent = fmtP(it.old); oldPriceEl.style.display = 'inline'; }
  else { oldPriceEl.style.display = 'none'; }

  // Sizes
  const sizeSection = document.getElementById('pdSizeSection');
  const sizesEl = document.getElementById('pdSizes');
  if (it.sz && it.sz.length > 1) {
    sizeSection.style.display = 'block';
    pdSz = it.sz[0].s; pdSzPrice = it.sz[0].p;
    sizesEl.innerHTML = it.sz.map((s, i) => `<div class="pd-opt${i === 0 ? ' on' : ''}" data-sz="${s.s}" data-p="${s.p}" onclick="pdSelectSize(this)"><span class="pd-opt-check">✓</span><span>${s.s}</span><span class="pd-opt-price">${fmtP(s.p)}</span></div>`).join('');
  } else {
    sizeSection.style.display = 'none';
    pdSz = it.sz ? it.sz[0].s : ''; pdSzPrice = it.sz ? it.sz[0].p : it.p;
  }

  // Drink options
  const drink = isDrinkItem(it);
  document.getElementById('pdSweetSection').style.display = drink ? 'block' : 'none';
  document.getElementById('pdIceSection').style.display = drink ? 'block' : 'none';
  document.getElementById('pdTpSection').style.display = drink ? 'block' : 'none';

  if (drink) {
    document.getElementById('pdSweet').innerHTML = SWEET_OPTS.map((s, i) => `<div class="pd-opt${i === 0 ? ' on' : ''}" data-val="${s.val}" onclick="pdSelectSweet(this)"><span class="pd-opt-check">✓</span><span>${s.label}</span></div>`).join('');
    pdSweet = SWEET_OPTS[0].val;

    document.getElementById('pdIce').innerHTML = ICE_OPTS.map((s, i) => `<div class="pd-opt${i === 0 ? ' on' : ''}" data-val="${s.val}" onclick="pdSelectIce(this)"><span class="pd-opt-check">✓</span><span>${s.label}</span></div>`).join('');
    pdIce = ICE_OPTS[0].val;

    const availTp = it.toppingIds && it.toppingIds.length > 0
      ? TOPPINGS.filter(t => it.toppingIds.includes(t._dbId)) : TOPPINGS;
    document.getElementById('pdToppings').innerHTML = availTp.map(t => `<div class="pd-tp" data-id="${t.id}" data-n="${t.n}" data-p="${t.p}" onclick="pdToggleTp(this)"><span class="pd-tp-em">${t.e}</span><div class="pd-tp-info"><div class="pd-tp-name">${t.n}</div><div class="pd-tp-price">+${fmtP(t.p)}</div></div><span class="pd-tp-chk">✓</span></div>`).join('');
    if (availTp.length === 0) document.getElementById('pdTpSection').style.display = 'none';
  }

  document.getElementById('pdNote').value = '';
  document.getElementById('pdQtyNum').textContent = '1';
  document.getElementById('pdQtyMinus').classList.add('dis');
  updPdPrice();

  document.getElementById('pdOverlay').classList.add('show');
  setTimeout(() => document.getElementById('pdSheet').classList.add('show'), 10);
  document.body.style.overflow = 'hidden';
  document.getElementById('pdContent').scrollTop = 0;
}

export function closePD() {
  document.getElementById('pdSheet').classList.remove('show');
  setTimeout(() => {
    document.getElementById('pdOverlay').classList.remove('show');
    document.body.style.overflow = '';
  }, 350);
}

export function pdSelectSize(el) {
  el.parentElement.querySelectorAll('.pd-opt').forEach(o => o.classList.remove('on'));
  el.classList.add('on'); pdSz = el.dataset.sz; pdSzPrice = +el.dataset.p; updPdPrice();
}

export function pdSelectSweet(el) {
  el.parentElement.querySelectorAll('.pd-opt').forEach(o => o.classList.remove('on'));
  el.classList.add('on'); pdSweet = el.dataset.val;
}

export function pdSelectIce(el) {
  el.parentElement.querySelectorAll('.pd-opt').forEach(o => o.classList.remove('on'));
  el.classList.add('on'); pdIce = el.dataset.val;
}

export function pdToggleTp(el) {
  el.classList.toggle('on');
  const id = el.dataset.id, n = el.dataset.n, p = +el.dataset.p;
  if (el.classList.contains('on')) pdTp.push({ id, n, p });
  else pdTp = pdTp.filter(t => t.id !== id);
  updPdPrice();
}

export function pdChgQty(d) {
  pdQty = Math.max(1, pdQty + d);
  document.getElementById('pdQtyNum').textContent = pdQty;
  document.getElementById('pdQtyMinus').classList.toggle('dis', pdQty <= 1);
  updPdPrice();
}

function updPdPrice() {
  const baseP = pdItem.sz ? (pdSzPrice || pdItem.sz[0].p) : pdItem.p;
  const tpP = pdTp.reduce((s, t) => s + t.p, 0);
  const totalP = (baseP + tpP) * pdQty;
  document.getElementById('pdPrice').innerHTML = fmtP(baseP);
  document.getElementById('pdAddPrice').textContent = fmtPd(totalP);
}

export function pdAddToCart() {
  if (!pdItem) return;
  pdNote = document.getElementById('pdNote').value.trim();
  const baseP = pdItem.sz ? (pdSzPrice || pdItem.sz[0].p) : pdItem.p;
  const key = cartKey(pdItem.id, pdSz, pdSweet, pdIce, pdTp, pdNote);

  if (cart[key]) { cart[key].q += pdQty; }
  else {
    cart[key] = {
      id: pdItem.id, n: pdItem.n, p: baseP, q: pdQty, e: pdItem.e, sz: pdSz,
      tp: [...pdTp], sweet: isDrinkItem(pdItem) ? pdSweet : '',
      ice: isDrinkItem(pdItem) ? pdIce : '', note: pdNote,
      _dbId: pdItem._dbId || 0,
    };
  }
  saveCart(); updCartUI(); closePD();
  showToastMsg('✅', `Đã thêm ${pdQty} × ${pdItem.n} vào giỏ!`);
  if (navigator.vibrate) navigator.vibrate(20);
  setTimeout(() => render(curCat), 400);
}
