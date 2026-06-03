const CACHE = 'arac-avcisi-v1';
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(['/', '/static/app.css', '/static/app.js', '/static/manifest.json', '/static/icon.svg'])));
});
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
