// DisasterAid AI - Offline Service Worker

const CACHE_NAME = 'disasteraid-cache-v1';
const ASSETS_TO_CACHE = [
    './',
    './index.html',
    './css/styles.css',
    './js/api.js',
    './js/app.js'
];

// Install Service Worker and cache core UI files
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[Service Worker] Caching app shell assets');
                return cache.addAll(ASSETS_TO_CACHE);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate and remove old caches if necessary
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cache) => {
                    if (cache !== CACHE_NAME) {
                        console.log('[Service Worker] Clearing old cache', cache);
                        return caches.delete(cache);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Intercept network requests to serve cached assets when offline
self.addEventListener('fetch', (event) => {
    // Only intercept requests for static files, not api calls
    if (event.request.url.includes('/api/')) {
        return; // Let API calls bypass service worker cache
    }

    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Return cached version if found
                if (response) {
                    return response;
                }
                
                // Otherwise fetch from network
                return fetch(event.request).catch(() => {
                    // If both fail (offline & not in cache), return index.html for navigation requests
                    if (event.request.mode === 'navigate') {
                        return caches.match('./index.html');
                    }
                });
            })
    );
});
