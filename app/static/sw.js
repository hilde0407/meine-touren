// Service Worker: App-Dateien offline verfügbar; Daten (/api), Kartenkacheln und kleine Fotos werden bei Verbindung
// frisch geladen und zuletzt Gesehenes dient als Rückfall, wenn keine Verbindung besteht.
const V = "mt-v61", API = "mt-api-v1", TILES = "mt-tiles-v1", PICS = "mt-pics-v1";
const KEEP = [V, API, TILES, PICS];
const NOCACHE = /^\/api\/(jobs|update|selftest|health|login|logout|setup|me\/password|clock-check\/ignore)/;
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => !KEEP.includes(x)).map(x => caches.delete(x)))).then(() => clients.claim())); });
async function trim(name, max) {
  const c = await caches.open(name), k = await c.keys();
  for (let i = 0; i < k.length - max; i++) await c.delete(k[i]);
}
function netFirst(req, cacheName, max) {
  return fetch(req).then(r => {
    if (r.ok) { const c = r.clone(); caches.open(cacheName).then(ch => ch.put(req, c)).then(() => max && trim(cacheName, max)); }
    return r;
  }).catch(() => caches.match(req).then(m => m || new Response('{"detail":"offline"}', {status: 503, headers: {"content-type": "application/json"}})));
}
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  const p = u.pathname;
  if (p.startsWith("/api/")) { if (NOCACHE.test(p) || e.request.headers.has("range")) return; e.respondWith(netFirst(e.request, API, 600)); return; }
  if (p.includes("/tiles/")) {   // Kacheln ändern sich praktisch nie: zuerst aus dem Speicher
    e.respondWith(caches.match(e.request).then(m => m || fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(TILES).then(ch => ch.put(e.request, c)).then(() => trim(TILES, 1500)); } return r; })));
    return;
  }
  if (p.startsWith("/pic/") || p.startsWith("/spic/")) { const s = +(u.searchParams.get("size") || 0); if (s && s <= 600) e.respondWith(netFirst(e.request, PICS, 400)); return; }
  if (p.startsWith("/photo/") || p.startsWith("/sphoto/")) return;
  e.respondWith(fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(V).then(ch => ch.put(e.request, c)); } return r; }).catch(() => caches.match(e.request).then(m => m || caches.match(u.pathname.endsWith("/") ? e.request : new Request(u.origin + u.pathname.replace(/[^/]*$/, ""))))));
});
