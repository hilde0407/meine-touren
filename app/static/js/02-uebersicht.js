/* ---------- Übersicht ---------- */
const VIEWS = {};
VIEWS.dash = async (_, q) => {
  if (!TOURS.length) {
    $("#main").className = "";
    $("#main").innerHTML =
      `<div class="empty"><h2>Noch keine Touren</h2><p>Unter <a href="#/admin"><b>Verwaltung</b></a> kannst du Zepp-Trainings oder GPX/TCX-Dateien importieren – sie werden lokal gespeichert. Optional: Komoot-Zugangsdaten eintragen und „Komoot aktualisieren“.</p></div>`;
    return;
  }
  $("#main").className = "flush";
  loadRoutesLater();
  /* 3.22.0: globaler Filter der Statistikseite (Sportarten, Zeitraum) aus der Adresse – stFilter/stRange in 56-statistik.js; ohne Angabe: alle Sportarten, gesamte Zeit wie bisher */
  const ys = years(),
    F = stFilter(q),
    R = stRange(F),
    Y = F.kind === "y" ? F.yr : 0,
    SP = F.sports,
    inR = R.kind === "all" ? () => true : t => flIn(t, R);
  const A = SP.length ? TOURS.filter(t => sgMatch(t.sport, SP)) : TOURS,          // 3.59.0: auch Statistik-Gruppen („sgrp:<id>“, 01-grundlagen.js)
    yearAll = TOURS.filter(inR),
    sel = A.filter(inR);
  const last = TOURS[0],
    prev = Y ? A.filter(t => t.y === Y - 1) : R.prev ? A.filter(t => flIn(t, R.prev)) : [],
    cmpL = Y ? String(Y - 1) : R.kind === "12m" ? "den 12 Monaten davor" : "den 90 Tagen davor";
  const sum = (a, f) => a.reduce((x, t) => x + f(t), 0);
  const km = sum(sel, t => t.km),
    up = sum(sel, t => t.up_m || 0),
    hh = sum(sel, t => t.h),
    pk = sum(prev, t => t.km);
  const delta = (a, b) =>
    b
      ? `<div class="d ${a >= b ? "up" : "down"}">${a >= b ? "+" : "−"}${nf((Math.abs(a - b) / b) * 100, 0)} % gegenüber ${cmpL}</div>`
      : "";
  /* 3.45.0: „Bestwerte“ (vorher „Rekorde“) ist ein Baustein (50-bausteine.js) und wird von der Layout-Engine gebaut */
  const pm = Array(12).fill(0);
  prev.forEach(t => (pm[t.m - 1] += t.km));
  /* Säulen „Strecke pro Monat oder Jahr“: ein Jahr = 12 Monate; 12 Monate, 90 Tage, freier Zeitraum bis 24 Monate = Monate des Zeitraums; sonst je Jahr */
  const mo0 = R.from ? +R.from.slice(0, 4) * 12 + +R.from.slice(5, 7) - 1 : 0,
    mo1 = +R.to.slice(0, 4) * 12 + +R.to.slice(5, 7) - 1,
    monthly = !!Y || R.kind === "12m" || R.kind === "90d" || (R.kind === "c" && mo1 - mo0 < 24),
    mser = Y ? Array.from({length: 12}, (_, i) => Y * 12 + i) : Array.from({length: mo1 - mo0 + 1}, (_, i) => mo0 + i),
    msum = (list, base, n) => {
      const v = Array(n).fill(0);
      list.forEach(t => {
        const i = t.y * 12 + t.m - 1 - base;
        if (i >= 0 && i < n) v[i] += t.km;
      });
      return v;
    },
    mkm = monthly ? msum(sel, mser[0], mser.length) : [],
    mlab = mser.map(k => MON[k % 12] + (Y || mo1 - mo0 < 12 ? "" : " " + String(Math.floor(k / 12)).slice(2))),
    mghost = Y ? pm : R.kind === "12m" && R.prev ? msum(A.filter(t => flIn(t, R.prev)), mser[0] - 12, 12) : null,
    yrs = R.kind === "all" ? ys.slice().reverse() : Array.from({length: +R.to.slice(0, 4) - +R.from.slice(0, 4) + 1}, (_, i) => +R.from.slice(0, 4) + i),
    byYear = yrs.map(y =>
      sum(
        sel.filter(t => t.y === y),
        t => t.km
      )
    ),
    bestK = mkm.indexOf(Math.max(...mkm)),
    bestKL = monthly && mkm[bestK] > 0 ? (Y ? MONL[bestK] : `${MONL[mser[bestK] % 12]} ${Math.floor(mser[bestK] / 12)}`) : "";
  const bySport = {};
  yearAll.forEach(t => (bySport[sgKey(t.sport)] = (bySport[sgKey(t.sport)] || 0) + t.km));     // 3.59.0: Mitglieder einer Statistik-Gruppe als eine Zeile
  const sports = Object.entries(bySport).sort((a, b) => b[1] - a[1]),
    tot = sum(yearAll, t => t.km) || 1;
  const hy = Y || (R.kind === "all" ? ys[0] : +R.to.slice(0, 4)),
    byDay = {};
  sel.filter(t => t.y === hy).forEach(t => {
    const k = t.date.slice(0, 10);
    byDay[k] = (byDay[k] || 0) + t.km;
  });
  const cum = (yr, pool = A) => {
    let c = 0;
    const pts = [[0, 0]];
    pool.filter(t => t.y === yr)
      .slice()
      .reverse()
      .forEach(t => {
        const d = (Date.UTC(yr, t.m - 1, +t.date.slice(8, 10)) - Date.UTC(yr, 0, 1)) / 864e5;
        c += t.km;
        pts.push([d, c]);
      });
    return pts;
  };
  const cy = Y || (R.kind === "all" ? ys[0] : +R.to.slice(0, 4)),
    own = Y || R.kind === "all",                                              // Jahr oder gesamte Zeit: wie bisher mit Vorjahreslinie; sonst nur der gewählte Zeitraum
    cs = [{pts: cum(cy, own ? A : sel), color: cssv("--bars"), w: 3.2}];
  if (own && ys.includes(cy - 1)) cs.unshift({pts: cum(cy - 1), color: cssv("--accent2"), dash: 1, w: 2});
  const today = new Date(),
    md = `${pad2(today.getMonth() + 1)}-${pad2(today.getDate())}`;
  const otd = TOURS.filter(t => t.date.slice(5, 10) === md && t.y !== today.getFullYear());
  const ph = last.photos ? await api(`/api/photos?tour_id=${last.id}&limit=4`) : [];
  $("#main").innerHTML = `
  <section class="hero"><div id="hm"></div><div class="in"><div class="t">
    <div class="k">Letzte Tour, ${sName(last.sport)}</div><h1>${esc(last.name)}</h1><div class="w">${fmtDatum(last.date, {zeit: true})}</div>
    ${ph.length ? `<div class="thumbrow">${ph.map((p, i) => `<img loading="lazy" decoding="async" src="${picSrc(p, 300)}" data-i="${i}">`).join("")}</div>` : ""}
    <div class="btns"><a class="btn" href="#/tour/${last.id}">Tour ansehen</a>${last.photos ? `<a class="btn alt c-white" target="_blank" href="slideshow.html?tour=${last.id}">Diashow</a>` : ""}</div></div>
    <div class="signs"><div class="sign">${fmtKm(last.km)}<small>Strecke</small></div><div class="sign l">${fmtHm(last.up_m)}<small>Aufstieg</small></div><div class="sign">${fmtDauer(last.h * 3600)}<small>Dauer</small></div></div></div></section>
  <div class="inner">
  ${stFilterBar(F, R, sel.length, yearAll)}
  <div class="figs" data-st="kpi" data-badge="${esc(`${nf(sel.length, 0)} Touren · ${fmtKm(km, {d: 0})}`)}">
    <div class="fig"><div class="v">${nf(sel.length, 0)}</div><div class="l">Touren</div>${delta(sel.length, prev.length)}</div>
    <div class="fig"><div class="v">${fmtKm(km, {summe: true, einheit: false})}<span class="u">km</span></div><div class="l">Strecke</div>${delta(km, pk)}</div>
    <div class="fig"><div class="v">${nf(up, 0)}<span class="u">m</span></div><div class="l">Aufstieg</div>${delta(
      up,
      sum(prev, t => t.up_m || 0)
    )}</div>
    <div class="fig"><div class="v">${fmtDauerHtml(hh * 3600, {summe: true})}</div><div class="l">Unterwegs</div>${delta(
      hh,
      sum(prev, t => t.h)
    )}</div>
    <div class="fig"><div class="v">${nf(km / (sel.length || 1), 1)}<span class="u">km</span></div><div class="l">pro Tour im Schnitt</div></div></div>
  <div class="grid g2 mt44">
    <div class="panel" data-st="kmmonat" data-badge="${esc(bestKL ? "Stärkster Monat: " + bestKL : monthly ? "" : `${fmtKm(sum(sel, t => t.km), {d: 0})}`)}"><h2>${monthly ? "Strecke pro Monat" : "Strecke pro Jahr"}</h2>${monthly ? barChart(mkm, mlab, {ghost: mghost, ghostLabel: Y ? Y - 1 : "Vorzeitraum"}) : barChart(byYear, yrs.map(String), {href: yrs})}
      <div class="legend">${monthly ? `<span><i style="background:var(--yellow);border:1px solid var(--ink)"></i>stärkster Monat</span>${mghost && mghost.some(v => v > 0) ? `<span><i style="background:var(--accent2)"></i>${Y ? Y - 1 : "Zeitraum davor"}</span>` : ""}` : "<span>Ein Klick auf einen Balken öffnet das Jahr.</span>"}</div></div>
    <div class="panel" data-st="kmverlauf" data-badge="${esc(`${cy}: ${fmtKm(cs[cs.length - 1].pts[cs[cs.length - 1].pts.length - 1][1], {d: 0})}`)}"><h2>Strecke im Jahresverlauf</h2>${lineChart(cs)}<div class="legend"><span><i style="background:var(--bars)"></i>${cy}</span>${own && ys.includes(cy - 1) ? `<span><i style="background:var(--accent2)"></i>${cy - 1}</span>` : ""}</div></div>
    <div class="panel" data-st="sportarten" data-badge="${esc(sports.length ? `${sName(sports[0][0])} ${nf((sports[0][1] / tot) * 100, 0)} %` : "")}"><h2>Sportarten</h2><div class="stack">${sports.map(([s, v]) => `<div style="width:${(v / tot) * 100}%;background:${sCol(s)}" title="${sName(s)}"></div>`).join("")}</div>
      <div class="rows mt10">${sports.map(([s, v]) => `<div class="r"><span><i class="sw" style="background:${sCol(s)}"></i>${sName(s)}</span><span class="mut">${fmtKm(v, {d: 0})}, ${nf((v / tot) * 100, 0)} %</span></div>`).join("")}</div></div>
    </div>
  <div class="panel gap" data-st="heat" data-badge="${esc(`${Object.keys(byDay).length} Tage mit Touren`)}"><h2>Aktivität im Jahr ${hy}</h2>${heat(hy, byDay)}</div>
  ${otd.length ? `<div data-st="tag" data-badge="${esc(otd.length === 1 ? "1 Tour" : otd.length + " Touren")}"><div class="sec"><h2>An diesem Tag</h2><span class="sub">in früheren Jahren</span></div><div class="tl">${otd.map(tourRow).join("")}</div></div>` : ""}
  <div data-st="erinn"><div class="sec" id="memh"><h2>Erinnerungen</h2><span class="sub" id="memsub"></span></div><div id="mem" class="thumbs"></div></div></div>`;
  stFilterBind(F);
  document.querySelectorAll("rect[data-h]").forEach(r => (r.onclick = () => (location.hash = stHash({...F, kind: "y", yr: +r.dataset.h}))));
  bindThumbs($(".thumbrow") || document.createElement("div"), ph);
  map = mkMap("hm", {
    zoom: false,
    attr: false,
    leaflet: {dragging: false, scrollWheelZoom: false, doubleClickZoom: false, touchZoom: false, boxZoom: false, keyboard: false},
  });
  map.setView([last.lat || 50, last.lng || 8], 12);
  api(`/api/tours/${last.id}/coords`)
    .then(c => {
      const l = L.polyline(
        cleanPts(c).map(p => [p[0], p[1]]),
        {color: "#f2c230", weight: 5}
      ).addTo(map);
      map.fitBounds(l.getBounds(), {paddingTopLeft: [window.innerWidth > 900 ? 640 : 40, 40], paddingBottomRight: [40, 40]});
    })
    .catch(() => {});
  try {
    const r = await api("/api/photos?random=true&limit=8");
    if (r.length) {
      $("#mem").innerHTML = r
        .map((p, i) => `<img loading="lazy" decoding="async" src="${picSrc(p, 400)}" data-i="${i}" title="${esc(p.tour_name || "")}">`)
        .join("");
      $("#memsub").innerHTML = `<a target="_blank" href="slideshow.html?random=1">Zufalls-Diashow starten</a>`;
      bindThumbs($("#mem"), r);
    } else {
      $("#memh").remove();
      $("#mem").remove();
    }
  } catch (e) {}
};
/* Jahreszeit: Sommerhalbjahr Mai–Oktober, Winterhalbjahr November–April */
const seasonOfMonth = m => (m >= 5 && m <= 10 ? "sommer" : "winter");
const seasonOf = d => seasonOfMonth(+String(d).slice(5, 7));
/* 3.52.0: Titelfoto je Tour in den Tourenlisten. Ein Aufruf für alle Touren (/api/tour-covers: Foto, Anzahl, Bildversion), parallel zur Tourenliste
   geladen; die Kachel hat eine feste Größe und steht sofort (die Zahl der Fotos kennt die Liste schon), das Bild kommt mit Version in der Adresse
   (der Browser behält es, beim erneuten Öffnen keine Bildanfrage) und erst kurz vor dem Sichtbereich (loading=lazy). Ohne Fotos: die Strecke.
   Abschaltbar je Gerät (Konto → Darstellung, „Mehr“ → Darstellung). */
let COVERS = null;
const TR_PIC = 300;                                           // = photos.COVER_SIZE (Größe des Foto-Streifens, wird vorab erzeugt)
const tlFotos = () => {
  try {
    return localStorage.getItem("mt_tlfotos") !== "0";
  } catch (e) {
    return true;
  }
};
let _trfT = null,
  _trf = false;
const trfOn = () => (_trfT === TOURS ? _trf : ((_trfT = TOURS), (_trf = tlFotos() && TOURS.some(t => t.photos > 0))));
function loadCovers() {
  _trfT = null;
  if (!tlFotos()) return (window.COVP = Promise.resolve((COVERS = {})));
  const pre = window._preCovers;
  window._preCovers = null;
  return (window.COVP = (pre ? pre.then(c => c || api("/api/tour-covers")) : api("/api/tour-covers"))
    .then(c => {
      COVERS = c || {};
      patchCovers();
      return COVERS;
    })
    .catch(() => (COVERS = COVERS || {})));
}
/* 3.54.0: Titelfotos für Startseite und Bausteine (Zuletzt unterwegs, Wiederentdecken): dieselbe Antwort wie die Tourenliste, auch wenn die Fotos der Liste ausgeschaltet sind */
const homeCovers = () => (tlFotos() ? (COVERS ? Promise.resolve(COVERS) : window.COVP || loadCovers()) : api("/api/tour-covers"));
const trImg = c => `<img class="trimg" src="/pic/${+c.id}?size=${TR_PIC}&v=${esc(c.v || "")}" alt="" loading="lazy" decoding="async" width="${TR_PIC}" height="${TR_PIC}">`;
function trThumb(t) {
  if (!trfOn()) return miniRoute(t.id, t.sport);
  const c = t.photos && COVERS ? COVERS[t.id] : null;
  if (c) return `<span class="trp">${trImg(c)}</span>`;
  if (t.photos && !COVERS) return `<span class="trp" data-cv="${esc(t.id)}"></span>`;      // Titelfoto ist unterwegs: Platzhalter in fester Größe, nichts springt
  return `<span class="trp trr">${miniRoute(t.id, t.sport)}</span>`;
}
/* Schalter „Fotos in der Tourenliste“ (Konto → Darstellung und „Mehr“ → Darstellung), je Gerät */
const tlFotosChk = () =>
  `<label class="chk tlfchk" title="Je Tour ein Foto statt der Strecke (gilt nur auf diesem Gerät)"><input type="checkbox" data-tlf${tlFotos() ? " checked" : ""}> <span>Fotos in der Tourenliste</span></label>`;
document.addEventListener("change", e => {
  const i = e.target;
  if (!i || !i.matches || !i.matches("input[data-tlf]")) return;
  try {
    localStorage.setItem("mt_tlfotos", i.checked ? "1" : "0");
  } catch (err) {}
  document.querySelectorAll("input[data-tlf]").forEach(x => (x.checked = i.checked));
  COVERS = i.checked ? null : {};
  loadCovers();
});
/* Platzhalter füllen, sobald die Titelfotos da sind (nur beim allerersten Aufbau, danach stehen sie schon beim Zeichnen fest) */
function patchCovers() {
  document.querySelectorAll(".trp[data-cv]").forEach(el => {
    const id = el.dataset.cv,
      c = COVERS && COVERS[id],
      t = BY[id];
    el.removeAttribute("data-cv");
    if (c) el.innerHTML = trImg(c);
    else {
      el.classList.add("trr");
      el.innerHTML = miniRoute(id, t ? t.sport : "");
    }
  });
}
/* Bild nicht ladbar (gelöscht, kein Zugriff): die Strecke zeigen */
document.addEventListener(
  "error",
  e => {
    const i = e.target,
      s = i && i.classList && i.classList.contains("trimg") && i.closest(".trp"),
      a = s && s.closest("a.tr"),
      id = a && decodeURIComponent((a.getAttribute("href") || "").slice(7));
    if (!s) return;
    s.classList.add("trr");
    s.innerHTML = miniRoute(id, BY[id] ? BY[id].sport : "");
  },
  true
);
function tourRow(t) {
  return `<a class="tr${trfOn() ? " trf" : ""}" href="#/tour/${t.id}">${trThumb(t)}<span><div class="nm">${esc(t.name)}</div><div class="s"><span>${fmtDatumKurz(t.date, {zeit: true})}</span><span><i style="background:${sCol(t.sport)}"></i>${sName(t.sport)}</span>${t.photos ? `<span>${t.photos} Fotos</span>` : ""}${t.has_hr ? `<span class="hrt" title="Mit Herzfrequenz">❤</span>` : ""}${t.stars ? `<span class="stars" title="Meine Bewertung">${"★".repeat(t.stars)}</span>` : ""}</div></span>
  <span class="n"><span>${fmtKm(t.km)}</span><span>${fmtAuf(t.up_m)}</span><span>${fmtDauer(t.h * 3600)}</span></span></a>`;
}

/* ---------- Gesamtkarte ---------- */
VIEWS.map = async () => {
  const routes = await loadRoutes(),
    ys = years(),
    sp = [...new Set(TOURS.map(t => t.sport))];
  $("#main").className = "wide";
  $("#main").innerHTML = `<div class="mapbox"><div id="bigmap"></div><div class="mapui">
    <div class="box"><select id="my"><option value="0">Alle Jahre</option>${ys.map(y => `<option>${y}</option>`).join("")}</select><span id="mc" class="cnt"></span></div>
    <div class="box" id="ms">${sp.map(s => `<button class="chip on" data-s="${s}" aria-pressed="true"><i style="background:${sCol(s)}"></i>${sName(s)}</button>`).join("")}</div><div class="box" id="mn" style="display:none"></div></div></div>`;
  map = mkMap("bigmap", {layers: true, leaflet: {preferCanvas: true}});
  const grp = L.layerGroup().addTo(map),
    off = new Set(),
    FULL = window._full || (window._full = {}),
    lines = {},
    casings = {},
    busy = new Set();
  let shown = [];
  const popup = t =>
    `<b>${esc(t.name)}</b><br>${fmtDatumKurz(t.date)}, ${fmtKm(t.km)} · ${fmtAuf(t.up_m)}<br><a href="#/tour/${t.id}">Tour öffnen</a>`;
  const line = (t, pts) => {
    if (lines[t.id]) grp.removeLayer(lines[t.id]);
    if (casings[t.id]) {
      grp.removeLayer(casings[t.id]);
      delete casings[t.id];
    }
    if (TS.casing) {
      casePane(map);
      casings[t.id] = L.polyline(pts, {pane: "casing", color: "#fff", weight: TS.weight + 3, opacity: 0.9, interactive: false}).addTo(grp);
    }
    const l = L.polyline(pts, trackStyle(t)).addTo(grp);
    l.bindPopup(popup(t));
    lines[t.id] = l;
    l.on("mouseover", () => l.setStyle({weight: TS.weight + 3, opacity: 1}));
    l.on("mouseout", () => l.setStyle(trackStyle(t)));
  };
  const draw = () => {
    grp.clearLayers();
    for (const k in lines) delete lines[k];
    for (const k in casings) delete casings[k];
    shown = [];
    const y = +$("#my").value;
    let n = 0,
      b = null;
    TOURS.forEach(t => {
      if ((y && t.y !== y) || off.has(t.sport)) return;
      const r = cleanPts(FULL[t.id] || routes[t.id]),
        st = r.length ? [r[0][0], r[0][1]] : okPt([t.lat, t.lng]) ? [t.lat, t.lng] : null;
      if (!st) return;
      n++;
      shown.push({t, st});
      L.circleMarker(st, {radius: 5, color: "#fff", weight: 1.5, fillColor: sCol(t.sport), fillOpacity: 0.95})
        .addTo(grp)
        .bindPopup(popup(t));
      b = b ? b.extend(L.latLng(st)) : L.latLngBounds([st, st]);
      if (r.length > 1)
        line(
          t,
          r.map(p => [p[0], p[1]])
        );
    });
    $("#mc").textContent = `${n} Touren`;
    return b;
  };
  // Beim Hineinzoomen: fehlende bzw. grob vereinfachte Strecken der sichtbaren Touren in voller Genauigkeit nachladen
  const detail = async () => {
    if (!$("#mn")) return;
    if (!map || map.getZoom() < 11) {
      $("#mn").style.display = "none";
      return;
    }
    const bd = map.getBounds().pad(0.1),
      c = map.getCenter();
    const need = shown
      .filter(x => bd.contains(x.st) && !FULL[x.t.id] && !busy.has(x.t.id))
      .sort((a, z) => map.distance(c, a.st) - map.distance(c, z.st))
      .slice(0, 30);
    if (!need.length) {
      $("#mn").style.display = "none";
      return;
    }
    let done = 0,
      fail = 0;
    $("#mn").style.display = "";
    $("#mn").textContent = `Strecken werden geladen (${need.length}) …`;
    const q = need.slice();
    need.forEach(x => busy.add(x.t.id));
    await Promise.all(
      [0, 1, 2, 3].map(async () => {
        while (q.length) {
          const x = q.shift();
          try {
            const pts = cleanPts(await api(`/api/tours/${x.t.id}/coords`));
            if (pts.length < 2) throw new Error("leer");
            FULL[x.t.id] = pts;
            line(
              x.t,
              pts.map(p => [p[0], p[1]])
            );
          } catch (e) {
            fail++;
            FULL[x.t.id] = null;
            delete FULL[x.t.id];
          }
          done++;
          busy.delete(x.t.id);
          if (!$("#mn")) return; // Seite inzwischen verlassen
          $("#mn").textContent = `Strecken werden geladen (${done}/${need.length}) …`;
        }
      })
    );
    if (!$("#mn")) return;
    if (fail) {
      $("#mn").textContent = `${fail} Strecken nicht lokal vorhanden – in der Verwaltung „Routen laden“ (Komoot-Zugang nötig)`;
      need.forEach(x => busy.add(x.t.id));
    } else $("#mn").style.display = "none";
  };
  document
    .querySelector(".mapui")
    .insertAdjacentHTML(
      "beforeend",
      `<div class="box" style="position:relative"><button class="chip mact" id="mtc" aria-haspopup="true" aria-expanded="false" title="Farbe und Breite der Strecken ändern">🎨 Strecken</button></div>`
    );
  $("#mtc").onclick = e => {
    if (document.querySelector(".tpanel")) {
      document.querySelector(".tpanel").remove();
      return;
    }
    trackPanel(e.target, () => {
      draw();
    });
  };
  let tm;
  map.on("moveend", () => {
    clearTimeout(tm);
    tm = setTimeout(detail, 350);
  });
  map.on("zoomend", () => {
    const z = map.getZoom();
    grp.eachLayer(l => {
      if (l.setRadius) l.setRadius(z < 9 ? 6 : z < 12 ? 5 : 4);
    });
  });
  $("#my").onchange = () => {
    const b = draw();
    if (b) map.fitBounds(b, {padding: [40, 40]});
  };
  $("#ms").onclick = e => {
    const s = e.target.closest("[data-s]");
    if (!s) return;
    s.setAttribute("aria-pressed", String(s.classList.toggle("on")));
    off.has(s.dataset.s) ? off.delete(s.dataset.s) : off.add(s.dataset.s);
    const b = draw();
    if (b) map.fitBounds(b, {padding: [40, 40]});
  };
  map.setView([50.5, 9], 6);
  const b0 = draw();
  if (b0) map.fitBounds(b0, {padding: [40, 40]});
  if (!Object.keys(routes).length) $("#mc").textContent += " (Strecken werden beim Hineinzoomen nachgeladen)";
};

/* ---------- Tourenliste ---------- */
/* 3.35.0: Filter, die eine Eigene Kennzahl beim Antippen mitgibt (#/tours?sp=hike,bike&von=…&bis=…&tag=…&minkm=…&hn=a|v&kz=Name). Alles streng geprüft, nichts davon wird als HTML eingesetzt. */
const XF_HN = {a: "Die Liste zeigt alle Touren im Zeitraum, auch solche ohne die nötige Angabe (zum Beispiel ohne Pulsdaten).", v: "Die Liste zeigt alle Touren im Zeitraum, auch solche, die für diese Kennzahl zu kurz sind."};
function tourXf(qp) {
  if (!qp || !qp.has("kz")) return null;
  const dt = x => (/^\d{4}-\d\d-\d\d$/.test(x || "") ? x : ""), mk = parseFloat(qp.get("minkm"));
  return {
    kz: (qp.get("kz") || "").slice(0, 60),
    sp: (qp.get("sp") || "").split(",").filter(x => /^[A-Za-z0-9_]{1,40}$/.test(x)).slice(0, 20),
    von: dt(qp.get("von")),
    bis: dt(qp.get("bis")),
    tag: (qp.get("tag") || "").slice(0, 40),
    minkm: mk > 0 && mk <= 1000 ? mk : 0,
    hn: XF_HN[qp.get("hn")] ? qp.get("hn") : "",
  };
}
const tourXfOk = (t, x) => {
  const d = (t.date || "").slice(0, 10);
  return (!x.sp.length || x.sp.includes(t.sport)) && (!x.von || d >= x.von) && (!x.bis || d <= x.bis) && (!x.tag || (t.tags || "").toLowerCase().split("|").includes(x.tag.toLowerCase())) && (!x.minkm || t.km >= x.minkm);
};
function tourXfBar(x) {
  const c = [];
  x.sp.forEach(s => c.push(sName(s)));
  if (x.von && x.bis) c.push(`${fmtDatumKurz(x.von)} – ${fmtDatumKurz(x.bis)}`);
  else if (x.von) c.push(`ab ${fmtDatumKurz(x.von)}`);
  else if (x.bis) c.push(`bis ${fmtDatumKurz(x.bis)}`);
  if (x.tag) c.push(`Schlagwort „${x.tag}“`);
  if (x.minkm) c.push(`mindestens ${nf(x.minkm, x.minkm % 1 ? 1 : 0)} km`);
  return `<div class="kzxf" role="status"><p class="kzxt"><b>Touren der Kennzahl „${esc(x.kz)}“</b> <a href="#/tours">Filter aufheben</a></p>` +
    `${c.length ? `<p class="kzxc">${c.map(i => `<span class="kzchip">${esc(i)}</span>`).join(" ")}</p>` : ""}${x.hn ? `<p class="mut kzxh">${XF_HN[x.hn]}</p>` : ""}</div>`;
}
VIEWS.tours = async (_name, qp) => {
  loadRoutesLater();
  const xf = tourXf(qp);
  const ys = years(),
    sp = [...new Set(TOURS.map(t => t.sport))];
  $("#main").innerHTML = `<div class="sec mt0"><h2>Alle Touren</h2><span class="sub" id="cnt"></span></div>
   ${xf ? tourXfBar(xf) : ""}<div class="filters" id="flt"><input id="q" placeholder="Name suchen" class="mnw230"><span class="fxtra"><select id="fy"><option value="0">Alle Jahre</option>${ys.map(y => `<option>${y}</option>`).join("")}</select></span>
   <select id="fs"><option value="">Alle Sportarten</option>${sp.map(s => `<option value="${s}">${sName(s)}</option>`).join("")}</select>
   <span class="fxtra"><select id="fz" title="Jahreszeit"><option value="">Ganzjährig</option><option value="sommer">Sommerhalbjahr (Mai–Okt)</option><option value="winter">Winterhalbjahr (Nov–Apr)</option></select>
   <select id="fb" title="Meine Bewertung"><option value="">Alle Bewertungen</option><option value="5">★★★★★</option><option value="4">ab ★★★★</option><option value="3">ab ★★★</option></select>
   <select id="fr" title="Region"><option value="">Alle Regionen</option>${regionOpts()}</select>
   <select id="ft" title="Tag / Album"><option value="">Alle Tags</option>${allTags()
     .map(x => `<option value="${esc(x)}">${esc(x)}</option>`)
     .join("")}</select></span>
   <select id="so"><option value="date">Neueste zuerst</option><option value="old">Älteste zuerst</option><option value="km">Längste Strecke</option><option value="up">Größter Aufstieg</option><option value="h">Längste Dauer</option></select>
   <button type="button" class="btn alt fmore" id="fmore" aria-expanded="false"><span>Filter</span><b class="fcnt" id="fcnt" hidden></b></button>
   <button type="button" class="btn ghost fclear" id="fclear" hidden>Filter zurücksetzen</button></div>
   <div class="tl" id="tl"></div><div class="row jcc mt20"><button class="btn ghost" id="more">Mehr anzeigen</button></div>`;
  let lim = 80;
  const KEY = "tf",
    ld = () => {
      try {
        return JSON.parse(sessionStorage.getItem(KEY)) || {};
      } catch (e) {
        return {};
      }
    };
  const sv = () => {
    try {
      sessionStorage.setItem(
        KEY,
        JSON.stringify({
          q: $("#q").value,
          fy: $("#fy").value,
          fs: $("#fs").value,
          fr: $("#fr").value,
          fz: $("#fz").value,
          fb: $("#fb").value,
          ft: $("#ft").value,
          so: $("#so").value,
          lim,
        })
      );
    } catch (e) {}
  };
  const f0 = xf ? {so: ld().so} : ld();                                                         // mit Kennzahl-Filter starten die übrigen Filter leer (sonst fehlen Touren ohne ersichtlichen Grund)
  ["q", "fy", "fs", "fr", "fz", "fb", "ft", "so"].forEach(i => {
    if (f0[i] !== undefined) $("#" + i).value = f0[i];
  });
  if (f0.lim) lim = f0.lim;
  const XF = ["fy", "fz", "fb", "fr", "ft"],                                                     // 3.48.0 (Handy): diese Filter stehen hinter dem Knopf „Filter“
    xCount = () => XF.filter(i => $("#" + i).value && $("#" + i).value !== "0").length,
    xPaint = () => {
      const n = xCount(),
        b = $("#fcnt");
      b.hidden = !n;
      b.textContent = n || "";
      $("#fmore").setAttribute("aria-label", (t => (typeof window.TL === "function" ? window.TL(t) : t))(n ? `Filter (${n} aktiv)` : "Filter"));
      $("#fclear").hidden = !n;
    };
  $("#fmore").onclick = () => {
    const o = $("#flt").classList.toggle("fxo");
    $("#fmore").setAttribute("aria-expanded", o ? "true" : "false");
  };
  $("#fclear").onclick = () => {
    XF.forEach(i => ($("#" + i).value = i === "fy" ? "0" : ""));
    lim = 80;
    draw();
  };
  if (xCount()) {
    $("#flt").classList.add("fxo");                                                              // gemerkte Filter sind sichtbar, nie unsichtbar aktiv
    $("#fmore").setAttribute("aria-expanded", "true");
  }
  const draw = () => {
    sv();
    xPaint();
    const q = $("#q").value,
      y = +$("#fy").value,
      s = $("#fs").value,
      so = $("#so").value,
      rg = $("#fr").value,
      tg = $("#ft").value,
      sz = $("#fz").value,
      sb = +$("#fb").value;
    let a = TOURS.filter(
      t =>
        (!y || t.y === y) &&
        (!sz || seasonOf(t.date) === sz) &&
        (!sb || (t.stars || 0) >= sb) &&
        (!s || t.sport === s) &&
        inRegion(t, rg) &&
        (!tg || (t.tags || "").split("|").includes(tg)) &&
        (!q.trim() || smatch(t.name, q)) &&
        (!xf || tourXfOk(t, xf))
    );
    const k = {date: t => -t.start_ts, old: t => t.start_ts, km: t => -t.km, up: t => -(t.up_m || 0), h: t => -t.h}[so];
    a.sort((x, z) => k(x) - k(z));
    $("#cnt").textContent = `${a.length} Touren, ${nf(
      a.reduce((c, t) => c + t.km, 0),
      0
    )} km`;
    $("#tl").innerHTML = a.slice(0, lim).map(tourRow).join("") || `<div class="empty">Keine Treffer</div>`;
    $("#more").style.display = a.length > lim ? "" : "none";
  };
  ["q", "fy", "fs", "fr", "fz", "fb", "ft", "so"].forEach(
    i =>
      ($("#" + i).oninput = () => {
        lim = 80;
        draw();
      })
  );
  $("#more").onclick = () => {
    lim += 120;
    draw();
  };
  draw();
  try {
    const y = +sessionStorage.getItem("tfy");
    if (y) setTimeout(() => window.scrollTo(0, y), 30);
    sessionStorage.removeItem("tfy");
  } catch (e) {}
  $("#tl").onclick = () => {
    try {
      sessionStorage.setItem("tfy", window.scrollY);
    } catch (e) {}
  };
};
