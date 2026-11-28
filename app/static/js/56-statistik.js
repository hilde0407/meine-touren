/* =====================  3.22.0 Statistik als Widget-Seite + globaler Filter  =====================
   Die Statistikseite (#/stats, Reiter „Übersicht“; Aufbau in 02-uebersicht.js, 06-erweiterungen.js „Ziele“, 46-belastung.js „Belastung“ und „Tempo“) ist jetzt wie die Übersicht anpassbar
   (Layout-Schlüssel „statistik“, Engine 49-seitenlayout.js). Kapselung statt Neuschreibung: Die bisherigen Abschnitte bauen sich wie vorher selbst auf; nach dem Aufbau steckt stBuild() jeden
   Abschnitt unverändert (samt seiner Steuerung und seinen Ereignissen) in eine Karte im Format von tlCard (einklappbar, Kopf mit Kurzaussage) und übergibt sie der Engine (slPlace).
   Globaler Filter (Sportart, Zeitraum): steht in der Adresse (#/stats?y=2025&s=hike,mtb | z=12m | z=90d | z=c&von=…&bis=…), bleibt also beim Neuladen erhalten und ist teilbar.
     s    Sportarten (Mehrfachauswahl, leer = alle)     y   Jahr     z   12m | 90d | c (frei: von, bis als JJJJ-MM-TT)     ohne Angabe: alle Sportarten, gesamte Zeit (wie bisher)
   Wer den Filter übernimmt, entscheidet die Fähigkeit des Abschnitts (ST_CAP) bzw. das Schema des Bausteins (Felder „sports“ und „range“): übernommen wird, was der Baustein kennt;
   was er nicht kennt, zeigt ein dezenter Hinweis im Kopf („Filter gilt hier nicht“, „Sportart gilt hier nicht“, „Zeitraum gilt hier nicht“). Das ist ehrlicher als ein stilles Ignorieren
   und lässt die Abschnitte unverändert, deren Daten nicht nach Sportart oder Zeitraum zu trennen sind (Uhr-Belastung, Tempo-Rechner, Erinnerungen). Ein Baustein mit eigenem Filter
   (Einstellungen → „Globalen Filter verwenden“ aus, Feld „eigen“) behält seine Einstellung. */
const ST = {F: {sports: [], kind: "all", yr: 0, von: "", bis: ""}, focus: "", base: null};
const ST_SPORT = /^(?:sgrp:[a-z0-9]{1,12}|[A-Za-z0-9_]{1,40})$/, ST_DATE = /^\d{4}-\d{2}-\d{2}$/;
/* Fähigkeit der festen Abschnitte: s = Sportart, r = Zeitraum (1 = ja, "y" = nur als Jahr, 0 = nein) */
const ST_CAP = {
  kpi: {s: 1, r: 1}, kmmonat: {s: 1, r: 1}, kmverlauf: {s: 1, r: 1}, sportarten: {s: 0, r: 1}, heat: {s: 1, r: 1},          // 3.45.0: „Ziele“ und „Bestwerte“ sind Bausteine (Filter über ihr Schema)
  bl: {s: 0, r: 0}, tp: {s: 0, r: 0}, tag: {s: 0, r: 0}, erinn: {s: 0, r: 0},
};
const ST_ICON = {kpi: "met", kmmonat: "met", kmverlauf: "trend", sportarten: "map", heat: "met", tag: "cmp", erinn: "cam"};

/* 3.22.0 Der Filter gehört zur Ansicht: gespeichert im Layout der Ansicht (Feld „filter“: {sports, range, yr, from, to}). Ohne Angabe in der Adresse gilt der Stand dieser Sitzung (sessionStorage,
   solange nicht gespeichert oder verworfen), sonst der gespeicherte Filter der Ansicht, sonst der alte Standard (alle Sportarten, gesamte Zeit). „z=all“ in der Adresse = ausdrücklich alles. */
const ST_DEF = () => ({sports: [], kind: "all", yr: 0, von: "", bis: ""});
function stFromDoc(d) {
  if (!d || typeof d !== "object") return ST_DEF();
  const r = d.range, sp = sgClean(sNormList((Array.isArray(d.sports) ? d.sports : []).filter(x => ST_SPORT.test(x)))).slice(0, 20);      // 3.59.0: gelöschte Gruppe fällt weg
  if (r === "y" && d.yr >= 1970) return {sports: sp, kind: "y", yr: +d.yr, von: "", bis: ""};
  if (r === "12m" || r === "90d") return {sports: sp, kind: r, yr: 0, von: "", bis: ""};
  if (r === "year") return {sports: sp, kind: "y", yr: new Date().getFullYear(), von: "", bis: ""};
  if (r === "c" && ST_DATE.test(d.from) && ST_DATE.test(d.to)) return {sports: sp, kind: "c", yr: 0, von: d.from, bis: d.to};
  return {sports: sp, kind: "all", yr: 0, von: "", bis: ""};
}
function stToDoc(F) {
  const d = {range: F.kind};
  if (F.sports.length) d.sports = F.sports.slice();
  if (F.kind === "y") d.yr = F.yr;
  if (F.kind === "c") {
    d.from = F.von;
    d.to = F.bis;
  }
  return d;
}
const stSaved = () => stFromDoc((SL.docs.statistik || {}).filter);
const stSame = (a, b) => JSON.stringify(stToDoc(a)) === JSON.stringify(stToDoc(b));
const stSsKey = () => "mt_stf_" + slUid() + "_" + (SL.view.statistik || "");
function stStored() {
  try {
    const v = sessionStorage.getItem(stSsKey());
    return v ? stFilter(new URLSearchParams(v)) : null;
  } catch (e) {
    return null;
  }
}
function stStore(F) {
  try {
    if (stSame(F, stSaved())) sessionStorage.removeItem(stSsKey());
    else sessionStorage.setItem(stSsKey(), stHash(F).replace(/^#\/stats\??/, ""));
  } catch (e) {}
}
const stDirty = () => !stSame(ST.F, stSaved());
function stReload(edit) {
  ST.reedit = !!edit && SL.edit;                          // Bearbeitungsmodus nach dem Neuaufbau wieder aufnehmen (z. B. Ansichtswechsel im Bearbeiten)
  if (location.hash === "#/stats") route();
  else location.hash = "#/stats";
}
SLF.statistik = {
  dirty: stDirty,
  apply(doc) {
    if (stDefault(ST.F)) delete doc.filter;
    else doc.filter = stToDoc(ST.F);
    try {
      sessionStorage.removeItem(stSsKey());
    } catch (e) {}
  },
  discard(id) {
    try {
      sessionStorage.removeItem(id ? "mt_stf_" + slUid() + "_" + id : stSsKey());
    } catch (e) {}
    if (!id) stReload();
  },
};

function stFilter(q) {
  const has = q && q.get && ["y", "z", "s", "von", "bis"].some(k => q.has(k));
  if (!has && ST.base) return ST.base;
  const g = k => (q && q.get && q.get(k)) || "",
    sports = sgClean(sNormList(g("s").split(",").filter(x => ST_SPORT.test(x)))).slice(0, 20),
    y = +g("y"), z = g("z"), von = g("von"), bis = g("bis");
  let kind = "all", yr = 0;
  if (y >= 1970 && y <= 2100) {
    kind = "y";
    yr = y;
  } else if (z === "12m" || z === "90d") kind = z;
  else if (z === "c" && ST_DATE.test(von) && ST_DATE.test(bis) && von <= bis) kind = "c";
  return {sports, kind, yr, von: kind === "c" ? von : "", bis: kind === "c" ? bis : ""};
}
const stRange = F => (F.kind === "c" ? flRange({range: "c", from: F.von, to: F.bis}) : flRange({range: F.kind, yr: F.yr}, "all"));
const stDefault = F => F.kind === "all" && !F.sports.length;
function stHash(F) {
  const p = [];
  if (stDefault(F) && !stDefault(stSaved())) return "#/stats?z=all";
  if (F.kind === "y") p.push("y=" + F.yr);
  else if (F.kind !== "all") {
    p.push("z=" + F.kind);
    if (F.kind === "c") p.push("von=" + F.von, "bis=" + F.bis);
  }
  if (F.sports.length) p.push("s=" + F.sports.map(encodeURIComponent).join(","));
  return "#/stats" + (p.length ? "?" + p.join("&") : "");
}
const stSportsTxt = F => (F.sports.length <= 2 ? F.sports.map(sName).join(" und ") : `${F.sports.length} Sportarten`);      // Gruppen mit ihrem Namen (sName kennt „sgrp:<id>“)

/* ---------- Filterleiste (oben auf der Seite; nutzt flRange/flIn aus 53-filter.js) ---------- */
function stFilterBar(F, R, n, inRange) {
  const ys = years(), cy = new Date().getFullYear(), km = {};
  inRange.forEach(t => {
    km[t.sport] = (km[t.sport] || 0) + t.km;
    if (isSg(sgKey(t.sport))) km[sgKey(t.sport)] = (km[sgKey(t.sport)] || 0) + t.km;            // 3.59.0: jede Statistik-Gruppe als eigener Eintrag (zusätzlich zu ihren Sportarten)
  });
  const sports = sportOrder(Object.keys(km).filter(k => !isSg(k)));             // 3.60.1: wie Karte und Baustein-Filter (Gruppen, dann Katalog-Reihenfolge)
  F.sports.forEach(s => !sports.includes(s) && sports.push(s));
  const title = (F.kind === "y" ? "Das Jahr " + F.yr : F.kind === "all" ? "Alle Touren" : R.label) + (F.sports.length ? ", " + stSportsTxt(F) : ""),
    Z = [["year", "Laufendes Jahr", F.kind === "y" && F.yr === cy], ["12m", "Letzte 12 Monate", F.kind === "12m"], ["90d", "Letzte 90 Tage", F.kind === "90d"], ["prev", "Vorjahr", F.kind === "y" && F.yr === cy - 1], ["c", "Von–bis …", F.kind === "c"]],
    sum = [F.sports.length ? stSportsTxt(F) : "", F.kind === "all" ? "" : R.label].filter(Boolean).join(", ");
  return `<section class="stf" id="stf" aria-label="Filter der Statistik">
  <div class="sec"><h2>${esc(title)}</h2><span class="sub">${fmtAnzahl(n, "Tour", "Touren")}</span></div>
  <div class="years" role="group" aria-label="Zeitraum: Jahr"><button type="button" data-y="0" aria-pressed="${F.kind === "all"}" class="${F.kind === "all" ? "on" : ""}">Gesamte Zeit</button>${ys.map(y => `<button type="button" data-y="${y}" aria-pressed="${F.kind === "y" && F.yr === y}" class="${F.kind === "y" && F.yr === y ? "on" : ""}">${y}</button>`).join("")}</div>
  <div class="chips mt14 stz" role="group" aria-label="Zeitraum: weitere">${Z.map(([k, l, on]) => `<button type="button" class="chip${on ? " on" : ""}" data-z="${k}" aria-pressed="${on}"${k === "c" ? ' aria-controls="stfc"' : ""}>${l}</button>`).join("")}</div>
  <form class="stfc" id="stfc"${F.kind === "c" ? "" : " hidden"} novalidate><label>Von <input type="date" name="von" value="${F.von}"></label><label>Bis <input type="date" name="bis" value="${F.bis}"></label><button class="btn sm" type="submit">Anzeigen</button><span class="stfe" role="alert"></span></form>
  <div class="chips mt14" id="sch" role="group" aria-label="Sportart">${sportFilterHtml(sports.filter(s => !isSg(s)), F.sports, (k, l, x) => `<button type="button" class="chip ${x.on ? "on" : ""}" data-s="${esc(k)}" aria-pressed="${x.on}"${x.title ? ` title="${esc(x.title)}" aria-label="${esc(x.title)}"` : ""}>${x.all ? "" : `<i style="background:${x.color}"></i>`}${esc(l)}</button>`)}</div>
  ${stDefault(F) || (!stDirty() && !stDefault(stSaved())) ? "" : `<p class="stfs mut"><span>Filter aktiv: ${esc(sum)}.</span> <a href="#/stats" id="stfr">${stDirty() ? "Auf den gespeicherten Filter zurücksetzen" : "Filter zurücksetzen"}</a></p>`}</section>`;
}
function stFilterBind(F) {
  const bar = document.getElementById("stf");
  if (!bar) return;
  const go = (G, sel) => {
    ST.focus = sel;
    location.hash = stHash(G);
  };
  const rs = bar.querySelector("#stfr");
  if (rs) rs.addEventListener("click", e => {
    e.preventDefault();
    SLF.statistik.discard("");
  });
  bar.addEventListener("click", e => {
    const y = e.target.closest(".years [data-y]"), z = e.target.closest("[data-z]"), s = e.target.closest("#sch [data-s]");
    if (y) go({...F, kind: +y.dataset.y ? "y" : "all", yr: +y.dataset.y, von: "", bis: ""}, `.years [data-y="${y.dataset.y}"]`);
    else if (z) {
      const k = z.dataset.z;
      if (k === "c") {
        const f = bar.querySelector("#stfc");
        f.hidden = F.kind === "c" ? false : !f.hidden;
        if (!f.hidden) {
          const i = f.querySelector('[name="von"]'), j = f.querySelector('[name="bis"]');
          if (!i.value) i.value = `${new Date().getFullYear()}-01-01`;
          if (!j.value) j.value = slIso(new Date());
          i.focus();
        }
      } else go(k === "year" ? {...F, kind: "y", yr: new Date().getFullYear(), von: "", bis: ""} : k === "prev" ? {...F, kind: "y", yr: new Date().getFullYear() - 1, von: "", bis: ""} : {...F, kind: k, yr: 0, von: "", bis: ""}, `[data-z="${k}"]`);
    } else if (s) {
      const v = s.dataset.s, cur = F.sports,
        next = !v ? [] : cur.includes(v) ? cur.filter(x => x !== v) : cur.concat([v]);
      go({...F, sports: next}, `#sch [data-s="${CSS.escape(v)}"]`);
    }
  });
  bar.querySelector("#stfc").addEventListener("submit", e => {
    e.preventDefault();
    const f = e.target, von = f.von.value, bis = f.bis.value, er = f.querySelector(".stfe");
    if (!ST_DATE.test(von) || !ST_DATE.test(bis)) return (er.textContent = "Bitte beide Daten angeben."), f.von.focus();
    if (von > bis) return (er.textContent = "„Von“ darf nicht nach „Bis“ liegen."), f.von.focus();
    go({...F, kind: "c", yr: 0, von, bis}, '[data-z="c"]');
  });
  if (ST.focus) {
    const el = bar.querySelector(ST.focus);
    ST.focus = "";
    if (el) el.focus({preventScroll: true});
  }
}

/* ---------- Hinweis „Filter gilt hier nicht“ ---------- */
function stNote(cap, F = ST.F) {
  const sNo = F.sports.length && !cap.s, rNo = F.kind !== "all" && !cap.r, rYear = F.kind !== "all" && cap.r === "y" && F.kind !== "y";
  if (sNo && (rNo || rYear)) return "Filter gilt hier nicht";
  if (sNo) return "Sportart gilt hier nicht";
  if (rYear) return "Zeitraum gilt hier nur als Jahr";
  if (rNo) return "Zeitraum gilt hier nicht";
  return "";
}
function stNoteAdd(root, text) {
  const sm = root && root.querySelector("summary"), old = sm && sm.querySelector(".stn");
  if (old) old.remove();
  if (!sm || !text) return;
  const k = sm.querySelector(".tlk");
  (k || sm.lastElementChild).insertAdjacentHTML("beforebegin", `<span class="stn mut">${esc(text)}</span>`);
}

/* ---------- Globaler Filter in der Konfiguration eines Bausteins: it.cfg wird zur wirksamen Konfiguration (it.raw = gespeicherte) ---------- */
/* 3.34.0: auch für den Zeitraum der Seite auf der Übersicht (65-zeitraum.js): o.page = Zeitraum der Seite (nur Zeitraum, keine Sportart; Bausteine ohne Zeitbezug bleiben ohne Hinweis;
   „eigen“ = eigener Zeitraum mit Hinweis), o.explicit = auch „Alle“ gilt. Auf der Statistik gilt der Filter für die Eigene Kennzahl (Typ-Flag „zeit“) erst, wenn ein Zeitraum gewählt ist (Standard „Gesamt“ lässt sie, wie sie ist). */
function stApply(it, F = ST.F, o = {}) {
  const T = window.SL_WT[it.wtype], raw = it.cfg || {}, fs = (T && T.fields) || [],
    hasS = fs.some(f => f.kind === "sports") && !o.page, rf = fs.find(f => f.kind === "range"), zeit = !!(T && T.zeit);
  it.raw = raw;
  it.note = "";
  if (o.page && !rf && !zeit) return;                                                   // kein Zeitbezug: kein Hinweis, nichts zu tun
  if (!T || raw.eigen === true || T.hinweis) {
    if (o.page && T && raw.eigen === true) it.note = "eigener Zeitraum";
    return;                                                                             // 3.23.0: Hinweis-Bausteine haben ihre eigene Sportart und keinen Zeitraum
  }
  if (zeit && !rf) {                                                                    // Eigene Kennzahl: range/yr/from/to der Einstellung werden vom Zeitraum der Seite ersetzt
    if (F.kind === "all" && !o.explicit) return void (it.note = stNote({s: 0, r: 1}, F));
    const out = {...raw};
    delete out.range;
    delete out.yr;
    out.range = F.kind;
    if (F.kind === "y") out.yr = F.yr;
    if (F.kind === "c") {
      out.from = F.von;
      out.to = F.bis;
    } else {
      delete out.from;
      delete out.to;
    }
    if (F.kind === "all") out._nr = true;
    it.note = o.page ? "" : stNote({s: 0, r: 1}, F);
    it.cfg = out;
    it.fl = slWFl(T, out);
    return;
  }
  const out = {...raw}, ok = rf ? !rf.opts || rf.opts.includes(F.kind) : false;
  if (hasS) {
    if (F.sports.length) out.sports = F.sports.slice();
    else delete out.sports;
  }
  if (rf && ok) {
    delete out.range;
    delete out.yr;
    out.range = F.kind;
    if (F.kind === "y") out.yr = F.yr;
    if (F.kind === "c") {
      out.from = F.von;
      out.to = F.bis;
    }    if (F.kind === "all" && T.filter && T.filter.range === "all") delete out.range;               // Standard des Bausteins: kein Zusatz im Kopf
  }
  if (F.kind === "all") out._nr = true;                                                  // „Gesamte Zeit“ ist der Standard: nicht im Kopf wiederholen
  if (T.stJahr && !o.page && F.kind === "y") out._jahr = F.yr;                           // 3.45.0 Baustein „Ziele“: das gewählte Jahr der Seite gilt als Jahr der Jahresziele
  it.note = o.page ? (ok ? "" : "Zeitraum gilt hier nur als Jahr") : stNote({s: hasS ? 1 : 0, r: rf ? (ok ? 1 : "y") : T.stJahr ? "y" : 0}, F);
  it.cfg = out;
  it.fl = slWFl(T, out);
}

/* ---------- Kapselung der Abschnitte ---------- */
function stBuild() {
  const inner = document.querySelector("#main .inner"), bar = document.getElementById("stf");
  if (!inner || !bar || document.getElementById("stx")) return;
  const host = document.createElement("div");
  host.id = "stx";
  host.className = "stx";
  bar.after(host);
  inner.querySelectorAll("[data-st]").forEach(e => {
    const id = e.dataset.st, reg = SL_REG.statistik.find(x => x.id === id);
    if (!reg || (id === "erinn" && !e.querySelector("#mem"))) return e.remove();
    const h = e.querySelector("h2"), title = h ? h.textContent : reg.title;
    if (h) h.remove();
    const c = tlCard("stc-" + id, {sec: id, key: "st_" + id, icon: ST_ICON[id], title: esc(title), badge: esc(e.dataset.badge || ""), def: true, bodyCls: "stb"});
    delete e.dataset.st;
    delete e.dataset.badge;
    tlBody(c).appendChild(e);
    stNoteAdd(c, stNote(ST_CAP[id]));
    host.appendChild(c);
  });
  inner.querySelectorAll(":scope > .grid:empty").forEach(g => g.remove());
  ["bl", "tp"].forEach(id => stNoteAdd(document.getElementById(id === "bl" ? "blsec" : "tpsec"), stNote(ST_CAP[id])));
  slPlace(host);
}

/* ---------- Anbindung an die Ansicht ---------- */
{
  const _stats56 = VIEWS.stats;
  VIEWS.stats = async (n, q) => {
    q = q || new URLSearchParams("");
    slViewStart("statistik");
    const tok = window._rt;
    await slEnsure("statistik");
    if (tok !== window._rt) return STALE();
    slResolve("statistik");
    ST.base = stStored() || stSaved();
    ST.F = stFilter(q);
    stStore(ST.F);
    await _stats56(n, q);
    if (tok !== window._rt) return;
    stBuild();
    if (ST.reedit) {
      ST.reedit = false;
      slEdit(true, false, true);
    }
  };
}
