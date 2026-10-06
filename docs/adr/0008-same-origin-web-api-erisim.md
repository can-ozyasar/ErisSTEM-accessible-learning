# ADR 0008: Web uygulaması API'ye aynı origin üzerinden erişir / Same-origin web-to-API access

Durum: Kabul edildi.

Tarayıcı, API'ye `http://localhost:8000` gibi makineye bağlı bir adresle doğrudan bağlanmaz. Web container'ındaki nginx, `/api/` isteklerini yalnız iç ağdaki API container'ına yönlendirir. Yalnız web container'ı dış ağda ve yayımlanmış portta bulunur; API, veritabanı ve worker özel ağda kalır.

PWA service worker'ı HTML kabuğunu cache-first stratejiyle saklamaz. Hash'li JavaScript paketleri dağıtımda değiştiğinde eski `index.html` yeni sürümde olmayan pakete işaret ederek boş ekran üretebilir. Yeni worker eski cache'leri temizler ve aynı-origin GET isteklerini ağdan alır.

Status: Accepted.

The browser never reaches the API through a machine-bound address such as `http://localhost:8000`. Nginx in the web container proxies `/api/` requests only to the API container on the private network. Only the web container is on the edge network and published port; the API, database, and worker remain private.

The PWA service worker does not cache the HTML shell with a cache-first strategy. When hashed JavaScript bundles change during deployment, an old `index.html` can point to a missing bundle and create a blank screen. The new worker clears old caches and fetches same-origin GET requests from the network.
