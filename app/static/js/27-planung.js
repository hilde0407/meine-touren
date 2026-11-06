/* =====================  Touren planen: zeichnen oder GPX laden, Höhenmeter und Zeit nach eigenem Tempo  ===================== */
const PLAN_DEF = {foot: [0.22, 0.0018], bike: [0.055, 0.0015], ski: [0.2, 0.0035], run: [0.1, 0.001], other: [0.22, 0.0018]}; // h je km, h je Höhenmeter (Gesamtzeit inkl. Pausen)

/* Eigenes Tempo aus dem Archiv: Gesamtzeit ≈ a·km + b·Höhenmeter (kleinste Quadrate); sonst Standardwerte */
function paceModel(sport) {
  const g = sportGrp(sport),
    T = TOURS.filter(t => sportGrp(t.sport) === g && t.km >= 3 && t.h >= 0.4 && t.h < 14 && t.up_m != null && t.km / t.h < 60);
  const def = PLAN_DEF[g] || PLAN_DEF.other;
  if (T.length < 6) return {a: def[0], b: def[1], n: 0, rel: 0.18};
  let sxx = 0, sxy = 0, syy = 0, sxh = 0, syh = 0;
  T.forEach(t => {
    sxx += t.km * t.km;
    sxy += t.km * t.up_m;
    syy += t.up_m * t.up_m;
    sxh += t.km * t.h;
    syh += t.up_m * t.h;
  });
  const det = sxx * syy - sxy * sxy;
  let a = det ? (sxh * syy - syh * sxy) / det : 0,
    b = det ? (syh * sxx - sxh * sxy) / det : 0;
  if (!(a > 0.02) || !(b >= 0) || b > 0.01) return {a: def[0], b: def[1], n: 0, rel: 0.18};
  const res = T.map(t => (t.h - (a * t.km + b * t.up_m)) / t.h),
    rmse = Math.sqrt(res.reduce((c, x) => c + x * x, 0) / res.length);
  return {a, b, n: T.length, rel: Math.min(0.3, Math.max(0.08, rmse)), kmh: T.reduce((c, t) => c + t.km, 0) / T.reduce((c, t) => c + t.h, 0)};
}
const planTime = (m, km, up) => {
  const h = m.a * km + m.b * (up || 0);
  return {h, lo: h * (1 - m.rel), hi: h * (1 + m.rel)};
};
const hmm = h => `${Math.floor(h)}:${pad2(Math.round((h % 1) * 60) % 60)}`;

function densify(pts, step = 50, max = 2000) {
  let tot = 0;
  for (let i = 1; i < pts.length; i++) tot += hav(pts[i - 1], pts[i]);
  step = Math.max(step, tot / max);
  const out = [pts[0]];
  let next = step,
    acc = 0;
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1],
      b = pts[i],
      d = hav(a, b);
    while (d > 0 && next <= acc + d) {
      const f = (next - acc) / d;
      out.push([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]);
      next += step;
    }
    acc += d;
  }
  out.push(pts[pts.length - 1]);
  return out;
}
const pathKm = pts => {
  let d = 0;
  for (let i = 1; i < pts.length; i++) d += hav(pts[i - 1], pts[i]);
  return d / 1000;
};
function parseGpxPts(text) {
  const x = new DOMParser().parseFromString(text, "application/xml");
  let n = [...x.getElementsByTagName("trkpt")];
  if (!n.length) n = [...x.getElementsByTagName("rtept")];
  if (!n.length) n = [...x.getElementsByTagName("wpt")];
  return n.map(e => [+e.getAttribute("lat"), +e.getAttribute("lon")]).filter(p => isFinite(p[0]) && isFinite(p[1]));
}
function planGpx(name, pts, ele) {
  const esc2 = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Meine Touren" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>${esc2(name)}</name><trkseg>${pts
    .map((p, i) => `<trkpt lat="${p[0].toFixed(6)}" lon="${p[1].toFixed(6)}">${ele && ele[i] != null ? `<ele>${ele[i]}</ele>` : ""}</trkpt>`)
    .join("")}</trkseg></trk></gpx>`;
}
function planProfile(dense, ele) {
  const W = 900, H = 170, L = 40, B = 22, T = 8, n = ele.length;
  const d = [0];
  for (let i = 1; i < n; i++) d.push(d[i - 1] + hav(dense[i - 1], dense[i]));
  const D = d[n - 1] || 1,
    mn = Math.min(...ele),
    mx = Math.max(...ele),
    pad = Math.max(10, (mx - mn) * 0.08),
    lo = mn - pad,
    hi = mx + pad,
    x = v => L + (v / D) * (W - L - 6),
    y = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const line = ele.map((h, i) => `${i ? "L" : "M"}${x(d[i]).toFixed(1)},${y(h).toFixed(1)}`).join("");
  const ticks = [lo + pad, (lo + hi) / 2, hi - pad].map(v => `<text x="2" y="${y(v) + 4}" font-size="11" fill="currentColor" opacity=".6">${Math.round(v)} m</text><line x1="${L}" x2="${W - 6}" y1="${y(v)}" y2="${y(v)}" stroke="currentColor" opacity=".12"/>`).join("");
  const kms = [0, 0.25, 0.5, 0.75, 1].map(f => `<text x="${x(D * f)}" y="${H - 4}" font-size="11" text-anchor="${f === 0 ? "start" : f === 1 ? "end" : "middle"}" fill="currentColor" opacity=".6">${nf((D * f) / 1000, 1)} km</text>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto">${ticks}${kms}<path d="${line}L${x(D)},${H - B}L${L},${H - B}Z" fill="var(--green,#2f8f5f)" opacity=".22"/><path d="${line}" fill="none" stroke="var(--green,#2f8f5f)" stroke-width="2.2"/></svg>`;
}

VIEWS.plan = async (pid, q) => {
  const P = {id: null, name: "", sport: "hike", wp: [], note: "", ele: null, dense: null, up: null, down: null, max: null};
  $("#main").className = "";
  const [plans, guides] = await Promise.all([api("/api/plans").catch(() => []), api("/api/guides").catch(() => [])]);
  const sports = Object.keys(SPORT);
  $("#main").innerHTML = `<div class="row"><a class="back" href="#/tours">‹ Alle Touren</a></div>
   <div class="sec"><h2>Tour planen</h2><span class="sub">Punkte in die Karte klicken oder eine GPX-Datei laden – Länge, Höhenmeter und Zeit nach deinem Tempo</span></div>
   <div class="row" style="gap:8px;flex-wrap:wrap"><input id="pn" placeholder="Name der Planung" maxlength="120" style="min-width:230px"><select id="ps">${sports.map(s => `<option value="${s}" ${s === "hike" ? "selected" : ""}>${sName(s)}</option>`).join("")}</select>
    <label class="btn alt sm" style="cursor:pointer">GPX laden …<input type="file" id="pg" accept=".gpx,application/gpx+xml,text/xml" style="display:none"></label>
    ${guides.length ? `<select id="pgd" style="max-width:260px"><option value="">Aus Wanderführer laden …</option>${guides.map(g => `<option value="${g.id}">${esc(g.book ? g.book + " – " : "")}${esc(g.title)}</option>`).join("")}</select>` : ""}
    <button class="btn ghost sm" id="pundo">↶ Letzten Punkt entfernen</button><button class="btn ghost sm" id="pclr">Leeren</button></div>
   <div class="tmap" id="pm" style="margin-top:12px;height:min(60vh,520px)"></div>
   <p class="mut" style="font-size:13px;margin:6px 0 0">Klick auf die Karte setzt einen Punkt (Punkte lassen sich ziehen, Rechtsklick entfernt einen). Die Punkte werden geradlinig verbunden – setze sie dicht entlang des Weges oder lade eine fertige GPX-Strecke.</p>
   <div class="figs" id="pf" style="margin-top:18px"></div><div class="mut" id="pb" style="margin:8px 0 0"></div>
   <div class="panel prof" style="margin-top:18px;display:none" id="pprof"><h2>Höhenprofil</h2><div id="pprofc"></div></div>
   <div class="field" style="max-width:760px;margin:16px 0 0"><label for="pnote">Notiz zur Planung</label><textarea id="pnote" rows="2" placeholder="Anfahrt, Einkehr, beste Jahreszeit …"></textarea></div>
   <div class="row" style="margin-top:12px"><button class="btn" id="psave">Plan speichern</button><button class="btn alt" id="pdl">⬇ Als GPX herunterladen</button><span id="pmsg" class="mut"></span></div>
   <div class="sec"><h2>Gespeicherte Pläne</h2><span class="sub">${plans.length ? plans.length + " Pläne" : "noch keine"}</span></div>
   <div class="panel"><div class="rows" id="plist">${plans.length ? plans.map(p => `<div class="r" data-p="${p.id}" style="cursor:pointer"><span>${esc(p.name)}<small>${sName(p.sport)} · ${nf(p.km || 0, 1)} km · ↑ ${nf(p.up || 0, 0)} m${p.est_h ? " · ca. " + hmm(p.est_h) + " h" : ""}</small></span><span><button class="btn ghost sm" data-d="${p.id}" title="Plan löschen">✕</button></span></div>`).join("") : `<p class="mut">Gespeicherte Planungen erscheinen hier.</p>`}</div></div>`;
  map = mkMap("pm", {layers: true});
  map.setView([47.5, 9], 6);
  const line = L.polyline([], {color: "#e8590c", weight: 4, opacity: 0.9}).addTo(map);
  let markers = [],
    seq = 0,
    tm = null;
  const sw = () => $("#ps").value;
  const redraw = () => {
    markers.forEach(m => map.removeLayer(m));
    markers = [];
    line.setLatLngs(P.wp);
    if (P.wp.length <= 80)
      P.wp.forEach((p, i) => {
        const m = L.circleMarker(p, {radius: 6, color: "#fff", weight: 2, fillColor: i === 0 ? "#2f8f5f" : i === P.wp.length - 1 ? "#c0504d" : "#e8590c", fillOpacity: 1}).addTo(map);
        m.on("contextmenu", ev => {
          L.DomEvent.stop(ev);
          P.wp.splice(i, 1);
          changed();
        });
        markers.push(m);
      });
  };
  const figs = () => {
    const km = P.wp.length > 1 ? pathKm(P.wp) : 0,
      m = paceModel(sw()),
      up = P.up,
      est = km > 0 ? planTime(m, km, up || 0) : null;
    P.km = km;
    P.est = est ? est.h : null;
    const F = (v, u, l) => `<div class="fig"><div class="v">${v}<span class="u">${u}</span></div><div class="l">${l}</div></div>`;
    $("#pf").innerHTML = P.wp.length > 1
      ? F(nf(km, 2), "km", "Strecke") + F(up != null ? nf(up, 0) : "…", "m", "Aufstieg") + F(P.down != null ? nf(P.down, 0) : "…", "m", "Abstieg") + F(P.max != null ? nf(P.max, 0) : "…", "m", "Höchster Punkt") + F(`${hmm(est.h)}`, "Std.", `Geschätzte Zeit (${hmm(est.lo)}–${hmm(est.hi)})`)
      : `<div class="mut">Setze mindestens zwei Punkte oder lade eine GPX-Datei.</div>`;
    $("#pb").textContent = P.wp.length > 1
      ? m.n
        ? `Zeit nach deinem Tempo aus ${m.n} ähnlichen Touren (im Schnitt ${nf(m.kmh, 1)} km/h, Gesamtzeit inklusive Pausen).`
        : `Zeit nach Standardwerten – sobald du mehr Touren dieser Sportart im Archiv hast, wird die Schätzung persönlich.`
      : "";
    if (P.ele && P.dense) {
      $("#pprof").style.display = "";
      $("#pprofc").innerHTML = planProfile(P.dense, P.ele);
    } else $("#pprof").style.display = "none";
  };
  const calc = async () => {
    const my = ++seq;
    if (P.wp.length < 2) {
      P.ele = P.dense = P.up = P.down = P.max = null;
      return figs();
    }
    const dense = densify(P.wp);
    try {
      const r = await api("/api/plan/elevation", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({points: dense})});
      if (my !== seq) return;
      Object.assign(P, {dense, ele: r.ele, up: r.up, down: r.down, max: r.max});
    } catch (e) {
      if (my !== seq) return;
      Object.assign(P, {dense: null, ele: null, up: null, down: null, max: null});
      $("#pmsg").innerHTML = `<span class="bad">Höhen konnten nicht geladen werden (${esc(e.message)}) – Strecke und Zeit ohne Höhenmeter.</span>`;
    }
    figs();
  };
  const changed = () => {
    redraw();
    figs();
    clearTimeout(tm);
    tm = setTimeout(calc, 500);
  };
  map.on("click", e => {
    P.wp.push([e.latlng.lat, e.latlng.lng]);
    changed();
  });
  const fit = () => P.wp.length > 1 && map.fitBounds(L.latLngBounds(P.wp), {padding: [30, 30]});
  const setPts = (pts, name) => {
    P.wp = pts;
    if (name && !$("#pn").value) $("#pn").value = name;
    changed();
    fit();
  };
  $("#ps").onchange = () => figs();
  $("#pundo").onclick = () => {
    P.wp.pop();
    changed();
  };
  $("#pclr").onclick = () => {
    P.wp = [];
    P.id = null;
    $("#pmsg").textContent = "";
    changed();
  };
  $("#pg").onchange = async e => {
    const f = e.target.files[0];
    if (!f) return;
    const pts = parseGpxPts(await f.text());
    if (pts.length < 2) return ($("#pmsg").innerHTML = `<span class="bad">In der Datei wurde keine Strecke gefunden.</span>`);
    P.id = null;
    setPts(pts.length > 3000 ? pts.filter((_, i) => i % Math.ceil(pts.length / 3000) === 0) : pts, f.name.replace(/\.gpx$/i, ""));
  };
  if ($("#pgd"))
    $("#pgd").onchange = async e => {
      if (!e.target.value) return;
      const g = await api(`/api/plan/guide/${e.target.value}`);
      P.id = null;
      setPts(g.pts, g.title);
    };
  $("#pdl").onclick = () => {
    if (P.wp.length < 2) return;
    const dense = P.dense || P.wp,
      blob = new Blob([planGpx($("#pn").value || "Planung", dense, P.ele)], {type: "application/gpx+xml"}),
      a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (($("#pn").value || "planung").replace(/[^\wäöüÄÖÜß\- ]+/g, "").trim() || "planung") + ".gpx";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };
  $("#psave").onclick = async () => {
    if (P.wp.length < 2) return ($("#pmsg").innerHTML = `<span class="bad">Bitte zuerst eine Strecke planen.</span>`);
    figs();
    try {
      const r = await api("/api/plans", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({id: P.id, name: $("#pn").value, sport: sw(), pts: P.wp, km: P.km, up: P.up, down: P.down, max_alt: P.max, est_h: P.est, note: $("#pnote").value})});
      P.id = r.id;
      history.replaceState(null, "", `#/plan/${r.id}`);
      $("#pmsg").textContent = "gespeichert ✓";
      const l = await api("/api/plans");
      $("#plist").innerHTML = l.map(p => `<div class="r" data-p="${p.id}" style="cursor:pointer"><span>${esc(p.name)}<small>${sName(p.sport)} · ${nf(p.km || 0, 1)} km · ↑ ${nf(p.up || 0, 0)} m${p.est_h ? " · ca. " + hmm(p.est_h) + " h" : ""}</small></span><span><button class="btn ghost sm" data-d="${p.id}" title="Plan löschen">✕</button></span></div>`).join("");
    } catch (e) {
      $("#pmsg").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  };
  $("#plist").onclick = async e => {
    const d = e.target.dataset.d,
      r = e.target.closest("[data-p]");
    if (d) {
      if (confirm("Diesen Plan löschen?")) {
        await api(`/api/plans/${d}`, {method: "DELETE"});
        route();
      }
    } else if (r) {
      const h = `#/plan/${r.dataset.p}`;
      if (location.hash === h) route();
      else location.hash = h;
    }
  };
  /* Start: gespeicherten Plan oder Wanderführer-Tour laden */
  if (pid && /^\d+$/.test(pid)) {
    try {
      const p = await api(`/api/plans/${pid}`);
      P.id = p.id;
      $("#pn").value = p.name;
      $("#ps").value = p.sport;
      $("#pnote").value = p.note || "";
      setPts(p.pts);
    } catch (e) {
      $("#pmsg").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  } else if (q && q.get("g")) {
    try {
      const g = await api(`/api/plan/guide/${+q.get("g")}`);
      setPts(g.pts, g.title);
    } catch (e) {
      $("#pmsg").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  } else figs();
};

/* Einstiegspunkte: Tourenliste und Wunschliste */
const _tours27 = VIEWS.tours;
VIEWS.tours = async (...a) => {
  await _tours27(...a);
  const h = document.querySelector("#main .sec");
  if (h && !$("#plink")) h.insertAdjacentHTML("beforeend", `<span class="sp"></span><a class="btn alt sm" id="plink" href="#/plan">🗺 Tour planen</a>`);
};
const _places27 = VIEWS.places;
VIEWS.places = async (...a) => {
  await _places27(...a);
  const w = $("#wlist");
  if (!w || w.dataset.plan) return;
  w.dataset.plan = "1";
  const mark = () => {
    const h = w.querySelector(".sec");
    if (h && !h.querySelector(".plan-l")) h.insertAdjacentHTML("beforeend", `<span class="sp"></span><a class="btn alt sm plan-l" href="#/plan">🗺 Tour planen</a>`);
    w.querySelectorAll("[data-w]").forEach(b => {
      const row = b.closest(".r");
      if (row && !row.querySelector(".plan-g")) b.insertAdjacentHTML("beforebegin", `<a class="btn ghost sm plan-g" href="#/plan?g=${b.dataset.w}" title="Diese Tour planen: Länge, Höhenmeter und Zeit nach deinem Tempo">🗺 Planen</a> `);
    });
  };
  mark();
  new MutationObserver(mark).observe(w, {childList: true, subtree: true});
};
