/* =====================  3.34.0 Gesamtkarte als anpassbare Seite (Layout-Schlüssel „karte“)  =====================
   Die Karte (#/map; Aufbau in 02-uebersicht.js, Heatmap und Fotos in 06-erweiterungen.js, Standort in 32-karte.js) ist wie die anderen Seiten anpassbar (Engine 49-seitenlayout.js).
   Aufbau: #kax ist das Raster der Seite. Hauptbaustein „karte“ (Pflicht, nicht ausblendbar; ganze, zwei Drittel oder halbe Breite) enthält die Karte mit ihren Bedienfeldern.
   Bedienfelder (Standort, Jahr und Anzahl, Sportarten, Strecken-Stil, Heatmap und Fotos, Touren im Ausschnitt) sind Abschnitte der Seite: kapw-Hüllen um die bisherigen Kästen (Kennungen, Knöpfe und Ereignisse
   bleiben dieselben Knoten). Ohne Anpassung liegen sie in dieser Reihenfolge als Kästen auf der Karte (ab 3.43.0 nach Aufgabe geordnet: Filter = Jahr, Sportarten | Ebenen = Strecken, Heatmap, Fotos | Aktionen = Standort, Touren im Ausschnitt; vorher Standort zuerst). Mit dem Layout lassen sie sich ausblenden (der Kasten bleibt in der Seite, nur unsichtbar),
   zuklappen („Standardmäßig offen“ aus: nur ein kleiner Knopf mit dem Namen bleibt) und umordnen. Im Bearbeitungsmodus stehen sie als Blöcke im Raster (wie die anderen Abschnitte) und gehen danach zurück auf die Karte.
   Bausteine (Katalog „Karte“): kzahlen (Karten-Kennzahlen), kliste (Touren im Kartenausschnitt), klegende (Legende der Sportarten). Sie lesen den Stand der Karte (Jahr, Sportarten, Ausschnitt) und
   aktualisieren sich bei jeder Änderung (KA.subs).
   Größe: Ändert sich das Layout (Bearbeitungsmodus, Baustein neben der Karte, andere Breite), passt ein ResizeObserver die Karte an (invalidateSize) und rahmt den bisherigen Ausschnitt neu ein,
   solange der Benutzer die Karte nicht selbst bewegt hat (map._kaUser); ein selbst gewählter Ausschnitt bleibt. Ohne Layout-Änderung verhält sich die Karte wie bisher (nur Leaflets eigene Größenanpassung). */
const KA_PANELS = ["jahr", "sport", "stil", "ebenen", "standort", "ausschnitt"];
const KA_NAME = {standort: "Standort", jahr: "Jahr", sport: "Sportarten", stil: "Strecken", ebenen: "Ebenen", ausschnitt: "Ausschnitt"};
SL_REG.karte = [
  {id: "karte", w: "voll", title: "Karte", page: "karte", plain: true, must: true, ws: ["voll", "zweidrittel", "halb"]},
  {id: "jahr", w: "voll", title: "Bedienfeld: Jahr und Anzahl", page: "karte", def: true, ws: ["voll"], panel: true, ckeys: ["ka_jahr"]},
  {id: "sport", w: "voll", title: "Bedienfeld: Sportarten", page: "karte", def: true, ws: ["voll"], panel: true, ckeys: ["ka_sport"]},
  {id: "stil", w: "voll", title: "Bedienfeld: Strecken-Stil", page: "karte", def: true, ws: ["voll"], panel: true, ckeys: ["ka_stil"]},
  {id: "ebenen", w: "voll", title: "Bedienfeld: Heatmap und Fotos", page: "karte", def: true, ws: ["voll"], panel: true, ckeys: ["ka_ebenen"]},
  {id: "standort", w: "voll", title: "Bedienfeld: Mein Standort", page: "karte", def: true, ws: ["voll"], panel: true, ckeys: ["ka_standort"]},
  {id: "ausschnitt", w: "voll", title: "Bedienfeld: Touren im Ausschnitt", page: "karte", def: true, ws: ["voll"], panel: true, ckeys: ["ka_ausschnitt"]},
];
const KA = {subs: [], edit: false, sig: "", relayout: false, timer: 0};
const kaEl = id => document.getElementById("kap-" + id);
SL_EL.karte = Object.fromEntries([["karte", () => document.getElementById("kac-karte")]].concat(KA_PANELS.map(id => [id, () => (KA.edit ? kaEl(id) : null)])));

/* ---------- Stand der Karte (für die Bausteine) ---------- */
function kaState() {
  const sel = document.getElementById("my"), y = sel ? +sel.value || 0 : 0, off = mapOff();
  return {y, off, tours: TOURS.filter(t => (!y || t.y === y) && !off.has(t.sport))};
}
/* Touren, deren Strecke den sichtbaren Ausschnitt berührt (wie „Touren im Ausschnitt“ in 06-erweiterungen.js) */
function kaInView(list) {
  if (typeof map === "undefined" || !map || !map.getBounds) return list;
  const b = map.getBounds(), R = ROUTES || {};
  return list.filter(t => cleanPts(R[t.id]).some(p => b.contains(p)) || (okPt([t.lat, t.lng]) && b.contains([t.lat, t.lng]) && !(R[t.id] || []).length));
}
function kaFire() {
  clearTimeout(KA.timer);
  KA.timer = setTimeout(() => (KA.subs = KA.subs.filter(f => f() !== false)), 150);
}
/* Baustein meldet sich an: fn() zeichnet neu und gibt false zurück, sobald der Baustein nicht mehr in der Seite steht */
function kaSub(fn) {
  KA.subs.push(fn);
  fn();
}
const KA_VALUES = [["touren", "Touren"], ["km", "Strecke"], ["up", "Aufstieg"], ["h", "Unterwegs"]];
const KA_DEF = ["touren", "km", "up"];
const kaTxt = (st, aus) => [st.y ? String(st.y) : "alle Jahre", aus ? "im Kartenausschnitt" : "auf der Karte"].join(", ");
Object.assign(window.SL_WT, {
  kzahlen: {
    fam: "karte", cat: "karte", icon: "met", name: "Karten-Kennzahlen", title: () => "Karten-Kennzahlen", multi: true, w: "halb", seiten: ["karte"], defaults: {values: KA_DEF, basis: "filter"},
    desc: "Touren, Strecke, Aufstieg und Zeit der Touren, die die Karte gerade zeigt (Jahr und Sportarten oben auf der Karte) oder die den sichtbaren Ausschnitt berühren. Die Zahlen folgen jeder Änderung der Karte.",
    fields: [{k: "values", kind: "checks", label: "Angezeigte Werte", min: 1, def: KA_DEF, options: KA_VALUES}, {k: "basis", kind: "radio", def: "filter", label: "Zählen", options: [["filter", "Gefilterte Touren"], ["ausschnitt", "Im Kartenausschnitt"]]}, {kind: "title"}],
    preview: () => slPvTiles([["42", "Touren"], ["512 km", "Strecke"], ["14 300 m", "Aufstieg"]]),
    render(c, b, cfg) {
      const want = (cfg.values && cfg.values.length ? cfg.values : KA_DEF).filter(v => KA_VALUES.some(k => k[0] === v)), aus = cfg.basis === "ausschnitt";
      kaSub(() => {
        if (!b.isConnected) return false;
        const st = kaState(), L = aus ? kaInView(st.tours) : st.tours;
        if (!L.length) {
          slNote(b, "Keine Touren in dieser Auswahl.");
          slBadge(c, "");
          return true;
        }
        const tile = {touren: [nf(L.length, 0), L.length === 1 ? "Tour" : "Touren"], km: [slKm(slSum(L, t => t.km)), "Strecke"], up: [slHm(slSum(L, t => t.up_m || 0)), "Aufstieg"], h: [fmtDauer(slSum(L, t => t.h) * 3600, {summe: true}), "Unterwegs"]};
        b.innerHTML = slTiles(want.map(v => tile[v]).filter(Boolean)) + `<p class="mut slcmpn">${esc(kaTxt(st, aus))}</p>`;
        slBadge(c, L.length === 1 ? "1 Tour" : `${fmtAnzahl(L.length, "Tour", "Touren")}`);
        return true;
      });
    },
  },
  kliste: {
    fam: "karte", cat: "karte", icon: "map", name: "Touren im Kartenausschnitt", title: () => "Touren im Kartenausschnitt", multi: true, w: "drittel", seiten: ["karte"], defaults: {n: 10, sort: "date"},
    desc: "Eine Liste der Touren, die den sichtbaren Kartenausschnitt berühren, neueste, längste oder mit dem größten Aufstieg zuerst. Beim Verschieben und Zoomen der Karte ändert sich die Liste.",
    fields: [{k: "n", kind: "radio", num: true, def: 10, label: "Anzahl", options: [[5, "5"], [10, "10"], [20, "20"]]}, {k: "sort", kind: "radio", def: "date", label: "Sortieren nach", options: [["date", "Datum"], ["km", "Strecke"], ["up", "Aufstieg"]]}, {kind: "title"}],
    preview: () => slPrev('<ul class="sllist"><li><b>Gipfelrunde</b><span>12,4 km</span></li><li><b>Seeufer</b><span>8,1 km</span></li></ul>'),
    render(c, b, cfg) {
      const n = [5, 10, 20].includes(+cfg.n) ? +cfg.n : 10, key = {date: t => t.date, km: t => t.km, up: t => t.up_m || 0}[cfg.sort] || (t => t.date);
      kaSub(() => {
        if (!b.isConnected) return false;
        const L = kaInView(kaState().tours).sort((x, y) => (key(x) < key(y) ? 1 : key(x) > key(y) ? -1 : 0));
        if (!L.length) {
          slNote(b, "In diesem Ausschnitt liegen keine Touren. Zoome heraus oder verschiebe die Karte.");
          slBadge(c, "");
          return true;
        }
        b.innerHTML = `<ul class="sllist kalist">${L.slice(0, n).map(t => `<li><a href="#/tour/${encodeURIComponent(t.id)}">${esc(t.name)}</a><span class="mut">${fmtDatumKurz(t.date)} · ${fmtKm(t.km)} · ${fmtHm(t.up_m || 0)}</span></li>`).join("")}</ul>` +
          (L.length > n ? `<p class="mut slcmpn">und ${nf(L.length - n, 0)} weitere</p>` : "");
        slBadge(c, L.length === 1 ? "1 Tour" : `${fmtAnzahl(L.length, "Tour", "Touren")}`);
        return true;
      });
    },
  },
  klegende: {
    fam: "karte", cat: "karte", icon: "pin", name: "Legende der Sportarten", title: () => "Legende der Sportarten", multi: true, w: "drittel", seiten: ["karte"], defaults: {metric: "count"},
    desc: "Welche Farbe zu welcher Sportart gehört, mit der Zahl der Touren (oder den Kilometern) im gewählten Jahr. Sportarten, die du oben auf der Karte abwählst, erscheinen blass.",
    fields: [{k: "metric", kind: "radio", def: "count", label: "Zahl je Sportart", options: [["count", "Anzahl der Touren"], ["km", "Strecke"]]}, {kind: "title"}],
    preview: () => slPvHbars([90, 62, 40, 22]),
    render(c, b, cfg) {
      const km = cfg.metric === "km";
      kaSub(() => {
        if (!b.isConnected) return false;
        const y = +((document.getElementById("my") || {}).value || 0), st = kaState(), L = TOURS.filter(t => !y || t.y === y), by = {};
        L.forEach(t => (by[t.sport] = (by[t.sport] || 0) + (km ? t.km : 1)));
        const keys = sportOrder(Object.keys(by)).filter(k => !isSg(k));            // 3.60.1: Katalog-Reihenfolge wie die Chips der Karte
        if (!keys.length) {
          slNote(b, "Keine Touren in diesem Jahr.");
          return true;
        }
        b.innerHTML = `<ul class="sllist kaleg">${keys.map(s => `<li class="${st.off.has(s) ? "kaoff" : ""}"><i class="kasw" data-c="${esc(s)}"></i><span>${esc(sName(s))}</span><b>${km ? fmtKm(by[s], {d: 0}) : nf(by[s], 0)}</b></li>`).join("")}</ul>`;
        b.querySelectorAll(".kasw").forEach(e => e.style.setProperty("background", sCol(e.dataset.c)));
        slBadge(c, `${keys.length} Sportarten`);
        return true;
      });
    },
  },
});
SL_TPL.push(
  {id: "ka-liste", fam: "karte", name: "Karte mit Liste", desc: "Die Karte in zwei Dritteln, daneben die Touren im Kartenausschnitt als Liste. Von den Bedienfeldern bleiben Jahr und Sportarten.",
    items: [["karte", "zweidrittel"], ["w:kliste", "drittel"], ["jahr", "voll"], ["sport", "voll"]]},
  {id: "ka-zahlen", fam: "karte", name: "Karte mit Kennzahlen", desc: "Oben die Kennzahlen der Auswahl und die Legende der Sportarten, darunter die Karte mit allen Bedienfeldern.",
    items: [["w:kzahlen", "halb"], ["w:klegende", "halb"], ["karte", "voll"], ["jahr", "voll"], ["sport", "voll"], ["stil", "voll"], ["ebenen", "voll"], ["standort", "voll"], ["ausschnitt", "voll"]]},
  {id: "ka-pur", fam: "karte", name: "Nur die Karte", desc: "Ruhig und übersichtlich: nur die Karte, alle Bedienfelder sind entfernt.",
    items: [["karte", "voll"]]},
);

/* ---------- Aufbau: Karte und Bedienfelder in das Raster einordnen ---------- */
function kaFrame() {
  const main = document.getElementById("main"), box = main && main.querySelector(":scope > .mapbox");
  if (!box || document.getElementById("kax") || typeof map === "undefined" || !map) return;
  const ui = box.querySelector(".mapui");
  if (ui)
    [...ui.querySelectorAll(":scope > .box")].forEach(bx => {
      const id = bx.querySelector("#mloc") ? "standort" : bx.querySelector("#my") ? "jahr" : (bx.id === "ms" || bx.querySelector("#ms")) ? "sport" : bx.querySelector("#mtc") ? "stil" : bx.querySelector("#mht") ? "ebenen" : bx.querySelector("#mbx") ? "ausschnitt" : "";
      if (!id) return;
      const w = document.createElement("div");
      w.className = "kapw";
      w.id = "kap-" + id;
      w.dataset.kp = id;
      ui.insertBefore(w, bx);
      w.innerHTML = `<button type="button" class="chip kapt" aria-expanded="false" hidden><span>${esc(KA_NAME[id])}</span> ${symSvg("▸", 14, "ic ics")}</button>`;
      w.appendChild(bx);
    });
  if (ui) {                                                                           // 3.43.0 Handy: ein Knopf „Filter & Ebenen“ öffnet das Blatt mit Jahr, Sportarten, Strecken, Heatmap/Fotos und Ausschnitt (am Desktop unsichtbar)
    const fw = document.createElement("div");
    fw.className = "box mfbw";
    fw.innerHTML = `<button type="button" class="chip mfb" id="mfb" aria-expanded="false" aria-controls="mapui">Filter & Ebenen</button>`;
    ui.appendChild(fw);
    ui.id = "mapui";
    fw.firstChild.onclick = () => {
      const open = !ui.classList.contains("mfo");
      closePanels();
      ui.classList.toggle("mfo", open);
      fw.firstChild.setAttribute("aria-expanded", String(open));
    };
  }
  const host = document.createElement("div"), card = document.createElement("div");
  host.id = "kax";
  host.className = "stx kax";
  card.id = "kac-karte";
  card.className = "kacard";
  card.appendChild(box);
  host.appendChild(card);
  main.appendChild(host);
  map._kaBounds = map.getBounds();
  map._kaUser = false;
  const c = map.getContainer(), mark = () => (map._kaUser = true);
  ["pointerdown", "wheel", "keydown"].forEach(ev => c.addEventListener(ev, mark, {passive: true}));
  map.on("moveend", () => {
    if (!map._kaBusy) map._kaBounds = map.getBounds();
    kaFire();
  });
  const my = document.getElementById("my"), ms = document.getElementById("ms");
  if (my) my.addEventListener("change", () => setTimeout(kaFire, 0));
  if (ms) ms.addEventListener("click", () => setTimeout(kaFire, 0));
  host.addEventListener("click", e => {                                              // zugeklapptes Bedienfeld: Knopf öffnet es (nur für diese Sitzung)
    const t = e.target.closest(".kapt");
    if (t) t.closest(".kapw").dataset.closed = t.closest(".kapw").dataset.closed === "1" ? "0" : "1";
  });
  slPlace(host);
  kaWatch();
}
/* Größe der Karte nachführen */
function kaWatch() {
  const el = document.getElementById("bigmap");
  if (!el || el.dataset.karo || typeof ResizeObserver !== "function") return;
  el.dataset.karo = "1";
  let k0 = "", raf = 0;
  new ResizeObserver(es => {
    const r = es[0].contentRect, k = Math.round(r.width) + "x" + Math.round(r.height);
    if (k === k0) return;
    k0 = k;                                                                          // auch die erste Messung zählt: war die Karte schon vor dem Umbau des Rasters gebaut, stimmt ihre Größe nicht
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      if (!el.isConnected || typeof map === "undefined" || !map || map.getContainer() !== el || !el.clientWidth) return;
      const sz = map.getSize();
      if (Math.abs(sz.x - el.clientWidth) < 1 && Math.abs(sz.y - el.clientHeight) < 1) return;
      const refit = KA.relayout && !map._kaUser && map._kaBounds;
      map._kaBusy = true;
      map.invalidateSize({animate: false});
      if (refit) map.fitBounds(map._kaBounds, {animate: false});
      map._kaBusy = false;
    });
  }).observe(el);
}
/* Vor dem Einordnen: Bedienfelder zurück auf die Karte (nicht im Bearbeitungsmodus) */
function kaBefore(root, edit) {
  KA.edit = edit;
  const ui = root.querySelector(".mapui");
  if (!ui || edit) return;
  const hid = slSt("karte").hidden || [], ord = slOrder("karte", "karte").map(i => i.id).filter(id => KA_PANELS.includes(id)), mn = document.getElementById("mn");
  let last = null;
  ord.forEach(id => {
    const w = kaEl(id);
    if (!w) return;
    ui.appendChild(w);
    w.classList.toggle("sl-off", hid.includes(id));
    w.dataset.closed = slDef(id, true) ? "0" : "1";
    last = id === "sport" ? w : last;
  });
  const mnb = mn && mn.closest(".box");
  if (mnb && last) last.after(mnb);                                                    // der Hinweis „Strecken werden geladen“ bleibt hinter den Sportarten
}
/* Nach dem Einordnen: Raster-Zustand, Knopf „Seite anpassen“ auf der Karte, Größe */
function kaAfter(root, edit, pres) {
  const main = document.getElementById("main"), ui = root.querySelector(".mapui"), vis = pres.filter(p => p.it.widget && !p.off), mp = pres.find(p => p.it.id === "karte"),
    multi = edit || vis.length > 0 || (mp && mp.cw !== "voll");
  root.classList.toggle("kamulti", !!multi);
  if (main) main.classList.toggle("kamulti", !!multi);
  const dup = !edit && vis.some(p => p.it.wtype === "kliste"), fb = document.getElementById("mfb");   // „Touren im Ausschnitt“ nur einmal: steht der Baustein auf der Seite, entfällt der Knopf
  if (edit) closePanels();
  const ap = document.getElementById("kap-ausschnitt");
  if (ap) ap.classList.toggle("sl-dup", dup);
  if (fb) fb.parentElement.hidden = edit || !root.querySelector(".kapw:not([data-kp=standort]):not(.sl-off):not(.sl-dup)");
  root.querySelectorAll(".kapw").forEach(w => {
    w.classList.toggle("kapedit", edit);
    const t = w.querySelector(".kapt"), closed = !edit && w.dataset.closed === "1";
    t.hidden = !closed;
    t.setAttribute("aria-expanded", "false");
    w.classList.toggle("kaclosed", closed);
  });
  const ow = document.getElementById("slopenw");
  if (ow && ui && ow.parentElement !== ui) {
    ow.classList.add("kaopen");
    ui.appendChild(ow);
  }
  const sig = [!!multi, mp && mp.cw, edit, vis.map(p => p.it.id).join(",")].join("|");
  if (KA.sig && sig !== KA.sig) {
    KA.relayout = true;                                                                // die nächste Größenänderung der Karte rahmt den Ausschnitt neu ein
    setTimeout(() => (KA.relayout = false), 900);
    if (typeof map !== "undefined" && map && map.invalidateSize) requestAnimationFrame(() => map && map.invalidateSize && map.invalidateSize({animate: false}));
  }
  KA.sig = sig;
  kaFire();
}
/* ---------- Anbindung an die Ansicht ---------- */
{
  const _map64 = VIEWS.map;
  VIEWS.map = async (...a) => {
    window.KA_WRAPPED = true;
    KA.subs = [];
    KA.sig = "";
    KA.edit = false;
    slViewStart("karte");
    const tok = window._rt;
    await slEnsure("karte");
    if (tok !== window._rt) return STALE();
    slResolve("karte");
    await _map64(...a);
    if (tok !== window._rt) return;
    kaFrame();
  };
}
slLate(/^#\/map(\?.*)?$/, "KA_WRAPPED", "#bigmap");
