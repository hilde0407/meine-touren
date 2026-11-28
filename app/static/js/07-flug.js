/* =====================  3D-Flug  ===================== */
/* 3.61.4: flüssiger auf Handys (Vorbild Mein Tourentagebuch 2.16.0; Rechenlogik in js/07-flugrechnung.js): Darstellungsstufen (Flüssig/Normal/Schön: Pixeldichte, Höhenkacheln, Neigung, Takte),
   gedrosselte Linie und Kopfzeile, Fotos als Kartenebene statt HTML-Marker (keine readPixels-Bremse), Kamera als reine Funktion der Position, nur jedes zweite Bild auf 120/144-Hz-Anzeigen,
   Anpassung bei langsamen Bildern mit Hysterese. */
const loadLib = () =>
  window.maplibregl
    ? Promise.resolve()
    : new Promise((ok, no) => {
        const l = document.createElement("link");
        l.rel = "stylesheet";
        l.href = "vendor/maplibre-gl.css";
        document.head.appendChild(l);
        const s = document.createElement("script");
        s.src = "vendor/maplibre-gl.js";
        s.onload = ok;
        s.onerror = () => no(new Error("3D-Bibliothek konnte nicht geladen werden"));
        document.head.appendChild(s);
      });
const hav = (a, b) => {
  const R = 6371000,
    r = Math.PI / 180,
    dl = (b[0] - a[0]) * r,
    dn = (b[1] - a[1]) * r,
    x = Math.sin(dl / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dn / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
};
const brg = (a, b) => {
  const r = Math.PI / 180,
    y = Math.sin((b[1] - a[1]) * r) * Math.cos(b[0] * r),
    x = Math.cos(a[0] * r) * Math.sin(b[0] * r) - Math.sin(a[0] * r) * Math.cos(b[0] * r) * Math.cos((b[1] - a[1]) * r);
  return (Math.atan2(y, x) / r + 360) % 360;
};
/* Berge im Weg: Prüft entlang des Sehstrahls von der Kamera zum Streckenpunkt, ob das Gelände die Sicht verdeckt, und liefert den
   steilsten Neigungswinkel (≤ base), bei dem die Sicht frei ist. elev(lng,lat) = Gelände relativ zum Streckenpunkt (null = unbekannt). */
const clearPitch = (elev, lng, lat, bearing, base, D, floor = 28) => FlugCalc.freieNeigung(elev, lng, lat, bearing, base, D, floor).th;
function flightPath(raw, cap = 900) {
  // gleichmäßig nach Strecke abtasten, Höhe auffüllen, Kamerapfad glätten
  const cum = [0];
  for (let i = 1; i < raw.length; i++) cum.push(cum[i - 1] + hav(raw[i - 1], raw[i]));
  const total = cum[cum.length - 1] || 1,
    N = Math.max(60, Math.min(cap, Math.round(total / 8))),
    P = [];
  let la = raw.find(p => p[2] != null)?.[2] ?? 0;
  const alt = raw.map(p => (la = p[2] ?? la));
  for (let k = 0, j = 0; k < N; k++) {
    const d = (total * k) / (N - 1);
    while (j < raw.length - 2 && cum[j + 1] < d) j++;
    const f = (d - cum[j]) / (cum[j + 1] - cum[j] || 1);
    P.push({
      lat: raw[j][0] + (raw[j + 1][0] - raw[j][0]) * f,
      lng: raw[j][1] + (raw[j + 1][1] - raw[j][1]) * f,
      alt: alt[j] + (alt[j + 1] - alt[j]) * f,
      d,
      t: raw[j][3] != null && raw[j + 1][3] != null && raw[0][3] != null ? (raw[j][3] + (raw[j + 1][3] - raw[j][3]) * f - raw[0][3]) / 1000 : null,
    });
  }
  const w = Math.max(3, Math.round(N / 80)),
    S = P.map((p, i) => {
      let a = 0,
        b = 0,
        c = 0;
      for (let k = Math.max(0, i - w); k <= Math.min(N - 1, i + w); k++) {
        a += P[k].lat;
        b += P[k].lng;
        c++;
      }
      return {lat: a / c, lng: b / c};
    });
  let up = 0;
  P.forEach((p, i) => {
    if (i) up += Math.max(0, p.alt - P[i - 1].alt > 0.3 ? p.alt - P[i - 1].alt : 0);
    p.up = up;
  });
  return {P, S, total, cum};
}
/* Reiseflug: Touren nacheinander; dazwischen steigt die Kamera auf, überfliegt die Lücke mit sanft an- und abschwellendem Tempo
   (Positionen mit smoothstep) und sinkt über der nächsten Tour wieder ab. T = Zeitpunkt (s) jedes Punkts, tq = Fortschritt im Übergang. */
function flightSet(raws, names) {
  const parts = raws.map(r => flightPath(r, 400)),
    nTour = parts.reduce((a, p) => a + p.P.length, 0),
    step = 90 / nTour,
    P = [],
    S = [],
    T = [];
  let off = 0,
    up = 0,
    t = 0;
  parts.forEach((pt, i) => {
    if (P.length) {
      const a = P[P.length - 1],
        b = pt.P[0],
        km = hav([a.lat, a.lng], [b.lat, b.lng]) / 1000,
        sec = Math.max(4, Math.min(10, 3.5 + km * 0.12)),
        K = Math.round(sec * 30),
        lift = Math.max(1.5, Math.min(3.4, 1 + Math.log2(1 + km) * 0.55));
      for (let j = 1; j < K; j++) {
        const q = j / K,
          e = q * q * (3 - 2 * q),
          o = {lat: a.lat + (b.lat - a.lat) * e, lng: a.lng + (b.lng - a.lng) * e, alt: a.alt + (b.alt - a.alt) * e, d: off, up, trans: true, tq: q, lift, name: names[i]};
        t += sec / K;
        T.push(t);
        P.push(o);
        S.push({lat: o.lat, lng: o.lng});
      }
    }
    pt.P.forEach((p, k) => {
      if (P.length) t += step;
      T.push(t);
      P.push({...p, d: p.d + off, up: p.up + up, name: names[i]});
      S.push(pt.S[k]);
    });
    off += pt.total;
    up += pt.P[pt.P.length - 1].up;
  });
  return {P, S, total: off, cum: null, T, Ttot: t || 1};
}
VIEWS.flight = async id => {
  id = decodeURIComponent(id || "");
  const SET = id.startsWith("set:"),
    t = SET
      ? {
          id,
          name: "Flug über " + id.slice(4).split(",").length + " Touren",
          sport: (BY[id.slice(4).split(",")[0]] || {}).sport || "hike",
          start_ts: 0,
          lat: 50,
          lng: 8,
        }
      : BY[id];
  if (!t) throw notFound("Tour", "#/tours", "Alle Touren");
  $("#main").className = "wide";
  $("#main").innerHTML =
    `<div class="flight" id="fl"><div id="fm"></div><div class="fbar"><a class="btn ghost sm" href="${SET ? "#" : "#/tour/" + t.id}"${SET ? ' data-act="back"' : ""}>‹ Zurück</a><b class="ft">${esc(t.name)}</b><span class="sp"></span><span id="fh" class="fh"></span></div>
   <div class="fctl"><button class="btn sm" id="fp">⏸ Pause</button><input type="range" id="fs" min="0" max="1000" value="0" aria-label="Position">
    <select id="fv" title="Tempo"><option value=".5">0,5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option><option value="8">8×</option></select>
    <select id="fc" title="Kamera"><option value="follow">Kamera folgt</option><option value="free">Kamera frei</option></select>
    <select id="fin" title="Bedienung im 3D-Flug" aria-label="Bedienung im 3D-Flug"><option value="auto">Bedienung: Automatisch</option><option value="maus">Bedienung: Maus</option><option value="touchpad">Bedienung: Touchpad</option></select>
    <select id="fz" title="Flughöhe"><option value="16">nah</option><option value="14.8" selected>mittel</option><option value="13.4">weit</option></select>
    <select id="fpi" title="Neigung"><option value="auto" selected>automatisch (weicht Bergen aus)</option><option value="55">flach</option><option value="68">schräg</option><option value="78">sehr schräg</option></select>
    <select id="fb" title="Karte"><option value="osm">Straßenkarte</option><option value="topo">Topografisch</option><option value="sat">Satellit</option></select>
    <select id="fst" title="3D-Flug: Darstellung" aria-label="3D-Flug: Darstellung"><option value="fluessig">Darstellung: Flüssig</option><option value="normal">Darstellung: Normal</option><option value="schoen">Darstellung: Schön</option></select>
    <select id="fq" title="Videoqualität"><option value="1280">Video: Standard</option><option value="1600" selected>Video: Hoch</option><option value="1920">Video: Sehr hoch</option></select>
    <button class="btn ghost sm" id="frec" title="Flug als Video aufnehmen und speichern">⏺ Video</button><button class="btn ghost sm" id="ffs" title="Vollbild">⛶</button></div>
   <div class="fnav" id="fnav" role="group" aria-label="Kamera steuern">
    <button type="button" id="fnn" class="fnb" title="Norden / Draufsicht" aria-label="Norden / Draufsicht"><svg viewBox="0 0 24 24" aria-hidden="true"><circle class="fnring" cx="12" cy="12" r="11"/><g id="fnk"><path class="fnk-n" d="M12 2.5l3.6 9.5H8.4z"/><path class="fnk-s" d="M12 21.5l3.6-9.5H8.4z"/></g></svg></button>
    <button type="button" id="fnh" class="fnb" title="Hilfe zur Bedienung" aria-label="Hilfe zur Bedienung" aria-expanded="false" aria-controls="fhint">?</button>
    <button type="button" id="fnl" class="fnb" title="Nach links drehen" aria-label="Nach links drehen"><svg viewBox="0 0 24 24" aria-hidden="true"><path class="fnl" d="M5 12a7 7 0 1 1 3 5.7"/><path class="fnf" d="M2 9l3.4 4.6L9.6 10z"/></svg></button>
    <button type="button" id="fnr" class="fnb" title="Nach rechts drehen" aria-label="Nach rechts drehen"><svg viewBox="0 0 24 24" aria-hidden="true"><path class="fnl" d="M19 12a7 7 0 1 0-3 5.7"/><path class="fnf" d="M22 9l-3.4 4.6L14.4 10z"/></svg></button>
    <button type="button" id="fnf" class="fnb" title="Flacher neigen" aria-label="Flacher neigen"><svg viewBox="0 0 24 24" aria-hidden="true"><path class="fnl" d="M3 17h18M6 13l6-3 6 3"/></svg></button>
    <button type="button" id="fns" class="fnb" title="Steiler neigen" aria-label="Steiler neigen"><svg viewBox="0 0 24 24" aria-hidden="true"><path class="fnl" d="M3 19h18M7 15l5-10 5 10"/></svg></button>
    <button type="button" id="fpo" class="fnb fnt">Von oben</button>
    <button type="button" id="fps" class="fnb fnt">Schräg</button>
    <button type="button" id="fpt" class="fnb fnt">Hinter der Tour</button>
    <span class="slsr" id="fsr" aria-live="polite"></span>
   </div>
   <div class="fhint" id="fhint" role="region" aria-label="Hilfe zur Bedienung" hidden>
    <p id="fhk">Zwei Finger wischen: drehen und neigen · Zwei Finger spreizen: zoomen · oder die Tasten rechts</p>
    <ul id="fhp" hidden><li>Umschalt + Ziehen: drehen und neigen</li><li>Rechte Maustaste oder Strg/Cmd + Ziehen: drehen und neigen</li><li>Pfeiltasten: drehen und neigen</li><li>Alt + Mausrad: neigen</li><li>Mausrad: zoomen</li><li>Maus oder Touchpad wird von selbst erkannt. Passt das nicht, hilft die Auswahl „Bedienung“ unten.</li></ul>
    <button type="button" class="btn sm" id="fhx">Schließen</button>
   </div>
   <div class="fph" id="fph"><img id="fphi" alt=""><span id="fphc"></span></div><div class="fmsg" id="fmsg">Lade Strecke …</div></div>`;
  let raws = [];
  if (SET)
    for (const tid of id.slice(4).split(",").filter(x => BY[x]).sort((a, b) => (BY[a].start_ts || 0) - (BY[b].start_ts || 0))) {
      const r = cleanPts(await api(`/api/tours/${tid}/coords`).catch(() => []));
      if (r.length >= 2) raws.push({r, name: BY[tid].name || tid});
    }
  const raw = SET ? raws.flatMap(x => x.r) : cleanPts(await api(`/api/tours/${t.id}/coords`).catch(() => []));
  if (raw.length < 2) {
    $("#fmsg").textContent = "Für diese Tour liegt noch keine Strecke vor (Tour mit Komoot abgleichen).";
    return;
  }
  await loadLib();
  const PHS0 = SET ? [] : (await api(`/api/photos?tour_id=${t.id}&limit=60`).catch(() => [])).filter(p => p.taken_ts);
  if (!document.createElement("canvas").getContext("webgl")) {
    $("#fmsg").textContent = "Dieser Browser unterstützt kein WebGL, die 3D-Ansicht ist nicht möglich.";
    return;
  }
  const FS = SET ? flightSet(raws.map(x => x.r), raws.map(x => x.name)) : flightPath(raw),
    {P, S, total, cum} = FS,
    N = P.length,
    lnglat = p => [p.lng, p.lat];
  const ras = (tiles, max, attr) => ({type: "raster", tiles, tileSize: 256, maxzoom: max, attribution: attr}),
    tp = k => TBASE + `tiles/${k}/{z}/{x}/{y}`;
  const DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
    demSrc = mz => ({type: "raster-dem", tiles: [DEM], tileSize: 256, maxzoom: mz, encoding: "terrarium", attribution: "Höhendaten: Mapzen/AWS Terrain Tiles"});
  let sty = "osm";
  try {
    sty = localStorage.getItem("mapstyle3d") || (localStorage.getItem("mapstyle") === "topo" ? "topo" : "osm");
  } catch (e) {}
  $("#fb").value = sty;
  /* 3.61.4: Darstellungsstufe (Flüssig / Normal / Schön, js/07-flugrechnung.js). Vorgabe am Handy (html.mob) „Flüssig“, sonst „Schön“ (wie bisher); die Wahl gilt je Gerät. */
  const handy = document.documentElement.classList.contains("mob"),
    dpr = () => window.devicePixelRatio || 1;
  let stRaw = "";
  try {
    stRaw = localStorage.getItem("flug_stufe") || "";
  } catch (e) {}
  let st = FlugCalc.stufe(stRaw, handy),
    S_ = FlugCalc.STUFEN[st];
  $("#fst").value = st;
  const Ttot = SET ? FS.Ttot : 100,
    fOf = uu => {                               // Position (Punktindex) zur Abspielzeit u (0..1)
      if (!SET) return uu * (N - 1);
      const tt = uu * Ttot;
      let lo = 0,
        hi = N - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        FS.T[mid] <= tt ? (lo = mid) : (hi = mid);
      }
      return Math.min(N - 1, lo + Math.max(0, Math.min(1, (tt - FS.T[lo]) / (FS.T[hi] - FS.T[lo] || 1))));
    };
  // Kamera-Bahn: Blickrichtung je Punkt einmal vorab (statt Glättung in jedem Bild), Neigung aus einer Tabelle, die sich beim Fliegen füllt
  const bahn = {S, P, brg: FlugCalc.peilungen(S, Math.max(6, Math.round(N / 60)), Math.max(3, Math.round(N / 100))), neig: null};
  const neuTabelle = () => {
    bahn.neig = FlugCalc.neigTabelle(N, Math.max(1, Math.round(N / 120)));
  };
  neuTabelle();
  // Gelbe Linie: ausgedünnt (je zusammenhängendem Stück ohne Überflug); behalten werden Indizes in P
  const keep = [],
    segId = new Int32Array(N);
  for (let i = 0, sc = 0; i < N; i++) segId[i] = P[i].trans ? (sc++, -1) : sc;
  for (let a = 0; a < N; ) {
    while (a < N && P[a].trans) a++;
    let b = a;
    while (b < N && !P[b].trans) b++;
    if (b - a >= 2) FlugCalc.duenneIdx(P.slice(a, b).map(lnglat), S_.tol).forEach(k => keep.push(a + k));
    a = b;
  }
  const keepLL = keep.map(k => lnglat(P[k]));
  const line = upto => {                        // Linie bis Punkt upto (einschließlich, mit genauem Endpunkt); Übergänge zwischen Touren werden nicht gezeichnet
    const parts = [];
    let cur = [],
      sg = -2,
      lk = -1;
    for (let j = 0; j < keep.length && keep[j] <= upto; j++) {
      const k = keep[j];
      if (segId[k] !== sg) {
        if (cur.length > 1) parts.push(cur);
        cur = [];
        sg = segId[k];
      }
      cur.push(keepLL[j]);
      lk = k;
    }
    if (upto < N && lk >= 0 && lk !== upto && segId[upto] === sg) cur.push(lnglat(P[upto]));
    if (cur.length > 1) parts.push(cur);
    return {type: "Feature", geometry: {type: "MultiLineString", coordinates: parts.length ? parts : [[lnglat(P[0]), lnglat(P[0])]]}};
  };
  const cam0 = FlugCalc.kamera(0, bahn, {neigung: "auto", basis: S_.neig, zBase: 14.8, set: SET, rec: false});
  const m = new maplibregl.Map({
    container: "fm",
    pitch: S_.neig,
    bearing: cam0.bearing,
    center: lnglat(P[0]),
    zoom: 14.8,
    maxPitch: 85,
    attributionControl: {compact: true},
    fadeDuration: 0,
    antialias: false,
    refreshExpiredTiles: false,
    maxTileCacheSize: 400,
    pixelRatio: FlugCalc.pixelRatio(st, dpr()),   // Handy: nie die volle Pixeldichte (bis 3 = neunmal so viele Bildpunkte wie bei 1)
    style: {
      version: 8,
      sources: {
        osm: ras([tp("osm")], 19, "© OpenStreetMap"),
        topo: ras([tp("topo")], 17, "© OpenTopoMap, © OpenStreetMap"),
        sat: ras([tp("sat")], 19, "Esri, Maxar, Earthstar Geographics"),
        dem: demSrc(S_.dem),
      },
      layers: [
        {id: "bg", type: "background", paint: {"background-color": "#cfd8d3"}},
        ...["osm", "topo", "sat"].map(k => ({id: k, type: "raster", source: k, paint: {"raster-fade-duration": 0}, layout: {visibility: k === sty ? "visible" : "none"}})),
      ],
    },
  });
  map = m;
  const camNow = () => ({center: m.getCenter().toArray(), bearing: m.getBearing(), pitch: m.getPitch(), zoom: m.getZoom()});
  const setStyle = k => ["osm", "topo", "sat"].forEach(x => m.setLayoutProperty(x, "visibility", x === k ? "visible" : "none"));
  const dot = document.createElement("div");
  dot.className = "fdot";
  const mk = new maplibregl.Marker({element: dot}).setLngLat(lnglat(P[0]));
  /* Bei Gelände prüft MapLibre für jeden HTML-Marker alle 100 ms per gl.readPixels, ob er hinter einem Berg liegt – das hält die Grafik jedes Mal an (auf Handys besonders teuer).
     Der Punkt liegt immer vor der Kamera, die Prüfung bringt nichts: abschalten. Fotos sind keine Marker mehr, sondern eine Kartenebene. */
  if (typeof mk._updateOpacity === "function") mk._updateOpacity = () => { dot.style.opacity = "1"; };
  mk.addTo(m);
  // Fotos entlang der Strecke: Kartenebene + Einblendung beim Vorbeifliegen
  const phs = PHS0;
  const phU = p => {
    const rel = (p.taken_ts - t.start_ts) * 1000;
    if (raw[0][3] != null) {
      let i = raw.findIndex(q => (q[3] ?? 0) >= rel);
      if (i < 0) i = raw.length - 1;
      return cum[i] / total;
    }
    return Math.min(1, Math.max(0, (p.taken_ts - t.start_ts) / ((t.end_ts || t.start_ts + 1) - t.start_ts || 1)));
  };
  phs.forEach(p => {
    p.u = phU(p);
    p.gi = Math.max(0, Math.min(N - 1, Math.round(p.u * (N - 1)) || 0));
  });
  m.once("style.load", () => {
    m.setTerrain({source: "dem", exaggeration: S_.ueber});
    m.addSource("full", {type: "geojson", data: line(N - 1)});
    m.addSource("done", {type: "geojson", data: line(1)});
    m.addSource("fotos", {type: "geojson", data: {type: "FeatureCollection", features: phs.map(p => ({type: "Feature", properties: {}, geometry: {type: "Point", coordinates: lnglat(P[p.gi])}}))}});
    m.addLayer({
      id: "full-c",
      type: "line",
      source: "full",
      paint: {"line-color": "#fff", "line-width": 7, "line-opacity": 0.55},
      layout: {"line-cap": "round", "line-join": "round"},
    });
    m.addLayer({
      id: "full",
      type: "line",
      source: "full",
      paint: {"line-color": "#6fb5a5", "line-width": 4},
      layout: {"line-cap": "round", "line-join": "round"},
    });
    m.addLayer({
      id: "done",
      type: "line",
      source: "done",
      paint: {"line-color": "#f2c230", "line-width": 5},
      layout: {"line-cap": "round", "line-join": "round"},
    });
    m.addLayer({id: "fotos", type: "circle", source: "fotos", paint: {"circle-radius": 6, "circle-color": "#fff", "circle-stroke-color": "#e11d74", "circle-stroke-width": 3}});
    $("#fmsg").style.display = "none";
    last = lastDraw = performance.now();
    zahl.start = last;
    requestAnimationFrame(tick);
  });
  let u = 0,
    playing = true,
    last = 0,
    lastDraw = 0,
    follow = true,
    lastDone = -1,
    zBase = 14.8,
    blend = null,
    camKey = "",
    hudAt = null,
    hudTxt = "",
    spurAt = null,
    neigAt = 0,
    hier = {lng: P[0].lng, lat: P[0].lat, tgt: 0};
  let ad = FlugCalc.adaptiv(st);
  const zahl = {bilder: 0, hud: 0, spur: 0, neig: 0, start: 0};          // Zählwerke für Tests und die Messung (tests/messung_flug.py)
  const elH = $("#fh"),
    elS = $("#fs"),
    elP = $("#fp"),
    elV = $("#fv"),
    elPi = $("#fpi"),
    elPh = $("#fph"),
    elMsg = $("#fmsg");
  let flHr = null,
    flHrMax = 185;
  if (!SET && window.hrData)
    hrData(t.id).then(h => {
      if (h && h.n) {
        flHr = hrLookup(h);
        flHrMax = h.hrmax;
      }
    });
  const hudText = f => {
    const i = Math.min(N - 1, Math.round(f)),
      p = P[i];
    if (SET && p.trans) return `✈ weiter zu <b>${esc(p.name)}</b>`;
    if (SET) return `<b>${esc(p.name)}</b> · ${nf(p.d / 1000, 1)} / ${fmtKm(total / 1000)} · ${fmtHm(p.alt)}`;
    const bpm = flHr && p.t != null ? flHr(p.t) : null;
    return `<b>${nf(p.d / 1000, 1)}</b> / ${fmtKm(total / 1000)} · <b>${nf(p.alt, 0)}</b> m · ${fmtAuf(p.up)}` + (bpm ? ` · <span style="color:${HR_ZC[hrZone(bpm, flHrMax)]}">❤</span> <b>${bpm}</b>` : "");
  };
  let phUntil = 0,
    prevU = 0;
  const phi = $("#fphi");
  const showPh = p => {
    phi.src = picSrc(p, 500);
    $("#fphc").textContent = fmtUhrzeit(p.taken_ts);
    elPh.classList.add("on");
    phUntil = performance.now() + 4500;
  };
  // Video-Aufnahme: Karte + Kopfzeile + Fotos auf eine Zeichenfläche, per MediaRecorder gespeichert
  let rec = null;
  const compose = () => {
    if (!rec) return;
    const c = m.getCanvas(),
      W = rec.c.width,
      H = rec.c.height,
      x = rec.x;
    x.drawImage(c, 0, 0, W, H);
    const p = P[Math.min(N - 1, Math.round(fOf(u)))];
    x.fillStyle = "rgba(14,42,43,.8)";
    x.fillRect(0, 0, W, 48);
    x.textBaseline = "middle";
    x.font = "600 24px sans-serif";
    x.fillStyle = "#fff";
    x.textAlign = "left";
    x.fillText(t.name, 16, 25);
    x.textAlign = "right";
    x.fillStyle = "#f2c230";
    x.fillText(`${fmtKm(p.d / 1000)} · ${fmtHm(p.alt)}`, W - 16, 25);
    x.fillStyle = "#f2c230";
    x.fillRect(0, H - 6, W * u, 6);
    if (performance.now() < phUntil && phi.complete && phi.naturalWidth) {
      const w = Math.min(340, W * 0.32),
        h = (w * phi.naturalHeight) / phi.naturalWidth;
      x.fillStyle = "#fff";
      x.fillRect(14, H - h - 34, w + 4, h + 4);
      x.drawImage(phi, 16, H - h - 32, w, h);
    }
  };
  m.on("render", compose);
  const stopRec = () => {
    if (!rec) return;
    const r = rec;
    rec = null;
    r.mr.stop();
    $("#frec").textContent = "⏺ Video";
  };
  /** Vor der Aufnahme die Strecke einmal im Schnelldurchlauf abfahren, damit Kartenkacheln und Höhendaten schon geladen sind (keine weißen Flächen im Video). */
  let mapErr = 0, preparing = false;
  m.on("error", () => mapErr++);
  const prewarm = async zoom => {
    const steps = Math.min(40, Math.max(12, Math.round(N / 12))),
      t0 = performance.now(),
      e0 = mapErr,
      g = elMsg,
      u0 = u;
    g.classList.add("prog");
    for (let k = 0; k <= steps; k++) {
      if (map !== m || performance.now() - t0 > 60000 || mapErr - e0 >= 4) break;     // bei schlechter oder fehlender Verbindung nicht ewig warten
      u = k / steps;
      const c = FlugCalc.kamera(fOf(u), bahn, {neigung: null, basis: S_.neig, zBase: zoom, set: SET, rec: false});
      m.jumpTo({center: c.center, bearing: c.bearing, pitch: 62, zoom: c.zoom != null ? c.zoom : zoom});
      g.textContent = "Karte wird geladen … " + Math.round((k / steps) * 100) + " %";
      g.style.display = "";
      await new Promise(ok => {
        let done = false;
        const fin = () => {
          if (!done) {
            done = true;
            ok();
          }
        };
        m.once("idle", fin);
        setTimeout(fin, 3000);
        m.triggerRepaint();
      });
    }
    u = u0;
    g.style.display = "none";
    g.classList.remove("prog");
  };
  $("#frec").onclick = async () => {
    if (rec) return stopRec();
    if (preparing) return;
    const mime =
      window.MediaRecorder &&
      ["video/mp4;codecs=avc1.42E01E", "video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"].find(x =>
        MediaRecorder.isTypeSupported(x)
      );
    if (!mime) return uiAlert("Dieser Browser kann keine Videos aufnehmen (Chrome, Edge, Firefox oder Safari 14.1+ verwenden).");
    preparing = true;
    $("#frec").disabled = true;
    playing = false;
    follow = false;
    const want = +$("#fq").value,
      css = $("#fm").clientWidth || 800,
      oldPR = m.getPixelRatio ? m.getPixelRatio() : window.devicePixelRatio;
    try {
      try {
        m.setPixelRatio(Math.min(3, Math.max(1, want / css)));
      } catch (e) {}
      await prewarm(zBase + 0.9);
    } finally {
      preparing = false;
      $("#frec").disabled = false;
    }
    if (map !== m) return;
    const c = m.getCanvas(),
      W = Math.min(c.width, want),
      oc = document.createElement("canvas");
    oc.width = W;
    oc.height = Math.round((W * c.height) / c.width);
    const mr = new MediaRecorder(oc.captureStream(30), {mimeType: mime, videoBitsPerSecond: want >= 1920 ? 12e6 : want >= 1600 ? 9e6 : 6e6}),
      chunks = [];
    mr.ondataavailable = e => e.data.size && chunks.push(e.data);
    mr.onstop = () => {
      try {
        m.setPixelRatio(oldPR);
      } catch (e) {}
      const a = document.createElement("a"),
        ext = mime.includes("mp4") ? "mp4" : "webm";
      a.href = URL.createObjectURL(new Blob(chunks, {type: mime.split(";")[0]}));
      a.download = (t.name.replace(/[^\w\-äöüÄÖÜß ]+/g, "_").trim() || "flug") + "." + ext;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    };
    rec = {c: oc, x: oc.getContext("2d"), mr, ending: false, stall: 0};
    u = 0;
    prevU = 0;
    playing = true;
    follow = true;
    $("#fc").value = "follow";
    blend = null;
    camKey = "";
    last = performance.now();
    elP.textContent = "⏸ Pause";
    mr.start(500);
    $("#frec").textContent = "⏹ Aufnahme beenden (läuft …)";
  };
  /** Neigungstabelle ein Stück vor der Kamera füllen (eine Stützstelle je Aufruf; jede wird nur einmal gerechnet, sobald Höhendaten da sind). alle = die ganze Strecke. */
  const fuelleNeig = (f, alle) => {
    const T = bahn.neig,
      k0 = Math.floor(f / T.schritt),
      k1 = alle ? T.w.length - 1 : Math.min(T.w.length - 1, k0 + 6);
    for (let k = k0; k <= k1; k++) {
      if (T.w[k] != null) continue;
      const i = Math.min(N - 1, k * T.schritt),
        s = S[i];
      try {
        const z = SET || rec ? zBase : m.getZoom(),
          pm = (512 * 2 ** z) / (40075016.686 * Math.cos((s.lat * Math.PI) / 180)),
          D = m.transform.cameraToCenterDistance / pm;
        if (!(isFinite(D) && D > 0)) return;
        const r = FlugCalc.freieNeigung((a, b) => m.queryTerrainElevation([a, b]), s.lng, s.lat, bahn.brg[i], S_.neig, D);
        zahl.neig++;
        if (r.voll) T.w[k] = r.th;
      } catch (e) {
        return;
      }
      if (!alle) return;
    }
  };
  /** Ein Bild: Punkt, gelbe Linie und Kopfzeile (gedrosselt, nur bei Änderung), Kamera. force = sofort alles. */
  const draw = (now, force) => {
    const f = fOf(u),
      a = Math.min(N - 2, Math.floor(f)),
      r = f - a,
      i = Math.min(N - 1, Math.round(f)),
      cur = [P[a].lng + (P[a + 1].lng - P[a].lng) * r, P[a].lat + (P[a + 1].lat - P[a].lat) * r];
    mk.setLngLat(cur);
    hier = {lng: cur[0], lat: cur[1], tgt: FlugCalc.winkelLerp(bahn.brg[a], bahn.brg[a + 1], r)};     // 3.40.0: aktueller Tourpunkt = Drehpunkt der freien Kamera
    if (i !== lastDone && (force || FlugCalc.faellig(spurAt, now, S_.spur)) && m.getSource("done")) {
      lastDone = i;
      spurAt = now;
      zahl.spur++;
      m.getSource("done").setData(line(Math.max(1, i)));
    }
    if (force || FlugCalc.faellig(hudAt, now, S_.hud)) {
      hudAt = now;
      const tx = hudText(f);
      if (tx !== hudTxt) {
        hudTxt = tx;
        elH.innerHTML = tx;
        zahl.hud++;
      }
      const sv = String(Math.round(u * 1000));
      if (elS.value !== sv) elS.value = sv;
    }
    if (follow) {
      const auto = elPi.value === "auto";
      if (auto && (force || now - neigAt > 100)) {
        neigAt = now;
        fuelleNeig(f, false);
      }
      const c = FlugCalc.kamera(f, bahn, {neigung: auto ? "auto" : null, basis: S_.neig, zBase, set: SET, rec: !!rec}),
        o = {center: c.center, bearing: c.bearing};
      if (c.pitch != null) o.pitch = c.pitch;
      if (c.zoom != null) o.zoom = c.zoom;
      if (blend) {                                         // nach „Kamera frei“ sanft zurück auf die Bahn (nur Anzeige, die Bahn selbst bleibt unverändert)
        const q = Math.min(1, (now - blend.t) / 800),
          e = q * q * (3 - 2 * q),
          A = blend.c;
        o.center = [A.center[0] + (o.center[0] - A.center[0]) * e, A.center[1] + (o.center[1] - A.center[1]) * e];
        o.bearing = FlugCalc.winkelLerp(A.bearing, o.bearing, e);
        if (o.pitch != null) o.pitch = A.pitch + (o.pitch - A.pitch) * e;
        if (o.zoom != null) o.zoom = A.zoom + (o.zoom - A.zoom) * e;
        if (q >= 1) blend = null;
      }
      const key = o.center[0] + "," + o.center[1] + "," + o.bearing + "," + o.pitch + "," + o.zoom;
      if (rec || blend || key !== camKey) {                // Pause und nichts hat sich geändert: Karte nicht neu zeichnen lassen
        camKey = key;
        m.jumpTo(o);
      }
    }
  };
  const meldung = txt => {                                 // kurzer Hinweis in der Bildmitte
    elMsg.textContent = txt;
    elMsg.classList.add("small");
    elMsg.style.display = "";
    clearTimeout(meldung.t);
    meldung.t = setTimeout(() => {
      if (elMsg.textContent === txt) elMsg.style.display = "none";
    }, 4000);
  };
  /** Stufe wechseln: Pixeldichte, Überhöhung, Takte, Grundneigung sofort; die Höhenkacheln (Zoomstufe) ab dem nächsten Flug. auto = Anpassung im Flug (wird nicht gespeichert). */
  const setStufe = (neu, auto) => {
    st = neu;
    S_ = FlugCalc.STUFEN[st];
    if (!rec && !preparing) {
      try {
        m.setPixelRatio(FlugCalc.pixelRatio(st, dpr()));
      } catch (e) {}
    }
    try {
      m.setTerrain({source: "dem", exaggeration: S_.ueber});
    } catch (e) {}
    neuTabelle();
    camKey = "";
    $("#fst").value = st;
    if (!auto) {
      ad = FlugCalc.adaptiv(st);
      try {
        localStorage.setItem("flug_stufe", st);
      } catch (e) {}
    }
  };
  /* Anpassung im Flug: Bildzeit in die Hysterese geben; zu langsam → eine Stufe herunter. Im Testbrowser (Software-Zeichnen, navigator.webdriver) aus, außer ein Test liefert
     die Bildzeiten über window.__flugBildzeit. */
  const bildzeit = ms => (typeof window.__flugBildzeit === "function" ? window.__flugBildzeit(ms) : navigator.webdriver ? 0 : ms);
  const tick = now => {
    if (map !== m) return;
    requestAnimationFrame(tick);
    if (now - lastDraw < FlugCalc.BILD_MIN_MS) return;   // 120/144-Hz-Bildschirm: nur jedes zweite Bild zeichnen
    const frame = now - lastDraw;
    lastDraw = now;
    zahl.bilder++;
    let dt = Math.max(0, Math.min(100, now - last));
    last = now;
    if (rec && !rec.ending && !m.areTilesLoaded() && rec.stall < 1500) {     // bei der Aufnahme kurz warten, bis die Kacheln da sind
      rec.stall += dt;
      dt = 0;
    } else if (rec && m.areTilesLoaded()) rec.stall = 0;
    if (playing) {
      u += (dt / 1000 / Ttot) * +elV.value;
      if (u >= 1) {
        u = 1;
        playing = false;
        elP.textContent = "↻ Nochmal";
      }
      if (!rec && !preparing) {
        const neu = FlugCalc.adaptivSchritt(ad, bildzeit(frame));
        if (neu) {
          setStufe(neu, true);
          meldung("Flug vereinfacht");
        }
      }
    }
    draw(now, false);
    if (playing)
      phs.forEach(p => {
        if (prevU < p.u && u >= p.u) showPh(p);
      });
    prevU = u;
    if (elPh.classList.contains("on") && now > phUntil) elPh.classList.remove("on");
    if (rec && u >= 1 && !rec.ending) {
      rec.ending = true;
      setTimeout(stopRec, 1800);
    }
  };
  /* Schnittstelle für Tests und die Messung: Zählwerke, Stufe, Kamera an einer Position (Teil der Strecke 0…1; gleiche Position → gleiche Kamera). */
  $("#fm")._flug = {
    stufe: () => st,
    zahlen: () => Object.assign({ms: performance.now() - zahl.start, linie: keep.length, punkte: N}, zahl),
    kameraBei: uu => FlugCalc.kamera(fOf(Math.max(0, Math.min(1, uu))), bahn, {neigung: elPi.value === "auto" ? "auto" : null, basis: S_.neig, zBase, set: SET, rec: !!rec}),
    stelleZeit(uu) {
      playing = false;
      elP.textContent = "▶ Weiter";
      u = Math.max(0, Math.min(1, uu));
      prevU = u;
      blend = null;
      draw(performance.now(), true);
      return this.kameraBei(u);
    },
    bildzeiten(l) {
      let r = null;
      l.forEach(ms => {
        const n = FlugCalc.adaptivSchritt(ad, ms);
        if (n) {
          r = n;
          setStufe(n, true);
          meldung("Flug vereinfacht");
        }
      });
      return r;
    },
  };
  elP.onclick = () => {
    if (u >= 1) {
      u = 0;
      playing = true;
    } else playing = !playing;
    elP.textContent = playing ? "⏸ Pause" : "▶ Weiter";
    if (playing) last = performance.now();
  };
  elS.oninput = () => {
    u = +elS.value / 1000;
  };
  // Bedienelemente blenden sich beim Abspielen nach ein paar Sekunden aus; ein Tipp auf die Karte bringt sie zurück
  const flEl = $("#fl");
  let hideT = null;
  const wake = () => {
    flEl.classList.remove("idle");
    clearTimeout(hideT);
    hideT = setTimeout(function again() {
      if (!flEl.isConnected) return;
      if (playing) flEl.classList.add("idle");
      else hideT = setTimeout(again, 2000);
    }, 4000);
  };
  ["pointerdown", "pointermove", "wheel", "keydown"].forEach((ev) => flEl.addEventListener(ev, wake, { passive: true, capture: true }));
  wake();
  $("#fc").onchange = () => {
    follow = $("#fc").value === "follow";
    if (follow) blend = {t: performance.now(), c: camNow()};
    camKey = "";
  };
  $("#fz").onchange = () => {
    zBase = +$("#fz").value;
    m.setZoom(zBase);
    neuTabelle();
    camKey = "";
  };
  $("#fpi").onchange = () => {
    if ($("#fpi").value === "auto") blend = {t: performance.now(), c: camNow()};
    else m.setPitch(+$("#fpi").value);
    camKey = "";
  };
  $("#fst").onchange = () => setStufe(FlugCalc.stufe($("#fst").value, handy), false);
  $("#fb").onchange = () => {
    setStyle($("#fb").value);
    try {
      localStorage.setItem("mapstyle3d", $("#fb").value);
    } catch (e) {}
  };
  $("#ffs").onclick = () => {
    const el = $("#fl");
    document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen && el.requestFullscreen();
  };
  // Multitouch in der freien Kamera: zwei Finger zoomen (Spreizen/Zusammenziehen), drehen (Verdrehen) und kippen (beide nach oben/unten)
  try {
    m.touchZoomRotate.enable();
    m.touchZoomRotate.enableRotation();
    m.touchPitch.enable();
    m.dragRotate.enable();
  } catch (e) {}
  /* Freie Kamera (reine Funktionen: 07-flugsteuerung.js). Im Modus „Kamera folgt“ bleibt alles wie bisher.
     3.40.0: kein „Drehen“-Modus mehr. Stattdessen a) immer sichtbare Bedienleiste rechts (Kompass, Drehen, Neigen, Voreinstellungen, Hilfe),
     b) Zweifinger-Wischen auf dem Touchpad dreht (seitwärts) und neigt (senkrecht) um den aktuellen Tourpunkt, Pinch (Strg+wheel) und das Mausrad zoomen;
        Maus oder Touchpad wird je Geste geschätzt (flWheelKind) oder über die Auswahl „Bedienung“ festgelegt (je Browser gemerkt, wie der Kartenstil),
     c) Safari-Geste (gesturechange) dreht und zoomt; die gleichzeitig gemeldeten Strg+wheel-Ereignisse werden verworfen (sonst doppelter Zoom),
     d) für Geübte: Umschalt+Ziehen, rechte Taste bzw. Strg/Cmd+Ziehen (MapLibre), Pfeiltasten, Alt+Rad.
     Statt MapLibres NavigationControl (visualizePitch) eine eigene Leiste: dessen Kompass kennt weder Neigen-Tasten noch Voreinstellungen und passt nicht zum dunklen Bedienfeld. */
  const fm = $("#fm");
  fm._map = m;                                                               // für Tests und Fehlersuche
  fm._hier = () => hier;
  const ruhig = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  let rd = null, panWas = true, srT = null, hintAuto = false;
  let pref = "auto";
  try {
    pref = localStorage.getItem("flug_bedienung") || "auto";
  } catch (e) {}
  if (!/^(auto|maus|touchpad)$/.test(pref)) pref = "auto";
  $("#fin").value = pref;
  $("#fin").onchange = () => {
    pref = $("#fin").value;
    wst.kind = null;
    try {
      localStorage.setItem("flug_bedienung", pref);
    } catch (e) {}
  };
  const wst = {t: 0, kind: null};
  const sagen = () => {                                                      // Richtung und Neigung für Screenreader, gedrosselt (erst wenn die Bewegung kurz ruht)
    clearTimeout(srT);
    srT = setTimeout(() => {
      const el = $("#fsr");
      if (el) el.textContent = `Blick nach ${flRichtung(m.getBearing())} · Neigung ${Math.round(m.getPitch())} Grad`;
    }, 700);
  };
  let nadelAt = 0, nadelT = null;
  const nadel = () => {                                                      // Kompass: Nadel zeigt nach Norden, wird mit der Neigung flacher (im Flug höchstens 5 × je Sekunde, danach der letzte Stand)
    const jetzt = performance.now();
    if (playing && follow && jetzt - nadelAt < 200) {
      if (!nadelT) nadelT = setTimeout(() => { nadelT = null; nadel(); }, 200);
      return;
    }
    nadelAt = jetzt;
    const k = $("#fnk");
    if (k) k.style.transform = `scaleY(${Math.max(0.5, Math.cos((m.getPitch() * Math.PI) / 180)).toFixed(3)}) rotate(${(-m.getBearing()).toFixed(1)}deg)`;
  };
  m.on("rotate", nadel);
  m.on("pitch", nadel);
  nadel();
  const hint = (voll, auto) => {
    const h = $("#fhint");
    $("#fhp").hidden = !voll;
    h.hidden = false;
    hintAuto = !!auto;
    $("#fnh").setAttribute("aria-expanded", "true");
    if (!auto) $("#fhx").focus();
  };
  const hintZu = () => {
    const h = $("#fhint"), war = !h.hidden && h.contains(document.activeElement);
    h.hidden = true;
    $("#fnh").setAttribute("aria-expanded", "false");
    if (war && !hintAuto) $("#fnh").focus();
  };
  $("#fhx").onclick = hintZu;
  $("#fnh").onclick = () => ($("#fhint").hidden ? hint(true, false) : hintZu());
  $("#fhint").addEventListener("keydown", e => {
    if (e.key === "Escape") { e.stopPropagation(); hintZu(); }
  });
  const hintEinmal = () => {                                                 // beim ersten Wechsel in die freie Kamera, einmal je Browser
    try {
      if (localStorage.getItem("flug_hinweis")) return;
      localStorage.setItem("flug_hinweis", "1");
    } catch (e) {
      return;
    }
    hint(false, true);
  };
  const freeNow = () => {
    if (follow) {
      follow = false;
      $("#fc").value = "free";
    }
    hintEinmal();
  };
  const turn = d => {                                                        // drehen um den aktuellen Tourpunkt (Orbit), neigen um die Bildmitte
    if (!d) return;
    fm.dataset.rot = String((+fm.dataset.rot || 0) + 1);                      // Zähler der eigenen Dreh-/Kippschritte (Tests)
    const o = {};
    if (d.bearing) {
      const c = m.getCenter(), z = flOrbit({lng: c.lng, lat: c.lat}, hier, d.bearing);
      o.bearing = flNorm(m.getBearing() + d.bearing);
      o.center = [z.lng, z.lat];
    }
    if (d.pitch) o.pitch = flClampPitch(m.getPitch() + d.pitch);
    m.jumpTo(o);
    sagen();
  };
  const preset = name => {
    freeNow();
    const v = flPreset(name, {bearing: m.getBearing(), pitch: m.getPitch()}, hier.tgt);
    if (!v) return;
    fm.dataset.rot = String((+fm.dataset.rot || 0) + 1);
    const o = {bearing: v.bearing, pitch: v.pitch};
    if (v.zentrieren) o.center = [hier.lng, hier.lat];
    if (ruhig()) m.jumpTo(o);                                                // keine animierten Kamerasprünge bei „Bewegung reduzieren“
    else m.easeTo(Object.assign(o, {duration: 500}));
    sagen();
  };
  const taste = (id, fn) => ($("#" + id).onclick = () => { freeNow(); fn(); });
  taste("fnl", () => turn({bearing: -15, pitch: 0}));
  taste("fnr", () => turn({bearing: 15, pitch: 0}));
  taste("fnf", () => turn({bearing: 0, pitch: 10}));
  taste("fns", () => turn({bearing: 0, pitch: -10}));
  $("#fnn").onclick = () => preset("nord");
  $("#fpo").onclick = () => preset("oben");
  $("#fps").onclick = () => preset("schraeg");
  $("#fpt").onclick = () => preset("hinter");
  try {
    m.boxZoom.disable();                                                     // Umschalt+Ziehen ist sonst „Rahmen aufziehen“
  } catch (e) {}
  const rdEnd = () => {
    if (!rd) return;
    rd = null;
    if (panWas) try { m.dragPan.enable(); } catch (e) {}
  };
  fm.addEventListener("pointerdown", e => {
    if (rd || follow || !e.isPrimary || e.button !== 0 || !e.shiftKey) return;
    if (e.target.closest && e.target.closest(".maplibregl-ctrl")) return;
    rd = {id: e.pointerId, x: e.clientX, y: e.clientY};
    panWas = m.dragPan.isEnabled();
    m.dragPan.disable();
    try { fm.setPointerCapture(e.pointerId); } catch (x) {}
    e.preventDefault();
  }, true);
  fm.addEventListener("pointermove", e => {
    if (!rd || e.pointerId !== rd.id) return;
    turn(flDragDelta(e.clientX - rd.x, e.clientY - rd.y));
    rd.x = e.clientX;
    rd.y = e.clientY;
  }, true);
  ["pointerup", "pointercancel", "lostpointercapture"].forEach(n => fm.addEventListener(n, e => rd && e.pointerId === rd.id && rdEnd(), true));
  let geste = null;                                                          // laufende Safari-Geste {rotation, scale}
  let folgT = -1e9;                                                          // letzte wheel-Zeit einer Geste, die im Modus „Kamera folgt“ begann
  fm.addEventListener("wheel", e => {
    const jetzt = performance.now();
    if (follow || jetzt - folgT < FL_GESTE_MS) {                             // „Kamera folgt“: wie bisher (MapLibre zoomt, das beendet das Folgen) – und zwar für die ganze Geste,
      folgT = jetzt;                                                         // nicht nur für ihr erstes Ereignis (sonst würde der Rest des Wischens plötzlich neigen)
      return;
    }
    const d = flWheelAction(e, e.ctrlKey || e.metaKey || e.altKey ? null : flWheelKind(e, wst, performance.now(), pref), !!geste);
    if (!d) return;                                                          // Mausrad und Pinch: MapLibre zoomt
    e.preventDefault();
    e.stopPropagation();
    if (!d.skip) turn(d);
  }, {capture: true, passive: false});
  fm.addEventListener("keydown", e => {
    if (follow || e.ctrlKey || e.metaKey || e.altKey) return;
    const d = flKeyDelta(e.key, e.shiftKey);
    if (!d) return;
    e.preventDefault();                                                      // die Seite scrollt nicht, MapLibre verschiebt nicht
    e.stopPropagation();
    turn(d);
  }, true);
  if ("GestureEvent" in window) {
    fm.addEventListener("gesturestart", e => {
      geste = {rotation: e.rotation || 0, scale: e.scale || 1};
      e.preventDefault();
    }, true);
    fm.addEventListener("gesturechange", e => {
      e.preventDefault();
      if (follow || !geste) return;
      const jetzt = {rotation: e.rotation || 0, scale: e.scale || 1}, d = flGestureStep(geste, jetzt);
      geste = jetzt;
      if (d.zoom) m.setZoom(m.getZoom() + d.zoom);
      turn({bearing: d.bearing, pitch: 0});
    }, true);
    ["gestureend", "gesturecancel"].forEach(n => fm.addEventListener(n, () => (geste = null), true));
  }
  $("#fc").addEventListener("change", () => {
    if ($("#fc").value === "free") hintEinmal();
  });
  const goFree = ev => {                    // jede eigene Bewegung (Maus, Finger, Mausrad) beendet das automatische Folgen
    if (follow && ev && ev.originalEvent) {
      follow = false;
      $("#fc").value = "free";
      hintEinmal();
    }
  };
  ["dragstart", "rotatestart", "pitchstart", "zoomstart"].forEach(n => m.on(n, goFree));
  let terr = 0;
  /* 3.24.0: OpenStreetMap und OpenTopoMap sperren Abrufe ohne Herkunftsangabe („Access blocked“). Die App sendet nach außen keine (Referrer-Policy same-origin), und MapLibre kann
     je Abruf keine Referrer-Policy setzen. Darum laden diese beiden Karten im 3D-Flug nie direkt, sondern nur über den Kachel-Cache des Servers (/tiles/…); nur Esri-Satellit weicht aus. */
  const DIRECT = {
    sat: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  };
  m.on("error", e => {
    console.warn("3D:", e && e.error && e.error.message);
    if (e.sourceId && DIRECT[e.sourceId] && ++terr === 4) {
      const sc = m.getSource(e.sourceId);
      sc && sc.setTiles && sc.setTiles([DIRECT[e.sourceId]]);
    }
    if (e && e.error && /terrain|dem/i.test(String(e.error.message))) {
      const g = $("#fmsg");
      g.textContent = "Höhendaten nicht erreichbar – Gelände wird flach dargestellt";
      g.classList.add("small");
      g.style.display = "";
    }
  });
};
