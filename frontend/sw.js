/**
 * Ngon-Ngon Service Worker
 * ========================
 * Caching strategy:
 *
 * 1. Static files (CSS, JS, images): Cache-First
 *    → Load từ cache ngay lập tức, update cache ở background
 *    → User thấy trang ngay, không chờ network
 *
 * 2. API /menu: Stale-While-Revalidate
 *    → Trả cache ngay + fetch mới ở background → update cache
 *    → Menu ít đổi, cached data đủ tốt
 *
 * 3. API /orders: Network-First
 *    → Luôn gọi server (data realtime), fallback cache nếu offline
 *
 * 4. Offline fallback: nếu hoàn toàn offline, show cached page
 *
 * WHY Service Worker quan trọng cho app này:
 * - KCN thường sóng 4G yếu → cache giúp load nhanh hơn
 * - Worker giờ nghỉ trưa mở app đặt hàng → cần instant load
 * - PWA install → chạy offline-capable
 */

// FIX B4: Cache version includes deploy timestamp.
// Bump this on every deploy to force cache invalidation.
// Without this, users can be stuck on old cached version indefinitely.
const CACHE_VERSION = 'nn-v3.0-20260330';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;

// Files to pre-cache on install
// v2 FIX: minimal pre-cache list. Other files use runtime caching.
// WHY: hardcoded list breaks when files are added/renamed.
// Only cache the absolute essentials for offline shell.
const PRE_CACHE = [
  '/',
  '/index.html',
];

// =============================================================================
// INSTALL — Pre-cache critical files
// =============================================================================
self.addEventListener('install', event => {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => {
      return cache.addAll(PRE_CACHE).catch(err => {
        // Không fail install nếu 1 file lỗi (VD: dev server chưa start)
        console.warn('[SW] Pre-cache partial failure:', err);
      });
    })
  );
  // Activate ngay, không chờ SW cũ đóng
  self.skipWaiting();
});

// =============================================================================
// ACTIVATE — Xóa cache cũ khi version mới
// =============================================================================
self.addEventListener('activate', event => {
  console.log('[SW] Activating...');
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== STATIC_CACHE && key !== API_CACHE)
          .map(key => {
            console.log('[SW] Deleting old cache:', key);
            return caches.delete(key);
          })
      )
    )
  );
  // Claim tất cả clients ngay (không cần refresh page)
  self.clients.claim();
});

// =============================================================================
// FETCH — Route requests to appropriate strategy
// =============================================================================
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Chỉ handle GET requests (POST orders, etc. → pass through)
  if (event.request.method !== 'GET') return;

  // --- API: /api/v1/menu → Stale-While-Revalidate ---
  if (url.pathname.startsWith('/api/v1/menu') || url.pathname.startsWith('/api/v1/toppings')) {
    event.respondWith(staleWhileRevalidate(event.request, API_CACHE));
    return;
  }

  // --- API: /api/v1/time-deals → Stale-While-Revalidate ---
  if (url.pathname.startsWith('/api/v1/time-deals')) {
    event.respondWith(staleWhileRevalidate(event.request, API_CACHE));
    return;
  }

  // --- API: other (orders, admin) → Network-First ---
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(event.request, API_CACHE));
    return;
  }

  // --- Static files → Cache-First ---
  event.respondWith(cacheFirst(event.request, STATIC_CACHE));
});

// =============================================================================
// STRATEGIES
// =============================================================================

/**
 * Cache-First: return cache immediately, update in background
 * Best for: static files (JS, CSS, images) that rarely change
 */
async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  if (cached) {
    // Update cache in background (don't await)
    fetch(request).then(response => {
      if (response.ok) cache.put(request, response);
    }).catch(() => {});
    return cached;
  }

  // Not in cache → fetch from network
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    // Offline + not in cache → return offline page if HTML request
    if (request.headers.get('Accept')?.includes('text/html')) {
      const fallback = await cache.match('/index.html');
      if (fallback) return fallback;
    }
    return new Response('Offline', { status: 503 });
  }
}

/**
 * Stale-While-Revalidate: return cache + fetch update simultaneously
 * Best for: API data that can be slightly stale (menu, toppings)
 */
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  // Fetch fresh data in background
  const fetchPromise = fetch(request).then(response => {
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  }).catch(() => null);

  // Return cached if available, otherwise wait for fetch
  return cached || (await fetchPromise) || new Response('{"error":"offline"}', {
    status: 503,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * Network-First: always try network, fall back to cache
 * Best for: data that should be fresh (orders, admin)
 */
async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    return cached || new Response('{"error":"offline"}', {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
