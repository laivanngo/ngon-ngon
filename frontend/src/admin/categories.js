/**
 * Admin Categories — Quản lý danh mục sản phẩm
 * ===============================================
 * Sub-tab: danh sách danh mục, modal thêm/sửa, toggle active.
 */
import { api } from '../shared/api.js';
import { esc } from '../shared/formatters.js';
import { openModal, closeModal, setEditingId, getEditingId, setModalMode } from '../shared/ui.js';
import { _productData, loadProducts, renderProductsList, catDragStart, catDragOver, catDragEnd, catDrop } from './products.js';

export async function loadCategoriesList() {
  const content = document.getElementById('categoriesContent');
  if (!content) return;

  let data = _productData;
  if (!data) {
    try {
      const resp = await api('/admin/products');
      data = resp.categories || [];
    } catch (err) {
      content.innerHTML = `<div class="empty-state">Lỗi: ${err.message}</div>`;
      return;
    }
  }

  if (data.length === 0) {
    content.innerHTML = '<div class="empty-state" style="padding:40px"><div class="icon">📁</div>Chưa có danh mục nào</div>';
    return;
  }

  content.innerHTML = data.map(cat => {
    const statusBadge = cat.is_active
      ? `<span class="cat-badge active">Đang hiện</span>`
      : `<span class="cat-badge hidden">Đã ẩn</span>`;
    return `
      <div class="prod-card" style="cursor:pointer" onclick="openCategoryModal(${cat.id})" draggable="true"
           ondragstart="catDragStart(event,${cat.id})" ondragover="catDragOver(event)" ondrop="catDrop(event,${cat.id})" ondragend="catDragEnd(event)">
        <span class="prod-drag">⠿</span>
        <span class="prod-emoji">${cat.emoji}</span>
        <div class="prod-info">
          <div class="prod-name">${esc(cat.name)} ${statusBadge}</div>
          <div class="prod-meta">${cat.slug} · Layout: ${cat.layout} · ${cat.products.length} sản phẩm · Sort: ${cat.sort_order}</div>
        </div>
        <label class="toggle prod-toggle" onclick="event.stopPropagation()">
          <input type="checkbox" ${cat.is_active ? 'checked' : ''} onchange="toggleCategoryActive(${cat.id}, this.checked)">
          <span class="slider"></span>
        </label>
      </div>`;
  }).join('');
}

export function openCategoryModal(catId) {
  setModalMode('category');
  setEditingId(catId || null);

  let cat = null;
  if (catId && _productData) cat = _productData.find(c => c.id === catId);
  const isEdit = !!cat;
  const title = isEdit ? `Sửa danh mục: ${cat.name}` : 'Thêm danh mục mới';

  const formHtml = `
    <div class="field">
      <label class="field-label">Tên danh mục <span class="req">*</span></label>
      <input class="field-input" id="cf_name" value="${isEdit ? esc(cat.name) : ''}" placeholder="VD: Trà Sữa, Cà Phê">
    </div>
    <div class="field-row">
      <div class="field">
        <label class="field-label">Slug <span class="req">*</span></label>
        <input class="field-input" id="cf_slug" value="${isEdit ? esc(cat.slug) : ''}" placeholder="tra-sua" ${isEdit ? 'readonly style="background:#F5F5F5"' : ''}>
        <div class="field-hint">URL-friendly, VD: tra-sua, ca-phe</div>
      </div>
      <div class="field">
        <label class="field-label">Emoji</label>
        <input class="field-input" id="cf_emoji" value="${isEdit ? cat.emoji : '📦'}" placeholder="📦" style="text-align:center;font-size:18px">
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label class="field-label">Layout</label>
        <select class="field-input" id="cf_layout">
          <option value="list" ${isEdit && cat.layout === 'list' ? 'selected' : ''}>📋 List (1 cột)</option>
          <option value="grid" ${isEdit && cat.layout === 'grid' ? 'selected' : ''}>🏁 Grid (2 cột)</option>
          <option value="combo" ${isEdit && cat.layout === 'combo' ? 'selected' : ''}>🎠 Combo scroll</option>
        </select>
      </div>
      <div class="field">
        <label class="field-label">Thứ tự</label>
        <input class="field-input" id="cf_sort" type="number" value="${isEdit ? cat.sort_order : '99'}">
      </div>
    </div>`;

  openModal(title, formHtml, saveCategory);

  if (!isEdit) {
    document.getElementById('cf_name').addEventListener('input', function () {
      const slug = this.value.toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/đ/g, 'd').replace(/Đ/g, 'd')
        .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      document.getElementById('cf_slug').value = slug;
    });
  }
}

async function saveCategory() {
  const name = document.getElementById('cf_name').value.trim();
  const slug = document.getElementById('cf_slug').value.trim();
  if (!name || !slug) { alert('Tên và slug là bắt buộc'); return; }

  const payload = {
    name, emoji: document.getElementById('cf_emoji').value.trim() || '📦',
    layout: document.getElementById('cf_layout').value,
    sort_order: parseInt(document.getElementById('cf_sort').value) || 0,
  };

  try {
    const editingId = getEditingId();
    if (editingId) {
      await api(`/admin/categories/${editingId}`, { method: 'PATCH', body: JSON.stringify(payload) });
    } else {
      payload.slug = slug;
      await api('/admin/categories', { method: 'POST', body: JSON.stringify(payload) });
    }
    closeModal();
    loadProducts();
    loadCategoriesList();
  } catch (err) { alert('Lỗi: ' + err.message); }
}

export function softDeleteCategory(catId, name) {
  if (!confirm(`Ẩn danh mục "${name}"?\nSản phẩm bên trong vẫn giữ nguyên.`)) return;
  api(`/admin/categories/${catId}`, { method: 'DELETE' }).then(() => loadProducts()).catch(err => alert('Lỗi: ' + err.message));
}

export function restoreCategory(catId) {
  api(`/admin/categories/${catId}`, { method: 'PATCH', body: JSON.stringify({ is_active: true }) })
    .then(() => loadProducts()).catch(err => alert('Lỗi: ' + err.message));
}

export async function toggleCategoryActive(catId, active) {
  try {
    if (active) await api(`/admin/categories/${catId}`, { method: 'PATCH', body: JSON.stringify({ is_active: true }) });
    else await api(`/admin/categories/${catId}`, { method: 'DELETE' });
    const cat = _productData?.find(c => c.id === catId);
    if (cat) cat.is_active = active;
    loadCategoriesList();
    renderProductsList();
  } catch (err) { alert('Lỗi: ' + err.message); loadCategoriesList(); }
}
