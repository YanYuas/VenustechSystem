// ============================================================
// PWA Service Worker（最小实现）
// 策略：静态资源 cache-first（带版本号），API 永远 network-only
// —— 数据主权：待办/行程数据绝不缓存陈旧版本误导人
// ============================================================
const CACHE = "qm-star-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.pathname.startsWith("/api/")) {
    return; // API 永远直连，不缓存
  }
  event.respondWith(
    caches.match(event.request).then(
      (hit) =>
        hit ||
        fetch(event.request).then((resp) => {
          // 只缓存同源静态资源
          if (url.origin === self.location.origin && resp.ok) {
            const clone = resp.clone();
            caches.open(CACHE).then((c) => c.put(event.request, clone));
          }
          return resp;
        }),
    ),
  );
});
