/* =====================  3.17.0 Bausteine (Widgets) für „Seite anpassen“  =====================
   Jeder Baustein ist ein einklappbarer Abschnitt im Kopfformat von tlCard() (Symbol, Titel, Kurzaussage). Er liest nur vorhandene Daten (vorhandene API-Endpunkte,
   keine neuen Berechnungen) und zeigt bei fehlenden Daten einen kurzen Hinweis statt einer leeren Fläche. Die Konfiguration je Baustein (cfg) steht im Layout-Dokument.
   3.18.0: jeder Typ hat eine Kategorie (cat: zahlen, grafik, spass, rueck, plan) für den Katalog; die neuen Bausteine stehen in 51-bausteine-tour.js und 52-bausteine-uebersicht.js,
   gemeinsame Hilfen (Balken, Ring, Spaltendiagramm) unten in dieser Datei. Grafiken sind Inline-SVG; Maße kommen als Attribute, Farben aus CSS-Variablen.
   Typ = {fam, cat, icon, name, title(cfg), desc, multi, fields, defaults, cfgOnAdd, preview(), render(card, body, cfg, ctx)}. Baustein einer Tourseite: ctx.t = Tour. */
const slNote = (b, text) => (b.innerHTML = `<p class="mut slnone">${text}</p>`);
const slTiles = list => `<div class="utiles">${list.map(([v, l, s]) => `<div class="utile"><b>${v}</b><span class="mut">${l}</span>${s ? `<small class="mut">${s}</small>` : ""}</div>`).join("")}</div>`;
const slMin = s => fmtMS(s);
const slBadge = (c, html) => typeof tlSetBadge === "function" && tlSetBadge(c, html);
const slPhotos = (c, body, list, label, cls = "") => {
  if (!list.length) return slNote(body, "Keine Fotos vorhanden.");
  body.innerHTML = `<div class="slfotos${cls ? " " + cls : ""}">${list.map((p, i) => `<img loading="lazy" tabindex="0" role="button" src="/pic/${p.id}?size=${cls ? 600 : 300}" data-i="${i}" alt="${esc(p.tour_name || label)}">`).join("")}</div>`;
  if (typeof bindThumbs === "function") bindThumbs(body, list);
  body.querySelectorAll("img[data-i]").forEach(im => (im.onkeydown = e => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), im.click())));
};
const slSum = (a, f) => a.reduce((x, t) => x + f(t), 0);
const slIso = d => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const slPrev = (inner) => `<div class="slpvi">${inner}</div>`;
const slPvTiles = list => slPrev(slTiles(list));
const slPvBars = v => slPrev(`<svg viewBox="0 0 120 40" class="slpvs" aria-hidden="true">${v.map((h, i) => `<rect x="${i * 14 + 4}" y="${38 - h}" width="10" height="${h}" rx="2"/>`).join("")}</svg>`);

/* ---- 3.18.0 gemeinsame Hilfen für Grafiken: Maße als Attribute, Farben über Klassen und CSS-Variablen (style.css „Mehr Bausteine“) ---- */
const SL_CATS = [["reise", "Reisen"], ["foto", "Fotos"], ["karte", "Karte"], ["statistik", "Statistik"], ["zahlen", "Zahlen"], ["grafik", "Grafiken"], ["spass", "Spaß und Eigenes"], ["rueck", "Rückblick"], ["plan", "Planung"], ["quellen", "Touren holen"]];
const slEnc = encodeURIComponent;
/* Zeile aus Teilen, jedes Teil ein eigener Textknoten (die Übersetzung greift je Teil; der Punkt dazwischen kommt aus dem Stylesheet) */
const slSegs = parts => parts.filter(Boolean).map(x => `<span>${x}</span>`).join("");
const slGet = u => api(u).catch(() => null);
/* 3.37.0 Wochenansicht von „Belastung und Erholung“: je Woche Belastung laut Uhr (Balken), Touren und Kilometer sowie Ruhetage (Tage ohne Tour) als sieben Punkte.
   „Ohne Angabe“ (Touren, aber kein Uhr-Wert) ist nie 0: kein Balken, dafür der Text. Eine Woche ohne Tour ist bekannt ruhig. Der Server liefert je Woche touren, belastung, km und tage (Mo bis So, "1" = Tour). */
function slBelWochen(c, b, d, said, nw, mon, now) {
  const by = new Map((d.wochen || []).map(x => [x.von, x])), wd = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"], run = ((now.getDay() + 6) % 7) + 1, rows = [];
  for (let i = nw - 1; i >= 0; i--) {
    const m0 = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() - i * 7), m1 = new Date(m0.getFullYear(), m0.getMonth(), m0.getDate() + 6), v = by.get(slIso(m0)) || {touren: 0, belastung: null, km: 0, tage: "0000000"},
      elapsed = i === 0 ? run : 7, act = [...v.tage].slice(0, elapsed).filter(x => x === "1").length;
    rows.push({m0, m1, v, cur: i === 0, rest: elapsed - act, elapsed, act});
  }
  const mx = Math.max(1, ...rows.map(r => r.v.belastung || 0)), rest = rows.reduce((a, r) => a + r.rest, 0), days = rows.reduce((a, r) => a + r.elapsed, 0), tours = rows.reduce((a, r) => a + r.v.touren, 0);
  if (!tours) return slNote(b, nw === 12 ? "In den letzten 12 Wochen gab es keine Tour." : "In den letzten 8 Wochen gab es keine Tour.");
  const wkNo = dt => {                                                                      // ISO-Kalenderwoche des Montags
    const x = new Date(Date.UTC(dt.getFullYear(), dt.getMonth(), dt.getDate())), dn = x.getUTCDay() || 7;
    x.setUTCDate(x.getUTCDate() + 4 - dn);
    return Math.ceil(((x - Date.UTC(x.getUTCFullYear(), 0, 1)) / 864e5 + 1) / 7);
  };
  const li = rows.slice().reverse().map(r => {
    const v = r.v, none = v.touren === 0, noval = v.touren > 0 && v.belastung == null, lab = `KW ${wkNo(r.m0)} · ${r.m0.getDate()}.${r.m0.getMonth() + 1}.–${r.m1.getDate()}.${r.m1.getMonth() + 1}.`,
      val = none ? "Ruhewoche" : noval ? "Belastung ohne Angabe" : `Belastung ${nf(v.belastung, 0)}`,
      dots = [...v.tage].map((x, k) => `<i class="slwdo ${k >= r.elapsed ? "fut" : x === "1" ? "on" : "off"}"><span class="slwdl">${wd[k]}</span></i>`).join("");
    return `<li class="slwk${r.cur ? " cur" : ""}"><div class="slr1"><span>${esc(lab)}${r.cur ? ' <small class="mut">läuft</small>' : ""}</span><b>${val}</b></div>${slBr(v.belastung == null ? 0 : (v.belastung / mx) * 100)}` +
      `<div class="slwdd" aria-hidden="true">${dots}</div><p class="mut slr2 slsegs">${slSegs([v.touren === 1 ? "1 Tour" : `${v.touren} Touren`, `${nf(v.km || 0, 1)} km`, r.rest === 1 ? "1 Ruhetag" : `${r.rest} Ruhetage`])}</p></li>`;
  });
  b.innerHTML = `<p class="slcmp">${said || "Für einen Vergleich liegen noch zu wenige Wochen mit Uhr-Daten vor"}</p>` +
    `<p class="mut slcmpn">In ${nw} Wochen: ${rest === 1 ? "1 Ruhetag" : rest + " Ruhetage"} bei ${tours === 1 ? "1 Tour" : tours + " Touren"} (im Schnitt ${nf((rest / days) * 7, 1)} Ruhetage je Woche).</p>` +
    (d.daten_insgesamt ? "" : '<p class="mut slcmpn">Noch keine Uhr-Daten: Die Belastung stammt aus den Trainingsdaten der Uhr.</p>') +
    `<ul class="slrows slwks">${li.join("")}</ul><p class="mut slcmpn slwleg">Balken: Belastung laut Uhr. Punkte: Tage mit Tour (gefüllt) und Ruhetage (leer), Montag bis Sonntag.</p><p><a href="#/places">Mehr in der Auswertung ›</a></p>`;
  slBadge(c, rest === 1 ? "1 Ruhetag" : `${rest} Ruhetage`);
}
const slClamp = (x, a = 0, b = 100) => Math.max(a, Math.min(b, x));
const slDur = s => {
  const m = Math.round(s / 60);
  return m >= 60 ? `${Math.floor(m / 60)}:${pad2(m % 60)} Std.` : `${m} Min.`;
};
const slKm = km => nf(km, km >= 100 ? 0 : 1) + " km";
const slHm = h => nf(h, 0) + " m";
const slBr = (pct, cls = "") => `<svg class="slbr${cls ? " " + cls : ""}" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true" focusable="false"><rect class="slbr-t" width="100" height="10"/><rect class="slbr-f" width="${slClamp(pct).toFixed(1)}" height="10"/></svg>`;
/* Spaltendiagramm: vals = Zahlen; o = {hl: Index (hervorgehoben), dim: [Indizes] (blass), avg: Mittellinie, label: Beschreibung für Vorlesehilfen, labels: Beschriftungen unter den Spalten} */
const slCols = (vals, o = {}) => {
  const n = vals.length, mx = Math.max(...vals, 1e-9),
    bars = vals.map((v, i) => {
      const h = v > 0 ? Math.max(2.5, (v / mx) * 94) : 1;
      return `<rect class="${i === o.hl ? "hl" : o.dim && o.dim.includes(i) ? "dim" : v > 0 ? "v" : "z"}" x="${i * 10 + 1}" y="${(100 - h).toFixed(1)}" width="8" height="${h.toFixed(1)}"/>`;
    }).join(""),
    avg = o.avg != null && o.avg > 0 ? `<line class="avg" x1="0" x2="${n * 10}" y1="${(100 - (o.avg / mx) * 94).toFixed(1)}" y2="${(100 - (o.avg / mx) * 94).toFixed(1)}"/>` : "";
  return `<svg class="slcol${o.cls ? " " + o.cls : ""}" viewBox="0 0 ${n * 10} 100" preserveAspectRatio="none" role="img" aria-label="${esc(o.label || "")}">${bars}${avg}</svg>` +
    (o.labels ? `<div class="slxl" aria-hidden="true">${o.labels.map(l => `<span>${esc(l)}</span>`).join("")}</div>` : "");
};
/* Positionen in Prozent (data-l) nach dem Einfügen setzen: berechnete Werte, keine Inline-Stile im Quelltext */
const slPos = root => root.querySelectorAll("[data-l]").forEach(e => e.style.setProperty("left", e.dataset.l + "%"));
const slPvRing = f => slPrev(`<svg viewBox="0 0 100 100" class="slpvs slpvr" aria-hidden="true"><circle class="t" cx="50" cy="50" r="40"/><circle class="f" cx="50" cy="50" r="40" stroke-dasharray="${(251.3 * f).toFixed(1)} 251.3" transform="rotate(-90 50 50)"/><circle class="t" cx="50" cy="50" r="30"/><circle class="g" cx="50" cy="50" r="30" stroke-dasharray="${(188.5 * 0.8).toFixed(1)} 188.5" transform="rotate(-90 50 50)"/></svg>`);
const slPvHeat = () => {
  const L = [0, 1, 0, 2, 3, 0, 1, 4, 2, 0, 1, 0, 3, 2, 0, 0, 4, 1, 2, 0, 0, 3, 1, 0, 2, 4, 0, 1];
  return slPrev(`<svg viewBox="0 0 168 56" class="slpvs slpvh" aria-hidden="true">${L.map((l, i) => `<rect class="slh${l}" x="${(i % 14) * 12}" y="${Math.floor(i / 14) * 14 + 6}" width="10" height="10" rx="2"/>`).join("")}</svg>`);
};
const slPvDonut = parts => {
  let o = 0;
  const C = 188.5;
  return slPrev(`<svg viewBox="0 0 100 100" class="slpvs slpvr" aria-hidden="true">${parts.map(([f, cl]) => {
    const r = `<circle class="${cl}" cx="50" cy="50" r="30" stroke-dasharray="${Math.max(0, C * f - 3).toFixed(1)} ${C}" stroke-dashoffset="${(-o * C).toFixed(1)}" transform="rotate(-90 50 50)"/>`;
    o += f;
    return r;
  }).join("")}</svg>`);
};
const slPvHbars = v => slPrev(`<svg viewBox="0 0 120 ${v.length * 12 + 2}" class="slpvs" aria-hidden="true">${v.map((w, i) => `<rect class="slhb" x="0" y="${i * 12 + 2}" width="${w}" height="8" rx="4"/>`).join("")}</svg>`);
const slPvLine = pts => slPrev(`<svg viewBox="0 0 120 44" class="slpvs" aria-hidden="true"><path class="slpa" d="M0 44 ${pts.map((y, i) => `L${(i * 120) / (pts.length - 1)} ${y}`).join(" ")} L120 44Z"/><path class="slpl" d="M${pts.map((y, i) => `${(i * 120) / (pts.length - 1)} ${y}`).join(" L")}"/></svg>`);

const SL_KZ = [["km", "Strecke"], ["up", "Aufstieg"], ["down", "Abstieg"], ["dur", "Dauer"], ["pace", "Tempo"], ["hr", "Puls (Durchschnitt)"], ["kcal", "Kalorien"]];
Object.assign(window.SL_WT, {
  /* ---------------- Tourseite ---------------- */
  kennzahlen: {
    fam: "tour", cat: "zahlen", icon: "met", name: "Kennzahlen-Kachel", title: () => "Kennzahlen", multi: true, defaults: {values: ["km", "up", "dur", "pace"]},
    desc: "Wählbare Kennzahlen dieser Tour als Kacheln: Strecke, Aufstieg, Dauer, Tempo, Puls, Kalorien.",
    fields: [{k: "values", kind: "checks", label: "Angezeigte Werte", min: 1, options: SL_KZ}],
    preview: () => slPvTiles([["12,4 km", "Strecke"], ["420 m", "Aufstieg"], ["3:05", "Dauer"]]),
    async render(c, b, cfg, {t}) {
      if (!t) return slNote(b, "Keine Tour.");
      const want = (cfg.values && cfg.values.length ? cfg.values : ["km", "up", "dur", "pace"]).filter(v => SL_KZ.some(k => k[0] === v)),
        tiles = {
          km: [nf(t.km, 1) + " km", "Strecke"], up: [nf(t.up_m, 0) + " m", "Aufstieg"], down: [nf(t.down_m, 0) + " m", "Abstieg"],
          dur: [`${fmtHM(t.h * 3600)} Std.`, "Dauer"], pace: t.h ? [nf(t.km / t.h, 1) + " km/h", "Tempo im Schnitt"] : null,
        };
      if (want.includes("hr")) {
        const h = await api(`/api/tours/${encodeURIComponent(t.id)}/hr`).catch(() => null);
        if (h && h.n && h.avg) tiles.hr = [`${h.avg} bpm`, "Puls (Durchschnitt)", `max ${h.max} bpm`];
      }
      if (want.includes("kcal")) {
        const u = await api(`/api/tours/${encodeURIComponent(t.id)}/uhr-training`).catch(() => null),
          k = u && u.werte && u.werte.kcal && u.werte.kcal.wert;
        if (k) tiles.kcal = [nf(k, 0) + " kcal", "Kalorien"];
      }
      const list = want.map(v => tiles[v]).filter(Boolean);
      if (!list.length) return slNote(b, "Für die gewählten Werte liegen bei dieser Tour keine Daten vor.");
      b.innerHTML = slTiles(list);
      slBadge(c, `${nf(t.km, 1)} km · ${nf(t.up_m, 0)} m`);
    },
  },
  tempo: {
    fam: "tour", cat: "zahlen", icon: "trend", name: "Tempo-Mini", title: () => "Tempo bergauf, eben, bergab",
    desc: "Durchschnittstempo bergauf, auf ebenem Weg und bergab, aus der Steigung der Strecke.",
    preview: () => slPvTiles([["3,1 km/h", "Bergauf"], ["4,6 km/h", "Eben"], ["4,2 km/h", "Bergab"]]),
    async render(c, b, cfg, {t}) {
      const d = t && (await api(`/api/tours/${encodeURIComponent(t.id)}/tempo`).catch(() => null));
      if (!d || d.status !== "ok") return slNote(b, "Für diese Tour liegt keine Auswertung nach Steigung vor (Strecke mit Höhen und Zeit nötig).");
      const k = d.klassen,
        one = (key, lab) => (k[key] ? [nf(k[key].kmh, 1) + " km/h", lab, nf(k[key].dist_m / 1000, 1) + " km"] : null);
      b.innerHTML = slTiles([one("auf", "Bergauf"), one("eben", "Eben"), one("ab", "Bergab")].filter(Boolean));
      slBadge(c, k.auf ? `Bergauf <b>${nf(k.auf.kmh, 1)} km/h</b>` : "");
    },
  },
  vergleich: {
    fam: "tour", cat: "zahlen", icon: "cmp", name: "Vergleich in einer Zeile", title: () => "Vergleich auf dieser Strecke",
    desc: "„Platz x von y“ unter allen Touren auf derselben Strecke, nach Tempo, mit Link zur Auswertung.",
    preview: () => slPrev('<p class="slcmp">Platz 2 von 5 auf dieser Strecke</p>'),
    async render(c, b, cfg, {t}) {
      const d = t && (await api(`/api/tours/${encodeURIComponent(t.id)}/aehnliche`).catch(() => null)),
        L = d && d.status === "ok" ? d.touren.filter(r => r.tempo_kmh != null).sort((x, y) => y.tempo_kmh - x.tempo_kmh) : [],
        i = L.findIndex(r => r.aktuell);
      if (!d || d.status !== "ok" || i < 0 || L.length < 2) return slNote(b, "Auf dieser Strecke gibt es noch keine Vergleichstouren.");
      b.innerHTML = `<p class="slcmp">Platz ${i + 1} von ${L.length} auf dieser Strecke</p><p class="mut slcmpn">nach Tempo (Strecke geteilt durch Dauer)</p><p><a href="#/tour/${encodeURIComponent(t.id)}/auswertung">Zur Auswertung ›</a></p>`;
      slBadge(c, `Platz <b>${i + 1}</b> von ${L.length}`);
    },
  },
  pulszonen: {
    fam: "tour", cat: "grafik", icon: "heart", name: "Puls-Zonen", title: () => "Puls-Zonen",
    desc: "Zeit in den fünf Pulszonen als Balken (nur bei Touren mit Herzfrequenz).",
    preview: () => slPrev('<svg viewBox="0 0 120 14" class="slpvs" aria-hidden="true"><rect x="0" y="0" width="14" height="14" fill="#8fb8d8"/><rect x="14" y="0" width="40" height="14" fill="#6bb38a"/><rect x="54" y="0" width="34" height="14" fill="#e2b13c"/><rect x="88" y="0" width="22" height="14" fill="#e0803c"/><rect x="110" y="0" width="10" height="14" fill="#c0504d"/></svg>'),
    async render(c, b, cfg, {t}) {
      const h = t ? await api(`/api/tours/${encodeURIComponent(t.id)}/hr`).catch(() => null) : null;
      if (!h || !h.n || !h.zones) return slNote(b, "Für diese Tour wurde kein Puls aufgezeichnet.");
      const tot = h.zones.reduce((x, y) => x + y, 0) || 1;
      let x = 0;
      const bars = h.zones.map((s, i) => {
        const w = (s / tot) * 600,
          r = `<rect x="${x.toFixed(1)}" y="0" width="${Math.max(w, 0).toFixed(1)}" height="22" fill="${HR_ZC[i]}"/>`;
        x += w;
        return r;
      }).join("");
      b.innerHTML = `<svg class="slzb" viewBox="0 0 600 22" preserveAspectRatio="none" role="img" aria-label="Zeit in den Pulszonen">${bars}</svg><ul class="slzl">${h.zones.map((s, i) => `<li><i class="slzd" data-z="${i}"></i><span>Z${i + 1} ${HR_ZN[i]}</span><b>${slMin(s)}</b><span class="mut">${Math.round((s / tot) * 100)} %</span></li>`).join("")}</ul>`;
      b.querySelectorAll(".slzd").forEach(e => e.style.setProperty("background", HR_ZC[+e.dataset.z]));
      slBadge(c, `Ø ${h.avg} · max ${h.max} bpm`);
    },
  },
  wetter: {
    fam: "tour", cat: "zahlen", icon: "cloud", name: "Wetter-Streifen", title: () => "Wetter zur Tour",
    desc: "Wetter am Tag der Tour in einer Zeile: Himmel, Temperatur, Niederschlag, Wind.",
    preview: () => slPvTiles([["Leicht bewölkt", "Wetter"], ["8–15 °C", "Temperatur"], ["18 km/h", "Wind bis"]]),
    async render(c, b, cfg, {t}) {
      const w = t && (await api(`/api/tours/${encodeURIComponent(t.id)}/weather`).catch(() => null));
      if (!w || w.tmin == null) return slNote(b, "Für diese Tour liegen keine Wetterdaten vor.");
      b.innerHTML = slTiles([[esc(w.text || "–"), "Wetter"], [`${nf(w.tmin, 0)}–${nf(w.tmax, 0)} °C`, "Temperatur"], [nf(w.precip, 1) + " mm", "Niederschlag"], [nf(w.wind, 0) + " km/h", "Wind bis"]]);
      slBadge(c, `${esc(w.text || "")} · ${nf(w.tmin, 0)}–${nf(w.tmax, 0)} °C`);
    },
  },
  fotostreifen: {
    fam: "tour", cat: "grafik", icon: "cam", name: "Fotostreifen", title: () => "Fotostreifen",
    desc: "Die ersten Fotos dieser Tour als Streifen zum Anklicken.",
    preview: () => slPrev('<div class="slpvf" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'),
    async render(c, b, cfg, {t}) {
      const l = t && t.photos ? await api(`/api/photos?tour_id=${encodeURIComponent(t.id)}&limit=12`).catch(() => []) : [];
      slPhotos(c, b, l, "Foto der Tour");
      if (l.length) slBadge(c, l.length === 1 ? "1 Foto" : `${l.length} Fotos`);
    },
  },
  notiz: {
    fam: "tour", cat: "spass", icon: "note", name: "Eigene Notiz", title: () => "Notiz", multi: true, cfgOnAdd: true, defaults: {text: ""},
    desc: "Ein freier Text (bis 500 Zeichen), den du selbst schreibst, zum Beispiel eine Erinnerung an die Tour.",
    fields: [{k: "text", kind: "text", label: "Text der Notiz", max: 500}],
    preview: () => slPrev('<p class="slnote">Einkehr im Gasthof, Rückweg über den Grat …</p>'),
    render(c, b, cfg) {
      const x = (cfg.text || "").trim();
      if (!x) return slNote(b, "Noch keine Notiz. Den Text trägst du unter „Seite anpassen“ bei „Einstellungen“ ein.");
      b.innerHTML = `<p class="slnote"></p>`;
      b.firstChild.textContent = x;
    },
  },
  /* ---------------- Übersicht ---------------- */
  periode: {
    fam: "uebersicht", cat: "zahlen", icon: "trend", name: "Diese Woche / dieser Monat", title: cfg => (cfg.period === "month" ? "Dieser Monat" : "Diese Woche"), multi: true, defaults: {period: "week"}, filter: {range: null},
    desc: "Touren, Kilometer und Höhenmeter der laufenden Woche oder des laufenden Monats.",
    fields: [{k: "period", kind: "radio", label: "Zeitraum", def: "week", options: [["week", "Diese Woche"], ["month", "Dieser Monat"]]}, {kind: "sports"}, {kind: "title"}],
    preview: () => slPvTiles([["3", "Touren"], ["41 km", "Kilometer"], ["1.120 m", "Höhenmeter"]]),
    render(c, b, cfg) {
      const now = new Date(),
        from = cfg.period === "month" ? new Date(now.getFullYear(), now.getMonth(), 1) : new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7)),
        iso = slIso(from),
        a = TOURS.filter(t => t.date.slice(0, 10) >= iso && flSport(t, cfg));
      b.innerHTML = slTiles([[nf(a.length, 0), a.length === 1 ? "Tour" : "Touren"], [nf(slSum(a, t => t.km), 1) + " km", "Kilometer"], [nf(slSum(a, t => t.up_m || 0), 0) + " m", "Höhenmeter"], [nf(slSum(a, t => t.h), 1) + " Std.", "Unterwegs"]]);
      slBadge(c, a.length ? `${nf(slSum(a, t => t.km), 0)} km` : "Noch keine Tour");
    },
  },
  belastung: {
    fam: "uebersicht", cat: "grafik", icon: "heart", name: "Belastung und Erholung", title: () => "Belastung und Erholung", defaults: {view: "kompakt", weeks: 8},
    desc: "Wie viel Belastung die letzten vier Wochen laut Uhr hatten, verglichen mit dem Schnitt davor, mit Wochenbalken. Als Wochenansicht: je Woche die Belastung laut Uhr, die Touren und die Ruhetage dazu.",
    fields: [{k: "view", kind: "radio", def: "kompakt", label: "Ansicht", options: [["kompakt", "Kompakt (Vergleich mit Wochenbalken)"], ["wochen", "Wochenansicht mit Ruhetagen"]]},
      {k: "weeks", kind: "radio", num: true, def: 8, label: "Wochen in der Wochenansicht", options: [[8, "8 Wochen"], [12, "12 Wochen"]]}],
    preview: () => slPvBars([10, 18, 14, 26, 20, 32, 24]),
    async render(c, b, cfg) {
      const wk = (cfg || {}).view === "wochen", nw = +(cfg || {}).weeks === 12 ? 12 : 8, now = new Date(),
        mon = new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7)),
        von = wk ? new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() - (nw - 1) * 7) : new Date(Date.now() - 84 * 864e5),
        d = await api(`/api/stats/belastung?von=${slIso(von)}&bis=${slIso(now)}`).catch(() => null);
      if (!wk && (!d || !d.daten_insgesamt)) return slNote(b, "Noch keine Uhr-Daten: Die Belastung stammt aus den Trainingsdaten der Uhr.");
      if (wk && !d) return slNote(b, "Die Belastung konnte nicht geladen werden.");
      const A = (d && d.aktuell) || {},
        said = {deutlich_mehr: "Deutlich mehr Belastung als sonst", mehr: "Etwas mehr Belastung als sonst", aehnlich: "Ähnlich viel Belastung wie sonst", weniger: "Etwas weniger Belastung als sonst", deutlich_weniger: "Deutlich weniger Belastung als sonst"}[A.stufe];
      if (wk) return slBelWochen(c, b, d, said, nw, mon, now);
      const w = d.wochen.slice(-12),
        mx = Math.max(1, ...w.map(x => x.belastung || 0)),
        bars = w.map((x, i) => `<rect class="${x.belastung == null ? "slbn" : "slbv"}" x="${i * 20 + 2}" y="${x.belastung == null ? 38 : 40 - Math.max(2, (x.belastung / mx) * 38)}" width="14" height="${x.belastung == null ? 2 : Math.max(2, (x.belastung / mx) * 38)}" rx="2"/>`).join("");
      b.innerHTML = `<p class="slcmp">${said || "Für einen Vergleich liegen noch zu wenige Wochen mit Uhr-Daten vor"}</p>${A.abweichung_pct != null ? `<p class="mut slcmpn">${A.abweichung_pct > 0 ? "+" : ""}${A.abweichung_pct} % gegenüber dem Schnitt der 12 Wochen davor</p>` : ""}` +
        `<svg class="slbars" viewBox="0 0 ${w.length * 20} 42" role="img" aria-label="Belastung je Woche, letzte 12 Wochen">${bars}</svg><p><a href="#/places">Mehr in der Auswertung ›</a></p>`;
      slBadge(c, said || "");
    },
  },
  jahresvergleich: {
    fam: "uebersicht", cat: "rueck", icon: "trend", name: "Jahresvergleich", title: () => "Jahresvergleich", filter: {range: null},
    fields: [{k: "metrics", kind: "checks", def: ["count", "km", "up"], label: "Angezeigte Werte", min: 1, options: [["count", "Touren"], ["km", "Kilometer"], ["up", "Höhenmeter"], ["h", "Stunden"]]}, {kind: "sports"}, {kind: "title"}],
    desc: "Das laufende Jahr gegen das Vorjahr bis zum selben Tag: Touren, Kilometer, Höhenmeter.",
    preview: () => slPvTiles([["31 Touren", "2026"], ["+12 %", "Kilometer"], ["−4 %", "Höhenmeter"]]),
    render(c, b, cfg) {
      const cy = new Date().getFullYear(), {list: a, prev: p} = flSelect(cfg, "year"),
        row = (m, d) => {
          const x = flVal(a, m), y = flVal(p, m), pct = y > 0 ? Math.round(((x - y) / y) * 100) : null;
          return [`${nf(x, d)}`, m === "count" ? "Touren" : m === "h" ? "Stunden" : FL_MET[m].name, `Vorjahr bis heute: ${nf(y, d)}${pct == null ? "" : ` (${pct >= 0 ? "+" : "−"}${Math.abs(pct)} %)`}`];
        };
      if (!a.length && !p.length) return flNone(b, (cfg.sports || []).length ? "" : "Noch keine Touren in diesem und im letzten Jahr.");
      b.innerHTML = slTiles((cfg.metrics && cfg.metrics.length ? cfg.metrics : ["count", "km", "up"]).filter(m => FL_MET[m]).map(m => row(m, 0)));
      slBadge(c, String(cy));
    },
  },
  letzte: {
    fam: "uebersicht", cat: "rueck", icon: "map", name: "Letzte Touren", title: () => "Letzte Touren", filter: {range: null}, defaults: {n: 5},
    fields: [{k: "n", kind: "radio", num: true, def: 5, label: "Anzahl", options: [[3, "3"], [5, "5"], [8, "8"], [10, "10"]]}, {kind: "sports"}, {kind: "title"}],
    desc: "Die zuletzt gemachten Touren (3 bis 10, wählbar, auch nur einer Aktivität) als Liste mit Link.",
    preview: () => slPrev('<ul class="sllist"><li><b>Gipfelrunde</b><span>12,4 km</span></li><li><b>Seeufer</b><span>8,1 km</span></li></ul>'),
    render(c, b, cfg) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const L = TOURS.filter(t => flSport(t, cfg)).slice(0, +cfg.n >= 1 && +cfg.n <= 10 ? +cfg.n : 5);
      if (!L.length) return flNone(b);
      b.innerHTML = `<ul class="sllist">${L.map(t => `<li><a href="#/tour/${encodeURIComponent(t.id)}">${esc(t.name)}</a><span class="mut">${dateS(t.date)} · ${nf(t.km, 1)} km · ${nf(t.up_m || 0, 0)} m</span></li>`).join("")}</ul>`;
    },
  },
  neuefotos: {
    fam: "uebersicht", cat: "grafik", icon: "cam", name: "Zuletzt aufgenommene Fotos", title: () => "Zuletzt aufgenommene Fotos",
    desc: "Die acht Fotos mit dem jüngsten Aufnahmedatum als Streifen.",
    preview: () => slPrev('<div class="slpvf" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'),
    async render(c, b) {
      const l = await api("/api/photos?recent=1&limit=8").catch(() => []);
      slPhotos(c, b, l, "Foto");
    },
  },
  auffaellig: {
    fam: "uebersicht", cat: "zahlen", icon: "watch", name: "Auffällige Touren", title: () => "Auffällige Touren",
    desc: "Wie viele Touren die Geräte-Qualität als auffällig meldet, mit Link zur Verwaltung.",
    preview: () => slPvTiles([["3", "Auffällige Touren"]]),
    async render(c, b) {
      const d = await api("/api/devices/quality").catch(() => null),
        devs = d && d.devices ? d.devices : [];
      if (!devs.length) return slNote(b, "Noch keine Geräte mit Auswertung.");
      const n = slSum(devs, x => x.flagged || 0);
      b.innerHTML = n
        ? `<p class="slcmp">${n === 1 ? "1 Tour ist auffällig" : n + " Touren sind auffällig"}</p><p><a href="#/admin?tab=quellen">In der Verwaltung ansehen ›</a></p>`
        : `<p class="slcmp">Keine auffälligen Touren</p><p><a href="#/admin?tab=quellen">Geräte in der Verwaltung ›</a></p>`;
      slBadge(c, n ? String(n) : "keine");
    },
  },
  rekorde: {
    fam: "uebersicht", cat: "rueck", icon: "trend", name: "Rekorde", title: () => "Rekorde", filter: {range: "all"}, defaults: {},
    fields: [{kind: "sports"}, {kind: "range", def: "all"}, {kind: "title"}],
    desc: "Längste Tour, meiste Höhenmeter und schnellstes Tempo, mit Link zur Tour.",
    preview: () => slPvTiles([["32,4 km", "Längste Tour"], ["1.480 m", "Meiste Höhenmeter"]]),
    render(c, b, cfg) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const A = flSelect(cfg, "all").list;
      if (!A.length) return flNone(b);
      const best = (f, ok) => A.filter(ok || (() => true)).reduce((m, t) => (!m || f(t) > f(m) ? t : m), null),
        L = best(t => t.km), U = best(t => t.up_m || 0), S = best(t => t.km / t.h, t => t.km >= 3 && t.h >= 0.5),
        tile = (t, v, l) => (t ? `<a class="utile slrec" href="#/tour/${encodeURIComponent(t.id)}"><b>${v}</b><span>${l}</span><small class="mut">${esc(t.name)} · ${dateS(t.date)}</small></a>` : "");
      b.innerHTML = `<div class="utiles">${tile(L, nf(L && L.km, 1) + " km", "Längste Tour")}${tile(U && U.up_m ? U : null, nf(U && U.up_m, 0) + " m", "Meiste Höhenmeter")}${tile(S, nf(S && S.km / S.h, 1) + " km/h", "Schnellstes Tempo")}</div>`;
    },
  },
  heutevor: {
    fam: "uebersicht", cat: "rueck", icon: "cmp", name: "Heute vor X Jahren", title: () => "Heute vor X Jahren",
    desc: "Touren, die du an genau diesem Datum in früheren Jahren gemacht hast.",
    preview: () => slPrev('<ul class="sllist"><li><b>Vor 3 Jahren</b><span>Seeufer, 8,1 km</span></li></ul>'),
    render(c, b) {
      const now = new Date(),
        md = `${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`,
        a = TOURS.filter(t => t.date.slice(5, 10) === md && t.y !== now.getFullYear());
      if (!a.length) return slNote(b, "An diesem Tag gab es in früheren Jahren keine Tour.");
      b.innerHTML = `<ul class="sllist">${a.map(t => `<li><b>${now.getFullYear() - t.y === 1 ? "Vor 1 Jahr" : "Vor " + (now.getFullYear() - t.y) + " Jahren"}</b><a href="#/tour/${encodeURIComponent(t.id)}">${esc(t.name)}</a><span class="mut">${nf(t.km, 1)} km</span></li>`).join("")}</ul>`;
      slBadge(c, a.length === 1 ? "1 Tour" : `${a.length} Touren`);
    },
  },
});
/* Baustein als Karte aufbauen; Daten werden danach nachgeladen */
window.slWidgetBuild = (it, root) => {
  const T = window.SL_WT[it.wtype];
  if (!T) return null;
  if (T.shell) {                                                            // 3.19.0: Baustein im Format eines Übersichtsblocks („Dein Jahr“), kein einklappbarer Abschnitt
    const e = T.shell(it, root);
    e.dataset.sig = slSig(it);
    return e;
  }
  const c = tlCard("tlw-" + it.id, {sec: it.id, key: "tl_w_" + it.id, icon: T.icon, title: esc(slWTitle(T, it.cfg || {})), def: true, bodyCls: "slwb"});
  c.dataset.wid = it.id;
  c.dataset.wtype = it.wtype;
  c.dataset.sig = slSig(it);
  flHead(c, T, it.cfg || {});
  if (it.note && typeof stNoteAdd === "function") stNoteAdd(c, it.note);                    // 3.22.0 Statistikseite: „Filter gilt hier nicht“
  const body = tlBody(c);
  if (T.hinweis) c.dataset.hn = "lade";                                                      // 3.23.0 Hinweis-Bausteine: bis die Daten da sind unsichtbar (58-bausteine-hinweise.js)
  body.innerHTML = '<p class="mut slnone">Wird geladen …</p>';
  const t = root && root.dataset && root.dataset.tid ? BY[root.dataset.tid] : null;
  Promise.resolve()
    .then(() => T.render(c, body, it.cfg || {}, {t, reise: window.RS_CUR || null}))
    .catch(() => {
      body.innerHTML = '<p class="mut slnone">Dieser Baustein konnte nicht geladen werden.</p>';
      if (T.hinweis) c.dataset.hn = "aus";
    });
  return c;
};
