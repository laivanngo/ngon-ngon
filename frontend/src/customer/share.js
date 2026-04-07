/**
 * Customer Share — Gửi menu cho đồng nghiệp, sao chép link
 * ===========================================================
 */
import { showToastMsg } from './social-proof.js';

export function shareMenu() {
  const text = '☕ Menu Ngon-Ngon — Giao miễn phí tận công ty! 🚀\n🧋 Trà sữa, sinh tố, cà phê, đồ ăn vặt\n📱 Xem menu: ' + location.origin + '\n📞 Hotline: 0378.148.148';
  if (navigator.share) { navigator.share({ title: 'Menu Ngon-Ngon', text, url: location.href }).catch(() => {}); }
  else { if (navigator.clipboard) navigator.clipboard.writeText(text); showToastMsg('📤', 'Đã sao chép nội dung — Dán vào Zalo để gửi!'); }
}

export function copyLink() {
  if (navigator.clipboard) navigator.clipboard.writeText(location.href);
  showToastMsg('🔗', 'Đã sao chép link menu!');
}
