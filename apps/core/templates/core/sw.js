/*
 * sw.js — The service worker. Rendered by apps/core/views.service_worker.
 *
 * Static files are cache-first (their names are versioned by the static
 * storage in production). Pages are network-first: the latest copy when
 * there's signal, the last copy seen when there isn't, and the offline
 * page when the page was never opened. Nothing that changes data is cached.
 */
const VERSION = "v1";
const STATIC_CACHE = "static-" + VERSION;
const PAGE_CACHE = "pages-" + VERSION;
const PRECACHE = {{ precache|safe }};

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function (cache) {
      return cache.addAll(PRECACHE);
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (key) {
        return key !== STATIC_CACHE && key !== PAGE_CACHE;
      }).map(function (key) {
        return caches.delete(key);
      }));
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener("fetch", function (event) {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then(function (hit) {
        return hit || fetch(request).then(function (response) {
          const copy = response.clone();
          caches.open(STATIC_CACHE).then(function (cache) { cache.put(request, copy); });
          return response;
        });
      })
    );
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).then(function (response) {
        if (response.ok) {
          const copy = response.clone();
          caches.open(PAGE_CACHE).then(function (cache) { cache.put(request, copy); });
        }
        return response;
      }).catch(function () {
        return caches.match(request).then(function (hit) {
          return hit || caches.match("/offline/");
        });
      })
    );
  }
});
