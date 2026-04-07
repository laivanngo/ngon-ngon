/**
 * Admin Products — Quản lý sản phẩm, Drag & Drop, Product Modal
 * ================================================================
 * Module lớn nhất của admin panel (~250 dòng) vì quản lý sản phẩm
 * là tính năng phức tạp nhất: CRUD + drag/drop + modal form.
 * Nếu cần tách thêm → tách product-modal.js riêng.
 */
import { api } from '../shared/api.js';
import { fmtP, esc } from '../shared/formatters.js';
import { openModal, closeModal, setEditingId, getEditingId, setModalMode } from '../shared/ui.js';

/** Product data cache — dùng chung cho products, categories sub-tab */
export let _productData = null;
/** Toppings data cache */
export let _toppingsData = null;

/** Current sub-tab */
let _currentSubTab = 'products';
export function getCurrentSubTab() { return _currentSubTab; }

// ── Sub-tab Switching ──────────────────────────────────

export function switchSubTab(tab) {
  document.querySelectorAll('.sub-tab').forEach(t => t.classList.toggle('on', t.dataset.sub === tab));
  document.querySelectorAll('.sub-panel').forEach(p => p.classList.remove('on'));
  const panel = document.getElementById('sub' + tab.charAt(0).toUpperCase() + tab.slice(1));
  if (panel) panel.classList.add('on');
  _currentSubTab = tab;

  // Lazy load data khi chuyển sub-tab
  document.dispatchEvent(new CustomEvent('admin-subtab-changed', { detail: tab }));
}

// ── Load & Render Products ─────────────────────────────

export async function loadProducts() {
  const content = document.getElementById('productsContent');
  if (!content) return;
  content.innerHTML = '<div class="loading"><span class="spinner"></span>Đang tải...</div>';
  try {
    const data = await api('/admin/products');
    _productData = data.categories || [];
    renderProductsList();
  } catch (err) {
    content.innerHTML = `<div class="empty-state">Lỗi: ${err.message}</div>`;
  }
}

export function renderProductsList() {
  const content = document.getElementById('productsContent');
  const searchTerm = (document.getElementById('prodSearch')?.value || '').toLowerCase();

  if (!_productData || _productData.length === 0) {
    content.innerHTML = '<div class="empty-state" style="padding:40px"><div class="icon">📦</div>Chưa có danh mục nào. Tạo danh mục trước, rồi thêm sản phẩm.</div>';
    return;
  }

  let html = '';
  for (const cat of _productData) {
    let prods = cat.products;
    if (searchTerm) {
      prods = prods.filter(p =>
        p.name.toLowerCase().includes(searchTerm) ||
        p.legacy_id.toLowerCase().includes(searchTerm) ||
        (p.badge && p.badge.toLowerCase().includes(searchTerm))
      );
      if (prods.length === 0) continue;
    }

    const catStatusBadge = cat.is_active
      ? `<span class="cat-badge active">Đang hiện</span>`
      : `<span class="cat-badge hidden">Đã ẩn</span>`;

    html += `<div class="cat-section" data-cat-id="${cat.id}">
      <div class="cat-header" draggable="true" ondragstart="catDragStart(event,${cat.id})" ondragover="catDragOver(event)" ondrop="catDrop(event,${cat.id})" ondragend="catDragEnd(event)">
        <div class="cat-info">
          <span class="drag-handle" title="Kéo thả sắp xếp">⠿</span>
          <span class="cat-emoji">${cat.emoji}</span>
          <span class="cat-name">${esc(cat.name)}</span>
          ${catStatusBadge}
          <span class="cat-count">${prods.length} sản phẩm</span>
        </div>
        <div class="cat-actions">
          <button class="cat-btn" onclick="event.stopPropagation();openCategoryModal(${cat.id})" title="Sửa danh mục">✏️</button>
          ${cat.is_active
            ? `<button class="cat-btn" onclick="event.stopPropagation();softDeleteCategory(${cat.id},'${esc(cat.name)}')" title="Ẩn danh mục">🙈</button>`
            : `<button class="cat-btn" onclick="event.stopPropagation();restoreCategory(${cat.id})" title="Hiện lại danh mục">👁️</button>`}
        </div>
      </div>
      <div class="prod-list" id="prodList-${cat.id}">`;

    if (prods.length === 0) {
      html += `<div class="cat-empty">Chưa có sản phẩm trong danh mục này</div>`;
    } else {
      for (const p of prods) {
        const sizesStr = p.sizes.length > 0 ? p.sizes.map(s => `${s.label}: ${fmtP(s.price)}`).join(' · ') : fmtP(p.base_price);
        const badgeHtml = p.badge ? `<span class="badge-tag badge-${p.badge}">${p.badge}</span>` : '';
        const comboTag = p.is_combo ? `<span class="badge-tag" style="background:#EDE7F6;color:#5E35B1">combo</span>` : '';

        html += `
          <div class="prod-card ${p.is_active ? '' : 'inactive'}" data-prod-id="${p.id}" draggable="true"
               ondragstart="prodDragStart(event,${p.id},${cat.id})" ondragover="prodDragOver(event)" ondrop="prodDrop(event,${p.id},${cat.id})" ondragend="prodDragEnd(event)">
            <span class="prod-drag" title="Kéo thả sắp xếp">⠿</span>
            <span class="prod-emoji">${p.emoji}</span>
            <div class="prod-info">
              <div class="prod-name">${esc(p.name)} ${badgeHtml} ${comboTag}</div>
              <div class="prod-meta">${p.legacy_id} · ${sizesStr}${p.is_drink ? ' · 🧊 Đồ uống' : ''}${p.topping_ids?.length > 0 ? ' · 🍡' + p.topping_ids.length + ' topping' : ''}</div>
            </div>
            <div class="prod-price">${fmtP(p.base_price)}</div>
            <label class="toggle prod-toggle" title="${p.is_active ? 'Đang bán — bấm để ẩn' : 'Đã ẩn — bấm để hiện'}">
              <input type="checkbox" ${p.is_active ? 'checked' : ''} onchange="toggleProductActive(${p.id}, this.checked)">
              <span class="slider"></span>
            </label>
            <button class="prod-edit-btn" onclick="openProductModal(${p.id}, ${cat.id})" title="Chỉnh sửa">✏️</button>
          </div>`;
      }
    }
    html += '</div></div>';
  }
  content.innerHTML = html || '<div class="empty-state" style="padding:40px">Không tìm thấy sản phẩm nào.</div>';
}

export function filterProductsList() { renderProductsList(); }

export async function toggleProductActive(productId, active) {
  try {
    await api(`/admin/products/${productId}`, { method: 'PATCH', body: JSON.stringify({ is_active: active }) });
    for (const cat of _productData) {
      const p = cat.products.find(x => x.id === productId);
      if (p) { p.is_active = active; break; }
    }
    renderProductsList();
  } catch (err) { alert('Lỗi: ' + err.message); loadProducts(); }
}

// ── Drag & Drop — Categories ───────────────────────────

let _dragCatId = null;

export function catDragStart(e, catId) { _dragCatId = catId; e.dataTransfer.effectAllowed = 'move'; e.currentTarget.classList.add('dragging'); }
export function catDragOver(e) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }
export function catDragEnd(e) { e.currentTarget.classList.remove('dragging'); _dragCatId = null; }
export async function catDrop(e, targetCatId) {
  e.preventDefault();
  if (_dragCatId === null || _dragCatId === targetCatId) return;
  const fromIdx = _productData.findIndex(c => c.id === _dragCatId);
  const toIdx = _productData.findIndex(c => c.id === targetCatId);
  if (fromIdx === -1 || toIdx === -1) return;
  const [moved] = _productData.splice(fromIdx, 1);
  _productData.splice(toIdx, 0, moved);
  for (let i = 0; i < _productData.length; i++) {
    _productData[i].sort_order = i;
    api(`/admin/categories/${_productData[i].id}`, { method: 'PATCH', body: JSON.stringify({ sort_order: i }) }).catch(() => {});
  }
  renderProductsList();
}

// ── Drag & Drop — Products (within category) ──────────

let _dragProdId = null;
let _dragProdCatId = null;

export function prodDragStart(e, prodId, catId) { _dragProdId = prodId; _dragProdCatId = catId; e.dataTransfer.effectAllowed = 'move'; e.currentTarget.classList.add('dragging'); e.stopPropagation(); }
export function prodDragOver(e) { e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = 'move'; }
export function prodDragEnd(e) { e.currentTarget.classList.remove('dragging'); _dragProdId = null; }
export async function prodDrop(e, targetProdId, targetCatId) {
  e.preventDefault(); e.stopPropagation();
  if (_dragProdId === null || _dragProdId === targetProdId) return;
  const cat = _productData.find(c => c.id === targetCatId);
  if (!cat) return;
  const fromIdx = cat.products.findIndex(p => p.id === _dragProdId);
  const toIdx = cat.products.findIndex(p => p.id === targetProdId);
  if (fromIdx === -1 || toIdx === -1) return;
  const [moved] = cat.products.splice(fromIdx, 1);
  cat.products.splice(toIdx, 0, moved);
  for (let i = 0; i < cat.products.length; i++) {
    cat.products[i].sort_order = i;
    api(`/admin/products/${cat.products[i].id}`, { method: 'PATCH', body: JSON.stringify({ sort_order: i }) }).catch(() => {});
  }
  renderProductsList();
}

// ── Ensure Toppings Loaded ─────────────────────────────

export async function ensureToppingsLoaded() {
  if (_toppingsData && _toppingsData.length > 0) return;
  try { const data = await api('/admin/toppings'); _toppingsData = data.toppings || []; }
  catch (e) { _toppingsData = []; }
}

export function setToppingsData(data) { _toppingsData = data; }

// ── Product Modal ──────────────────────────────────────
// See product-modal.js (tách riêng vì modal form phức tạp)
