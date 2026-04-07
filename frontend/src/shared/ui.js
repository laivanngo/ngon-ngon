/**
 * Shared UI — Modal, Toast, và Security helpers
 * ================================================
 * Quản lý modal overlay dùng chung cho products, categories, toppings, cross-sell.
 * escapeHtml() — chống XSS khi render user content vào innerHTML.
 */

/**
 * Escape HTML special characters — chống XSS khi dùng innerHTML.
 * Dùng cho mọi user-generated content trước khi render.
 */
export function escapeHtml(str) {
  if (typeof str !== 'string') return str ?? '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/** Trạng thái modal hiện tại */
let _modalMode = null;
let _editingId = null;

export function getModalMode() { return _modalMode; }
export function setModalMode(m) { _modalMode = m; }
export function getEditingId() { return _editingId; }
export function setEditingId(id) { _editingId = id; }

/**
 * Mở modal dialog với title, body HTML, và callback khi bấm Lưu.
 */
export function openModal(title, bodyHtml, saveCallback) {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML = bodyHtml;
  document.getElementById('modalSave').onclick = saveCallback;
  document.getElementById('modalOverlay').classList.add('show');

  // Focus first input after animation
  setTimeout(() => {
    const firstInput = document.querySelector(
      '#modalBody input:not([type=checkbox]),#modalBody select'
    );
    if (firstInput) firstInput.focus();
  }, 100);
}

/**
 * Đóng modal dialog.
 */
export function closeModal() {
  document.getElementById('modalOverlay').classList.remove('show');
  _modalMode = null;
  _editingId = null;
}

/**
 * Đóng modal khi nhấn Escape.
 * Gọi 1 lần khi init.
 */
export function initModalEscapeKey() {
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && document.getElementById('modalOverlay').classList.contains('show')) {
      closeModal();
    }
  });
}
