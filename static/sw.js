const CACHE_NAME = 'promptforge-v1';
const ASSETS = [
  '/',
  '/static/index.html'
];

// 安装时缓存核心文件
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
});

// 拦截网络请求（如果缓存有，就优先走缓存，让打开速度极快）
self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((res) => {
      return res || fetch(e.request);
    })
  );
});