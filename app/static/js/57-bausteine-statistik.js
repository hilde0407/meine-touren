/* =====================  3.22.0 Bausteine der Statistikseite  =====================
   Gleiches Muster wie 50-bausteine.js und 52-bausteine-uebersicht.js (Katalog-Kategorie „Statistik“, nur auf der Statistikseite). Sie rechnen aus den geladenen Touren (TOURS) mit denselben Regeln
   wie der Server (GET /api/bausteine/statistik in app/bausteine_daten.py, dort die Referenz): Sportart und Zeitraum über flSelect() (53-filter.js), Zeitraum standardmäßig „Gesamte Zeit“.
   Auf der Statistikseite übernehmen sie den globalen Filter (56-statistik.js), außer ihr Eigentümer schaltet im Zahnrad „Globalen Filter verwenden“ aus.
   Wochentage gibt es schon als „Lieblingstage und Tageszeiten“ (Übersichts-Baustein, auch auf der Statistikseite einfügbar). */
const ST_FIELDS = [{kind: "sports"}, {kind: "range", def: "all"}, {kind: "title"}];
const ST_LEN = [5, 10, 15, 20, 30, 50];                                                  // Obergrenzen der Längenklassen in km (wie LAENGEN im Server)
const ST_LENL = ["unter 5", "5–10", "10–15", "15–20", "20–30", "30–50", "über 50"];
const ST_WERT = {km: ["Strecke", t => t.km, v => slKm(v)], hm: ["Aufstieg", t => t.up_m || 0, v => slHm(v)], dauer: ["Dauer", t => t.h, v => slDur(v * 3600)], tempo: ["Tempo", t => (t.h > 0 ? t.km / t.h : 0), v => fmtTempo(v)]};
const stNoTours = (b, cfg) => flNone(b, (cfg.sports || []).length || cfg.range ? "" : "Noch keine Touren.");
/* Spaltendiagramm-Zeitstrahl und Trend: kleine Linie als Inline-SVG (Farben über Klassen, Maße als Attribute) */
function stLine(pts, trend, label) {
  const W = 300, H = 110, mn = Math.min(...pts.map(p => p.v)), mx = Math.max(...pts.map(p => p.v)), pad = (mx - mn || 1) * 0.12, lo = mn - pad, hi = mx + pad,
    X = i => 6 + (i * (W - 12)) / Math.max(1, pts.length - 1), Y = v => H - 8 - ((v - lo) / (hi - lo || 1)) * (H - 16),
    d = pts.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(p.v).toFixed(1)}`).join(" ");
  return `<svg class="stline" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}"><path class="stl" d="${d}"/>${pts.map((p, i) => `<circle class="std" cx="${X(i).toFixed(1)}" cy="${Y(p.v).toFixed(1)}" r="3"><title>${esc(p.l)}: ${esc(p.t)}</title></circle>`).join("")}` +
    (trend ? `<path class="stt" d="M${X(trend.i0).toFixed(1)} ${Y(trend.a + trend.b * trend.i0).toFixed(1)} L${X(trend.i1).toFixed(1)} ${Y(trend.a + trend.b * trend.i1).toFixed(1)}"/>` : "") + "</svg>";
}
const stFit = pts => {                                                                    // Ausgleichsgerade über die Zeitabschnitte (x = Index im Zeitstrahl)
  const n = pts.length, xs = pts.map(p => p.x), mx = xs.reduce((a, b) => a + b, 0) / n, my = pts.reduce((a, p) => a + p.v, 0) / n,
    sxx = xs.reduce((a, x) => a + (x - mx) ** 2, 0), b = sxx ? pts.reduce((a, p, i) => a + (xs[i] - mx) * (p.v - my), 0) / sxx : 0;
  return {a: my - b * mx, b, i0: xs[0], i1: xs[n - 1]};
};

Object.assign(window.SL_WT, {
  stmonate: {
    fam: "statistik", cat: "statistik", icon: "met", name: "Monatsvergleich", title: () => "Monatsvergleich", multi: true, defaults: {metric: "km"}, filter: {range: "all"}, w: "halb", seiten: ["statistik"],
    desc: "Welche Monate des Jahres am stärksten sind: zwölf Säulen von Januar bis Dezember, nach Strecke, Aufstieg, Dauer oder Anzahl der Touren, mit dem stärksten Monat hervorgehoben.",
    fields: [{k: "metric", kind: "radio", def: "km", label: "Säulen nach", options: [["km", "Strecke"], ["up", "Aufstieg"], ["h", "Dauer"], ["count", "Anzahl der Touren"]]}, ...ST_FIELDS],
    preview: () => slPvBars([8, 12, 20, 28, 34, 26, 30, 22, 16, 10, 6, 4]),
    render(c, b, cfg) {
      const A = flSelect(cfg, "all").list, MT = FL_MET[cfg.metric] ? cfg.metric : "km";
      if (!A.length) return stNoTours(b, cfg);
      const v = Array(12).fill(0);
      A.forEach(t => (v[t.m - 1] += FL_MET[MT].f(t)));
      const best = v.indexOf(Math.max(...v)), avg = slSum(v, x => x) / 12, F = FL_MET[MT].fmt, un = MT === "count" ? " Touren" : "";
      b.innerHTML = slCols(v, {hl: best, avg, label: `Säulendiagramm ${FL_MET[MT].name} je Monat, am stärksten ${MONL[best]} mit ${F(v[best])}${un}`, labels: SL_MON, cls: "slsm"}) +
        `<p class="slcmp">${MONL[best]} ist dein stärkster Monat.</p><p class="mut slcmpn">${F(v[best])}${un}; im Schnitt aller Monate ${F(avg)}${un} (gestrichelte Linie).</p>`;
      slBadge(c, MONL[best]);
    },
  },
  stentwicklung: {
    fam: "statistik", cat: "statistik", icon: "trend", name: "Entwicklung", title: cfg => (cfg.metric === "km" ? "Entwicklung der Strecke" : "Entwicklung des Tempos"), multi: true, defaults: {metric: "pace"}, filter: {range: "all"}, w: "halb", seiten: ["statistik"],
    desc: "Wie sich dein Tempo (km/h) oder die Länge deiner Touren (km pro Tour) über die Zeit entwickelt, als Linie je Monat (bei langen Zeiträumen je Jahr) mit gestrichelter Trend-Linie.",
    fields: [{k: "metric", kind: "radio", def: "pace", label: "Linie zeigt", options: [["pace", "Tempo (km/h)"], ["km", "Strecke pro Tour (km)"]]}, ...ST_FIELDS],
    preview: () => slPvLine([34, 30, 32, 24, 26, 18, 20, 12]),
    render(c, b, cfg) {
      const A = flSelect(cfg, "all").list.filter(t => t.h > 0 || cfg.metric === "km"), pace = cfg.metric !== "km";
      if (!A.length) return stNoTours(b, cfg);
      const first = A.reduce((m, t) => (t.date < m ? t.date : m), A[0].date), last = A.reduce((m, t) => (t.date > m ? t.date : m), A[0].date),
        months = (+last.slice(0, 4) - +first.slice(0, 4)) * 12 + +last.slice(5, 7) - +first.slice(5, 7) + 1, yearly = months > 36,
        key = t => (yearly ? t.y : t.y * 12 + t.m - 1), g = new Map();
      A.forEach(t => {
        const k = key(t), e = g.get(k) || {n: 0, km: 0, h: 0};
        e.n++;
        e.km += t.km;
        e.h += t.h;
        g.set(k, e);
      });
      const un = pace ? "km/h" : "km", k0 = Math.min(...g.keys()),
        pts = [...g.entries()].sort((x, y) => x[0] - y[0]).map(([k, e]) => ({x: k - k0, v: pace ? (e.h ? e.km / e.h : 0) : e.km / e.n,
          l: yearly ? String(k) : `${MON[k % 12]} ${Math.floor(k / 12)}`})).filter(p => p.v > 0);
      pts.forEach(p => (p.t = `${nf(p.v, 1)} ${un}`));
      if (pts.length < 3) return slNote(b, "Für eine Entwicklung braucht es mindestens drei " + (yearly ? "Jahre" : "Monate") + " mit Touren.");
      const f = stFit(pts), span = f.b * (pts[pts.length - 1].x - pts[0].x), avg = slSum(pts, p => p.v) / pts.length,
        dir = Math.abs(span) < avg * 0.03 ? "gleichbleibend" : span > 0 ? "steigend" : "fallend",
        what = pace ? "Tempo" : "Strecke pro Tour";
      b.innerHTML = stLine(pts, f, `Liniendiagramm ${what} je ${yearly ? "Jahr" : "Monat"} von ${pts[0].l} bis ${pts[pts.length - 1].l}, Trend ${dir}`) +
        `<div class="slxl sb" aria-hidden="true"><span>${esc(pts[0].l)}</span><span>${esc(pts[pts.length - 1].l)}</span></div>` +
        `<p class="slcmp">Trend: ${dir}</p><p class="mut slcmpn">${what} von ${nf(pts[0].v, 1)} auf ${nf(pts[pts.length - 1].v, 1)} ${un} (Mittel ${nf(avg, 1)} ${un}); Trend-Linie gestrichelt.</p>`;
      slBadge(c, dir);
    },
  },
  stlaengen: {
    fam: "statistik", cat: "statistik", icon: "met", name: "Streckenlängen", title: () => "Streckenlängen", filter: {range: "all"}, w: "halb", seiten: ["statistik"],
    desc: "Wie lang deine Touren sind: ein Histogramm der Strecken in Klassen von unter 5 bis über 50 Kilometer.",
    fields: ST_FIELDS,
    preview: () => slPvBars([18, 34, 28, 20, 12, 6, 3]),
    render(c, b, cfg) {
      const A = flSelect(cfg, "all").list;
      if (!A.length) return stNoTours(b, cfg);
      const n = Array(ST_LEN.length + 1).fill(0);
      A.forEach(t => {
        const i = ST_LEN.findIndex(g => t.km < g);
        n[i < 0 ? ST_LEN.length : i]++;
      });
      const best = n.indexOf(Math.max(...n));
      b.innerHTML = slCols(n, {hl: best, label: `Histogramm der Streckenlängen in Kilometern, die meisten Touren (${n[best]}) liegen bei ${ST_LENL[best]} km`, labels: ST_LENL.map(l => l.replace("unter ", "<").replace("über ", ">")), cls: "slsm"}) +
        `<p class="slcmp">Meist ${ST_LENL[best]} km</p><p class="mut slcmpn">${n[best] === 1 ? "1 Tour" : n[best] + " Touren"} von ${A.length} liegen in dieser Klasse; die Länge zählt in Kilometern.</p>`;
      slBadge(c, `${ST_LENL[best]} km`);
    },
  },
  sthoehe: {
    fam: "statistik", cat: "statistik", icon: "prof", name: "Aufstieg im Jahr", title: () => "Aufstieg im Jahresverlauf", multi: true, filter: {range: "year"}, w: "halb", seiten: ["statistik"],
    desc: "Wie sich dein Aufstieg im Lauf eines Jahres aufsummiert, als Linie, dazu das Vorjahr gestrichelt. Gezeigt wird das gewählte Jahr, sonst das jüngste Jahr mit Touren.",
    fields: [{kind: "sports"}, {kind: "range", def: "year", opts: ["year", "y"], label: "Jahr"}, {kind: "title"}],
    preview: () => slPvLine([40, 38, 34, 30, 24, 20, 12, 6]),
    render(c, b, cfg) {
      const base = TOURS.filter(t => flSport(t, cfg));
      if (!base.length) return stNoTours(b, cfg);
      const R = flRange(cfg, "year", {fallback: true}), want = R.year && (R.kind === "y" || R.kind === "year") ? R.year : null,
        yr = want || Math.max(...base.map(t => t.y)), cum = y => {
          let s = 0;
          const pts = [[0, 0]];
          base.filter(t => t.y === y).slice().reverse().forEach(t => {
            s += t.up_m || 0;
            pts.push([(Date.UTC(y, t.m - 1, +t.date.slice(8, 10)) - Date.UTC(y, 0, 1)) / 864e5, s]);
          });
          return pts;
        },
        cur = cum(yr), tot = cur[cur.length - 1][1], ser = [{pts: cur, color: cssv("--bars"), w: 3.2}];
      if (base.some(t => t.y === yr - 1)) ser.unshift({pts: cum(yr - 1), color: cssv("--accent2"), dash: 1, w: 2});
      const vj = ser.length > 1 ? ser[0].pts[ser[0].pts.length - 1][1] : 0;
      b.innerHTML = lineChart(ser).replace('<svg class="chart"', `<svg class="chart" role="img" aria-label="${esc(`Aufstieg im Jahr ${yr} kumuliert, insgesamt ${fmtHm(tot)}`)}"`) +
        `<div class="legend"><span><i class="stk"></i>${yr}</span>${vj ? `<span><i class="stk stk2"></i>${yr - 1}</span>` : ""}</div><p class="slcmp">${fmtHm(tot)} in ${yr}</p>` +
        (vj ? `<p class="mut slcmpn">Vorjahr insgesamt ${fmtHm(vj)}.</p>` : "");
      slBadge(c, `${yr}: ${fmtHm(tot)}`);
    },
  },
  sttop: {
    fam: "statistik", cat: "statistik", icon: "cmp", name: "Top-Touren", title: cfg => `Top-Touren nach ${(ST_WERT[cfg.wert] || ST_WERT.km)[0]}`, multi: true, defaults: {wert: "km", n: 5}, filter: {range: "all"}, w: "halb", seiten: ["statistik"],
    desc: "Deine besten Touren als Liste mit Link: nach Strecke, Aufstieg, Dauer oder Tempo, drei bis zehn Einträge.",
    fields: [{k: "wert", kind: "radio", def: "km", label: "Sortiert nach", options: [["km", "Strecke"], ["hm", "Aufstieg"], ["dauer", "Dauer"], ["tempo", "Tempo"]]}, {k: "n", kind: "radio", num: true, def: 5, label: "Anzahl", options: [[3, "3"], [5, "5"], [8, "8"], [10, "10"]]}, ...ST_FIELDS],
    preview: () => slPrev('<ul class="sllist"><li><b>Gipfelrunde</b><span>32,4 km</span></li><li><b>Seeufer</b><span>28,1 km</span></li></ul>'),
    render(c, b, cfg) {
      const W = ST_WERT[cfg.wert] || ST_WERT.km, A = flSelect(cfg, "all").list.filter(t => cfg.wert !== "tempo" || (t.km >= 3 && t.h >= 0.5)), n = +cfg.n >= 1 && +cfg.n <= 10 ? +cfg.n : 5;
      if (!A.length) return stNoTours(b, cfg);
      const L = A.slice().sort((x, y) => W[1](y) - W[1](x) || (x.start_ts || 0) - (y.start_ts || 0)).filter(t => W[1](t) > 0).slice(0, n);
      if (!L.length) return slNote(b, "Dafür fehlen Angaben in den Touren.");
      b.innerHTML = `<ol class="sllist stt-l">${L.map(t => `<li><a href="#/tour/${slEnc(t.id)}">${esc(t.name)}</a><b>${W[2](W[1](t))}</b><span class="mut">${fmtDatumKurz(t.date)} · ${fmtKm(t.km)}</span></li>`).join("")}</ol>`;
      slBadge(c, W[2](W[1](L[0])));
    },
  },
});
