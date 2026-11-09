/* Karte: eigener Standort, Live-Standort des Besitzers, Betrachter-Ansicht */

/* ---- Betrachter: nur ansehen ---- */
["account", "admin", "apptest", "check", "plan", "record", "shared", "sheet", "compare", "tripsheet"].forEach(k => {
  const o = VIEWS[k];
  if (o) VIEWS[k] = (...a) => (isViewer() ? void (location.hash = "#/dash") : o(...a));
});

/* Betrachter: Bedienelemente zum Ändern, Hochladen, Teilen und für PDFs entfernen (api() in 01-grundlagen.js sendet für Betrachter nur Abfragen) */
const VHIDE =
  "#ren,#ksync,#eup,#edel,#etag,#eshr,#etc,#efix,#padd,#pgps,#pimp,#pbest,#shr,#esnd,#esheet,#shp,#pdfdl,#trpdf,#tredit,#trhide,#sbbtn,#serren,#chb,#offb,#stclr,#ssave,#snote,#sgrp,#gedit,#gnew,#starrow,.pdfctl,a[href*='pdf'],a[href^='#/sheet'],a[href^='#/tripsheet'],a[href^='#/compare'],a[href^='#/plan'],a[href^='#/record']";
const VTXT = /^(Fotos (zuordnen|bearbeiten|importieren|hinzufügen)|Tourblatt|PDF|Senden|Teilen|Löschen|Keine Reise|Entfernte Reisen)/;
function viewerLock() {
  if (!isViewer()) return;
  document.querySelectorAll(VHIDE).forEach(e => (e.hidden = true));
  document.querySelectorAll("#main button, #main a.btn").forEach(b => {
    if (VTXT.test(b.textContent.trim()) || /Ändern|bearbeiten|umbenennen/i.test(b.title || "")) b.hidden = true;
  });
  document.querySelectorAll("#main textarea, #main input:not([type=checkbox])").forEach(i => {
    if (!i.closest(".mapui") && i.id !== "gs") i.readOnly = true;
  });
  document.querySelectorAll("#main .st").forEach(b => (b.disabled = true));
}
new MutationObserver(() => viewerLock()).observe(document.body, {childList: true, subtree: true});

const fmtAge = s => {
  if (s < 90) return "gerade eben";
  if (s < 3600) return `vor ${Math.round(s / 60)} Min.`;
  if (s < 86400) return `vor ${Math.round(s / 3600)} Std.`;
  return `vor ${Math.round(s / 86400)} Tagen`;
};

const _mapK = VIEWS.map;
VIEWS.map = async () => {
  await _mapK();
  const box = $(".mapui");
  if (!box || !map) return;
  const myName = (ME.user && ME.user.name) || "Standort",
    m = map,
    viewer = typeof isViewer === "function" && isViewer();
  const meL = L.layerGroup().addTo(m),
    liveL = L.layerGroup().addTo(m);
  let liveMode = "off",
    lastSent = 0,
    watch = null,
    first = true,
    timer = null,
    lastLive = null;
  if (!viewer) api("/api/settings").then(c => (liveMode = c.live_mode || "off")).catch(() => {});
  box.insertAdjacentHTML(
    "afterbegin",
    `<div class="box"><button class="chip" id="mloc" title="Meinen Standort auf der Karte zeigen">⌖ ${esc(myName)}</button><button class="chip" id="mlive" style="display:none" title="Zuletzt gemeldeten Standort zeigen">📍 Live</button></div>`
  );
  const stop = () => {
    if (watch != null) navigator.geolocation.clearWatch(watch);
    watch = null;
    meL.clearLayers();
    $("#mloc") && $("#mloc").classList.remove("on");
  };
  $("#mloc").onclick = () => {
    if (watch != null) return stop();
    if (!navigator.geolocation) return alert("Dieses Gerät kann keinen Standort bestimmen.");
    $("#mloc").classList.add("on");
    first = true;
    watch = navigator.geolocation.watchPosition(
      p => {
        const ll = [p.coords.latitude, p.coords.longitude];
        meL.clearLayers();
        L.circle(ll, {radius: Math.max(p.coords.accuracy || 10, 5), color: "#1a73e8", weight: 1, fillOpacity: 0.12, interactive: false}).addTo(meL);
        L.circleMarker(ll, {radius: 8, color: "#fff", weight: 3, fillColor: "#1a73e8", fillOpacity: 1}).addTo(meL).bindPopup(`<b>${esc(myName)}</b><br>Du bist hier`).bindTooltip(esc(myName), {permanent: true, direction: "bottom", offset: [0, 8], className: "livetip me"});
        if (!viewer && liveMode === "on" && Date.now() - lastSent > 30000) {
          lastSent = Date.now();
          api("/api/live", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({lat: ll[0], lon: ll[1], acc: p.coords.accuracy, source: "manual"})}).catch(() => {});
        }
        if (first) {
          first = false;
          m.setView(ll, Math.max(m.getZoom(), 14));
        }
      },
      e => {
        stop();
        alert(e.code === 1 ? "Der Standort ist für diese Seite nicht erlaubt." : "Standort nicht verfügbar.");
      },
      {enableHighAccuracy: true, maximumAge: 10000, timeout: 20000}
    );
  };
  const showLive = p => {
    liveL.clearLayers();
    if (!p || p.lat == null) return;
    const ll = [p.lat, p.lon];
    if (p.acc && p.acc > 20) L.circle(ll, {radius: p.acc, color: "#d93025", weight: 1, fillOpacity: 0.1, interactive: false}).addTo(liveL);
    L.marker(ll, {icon: L.divIcon({className: "livepin", html: "<i></i>", iconSize: [22, 22], iconAnchor: [11, 11]}), zIndexOffset: 900})
      .addTo(liveL)
      .bindPopup(`<b>${esc(p.name || "Aktueller Standort")}</b><br>${fmtAge(p.age_s)}${p.acc ? " · ±" + p.acc + " m" : ""}`)
      .bindTooltip(fmtAge(p.age_s), {permanent: true, direction: "bottom", offset: [0, 8], className: "livetip"});
  };
  const poll = async () => {
    if (!$("#mlive")) return clearInterval(timer);
    try {
      const p = await api("/api/live");
      lastLive = p && p.lat != null ? p : null;
    } catch (e) {
      lastLive = null;
    }
    $("#mlive").style.display = lastLive ? "" : "none";
    if (lastLive && lastLive.name) $("#mlive").textContent = "📍 " + lastLive.name;
    showLive(lastLive);
  };
  $("#mlive").onclick = () => lastLive && m.setView([lastLive.lat, lastLive.lon], Math.max(m.getZoom(), 14));
  await poll();
  timer = setInterval(poll, 30000);
  m.on("unload", () => clearInterval(timer));
  if (viewer && lastLive) m.setView([lastLive.lat, lastLive.lon], 13);
};

/* ---- Verwaltung: Standort teilen ---- */
const _admK = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admK(...a);
  if ($("#livebox")) return;
  const cfg = await api("/api/settings").catch(() => ({})),
    cur = cfg.live_mode || "off",
    box = `<div class="panel" id="livebox"><h2>Standort teilen</h2>
    <p class="mut fs13">Zeigt Betrachtern (und dir selbst auf der Karte) deine zuletzt gemeldete Position. Die Android-App meldet sie während einer Aufzeichnung alle 30 Sekunden; mit „Immer“ auch die Ortungstaste auf der Karte. Es wird nur die letzte Position gespeichert, nicht der Verlauf.</p>
    <div class="row g8"><select id="livem"><option value="off">Aus</option><option value="rec">Nur während einer Aufzeichnung</option><option value="on">Immer, wenn die Karte meinen Standort zeigt</option></select><button class="btn alt" id="livex">Letzten Standort löschen</button><span id="livemsg" class="mut"></span></div></div>`,
    body = document.querySelector('.atab[data-t="handy"] .gbody');
  if (body) body.insertAdjacentHTML("beforeend", box);
  else if ($("#save")) $("#save").closest(".row").insertAdjacentHTML("beforebegin", box);
  if (!$("#livem")) return;
  if (!$("#rescue") && $("#livebox"))
    $("#livebox").insertAdjacentHTML("afterend", `<div class="panel" id="rescue"><h2>Verlorene App-Aufzeichnungen suchen</h2><p class="mut fs13">Vor Version 2.3.2 konnten Aufzeichnungen aus der Android-App im Altbestand statt in deinem Konto landen. Hier werden sie (aus den letzten 30 Tagen) in dein Konto übernommen.</p><button class="btn alt" id="rescueb">Suchen und übernehmen</button> <span id="rescuem" class="mut"></span></div>`);
  if ($("#rescueb"))
    $("#rescueb").onclick = async () => {
      $("#rescuem").textContent = "Suche …";
      try {
        const r = await api("/api/record/rescue", {method: "POST"});
        $("#rescuem").textContent = r.imported.length ? `${r.imported.length} Tour(en) übernommen: ${r.imported.map(x => x.name + " (" + x.km + " km)").join(", ")}` : "Nichts Verlorenes gefunden.";
        if (r.imported.length) loadTours().catch(() => {});
      } catch (e) {
        $("#rescuem").textContent = e.message;
      }
    };
  $("#livem").value = cur;
  $("#livem").onchange = async () => {
    try {
      await api("/api/settings", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({live_mode: $("#livem").value})});
      $("#livemsg").textContent = "Gespeichert.";
    } catch (e) {
      $("#livemsg").textContent = e.message;
    }
  };
  $("#livex").onclick = () => api("/api/live", {method: "DELETE"}).then(() => ($("#livemsg").textContent = "Gelöscht."));
};
