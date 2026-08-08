/* Service worker — the last thing standing between a manifest and an app you
 * can actually install.
 *
 * Deliberately network-first for anything that can change. A self-hosted app
 * updates by pulling a new container, and the classic service-worker failure
 * is that it keeps serving yesterday's bundle afterwards — the user pulls the
 * fix, reloads, and nothing happens. That failure is invisible from the
 * outside and infuriating from the inside, so this caches for offline and
 * never for speed.
 *
 * Three rules:
 *   - /api and /images  never touched. Your collection is not cacheable.
 *   - hashed build files cache-first, because index-a1b2c3.js can only ever
 *     mean one thing.
 *   - everything else network-first, cache only as the offline fallback.
 */

// Bump when a precached file changes. The favicon lives in the shell cache,
// so a new icon with the old version would keep serving the old one.
const VERSION = "v2";
const SHELL = `loot-shell-${VERSION}`;
const RUNTIME = `loot-runtime-${VERSION}`;

// Enough to draw something rather than the browser's offline page.
const PRECACHE = ["/", "/manifest.json", "/assets/favicon.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(SHELL)
      .then((c) => c.addAll(PRECACHE))
      // A missing file must not wedge the install — a broken worker is worse
      // than no worker.
      .catch(() => {})
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((k) => k !== SHELL && k !== RUNTIME).map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

const isBuildAsset = (url) =>
  url.pathname.startsWith("/assets/") && /-[A-Za-z0-9_]{8,}\.(js|css|woff2?)$/.test(url.pathname);

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  // The collection itself and every uploaded photo: always live.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/images/")) return;

  if (isBuildAsset(url)) {
    e.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((res) => {
            const copy = res.clone();
            caches.open(RUNTIME).then((c) => c.put(request, copy));
            return res;
          })
      )
    );
    return;
  }

  // Everything else — the page itself included — comes off the network when
  // there is one, so an upgrade lands the moment it's pulled.
  e.respondWith(
    fetch(request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(RUNTIME).then((c) => c.put(request, copy));
        }
        return res;
      })
      .catch(() =>
        caches
          .match(request)
          .then((hit) => hit || (request.mode === "navigate" ? caches.match("/") : undefined))
      )
  );
});
