/**
 * Customer Menu — Render menu sections and product cards
 * ========================================================
 * Responsible for displaying the menu grid/list, category sections,
 * and search results. Card clicks dispatch to product-detail module.
 */
import { M, cart, showAll, SHOW_LIMIT, curCat, setCurCat } from './state.js';
import { fmtP } from '../shared/formatters.js';
import { getFlashSaleProductIds, getFlashSaleInfo } from './flash-sale.js';

/**
 * Render menu based on selected category or search term.
 * @param {string|null} cat - Category slug or null for search
 * @param {string} search - Search query (empty = show category)
 */
export function render(cat, search = '') {
  if (cat !== null && cat !== undefined) setCurCat(cat);
  const el = document.getElementById('mc');
  el.innerHTML = '';

  if (search) {
    const s = search.toLowerCase();
    let found = [];
    Object.values(M).forEach(c => {
      if (c.isCombo) return;
      c.items.forEach(i => {
        if (i.n.toLowerCase().includes(s) || (i.d && i.d.toLowerCase().includes(s)))
          found.push({ ...i, bg: i.bg || c.bg || 'x' });
      });
    });
    if (!found.length) {
      el.innerHTML = '<div class="empty-st"><div class="ee">😢</div>Không tìm thấy món — Thử từ khóa khác!</div>';
      return;
    }
    el.innerHTML = `<div class="sec-h"><span class="sec-em">🔍</span><span class="sec-t">Tìm thấy ${found.length} món</span></div>`;
    const g = document.createElement('div'); g.className = 'grid';
    found.forEach(i => g.appendChild(mkCard(i)));
    el.appendChild(g);
    return;
  }

  const activeCat = cat || curCat;
  renderFlashSaleSection(el);
  if (activeCat === 'all') Object.keys(M).forEach(k => renderSection(k, el, true));
  else renderSection(activeCat, el, false);
}

function renderFlashSaleSection(parentEl) {
  const { ids, discount } = getFlashSaleInfo();
  if (ids.size === 0) return;
  const items = [];
  for (const c of Object.values(M)) {
    if (c.isCombo) continue;
    for (const item of (c.items || [])) {
      if (ids.has(item._dbId)) items.push({ ...item, bg: item.bg || c.bg || 'x' });
    }
  }
  if (!items.length) return;
  const h = document.createElement('div'); h.className = 'sec-h';
  h.innerHTML = `<span class="sec-em">⚡</span><span class="sec-t">Flash Sale -${discount}%</span><span class="sec-c">${items.length} món</span>`;
  parentEl.appendChild(h);
  const g = document.createElement('div'); g.className = 'grid';
  items.forEach(i => g.appendChild(mkCard(i)));
  parentEl.appendChild(g);
}

function renderSection(cat, parentEl, isAllView) {
  const c = M[cat]; if (!c) return;
  const h = document.createElement('div'); h.className = 'sec-h';
  h.innerHTML = `<span class="sec-em">${c.em}</span><span class="sec-t">${c.t}</span><span class="sec-c">${c.items.length} món</span>`;
  parentEl.appendChild(h);

  if (c.isCombo) {
    const sc = document.createElement('div'); sc.className = 'combo-s';
    c.items.forEach(i => {
      const qty = getItemQtyInCart(i.id);
      const cd = document.createElement('div'); cd.className = 'cc' + (qty > 0 ? ' in' : '');
      cd.innerHTML = `<div class="cc-img">${i.img ? `<img src="${i.img}" alt="${i.n}" loading="lazy">` : i.e}<span class="cc-badge">COMBO</span><span class="cc-save">-${fmtP(i.sv)}</span>${qty > 0 ? `<span class="cc-qty-badge">${qty}</span>` : ''}</div><div class="cc-body"><div class="cc-name">${i.n}</div><div class="cc-desc">${i.desc}</div><div class="cc-pr"><span class="cc-old">${fmtP(i.old)}</span><span class="cc-new">${fmtP(i.p)}</span></div></div>`;
      cd.onclick = () => window.openPD(i.id); // legacy global
      sc.appendChild(cd);
    });
    parentEl.appendChild(sc);
  } else {
    // Sort flash sale items lên đầu danh mục
    const fsIds = getFlashSaleProductIds();
    const items = fsIds.size > 0
      ? [...c.items].sort((a, b) => (fsIds.has(a._dbId) ? 0 : 1) - (fsIds.has(b._dbId) ? 0 : 1))
      : c.items;
    const limit = showAll[cat] ? items.length : Math.min(SHOW_LIMIT, items.length);
    const useGrid = (cat === 'hot');
    const container = document.createElement('div');
    container.className = useGrid ? 'grid' : 'list';
    for (let i = 0; i < limit; i++) {
      const itemData = { ...items[i], bg: items[i].bg || c.bg || 'x' };
      container.appendChild(useGrid ? mkCard(itemData) : mkListCard(itemData));
    }
    parentEl.appendChild(container);
    if (items.length > SHOW_LIMIT && !showAll[cat]) {
      const btn = document.createElement('button'); btn.className = 'more-btn';
      btn.textContent = `Xem thêm ${items.length - SHOW_LIMIT} món ↓`;
      btn.onclick = () => { showAll[cat] = 1; render(curCat); };
      parentEl.appendChild(btn);
    }
  }
}

function getItemQtyInCart(id) {
  let q = 0;
  for (const [k, v] of Object.entries(cart)) { if (v.id === id) q += v.q; }
  return q;
}

function mkCard(it) {
  const cd = document.createElement('div');
  const qty = getItemQtyInCart(it.id);
  cd.className = 'pc' + (qty > 0 ? ' in' : '');
  const bg = it.bg || 'x';
  const pr = it.sz ? it.sz[0].p : it.p;
  const { ids: fsIds, discount: fsDsc } = getFlashSaleInfo();
  const isFs = fsIds.has(it._dbId);
  let bdg = '';
  if (isFs) bdg = '<span class="bdg fs">⚡ Sale</span>';
  else if (it.b === 'hot') bdg = '<span class="bdg hot">🔥 HOT</span>';
  else if (it.b === 'best') bdg = '<span class="bdg best">⭐ Best</span>';
  let sold = it.sold ? `<span class="sold-t">Đã bán ${it.sold}+</span>` : '';
  let desc = it.d ? `<div class="pd">${it.d}</div>` : '';
  const priceHtml = isFs && fsDsc > 0
    ? `<span class="pp-old">${fmtP(pr)}</span><span class="pp-fs">${fmtP(pr - Math.floor(pr * fsDsc / 100))}</span>`
    : fmtP(pr);
  cd.innerHTML = `<div class="pi bg-${bg}">${bdg}${it.img ? `<img src="${it.img}" alt="${it.n}" loading="lazy">` : it.e}${sold}${qty > 0 ? `<span class="pc-qty-badge">${qty}</span>` : ''}</div><div class="pb"><div class="pn">${it.n}</div>${desc}<div class="pbot"><div class="pp">${priceHtml}</div></div></div>`;
  cd.onclick = () => window.openPD(it.id); // legacy global
  return cd;
}

function mkListCard(it) {
  const cd = document.createElement('div');
  const qty = getItemQtyInCart(it.id);
  cd.className = 'lc' + (qty > 0 ? ' in' : '');
  const bg = it.bg || 'x';
  const pr = it.sz ? it.sz[0].p : it.p;
  const { ids: fsIds, discount: fsDsc } = getFlashSaleInfo();
  const isFs = fsIds.has(it._dbId);
  let bdgH = '';
  if (isFs) bdgH = '<span class="lc-badge fs">⚡ Sale</span>';
  else if (it.b === 'hot') bdgH = '<span class="lc-badge hot">🔥 HOT</span>';
  else if (it.b === 'best') bdgH = '<span class="lc-badge best">⭐ Best</span>';
  let desc = it.d ? `<div class="lc-desc">${it.d}</div>` : '';
  const priceHtml = isFs && fsDsc > 0
    ? `<span class="lc-old">${fmtP(pr)}</span><span class="lc-fs">${fmtP(pr - Math.floor(pr * fsDsc / 100))}</span>`
    : fmtP(pr);
  cd.innerHTML = `
    <div class="lc-img bg-${bg}">${it.img ? `<img src="${it.img}" alt="${it.n}" loading="lazy">` : it.e}${qty > 0 ? `<span class="lc-qty-badge">${qty}</span>` : ''}</div>
    <div class="lc-body">
      <div class="lc-top"><div class="lc-info"><div class="lc-name">${it.n}</div>${desc}</div>${bdgH}</div>
      <div class="lc-bot"><div class="lc-right"><div class="lc-price">${priceHtml}</div></div></div>
    </div>`;
  cd.onclick = () => window.openPD(it.id); // legacy global
  return cd;
}
