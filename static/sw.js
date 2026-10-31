const CACHE_NAME = "pf-v1";
const ASSETS = [
    "/",
    "/static/index.html",
    "/static/app.js",
    "/static/style.css",
    "/static/skills-panel.css",
    "/static/skills-panel.js"
];

self.addEventListener("install", (e) => {
    e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)));
    self.skipWaiting();
});

self.addEventListener("activate", (e) => {
    e.waitUntil(
        caches.keys().then(keys => Promise.all(
            keys.map(k => k !== CACHE_NAME && caches.delete(k))
        ))
    );
    self.clients.claim();
});

self.addEventListener("fetch", (e) => {
    const url = new URL(e.request.url);
    // API 和 output 走网络，不缓存
    if (url.pathname.startsWith("/api") || url.pathname.startsWith("/output")) {
        return;
    }
    e.respondWith(
        caches.match(e.request).then(res => {
            return res || fetch(e.request).then(response => {
                return caches.open(CACHE_NAME).then(cache => {
                    cache.put(e.request, response.clone());
                    return response;
                });
            });
        })
    );
});