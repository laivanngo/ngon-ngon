/**
 * Customer Social Proof — Toast notifications & social proof rotation
 * =====================================================================
 */
import { SP_MSGS, TOASTS } from './state.js';

let spIdx = 0;
let toastIdx = 0;

/** Rotate social proof text */
export function rotSP() {
  spIdx = (spIdx + 1) % SP_MSGS.length;
  const el = document.getElementById('spText');
  el.style.opacity = '0';
  setTimeout(() => { el.textContent = SP_MSGS[spIdx]; el.style.opacity = '1'; }, 250);
}

/** Show a preset toast from TOASTS array */
export function showToast() {
  const t = TOASTS[toastIdx % TOASTS.length];
  showToastMsg(t.e, t.m);
  toastIdx++;
}

/** Show a toast with custom emoji and message */
export function showToastMsg(emoji, msg) {
  const el = document.getElementById('toast');
  document.getElementById('toastEm').textContent = emoji;
  document.getElementById('toastMsg').textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 4000);
}
