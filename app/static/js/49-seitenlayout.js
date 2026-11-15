/* =====================  3.17.0 Seite anpassen: gemeinsame Layout-Engine  =====================
   Seiten (Schlüssel wie in der API /api/layout/<Schlüssel>): „tour-haupt“ (#/tour/<id>), „tour-auswertung“ (#/tour/<id>/auswertung), „uebersicht“ (#/dash).
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
const SL_PAGE_KEY = {haupt: "tour-haupt", auswertung: "tour-auswertung", uebersicht: "uebersicht"};
const SL_W = {d: {voll: 12, zweidrittel: 8, halb: 6, drittel: 4}, t: {voll: 12, zweidrittel: 12, halb: 6, drittel: 6}};            // Spalten je Breite: Desktop (ab 900 px) und Tablet
const SL_WALL = ["voll", "zweidrittel", "halb", "drittel"];
const SL_WNAME = {voll: "Ganze Breite", zweidrittel: "Zwei Drittel", halb: "Halbe Breite", drittel: "Ein Drittel"};
const SL_WCLS = SL_WALL.map(k => "w-" + k);
const slTypeW = T => (T && SL_W.d[T.w] ? T.w : "voll");
const slSeiten = T => (T && T.seiten) || (T && T.fam === "tour" ? ["tour"] : ["uebersicht", "tour"]);
const slFits = (T, fam) => !!T && slSeiten(T).includes(fam);
const SL_GROUPS = {route: "Streckenverlauf", rec: "Aufzeichnung", eval: "Auswertung dieser Tour", more: "Fotos zur Tour", bst: "Bausteine"};
/* Registry: Standardseite, Gruppe, Standard „offen“ (def), fixed = kann nur auf dieser Seite stehen (wird von der Tourseite selbst aufgebaut),
   must = Pflicht (nicht ausblendbar), plain = kein einklappbarer Abschnitt, ckeys = Speicherschlüssel des Auf-/Zu-Zustands (localStorage „mt_trf_…“) */
const SL_REG = {
  tour: [
    {id: "map", w: "voll", title: "Karte", page: "haupt", group: "route", def: true, fixed: true, ckeys: ["tl_map"]},
    {id: "prof", w: "voll", title: "Höhenprofil", page: "haupt", group: "route", def: true, fixed: true, ckeys: ["tl_prof"]},
    {id: "puls", w: "halb", title: "Herzfrequenz", page: "haupt", group: "route", def: true, fixed: true, ckeys: ["tl_puls"]},
    {id: "wp", w: "halb", title: "Wegpunkte", page: "haupt", group: "route", def: true, fixed: true, ckeys: ["tl_wp"]},
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
    {id: "zuletzt", w: "voll", title: "Letzte Touren", page: "uebersicht", plain: true, ws: ["voll", "zweidrittel"]},
    {id: "tag", w: "halb", title: "An diesem Tag", page: "uebersicht", group: "cols", plain: true},
    {id: "erinn", w: "halb", title: "Erinnerungen", page: "uebersicht", group: "cols", plain: true},
  ],
};
const SL_EL = {
  tour: {
    map: () => tlSec("map"), prof: () => tlSec("prof"), puls: () => $("#pulscard"), wp: () => $("#wpcard"), sum: () => $("#tlg-sum"), photos: () => tlSec("photos"),
    geraet: () => $("#tlrec"), wx: () => tlSec("wx"), ana: () => $("#anacard"), steig: () => $("#steigcard"), aehn: () => $("#aehncard"), cmp: () => $("#cmpseg"),
  },
  uebersicht: {aufmacher: () => $("#hlast"), jahr: () => $("#hyear"), zuletzt: () => $("#hrecent"), tag: () => $("#htag"), erinn: () => $("#hmemsec")},
};
const SL = {docs: {}, loaded: {}, edit: false, dirty: new Set(), fam: "tour", page: "haupt", present: [], timer: null, focus: null, drag: null};
const slCan = () => !(typeof isViewer === "function" && isViewer());
const slUid = () => {
  try {
    return (ME.user && (ME.user.uid || ME.user.name)) || "_";
  } catch (e) {
    return "_";
  }
};
const slLsKey = k => "mt_sl_" + slUid() + "_" + k;
const slKeys = fam => (fam === "tour" ? ["tour-haupt", "tour-auswertung"] : ["uebersicht"]);
const slSt = fam => SL.docs[fam === "tour" ? "tour-haupt" : "uebersicht"] || {};
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
    it.cfg = (st.cfg || {})[it.id] || {};
    it.title = slWTitle(T, it.cfg);
    it.fl = slWFl(T, it.cfg);
  });
  (st.widgets || []).forEach(w => {
    const T = window.SL_WT[w.type];
    if (!slFits(T, fam)) return;                                          // unbekannter Baustein (z. B. von einer neueren Version) oder einer, der auf dieser Seite nicht stehen darf: ignorieren
    items.push({id: w.id, w: slTypeW(T), ws: T.ws, title: slWTitle(T, w.cfg || {}), fl: slWFl(T, w.cfg || {}), page: fam === "tour" ? "haupt" : "uebersicht", group: fam === "tour" ? "bst" : "", widget: true, plain: !!T.shell, wtype: w.type, cfg: w.cfg || {}, def: true, ckeys: ["tl_w_" + w.id]});
  });
  if (fam === "tour") items.forEach(it => !it.fixed && (pg[it.id] === "haupt" || pg[it.id] === "auswertung") && (it.page = pg[it.id]));
  items.forEach(it => {                                                   // 3.20.0: Breite = gespeicherte Abweichung, sonst Standard (immer eine der erlaubten)
    const ws = it.ws || SL_WALL, v = (st.w || {})[it.id];
    it.w = it.w && ws.includes(it.w) ? it.w : ws[0];
    it.cw = ws.includes(v) ? v : it.w;
  });
  return items;
}
/* Reihenfolge einer Seite: gespeicherte Ids (bekannte), Fehlende an ihrer Standardposition (hinter dem nächsten davor liegenden, schon eingeordneten Standard-Abschnitt) */
function slOrder(fam, page) {
  const mine = slItems(fam).filter(i => i.page === page),
    ids = mine.map(i => i.id),
    doc = SL.docs[SL_PAGE_KEY[page]] || {},
    eff = [];
  (doc.order || []).forEach(id => ids.includes(id) && !eff.includes(id) && eff.push(id));
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
const slHid = id => (slSt("tour").hidden || []).includes(slAlias(id));
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
  return j && j.layout && typeof j.layout === "object" ? j.layout : null;
}
/* Beim ersten Aufruf: Zwischenspeicher dieses Geräts sofort nutzen und im Hintergrund abgleichen; ohne Zwischenspeicher höchstens 1,5 s auf den Server warten (nie blockieren) */
async function slEnsure(fam) {
  const keys = slKeys(fam);
  if (!slCan()) {
    keys.forEach(k => delete SL.docs[k]);
    return;
  }
  const first = !SL.loaded[fam];
  if (first)
    keys.forEach(k => {
      const c = slReadCache(k);
      if (c) SL.docs[k] = c;
    });
  const pull = Promise.all(keys.map(k => slFetch(k).then(d => [k, d]).catch(() => null))).then(rs => {
    let changed = false;
    rs.forEach(r => {
      if (!r || SL.dirty.has(r[0])) return;
      const [k, d] = r;
      if (JSON.stringify(d) !== JSON.stringify(SL.docs[k] || null)) {
        if (d) SL.docs[k] = d;
        else delete SL.docs[k];
        slWriteCache(k, d);
        changed = true;
      }
    });
    return changed;
  });
  SL.loaded[fam] = true;
  if (first && !keys.some(k => SL.docs[k])) await Promise.race([pull, new Promise(r => setTimeout(r, 1500))]);
  else pull.then(ch => ch && SL.fam === fam && slApply());
}
function slStatus(text, bad) {
  const s = document.getElementById("slsaved");
  if (!s) return;
  s.textContent = text;
  s.dataset.state = bad ? "bad" : text === "Gespeichert" ? "ok" : "busy";
}
function slTouch(...keys) {
  keys.forEach(k => {
    SL.dirty.add(k);
    slWriteCache(k, SL.docs[k] || null);
  });
  slStatus("Speichert …");
  clearTimeout(SL.timer);
  SL.timer = setTimeout(slFlush, 500);
}
async function slFlush() {
  clearTimeout(SL.timer);
  const keys = [...SL.dirty];
  SL.dirty.clear();
  if (!keys.length) return;
  let ok = true;
  for (const k of keys) {
    try {
      const d = SL.docs[k],
        r = await fetch("/api/layout/" + k, d ? {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(d), credentials: "same-origin"} : {method: "DELETE", credentials: "same-origin"});
      if (!r.ok) throw new Error(String(r.status));
    } catch (e) {
      ok = false;
    }
  }
  if (SL.dirty.size) return;                                              // inzwischen weitere Änderungen: der nächste Lauf meldet
  slStatus(ok ? "Gespeichert" : "Nicht gespeichert – nur auf diesem Gerät gemerkt", !ok);
}
const slDocOf = page => SL.docs[SL_PAGE_KEY[page]] || (SL.docs[SL_PAGE_KEY[page]] = {v: 1});
const slStDoc = fam => slDocOf(fam === "tour" ? "haupt" : "uebersicht");
const slSet = (st, name, id, on) => {
  const a = (st[name] || []).filter(x => x !== id);
  if (on) a.push(id);
  if (a.length) st[name] = a;
  else delete st[name];
};

/* ---------- Änderungen (Bearbeitungsmodus) ---------- */
const slLive = t => {
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
  slDocOf(SL.page).order = ids;
  slTouch(SL_PAGE_KEY[SL.page]);
}
function slMove(id, beforeId) {
  const cur = slOrder(SL.fam, SL.page).map(i => i.id).filter(x => x !== id),
    at = beforeId ? cur.indexOf(beforeId) : -1;
  if (at < 0) cur.push(id);
  else cur.splice(at, 0, id);
  if (cur.join() === slOrder(SL.fam, SL.page).map(i => i.id).join()) return;          // nichts geändert
  slSaveOrder(cur);
  slApply();
  const n = cur.length;
  slLive(`${slTitle(id)}: Position ${cur.indexOf(id) + 1} von ${n}`);
}
function slStep(id, d) {
  const ord = SL.present.length ? SL.present.slice() : slOrder(SL.fam, SL.page).map(i => i.id),
    i = ord.indexOf(id),
    j = i + d;
  if (i < 0 || j < 0 || j >= ord.length) {
    slLive(`${slTitle(id)}: ${d < 0 ? "ganz oben" : "ganz unten"}`);
    return;
  }
  if (d < 0) slMove(id, ord[j]);
  else slMove(id, ord[j + 1] || null);
}
function slToggleHidden(id) {
  const st = slStDoc(SL.fam),
    on = !(st.hidden || []).includes(id);
  slSet(st, "hidden", id, on);
  slTouch(SL.fam === "tour" ? "tour-haupt" : "uebersicht");
  slApply();
  slLive(on ? `${slTitle(id)}: ausgeblendet` : `${slTitle(id)}: eingeblendet`);
}
function slSetOpen(id, on) {
  const it = slItems(SL.fam).find(i => i.id === id);
  if (!it) return;
  const st = slStDoc(SL.fam);
  slSet(st, "open", id, on && !it.def);                                     // nur Abweichungen vom Standard speichern
  slSet(st, "closed", id, !on && !!it.def);
  slTouch(SL.fam === "tour" ? "tour-haupt" : "uebersicht");
  (it.ckeys || []).forEach(k => {
    try {
      localStorage.removeItem("mt_trf_" + k);                               // sonst überstimmt der zuletzt gemerkte Zustand den neuen Standard
    } catch (e) {}
  });
  const secs = id === "geraet" ? ["met", "uhr"] : [id];
  secs.forEach(s => {
    const d = tlSec(s) || document.querySelector(`#tls-${s}`);
    if (d && d.tagName === "DETAILS") d.open = on;
  });
  slLive(`${it.title}: ${on ? "standardmäßig offen" : "standardmäßig zu"}`);
}
function slSetPage(id, page) {
  if (SL.fam !== "tour") return;
  const it = slItems("tour").find(i => i.id === id);
  if (!it || it.fixed) return;
  const from = SL.page,
    fromIds = slOrder("tour", from).map(i => i.id).filter(x => x !== id),
    st = slStDoc("tour");
  st.page = st.page || {};
  if (!it.widget && page === SL_REG.tour.find(r => r.id === id).page) delete st.page[id];
  else st.page[id] = page;
  if (!Object.keys(st.page).length) delete st.page;
  slDocOf(from).order = fromIds;
  const toIds = slOrder("tour", page).map(i => i.id).filter(x => x !== id);
  toIds.push(id);
  slDocOf(page).order = toIds;
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
  slTouch(SL.fam === "tour" ? "tour-haupt" : "uebersicht");
  SL.focus = {id, a: "w", q: `[data-w="${w}"]`};
  slApply();
  slLive(`${slTitle(id)}: ${SL_WNAME[w]}`);
}
function slAddWidget(type) {
  const T = window.SL_WT[type];
  if (!slFits(T, SL.fam)) return null;
  const st = slStDoc(SL.fam);
  if ((st.widgets || []).length >= 40) {
    uiAlert("Es sind höchstens 40 Bausteine möglich.");
    return null;
  }
  let id;
  do id = "w" + Math.random().toString(36).slice(2, 7);
  while ((st.widgets || []).some(w => w.id === id));
  st.widgets = (st.widgets || []).concat([{id, type, cfg: JSON.parse(JSON.stringify(T.defaults || {}))}]);
  if (SL.fam === "tour" && SL.page === "auswertung") (st.page = st.page || {})[id] = "auswertung";
  const ids = slOrder(SL.fam, SL.page).map(i => i.id).filter(x => x !== id);
  ids.push(id);
  slSaveOrder(ids);
  slTouch(SL.fam === "tour" ? "tour-haupt" : "uebersicht");
  SL.focus = {id, a: "grip"};
  slApply();
  slLive(`Baustein „${T.title(T.defaults || {})}“ hinzugefügt`);
  return id;
}
function slRemoveWidget(id) {
  const st = slStDoc(SL.fam);
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
  slKeys(SL.fam).forEach(k => SL.docs[k] && SL.docs[k].order && (SL.docs[k].order = SL.docs[k].order.filter(x => x !== id)));
  slTouch(...slKeys(SL.fam));
  const el = document.getElementById("tlw-" + id);
  if (el) el.remove();
  SL.focus = null;
  slApply();
}
/* Baustein zu einer Kennung: hinzugefügter Baustein oder Standard-Baustein mit Konfiguration (cfg[id]) */
function slWidgetOf(id) {
  const st = slSt(SL.fam), w = (st.widgets || []).find(x => x.id === id);
  if (w) return {id, type: w.type, cfg: w.cfg || {}, widget: true};
  const r = SL_REG[SL.fam].find(x => x.id === id && x.build);
  return r ? {id, type: r.build, cfg: (st.cfg || {})[id] || {}} : null;
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
  slTouch(SL.fam === "tour" ? "tour-haupt" : "uebersicht");
  const el = document.getElementById("tlw-" + id);
  if (el) el.remove();                                                      // wird mit der neuen Konfiguration neu gebaut
  SL.focus = {id, a: "cfg"};
  slApply();
}
async function slReset() {
  const ok = await uiConfirm({
    title: "Standard wiederherstellen?",
    text: SL.fam === "tour"
      ? "Reihenfolge, ausgeblendete Abschnitte, Seitenzuordnung und alle hinzugefügten Bausteine der Tourseite (Hauptseite und Auswertung) werden zurückgesetzt."
      : "Reihenfolge, ausgeblendete Abschnitte und alle hinzugefügten Bausteine der Übersicht werden zurückgesetzt.",
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
  h += `<span class="slnm">${nm}${it.fl ? ` <small class="slfl mut">${esc(it.fl)}</small>` : ""}</span>`;
  if (p.off) h += `<span class="slhid">ausgeblendet</span>`;
  h += `<span class="slbs">`;
  if ((it.ws || SL_WALL).length > 1) h += `<span class="slwd" role="group" aria-label="Breite">${(it.ws || SL_WALL).map(k => `<button type="button" class="slw" data-a="w" data-w="${k}" aria-pressed="${k === p.cw}" aria-label="${SL_WNAME[k]}" title="${SL_WNAME[k]}">${slWIcon(k)}</button>`).join("")}</span>`;
  h += `<button type="button" class="slb" data-a="up" aria-label="Nach oben" title="Nach oben"${dis(idx === 0)}>↑</button>`;
  h += `<button type="button" class="slb" data-a="down" aria-label="Nach unten" title="Nach unten"${dis(idx === n - 1)}>↓</button>`;
  if (!it.must) h += `<button type="button" class="slb" data-a="eye" aria-pressed="${p.off}">${p.off ? slIcon.eyeoff : slIcon.eye}<span>${p.off ? "Einblenden" : "Ausblenden"}</span></button>`;
  if (!it.plain) h += `<label class="slsw"><input type="checkbox" data-a="open"${open ? " checked" : ""}><span>Standardmäßig offen</span></label>`;
  if (SL.fam === "tour" && !it.fixed) h += `<button type="button" class="slb" data-a="page" >${other}</button>`;
  if ((it.widget || it.build) && ((window.SL_WT[it.wtype] || {}).fields || []).length) h += `<button type="button" class="slb slcfgb" data-a="cfg" aria-haspopup="dialog" title="Einstellungen dieses Bausteins">${slIcon.gear}<span>Einstellungen</span></button>`;
  if (it.widget) h += `<button type="button" class="slb slrm" data-a="del" >Entfernen</button>`;
  if (it.must) h += `<span class="slmust">bleibt immer sichtbar</span>`;
  return h + `</span>`;
}
function slPlace(root) {
  const main = root.matches && root.matches("main.home"),
    fam = main ? "uebersicht" : "tour",
    page = main ? "uebersicht" : root.classList.contains("tlsub") ? "auswertung" : "haupt";
  SL.fam = fam;
  SL.page = page;
  SL.root = root;
  const items = slOrder(fam, page),
    edit = SL.edit && slCan(),
    st = slSt(fam),
    hid = st.hidden || [],
    mine = new Set(items.map(i => i.id));
  root.querySelectorAll(".tlw[data-wid]").forEach(e => !mine.has(e.dataset.wid) && e.remove());        // Baustein einer anderen Seite oder entfernt
  const pres = [];
  items.forEach(it => {
    let el = (SL_EL[fam][it.id] || (() => document.getElementById("tlw-" + it.id)))();
    if (el && (it.widget || it.build) && el.dataset.sig !== undefined && el.dataset.sig !== slSig(it)) {
      el.remove();                                                            // Konfiguration hat sich geändert (auch durch Abgleich mit dem Server): neu bauen
      el = null;
    }
    if (!el && (it.widget || it.build) && typeof window.slWidgetBuild === "function") el = window.slWidgetBuild(it, root);
    if (!el || slSelfHidden(it, el)) return;
    pres.push({it, el, off: hid.includes(it.id) && !it.must, cw: it.cw});
  });
  SL.present = pres.map(p => p.it.id);
  const blocks = [];
  let cur = null;
  const cnt = {};
  pres.forEach(p => {
    p.unit = slUnit(p, edit);
    slCell(p, fam !== "tour" || (!!p.it.group && !p.it.own));
    p.el.classList.toggle("sl-off", p.off && !edit);
    p.unit.classList.toggle("sl-dim", edit && p.off && p.unit !== p.el);
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
      const r = slRun(root, fam, b.g, b.n);
      used.add(r.el);
      slPlaceIn(r.body, b.ps.map(p => p.unit));
      r.el.hidden = !b.ps.some(p => edit || !p.off);                          // eine Gruppe ohne sichtbaren Inhalt zeigt keine Überschrift
      return r.el;
    });
  if (fam === "tour") root.querySelectorAll(":scope > .tlg:not(.tlsumg)").forEach(g => !used.has(g) && (g.hidden = true));
  const op = slOpener(root, edit);
  slPlaceIn(root, main ? [op, ...seq] : seq);
  if (edit)
    pres.forEach((p, i) => {
      const w = p.unit;
      if (w === p.el) return;
      const sig = [i, pres.length, p.off, p.cw, slDef(p.it.id, !!p.it.def), SL.page, p.it.title, p.it.fl || ""].join("|");
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
      }
    });
  root.querySelectorAll(".slit").forEach(w => !w.querySelector(":scope > :not(.slst)") && w.remove());
  if (edit && SL.focus) {
    const f = SL.focus;
    SL.focus = null;
    const w = root.querySelector(`.slit[data-sl="${f.id}"]`),
      b = w && ((f.q && w.querySelector(`[data-a="${f.a}"]${f.q}`)) || w.querySelector(`[data-a="${f.a}"]`) || w.querySelector('[data-a="grip"]'));
    if (b) b.focus({preventScroll: !!f.ps});
  }
  slSubNote(root, pres);
  if (fam === "tour") slWatchMap();
  slRaster();
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
    w.innerHTML = `<button type="button" class="btn ghost sm" id="slopen" data-a="edit">${slIcon.sliders}<span>Seite anpassen</span></button>`;
  }
  w.hidden = !!edit;
  if (!root.matches("main.home") && w.nextElementSibling !== root) root.parentNode.insertBefore(w, root);
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
      e.insertAdjacentHTML("afterbegin", '<h2 class="slmoved">Hier gibt es nichts anzuzeigen</h2><p class="mut slmoved">Abschnitte, die du auf die Hauptseite gelegt hast, findest du dort. Mit „Seite anpassen“ lassen sie sich zurückholen.</p>');
    } else if (!moved && n) e.querySelectorAll(".slmoved").forEach(x => x.remove());
  }
}
function slApply() {
  if (SL.fam === "tour") {
    if (typeof tlRefresh === "function") tlRefresh();
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
    `<p class="slbi"><b>Seite anpassen</b><span class="slsaved" id="slsaved" role="status" aria-live="polite"></span></p>` +
    `<div class="slbb"><button type="button" class="btn ghost sm" data-a="add">Baustein hinzufügen</button><button type="button" class="btn ghost sm" data-a="reset">Standard wiederherstellen</button><button type="button" class="btn sm" data-a="done">Fertig</button></div>`;
  document.body.appendChild(b);
}
function slEdit(on) {
  on = !!on && slCan();
  if (on === SL.edit) return;
  SL.edit = on;
  document.body.classList.toggle("sl-editing", on);
  slBar(on);
  SL.focus = on ? {id: SL.present[0] || "", a: "grip", ps: true} : null;
  slApply();
  if (on) slLive("Seite anpassen ist an. Abschnitte ziehen oder mit den Pfeiltasten verschieben.");
  else {
    slFlush();
    const o = document.getElementById("slopen");
    if (o) o.focus();
  }
}
function slLeave() {
  if (!SL.edit) return;
  SL.edit = false;
  document.body.classList.remove("sl-editing");
  slBar(false);
  slFlush();
}

/* ---------- Dialoge (Katalog, Einstellungen) ---------- */
function slModal(title, build, cls) {
  const trigger = document.activeElement,
    host = document.createElement("div"),
    box = document.createElement("div"),
    id = "sld" + Math.random().toString(36).slice(2, 7);
  host.className = "uidlg sldlg";
  box.className = "uibox slbox" + (cls ? " " + cls : "");
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  box.setAttribute("aria-labelledby", id);
  box.tabIndex = -1;
  const h = document.createElement("h2");
  h.id = id;
  h.textContent = title;
  const body = document.createElement("div");
  body.className = "slmb";
  box.append(h, body);
  host.appendChild(box);
  const inerted = [];
  [...document.body.children].forEach(el => {
    if (!el.inert) {
      el.inert = true;
      inerted.push(el);
    }
  });
  document.body.appendChild(host);
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    host.removeEventListener("keydown", key, true);
    host.remove();
    inerted.forEach(el => (el.inert = false));
    if (trigger && trigger.isConnected && trigger.focus) {
      try {
        trigger.focus();
      } catch (e) {}
    }
  };
  const key = e => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close();
    } else if (e.key === "Tab") {
      const f = [...box.querySelectorAll("button:not([disabled]),input:not([disabled]),textarea,select,a[href]")].filter(x => x.offsetParent !== null);
      if (!f.length) return;
      const i = f.indexOf(document.activeElement);
      if (e.shiftKey && i <= 0) {
        e.preventDefault();
        f[f.length - 1].focus();
      } else if (!e.shiftKey && (i === f.length - 1 || i < 0)) {
        e.preventDefault();
        f[0].focus();
      }
    }
  };
  host.addEventListener("keydown", key, true);
  host.addEventListener("mousedown", e => e.target === host && close());
  build(body, close);
  const f = body.querySelector("button, input, textarea, select");
  (f || box).focus();
  return {close, box};
}
function slCatalog() {
  const list = Object.entries(window.SL_WT).filter(([, T]) => slFits(T, SL.fam)),
    have = type => (slSt(SL.fam).widgets || []).filter(w => w.type === type).length,
    cats = SL_CATS.filter(([k]) => list.some(([, T]) => (T.cat || "zahlen") === k)),
    card = ([type, T]) => {
      const n = have(type),
        dis = !T.multi && n > 0;
      return `<article class="slcard" data-cat="${T.cat || "zahlen"}"><div class="slpv" aria-hidden="true">${T.preview ? T.preview() : ""}</div><div class="slci"><h3>${esc(T.name || T.title(T.defaults || {}))}</h3><p>${esc(T.desc || "")}</p>` +
        `<button type="button" class="btn sm${dis ? " ghost" : ""}" data-add="${type}"${dis ? " disabled" : ""}>${dis ? "Bereits hinzugefügt" : n ? "Noch einmal hinzufügen" : "Hinzufügen"}</button></div></article>`;
    };
  slModal("Baustein hinzufügen", (body, close) => {
    body.innerHTML =
      `<p class="mut slcatin">Bausteine zeigen Auswertungen aus deinen vorhandenen Daten. Die Vorschau zeigt Beispielwerte.</p>` +
      `<div class="slfilt"><div class="slchips" role="group" aria-label="Kategorie"><button type="button" class="slchip" data-cat="" aria-pressed="true">Alle</button>` +
      cats.map(([k, l]) => `<button type="button" class="slchip" data-cat="${k}" aria-pressed="false">${l}</button>`).join("") +
      `</div><label class="slsr" for="slq">Bausteine suchen</label><input id="slq" type="search" class="slq" placeholder="Bausteine suchen …" autocomplete="off" enterkeyhint="search"></div>` +
      `<p class="mut slcnt" role="status" aria-live="polite"></p><div class="slcatl">` +
      cats.map(([k, l]) => `<section class="slsec" data-cat="${k}"><h3 class="slcath">${l}</h3><div class="slcats">${list.filter(([, T]) => (T.cat || "zahlen") === k).map(card).join("")}</div></section>`).join("") +
      `</div><p class="slnorsl mut" hidden>Nichts gefunden. Probiere einen anderen Suchbegriff oder eine andere Kategorie.</p><div class="uifoot"><button type="button" class="btn ghost" data-close>Schließen</button></div>`;
    let cat = "";
    const q = body.querySelector("#slq"),
      cnt = body.querySelector(".slcnt"),
      none = body.querySelector(".slnorsl"),
      apply = () => {
        const term = q.value.trim().toLowerCase();
        let n = 0;
        body.querySelectorAll(".slsec").forEach(sec => {
          let any = 0;
          sec.querySelectorAll(".slcard").forEach(cd => {
            const ok = (!cat || cd.dataset.cat === cat) && (!term || cd.textContent.toLowerCase().includes(term));
            cd.hidden = !ok;
            any += ok ? 1 : 0;
          });
          sec.hidden = !any;
          n += any;
        });
        none.hidden = n > 0;
        cnt.textContent = n === 1 ? "1 Baustein" : `${n} Bausteine`;
        body.querySelectorAll(".slchip").forEach(c => c.setAttribute("aria-pressed", String(c.dataset.cat === cat)));
      };
    apply();
    q.addEventListener("input", apply);
    q.addEventListener("keydown", e => e.key === "Enter" && e.preventDefault());
    body.onclick = e => {
      const a = e.target.closest("[data-add]"),
        ch = e.target.closest(".slchip");
      if (e.target.closest("[data-close]")) close();
      else if (ch) {
        cat = ch.dataset.cat;
        apply();
      } else if (a && !a.disabled) {
        close();
        const id = slAddWidget(a.dataset.add);
        if (id && (window.SL_WT[a.dataset.add].fields || []).length && window.SL_WT[a.dataset.add].cfgOnAdd) slCfgDialog(id);
      }
    };
  }, "slcat");
}
function slCfgDialog(id) {
  const w = slWidgetOf(id),
    T = w && window.SL_WT[w.type];
  if (!T) return;
  slModal(`Einstellungen: ${T.name || T.title(w.cfg)}`, (body, close) => {
    const cfg = JSON.parse(JSON.stringify(w.cfg || {}));
    body.innerHTML = `<form class="slform" novalidate>${(T.fields || []).map((f, i) => slField(f, cfg, i)).join("")}<div class="uifoot"><button type="button" class="btn ghost" data-close>Abbrechen</button><button type="submit" class="btn">Speichern</button></div></form>`;
    const form = body.querySelector("form");
    form.onsubmit = e => {
      e.preventDefault();
      const out = {...cfg};
      let bad = null;
      (T.fields || []).forEach((f, i) => {
        if (FL_KINDS.has(f.kind)) flRead(f, form, i, out);
        else if (f.kind === "checks") out[f.k] = [...form.querySelectorAll(`input[name="f${i}"]:checked`)].map(x => x.value);
        else if (f.kind === "radio") {
          const v = (form.querySelector(`input[name="f${i}"]:checked`) || {}).value || cfg[f.k] || f.def;
          out[f.k] = f.num ? +v : v;
        }
        else if (f.kind === "text") out[f.k] = form.querySelector(`[name="f${i}"]`).value.slice(0, f.max || 500);
        else if (f.kind === "number") {
          const inp = form.querySelector(`[name="f${i}"]`),
            v = parseFloat(String(inp.value).replace(",", "."));
          out[f.k] = v;
          if (!(v >= f.min && v <= f.max)) bad = bad || {inp, msg: `Bitte eine Zahl von ${f.min} bis ${f.max} eingeben.`};
        }
      });
      if (bad) {
        const er = bad.inp.closest(".slfs").querySelector(".slerr");
        if (er) er.textContent = bad.msg;
        bad.inp.focus();
        return;
      }
      if (T.fields.some(f => f.kind === "checks" && f.min && out[f.k].length < f.min)) {
        form.querySelector(".slerr").textContent = "Bitte mindestens einen Wert wählen.";
        return;
      }
      (T.fields || []).forEach(f => f.kind === "checks" && f.def && out[f.k].join() === f.def.join() && delete out[f.k]);          // Standardwerte nicht speichern
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
function slField(f, cfg, i) {
  const id = "slf" + i;
  if (FL_KINDS.has(f.kind)) return flField(f, cfg, i);
  if (f.kind === "checks")
    return `<fieldset class="slfs"><legend>${esc(f.label)}</legend><div class="flchips">${f.options.map(([v, l]) => `<label class="flchip"><input type="checkbox" name="f${i}" value="${v}"${(cfg[f.k] || f.def || []).includes(v) ? " checked" : ""}><span>${esc(l)}</span></label>`).join("")}</div><p class="slerr" role="alert"></p></fieldset>`;
  if (f.kind === "radio")
    return `<fieldset class="slfs"><legend>${esc(f.label)}</legend><div class="flchips">${f.options.map(([v, l]) => `<label class="flchip"><input type="radio" name="f${i}" value="${v}"${String(cfg[f.k] ?? f.def) === String(v) ? " checked" : ""}><span>${esc(l)}</span></label>`).join("")}</div></fieldset>`;
  if (f.kind === "number")
    return `<div class="slfs"><label for="${id}">${esc(f.label)}</label><input id="${id}" name="f${i}" type="number" inputmode="decimal" min="${f.min}" max="${f.max}" step="${f.step || 1}" value="${esc(cfg[f.k] ?? "")}" required><p class="slerr" role="alert"></p></div>`;
  const max = f.max || 500;
  return `<div class="slfs"><label for="${id}">${esc(f.label)}</label><textarea id="${id}" name="f${i}" rows="6" maxlength="${max}" data-max="${max}">${esc(cfg[f.k] || "")}</textarea><p class="mut slcount">${(cfg[f.k] || "").length} / ${max}</p></div>`;
}

/* ---------- Ereignisse ---------- */
document.addEventListener("click", e => {
  const o = e.target.closest && e.target.closest("#slopen"),
    bar = e.target.closest && e.target.closest("#slbar [data-a]"),
    b = e.target.closest && e.target.closest(".slst button[data-a]");
  if (o) return slEdit(true);
  if (bar) {
    const a = bar.dataset.a;
    if (a === "done") slEdit(false);
    else if (a === "add") slCatalog();
    else if (a === "reset") slReset();
    return;
  }
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
  else if (a === "del")
    uiConfirm({title: "Baustein entfernen?", text: `„${slTitle(id)}“ wird von dieser Seite entfernt.`, ok: "Entfernen", danger: true}).then(ok => ok && slRemoveWidget(id));
});
document.addEventListener("change", e => {
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
  const ws = [...(SL.root || document).querySelectorAll(".slit")].filter(x => x !== d.w);
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
  try {
    d.g.releasePointerCapture(d.pid);
  } catch (x) {}
  if (cancel || Math.hypot(d.y - d.y0, d.x - d.x0) < 4) return;
  slDragTarget(d);
  document.querySelectorAll(".sl-before,.sl-after").forEach(x => x.classList.remove("sl-before", "sl-after"));
  SL.focus = {id: d.id, a: "grip"};
  slMove(d.id, d.target);
}
document.addEventListener("pointerup", e => slDragEnd(e, false));
document.addEventListener("pointercancel", e => slDragEnd(e, true));
window.addEventListener("hashchange", slLeave);

/* ---------- Anbindung an die Ansichten ---------- */
function slViewStart(fam) {
  slLeave();
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
  await _tour49(...a);
};
const _aus49 = VIEWS.tourauswertung;
VIEWS.tourauswertung = async (...a) => {
  slViewStart("tour");
  const tok = window._rt;
  await slEnsure("tour");
  if (tok !== window._rt) return STALE();                            // inzwischen eine andere Seite geöffnet
  await _aus49(...a);
};
const _dash49 = VIEWS.dash;
VIEWS.dash = async (...a) => {
  slViewStart("uebersicht");
  const tok = window._rt;
  await slEnsure("uebersicht");
  if (tok !== window._rt) return STALE();                            // inzwischen eine andere Seite geöffnet
  await _dash49(...a);
  const m = document.getElementById("main");
  if (m && m.classList.contains("home") && m.querySelector("#hlast")) slPlace(m);
};
