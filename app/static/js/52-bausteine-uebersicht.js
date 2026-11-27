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
/* 3.59.0: jede Aktivität einzeln (Name und Farbe aus SPORT); eigene Statistik-Gruppen als ein Eintrag (Gruppenname, Farbe der ersten Sportart). SL_SPG gilt nicht mehr. */
const slGroup = s => {
  const k = sgKey(s), f = x => (SPORT[x] ? SPORT[x][1].slice(2) : "other");
  return isSg(k) ? [esc(sName(k)), f(sgById(k).sports[0])] : [esc(sName(s)), f(sNorm(s))];
};
const slRows = list => `<ul class="slrows">${list.join("")}</ul>`;

/* Jahres-Rückblick: bis 3.18.0 „Dieses/Letztes Jahr“ (cfg.year), seit 3.19.0 wie die übrigen Bausteine (range year | y + yr); die ältere Einstellung gilt weiter */
const slRbRange = cfg => flRange(cfg.range || cfg.yr ? cfg : cfg.year === "last" ? {range: "y", yr: new Date().getFullYear() - 1} : {}, "year");

/* ---- 3.45.0 Baustein „Ziele“: ein Baustein statt vier (bis 3.44: „Jahresziel“ mit eigenem Ziel, „Ziele“, Hinweis „Jahresziel in Gefahr“, Hinweis „Wochenziel“ mit eigenem Ziel).
   Ziele werden nur an einer Stelle gepflegt: GET/POST/DELETE /api/goals (app/extras.py; period year | week). Darstellung (cfg.view): balken (Fortschrittsbalken mit Prognose), ring (je Ziel ein Ring
   wie der frühere „Jahresziel“-Baustein), warnung (erscheint nur, wenn ein Ziel in Gefahr ist; Regeln und Zahlen aus GET /api/bausteine/hinweise, Arten ziel und woche, Ausblenden wie bei den
   Hinweisen). Welche Ziele (cfg.zeit): alle | jahr | woche; Jahr (cfg.year): cur | last; Sportart wählt Ziele aus (ein Ziel ohne Sportart betrifft alle).
   Als Abschnitt „Ziele“ der Statistik (SL_REG, verwalten) zeigt er zusätzlich Löschen und „Ziel hinzufügen“ – das ist die eine Stelle zum Pflegen; das Jahr folgt dort dem Filter der Seite.
   Alte Typkennungen bildet SL_ALIAS (49-seitenlayout.js) bzw. app/baustein_umzug.py auf diesen Baustein ab. ---- */
const ZL_VIEW = [["balken", "Balken"], ["ring", "Ring"], ["warnung", "Nur Warnung, wenn ein Ziel in Gefahr ist"]];
const ZL_ZEIT = [["alle", "Jahres- und Wochenziele"], ["jahr", "Nur Jahresziele"], ["woche", "Nur Wochenziele"]];
const zlWeek = g => g && g.period === "week";
const zlSports = g => goalSports(g.sport);                                     // 3.59.0: zentrale Regel (06-erweiterungen.js), auch Statistik-Gruppen
const zlFits = (g, cfg) => {
  const want = sgPlain(cfg.sports || []), sp = zlSports(g);
  return !want.length || sp === null || sp.some(s => want.includes(s));
};
const zlMon = (now = new Date()) => new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7));
const zlWeekVal = (g, now = new Date()) => {
  const from = slIso(zlMon(now)), to = slIso(now);
  return TOURS.filter(t => t.date.slice(0, 10) >= from && t.date.slice(0, 10) <= to && goalSport(g, t))
    .reduce((c, t) => c + (g.metric === "km" ? t.km : g.metric === "up" ? t.up_m || 0 : g.metric === "hours" ? t.h : 1), 0);
};
const zlName = g => `${GM[g.metric][1]}${zlWeek(g) ? " pro Woche" : ""}${g.sport ? " " + goalSportName(g.sport) : ""}`;
const zlYear = cfg => (cfg._jahr >= 1970 ? cfg._jahr : new Date().getFullYear() - (cfg.year === "last" ? 1 : 0));          // Statistik: das gewählte Jahr der Seite (56-statistik.js, stApply)
const zlCan = () => (typeof isViewer === "function" ? !isViewer() : true);
function zlBar(g, yr, cy, now, ed) {
  const del = ed ? ` <button type="button" class="gx" data-g="${g.id}" aria-label="${esc(`Ziel löschen: ${zlName(g)}`)}" title="Ziel löschen">×</button>` : "";
  if (zlWeek(g)) {
    const v = zlWeekVal(g, now), p = Math.min(100, (v / g.target) * 100), u = GM[g.metric][0], rest = 6 - ((now.getDay() + 6) % 7);
    return `<div class="goal zlw"><div class="gh"><b>${zlName(g)}</b><span>${nf(v, g.metric === "count" ? 0 : g.metric === "hours" || g.target < 50 ? 1 : 0)} / ${nf(g.target, 0)} ${u}${del}</span></div>${slBr(p, v >= g.target ? "kzfull" : "")}` +
      `<div class="gs">${nf(p, 0)}\u00a0%${v >= g.target ? ` · <span class="ok">Wochenziel erreicht ✓</span>` : ` · ${rest === 0 ? "Heute ist der letzte Tag der Woche." : rest === 1 ? "Noch 1 Tag in dieser Woche." : `Noch ${rest} Tage in dieser Woche.`}`}</div></div>`;
  }
  const frac = yr === cy ? Math.max(0, (now - new Date(cy, 0, 1)) / (new Date(cy + 1, 0, 1) - new Date(cy, 0, 1))) : yr > cy ? 0 : 1,
    v = goalVal(g, TOURS), p = Math.min(100, (v / g.target) * 100), u = GM[g.metric][0], proj = frac > 0.02 && frac < 1 ? v / frac : null;
  return `<div class="goal"><div class="gh"><b>${zlName(g)}</b><span>${nf(v, 0)} / ${nf(g.target, 0)} ${u}${del}</span></div>${slBr(p, v >= g.target ? "kzfull" : "")}` +
    `<div class="gs">${nf(p, 0)}\u00a0%${goalNote(g, v, u, frac, proj, yr, cy)}</div></div>`;
}
function zlRing(g, yr, cy, now) {
  const wk = zlWeek(g), val = wk ? zlWeekVal(g, now) : goalVal(g, TOURS), goal = Math.max(1e-9, g.target), u = GM[g.metric][0] || (g.metric === "count" ? "Touren" : ""),
    frac = val / goal, C1 = 263.9, C2 = 194.8, dec = g.metric === "count" ? 0 : g.metric === "hours" || goal < 50 ? 1 : 0;
  let tf, fc = null, need = "";
  if (wk) {
    const d = (now.getDay() + 6) % 7;
    tf = (d + 1) / 7;
    if (val < goal) need = 6 - d > 0 ? `Noch ${nf(goal - val, dec)} ${u} in ${6 - d === 1 ? "1 Tag" : `${6 - d} Tagen`}.` : "Heute ist der letzte Tag der Woche.";
  } else {
    const ylen = (yr % 4 === 0 && yr % 100 !== 0) || yr % 400 === 0 ? 366 : 365, doy = yr === cy ? Math.floor((now - new Date(cy, 0, 0)) / 864e5) : yr < cy ? ylen : 0, left = Math.max(1, (ylen - doy) / 7);
    tf = doy / ylen;
    fc = yr === cy && doy >= 14 ? val / tf : null;
    need = fc != null && fc >= goal ? "Auf Kurs: Bei diesem Tempo erreichst du dein Ziel." : yr === cy ? `Dafür brauchst du noch ${nf((goal - val) / left, dec)} ${u} pro Woche.` : "";
  }
  const pct = Math.round(frac * 100), yp = Math.round(tf * 100), lbl = wk ? `Die Woche ist zu ${yp}\u00a0% vorbei` : `Das Jahr ist zu ${yp}\u00a0% vorbei`;
  return `<div class="slgoal"><div class="slring" role="img" aria-label="${esc(`Ring: ${pct}\u00a0% des Ziels erreicht, ${lbl}`)}"><svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">` +
    `<circle class="t" cx="50" cy="50" r="42"/><circle class="f${frac >= 1 ? " done" : ""}" cx="50" cy="50" r="42" stroke-dasharray="${(C1 * slClamp(frac, 0, 1)).toFixed(1)} ${C1}" transform="rotate(-90 50 50)"/>` +
    `<circle class="t2" cx="50" cy="50" r="31"/><circle class="g" cx="50" cy="50" r="31" stroke-dasharray="${(C2 * slClamp(tf, 0, 1)).toFixed(1)} ${C2}" transform="rotate(-90 50 50)"/></svg><div class="slrc"><b>${pct}\u00a0%</b></div></div>` +
    `<div class="slgt"><p class="zlrn">${zlName(g)}</p><p class="slcmp">${nf(val, dec)} von ${nf(goal, 0)} ${u}</p><p class="mut slcmpn">${frac >= 1 ? `Das sind ${nf(val - goal, dec)} ${u} über dem Ziel.` : `Noch ${nf(goal - val, dec)} ${u}`}</p>` +
    (fc != null ? `<p class="slfc">Prognose zum Jahresende: ${nf(fc, 0)} ${u}</p>` : "") + `<p class="mut slcmpn">${frac >= 1 ? "Das Ziel ist erreicht." : val > 0 ? need : wk ? "Noch keine Tour in dieser Woche." : "Noch keine Tour in diesem Jahr."}</p>` +
    `<ul class="sllg"><li><i class="slsq slbf"></i>Ziel</li><li><i class="slsq slyr"></i>${lbl}</li></ul></div></div>`;
}
/* Nur Warnung: Server-Hinweise „ziel“ (Prognose zum Jahresende unter der Schwelle) und „woche“ (Wochenziel am Samstag/Sonntag noch offen); Ausblenden je Art wie bei den Hinweisen */
async function zlWarn(c, b, cfg) {
  const arts = cfg.zeit === "jahr" ? ["ziel"] : cfg.zeit === "woche" ? ["woche"] : ["ziel", "woche"], sch = cfg.schwelle ?? 10,
    cond = `<p class="hnphc">${esc(cfg.zeit === "woche" ? "Wird nur angezeigt, wenn ein Wochenziel am Samstag oder Sonntag noch offen ist."
      : cfg.zeit === "jahr" ? `Wird nur angezeigt, wenn die Prognose zum Jahresende um mehr als ${hnNum(sch)}\u00a0% unter einem deiner Jahresziele liegt.`
        : `Wird nur angezeigt, wenn ein Ziel in Gefahr ist: Die Prognose zum Jahresende liegt um mehr als ${hnNum(sch)}\u00a0% unter einem Jahresziel, oder ein Wochenziel ist am Samstag oder Sonntag noch offen.`)}</p>` +
      `<p class="mut hnphs">${esc("Voraussetzung: ein Ziel in der Statistik unter „Ziele“; die Prognose eines Jahresziels gibt es ab dem 14. Tag des Jahres.")}</p>`;
  c.dataset.hn = "lade";
  let d;
  try {
    d = await hnGet(hnQuery(arts, cfg, false));
  } catch (e) {
    b.innerHTML = cond + `<p class="mut hnphs">Die Hinweise konnten nicht geladen werden.</p>`;
    slBadge(c, "");
    return hnState(c, "aus");
  }
  const all = d.hinweise.filter(h => arts.includes(h.art) && (h.art === "ziel" || (h.stufe === "hinweis" && !h.daten.erreicht))),
    items = all.filter(h => !hnSnoozed(cfg, h.art)), hidden = all.filter(h => hnSnoozed(cfg, h.art)).map(h => h.art);
  if (!items.length) {
    b.innerHTML = cond + `<p class="mut hnphs">${hidden.length ? "" : "Gerade ist kein Ziel in Gefahr: Der Baustein ist unsichtbar."}</p>` +
      hidden.map(a => `<p class="mut hnphs"><span>Ausgeblendet bis ${fmtDatumKurz(slIso(new Date(hnSnoozeTs(cfg, a) * 1000)))}.</span> ${slCan() ? `<button type="button" class="btn ghost sm hnun" data-art="${a}">Wieder anzeigen</button>` : ""}</p>`).join("");
    slBadge(c, hidden.length ? "ausgeblendet" : "nichts los");
    return hnState(c, "aus");
  }
  b.innerHTML = items.length > 1 ? `<div class="hnlist">${items.map(h => hnBox(h, cfg, {titel: true})).join("")}</div>` : hnBox(items[0], cfg, {titel: true});
  slBadge(c, HN_ART[items[0].art].badge(items[0]));
  hnState(c, "an");
}
/* Pflege der Ziele (nur als Abschnitt „Ziele“ der Statistik): Ziel hinzufügen (Jahr oder Woche), löschen, aus dem Vorjahr übernehmen */
function zlForm(yr, prev) {
  return (prev.length ? `<p><button type="button" class="btn sm alt" id="gcopy">Ziele aus ${yr - 1} übernehmen (${prev.length})</button></p>` : "") +
    `<details class="zladd"><summary>Ziel hinzufügen</summary><div class="row mt8 zlrow"><label class="slsr" for="gper">Zeitraum</label><select id="gper"><option value="year">Ziel für ${yr}</option><option value="week">Ziel für jede Woche</option></select>` +
    `<label class="slsr" for="gm">Messgröße</label><select id="gm">${Object.entries(GM).map(([k, v]) => `<option value="${k}">${v[1]}</option>`).join("")}</select>` +
    `<div class="zlsp"><span class="slsr">Sportart</span>${sportWahlHtml("", {id: "gsp", moreId: "gspmore", extra: [["", "Alle Sportarten", ""]].concat(SGRP.map(g => [SG_PRE + g.id, sgLabel(SG_PRE + g.id), sgTitle(SG_PRE + g.id)]))})}</div>` +   // 3.61.0: Muster „Zuweisen“
    `<label class="slsr" for="gt">Zielwert</label><input id="gt" type="number" min="1" inputmode="decimal" placeholder="Zielwert"><button type="button" class="btn sm" id="gadd">Speichern</button></div><p class="slerr" role="alert"></p></details>`;
}
function zlBind(b, yr, prev) {
  const post = g => api("/api/goals", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(g)});
  sportWahlBind(b);
  b.onclick = async e => {
    const x = e.target.closest(".gx"), cp = e.target.closest("#gcopy"), add = e.target.closest("#gadd");
    if (x && (await uiConfirm({text: "Ziel löschen?", danger: true, ok: "Löschen"}))) {
      await api(`/api/goals/${x.dataset.g}`, {method: "DELETE"});
      route();
    } else if (cp) {
      for (const g of prev.filter(g => !isSg(g.sport) || sgById(g.sport))) await post({year: yr, metric: g.metric, sport: g.sport, target: g.target});     // 3.59.0: Ziel einer gelöschten Gruppe nicht übernehmen
      route();
    } else if (add) {
      const t = parseFloat(String(b.querySelector("#gt").value).replace(",", ".")), er = b.querySelector(".zladd .slerr");
      if (!(t > 0)) {
        er.textContent = "Bitte einen Zielwert größer als 0 eingeben.";
        return b.querySelector("#gt").focus();
      }
      await post({period: b.querySelector("#gper").value, year: yr, metric: b.querySelector("#gm").value, sport: b.querySelector("#gsp").value, target: t});
      route();
    }
  };
}
/* Registriert wird der Baustein am Ende von 58-bausteine-hinweise.js (er nutzt dessen Hinweis-Hilfen) */
function zlType() {
  return {
    fam: "uebersicht", cat: "plan", icon: "pin", name: "Ziele", multi: true, defaults: {view: "balken", zeit: "alle"}, filter: {range: null}, w: "halb", seiten: ["uebersicht", "tour", "statistik"],
    title: cfg => (cfg.zeit === "woche" ? "Ziele dieser Woche" : `Ziele ${zlYear(cfg)}`), stJahr: true,
    kurz: cfg => flParts(cfg, null),
    desc: "Deine Ziele aus der Statistik (zum Beispiel 1000 km im Jahr oder 3 Touren pro Woche) mit Stand und Prognose – als Balken, als Ring oder nur als Warnung, wenn ein Ziel in Gefahr ist. Angelegt und gelöscht werden Ziele in der Statistik unter „Ziele“.",
    fields: [{k: "view", kind: "radio", def: "balken", label: "Darstellung", options: ZL_VIEW}, {k: "zeit", kind: "radio", def: "alle", label: "Welche Ziele", options: ZL_ZEIT},
      {k: "year", kind: "radio", def: "cur", label: "Jahr der Jahresziele", options: [["cur", "Dieses Jahr"], ["last", "Letztes Jahr"]], show: {view: ["balken", "ring"]}},
      {kind: "sports", label: "Sportart (nur Ziele, die sie betreffen)"},
      {k: "schwelle", kind: "number", def: 10, label: "Warnung, wenn die Prognose um mehr als so viele Prozent unter dem Jahresziel liegt", min: 1, max: 90, step: 1, int: true, show: {view: ["warnung"]}},
      {kind: "title"}, {...HN_FIELD_AUS, show: {view: ["warnung"]}}],
    preview: () => slPvHbars([84, 52]),
    async render(c, b, cfg, ctx = {}) {
      cfg = {view: "balken", zeit: "alle", ...cfg};
      if (cfg.view === "warnung" && !(ctx && ctx.verwalten)) return zlWarn(c, b, cfg);
      delete c.dataset.hn;
      const now = new Date(), cy = now.getFullYear(), yr = zlYear(cfg), ed = !!(ctx && ctx.verwalten) && zlCan();
      const all = await slGet("/api/goals");
      if (all === null) return slNote(b, "Die Ziele konnten nicht geladen werden.");
      const ys = cfg.zeit === "woche" ? [] : all.filter(g => !zlWeek(g) && g.year === yr && zlFits(g, cfg)),
        ws = cfg.zeit === "jahr" || yr !== cy ? [] : all.filter(g => zlWeek(g) && zlFits(g, cfg)),
        gs = [...ys, ...ws], prev = all.filter(g => !zlWeek(g) && g.year === yr - 1);
      if (!gs.length) {
        const what = cfg.zeit === "woche" ? "Noch kein Wochenziel." : `Noch kein Ziel für ${yr}.`;
        b.innerHTML = `<div${ed ? ' id="goals"' : ""} class="zlbox"><p class="mut slnone">${what}${ed ? " Setze dir eines, zum Beispiel 1000 km Wandern." : ""}</p>` +
          (ed ? zlForm(yr, ys.length ? [] : prev) : zlCan() ? `<p><a href="#/stats">Ziel in der Statistik festlegen ›</a></p>` : "") + "</div>";
        if (ed) zlBind(b, yr, prev);
        return slBadge(c, "Noch kein Ziel");
      }
      const body = cfg.view === "ring" && !ed ? `<div class="zlrings">${gs.slice(0, 6).map(g => zlRing(g, yr, cy, now)).join("")}</div>` : gs.map(g => zlBar(g, yr, cy, now, ed)).join("");
      b.innerHTML = `<div${ed ? ' id="goals"' : ""} class="zlbox">${body}${ed ? zlForm(yr, ys.length ? [] : prev) : `<p><a href="#/stats">Ziele in der Statistik verwalten ›</a></p>`}</div>`;
      if (ed) zlBind(b, yr, prev);
      const done = gs.filter(g => (zlWeek(g) ? zlWeekVal(g, now) : goalVal(g, TOURS)) >= g.target).length;
      slBadge(c, gs.length === 1 ? (done ? "erreicht" : "1 Ziel") : `${done} von ${gs.length} erreicht`);
    },
  };
}

Object.assign(window.SL_WT, {
  jahr: {
    fam: "uebersicht", cat: "zahlen", icon: "trend", name: "Dein Jahr", title: () => "Dein Jahr", multi: true, shell: it => slYearShell(it), defaults: {},
    kurz: cfg => (cfg.title ? flParts(cfg, "year") : flParts(cfg, "year", {noRange: true})),
    desc: "Touren, Strecke, Aufstieg und Stunden mit Monatssäulen und Vorjahresvergleich, wählbar nach Sportart und Zeitraum. In der Übersicht steht „Dein Jahr“ schon; hier kannst du weitere mit anderem Filter hinzufügen.",
    fields: [{kind: "sports"}, {kind: "range", def: "year"}, {k: "metrics", kind: "checks", def: ["count", "km", "up", "h"], label: "Angezeigte Werte", min: 1, options: [["count", "Touren"], ["km", "Strecke"], ["up", "Aufstieg"], ["h", "Dauer"]]}, {kind: "compare"}, {kind: "title", ph: "Dein Jahr"}],
    preview: () => slPrev(slTiles([["31", "Touren"], ["412", "Strecke"], ["8.400", "Aufstieg"]]) + '<svg viewBox="0 0 120 30" class="slpvs" aria-hidden="true">' + [6, 10, 14, 22, 18, 26, 24, 16, 12, 8, 4, 2].map((h, i) => `<rect x="${i * 10 + 1}" y="${30 - h}" width="8" height="${h}" rx="1"/>`).join("") + "</svg>"),
  },
  serie: {
    fam: "uebersicht", cat: "zahlen", icon: "heart", name: "Wochen-Serie", title: () => "Wochen-Serie", filter: {range: null}, fields: [{kind: "sports"}, {kind: "title"}],
    desc: "Wie viele Wochen in Folge du mindestens eine Tour gemacht hast, dein Bestwert und die letzten 26 Wochen als Punktreihe.",
    preview: () => slPrev('<svg viewBox="0 0 156 14" class="slpvs" aria-hidden="true">' + [1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1].map((o, i) => `<rect class="${o ? "slhb" : "slhz"}" x="${i * 12}" y="2" width="10" height="10" rx="3"/>`).join("") + "</svg>"),
    render(c, b, cfg) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const T0 = TOURS.filter(t => flSport(t, cfg));
      if (!T0.length) return flNone(b);
      const set = new Set(T0.map(t => slWeek(t.date))), cur = slWeek(slIso(new Date())), all = [...set].sort((x, y) => x - y);
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
      b.innerHTML = slTiles([[wk(s), "Aktuelle Serie"], [wk(rec), "Bestwert", s >= rec && s > 0 ? "gerade erreicht" : ""], [`${n26} von 26`, "Wochen mit Tour", "in den letzten 26 Wochen"]]) +
        `<svg class="slpts" viewBox="0 0 312 14" preserveAspectRatio="xMinYMid meet" role="img" aria-label="${esc(`Letzte 26 Wochen: ${n26} Wochen mit mindestens einer Tour`)}">${dots}</svg>` +
        `<p class="mut slcap">${!set.has(cur) && s > 0 ? "Diese Woche fehlt noch eine Tour, damit die Serie weiterläuft." : "Eine Woche zählt, wenn sie mindestens eine Tour enthält (Montag bis Sonntag)."}</p>`;
      slBadge(c, wk(s));
    },
  },
  heatmap: {
    fam: "uebersicht", cat: "grafik", icon: "met", name: "Kalender-Heatmap", title: () => "Kalender-Heatmap", defaults: {metric: "km"}, filter: {range: null},
    desc: "Die letzten 52 Wochen als Kalenderfläche: je dunkler ein Tag, desto mehr Kilometer (oder Touren) an diesem Tag.",
    fields: [{k: "metric", kind: "radio", def: "km", label: "Färben nach", options: [["km", "Strecke"], ["count", "Anzahl der Touren"], ["up", "Aufstieg"], ["h", "Dauer"]]}, {kind: "sports"}, {kind: "title"}],
    preview: () => slPvHeat(),
    render(c, b, cfg) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const MT = FL_MET[cfg.metric] ? cfg.metric : "km";
      const today = new Date(), t0 = slDay(slIso(today)), cur = slWeek(slIso(today)), first = (cur - 52) * 7 - 3, byDay = new Map();
      TOURS.forEach(t => {
        if (!flSport(t, cfg)) return;
        const k = slDay(t.date), e = byDay.get(k) || {n: 0, km: 0, v: 0};
        e.n++;
        e.km += t.km;
        e.v += FL_MET[MT].f(t);
        byDay.set(k, e);
      });
      const val = e => (e ? e.v : 0), pos = [];
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
          rects += `<rect class="slh${l}" x="${w * 12}" y="${r * 12}" width="10" height="10" rx="2">${e ? `<title>${ds} · ${e.n === 1 ? "1 Tour" : e.n + " Touren"} · ${fmtKm(e.km)}</title>` : ""}</rect>`;
        }
      }
      b.innerHTML = `<div class="slmos" aria-hidden="true">${mos}</div><svg class="slheat" viewBox="0 0 636 82" role="img" aria-label="${esc(`Kalender der letzten 52 Wochen: ${days} Aktive Tage`)}">${rects}</svg>` +
        `<div class="slhl2"><span class="mut">${days} Aktive Tage in den letzten 12 Monaten</span><span class="sllgh mut" aria-hidden="true">weniger ${[0, 1, 2, 3, 4].map(i => `<svg viewBox="0 0 10 10" width="12" height="12"><rect class="slh${i}" width="10" height="10" rx="2"/></svg>`).join("")} mehr</span></div>`;
      slPos(b);
      slBadge(c, `${days} Tage`);
    },
  },
  meilensteine: {
    fam: "uebersicht", cat: "plan", icon: "pin", name: "Meilensteine", title: () => "Meilensteine", filter: {range: null}, fields: [{kind: "sports"}, {kind: "title"}],
    desc: "Wie weit es bis zum nächsten runden Kilometerstand, zur nächsten Tour-Marke und zum nächsten „Mount Everest“ beim Aufstieg ist.",
    preview: () => slPvHbars([96, 58, 80]),
    render(c, b, cfg) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const TA = TOURS.filter(t => flSport(t, cfg));
      if (!TA.length) return flNone(b);
      const km = slSum(TA, t => t.km), up = slSum(TA, t => t.up_m || 0), n = TA.length, EV = 8849,
        step = (v, L) => {
          const nx = L.find(x => x > v), pv = nx ? [0, ...L].filter(x => x <= v).pop() : L[L.length - 1];
          return {nx, pv, p: nx ? ((v - pv) / (nx - pv)) * 100 : 100};
        },
        K = step(km, [100, 250, 500, 1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 30000, 40075]), N = step(n, [10, 25, 50, 100, 150, 200, 300, 400, 500, 750, 1000, 1500, 2000]),
        ev = up / EV, evn = Math.floor(ev) + 1,
        row = (lab, val, p, line) => `<li><div class="slr1"><span>${lab}</span><b>${val}</b></div>${slBr(p)}<p class="mut slr2">${line}</p></li>`;
      b.innerHTML = slRows([
        row("Strecke gesamt", slKm(km), K.p, K.nx ? `Noch ${slKm(K.nx - km)} bis ${fmtKm(K.nx, {d: 0})}` : "Alle Meilensteine erreicht: mehr als einmal um die Erde."),
        row("Aufstieg gesamt", `${nf(ev, ev >= 10 ? 0 : 1)} × Mount Everest`, (ev % 1) * 100, `Noch ${slHm(evn * EV - up)} bis zum nächsten Everest`),
        row("Touren gesamt", nf(n, 0), N.p, N.nx ? `Noch ${N.nx - n} bis ${N.nx} Touren` : "Alle Meilensteine erreicht."),
      ]);
      slBadge(c, K.nx ? `Noch ${slKm(K.nx - km)}` : "");
    },
  },
  wochentage: {
    fam: "uebersicht", cat: "grafik", icon: "met", name: "Lieblingstage und Tageszeiten", title: () => "Lieblingstage und Tageszeiten", defaults: {metric: "count"}, filter: {range: "all"},
    desc: "An welchen Wochentagen und zu welcher Tageszeit du am liebsten unterwegs bist, als zwei Säulendiagramme.",
    fields: [{k: "metric", kind: "radio", def: "count", label: "Zählen nach", options: [["count", "Anzahl der Touren"], ["km", "Strecke"], ["up", "Aufstieg"], ["h", "Dauer"]]}, {kind: "sports"}, {kind: "range", def: "all"}, {kind: "title"}],
    preview: () => slPvBars([20, 12, 14, 12, 24, 36, 30]),
    render(c, b, cfg) {
      const A = flSelect(cfg, "all").list, MT = FL_MET[cfg.metric] ? cfg.metric : "count";
      if (A.length < 3) return slNote(b, TOURS.length < 3 || !(cfg.sports || []).length && cfg.range == null ? "Dafür braucht es mindestens drei Touren." : "Mit diesem Filter gibt es weniger als drei Touren.");
      const wd = Array(7).fill(0), dp = Array(4).fill(0), PART = ["Morgens", "Mittags", "Nachmittags", "Abends"], PARTS = ["morgens", "mittags", "nachmittags", "abends"];
      A.forEach(t => {
        const h = +t.date.slice(11, 13), v = FL_MET[MT].f(t);
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
  /* 3.37.0 Jahreszeiten und Wetter: rechnet der Server (GET /api/bausteine/saison, app/bausteine_daten.py) aus Touren und den schon lokal gespeicherten Wetterdaten; hier wird nie ein Wetterdienst gefragt */
  saison: {
    fam: "uebersicht", cat: "grafik", icon: "cloud", name: "Jahreszeiten und Wetter", title: () => "Jahreszeiten und Wetter", defaults: {metric: "km"}, filter: {range: "all"},
    desc: "Wann du unterwegs bist: Touren und Strecke je Monat und je Jahreszeit. Wenn zu deinen Touren Wetterdaten gespeichert sind, kommen die Temperaturen dazu, sonst steht ein Hinweis da. Es wird nichts nachgeladen.",
    fields: [{k: "metric", kind: "radio", def: "km", label: "Säulen nach", options: [["km", "Strecke"], ["count", "Anzahl der Touren"]]}, {kind: "sports"}, {kind: "range", def: "all"}, {kind: "title"}],
    preview: () => slPvBars([8, 12, 20, 28, 34, 26, 30, 22, 16, 10, 6, 4]),
    async render(c, b, cfg) {
      const R = flRange(cfg, "all"), u = new URLSearchParams();
      if ((cfg.sports || []).length) u.set("sport", cfg.sports.join(","));
      if (R.kind === "all" || !R.from) u.set("zeitraum", "all");
      else {
        u.set("zeitraum", "c");
        u.set("von", R.from);
        u.set("bis", R.to);
      }
      const d = await slGet(`/api/bausteine/saison?${u}`);
      if (!d) return slNote(b, "Die Auswertung konnte nicht geladen werden.");
      if (!d.touren) return flNone(b, (cfg.sports || []).length || cfg.range ? "" : "Noch keine Touren.");
      const km = cfg.metric !== "count", val = x => (km ? x.km : x.touren), un = km ? "km" : "Touren", ZN = {fruehling: "Frühling", sommer: "Sommer", herbst: "Herbst", winter: "Winter"},
        ZM = {fruehling: "März bis Mai", sommer: "Juni bis August", herbst: "September bis November", winter: "Dezember bis Februar"}, wx = d.wetter || {}, has = wx.mit > 0,
        tt = x => `im Schnitt ${nf(x.t_mittel, 0)} °C (${nf(x.t_min, 0)} bis ${nf(x.t_max, 0)} °C)`,
        zmax = Math.max(...d.jahreszeiten.map(val), 1e-9), best = d.jahreszeiten.reduce((a, x) => (val(x) > val(a) ? x : a), d.jahreszeiten[0]),
        zrows = d.jahreszeiten.map(z => `<li${z === best ? ' class="slbest"' : ""}><div class="slr1"><span>${ZN[z.key]}</span><b>${nf(val(z), 0)} ${un}</b></div>${slBr((val(z) / zmax) * 100)}` +
          `<p class="mut slr2 slsegs">${slSegs([ZM[z.key], z.touren === 1 ? "1 Tour" : z.touren + " Touren", km ? "" : `${fmtKm(z.km, {d: 0})}`, z.mit_wetter ? tt(z) : ""])}</p></li>`),
        vals = d.monate.map(val), mb = vals.indexOf(Math.max(...vals));
      let h = `${val(best) > 0 ? `<p class="slcmp">Deine stärkste Jahreszeit: ${ZN[best.key]}.</p>` : ""}<p class="mut slcmpn">${d.touren === 1 ? "1 Tour" : d.touren + " Touren"} im gewählten Zeitraum, Jahreszeiten nach den Monaten der nördlichen Halbkugel.</p>` + slRows(zrows) +
        `<p class="slcmpn">Monate</p>` + slCols(vals, {hl: mb, label: `Säulendiagramm ${km ? "Strecke" : "Touren"} je Monat, am stärksten ${MONL[mb]} mit ${nf(vals[mb], 0)} ${un}`, labels: SL_MON, cls: "slsm"});
      if (has) h += `<div class="slxl sltmp" aria-hidden="true">${d.monate.map(m => `<span>${m.t_mittel == null ? "–" : nf(m.t_mittel, 0) + "°"}</span>`).join("")}</div><p class="mut slcmpn">Zeile unter den Monaten: durchschnittliche Temperatur der Touren in °C.</p>`;
      if (!has) h += '<p class="mut slnone slwx">Für diese Touren liegen noch keine Wetterdaten vor, deshalb gibt es keine Temperaturen. Sie werden beim Öffnen einer Tour oder in der Verwaltung mit „Wetter laden“ gespeichert; hier wird nichts abgerufen.</p>';
      else {
        const KL = {kalt: "Unter 0 °C", kuehl: "0 bis 10 °C", mild: "10 bis 20 °C", warm: "Ab 20 °C"}, kmax = Math.max(...wx.klassen.map(x => x.touren), 1);
        h += `<p class="slcmpn">Touren nach Temperatur</p>` + slRows(wx.klassen.map(k => `<li><div class="slr1"><span>${KL[k.key]}</span><b>${k.touren === 1 ? "1 Tour" : k.touren + " Touren"}</b></div>${slBr((k.touren / kmax) * 100)}<p class="mut slr2">${fmtKm(k.km, {d: 0})}</p></li>`)) +
          `<p class="mut slcmpn">${wx.ohne ? `Wetterdaten für ${wx.mit} von ${d.touren} Touren; die übrigen fehlen und zählen nicht mit (nie als 0 °C).` : `Wetterdaten für alle ${wx.mit} Touren.`} Gespeichertes Wetter, kein neuer Abruf.</p>`;
      }
      b.innerHTML = h;
      slPos(b);
      slBadge(c, ZN[best.key]);
    },
  },
  sportarten: {
    fam: "uebersicht", cat: "grafik", icon: "map", name: "Sportarten-Verteilung", title: () => "Sportarten-Verteilung", defaults: {metric: "count"}, filter: {range: "all"},
    desc: "Welche Sportarten du wie oft machst, als Ring mit Legende, nach Anzahl der Touren, Kilometern oder Zeit.",
    fields: [{k: "metric", kind: "radio", def: "count", label: "Verteilung nach", options: [["count", "Anzahl der Touren"], ["km", "Strecke"], ["time", "Dauer"]]}, {kind: "range", def: "all"}, {kind: "title"}],
    preview: () => slPvDonut([[0.5, "slsg slsg-hike"], [0.28, "slsg slsg-bike"], [0.14, "slsg slsg-ski"], [0.08, "slsg slsg-other"]]),
    render(c, b, cfg) {
      if (!TOURS.length) return slNote(b, "Noch keine Touren.");
      const A = flSelect({...cfg, sports: []}, "all").list;
      if (!A.length) return flNone(b);
      const m = cfg.metric === "km" ? t => t.km : cfg.metric === "time" ? t => t.h : () => 1, G = {};
      A.forEach(t => {
        const [name, cl] = slGroup(t.sport), g = (G[name] = G[name] || {name, cl, v: 0, n: 0});
        g.v += m(t);
        g.n++;
      });
      const L = Object.values(G).filter(g => g.v > 0).sort((x, y) => y.v - x.v), tot = slSum(L, g => g.v), C = 213.6, fmt = v => (cfg.metric === "km" ? slKm(v) : cfg.metric === "time" ? fmtDauer(v * 3600, {summe: true}) : nf(v, 0));
      if (!L.length) return slNote(b, "Für diese Auswertung fehlen Angaben in den Touren.");
      let off = 0;
      const segs = L.map(g => {
        const f = g.v / tot, s = `<circle class="slsg slsg-${g.cl}" cx="50" cy="50" r="34" stroke-dasharray="${Math.max(0.5, C * f - (L.length > 1 ? 1.6 : 0)).toFixed(1)} ${C}" stroke-dashoffset="${(-off * C).toFixed(1)}" transform="rotate(-90 50 50)"/>`;
        off += f;
        return s;
      }).join("");
      b.innerHTML = `<div class="slgoal"><div class="slring slsd"><svg viewBox="0 0 100 100" role="img" aria-label="Ringdiagramm der Sportarten" focusable="false"><circle class="t" cx="50" cy="50" r="34"/>${segs}</svg><div class="slrc"><b>${fmt(tot)}</b>${cfg.metric === "km" || cfg.metric === "time" ? "" : '<small class="mut">Touren</small>'}</div></div>` +
        `<ul class="slleg">${L.map(g => `<li><i class="slsq slsg slsg-${g.cl}"></i><span>${g.name}</span><b>${Math.round((g.v / tot) * 100)}\u00a0%</b><span class="mut">${fmt(g.v)}</span></li>`).join("")}</ul></div>`;
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
      /* 3.54.0: das Titelfoto der Tour (wie in der Tourenliste, mit Bildversion) statt je Besuch einer Anfrage; die gewürfelte Tour bleibt für diesen Tab bis zum nächsten Tag
         oder bis „Andere Tour“ – beim erneuten Öffnen der Übersicht dieselbe Tour und keine Bildanfrage */
      const hk = "mt_wied", day = slIso(new Date()), held = () => {
        try {
          const h = JSON.parse(sessionStorage.getItem(hk) || "null");
          return h && h.day === day && pool.find(t => t.id === h.id);
        } catch (e) {
          return null;
        }
      };
      const draw = async keep => {
        const others = pool.filter(t => !cur || t.id !== cur.id), t = (keep && held()) || others[Math.floor(Math.random() * others.length)] || pool[0],
          cv = t.photos ? await homeCovers().catch(() => null) : null, p = cv && cv[t.id];
        cur = t;
        try {
          sessionStorage.setItem(hk, JSON.stringify({day, id: t.id}));
        } catch (e) {}
        b.innerHTML = `<div class="slrd">${p ? `<img src="${picSrc({id: +p.id, v: esc(p.v || "")}, PH_STRIP_PX)}" width="112" height="112" alt="${esc(t.name)}" loading="lazy" decoding="async">` : '<span class="slrd-i" aria-hidden="true">⛰️</span>'}` +
          `<div class="slrdt"><a class="slrdn" href="#/tour/${slEnc(t.id)}">${esc(t.name)}</a><span class="mut">${fmtDatumKurz(t.date)} · ${slAgo(t.date)}</span><span class="mut">${fmtKm(t.km)} · ${fmtAuf(t.up_m || 0)} · ${fmtDauer(t.h * 3600)}</span>` +
          (pool.length > 1 ? '<button type="button" class="btn sm ghost" data-other>Andere Tour</button>' : "") + "</div></div>";
        const o = b.querySelector("[data-other]");
        if (o) o.onclick = () => draw().then(() => {
          const n = b.querySelector("[data-other]");
          if (n) n.focus();
        });
        slBadge(c, slAgo(t.date));
      };
      return draw(true);
    },
  },
  orte: {
    fam: "uebersicht", cat: "zahlen", icon: "pin", name: "Meistbesuchte Orte", title: () => "Meistbesuchte Orte", defaults: {level: "county"},
    desc: "Die Orte, Landkreise, Regionen, Gebiete oder Länder, in denen du die meisten Touren gemacht hast, als Balken.",
    fields: [{k: "level", kind: "radio", label: "Gliedern nach", options: [["place", "Ort"], ["county", "Landkreis"], ["state", "Bundesland oder Region"], ["gebiet", "Gebiet"], ["country", "Land"]]}],
    preview: () => slPvHbars([96, 70, 52, 30]),
    render(c, b, cfg) {
      const key = {place: "g_place", county: "g_county", state: "g_state", country: "g_country"}[cfg.level] || "g_county", G = {}, gb = cfg.level === "gebiet";       // 3.64.0: Gebiet = das genaueste Gebiet der Tour (jede Tour zählt einmal)
      let miss = 0;
      TOURS.forEach(t => {
        const k = gb ? ((Gebiete.von(t)[0] || {}).name || "") : (t[key] || "").trim();
        if (!k) return miss++;
        const g = (G[k] = G[k] || {k, n: 0, km: 0});
        g.n++;
        g.km += t.km;
      });
      const L = Object.values(G).sort((x, y) => y.n - x.n || y.km - x.km).slice(0, 8);
      if (!L.length) return slNote(b, gb ? "Noch keine Tour liegt in einem bekannten Gebiet." : "Noch keine Regionen bestimmt: Verwaltung → Touren holen → Komoot „Regionen bestimmen“.");
      b.innerHTML = slRows(L.map(g => `<li><div class="slr1"><span>${esc(g.k)}</span><b>${g.n === 1 ? "1 Tour" : g.n + " Touren"}</b></div>${slBr((g.n / L[0].n) * 100)}<p class="mut slr2">${slKm(g.km)}</p></li>`)) +
        (miss ? `<p class="mut slcap">${gb ? (miss === 1 ? "1 Tour ohne Gebiet" : miss + " Touren ohne Gebiet") : miss === 1 ? "1 Tour ohne Ortsangabe" : miss + " Touren ohne Ortsangabe"}</p>` : "");
      slBadge(c, esc(L[0].k));
    },
  },
  uhrenzeit: {
    fam: "uebersicht", cat: "grafik", icon: "watch", name: "Uhren und Geräte", title: () => "Uhren und Geräte",
    desc: "Deine Geräte (Uhren, Handys) auf einer Zeitleiste: wann du sie genutzt hast und wie viele Touren sie aufgezeichnet haben.",
    preview: () => slPrev('<svg viewBox="0 0 120 34" class="slpvs" aria-hidden="true"><rect class="slhz" x="0" y="2" width="120" height="8" rx="4"/><rect class="slhb" x="4" y="2" width="56" height="8" rx="4"/><rect class="slhz" x="0" y="14" width="120" height="8" rx="4"/><rect class="slhb" x="50" y="14" width="70" height="8" rx="4"/><rect class="slhz" x="0" y="26" width="120" height="8" rx="4"/><rect class="slhb" x="30" y="26" width="40" height="8" rx="4"/></svg>'),
    async render(c, b) {
      const d = await slGet("/api/my-devices"), devs = d && d.devices ? d.devices : [];
      if (!devs.length) return slNote(b, "Noch kein Gerät angelegt – unter Verwaltung → Touren holen → Meine Geräte.");
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
    fam: "uebersicht", cat: "plan", icon: "dot", name: "Ausrüstung", title: () => "Ausrüstung",
    desc: "Kilometerstand deiner Ausrüstung (Schuhe, Rad, Ski) gegen das Limit, mit Hinweis, wann ein Wechsel ansteht.",
    preview: () => slPvHbars([96, 70, 34]),
    async render(c, b) {
      const L = await slGet("/api/bausteine/ausruestung");
      if (!L || !L.length) return slNote(b, "Noch keine Ausrüstung angelegt.");
      const rank = g => (g.status === "over" ? 0 : g.status === "soon" ? 1 : 2), S = L.map((g, i) => [g, i]).sort((x, y) => rank(x[0]) - rank(y[0]) || x[1] - y[1]).map(x => x[0]);   // 3.37.0: Warnungen zuerst
      const rows = S.slice(0, 8).map(g => {
        const lim = g.limit_km, cls = g.status === "over" ? "bad" : g.status === "soon" ? "warn" : "", pct = lim ? Math.round((g.km / lim) * 100) : null,
          ic = g.status === "over" ? '<span class="slwi bad" aria-hidden="true">×</span>' : g.status === "soon" ? '<span class="slwi warn" aria-hidden="true">!</span>' : "",
          line = !lim ? "Ohne Limit" : g.status === "over" ? (g.km > lim ? `Limit überschritten um ${slKm(g.km - lim)}: Zeit für einen Wechsel` : "Limit erreicht: Zeit für einen Wechsel") : g.status === "soon" ? `Bald fällig: noch ${slKm(lim - g.km)}` : `Noch ${slKm(lim - g.km)}`;
        return `<li${cls ? ` class="slgw gw-${cls}"` : ""}><div class="slr1"><span>${ic}${esc(g.name)}</span><b>${lim ? `${nf(g.km, 0)} von ${slKm(lim)} (${pct}\u00a0%)` : slKm(g.km)}</b></div>${slBr(lim ? (g.km / lim) * 100 : 0, cls)}` +
          `<p class="mut slr2">${line}</p></li>`;
      });
      b.innerHTML = slRows(rows) + '<p><a href="#/places">Ausrüstung verwalten ›</a></p>';
      const due = L.filter(g => g.status === "over" || g.status === "soon").length;
      slBadge(c, due ? (due === 1 ? "1 bald fällig" : `${due} bald fällig`) : "");
    },
  },
  geplant: {
    fam: "uebersicht", cat: "plan", icon: "map", name: "Geplante Touren", title: () => "Geplante Touren", defaults: {},
    desc: "Die offenen geplanten Touren (noch nicht gegangen) mit Strecke, Aufstieg und geschätzter Dauer, mit Link zur Planung. Auf Wunsch auch gegangene geplante Touren mit dem Vergleich von geplanter und gelaufener Zeit. Verworfene geplante Touren erscheinen nie.",
    fields: [{k: "gegangen", kind: "bool", label: "Gegangene geplante Touren auch zeigen"}],
    preview: () => slPrev('<ul class="sllist"><li><b>Gipfelweg</b><span>8,0 km · 900 m</span></li><li><b>Rund um den See</b><span>12,5 km</span></li></ul>'),
    async render(c, b, cfg) {
      const mit = !!(cfg && cfg.gegangen === true), L = await slGet("/api/bausteine/geplant" + (mit ? "?gegangen=1" : "")), can = typeof isViewer === "function" ? !isViewer() : true;
      if (!L || !L.length) return (b.innerHTML = `<p class="mut slnone">Keine offenen geplanten Touren.</p>${can ? '<p><a href="#/plan">Tour planen ›</a></p>' : ""}`);
      const row = p => {
        const done = p.status === "gegangen", t = done ? p.tour : null,
          nm = can ? `<a href="#/plan/${p.id}">${esc(p.name || "Ohne Namen")}</a>` : `<b>${esc(p.name || "Ohne Namen")}</b>`,
          vals = [p.km != null ? slKm(p.km) : "", p.up ? slHm(p.up) : "", p.est_h ? fmtDauer(p.est_h * 3600, {summe: true}) : ""].filter(Boolean).join(" · ");
        if (!done) return `<li>${nm}<span class="mut">${vals}</span></li>`;
        const cmp = t && p.est_h && t.h ? `<span>geplant ${hmm(p.est_h)}</span> · <span>gelaufen ${hmm(t.h)} (${hmSigned(t.h - p.est_h)})</span>`
          : t && p.km && t.km ? `<span>Strecke: geplant ${fmtKm(p.km)}, gelaufen ${fmtKm(t.km)} (${nSigned(t.km - p.km, 1)}\u00a0km)</span>` : "";
        return `<li class="slgone">${nm}<span class="mut"><span aria-hidden="true">✓</span> ${t && t.start_ts ? `gegangen am ${esc(planDate(t.start_ts))}` : "gegangen"}</span>${cmp ? `<small class="mut slgcmp">${cmp}</small>` : ""}</li>`;
      };
      b.innerHTML = `<ul class="sllist">${[...L.filter(p => p.status !== "gegangen"), ...L.filter(p => p.status === "gegangen")].slice(0, 5).map(row).join("")}</ul>` + (can ? '<p><a href="#/plan">Tour planen ›</a></p>' : "");
      const open = L.filter(p => p.status !== "gegangen").length;
      slBadge(c, open === 1 ? "1 geplante Tour" : open ? `${open} geplante Touren` : "");
    },
  },
  /* Schlüssel bleibt „zeppimport“ (gespeicherte Layouts und Ansichten); seit 3.31.0 der Baustein „Touren holen“. 3.48.0: Einstellung „Darstellung“ Karte oder Nur Knopf
     (der frühere Baustein „Touren holen (nur Knopf)“, Kennung holenknopf, wird über SL_ALIAS / app/baustein_umzug.py darauf abgebildet). */
  zeppimport: {
    fam: "uebersicht", cat: "quellen", icon: "watch", name: "Touren holen", title: () => "Touren holen", defaults: {}, filter: {range: null},
    desc: "Startet den Import deiner Touren aus dem Konto deiner Uhr (Zepp, Garmin oder Suunto) mit einem Tipp, zeigt den Fortschritt und wie der letzte Lauf ausging. Bei mehreren Konten gibt es je Konto eine Zeile und „Alle Touren holen“. Fehlt die Verbindung, führt ein Knopf zur Einrichtung. Als „Nur Knopf“ bleibt ein einziger Knopf (bei mehreren Konten mit kleinem Menü) mit Statuszeile, für alle, die ihn lieber im Raster haben als in der Kopfzeile. Für Betrachter unsichtbar.",
    fields: [{k: "view", kind: "radio", def: "karte", label: "Darstellung", options: [["karte", "Karte mit Fortschritt"], ["knopf", "Nur Knopf"]]}],
    preview: () => slPrev('<span class="zpi-pv"><b>Touren holen</b></span>'),
    render(c, b, cfg) {
      if (typeof isViewer === "function" && isViewer()) {                     // Betrachter dürfen nichts starten (der Server lehnt es ohnehin ab): Karte bleibt unsichtbar
        c.dataset.hn = "aus";
        return;
      }
      if (cfg && cfg.view === "knopf") {
        c.dataset.zk = "1";
        c.classList.add("zpk");
      } else {
        delete c.dataset.zk;
        c.classList.remove("zpk");
      }
      ZI.cards.add(c);
      ziHook();
      ziPaint(c);
      return ziTick();
    },
  },
  rueckblick: {
    fam: "uebersicht", cat: "rueck", icon: "trend", name: "Jahresrückblick", title: cfg => `Jahresrückblick ${slRbRange(cfg).year}`, multi: true, defaults: {}, filter: {range: "year"},
    desc: "Das Jahr in einem Baustein: Touren, Strecke und Aufstieg, die Monate als Säulen, die längste und die höchste Tour.",
    fields: [{kind: "range", opts: ["year", "y"], def: "year", label: "Jahr"}, {kind: "sports"}, {kind: "title"}],
    preview: () => slPvBars([8, 14, 20, 30, 26, 34, 28, 22, 14, 12, 6, 4]),
    render(c, b, cfg) {
      const y = slRbRange(cfg).year, A = TOURS.filter(t => t.y === y && flSport(t, cfg));
      if (!A.length) return slNote(b, (cfg.sports || []).length ? "Mit diesem Filter gab es in diesem Jahr keine Touren." : `Im Jahr ${y} gab es keine Touren.`);
      const mk = Array(12).fill(0), mn = Array(12).fill(0);
      A.forEach(t => {
        mk[t.m - 1] += t.km;
        mn[t.m - 1]++;
      });
      const best = mk.indexOf(Math.max(...mk)), L = A.reduce((m, t) => (t.km > m.km ? t : m)), U = A.reduce((m, t) => ((t.up_m || 0) > (m.up_m || 0) ? t : m)),
        tile = (t, v, l) => `<a class="utile slrec" href="#/tour/${slEnc(t.id)}"><b>${v}</b><span>${l}</span><small class="mut">${esc(t.name)} · ${fmtDatumKurz(t.date)}</small></a>`;
      b.innerHTML = slTiles([[nf(A.length, 0), A.length === 1 ? "Tour" : "Touren"], [slKm(slSum(A, t => t.km)), "Strecke"], [slHm(slSum(A, t => t.up_m || 0)), "Aufstieg"]]) +
        `<p class="slcmpn">Strecke je Monat</p>${slCols(mk, {hl: best, label: `Säulendiagramm der Strecke je Monat, am meisten im ${SL_MON[best]}`, labels: SL_MON, cls: "slsm"})}` +
        `<div class="utiles">${tile(L, fmtKm(L.km), "Längste Tour")}${U.up_m ? tile(U, slHm(U.up_m), "Größter Aufstieg") : ""}<div class="utile"><b>${SL_MON[best]}</b><span>Aktivster Monat</span><small class="mut">${slKm(mk[best])} · ${mn[best] === 1 ? "1 Tour" : mn[best] + " Touren"}</small></div></div>`;
      slBadge(c, `${fmtKm(slSum(A, t => t.km), {d: 0})}`);
    },
  },
});

/* =====================  3.30.0 Zepp-Import, seit 3.31.0 „Touren holen“ je nach Uhr  =====================
   Ein Zustand für alle Karten dieses Typs (ZI): Job-Stand aus GET /api/jobs, Quellen und letzte Läufe aus GET /api/import-quellen (Zepp, Garmin, Suunto; dazu Marken aus „Meine Geräte“).
   Eine verbundene Quelle: Knopf „<Marke>-Import starten“. Mehrere: je Quelle eine Zeile plus „Alle Touren holen“ (nacheinander, nie parallel; der Server lässt ohnehin nur einen Job zu).
   Keine Quelle: „<Marke> einrichten“ bzw. Hinweis auf den Dateiimport (Polar, Handy, Anderes haben keinen Konto-Import). Solange ein Lauf läuft, fragt die Karte alle 1,5 s nach;
   danach werden die Touren neu geladen. Kein Doppelstart: Knöpfe gesperrt, solange irgendein Job läuft. */
const ZI_JOBS = {zepp: ["Zepp-Import (ohne Upload)", "export"], garmin: ["Garmin-Import", "garmin-import"], suunto: ["Suunto-Import", "suunto-import"]};     // Art -> [Jobname im Server, Schlüssel in POST /api/jobs/<Schlüssel>]
const ZI_ADMIN = "#/admin?tab=quellen";
const ZI = {cards: new Set(), quick: new Set(), job: null, q: null, tm: null, watch: false, busy: false, err: "", loaded: false, queue: [], open: null, hooked: false};
const ziRun = () => !!(ZI.job && ZI.job.running);
const ziKind = () => (ziRun() ? Object.keys(ZI_JOBS).find(k => ZI_JOBS[k][0] === ZI.job.running) || null : null);
const ziMine = () => !!ziKind();
const ziAcc = () => (ZI.q ? ZI.q.quellen.filter(x => x.verbunden) : []);
const ziBusy = () => ziMine() || ZI.busy || ZI.queue.length > 0;
const ziLab = k => ((ZI.q && ZI.q.quellen.find(x => x.kind === k)) || {}).label || k;
const ziNext = () => ziKind() || ZI.queue[0] || (ZI.busy && ZI.cur) || "";
function ziWhen(ts) {
  const same = new Date(ts * 1000).toDateString() === new Date().toDateString();
  return same ? fmtUhrzeit(ts) : fmtDatumKurz(ts, {zeit: true});
}
const ziN = (n, one, many) => (n === 1 ? one : many.replace("{}", nf(n, 0)));
/* Was die Oberfläche anbietet: load (Stand fehlt), one (genau ein Konto), many (mehrere), setup (Konto einrichten), file (nur Dateiimport) */
function ziMode() {
  if (!ZI.q) return {t: ZI.loaded ? "err" : "load"};
  const acc = ziAcc(), g = ZI.q.geraete || [], kb = g.filter(x => x.konto), fb = g.filter(x => !x.konto);
  if (acc.length === 1) return {t: "one", src: acc[0], fb};
  if (acc.length > 1) return {t: "many", acc, fb};
  if (kb.length === 1) return {t: "setup", txt: `${kb[0].label} einrichten`, brand: kb[0].kind, kb, fb};
  if (kb.length > 1 || !fb.length) return {t: "setup", txt: "Touren holen einrichten", brand: "", kb, fb};
  return {t: "file", txt: fb.length === 1 ? `${fb[0].label}: Touren per Datei importieren` : "Touren per Datei importieren", fb};
}
const ziFileRows = fb => fb.map(x => `<p class="zpm"><a href="${ZI_ADMIN}">${esc(`${x.label}: Touren per Datei importieren ›`)}</a></p>`);
function ziStatus(s) {                                                           // Zeilen zum letzten Lauf einer Quelle
  const last = s.letzter, rows = [], L = s.label, zepp = s.kind === "zepp";
  if (!last) return ['<p class="zpm">Noch kein Import gestartet.</p>'];
  if (last.ok) {
    const l = [];
    if (zepp) l.push(last.neu ? ziN(last.neu, "1 neues Training gefunden", "{} neue Trainings gefunden") : "Keine neuen Trainings.");
    else l.push(last.neu ? ziN(last.neu, "1 neue Tour übernommen", "{} neue Touren übernommen") : "Keine neuen Touren.");
    if (zepp && last.uebernommen) l.push(ziN(last.uebernommen, "1 als Tour übernommen", "{} als Tour übernommen"));
    if (!zepp && last.dup) l.push(`${nf(last.dup, 0)} schon vorhanden`);
    if (last.ohne_gps) l.push(ziN(last.ohne_gps, "1 ohne GPS-Daten vermerkt", "{} ohne GPS-Daten vermerkt"));
    if (last.fehler) l.push(ziN(last.fehler, "1 konnte nicht geladen werden", "{} konnten nicht geladen werden"));
    rows.push(`<p class="zpm zpok">${esc(`Letzter Lauf: ${ziWhen(last.ts)}`)}</p><ul class="zpl">${l.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`);
    if (zepp && last.gps && !last.uebernommen) rows.push(`<p class="zpm"><a href="${ZI_ADMIN}">Neue Zepp-Trainings holen (Verwaltung → Touren holen) ›</a></p>`);
    return rows;
  }
  const why = zepp
    ? {kein_zugang: "Der Zepp-Zugang fehlt.", anmeldung: "Zepp hat die Anmeldung abgelehnt. Hole in der Verwaltung ein neues Token.", netz: "Zepp war nicht erreichbar. Prüfe die Internetverbindung und versuche es noch einmal."}[last.code]
    : {kein_zugang: `Für ${L} fehlt noch die Verbindung. Richte sie in der Verwaltung ein.`, anmeldung: `${L} hat die Anmeldung abgelehnt. Verbinde das Konto in der Verwaltung neu.`, netz: `${L} war nicht erreichbar. Prüfe die Internetverbindung und versuche es noch einmal.`}[last.code];
  return [`<p class="zpm zpbad">${esc(`Der letzte Import (${ziWhen(last.ts)}) ist fehlgeschlagen.`)}</p><p class="zpm">${why ? esc(why) : esc(`Meldung: ${last.meldung || ""}`)}</p><p class="zpm"><a href="${ZI_ADMIN}">Zugang in der Verwaltung prüfen ›</a></p>`];
}
function ziProgress(s) {                                                         // Fortschritt des laufenden Laufs dieser Quelle
  const j = ZI.job, tot = j.total || 0, done = j.done || 0, zepp = s.kind === "zepp";
  return tot ? `<p class="zpm">${esc(zepp ? `Training ${Math.min(tot, done + 1)} von ${tot}` : `Tour ${Math.min(tot, done + 1)} von ${tot}`)}</p>${slBr((done / tot) * 100)}` : `<p class="zpm">${esc(zepp ? "Verbinde mit Zepp …" : `Verbinde mit ${s.label} …`)}</p>`;
}
function ziSrc(s, mode, other) {                                                 // eine Quelle: Knopf und Stand (.zpi)
  const mine = ziKind() === s.kind, wait = !mine && ZI.queue.includes(s.kind), run = mine || (ZI.busy && ZI.cur === s.kind), off = ziBusy() || other;
  const btn = `<button type="button" class="btn zpb${run ? " zprun" : ""}" data-a="start" data-k="${s.kind}"${off ? " disabled" : ""}${run ? ' aria-busy="true"' : ""}><i class="zpic" aria-hidden="true">⟳</i><span>${run ? "Import läuft …" : `${s.label}-Import starten`}</span></button>`;
  let rows;
  if (mine) rows = [ziProgress(s)];
  else if (wait) rows = ['<p class="zpm">Kommt gleich dran.</p>'];
  else rows = ziStatus(s);
  return `<div class="zpi" data-k="${s.kind}">${btn}<div class="zpt" role="status" aria-live="polite">${rows.join("")}</div></div>`;
}
/* Baustein „Touren-Knopf“ (3.31.0): nur der beschriftete Start-Knopf (bei mehreren Quellen mit Menü) und eine Statuszeile, kompakt für drittel/halb */
function ziSum(s) {
  const l = s.letzter, zepp = s.kind === "zepp";
  if (!l) return {c: "", t: "Noch kein Import gestartet."};
  if (!l.ok) return {c: "zpbad", t: "Letzter Import fehlgeschlagen", bad: true};
  const n = zepp ? (l.neu ? ziN(l.neu, "1 neues Training gefunden", "{} neue Trainings gefunden") : "Keine neuen Trainings.") : l.neu ? ziN(l.neu, "1 neue Tour übernommen", "{} neue Touren übernommen") : "Keine neuen Touren.";
  return {c: "zpok", t: `Letzter Lauf: ${ziWhen(l.ts)} · ${n}`};
}
function ziPaintKnopf(c) {
  const b = c.querySelector(".tlsb");
  if (!b) return;
  const m = ziMode(), mine = ziMine(), other = ziRun() && !mine, run = ziBusy(), rows = [];
  let btn = "", bad = false;
  if (other) rows.push(`<p class="zpm">${esc(`Es läuft gerade ein anderer Vorgang: ${ZI.job.running}`)}</p>`);
  else if (ZI.err) rows.push(`<p class="zpm zpbad">${esc(`Import starten nicht möglich: ${ZI.err}`)}</p>`);
  const ic = '<i class="zpic" aria-hidden="true">⟳</i>', lnk = `<p class="zpm"><a href="${ZI_ADMIN}">Zugang in der Verwaltung prüfen ›</a></p>`;
  if (m.t === "load" || m.t === "err") {
    btn = `<button type="button" class="btn zpb" disabled><span>Touren holen</span></button>`;
    rows.push(`<p class="zpm">${m.t === "load" ? "Status wird geladen …" : "Der Status konnte nicht geladen werden."}</p>`);
  } else if (m.t === "one" || m.t === "many") {
    const acc = m.t === "one" ? [m.src] : m.acc, rs = mine ? ziAcc().find(x => x.kind === ziKind()) : null;
    bad = !run && acc.some(x => x.letzter && !x.letzter.ok);
    if (m.t === "one") {
      btn = `<button type="button" class="btn zpb${run ? " zprun" : ""}" data-a="start" data-k="${m.src.kind}"${run || other ? " disabled" : ""}${run ? ' aria-busy="true"' : ""}>${ic}<span>${run ? "Import läuft …" : `${m.src.label}-Import starten`}</span></button>`;
    } else {
      btn = `<div class="zpanc"><button type="button" class="btn zpb zpmb${run ? " zprun" : ""}" data-a="menu" aria-haspopup="menu" aria-expanded="false"${run || other ? " disabled" : ""}${run ? ' aria-busy="true"' : ""}>${ic}<span>${run ? "Import läuft …" : "Touren holen"}</span>${run ? "" : '<i class="zpcar" aria-hidden="true">▾</i>'}</button><div class="zpmenu" role="menu" aria-label="Touren holen" hidden>${ziItems()}</div></div>`;
    }
    if (rs && !other) rows.push(ziProgress(rs));
    if (!rs && !other && !ZI.err) acc.forEach(x => {
      const u = ziSum(x);
      rows.push(m.t === "one" ? `<p class="zpm ${u.c}">${esc(u.t)}</p>${u.bad ? lnk : ""}` : `<p class="zpm ${u.c}"><b>${esc(x.label)}</b> <span>${esc(u.t)}</span></p>`);
    });
    if (m.t === "many" && !rs && !other && acc.some(x => ziSum(x).bad)) rows.push(lnk);
    if (m.fb.length) rows.push(...ziFileRows(m.fb));
  } else if (m.t === "setup") {
    btn = `<a class="btn zpb" href="${ZI_ADMIN}"><span>${esc(m.txt)}</span></a>`;
    rows.push(`<p class="zpm">${esc(m.brand ? "Hier fehlt noch die Verbindung zum Konto deiner Uhr." : "Noch keine Quelle eingerichtet.")}</p>`);
    rows.push(...ziFileRows(m.fb));
  } else rows.push(...ziFileRows(m.fb));
  const html = `<div class="zpbox"><div class="zpi">${btn}<div class="zpt" role="status" aria-live="polite">${rows.join("")}</div></div></div>`;
  if (b.dataset.zp !== html) {
    b.dataset.zp = html;
    b.innerHTML = html;
    b.querySelectorAll("[data-a=start]").forEach(k => (k.onclick = () => ziStart(k.dataset.k)));
    const mb = b.querySelector("[data-a=menu]");
    if (mb) {
      ziWireMenu(mb.nextElementSibling);
      mb.onclick = () => (ZI.open === mb ? ziMenuClose(true) : ziMenuOpen(mb));
    }
  }
  slBadge(c, mine ? "läuft" : bad ? "Fehler" : "");
}
function ziPaint(c) {
  if (c.dataset.zk) return ziPaintKnopf(c);
  const b = c.querySelector(".tlsb");
  if (!b) return;
  const m = ziMode(), mine = ziMine(), other = ziRun() && !mine, run = ziBusy(), glob = [];
  let html = "", bad = false;
  if (other) glob.push(`<p class="zpm">${esc(`Es läuft gerade ein anderer Vorgang: ${ZI.job.running}`)}</p>`);
  else if (ZI.err) glob.push(`<p class="zpm zpbad">${esc(`Import starten nicht möglich: ${ZI.err}`)}</p>`);
  if (m.t === "load" || m.t === "err") {
    html = `<div class="zpi"><button type="button" class="btn zpb" disabled><span>Touren holen</span></button><div class="zpt" role="status" aria-live="polite"><p class="zpm">${m.t === "load" ? "Status wird geladen …" : "Der Status konnte nicht geladen werden."}</p></div></div>`;
  } else if (m.t === "one") {
    const s = m.src;
    bad = !run && !!s.letzter && !s.letzter.ok;
    const one = ziSrc(s, m, other);
    html = glob.length && !mine ? one.replace('role="status" aria-live="polite">', 'role="status" aria-live="polite">' + glob.join("")).replace(/(<div class="zpt"[^>]*>)(.*?)(<p class="zpm[^"]*">Noch kein|<p class="zpm zpok|<p class="zpm zpbad)/s, "$1$2$3") : one;
    if (glob.length && !mine) html = one.replace(/(<div class="zpt"[^>]*>)[\s\S]*<\/div><\/div>$/, `$1${glob.join("")}</div></div>`);   // Hinweis ersetzt den Stand wie in 3.30.0
    if (m.fb.length) html += ziFileRows(m.fb).join("");
  } else if (m.t === "many") {
    bad = !run && m.acc.some(s => s.letzter && !s.letzter.ok);
    html = `<div class="zpq"><button type="button" class="btn ghost zpall" data-a="all"${run || other ? " disabled" : ""}${run ? ' aria-busy="true"' : ""}><i class="zpic" aria-hidden="true">⟳</i><span>Alle Touren holen</span></button>${glob.length ? `<div class="zpt" role="status" aria-live="polite">${glob.join("")}</div>` : ""}` +
      m.acc.map(s => `<section class="zpsrc" aria-label="${esc(s.label)}"><h3 class="zph">${esc(s.label)}</h3>${ziSrc(s, m, other)}</section>`).join("") + ziFileRows(m.fb).join("") + "</div>";
  } else if (m.t === "setup") {
    const msg = !m.brand ? (m.kb.length ? `Du hast mehrere Uhren angelegt, aber noch kein Konto verbunden. Verbinde in der Verwaltung: ${m.kb.map(x => x.label).join(", ")}.` : "Noch keine Quelle eingerichtet. Verbinde in der Verwaltung dein Zepp-, Garmin- oder Suunto-Konto oder importiere Tourendateien.")
      : m.brand === "zepp" ? "Für den Import fehlt noch der Zepp-Zugang. Trage ihn in der Verwaltung ein." : `Für ${m.kb[0].label} fehlt noch die Verbindung. Richte sie in der Verwaltung ein.`;
    html = `<div class="zpi"><a class="btn zpb" href="${ZI_ADMIN}"><span>${esc(m.txt)}</span></a><div class="zpt" role="status" aria-live="polite"><p class="zpm">${esc(msg)}</p>${ziFileRows(m.fb).join("")}</div></div>`;
  } else {
    html = `<div class="zpi"><div class="zpt" role="status" aria-live="polite">${ziFileRows(m.fb).join("")}<p class="zpm zpmut">Eine Uhr ohne Konto-Anbindung liefert Touren als Dateien (FIT, GPX, TCX oder ZIP).</p></div></div>`;
  }
  html = `<div class="zpbox">${html}</div>`;
  if (b.dataset.zp !== html) {
    b.dataset.zp = html;
    b.innerHTML = html;
    b.querySelectorAll("[data-a=start]").forEach(k => (k.onclick = () => ziStart(k.dataset.k)));
    const al = b.querySelector("[data-a=all]");
    if (al) al.onclick = ziAll;
  }
  slBadge(c, mine ? "läuft" : bad && !run ? "Fehler" : "");
}
const ziPaintAll = () => {
  if (ZI.open && !ZI.open.isConnected) ZI.open = null;
  ZI.cards.forEach(c => (c.isConnected ? ziPaint(c) : ZI.cards.delete(c)));
  ZI.quick.forEach(q => {                                                         // der Knopf wird erst nach dem Aufbau in die Seite gesetzt: erst entfernen, wenn er einmal dort stand
    if (q.isConnected) q.dataset.seen = "1";
    if (q.isConnected || !q.dataset.seen) ziPaintQuick(q);
    else ZI.quick.delete(q);
  });
};
/* ---- Menü bei mehreren Quellen (Schnell-Knopf und Baustein „Touren-Knopf“): ein Eintrag je Quelle plus „Alle Touren holen“; schließt bei Klick außerhalb, Escape und Tab ---- */
const ziMenuOf = a => (a && a.nextElementSibling && a.nextElementSibling.classList.contains("zpmenu") ? a.nextElementSibling : null);
const ziItems = () => ziAcc().map(s => `<button type="button" role="menuitem" class="zpmi" data-k="${s.kind}"><span>${esc(`${s.label}-Import starten`)}</span></button>`).join("") + '<button type="button" role="menuitem" class="zpmi zpmall" data-k="alle"><span>Alle Touren holen</span></button>';
function ziWireMenu(m) {
  m.onclick = e => {
    const k = e.target.closest("[data-k]");
    if (!k || k.disabled) return;
    ziMenuClose(false);
    if (k.dataset.k === "alle") ziAll();
    else ziStart(k.dataset.k);
  };
  m.onkeydown = e => {
    const it = [...m.querySelectorAll("button:not(:disabled)")], i = it.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Home" || e.key === "End") {
      e.preventDefault();
      if (it.length) it[e.key === "Home" ? 0 : e.key === "End" ? it.length - 1 : (i + (e.key === "ArrowDown" ? 1 : -1) + it.length) % it.length].focus();
    } else if (e.key === "Tab") ziMenuClose(false);
  };
}
function ziMenuEl(a) {                                                            // Menü hinter dem Knopf (beim Schnell-Knopf erst bei Bedarf angelegt)
  let m = ziMenuOf(a);
  if (!m) {
    m = document.createElement("div");
    m.className = "zpmenu";
    if (a.id === "slzepp") m.id = "slzmenu";
    m.setAttribute("role", "menu");
    m.setAttribute("aria-label", "Touren holen");
    m.hidden = true;
    ziWireMenu(m);
    a.after(m);
  }
  return m;
}
function ziMenuClose(focus) {
  const a = ZI.open, m = ziMenuOf(a);
  ZI.open = null;
  if (m) m.hidden = true;
  if (a) a.setAttribute("aria-expanded", "false");
  if (focus && a && a.isConnected) a.focus();
}
function ziMenuOpen(a) {
  if (ZI.open && ZI.open !== a) ziMenuClose(false);
  const m = ziMenuEl(a), w = a.offsetParent || a.parentNode;
  if (!m.children.length) m.innerHTML = ziItems();
  m.style.setProperty("--zt", `${a.offsetTop + a.offsetHeight + 6}px`);          // Lage unter dem Knopf (berechnete Werte, daher per Skript)
  m.style.setProperty("--zr", `${Math.max(0, w.clientWidth - a.offsetLeft - a.offsetWidth)}px`);
  m.hidden = false;
  ZI.open = a;
  a.setAttribute("aria-expanded", "true");
  const f = m.querySelector("button:not(:disabled)");
  if (f) f.focus();
}
function ziHook() {                                                               // einmalig: Klick außerhalb und Escape schließen das Menü
  if (ZI.hooked) return;
  ZI.hooked = true;
  document.addEventListener("pointerdown", e => {
    if (ZI.open && !e.target.closest(".zpmenu") && !ZI.open.contains(e.target)) ziMenuClose(false);
  }, true);
  document.addEventListener("keydown", e => {
    if (ZI.open && e.key === "Escape") {
      e.preventDefault();
      ziMenuClose(true);
    }
  });
  window.addEventListener("hashchange", () => ziMenuClose(false));
}
/* ---- Schnell-Knopf in der Kopfzeile der Übersicht (neben „Seite anpassen“): Beschriftung je nach Quelle; abschaltbar in „Seite anpassen“ (Layout-Feld kopf.holen) ---- */
function ziQuickGo(q) {
  const m = ziMode();
  if (m.t === "err") return ziTick();
  if (m.t === "one") return ziStart(m.src.kind);
  if (m.t === "many") return ZI.open === q ? ziMenuClose(true) : ziMenuOpen(q);
  if (m.t === "setup" || m.t === "file") location.hash = ZI_ADMIN;
}
function ziQuick(w) {
  if (typeof isViewer === "function" && isViewer()) return;
  let q = w.querySelector("#slzepp");
  if (typeof slHolenOn === "function" && !slHolenOn()) {                          // in „Seite anpassen“ abgeschaltet: Knopf und Menü verschwinden
    if (q) {
      ZI.quick.delete(q);
      if (ZI.open === q) ZI.open = null;
      const m = ziMenuOf(q);
      if (m) m.remove();
      q.remove();
    }
    return;
  }
  ziHook();
  if (!q) {
    q = document.createElement("button");
    q.type = "button";
    q.id = "slzepp";
    q.className = "btn ghost sm";
    q.onclick = () => ziQuickGo(q);
    w.insertBefore(q, w.firstChild);
  }
  ZI.quick.add(q);
  ziPaintQuick(q);
  if (!ZI.loaded && !ZI.tm) ziTick();
}
function ziPaintQuick(q) {
  const m = ziMode(), run = ziBusy(), accs = ziAcc(), bad = !run && accs.some(s => s.letzter && !s.letzter.ok), key = `${m.t}|${m.txt || ""}|${m.t === "one" ? m.src.label : ""}|${run}|${ziNext()}|${bad}|${ziRun()}|${m.t === "many" ? accs.map(s => s.kind).join() : ""}`;
  if (q.dataset.k === key) return;
  q.dataset.k = key;
  const ic = '<i class="zpic" aria-hidden="true">⟳</i>';
  let txt, tip, go = true;
  if (run) {
    txt = `${ziLab(ziNext() || (m.src || {}).kind)}-Abruf läuft …`;
    tip = txt;
  } else if (m.t === "one") {
    txt = bad ? `${m.src.label} (Fehler)` : m.src.label;
    tip = `${m.src.label}-Import starten`;
  } else if (m.t === "many") {
    txt = bad ? "Touren holen (Fehler)" : "Touren holen";
    tip = "Touren holen";
  } else if (m.t === "setup" || m.t === "file") {
    txt = tip = m.txt;
    go = false;
  } else {
    txt = tip = "Touren holen";
  }
  q.classList.toggle("zprun", run);
  q.disabled = ziRun() || ZI.busy || m.t === "load";
  q.setAttribute("aria-busy", String(run));
  q.setAttribute("aria-label", tip);
  q.title = tip;
  if (m.t === "many" && !run) {
    q.setAttribute("aria-haspopup", "menu");
    q.setAttribute("aria-expanded", String(ZI.open === q));
    q.setAttribute("aria-controls", "slzmenu");
  } else {
    ["aria-haspopup", "aria-expanded", "aria-controls"].forEach(a => q.removeAttribute(a));
  }
  q.innerHTML = `${go ? ic : ""}<span>${esc(txt)}</span>${m.t === "many" && !run ? '<i class="zpcar" aria-hidden="true">▾</i>' : ""}`;
  const mn = ziMenuOf(q);
  if (m.t === "many") {
    const me = ziMenuEl(q), items = ziItems();
    if (me.dataset.k !== items) {
      me.dataset.k = items;
      me.innerHTML = items;
    }
  } else if (mn) {
    mn.remove();
    if (ZI.open === q) ZI.open = null;
  }
  if (run && ZI.open === q) ziMenuClose(false);
}
/* Stand holen (erst der Job, dann die Quellen: der Lauf trägt sein Ergebnis ein, bevor er als beendet gilt), malen, bei Bedarf weiter fragen */
async function ziTick() {
  clearTimeout(ZI.tm);
  ZI.tm = null;
  ziPaintAll();
  if (!ZI.cards.size && !ZI.quick.size) return;
  const j = await slGet("/api/jobs");
  if (j) ZI.job = j;
  const s = await slGet("/api/import-quellen");
  if (s && Array.isArray(s.quellen)) ZI.q = s;
  ZI.loaded = true;
  if (ziMine()) ZI.watch = true;
  const fin = ZI.watch && !ZI.busy && !ziRun();
  if (fin) ZI.watch = false;
  ziPaintAll();
  if (fin && ZI.job && ZI.job.ok && typeof loadTours === "function") {      // fertig: neue Touren in die Übersicht (und alle Abschnitte, die sie zeigen)
    try {
      ROUTES = null;
      await loadTours();
      if (/^#?\/?(dash)?$/.test(location.hash)) await route();
    } catch (e) {}
  }
  if (!ziRun() && !ZI.busy && ZI.queue.length) return ziStart(ZI.queue.shift(), true);         // „Alle Touren holen“: die nächste Quelle erst, wenn die vorige fertig ist
  if ((ZI.cards.size || ZI.quick.size) && (ziRun() || ZI.busy || ZI.watch || ZI.queue.length)) ZI.tm = setTimeout(ziTick, 1500);
}
async function ziStart(kind, queued) {
  if (!ZI_JOBS[kind] || ZI.busy || (ziRun() && !queued)) return;
  ZI.busy = true;
  ZI.cur = kind;
  ZI.err = "";
  ziPaintAll();
  try {
    await api("/api/jobs/" + ZI_JOBS[kind][1], {method: "POST"});
    ZI.watch = true;
    ZI.job = {...(ZI.job || {}), running: ZI_JOBS[kind][0], progress: "", done: null, total: null, ok: null};
  } catch (e) {
    if (queued && /409|läuft bereits/.test(String((e && e.message) || e))) ZI.queue.unshift(kind);       // noch beschäftigt: gleich noch einmal versuchen
    else {
      ZI.err = String((e && e.message) || e);
      ZI.queue = [];
    }
  }
  ZI.busy = false;
  ZI.cur = "";
  await ziTick();
}
function ziAll() {
  const k = ziAcc().map(x => x.kind);
  if (!k.length || ZI.busy || ziRun() || ZI.queue.length) return;
  ZI.queue = k.slice(1);
  return ziStart(k[0]);
}

/* =====================  3.19.0 „Dein Jahr“ als Baustein  =====================
   Gerüst wie der frühere feste Block der Startseite (41-startseite.js): Überschrift mit Vorjahresvergleich und Link, Kennzahlen, Monatssäulen, Jahresziele.
   Ohne Konfiguration identisch zu 3.18.x (laufendes Jahr, alle Sportarten, vier Kennzahlen, Vergleich mit dem Vorjahr bis heute). Die Standard-Instanz hat die Kennung „hyear“,
   weitere Instanzen „tlw-<id>“. Zeitraum und Sportart: flSelect() in 53-filter.js. */
const SL_JM = ["count", "km", "up", "h"];
/* Säulen des Verlaufs je Zeitraumart: {vals, labels, tips, cur}; Einheit je Kennzahl */
function slYearSeries(list, R, m, now) {
  const f = FL_MET[m].f, fmt = FL_MET[m].fmt, vals = [], labels = [], tips = [];
  let cur = -1, step = "Monat";
  if (R.kind === "year" || R.kind === "y") {
    for (let i = 0; i < 12; i++) {
      vals.push(0);
      labels.push(MON[i].slice(0, 1));
      tips.push(MONL[i]);
    }
    list.forEach(t => (vals[t.m - 1] += f(t)));
    if (R.year === now.getFullYear()) cur = now.getMonth();
  } else if (R.kind === "12m") {
    const s = +R.from.slice(0, 4) * 12 + (+R.from.slice(5, 7) - 1);
    for (let i = 0; i < 12; i++) {
      const mo = (s + i) % 12;
      vals.push(0);
      labels.push(MON[mo].slice(0, 1));
      tips.push(`${MONL[mo]} ${Math.floor((s + i) / 12)}`);
    }
    list.forEach(t => {
      const i = t.y * 12 + t.m - 1 - s;
      if (i >= 0 && i < 12) vals[i] += f(t);
    });
    cur = 11;
  } else if (R.kind === "90d") {
    step = "Woche";
    for (let i = 0; i < 13; i++) {
      const d = flDayAdd(R.from, i * 7);
      vals.push(0);
      labels.push(i % 4 === 0 ? `${+d.slice(8, 10)}.${+d.slice(5, 7)}.` : "");
      tips.push(`Woche ab ${fmtDatumKurz(d)}`);
    }
    list.forEach(t => {
      const i = Math.min(12, Math.floor((slDay(t.date) - slDay(R.from)) / 7));
      if (i >= 0) vals[i] += f(t);
    });
    cur = 12;
  } else {
    step = "Jahr";
    const ys = [...new Set(list.map(t => t.y))].sort((a, b) => a - b), y1 = ys.length ? ys[ys.length - 1] : now.getFullYear(), y0 = Math.max(ys.length ? ys[0] : y1, y1 - 11);
    for (let y = y0; y <= y1; y++) {
      vals.push(0);
      labels.push(String(y).slice(2));
      tips.push(String(y));
    }
    list.forEach(t => t.y >= y0 && (vals[t.y - y0] += f(t)));
    cur = y1 === now.getFullYear() ? vals.length - 1 : -1;
  }
  return {vals, labels, tips: tips.map((x, i) => `${x}: ${fmt(vals[i])}`), cur, step};
}
function slYearShell(it) {
  const cfg = it.cfg || {}, now = new Date(), {R, list, prev} = flSelect(cfg, "year", {now, fallback: true}),
    ms = (cfg.metrics && cfg.metrics.length ? cfg.metrics : SL_JM).filter(m => SL_JM.includes(m)), bm = ms.includes("km") ? "km" : ms[0],
    ser = slYearSeries(list, R, bm, now), mx = Math.max(...ser.vals, 1),
    title = (cfg.title || "").trim() || (R.kind === "12m" ? "Deine letzten 12 Monate" : R.kind === "90d" ? "Deine letzten 90 Tage" : R.kind === "all" ? "Deine Touren insgesamt" : R.kind === "c" ? "Dein Zeitraum" : `Dein Jahr ${R.year}`),
    now_ = flVal(list, bm), was = prev ? flVal(prev, bm) : 0, up = now_ >= was,
    cmpTxt = was > 0 && now_ > 0 && cfg.compare !== false && R.prev
      ? `${up ? "+" : "−"}${nf((Math.abs(now_ - was) / was) * 100, 0)}\u00a0% gegenüber ` + (R.kind === "year" ? `${R.year - 1} bis heute` : R.kind === "y" ? String(R.year - 1) : R.kind === "12m" ? "den 12 Monaten davor" : "den 90 Tagen davor")
      : "",
    kz = ms.map(m => `<div class="hyn"><b>${FL_MET[m].fmt(flVal(list, m))}</b><span>${m === "count" ? "Touren" : FL_MET[m].name}</span></div>`).join(""),
    sec = document.createElement("section");
  sec.className = "hyear" + (it.widget ? " tlw" : "");
  sec.id = it.widget ? "tlw-" + it.id : "hyear";
  if (it.widget) {
    sec.dataset.wid = it.id;
    sec.dataset.wtype = it.wtype;
  }
  const fl = (cfg.title ? flParts(cfg, "year") : flParts(cfg, "year", {noRange: true})).map(p => `<span>${esc(p)}</span>`).join(", ");
  sec.innerHTML = `<div class="hyh"><h2>${esc(title)}</h2>${fl ? `<span class="flk">${fl}</span>` : ""}${cmpTxt ? `<span class="hcmp ${up ? "up" : "down"}" title="${esc(FL_MET[bm].name)}">${cmpTxt}</span>` : ""}<span class="sp"></span><a class="hmore" href="#/stats">Zur Statistik</a></div>` +
    `<div class="hyg" data-n="${ms.length}">${kz}<div class="hym" role="img" aria-label="${esc(`${FL_MET[bm].name} pro ${ser.step}`)}" title="${esc(`${FL_MET[bm].name} pro ${ser.step}`)}">${ser.vals.map((v, i) => `<div class="${i === ser.cur ? "cur" : ""}" title="${esc(ser.tips[i])}"><i data-h="${Math.max(v ? 6 : 2, (v / mx) * 100).toFixed(1)}"></i><span>${esc(ser.labels[i])}</span></div>`).join("")}</div></div>` +
    (list.length ? "" : `<p class="mut flnone">${(cfg.sports || []).length || R.kind !== "year" ? "Keine Touren mit diesem Filter." : "Noch keine Touren in diesem Jahr."}</p>`) +
    (it.widget ? "" : '<div id="hgoals"></div>');
  const bars = sec.querySelector(".hym");
  bars.style.setProperty("grid-template-columns", `repeat(${ser.vals.length},1fr)`);
  bars.querySelectorAll("i[data-h]").forEach(e => e.style.setProperty("height", e.dataset.h + "%"));
  if (!it.widget && typeof homeGoals === "function" && (R.kind === "year" || R.kind === "y")) homeGoals(sec.querySelector("#hgoals"), R.year, now);
  return sec;
}

/* ---- 3.20.0 Raster und Seiteneignung je Typ ----
   w      Standardbreite im Raster (voll | zweidrittel | halb | drittel); große Grafiken und Fotos „voll“, Kacheln und Listen „halb“
   seiten Seiten, auf denen der Baustein stehen darf: "tour" (Tourseite, Hauptseite und Auswertung) und/oder "uebersicht". Ohne Angabe: Tour-Bausteine nur Tourseite, Übersichts-Bausteine beide
          (sie rechnen aus den geladenen Touren, ohne Tour-Kontext); Bausteine, die eine Tour brauchen (ctx.t), gehören nie in die Übersicht (app/layout.py TOUR_ONLY lehnt sie ab). */
{
  const META = {
    kennzahlen: "halb", tempo: "halb", vergleich: "halb", pulszonen: "halb", wetter: "halb", fotostreifen: "voll", notiz: "halb", splits: "voll", steigung: "halb", bewegung: "halb",
    durchschnitt: "halb", jahresrang: "halb", tageslicht: "halb", gipfel: "halb", vergleiche: "halb", stimmung: "halb", fotohighlights: "voll", miniprofil: "voll", steckbrief: "halb",
    jahr: "voll", periode: "halb", belastung: "halb", jahresvergleich: "halb", letzte: "halb", neuefotos: "voll", auffaellig: "drittel", bestwerte: "halb", heutevor: "halb",
    serie: "halb", heatmap: "voll", meilensteine: "halb", wochentage: "halb", saison: "voll", sportarten: "halb", wiederentdecken: "voll", orte: "halb", uhrenzeit: "voll", ausruestung: "halb", geplant: "halb", rueckblick: "voll", zeppimport: "halb", planergebnis: "voll",
  };
  Object.entries(META).forEach(([k, w]) => {
    const T = window.SL_WT[k];
    if (!T) return;
    T.w = w;
    T.seiten = T.fam === "tour" ? ["tour"] : ["uebersicht", "tour", "statistik"];
  });
  window.SL_WT.auffaellig.seiten = ["uebersicht"];                                          // Verwaltungs-Hinweis auf Geräte, gehört zur Übersicht
  window.SL_WT.zeppimport.seiten = ["uebersicht"];                                          // ein Import-Knopf gehört nur zur Übersicht
}
