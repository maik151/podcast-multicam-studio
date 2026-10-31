const CACHE_NAME = 'tx-studio-pwa-v1.1.0';
const STATIC_ASSETS = [
  '/',
  '/favicon.ico',
  '/manifest.webmanifest',
  '/tx_studio_logoNaranja.svg',
  '/tx_studio_Isotipo_naranja.svg',
  '/tx_studio_Isotipo_naranja.png',
  '/tx_studio_Isotipo_gris.svg'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => {}))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || req.url.includes('/api/') || req.url.includes('/ws')) {
    return;
  }
  event.respondWith(
    fetch(req).catch(() => caches.match(req).then((cached) => cached || caches.match('/')))
  );
});
