/**
 * ============================================================================
 * TYRESVISION PWA SERVICE WORKER
 * Provides robust offline fallback experience and asset caching.
 * ============================================================================
 * 
 * TO UPDATE CACHE:
 * Simply increment the CACHE_NAME version below (e.g. 'tyresvision-offline-v2').
 * The service worker will automatically purge old caches and install fresh assets.
 */

const CACHE_NAME = 'tyresvision-offline-v2';

// Minimal, essential offline resources to pre-cache on install
const PRECACHE_RESOURCES = [
  '/offline',
  '/static/assets/images/offline-bg.png',
  '/static/assets/images/logo/tyresvision-horizontal-clean.png',
  '/static/assets/images/logo/tyresvision-icon-symbol.png',
  '/static/assets/images/logo/favicon.ico',
  '/manifest.json'
];

// Paths that should NEVER be cached or handled offline (security & state safety)
const SENSITIVE_PATH_PREFIXES = [
  '/api/',
  '/visionadmin/',
  '/tcsadmin/',
  '/cart',
  '/checkout',
  '/payment',
  '/login',
  '/logout',
  '/reset-password',
  '/forgot-password',
  '/auth'
];

/**
 * 1. INSTALL EVENT
 * Pre-caches the offline fallback page and its background image.
 */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        // Cache offline fallback assets gracefully
        return cache.addAll(PRECACHE_RESOURCES);
      })
      .then(() => {
        // Immediately activate updated service worker without waiting
        return self.skipWaiting();
      })
      .catch((error) => {
        console.warn('[ServiceWorker] Pre-cache failed during install:', error);
      })
  );
});

/**
 * 2. ACTIVATE EVENT
 * Cleans up stale caches from previous versions and takes immediate control.
 */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((existingCache) => {
            if (existingCache !== CACHE_NAME) {
              console.log('[ServiceWorker] Removing stale cache:', existingCache);
              return caches.delete(existingCache);
            }
          })
        );
      })
      .then(() => {
        // Take control of all open client tabs immediately
        return self.clients.claim();
      })
  );
});

/**
 * 3. FETCH EVENT
 * Strategy:
 * - For Navigation (HTML page loads / refreshes):
 *   Network First -> Fallback to cached '/offline' if offline or network drops.
 * - For Sensitive routes / APIs:
 *   Network Only (never cache private or financial data).
 * - For Cached Assets (offline-bg.png):
 *   Cache First with Network Fallback.
 */
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Ignore non-GET requests (e.g. POST, PUT, DELETE) and browser extensions
  if (request.method !== 'GET' || !url.protocol.startsWith('http')) {
    return;
  }

  // Bypass service worker for sensitive API or authenticated routes
  const isSensitive = SENSITIVE_PATH_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
  if (isSensitive) {
    return;
  }

  // A. Navigation Requests (Page browsing, clicking links, refreshing pages)
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .catch(() => {
          // If device is offline or network fails, serve the custom offline fallback page
          return caches.match('/offline')
            .then((offlineResponse) => {
              if (offlineResponse) {
                return offlineResponse;
              }
              // Fallback plain text if cache was somehow cleared
              return new Response(
                '<h1>Offline</h1><p>Please check your internet connection.</p>',
                {
                  headers: { 'Content-Type': 'text/html; charset=utf-8' },
                  status: 503,
                  statusText: 'Service Unavailable'
                }
              );
            });
        })
    );
    return;
  }

  // B. Pre-cached Static Assets (e.g. offline-bg.png, manifest)
  if (PRECACHE_RESOURCES.includes(url.pathname)) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        return cachedResponse || fetch(request);
      })
    );
    return;
  }

  // Default behavior for other resources: normal network fetch
});
