/* =====================  Erweiterungen  ===================== */
NAV.splice(3, 0, ["records", "Bestwerte"]);
$("#nav").innerHTML = NAV.map(([k, l]) => `<a href="#/${k}" data-k="${k}">${l}</a>`).join("");
{
  const gs = document.createElement("input");
  gs.id = "gs";
  gs.type = "search";
  gs.placeholder = "Suchen …  ( / )";
  gs.setAttribute("aria-label", "Touren suchen");
  $(".top").insertBefore(gs, $("#busy"));
  let tmr;
  gs.oninput = () => {
    clearTimeout(tmr);
    tmr = setTimeout(() => {
      const v = gs.value.trim();
      location.hash = v ? `#/search?q=${encodeURIComponent(v)}` : "#/tours";
    }, 250);
  };
  addEventListener("keydown", e => {
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      e.preventDefault();
      gs.focus();
      gs.select();
    }
  });
}

/* ---- Suche ---- */
VIEWS.search = async (_, q) => {
  const term = (q.get("q") || "").trim(),
    toks = term.split(/\s+/).filter(Boolean);
  const hay = t =>
    `${t.name} ${t.note || ""} ${sName(t.sport)} ${fmtDatumKurz(t.date)} ${MONL[t.m - 1]} ${t.y} ${t.g_place || ""} ${t.g_county || ""} ${t.g_state || ""} ${t.g_country || ""} ${(t.tags || "").replace(/\|/g, " ")}`;
  const a = toks.length
    ? TOURS.filter(t => {
        const h = sforms(hay(t));
        return toks.every(k => sin(h, k));
      })
    : [];
  if (document.activeElement !== $("#gs") && $("#gs")) $("#gs").value = q.get("q") || "";
  $("#main").innerHTML =
    `<div class="sec mt0"><h2>Suche: „${esc(q.get("q") || "")}“</h2><span class="sub">${a.length} Touren, ${nf(
      a.reduce((c, t) => c + t.km, 0),
      0
    )} km</span></div>
   <div class="tl">${a.slice(0, 200).map(tourRow).join("") || `<div class="empty">Keine Treffer. Gesucht wird in Name, Notiz, Sportart, Datum, Monat und Region (Land, Bundesland, Landkreis, Ort).</div>`}</div>`;
};

/* ---- Ziele (Übersicht) ---- */
const GM = {km: ["km", "Strecke"], up: ["m", "Aufstieg"], count: ["", "Touren"], hours: [FMT_E[FMT_LG()].h, "Dauer"]};
const GOAL_GRP = {"grp:bike": ["Alle Rad-Sportarten", "bike"], "grp:ski": ["Alle Ski-Sportarten", "ski"], "grp:foot": ["Zu Fuß (Wandern, Bergtour, Schneeschuh)", "foot"], "grp:run": ["Laufen und Langlauf", "run"]};
/* 3.59.0 Sportarten eines Ziels (null = alle), wie stat_gruppen.ziel_sportarten (Server): „grp:<id>“ (ältere Ziele „Alle Rad-Sportarten“ …) = die eigene Statistik-Gruppe
   mit dieser Kennung, sonst die Aktivitäten-Familie (SPORT_GRP, 24-sport.js); „sgrp:<id>“ = eigene Gruppe (gelöscht: alle Sportarten); sonst die Sportart */
function goalSports(s) {
  if (!s) return null;
  if (s.startsWith("grp:") || isSg(s)) {
    const id = s.split(":")[1], g = SGRP.find(x => x.id === id);
    if (g) return g.sports;
    return s.startsWith("grp:") && SPORT_GRP[id] ? SPORT_GRP[id] : null;
  }
  return [sNorm(s)];
}
const goalSport = (g, t) => {
  const sp = goalSports(g.sport);
  return !sp || sp.includes(sNorm(t.sport));
};
const goalSportName = s => {
  if (s && (s.startsWith("grp:") || isSg(s))) {
    const g = SGRP.find(x => x.id === s.split(":")[1]);
    if (g) return sgLabel(SG_PRE + g.id);                                  // 3.60.1: „<Name> = A + B + …“ wie in Filtern und Aufteilungen
    if (isSg(s)) return "(Statistik-Gruppe gelöscht)";
  }
  return GOAL_GRP[s] ? GOAL_GRP[s][0] : sName(s);
};
/* Auswahl der Sportart eines Ziels: die eigenen Statistik-Gruppen, dann jede Aktivität (vorhandene zuerst, dann alle übrigen des Katalogs). Feste Gruppen gibt es nicht mehr. */
function goalSportOptions() {
  const have = [...new Set(TOURS.map(t => sNorm(t.sport)))], sp = have.concat(Object.keys(SPORT).filter(s => !have.includes(s)));
  return SGRP.map(g => [SG_PRE + g.id, sgLabel(SG_PRE + g.id)]).concat(sp.map(s => [s, sName(s)]));
}
const goalVal = (g, T) =>
  T.filter(t => t.y === g.year && goalSport(g, t)).reduce(
    (c, t) => c + (g.metric === "km" ? t.km : g.metric === "up" ? t.up_m || 0 : g.metric === "hours" ? t.h : 1),
    0
  );
// Prognose: voraussichtlicher Zieltermin und Warnung bei Rückstand
function goalNote(g, v, u, frac, proj, yr, cy) {
  if (v >= g.target) return ` · <span class="ok">Ziel erreicht ✓</span>`;
  if (frac >= 1) return ` · <span class="bad">Ziel verfehlt (${nf(g.target - v, 0)} ${u} gefehlt)</span>`;
  if (proj == null) return "";
  const y0 = new Date(cy, 0, 1),
    days = (new Date(cy + 1, 0, 1) - y0) / 864e5,
    rate = v / (frac * days); // pro Tag bisher
  let s = ` · Prognose zum Jahresende: ${nf(proj, 0)} ${u} (${nf((proj / g.target) * 100, 0)} %)`;
  if (rate > 0) {
    const d = (g.target - v) / rate,
      when = new Date(Date.now() + d * 864e5);
    if (proj >= g.target) s += ` · Ziel voraussichtlich am ${fmtDatum(when)}`;
    else {
      const left = (new Date(cy + 1, 0, 1) - Date.now()) / 864e5 / 7;
      s += ` · <span class="bad">Ziel wird bei diesem Tempo verfehlt – nötig wären ${nf((g.target - v) / Math.max(0.5, left), g.target < 50 ? 1 : 0)} ${u} pro Woche (bisher ${nf(rate * 7, g.target < 50 ? 1 : 0)})</span>`;
    }
  }
  else s += ` · <span class="bad">noch kein Fortschritt – Ziel wird so verfehlt</span>`;
  return s + (v < g.target * frac ? ` · <span class="bad">${nf(g.target * frac - v, 0)} ${u} unter dem Soll</span>` : ` · <span class="ok">im Soll</span>`);
}
const _dash = VIEWS.dash;
VIEWS.dash = async (n, q) => {
  await _dash(n, q);
  const fg = $(".figs");
  if (!fg) return;
  const ys = years(),
    Y = +(q.get("y") || 0) || 0;
  /* 3.45.0: Die Ziele (Anzeige und Pflege) sind der Baustein „Ziele“ (52-bausteine-uebersicht.js), als Abschnitt „Ziele“ der Statistik mit „Ziel hinzufügen“ und Löschen. */
  const yrs = $(".years");
  if (yrs)
    yrs.insertAdjacentHTML(
      "beforeend",
      `<a class="btn ghost sm" style="margin-left:auto;align-self:center" href="#/recap/${Y || ys[0]}">Jahresrückblick ${Y || ys[0]}</a>`
    );
};

/* ---- Rekorde ---- */
VIEWS.records = async (_, q) => {
  if (!TOURS.length) {
    $("#main").innerHTML = `<div class="empty"><h2>Noch keine Touren</h2></div>`;
    return;
  }
  let fs = (q && q.get("s")) || "";
  try {
    if (!q || !q.has("s")) fs = sessionStorage.getItem("rec_s") || "";
    sessionStorage.setItem("rec_s", fs);
  } catch (e) {}
  /* 3.59.0: Statistik-Gruppen als eigener Eintrag (Auswahl) und als eine Zeile in „Je Sportart“ (sgKey/sgMatch, 01-grundlagen.js) */
  const present = [...new Set(TOURS.map(t => t.sport))],
    allSp = sportOrder(present);                                                 // 3.60.1: dieselbe Auswahl wie Karte und Statistik
  if (fs && !allSp.includes(fs)) fs = "";
  const T = fs ? TOURS.filter(t => (isSg(fs) ? sgMatch(t.sport, [fs]) : t.sport === fs)) : TOURS;
  const chips = `<div class="row g6 mn4-0-18 fxw">${sportFilterHtml(present, fs ? [fs] : [], (k, l, x) => `<a class="chip${x.on ? " on" : ""}" href="#/records?s=${encodeURIComponent(k)}"${x.title ? ` title="${esc(x.title)}"` : ""}>${x.all ? "" : `<i class="sw" style="background:${x.color}"></i>`}${esc(l)}</a>`)}</div>`;      // 3.61.0: eine Darstellung für alle Sportart-Filter
  const sum = (a, f) => a.reduce((c, t) => c + f(t), 0),
    km = sum(T, t => t.km),
    up = sum(T, t => t.up_m || 0),
    h = sum(T, t => t.h);
  const best = (a, f) => a.reduce((b, t) => (b == null || f(t) > f(b) ? t : b), null);
  const sports = [...new Set(T.map(t => sgKey(t.sport)))].sort(
    (a, b) => T.filter(t => sgKey(t.sport) === b).length - T.filter(t => sgKey(t.sport) === a).length
  );
  const lnk = (t, v) =>
    t
      ? `<div class="r"><span>${v[0]}<small><a href="#/tour/${t.id}">${esc(t.name)}</a>, ${fmtDatumKurz(t.date)}</small></span><b>${v[1]}</b></div>`
      : "";
  const wkIdx = t => Math.floor((Date.UTC(t.y, t.m - 1, +t.date.slice(8, 10)) / 864e5 + 3) / 7),
    wks = [...new Set(T.map(wkIdx))].sort((a, b) => a - b);
  let longest = 0,
    run = 0,
    prevW = null;
  wks.forEach(w => {
    run = prevW !== null && w === prevW + 1 ? run + 1 : 1;
    longest = Math.max(longest, run);
    prevW = w;
  });
  const curW = Math.floor((Date.now() / 864e5 + 3) / 7);
  let cur = 0;
  {
    let w = wks.includes(curW) ? curW : wks.includes(curW - 1) ? curW - 1 : null;
    while (w !== null && wks.includes(w)) {
      cur++;
      w--;
    }
  }
  const dayN = new Set(T.map(t => t.date.slice(0, 10))).size,
    wd = Array(7).fill(0);
  T.forEach(t => wd[(new Date(t.date.slice(0, 10) + "T12:00:00").getDay() + 6) % 7]++);
  const alts = (await api(`/api/records/altitude?limit=${fs ? 60 : 8}`).catch(() => []))
    .filter(a => !fs || (BY[a.id] && (isSg(fs) ? sgMatch(BY[a.id].sport, [fs]) : BY[a.id].sport === fs)))
    .slice(0, 8);
  $("#main").innerHTML =
    `<div class="sec mt0"><h2>Bestwerte</h2><span class="sub">${nf(T.length, 0)} Touren seit ${T[T.length - 1].y}${fs ? " · " + sName(fs) : ""}</span></div>${chips}
   <div class="figs"><div class="fig"><div class="v">${nf(km / 40075, 2)}<span class="u">×</span></div><div class="l">um die Erde (${fmtKm(km, {d: 0})})</div></div>
    <div class="fig"><div class="v">${nf(up / 8849, 1)}<span class="u">×</span></div><div class="l">Mount Everest bergauf (${fmtHm(up)})</div></div>
    <div class="fig"><div class="v">${nf(h / 24, 1)}<span class="u">Tage</span></div><div class="l">unterwegs (${fmtDauer(h * 3600, {summe: true})})</div></div>
    <div class="fig"><div class="v">${nf(dayN, 0)}</div><div class="l">Aktive Tage</div></div>
    <div class="fig"><div class="v">${longest}<span class="u">Wochen</span></div><div class="l">längste Serie · aktuell ${cur}</div></div></div>
   <div class="grid g2 mt36">
    <div class="panel"><h2>Bestwerte gesamt</h2><div class="rows">${lnk(
      best(T, t => t.km),
      ["Längste Strecke", fmtKm(best(T, t => t.km).km)]
    )}${lnk(
      best(T, t => t.up_m || 0),
      ["Größter Aufstieg", fmtHm(best(T, t => t.up_m || 0).up_m)]
    )}${lnk(
      best(T, t => t.h),
      ["Längste Dauer", fmtDauer(best(T, t => t.h).h * 3600)]
    )}</div></div>
    <div class="panel"><h2>Höchste Punkte</h2><div class="rows">${alts.length ? alts.map(a => (BY[a.id] ? `<div class="r"><span><a href="#/tour/${a.id}">${esc(BY[a.id].name)}</a><small>${fmtDatumKurz(BY[a.id].date)}</small></span><b>${fmtHm(a.alt)}</b></div>` : "")).join("") : `<div class="mut">Sobald die Strecken da sind (Verwaltung → Touren holen → Komoot „Fehlende Strecken holen“), erscheinen hier die höchsten Punkte.</div>`}</div></div>
    <div class="panel"><h2>Nach Wochentag</h2>${barChart(wd, ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"])}</div>
    <div class="panel"><h2>Je Sportart</h2><div class="rows">${sports
      .map(s => {
        const a = T.filter(t => sgKey(t.sport) === s),
          l = best(a, t => t.km),
          u = best(a, t => t.up_m || 0),
          f = best(
            a.filter(t => t.km >= 3 && t.h > 0),
            t => t.km / t.h
          );
        return `<div class="r" style="display:block"><div><i class="sw" style="background:${sCol(s)}"></i><b style="font:600 20px var(--d)"${isSg(s) ? ` title="${esc(sgTitle(s))}"` : ""}>${isSg(s) ? esc(sName(s)) : sName(s)}</b> <span class="mut">· ${a.length} Touren, ${nf(
          sum(a, t => t.km),
          0
        )} km, ${nf(
          sum(a, t => t.up_m || 0),
          0
        )} m</span></div>
       <small>Längste: <a href="#/tour/${l.id}">${fmtKm(l.km)}</a> · Größter Aufstieg: <a href="#/tour/${u.id}">${fmtHm(u.up_m)}</a>${f ? ` · Schnellste: <a href="#/tour/${f.id}">${fmtTempo(f.km / f.h)}</a>` : ""}</small></div>`;
      })
      .join("")}</div></div></div>`;
};

/* ---- Jahresrückblick ---- */
VIEWS.recap = async name => {
  const Y = +name || years()[0],
    sel = TOURS.filter(t => t.y === Y),
    prev = TOURS.filter(t => t.y === Y - 1);
  if (!sel.length) {
    $("#main").innerHTML = `<div class="empty"><h2>Keine Touren in ${Y}</h2></div>`;
    return;
  }
  const sum = (a, f) => a.reduce((c, t) => c + f(t), 0),
    km = sum(sel, t => t.km),
    up = sum(sel, t => t.up_m || 0),
    h = sum(sel, t => t.h);
  const mm = Array(12).fill(0),
    pm = Array(12).fill(0);
  sel.forEach(t => (mm[t.m - 1] += t.km));
  prev.forEach(t => (pm[t.m - 1] += t.km));
  const bySport = {};
  sel.forEach(t => (bySport[sgKey(t.sport)] = (bySport[sgKey(t.sport)] || 0) + t.km));         // 3.59.0: Statistik-Gruppen als eine Zeile
  const sp = Object.entries(bySport).sort((a, b) => b[1] - a[1]);
  const eff = sel.filter(t => t.sport !== "skialpin") /* Liftabfahrten sagen nichts über die Leistung */,
    pool = eff.length ? eff : sel,
    top = pool
      .slice()
      .sort((a, b) => b.km + (b.up_m || 0) / 100 - (a.km + (a.up_m || 0) / 100))
      .slice(0, 5),
    steep = pool.slice().sort((a, b) => (b.up_m || 0) - (a.up_m || 0))[0],
    bm = mm.indexOf(Math.max(...mm));
  const byPlace = {};
  sel.forEach(t => { if (t.g_place) { const o = byPlace[t.g_place] || (byPlace[t.g_place] = {n: 0, km: 0, st: t.g_state || t.g_country || ""}); o.n++; o.km += t.km; } });
  const places = Object.entries(byPlace).sort((a, b) => b[1].n - a[1].n || b[1].km - a[1].km),
    states = new Set(sel.map(t => t.g_state).filter(Boolean)).size, lands = new Set(sel.map(t => t.g_country).filter(Boolean)).size;
  const placePanel = places.length ? `<div class="panel gap"><h2>Orte des Jahres</h2><div class="mut fs14 mb8">${places.length} Startorte${states ? ` · ${states} Bundesländer/Regionen` : ""}${lands ? ` · ${lands} ${lands === 1 ? "Land" : "Länder"}` : ""}</div><div class="rows">${places.slice(0, 8).map(([n, o]) => `<div class="row"><span>📌 ${esc(n)}${o.st ? ` <span class="mut">(${esc(o.st)})</span>` : ""}</span><span class="sp"></span><b>${o.n} ${o.n === 1 ? "Tour" : "Touren"} · ${fmtKm(o.km, {d: 0})}</b></div>`).join("")}</div></div>` : "";
  await pdfPhotoLoad();
  const days = new Set(sel.map(t => t.date.slice(0, 10))).size,
    ph = await api(`/api/photos?year=${Y}&random=true&limit=${Math.max(12, PDFP.n)}`).catch(() => []);
  const dl = (a, b) => (b ? `${a >= b ? "+" : "−"}${nf((Math.abs(a - b) / b) * 100, 0)} % gegenüber ${Y - 1}` : "");
  $("#main").innerHTML =
    `<div class="recap"><div class="noprint row mb10"><a class="back" href="#/dash?y=${Y}">‹ Übersicht</a><span class="sp"></span>${pdfPhotoBar()}${pdfBtn()}<button class="btn ghost sm" data-act="print">Drucken</button></div>
   <div class="rhero"><div class="k">Mein Tourenjahr</div><h1>${Y}</h1><div class="rs"><span><b>${nf(sel.length, 0)}</b> Touren</span><span><b>${fmtKm(km, {summe: true})}</b> Strecke</span><span><b>${fmtHm(up)}</b> Aufstieg</span><span><b>${fmtDauer(h * 3600, {summe: true})}</b> Dauer</span><span><b>${days}</b> aktive Tage</span></div>
   <div class="rd">${[
     dl(
       km,
       sum(prev, t => t.km)
     ),
   ]
     .filter(Boolean)
     .join("")}</div></div>
   <div class="grid g2 mt34"><div class="panel"><h2>Strecke pro Monat</h2>${barChart(mm, MON, {ghost: pm, ghostLabel: Y - 1})}<div class="mut fs14">Stärkster Monat: ${MONL[bm]} mit ${fmtKm(mm[bm], {d: 0})}</div></div>
    <div class="panel"><h2>Sportarten</h2><div class="stack">${sp.map(([s, v]) => `<div style="width:${(v / km) * 100}%;background:${sCol(s)}"></div>`).join("")}</div><div class="rows mt10">${sp.map(([s, v]) => `<div class="r"><span><i class="sw" style="background:${sCol(s)}"></i>${sName(s)}</span><span class="mut">${fmtKm(v, {d: 0})}, ${nf((v / km) * 100, 0)} %</span></div>`).join("")}</div></div></div>
   <div class="panel gap"><h2>Die fünf stärksten Touren</h2><div class="tl">${top.map(tourRow).join("")}</div><div class="mut mt10">Größter Aufstieg: <a href="#/tour/${steep.id}">${esc(steep.name)}</a> (${fmtHm(steep.up_m)})</div></div>
   ${placePanel}
   ${ph.length ? `<div class="panel gap"><div class="row"><h2>Fotos des Jahres</h2><span class="sp"></span><a class="btn sm noprint" target="_blank" href="slideshow.html?year=${Y}">Diashow</a></div><div class="thumbs" id="rph">${ph.map((p, i) => `<div class="th"><img loading="lazy" decoding="async" src="${picSrc(p, 400)}" data-i="${i}"></div>`).join("")}</div></div>` : ""}</div>`;
  if (ph.length) bindThumbs($("#rph"), ph);
  const mark = () => {                  // Fotos nur im Druck/PDF: aus oder nur die ersten n
    const pn = $("#rph") && $("#rph").closest(".panel");
    if (!pn) return;
    pn.classList.toggle("noprint", !PDFP.on);
    [...$("#rph").children].forEach((c, i) => c.classList.toggle("noprint", i >= PDFP.n));
  };
  pdfPhotoBind(mark);
  pdfBindDl(`/api/recap/${Y}/pdf`);
  mark();
};

/* ---- Tourdetail: Notiz, GPX, Teilen ---- */
const _tourV = VIEWS.tour;
VIEWS.tour = async id => {
  await _tourV(id);
  const t = BY[id],
    r = ($("#ksync") || $("#eup")) && ($("#ksync") || $("#eup")).closest(".row");
  if (!t || !r) return;
  if (!$("#e3d"))           // 3D-Flug und Diashow-Link für alle Touren (Komoot, Zepp, lokale Dateien, Aufzeichnungen)
  r.insertAdjacentHTML(
    "beforeend",
    `<a class="btn ghost sm" id="e3d" href="#/flight/${encodeURIComponent(id)}" title="Die Strecke im 3D-Gelände abfliegen">🛰 3D-Flug</a>${t.photos ? `<button class="btn ghost sm" id="shr" title="Link zur Foto-Diashow dieser Tour kopieren">🔗 Diashow-Link</button>` : ""}`
  );
  if ($("#shr"))
    $("#shr").onclick = async () => {
      const u = new URL(`slideshow.html?tour=${id}`, location.href).href;
      try {
        await navigator.clipboard.writeText(u);
        $("#shr").textContent = "Link kopiert";
      } catch (e) {
        uiLink("Link zur Diashow", u);
      }
    };
  r.insertAdjacentHTML(
    "afterend",
    `<div class="field mw760 m0-0-18"><label for="note">Notiz zur Tour (Wetter, Begleitung, Einkehr …)</label><textarea id="note" rows="2" placeholder="Hier eine Notiz eintragen …">${esc(t.note || "")}</textarea><span id="notes" class="mut fs13"></span></div>`
  );
  $("#note").onchange = async () => {
    try {
      await api(`/api/tours/${encodeURIComponent(id)}/note`, {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({note: $("#note").value}),
      });
      t.note = $("#note").value.trim();
      if ($("#notes")) $("#notes").textContent = "Notiz gespeichert";
    } catch (e) {
      if ($("#notes")) $("#notes").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  };
};

/* ---- Verwaltung: Sicherung und Schutz ---- */
/* ---- Updates: Prüfung auf GitHub, Installation aus der Oberfläche ---- */
const isAdmin = () => !ME.users_enabled || (ME.user && ME.user.role === "admin");
async function installUpdate(u, say) {
  if (
    !await uiConfirm({title: `Version ${u.latest} installieren?`, ok: "Installieren", text: `Vorher wird eine Sicherung aller Daten angelegt. Die Seite ist während der Installation kurz nicht erreichbar.`})
  )
    return;
  const before = u.current;
  let bkWarn = "";
  say("Sicherung wird angelegt …");
  try {
    const ir = await api("/api/update/install", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({version: u.latest}),
    });
    bkWarn = ir && ir.backup_fehler && ir.backup_fehler.length ? `<span class="bad">⚠ Die Sicherung vor dem Update ist fehlgeschlagen: ${esc(ir.backup_fehler.join("; "))}</span><br>` : "";
  } catch (e) {
    return say(`<span class="bad">${esc(e.message)}</span>`);
  }
  if (bkWarn) {
    const say0 = say;
    say = h => say0(bkWarn + h);
  }
  say("Version wird installiert … (dauert etwa ein bis zwei Minuten)");
  const t0 = Date.now();
  const tick = async () => {
    let v = null,
      s = null;
    try {
      v = (await (await fetch("/api/version", {cache: "no-store"})).json()).version;
      s = (await api("/api/update/status")).status;
    } catch (e) {}
    if (v && v.split(" ")[0] !== before) {
      say(`<span class="ok">Version ${esc(v.split(" ")[0])} ist installiert ✓ – Seite wird neu geladen …</span>`);
      return setTimeout(() => location.reload(), 1500);
    }
    if (s && s.state === "error") return say(`<span class="bad">Update nicht möglich: ${esc(s.message || "unbekannter Fehler")}</span>`);
    if (Date.now() - t0 > 6 * 60000)
      return say(
        `<span class="bad">Das dauert ungewöhnlich lange. Bitte im Container <code>journalctl -u ${esc(u.command.split("-update")[0])}-update</code> ansehen.</span>`
      );
    setTimeout(tick, 3000);
  };
  setTimeout(tick, 4000);
}
async function updatePanel() {
  const b = $("#upd");
  if (!b) return;
  let u;
  try {
    u = await api("/api/update-check");
  } catch (e) {
    return;
  }
  const admin = isAdmin();
  const notes = (u.notes || "").trim();
  b.innerHTML = `<div class="panel" style="margin-bottom:16px${u.newer ? ";border-color:var(--yellow)" : ""}"><h2>Updates</h2>
   <p>Installiert: <b>${esc(u.current)}</b>${u.latest ? ` · neueste Version auf GitHub: <b>${esc(u.latest)}</b>${u.published ? ` (${esc(u.published)})` : ""}` : ` · <span class="mut">GitHub war nicht erreichbar${u.error ? " (" + esc(u.error) + ")" : ""}</span>`}
   ${u.newer ? `<span class="bad"> – es gibt eine neuere Version</span>` : u.ok ? `<span class="ok"> ✓ aktuell</span>` : ""}</p>
   ${notes && u.newer ? `<details><summary>Was ist neu?</summary><pre class="pre ova" style="white-space:pre-wrap;max-height:240px">${esc(notes)}</pre></details>` : ""}
   <div class="row"><button class="btn alt" id="ucheck">Jetzt prüfen</button>
   ${u.newer && admin && u.can_install ? `<button class="btn" id="uinst">Version ${esc(u.latest)} installieren</button>` : ""}
   ${u.newer ? `<a class="btn alt" target="_blank" rel="noopener" href="${esc(u.url)}">Auf GitHub ansehen</a>` : ""}<span id="umsg"></span></div>
   ${
     u.newer && !u.can_install
       ? `<p class="mut fs13">Die Installation aus der Oberfläche ist hier noch nicht eingerichtet. Im Container <b>einmal</b> ausführen: <code>${esc(u.command)}</code> – danach klappt es per Knopfdruck.</p>`
       : ""
   }
   ${swField("update_check", "Regelmäßig (alle 6 Stunden) auf neue Versionen prüfen", "", "mt8")}
   ${u.status && u.status.state === "error" ? `<p class="bad fs13">Letztes Update nicht möglich: ${esc(u.status.message || "")}</p>` : ""}</div>`;
  const sel = b.querySelector('[data-k="update_check"]');
  if (sel) sel.checked = !!u.enabled;
  const uc = b.querySelector("#ucheck");
  if (!uc || !b.isConnected) return;       // Seite wurde inzwischen gewechselt
  uc.onclick = async () => {
    b.querySelector("#umsg").textContent = "…";
    await api("/api/update-check?force=1").catch(() => {});
    updatePanel();
  };
  const ui = b.querySelector("#uinst");
  if (ui) ui.onclick = () => installUpdate(u, h => (b.querySelector("#umsg").innerHTML = h));
}

const _adm = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm(...a);
  const st = await api("/api/status").catch(() => ({})),
    sv = $("#save");
  if (!sv) return;
  if ($("#ver")) $("#ver").textContent = "Version: " + (st.version || "alt");
  api("/api/zustand")
    .then(h => {
      const b = $("#hlt");
      if (!b) return;
      b.innerHTML =
        `<h2>Zustand <span class="mut h2sub">${h.ok ? "– alles in Ordnung" : "– bitte prüfen"}</span></h2><div class="rows">${h.checks.map(c => `<div class="r"><span><i style="font-style:normal">${c.ok ? "✓" : "⚠"}</i> <span>${esc(c.name)}</span></span><span class="${c.ok ? "mut" : "bad"}"><span>${esc(c.detail)}</span>${c.hint ? ` – <span>${esc(c.hint)}</span>` : ""}${c.name === "Letzte Sicherung" && !c.ok ? ` <button class="btn sm" data-act="backup">Jetzt sichern</button>` : ""}</span></div>`).join("")}</div>` +
        (h.duplicates.length
          ? `<p class="mut mt8">Doppelte Namen: ${h.duplicates.map(d => esc(d.name) + " (" + d.tours.map(t => `<a href="#/tour/${t.id}">${t.date}</a>`).join(", ") + ")").join(" · ")}</p>`
          : "");
      const bb = b.querySelector('[data-act="backup"]');
      if (bb)
        bb.onclick = async () => {
          bb.disabled = true;
          try {
            await api("/api/backup/now", {method: "POST"});
            route();
          } catch (e) {
            bb.disabled = false;
            uiAlert(e.message || e);
          }
        };
    })
    .catch(() => {
      const b = $("#hlt");
      if (b) b.remove();
    });
  updatePanel();
  setTimeout(umzugInit, 0);
  sv.closest(".row").insertAdjacentHTML(
    "beforebegin",
    `<div class="grid g2 mt40"><div class="panel"><h2>Sicherung</h2>
   <p class="mut">Täglich um 03:40 Uhr wird die Datenbank (Touren, Notizen, Ziele, Zuordnungen) automatisch nach <code>${esc(st.backup_dir || "/var/backups/meine-touren")}</code> gesichert, die letzten 14 bleiben erhalten. Zurückspielen: <code>${esc(st.app_name || "meine-touren")}-restore &lt;Datei&gt;</code> im Container.</p>
   <div id="bkst" class="bkst" aria-live="polite"></div>
   <div class="row g8"><button class="btn alt" id="bkchk" type="button">Letzte Sicherung prüfen</button><span id="bkmsg" class="mut" role="status" aria-live="polite"></span></div>
   <p class="mut fs13">Geprüft wird nur die Sicherungsdatei in einem temporären Ordner – deine Daten werden nicht verändert. Nicht in der Tagessicherung enthalten: die Fotodateien (nur die Angaben dazu) und der Zwischenspeicher. Auch der Schlüssel für gespeicherte Zugangsdaten (secret.key) fehlt: Nach dem Zurückspielen auf einem neuen Rechner müssen sie neu eingegeben werden. Das Umzugspaket enthält beides.</p>
   <div class="row"><a class="btn alt" href="/api/backup" download>Sicherung jetzt herunterladen</a></div><p class="mut fs13">Passwörter und Tokens sind im Download nicht enthalten. Fotos und Routen sind nicht enthalten.</p>
   ${isAdmin() ? `<div id="rsbox"></div>` : ""}
   <h3 class="mt16">Umzug auf einen neuen Server</h3>
   <p class="mut">Das Umzugspaket enthält alles: alle Benutzer, Touren mit Notizen und Kommentaren, Freigabelinks, Fotos, Strecken samt Original-Höhen, gespeicherte Zugangsdaten samt Schlüssel. Auf dem neuen Server zuerst installieren, dann <code>${esc(st.app_name || "meine-touren")}-restore &lt;Paket&gt;</code> – danach läuft alles wie vorher. Das Paket enthält Passwörter und Schlüssel: gut aufbewahren. Es kann groß werden (Fotos).</p>
   <div class="row"><button class="btn" id="umzmk">Umzugspaket erstellen</button><span id="umzst" class="mut"></span></div><div id="umzls" class="mt8"></div></div>
   <div class="panel" id="uipw"><h2>Zugriffsschutz</h2>${
     st.users
       ? `<p class="mut">Mit Benutzerverwaltung melden sich alle mit ihrem eigenen Benutzernamen und Passwort an (siehe „Benutzer“).</p>`
       : st.ui_pw_env
         ? `<p class="ok"><b>✓ Passwortschutz ist aktiv.</b></p><p class="mut">Das Passwort ist über <code>UI_PASSWORD</code> in <code>/etc/${esc(st.app_name || "meine-touren")}.env</code> festgelegt und lässt sich hier nicht ändern.</p>`
         : `${st.protected ? `<p class="ok"><b>✓ Passwortschutz ist aktiv.</b></p>` : `<p class="bad"><b>Die Oberfläche ist nicht passwortgeschützt.</b></p><p class="mut">Jeder im Netzwerk kann Touren, Fotos und Einstellungen sehen.</p>`}
            <div class="row g8"><input type="password" id="uipw1" autocomplete="new-password" placeholder="${st.protected ? "Neues Passwort" : "Passwort festlegen"} (mind. 6 Zeichen)" class="mw260"><input type="password" id="uipw2" autocomplete="new-password" placeholder="Wiederholen" class="mw200"><button class="btn sm" id="uipws">${st.protected ? "Passwort ändern" : "Passwort setzen"}</button>${st.protected ? `<button class="btn ghost sm" id="uipwx">Schutz aufheben</button>` : ""}</div>
            <p class="mut fs13">Der Browser fragt danach nach dem Passwort (Benutzername beliebig). Das Passwort wird nur als Hash im Datenordner gespeichert.</p><div id="uipwm"></div>`
   }</div></div>`
  );
  bkInit();
  if (typeof rsInit === "function") rsInit();
  const setPw = async pw => {
    try {
      await api("/api/ui-password", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({password: pw})});
      $("#uipwm").innerHTML = `<span class="ok">${pw ? "Passwort gespeichert – beim nächsten Aufruf fragt der Browser danach." : "Schutz aufgehoben."}</span>`;
      setTimeout(() => route(), 1200);
    } catch (e) {
      $("#uipwm").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  };
  if ($("#uipws"))
    $("#uipws").onclick = () => {
      const a = $("#uipw1").value;
      if (a !== $("#uipw2").value) return ($("#uipwm").innerHTML = `<span class="bad">Die beiden Eingaben stimmen nicht überein.</span>`);
      if (a.length < 6) return ($("#uipwm").innerHTML = `<span class="bad">Das Passwort braucht mindestens 6 Zeichen.</span>`);
      setPw(a);
    };
  if ($("#uipwx")) $("#uipwx").onclick = async () => (await uiConfirm({text: "Passwortschutz wirklich aufheben? Danach kann jeder im Netzwerk die App öffnen.", danger: true, ok: "Aufheben"})) && setPw("");
};

/* ---- Karte: Heatmap und Fotos ---- */
const _mapV = VIEWS.map;
VIEWS.map = async () => {
  await _mapV();
  const routes = ROUTES || {},
    box = $(".mapui");
  if (!box || !map) return;
  box.insertAdjacentHTML(
    "beforeend",
    `<div class="box"><button class="chip" id="mht" aria-pressed="false" title="Heatmap: zeichnet alle Touren in einer Farbe übereinander – häufig begangene Wege leuchten stärker. Ersetzt die farbigen Tracklinien (Knopf 'Strecken' ändert deren Farbe und Breite).">Heatmap</button><button class="chip" id="mph" aria-pressed="false" title="Zeigt als rosa Punkte alle Fotos. Haben sie keinen eigenen Aufnahmeort, wird er aus der Uhrzeit auf dem Track der Tour berechnet (blassere Punkte). Antippen öffnet das Foto mit Zeit und Tour. Gilt für das gewählte Jahr.">Fotos</button></div>`
  );
  const m = map,
    hl = L.layerGroup().addTo(m),
    pl = L.layerGroup().addTo(m);
  let heat = false,
    phs = null,
    phOn = false;
  const yearSel = () => +$("#my").value,
    off = () => mapOff();                                                     // 3.60.1: abgewählte Sportarten (02-uebersicht.js; Gruppen-Chips zählen nicht selbst)
  const drawHeat = () => {
    hl.clearLayers();
    if (!heat) return;
    const o = off(),
      y = yearSel();
    TOURS.forEach(t => {
      if ((y && t.y !== y) || o.has(t.sport)) return;
      const r = cleanPts(routes[t.id]);
      if (r.length > 1) L.polyline(r, {color: "#ff4d12", weight: 4, opacity: 0.17, interactive: false}).addTo(hl);
    });
  };
  const drawPh = () => {
    pl.clearLayers();
    if (!phOn || !phs) return ($("#mph").textContent = "Fotos");
    const y = yearSel();
    let n = 0;
    phs.forEach(p => {
      if (y && new Date(p.taken_ts * 1000).getFullYear() !== y) return;
      if (!okPt([p.lat, p.lng])) return;
      n++;
      L.circleMarker([p.lat, p.lng], {radius: p.est ? 4 : 5, color: "#fff", weight: 1.5, fillColor: "#e11d74", fillOpacity: p.est ? 0.6 : 0.95})
        .addTo(pl)
        .bindPopup(
          `<img src="/pic/${p.id}?size=300" class="br3" style="width:220px;display:block"><div class="mt4">${fmtDatumKurz(p.taken_ts, {zeit: true})}${p.tour_id && BY[p.tour_id] ? `<br><a href="#/tour/${p.tour_id}">${esc(BY[p.tour_id].name)}</a>` : "<br>ohne Tour"}${p.est ? '<br><small style="opacity:.7">Position aus der Uhrzeit auf dem Track berechnet</small>' : ""}</div>`
        );
    });
    $("#mph").textContent = `Fotos (${n})`;       // so sieht man, wie viele Fotos mit Standort gezeigt werden
  };
  const mainGrp = [];
  m.eachLayer(l => {
    if (l instanceof L.LayerGroup && !(l === hl || l === pl)) mainGrp.push(l);
  });
  $("#mht").onclick = e => {
    heat = !heat;
    e.target.classList.toggle("on", heat);
    e.target.setAttribute("aria-pressed", String(heat));
    mainGrp.forEach(g => (heat ? m.removeLayer(g) : m.addLayer(g)));
    drawHeat();
  };
  $("#mph").onclick = async e => {
    phOn = !phOn;
    e.target.classList.toggle("on", phOn);
    e.target.setAttribute("aria-pressed", String(phOn));
    if (phOn && !phs) {
      try {
        phs = await api("/api/photos?gps=true&est=true&limit=60000");
      } catch (x) {
        phs = [];
      }
      if (!phs.length) e.target.title = "Keine Fotos mit GPS-Position";
    }
    drawPh();
  };
  box.insertAdjacentHTML(
    "beforeend",
    `<div class="box"><button class="chip mact" id="mbx" aria-haspopup="dialog" title="Alle Touren auflisten, die den sichtbaren Kartenausschnitt berühren">Touren im Ausschnitt</button></div>`
  );
  $("#mbx").onclick = () => {
    document.querySelectorAll(".uimod.mbxfen").forEach(x => x.remove());     // ein zweiter Klick ersetzt das Fenster, es gibt nie mehrere
    const b = m.getBounds(),
      y = yearSel(),
      o = off();
    const a = TOURS.filter(t => (!y || t.y === y) && !o.has(t.sport) && cleanPts(routes[t.id]).some(p => b.contains(p)));
    const md = uiModal(`<div class="sec m0-0-10"><h2>Im Kartenausschnitt</h2><span class="sub">${a.length} Touren, ${fmtKm(a.reduce((c, t) => c + t.km, 0), {summe: true})} · ${fmtAuf(a.reduce((c, t) => c + (t.up_m || 0), 0))}</span></div>
      <div class="tl">${a.slice(0, 300).map(tourRow).join("") || '<div class="empty">Keine Touren in diesem Ausschnitt. Zoome heraus oder verschiebe die Karte.</div>'}</div>
      <div class="uifoot"><button class="btn ghost" id="mbc">Schließen</button></div>`);
    md.classList.add("mbxfen");
    md.querySelector("#mbc").onclick = () => md.remove();
    md.onclick = e => { if (e.target.closest("a")) md.remove(); };
  };
  ["#my"].forEach(s =>
    $(s).addEventListener("change", () => {
      drawHeat();
      drawPh();
    })
  );
  $("#ms").addEventListener("click", () => setTimeout(drawHeat, 0));
};

/* ---- Foto-Zuordnung: GPS-Hinweis ---- */
const _ad = assignDialog;
assignDialog = (sp, done) => {
  loadRoutes()
    .catch(() => {})
    .then(() => {
      const first = sp.slice().sort((a, b) => a.taken_ts - b.taken_ts)[0],
        R = ROUTES || {};
      const near = t =>
        okPt([first.lat, first.lng]) &&
        cleanPts(R[t.id]).some(p => Math.abs(p[0] - first.lat) < 0.012 && Math.abs(p[1] - first.lng) < 0.02);
      const mark = TOURS.map(t => [t, near(t)])
        .filter(x => x[1])
        .map(x => x[0].id);
      _ad(sp, done);
      if (mark.length) {
        const sel = $("#at");
        [...sel.options].forEach(o => {
          if (mark.includes(o.value)) o.textContent = "📍 " + o.textContent;
        });
        const opts = [...sel.options].sort((a, b) => (b.textContent.startsWith("📍") ? 1 : 0) - (a.textContent.startsWith("📍") ? 1 : 0));
        opts.forEach(o => sel.appendChild(o));
        sel.selectedIndex = 0;
        sel.dispatchEvent(new Event("input"));
        sel.insertAdjacentHTML(
          "afterend",
          `<div class="mut fs13 mt4">📍 = das Foto wurde in der Nähe dieser Strecke aufgenommen (GPS)</div>`
        );
      }
    });
};


/* Sicherung: Zustand (neueste Datei, letzter Fehler) und Prüfung der letzten Sicherung */
async function bkInit() {
  const box = $("#bkst"), btn = $("#bkchk"), msg = $("#bkmsg");
  if (!box || !btn) return;
  const dt = ts => fmtDatumKurz(ts, {zeit: true});
  const render = s => {
    if (!box.isConnected) return;
    let h = "";
    if (s.neueste) h += `<p class="${s.ueberfaellig ? "bad" : "ok"}"><span aria-hidden="true">${s.ueberfaellig ? "⚠" : "✓"}</span> <span>Letzte Sicherung: ${dt(s.neueste.ts)} (${fmtGroesse(s.neueste.groesse)})</span></p>`;
    else h += `<p class="bad"><span aria-hidden="true">⚠</span> <span>Es gibt noch keine Sicherung.</span></p>`;
    if (s.fehler) h += `<p class="bad" id="bkerr"><span aria-hidden="true">⚠</span> <span>Letzte Sicherung fehlgeschlagen: ${esc(s.fehler)}</span></p>`;
    const g = s.geprueft;
    if (g) {
      const von = g.name && g.alter_h != null ? `<span class="ml8">Geprüft: Sicherung vom ${dt(g.ts - g.alter_h * 3600)}.</span>` : "";
      if (g.ok) {
        const inh = g.layouts != null ? `Enthält ${g.touren} Touren, ${g.tracks} Tracks und ${g.layouts} Ansichten` : `Enthält ${g.touren} Touren und ${g.tracks} Tracks`;
        h += `<p class="ok" id="bkok"><span aria-hidden="true">✓</span> <span>Zuletzt geprüft: ${dt(g.ts)}, in Ordnung</span></p><p class="mut fs13"><span>${inh}.</span>${von}</p>`;
      } else h += `<p class="bad" id="bkbad"><span aria-hidden="true">✗</span> <span>Zuletzt geprüft: ${dt(g.ts)}, Fehler: ${esc(g.fehler || "")}</span></p>`;
    } else h += `<p class="mut">Die letzte Sicherung wurde noch nicht geprüft.</p>`;
    box.innerHTML = h;
  };
  const load = () => api("/api/backup/status").then(render).catch(() => {});
  btn.onclick = async () => {
    btn.disabled = true;
    msg.textContent = "Prüfe …";
    try {
      await api("/api/backup/check", {method: "POST"});
      msg.textContent = "";
      await load();
    } catch (e) {
      msg.innerHTML = `<span class="bad">${esc(e.message || e)}</span>`;
    }
    btn.disabled = false;
  };
  load();
}

/* Umzugspaket (komplette Sicherung): erstellen, auflisten, herunterladen */
async function umzugInit() {
  const mk = $("#umzmk"), ls = $("#umzls"), stx = $("#umzst");
  if (!mk) return;
  const list = async () => {
    const l = await api("/api/backup/full").catch(() => []);
    ls.innerHTML = l.map(x => `<div class="row g8"><a href="/api/backup/full/${encodeURIComponent(x.name)}" download>${esc(x.name)}</a><small class="mut">${fmtGroesse(x.size)} · ${fmtDatumKurz(x.ts, {zeit: true})}</small></div>`).join("") || '<small class="mut">Noch kein Umzugspaket erstellt.</small>';
  };
  const poll = async () => {
    const j = await api("/api/jobs").catch(() => null);
    if (j && j.running) { stx.textContent = (j.running || "") + " …"; mk.disabled = true; setTimeout(poll, 3000); return; }
    mk.disabled = false;
    stx.textContent = j && j.finished && j.ok === false ? "Fehlgeschlagen – siehe Protokoll" : "";
    list();
  };
  mk.onclick = async () => {
    try { await api("/api/backup/full", {method: "POST"}); stx.textContent = "Wird erstellt …"; mk.disabled = true; setTimeout(poll, 2000); } catch (e) { stx.textContent = e.message; }
  };
  list();
}
