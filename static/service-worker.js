const CACHE_NAME = 'airline-reservation-cache-v1';
const urlsToCache = [
  '/',
  '/static/styles.css',
  '/static/icons/logo-192x192.png',
  '/static/icons/logo-512x512.png',
  // Include other assets you want to cache
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        return response || fetch(event.request);
      })
  );
});
