/**
 * Customer Time Deals — Flash deals theo giờ (sáng/trưa/chiều/tối)
 * ==================================================================
 */

export function updTimeDeal() {
  const h = new Date().getHours();
  const L = document.getElementById('tdLabel'), T = document.getElementById('tdTitle'), Ti = document.getElementById('tdTimer');
  if (h >= 6 && h < 10) { L.textContent = '☀️ Deal Buổi Sáng'; T.textContent = 'Cà Phê + Bánh Flan chỉ 25k!'; updCD(Ti, 10); }
  else if (h >= 10 && h < 14) { L.textContent = '🔥 Deal Buổi Trưa'; T.textContent = 'Combo Trưa Tiết Kiệm — Giảm đến 20%'; updCD(Ti, 14); }
  else if (h >= 14 && h < 17) { L.textContent = '🧊 Deal Chiều Mát'; T.textContent = 'Giải khát buổi chiều — Trà sữa từ 20k'; updCD(Ti, 17); }
  else { L.textContent = '🌙 Menu Tối'; T.textContent = 'Đặt sẵn cho ngày mai — Giao từ 7h sáng'; Ti.style.display = 'none'; }
}

function updCD(el, endH) {
  const n = new Date(), e = new Date(n); e.setHours(endH, 0, 0, 0);
  if (e <= n) { el.style.display = 'none'; return; }
  const d = e - n, hh = Math.floor(d / 36e5), mm = Math.floor(d % 36e5 / 6e4), ss = Math.floor(d % 6e4 / 1e3);
  el.textContent = `⏰ Còn ${hh}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
  el.style.display = 'inline-flex';
}
