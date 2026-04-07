/**
 * Admin Cross-Sell — "Thêm cho đủ bữa?" Management
 * ====================================================
 */
import { api } from '../shared/api.js';
import { fmtP, esc } from '../shared/formatters.js';
import { openModal, closeModal, setEditingId, getEditingId, setModalMode } from '../shared/ui.js';
import { _productData } from './products.js';

let _crossSellData = null;

export async function loadCrossSellList() {
  const content = document.getElementById('crossSellContent');
  if (!content) return;
  content.innerHTML = '<div class="loading"><span class="spinner"></span>Đang tải...</div>';
  try {
    const data = await api('/admin/cross-sell');
    _crossSellData = data.items || [];
    renderCrossSellList();
  } catch (err) { content.innerHTML = `<div class="empty-state">Lỗi: ${err.message}</div>`; }
}

function renderCrossSellList() {
  const content = document.getElementById('crossSellContent');
  if (!_crossSellData || _crossSellData.length === 0) {
    content.innerHTML = `<div class="empty-state" style="padding:40px"><div class="icon">🛒</div>Chưa cấu hình món cross-sell nào.<br><span style="font-size:12px;color:var(--text2)">Thêm sản phẩm để hiện trong "👉 Thêm cho đủ bữa?" khi khách thanh toán.</span></div>`;
    return;
  }
  const targetLabels = { drink: '🍹 Gợi khi có đồ uống', snack: '🍟 Gợi khi có ăn vặt', both: '🔄 Luôn gợi ý' };
  content.innerHTML = _crossSellData.map(cs => `
    <div class="prod-card">
      <span class="prod-emoji">${cs.product_emoji}</span>
      <div class="prod-info">
        <div class="prod-name">${esc(cs.product_name)}</div>
        <div class="prod-meta">${cs.product_legacy_id} · ${fmtP(cs.product_price)} · ${targetLabels[cs.target] || cs.target} · Sort: ${cs.sort_order}</div>
      </div>
      <label class="toggle" onclick="event.stopPropagation()">
        <input type="checkbox" ${cs.is_active ? 'checked' : ''} onchange="toggleCrossSellActive(${cs.id}, this.checked)">
        <span class="slider"></span>
      </label>
      <button class="prod-edit-btn" onclick="openCrossSellEditModal(${cs.id})" title="Chỉnh sửa">✏️</button>
      <button class="prod-edit-btn" onclick="deleteCrossSell(${cs.id},'${esc(cs.product_name)}')" title="Xóa" style="color:#C62828">🗑️</button>
    </div>
  `).join('');
}

export async function toggleCrossSellActive(csId, active) {
  try {
    await api(`/admin/cross-sell/${csId}`, { method: 'PATCH', body: JSON.stringify({ is_active: active }) });
    const cs = _crossSellData?.find(x => x.id === csId);
    if (cs) cs.is_active = active;
    renderCrossSellList();
  } catch (err) { alert('Lỗi: ' + err.message); loadCrossSellList(); }
}

export async function deleteCrossSell(csId, name) {
  if (!confirm(`Xóa "${name}" khỏi danh sách cross-sell?`)) return;
  try { await api(`/admin/cross-sell/${csId}`, { method: 'DELETE' }); loadCrossSellList(); }
  catch (err) { alert('Lỗi: ' + err.message); }
}

export function openCrossSellModal() {
  setModalMode('crosssell'); setEditingId(null);
  let prodOptions = '<option value="">-- Chọn sản phẩm --</option>';
  if (_productData) {
    for (const cat of _productData) {
      for (const p of cat.products) {
        if (p.is_active) prodOptions += `<option value="${p.id}">${p.emoji} ${esc(p.name)} (${fmtP(p.base_price)})</option>`;
      }
    }
  }
  const formHtml = `
    <div class="field"><label class="field-label">Sản phẩm <span class="req">*</span></label><select class="field-input" id="cs_productId">${prodOptions}</select></div>
    <div class="field"><label class="field-label">Hiển thị khi</label>
      <select class="field-input" id="cs_target">
        <option value="both">🔄 Luôn gợi ý</option><option value="drink">🍹 Gợi khi giỏ có đồ uống</option><option value="snack">🍟 Gợi khi giỏ có ăn vặt</option>
      </select>
      <div class="field-hint">VD: khách có trà sữa, gợi thêm khoai tây chiên → "Gợi khi giỏ có đồ uống"</div>
    </div>
    <div class="field"><label class="field-label">Thứ tự</label><input class="field-input" id="cs_sort" type="number" value="0"></div>`;
  openModal('Thêm món Cross-Sell', formHtml, saveCrossSell);
}

export function openCrossSellEditModal(csId) {
  const cs = _crossSellData?.find(x => x.id === csId);
  if (!cs) return;
  setModalMode('crosssell'); setEditingId(csId);
  const formHtml = `
    <div class="field"><label class="field-label">Sản phẩm</label><input class="field-input" value="${cs.product_emoji} ${esc(cs.product_name)} (${fmtP(cs.product_price)})" readonly style="background:#F5F5F5"></div>
    <div class="field"><label class="field-label">Hiển thị khi</label>
      <select class="field-input" id="cs_target"><option value="both" ${cs.target === 'both' ? 'selected' : ''}>🔄 Luôn gợi ý</option><option value="drink" ${cs.target === 'drink' ? 'selected' : ''}>🍹 Gợi khi giỏ có đồ uống</option><option value="snack" ${cs.target === 'snack' ? 'selected' : ''}>🍟 Gợi khi giỏ có ăn vặt</option></select>
    </div>
    <div class="field"><label class="field-label">Thứ tự</label><input class="field-input" id="cs_sort" type="number" value="${cs.sort_order}"></div>`;
  openModal('Sửa Cross-Sell: ' + cs.product_name, formHtml, saveCrossSell);
}

async function saveCrossSell() {
  const target = document.getElementById('cs_target').value;
  const sortOrder = parseInt(document.getElementById('cs_sort').value) || 0;
  try {
    const editingId = getEditingId();
    if (editingId) {
      await api(`/admin/cross-sell/${editingId}`, { method: 'PATCH', body: JSON.stringify({ target, sort_order: sortOrder }) });
    } else {
      const productId = parseInt(document.getElementById('cs_productId').value);
      if (!productId) { alert('Vui lòng chọn sản phẩm'); return; }
      await api('/admin/cross-sell', { method: 'POST', body: JSON.stringify({ product_id: productId, target, sort_order: sortOrder }) });
    }
    closeModal(); loadCrossSellList();
  } catch (err) { alert('Lỗi: ' + err.message); }
}
