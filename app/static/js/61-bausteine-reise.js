/* =====================  3.33.0 Bausteine der Reisen-Seiten  =====================
   Gleiches Muster wie 50-bausteine.js, 57-bausteine-statistik.js und 60-bausteine-erinnerungen.js (Katalog-Kategorie „Reisen“). Die Seiten selbst (Karten der Reise, Reisen-Übersicht) baut 62-reiseseiten.js.
   Reise-Detailseite (Layout-Schlüssel „reise“, gilt für alle Reisen gleich; die Reise liefert ctx.reise = {tr, ts, days}: die Reise, ihre Touren nach Startzeit und ihre Tage mit Touren):
     rkennzahl  Reise-Kennzahlen: Reisetage, Touren, Strecke, Aufstieg, Abstieg, Unterwegs, Länder (Auswahl, geprüft in app/layout.py „REISE_VALUES“)
     rkmtag     Strecke je Tag: Säulendiagramm (Inline-SVG) über die Tage der Reise, auch Aufstieg, Dauer oder Anzahl der Touren (Feld „metric“)
     rdiashow   Reise-Diashow: der Baustein „Erinnerungen“ (60-bausteine-erinnerungen.js), eingeschränkt auf die Fotos aus dem Zeitraum der Reise (GET /api/photos?date_from=…&date_to=…, seit 3.32.0)
   Reisen-Übersicht (Schlüssel „reisen“, ctx.reise = {trips}):
     rnzahlen   Reisen-Kennzahlen: Reisen, Reisetage, Strecke, Aufstieg, Länder        rnjahre   Reisen je Jahr: Säulen je Jahr (Strecke, Anzahl der Reisen oder Reisetage)
   Alle Bausteine rechnen aus den schon geladenen Touren und Reisen (keine neue Abfrage außer den Fotos der Diashow) und zeigen bei fehlenden Daten einen kurzen Hinweis. */
const RS_DAY = 86400000;
const rsUtc = iso => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
const rsSpan = tr => Math.round((rsUtc(tr.end) - rsUtc(tr.start)) / RS_DAY) + 1;                      // Kalendertage der Reise (erster bis letzter Tag, beide mitgezählt)
const rsCountries = ts => [...new Set(ts.map(t => t.g_country).filter(Boolean))];
const RK_VALUES = [["tage", "Reisetage"], ["touren", "Touren"], ["km", "Strecke"], ["up", "Aufstieg"], ["down", "Abstieg"], ["h", "Unterwegs"], ["laender", "Länder"]];
const RK_DEF = ["tage", "touren", "km", "up", "h", "laender"];
const RN_VALUES = [["reisen", "Reisen"], ["tage", "Reisetage"], ["km", "Strecke"], ["up", "Aufstieg"], ["laender", "Länder"]];
const RT_METRIC = {km: ["Strecke je Tag", "km", t => t.km, v => fmtKm(v, {summe: true})], up: ["Aufstieg je Tag", "m", t => t.up_m || 0, v => fmtHm(v)],
  h: ["Dauer je Tag", "Std.", t => t.h, v => slDur(v * 3600)], count: ["Touren je Tag", "Touren", () => 1, v => nf(v, 0) + (v === 1 ? " Tour" : " Touren")]};
const RJ_METRIC = {km: ["Reisen: Strecke je Jahr", "km", tr => tr.km], count: ["Reisen je Jahr", "Reisen", () => 1], days: ["Reisetage je Jahr", "Tage", tr => rsSpan(tr)]};
const rsNoTrip = b => slNote(b, "Dieser Baustein gehört auf die Seite einer Reise.");
/* Beschriftung unter den Säulen: bei vielen Säulen nur jede n-te (die Spalten bleiben ausgerichtet) */
const rsLabels = (labels, max = 10) => {
  const k = Math.max(1, Math.ceil(labels.length / max));
  return labels.map((l, i) => (i % k ? "" : l));
};

Object.assign(window.SL_WT, {
  rkennzahl: {
    fam: "reise", cat: "reise", icon: "met", name: "Reise-Kennzahlen", title: () => "Reise-Kennzahlen", multi: true, w: "halb", seiten: ["reise"], defaults: {values: RK_DEF},
    desc: "Die wichtigsten Zahlen dieser Reise als Kacheln: Reisetage, Touren, Strecke, Aufstieg, Abstieg, Zeit unterwegs und Länder. Welche Kacheln erscheinen, wählst du in den Einstellungen.",
    fields: [{k: "values", kind: "checks", label: "Angezeigte Werte", min: 1, def: RK_DEF, options: RK_VALUES}, {kind: "title"}],
    preview: () => slPvTiles([["6", "Reisetage"], ["212 km", "Strecke"], ["3 100 m", "Aufstieg"]]),
    render(c, b, cfg, {reise}) {
      if (!reise || !reise.tr) return rsNoTrip(b);
      const {tr, ts, days} = reise, want = (cfg.values && cfg.values.length ? cfg.values : RK_DEF).filter(v => RK_VALUES.some(k => k[0] === v)), span = rsSpan(tr), land = rsCountries(ts),
        km = slSum(ts, t => t.km), tile = {
          tage: [String(span), "Reisetage", days.length < span ? `an ${days.length} Tagen mit Touren` : ""], touren: [String(ts.length), "Touren"], km: [slKm(km), "Strecke"],
          up: [slHm(slSum(ts, t => t.up_m || 0)), "Aufstieg"], down: [slHm(slSum(ts, t => t.down_m || 0)), "Abstieg"], h: [slDur(slSum(ts, t => t.h) * 3600), "Unterwegs"],
          laender: land.length ? [String(land.length), "Länder", land.slice(0, 3).join(", ") + (land.length > 3 ? " …" : "")] : null,
        }, list = want.map(v => tile[v]).filter(Boolean);
      if (!list.length) return slNote(b, "Für die gewählten Werte liegen bei dieser Reise keine Daten vor.");
      b.innerHTML = slTiles(list);
      slBadge(c, `${fmtKm(km, {d: 0})} · ${span === 1 ? "1 Tag" : span + " Tage"}`);
    },
  },
  rkmtag: {
    fam: "reise", cat: "reise", icon: "trend", name: "Strecke je Tag", title: cfg => (RT_METRIC[cfg.metric] || RT_METRIC.km)[0], multi: true, w: "halb", seiten: ["reise"], defaults: {metric: "km"},
    desc: "Ein Säulendiagramm über die Tage der Reise: wie viele Kilometer (oder Aufstieg, Stunden, Touren) an jedem Tag zusammenkamen, mit dem stärksten Tag hervorgehoben und der gestrichelten Durchschnittslinie.",
    fields: [{k: "metric", kind: "radio", def: "km", label: "Säulen nach", options: [["km", "Strecke"], ["up", "Aufstieg"], ["h", "Dauer"], ["count", "Anzahl der Touren"]]}, {kind: "title"}],
    preview: () => slPvBars([14, 22, 30, 18, 34, 10, 26]),
    render(c, b, cfg, {reise}) {
      if (!reise || !reise.tr) return rsNoTrip(b);
      const {tr, ts} = reise, M = RT_METRIC[cfg.metric] ? cfg.metric : "km", [name, un, f, fmt] = RT_METRIC[M], span = rsSpan(tr);
      if (!ts.length) return slNote(b, "Diese Reise hat keine Touren.");
      const all = span >= 1 && span <= 60,                                              // sehr lange Reisen: nur die Tage mit Touren, sonst zeigt jede Säule einen Kalendertag (auch Ruhetage)
        keys = all ? Array.from({length: span}, (_, i) => flDayAdd(tr.start, i)) : [...new Set(ts.map(t => t.date.slice(0, 10)))].sort(),
        v = keys.map(k => slSum(ts.filter(t => t.date.slice(0, 10) === k), f)),
        best = v.indexOf(Math.max(...v)), avg = slSum(v, x => x) / (v.filter(x => x > 0).length || 1),
        lab = keys.map(k => `${+k.slice(8, 10)}.${+k.slice(5, 7)}.`);
      b.innerHTML = slCols(v, {hl: best, avg, label: `Säulendiagramm: ${name}, am stärksten am ${fmtDatumKurz(keys[best])} mit ${fmt(v[best])}`, labels: rsLabels(lab), cls: "slsm rscol"}) +
        `<p class="slcmp">Stärkster Tag: ${fmtDatumKurz(keys[best])}</p><p class="mut slcmpn">${fmt(v[best])}; im Schnitt der Tage mit Touren ${fmt(avg)} (gestrichelte Linie).</p>`;
      slBadge(c, fmt(v[best]));
    },
  },
  rdiashow: {
    fam: "reise", cat: "reise", icon: "cam", name: "Reise-Diashow", title: () => "Fotos der Reise", multi: true, w: "voll", seiten: ["reise"], defaults: {mode: "best", view: "show", n: 12, link: true},
    desc: "Die Fotos aus dem Zeitraum dieser Reise als Einzelbild-Show, Raster oder Streifen, mit Link zur Vollbild-Diashow. Das ist der Baustein „Erinnerungen“, eingeschränkt auf diese Reise: Auswahl, Anzahl, Darstellung und Bildgröße stellst du in den Einstellungen ein.",
    dialog: (id, cfg) => erDialog(id, cfg, true), fields: [{kind: "erinn"}],
    kurz: cfg => (erCfg(cfg).mode === "random" ? ["Zufällig"] : erCfg(cfg).mode === "recent" ? ["Neueste"] : []),
    preview: () => slPrev('<div class="slpvf" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'),
    render(c, b, cfg, {reise}) {
      if (!reise || !reise.tr) return rsNoTrip(b);
      const fix = {from: reise.tr.start, to: reise.tr.end}, k = erCfg(cfg);
      b.innerHTML = (k.shuffle || k.link ? `<div class="rsdh">${k.shuffle ? '<button type="button" class="btn ghost sm ernew">Neu mischen</button>' : ""}${k.link ? `<a class="hmore erdia" target="_blank" rel="noopener" href="${esc(erSlideUrl(cfg, fix))}">Diashow starten</a>` : ""}</div>` : "") + '<div class="erb"></div>';
      const o = {keep: true, fix, none: "Zu dieser Reise gibt es keine Fotos."}, nb = b.querySelector(".ernew");
      if (nb) nb.onclick = () => erLoad(b, cfg, k.mode === "random" ? o : {...o, mix: true});
      return erLoad(b, cfg, o).then(() => {
        const n = (b._erList || []).length;
        if (n) slBadge(c, n === 1 ? "1 Foto" : `${n} Fotos`);
      });
    },
  },
  rnzahlen: {
    fam: "reisen", cat: "reise", icon: "met", name: "Reisen-Kennzahlen", title: () => "Reisen-Kennzahlen", w: "halb", seiten: ["reisen"], defaults: {values: ["reisen", "tage", "km", "up", "laender"]},
    desc: "Alle Reisen auf einen Blick: wie viele Reisen, Reisetage, Strecke, Aufstieg und Länder zusammenkommen.",
    fields: [{k: "values", kind: "checks", label: "Angezeigte Werte", min: 1, def: ["reisen", "tage", "km", "up", "laender"], options: RN_VALUES}, {kind: "title"}],
    preview: () => slPvTiles([["7", "Reisen"], ["46", "Reisetage"], ["1 480 km", "Strecke"]]),
    render(c, b, cfg, {reise}) {
      const L = (reise && reise.trips) || [];
      if (!L.length) return slNote(b, "Noch keine Reisen erkannt.");
      const want = (cfg.values && cfg.values.length ? cfg.values : RN_VALUES.map(v => v[0])).filter(v => RN_VALUES.some(k => k[0] === v)),
        land = [...new Set(L.flatMap(tr => [tr.country, ...tr.tours.map(i => (BY[i] || {}).g_country)]).filter(Boolean))],
        km = slSum(L, tr => tr.km), tile = {
          reisen: [String(L.length), L.length === 1 ? "Reise" : "Reisen"], tage: [String(slSum(L, rsSpan)), "Reisetage"], km: [fmtKm(km, {d: 0}), "Strecke"],
          up: [fmtHm(slSum(L, tr => tr.up_m || 0)), "Aufstieg"], laender: land.length ? [String(land.length), "Länder", land.slice(0, 3).join(", ") + (land.length > 3 ? " …" : "")] : null,
        }, list = want.map(v => tile[v]).filter(Boolean);
      if (!list.length) return slNote(b, "Für die gewählten Werte liegen keine Daten vor.");
      b.innerHTML = slTiles(list);
      slBadge(c, L.length === 1 ? "1 Reise" : `${L.length} Reisen`);
    },
  },
  rnjahre: {
    fam: "reisen", cat: "reise", icon: "trend", name: "Reisen je Jahr", title: cfg => (RJ_METRIC[cfg.metric] || RJ_METRIC.km)[0], w: "halb", seiten: ["reisen"], defaults: {metric: "km"},
    desc: "Ein Säulendiagramm über die Jahre: wie viele Reise-Kilometer, Reisen oder Reisetage auf jedes Jahr entfallen.",
    fields: [{k: "metric", kind: "radio", def: "km", label: "Säulen nach", options: [["km", "Strecke"], ["count", "Anzahl der Reisen"], ["days", "Reisetagen"]]}, {kind: "title"}],
    preview: () => slPvBars([10, 18, 8, 30, 22, 34]),
    render(c, b, cfg, {reise}) {
      const L = (reise && reise.trips) || [];
      if (!L.length) return slNote(b, "Noch keine Reisen erkannt.");
      const M = RJ_METRIC[cfg.metric] ? cfg.metric : "km", [name, un, f] = RJ_METRIC[M], ys = L.map(tr => +tr.start.slice(0, 4)),
        y1 = Math.max(...ys), y0 = Math.max(Math.min(...ys), y1 - 11), years = Array.from({length: y1 - y0 + 1}, (_, i) => y0 + i),
        v = years.map(y => slSum(L.filter(tr => +tr.start.slice(0, 4) === y), f)), best = v.indexOf(Math.max(...v)), val = x => nf(x, 0) + " " + un;
      b.innerHTML = slCols(v, {hl: best, label: `Säulendiagramm: ${name}, am stärksten ${years[best]} mit ${val(v[best])}`, labels: years.map(y => (years.length > 8 ? "’" + String(y).slice(2) : String(y))), cls: "slsm rscol"}) +
        `<p class="slcmp">Stärkstes Jahr: ${years[best]}</p><p class="mut slcmpn">${val(v[best])}</p>`;
      slBadge(c, String(years[best]));
    },
  },
});

/* Vorlagen für die Ansichten der Reisen-Seiten (55-vorlagen.js: Format der Einträge dort beschrieben) */
SL_TPL.push(
  {id: "re-kompakt", fam: "reise", name: "Kompakt", desc: "Wenig auf einen Blick: Kopf und Karte oben, daneben die Strecke je Tag, darunter die Touren. Statistik, Flug und Fotos sind ausgeblendet.",
    items: [["kopf", "voll"], ["karte", "halb"], ["w:rkmtag", "halb"], ["touren", "voll"]]},
  {id: "re-fotos", fam: "reise", name: "Fotoreise", desc: "Für die Erinnerung: oben die Foto-Show der Reise, dann Karte und Kennzahlen, darunter alle Fotos und die Touren.",
    items: [["kopf", "voll"], ["w:rdiashow", "voll"], ["karte", "voll"], ["w:rkennzahl", "voll"], ["fotos", "voll"], ["touren", "voll"]]},
  {id: "re-tage", fam: "reise", name: "Tag für Tag", desc: "Für den Verlauf: Reise-Kennzahlen und Strecke je Tag nebeneinander, darunter Karte, Statistik nach Sportart und die Touren.",
    items: [["kopf", "voll"], ["w:rkennzahl", "halb"], ["w:rkmtag", "halb"], ["karte", "voll"], ["stat", "voll"], ["touren", "voll"]]},
  {id: "rn-kompakt", fam: "reisen", name: "Nur Reisen", desc: "Ruhig und kurz: die Reisen mit ihren Kennzahlen, ohne Mehrtagestouren und Alben.",
    items: [["w:rnzahlen", "voll"], ["reisen", "voll"]]},
  {id: "rn-jahre", fam: "reisen", name: "Reisen im Überblick", desc: "Für den Blick auf alle Reisen: Kennzahlen und Reisen je Jahr nebeneinander, darunter die Reisen und die Mehrtagestouren.",
    items: [["w:rnzahlen", "halb"], ["w:rnjahre", "halb"], ["reisen", "voll"], ["serien", "voll"]]},
);
