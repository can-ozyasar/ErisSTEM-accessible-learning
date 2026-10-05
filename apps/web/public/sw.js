const CACHE = "eristem-shell-v1";
self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(["/"]))));
self.addEventListener("fetch", event => { if (event.request.method === "GET" && new URL(event.request.url).origin === location.origin) event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request))); });
