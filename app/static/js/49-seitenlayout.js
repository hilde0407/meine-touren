/* =====================  3.17.0 Seite anpassen: gemeinsame Layout-Engine  =====================
   Seiten (Schlüssel wie in der API /api/layout/<Schlüssel>): „tour-haupt“ (#/tour/<id>), „tour-auswertung“ (#/tour/<id>/auswertung), „uebersicht“ (#/dash), „statistik“ (#/stats, 3.22.0).
   Layout-Dokument je Schlüssel: {order:[ids], hidden:[ids], closed:[ids], open:[ids], page:{id:"haupt"|"auswertung"}, widgets:[{id,type,cfg}]}.
     order     Reihenfolge der Abschnitte der Seite; bekannte, aber nicht aufgeführte Abschnitte werden an ihrer Standardposition ergänzt, unbekannte ignoriert
     hidden    ausgeblendete Abschnitte   closed/open  „Standardmäßig offen“ weicht vom Standard des Abschnitts ab
     page/widgets  gelten für die ganze Tourseite und stehen im Dokument „tour-haupt“ (die Reihenfolge der Unterseite steht in „tour-auswertung“)
   Ohne gespeichertes Layout ist alles wie in 3.16.x: die Registry (SL_REG) bildet die Standardposition ab. Betrachter bekommen immer den Standard.
   Aufgabenteilung: 48-tourlayout.js sammelt die Karten (und fasst die Unterseite zusammen), slPlace() ordnet sie ein: je Lauf gleicher Gruppen eine Überschrift,
   leere Gruppen entfallen. Im Bearbeitungsmodus steckt jeder Abschnitt in einem Rahmen „.slit“ mit Griff, Hoch/Runter, Auge, Schaltern (Pointer-Ereignisse, auch Touch).
   Die Bausteine (Katalog, Typen) stehen in 50-bausteine.js (window.SL_WT).
   3.20.0 Raster: jeder Abschnitt hat eine Breite (voll, zweidrittel, halb, drittel; Dokumentfeld w, Standard je Eintrag/Typ: Feld w der Registry), das Raster selbst ist CSS (style.css „3.20.0“),
   hier werden nur die Klassen gesetzt (.slcell .w-…) und Zeilenreste aufgefüllt (slRaster). Seiteneignung: Typ.seiten (Standard: Tour-Bausteine nur „tour“, Übersichts-Bausteine „uebersicht“ und „tour“). */
window.SL_WT = window.SL_WT || {};
const SL_PAGE_KEY = {haupt: "tour-haupt", auswertung: "tour-auswertung", uebersicht: "uebersicht", statistik: "statistik", reise: "reise", serie: "serie", reisen: "reisen", gebiete: "gebiete", gebiet: "gebiet", fotos: "fotos", karte: "karte"};
const slKey1 = fam => (fam === "tour" ? "tour-haupt" : fam);                                  // Schlüssel des (ersten) Dokuments einer Seitenfamilie
const SL_ONE = ["uebersicht", "statistik", "reise", "serie", "reisen", "gebiete", "gebiet", "fotos", "karte"];                    // Seiten mit genau einem Dokument (3.33.0: Reise-Detailseite „reise“ und Reisen-Übersicht „reisen“; 3.34.0: Fotos „fotos“ und Gesamtkarte „karte“)
const slFamOf = k => (SL_ONE.includes(k) ? k : "tour");
const SL_W = {d: {voll: 12, zweidrittel: 8, halb: 6, drittel: 4}, t: {voll: 12, zweidrittel: 12, halb: 6, drittel: 6}};            // Spalten je Breite: Desktop (ab 900 px) und Tablet
const SL_WALL = ["voll", "zweidrittel", "halb", "drittel"];
const SL_WNAME = {voll: "Ganze Breite", zweidrittel: "Zwei Drittel", halb: "Halbe Breite", drittel: "Ein Drittel"};
const SL_WCLS = SL_WALL.map(k => "w-" + k);
const slTypeW = T => (T && SL_W.d[T.w] ? T.w : "voll");
const slSeiten = T => (T && T.seiten) || (T && T.fam === "tour" ? ["tour"] : ["uebersicht", "tour"]);
const slFits = (T, fam) => !!T && slSeiten(T).includes(fam);
const SL_ROOT = {statistik: "stx", reise: "trx", serie: "srx", reisen: "rsx", gebiete: "gex", gebiet: "gdx", fotos: "fox", karte: "kax"};
const slOneRoot = fam => document.getElementById(SL_ROOT[fam] || "rsx");          // Wurzel des Rasters einer Seite mit einem Dokument (Übersicht: main.home)
const SL_GROUPS = {route: "Streckenverlauf", rec: "Aufzeichnung", eval: "Auswertung dieser Tour", more: "Fotos zur Tour", bst: "Bausteine"};
/* Registry: Standardseite, Gruppe, Standard „offen“ (def), fixed = kann nur auf dieser Seite stehen (wird von der Tourseite selbst aufgebaut),
   must = Pflicht (nicht ausblendbar), plain = kein einklappbarer Abschnitt, ckeys = Speicherschlüssel des Auf-/Zu-Zustands (localStorage „mt_trf_…“) */
const SL_REG = {
  tour: [
    {id: "map", w: "voll", title: "Karte", page: "haupt", group: "route", def: true, fixed: true, ckeys: ["tl_map"]},
    {id: "prof", w: "voll", title: "Höhenprofil", page: "haupt", group: "route", def: true, fixed: true, ckeys: ["tl_prof"]},
    {id: "puls", w: "halb", title: "Herzfrequenz", page: "haupt", group: "route", def: true, fixed: true, ckeys: ["tl_puls"]},
    {id: "wp", w: "halb", title: "Wegpunkte", page: "haupt", group: "route", def: true, fixed: true, ckeys: ["tl_wp"]},
    {id: "planist", w: "voll", title: "Planung und Ergebnis", page: "haupt", group: "route", build: "planergebnis", def: true, when: () => typeof planErgHas === "function" && planErgHas(), ckeys: ["tl_w_planist"]},        // 3.39.0: Soll/Ist, nur mit verknüpftem Plan (when)
    {id: "sum", w: "voll", title: "Einstieg in die Auswertung", page: "haupt", group: "sum", own: true, fixed: true, must: true, plain: true, ws: ["voll"]},
    {id: "photos", w: "voll", title: "Fotos", page: "haupt", group: "more", def: true, fixed: true, ckeys: ["tl_photos"]},
    {id: "geraet", w: "voll", title: "Gerät: Messwerte und Training laut Uhr", page: "auswertung", group: "rec", def: true, fixed: true, ckeys: ["tl_met", "tl_uhr"], ws: ["voll"]},
    {id: "wx", w: "halb", title: "Wetter", page: "auswertung", group: "rec", def: false, ckeys: ["tl_wx"]},
    {id: "ana", w: "voll", title: "Analyse", page: "auswertung", group: "eval", def: false, ckeys: ["tl_ana"]},
    {id: "steig", w: "halb", title: "Tempo nach Steigung", page: "auswertung", group: "eval", def: false, ckeys: ["steig"]},
    {id: "aehn", w: "halb", title: "Ähnliche Touren im Vergleich", page: "auswertung", group: "eval", def: false, ckeys: ["aehn"]},
    {id: "cmp", w: "halb", title: "Vergleich dieser Strecke", page: "auswertung", group: "eval", def: false, ckeys: ["tl_cmp"]},
  ],
  uebersicht: [
    {id: "aufmacher", w: "voll", title: "Zuletzt unterwegs (Aufmacher)", page: "uebersicht", plain: true, ws: ["voll"]},
    {id: "jahr", w: "voll", title: "Dein Jahr", page: "uebersicht", plain: true, build: "jahr"},
    {id: "zepp", w: "voll", title: "Touren holen", page: "uebersicht", build: "zeppimport", def: true, ckeys: ["tl_w_zepp"]},                // 3.30.0: kompakte Karte mit Import-Knopf (Baustein „zeppimport“) gleich unter „Dein Jahr“
    {id: "zuletzt", w: "voll", title: "Letzte Touren", page: "uebersicht", plain: true, ws: ["voll", "zweidrittel"]},
    {id: "tag", w: "halb", title: "An diesem Tag", page: "uebersicht", group: "cols", plain: true},
    {id: "erinn", w: "halb", title: "Erinnerungen", page: "uebersicht", group: "cols", plain: true, build: "erinn"},                // 3.32.0: einstellbarer Baustein (60-bausteine-erinnerungen.js), ohne Einstellung wie bisher
  ],
  /* 3.22.0 Statistik: die Abschnitte der Seite #/stats in der bisherigen Reihenfolge (Kapselung in 56-statistik.js: jeder Abschnitt ist eine Karte im Format von tlCard).
     „bl“ und „tp“ (Belastung, Tempo) sind schon einklappbare Abschnitte mit eigenem Zustand (plain). Fehlen Daten (Tage, Fotos), gibt es den Abschnitt nicht. */
  statistik: [
    {id: "kpi", w: "voll", title: "Kennzahlen", page: "statistik", def: true, ckeys: ["st_kpi"]},
    {id: "ziele", w: "voll", title: "Ziele", page: "statistik", build: "ziele", verwalten: true, def: true, ckeys: ["tl_w_ziele"]},            // 3.45.0: Baustein „Ziele“ mit Pflege der Ziele (die eine Stelle dafür)
    {id: "kmmonat", w: "halb", title: "Strecke pro Monat oder Jahr", page: "statistik", def: true, ckeys: ["st_kmmonat"]},
    {id: "kmverlauf", w: "halb", title: "Strecke im Jahresverlauf", page: "statistik", def: true, ckeys: ["st_kmverlauf"]},
    {id: "sportarten", w: "halb", title: "Sportarten", page: "statistik", def: true, ckeys: ["st_sportarten"]},
    {id: "bestwerte", w: "halb", title: "Bestwerte", page: "statistik", build: "bestwerte", def: true, ckeys: ["tl_w_bestwerte"]},         // 3.45.0: Baustein „Bestwerte“ (vorher eigener Abschnitt „Rekorde“)
    {id: "heat", w: "voll", title: "Touren im Jahr", page: "statistik", def: true, ckeys: ["st_heat"]},
    {id: "bl", w: "voll", title: "Belastung und Erholung", page: "statistik", plain: true},
    {id: "tp", w: "voll", title: "Dein typisches Tempo", page: "statistik", plain: true},
    {id: "tag", w: "voll", title: "An diesem Tag", page: "statistik", def: true, ckeys: ["st_tag"]},
    {id: "erinn", w: "voll", title: "Erinnerungen", page: "statistik", def: true, ckeys: ["st_erinn"]},
  ],
};
/* 3.33.0 Reisen: Reise-Detailseite (#/trip/<id>, 62-reiseseiten.js kapselt collView in Karten) und Reisen-Übersicht (#/trips). Die Abschnitte stehen in der Reihenfolge der bisherigen Seite;
   „kopf“ (Titel, Zeitraum, Aktionen) ist Pflicht und bleibt sichtbar. Kennzahlen, Statistik, Flug/Offline-Karte, Karte, Fotos und Touren sind einklappbare Karten. Bausteine: 61-bausteine-reise.js. */
const SL_FOTOS_DEF = {mode: "all", ratio: "43", size: "l"};                   // Vorgabe des Standard-Abschnitts „Fotos“ der Reise (ohne gespeicherte Einstellung): alle Fotos der Reise als Vorschaubilder 4:3
SL_REG.reise = [
  {id: "kopf", w: "voll", title: "Kopf: Titel, Zeitraum und Aktionen", page: "reise", plain: true, must: true, ws: ["voll"]},
  {id: "kennzahlen", w: "voll", title: "Kennzahlen", page: "reise", def: true, ckeys: ["rs_kennzahlen"]},
  {id: "stat", w: "voll", title: "Statistik nach Sportart", page: "reise", def: true, ckeys: ["rs_stat"]},
  {id: "flug", w: "voll", title: "3D-Flug und Offline-Karte", page: "reise", def: true, ckeys: ["rs_flug"]},
  {id: "karte", w: "voll", title: "Karte", page: "reise", def: true, ckeys: ["rs_karte"]},
  {id: "fotos", w: "voll", title: "Fotos", page: "reise", build: "rdiashow", defcfg: SL_FOTOS_DEF, def: true, ckeys: ["rs_fotos"]},        // 3.62.0: der Abschnitt „Fotos“ ist der Baustein „Fotos“ (Typ rdiashow) mit „Alle“; Id, Position, Breite, Sichtbarkeit und Auf-/Zu-Zustand bleiben wie bisher
  {id: "touren", w: "voll", title: "Touren", page: "reise", def: true, ckeys: ["rs_touren"]},
];
/* 3.63.0 Mehrtagestour (#/series/<id>): dieselben Abschnitte wie die Reise (Kopf, Kennzahlen, Statistik, Flug, Karte, Fotos, Touren), eigenes Layout (Schlüssel „serie“, für alle Mehrtagestouren gleich),
   eigene Zustandsschlüssel (se_…); die Bausteine sind die der Reise (61-bausteine-reise.js: seiten enthält auch „serie“). Aufbau: 62-reiseseiten.js (rsFrame mit fam „serie“), Ansicht: 15-etappen.js. */
SL_REG.serie = [
  {id: "kopf", w: "voll", title: "Kopf: Titel, Zeitraum und Aktionen", page: "serie", plain: true, must: true, ws: ["voll"]},
  {id: "kennzahlen", w: "voll", title: "Kennzahlen", page: "serie", def: true, ckeys: ["se_kennzahlen"]},
  {id: "stat", w: "voll", title: "Statistik nach Sportart", page: "serie", def: true, ckeys: ["se_stat"]},
  {id: "flug", w: "voll", title: "3D-Flug und Offline-Karte", page: "serie", def: true, ckeys: ["se_flug"]},
  {id: "karte", w: "voll", title: "Karte", page: "serie", def: true, ckeys: ["se_karte"]},
  {id: "fotos", w: "voll", title: "Fotos", page: "serie", build: "rdiashow", defcfg: SL_FOTOS_DEF, def: true, ckeys: ["se_fotos"]},
  {id: "touren", w: "voll", title: "Etappen", page: "serie", def: true, ckeys: ["se_touren"]},
];
SL_REG.reisen = [
  {id: "serien", w: "voll", title: "Mehrtagestouren", page: "reisen", def: true, ckeys: ["rn_serien"]},
  {id: "reisen", w: "voll", title: "Reisen", page: "reisen", def: true, ckeys: ["rn_reisen"]},
  {id: "alben", w: "voll", title: "Schlagwörter & Alben", page: "reisen", def: true, ckeys: ["rn_alben"]},
  {id: "entfernt", w: "voll", title: "Entfernte Reisen", page: "reisen", def: false, ckeys: ["rn_entfernt"]},
];
const SL_EL = {
  tour: {
    map: () => tlSec("map"), prof: () => tlSec("prof"), puls: () => $("#pulscard"), wp: () => $("#wpcard"), sum: () => $("#tlg-sum"), photos: () => tlSec("photos"),
    geraet: () => $("#tlrec"), wx: () => tlSec("wx"), ana: () => $("#anacard"), steig: () => $("#steigcard"), aehn: () => $("#aehncard"), cmp: () => $("#cmpseg"),
  },
  reise: Object.fromEntries(["kopf", "kennzahlen", "stat", "flug", "karte", "touren"].map(id => [id, () => (id === "kopf" ? document.getElementById("rs-kopf") : document.getElementById("rsc-" + id))])),
  serie: Object.fromEntries(["kopf", "kennzahlen", "stat", "flug", "karte", "touren"].map(id => [id, () => (id === "kopf" ? document.getElementById("rs-kopf") : document.getElementById("rsc-" + id))])),
  reisen: Object.fromEntries(["serien", "reisen", "alben", "entfernt"].map(id => [id, () => document.getElementById("rnc-" + id)])),
  uebersicht: {aufmacher: () => $("#hlast"), jahr: () => $("#hyear"), zuletzt: () => $("#hrecent"), tag: () => $("#htag"), erinn: () => $("#hmemsec")},
  statistik: Object.fromEntries(["kpi", "kmmonat", "kmverlauf", "sportarten", "heat", "tag", "erinn"].map(id => [id, () => document.getElementById("stc-" + id)]).concat([["bl", () => $("#blsec")], ["tp", () => $("#tpsec")]])),
};
/* 3.21.0 Ansichten: SL.store[Schlüssel] = Behälter {views:[{id,name,layout}], active, rules} (so liegt er auf dem Server); SL.docs[Schlüssel] = Layout der gerade angezeigten Ansicht
   (damit arbeitet der ganze übrige Code unverändert); SL.view[fam] = Kennung der angezeigten Ansicht; SL.manual[fam] = in dieser Sitzung von Hand gewählte Ansicht (vor den Regeln). */
const SL = {docs: {}, store: {}, view: {}, manual: {}, sport: {}, loaded: {}, edit: false, dirty: new Set(), busy: new Set(), rev: {}, fam: "tour", page: "haupt", present: [], timer: null, focus: null, drag: null};
const SL_STD = "standard";
const SL_MAXV = 12;
const slBlank = () => ({v: 2, views: [{id: SL_STD, name: "Standard", layout: {v: 1}}], active: SL_STD, rules: {}});
/* 3.45.0 Umzug alter Bausteine: alte Typkennung → [neuer Typ, Einstellung] (gleiche Tabelle wie app/baustein_umzug.py; der Server zieht gespeicherte Layouts beim Öffnen der Datenbank um
   und übernimmt eigene Ziele in die Ziele der Statistik – hier wird nur angezeigt, damit Zwischenspeicher, ältere Antworten und Ansichten nie leer oder kaputt sind) */
const slPick = (c, ks) => Object.fromEntries(ks.filter(k => k in c).map(k => [k, c[k]]));
const SL_ALIAS = {
  jahresziel: c => ["ziele", {view: "ring", zeit: "jahr", ...slPick(c, ["sports", "title"])}],
  jahresziele: c => ["ziele", {view: "balken", zeit: "jahr", ...slPick(c, ["sports", "title"]), ...(c.year === "last" ? {year: "last"} : {})}],
  hnziel: c => {
    const sn = (c.snoozes || []).filter(x => typeof x === "string" && x.startsWith("ziel:"));
    return ["ziele", {view: "warnung", zeit: "jahr", ...slPick(c, ["sports", "title", "schwelle", "ausblenden"]), ...(sn.length ? {snoozes: sn} : {})}];
  },
  hnwoche: c => ["ziele", {view: "balken", zeit: "woche", ...slPick(c, ["sports", "title"])}],
  holenknopf: c => ["zeppimport", {view: "knopf", ...slPick(c, ["title"])}],                      // 3.48.0: „Touren holen (nur Knopf)“ ist die Darstellung „Nur Knopf“ von „Touren holen“
  rekorde: c => ["bestwerte", {n: 1, werte: ["km", "hm", "tempo"], ...slPick(c, ["sports", "range", "yr", "eigen", "title"])}],
  sttop: c => ["bestwerte", {n: c.n === 8 ? 10 : [1, 3, 5, 10].includes(c.n) ? c.n : 5, werte: [["km", "hm", "dauer", "tempo"].includes(c.wert) ? c.wert : "km"], ...slPick(c, ["sports", "range", "yr", "eigen", "title"])}],
};
function slAliasW(w) {
  if (!w || typeof w !== "object" || typeof w.type !== "string") return w;
  const c = w.cfg && typeof w.cfg === "object" ? w.cfg : {};
  if (w.type === "hinweise" && ("woche_ziel" in c || "woche_einheit" in c)) {
    const o = {...c};
    delete o.woche_ziel;
    delete o.woche_einheit;
    return {...w, cfg: o};
  }
  const f = SL_ALIAS[w.type];
  if (!f) return w;
  const [type, cfg] = f(c);
  return {...w, type, cfg};
}
const slAliasLay = l => (l && typeof l === "object" && Array.isArray(l.widgets) && l.widgets.some(w => w && (SL_ALIAS[w.type] || (w.type === "hinweise" && w.cfg && "woche_ziel" in w.cfg))) ? {...l, widgets: l.widgets.map(slAliasW)} : l);
/* Gespeichertes (Server, Zwischenspeicher; altes Format = ein Layout-Dokument) als Behälter, unbrauchbares als null */
function slNorm(x) {
  if (!x || typeof x !== "object" || Array.isArray(x)) return null;
  if (!Array.isArray(x.views)) return {v: 2, views: [{id: SL_STD, name: "Standard", layout: slAliasLay(x)}], active: SL_STD, rules: {}};
  const ids = new Set(), views = [];
  x.views.forEach(v => {
    if (v && typeof v.id === "string" && !ids.has(v.id) && views.length < SL_MAXV) {
      ids.add(v.id);
      views.push({id: v.id, name: String(v.name || "Ansicht").slice(0, 40), layout: v.layout && typeof v.layout === "object" ? slAliasLay(v.layout) : {v: 1}});
    }
  });
  if (!views.length) return null;
  const rules = {};
  Object.entries(x.rules || {}).forEach(([k, id]) => ids.has(id) && (rules[k] = id));
  return {v: 2, views, active: ids.has(x.active) ? x.active : views[0].id, rules};
}
const slStore = k => SL.store[k] || (SL.store[k] = slBlank());
const slMaster = fam => slStore(slKeys(fam)[0]);
const slTrivial = st => st.views.length === 1 && st.views[0].id === SL_STD && st.views[0].name === "Standard" && !Object.keys(st.rules || {}).length;
const slLayEmpty = l => !l || !Object.keys(l).some(x => x !== "v");
const slSsKey = fam => "mt_slv_" + slUid() + "_" + fam;
const slManual = fam => {
  if (SL.manual[fam] === undefined) {
    try {
      SL.manual[fam] = sessionStorage.getItem(slSsKey(fam)) || "";
    } catch (e) {
      SL.manual[fam] = "";
    }
  }
  return SL.manual[fam];
};
function slSetManual(fam, id) {
  SL.manual[fam] = id || "";
  try {
    if (id) sessionStorage.setItem(slSsKey(fam), id);
    else sessionStorage.removeItem(slSsKey(fam));
  } catch (e) {}
}
/* Tourseite: die zweite Datei führt dieselben Ansichten wie die erste (Kennungen, Namen, Standard, Regeln); der Inhalt je Schlüssel bleibt eigen */
function slAlign(fam) {
  if (fam !== "tour") return;
  const m = slMaster(fam), s = slStore("tour-auswertung");
  s.views = m.views.map(v => {
    const o = s.views.find(x => x.id === v.id);
    return {id: v.id, name: v.name, layout: o ? o.layout : {v: 1}};
  });
  s.active = m.active;
  s.rules = {...(m.rules || {})};
}
/* Wählt die anzuzeigende Ansicht: von Hand gewählt (diese Sitzung) vor Regel der Sportart vor Standardansicht, und setzt SL.docs auf ihr Layout */
function slResolve(fam, sport) {
  if (sport !== undefined) SL.sport[fam] = sport;
  slAlign(fam);
  const m = slMaster(fam), has = id => !!id && m.views.some(v => v.id === id);
  const man = slManual(fam), rule = fam === "tour" ? (m.rules || {})[SL.sport[fam]] : "";
  const id = has(man) ? man : has(rule) ? rule : has(m.active) ? m.active : m.views[0].id;
  SL.view[fam] = id;
  slKeys(fam).forEach(k => {
    const v = slStore(k).views.find(x => x.id === id), l = v && v.layout;
    if (l && !slLayEmpty(l)) SL.docs[k] = l;
    else delete SL.docs[k];
  });
  return id;
}
const slViewName = (fam, id) => ((slMaster(fam).views.find(v => v.id === id) || {}).name || "");
const slCan = () => !(typeof isViewer === "function" && isViewer());
const slUid = () => {
  try {
    return (ME.user && (ME.user.uid || ME.user.name)) || "_";
  } catch (e) {
    return "_";
  }
};
const slLsKey = k => "mt_sl_" + slUid() + "_" + k;
const slKeys = fam => (fam === "tour" ? ["tour-haupt", "tour-auswertung"] : [fam]);
const slSt = fam => SL.docs[slKey1(fam)] || {};
/* 3.36.0 Handy: Im Bearbeitungsmodus bestimmt der Umschalter „Desktop | Handy“ (SL.dev), sonst die Klasse html.mob (schmaler Bildschirm), welche Anordnung gilt.
   Ohne eigenes „mob“ im Dokument gilt überall die Desktop-Anordnung wie bisher; die Karte hat keine eigene Handy-Anordnung. */
const slMobNow = () => document.documentElement.classList.contains("mob");
const slMobEff = fam => (fam || SL.fam) !== "karte" && (SL.edit ? SL.dev === "mob" : slMobNow());
const slHidList = st => (slMobEff() && st && st.mob && st.mob.hidden ? st.mob.hidden : (st && st.hidden) || []);
const slAlias = id => (id === "met" || id === "uhr" ? "geraet" : id);        // Messwerte und Training laut Uhr bilden einen Block

/* ---------- Abschnitte, Seiten, Reihenfolge ---------- */
const slWTitle = (T, cfg) => ((cfg && cfg.title) || "").trim() || T.title(cfg || {});               // 3.19.0: eigener Titel überschreibt den Standard
const slWFl = (T, cfg) => (T.kurz ? T.kurz(cfg || {}).join(", ") : T.filter ? flPlain(cfg || {}, T.filter.range) : "");
const slSig = it => JSON.stringify(it.cfg || {});
function slItems(fam) {
  const st = slSt(fam),
    items = SL_REG[fam].map(r => ({...r})),
    pg = st.page || {};
  items.forEach(it => {
    const T = it.build && window.SL_WT[it.build];                          // 3.19.0: Standard-Baustein („Dein Jahr“) mit Konfiguration unter „cfg“ im Dokument
    if (!T) return;
    it.wtype = it.build;
    it.cfg = {...(it.defcfg || {}), ...((st.cfg || {})[it.id] || {})};          // 3.62.0: defcfg = Vorgabe des Abschnitts, solange nichts gespeichert ist
    it.title = slWTitle(T, it.cfg);
    it.fl = slWFl(T, it.cfg);
  });
  (st.widgets || []).forEach(w => {
    const T = window.SL_WT[w.type];
    if (!slFits(T, fam)) return;                                          // unbekannter Baustein (z. B. von einer neueren Version) oder einer, der auf dieser Seite nicht stehen darf: ignorieren
    items.push({id: w.id, w: slTypeW(T), ws: T.ws, title: slWTitle(T, w.cfg || {}), fl: slWFl(T, w.cfg || {}), page: fam === "tour" ? "haupt" : fam, group: fam === "tour" ? "bst" : "", widget: true, plain: !!T.shell, wtype: w.type, cfg: w.cfg || {}, def: true, ckeys: ["tl_w_" + w.id]});
  });
  if (fam === "statistik" && typeof stApply === "function") items.forEach(it => it.wtype && stApply(it));          // 3.22.0: globaler Filter der Statistikseite
  else if (fam === "uebersicht" && typeof zrApplyAll === "function") zrApplyAll(items);                         // 3.34.0: Zeitraum der Seite (65-zeitraum.js)
  if (fam === "tour") items.forEach(it => !it.fixed && (pg[it.id] === "haupt" || pg[it.id] === "auswertung") && (it.page = pg[it.id]));
  items.forEach(it => {                                                   // 3.20.0: Breite = gespeicherte Abweichung, sonst Standard (immer eine der erlaubten)
    const ws = it.ws || SL_WALL, v = (st.w || {})[it.id];
    it.w = it.w && ws.includes(it.w) ? it.w : ws[0];
    it.cw = ws.includes(v) ? v : it.w;
  });
  return items;
}
/* Reihenfolge einer Seite: gespeicherte Ids (bekannte), Fehlende an ihrer Standardposition (hinter dem nächsten davor liegenden, schon eingeordneten Standard-Abschnitt) */
function slOrder(fam, page, desk) {
  const mine = slItems(fam).filter(i => i.page === page),
    ids = mine.map(i => i.id),
    doc = SL.docs[SL_PAGE_KEY[page]] || {},
    eff = [];
  (!desk && slMobEff(fam) && doc.mob && doc.mob.order ? doc.mob.order : doc.order || []).forEach(id => ids.includes(id) && !eff.includes(id) && eff.push(id));
  mine.forEach((it, idx) => {
    if (eff.includes(it.id)) return;
    let at = 0;
    for (let j = idx - 1; j >= 0; j--) {
      const p = eff.indexOf(mine[j].id);
      if (p >= 0) {
        at = p + 1;
        break;
      }
    }
    eff.splice(at, 0, it.id);
  });
  return eff.map(id => mine.find(i => i.id === id));
}
/* Schnittstelle für 48-tourlayout.js */
const slOn = (id, page) => {
  const it = slItems("tour").find(i => i.id === slAlias(id));
  return !it || it.page === page;
};
const slHid = id => slHidList(slSt("tour")).includes(slAlias(id));
function slDef(id, d) {
  const st = slSt(SL.fam),
    a = slAlias(id);
  return (st.open || []).includes(a) ? true : (st.closed || []).includes(a) ? false : d;
}

/* ---------- Laden, Zwischenspeicher, Speichern ---------- */
const slReadCache = k => {
  try {
    const v = localStorage.getItem(slLsKey(k));
    return v ? JSON.parse(v) : null;
  } catch (e) {
    return null;
  }
};
const slWriteCache = (k, d) => {
  try {
    if (d) localStorage.setItem(slLsKey(k), JSON.stringify(d));
    else localStorage.removeItem(slLsKey(k));
  } catch (e) {}
};
async function slFetch(k) {
  const r = await fetch("/api/layout/" + k, {credentials: "same-origin"});
  if (!r.ok) throw new Error(String(r.status));
  const j = await r.json();
  return slNorm(j && j.container);
}
/* Beim ersten Aufruf: Zwischenspeicher dieses Geräts sofort nutzen und im Hintergrund abgleichen; ohne Zwischenspeicher höchstens 1,5 s auf den Server warten (nie blockieren) */
async function slEnsure(fam) {
  const keys = slKeys(fam);
  if (!slCan()) {
    keys.forEach(k => {
      delete SL.docs[k];
      delete SL.store[k];
    });
    return;
  }
  const first = !SL.loaded[fam];
  if (first)
    keys.forEach(k => {
      const c = slNorm(slReadCache(k));
      if (c) SL.store[k] = c;
    });
  const rev0 = keys.map(k => (SL.dirty.has(k) || SL.busy.has(k) ? -1 : SL.rev[k] || 0));            // -1: beim Start der Abfrage war schon etwas ungespeichert, die Antwort kann veraltet sein
  const pull = Promise.all(keys.map((k, i) => slFetch(k).then(d => ((SL.rev[k] || 0) === rev0[i] ? [k, d] : null)).catch(() => null))).then(rs => {
    let changed = false;
    rs.forEach(r => {
      if (!r || SL.dirty.has(r[0]) || SL.busy.has(r[0])) return;                // eigene, noch nicht (vollständig) gespeicherte Änderungen nie überschreiben
      const [k, d] = r;
      if (JSON.stringify(d || slBlank()) !== JSON.stringify(SL.store[k] || slBlank())) {
        if (d) SL.store[k] = d;
        else delete SL.store[k];
        slWriteCache(k, d);
        changed = true;
      }
    });
    if (changed) slResolve(fam);
    return changed;
  });
  SL.loaded[fam] = true;
  if (first && !keys.some(k => SL.store[k])) await Promise.race([pull, new Promise(r => setTimeout(r, 1500))]);
  else pull.then(ch => ch && SL.fam === fam && slApply());
}
function slStatus(text, bad) {
  const s = document.getElementById("slsaved");
  if (!s) return;
  s.textContent = text;
  s.dataset.state = bad ? "bad" : text === "Ansicht gespeichert" ? "ok" : "busy";
}
/* Layout der angezeigten Ansicht in den Behälter übernehmen (vor dem Speichern und vor jeder Änderung der Ansichten) */
function slSync(k) {
  const fam = slFamOf(k), v = slStore(k).views.find(x => x.id === SL.view[fam]);
  if (v) v.layout = SL.docs[k] || {};                       // {} (ohne „v“) = nichts gespeichert (Standard wiederhergestellt): bei unveränderter Standardansicht wird das Dokument gelöscht
}
/* Was auf den Server geht: unveränderter Standard = wie bisher das Layout-Dokument selbst (oder löschen, wenn leer), sonst der Behälter */
function slPack(k) {
  const st = slStore(k);
  if (slTrivial(st)) return st.views[0].layout && Object.keys(st.views[0].layout).length ? st.views[0].layout : null;
  return {v: 2, views: st.views, active: st.active, rules: st.rules || {}};
}
function slTouch(...keys) {
  if (SL.edit && typeof slHistPush === "function") slHistPush(keys);
  keys.forEach(k => {
    slSync(k);
    SL.dirty.add(k);
    SL.rev[k] = (SL.rev[k] || 0) + 1;
    slWriteCache(k, slStore(k));
  });
  slStatus("Ansicht wird gespeichert …");
  slChg();
  clearTimeout(SL.timer);
  SL.timer = setTimeout(slFlush, 500);
}
async function slFlush() {
  clearTimeout(SL.timer);
  const keys = [...SL.dirty];
  SL.dirty.clear();
  if (!keys.length) return true;
  let ok = true;
  keys.forEach(k => SL.busy.add(k));
  for (const k of keys) {
    try {
      const d = slPack(k),
        r = await fetch("/api/layout/" + k, d ? {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(d), credentials: "same-origin"} : {method: "DELETE", credentials: "same-origin"});
      if (!r.ok) throw new Error(String(r.status));
    } catch (e) {
      ok = false;
    }
    SL.busy.delete(k);
  }
  if (SL.dirty.size) return ok;                                           // inzwischen weitere Änderungen: der nächste Lauf meldet
  slStatus(ok ? "Ansicht gespeichert" : "Speichern nicht möglich: nur auf diesem Gerät gemerkt", !ok);
  return ok;
}
const slDocOf = page => SL.docs[SL_PAGE_KEY[page]] || (SL.docs[SL_PAGE_KEY[page]] = {v: 1});
const slStDoc = fam => slDocOf(fam === "tour" ? "haupt" : fam);
/* 3.31.0 Schnell-Knopf „Touren holen“ in der Kopfzeile der Übersicht: Standard an; abgeschaltet steht {kopf: {holen: false}} im Layout-Dokument (gehört damit zur Ansicht) */
const slHolenOn = () => {
  const d = SL.docs[SL_PAGE_KEY.uebersicht];
  return !(d && d.kopf && d.kopf.holen === false);
};
function slSetHolen(on) {
  const st = slDocOf("uebersicht");
  if (on) delete st.kopf;
  else st.kopf = {holen: false};
  slTouch(SL_PAGE_KEY.uebersicht);
  slApply();
  slLive(on ? "Schnell-Knopf zum Touren holen: an" : "Schnell-Knopf zum Touren holen: aus");
}
/* 3.37.2 Schalter „Zeitraum der Seite anzeigen“ (Layout-Feld zrbar, Standard aus; nur die Abweichung steht im Dokument). Gilt ein Zeitraum (Adresse, zuletzt gewählt, Ansicht), ist die Leiste ohnehin sichtbar: der Schalter steht dann an und ist gesperrt. */
function slSetZr(on) {
  const st = slDocOf("uebersicht");
  if (on) st.zrbar = true;
  else {
    delete st.zrbar;
    if (typeof ZR !== "undefined") ZR.sess.uebersicht = false;
  }
  slTouch(SL_PAGE_KEY.uebersicht);
  slApply();
  slLive(on ? "Zeitraum der Seite: Leiste eingeblendet" : "Zeitraum der Seite: Leiste ausgeblendet");
}
function slKopfSync() {
  const l = document.getElementById("slkopf"), w = document.getElementById("slsw");
  if (!l) return;
  l.hidden = SL.fam !== "uebersicht";
  if (w) w.hidden = l.hidden;
  const i = l.querySelector("input");
  if (i) i.checked = slHolenOn();
  const z = document.getElementById("slzrin");
  if (z && typeof zrOn === "function") {
    const f = !!ZR.F.uebersicht;
    z.checked = zrOn("uebersicht");
    z.disabled = f;
    const n = document.getElementById("slzrnote");
    if (n) n.hidden = !f;
  }
  slBarH();
}
const slSet = (st, name, id, on) => {
  const a = (st[name] || []).filter(x => x !== id);
  if (on) a.push(id);
  if (a.length) st[name] = a;
  else delete st[name];
};

/* ---------- Änderungen (Bearbeitungsmodus) ---------- */
const slLive = t => {
  if (SL.hlast && !SL.hlast.l) SL.hlast.l = t;                              // 3.36.0: der Verlauf (Rückgängig/Wiederholen) benennt den Schritt mit der Ansage der Änderung
  const l = document.getElementById("sllive");
  if (l) {
    l.textContent = "";
    setTimeout(() => (l.textContent = t), 30);
  }
};
const slTitle = id => {
  const it = slItems(SL.fam).find(i => i.id === id);
  return it ? it.title : id;
};
function slSaveOrder(ids) {
  const d = slDocOf(SL.page);
  if (slMobEff()) (d.mob = d.mob || {}).order = ids;                       // 3.36.0: auf dem Handy-Reiter nur die Handy-Reihenfolge ändern
  else d.order = ids;
  slTouch(SL_PAGE_KEY[SL.page]);
}
/* grp: undefined = Gruppen unverändert (Tastatur), null = ohne Gruppe, sonst Kennung der Gruppe (Ziehen: Zeiger über der Gruppe); beforeId null = ans Ende (der Gruppe) */
function slMove(id, beforeId, grp) {
  const old = slOrder(SL.fam, SL.page).map(i => i.id),
    cur = old.filter(x => x !== id);
  let at = beforeId ? cur.indexOf(beforeId) : -1;
  if (grp && !beforeId) {
    const m = cur.map((x, i) => (slGrpHas(grp, x) ? i : -1)).filter(i => i >= 0);
    at = m.length ? m[m.length - 1] + 1 : -1;
    if (at >= cur.length) at = -1;
  }
  if (at < 0) cur.push(id);
  else cur.splice(at, 0, id);
  const gch = grp !== undefined && slGrpSet(id, grp || null);
  if (!gch && cur.join() === old.join()) return;                           // nichts geändert
  slSaveOrder(cur);
  slApply();
  const n = cur.length, g = slGrpOf(id);
  slLive(`${slTitle(id)}: Position ${cur.indexOf(id) + 1} von ${n}` + (gch ? (g ? `, in Bausteingruppe „${slGrpName(g)}“` : ", ohne Bausteingruppe") : ""));
}
function slStep(id, d) {
  const ord = SL.present.length ? SL.present.slice() : slOrder(SL.fam, SL.page).map(i => i.id),
    i = ord.indexOf(id),
    j = i + d,
    g = slGrpOf(id);
  if (i < 0) return;
  if (g && (j < 0 || j >= ord.length || !g.ids.includes(ord[j]))) {          // Rand der Gruppe: der Baustein verlässt sie an Ort und Stelle
    slGrpSet(id, null);
    slSaveOrder(slOrder(SL.fam, SL.page).map(x => x.id));
    slApply();
    slLive(`${slTitle(id)}: aus der Bausteingruppe „${slGrpName(g)}“ gelöst`);
    return;
  }
  if (j < 0 || j >= ord.length) {
    slLive(`${slTitle(id)}: ${d < 0 ? "ganz oben" : "ganz unten"}`);
    return;
  }
  const o = !g && slGrpOf(ord[j]);                                         // eine ganze Gruppe zählt als ein Schritt
  if (o) {
    const idx = o.ids.map(x => ord.indexOf(x)).filter(x => x >= 0);
    if (d < 0) slMove(id, ord[Math.min(...idx)], null);
    else slMove(id, ord[Math.max(...idx) + 1] || null, null);
    return;
  }
  if (d < 0) slMove(id, ord[j], g ? g.id : undefined);
  else slMove(id, ord[j + 1] || null, g ? g.id : undefined);
}
function slToggleHidden(id) {
  const st = slStDoc(SL.fam),
    on = !slHidList(st).includes(id);
  if (slMobEff()) {                                                         // 3.36.0: Handy-Reiter: eigene Liste der ausgeblendeten Abschnitte (Start: Kopie der Desktop-Liste)
    const m = (st.mob = st.mob || {}), l = (m.hidden || st.hidden || []).filter(x => x !== id);
    if (on) l.push(id);
    m.hidden = l;
  } else slSet(st, "hidden", id, on);
  slTouch(slKey1(SL.fam));
  slApply();
  slLive(on ? `${slTitle(id)}: ausgeblendet` : `${slTitle(id)}: eingeblendet`);
}
/* Zustand „offen/zu“ eines gebauten Abschnitts setzen (auch für Rückgängig/Wiederholen) */
function slOpenDom(it, on) {
  (it.ckeys || []).forEach(k => {
    try {
      localStorage.removeItem("mt_trf_" + k);                               // sonst überstimmt der zuletzt gemerkte Zustand den neuen Standard
    } catch (e) {}
  });
  const secs = it.id === "geraet" ? ["met", "uhr"] : [it.id];
  secs.forEach(s => {
    const d = tlSec(s) || document.querySelector(`#tls-${s}`);
    if (d && d.tagName === "DETAILS") d.open = on;
  });
}
function slSetOpen(id, on) {
  const it = slItems(SL.fam).find(i => i.id === id);
  if (!it) return;
  const st = slStDoc(SL.fam);
  slSet(st, "open", id, on && !it.def);                                     // nur Abweichungen vom Standard speichern
  slSet(st, "closed", id, !on && !!it.def);
  slTouch(slKey1(SL.fam));
  slOpenDom(it, on);
  slLive(`${it.title}: ${on ? "standardmäßig offen" : "standardmäßig zu"}`);
}
function slSetPage(id, page) {
  if (SL.fam !== "tour") return;
  const it = slItems("tour").find(i => i.id === id);
  if (!it || it.fixed) return;
  const from = SL.page,
    fromIds = slOrder("tour", from, true).map(i => i.id).filter(x => x !== id),
    st = slStDoc("tour");
  st.page = st.page || {};
  if (!it.widget && page === SL_REG.tour.find(r => r.id === id).page) delete st.page[id];
  else st.page[id] = page;
  if (!Object.keys(st.page).length) delete st.page;
  slDocOf(from).order = fromIds;
  const toIds = slOrder("tour", page, true).map(i => i.id).filter(x => x !== id);
  toIds.push(id);
  slDocOf(page).order = toIds;
  slGrpSet(id, null);                                                       // 3.36.0: eine Gruppe gehört zu einer Seite
  ["haupt", "auswertung"].forEach(pg => {
    const d = SL.docs[SL_PAGE_KEY[pg]];
    if (d && d.mob && d.mob.order) d.mob.order = d.mob.order.filter(x => x !== id);
  });
  slTouch("tour-haupt", "tour-auswertung");
  SL.focus = null;
  slApply();
  slLive(page === "haupt" ? `${it.title}: liegt jetzt auf der Hauptseite` : `${it.title}: liegt jetzt auf der Auswertungsseite`);
}
function slSetWidth(id, w) {
  const it = slItems(SL.fam).find(i => i.id === id);
  if (!it || !(it.ws || SL_WALL).includes(w)) return;
  const st = slStDoc(SL.fam);
  st.w = st.w || {};
  if (w === it.w) delete st.w[id];                                        // nur Abweichungen vom Standard speichern
  else st.w[id] = w;
  if (!Object.keys(st.w).length) delete st.w;
  slTouch(slKey1(SL.fam));
  SL.focus = {id, a: "w", q: `[data-w="${w}"]`};
  slApply();
  slLive(`${slTitle(id)}: ${SL_WNAME[w]}`);
}
/* cfg = fertige Einstellung (3.28.0: eigene Kennzahl), after = Kennung, hinter der der neue Baustein steht (Duplizieren); T.grenze() liefert eine Meldung, wenn der Typ nicht noch einmal hinzugefügt werden darf */
function slAddWidget(type, cfg, after) {
  const T = window.SL_WT[type];
  if (!slFits(T, SL.fam)) return null;
  const st = slStDoc(SL.fam);
  if ((st.widgets || []).length >= 40) {
    uiAlert("Es sind höchstens 40 Bausteine möglich.");
    return null;
  }
  const lim = T.grenze && T.grenze();
  if (lim) {
    uiAlert(lim);
    return null;
  }
  let id;
  do id = "w" + Math.random().toString(36).slice(2, 7);
  while ((st.widgets || []).some(w => w.id === id));
  st.widgets = (st.widgets || []).concat([{id, type, cfg: JSON.parse(JSON.stringify(cfg || T.defaults || {}))}]);
  if (SL.fam === "tour" && SL.page === "auswertung") (st.page = st.page || {})[id] = "auswertung";
  const ids = slOrder(SL.fam, SL.page).map(i => i.id).filter(x => x !== id);
  if (after && ids.includes(after)) ids.splice(ids.indexOf(after) + 1, 0, id);
  else ids.push(id);
  if (after) slGrpLike(id, after);                                           // 3.36.0: die Kopie steht in derselben Gruppe wie das Original
  slSaveOrder(ids);
  slTouch(slKey1(SL.fam));
  SL.focus = {id, a: "grip"};
  slApply();
  slLive(`Baustein „${T.title(cfg || T.defaults || {})}“ hinzugefügt`);
  return id;
}
/* 3.36.0 Baustein duplizieren: nur Bausteine, die mehrfach vorkommen dürfen (Typ-Merkmal „multi“, die Eigene Kennzahl hat ihr eigenes „dup“): gleiche Einstellung, neue Kennung,
   Titel „… (Kopie)“, direkt hinter dem Original (und in dessen Gruppe); der Fokus springt auf die Kopie (slAddWidget). */
const slCanDup = T => !!T && !!(T.multi || T.dup);
function slDupWidget(id) {
  const w = slWidgetOf(id), T = w && w.widget && window.SL_WT[w.type];
  if (!slCanDup(T)) return;
  const cfg = JSON.parse(JSON.stringify(w.cfg || {}));
  if (T.dup) return slAddWidget(w.type, T.dup(cfg), id);
  const tl = x => (typeof window.TL === "function" ? window.TL(x) : x);
  cfg.title = `${slWTitle(T, cfg).slice(0, 40)} (${tl("Kopie")})`.slice(0, 60);
  return slAddWidget(w.type, cfg, id);
}
function slRemoveWidget(id) {
  const st = slStDoc(SL.fam), nm = slTitle(id);
  st.widgets = (st.widgets || []).filter(w => w.id !== id);
  if (!st.widgets.length) delete st.widgets;
  ["hidden", "open", "closed"].forEach(n => slSet(st, n, id, false));
  if (st.w) {
    delete st.w[id];
    if (!Object.keys(st.w).length) delete st.w;
  }
  if (st.page) {
    delete st.page[id];
    if (!Object.keys(st.page).length) delete st.page;
  }
  slKeys(SL.fam).forEach(k => {
    const d = SL.docs[k];
    if (!d) return;
    if (d.order) d.order = d.order.filter(x => x !== id);
    if (d.mob) {
      ["order", "hidden"].forEach(n => d.mob[n] && (d.mob[n] = d.mob[n].filter(x => x !== id)));
      if (!Object.keys(d.mob).length) delete d.mob;
    }
  });
  slGrpDrop(id);
  slTouch(...slKeys(SL.fam));
  const el = document.getElementById("tlw-" + id);
  if (el) el.remove();
  SL.focus = null;
  slApply();
  slLive(`Baustein „${nm}“ entfernt`);
}
/* Baustein zu einer Kennung: hinzugefügter Baustein oder Standard-Baustein mit Konfiguration (cfg[id]) */
function slWidgetOf(id) {
  const st = slSt(SL.fam), w = (st.widgets || []).find(x => x.id === id);
  if (w) return {id, type: w.type, cfg: w.cfg || {}, widget: true};
  const r = SL_REG[SL.fam].find(x => x.id === id && x.build);
  return r ? {id, type: r.build, cfg: {...(r.defcfg || {}), ...((st.cfg || {})[id] || {})}} : null;
}
function slSetCfg(id, cfg) {
  const st = slStDoc(SL.fam),
    w = (st.widgets || []).find(x => x.id === id);
  if (w) w.cfg = cfg;
  else if (SL_REG[SL.fam].some(x => x.id === id && x.build)) {
    st.cfg = st.cfg || {};
    if (Object.keys(cfg).length) st.cfg[id] = cfg;
    else delete st.cfg[id];                                               // leere Konfiguration = Standard: nichts speichern
    if (!Object.keys(st.cfg).length) delete st.cfg;
  } else return;
  slTouch(slKey1(SL.fam));
  const el = document.getElementById("tlw-" + id);
  if (el) el.remove();                                                      // wird mit der neuen Konfiguration neu gebaut
  SL.focus = {id, a: "cfg"};
  slApply();
  slLive(`${slTitle(id)}: Einstellungen geändert`);
}
/* „Verwerfen“: stellt den Stand von vor dem Bearbeiten wieder her (Behälter, Zwischenspeicher dieses Geräts und Server) */
async function slDiscard() {
  const fam = SL.fam;
  if (!SL.snap || SL.snap.fam !== fam) return;
  if (!slIsChg()) return slLive("Keine Änderungen seit Beginn des Bearbeitens");
  const ok = await uiConfirm({title: "Änderungen verwerfen?", text: "Die Seite wird auf den Stand von vor dem Bearbeiten zurückgesetzt. Alles, was du seitdem geändert hast, geht verloren.", ok: "Verwerfen", danger: true});
  if (!ok || !SL.snap) return;
  const snap = SL.snap, was = SL.view[fam];
  slKeys(fam).forEach(k => (SL.store[k] = JSON.parse(snap.st[k])));
  slSetManual(fam, snap.manual);
  slResolve(fam);
  document.querySelectorAll(".tlw[data-wid]").forEach(e => e.remove());
  slTouch(...slKeys(fam));
  SL.focus = null;
  slApply();
  slChg();
  slStatus("Verworfen");
  slHistReset();
  slLive("Änderungen verworfen, der Stand von vor dem Bearbeiten ist wiederhergestellt");
  if (fam === "statistik" && SL.view[fam] !== was && typeof stReload === "function") stReload();
}
async function slReset() {
  const ok = await uiConfirm({
    title: "Standard wiederherstellen?",
    text: slMaster(SL.fam).views.length > 1
      ? "Alles in dieser Ansicht wird auf den Standard zurückgesetzt: Reihenfolge, ausgeblendete und alle hinzugefügten Bausteine. Andere Ansichten bleiben unverändert."
      : SL.fam === "tour"
      ? "Reihenfolge, ausgeblendete Bausteine, Seitenzuordnung und alle hinzugefügten Bausteine der Tourseite (Hauptseite und Auswertung) werden zurückgesetzt."
      : SL.fam === "statistik"
      ? "Reihenfolge, Breiten, ausgeblendete und alle hinzugefügten Bausteine der Statistik werden zurückgesetzt. Der Filter oben bleibt, wie er ist."
      : SL.fam === "reise"
      ? "Reihenfolge, Breiten, ausgeblendete und alle hinzugefügten Bausteine der Reise-Seite werden zurückgesetzt. Das gilt für alle Reisen."
      : SL.fam === "serie"
      ? "Reihenfolge, Breiten, ausgeblendete und alle hinzugefügten Bausteine der Mehrtagestour-Seite werden zurückgesetzt. Das gilt für alle Mehrtagestouren."
      : SL.fam === "gebiete"
      ? "Reihenfolge, Breiten, ausgeblendete und alle hinzugefügten Bausteine der Gebiete-Übersicht werden zurückgesetzt."
      : SL.fam === "gebiet"
      ? "Reihenfolge, Breiten, ausgeblendete und alle hinzugefügten Bausteine der Gebiets-Seite werden zurückgesetzt. Das gilt für alle Gebiete."
      : SL.fam === "reisen"
      ? "Reihenfolge, Breiten, ausgeblendete und alle hinzugefügten Bausteine der Reisen-Übersicht werden zurückgesetzt."
      : SL.fam === "fotos"
      ? "Reihenfolge, Breiten, ausgeblendete und alle hinzugefügten Bausteine der Fotos-Seite werden zurückgesetzt."
      : SL.fam === "karte"
      ? "Reihenfolge, Breite der Karte, ausgeblendete Bedienfelder und alle hinzugefügten Bausteine der Karte werden zurückgesetzt."
      : "Reihenfolge, ausgeblendete und alle hinzugefügten Bausteine der Übersicht werden zurückgesetzt.",
    ok: "Standard wiederherstellen",
    danger: true,
  });
  if (!ok) return;
  slKeys(SL.fam).forEach(k => delete SL.docs[k]);
  slItems(SL.fam).forEach(it => (it.ckeys || []).forEach(k => {
    try {
      localStorage.removeItem("mt_trf_" + k);
    } catch (e) {}
  }));
  document.querySelectorAll(".tlw[data-wid]").forEach(e => e.remove());
  slTouch(...slKeys(SL.fam));
  SL.focus = null;
  slApply();
  slLive("Standard wiederhergestellt");
  slStatus("Standard wiederhergestellt");
}

/* ---------- Einordnen ---------- */
function slPlaceIn(parent, els) {
  let ref = parent.firstElementChild;
  while (ref && ref.classList.contains("warnbar")) ref = ref.nextElementSibling;
  for (const el of els.filter(Boolean)) {
    if (el === ref) ref = ref.nextElementSibling;
    else parent.insertBefore(el, ref);
  }
}
function slRun(root, fam, g, n) {
  const sfx = n > 1 ? "-" + n : "";
  if (fam === "tour") {
    const id = "tlg-" + g + sfx;
    let el = document.getElementById(id);
    if (!el) {
      root.insertAdjacentHTML("beforeend", `<section class="tlg" id="${id}" aria-labelledby="tlgh-${g}${sfx}"><h2 class="tlgh" id="tlgh-${g}${sfx}">${SL_GROUPS[g]}</h2><div class="tlgb" id="tlgb-${g}${sfx}"></div></section>`);
      el = document.getElementById(id);
    }
    return {el, body: document.getElementById("tlgb-" + g + sfx)};
  }
  const id = "hcols" + sfx;
  let el = document.getElementById(id);
  if (!el) {
    root.insertAdjacentHTML("beforeend", `<div class="hcols" id="${id}"></div>`);
    el = document.getElementById(id);
  }
  return {el, body: el};
}
const slSelfHidden = (it, el) => {
  if (SL.fam !== "tour") return false;
  if (it.id === "geraet") return !el.querySelector(".tldev");
  if (it.id === "sum") return el.hidden;
  return el.hidden || (el.firstElementChild && el.firstElementChild.hidden);
};
/* Rahmen eines Abschnitts im Bearbeitungsmodus (sonst steht der Abschnitt ohne Rahmen im Seiteninhalt) */
function slUnit(p, edit) {
  const el = p.el,
    par = el.parentElement,
    w = par && par.classList.contains("slit") && par.dataset.sl === p.it.id ? par : null;
  if (!edit) {
    if (w) {
      w.parentNode.insertBefore(el, w);
      w.remove();
    }
    return el;
  }
  if (w) return w;
  const nw = document.createElement("div");
  nw.className = "slit";
  nw.dataset.sl = p.it.id;
  if (par) par.insertBefore(nw, el);
  nw.appendChild(el);
  return nw;
}
const slIcon = {
  grip: '<svg class="sli" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="9" cy="6" r="1.8"/><circle cx="15" cy="6" r="1.8"/><circle cx="9" cy="12" r="1.8"/><circle cx="15" cy="12" r="1.8"/><circle cx="9" cy="18" r="1.8"/><circle cx="15" cy="18" r="1.8"/></svg>',
  eye: '<svg class="sli" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M2 12s3.7-6.5 10-6.5S22 12 22 12s-3.7 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  eyeoff: '<svg class="sli" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M3 3l18 18M10.6 5.7A10 10 0 0 1 12 5.5c6.3 0 10 6.5 10 6.5a17 17 0 0 1-3.2 3.9M6.4 7.4A16.5 16.5 0 0 0 2 12s3.7 6.5 10 6.5c1.5 0 2.8-.3 4-.8"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>',
  gear: '<svg class="sli" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  sliders: '<svg class="sli" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2.2"/><circle cx="9" cy="17" r="2.2"/></svg>',
  layers: '<svg class="sli" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3.5l8.5 4.5-8.5 4.5L3.5 8z"/><path d="M3.5 12.5l8.5 4.5 8.5-4.5"/></svg>',
};
/* Symbol der Breite: Rahmen = ganze Zeile, Füllung = Anteil */
const slWIcon = k => `<svg viewBox="0 0 24 14" aria-hidden="true" focusable="false"><rect class="wb" x=".65" y=".65" width="22.7" height="12.7" rx="2.5"/><rect class="wf" x="2" y="2" width="${((SL_W.d[k] / 12) * 20).toFixed(1)}" height="10" rx="1.5"/></svg>`;
/* Breite eines Abschnitts als Klasse am Rasterelement (Rahmen im Bearbeitungsmodus, sonst der Abschnitt selbst) */
function slCell(p, on) {
  const u = p.unit;
  if (u !== p.el) p.el.classList.remove("slcell", ...SL_WCLS);
  SL_WCLS.forEach(c => u.classList.toggle(c, on && c === "w-" + p.cw));
  u.classList.toggle("slcell", on);
  if (on) u.dataset.cw = p.cw;
  else delete u.dataset.cw;
}
/* Zeilenreste auffüllen: Die Reihenfolge ist die des Dokuments (kein „dense“, Tab-Reihenfolge = sichtbare Reihenfolge). Passt das nächste Element nicht mehr in die Zeile, wird die Zeile
   geschlossen; was dann frei bleibt, bekommt gleichmäßig die jeweils schmalste Kachel (Standardfall: eine einzelne halbe Kachel wird zur ganzen Zeile). Zwei Rechnungen: Desktop und Tablet. */
function slFillRows(cws, tier) {
  const sp = cws.map(c => SL_W[tier][c]), out = sp.slice();
  let row = [], acc = 0;
  const close = () => {
    let rem = 12 - acc;
    while (rem > 0 && row.length) {
      let m = row[0];
      row.forEach(i => out[i] <= out[m] && (m = i));
      out[m]++;
      rem--;
    }
    row = [];
    acc = 0;
  };
  cws.forEach((c, i) => {
    if (acc + sp[i] > 12) close();
    row.push(i);
    acc += sp[i];
  });
  close();
  return {out, base: sp};
}
const slFillSet = (c, pre, n) => {
  const want = n ? pre + "-" + n : "";
  [...c.classList].forEach(k => k.startsWith(pre + "-") && k !== want && c.classList.remove(k));
  if (want && !c.classList.contains(want)) c.classList.add(want);
};
const SL_CELLOBS = typeof MutationObserver === "function" ? new MutationObserver(() => !SL.drag && slRasterSoon()) : null;
let SL_RAF = 0;
function slRasterSoon() {
  if (SL_RAF) return;
  SL_RAF = requestAnimationFrame(() => {
    SL_RAF = 0;
    slRaster();
  });
}
function slRaster() {
  const grids = new Map();
  document.querySelectorAll("#main .slcell").forEach(c => {
    if (SL_CELLOBS) SL_CELLOBS.observe(c, {attributes: true, attributeFilter: ["hidden", "style"]});         // erscheint ein Abschnitt später (Daten geladen), wird neu aufgefüllt
    let g = c.parentElement;
    if (g && g.classList.contains("hcols")) g = g.parentElement;
    if (!g) return;
    if (getComputedStyle(c).display === "none") {
      slFillSet(c, "fd", 0);
      slFillSet(c, "ft", 0);
      return;
    }
    if (!grids.has(g)) grids.set(g, []);
    grids.get(g).push(c);
  });
  grids.forEach(list => {
    const cws = list.map(c => c.dataset.cw || "voll");
    [["d", "fd"], ["t", "ft"]].forEach(([tier, pre]) => {
      const {out, base} = slFillRows(cws, tier);
      list.forEach((c, i) => slFillSet(c, pre, out[i] > base[i] ? out[i] : 0));
    });
  });
}
/* Ändert sich die Breite der Karte (anderes Raster, Fenstergröße, Bearbeitungsmodus), muss Leaflet seine Größe neu bestimmen */
function slWatchMap() {
  const m = typeof tlSec === "function" && tlSec("map");
  if (!m || m.dataset.slro || typeof ResizeObserver !== "function") return;
  m.dataset.slro = "1";
  let w0 = -1, raf = 0;
  new ResizeObserver(es => {
    const w = Math.round(es[0].contentRect.width);
    if (w === w0) return;
    w0 = w;
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      if (typeof map === "undefined" || !map || !map.invalidateSize) return;               // „map“ ist eine globale Variable (01-grundlagen.js), keine Eigenschaft von window
      map.invalidateSize();
      if (map._tlStale && map._tlFit && m.open) {
        map._tlStale = false;
        map._tlFit();
      }
    });
  }).observe(m);
}
function slStripHtml(p, idx, n) {
  const it = p.it,
    nm = esc(it.title),
    other = SL.page === "haupt" ? "Auf Auswertungsseite" : "Auf Hauptseite",
    dis = (c, e) => (c ? ' aria-disabled="true"' : "") + (e || ""),
    open = slDef(it.id, !!it.def);
  let h = `<button type="button" class="slgrip" data-a="grip" aria-label="Zum Verschieben ziehen, oder Pfeil hoch und Pfeil runter drücken" aria-describedby="slhint">${slIcon.grip}</button>`;
  h += `<span class="slnm" title="${nm}">${nm}${it.fl ? ` <small class="slfl mut">${esc(it.fl)}</small>` : ""}</span>`;
  if (p.off) h += `<span class="slhid">ausgeblendet</span>`;
  h += `<span class="slbs">`;
  if ((it.ws || SL_WALL).length > 1) h += `<span class="slwd" role="group" aria-label="Breite">${(it.ws || SL_WALL).map(k => `<button type="button" class="slw" data-a="w" data-w="${k}" aria-pressed="${k === p.cw}" aria-label="${SL_WNAME[k]}" title="${SL_WNAME[k]}">${slWIcon(k)}</button>`).join("")}</span>`;
  h += `<button type="button" class="slb" data-a="up" aria-label="Nach oben" title="Nach oben"${dis(idx === 0)}>↑</button>`;
  h += `<button type="button" class="slb" data-a="down" aria-label="Nach unten" title="Nach unten"${dis(idx === n - 1)}>↓</button>`;
  if (!it.must) h += `<button type="button" class="slb" data-a="eye" aria-pressed="${p.off}" title="${p.off ? "Einblenden" : "Ausblenden"}">${p.off ? slIcon.eyeoff : slIcon.eye}<span>${p.off ? "Einblenden" : "Ausblenden"}</span></button>`;
  let mo = "";
  if (!it.plain) mo += `<label class="slsw"><input type="checkbox" data-a="open"${open ? " checked" : ""}><span>Standardmäßig offen</span></label>`;
  if (SL.fam === "tour" && !it.fixed) mo += `<button type="button" class="slb" data-a="page" >${other}</button>`;
  if ((it.widget || it.build) && slFieldsOf(window.SL_WT[it.wtype]).length) mo += `<button type="button" class="slb slcfgb" data-a="cfg" aria-haspopup="dialog" title="Einstellungen dieses Bausteins">${slIcon.gear}<span>Einstellungen</span></button>`;
  if (it.widget && slCanDup(window.SL_WT[it.wtype])) mo += `<button type="button" class="slb slmx" data-a="dup" aria-label="Duplizieren: ${nm}" title="Eine Kopie mit denselben Einstellungen direkt dahinter anlegen">Duplizieren</button>`;
  if (slGrpOk(it)) mo += `<button type="button" class="slb slmx" data-a="grp" aria-haspopup="dialog">${slGrpOf(it.id) ? "Bausteingruppe wechseln …" : "In Bausteingruppe …"}</button>` + (slGrpOf(it.id) ? `<button type="button" class="slb slmx" data-a="ungrp">Aus Bausteingruppe lösen</button>` : "");
  if (it.widget) mo += `<button type="button" class="slb slrm" data-a="del" >Entfernen</button>`;
  if (mo) h += `<button type="button" class="slb slmorebtn" data-a="more" aria-haspopup="true" aria-expanded="false" aria-label="Weitere Aktionen" title="Weitere Aktionen">⋯</button><span class="slmo">${mo}</span>`;
  if (it.must) h += `<span class="slmust">bleibt immer sichtbar</span>`;
  return h + `</span>`;
}
/* Mitglieder derselben Gruppe zusammenziehen: Die Gruppe steht an der Stelle ihres ersten vorhandenen Mitglieds, die Reihenfolge der Mitglieder bleibt (stabil).
   So entsteht nie eine zweite Überschrift „Streckenverlauf“ hinter Fotos und Einstieg, wenn Herzfrequenz oder Wegpunkte erst später eintreffen oder eine ältere Reihenfolge sie hinter die Fotos stellt. */
function slRegroup(pres) {
  const first = new Map(),
    out = [];
  pres.forEach(p => {
    const g = p.it.own ? null : p.it.group;
    if (g && !first.has(g)) first.set(g, []);
    if (g) first.get(g).push(p);
  });
  const done = new Set();
  pres.forEach(p => {
    const g = p.it.own ? null : p.it.group;
    if (!g) out.push(p);
    else if (!done.has(g)) {
      done.add(g);
      out.push(...first.get(g));
    }
  });
  pres.splice(0, pres.length, ...out);
}
function slPlace(root) {
  const main = root.matches && root.matches("main.home"),
    one = {stx: "statistik", trx: "reise", srx: "serie", rsx: "reisen", gex: "gebiete", gdx: "gebiet", fox: "fotos", kax: "karte"}[root.id],
    fam = one || (main ? "uebersicht" : "tour"),
    page = one || (main ? "uebersicht" : root.classList.contains("tlsub") ? "auswertung" : "haupt");
  SL.fam = fam;
  SL.page = page;
  SL.root = root;
  const items = slOrder(fam, page),
    edit = SL.edit && slCan(),
    st = slSt(fam),
    hid = slHidList(st),
    mine = new Set(items.map(i => i.id)),
    gdefs = slGrpDefs(fam, page);
  if (fam === "karte" && typeof kaBefore === "function") kaBefore(root, edit);                  // 3.34.0: Bedienfelder zurück auf die Karte (oder im Bearbeitungsmodus ins Raster)
  root.querySelectorAll(".tlw[data-wid]").forEach(e => !mine.has(e.dataset.wid) && e.remove());        // Baustein einer anderen Seite oder entfernt
  const pres = [];
  items.forEach(it => {
    let el = (SL_EL[fam][it.id] || (() => document.getElementById("tlw-" + it.id)))();
    if (el && (it.widget || it.build) && el.dataset.sig !== undefined && el.dataset.sig !== slSig(it)) {
      el.remove();                                                            // Konfiguration hat sich geändert (auch durch Abgleich mit dem Server): neu bauen
      el = null;
    }
    if (it.when && !it.when()) {                                              // 3.39.0: Abschnitt, den es nur unter einer Bedingung gibt (Plan und Ergebnis): sonst gar nicht bauen, einen vorhandenen entfernen
      if (el) el.remove();
      return;
    }
    if (!el && (it.widget || it.build) && typeof window.slWidgetBuild === "function") el = window.slWidgetBuild(it, root);
    if (!el || slSelfHidden(it, el)) return;
    pres.push({it, el, off: hid.includes(it.id) && !it.must, cw: it.cw});
  });
  if (fam === "tour" && !edit) slRegroup(pres);                          // 3.24.1: eine Gruppe steht nur einmal da (eine Überschrift), auch wenn eine alte gespeicherte Reihenfolge ihre Mitglieder trennt
  slGrpOrder(pres, gdefs);                                               // 3.36.0: Mitglieder einer Gruppe stehen zusammen
  SL.present = pres.map(p => p.it.id);
  const blocks = [];
  let cur = null;
  const cnt = {};
  pres.forEach(p => {
    p.unit = slUnit(p, edit);
    p.grp = gdefs.find(g => g.ids.includes(p.it.id)) || null;
    slCell(p, fam !== "tour" || !!p.grp || (!!p.it.group && !p.it.own));
    p.el.classList.toggle("sl-off", p.off && !edit);
    p.unit.classList.toggle("sl-dim", edit && p.off && p.unit !== p.el);
    if (p.grp) {
      if (!cur || cur.grp !== p.grp) {
        cur = {grp: p.grp, ps: []};
        blocks.push(cur);
      }
      cur.ps.push(p);
      return;
    }
    const g = p.it.own ? null : p.it.group;
    if (!g || (fam !== "tour" && g !== "cols")) {
      cur = null;
      blocks.push({unit: p.unit, p});
      return;
    }
    if (!cur || cur.g !== g) {
      cnt[g] = (cnt[g] || 0) + 1;
      cur = {g, n: cnt[g], ps: []};
      blocks.push(cur);
    }
    cur.ps.push(p);
  });
  const used = new Set(),
    seq = blocks.map(b => {
      if (b.unit) return b.unit;
      if (b.grp) {
        const ge = slGrpBlock(root, b.grp, b.ps, edit);
        used.add(ge);
        return ge;
      }
      const r = slRun(root, fam, b.g, b.n);
      used.add(r.el);
      slPlaceIn(r.body, b.ps.map(p => p.unit));
      r.el.hidden = !b.ps.some(p => edit || !p.off);                          // eine Gruppe ohne sichtbaren Inhalt zeigt keine Überschrift
      return r.el;
    });
  if (fam === "tour") root.querySelectorAll(":scope > .tlg:not(.tlsumg)").forEach(g => !used.has(g) && (g.hidden = true));
  slGrpClean(root, used);
  const op = slOpener(root, edit), zb = typeof zrBar === "function" ? zrBar(fam, pres, root, edit, op) : null;          // 3.34.0: Zeitraum-Leiste der Seite (65-zeitraum.js)
  slPlaceIn(root, main ? [op, zb, ...seq] : seq);
  if (edit)
    pres.forEach((p, i) => {
      const w = p.unit;
      if (w === p.el) return;
      const sig = [i, pres.length, p.off, p.cw, slDef(p.it.id, !!p.it.def), SL.page, p.it.title, p.it.fl || "", SL.mopen === p.it.id, (p.grp || {}).id || "", gdefs.length, SL.dev].join("|");
      let s = w.querySelector(":scope > .slst");
      if (!s) {
        s = document.createElement("div");
        s.className = "slst";
        s.setAttribute("role", "group");
        w.insertBefore(s, w.firstChild);
      }
      if (s.dataset.sig !== sig) {
        s.dataset.sig = sig;
        s.setAttribute("aria-label", p.it.title);
        s.innerHTML = slStripHtml(p, i, pres.length);
        s.classList.toggle("mo-open", SL.mopen === p.it.id);
        const mb = s.querySelector(".slmorebtn");
        if (mb) mb.setAttribute("aria-expanded", SL.mopen === p.it.id ? "true" : "false");
      }
      if (!w.querySelector(":scope > .slempty")) s.insertAdjacentHTML("afterend", '<p class="slempty mut">Gerade leer: Dieser Baustein erscheint, sobald es etwas zu zeigen gibt.</p>');
    });
  root.querySelectorAll(".slit").forEach(w => !w.querySelector(":scope > :not(.slst):not(.slempty)") && w.remove());
  if (edit && SL.focus) {
    const f = SL.focus;
    SL.focus = null;
    const w = f.gid ? root.querySelector(`.slgrp[data-gid="${f.gid}"]`) : root.querySelector(`.slit[data-sl="${f.id}"]`),
      b = w && ((f.q && w.querySelector(`[data-a="${f.a}"]${f.q}`)) || w.querySelector(`[data-a="${f.a}"]`) || w.querySelector('[data-a="grip"]'));
    if (b) b.focus({preventScroll: !!f.ps});
  }
  slSubNote(root, pres);
  if (fam === "tour") slWatchMap();
  slRaster();
  if (fam === "karte" && typeof kaAfter === "function") kaAfter(root, edit, pres);                // 3.34.0: Karte: Größe nachführen, Bedienfelder anordnen
}
/* „Seite anpassen“ steht über dem Seiteninhalt (Tourseite: vor dem Container, Übersicht: erstes Element) */
function slOpener(root, edit) {
  let w = document.getElementById("slopenw");
  if (!slCan()) {
    if (w) w.remove();
    return null;
  }
  if (!w) {
    w = document.createElement("div");
    w.id = "slopenw";
    w.className = "slopen";
    w.innerHTML = `<button type="button" class="btn ghost sm" id="slopen" data-a="edit">${slIcon.sliders}<span class="slbt">Seite anpassen</span></button><button type="button" class="btn ghost sm" id="slviews" aria-haspopup="dialog">${slIcon.layers}<span class="slbt">Ansichten</span><i class="slvdot" aria-hidden="true"></i></button>`;
  }
  if (root.matches("main.home") && typeof ziQuick === "function") ziQuick(w);                // 3.30.0: Schnell-Knopf „Touren holen“ je nach Uhr (52-bausteine-uebersicht.js), damit der Import auf dem Handy ohne Scrollen erreichbar ist
  const b = w.querySelector("#slopen"), vb = w.querySelector("#slviews");
  if (typeof slvBtnSync === "function") slvBtnSync(w);                                     // 3.37.1: Handy: Menü statt Dialog
  b.hidden = !!edit;
  if (vb) vb.hidden = !!edit;                                                              // 3.24.0: der Knopf „Ansichten“ steht immer neben „Seite anpassen“ (im Bearbeitungsmodus sitzt er in der Leiste)
  w.hidden = !!edit;
  if (typeof slViewPick === "function" && slViewPick(w)) w.hidden = false;                // 3.21.0: Ansichten-Auswahl bleibt auch im Bearbeitungsmodus stehen
  if (typeof slSaveBar === "function" && slSaveBar(w)) w.hidden = false;
  if (SL.msg && !edit) {
    slShowMsg(w);
    w.hidden = false;
  }                  // 3.22.0: „Ansicht speichern“, solange der Filter vom gespeicherten Stand abweicht
  if (!root.matches("main.home") && SL.fam !== "karte") {                                  // 3.42.0: fester Ort auf jeder Seite: ganz oben rechts im Inhalt (wie auf der Übersicht); Karte: der Knopf sitzt auf der Karte (kaAfter)
    const mn = root.closest("#main");
    if (mn && mn !== root && mn.firstChild !== w) mn.insertBefore(w, mn.firstChild);
    else if (!mn && w.nextElementSibling !== root) root.parentNode.insertBefore(w, root);
  }
  if (SL.fam === "karte") {
    const ui = document.querySelector(".mapui");
    if (ui && w.parentElement !== ui) {
      w.classList.add("kaopen");
      ui.appendChild(w);
    }
  }
  if (typeof slCodePending === "function") slCodePending();                                // 3.36.0: Link mit Ansichtscode geöffnet → Import-Dialog
  return root.matches("main.home") ? w : null;
}
/* Auswertungsseite ohne Inhalt, weil alles auf der Hauptseite liegt: passende Erklärung statt „keine Auswertung“ */
function slSubNote(root, pres) {
  const e = document.getElementById("tlempty");
  if (!e || SL.page !== "auswertung") return;
  const moved = Object.values(slSt("tour").page || {}).includes("haupt");
  e.classList.toggle("sl-moved", moved);
  const h = e.querySelector("h2:not(.slmoved)"), p = e.querySelector("p.mut:not(.slmoved)");
  if (h && p) {
    if (moved && !e.dataset.orig) e.dataset.orig = "1";
    h.hidden = moved;
    p.hidden = moved;
    let n = e.querySelector(".slmoved");
    if (moved && !n) {
      e.insertAdjacentHTML("afterbegin", '<h2 class="slmoved">Hier gibt es nichts anzuzeigen</h2><p class="mut slmoved">Bausteine, die du auf die Hauptseite gelegt hast, findest du dort. Mit „Seite anpassen“ lassen sie sich zurückholen.</p>');
    } else if (!moved && n) e.querySelectorAll(".slmoved").forEach(x => x.remove());
  }
}
function slApply() {
  if (SL.fam === "tour") {
    if (typeof tlRefresh === "function") tlRefresh();
  } else if (SL.fam !== "uebersicht") {
    const r = slOneRoot(SL.fam);
    if (r) slPlace(r);
  } else {
    const m = document.getElementById("main");
    if (m && m.classList.contains("home")) slPlace(m);
  }
}

/* ---------- Bearbeitungsleiste ---------- */
function slBar(on) {
  let b = document.getElementById("slbar");
  if (!on) {
    if (b) b.remove();
    return;
  }
  if (b) return;
  b = document.createElement("div");
  b.id = "slbar";
  b.className = "slbar";
  b.setAttribute("role", "region");
  b.setAttribute("aria-label", "Seite anpassen");
  b.innerHTML =
    `<p class="slsr" id="slhint">Zum Verschieben ziehen oder Pfeil hoch bzw. Pfeil runter drücken.</p>` +
    `<div class="slsr" id="sllive" aria-live="polite" aria-atomic="true"></div>` +
    `<p class="slbi"><b>Seite anpassen</b><span class="slvn" id="slvn"></span><span class="slsaved" id="slsaved" role="status" aria-live="polite"></span><span class="slchg" id="slchg" hidden>Ungespeicherte Änderungen</span></p>` +
    `<div class="slbt" id="slbt">${slHistHtml()}${slDevHtml()}</div>` +
    `<div class="slsws" id="slsw" hidden><label class="slkopf" id="slkopf" hidden><input type="checkbox" id="slkopfin" data-opt="holen"><span>Schnell-Knopf zum Touren holen in der Kopfzeile</span></label>` +
    `<div class="slzr" id="slzr"><label class="slzrl"><input type="checkbox" id="slzrin" aria-describedby="slzrnote"><span>Zeitraum der Seite anzeigen</span></label>` +
    `<button type="button" class="slzrh" id="slzrhb" aria-expanded="false" aria-controls="slzrhelp">Was ist das?</button>` +
    `<p class="mut slzrnote" id="slzrnote" hidden>Ein Zeitraum ist gewählt, die Leiste bleibt sichtbar. Setze ihn auf „Je Baustein“ zurück, um sie auszublenden.</p>` +
    `<div class="slzrhelp" id="slzrhelp" role="region" aria-label="Zeitraum der Seite" hidden>${typeof zrHelpHtml === "function" ? zrHelpHtml() : ""}</div></div></div>` +
    `<div class="slbb"><button type="button" class="btn ghost sm" data-a="views" aria-haspopup="dialog">Ansichten</button><button type="button" class="btn ghost sm" data-a="add" aria-label="Baustein hinzufügen"><span class="slfu">Baustein hinzufügen</span><span class="slsh" aria-hidden="true">+ Baustein</span></button>` +
    `<button type="button" class="btn ghost sm slmorebtn" data-a="more" aria-haspopup="true" aria-expanded="false" aria-label="Weitere Aktionen" title="Weitere Aktionen">⋯</button>` +
    `<span class="slbmo"><button type="button" class="btn ghost sm" data-a="reset">Standard wiederherstellen</button><button type="button" class="btn ghost sm" data-a="savenew" aria-haspopup="dialog">Als neue Ansicht speichern …</button><button type="button" class="btn ghost sm" data-a="discard">Verwerfen</button></span>` +
    `<button type="button" class="btn sm" data-a="done">Fertig</button></div>`;
  document.body.appendChild(b);
  slKopfSync();
  slBarH();
}
/* 3.24.0 Abstand am Seitenfuß = Höhe der Leiste (die Leiste ist je nach Breite unterschiedlich hoch), damit nichts dahinter verschwindet */
function slBarH() {
  const b = document.getElementById("slbar");
  const k = document.getElementById("slsw");                                     // 3.31.0: der Schalter schwebt über der Leiste und macht sie nicht höher; Platz am Seitenfuß aber mitrechnen (3.37.2: beide Schalter)
  if (b) document.body.style.setProperty("--slbh", b.offsetHeight + (k && !k.hidden ? k.offsetHeight + 8 : 0) + "px");
  else document.body.style.removeProperty("--slbh");
}
window.addEventListener("resize", () => slBarH());
/* 3.24.0 „⋯“-Menü: Baustein-Kopf (nur schmale Bausteine) und Leiste (nur schmale Schirme); je Baustein höchstens eines offen */
function slMore(b) {
  const st = b.closest(".slst"), bar = b.closest("#slbar"), host = st || bar;
  if (!host) return;
  const on = !host.classList.contains("mo-open");
  document.querySelectorAll(".slst.mo-open, #slbar.mo-open").forEach(x => {
    x.classList.remove("mo-open");
    const k = x.querySelector(".slmorebtn");
    if (k) k.setAttribute("aria-expanded", "false");
  });
  host.classList.toggle("mo-open", on);
  b.setAttribute("aria-expanded", on ? "true" : "false");
  SL.mopen = st && on ? st.closest(".slit").dataset.sl : null;
  slBarH();
}
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  const o = document.querySelector(".slst.mo-open, #slbar.mo-open");
  if (!o) return;
  const k = o.querySelector(".slmorebtn");
  slMore(k);
  k.focus();
});
/* 3.22.0 Stand vor dem Bearbeiten: Grundlage für „Verwerfen“, „Als neue Ansicht speichern“ und die Markierung „Ungespeicherte Änderungen“ */
function slSnap() {
  const fam = SL.fam, st = {};
  slKeys(fam).forEach(k => {
    slSync(k);
    st[k] = JSON.stringify(slStore(k));
  });
  SL.snap = {fam, st, view: SL.view[fam], manual: slManual(fam)};
}
function slIsChg() {
  if (!SL.snap || SL.snap.fam !== SL.fam) return false;
  slKeys(SL.fam).forEach(slSync);
  return slKeys(SL.fam).some(k => JSON.stringify(slStore(k)) !== SL.snap.st[k]);
}
function slChg() {
  slKopfSync();
  if (typeof slBarSync === "function") slBarSync();
  const m = document.getElementById("slchg");
  if (m) m.hidden = !(SL.edit && slIsChg());
}
/* Sichtbare Bestätigung neben „Seite anpassen“ (bleibt stehen, bis die Seite verlassen oder erneut bearbeitet wird) */
function slAnnounce(text, bad) {
  slLive(text);
  SL.msg = {text, bad: !!bad, fam: SL.fam, fresh: true};
  slShowMsg();
}
function slShowMsg(el) {
  const w = el || document.getElementById("slopenw"), g = SL.msg;
  if (!w || !g) return;
  const text = g.text, bad = g.bad;
  let m = w.querySelector(".slok");
  if (!m) {
    m = document.createElement("span");
    m.className = "slok";
    m.setAttribute("role", "status");
    w.appendChild(m);
  }
  if (m.dataset.t === text && m.dataset.state === (bad ? "bad" : "ok")) return;               // unverändert nicht neu schreiben (Beobachter und Übersetzung würden sonst im Kreis laufen)
  m.dataset.t = text;
  m.dataset.state = bad ? "bad" : "ok";
  m.textContent = text;
}
function slEdit(on, announce, keepMsg) {
  on = !!on && slCan();
  if (on === SL.edit) return;
  SL.edit = on;
  SL.dev = on && slMobNow() ? "mob" : "desk";                                  // 3.36.0: auf einem schmalen Bildschirm startet der Umschalter bei „Handy“
  document.body.classList.toggle("sl-dev-mob", on && SL.dev === "mob" && SL.fam !== "karte");
  if (on) {
    slSnap();
    if (!keepMsg) SL.msg = null;
    const m = document.querySelector("#slopenw .slok");
    if (m) m.remove();
  }
  document.body.classList.toggle("sl-editing", on);
  if (!on) {
    SL.mopen = null;
    document.body.classList.remove("sl-dev-mob");
  }
  slBar(on);
  slHistReset();
  if (on && keepMsg && SL.msg) slStatus(SL.msg.text);
  SL.focus = on ? {id: SL.present[0] || "", a: "grip", ps: true} : null;
  slApply();
  if (on) slLive("Seite anpassen ist an. Bausteine ziehen oder mit den Pfeiltasten verschieben.");
  else {
    const snap = SL.snap;
    SL.snap = null;
    const o = document.getElementById("slopen");
    if (o) o.focus();
    slFlush().then(ok => announce && (ok ? slAnnounce(snap && snap.st && slKeys(snap.fam).some(k => JSON.stringify(slStore(k)) !== snap.st[k]) ? "Anordnung gespeichert" : "Anordnung gespeichert (keine Änderungen)") : slAnnounce("Nicht gespeichert – nur auf diesem Gerät gemerkt", true)));
  }
}
function slLeave() {
  if (!SL.edit) return;
  SL.edit = false;
  SL.snap = null;
  slHistReset();
  document.body.classList.remove("sl-editing", "sl-dev-mob");
  SL.mopen = null;
  slBar(false);
  slFlush();
}

/* ---------- Dialoge (Katalog, Einstellungen) ---------- */
function slModal(title, build, cls) {                  // 3.46.0: Rahmen, Fokusfalle, Esc, Klick daneben, inert und Fokus-Rückgabe kommen aus uiModal (00-dialog.js)
  const host = uiModal(`<h2></h2><div class="slmb"></div>`),
    box = host.querySelector(".uibox"),
    body = host.querySelector(".slmb");
  host.classList.add("sldlg");
  box.classList.add("slbox");
  if (cls) box.classList.add(...cls.split(/\s+/).filter(Boolean));
  host.querySelector("h2").textContent = title;
  const close = () => host.remove();
  build(body, close);
  const f = body.querySelector("button, input, textarea, select");
  (f || box).focus();
  return {close, box};
}
/* 3.34.0 Galerie: Live-Vorschau mit den echten Daten des Benutzers. Jede Karte baut ihren Baustein erst, wenn sie ins Bild kommt (IntersectionObserver), höchstens drei gleichzeitig;
   die Vorschau ist nicht bedienbar (inert), ein Fehler oder eine leere Auswertung lässt die statische Beispielvorschau stehen und blockiert den Dialog nie. */
let SL_PVN = 0;
function slLivePreviews(body) {
  const els = [...body.querySelectorAll(".slpv[data-live]")];
  if (!els.length) return;
  const queue = [];
  let run = 0, gone = false;
  const done = (pv, ok, why) => {
    pv.removeAttribute("aria-busy");
    pv.classList.remove("slpv-load");
    pv.classList.toggle("slpv-ex", !ok);
    pv.dataset.live = ok ? "live" : why || "ex";
    run--;
    next();
  };
  const next = () => {
    while (!gone && run < 3 && queue.length) {
      const pv = queue.shift();
      if (!pv.isConnected) continue;
      run++;
      draw(pv);
    }
  };
  const draw = pv => {
    const type = pv.dataset.live, T = window.SL_WT[type], stat = pv.innerHTML;
    pv.classList.add("slpv-load");
    pv.setAttribute("aria-busy", "true");
    let card;
    try {
      card = window.slWidgetBuild({id: "pv" + ++SL_PVN, wtype: type, cfg: JSON.parse(JSON.stringify(T.defaults || {}))}, SL.root);
    } catch (e) {
      card = null;
    }
    if (!card) return done(pv, false, "fehler");
    card.inert = true;
    card.querySelectorAll("details").forEach(d => (d.open = true));
    card.classList.add("slpvcard");
    const host = document.createElement("div");
    host.className = "slpvlive" + (T.shell ? " slpvshell" : "");
    host.appendChild(card);
    host.hidden = true;
    pv.appendChild(host);                                                            // unsichtbar aufbauen, die statische Vorschau bleibt bis zum Ergebnis stehen
    let fin = false;
    const finish = () => {
      if (fin) return;
      fin = true;
      mo.disconnect();
      clearTimeout(to);
      const b = card.querySelector(".slwb") || card, bad = !b.isConnected || b.querySelector(".slnone") || !b.textContent.trim() || (card.dataset.hn === "aus");
      if (bad) {
        host.remove();
        if (!pv.querySelector(".slpvex")) pv.insertAdjacentHTML("beforeend", '<span class="slpvex">Beispielwerte</span>');
        return done(pv, false, "leer");
      }
      pv.innerHTML = "";
      pv.appendChild(host);
      host.hidden = false;
      done(pv, true);
    };
    const settled = () => {
      const b = card.querySelector(".slwb") || card;
      return !!b && !/Wird geladen/.test(b.textContent) && !!b.textContent.trim();
    };
    const mo = new MutationObserver(() => settled() && setTimeout(finish, 60));
    mo.observe(card, {childList: true, subtree: true, characterData: true});
    const to = setTimeout(finish, 7000);
    if (!pv._stat) pv._stat = stat;
  };
  const enqueue = pv => {
    if (pv.dataset.live === "live" || pv.classList.contains("slpv-load") || pv.dataset.live === "leer" || pv.dataset.live === "fehler") return;
    queue.push(pv);
    next();
  };
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) {
        io.unobserve(e.target);
        enqueue(e.target);
      }
    }), {root: body.closest(".slbox") || null, rootMargin: "120px"});
    els.forEach(pv => io.observe(pv));
    body._slio = io;
  } else els.slice(0, 6).forEach(enqueue);
  new MutationObserver((_, o) => {
    if (!body.isConnected) {
      gone = true;
      if (body._slio) body._slio.disconnect();
      o.disconnect();
    }
  }).observe(document.body, {childList: true});
}
/* 3.45.0 Tourseite: Bausteine ohne Bezug zur einzelnen Tour (Übersichts-Bausteine wie „Dein Jahr“ oder „Ziele“) stehen im Katalog in einer eigenen, zugeklappten Gruppe */
const SL_ALLG = ["allg", "Allgemein (nicht zu dieser Tour)"];
const slCatOf = T => (SL.fam === "tour" && T.fam !== "tour" ? SL_ALLG[0] : T.cat || "zahlen");
function slCatalog() {
  const list = Object.entries(window.SL_WT).filter(([, T]) => slFits(T, SL.fam)),
    have = type => (slSt(SL.fam).widgets || []).filter(w => w.type === type).length,
    cats = [...SL_CATS, SL_ALLG].filter(([k]) => list.some(([, T]) => slCatOf(T) === k)),
    card = ([type, T]) => {
      const n = have(type),
        std = !T.multi && SL_REG[SL.fam].some(r => r.build === type && !(slSt(SL.fam).hidden || []).includes(r.id)),             // 3.30.0: steht als Standard-Abschnitt schon (sichtbar) auf der Seite
        dis = !T.multi && (n > 0 || std);
      if (T.neu)                                                                                         // 3.28.0: Baustein, den der Benutzer in einem eigenen Dialog zusammenstellt
        return `<article class="slcard" data-cat="${slCatOf(T)}"><div class="slpv" aria-hidden="true">${T.preview ? T.preview() : ""}</div><div class="slci"><h3>${esc(T.name)}</h3><p>${esc(T.desc || "")}</p>` +
          `<button type="button" class="btn sm" data-neu="${type}">${n ? "Noch eine erstellen" : "Erstellen"}</button></div></article>`;
      return `<article class="slcard" data-cat="${slCatOf(T)}"><div class="slpv" aria-hidden="true"${T.hinweis ? "" : ` data-live="${type}"`}>${T.preview ? T.preview() : ""}</div><div class="slci"><h3>${esc(T.name || T.title(T.defaults || {}))}</h3>${n || std ? '<span class="slhave">Bereits auf dieser Seite</span>' : ""}<p>${esc(T.desc || "")}</p>` +
        `<button type="button" class="btn sm${dis ? " ghost" : ""}" data-add="${type}"${dis ? " disabled" : ""}>${dis ? (std && !n ? "Steht schon auf der Seite" : "Bereits hinzugefügt") : n ? "Noch einmal hinzufügen" : "Hinzufügen"}</button></div></article>`;
    };
  slModal("Baustein hinzufügen", (body, close) => {
    body.innerHTML =
      `<p class="mut slcatin">Bausteine zeigen Auswertungen aus deinen vorhandenen Daten. Die Vorschau zeigt deine echten Zahlen; Beispielwerte erscheinen nur, wenn noch keine Daten da sind.</p>` +
      `<div class="slfilt"><div class="slchips" role="group" aria-label="Kategorie"><button type="button" class="slchip" data-cat="" aria-pressed="true">Alle</button>` +
      cats.map(([k, l]) => `<button type="button" class="slchip" data-cat="${k}" aria-pressed="false">${k === SL_ALLG[0] ? "Allgemein" : l}</button>`).join("") +
      `</div><label class="slsr" for="slq">Bausteine suchen</label><input id="slq" type="search" class="slq" placeholder="Bausteine suchen …" autocomplete="off" enterkeyhint="search"></div>` +
      `<p class="mut slcnt" role="status" aria-live="polite"></p><div class="slcatl">` +
      cats.map(([k, l]) => (k === SL_ALLG[0]
        ? `<details class="slsec slallg" data-cat="${k}"><summary class="slcath">${l}</summary><p class="mut slallgp">Diese Bausteine zeigen nichts zu dieser Tour, sondern deine Touren insgesamt (wie auf der Übersicht).</p><div class="slcats">${list.filter(([, T]) => slCatOf(T) === k).map(card).join("")}</div></details>`
        : `<section class="slsec" data-cat="${k}"><h3 class="slcath">${l}</h3><div class="slcats">${list.filter(([, T]) => slCatOf(T) === k).map(card).join("")}</div></section>`)).join("") +
      `</div><p class="slnorsl mut" hidden>Nichts gefunden. Probiere einen anderen Suchbegriff oder eine andere Kategorie.</p><div class="uifoot"><button type="button" class="btn ghost" data-close>Schließen</button></div>`;
    let cat = "";
    const q = body.querySelector("#slq"),
      cnt = body.querySelector(".slcnt"),
      none = body.querySelector(".slnorsl"),
      apply = () => {
        const term = q.value.trim();
        let n = 0;
        body.querySelectorAll(".slsec").forEach(sec => {
          let any = 0;
          sec.querySelectorAll(".slcard").forEach(cd => {
            const ok = (!cat || cd.dataset.cat === cat) && (!term || smatch(cd.textContent, term));
            cd.hidden = !ok;
            any += ok ? 1 : 0;
          });
          sec.hidden = !any;
          if (sec.tagName === "DETAILS" && any && (term || cat === sec.dataset.cat)) sec.open = true;              // Suche oder Kategorie „Allgemein“: die zugeklappte Gruppe öffnen
          n += any;
        });
        none.hidden = n > 0;
        cnt.textContent = n === 1 ? "1 Baustein" : `${n} Bausteine`;
        body.querySelectorAll(".slchip").forEach(c => c.setAttribute("aria-pressed", String(c.dataset.cat === cat)));
      };
    apply();
    slLivePreviews(body);
    q.addEventListener("input", apply);
    q.addEventListener("keydown", e => e.key === "Enter" && e.preventDefault());
    body.onclick = e => {
      const a = e.target.closest("[data-add]"),
        nw = e.target.closest("[data-neu]"),
        ch = e.target.closest(".slchip");
      if (e.target.closest("[data-close]")) close();
      else if (nw) {
        close();
        window.SL_WT[nw.dataset.neu].neu();
      }
      else if (ch) {
        cat = ch.dataset.cat;
        apply();
      } else if (a && !a.disabled) {
        close();
        const id = slAddWidget(a.dataset.add);
        if (id && slFieldsOf(window.SL_WT[a.dataset.add]).length && window.SL_WT[a.dataset.add].cfgOnAdd) slCfgDialog(id);
      }
    };
  }, "slcat");
}
function slCfgDialog(id) {
  const w = slWidgetOf(id),
    T = w && window.SL_WT[w.type];
  if (!T) return;
  if (T.dialog) return T.dialog(id, w.cfg || {});                          // 3.28.0: eigener Dialog (eigene Kennzahl)
  slModal(`Einstellungen: ${T.name || T.title(w.cfg)}`, (body, close) => {
    const cfg = JSON.parse(JSON.stringify(w.cfg || {}));
    const FS = slFieldsOf(T);
    body.innerHTML = `<form class="slform" novalidate>${FS.map((f, i) => (f.show ? `<div class="slshow" data-show="${i}">${slField(f, cfg, i)}</div>` : slField(f, cfg, i))).join("")}<div class="uifoot"><button type="button" class="btn ghost" data-close>Abbrechen</button><button type="submit" class="btn">Speichern</button></div></form>`;
    const form = body.querySelector("form");
    /* 3.45.0 Felder, die nur zu einer Auswahl gehören (f.show = {Schlüssel: [Werte]}, z. B. „Schwelle“ nur bei „Nur Warnung“): sonst ausgeblendet und nicht geprüft */
    const shown = i => {
      const f = FS[i];
      if (!f.show) return true;
      return Object.entries(f.show).every(([k, vs]) => {
        const j = FS.findIndex(x => x.k === k), sel = j >= 0 && form.querySelector(`input[name="f${j}"]:checked`);
        return vs.map(String).includes(String(sel ? sel.value : cfg[k] ?? (FS[j] || {}).def));
      });
    };
    const syncShow = () => form.querySelectorAll("[data-show]").forEach(el => {
      const on = shown(+el.dataset.show);
      el.hidden = !on;
      el.querySelectorAll("input,select,textarea").forEach(x => (x.disabled = !on));
    });
    syncShow();
    form.addEventListener("change", syncShow);
    form.onsubmit = e => {
      e.preventDefault();
      const out = {...cfg};
      let bad = null;
      FS.forEach((f, i) => {
        if (!shown(i)) return;
        if (FL_KINDS.has(f.kind)) flRead(f, form, i, out);
        else if (f.kind === "checks") out[f.k] = [...form.querySelectorAll(`input[name="f${i}"]:checked`)].map(x => x.value);
        else if (f.kind === "bool") {
          if (form.querySelector(`input[name="f${i}"]`).checked) out[f.k] = true;
          else delete out[f.k];                                            // Standard (aus) nicht speichern
        }
        else if (f.kind === "radio") {
          const v = (form.querySelector(`input[name="f${i}"]:checked`) || {}).value || cfg[f.k] || f.def;
          out[f.k] = f.num ? +v : v;
        }
        else if (f.kind === "text") out[f.k] = form.querySelector(`[name="f${i}"]`).value.slice(0, f.max || 500);
        else if (f.kind === "number") {
          const inp = form.querySelector(`[name="f${i}"]`),
            v = parseFloat(String(inp.value).replace(",", "."));
          out[f.k] = f.int ? Math.round(v) : v;
          if (!(v >= f.min && v <= f.max)) bad = bad || {inp, msg: `Bitte eine Zahl von ${f.min} bis ${f.max} eingeben.`};
        }
      });
      if (bad) {
        const er = bad.inp.closest(".slfs").querySelector(".slerr");
        if (er) er.textContent = bad.msg;
        bad.inp.focus();
        return;
      }
      if (FS.some((f, i) => f.kind === "checks" && f.min && shown(i) && out[f.k].length < f.min)) {
        form.querySelector(".slerr").textContent = "Bitte mindestens einen Wert wählen.";
        return;
      }
      FS.forEach(f => f.kind === "checks" && f.def && out[f.k] && out[f.k].join() === f.def.join() && delete out[f.k]);          // Standardwerte nicht speichern
      close();
      slSetCfg(id, out);
    };
    form.onclick = e => e.target.closest("[data-close]") && close();
    flBind(form);
    form.addEventListener("input", e => {
      const ta = e.target.closest("textarea[data-max]");
      if (ta) form.querySelector(".slcount").textContent = `${ta.value.length} / ${ta.dataset.max}`;
    });
  });
}
/* Felder im Einstellungs-Dialog: auf der Statistikseite kommt bei Bausteinen mit Sportart oder Zeitraum der Schalter „Globalen Filter verwenden“ davor (3.22.0) */
function slFieldsOf(T) {
  const fs = (T && T.fields) || [];
  if (SL.fam === "uebersicht" && !(T && T.hinweis) && fs.some(f => f.kind === "range"))                       // 3.34.0: Zeitraum der Seite (65-zeitraum.js)
    return [{kind: "global", zr: true, label: "Zeitraum der Seite verwenden"}, ...fs];
  return SL.fam === "statistik" && !(T && T.hinweis) && fs.some(f => f.kind === "sports" || f.kind === "range") ? [{kind: "global"}, ...fs] : fs;      // 3.23.0: Hinweis-Bausteine haben nie den globalen Filter
}
function slField(f, cfg, i) {
  const id = "slf" + i;
  if (FL_KINDS.has(f.kind)) return flField(f, cfg, i);
  if (f.kind === "checks")
    return `<fieldset class="slfs"><legend>${esc(f.label)}</legend><div class="flchips">${f.options.map(([v, l]) => `<label class="flchip"><input type="checkbox" name="f${i}" value="${v}"${(cfg[f.k] || f.def || []).includes(v) ? " checked" : ""}><span>${esc(l)}</span></label>`).join("")}</div><p class="slerr" role="alert"></p></fieldset>`;
  if (f.kind === "bool")
    return `<fieldset class="slfs"><label class="slck"><input type="checkbox" name="f${i}"${cfg[f.k] === true ? " checked" : ""}><span>${esc(f.label)}</span></label></fieldset>`;
  if (f.kind === "radio")
    return `<fieldset class="slfs"><legend>${esc(f.label)}</legend><div class="flchips">${f.options.map(([v, l]) => `<label class="flchip"><input type="radio" name="f${i}" value="${v}"${String(cfg[f.k] ?? f.def) === String(v) ? " checked" : ""}><span>${esc(l)}</span></label>`).join("")}</div></fieldset>`;
  if (f.kind === "number")
    return `<div class="slfs"><label for="${id}">${esc(f.label)}</label><input id="${id}" name="f${i}" type="number" inputmode="decimal" min="${f.min}" max="${f.max}" step="${f.step || 1}" value="${esc(cfg[f.k] ?? f.def ?? "")}" required><p class="slerr" role="alert"></p></div>`;
  const max = f.max || 500;
  return `<div class="slfs"><label for="${id}">${esc(f.label)}</label><textarea id="${id}" name="f${i}" rows="6" maxlength="${max}" data-max="${max}">${esc(cfg[f.k] || "")}</textarea><p class="mut slcount">${(cfg[f.k] || "").length} / ${max}</p></div>`;
}

/* ---------- Ereignisse ---------- */
document.addEventListener("click", e => {
  const o = e.target.closest && e.target.closest("#slopen"),
    vo = e.target.closest && e.target.closest("#slviews"),
    mo = e.target.closest && e.target.closest(".slmorebtn"),
    bar = e.target.closest && e.target.closest("#slbar [data-a]"),
    b = e.target.closest && e.target.closest(".slst button[data-a]");
  if (o) return slEdit(true);
  if (vo) return typeof slvMenuOn === "function" && slvMenuOn() ? slvMenuToggle(vo) : typeof slViewsDialog === "function" && slViewsDialog();          // 3.37.1: auf dem Handy ein Menü (Auswahl, Speichern, Verwalten), sonst der Dialog
  if (mo) return slMore(mo);
  if (bar) {
    const a = bar.dataset.a;
    if (a === "done") slEdit(false, true);
    else if (a === "discard") slDiscard();
    else if (a === "savenew") slSaveNew(SL.fam, true);
    else if (a === "add") slCatalog();
    else if (a === "views" && typeof slViewsDialog === "function") slViewsDialog();
    else if (a === "reset") slReset();
    else if (a === "undo") slUndo();
    else if (a === "redo") slRedo();
    else if (a === "dev") slSetDev(bar.dataset.d);
    else if (a === "mobreset") slMobReset();
    return;
  }
  const gb = e.target.closest && e.target.closest(".slgst [data-a]");
  if (gb) return slGrpAction(gb);
  if (!b || b.dataset.a === "grip") return;
  const id = b.closest(".slit").dataset.sl,
    a = b.dataset.a;
  if (b.getAttribute("aria-disabled") === "true") return slLive(`${slTitle(id)}: ${a === "up" ? "ganz oben" : "ganz unten"}`);
  SL.focus = {id, a};
  if (a === "up") slStep(id, -1);
  else if (a === "down") slStep(id, 1);
  else if (a === "eye") slToggleHidden(id);
  else if (a === "w") slSetWidth(id, b.dataset.w);
  else if (a === "page") slSetPage(id, SL.page === "haupt" ? "auswertung" : "haupt");
  else if (a === "cfg") slCfgDialog(id);
  else if (a === "dup") slDupWidget(id);
  else if (a === "grp") slGrpDialog(id);
  else if (a === "ungrp") slGrpUngroup(id);
  else if (a === "del")
    uiConfirm({title: "Baustein entfernen?", text: `„${slTitle(id)}“ wird von dieser Seite entfernt.`, ok: "Entfernen", danger: true}).then(ok => ok && slRemoveWidget(id));
});
document.addEventListener("click", e => {
  const h = e.target.closest && e.target.closest("#slzrhb");
  if (!h) return;
  const open = h.getAttribute("aria-expanded") !== "true", p = document.getElementById("slzrhelp");
  h.setAttribute("aria-expanded", String(open));
  if (p) p.hidden = !open;
  slBarH();
});
document.addEventListener("change", e => {
  const k = e.target.closest && e.target.closest("#slkopfin");
  if (k) return slSetHolen(k.checked);
  const z = e.target.closest && e.target.closest("#slzrin");
  if (z) return slSetZr(z.checked);
  const c = e.target.closest && e.target.closest(".slst input[data-a=open]");
  if (c) slSetOpen(c.closest(".slit").dataset.sl, c.checked);
});
document.addEventListener("keydown", e => {
  const g = e.target.closest && e.target.closest(".slgrip");
  if (!g) return;
  const id = g.closest(".slit").dataset.sl,
    k = e.key;
  if (k === "ArrowUp" || k === "ArrowDown" || k === "ArrowLeft" || k === "ArrowRight") {          // Reihenfolge = Leserichtung: links/oben = früher, rechts/unten = später
    e.preventDefault();
    SL.focus = {id, a: "grip"};
    slStep(id, k === "ArrowUp" || k === "ArrowLeft" ? -1 : 1);
  } else if (k === "Home" || k === "End") {
    e.preventDefault();
    SL.focus = {id, a: "grip"};
    const ord = SL.present;
    if (k === "Home" && ord[0] !== id) slMove(id, ord[0]);
    else if (k === "End" && ord[ord.length - 1] !== id) slMove(id, null);
  }
});
/* Ziehen mit Maus, Stift und Finger (Pointer-Ereignisse, nicht HTML5-Drag&Drop); der Griff bleibt dabei „gefangen“, damit die Bewegung nie verloren geht */
document.addEventListener("pointerdown", e => {
  const g = e.target.closest && e.target.closest(".slgrip");
  if (!g || (e.pointerType === "mouse" && e.button !== 0)) return;
  e.preventDefault();
  const w = g.closest(".slit");
  try {
    g.setPointerCapture(e.pointerId);
  } catch (x) {}
  SL.drag = {id: w.dataset.sl, w, g, pid: e.pointerId, x0: e.clientX, y0: e.clientY, s0: window.scrollY, x: e.clientX, y: e.clientY, target: null, raf: 0};
  w.classList.add("sl-lift");
  g.focus({preventScroll: true});
});
function slDragTarget(d) {
  const root = SL.root || document,
    gr = [...root.querySelectorAll(".slgrp")].find(g => {                  // 3.36.0: Zeiger über einer Gruppe = in die Gruppe ablegen
      const r = g.getBoundingClientRect();
      return d.x >= r.left && d.x <= r.right && d.y >= r.top && d.y <= r.bottom;
    }),
    ws = [...root.querySelectorAll(".slit")].filter(x => x !== d.w && (!gr || gr.contains(x)));
  d.grp = gr ? gr.dataset.gid : null;
  document.querySelectorAll(".sl-before,.sl-after").forEach(x => x.classList.remove("sl-before", "sl-after"));
  let t = null;
  for (const w of ws) {                                                   // in Leserichtung: erstes Element, vor dem der Zeiger liegt
    const r = w.getBoundingClientRect(),
      g = w.parentElement && w.parentElement.classList.contains("hcols") ? w.parentElement.parentElement : w.parentElement,
      full = !g || r.width > g.getBoundingClientRect().width * 0.9,
      before = full ? d.y < r.top + r.height / 2 : d.y < r.top || (d.y <= r.bottom && d.x < r.left + r.width / 2);
    if (before) {
      t = w;
      break;
    }
  }
  if (t) t.classList.add("sl-before");
  else if (ws.length) ws[ws.length - 1].classList.add("sl-after");
  d.target = t ? t.dataset.sl : null;
  document.querySelectorAll(".slgrp.sl-into").forEach(x => x !== gr && x.classList.remove("sl-into"));
  if (gr) gr.classList.add("sl-into");
}
function slDragFrame() {
  const d = SL.drag;
  if (!d) return;
  d.w.style.transform = `translate(${d.x - d.x0}px,${d.y - d.y0 + (window.scrollY - d.s0)}px)`;
  const edge = 70;
  if (d.y < edge) window.scrollBy(0, -14);
  else if (d.y > window.innerHeight - edge) window.scrollBy(0, 14);
  slDragTarget(d);
  d.raf = requestAnimationFrame(slDragFrame);
}
document.addEventListener("pointermove", e => {
  const d = SL.drag;
  if (!d || e.pointerId !== d.pid) return;
  d.y = e.clientY;
  d.x = e.clientX;
  if (!d.raf) d.raf = requestAnimationFrame(slDragFrame);
});
function slDragEnd(e, cancel) {
  const d = SL.drag;
  if (!d || e.pointerId !== d.pid) return;
  SL.drag = null;
  cancelAnimationFrame(d.raf);
  d.w.style.transform = "";
  d.w.classList.remove("sl-lift");
  document.querySelectorAll(".sl-before,.sl-after").forEach(x => x.classList.remove("sl-before", "sl-after"));
  document.querySelectorAll(".slgrp.sl-into").forEach(x => x.classList.remove("sl-into"));
  try {
    d.g.releasePointerCapture(d.pid);
  } catch (x) {}
  if (cancel || Math.hypot(d.y - d.y0, d.x - d.x0) < 4) return;
  slDragTarget(d);
  document.querySelectorAll(".sl-before,.sl-after").forEach(x => x.classList.remove("sl-before", "sl-after"));
  SL.focus = {id: d.id, a: "grip"};
  document.querySelectorAll(".slgrp.sl-into").forEach(x => x.classList.remove("sl-into"));
  slMove(d.id, d.target, slGrpCan(d.id) ? d.grp : undefined);
}
document.addEventListener("pointerup", e => slDragEnd(e, false));
document.addEventListener("pointercancel", e => slDragEnd(e, true));
window.addEventListener("hashchange", slLeave);

/* 3.34.0 Späte Einhängung: Zeichnet boot() (13-start.js) die Seite, bevor das Skript mit der Ansicht geladen war, ist sie ohne Layout gebaut. Dann (und nur dann) wird sie einmal neu gezeichnet:
   erst wenn die alte Ansicht fertig ist (Element drawn da) und die eingehängte Ansicht (Flag flag) nie angelaufen ist. Ein sofortiges route() ließe zwei Läufe gleichzeitig in dieselbe Seite schreiben (doppelte Bedienfelder). */
function slLate(re, flag, drawn) {
  if (!re.test(location.hash) || !(window._rt > 0)) return;
  let n = 0;
  const t = setInterval(() => {
    if (window[flag] || ++n > 100) return clearInterval(t);
    if (document.querySelector(drawn)) {
      clearInterval(t);
      route();
    }
  }, 100);
}
/* ---------- Anbindung an die Ansichten ---------- */
function slViewStart(fam) {
  slLeave();
  if (SL.msg && SL.msg.fam === fam && SL.msg.fresh) SL.msg.fresh = false;                   // Bestätigung überlebt genau einen Neuaufbau (z. B. nach Ansichtswechsel)
  else SL.msg = null;
  SL.fam = fam;
  SL.present = [];
  SL.focus = null;
  const o = document.getElementById("slopenw");
  if (o) o.remove();
}
const _tour49 = VIEWS.tour;
VIEWS.tour = async (...a) => {
  slViewStart("tour");
  const tok = window._rt;
  await slEnsure("tour");
  if (tok !== window._rt) return STALE();                            // inzwischen eine andere Seite geöffnet
  slResolve("tour", (BY[a[0]] || {}).sport);                          // 3.21.0: Ansicht wählen (von Hand gewählt, Regel der Sportart oder Standardansicht)
  await _tour49(...a);
};
const _aus49 = VIEWS.tourauswertung;
VIEWS.tourauswertung = async (...a) => {
  slViewStart("tour");
  const tok = window._rt;
  await slEnsure("tour");
  if (tok !== window._rt) return STALE();                            // inzwischen eine andere Seite geöffnet
  slResolve("tour", (BY[a[0]] || {}).sport);
  await _aus49(...a);
};
const _dash49 = VIEWS.dash;
VIEWS.dash = async (...a) => {
  slViewStart("uebersicht");
  const tok = window._rt;
  await slEnsure("uebersicht");
  if (tok !== window._rt) return STALE();                            // inzwischen eine andere Seite geöffnet
  slResolve("uebersicht");
  if (typeof zrInit === "function") zrInit("uebersicht", a[1]);                                  // 3.34.0: Zeitraum der Seite (Adresse > zuletzt gewählt > Ansicht)
  await _dash49(...a);
  const m = document.getElementById("main");
  if (m && m.classList.contains("home") && m.querySelector("#hlast")) slPlace(m);
};
