const CACHE = "eristem-shell-v2";

self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()),
));

// HTML dosyası ve hash'li JavaScript paketleri farklı sürümlerde birlikte
// önbelleğe alınamaz; aksi hâlde eski HTML boş ekrana yol açabilir.
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== location.origin) return;
  event.respondWith(fetch(event.request));
});
