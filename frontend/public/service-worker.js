// Minimal service worker — exists so Dayo is installable on Android Chrome.
// Strategy: pass-through for everything except top-level navigations, which
// fall back to a cached copy of index.html if the network is unreachable.

const CACHE = 'dayo-shell-v1';
const SHELL = '/index.html';

self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || req.mode !== 'navigate') return;

  event.respondWith((async () => {
    try {
      const fresh = await fetch(req);
      const cache = await caches.open(CACHE);
      cache.put(SHELL, fresh.clone()).catch(() => {});
      return fresh;
    } catch (_) {
      const cached = await caches.match(SHELL);
      if (cached) return cached;
      throw _;
    }
  })());
});
