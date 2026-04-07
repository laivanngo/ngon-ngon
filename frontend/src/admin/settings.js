/**
 * Admin Settings — Feature Flags & Growth Settings
 * ==================================================
 * Bật/tắt tính năng + điều chỉnh giá trị kinh doanh (loyalty threshold...).
 */
import { api } from '../shared/api.js';
import { esc } from '../shared/formatters.js';

export async function loadFeatureFlags() {
  const content = document.getElementById('flagsContent');
  if (!content) return;
  content.innerHTML = '<div class="loading"><span class="spinner"></span>Đang tải...</div>';

  try {
    const data = await api('/crm/config');
    const flags = data.flags || {};

    const descriptions = {
      upsell: '① Gợi ý thêm topping / size lớn khi chọn món → +15-30% giá trị đơn',
      reorder: '② Nút "Đặt lại đơn trước" trên trang chủ → +20-40% đơn lặp',
      cross_sell: '③ Gợi ý mua kèm trong giỏ hàng → +10-15% giá trị đơn',
      estimated_time: '④ Hiện thời gian giao ước tính → -30-50% hủy đơn',
      loyalty: '⑤ Tích điểm mua 10 tặng 1 → +15-25% retention',
      analytics: '⑥ Dashboard phân tích cho chủ quán',
      reviews: '⑦ Đánh giá sau khi nhận hàng → cải thiện chất lượng',
      push_notifications: '⑧ Push notification deal giờ vàng → +10-15% đơn',
      referral: '⑨ Giới thiệu bạn bè được giảm giá → giảm chi phí acquire',
    };

    const orderedKeys = Object.keys(descriptions).filter(k => k in flags);
    Object.keys(flags).forEach(k => { if (!orderedKeys.includes(k)) orderedKeys.push(k); });

    content.innerHTML = orderedKeys.map(key => `
      <div class="flag-card">
        <div class="flag-info">
          <div class="flag-name">${key}</div>
          <div class="flag-desc">${descriptions[key] || ''}</div>
        </div>
        <label class="toggle">
          <input type="checkbox" ${flags[key] ? 'checked' : ''} onchange="toggleFeature('${key}', this.checked)">
          <span class="slider"></span>
        </label>
      </div>
    `).join('');
  } catch (err) {
    content.innerHTML = `<div class="empty-state">Lỗi: ${err.message}</div>`;
  }
}

export async function toggleFeature(key, enabled) {
  try {
    await api(`/promotions/flags/${key}`, { method: 'PATCH', body: JSON.stringify({ enabled }) });
    loadFeatureFlags();
  } catch (err) { alert('Lỗi: ' + err.message); loadFeatureFlags(); }
}

export async function loadGrowthSettings() {
  const content = document.getElementById('settingsContent');
  if (!content) return;

  try {
    const data = await api('/crm/settings');
    const settings = data.settings || [];
    if (!settings.length) {
      content.innerHTML = '<div class="empty-state">Chưa có cài đặt nào.</div>';
      return;
    }

    content.innerHTML = settings.map(s => `
      <div class="setting-card" id="sc_${s.key}">
        <div class="setting-header">
          <div class="setting-label">${esc(s.label)}</div>
          <div class="setting-range">${s.min_value} – ${s.max_value}${esc(s.unit)}</div>
        </div>
        <div class="setting-desc">${esc(s.description)}</div>
        <div class="setting-input-row">
          <input type="number" class="setting-input" id="si_${s.key}"
            value="${s.value}" min="${s.min_value}" max="${s.max_value}"
            oninput="onSettingInput('${s.key}', ${s.value})">
          <span class="setting-unit">${esc(s.unit)}</span>
          <button class="setting-save" id="sb_${s.key}" disabled
            onclick="updateGrowthSetting('${s.key}')">Lưu</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    content.innerHTML = `<div class="empty-state">Lỗi: ${err.message}</div>`;
  }
}

export function onSettingInput(key, originalValue) {
  const input = document.getElementById('si_' + key);
  const btn = document.getElementById('sb_' + key);
  if (input && btn) btn.disabled = (parseInt(input.value) === originalValue);
}

export async function updateGrowthSetting(key) {
  const input = document.getElementById('si_' + key);
  const btn = document.getElementById('sb_' + key);
  if (!input) return;
  const value = parseInt(input.value);
  if (isNaN(value)) { alert('Giá trị không hợp lệ'); return; }
  btn.disabled = true; btn.textContent = '...';
  try {
    await api(`/crm/settings/${key}`, { method: 'PATCH', body: JSON.stringify({ value }) });
    loadGrowthSettings();
  } catch (err) { alert('Lỗi: ' + err.message); loadGrowthSettings(); }
}
