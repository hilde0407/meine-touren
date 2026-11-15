/* =====================  3.18.0 Mehr Bausteine: Übersicht  =====================
   Gleiches Muster wie 50-bausteine.js. Fast alles rechnet aus den schon geladenen Touren (TOURS); nur Ausrüstung und geplante Touren holen Daten
   (GET /api/bausteine/ausruestung und /geplant, app/bausteine_daten.py), die Geräte kommen aus /api/my-devices. Grafiken: Inline-SVG, Farben aus CSS-Variablen. */
const SL_MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const SL_WD = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const SL_WDL = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];
const SL_WDS = ["montags", "dienstags", "mittwochs", "donnerstags", "freitags", "samstags", "sonntags"];
const slDay = iso => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 864e5;           // Tage seit 1970 (Datum der Tour in Ortszeit)
const slWeek = iso => Math.floor((slDay(iso) + 3) / 7);                                                    // Wochen ab Montag
const slWdx = iso => (new Date(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)).getDay() + 6) % 7;    // 0 = Montag
const slAgo = iso => {
  const n = new Date(), mo = (n.getFullYear() - +iso.slice(0, 4)) * 12 + n.getMonth() - (+iso.slice(5, 7) - 1) - (n.getDate() < +iso.slice(8, 10) ? 1 : 0), y = Math.floor(mo / 12);
  return y >= 1 ? (y === 1 ? "vor 1 Jahr" : `vor ${y} Jahren`) : mo <= 1 ? "vor 1 Monat" : `vor ${mo} Monaten`;
};
const SL_SPG = {                                                                  // Sportart → Gruppe [Name, Farb-Klasse]
  hike: ["Wandern", "hike"], mountaineering: ["Wandern", "hike"], nordicwalking: ["Wandern", "hike"], touringbicycle: ["Rad", "bike"], racebike: ["Rad", "bike"], mtb: ["Rad", "bike"],
  e_touringbicycle: ["E-Bike", "ebike"], jogging: ["Laufen", "run"], skialpin: ["Ski", "ski"], skitour: ["Ski", "ski"], nordic: ["Ski", "ski"], snowshoe: ["Schneeschuh", "snow"],
};
const slGroup = s => SL_SPG[s] || ["Sonstiges", "other"];
const slRows = list => `<ul class="slrows">${list.join("")}</ul>`;

Object.assign(window.SL_WT, {
  jahresziel: {
    fam: "uebersicht", cat: "plan", icon: "trend", name: "Jahresziel", title: () => "Jahresziel", multi: true, defaults: {metric: "km", goal: 1000},
    desc: "Ein Ring zeigt, wie weit du auf dein Jahresziel bist, dazu der Stand des Jahres und eine Prognose bis Silvester.",
    fields: [{k: "metric", kind: "radio", label: "Ziel in", options: [["km", "Kilometern"], ["hm", "Höhenmetern"]]}, {k: "goal", kind: "number", label: "Ziel für das Jahr (Zahl in der gewählten Einheit)", min: 10, max: 100000, step: 10}],
    preview: () => slPvRing(0.62),
    render(c, b, cfg) {
      const now = new Date(), cy = now.getFullYear(), hm = cfg.metric === "hm", u = hm ? "m" : "km", goal = Math.max(1, +cfg.goal || (hm ? 20000 : 1000)),
        val = slSum(TOURS.filter(t => t.y === cy), t => (hm ? t.up_m || 0 : t.km)), frac = val / goal,
        ylen = (cy % 4 === 0 && cy % 100 !== 0) || cy % 400 === 0 ? 366 : 365, doy = Math.floor((now - new Date(cy, 0, 0)) / 864e5), tf = doy / ylen,
        fc = doy >= 14 ? val / tf : null, left = Math.max(1, (ylen - doy) / 7), C1 = 263.9, C2 = 194.8,
        pct = Math.round(frac * 100), yp = Math.round(tf * 100),
        status = frac >= 1 ? "Das Ziel ist erreicht." : fc != null && fc >= goal ? "Auf Kurs: Bei diesem Tempo erreichst du dein Ziel." : `Dafür brauchst du noch ${nf((goal - val) / left, hm ? 0 : 1)} ${u} pro Woche.`;
      b.innerHTML = `<div class="slgoal"><div class="slring" role="img" aria-label="${esc(`Ring: ${pct} % des Jahresziels erreicht, das Jahr ist zu ${yp} % vorbei`)}"><svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">` +
        `<circle class="t" cx="50" cy="50" r="42"/><circle class="f${frac >= 1 ? " done" : ""}" cx="50" cy="50" r="42" stroke-dasharray="${(C1 * slClamp(frac, 0, 1)).toFixed(1)} ${C1}" transform="rotate(-90 50 50)"/>` +
        `<circle class="t2" cx="50" cy="50" r="31"/><circle class="g" cx="50" cy="50" r="31" stroke-dasharray="${(C2 * tf).toFixed(1)} ${C2}" transform="rotate(-90 50 50)"/></svg><div class="slrc"><b>${pct} %</b></div></div>` +
        `<div class="slgt"><p class="slcmp">${nf(val, 0)} von ${nf(goal, 0)} ${u}</p><p class="mut slcmpn">${frac >= 1 ? `Das sind ${nf(val - goal, 0)} ${u} über dem Ziel.` : `Noch ${nf(goal - val, 0)} ${u}`}</p>` +
        (fc != null ? `<p class="slfc">Prognose zum Jahresende: ${nf(fc, 0)} ${u}</p>` : "") + `<p class="mut slcmpn">${val > 0 ? status : "Noch keine Tour in diesem Jahr."}</p>` +
        `<ul class="sllg"><li><i class="slsq slbf"></i>Ziel</li><li><i class="slsq slyr"></i>Das Jahr ist zu ${yp} % vorbei</li></ul></div></div>`;
      slBadge(c, `${pct} %`);
    },
  },
  serie: {
    fam: "uebersicht", cat: "zahlen", icon: "heart", name: "Wochen-Serie", title: () => "Wochen-Serie",
    desc: "Wie viele Wochen in Folge du mindestens eine Tour gemacht hast, dein Rekord und die letzten 26 Wochen als Punktreihe.",
    preview: () => slPrev('<svg viewBox="0 0 156 14" class="slpvs" aria-hidden="true">' + [1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1].map((o, i) => `<rect class="${o ? "slhb" : "slhz"}" x="${i * 12}" y="2" width="10" height="10" rx="3"/>`).join("") + "</svg>"),
    render(c, b) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const set = new Set(TOURS.map(t => slWeek(t.date))), cur = slWeek(slIso(new Date())), all = [...set].sort((x, y) => x - y);
      let s = 0, w = set.has(cur) ? cur : cur - 1, rec = 0, run = 0;
      while (set.has(w)) {
        s++;
        w--;
      }
      all.forEach((x, i) => {
        run = i && x === all[i - 1] + 1 ? run + 1 : 1;
        rec = Math.max(rec, run);
      });
      const last = Array.from({length: 26}, (_, i) => set.has(cur - 25 + i)), n26 = last.filter(Boolean).length, wk = n => (n === 1 ? "1 Woche" : `${n} Wochen`),
        dots = last.map((o, i) => `<rect class="${o ? "slhb" : "slhz"}" x="${i * 12}" y="2" width="10" height="10" rx="3"/>`).join("");
      b.innerHTML = slTiles([[wk(s), "Aktuelle Serie"], [wk(rec), "Rekord", s >= rec && s > 0 ? "gerade erreicht" : ""], [`${n26} von 26`, "Wochen mit Tour", "in den letzten 26 Wochen"]]) +
        `<svg class="slpts" viewBox="0 0 312 14" preserveAspectRatio="xMinYMid meet" role="img" aria-label="${esc(`Letzte 26 Wochen: ${n26} Wochen mit mindestens einer Tour`)}">${dots}</svg>` +
        `<p class="mut slcap">${!set.has(cur) && s > 0 ? "Diese Woche fehlt noch eine Tour, damit die Serie weiterläuft." : "Eine Woche zählt, wenn sie mindestens eine Tour enthält (Montag bis Sonntag)."}</p>`;
      slBadge(c, wk(s));
    },
  },
  heatmap: {
    fam: "uebersicht", cat: "grafik", icon: "met", name: "Kalender-Heatmap", title: () => "Kalender-Heatmap", defaults: {metric: "km"},
    desc: "Die letzten 52 Wochen als Kalenderfläche: je dunkler ein Tag, desto mehr Kilometer (oder Touren) an diesem Tag.",
    fields: [{k: "metric", kind: "radio", label: "Färben nach", options: [["km", "Kilometern"], ["count", "Anzahl der Touren"]]}],
    preview: () => slPvHeat(),
    render(c, b, cfg) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const today = new Date(), t0 = slDay(slIso(today)), cur = slWeek(slIso(today)), first = (cur - 52) * 7 - 3, byDay = new Map(), cnt = cfg.metric === "count";
      TOURS.forEach(t => {
        const k = slDay(t.date), e = byDay.get(k) || {n: 0, km: 0};
        e.n++;
        e.km += t.km;
        byDay.set(k, e);
      });
      const val = e => (e ? (cnt ? e.n : e.km) : 0), pos = [];
      for (let k = first; k <= t0; k++) val(byDay.get(k)) > 0 && pos.push(val(byDay.get(k)));
      pos.sort((x, y) => x - y);
      const q = f => pos[Math.min(pos.length - 1, Math.floor(f * pos.length))], th = [q(0.25), q(0.5), q(0.75)],
        lvl = v => (v <= 0 ? 0 : v <= th[0] ? 1 : v <= th[1] ? 2 : v <= th[2] ? 3 : 4);
      let rects = "", days = 0, mos = "";
      for (let w = 0; w < 53; w++) {
        const d0 = new Date((first + w * 7) * 864e5);
        if (d0.getUTCDate() <= 7 && w > 0 && w < 52) mos += `<span data-l="${((w / 53) * 100).toFixed(1)}">${SL_MON[d0.getUTCMonth()]}</span>`;
        for (let r = 0; r < 7; r++) {
          const k = first + w * 7 + r;
          if (k > t0) break;
          const e = byDay.get(k), l = lvl(val(e));
          if (e) days++;
          const dt = new Date(k * 864e5), ds = `${pad2(dt.getUTCDate())}.${pad2(dt.getUTCMonth() + 1)}.${dt.getUTCFullYear()}`;
          rects += `<rect class="slh${l}" x="${w * 12}" y="${r * 12}" width="10" height="10" rx="2">${e ? `<title>${ds} · ${e.n === 1 ? "1 Tour" : e.n + " Touren"} · ${nf(e.km, 1)} km</title>` : ""}</rect>`;
        }
      }
      b.innerHTML = `<div class="slmos" aria-hidden="true">${mos}</div><svg class="slheat" viewBox="0 0 636 82" role="img" aria-label="${esc(`Kalender der letzten 52 Wochen: ${days} Tage mit Touren`)}">${rects}</svg>` +
        `<div class="slhl2"><span class="mut">${days} Tage mit Touren in den letzten 12 Monaten</span><span class="sllgh mut" aria-hidden="true">weniger ${[0, 1, 2, 3, 4].map(i => `<svg viewBox="0 0 10 10" width="12" height="12"><rect class="slh${i}" width="10" height="10" rx="2"/></svg>`).join("")} mehr</span></div>`;
      slPos(b);
      slBadge(c, `${days} Tage`);
    },
  },
  meilensteine: {
    fam: "uebersicht", cat: "plan", icon: "pin", name: "Meilensteine", title: () => "Meilensteine",
    desc: "Wie weit es bis zum nächsten runden Kilometerstand, zur nächsten Tour-Marke und zum nächsten „Mount Everest“ an Höhenmetern ist.",
    preview: () => slPvHbars([96, 58, 80]),
    render(c, b) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const km = slSum(TOURS, t => t.km), up = slSum(TOURS, t => t.up_m || 0), n = TOURS.length, EV = 8849,
        step = (v, L) => {
          const nx = L.find(x => x > v), pv = nx ? [0, ...L].filter(x => x <= v).pop() : L[L.length - 1];
          return {nx, pv, p: nx ? ((v - pv) / (nx - pv)) * 100 : 100};
        },
        K = step(km, [100, 250, 500, 1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 30000, 40075]), N = step(n, [10, 25, 50, 100, 150, 200, 300, 400, 500, 750, 1000, 1500, 2000]),
        ev = up / EV, evn = Math.floor(ev) + 1,
        row = (lab, val, p, line) => `<li><div class="slr1"><span>${lab}</span><b>${val}</b></div>${slBr(p)}<p class="mut slr2">${line}</p></li>`;
      b.innerHTML = slRows([
        row("Kilometer gesamt", slKm(km), K.p, K.nx ? `Noch ${slKm(K.nx - km)} bis ${nf(K.nx, 0)} km` : "Alle Meilensteine erreicht: mehr als einmal um die Erde."),
        row("Höhenmeter gesamt", `${nf(ev, ev >= 10 ? 0 : 1)} × Mount Everest`, (ev % 1) * 100, `Noch ${slHm(evn * EV - up)} bis zum nächsten Everest`),
        row("Touren gesamt", nf(n, 0), N.p, N.nx ? `Noch ${N.nx - n} bis ${N.nx} Touren` : "Alle Meilensteine erreicht."),
      ]);
      slBadge(c, K.nx ? `Noch ${slKm(K.nx - km)}` : "");
    },
  },
  wochentage: {
    fam: "uebersicht", cat: "grafik", icon: "met", name: "Lieblingstage und Tageszeiten", title: () => "Lieblingstage und Tageszeiten", defaults: {metric: "count"},
    desc: "An welchen Wochentagen und zu welcher Tageszeit du am liebsten unterwegs bist, als zwei Säulendiagramme.",
    fields: [{k: "metric", kind: "radio", label: "Zählen nach", options: [["count", "Anzahl der Touren"], ["km", "Kilometern"]]}],
    preview: () => slPvBars([20, 12, 14, 12, 24, 36, 30]),
    render(c, b, cfg) {
      if (TOURS.length < 3) return slNote(b, "Dafür braucht es mindestens drei Touren.");
      const km = cfg.metric === "km", wd = Array(7).fill(0), dp = Array(4).fill(0), PART = ["Morgens", "Mittags", "Nachmittags", "Abends"], PARTS = ["morgens", "mittags", "nachmittags", "abends"];
      TOURS.forEach(t => {
        const h = +t.date.slice(11, 13), v = km ? t.km : 1;
        wd[slWdx(t.date)] += v;
        dp[h >= 5 && h < 10 ? 0 : h >= 10 && h < 14 ? 1 : h >= 14 && h < 18 ? 2 : 3] += v;
      });
      const top = a => a.indexOf(Math.max(...a)), fav = top(wd), part = top(dp);
      b.innerHTML = `<div class="slg2"><div><p class="slcmpn">Wochentage</p>${slCols(wd, {hl: fav, label: `Säulendiagramm der Wochentage, am häufigsten ${SL_WDL[fav]}`, labels: SL_WD, cls: "slsm"})}</div>` +
        `<div><p class="slcmpn">Tageszeiten</p>${slCols(dp, {hl: part, label: `Säulendiagramm der Tageszeiten, am häufigsten ${PARTS[part]}`, labels: PART, cls: "slsm"})}</div></div>` +
        `<p class="slcmp">Dein Lieblingstag ist ${SL_WDL[fav]}.</p><p class="mut slcmpn">Am liebsten bist du ${PARTS[part]} unterwegs.</p>`;
      slBadge(c, SL_WDL[fav]);
    },
  },
  sportarten: {
    fam: "uebersicht", cat: "grafik", icon: "map", name: "Sportarten-Verteilung", title: () => "Sportarten-Verteilung", defaults: {metric: "count"},
    desc: "Welche Sportarten du wie oft machst, als Ring mit Legende, nach Anzahl der Touren, Kilometern oder Zeit.",
    fields: [{k: "metric", kind: "radio", label: "Verteilung nach", options: [["count", "Anzahl der Touren"], ["km", "Kilometern"], ["time", "Zeit unterwegs"]]}],
    preview: () => slPvDonut([[0.5, "slsg slsg-hike"], [0.28, "slsg slsg-bike"], [0.14, "slsg slsg-ski"], [0.08, "slsg slsg-other"]]),
    render(c, b, cfg) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const m = cfg.metric === "km" ? t => t.km : cfg.metric === "time" ? t => t.h : () => 1, G = {};
      TOURS.forEach(t => {
        const [name, cl] = slGroup(t.sport), g = (G[name] = G[name] || {name, cl, v: 0, n: 0});
        g.v += m(t);
        g.n++;
      });
      const L = Object.values(G).filter(g => g.v > 0).sort((x, y) => y.v - x.v), tot = slSum(L, g => g.v), C = 213.6, fmt = v => (cfg.metric === "km" ? slKm(v) : cfg.metric === "time" ? nf(v, 0) + " Std." : nf(v, 0));
      if (!L.length) return slNote(b, "Für diese Auswertung fehlen Angaben in den Touren.");
      let off = 0;
      const segs = L.map(g => {
        const f = g.v / tot, s = `<circle class="slsg slsg-${g.cl}" cx="50" cy="50" r="34" stroke-dasharray="${Math.max(0.5, C * f - (L.length > 1 ? 1.6 : 0)).toFixed(1)} ${C}" stroke-dashoffset="${(-off * C).toFixed(1)}" transform="rotate(-90 50 50)"/>`;
        off += f;
        return s;
      }).join("");
      b.innerHTML = `<div class="slgoal"><div class="slring slsd"><svg viewBox="0 0 100 100" role="img" aria-label="Ringdiagramm der Sportarten" focusable="false"><circle class="t" cx="50" cy="50" r="34"/>${segs}</svg><div class="slrc"><b>${fmt(tot)}</b>${cfg.metric === "km" || cfg.metric === "time" ? "" : '<small class="mut">Touren</small>'}</div></div>` +
        `<ul class="slleg">${L.map(g => `<li><i class="slsq slsg slsg-${g.cl}"></i><span>${g.name}</span><b>${Math.round((g.v / tot) * 100)} %</b><span class="mut">${fmt(g.v)}</span></li>`).join("")}</ul></div>`;
      slBadge(c, L[0].name);
    },
  },
  wiederentdecken: {
    fam: "uebersicht", cat: "rueck", icon: "cam", name: "Wiederentdecken", title: () => "Wiederentdecken",
    desc: "Eine zufällige ältere Tour mit Foto, zum Erinnern. Mit „Andere Tour“ würfelst du neu.",
    preview: () => slPrev('<div class="slrd slrd-pv"><i></i><div><b>Seeufer-Runde</b><span>vor 2 Jahren · 8,1 km</span></div></div>'),
    render(c, b) {
      const old = TOURS.filter(t => Date.now() - Date.parse(t.date) > 365 * 864e5), pool = old.length >= 2 ? old : TOURS.filter(t => Date.now() - Date.parse(t.date) > 30 * 864e5);
      if (!pool.length) return slNote(b, "Sobald du ältere Touren hast, zeige ich dir hier eine zufällige.");
      let cur = null;
      const draw = async () => {
        const others = pool.filter(t => !cur || t.id !== cur.id), t = others[Math.floor(Math.random() * others.length)] || pool[0],
          ph = t.photos ? await slGet(`/api/photos?tour_id=${slEnc(t.id)}&limit=1`) : null, p = ph && ph[0];
        cur = t;
        b.innerHTML = `<div class="slrd">${p ? `<img src="/pic/${p.id}?size=300" alt="${esc(t.name)}" loading="lazy">` : '<span class="slrd-i" aria-hidden="true">⛰️</span>'}` +
          `<div class="slrdt"><a class="slrdn" href="#/tour/${slEnc(t.id)}">${esc(t.name)}</a><span class="mut">${dateS(t.date)} · ${slAgo(t.date)}</span><span class="mut">${slKm(t.km)} · ${slHm(t.up_m || 0)} · ${slDur(t.h * 3600)}</span>` +
          (pool.length > 1 ? '<button type="button" class="btn sm ghost" data-other>Andere Tour</button>' : "") + "</div></div>";
        const o = b.querySelector("[data-other]");
        if (o) o.onclick = () => draw().then(() => {
          const n = b.querySelector("[data-other]");
          if (n) n.focus();
        });
        slBadge(c, slAgo(t.date));
      };
      return draw();
    },
  },
  orte: {
    fam: "uebersicht", cat: "zahlen", icon: "pin", name: "Meistbesuchte Orte", title: () => "Meistbesuchte Orte", defaults: {level: "county"},
    desc: "Die Orte, Landkreise, Regionen oder Länder, in denen du die meisten Touren gemacht hast, als Balken.",
    fields: [{k: "level", kind: "radio", label: "Gliedern nach", options: [["place", "Ort"], ["county", "Landkreis"], ["state", "Bundesland oder Region"], ["country", "Land"]]}],
    preview: () => slPvHbars([96, 70, 52, 30]),
    render(c, b, cfg) {
      const key = {place: "g_place", county: "g_county", state: "g_state", country: "g_country"}[cfg.level] || "g_county", G = {};
      let miss = 0;
      TOURS.forEach(t => {
        const k = (t[key] || "").trim();
        if (!k) return miss++;
        const g = (G[k] = G[k] || {k, n: 0, km: 0});
        g.n++;
        g.km += t.km;
      });
      const L = Object.values(G).sort((x, y) => y.n - x.n || y.km - x.km).slice(0, 8);
      if (!L.length) return slNote(b, "Noch keine Regionen bestimmt: Verwaltung → „Regionen bestimmen“.");
      b.innerHTML = slRows(L.map(g => `<li><div class="slr1"><span>${esc(g.k)}</span><b>${g.n === 1 ? "1 Tour" : g.n + " Touren"}</b></div>${slBr((g.n / L[0].n) * 100)}<p class="mut slr2">${slKm(g.km)}</p></li>`)) +
        (miss ? `<p class="mut slcap">${miss === 1 ? "1 Tour ohne Ortsangabe" : miss + " Touren ohne Ortsangabe"}</p>` : "");
      slBadge(c, esc(L[0].k));
    },
  },
  uhrenzeit: {
    fam: "uebersicht", cat: "grafik", icon: "watch", name: "Uhren-Zeitleiste", title: () => "Uhren und Geräte",
    desc: "Deine Geräte (Uhren, Handys) auf einer Zeitleiste: wann du sie genutzt hast und wie viele Touren sie aufgezeichnet haben.",
    preview: () => slPrev('<svg viewBox="0 0 120 34" class="slpvs" aria-hidden="true"><rect class="slhz" x="0" y="2" width="120" height="8" rx="4"/><rect class="slhb" x="4" y="2" width="56" height="8" rx="4"/><rect class="slhz" x="0" y="14" width="120" height="8" rx="4"/><rect class="slhb" x="50" y="14" width="70" height="8" rx="4"/><rect class="slhz" x="0" y="26" width="120" height="8" rx="4"/><rect class="slhb" x="30" y="26" width="40" height="8" rx="4"/></svg>'),
    async render(c, b) {
      const d = await slGet("/api/my-devices"), devs = d && d.devices ? d.devices : [];
      if (!devs.length) return slNote(b, "Noch kein Gerät angelegt – in der Verwaltung unter „Meine Geräte“.");
      const kind = k => ((d.kinds || []).find(x => x.kind === k) || {}).label || "",
        today = slIso(new Date()), ts = Date.parse, rows = [];
      devs.forEach(v => {
        const mine = TOURS.filter(t => t.dev === v.name).map(t => t.date.slice(0, 10)).sort(), from = v.since || mine[0], to = v.until || (v.active ? today : mine[mine.length - 1]);
        if (from && to) rows.push({v, from, to: to < from ? from : to, n: v.n || mine.length, open: !v.until && v.active});
      });
      if (!rows.length) return slNote(b, "Für deine Geräte sind noch keine Zeiträume bekannt.");
      rows.sort((x, y) => (x.from < y.from ? -1 : 1));
      const lo = ts(rows.reduce((m, r) => (r.from < m ? r.from : m), rows[0].from)), hi = Math.max(ts(today), lo + 864e5 * 30), my = s => `${s.slice(5, 7)}/${s.slice(0, 4)}`;
      b.innerHTML = slRows(rows.slice(0, 10).map(r => {
        const x = ((ts(r.from) - lo) / (hi - lo)) * 100, w = Math.max(1.5, ((ts(r.to) - ts(r.from)) / (hi - lo)) * 100);
        return `<li><div class="slr1"><span>${esc(r.v.name)}</span><b>${r.n === 1 ? "1 Tour" : r.n + " Touren"}</b></div><svg class="slbr" aria-hidden="true" focusable="false"><rect class="slbr-t" width="100%" height="10" rx="5"/><rect class="slbr-f" x="${x.toFixed(1)}%" width="${w.toFixed(1)}%" height="10" rx="5"/></svg>` +
          `<p class="mut slr2">${[kind(r.v.kind), r.open ? `${my(r.from)} – heute` : `${my(r.from)} – ${my(r.to)}`].filter(Boolean).join(" · ")}</p></li>`;
      })) + `<div class="slxl sb" aria-hidden="true"><span>${new Date(lo).getFullYear()}</span><span>${new Date().getFullYear()}</span></div>`;
      slBadge(c, rows.length === 1 ? "1 Gerät" : `${rows.length} Geräte`);
    },
  },
  ausruestung: {
    fam: "uebersicht", cat: "plan", icon: "dot", name: "Ausrüstungs-Kilometerstand", title: () => "Ausrüstung",
    desc: "Kilometerstand deiner Ausrüstung (Schuhe, Rad, Ski) gegen das Limit, mit Hinweis, wann ein Wechsel ansteht.",
    preview: () => slPvHbars([96, 70, 34]),
    async render(c, b) {
      const L = await slGet("/api/bausteine/ausruestung");
      if (!L || !L.length) return slNote(b, "Noch keine Ausrüstung angelegt.");
      const rows = L.slice(0, 8).map(g => {
        const lim = g.limit_km, cls = g.status === "over" ? "bad" : g.status === "soon" ? "warn" : "";
        return `<li><div class="slr1"><span>${esc(g.name)}</span><b>${lim ? `${nf(g.km, 0)} von ${slKm(lim)}` : slKm(g.km)}</b></div>${slBr(lim ? (g.km / lim) * 100 : 0, cls)}` +
          `<p class="mut slr2">${lim ? (g.status === "over" ? "Limit erreicht" : g.status === "soon" ? `Bald fällig: noch ${slKm(lim - g.km)}` : `Noch ${slKm(lim - g.km)}`) : "Ohne Limit"}</p></li>`;
      });
      b.innerHTML = slRows(rows) + '<p><a href="#/places">Ausrüstung verwalten ›</a></p>';
      const due = L.filter(g => g.status === "over" || g.status === "soon").length;
      slBadge(c, due ? (due === 1 ? "1 bald fällig" : `${due} bald fällig`) : "");
    },
  },
  geplant: {
    fam: "uebersicht", cat: "plan", icon: "map", name: "Geplante Touren", title: () => "Geplante Touren",
    desc: "Die zuletzt geplanten Touren mit Länge, Höhenmetern und geschätzter Dauer, mit Link zur Planung.",
    preview: () => slPrev('<ul class="sllist"><li><b>Gipfelweg</b><span>8,0 km · 900 m</span></li><li><b>Rund um den See</b><span>12,5 km</span></li></ul>'),
    async render(c, b) {
      const L = await slGet("/api/bausteine/geplant"), can = typeof isViewer === "function" ? !isViewer() : true;
      if (!L || !L.length) return (b.innerHTML = `<p class="mut slnone">Keine geplanten Touren.</p>${can ? '<p><a href="#/plan">Tour planen ›</a></p>' : ""}`);
      b.innerHTML = `<ul class="sllist">${L.slice(0, 5).map(p => `<li>${can ? `<a href="#/plan/${p.id}">${esc(p.name || "Ohne Namen")}</a>` : `<b>${esc(p.name || "Ohne Namen")}</b>`}<span class="mut">${[p.km != null ? slKm(p.km) : "", p.up ? slHm(p.up) : "", p.est_h ? slDur(p.est_h * 3600) : ""].filter(Boolean).join(" · ")}</span></li>`).join("")}</ul>` +
        (can ? '<p><a href="#/plan">Tour planen ›</a></p>' : "");
      slBadge(c, L.length === 1 ? "1 Plan" : `${L.length} Pläne`);
    },
  },
  rueckblick: {
    fam: "uebersicht", cat: "rueck", icon: "trend", name: "Jahres-Rückblick", title: cfg => `Rückblick ${new Date().getFullYear() - (cfg.year === "last" ? 1 : 0)}`, multi: true, defaults: {year: "this"},
    desc: "Das Jahr in einer Kachel: Touren, Kilometer und Höhenmeter, die Monate als Säulen, die längste und die höchste Tour.",
    fields: [{k: "year", kind: "radio", label: "Jahr", options: [["this", "Dieses Jahr"], ["last", "Letztes Jahr"]]}],
    preview: () => slPvBars([8, 14, 20, 30, 26, 34, 28, 22, 14, 12, 6, 4]),
    render(c, b, cfg) {
      const y = new Date().getFullYear() - (cfg.year === "last" ? 1 : 0), A = TOURS.filter(t => t.y === y);
      if (!A.length) return slNote(b, `Im Jahr ${y} gab es keine Touren.`);
      const mk = Array(12).fill(0), mn = Array(12).fill(0);
      A.forEach(t => {
        mk[t.m - 1] += t.km;
        mn[t.m - 1]++;
      });
      const best = mk.indexOf(Math.max(...mk)), L = A.reduce((m, t) => (t.km > m.km ? t : m)), U = A.reduce((m, t) => ((t.up_m || 0) > (m.up_m || 0) ? t : m)),
        tile = (t, v, l) => `<a class="utile slrec" href="#/tour/${slEnc(t.id)}"><b>${v}</b><span>${l}</span><small class="mut">${esc(t.name)} · ${dateS(t.date)}</small></a>`;
      b.innerHTML = slTiles([[nf(A.length, 0), A.length === 1 ? "Tour" : "Touren"], [slKm(slSum(A, t => t.km)), "Kilometer"], [slHm(slSum(A, t => t.up_m || 0)), "Höhenmeter"]]) +
        `<p class="slcmpn">Kilometer je Monat</p>${slCols(mk, {hl: best, label: `Säulendiagramm der Kilometer je Monat, am meisten im ${SL_MON[best]}`, labels: SL_MON, cls: "slsm"})}` +
        `<div class="utiles">${tile(L, slKm(L.km), "Längste Tour")}${U.up_m ? tile(U, slHm(U.up_m), "Meiste Höhenmeter") : ""}<div class="utile"><b>${SL_MON[best]}</b><span>Aktivster Monat</span><small class="mut">${slKm(mk[best])} · ${mn[best] === 1 ? "1 Tour" : mn[best] + " Touren"}</small></div></div>`;
      slBadge(c, `${nf(slSum(A, t => t.km), 0)} km`);
    },
  },
});
