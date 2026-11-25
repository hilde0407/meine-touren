/* =====================  3.18.0 Mehr Bausteine: Tourseite  =====================
   Gleiches Muster wie 50-bausteine.js: Typ = {fam, cat, icon, name, title, desc, multi, fields, defaults, preview(), render(card, body, cfg, {t})}.
   Daten: vorhandene Endpunkte, dazu GET /api/bausteine/<name>?tour=<id> (app/bausteine_daten.py). Grafiken sind Inline-SVG (Maße als Attribute) oder Balken aus CSS,
   Farben über Variablen (style.css „Mehr Bausteine“). Jeder Baustein zeigt bei fehlenden Daten einen Hinweis statt einer leeren Fläche. */
const SL_SLOPE = [
  ["steil_ab", "Steil bergab", "unter −15 %"], ["ab", "Bergab", "−15 bis −5 %"], ["leicht_ab", "Leicht bergab", "−5 bis −2 %"], ["eben", "Eben", "−2 bis 2 %"],
  ["leicht_auf", "Leicht bergauf", "2 bis 5 %"], ["auf", "Bergauf", "5 bis 15 %"], ["steil_auf", "Steil bergauf", "über 15 %"],
];
const SL_WHY = {keine_strecke: "Für diese Tour liegt keine Strecke vor.", zu_kurz: "Die Strecke ist für diese Auswertung zu kurz.", keine_zeit: "Der Track dieser Tour enthält keine Zeitstempel.", keine_hoehe: "Der Track dieser Tour enthält keine Höhenwerte."};
const slWhy = (b, d) => slNote(b, SL_WHY[d && d.status] || "Für diese Tour liegen dafür keine Daten vor.");
const slMedian = a => {
  const s = a.slice().sort((x, y) => x - y), m = s.length >> 1;
  return s.length ? (s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2) : 0;
};
const slClock = m => {
  const r = Math.round(m);
  return `${pad2(Math.floor(r / 60) % 24)}:${pad2(r % 60)}`;
};
const slSignPct = p => `${p >= 0 ? "+" : "−"}${Math.abs(Math.round(p))} %`;
const slFmtN = n => nf(n, n >= 10 ? 0 : 1);
/* Bezugsgrößen der Spaß-Vergleiche: [Kennung, Name, Wert in m bzw. kcal] */
const SL_FUN = {
  hoehe: [["dom", "Kölner Dom", 157], ["eiffel", "Eiffelturm", 330], ["burj", "Burj Khalifa", 828], ["everest", "Mount Everest", 8849]],
  weg: [["fussball", "Fußballfelder", 105], ["marathon", "Marathon", 42195], ["stadion", "Stadionrunden", 400]],
  kcal: [["schnitzel", "Schnitzel", 650], ["pizza", "Pizza", 800], ["koelsch", "Kölsch (0,2 l)", 85], ["eis", "Kugeln Eis", 100]],
};

Object.assign(window.SL_WT, {
  splits: {
    fam: "tour", cat: "grafik", icon: "met", name: "Kilometer-Splits", title: () => "Kilometer-Splits", defaults: {unit: "kmh"},
    desc: "Tempo je Kilometer als Säulen, mit schnellstem und langsamstem Abschnitt und dem Durchschnitt als gestrichelter Linie.",
    fields: [{k: "unit", kind: "radio", label: "Anzeige", options: [["kmh", "Tempo in km/h"], ["pace", "Zeit je Kilometer"]]}],
    preview: () => slPvBars([22, 30, 26, 34, 18, 28, 32, 24]),
    async render(c, b, cfg, {t}) {
      const d = t && (await slGet(`/api/bausteine/splits?tour=${slEnc(t.id)}`));
      if (!d || d.status !== "ok" || !d.splits.length) return slWhy(b, d);
      const S = d.splits, step = d.schritt_m, pace = cfg.unit === "pace",
        full = S.filter(x => !x.teil).length ? S.filter(x => !x.teil) : S,
        fast = full.reduce((m, x) => (x.kmh > m.kmh ? x : m)), slow = full.reduce((m, x) => (x.kmh < m.kmh ? x : m)),
        lens = S.map((x, i) => (x.km - (i ? S[i - 1].km : 0)) * 1000), avg = (slSum(lens, x => x) / slSum(S, x => x.dauer_s)) * 3.6,
        f = kmh => (pace ? `${slMin(3600 / kmh)} min/km` : `${fmtTempo(kmh)}`),
        every = Math.ceil(S.length / 9),
        labels = S.map((x, i) => (S.length <= 9 || (i + 1) % every === 0 || i === S.length - 1 ? nf(x.km, x.teil ? 1 : 0) : "")),
        label = `Säulendiagramm: Tempo je Abschnitt, von ${f(slow.kmh)} bis ${f(fast.kmh)}`;
      b.innerHTML = `<p class="mut slcap">${step === 1000 ? "Tempo je Kilometer (nur Bewegungszeit)" : `Tempo je ${fmtKm(step / 1000, {d: 0})} (nur Bewegungszeit)`}</p>` +
        slCols(S.map(x => x.kmh), {hl: S.indexOf(fast), dim: S.map((x, i) => (x.teil ? i : -1)).filter(i => i >= 0), avg, label, labels, cls: "slsp"}) +
        `<ul class="slfacts"><li><i class="slsq hl"></i><span>Schnellster Abschnitt</span><b>bis km ${nf(fast.km, fast.teil ? 1 : 0)} · ${f(fast.kmh)}</b></li>` +
        `<li><i class="slsq v"></i><span>Langsamster Abschnitt</span><b>bis km ${nf(slow.km, slow.teil ? 1 : 0)} · ${f(slow.kmh)}</b></li>` +
        `<li><i class="slsq avg"></i><span>Durchschnitt (gestrichelt)</span><b>${f(avg)}</b></li></ul>`;
      slBadge(c, `Ø ${f(avg)}`);
    },
  },
  steigung: {
    fam: "tour", cat: "grafik", icon: "prof", name: "Steigungs-Verteilung", title: () => "Steigungs-Verteilung",
    desc: "Welcher Anteil der Strecke war steil bergab, eben oder steil bergauf: sieben Steigungsklassen als Balken.",
    preview: () => slPvHbars([14, 30, 46, 96, 52, 34, 12]),
    async render(c, b, cfg, {t}) {
      const d = t && (await slGet(`/api/bausteine/steigung?tour=${slEnc(t.id)}`));
      if (!d || d.status !== "ok") return slWhy(b, d);
      const up = d.anteile.leicht_auf + d.anteile.auf + d.anteile.steil_auf;
      b.innerHTML = `<ul class="slhist">${SL_SLOPE.map(([k, name, rng], i) => {
        const p = d.anteile[k] * 100;
        return `<li><span class="slhn">${name}<small class="mut">${rng}</small></span>${slBr(p, "slc" + i)}<b>${p > 0 && p < 1 ? "unter 1 %" : Math.round(p) + " %"}</b></li>`;
      }).join("")}</ul><p class="mut slcap">Anteil an der Strecke von ${fmtKm(d.dist_m / 1000)}, Steigung über 50 m geglättet.</p>`;
      slBadge(c, `${Math.round(up * 100)} % bergauf`);
    },
  },
  bewegung: {
    fam: "tour", cat: "grafik", icon: "trend", name: "Bewegung und Pause", title: () => "Bewegung und Pause",
    desc: "Die ganze Tour als Zeitstreifen: wann du gelaufen bist und wann du Pause gemacht hast.",
    preview: () => slPrev('<svg viewBox="0 0 120 22" class="slpvs" aria-hidden="true"><rect class="slmv" x="0" y="2" width="44" height="18" rx="3"/><rect class="slps" x="46" y="7" width="12" height="8" rx="2"/><rect class="slmv" x="60" y="2" width="38" height="18" rx="3"/><rect class="slps" x="100" y="7" width="6" height="8" rx="2"/><rect class="slmv" x="108" y="2" width="12" height="18" rx="3"/></svg>'),
    async render(c, b, cfg, {t}) {
      const d = t && (await slGet(`/api/bausteine/bewegung?tour=${slEnc(t.id)}`));
      if (!d || d.status !== "ok") return slWhy(b, d);
      const tot = d.gesamt_s || 1, pct = Math.round((d.bewegung_s / tot) * 100),
        rects = d.abschnitte.map(([k, a, e]) => `<rect class="${k === "p" ? "slps" : "slmv"}" x="${((a / tot) * 1000).toFixed(1)}" y="${k === "p" ? 9 : 0}" width="${Math.max(1.5, ((e - a) / tot) * 1000).toFixed(1)}" height="${k === "p" ? 10 : 28}"/>`).join("");
      b.innerHTML = `<svg class="slstrip" viewBox="0 0 1000 28" preserveAspectRatio="none" role="img" aria-label="${esc(`Zeitstreifen: ${pct} % in Bewegung, ${100 - pct} % Pause`)}">${rects}</svg>` +
        `<div class="slxl sb" aria-hidden="true"><span>0:00</span><span>${fmtDauer(tot, {summe: true})}</span></div>` +
        slTiles([[fmtDauer(d.bewegung_s, {summe: true}), "In Bewegung", `${pct} %`], [d.pause_s >= 60 ? fmtDauer(d.pause_s, {summe: true}) : "keine", "Pause", d.pause_s >= 60 ? `${100 - pct} %` : ""]]) +
        (d.pause_s < 60 ? '<p class="mut slcap">Keine nennenswerten Pausen aufgezeichnet.</p>' : '<p class="mut slcap">Pause: Tempo unter 0,3 km/h.</p>');
      slBadge(c, `${pct} % in Bewegung`);
    },
  },
  durchschnitt: {
    fam: "tour", cat: "grafik", icon: "cmp", name: "Diese Tour und dein Durchschnitt", title: () => "Diese Tour und dein Durchschnitt", defaults: {values: ["km", "up", "pace"]},
    kurz: cfg => (cfg.basis === "all" ? ["Alle Touren"] : cfg.basis === "year" ? ["Touren dieses Jahres"] : []),
    desc: "Strecke, Aufstieg, Tempo oder Dauer dieser Tour gegen den Median deiner Touren gleicher Sportart, als Balken mit Marke.",
    fields: [{k: "values", kind: "checks", label: "Angezeigte Werte", min: 1, options: [["km", "Strecke"], ["up", "Aufstieg"], ["pace", "Tempo"], ["dur", "Dauer"]]},
      {k: "basis", kind: "radio", def: "sport", label: "Vergleichen mit", options: [["sport", "Gleiche Sportart"], ["all", "Allen Touren"], ["year", "Touren dieses Jahres"]]}, {kind: "title"}],
    preview: () => slPrev('<svg viewBox="0 0 120 40" class="slpvs" aria-hidden="true"><rect class="slhb" x="0" y="4" width="84" height="8" rx="4"/><rect class="slmk" x="58" y="1" width="2" height="14"/><rect class="slhb" x="0" y="24" width="40" height="8" rx="4"/><rect class="slmk" x="58" y="21" width="2" height="14"/></svg>'),
    render(c, b, cfg, {t}) {
      if (!t) return slNote(b, "Keine Tour.");
      const basis = cfg.basis === "all" || cfg.basis === "year" ? cfg.basis : "sport",
        others = TOURS.filter(o => o.id !== t.id && o.km > 0 && (basis === "all" || (basis === "year" ? o.y === t.y : o.sport === t.sport)));
      if (others.length < 3) return slNote(b, basis === "sport" ? "Für diesen Vergleich braucht es mindestens drei andere Touren derselben Sportart." : basis === "year" ? "Für diesen Vergleich braucht es mindestens drei andere Touren dieses Jahres." : "Für diesen Vergleich braucht es mindestens drei andere Touren.");
      const pace = o => (o.h > 0.2 ? o.km / o.h : null),
        M = {
          km: ["Strecke", t.km, others.map(o => o.km), slKm], up: ["Aufstieg", t.up_m, others.map(o => o.up_m).filter(v => v != null), slHm],
          pace: ["Tempo", pace(t), others.map(pace).filter(v => v != null), v => fmtTempo(v)], dur: ["Dauer", t.h > 0 ? t.h * 3600 : null, others.filter(o => o.h > 0).map(o => o.h * 3600), s => fmtDauer(s, {summe: true})],
        },
        want = (cfg.values && cfg.values.length ? cfg.values : ["km", "up", "pace"]).filter(k => M[k]),
        rows = want.map(k => {
          const [lab, v, vals, fmt] = M[k];
          if (v == null || vals.length < 3) return "";
          const med = slMedian(vals), mx = Math.max(v, med) * 1.15 || 1, pct = med > 0 ? ((v - med) / med) * 100 : 0;
          return `<li><div class="slr1"><span>${lab}</span><b>${fmt(v)}</b></div>` +
            `<svg class="slbr slbm" viewBox="0 0 100 14" preserveAspectRatio="none" aria-hidden="true" focusable="false"><rect class="slbr-t" y="2" width="100" height="10"/><rect class="slbr-f${pct >= 0 ? " hl" : ""}" y="2" width="${((v / mx) * 100).toFixed(1)}" height="10"/><rect class="slmk" x="${((med / mx) * 100 - 0.3).toFixed(1)}" y="0" width="0.6" height="14"/></svg>` +
            `<div class="slr2 mut"><span>Median ${fmt(med)}</span><span class="slpct">${slSignPct(pct)}</span></div></li>`;
        }).filter(Boolean);
      if (!rows.length) return slNote(b, "Für die gewählten Werte liegen bei dieser Tour keine Daten vor.");
      b.innerHTML = `<ul class="slrows">${rows.join("")}</ul><p class="mut slcap">Der senkrechte Strich zeigt den Median deiner ${others.length} anderen Touren (${basis === "sport" ? `Sportart: ${esc(sName(t.sport))}` : basis === "year" ? `Jahr: ${t.y}` : "Alle Sportarten"}).</p>`;
      const km = pace(t) ? M.pace : M.km;
      slBadge(c, `${km[0]} ${slSignPct(((km[1] - slMedian(km[2])) / slMedian(km[2])) * 100)}`);
    },
  },
  jahresrang: {
    fam: "tour", cat: "zahlen", icon: "trend", name: "Rang im Jahr", title: () => "Rang im Jahr", multi: true, defaults: {metric: "km", scope: "all"},
    desc: "Die wievielte längste (oder höchste, längste Dauer) Tour des Jahres das ist, mit allen Touren des Jahres als Säulen.",
    fields: [{k: "metric", kind: "radio", label: "Rang nach", options: [["km", "Strecke"], ["up", "Aufstieg"], ["dur", "Dauer"]]}, {k: "scope", kind: "radio", label: "Vergleichen mit", options: [["all", "Allen Touren des Jahres"], ["sport", "Touren derselben Sportart"]]}],
    preview: () => slPrev('<p class="slcmp">Platz 3 von 41</p><svg viewBox="0 0 120 20" class="slpvs" aria-hidden="true">' + [20, 17, 15, 12, 11, 9, 8, 6, 5, 4, 3, 2].map((h, i) => `<rect class="${i === 2 ? "slhl" : ""}" x="${i * 10 + 1}" y="${20 - h}" width="8" height="${h}" rx="1"/>`).join("") + "</svg>"),
    render(c, b, cfg, {t}) {
      if (!t) return slNote(b, "Keine Tour.");
      const key = {km: o => o.km, up: o => o.up_m || 0, dur: o => o.h}[cfg.metric] || (o => o.km),
        what = {km: "Strecke", up: "Aufstieg", dur: "Dauer"}[cfg.metric] || "Strecke",
        pool = TOURS.filter(o => o.y === t.y && (cfg.scope !== "sport" || o.sport === t.sport) && key(o) > 0);
      if (!pool.some(o => o.id === t.id) || pool.length < 2) return slNote(b, "In diesem Jahr gibt es noch keine weitere Tour zum Vergleichen.");
      const v = pool.map(key).sort((x, y) => y - x), rank = 1 + v.filter(x => x > key(t)).length, shown = v.slice(0, 60),
        label = `Säulendiagramm: alle Touren ${t.y} nach ${what}, diese Tour liegt auf Platz ${rank}`;
      b.innerHTML = `<p class="slcmp">Platz ${rank} von ${pool.length}</p><p class="mut slcmpn">Touren im Jahr ${t.y}${cfg.scope === "sport" ? ` (${esc(sName(t.sport))})` : ""}, sortiert nach ${what}</p>` +
        slCols(shown, {hl: rank <= 60 ? rank - 1 : -1, dim: [], label, cls: "slsm"}) +
        `<p class="mut slcap">${rank === 1 ? "Das ist die Spitze des Jahres." : `Die Spitze liegt bei ${{km: fmtKm, up: slHm, dur: x => fmtDauer(x * 3600, {summe: true})}[cfg.metric || "km"](v[0])}.`}</p>`;
      slBadge(c, `Platz <b>${rank}</b> von ${pool.length}`);
    },
  },
  tageslicht: {
    fam: "tour", cat: "grafik", icon: "cloud", name: "Tageslicht", title: () => "Tageslicht",
    desc: "Sonnenaufgang und -untergang am Tag der Tour (aus Datum und Ort gerechnet) und wann du im Hellen unterwegs warst.",
    preview: () => slPrev('<svg viewBox="0 0 120 30" class="slpvs" aria-hidden="true"><rect class="slnight" x="0" y="0" width="120" height="14"/><rect class="sldawn" x="22" y="0" width="76" height="14"/><rect class="slday" x="30" y="0" width="60" height="14"/><rect class="sltour" x="46" y="20" width="26" height="7" rx="3"/></svg>'),
    async render(c, b, cfg, {t}) {
      const d = t && (await slGet(`/api/bausteine/tageslicht?tour=${slEnc(t.id)}`));
      if (!d || d.status !== "ok")
        return slNote(b, d && d.status === "polar" ? "An diesem Ort geht die Sonne an diesem Tag nicht auf oder nicht unter." : d && d.status === "keine_position" ? "Für diese Tour ist keine Position bekannt." : "Für diese Tour liegt keine Zeit vor.");
      const X = m => (slClamp(m, 0, 1440)).toFixed(1), W = (a, e) => Math.max(0, slClamp(e, 0, 1440) - slClamp(a, 0, 1440)).toFixed(1),
        tour = d.ende_min != null ? `<rect class="sltour" x="${X(d.start_min)}" y="30" width="${Math.max(6, W(d.start_min, d.ende_min))}" height="12" rx="3"/>` : "",
        label = `Tageslicht: Sonnenaufgang ${slClock(d.aufgang_min)}, Sonnenuntergang ${slClock(d.untergang_min)}, Tour ab ${slClock(d.start_min)}`;
      b.innerHTML = `<svg class="slstrip slday-s" viewBox="0 0 1440 44" preserveAspectRatio="none" role="img" aria-label="${esc(label)}"><rect class="slnight" x="0" y="0" width="1440" height="24"/>` +
        (d.daemm_von_min != null ? `<rect class="sldawn" x="${X(d.daemm_von_min)}" y="0" width="${W(d.daemm_von_min, d.daemm_bis_min)}" height="24"/>` : "") +
        `<rect class="slday" x="${X(d.aufgang_min)}" y="0" width="${W(d.aufgang_min, d.untergang_min)}" height="24"/>${tour}</svg>` +
        `<div class="slxl sb" aria-hidden="true"><span>0</span><span>6</span><span>12</span><span>18</span><span>24</span></div>` +
        `<ul class="sllg"><li><i class="slsq slnight"></i>Nacht</li><li><i class="slsq sldawn"></i>Dämmerung</li><li><i class="slsq slday"></i>Tag</li><li><i class="slsq sltour"></i>Tour</li></ul>` +
        slTiles([[slClock(d.aufgang_min), "Sonnenaufgang"], [slClock(d.untergang_min), "Sonnenuntergang"], [fmtDauer(d.tag_min * 60, {summe: true}), "Tageslänge"], d.hell_min != null ? [fmtDauer(d.hell_min * 60, {summe: true}), "Im Hellen unterwegs", d.dunkel_min > 0 ? `${fmtDauer(d.dunkel_min * 60, {summe: true})} im Dunkeln` : "ganze Tour bei Tageslicht"] : null].filter(Boolean));
      slPos(b);
      slBadge(c, `${slClock(d.aufgang_min)}–${slClock(d.untergang_min)}`);
    },
  },
  gipfel: {
    fam: "tour", cat: "zahlen", icon: "pin", name: "Höchster Punkt", title: () => "Höchster Punkt", defaults: {ab: "500"},
    desc: "Der höchste Punkt der Tour als Wegweiser-Tafel, wann du ihn erreicht hast und wie viel der Strecke über einer wählbaren Höhe lag.",
    fields: [{k: "ab", kind: "radio", label: "Anteil der Strecke über", options: [["500", "500 m"], ["1000", "1.000 m"], ["1500", "1.500 m"], ["2000", "2.000 m"]]}],
    preview: () => slPrev('<div class="slsign slsign-pv"><span>Höchster Punkt</span><b>1.234 m</b></div>'),
    async render(c, b, cfg, {t}) {
      const ab = +cfg.ab || 500, d = t && (await slGet(`/api/bausteine/gipfel?tour=${slEnc(t.id)}&ab=${ab}`));
      if (!d || d.status !== "ok") return slWhy(b, d);
      const tiles = [d.nach_s != null ? [fmtDauer(d.nach_s, {summe: true}), "Erreicht nach"] : null, d.bei_m != null ? [fmtKm(d.bei_m / 1000), "Bei Kilometer"] : null, [slHm(d.tief_m), "Tiefster Punkt"], [slHm(d.hoch_m - d.tief_m), "Höhenunterschied"]].filter(Boolean),
        sh = d.ueber_anteil != null ? Math.round(d.ueber_anteil * 100) : null;
      b.innerHTML = `<div class="slsign"><span>Höchster Punkt</span><b>${slHm(d.hoch_m)}</b></div>${slTiles(tiles)}` +
        (sh != null ? `<div class="slr1"><span>Anteil der Strecke über ${fmtHm(ab)}</span><b>${sh} %</b></div>${slBr(sh, "slc5")}` : "");
      slBadge(c, slHm(d.hoch_m));
    },
  },
  vergleiche: {
    fam: "tour", cat: "spass", icon: "dot", name: "Spaß-Vergleiche", title: () => "Spaß-Vergleiche", multi: true, defaults: {hoehe: "dom", weg: "fussball", kcal: "schnitzel"},
    desc: "Aufstieg, Strecke und Kalorien in Bezugsgrößen: „1,2 × Kölner Dom“, „2 × Schnitzel“. Die Bezugsgrößen wählst du selbst.",
    fields: [
      {k: "hoehe", kind: "radio", label: "Aufstieg vergleichen mit", options: SL_FUN.hoehe.map(x => [x[0], x[1]])},
      {k: "weg", kind: "radio", label: "Strecke vergleichen mit", options: SL_FUN.weg.map(x => [x[0], x[1]])},
      {k: "kcal", kind: "radio", label: "Kalorien vergleichen mit", options: SL_FUN.kcal.map(x => [x[0], x[1]])},
    ],
    preview: () => slPrev('<ul class="slfun"><li><span class="slem">⛰️</span><b>1,2 ×</b> Kölner Dom</li><li><span class="slem">🍽️</span><b>2 ×</b> Schnitzel</li></ul>'),
    async render(c, b, cfg, {t}) {
      if (!t) return slNote(b, "Keine Tour.");
      const pick = (L, k) => L.find(x => x[0] === k) || L[0], H = pick(SL_FUN.hoehe, cfg.hoehe), G = pick(SL_FUN.weg, cfg.weg), K = pick(SL_FUN.kcal, cfg.kcal),
        u = await slGet(`/api/tours/${slEnc(t.id)}/uhr-training`), kc = u && u.werte && u.werte.kcal && u.werte.kcal.wert,
        row = (em, n, name, sub) => `<li><span class="slem" aria-hidden="true">${em}</span><div><p class="slfn"><b>${slFmtN(n)} ×</b> ${name}</p><p class="mut slfs2">${sub}</p></div></li>`,
        rows = [];
      if (t.up_m > 0) rows.push(row("⛰️", t.up_m / H[2], H[1], `Aufstieg ${slHm(t.up_m)} geteilt durch ${slHm(H[2])}`));
      if (t.km > 0) rows.push(row("👟", (t.km * 1000) / G[2], G[1], `Strecke ${fmtKm(t.km)} geteilt durch ${G[2] >= 1000 ? fmtKm(G[2] / 1000) : slHm(G[2])}`));
      rows.push(kc ? row("🍽️", kc / K[2], K[1], `Kalorien ${nf(kc, 0)} kcal geteilt durch ${nf(K[2], 0)} kcal`) : `<li><span class="slem" aria-hidden="true">🍽️</span><p class="mut slfs2">Kalorien wurden bei dieser Tour nicht aufgezeichnet.</p></li>`);
      b.innerHTML = `<ul class="slfun">${rows.join("")}</ul>`;
      if (t.up_m > 0) slBadge(c, `${slFmtN(t.up_m / H[2])} × ${H[1]}`);
    },
  },
  stimmung: {
    fam: "tour", cat: "spass", icon: "cloud", name: "Wetter und Tageszeit", title: () => "Wetter und Tageszeit",
    desc: "Die Stimmung der Tour in Symbolen: Tageszeit, Himmel, Temperatur, Wind und Regen.",
    preview: () => slPrev('<ul class="slmood"><li><span class="slem">🌅</span>Morgen</li><li><span class="slem">⛅</span>Wolkig</li><li><span class="slem">🧥</span>Kühl</li></ul>'),
    async render(c, b, cfg, {t}) {
      if (!t) return slNote(b, "Keine Tour.");
      const h = +t.date.slice(11, 13), w = await slGet(`/api/tours/${slEnc(t.id)}/weather`),
        part = h < 5 ? ["🌙", "Nacht"] : h < 9 ? ["🌅", "Morgen"] : h < 12 ? ["🌤️", "Vormittag"] : h < 14 ? ["☀️", "Mittag"] : h < 17 ? ["🌞", "Nachmittag"] : h < 21 ? ["🌇", "Abend"] : ["🌙", "Nacht"],
        chips = [[part[0], part[1], `${pad2(h)}:${t.date.slice(14, 16)} Uhr`]];
      if (w && w.tmin != null) {
        const cd = w.code, sky = cd === 0 ? "☀️" : cd === 1 ? "🌤️" : cd === 2 ? "⛅" : cd === 3 ? "☁️" : cd === 45 || cd === 48 ? "🌫️" : cd >= 95 ? "⛈️" : cd >= 71 && cd <= 77 || cd === 85 || cd === 86 ? "❄️" : cd >= 61 && cd <= 67 || cd >= 80 && cd <= 82 ? "🌧️" : cd >= 51 ? "🌦️" : "🌡️",
          tm = w.tmax, feel = tm < 2 ? ["🥶", "Frostig"] : tm < 12 ? ["🧥", "Kühl"] : tm < 20 ? ["🙂", "Mild"] : tm < 27 ? ["😎", "Warm"] : ["🥵", "Heiß"],
          wind = w.wind < 15 ? ["🍃", "Kaum Wind"] : w.wind < 30 ? ["💨", "Frischer Wind"] : ["🌬️", "Stürmisch"];
        chips.push([sky, esc(w.text || "–"), ""], [feel[0], feel[1], `${nf(w.tmin, 0)}–${nf(w.tmax, 0)} °C`], [wind[0], wind[1], `bis ${fmtTempo(w.wind, {d: 0})}`]);
        if (w.precip >= 1) chips.push(["☔", "Regen", nf(w.precip, 1) + " mm"]);
      }
      b.innerHTML = `<ul class="slmood">${chips.map(([e, l, s]) => `<li><span class="slem" aria-hidden="true">${e}</span><b>${l}</b>${s ? `<small class="mut">${s}</small>` : ""}</li>`).join("")}</ul>` + (w && w.tmin != null ? "" : '<p class="mut slcap">Für diese Tour liegen keine Wetterdaten vor.</p>');
      slBadge(c, part[1]);
    },
  },
  fotohighlights: {
    fam: "tour", cat: "grafik", icon: "cam", name: "Foto-Highlights", title: () => "Foto-Highlights",
    desc: "Die drei besten Fotos der Tour groß, ausgewählt nach deiner Bewertung und der Schärfe.",
    preview: () => slPrev('<div class="slpvf" aria-hidden="true"><i class="big"></i><i></i><i></i></div>'),
    async render(c, b, cfg, {t}) {
      const r = t && t.photos ? await slGet(`/api/tours/${slEnc(t.id)}/best-photos?n=3`) : null,
        l = ((r && r.photos) || []).map(p => ({...p, tour_name: t.name}));
      slPhotos(c, b, l, "Foto der Tour", "slfh");
      if (l.length) {
        b.insertAdjacentHTML("beforeend", '<p class="mut slcap">Ausgewählt nach Bewertung und Schärfe.</p>');
        slBadge(c, l.length === 1 ? "1 Foto" : `${l.length} Fotos`);
      }
    },
  },
  miniprofil: {
    fam: "tour", cat: "grafik", icon: "prof", name: "Höhenprofil nach Steigung", title: () => "Höhenprofil nach Steigung",
    desc: "Das Höhenprofil kompakt, die Linie nach Steigung eingefärbt: bergab, eben, bergauf.",
    preview: () => slPvLine([32, 26, 14, 8, 16, 12, 24, 30]),
    async render(c, b, cfg, {t}) {
      const d = t && (await slGet(`/api/bausteine/profil?tour=${slEnc(t.id)}`));
      if (!d || d.status !== "ok" || d.h.length < 2) return slWhy(b, d);
      const lo = Math.min(...d.h), hi = Math.max(...d.h), dm = d.d[d.d.length - 1] || 1,
        X = i => ((d.d[i] / dm) * 600).toFixed(1), Y = i => (hi === lo ? 60 : 112 - ((d.h[i] - lo) / (hi - lo)) * 96).toFixed(1),
        cls = i => {
          const p = ((d.h[i + 1] - d.h[i]) / Math.max(1, d.d[i + 1] - d.d[i])) * 100;
          return p < -15 ? 0 : p < -5 ? 1 : p < -2 ? 2 : p < 2 ? 3 : p < 5 ? 4 : p < 15 ? 5 : 6;
        },
        line = d.h.slice(1).map((_, i) => `<path class="slpl slcl${cls(i)}" d="M${X(i)} ${Y(i)}L${X(i + 1)} ${Y(i + 1)}"/>`).join(""),
        area = `M0 120${d.h.map((_, i) => `L${X(i)} ${Y(i)}`).join("")}L600 120Z`,
        label = `Höhenprofil, tiefster Punkt ${slHm(lo)}, höchster Punkt ${slHm(hi)}, Strecke ${fmtKm(dm / 1000)}`;
      b.innerHTML = `<svg class="slprof" viewBox="0 0 600 120" preserveAspectRatio="none" role="img" aria-label="${esc(label)}"><path class="slpa" d="${area}"/>${line}</svg>` +
        `<div class="slxl sb" aria-hidden="true"><span>0 km</span><span>${slHm(lo)} bis ${slHm(hi)}</span><span>${fmtKm(dm / 1000)}</span></div>` +
        `<ul class="sllg"><li><i class="slsq slc1"></i>bergab</li><li><i class="slsq slc3"></i>eben</li><li><i class="slsq slc5"></i>bergauf</li></ul>`;
      slBadge(c, `${slHm(lo)} bis ${slHm(hi)}`);
    },
  },
  steckbrief: {
    fam: "tour", cat: "zahlen", icon: "map", name: "Strecken-Steckbrief", title: () => "Strecken-Steckbrief",
    desc: "Wie oft du diese Strecke gegangen bist, das erste und das letzte Mal, das beste Tempo und eine Zeitleiste der Wiederholungen.",
    preview: () => slPvTiles([["5 ×", "Auf dieser Strecke"], ["12.03.2024", "Erstes Mal"], ["4,8 km/h", "Bestes Tempo"]]),
    async render(c, b, cfg, {t}) {
      const d = t && (await slGet(`/api/tours/${slEnc(t.id)}/aehnliche`));
      if (!d || d.status !== "ok" || !d.touren || d.touren.length < 2) return slNote(b, "Diese Strecke hast du bisher nur einmal aufgezeichnet.");
      const R = d.touren.slice().sort((x, y) => x.start_ts - y.start_ts), f = R[0], l = R[R.length - 1], best = R.find(r => r.id === d.bestes_id),
        span = Math.max(1, l.start_ts - f.start_ts),
        dots = R.map(r => `<span class="sltd${r.aktuell ? " cur" : ""}" data-l="${(((r.start_ts - f.start_ts) / span) * 100).toFixed(1)}"></span>`).join(""),
        label = `Zeitleiste: ${R.length} Wiederholungen von ${fmtDatumKurz(f.datum)} bis ${fmtDatumKurz(l.datum)}`;
      b.innerHTML = slTiles([[`${R.length} ×`, "Auf dieser Strecke"], [fmtDatumKurz(f.datum), "Erstes Mal", f.aktuell ? "diese Tour" : ""], [fmtDatumKurz(l.datum), "Letztes Mal", l.aktuell ? "diese Tour" : ""],
        best ? [fmtTempo(best.tempo_kmh), "Bestes Tempo", best.aktuell ? "diese Tour" : fmtDatumKurz(best.datum)] : null].filter(Boolean)) +
        `<div class="sltl" role="img" aria-label="${esc(label)}"><span class="sltl-l"></span>${dots}</div><div class="slxl sb" aria-hidden="true"><span>${f.datum.slice(0, 4)}</span><span>${l.datum.slice(0, 4)}</span></div>`;
      slPos(b);
      slBadge(c, `${R.length} ×`);
    },
  },
});

/* =====================  3.39.0 Plan und Ergebnis (Soll/Ist) an der Tourseite  =====================
   Hat eine gelaufene Tour eine verknüpfte Planung (plans.tour_id, 3.38.0), steht an der Tourseite die Karte „Plan und Ergebnis“: Kennzahlen Soll/Ist mit Unterschied (Text UND Symbol), die geplante Linie
   (gestrichelt) über der gelaufenen (durchgezogen) und der Link zum Plan. Daten: GET /api/tours/<id>/plan (nur lesend, höchstens 400 Punkte je Linie). Ohne Verknüpfung gibt es nichts zu sehen:
   als Standard-Abschnitt („planist“, SL_REG.tour) wird die Karte gar nicht erst gebaut (when), als eigenständiger Baustein aus dem Katalog bleibt sie unsichtbar (data-hn = aus). */
const PLAN_OF = {};                                                                                  // Tour-Kennung → Antwort des Servers (nur mit Verknüpfung)
const planErgHas = () => {
  const r = typeof tlRoot === "function" ? tlRoot() : null;
  return !!(r && PLAN_OF[r.dataset.tid]);
};
async function planErgData(id, fresh) {
  if (!fresh && PLAN_OF[id]) return PLAN_OF[id];
  const d = await slGet(`/api/tours/${slEnc(id)}/plan`);
  if (d && d.status === "ok") PLAN_OF[id] = d;
  else {
    delete PLAN_OF[id];
    const r = await slGet(`/api/tours/${slEnc(id)}/rueckblick`).catch(() => null);          // 3.48.0: ohne Plan „Wie ist es gelaufen?“ (nur mit genug Vergleichstouren, sonst gibt es den Abschnitt nicht)
    if (r && r.status === "ok") PLAN_OF[id] = {...r, modus: "rueckblick"};
  }
  return PLAN_OF[id] || null;
}
const planErgModus = () => {
  const r = typeof tlRoot === "function" ? tlRoot() : null, d = r && PLAN_OF[r.dataset.tid];
  return d && d.modus === "rueckblick" ? "rueckblick" : "plan";
};
/* 3.48.0 Rückblick „Wie ist es gelaufen?“ (ohne Plan): Dauer, Strecke, Aufstieg und Tempo gegenüber den eigenen Touren derselben Sportart der letzten 12 Monate und den ähnlichen Touren
   (Median-Verhältnis, Schwellen 80 %/125 %, Server: app/tourrueckblick.py). Mit verknüpftem Plan gilt allein Plan und Ergebnis. */
const RB_ROWS = [["dauer", "Dauer"], ["strecke", "Strecke"], ["auf", "Aufstieg"], ["tempo", "Tempo"]];
const RB_WORD = {
  dauer: {unter: "kürzer als üblich", aehnlich: "ähnlich lang wie üblich", ueber: "länger als üblich"},
  strecke: {unter: "kürzer als üblich", aehnlich: "ähnlich lang wie üblich", ueber: "länger als üblich"},
  auf: {unter: "weniger Aufstieg als üblich", aehnlich: "ähnlich viel Aufstieg wie üblich", ueber: "mehr Aufstieg als üblich"},
  tempo: {unter: "langsamer als üblich", aehnlich: "ähnlich schnell wie üblich", ueber: "schneller als üblich"},
};
const RB_SYM = {unter: "↓", aehnlich: "=", ueber: "↑"};
const rbVal = (k, v) => (k === "dauer" ? fmtDauer(v * 3600) : k === "strecke" ? slKm(v) : k === "auf" ? slHm(v) : fmtTempo(v));
function rbBlock(blk, head) {
  const rows = RB_ROWS.filter(([k]) => blk.kennzahlen[k]);
  return `<h3 class="rbh">${head}</h3><ul class="plrows">${rows.map(([k, lab]) => {
    const m = blk.kennzahlen[k];
    return `<li class="plrow"><span class="pll">${lab}</span><span class="plv"><small class="mut">Diese Tour</small> ${rbVal(k, m.wert)}</span><span class="plv"><small class="mut">Üblich (Median)</small> ${rbVal(k, m.median)}</span>` +
      `<span class="pld"><span aria-hidden="true">${RB_SYM[m.einordnung]}</span> <b>${RB_WORD[k][m.einordnung]}</b></span></li>`;
  }).join("")}</ul>`;
}
function rbPaint(c, b, d) {
  const parts = [];
  if (d.eigene) parts.push(rbBlock(d.eigene, d.eigene.n === 1 ? "Gegenüber deiner Tour dieser Sportart in den 12 Monaten davor" : `Gegenüber deinen ${d.eigene.n} Touren dieser Sportart in den 12 Monaten davor`));
  if (d.aehnliche) parts.push(rbBlock(d.aehnliche, `Gegenüber ${d.aehnliche.n} ähnlichen Touren auf dieser Strecke`));
  const bs = d.besuch ? `<p class="rbv"><b>Dein ${d.besuch.nr}. Besuch dieser Strecke</b> <span class="mut">(${d.besuch.von} Läufe insgesamt)</span></p>` : "";
  b.innerHTML = `<div role="group" aria-label="Wie ist es gelaufen?">${bs}${parts.join("")}<p class="mut slcap">Üblich = Median der Vergleichstouren. Unter 80 % davon gilt als kürzer, weniger oder langsamer, über 125 % als länger, mehr oder schneller. Tempo = Strecke geteilt durch die gesamte Dauer.</p></div>`;
  const first = RB_ROWS.map(([k]) => [k, (d.eigene && d.eigene.kennzahlen[k]) || (d.aehnliche && d.aehnliche.kennzahlen[k])]).find(([, m]) => m);
  slBadge(c, d.besuch ? `${d.besuch.nr}. Besuch` : first ? RB_WORD[first[0]][first[1].einordnung] : "");
}
/* Unterschied Ist − Soll: Pfeil, Zahl mit Vorzeichen und Wort („länger als geplant“); innerhalb der Toleranz „wie geplant“ (=). Fehlt ein Wert, steht „ohne Angabe“ (nie 0). */
const PLAN_TOL = {km: 0.05, up: 1, down: 1, h: 1 / 60};
const PLAN_WORDS = {km: ["länger als geplant", "kürzer als geplant"], up: ["mehr Aufstieg als geplant", "weniger Aufstieg als geplant"], down: ["mehr Abstieg als geplant", "weniger Abstieg als geplant"], h: ["länger als geplant", "kürzer als geplant"]};
function planErgDiff(k, v) {
  if (v == null) return '<span class="pld mut"><span>ohne Angabe</span></span>';
  if (Math.abs(v) < PLAN_TOL[k]) return '<span class="pld"><span aria-hidden="true">=</span> <span>wie geplant</span></span>';
  const num = k === "km" ? `${nSigned(v, 1)} km` : k === "up" || k === "down" ? `${nSigned(v, 0)} m` : null;
  return `<span class="pld"><span aria-hidden="true">${v > 0 ? "↑" : "↓"}</span> ` +
    (num ? `<b>${num}</b>` : `<b>${v < 0 ? "−" : "+"}${fmtDauer(Math.abs(v) * 3600)}</b>`) + ` <small class="mut">${PLAN_WORDS[k][v > 0 ? 0 : 1]}</small></span>`;
}
const planErgVal = (k, v) => (v == null ? '<span class="mut">ohne Angabe</span>' : k === "km" ? slKm(v) : k === "up" || k === "down" ? slHm(v) : fmtDauer(v * 3600));
/* Ersatz ohne Leaflet (z. B. Vorschau): Linien übereinander als SVG, gleichmäßige Abbildung (Längengrad mit cos(Breite) gestreckt), Strichbreite bleibt beim Skalieren gleich */
function planErgSvg(d) {
  const A = (d.plan_linie || []).filter(p => p.length >= 2), B = (d.tour_linie || []).filter(p => p.length >= 2), all = A.concat(B);
  if (all.length < 2) return "";
  const la = all.map(p => p[0]), lo = all.map(p => p[1]), k = Math.cos((((Math.min(...la) + Math.max(...la)) / 2) * Math.PI) / 180),
    x0 = Math.min(...lo) * k, y1 = Math.max(...la), w0 = Math.max(1e-6, (Math.max(...lo) - Math.min(...lo)) * k), h0 = Math.max(1e-6, y1 - Math.min(...la)),
    W = 600, H = Math.round(Math.max(120, Math.min(420, (W * h0) / w0))), sc = Math.min((W - 24) / w0, (H - 24) / h0), ox = (W - w0 * sc) / 2, oy = (H - h0 * sc) / 2,
    pts = L => L.map(p => `${(ox + (p[1] * k - x0) * sc).toFixed(1)},${(oy + (y1 - p[0]) * sc).toFixed(1)}`).join(" ");
  return `<svg class="plmap" viewBox="0 0 ${W} ${H}" aria-hidden="true" focusable="false">` +
    (B.length ? `<polyline class="plis peis" fill="none" points="${pts(B)}" vector-effect="non-scaling-stroke"/>` : "") +
    (A.length ? `<polyline class="plpl pepl" fill="none" points="${pts(A)}" vector-effect="non-scaling-stroke"/>` : "") + "</svg>";
}
/* 3.55.0: Geplant und Gelaufen als zwei klar beschriftete Spalten (mobil untereinander) in eigener Farbe – Plan Indigo gestrichelt, gelaufen in der Sportfarbe durchgezogen, wie in Karte und Legende.
   Die Abweichung steht unter dem gelaufenen Wert; in der Planspalte steht dieselbe Zeile unsichtbar (pe0), damit beide Spalten gleich hohe Zeilen haben. */
const PLAN_KEYS = [["km", "Strecke"], ["up", "Aufstieg"], ["down", "Abstieg"], ["h", "Dauer"]];
const peSw = side => `<svg class="pesw" viewBox="0 0 28 10" aria-hidden="true" focusable="false"><line class="pesw-${side}" x1="2" y1="5" x2="26" y2="5"/></svg>`;
const peSport = s => ((typeof SPORT === "object" && SPORT[typeof sNorm === "function" ? sNorm(s) : s]) || [0, "--other"])[1].slice(2);
function planErgCol(side, d, t, can) {
  const plan = side === "pl", S = plan ? d.soll : d.ist, nm = esc((plan ? d.plan.name : t && t.name) || "Ohne Namen"), dt = plan ? d.plan.ts : t && t.date,
    name = plan && can ? `<a href="#/plan/${d.plan.id}">${nm}</a>` : nm;
  return `<section class="pecol pe-${plan ? "plan" : "ist"}" aria-label="${plan ? "Geplant" : "Gelaufen"}"><h4 class="peh"><span class="petag">${peSw(side)}<span>${plan ? "Geplant" : "Gelaufen"}</span></span></h4>` +
    `<p class="pename${plan ? " plname" : ""}">${name}</p>${dt ? `<p class="pedt mut">${plan ? "Geplant" : "Gelaufen"} am ${fmtDatumKurz(dt)}</p>` : ""}` +
    `<dl class="pefig">${PLAN_KEYS.map(([k, lab]) => `<div class="pek pek-${k}"><dt>${lab}</dt><dd><b class="pev">${planErgVal(k, S[k])}</b>` +
      (plan ? `<span class="pe0" aria-hidden="true">${planErgDiff(k, d.diff[k])}</span>` : planErgDiff(k, d.diff[k])) + "</dd></div>").join("")}</dl></section>`;
}
/* Karte mit beiden Strecken: dieselben Bausteine wie die Tourkarte (mkMap: Kacheln über den Zwischenspeicher des Servers, offline aus dem Service Worker; Start/Ziel wie dort).
   Plan gestrichelt über der gelaufenen Linie, beide mit weißem Rand; die Ansicht passt auf beide Strecken und wird nach jeder Größenänderung neu eingepasst, bis jemand selbst verschiebt oder zoomt. */
function planErgMap(b, d) {
  const el = b.querySelector(".pemap");
  if (b._plm) {
    try { b._plm.remove(); } catch (e) {}
    b._plm = null;
  }
  if (b._plro) b._plro.disconnect();
  if (!el) return;
  const A = cleanPts(d.plan_linie).map(p => [p[0], p[1]]), B = cleanPts(d.tour_linie).map(p => [p[0], p[1]]);
  if (A.length < 2 && B.length < 2) return el.remove();
  if (typeof L === "undefined" || typeof mkMap !== "function") return (el.innerHTML = planErgSvg(d));
  const m = (b._plm = mkMap(el, {layers: false, leaflet: {scrollWheelZoom: false, zoomSnap: 0.25, dragging: !document.documentElement.classList.contains("mob")}})),
    cs = getComputedStyle(el), cPl = cs.getPropertyValue("--pe-plan").trim() || "#5c6bdc", cIs = cs.getPropertyValue("--pe-ist").trim() || "#2f8f5f",
    line = (P, o) => L.polyline(P, {interactive: false, ...o}).addTo(m);
  if (B.length > 1) {
    line(B, {color: "#fff", weight: 9, opacity: 0.85, className: "pecase"});
    line(B, {color: cIs, weight: 5, opacity: 0.95, className: "peis"});
  }
  if (A.length > 1) {
    line(A, {color: "#fff", weight: 7, opacity: 0.8, className: "pecase"});
    line(A, {color: cPl, weight: 4, opacity: 1, dashArray: "9 8", lineCap: "butt", className: "pepl"});
  }
  const E = B.length > 1 ? B : A;
  L.circleMarker(E[0], {radius: 7, color: "#fff", fillColor: "#2f8f5f", fillOpacity: 1, weight: 2, className: "pestart"}).addTo(m).bindTooltip("Start");
  L.circleMarker(E[E.length - 1], {radius: 7, color: "#fff", fillColor: "#c0504d", fillOpacity: 1, weight: 2, className: "peziel"}).addTo(m).bindTooltip("Ziel");
  const bb = L.latLngBounds(A.concat(B)), fit = () => m.fitBounds(bb, {padding: [24, 24]});
  let user = false, w0 = el.clientWidth;
  ["pointerdown", "wheel", "keydown"].forEach(ev => el.addEventListener(ev, () => (user = true), {passive: true}));
  if (w0) fit();
  else m.setView(bb.getCenter(), 13);
  m._peFit = fit;
  if (typeof ResizeObserver === "function") {
    b._plro = new ResizeObserver(() => {
      const w = el.clientWidth;
      if (!w || w === w0) return;
      w0 = w;
      m.invalidateSize();
      if (!user) fit();
    });
    b._plro.observe(el);
  }
}
function planErgPaint(c, b, d, t) {
  const can = typeof isViewer === "function" ? !isViewer() : true, D = d.diff, hasLine = (d.plan_linie || []).length > 1 || (d.tour_linie || []).length > 1;
  b.innerHTML = `<div class="pewrap pe-s-${peSport((t && t.sport) || d.plan.sport)}" role="group" aria-label="Planung und Ergebnis im Vergleich">` +
    `<div class="pecols">${planErgCol("pl", d, t, can)}${planErgCol("is", d, t, can)}</div>` +
    (hasLine ? `<div class="pemap" role="region" aria-label="Karte: geplante Linie gestrichelt, gelaufene Linie durchgezogen"></div>` : "") +
    `<ul class="plleg peleg"><li>${peSw("pl")}<span>Geplant (gestrichelt)</span></li><li>${peSw("is")}<span>Gelaufen (durchgezogen)</span></li>` +
    (hasLine ? `<li><i class="pedot pedot-s" aria-hidden="true"></i><span>Start</span></li><li><i class="pedot pedot-z" aria-hidden="true"></i><span>Ziel</span></li>` : "") + "</ul>" +
    `<p class="mut slcap">Dauer: einschließlich Pausen; geplante Dauer nach deinem persönlichen Tempo.</p>` +
    (can ? `<div class="plact pebtns"><a class="btn alt sm" data-a="plan" href="#/plan/${d.plan.id}">Zur Planung ›</a><button type="button" class="btn alt sm" data-a="unlink">Verknüpfung lösen</button></div>` : "") + "</div>";
  planErgMap(b, d);
  const first = [["km", D.km], ["h", D.h]].find(([, v]) => v != null);
  slBadge(c, !first ? "" : Math.abs(first[1]) < PLAN_TOL[first[0]] ? "wie geplant" : `${first[1] > 0 ? "↑" : "↓"} ${first[0] === "km" ? nSigned(first[1], 1) + " km" : (first[1] < 0 ? "−" : "+") + fmtDauer(Math.abs(first[1]) * 3600)}`);
  const ub = b.querySelector('[data-a="unlink"]');
  if (ub)
    ub.onclick = async () => {
      if (!(await uiConfirm({title: "Verknüpfung lösen?", text: `Die geplante Tour „${d.plan.name || "Ohne Namen"}“ bleibt erhalten, ist aber nicht mehr mit dieser Tour verknüpft und steht wieder als „geplant“ in deiner Planliste.`, ok: "Verknüpfung lösen", cancel: "Abbrechen"}))) return;
      ub.disabled = true;
      try {
        await api(`/api/plans/${d.plan.id}/tour`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({tour_id: null})});
      } catch (e) {
        ub.disabled = false;
        uiAlert(e.message || e);
        return;
      }
      delete PLAN_OF[t.id];
      planErgMap(b, {});
      c.dataset.hn = "aus";
      slNote(b, "Zu dieser Tour gibt es keine verknüpfte Planung. Der Baustein erscheint nur bei Touren mit verknüpfter Planung.");
      slBadge(c, "");
      if (typeof tlRefresh === "function") tlRefresh();
      planErgLoad(t).catch(() => {});                                                               // ohne Plan: gegebenenfalls „Wie ist es gelaufen?“
    };
}
/* Nach dem Öffnen der Tourseite (und der Unterseite) nachsehen, ob es eine Verknüpfung gibt; erst dann wird die Karte gebaut und eingeordnet */
function planErgLoad(t) {
  if (!t) return Promise.resolve();
  delete PLAN_OF[t.id];
  return planErgData(t.id, true).then(d => {
    const r = typeof tlRoot === "function" ? tlRoot() : null;
    if (d && r && r.dataset.tid === String(t.id) && typeof tlRefresh === "function") tlRefresh();
  });
}

Object.assign(window.SL_WT, {
  planergebnis: {
    fam: "tour", cat: "plan", icon: "map", name: "Planung und Ergebnis", title: () => (planErgModus() === "rueckblick" ? "Wie ist es gelaufen?" : "Planung und Ergebnis"), defaults: {},
    desc: "Wie die Tour im Vergleich zur verknüpften Planung ausgefallen ist: Geplant und Gelaufen nebeneinander mit Strecke, Aufstieg, Abstieg und Dauer samt Abweichung, beide Strecken übereinander auf der Karte (geplant gestrichelt), Link zum Plan. Ohne Plan zeigt der Baustein „Wie ist es gelaufen?“: Dauer, Strecke, Aufstieg und Tempo gegenüber deinen Touren derselben Sportart der letzten 12 Monate und den ähnlichen Touren (ab 5 Vergleichstouren). Erscheint nur bei Touren, die mit einem Plan verknüpft sind.",
    preview: () => slPrev('<svg viewBox="0 0 120 40" class="slpvs" aria-hidden="true"><polyline class="plpl" fill="none" points="6,32 30,12 56,26 84,8 112,20"/><polyline class="plis" fill="none" points="6,34 32,16 58,30 86,12 112,24"/></svg><p class="slcmp">Plan 12,0 km · Ergebnis 12,6 km (↑ +0,6 km)</p>'),
    async render(c, b, cfg, {t}) {
      c.dataset.hn = "lade";                                                                          // unsichtbar, bis feststeht, dass es eine Verknüpfung gibt
      const d = t && (await planErgData(t.id));
      if (!d) {
        c.dataset.hn = "aus";
        planErgMap(b, {});
        return slNote(b, "Zu dieser Tour gibt es weder eine verknüpfte Planung noch genug Vergleichstouren (mindestens 5). Der Baustein erscheint nur bei Touren mit Planung oder genug Vergleichstouren.");
      }
      c.dataset.hn = "an";
      if (d.modus === "rueckblick") {
        planErgMap(b, {});                                                                            // eine frühere Karte (mit Plan) aufräumen
        return rbPaint(c, b, d);
      }
      planErgPaint(c, b, d, t);
    },
  },
});
/* Die Karte steht als Standard-Abschnitt auf der Tourseite (nur mit Verknüpfung, siehe SL_REG.tour „planist“) */
(() => {
  const w = f => f && (async (...a) => {
    const t = BY[a[0]],
      pr = t ? planErgLoad(t).catch(() => {}) : null;                      // Abfrage läuft parallel zum Aufbau der Seite; ist sie früher da, wird die Karte gleich beim ersten Einordnen gebaut
    await f(...a);
    await pr;
  });
  VIEWS.tour = w(VIEWS.tour);
  VIEWS.tourauswertung = w(VIEWS.tourauswertung);
})();
