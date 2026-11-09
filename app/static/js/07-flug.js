/* =====================  3D-Flug  ===================== */
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
function clearPitch(elev, lng, lat, bearing, base, D, floor = 28) {
  const br = (bearing * Math.PI) / 180,
    kx = 111320 * Math.cos((lat * Math.PI) / 180),
    ky = 110540,
    aim = 25;                                        // Blickziel etwas über dem Boden, damit der Punkt selbst nicht verdeckt ist
  for (let th = base; th >= floor; th -= 4) {
    const a = (th * Math.PI) / 180,
      dh = D * Math.sin(a),
      hz = D * Math.cos(a);
    let ok = true;
    for (let k = 1; k <= 14 && ok; k++) {
      const f = k / 15,
        e = elev(lng - (Math.sin(br) * dh * (1 - f)) / kx, lat - (Math.cos(br) * dh * (1 - f)) / ky);
      if (e != null && e > aim + (hz - aim) * (1 - f) - 25) ok = false;
    }
    if (ok) return th;
  }
  return floor;
}
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
  if (!t) throw new Error("Tour nicht gefunden");
  $("#main").className = "wide";
  $("#main").innerHTML =
    `<div class="flight" id="fl"><div id="fm"></div><div class="fbar"><a class="btn ghost sm" href="${SET ? "#" : "#/tour/" + t.id}"${SET ? ' data-act="back"' : ""}>‹ Zurück</a><b class="ft">${esc(t.name)}</b><span class="sp"></span><span id="fh" class="fh"></span></div>
   <div class="fctl"><button class="btn sm" id="fp">⏸ Pause</button><input type="range" id="fs" min="0" max="1000" value="0" aria-label="Position">
    <select id="fv" title="Tempo"><option value=".5">0,5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option><option value="8">8×</option></select>
    <select id="fc" title="Kamera"><option value="follow">Kamera folgt</option><option value="free">Kamera frei</option></select>
    <select id="fz" title="Flughöhe"><option value="16">nah</option><option value="14.8" selected>mittel</option><option value="13.4">weit</option></select>
    <select id="fpi" title="Neigung"><option value="auto" selected>automatisch (weicht Bergen aus)</option><option value="55">flach</option><option value="68">schräg</option><option value="78">sehr schräg</option></select>
    <select id="fb" title="Karte"><option value="osm">Straßenkarte</option><option value="topo">Topografisch</option><option value="sat">Satellit</option></select>
    <button class="btn ghost sm" id="frec" title="Flug als Video aufnehmen und speichern">⏺ Video</button><button class="btn ghost sm" id="ffs" title="Vollbild">⛶</button></div><div class="fph" id="fph"><img id="fphi" alt=""><span id="fphc"></span></div><div class="fmsg" id="fmsg">Lade Strecke …</div></div>`;
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
  let sty = "osm";
  try {
    sty = localStorage.getItem("mapstyle3d") || (localStorage.getItem("mapstyle") === "topo" ? "topo" : "osm");
  } catch (e) {}
  $("#fb").value = sty;
  const m = new maplibregl.Map({
    container: "fm",
    pitch: 68,
    bearing: brg([P[0].lat, P[0].lng], [S[Math.min(10, N - 1)].lat, S[Math.min(10, N - 1)].lng]),
    center: lnglat(P[0]),
    zoom: 14.8,
    maxPitch: 85,
    attributionControl: {compact: true},
    style: {
      version: 8,
      sources: {
        osm: ras([tp("osm")], 19, "© OpenStreetMap"),
        topo: ras([tp("topo")], 17, "© OpenTopoMap, © OpenStreetMap"),
        sat: ras([tp("sat")], 19, "Esri, Maxar, Earthstar Geographics"),
        dem: {
          type: "raster-dem",
          tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
          tileSize: 256,
          maxzoom: 15,
          encoding: "terrarium",
          attribution: "Höhendaten: Mapzen/AWS Terrain Tiles",
        },
      },
      layers: [
        {id: "bg", type: "background", paint: {"background-color": "#cfd8d3"}},
        ...["osm", "topo", "sat"].map(k => ({id: k, type: "raster", source: k, layout: {visibility: k === sty ? "visible" : "none"}})),
      ],
    },
  });
  map = m;
  const setStyle = k => ["osm", "topo", "sat"].forEach(x => m.setLayoutProperty(x, "visibility", x === k ? "visible" : "none"));
  const dot = document.createElement("div");
  dot.className = "fdot";
  const mk = new maplibregl.Marker({element: dot}).setLngLat(lnglat(P[0])).addTo(m);
  const line = (a, b) => {                      // Übergänge zwischen Touren werden nicht als Linie gezeichnet
    const segs = [];
    let cur = [];
    for (let i = a; i < b; i++) {
      if (P[i].trans) {
        if (cur.length > 1) segs.push(cur);
        cur = [];
      } else cur.push(lnglat(P[i]));
    }
    if (cur.length > 1) segs.push(cur);
    return {type: "Feature", geometry: {type: "MultiLineString", coordinates: segs.length ? segs : [[lnglat(P[0]), lnglat(P[0])]]}};
  };
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
  m.once("style.load", () => {
    m.setTerrain({source: "dem", exaggeration: 1.5});
    m.addSource("full", {type: "geojson", data: line(0, N)});
    m.addSource("done", {type: "geojson", data: line(0, 2)});
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
    $("#fmsg").style.display = "none";
    last = performance.now();
    requestAnimationFrame(tick);
  });
  let u = 0,
    playing = true,
    bear = m.getBearing(),
    last = 0,
    follow = true,
    dragged = false,
    lastDone = -1,
    pitchNow = 68,
    pitchAt = 0,
    pitchWant = 68,
    zBase = 14.8,
    zoomLift = 0;
  const at = (A, f, key) => {
    const i = Math.min(N - 2, Math.floor(f)),
      r = f - i;
    return A[i][key] + (A[i + 1][key] - A[i][key]) * r;
  };
  const place = () => {
    const f = fOf(u),
      lat = at(S, f, "lat"),
      lng = at(S, f, "lng"),
      cur = {lat: at(P, f, "lat"), lng: at(P, f, "lng")};
    mk.setLngLat([cur.lng, cur.lat]);
    const i = Math.min(N - 1, Math.round(f));
    if (i !== lastDone && m.getSource("done")) {
      lastDone = i;
      m.getSource("done").setData(line(0, Math.max(2, i + 1)));
    }
    const look = S[Math.min(N - 1, Math.round(f) + Math.max(6, Math.round(N / 60)))],
      tgt = brg([lat, lng], [look.lat, look.lng]);
    return {lat, lng, tgt, f};
  };
  const hud = f => {
    const i = Math.min(N - 1, Math.round(f)),
      p = P[i];
    if (SET && p.trans) return ($("#fh").innerHTML = `✈ weiter zu <b>${esc(p.name)}</b>`);
    if (SET) return ($("#fh").innerHTML = `<b>${esc(p.name)}</b> · ${nf(p.d / 1000, 1)} / ${nf(total / 1000, 1)} km · ${nf(p.alt, 0)} m`);
    $("#fh").innerHTML = `<b>${nf(p.d / 1000, 1)}</b> / ${nf(total / 1000, 1)} km · <b>${nf(p.alt, 0)}</b> m · ↑ ${nf(p.up, 0)} m`;
  };
  // Fotos entlang der Strecke: Marker + Einblendung beim Vorbeifliegen
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
    const k = P[Math.max(0, Math.min(N - 1, Math.round(p.u * (N - 1)) || 0))],
      el = document.createElement("div");
    el.className = "fcam";
    el.title = "Foto";
    new maplibregl.Marker({element: el}).setLngLat([k.lng, k.lat]).addTo(m);
  });
  let phUntil = 0,
    prevU = 0;
  const phi = $("#fphi");
  const showPh = p => {
    phi.src = `/pic/${p.id}?size=500`;
    $("#fphc").textContent = new Date(p.taken_ts * 1000).toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"}) + " Uhr";
    $("#fph").classList.add("on");
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
    x.fillText(`${nf(p.d / 1000, 1)} km · ${nf(p.alt, 0)} m`, W - 16, 25);
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
  $("#frec").onclick = () => {
    if (rec) return stopRec();
    const mime =
      window.MediaRecorder &&
      ["video/mp4;codecs=avc1.42E01E", "video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"].find(x =>
        MediaRecorder.isTypeSupported(x)
      );
    if (!mime) return alert("Dieser Browser kann keine Videos aufnehmen (Chrome, Edge, Firefox oder Safari 14.1+ verwenden).");
    const c = m.getCanvas(),
      W = Math.min(c.width, 1280),
      oc = document.createElement("canvas");
    oc.width = W;
    oc.height = Math.round((W * c.height) / c.width);
    const mr = new MediaRecorder(oc.captureStream(30), {mimeType: mime, videoBitsPerSecond: 6e6}),
      chunks = [];
    mr.ondataavailable = e => e.data.size && chunks.push(e.data);
    mr.onstop = () => {
      const a = document.createElement("a"),
        ext = mime.includes("mp4") ? "mp4" : "webm";
      a.href = URL.createObjectURL(new Blob(chunks, {type: mime.split(";")[0]}));
      a.download = (t.name.replace(/[^\w\-äöüÄÖÜß ]+/g, "_").trim() || "flug") + "." + ext;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    };
    rec = {c: oc, x: oc.getContext("2d"), mr, ending: false};
    u = 0;
    prevU = 0;
    playing = true;
    follow = true;
    $("#fc").value = "follow";
    bear = m.getBearing();
    last = performance.now();
    $("#fp").textContent = "⏸ Pause";
    mr.start(500);
    $("#frec").textContent = "⏹ Aufnahme beenden (läuft …)";
  };
  const rec_skip = () => false;
  const tick = now => {
    if (map !== m) return;
    const dt = Math.max(0, Math.min(100, now - last));
    last = now;
    if (playing) {
      u += (dt / 1000 / Ttot) * +$("#fv").value;
      if (u >= 1) {
        u = 1;
        playing = false;
        $("#fp").textContent = "↻ Nochmal";
      }
      $("#fs").value = Math.round(u * 1000);
    }
    const {lat, lng, tgt, f} = place();
    hud(f);
    if (playing)
      phs.forEach(p => {
        if (prevU < p.u && u >= p.u) showPh(p);
      });
    prevU = u;
    if ($("#fph").classList.contains("on") && performance.now() > phUntil) $("#fph").classList.remove("on");
    if (rec && u >= 1 && !rec.ending) {
      rec.ending = true;
      setTimeout(stopRec, 1800);
    }
    if (follow) {
      const d = ((tgt - bear + 540) % 360) - 180;
      bear = (bear + d * Math.min(1, dt / 600) + 360) % 360;
      const o = {center: [lng, lat], bearing: bear};
      if ($("#fpi").value === "auto" && !rec_skip()) {     // Gelände im Weg? Neigung sanft verringern (Blick steiler von oben), danach wieder zurück
        if (now - pitchAt > 130) {
          pitchAt = now;
          try {
            const pm = (512 * 2 ** m.getZoom()) / (40075016.686 * Math.cos((lat * Math.PI) / 180)),
              D = m.transform.cameraToCenterDistance / pm;
            pitchWant = isFinite(D) && D > 0 ? clearPitch((a, b) => m.queryTerrainElevation([a, b]), lng, lat, bear, 68, D) : 68;
          } catch (e) {
            pitchWant = 68;
          }
        }
        const pt = P[Math.min(N - 1, Math.round(f))];
        if (SET && pt.trans) pitchWant = Math.min(pitchWant, 68 - 22 * Math.sin(Math.PI * pt.tq));    // im Übergang steiler von oben
        const step = Math.min(1, dt / 700);                 // weich: ca. 0,7 s Annäherung, nach unten schneller als nach oben
        pitchNow += (pitchWant - pitchNow) * step * (pitchWant < pitchNow ? 1 : 0.35);
        o.pitch = pitchNow;
      }
      if (SET) {                                            // Reiseflug: im Übergang aufsteigen (herauszoomen) und danach wieder absinken
        const pt = P[Math.min(N - 1, Math.round(f))];
        zoomLift += ((pt.trans ? pt.lift * Math.sin(Math.PI * pt.tq) : 0) - zoomLift) * Math.min(1, dt / 450);
        o.zoom = zBase - zoomLift;
      }
      m.jumpTo(o);
    }
    requestAnimationFrame(tick);
  };
  $("#fp").onclick = () => {
    if (u >= 1) {
      u = 0;
      playing = true;
    } else playing = !playing;
    $("#fp").textContent = playing ? "⏸ Pause" : "▶ Weiter";
    if (playing) last = performance.now();
  };
  $("#fs").oninput = () => {
    u = +$("#fs").value / 1000;
  };
  $("#fc").onchange = () => {
    follow = $("#fc").value === "follow";
    if (follow) bear = m.getBearing();
  };
  $("#fz").onchange = () => {
    zBase = +$("#fz").value;
    m.setZoom(zBase - (follow ? zoomLift : 0));
  };
  $("#fpi").onchange = () => {
    if ($("#fpi").value === "auto") pitchNow = m.getPitch();
    else m.setPitch(+$("#fpi").value);
  };
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
  const goFree = ev => {                    // jede eigene Bewegung (Maus, Finger, Mausrad) beendet das automatische Folgen
    if (follow && ev && ev.originalEvent) {
      follow = false;
      $("#fc").value = "free";
    }
  };
  ["dragstart", "rotatestart", "pitchstart", "zoomstart"].forEach(n => m.on(n, goFree));
  let terr = 0;
  const DIRECT = {
    osm: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    topo: "https://tile.opentopomap.org/{z}/{x}/{y}.png",
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
