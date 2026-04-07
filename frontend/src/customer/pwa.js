/**
 * Customer PWA — Add to Home Screen (A2HS) install prompt
 * =========================================================
 * Shows modal on first visit, then mini banner on subsequent visits.
 * Uses beforeinstallprompt for Chrome/Edge, manual instructions for Safari.
 */
import { showToastMsg } from './social-proof.js';

let deferredPrompt = null;

export function initPWA() {
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches; // legacy
  let modalSeen = false; try { modalSeen = !!localStorage.getItem('nn_a2hs_modal'); } catch (e) {}
  let bannerClosed = false; try { bannerClosed = !!localStorage.getItem('nn_a2hs_closed'); } catch (e) {}
  let alreadyInstalled = false; try { alreadyInstalled = !!localStorage.getItem('nn_pwa_installed'); } catch (e) {}

  window.addEventListener('appinstalled', () => { // legacy
    try { localStorage.setItem('nn_pwa_installed', '1'); } catch (e) {}
    alreadyInstalled = true;
    document.getElementById('a2hsModal').classList.remove('show');
    document.getElementById('a2hsBanner').classList.remove('show');
    showToastMsg('✅', 'Đã cài Ngon-Ngon! Tìm icon trên màn hình chính 🎉');
  });
  window.addEventListener('beforeinstallprompt', e => { deferredPrompt = e; }); // legacy

  if (!isStandalone && !alreadyInstalled && !modalSeen) {
    setTimeout(() => document.getElementById('a2hsModal').classList.add('show'), 1500);
  } else if (!isStandalone && !alreadyInstalled && modalSeen && !bannerClosed) {
    document.getElementById('a2hsBanner').classList.add('show');
  }

  document.getElementById('a2hsInstallBtn').addEventListener('click', () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(choice => {
        deferredPrompt = null;
        document.getElementById('a2hsModal').classList.remove('show');
        try { localStorage.setItem('nn_a2hs_modal', '1'); localStorage.setItem('nn_a2hs_closed', '1'); localStorage.setItem('nn_pwa_installed', '1'); } catch (e) {}
        if (choice.outcome === 'accepted') showToastMsg('✅', 'Đã cài Ngon-Ngon! 🎉');
      });
    } else {
      document.getElementById('a2hsModal').classList.remove('show');
      try { localStorage.setItem('nn_a2hs_modal', '1'); } catch (e) {}
      const isAndroid = /android/i.test(navigator.userAgent);
      showToastMsg('📲', isAndroid ? 'Bấm ⋮ (3 chấm) → "Thêm vào MH chính" → "Thêm"' : 'Bấm 📤 Chia sẻ → "Thêm vào MH chính"');
      document.getElementById('a2hsBanner').classList.add('show');
    }
  });

  document.getElementById('a2hsLaterBtn').addEventListener('click', () => {
    document.getElementById('a2hsModal').classList.remove('show');
    try { localStorage.setItem('nn_a2hs_modal', '1'); } catch (e) {}
    document.getElementById('a2hsBanner').classList.add('show');
  });

  document.getElementById('a2hsBanner').addEventListener('click', () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(choice => {
        deferredPrompt = null;
        document.getElementById('a2hsBanner').classList.remove('show');
        try { localStorage.setItem('nn_a2hs_closed', '1'); } catch (e) {}
        if (choice.outcome === 'accepted') showToastMsg('✅', 'Đã cài Ngon-Ngon! 🎉');
      });
    } else {
      showToastMsg('📲', /android/i.test(navigator.userAgent) ? 'Bấm ⋮ → "Thêm vào MH chính"' : 'Bấm 📤 → "Thêm vào MH chính"');
    }
  });

  document.getElementById('a2hsClose').addEventListener('click', e => {
    e.stopPropagation();
    document.getElementById('a2hsBanner').classList.remove('show');
    try { localStorage.setItem('nn_a2hs_closed', '1'); } catch (e2) {}
  });
}
