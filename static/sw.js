const CACHE = 'arac-avcisi-v8';
self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(['/', '/static/app.css?v=8', '/static/app.js?v=8', '/static/manifest.json', '/static/icon.svg'])));
});
self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request).then(resp => {
    const copy = resp.clone();
    caches.open(CACHE).then(cache => cache.put(event.request, copy)).catch(()=>{});
    return resp;
  }).catch(() => caches.match(event.request)));
});
