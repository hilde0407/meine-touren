/* =====================  Offline-Nutzung: Hinweisband + „Für Offline vorbereiten“  ===================== */
(function () {
  const bar = document.createElement("div");
  bar.id = "offbar";
  bar.style.cssText = "display:none;position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#b45309;color:#fff;text-align:center;padding:8px 12px;font:600 14px system-ui";
  bar.textContent = "Offline – es werden die zuletzt geladenen Daten gezeigt (Änderungen sind nicht möglich).";
  document.body.appendChild(bar);
  const nat = () => { try { return !!(window.MTApp && MTApp.offlineServed && MTApp.offlineServed()); } catch (e) { return false; } };
  const upd = () => (bar.style.display = navigator.onLine && !nat() ? "none" : "block");
  if (window.MTApp && MTApp.offlineServed) setInterval(upd, 4000);      // App: Hinweis, solange der Server nicht erreichbar ist
  addEventListener("online", upd);
  addEventListener("offline", upd);
  upd();
  // Beim Abmelden die zwischengespeicherten Daten löschen (gemeinsam genutzte Geräte)
  document.addEventListener("click", e => {
    if (e.target && e.target.id === "umo") {
      if (window.caches) ["mt-api-v1", "mt-pics-v1"].forEach(n => caches.delete(n));
      try { if (window.MTApp && MTApp.clearOffline) MTApp.clearOffline(); } catch (x) {}
    }
  }, true);
})();

const tileXY = (lat, lng, z) => {
  const n = 2 ** z, r = (lat * Math.PI) / 180;
  return [Math.floor(((lng + 180) / 360) * n), Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n)];
};
async function prepareOffline(onProgress, nTours = 8, all = false) {
  if (all) {                                        // alle Touren: Daten und Strecken (ohne Fotos und Kacheln)
    const rest = TOURS.slice(nTours);
    let k = 0;
    for (let i = 0; i < rest.length; i += 4) {
      onProgress(`Daten von Tour ${Math.min(i + 4, rest.length)} von ${rest.length}`);
      await Promise.all(rest.slice(i, i + 4).map(t => Promise.all([api(`/api/tours/${t.id}`), api(`/api/tours/${t.id}/coords`)]).then(() => k++).catch(() => 0)));
    }
    var allDone = k;
  }
  const tours = TOURS.slice(0, nTours);
  let tiles = new Set(), done = 0;
  for (const t of tours) {
    onProgress(`Tour ${++done} von ${tours.length}: ${t.name}`);
    try {
      const c = await api(`/api/tours/${t.id}/coords`);
      const pts = c.filter((_, i) => i % Math.max(1, Math.floor(c.length / 60)) === 0);
      for (const z of [11, 13, 14]) pts.forEach(p => { const [x, y] = tileXY(p[0], p[1], z); for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) tiles.add(`${z}/${x + dx}/${y + dy}`); });
      const ph = await api(`/api/photos?tour_id=${t.id}&limit=400`);
      for (const p of ph.slice(0, 12)) await fetch(`/pic/${p.id}?size=500`).then(r => r.blob()).catch(() => 0);
    } catch (e) {}
  }
  const list = [...tiles].slice(0, 1200);
  for (let i = 0; i < list.length; i += 8) {
    onProgress(`Kartenkacheln ${Math.min(i + 8, list.length)} von ${list.length}`);
    await Promise.all(list.slice(i, i + 8).map(k => fetch(TBASE + "tiles/osm/" + k).then(r => r.blob()).catch(() => 0)));
  }
  await Promise.all(["/api/tours", "/api/goals"].map(u => fetch(u).catch(() => 0)));
  return {tours: tours.length + (allDone || 0), tiles: list.length};
}
const _adminO = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adminO(...a);
  if ($("#offprep") || !$("#main")) return;
  $("#main").insertAdjacentHTML("beforeend", `<div class="panel gap" id="offprep"><h2>Offline-Nutzung</h2>
   <p class="mut" style="font-size:14px">Lädt die letzten 8 Touren mit Strecke, einigen Fotos und den Kartenkacheln auf dieses Gerät. Danach lassen sie sich auch ohne Verbindung ansehen (z. B. unterwegs ohne Netz). Die App-Seiten werden automatisch zwischengespeichert; Daten und Karten, die du schon angesehen hast, ebenfalls.</p>
   <div class="row"><button class="btn alt" id="offb">Für Offline vorbereiten</button><button class="btn alt" id="offall">Alle Touren offline (Daten und Strecken)</button><span id="offm" class="mut"></span></div></div>`);
  const go = async all => {
    const b = $("#offb"), b2 = $("#offall");
    b.disabled = b2.disabled = true;
    try {
      const r = await prepareOffline(m => ($("#offm").textContent = m), 8, all);
      $("#offm").textContent = `Fertig: ${r.tours} Touren und ${r.tiles} Kartenkacheln stehen offline bereit.`;
    } catch (e) {
      $("#offm").textContent = "Fehler: " + e.message;
    }
    b.disabled = b2.disabled = false;
  };
  $("#offb").onclick = () => go(false);
  $("#offall").onclick = () => go(true);
};
