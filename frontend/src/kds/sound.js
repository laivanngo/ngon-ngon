/**
 * KDS Sound & System — Âm thanh, rung, giữ màn hình sáng
 * =========================================================
 * WHY vibration: điện thoại trong túi/trên bàn, nhân viên bếp không nhìn màn hình.
 * WHY wake lock: KDS treo trong bếp → màn hình phải luôn sáng.
 */

let soundOn = true;

/** Phát âm thanh khi có đơn mới */
export function playSound() {
  if (!soundOn) return;
  const audio = document.getElementById('notifSound');
  if (audio) { audio.currentTime = 0; audio.play().catch(() => {}); }
}

/** Rung mạnh — pattern dài hơn admin vì bếp ồn */
export function vibrate() {
  if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 200]);
}

/** Bật/tắt âm thanh */
export function toggleSound() {
  soundOn = !soundOn;
  const btn = document.getElementById('soundBtn');
  btn.textContent = soundOn ? '🔔' : '🔕';
  btn.classList.toggle('off', !soundOn);
  try { localStorage.setItem('nn_kds_sound', soundOn ? '1' : '0'); } catch (e) {}
  if (soundOn) playSound();
}

/** Khôi phục preference âm thanh */
export function restoreSoundPreference() {
  try {
    if (localStorage.getItem('nn_kds_sound') === '0') {
      soundOn = false;
      const b = document.getElementById('soundBtn');
      if (b) { b.textContent = '🔕'; b.classList.add('off'); }
    }
  } catch (e) {}
}

/**
 * Wake Lock — giữ màn hình sáng khi KDS đang chạy.
 * WHY: KDS treo trong bếp → tắt màn hình = bỏ lỡ đơn.
 * Chỉ hoạt động trên HTTPS + supported browsers (Chrome, Edge).
 */
export async function requestWakeLock() {
  try {
    if ('wakeLock' in navigator) {
      await navigator.wakeLock.request('screen');
      console.log('[KDS] Wake lock acquired — screen will stay on');
    }
  } catch (e) {
    console.warn('[KDS] Wake lock not available:', e.message);
  }
}
