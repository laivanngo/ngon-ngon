/**
 * Admin Toppings — Quản lý topping đồ uống
 * ==========================================
 */
import { api } from '../shared/api.js';
import { fmtP, esc } from '../shared/formatters.js';
import { openModal, closeModal, setEditingId, getEditingId, setModalMode } from '../shared/ui.js';
import { _toppingsData, setToppingsData } from './products.js';

export async function loadToppingsList() {
  const content = document.getElementById('toppingsContent');
  if (!content) return;
  content.innerHTML = '<div class="loading"><span class="spinner"></span>Đang tải...</div>';
  try {
    const data = await api('/admin/toppings');
    setToppingsData(data.toppings || []);
    renderToppingsList();
  } catch (err) { content.innerHTML = `<div class="empty-state">Lỗi: ${err.message}</div>`; }
}

function renderToppingsList() {
  const content = document.getElementById('toppingsContent');
  const data = _toppingsData;
  if (!data || data.length === 0) {
    content.innerHTML = '<div class="empty-state" style="padding:40px"><div class="icon">🍡</div>Chưa có topping nào</div>';
    return;
  }
  content.innerHTML = data.map(t => `
    <div class="topping-card ${t.is_active ? '' : 'inactive'}">
      <span class="topping-emoji">${t.emoji}</span>
      <div class="topping-info">
        <div class="topping-name">${esc(t.name)}</div>
        <div class="topping-price">${t.legacy_id} · ${fmtP(t.price)}</div>
      </div>
      <label class="toggle" onclick="event.stopPropagation()">
        <input type="checkbox" ${t.is_active ? 'checked' : ''} onchange="toggleToppingActive(${t.id}, this.checked)">
        <span class="slider"></span>
      </label>
      <button class="prod-edit-btn" onclick="openToppingModal(${t.id})" title="Chỉnh sửa">✏️</button>
    </div>
  `).join('');
}

export async function toggleToppingActive(toppingId, active) {
  try {
    if (active) await api(`/admin/toppings/${toppingId}`, { method: 'PATCH', body: JSON.stringify({ is_active: true }) });
    else await api(`/admin/toppings/${toppingId}`, { method: 'DELETE' });
    const t = _toppingsData?.find(x => x.id === toppingId);
    if (t) t.is_active = active;
    renderToppingsList();
  } catch (err) { alert('Lỗi: ' + err.message); loadToppingsList(); }
}

export function openToppingModal(toppingId) {
  setModalMode('topping');
  setEditingId(toppingId || null);
  let t = null;
  if (toppingId && _toppingsData) t = _toppingsData.find(x => x.id === toppingId);
  const isEdit = !!t;
  const title = isEdit ? `Sửa topping: ${t.name}` : 'Thêm topping mới';

  const formHtml = `
    <div class="field">
      <label class="field-label">Tên topping <span class="req">*</span></label>
      <input class="field-input" id="tf_name" value="${isEdit ? esc(t.name) : ''}" placeholder="VD: Trân châu đen">
    </div>
    <div class="field-row-3">
      <div class="field">
        <label class="field-label">Mã (legacy_id)</label>
        <input class="field-input" id="tf_legacyId" value="${isEdit ? esc(t.legacy_id) : 'tp' + Date.now().toString().slice(-4)}" ${isEdit ? 'readonly style="background:#F5F5F5"' : ''}>
      </div>
      <div class="field">
        <label class="field-label">Emoji</label>
        <input class="field-input" id="tf_emoji" value="${isEdit ? t.emoji : '🍡'}" style="text-align:center;font-size:18px">
      </div>
      <div class="field">
        <label class="field-label">Giá (k) <span class="req">*</span></label>
        <input class="field-input" id="tf_price" type="number" min="1" value="${isEdit ? t.price : '5'}">
      </div>
    </div>`;

  openModal(title, formHtml, saveTopping);
}

async function saveTopping() {
  const name = document.getElementById('tf_name').value.trim();
  const price = parseInt(document.getElementById('tf_price').value);
  if (!name) { alert('Tên topping là bắt buộc'); return; }
  if (!price || price < 1) { alert('Giá phải > 0'); return; }

  const payload = { name, emoji: document.getElementById('tf_emoji').value.trim() || '🍡', price };
  try {
    const editingId = getEditingId();
    if (editingId) {
      await api(`/admin/toppings/${editingId}`, { method: 'PATCH', body: JSON.stringify(payload) });
    } else {
      payload.legacy_id = document.getElementById('tf_legacyId').value.trim();
      await api('/admin/toppings', { method: 'POST', body: JSON.stringify(payload) });
    }
    closeModal();
    loadToppingsList();
  } catch (err) { alert('Lỗi: ' + err.message); }
}
