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
        f = kmh => (pace ? `${slMin(3600 / kmh)} min/km` : `${nf(kmh, 1)} km/h`),
        every = Math.ceil(S.length / 9),
        labels = S.map((x, i) => (S.length <= 9 || (i + 1) % every === 0 || i === S.length - 1 ? nf(x.km, x.teil ? 1 : 0) : "")),
        label = `Säulendiagramm: Tempo je Abschnitt, von ${f(slow.kmh)} bis ${f(fast.kmh)}`;
      b.innerHTML = `<p class="mut slcap">${step === 1000 ? "Tempo je Kilometer (nur Bewegungszeit)" : `Tempo je ${nf(step / 1000, 0)} km (nur Bewegungszeit)`}</p>` +
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
      }).join("")}</ul><p class="mut slcap">Anteil an der Strecke von ${slKm(d.dist_m / 1000)}, Steigung über 50 m geglättet.</p>`;
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
        `<div class="slxl sb" aria-hidden="true"><span>0:00</span><span>${slDur(tot)}</span></div>` +
        slTiles([[slDur(d.bewegung_s), "In Bewegung", `${pct} %`], [d.pause_s >= 60 ? slDur(d.pause_s) : "keine", "Pause", d.pause_s >= 60 ? `${100 - pct} %` : ""]]) +
        (d.pause_s < 60 ? '<p class="mut slcap">Keine nennenswerten Pausen aufgezeichnet.</p>' : '<p class="mut slcap">Pause: Tempo unter 0,3 km/h.</p>');
      slBadge(c, `${pct} % in Bewegung`);
    },
  },
  durchschnitt: {
    fam: "tour", cat: "grafik", icon: "cmp", name: "Diese Tour und dein Durchschnitt", title: () => "Diese Tour und dein Durchschnitt", defaults: {values: ["km", "up", "pace"]},
    desc: "Strecke, Aufstieg, Tempo oder Dauer dieser Tour gegen den Median deiner Touren gleicher Sportart, als Balken mit Marke.",
    fields: [{k: "values", kind: "checks", label: "Angezeigte Werte", min: 1, options: [["km", "Strecke"], ["up", "Aufstieg"], ["pace", "Tempo"], ["dur", "Dauer"]]}],
    preview: () => slPrev('<svg viewBox="0 0 120 40" class="slpvs" aria-hidden="true"><rect class="slhb" x="0" y="4" width="84" height="8" rx="4"/><rect class="slmk" x="58" y="1" width="2" height="14"/><rect class="slhb" x="0" y="24" width="40" height="8" rx="4"/><rect class="slmk" x="58" y="21" width="2" height="14"/></svg>'),
    render(c, b, cfg, {t}) {
      if (!t) return slNote(b, "Keine Tour.");
      const others = TOURS.filter(o => o.id !== t.id && o.sport === t.sport && o.km > 0);
      if (others.length < 3) return slNote(b, "Für diesen Vergleich braucht es mindestens drei andere Touren derselben Sportart.");
      const pace = o => (o.h > 0.2 ? o.km / o.h : null),
        M = {
          km: ["Strecke", t.km, others.map(o => o.km), slKm], up: ["Aufstieg", t.up_m, others.map(o => o.up_m).filter(v => v != null), slHm],
          pace: ["Tempo", pace(t), others.map(pace).filter(v => v != null), v => nf(v, 1) + " km/h"], dur: ["Dauer", t.h > 0 ? t.h * 3600 : null, others.filter(o => o.h > 0).map(o => o.h * 3600), slDur],
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
      b.innerHTML = `<ul class="slrows">${rows.join("")}</ul><p class="mut slcap">Der senkrechte Strich zeigt den Median deiner ${others.length} anderen Touren (Sportart: ${esc(sName(t.sport))}).</p>`;
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
        `<p class="mut slcap">${rank === 1 ? "Das ist die Spitze des Jahres." : `Die Spitze liegt bei ${{km: slKm, up: slHm, dur: x => slDur(x * 3600)}[cfg.metric || "km"](v[0])}.`}</p>`;
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
        slTiles([[slClock(d.aufgang_min), "Sonnenaufgang"], [slClock(d.untergang_min), "Sonnenuntergang"], [slDur(d.tag_min * 60), "Tageslänge"], d.hell_min != null ? [slDur(d.hell_min * 60), "Im Hellen unterwegs", d.dunkel_min > 0 ? `${slDur(d.dunkel_min * 60)} im Dunkeln` : "ganze Tour bei Tageslicht"] : null].filter(Boolean));
      slPos(b);
      slBadge(c, `${slClock(d.aufgang_min)}–${slClock(d.untergang_min)}`);
    },
  },
  gipfel: {
    fam: "tour", cat: "zahlen", icon: "pin", name: "Gipfel-Tafel", title: () => "Gipfel-Tafel", defaults: {ab: "500"},
    desc: "Höchster Punkt der Tour als Wegweiser-Tafel, wann du ihn erreicht hast und wie viel der Strecke über einer wählbaren Höhe lag.",
    fields: [{k: "ab", kind: "radio", label: "Anteil der Strecke über", options: [["500", "500 m"], ["1000", "1.000 m"], ["1500", "1.500 m"], ["2000", "2.000 m"]]}],
    preview: () => slPrev('<div class="slsign slsign-pv"><span>Höchster Punkt</span><b>1.234 m</b></div>'),
    async render(c, b, cfg, {t}) {
      const ab = +cfg.ab || 500, d = t && (await slGet(`/api/bausteine/gipfel?tour=${slEnc(t.id)}&ab=${ab}`));
      if (!d || d.status !== "ok") return slWhy(b, d);
      const tiles = [d.nach_s != null ? [slDur(d.nach_s), "Erreicht nach"] : null, d.bei_m != null ? [slKm(d.bei_m / 1000), "Bei Kilometer"] : null, [slHm(d.tief_m), "Tiefster Punkt"], [slHm(d.hoch_m - d.tief_m), "Höhenunterschied"]].filter(Boolean),
        sh = d.ueber_anteil != null ? Math.round(d.ueber_anteil * 100) : null;
      b.innerHTML = `<div class="slsign"><span>Höchster Punkt</span><b>${slHm(d.hoch_m)}</b></div>${slTiles(tiles)}` +
        (sh != null ? `<div class="slr1"><span>Anteil der Strecke über ${nf(ab, 0)} m</span><b>${sh} %</b></div>${slBr(sh, "slc5")}` : "");
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
      if (t.km > 0) rows.push(row("👟", (t.km * 1000) / G[2], G[1], `Strecke ${slKm(t.km)} geteilt durch ${G[2] >= 1000 ? slKm(G[2] / 1000) : slHm(G[2])}`));
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
        chips.push([sky, esc(w.text || "–"), ""], [feel[0], feel[1], `${nf(w.tmin, 0)}–${nf(w.tmax, 0)} °C`], [wind[0], wind[1], `bis ${nf(w.wind, 0)} km/h`]);
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
    fam: "tour", cat: "grafik", icon: "prof", name: "Mini-Höhenprofil", title: () => "Mini-Höhenprofil",
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
        label = `Höhenprofil, tiefster Punkt ${slHm(lo)}, höchster Punkt ${slHm(hi)}, Länge ${slKm(dm / 1000)}`;
      b.innerHTML = `<svg class="slprof" viewBox="0 0 600 120" preserveAspectRatio="none" role="img" aria-label="${esc(label)}"><path class="slpa" d="${area}"/>${line}</svg>` +
        `<div class="slxl sb" aria-hidden="true"><span>0 km</span><span>${slHm(lo)} bis ${slHm(hi)}</span><span>${slKm(dm / 1000)}</span></div>` +
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
        label = `Zeitleiste: ${R.length} Wiederholungen von ${dateS(f.datum)} bis ${dateS(l.datum)}`;
      b.innerHTML = slTiles([[`${R.length} ×`, "Auf dieser Strecke"], [dateS(f.datum), "Erstes Mal", f.aktuell ? "diese Tour" : ""], [dateS(l.datum), "Letztes Mal", l.aktuell ? "diese Tour" : ""],
        best ? [nf(best.tempo_kmh, 1) + " km/h", "Bestes Tempo", best.aktuell ? "diese Tour" : dateS(best.datum)] : null].filter(Boolean)) +
        `<div class="sltl" role="img" aria-label="${esc(label)}"><span class="sltl-l"></span>${dots}</div><div class="slxl sb" aria-hidden="true"><span>${f.datum.slice(0, 4)}</span><span>${l.datum.slice(0, 4)}</span></div>`;
      slPos(b);
      slBadge(c, `${R.length} ×`);
    },
  },
});
