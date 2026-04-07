/**
 * Admin Product Modal — Form thêm/sửa sản phẩm
 * ================================================
 * Tách riêng vì modal form phức tạp: sizes, toppings, combo, image preview.
 */
import { api } from '../shared/api.js';
import { fmtP, esc } from '../shared/formatters.js';
import { openModal, closeModal, setEditingId, getEditingId, setModalMode } from '../shared/ui.js';
import { _productData, _toppingsData, ensureToppingsLoaded, loadProducts } from './products.js';

/**
 * Mở modal thêm/sửa sản phẩm.
 */
export function openProductModal(productId, catId) {
  setModalMode('product');
  setEditingId(productId || null);

  let p = null;
  if (productId) {
    for (const cat of _productData) {
      p = cat.products.find(x => x.id === productId);
      if (p) { catId = cat.id; break; }
    }
  }

  const isEdit = !!p;
  const title = isEdit ? `Sửa: ${p.name}` : 'Thêm sản phẩm mới';
  const catOptions = (_productData || []).filter(c => c.is_active).map(c =>
    `<option value="${c.id}" ${c.id === catId ? 'selected' : ''}>${c.emoji} ${esc(c.name)}</option>`
  ).join('');

  const sizes = isEdit && p.sizes.length > 0 ? p.sizes : [];
  const sizesHtml = sizes.map((s, i) => sizeRowHtml(i, s.label, s.price)).join('');

  const formHtml = `
    <div class="field-row">
      <div class="field">
        <label class="field-label">Danh mục <span class="req">*</span></label>
        <select class="field-input" id="pf_category">${catOptions}</select>
      </div>
      <div class="field">
        <label class="field-label">Mã SP (legacy_id) <span class="req">*</span></label>
        <input class="field-input" id="pf_legacyId" value="${isEdit ? esc(p.legacy_id) : 'sp' + Date.now().toString().slice(-4)}" placeholder="VD: ts1, cf2" ${isEdit ? 'readonly style="background:#F5F5F5"' : ''}>
      </div>
    </div>
    <div class="field">
      <label class="field-label">Tên sản phẩm <span class="req">*</span></label>
      <input class="field-input" id="pf_name" value="${isEdit ? esc(p.name) : ''}" placeholder="VD: Trà Sữa Trân Châu">
    </div>
    <div class="field-row-3">
      <div class="field">
        <label class="field-label">Giá gốc (k) <span class="req">*</span></label>
        <input class="field-input" id="pf_price" type="number" min="1" value="${isEdit ? p.base_price : '25'}" placeholder="25">
      </div>
      <div class="field">
        <label class="field-label">Emoji</label>
        <input class="field-input" id="pf_emoji" value="${isEdit ? p.emoji : '🍽'}" placeholder="🍽" style="text-align:center;font-size:18px">
      </div>
      <div class="field">
        <label class="field-label">Badge</label>
        <select class="field-input" id="pf_badge">
          <option value="">Không</option>
          <option value="hot" ${isEdit && p.badge === 'hot' ? 'selected' : ''}>🔥 Hot</option>
          <option value="best" ${isEdit && p.badge === 'best' ? 'selected' : ''}>⭐ Best</option>
          <option value="new" ${isEdit && p.badge === 'new' ? 'selected' : ''}>🆕 New</option>
        </select>
      </div>
    </div>
    <div class="field">
      <label class="field-label">Mô tả (tùy chọn)</label>
      <textarea class="field-input" id="pf_desc" rows="2" placeholder="Mô tả ngắn gọn...">${isEdit && p.description ? esc(p.description) : ''}</textarea>
    </div>
    <div class="field">
      <label class="field-label">Hình ảnh URL (tùy chọn)</label>
      <input class="field-input" id="pf_image" value="${isEdit && p.image_path ? esc(p.image_path) : ''}" placeholder="https://... hoặc /images/product.jpg" oninput="previewProductImage()">
      <div class="img-preview" id="pf_imagePreview">
        ${isEdit && p.image_path ? `<img src="${esc(p.image_path)}" onerror="this.style.display='none';this.nextElementSibling.style.display=''">` : ''}
        <span class="placeholder" ${isEdit && p.image_path ? 'style="display:none"' : ''}>${isEdit ? p.emoji : '🍽'}</span>
      </div>
    </div>
    <div style="border-top:1px solid var(--bdr);margin:16px 0;padding-top:16px">
      <label class="field-label" style="font-size:13px;font-weight:700;color:var(--text);margin-bottom:10px">📐 Sizes (để trống nếu 1 size duy nhất)</label>
      <div class="sizes-editor" id="sizesEditor">${sizesHtml}</div>
      <button type="button" class="size-add-btn" onclick="addSizeRow()">＋ Thêm size</button>
    </div>
    <div style="border-top:1px solid var(--bdr);margin:16px 0;padding-top:12px">
      <div class="check-row"><label><input type="checkbox" id="pf_isDrink" ${!isEdit || p.is_drink ? 'checked' : ''}> Là đồ uống (hiện đường/đá/topping)</label></div>
      <div class="check-row"><label><input type="checkbox" id="pf_isCombo" ${isEdit && p.is_combo ? 'checked' : ''} onchange="toggleComboFields()"> Là Combo</label></div>
      <div id="comboFields" style="display:${isEdit && p.is_combo ? 'block' : 'none'};margin-top:8px">
        <div class="field"><label class="field-label">Mô tả Combo</label><input class="field-input" id="pf_comboDesc" value="${isEdit && p.combo_description ? esc(p.combo_description) : ''}" placeholder="VD: 2 trà sữa + 1 bánh"></div>
        <div class="field-row">
          <div class="field"><label class="field-label">Giá gốc (k)</label><input class="field-input" id="pf_origPrice" type="number" value="${isEdit && p.original_price ? p.original_price : ''}"></div>
          <div class="field"><label class="field-label">Tiết kiệm (k)</label><input class="field-input" id="pf_saveAmt" type="number" value="${isEdit && p.save_amount ? p.save_amount : ''}"></div>
        </div>
      </div>
    </div>
    <div style="border-top:1px solid var(--bdr);margin:16px 0;padding-top:16px" id="toppingPickerSection">
      <label class="field-label" style="font-size:13px;font-weight:700;color:var(--text);margin-bottom:10px">🍡 Topping được phép (bỏ trống = hiện tất cả)</label>
      <div class="field-hint" style="margin-bottom:10px">Chọn topping nào sẽ hiện khi khách đặt sản phẩm này.</div>
      <div id="toppingCheckboxes" style="display:flex;flex-wrap:wrap;gap:6px"><span style="color:var(--hint);font-size:12px">Đang tải toppings...</span></div>
    </div>`;

  openModal(title, formHtml, saveProduct);
  loadToppingCheckboxes(isEdit ? p : null);
}

function loadToppingCheckboxes(product) {
  ensureToppingsLoaded().then(() => {
    const container = document.getElementById('toppingCheckboxes');
    if (!container || !_toppingsData) return;
    const assignedIds = product?.topping_ids || [];
    const activeToppings = _toppingsData.filter(t => t.is_active);
    if (activeToppings.length === 0) {
      container.innerHTML = '<span style="color:var(--hint);font-size:12px">Chưa có topping nào active</span>';
      return;
    }
    container.innerHTML = activeToppings.map(t => {
      const checked = assignedIds.includes(t.id) ? 'checked' : '';
      return `<label style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;border:1.5px solid var(--bdr);border-radius:6px;cursor:pointer;font-size:12px;transition:all .15s;${checked ? 'border-color:var(--brand);background:var(--brand-lt)' : ''}">
        <input type="checkbox" value="${t.id}" ${checked} style="accent-color:var(--brand)" onchange="this.parentElement.style.borderColor=this.checked?'var(--brand)':'var(--bdr)';this.parentElement.style.background=this.checked?'var(--brand-lt)':''">
        ${t.emoji} ${esc(t.name)} (+${fmtP(t.price)})
      </label>`;
    }).join('');
  });
}

export function sizeRowHtml(idx, label, price) {
  return `<div class="size-row" data-idx="${idx}">
    <input class="size-label" placeholder="VD: M, L, XL" value="${esc(label || '')}">
    <input class="size-price" type="number" min="1" placeholder="Giá (k)" value="${price || ''}">
    <button type="button" class="size-remove" onclick="this.closest('.size-row').remove()" title="Xóa size">✕</button>
  </div>`;
}

export function addSizeRow() {
  const editor = document.getElementById('sizesEditor');
  const idx = editor.querySelectorAll('.size-row').length;
  editor.insertAdjacentHTML('beforeend', sizeRowHtml(idx, '', ''));
  editor.querySelector('.size-row:last-child .size-label').focus();
}

export function toggleComboFields() {
  document.getElementById('comboFields').style.display = document.getElementById('pf_isCombo').checked ? 'block' : 'none';
}

export function previewProductImage() {
  const url = document.getElementById('pf_image').value.trim();
  const preview = document.getElementById('pf_imagePreview');
  if (url) {
    preview.innerHTML = `<img src="${esc(url)}" onerror="this.style.display='none';this.nextElementSibling.style.display=''"><span class="placeholder" style="display:none">${document.getElementById('pf_emoji').value || '🍽'}</span>`;
  } else {
    preview.innerHTML = `<span class="placeholder">${document.getElementById('pf_emoji').value || '🍽'}</span>`;
  }
}

async function saveProduct() {
  const name = document.getElementById('pf_name').value.trim();
  const price = parseInt(document.getElementById('pf_price').value);
  const legacyId = document.getElementById('pf_legacyId').value.trim();
  const catId = parseInt(document.getElementById('pf_category').value);

  if (!name) { document.getElementById('pf_name').classList.add('error'); return; }
  if (!price || price < 1) { document.getElementById('pf_price').classList.add('error'); return; }
  if (!legacyId) { document.getElementById('pf_legacyId').classList.add('error'); return; }

  const sizeRows = document.querySelectorAll('#sizesEditor .size-row');
  const sizes = [];
  for (const row of sizeRows) {
    const label = row.querySelector('.size-label').value.trim();
    const p = parseInt(row.querySelector('.size-price').value);
    if (label && p > 0) sizes.push({ label, price: p });
  }

  const payload = {
    category_id: catId, name, base_price: price,
    emoji: document.getElementById('pf_emoji').value.trim() || '🍽',
    badge: document.getElementById('pf_badge').value || null,
    description: document.getElementById('pf_desc').value.trim() || null,
    image_path: document.getElementById('pf_image').value.trim() || null,
    is_drink: document.getElementById('pf_isDrink').checked,
    is_combo: document.getElementById('pf_isCombo').checked,
    sizes,
  };
  const toppingChecks = document.querySelectorAll('#toppingCheckboxes input[type=checkbox]:checked');
  payload.topping_ids = [...toppingChecks].map(cb => parseInt(cb.value));

  if (payload.is_combo) {
    payload.combo_description = document.getElementById('pf_comboDesc').value.trim() || null;
    payload.original_price = parseInt(document.getElementById('pf_origPrice').value) || null;
    payload.save_amount = parseInt(document.getElementById('pf_saveAmt').value) || null;
  }

  try {
    const editingId = getEditingId();
    if (editingId) {
      await api(`/admin/products/${editingId}`, { method: 'PATCH', body: JSON.stringify(payload) });
    } else {
      payload.legacy_id = legacyId;
      await api('/admin/products', { method: 'POST', body: JSON.stringify(payload) });
    }
    closeModal();
    loadProducts();
  } catch (err) { alert('Lỗi: ' + err.message); }
}
