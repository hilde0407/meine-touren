/* =====================  3.33.0 Reisen als anpassbare Seiten  =====================
   Reise-Detailseite (#/trip/<id>, Layout-Schlüssel „reise“) und Reisen-Übersicht (#/trips, Schlüssel „reisen“) sind jetzt wie Tourseite, Übersicht und Statistik anpassbar (Engine 49-seitenlayout.js,
   Ansichten 54, Vorlagen 55, Bausteine 61). Das Layout gilt für alle Reisen gleich (je Benutzer gespeichert, nicht je Reise).
   Kapselung statt Neuschreibung: Die bisherigen Ansichten bauen sich wie vorher auf; collView() (10-auswertung.js) markiert die Abschnitte mit data-rs und ruft für eine Reise rsFrame() auf, noch bevor
   die Karte gezeichnet wird. rsFrame() steckt jeden Abschnitt unverändert (samt Kennungen #cm, #cph, #coff, #cofm …) in eine einklappbare Karte im Format von tlCard und übergibt sie der Engine (slPlace).
   Die Reisen-Übersicht ordnet nach dem Aufbau (rnFrame) ihre vier Abschnitte neu: Mehrtagestouren, Reisen, Alben und Tags, Entfernte Reisen.
   Karte: Leaflet braucht einen sichtbaren Container. Wird die Karte verschoben, ein- oder ausgeblendet, zu- oder aufgeklappt oder ändert sich ihre Breite, passt ein ResizeObserver die Größe an (invalidateSize)
   und rahmt die Strecken neu ein (map._cvFit aus collView()): zwingend, wenn das beim Aufbau nicht möglich war (map._cvStale), sonst solange der Benutzer die Karte nicht selbst bewegt hat (map._cvUser).
   Router-Schutz: Beide Ansichten prüfen nach jedem await das Token window._rt (3.17.0), eine inzwischen verlassene Seite zeichnet nichts mehr. */
const RS_ICON = {kennzahlen: "met", stat: "trend", flug: "pin", karte: "map", fotos: "cam", touren: "note"};
const RN_ICON = {serien: "trend", reisen: "map", alben: "cam", entfernt: "note"};
function rsBadge(id, html) {
  const c = document.getElementById("rsc-" + id);
  if (c && typeof tlSetBadge === "function") tlSetBadge(c, html);
}
/* Hat der Benutzer die Karte selbst bewegt (ziehen, zoomen, Tasten), bleibt sein Ausschnitt; sonst rahmt die Seite die Strecken nach jeder Größenänderung neu ein */
function rsMapBind(m) {
  const c = m.getContainer(), mark = () => (m._cvUser = true);
  ["pointerdown", "wheel", "keydown"].forEach(ev => c.addEventListener(ev, mark, {passive: true}));
}
/* Größe der Karte nachführen (siehe oben) */
function rsWatchMap() {
  const el = document.getElementById("cm");
  if (!el || typeof ResizeObserver !== "function") return;
  let k0 = "", raf = 0;
  new ResizeObserver(es => {
    const r = es[0].contentRect, k = Math.round(r.width) + "x" + Math.round(r.height);
    if (k === k0) return;
    k0 = k;
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      if (!el.isConnected || typeof map === "undefined" || !map || !map.invalidateSize || map.getContainer() !== el) return;                // „map“ ist eine globale Variable (01-grundlagen.js)
      if (!el.clientWidth) return;
      map.invalidateSize({animate: false});
      if (map._cvFit && (map._cvStale || !map._cvUser)) {
        map._cvStale = false;
        map._cvFit();
      }
    });
  }).observe(el);
}
/* Reise-Detailseite: Abschnitte aus collView() in Karten stecken und einordnen (läuft synchron, vor dem Zeichnen der Karte).
   3.63.0: Dasselbe für die Seite einer Mehrtagestour (tr.serie, Familie „serie“, Wurzel #srx, eigene Zustandsschlüssel se_…, Liste heißt „Etappen“). */
function rsFrame(tr, ts, days) {
  const main = document.getElementById("main"), fam = tr.serie ? "serie" : "reise", root = SL_ROOT[fam], kp = fam === "serie" ? "se_" : "rs_";
  if (!main || document.getElementById(root)) return;
  window.RS_CUR = {tr, ts, days, fam};
  const host = document.createElement("div");
  host.id = root;
  host.className = "stx";
  host.dataset.trip = tr.id;
  const kopf = main.querySelector('[data-rs="kopf"]');
  if (kopf) {
    kopf.id = "rs-kopf";
    kopf.classList.add("rskopf");
    host.appendChild(kopf);
  }
  const km = ts.reduce((a, t) => a + t.km, 0);
  SL_REG[fam].forEach(reg => {
    if (reg.id === "kopf") return;
    const e = main.querySelector(`:scope > [data-rs="${reg.id}"]`);
    if (!e) return;
    if (reg.build) return e.remove();                                                   // 3.62.0: „Fotos“ ist ein Baustein (61-bausteine-reise.js), der Abschnitt der alten Ansicht entfällt
    const sec = e.querySelector(":scope > .sec");
    if (sec) sec.remove();                                                              // die Überschrift steht im Kopf der Karte
    if (!e.children.length) return e.remove();                                          // z. B. keine Statistik ohne Touren
    const badge = {
      kennzahlen: `${fmtAnzahl(ts.length, "Tour", "Touren")} · ${fmtKm(km, {d: 0})}`,
      stat: (n => (n === 1 ? "1 Sportart" : `${n} Sportarten`))(e.querySelectorAll("tbody tr").length),
      touren: fam === "serie" ? (ts.length === 1 ? "1 Etappe" : `${ts.length} Etappen`) : `${fmtAnzahl(ts.length, "Tour", "Touren")}`,
    }[reg.id] || "";
    const c = tlCard("rsc-" + reg.id, {sec: reg.id, key: kp + reg.id, icon: RS_ICON[reg.id], title: esc(reg.title), badge: esc(badge), def: true, bodyCls: reg.id === "karte" ? "tlmap" : "stb rsb"});
    tlBody(c).appendChild(e);
    delete e.dataset.rs;
    host.appendChild(c);
  });
  main.appendChild(host);
  slPlace(host);
  rsWatchMap();
}
/* Reisen-Übersicht: die Abschnitte der fertigen Seite in Karten stecken */
function rnFrame() {
  const main = document.getElementById("main");
  if (!main || document.getElementById("rsx") || !document.getElementById("tr")) return;
  window.RS_CUR = {trips: window.RS_TRIPS || []};
  const host = document.createElement("div");
  host.id = "rsx";
  host.className = "stx";
  const card = (id, title, badge, def) => {
    const c = tlCard("rnc-" + id, {sec: id, key: "rn_" + id, icon: RN_ICON[id], title: esc(title), badge: esc(badge || ""), def, bodyCls: "stb rsb"});
    host.appendChild(c);
    return tlBody(c);
  };
  const alb = main.querySelector("#rnalb"), ser = main.querySelector("#rnser"), btn = main.querySelector("#sbbtn"), nser = ser ? ser.querySelectorAll(".otd").length : 0;
  let b = card("serien", "Mehrtagestouren", nser ? `${nser} erkannt` : "", true);
  b.insertAdjacentHTML("beforeend", '<p class="mut rnhint">erkannt an Namen wie „… Tag 3“ oder „… Etappe 2“</p>');
  if (btn && btn.parentElement) b.appendChild(btn.parentElement);
  const grid = ser && ser.querySelector(":scope > .otdg");
  if (grid) b.appendChild(grid);
  if (ser) ser.remove();
  const trips = window.RS_TRIPS || [];
  b = card("reisen", "Reisen", trips.length === 1 ? "1 Reise" : trips.length ? `${trips.length} Reisen` : "", true);
  b.appendChild(document.getElementById("tr"));
  b = card("alben", "Schlagwörter & Alben", "", true);
  if (alb) {
    const h = alb.querySelector(":scope > .sec .sub");
    if (h) b.insertAdjacentHTML("beforeend", `<p class="mut rnhint">${esc(h.textContent)}</p>`);
    alb.querySelectorAll(":scope > .sec").forEach(x => x.remove());
    while (alb.firstChild) b.appendChild(alb.firstChild);
    alb.remove();
  }
  const hid = main.querySelector("#trhidbox");
  if (hid) {
    const n = (/\((\d+)\)/.exec((hid.querySelector("summary") || {}).textContent || "") || [])[1];
    b = card("entfernt", "Entfernte Reisen", n ? (n === "1" ? "1 Reise" : `${n} Reisen`) : "", false);
    const sm = hid.querySelector("summary");
    if (sm) sm.remove();
    while (hid.firstChild) b.appendChild(hid.firstChild);
    hid.remove();
  }
  main.appendChild(host);
  slPlace(host);
}
/* ---------- Anbindung an die Ansichten ---------- */
{
  const _trip62 = VIEWS.trip, _trips62 = VIEWS.trips;
  VIEWS.trip = async (...a) => {
    window.RS_WRAPPED = true;
    slViewStart("reise");
    const tok = window._rt;
    await slEnsure("reise");
    if (tok !== window._rt) return STALE();                            // inzwischen eine andere Seite geöffnet
    slResolve("reise");
    window.RS_CUR = null;
    await _trip62(...a);
  };
  VIEWS.trips = async (...a) => {
    window.RS_WRAPPED = true;
    slViewStart("reisen");
    const tok = window._rt;
    await slEnsure("reisen");
    if (tok !== window._rt) return STALE();
    slResolve("reisen");
    window.RS_CUR = null;
    await _trips62(...a);
    if (tok !== window._rt) return;
    rnFrame();
  };
}
/* 3.63.0 Mehrtagestour (#/series/<id>, Ansicht in 15-etappen.js): wie die Reise-Seite anpassbar (Layout-Schlüssel „serie“) */
{
  const _ser62 = VIEWS.series;
  VIEWS.series = async (...a) => {
    window.SE_WRAPPED = true;
    slViewStart("serie");
    const tok = window._rt;
    await slEnsure("serie");
    if (tok !== window._rt) return STALE();
    slResolve("serie");
    window.RS_CUR = null;
    await _ser62(...a);
  };
}
/* Dieses Skript lädt zuletzt: Hat die Seite schon gezeichnet (boot() in 13-start.js läuft früher), bevor die Ansichten hier eingehängt waren, wird sie jetzt mit dem Layout neu gezeichnet (wie 56-statistik.js) */
slLate(/^#\/trips?(\/[^/]*)?$/, "RS_WRAPPED", "#tr, #cm");
slLate(/^#\/series\/[^/]*$/, "SE_WRAPPED", "#cm");
