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
  await loadRoutes().catch(() => {});
  const ys = years(),
    Y = +(q.get("y") || 0) || 0,
    S = q.get("s") || "";
  const A = S ? TOURS.filter(t => t.sport === S) : TOURS,
    yearAll = Y ? TOURS.filter(t => t.y === Y) : TOURS,
    sel = Y ? A.filter(t => t.y === Y) : A;
  const dh = (y, s) =>
    "#/dash" + (y || s ? "?" + [y ? "y=" + y : "", s ? "s=" + encodeURIComponent(s) : ""].filter(Boolean).join("&") : "");
  const last = TOURS[0],
    prev = Y ? A.filter(t => t.y === Y - 1) : [];
  const sum = (a, f) => a.reduce((x, t) => x + f(t), 0);
  const km = sum(sel, t => t.km),
    up = sum(sel, t => t.up_m || 0),
    hh = sum(sel, t => t.h),
    pk = sum(prev, t => t.km);
  const delta = (a, b) =>
    b
      ? `<div class="d ${a >= b ? "up" : "down"}">${a >= b ? "+" : "−"}${nf((Math.abs(a - b) / b) * 100, 0)} % gegenüber ${Y - 1}</div>`
      : "";
  const longest = [...sel].sort((a, b) => b.km - a.km)[0],
    steepest = [...sel].sort((a, b) => (b.up_m || 0) - (a.up_m || 0))[0],
    longT = [...sel].sort((a, b) => b.h - a.h)[0];
  const mm = Array(12).fill(0);
  sel.forEach(t => (mm[t.m - 1] += t.km));
  const bestM = mm.indexOf(Math.max(...mm));
  const pm = Array(12).fill(0);
  prev.forEach(t => (pm[t.m - 1] += t.km));
  const byYear = ys
    .slice()
    .reverse()
    .map(y =>
      sum(
        A.filter(t => t.y === y),
        t => t.km
      )
    );
  const bySport = {};
  yearAll.forEach(t => (bySport[t.sport] = (bySport[t.sport] || 0) + t.km));
  const sports = Object.entries(bySport).sort((a, b) => b[1] - a[1]),
    tot = sum(yearAll, t => t.km) || 1;
  const hy = Y || ys[0],
    byDay = {};
  A.filter(t => t.y === hy).forEach(t => {
    const k = t.date.slice(0, 10);
    byDay[k] = (byDay[k] || 0) + t.km;
  });
  const cum = yr => {
    let c = 0;
    const pts = [[0, 0]];
    A.filter(t => t.y === yr)
      .slice()
      .reverse()
      .forEach(t => {
        const d = (Date.UTC(yr, t.m - 1, +t.date.slice(8, 10)) - Date.UTC(yr, 0, 1)) / 864e5;
        c += t.km;
        pts.push([d, c]);
      });
    return pts;
  };
  const cy = Y || ys[0],
    cs = [{pts: cum(cy), color: cssv("--bars"), w: 3.2}];
  if (ys.includes(cy - 1)) cs.unshift({pts: cum(cy - 1), color: cssv("--accent2"), dash: 1, w: 2});
  const today = new Date(),
    md = `${pad2(today.getMonth() + 1)}-${pad2(today.getDate())}`;
  const otd = TOURS.filter(t => t.date.slice(5, 10) === md && t.y !== today.getFullYear());
  const ph = last.photos ? await api(`/api/photos?tour_id=${last.id}&limit=4`) : [];
  $("#main").innerHTML = `
  <section class="hero"><div id="hm"></div><div class="in"><div class="t">
    <div class="k">Letzte Tour, ${sName(last.sport)}</div><h1>${esc(last.name)}</h1><div class="w">${dateL(last.date)}, ${timeS(last.date)} Uhr</div>
    ${ph.length ? `<div class="thumbrow">${ph.map((p, i) => `<img loading="lazy" src="/pic/${p.id}?size=300" data-i="${i}">`).join("")}</div>` : ""}
    <div class="btns"><a class="btn" href="#/tour/${last.id}">Tour ansehen</a>${last.photos ? `<a class="btn alt" style="color:#fff" target="_blank" href="slideshow.html?tour=${last.id}">Diashow</a>` : ""}</div></div>
    <div class="signs"><div class="sign">${nf(last.km, 1)}<small>Kilometer</small></div><div class="sign l">${nf(last.up_m, 0)}<small>Meter aufwärts</small></div><div class="sign">${nf(last.h, 1)}<small>Stunden</small></div></div></div></section>
  <div class="inner">
  <div class="sec"><h2>${Y ? "Das Jahr " + Y : "Alle Touren"}${S ? ", " + sName(S) : ""}</h2><span class="sub">${nf(sel.length, 0)} Touren</span></div>
  <div class="years"><button data-y="0" class="${Y ? "" : "on"}">Gesamt</button>${ys.map(y => `<button data-y="${y}" class="${Y === y ? "on" : ""}">${y}</button>`).join("")}</div>
  <div class="chips" id="sch" style="margin-top:14px"><button class="chip ${S ? "" : "on"}" data-s="">Alle Sportarten</button>${sports.map(([s]) => `<button class="chip ${S === s ? "on" : ""}" data-s="${esc(s)}"><i style="background:${sCol(s)}"></i>${sName(s)}</button>`).join("")}${S && !bySport[S] ? `<button class="chip on" data-s="${esc(S)}"><i style="background:${sCol(S)}"></i>${sName(S)}</button>` : ""}</div>
  <div class="figs">
    <div class="fig"><div class="v">${nf(sel.length, 0)}</div><div class="l">Touren</div>${delta(sel.length, prev.length)}</div>
    <div class="fig"><div class="v">${nf(km, 0)}<span class="u">km</span></div><div class="l">Strecke</div>${delta(km, pk)}</div>
    <div class="fig"><div class="v">${nf(up, 0)}<span class="u">m</span></div><div class="l">Aufstieg</div>${delta(
      up,
      sum(prev, t => t.up_m || 0)
    )}</div>
    <div class="fig"><div class="v">${nf(hh, 0)}<span class="u">h</span></div><div class="l">Unterwegs</div>${delta(
      hh,
      sum(prev, t => t.h)
    )}</div>
    <div class="fig"><div class="v">${nf(km / (sel.length || 1), 1)}<span class="u">km</span></div><div class="l">pro Tour im Schnitt</div></div></div>
  <div class="grid g2" style="margin-top:44px">
    <div class="panel"><h2>${Y ? "Kilometer pro Monat" : "Kilometer pro Jahr"}</h2>${Y ? barChart(mm, MON, {ghost: pm, ghostLabel: Y - 1}) : barChart(byYear, ys.slice().reverse().map(String), {href: ys.slice().reverse()})}
      <div class="legend">${Y ? `<span><i style="background:var(--yellow);border:1px solid var(--ink)"></i>stärkster Monat</span>${prev.length ? `<span><i style="background:var(--accent2)"></i>${Y - 1}</span>` : ""}` : "<span>Ein Klick auf einen Balken öffnet das Jahr.</span>"}</div></div>
    <div class="panel"><h2>Kilometer im Jahresverlauf</h2>${lineChart(cs)}<div class="legend"><span><i style="background:var(--bars)"></i>${cy}</span>${ys.includes(cy - 1) ? `<span><i style="background:var(--accent2)"></i>${cy - 1}</span>` : ""}</div></div>
    <div class="panel"><h2>Sportarten</h2><div class="stack">${sports.map(([s, v]) => `<div style="width:${(v / tot) * 100}%;background:${sCol(s)}" title="${sName(s)}"></div>`).join("")}</div>
      <div class="rows" style="margin-top:10px">${sports.map(([s, v]) => `<div class="r"><span><i class="sw" style="background:${sCol(s)}"></i>${sName(s)}</span><span class="mut">${nf(v, 0)} km, ${nf((v / tot) * 100, 0)} %</span></div>`).join("")}</div></div>
    <div class="panel"><h2>Bestwerte ${Y || "gesamt"}</h2><div class="rows">
      ${
        longest
          ? `<div class="r"><span><a href="#/tour/${longest.id}">Längste Tour</a><small>${esc(longest.name)}</small></span><b>${nf(longest.km, 1)} km</b></div>
      <div class="r"><span><a href="#/tour/${steepest.id}">Meiste Höhenmeter</a><small>${esc(steepest.name)}</small></span><b>${nf(steepest.up_m, 0)} m</b></div>
      <div class="r"><span><a href="#/tour/${longT.id}">Längste Dauer</a><small>${esc(longT.name)}</small></span><b>${nf(longT.h, 1)} h</b></div>
      <div class="r"><span>Stärkster Monat<small>${MONL[bestM]}</small></span><b>${nf(mm[bestM], 0)} km</b></div>`
          : '<div class="mut">Keine Touren</div>'
      }</div></div></div>
  <div class="panel" style="margin-top:44px"><h2>Aktivität im Jahr ${hy}</h2>${heat(hy, byDay)}</div>
  ${otd.length ? `<div class="sec"><h2>An diesem Tag</h2><span class="sub">in früheren Jahren</span></div><div class="tl">${otd.map(tourRow).join("")}</div>` : ""}
  <div class="sec" id="memh"><h2>Erinnerungen</h2><span class="sub" id="memsub"></span></div><div id="mem" class="thumbs"></div></div>`;
  $(".years").onclick = e => {
    const y = e.target.dataset.y;
    if (y !== undefined) location.hash = dh(+y, S);
  };
  $("#sch").onclick = e => {
    const b = e.target.closest("[data-s]");
    if (b) location.hash = dh(Y, b.dataset.s);
  };
  document.querySelectorAll("rect[data-h]").forEach(r => (r.onclick = () => (location.hash = dh(+r.dataset.h, S))));
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
        .map((p, i) => `<img loading="lazy" src="/pic/${p.id}?size=400" data-i="${i}" title="${esc(p.tour_name || "")}">`)
        .join("");
      $("#memsub").innerHTML = `<a target="_blank" href="slideshow.html?random=1">Zufalls-Diashow starten</a>`;
      bindThumbs($("#mem"), r);
    } else {
      $("#memh").remove();
      $("#mem").remove();
    }
  } catch (e) {}
};
function tourRow(t) {
  return `<a class="tr" href="#/tour/${t.id}">${miniRoute(t.id, t.sport)}<span><div class="nm">${esc(t.name)}</div><div class="s"><span>${dateS(t.date)}, ${timeS(t.date)}</span><span><i style="background:${sCol(t.sport)}"></i>${sName(t.sport)}</span>${t.photos ? `<span>${t.photos} Fotos</span>` : ""}</div></span>
  <span class="n"><span>${nf(t.km, 1)}<small>km</small></span><span>${nf(t.up_m, 0)}<small>m auf</small></span><span>${nf(t.h, 1)}<small>Std.</small></span></span></a>`;
}

/* ---------- Gesamtkarte ---------- */
VIEWS.map = async () => {
  const routes = await loadRoutes(),
    ys = years(),
    sp = [...new Set(TOURS.map(t => t.sport))];
  $("#main").className = "wide";
  $("#main").innerHTML = `<div class="mapbox"><div id="bigmap"></div><div class="mapui">
    <div class="box"><select id="my"><option value="0">Alle Jahre</option>${ys.map(y => `<option>${y}</option>`).join("")}</select><span id="mc" class="cnt"></span></div>
    <div class="box" id="ms">${sp.map(s => `<button class="chip on" data-s="${s}"><i style="background:${sCol(s)}"></i>${sName(s)}</button>`).join("")}</div><div class="box" id="mn" style="display:none"></div></div></div>`;
  map = mkMap("bigmap", {layers: true, leaflet: {preferCanvas: true}});
  const grp = L.layerGroup().addTo(map),
    off = new Set(),
    FULL = window._full || (window._full = {}),
    lines = {},
    casings = {},
    busy = new Set();
  let shown = [];
  const popup = t =>
    `<b>${esc(t.name)}</b><br>${dateS(t.date)}, ${nf(t.km, 1)} km, ${nf(t.up_m, 0)} m auf<br><a href="#/tour/${t.id}">Tour öffnen</a>`;
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
          $("#mn").textContent = `Strecken werden geladen (${done}/${need.length}) …`;
        }
      })
    );
    if (fail) {
      $("#mn").textContent = `${fail} Strecken nicht lokal vorhanden – in der Verwaltung „Routen laden“ (Komoot-Zugang nötig)`;
      need.forEach(x => busy.add(x.t.id));
    } else $("#mn").style.display = "none";
  };
  document
    .querySelector(".mapui")
    .insertAdjacentHTML(
      "beforeend",
      `<div class="box" style="position:relative"><button class="chip" id="mtc" title="Farbe und Breite der Strecken ändern">🎨 Strecken</button></div>`
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
    s.classList.toggle("on");
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
VIEWS.tours = async () => {
  await loadRoutes().catch(() => {});
  const ys = years(),
    sp = [...new Set(TOURS.map(t => t.sport))];
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Alle Touren</h2><span class="sub" id="cnt"></span></div>
   <div class="filters"><input id="q" placeholder="Name suchen" style="min-width:230px"><select id="fy"><option value="0">Alle Jahre</option>${ys.map(y => `<option>${y}</option>`).join("")}</select>
   <select id="fs"><option value="">Alle Sportarten</option>${sp.map(s => `<option value="${s}">${sName(s)}</option>`).join("")}</select>
   <select id="fr" title="Region"><option value="">Alle Regionen</option>${regionOpts()}</select>
   <select id="ft" title="Tag / Album"><option value="">Alle Tags</option>${allTags()
     .map(x => `<option value="${esc(x)}">${esc(x)}</option>`)
     .join("")}</select>
   <select id="so"><option value="date">Neueste zuerst</option><option value="old">Älteste zuerst</option><option value="km">Längste Strecke</option><option value="up">Meiste Höhenmeter</option><option value="h">Längste Dauer</option></select></div>
   <div class="tl" id="tl"></div><div class="row" style="justify-content:center;margin-top:20px"><button class="btn ghost" id="more">Mehr anzeigen</button></div>`;
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
          ft: $("#ft").value,
          so: $("#so").value,
          lim,
        })
      );
    } catch (e) {}
  };
  const f0 = ld();
  ["q", "fy", "fs", "fr", "ft", "so"].forEach(i => {
    if (f0[i] !== undefined) $("#" + i).value = f0[i];
  });
  if (f0.lim) lim = f0.lim;
  const draw = () => {
    sv();
    const q = $("#q").value.toLowerCase(),
      y = +$("#fy").value,
      s = $("#fs").value,
      so = $("#so").value,
      rg = $("#fr").value,
      tg = $("#ft").value;
    let a = TOURS.filter(
      t =>
        (!y || t.y === y) &&
        (!s || t.sport === s) &&
        inRegion(t, rg) &&
        (!tg || (t.tags || "").split("|").includes(tg)) &&
        (!q || t.name.toLowerCase().includes(q))
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
  ["q", "fy", "fs", "fr", "ft", "so"].forEach(
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
