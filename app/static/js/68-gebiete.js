/* =====================  3.65.0 Gebiete: Übersicht (#/areas) und Seite eines Gebiets (#/area/<Kennung>) als anpassbare Seiten, eigene Gebiete  =====================
   Grundlage ist die Gebietstabelle (gebiete-daten.js, Zuordnung einer Tour aus ihrem Startpunkt; Näherung) und der Filter „Gebiet“ (01-grundlagen.js: gebietListe, inGebiet). Neu:
     Übersicht   Layout-Schlüssel „gebiete“ (Wurzel #gex): Kopf (Titel, Suche, Gliederung, Sortierung, „Gebiet hinzufügen“) und Liste der besuchten Gebiete mit Touren, Tagen, Strecke, Aufstieg und Zeitraum,
                 gegliedert nach Typ oder Land; Baustein gbzahlen (Kennzahlen aller Gebiete). Ein Klick öffnet die Seite des Gebiets.
     Gebiet      Layout-Schlüssel „gebiet“ (Wurzel #gdx, gilt für alle Gebiete gleich): Kopf, Kennzahlen, Karte der Touren (Strecken aus /api/routes, dazu die Grenzen des Gebiets), Beste Monate (Baustein gmonate),
                 Fotos (Baustein gfotos: die Fotos der Touren im Gebiet, GET /api/photos?gebiet=<Kennung>), Reisen in diesem Gebiet, Touren (die neuesten; „Alle Touren“ = Tourenliste mit dem Filter „Gebiet“).
     Eigene Gebiete (Tabelle gebiet_custom, app/gebiete.py): „Gebiet hinzufügen“ sucht per Namen über den Server (OpenStreetMap/Nominatim, nur auf Knopfdruck, zwischengespeichert), zeigt Treffer mit Name,
                 Art und Land; die Wahl öffnet Name, Typ, Land und die Grenzen des Rechtecks (Zahlen oder Kartenausschnitt) zum Bearbeiten. Ohne Verbindung geht „Von Hand anlegen“. Eigene Gebiete rechnen
                 wie eingebaute (Gebiete.setEigene), tragen in Listen die Marke „eigen“ und sind bearbeit- und löschbar. */
const GB_TYP = [["gebirge", "Gebirge"], ["tal", "Tal"], ["insel", "Insel"], ["kueste", "Küste"], ["region", "Landschaft"]];
const gbTypName = k => (GB_TYP.find(x => x[0] === k) || [0, k])[1];
const gbViewer = () => typeof isViewer === "function" && isViewer();
const gbDay = t => String(t.date).slice(0, 10);
const gbLs = (k, d) => {
  try {
    return localStorage.getItem(k) || d;
  } catch (e) {
    return d;
  }
};
const gbLsSet = (k, v) => {
  try {
    localStorage.setItem(k, v);
  } catch (e) {}
};

/* Kennzahlen je Gebiet: Touren, aktive Tage, Strecke, Aufstieg, Dauer, erstes und letztes Mal, Länder (eine Tour zählt in jedem Gebiet, in dem sie liegt, samt Oberbegriffen) */
function gbStats(ts) {
  const m = {};
  (ts || TOURS).forEach(t => Gebiete.von(t).forEach(v => {
    const e = (m[v.id] ||= {id: v.id, n: 0, days: new Set(), km: 0, up: 0, h: 0, first: "", last: "", ld: {}}), d = gbDay(t);
    e.n++;
    e.days.add(d);
    e.km += t.km;
    e.up += t.up_m || 0;
    e.h += t.h;
    if (!e.first || d < e.first) e.first = d;
    if (d > e.last) e.last = d;
    if (t.g_country) e.ld[t.g_country] = (e.ld[t.g_country] || 0) + 1;
  }));
  return m;
}
/* Land eines Gebiets: das häufigste Land seiner Touren; land = nur, wenn mindestens 80 % der Touren dort liegen */
function gbLand(e) {
  const top = e && Object.entries(e.ld).sort((a, b) => b[1] - a[1])[0];
  return {top: top ? top[0] : "", land: top && top[1] >= e.n * 0.8 ? top[0] : ""};
}
function gbRows() {
  const st = gbStats(), out = [];
  Gebiete.liste.forEach(x => {
    const e = st[x.id], eigen = x.quelle === "eigen";
    if (!e && !eigen) return;
    const l = gbLand(e), land = l.land || (eigen ? x.land || "" : "");
    out.push({id: x.id, name: x.name, typ: x.typ, eigen, n: e ? e.n : 0, tage: e ? e.days.size : 0, km: e ? e.km : 0, up: e ? e.up : 0, first: e ? e.first : "", last: e ? e.last : "", land, top: l.top || (eigen ? x.land || "" : ""),
      s: [x.name, land, eigen ? "eigen" : ""].concat(x.alias || []).map(Gebiete.fold).filter(Boolean).join("|")});
  });
  return out;
}
const gbSpan = r => (r.first && r.last ? (r.first === r.last ? fmtDatumKurz(r.first) : `${fmtDatumKurz(r.first)} – ${fmtDatumKurz(r.last)}`) : "");

/* ---------- Seiten im Baukasten ---------- */
SL_REG.gebiete = [
  {id: "kopf", w: "voll", title: "Kopf: Titel, Suche und Aktionen", page: "gebiete", plain: true, must: true, ws: ["voll"]},
  {id: "liste", w: "voll", title: "Gebiete", page: "gebiete", def: true, ckeys: ["ge_liste"]},
];
SL_REG.gebiet = [
  {id: "kopf", w: "voll", title: "Kopf: Titel, Typ und Aktionen", page: "gebiet", plain: true, must: true, ws: ["voll"]},
  {id: "kennzahlen", w: "voll", title: "Kennzahlen", page: "gebiet", def: true, ckeys: ["gd_kennzahlen"]},
  {id: "karte", w: "voll", title: "Karte", page: "gebiet", def: true, ckeys: ["gd_karte"]},
  {id: "monate", w: "voll", title: "Beste Monate", page: "gebiet", build: "gmonate", defcfg: {view: "monate", metric: "count"}, def: true, ckeys: ["gd_monate"]},
  {id: "fotos", w: "voll", title: "Fotos", page: "gebiet", build: "gfotos", defcfg: SL_FOTOS_DEF, def: true, ckeys: ["gd_fotos"]},
  {id: "reisen", w: "voll", title: "Reisen", page: "gebiet", def: true, ckeys: ["gd_reisen"]},
  {id: "touren", w: "voll", title: "Touren", page: "gebiet", def: true, ckeys: ["gd_touren"]},
];
SL_EL.gebiete = {kopf: () => document.getElementById("ge-kopf"), liste: () => document.getElementById("gec-liste")};
SL_EL.gebiet = Object.fromEntries(["kopf", "kennzahlen", "karte", "reisen", "touren"].map(id => [id, () => (id === "kopf" ? document.getElementById("gd-kopf") : document.getElementById("gdc-" + id))]));
const GE_ICON = {liste: "map", kennzahlen: "met", karte: "map", reisen: "map", touren: "note"};

/* ---------- Bausteine ---------- */
const GB_VALUES = [["gebiete", "Gebiete"], ["laender", "Länder"], ["touren", "Touren in Gebieten"], ["km", "Strecke"], ["ohne", "Touren ohne Gebiet"]];
const GB_DEF = ["gebiete", "laender", "touren", "km", "ohne"];
const GM_METRIC = {count: ["Touren", t => 1, v => fmtAnzahl(v, "Tour", "Touren")], km: ["Strecke", t => t.km, v => fmtKm(v, {summe: true})], up: ["Aufstieg", t => t.up_m || 0, v => fmtHm(v)]};
const gbNoArea = b => slNote(b, "Dieser Baustein gehört auf die Seite eines Gebiets.");
Object.assign(window.SL_WT, {
  gbzahlen: {
    fam: "gebiete", cat: "gebiet", icon: "met", name: "Gebiete-Kennzahlen", title: () => "Gebiete-Kennzahlen", multi: true, w: "halb", seiten: ["gebiete"], defaults: {values: GB_DEF},
    desc: "Alle Gebiete auf einen Blick: in wie vielen Gebieten und Ländern du Touren gemacht hast, wie viele Touren und wie viele Kilometer in einem Gebiet liegen und wie viele Touren in keinem bekannten Gebiet.",
    fields: [{k: "values", kind: "checks", label: "Angezeigte Werte", min: 1, def: GB_DEF, options: GB_VALUES}, {kind: "title"}],
    preview: () => slPvTiles([["14", "Gebiete"], ["5", "Länder"], ["1 480 km", "Strecke"]]),
    render(c, b, cfg) {
      const rows = gbRows().filter(r => r.n), mit = TOURS.filter(t => Gebiete.von(t).length);
      if (!rows.length) return slNote(b, "Noch keine Tour liegt in einem bekannten Gebiet.");
      const want = (cfg.values && cfg.values.length ? cfg.values : GB_DEF).filter(v => GB_VALUES.some(k => k[0] === v)), land = [...new Set(mit.map(t => t.g_country).filter(Boolean))], ohne = TOURS.length - mit.length,
        tile = {
          gebiete: [String(rows.length), rows.length === 1 ? "Gebiet" : "Gebiete"], laender: land.length ? [String(land.length), land.length === 1 ? "Land" : "Länder", land.slice(0, 3).join(", ") + (land.length > 3 ? " …" : "")] : null,
          touren: [String(mit.length), mit.length === 1 ? "Tour in Gebieten" : "Touren in Gebieten"], km: [slKm(slSum(mit, t => t.km)), "Strecke"], ohne: [String(ohne), ohne === 1 ? "Tour ohne Gebiet" : "Touren ohne Gebiet"],
        }, list = want.map(v => tile[v]).filter(Boolean);
      if (!list.length) return slNote(b, "Für die gewählten Werte liegen keine Daten vor.");
      b.innerHTML = slTiles(list);
      slBadge(c, rows.length === 1 ? "1 Gebiet" : `${rows.length} Gebiete`);
    },
  },
  gmonate: {
    fam: "gebiet", cat: "gebiet", icon: "trend", name: "Beste Monate", title: cfg => (cfg.view === "jahre" ? "Jahre" : "Beste Monate"), multi: true, w: "halb", seiten: ["gebiet"], defaults: {view: "monate", metric: "count"},
    desc: "Ein Säulendiagramm über die zwölf Monate (oder über die Jahre): wann du in diesem Gebiet unterwegs warst, nach Anzahl der Touren, Strecke oder Aufstieg. Die stärksten Monate stehen darunter. Gerechnet wird aus deinen eigenen Touren im Gebiet.",
    fields: [{k: "view", kind: "radio", def: "monate", label: "Säulen je", options: [["monate", "Monat (alle Jahre)"], ["jahre", "Jahr"]]},
      {k: "metric", kind: "radio", def: "count", label: "Gemessen nach", options: [["count", "Anzahl der Touren"], ["km", "Strecke"], ["up", "Aufstieg"]]}, {kind: "title"}],
    preview: () => slPvBars([8, 6, 12, 20, 26, 34, 30, 28, 22, 14, 6, 4]),
    render(c, b, cfg, {reise}) {
      const G = reise && reise.gebiet;
      if (!G) return gbNoArea(b);
      if (!G.ts.length) return slNote(b, "In diesem Gebiet gibt es noch keine Tour.");
      const M = GM_METRIC[cfg.metric] ? cfg.metric : "count", [name, f, fmt] = GM_METRIC[M], jahre = cfg.view === "jahre";
      let keys, v, lab, txt, best;
      if (jahre) {
        const ys = G.ts.map(t => t.y), y1 = Math.max(...ys), y0 = Math.max(Math.min(...ys), y1 - 11);
        keys = Array.from({length: y1 - y0 + 1}, (_, i) => y0 + i);
        v = keys.map(y => slSum(G.ts.filter(t => t.y === y), f));
        lab = keys.map(y => (keys.length > 8 ? "’" + String(y).slice(2) : String(y)));
        best = v.indexOf(Math.max(...v));
        txt = `<p class="slcmp"><span>Stärkstes Jahr</span>: ${keys[best]}</p><p class="mut slcmpn">${fmt(v[best])}</p>`;
      } else {
        keys = Array.from({length: 12}, (_, i) => i + 1);
        v = keys.map(mo => slSum(G.ts.filter(t => t.m === mo), f));
        lab = MONL.map(x => x.slice(0, 3));
        best = v.indexOf(Math.max(...v));
        const top = keys.map((mo, i) => [mo, v[i]]).filter(x => x[1] > 0).sort((a, z) => z[1] - a[1] || a[0] - z[0]).slice(0, 3);
        txt = `<p class="slcmp"><span>Beste Monate</span>: ${top.map(x => MONL[x[0] - 1]).join(", ")}</p><p class="mut slcmpn">${MONL[keys[best] - 1]}: ${fmt(v[best])}</p>`;
      }
      b.innerHTML = slCols(v, {hl: best, label: `Säulendiagramm: ${jahre ? "Jahre" : "Monate"}, am stärksten ${jahre ? keys[best] : MONL[keys[best] - 1]} mit ${fmt(v[best])} (${name})`, labels: rsLabels(lab, 12), cls: "slsm rscol"}) + txt;
      slBadge(c, jahre ? String(keys[best]) : MONL[keys[best] - 1]);
    },
  },
  gfotos: {
    fam: "gebiet", cat: "gebiet", icon: "cam", name: "Fotos", title: () => "Fotos", multi: true, w: "voll", seiten: ["gebiet"], defaults: {mode: "all", ratio: "43", size: "l", link: true},
    desc: "Die Fotos der Touren in diesem Gebiet als Vorschaubilder, Raster, Streifen oder Einzelbild-Show: alle, die besten, zufällige oder die neuesten. „Diashow starten“ zeigt sie im Vollbild. Du kannst den Baustein mehrfach hinzufügen und verschieden einstellen.",
    dialog: (id, cfg) => erDialog(id, cfg, "gebiet"), fields: [{kind: "erinn"}],
    kurz: cfg => ({random: ["Zufällig"], recent: ["Neueste"], best: ["Beste"]}[erCfg(cfg).mode] || []),
    preview: () => slPrev('<div class="slpvf" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'),
    render(c, b, cfg, {reise}) {
      const G = reise && reise.gebiet;
      if (!G) return gbNoArea(b);
      const fix = {gebiet: G.id, noun: "Gebiet"}, k = erCfg(cfg), pv = /^pv\d+$/.test(c.dataset.wid || "");
      b.innerHTML = (k.shuffle || k.link ? `<div class="rsdh">${k.shuffle ? '<button type="button" class="btn ghost sm ernew">Neu mischen</button>' : ""}${k.link ? `<a class="hmore erdia" target="_blank" rel="noopener" href="${esc(erSlideUrl(cfg, fix))}">Diashow starten</a>` : ""}</div>` : "") + '<div class="erb"></div>';
      const o = {keep: true, fix, cap: pv ? 12 : 0, none: "Zu diesem Gebiet gibt es keine Fotos."}, nb = b.querySelector(".ernew");
      if (nb) nb.onclick = () => erLoad(b, cfg, k.mode === "random" ? {...o, fresh: true} : {...o, mix: true});
      return erLoad(b, cfg, o).then(() => {
        const n = (b._erList || []).length;
        if (n) slBadge(c, n === 1 ? "1 Foto" : `${n} Fotos`);
      });
    },
  },
});
SL_TPL.push(
  {id: "gb-kompakt", fam: "gebiete", name: "Nur die Liste", desc: "Ruhig und kurz: nur die Liste der Gebiete, ohne Kennzahlen.", items: [["kopf", "voll"], ["liste", "voll"]]},
  {id: "gb-zahlen", fam: "gebiete", name: "Mit Kennzahlen", desc: "Oben die Kennzahlen aller Gebiete, darunter die Liste.", items: [["kopf", "voll"], ["w:gbzahlen", "voll"], ["liste", "voll"]]},
  {id: "gd-kompakt", fam: "gebiet", name: "Kompakt", desc: "Wenig auf einen Blick: Kopf, Kennzahlen, Karte und die Touren. Beste Monate, Fotos und Reisen sind ausgeblendet.", items: [["kopf", "voll"], ["kennzahlen", "voll"], ["karte", "voll"], ["touren", "voll"]]},
  {id: "gd-jahreszeit", fam: "gebiet", name: "Wann hinfahren", desc: "Für die Planung: die besten Monate und die Jahre nebeneinander, darunter Kennzahlen, Karte und Reisen.",
    items: [["kopf", "voll"], ["monate", "halb"], ["w:gmonate", "halb", {view: "jahre"}], ["kennzahlen", "voll"], ["karte", "voll"], ["reisen", "voll"]]},
  {id: "gd-fotos", fam: "gebiet", name: "Mit Fotos", desc: "Für die Erinnerung: oben die besten Fotos des Gebiets als Show, dann Karte und Kennzahlen, darunter alle Fotos und die Touren.",
    items: [["kopf", "voll"], ["w:gfotos", "voll", {mode: "best", view: "show", n: 12, ratio: "sq", size: "m", link: true}], ["karte", "voll"], ["kennzahlen", "voll"], ["fotos", "voll"], ["touren", "voll"]]},
);

/* ---------- Übersicht #/areas ---------- */
const gbRow = r => `<a class="gbrow${r.n ? "" : " gb0"}" href="#/area/${encodeURIComponent(r.id)}"><span class="gbname"><b>${esc(r.name)}</b>${r.eigen ? '<i class="gbeigen">eigen</i>' : ""}${r.land ? `<small class="mut">${esc(r.land)}</small>` : ""}</span>` +
  (r.n
    ? `<span class="gbc"><b>${nf(r.n, 0)}</b><small>Touren</small></span><span class="gbc"><b>${nf(r.tage, 0)}</b><small>Tage</small></span><span class="gbc"><b>${fmtKm(r.km, {d: 0})}</b><small>Strecke</small></span><span class="gbc"><b>${fmtHm(r.up)}</b><small>Aufstieg</small></span><span class="gbc gbz"><b>${esc(gbSpan(r))}</b></span>`
    : '<span class="gbnt mut">Noch keine Tour in diesem Gebiet</span>') + `</a>`;
const GB_SORT = {name: (a, b) => a.name.localeCompare(b.name, "de"), n: (a, b) => b.n - a.n || a.name.localeCompare(b.name, "de"), km: (a, b) => b.km - a.km || a.name.localeCompare(b.name, "de"),
  last: (a, b) => (b.last > a.last ? 1 : b.last < a.last ? -1 : 0) || a.name.localeCompare(b.name, "de")};
function gbDraw(rows) {
  const box = document.getElementById("gbl");
  if (!box) return;
  const f = Gebiete.fold(document.getElementById("gbq").value), gr = document.getElementById("gbgr").value, so = document.getElementById("gbso").value,
    a = rows.filter(r => !f || r.s.split("|").some(x => x.includes(f))).sort(GB_SORT[so] || GB_SORT.name);
  gbLsSet("mt_gb_gr", gr);
  gbLsSet("mt_gb_so", so);
  const groups = gr === "land"
    ? [...new Set(a.map(r => r.top || ""))].sort((x, y) => (x === "" ? 1 : y === "" ? -1 : x.localeCompare(y, "de"))).map(l => [l || "Ohne Land", a.filter(r => (r.top || "") === l)])
    : GEB_TYPEN.map(([k, l]) => [l, a.filter(r => r.typ === k)]).filter(g => g[1].length);
  box.innerHTML = a.length
    ? `<div class="gbhead" aria-hidden="true"><span>Gebiet</span><span>Touren</span><span>Tage</span><span>Strecke</span><span>Aufstieg</span><span>Erstes – letztes Mal</span></div>` +
      groups.map(([l, rs]) => `<section class="gbg2"><h3 class="gbh">${esc(l)} <span class="mut">(${rs.length})</span></h3>${rs.map(gbRow).join("")}</section>`).join("")
    : `<p class="mut gbnone" role="status">${f ? "Kein Gebiet gefunden." : "Noch keine Tour liegt in einem bekannten Gebiet."}</p>`;
}
async function gbAreasBase() {
  const rows = gbRows(), nv = rows.filter(r => r.n).length, own = rows.filter(r => r.eigen).length;
  $("#main").innerHTML = `<div data-ge="kopf"><div class="sec mt0"><h2>Gebiete</h2><span class="sub" id="gbsub"><span>${nv === 1 ? "1 Gebiet" : nv + " Gebiete"}</span>${own ? `, <span>${own === 1 ? "1 eigenes" : own + " eigene"}</span>` : ""}</span></div>
   <div class="filters gbflt" id="gbflt"><input id="gbq" type="search" class="mnw230" placeholder="Gebiet suchen" aria-label="Gebiet suchen" autocomplete="off">
   <select id="gbgr" aria-label="Gliedern nach"><option value="typ">Nach Typ</option><option value="land">Nach Land</option></select>
   <select id="gbso" aria-label="Sortieren nach"><option value="name">Name</option><option value="n">Meiste Touren</option><option value="km">Längste Strecke</option><option value="last">Zuletzt besucht</option></select>
   ${gbViewer() ? "" : '<button type="button" class="btn alt sm" id="gbadd">＋ Gebiet hinzufügen …</button>'}</div></div>
   <div data-ge="liste"><div id="gbl"></div></div>`;
  $("#gbgr").value = gbLs("mt_gb_gr", "typ") === "land" ? "land" : "typ";
  $("#gbso").value = GB_SORT[gbLs("mt_gb_so", "name")] ? gbLs("mt_gb_so", "name") : "name";
  const draw = () => gbDraw(rows);
  ["gbq", "gbgr", "gbso"].forEach(i => ($("#" + i).oninput = draw));
  $("#gbq").onkeydown = e => {                                                           // Enter öffnet den ersten Treffer
    const a = e.key === "Enter" && document.querySelector("#gbl .gbrow");
    if (a) {
      e.preventDefault();
      location.hash = a.getAttribute("href");
    }
  };
  if ($("#gbadd")) $("#gbadd").onclick = () => gbDialog(null);
  draw();
}
function gbFrame() {
  const main = document.getElementById("main");
  if (!main || document.getElementById("gex") || !document.getElementById("gbl")) return;
  const host = document.createElement("div"), kopf = main.querySelector('[data-ge="kopf"]'), liste = main.querySelector('[data-ge="liste"]'), n = document.querySelectorAll("#gbl .gbrow").length;
  host.id = "gex";
  host.className = "stx";
  kopf.id = "ge-kopf";
  kopf.classList.add("rskopf");
  host.appendChild(kopf);
  const c = tlCard("gec-liste", {sec: "liste", key: "ge_liste", icon: GE_ICON.liste, title: "Gebiete", badge: esc(n === 1 ? "1 Gebiet" : n ? `${n} Gebiete` : ""), def: true, bodyCls: "stb rsb"});
  tlBody(c).appendChild(liste.firstElementChild);
  liste.remove();
  host.appendChild(c);
  main.appendChild(host);
  slPlace(host);
}
{
  VIEWS.areas = async (...a) => {
    window.GE_WRAPPED = true;
    slViewStart("gebiete");
    const tok = window._rt;
    await slEnsure("gebiete");
    if (tok !== window._rt) return STALE();
    slResolve("gebiete");
    window.RS_CUR = null;
    await gbAreasBase(...a);
    if (tok !== window._rt) return;
    gbFrame();
  };
}

/* ---------- Seite eines Gebiets #/area/<Kennung> ---------- */
const gbAlle = n => `Alle ${nf(n, 0)} Touren in der Liste ›`;
const gbFig = (v, u, l) => `<div class="fig"><div class="v">${v}${u ? `<span class="u">${u}</span>` : ""}</div><div class="l">${l}</div></div>`;
async function gbAreaBase(id) {
  try {
    id = decodeURIComponent(id || "");
  } catch (e) {}
  const g = Gebiete.nach[id];
  if (!g) throw new Error("Gebiet nicht gefunden");
  const ts = TOURS.filter(t => inGebiet(t, id)).sort((a, z) => a.start_ts - z.start_ts), st = gbStats(ts)[id], eigen = g.quelle === "eigen", l = gbLand(st), land = l.land || l.top || g.land || "",
    par = g.eltern && Gebiete.nach[g.eltern], box = eigen ? g.boxen[0] : null,
    quelle = eigen
      ? `<span>Eigenes Gebiet</span> · <span>Rechteck: Süd ${nf(box[0], 2)}, West ${nf(box[1], 2)}, Nord ${nf(box[2], 2)}, Ost ${nf(box[3], 2)}</span>`
      : "<span>Eingebautes Gebiet</span> · <span>die Grenzen sind eine Näherung</span>";
  window.RS_CUR = {gebiet: {id, name: g.name, ts}, fam: "gebiet"};
  const trips = ts.length ? (await api("/api/trips").catch(() => [])).filter(tr => (tr.tours || []).some(i => BY[i] && inGebiet(BY[i], id))) : [];
  const tab = ts.length
    ? [gbFig(nf(ts.length, 0), "", ts.length === 1 ? "Tour" : "Touren"), gbFig(nf(st.days.size, 0), "", st.days.size === 1 ? "aktiver Tag" : "aktive Tage"), gbFig(fmtKm(st.km, {summe: true, einheit: false}), "km", "Strecke"),
      gbFig(nf(st.up, 0), "m", "Aufstieg"), `<div class="fig"><div class="v">${fmtDauerHtml(st.h * 3600, {summe: true})}</div><div class="l">Dauer</div></div>`, gbFig(`<small>${fmtDatumKurz(st.first)}</small>`, "", "Erstes Mal"), gbFig(`<small>${fmtDatumKurz(st.last)}</small>`, "", "Letztes Mal")].join("")
    : "";
  $("#main").innerHTML = `<div data-gd="kopf"><div class="row"><a class="back" href="#/areas">‹ Zurück</a></div><div class="sec mt12"><h1 class="gbh1">${esc(g.name)}${eigen ? '<i class="gbeigen">eigen</i>' : ""}</h1></div>
   <div class="mut"><span>${esc(gbTypName(g.typ))}</span>${land ? ` · <span>${esc(land)}</span>` : ""}${par ? ` · <span>Teil von</span> <a class="gblink" href="#/area/${encodeURIComponent(par.id)}">${esc(par.name)}</a>` : ""}</div><div class="mut fs14 mt4">${quelle}</div>
   <div class="row g8 aic mt12 gbact">${ts.length ? `<a class="btn alt sm" id="gballe" href="#/tours?g=${encodeURIComponent(id)}">Alle Touren</a>` : ""}${eigen && !gbViewer() ? '<button type="button" class="btn alt sm" id="gbedit">✎ Gebiet bearbeiten</button><button type="button" class="btn alt sm" id="gbdel">Löschen</button>' : ""}</div></div>
   ${ts.length ? `<div class="figs" data-gd="kennzahlen">${tab}</div><div data-gd="karte"><div class="tmap" id="cm" role="img" aria-label="Karte der Touren in diesem Gebiet"></div></div>` : '<p class="mut gbleer" role="status">In diesem Gebiet gibt es noch keine Tour.</p>'}
   ${trips.length ? `<div data-gd="reisen"><div class="otdg">${trips.map(tripKarte).join("")}</div></div>` : ""}
   ${ts.length ? `<div data-gd="touren"><div class="tl">${ts.slice().reverse().slice(0, 20).map(tourRow).join("")}</div>${ts.length > 20 ? `<p class="mut mt8"><a class="gblink" href="#/tours?g=${encodeURIComponent(id)}">${gbAlle(ts.length)}</a></p>` : ""}</div>` : ""}`;
  if ($("#gbedit")) {
    $("#gbedit").onclick = () => gbDialog(EIGENE_GEB.find(x => x.id === id) || null);
    $("#gbdel").onclick = async () => {
      if (!await uiConfirm({title: `„${g.name}“ löschen?`, text: "Das eigene Gebiet wird gelöscht. Touren, Reisen und Fotos bleiben unverändert; nur die Zuordnung zu diesem Gebiet entfällt, und Reisen, die danach hießen, bekommen wieder ihren früheren automatischen Namen. Das lässt sich nicht rückgängig machen; du kannst das Gebiet aber neu hinzufügen.", danger: true, ok: "Löschen"})) return;
      try {
        await api(`/api/gebiete/eigene/${encodeURIComponent(id)}`, {method: "DELETE"});
      } catch (e) {
        return uiAlert({title: "Löschen nicht möglich", text: e.message});
      }
      await gbChanged();
      location.hash = "#/areas";
    };
  }
  gbAreaFrame(g, ts, trips);
  if (ts.length) await gbAreaMap(g, ts);
}
/* Nach Änderung eigener Gebiete: Tabelle neu holen, Suche der Reisen neu laden (Namen ändern sich), gemerkten Filter behalten */
async function gbChanged() {
  await gebieteLaden();
  window._sReisen = null;
}
function gbAreaFrame(g, ts, trips) {
  const main = document.getElementById("main");
  if (!main || document.getElementById("gdx")) return;
  const host = document.createElement("div");
  host.id = "gdx";
  host.className = "stx";
  const kopf = main.querySelector('[data-gd="kopf"]');
  kopf.id = "gd-kopf";
  kopf.classList.add("rskopf");
  host.appendChild(kopf);
  const badge = {kennzahlen: ts.length === 1 ? "1 Tour" : `${ts.length} Touren`, reisen: trips.length === 1 ? "1 Reise" : `${trips.length} Reisen`, touren: ts.length === 1 ? "1 Tour" : `${ts.length} Touren`}, title = {kennzahlen: "Kennzahlen", karte: "Karte", reisen: "Reisen in diesem Gebiet", touren: "Touren"};
  SL_REG.gebiet.forEach(reg => {
    if (reg.id === "kopf" || reg.build) return;
    const e = main.querySelector(`:scope > [data-gd="${reg.id}"]`);
    if (!e) return;
    const c = tlCard("gdc-" + reg.id, {sec: reg.id, key: "gd_" + reg.id, icon: GE_ICON[reg.id], title: esc(reg.id === "reisen" ? "Reisen in diesem Gebiet" : reg.title), badge: esc(badge[reg.id] || ""), def: true, bodyCls: reg.id === "karte" ? "tlmap" : "stb rsb"});
    tlBody(c).appendChild(e);
    delete e.dataset.gd;
    host.appendChild(c);
  });
  main.querySelectorAll(":scope > .gbleer").forEach(e => host.appendChild(e));
  main.appendChild(host);
  slPlace(host);
}
/* Karte: die Strecken der Touren im Gebiet (vereinfachte Strecken aus /api/routes, Farbe der Sportart) und die Grenzen des Gebiets (gestrichelt) */
async function gbAreaMap(g, ts) {
  const el = document.getElementById("cm");
  if (!el) return;
  const tok = window._rt;
  map = mkMap("cm", {layers: true});
  const cmap = map, fg = L.featureGroup().addTo(map), bg = L.featureGroup().addTo(map);
  g.boxen.forEach(b => L.rectangle([[b[0], b[1]], [b[2], b[3]]], {color: "#6a8f90", weight: 1.5, dashArray: "6 5", fill: false, interactive: false}).addTo(bg));
  g.poly.forEach(r => L.polygon(r, {color: "#6a8f90", weight: 1.5, dashArray: "6 5", fill: false, interactive: false}).addTo(bg));
  const draw = R => {
    fg.clearLayers();
    ts.forEach(t => {
      const p = cleanPts(R && R[t.id]).map(x => [x[0], x[1]]);
      if (p.length > 1) L.polyline(p, {color: sCol(t.sport), weight: 3, opacity: 0.85}).addTo(fg);
      else if (okPt([t.lat, t.lng])) L.circleMarker([t.lat, t.lng], {radius: 4, color: sCol(t.sport), weight: 2, fillOpacity: 0.6}).addTo(fg);
    });
  };
  cmap._cvFit = () => {
    const b = fg.getLayers().length ? fg.getBounds() : bg.getLayers().length ? bg.getBounds() : null;
    if (b && b.isValid()) cmap.fitBounds(b, {padding: [30, 30], animate: false, maxZoom: 13});
    else cmap.setView([50, 9], 6, {animate: false});
  };
  draw(ROUTES);
  if (typeof rsMapBind === "function") rsMapBind(cmap);
  if (el.clientWidth && !el.closest("details:not([open])")) cmap._cvFit();
  else {
    cmap._cvStale = true;
    cmap.setView([50, 9], 6, {animate: false});
  }
  if (typeof rsWatchMap === "function") rsWatchMap();
  if (!ROUTES) {
    await loadRoutes().catch(() => null);
    if (tok !== window._rt || map !== cmap) return;
    draw(ROUTES);
    if (!cmap._cvUser) cmap._cvFit();
  }
}
{
  VIEWS.area = async (...a) => {
    window.GD_WRAPPED = true;
    slViewStart("gebiet");
    const tok = window._rt;
    await slEnsure("gebiet");
    if (tok !== window._rt) return STALE();
    slResolve("gebiet");
    window.RS_CUR = null;
    await gbAreaBase(...a);
  };
}

/* ---------- Gebiet hinzufügen / bearbeiten (eigene Gebiete) ---------- */
/* g = eigenes Gebiet zum Bearbeiten (Zeile von /api/gebiete/eigene) oder null: dann erst suchen (Server, OpenStreetMap), dann bearbeiten. Das Rechteck ist [Süd, West, Nord, Ost]. */
function gbDialog(g) {
  const m = uiModal(`<h2>${g ? "Gebiet bearbeiten" : "Gebiet hinzufügen"}</h2><div id="gbdb"></div>`), body = m.querySelector("#gbdb");
  let mp = null;
  const rm = m.remove.bind(m);
  m.remove = () => {
    try {
      if (mp) mp.remove();
    } catch (e) {}
    mp = null;
    rm();
  };
  const set = (title, html) => {
    m.querySelector("h2").textContent = title;
    body.innerHTML = html;
  };
  const num = v => (v === "" || v == null ? NaN : +String(v).replace(",", "."));
  /* Schritt 2: Name, Typ, Land, Rechteck (Zahlen, Karte) */
  const form = (d, titel) => {
    set(titel, `<div class="field"><label for="gbn">Name</label><input id="gbn" maxlength="80" class="w100" value="${esc(d.name || "")}"></div>
     <div class="row g8 aic mt8"><label for="gbt">Typ</label><select id="gbt">${GB_TYP.map(([k, l]) => `<option value="${k}"${k === d.typ ? " selected" : ""}>${l}</option>`).join("")}</select>
      <label for="gbland">Land</label><input id="gbland" maxlength="60" class="fx1 mnw130" value="${esc(d.land || "")}" placeholder="optional"></div>
     <fieldset class="gbbox"><legend>Rechteck des Gebiets</legend><p class="mut fs14 m0-0-8">Grenzen in Grad (Breite und Länge). Zuordnung: eine Tour gehört zum Gebiet, wenn ihr Startpunkt im Rechteck liegt. Du kannst die Zahlen eingeben oder den Kartenausschnitt übernehmen.</p>
      <div class="gbnums"><label>Nord <input id="gbN" inputmode="decimal" value="${d.box ? d.box[2] : ""}"></label><label>West <input id="gbW" inputmode="decimal" value="${d.box ? d.box[1] : ""}"></label>
       <label>Ost <input id="gbE" inputmode="decimal" value="${d.box ? d.box[3] : ""}"></label><label>Süd <input id="gbS" inputmode="decimal" value="${d.box ? d.box[0] : ""}"></label></div>
      <div id="gbmap" class="gbmap" role="img" aria-label="Karte mit dem Rechteck des Gebiets"></div>
      <div class="row g8 aic mt8"><button type="button" class="btn ghost sm" id="gbfit">Kartenausschnitt übernehmen</button><span class="mut" id="gbcnt" role="status" aria-live="polite"></span></div></fieldset>
     <div id="gber" class="bad" role="alert"></div><div class="uifoot"><button type="button" class="btn ghost" id="gbno">Abbrechen</button><button type="button" class="btn" id="gbok">Speichern</button></div>`);
    const q = s => body.querySelector(s), box = () => [num(q("#gbS").value), num(q("#gbW").value), num(q("#gbN").value), num(q("#gbE").value)], okBox = b => b.every(isFinite) && b[0] < b[2] && b[1] < b[3];
    mp = mkMap(q("#gbmap"), {layers: false});
    const rect = L.rectangle([[0, 0], [0, 0]], {color: "#2a7f7f", weight: 2, fillOpacity: 0.12, interactive: false}).addTo(mp);
    const draw = fit => {
      const b = box();
      if (!okBox(b)) {
        rect.setBounds([[0, 0], [0, 0]]);
        q("#gbcnt").textContent = "";
        return;
      }
      rect.setBounds([[b[0], b[1]], [b[2], b[3]]]);
      if (fit) mp.fitBounds(rect.getBounds(), {padding: [20, 20], animate: false});
      const n = TOURS.filter(t => okPt([t.lat, t.lng]) && t.lat >= b[0] && t.lat <= b[2] && t.lng >= b[1] && t.lng <= b[3]).length;
      q("#gbcnt").textContent = n === 1 ? "1 Tour liegt in diesem Rechteck" : `${n} Touren liegen in diesem Rechteck`;
    };
    mp.setView([48, 10], 4, {animate: false});
    draw(true);
    ["gbN", "gbW", "gbE", "gbS"].forEach(i => (q("#" + i).oninput = () => draw(true)));
    q("#gbfit").onclick = () => {
      const b = mp.getBounds(), r = v => String(Math.round(v * 10000) / 10000);
      q("#gbS").value = r(b.getSouth());
      q("#gbW").value = r(b.getWest());
      q("#gbN").value = r(b.getNorth());
      q("#gbE").value = r(b.getEast());
      draw(false);
    };
    q("#gbno").onclick = () => m.remove();
    q("#gbok").onclick = async () => {
      const er = q("#gber"), b = box(), name = q("#gbn").value.trim();
      er.textContent = "";
      if (!name) return void (er.textContent = "Bitte einen Namen eingeben.");
      if (!okBox(b)) return void (er.textContent = "Bitte ein gültiges Rechteck angeben: Süd kleiner als Nord, West kleiner als Ost.");
      const bd = JSON.stringify({name, typ: q("#gbt").value, land: q("#gbland").value.trim(), box: b, quelle: d.quelle || ""}), h = {"content-type": "application/json"};
      q("#gbok").disabled = true;
      try {
        const r = await api(g ? `/api/gebiete/eigene/${encodeURIComponent(g.id)}` : "/api/gebiete/eigene", {method: "POST", headers: h, body: bd});
        await gbChanged();
        m.remove();
        if (g) route();
        else location.hash = "#/area/" + encodeURIComponent(r.id);
      } catch (e) {
        er.textContent = e.message;
        q("#gbok").disabled = false;
      }
    };
    q("#gbn").focus();
  };
  if (g) return form(g, "Gebiet bearbeiten");
  /* Schritt 1: Suche */
  set("Gebiet hinzufügen", `<p class="mut fs14">Gib den Namen eines Gebirges, Tals, einer Insel, Küste oder Landschaft ein. Die Suche (OpenStreetMap) schlägt Gebiete mit ihrem Rechteck vor; Name, Typ und Grenzen kannst du danach ändern.</p>
   <form id="gbsf" class="row g8 aic" novalidate><input id="gbsq" type="search" class="fx1 mnw200" placeholder="Name des Gebiets" aria-label="Name des Gebiets" maxlength="120" autocomplete="off"><button type="submit" class="btn alt" id="gbsb">Suchen</button></form>
   <div id="gbsr" class="gbsr" role="status" aria-live="polite"></div>
   <div class="uifoot"><button type="button" class="btn ghost" id="gbno">Abbrechen</button><button type="button" class="btn alt" id="gbman">Von Hand anlegen …</button></div>`);
  const q = s => body.querySelector(s);
  q("#gbno").onclick = () => m.remove();
  q("#gbman").onclick = () => form({name: q("#gbsq").value.trim(), typ: "region", box: null}, "Gebiet hinzufügen");
  let res = [];
  q("#gbsf").onsubmit = async e => {
    e.preventDefault();
    const t = q("#gbsq").value.trim(), out = q("#gbsr");
    if (t.length < 2) return void (out.textContent = "Bitte mindestens zwei Zeichen eingeben.");
    out.textContent = "Suche …";
    q("#gbsb").disabled = true;
    try {
      res = await api("/api/gebiete/suche?q=" + encodeURIComponent(t));
    } catch (er) {
      q("#gbsb").disabled = false;
      return void (out.innerHTML = `<span>${esc(er.message)}</span>. <span>Du kannst das Gebiet auch von Hand anlegen.</span>`);
    }
    q("#gbsb").disabled = false;
    if (!res.length) return void (out.textContent = "Kein Gebiet gefunden. Probiere einen anderen Namen oder lege das Gebiet von Hand an.");
    out.innerHTML = `<div class="gbres" role="group" aria-label="Treffer">${res.map((r, i) => `<button type="button" class="gbr" data-i="${i}"${r.gross ? " disabled" : ""}><span class="gbrn"><b>${esc(r.name)}</b><small class="mut">${esc([r.art, r.land].filter(Boolean).join(" · "))}</small></span>${r.gross ? '<small class="mut">zu groß</small>' : ""}</button>`).join("")}</div>`;
  };
  q("#gbsr").onclick = e => {
    const b = e.target.closest(".gbr");
    if (b && !b.disabled) {
      const r = res[+b.dataset.i];
      form({name: r.name, typ: r.typ, land: r.land, box: r.box, quelle: r.quelle}, "Gebiet hinzufügen");
    }
  };
  q("#gbsq").focus();
}
/* ---------- Anbindung: Adresse #/area/… gehört zum Menüpunkt „Gebiete“ ---------- */
if (typeof NAV_OF !== "undefined") NAV_OF.area = "areas";
slLate(/^#\/areas(\?.*)?$/, "GE_WRAPPED", "#gbl");
slLate(/^#\/area\/[^/]*$/, "GD_WRAPPED", "#cm, .gbleer");
