/* =====================  Touren planen: zeichnen oder GPX laden, Aufstieg und Zeit nach eigenem Tempo  ===================== */
const PLAN_DEF = {foot: [0.22, 0.0018], bike: [0.055, 0.0015], ski: [0.2, 0.0035], run: [0.1, 0.001], other: [0.22, 0.0018]}; // h je km, h je Aufstieg (Gesamtzeit inkl. Pausen)

/* Eigenes Tempo aus dem Archiv: Gesamtzeit ≈ a·km + b·Aufstieg (kleinste Quadrate); sonst Standardwerte */
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
const hmm = h => fmtDauer(h * 3600);

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
  const kms = [0, 0.25, 0.5, 0.75, 1].map(f => `<text x="${x(D * f)}" y="${H - 4}" font-size="11" text-anchor="${f === 0 ? "start" : f === 1 ? "end" : "middle"}" fill="currentColor" opacity=".6">${fmtKm((D * f) / 1000)}</text>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" class="w100" style="height:auto">${ticks}${kms}<path d="${line}L${x(D)},${H - B}L${L},${H - B}Z" fill="var(--green,#2f8f5f)" opacity=".22"/><path d="${line}" fill="none" stroke="var(--green,#2f8f5f)" stroke-width="2.2"/></svg>`;
}

/* Machbarkeit (3.38.0): Vergleich der Planung mit den eigenen Touren der letzten 12 Monate – Text UND Symbol, nie nur Farbe */
const PLAN_STUFE = {
  gewohnt: ["ok", "✓", "Im gewohnten Rahmen"],
  etwas_mehr: ["warn", "▲", "Etwas mehr als gewohnt"],
  deutlich_mehr: ["bad", "⚠", "Deutlich mehr als bisher"],
  zu_wenig: ["info", "ℹ", "Zu wenig eigene Touren für eine persönliche Einschätzung"],
};
const PLAN_QUELLE = {eigene: "nach deinem Steigungstempo", teilweise: "teilweise nach deinem Steigungstempo", standard: "nach Standardwerten (Naismith)"};
function planCheckHtml(r, estH) {
  const st = PLAN_STUFE[r.stufe] || PLAN_STUFE.zu_wenig,
    dk = r.diese,
    kmup = (km, up) => (up != null ? `${fmtKm(km)} mit ${fmtHm(up)}` : `${fmtKm(km)} (ohne Höhenangabe)`),
    li = [];
  if (r.stufe === "zu_wenig") li.push(`<li>Gefunden: ${r.n} Touren dieser Sportart in den letzten ${r.monate} Monaten, nötig sind mindestens ${r.min_n}.</li>`);
  else {
    const L = r.laengste,
      H = r.hoechster_aufstieg;
    li.push(`<li>Deine längste Tour der letzten ${r.monate} Monate: ${kmup(L.km, L.up)}; diese: ${kmup(dk.km, dk.up)}</li>`);
    if (H && H.id !== L.id && dk.up != null) li.push(`<li>Dein größter Aufstieg der letzten ${r.monate} Monate: ${fmtHm(H.up)} auf ${fmtKm(H.km)}; diese: ${fmtHm(dk.up)}</li>`);
    if (r.gruende.includes("km")) li.push(`<li>Länger als deine längste Tour (+${Math.round((dk.km / L.km - 1) * 100)} %)</li>`);
    if (r.gruende.includes("up") && H && H.up > 0) li.push(`<li>Mehr Aufstieg als deine bisher höchste Tour (+${Math.round((dk.up / H.up - 1) * 100)} %)</li>`);
    li.push(`<li>Länger als diese Strecke: ${r.laenger} von ${r.n} Touren</li>`);
    const a = r.aehnlich;
    if (a) {
      li.push(`<li>Ähnlich lange Touren (±25 % der Länge): ${a.n} in den letzten ${r.monate} Monaten</li>`);
      if (a.dauer_h != null) li.push(`<li>Mittlere Gesamtzeit dieser Touren: ${hmm(a.dauer_h)}</li>`);
      if (a.up != null) li.push(`<li>Mittlerer Aufstieg dieser Touren: ${fmtHm(a.up)}</li>`);
    }
    if (r.hoechster_punkt) li.push(`<li>Höchster Punkt dieser Strecke: ${fmtHm(dk.max_alt)}; höchster Punkt deiner Touren der letzten ${r.monate} Monate: ${fmtHm(r.hoechster_punkt.eigen)}</li>`);
  }
  if (estH != null) li.push(`<li>Geschätzte Gesamtzeit inkl. Pausen: ${hmm(estH)} (wie oben)</li>`);
  if (r.gehzeit) li.push(`<li><span>Reine Gehzeit ohne Pausen: ca. ${hmm(r.gehzeit.sekunden / 3600)}</span> <span class="mut">(${PLAN_QUELLE[r.gehzeit.quelle] || PLAN_QUELLE.standard})</span></li>`);
  const base = r.stufe === "zu_wenig" ? "" : `<p class="mut fs13">Grundlage: ${r.n} Touren dieser Sportart der letzten ${r.monate} Monate.</p>`;
  return {
    cls: st[0],
    sum: `<span class="pcs ${st[0]}"><span aria-hidden="true">${st[1]}</span> <span>${st[2]}</span></span>`,
    body: `<p class="pcst ${st[0]}"><i aria-hidden="true">${st[1]}</i><span>${st[2]}</span></p><ul class="pcl">${li.join("")}</ul>${base}`,
  };
}
const hmSigned = h => (h < 0 ? "−" : "+") + fmtDauer(Math.abs(h) * 3600);
const nSigned = (v, d) => (v < 0 ? "−" : "+") + nf(Math.abs(v), d);
/* verknüpfte Pläne: geplant ↔ gelaufen (fehlende Werte werden weggelassen, nie als 0 gerechnet) */
function planCmpHtml(p) {
  const t = p.tour;
  if (!t) return "";
  const out = [];
  if (p.est_h && t.h) out.push(`<span>geplant ${hmm(p.est_h)}</span> · <span>gelaufen ${hmm(t.h)} (${hmSigned(t.h - p.est_h)})</span>`);
  else if (t.h) out.push(`<span>gelaufen ${hmm(t.h)}</span>`);
  if (p.km && t.km) out.push(`<span>Strecke: geplant ${fmtKm(p.km)}, gelaufen ${fmtKm(t.km)} (${nSigned(t.km - p.km, 1)} km)</span>`);
  if (p.up != null && t.up != null) out.push(`<span>Aufstieg: geplant ${fmtHm(p.up)}, gelaufen ${fmtHm(t.up)} (${nSigned(t.up - p.up, 0)} m)</span>`);
  return `<small class="pcmp">${out.join(" · ") || ""}</small>`;
}
const planDate = ts => (ts ? fmtDatumKurz(ts) : "");
const planSugGone = () => {
  try {
    return JSON.parse(localStorage.getItem("mt-plan-sug-no") || "[]");
  } catch (e) {
    return [];
  }
};
const planSugNo = key => {
  try {
    localStorage.setItem("mt-plan-sug-no", JSON.stringify([...planSugGone(), key].slice(-200)));
  } catch (e) {}
};
function planRowHtml(p, sug) {
  const key = sug ? `${p.id}:${sug.tour_id}` : "",
    stOpt = [["geplant", "geplant"], ["gegangen", "gegangen"], ["verworfen", "verworfen"]];
  const badge = p.status === "gegangen" ? `<span class="pst g"><span aria-hidden="true">✓</span> <span>gegangen</span></span>` : p.status === "verworfen" ? `<span class="pst v"><span aria-hidden="true">✕</span> <span>verworfen</span></span>` : "";
  const sg = sug && !planSugGone().includes(key)
    ? `<span class="psug"><span>Gelaufen am ${planDate(Date.parse(sug.datum) / 1000)} vorschlagen:</span> <a href="#/tour/${esc(sug.tour_id)}">${esc(sug.name || "Tour")}</a> <button class="btn sm" data-ok="${p.id}:${esc(sug.tour_id)}" type="button" aria-label="Verknüpfung bestätigen: ${esc(p.name)}">Bestätigen</button> <button class="btn ghost sm" data-no="${esc(key)}" type="button">Nicht passend</button></span>`
    : "";
  return `<div class="r cp prow" data-p="${p.id}" role="group" aria-label="Plan: ${esc(p.name)}"><span><a class="prn" href="#/plan/${p.id}">${esc(p.name)}</a>${badge}<small>${sName(p.sport)} · ${fmtKm(p.km || 0)} · ${fmtAuf(p.up || 0)}${p.est_h ? " · ca. " + hmm(p.est_h) : ""}</small>${planCmpHtml(p)}${sg}</span><span class="prow-a">${
    p.tour ? `<a class="btn ghost sm" href="#/tour/${esc(p.tour.id)}" aria-label="Zur gelaufenen Tour: ${esc(p.name)}">Tour ansehen</a><button class="btn ghost sm" data-un="${p.id}" type="button" aria-label="Verknüpfung lösen: ${esc(p.name)}">Verknüpfung lösen</button>` : ""
  }<select class="pstat" data-s="${p.id}" aria-label="Status: ${esc(p.name)}">${stOpt.map(o => `<option value="${o[0]}" ${o[0] === (p.status || "geplant") ? "selected" : ""}>${o[1]}</option>`).join("")}</select><button class="btn ghost sm" data-d="${p.id}" title="Plan löschen" aria-label="Plan löschen: ${esc(p.name)}" type="button">✕</button></span></div>`;
}

const PLAN_PROFILE = s => ({racebike: "fastbike", mtb: "mtb"}[s] || (sportGrp(s) === "bike" ? "trekking" : "hiking-mountain"));
const PLAN_MAXROUTED = 40; // so viele Punkte werden höchstens über Wege verbunden (jeder Abschnitt ist eine Anfrage)
const ALT_COL = ["#e8590c", "#1c7ed6", "#9c36b5", "#2b8a3e"];

VIEWS.plan = async (pid, q) => {
  const P = {id: null, wp: [], rt: true, alt: {}, segs: {}, pend: {}, sel: null, stored: null, ele: null, dense: null, up: null, down: null, max: null, warned: false};
  $("#main").className = "";
  if (!(await planOn())) {
    $("#main").innerHTML = `<div class="row"><a class="back" href="#/tours">‹ Alle Touren</a></div><div class="sec"><h2>Tour planen</h2></div><p class="mut">Die Tourplanung ist ausgeschaltet. Du kannst sie unter Verwaltung → „Tourplanung“ wieder einschalten.</p>`;
    return;
  }
  const [plans, guides] = await Promise.all([api("/api/plans").catch(() => []), api("/api/guides").catch(() => [])]);
  const sports = Object.keys(SPORT);
  let SUG = {};
  const planRow = p => planRowHtml(p, SUG[p.id]);
  $("#main").innerHTML = `<div class="row"><a class="back" href="#/tours">‹ Alle Touren</a></div>
   <div class="sec"><h2>Tour planen</h2><span class="sub">Punkte in die Karte klicken – sie werden über bekannte Wege verbunden – oder eine GPX-Datei laden</span></div>
   <div class="row g8 fxw"><input id="pn" placeholder="Name der Planung" aria-label="Name der Planung" maxlength="120" class="mnw230"><select id="ps" aria-label="Sportart">${sports.map(s => `<option value="${s}" ${s === "hike" ? "selected" : ""}>${sName(s)}</option>`).join("")}</select>
    <label class="chip on cp" title="Verbindet die Punkte über Wege und Straßen aus OpenStreetMap (BRouter). Aus: gerade Linien."><input type="checkbox" id="prt" checked style="display:none">Wegen folgen</label>
    <label class="btn alt sm cp">GPX laden …<input type="file" id="pg" accept=".gpx,application/gpx+xml,text/xml" style="display:none"></label>
    ${guides.length ? `<select id="pgd" class="mw260" aria-label="Aus Wanderführer laden"><option value="">Aus Wanderführer laden …</option>${guides.map(g => `<option value="${g.id}">${esc(g.book ? g.book + " – " : "")}${esc(g.title)}</option>`).join("")}</select>` : ""}
    <button class="btn ghost sm" id="pundo">↶ Letzten Punkt entfernen</button><button class="btn ghost sm" id="pclr">Leeren</button></div>
   <div class="tmap mt12" id="pm" role="region" aria-label="Karte zur Planung: Klick setzt einen Punkt" style="height:min(60vh,520px)"></div>
   <div id="pseg" class="wx m8-0-0" style="display:none"></div>
   <p class="mut fs13 m6-0-0">Klick auf die Karte setzt einen Punkt, Rechtsklick auf einen Punkt entfernt ihn. Ein Klick auf einen Abschnitt wählt ihn aus – dort lassen sich <b>Alternativen</b> anzeigen. Gestrichelt = gerade Linie (kein Weg gefunden oder „Wegen folgen“ aus).</p>
   <div class="figs mt18" id="pf" role="group" aria-label="Kennzahlen der Planung"></div><div class="mut m8-0-0" id="pb"></div>
   <div class="panel prof gap" style="display:none" id="pprof" role="region" aria-label="Höhenprofil der Planung"><h2>Höhenprofil</h2><div id="pprofc"></div></div>
   <details class="pcheck" id="pcheck" hidden open><summary><span class="pcsh">Machbarkeit</span> <span id="pcsum"></span></summary><div id="pcb" class="pcb" role="status" aria-live="polite" aria-atomic="true"></div></details>
   <div class="field mw760 m16-0-0"><label for="pnote">Notiz zur Planung</label><textarea id="pnote" rows="2" aria-label="Notiz zur Planung" placeholder="Anfahrt, Einkehr, beste Jahreszeit …"></textarea></div>
   <div class="row mt12"><button class="btn" id="psave">Plan speichern</button><button class="btn alt" id="pdl">⬇ Als GPX herunterladen</button><span id="pmsg" class="mut"></span></div>
   <div class="sec"><h2>Gespeicherte Pläne</h2><span class="sub">${plans.length ? plans.length + " Pläne" : "noch keine"}</span></div>
   <div class="panel"><div class="rows" id="plist" aria-label="Gespeicherte Pläne">${plans.length ? plans.map(planRow).join("") : `<p class="mut">Gespeicherte Planungen erscheinen hier.</p>`}</div></div>`;
  map = mkMap("pm", {layers: true});
  map.setView([47.5, 9], 6);
  const segLayer = L.layerGroup().addTo(map),
    altLayer = L.layerGroup().addTo(map);
  let markers = [],
    seq = 0,
    tm = null;
  const sw = () => $("#ps").value,
    prof = () => PLAN_PROFILE(sw()),
    r5 = p => p[0].toFixed(5) + "," + p[1].toFixed(5),
    base = i => `${r5(P.wp[i])}>${r5(P.wp[i + 1])}|${prof()}`,
    ckey = (i, a) => base(i) + "#" + (a == null ? P.alt[base(i)] || 0 : a),
    routedOK = () => P.rt && P.wp.length >= 2 && P.wp.length <= PLAN_MAXROUTED,
    segRes = i => (routedOK() ? P.segs[ckey(i)] : null),
    segPts = i => {
      const r = segRes(i);
      return r && r.pts ? r.pts : [P.wp[i], P.wp[i + 1]];
    };
  const path = () => {
    if (P.stored) return P.stored;
    const out = [];
    for (let i = 0; i < P.wp.length - 1; i++) (i ? segPts(i).slice(1) : segPts(i)).forEach(p => out.push([p[0], p[1]]));
    return out.length ? out : P.wp.map(p => [p[0], p[1]]);
  };
  const msg = (t, bad) => ($("#pmsg").innerHTML = t ? `<span class="${bad ? "bad" : "ok"}">${esc(t)}</span>` : "");
  const segInfo = () => {
    const el = $("#pseg");
    if (P.stored || P.sel == null || P.sel >= P.wp.length - 1 || !routedOK()) return (el.style.display = "none");
    const r = segRes(P.sel);
    el.style.display = "";
    el.innerHTML = `<b>Abschnitt ${P.sel + 1} von ${P.wp.length - 1}</b> ${r && r.pts ? `· ${fmtKm(r.km)} · ${fmtAuf(r.up)}` : r && r.fail ? `· <span class="bad">kein Weg gefunden – gerade Linie</span>` : "· wird berechnet …"} <button class="btn alt sm ml8" id="palts">Alternativen anzeigen</button><span id="paltl"></span>`;
    $("#palts").onclick = () => showAlts(P.sel);
  };
  const redraw = () => {
    markers.forEach(m => map.removeLayer(m));
    markers = [];
    segLayer.clearLayers();
    altLayer.clearLayers();
    if (P.stored) L.polyline(P.stored, {color: "#e8590c", weight: 4, opacity: 0.9, bubblingMouseEvents: false}).addTo(segLayer);
    else
      for (let i = 0; i < P.wp.length - 1; i++) {
        const r = segRes(i),
          straight = !(r && r.pts),
          sel = i === P.sel && routedOK();
        const pl = L.polyline(segPts(i).map(p => [p[0], p[1]]), {color: sel ? "#1c7ed6" : "#e8590c", weight: sel ? 7 : 4, opacity: 0.9, dashArray: straight ? "7 8" : null, bubblingMouseEvents: false}).addTo(segLayer);
        pl.on("click", () => {
          P.sel = i;
          redraw();
          segInfo();
        });
      }
    if (P.wp.length <= 80)
      P.wp.forEach((p, i) => {
        const m = L.circleMarker(p, {radius: 6, color: "#fff", weight: 2, fillColor: i === 0 ? "#2f8f5f" : i === P.wp.length - 1 ? "#c0504d" : "#e8590c", fillOpacity: 1, bubblingMouseEvents: false}).addTo(map);
        m.on("contextmenu", ev => {
          L.DomEvent.stop(ev);
          P.wp.splice(i, 1);
          changed();
        });
        markers.push(m);
      });
    segInfo();
  };
  const figs = () => {
    const pth = path(),
      km = pth.length > 1 ? pathKm(pth) : 0,
      m = paceModel(sw()),
      up = P.up,
      est = km > 0 ? planTime(m, km, up || 0) : null;
    P.km = km;
    P.est = est ? est.h : null;
    const F = (v, u, l) => `<div class="fig"><div class="v">${v}<span class="u">${u}</span></div><div class="l">${l}</div></div>`;
    $("#pf").innerHTML = pth.length > 1
      ? F(fmtKm(km, {d: 2, einheit: false}), "km", "Strecke") + F(up != null ? nf(up, 0) : "…", "m", "Aufstieg") + F(P.down != null ? nf(P.down, 0) : "…", "m", "Abstieg") + F(P.max != null ? nf(P.max, 0) : "…", "m", "Höchster Punkt") + F(fmtDauerTeile(est.h * 3600).v, fmtDauerTeile(est.h * 3600).u, `Geschätzte Zeit inkl. Pausen (${hmm(est.lo)}–${hmm(est.hi)})`)
      : `<div class="mut">Setze mindestens zwei Punkte oder lade eine GPX-Datei.</div>`;
    $("#pb").textContent = pth.length > 1
      ? m.n
        ? `Zeit nach deinem Tempo aus ${m.n} ähnlichen Touren (im Schnitt ${fmtTempo(m.kmh)}, Gesamtzeit inklusive Pausen).`
        : `Zeit nach Standardwerten – sobald du mehr Touren dieser Sportart im Archiv hast, wird die Schätzung persönlich.`
      : "";
    if (P.ele && P.dense) {
      $("#pprof").style.display = "";
      $("#pprofc").innerHTML = planProfile(P.dense, P.ele);
    } else $("#pprof").style.display = "none";
    if (P.chk) chkShow();
  };
  /* Machbarkeit: Server vergleicht km/Aufstieg mit den eigenen Touren; die Gesamtzeit kommt aus derselben Schätzung wie die Kennzahlen oben */
  let chkSeq = 0;
  const chkShow = () => {
    const box = $("#pcheck");
    if (!box || !P.chk) return;
    const h = planCheckHtml(P.chk, P.est);
    $("#pcsum").innerHTML = h.sum;
    $("#pcb").innerHTML = h.body;
  };
  const chkRun = async () => {
    const my = ++chkSeq,
      box = $("#pcheck"),
      pth = path();
    if (!box) return;
    if (pth.length < 2) {
      P.chk = null;
      box.hidden = true;
      return;
    }
    box.hidden = false;
    if (!P.chk) $("#pcb").innerHTML = `<p class="mut">Vergleich mit deinen Touren wird berechnet …</p>`;
    try {
      const r = await api("/api/plan/check", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({km: pathKm(pth), up: P.up, down: P.down, max_alt: P.max, sport: sw()})});
      if (my !== chkSeq || !$("#pcheck")) return;
      P.chk = r;
      chkShow();
    } catch (e) {
      if (my !== chkSeq || !$("#pcheck")) return;
      P.chk = null;
      $("#pcsum").innerHTML = "";
      $("#pcb").innerHTML = `<p class="mut">Der Vergleich konnte nicht berechnet werden: ${esc(e.message || e)}</p>`;
    }
  };
  const calc = async () => {
    const my = ++seq,
      pth = path();
    if (pth.length < 2) {
      P.ele = P.dense = P.up = P.down = P.max = null;
      figs();
      return chkRun();
    }
    const dense = densify(pth);
    try {
      const r = await api("/api/plan/elevation", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({points: dense})});
      if (my !== seq) return;
      Object.assign(P, {dense, ele: r.ele, up: r.up, down: r.down, max: r.max});
    } catch (e) {
      if (my !== seq) return;
      Object.assign(P, {dense: null, ele: null, up: null, down: null, max: null});
      msg(`Höhen konnten nicht geladen werden (${e.message}) – Strecke und Zeit ohne Aufstieg.`, true);
    }
    figs();
    chkRun();
  };
  const later = () => {
    clearTimeout(tm);
    tm = setTimeout(calc, 500);
  };
  /* Abschnitte über Wege berechnen (jeder Abschnitt einzeln, Ergebnisse werden gemerkt) */
  const ensure = () => {
    if (!routedOK()) return;
    for (let i = 0; i < P.wp.length - 1; i++) {
      const k = ckey(i);
      if (P.segs[k] || P.pend[k]) continue;
      P.pend[k] = 1;
      const a = P.wp[i],
        b = P.wp[i + 1];
      api("/api/plan/route", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({a, b, profile: prof(), alt: P.alt[base(i)] || 0})})
        .then(r => (P.segs[k] = r))
        .catch(e => {
          P.segs[k] = {fail: e.message};
          if (!P.warned) {
            P.warned = true;
            msg(`Kein Weg über das Routing gefunden (${e.message}) – dort wird eine gerade Linie gezeichnet.`, true);
          }
        })
        .finally(() => {
          delete P.pend[k];
          if (!$("#pm")) return;
          redraw();
          figs();
          later();
        });
    }
  };
  const showAlts = async i => {
    altLayer.clearLayers();
    $("#paltl").innerHTML = ` <span class="mut">suche Alternativen …</span>`;
    const b = base(i),
      res = await Promise.all([0, 1, 2, 3].map(a => api("/api/plan/route", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({a: P.wp[i], b: P.wp[i + 1], profile: prof(), alt: a})}).then(r => ({a, r})).catch(() => null)));
    if (!$("#pm") || P.wp.length < i + 2 || base(i) !== b) return;
    const seen = [],
      list = res.filter(x => {
        if (!x) return false;
        const sig = `${Math.round(x.r.km * 20)}|${x.r.up}`;
        if (seen.includes(sig)) return false;
        seen.push(sig);
        return true;
      });
    if (list.length < 2) return ($("#paltl").innerHTML = ` <span class="mut">Keine Alternativen gefunden.</span>`);
    const cur = P.alt[b] || 0;
    $("#paltl").innerHTML = " " + list.map(x => `<button class="btn ${x.a === cur ? "" : "ghost"} sm alt-c" data-a="${x.a}" style="border-left:6px solid ${ALT_COL[x.a]}">${fmtKm(x.r.km)} · ${fmtAuf(x.r.up)}</button>`).join(" ");
    list.forEach(x => {
      if (x.a !== cur) L.polyline(x.r.pts.map(p => [p[0], p[1]]), {color: ALT_COL[x.a], weight: 5, opacity: 0.85, dashArray: "2 8", bubblingMouseEvents: false}).bindTooltip(`${fmtKm(x.r.km)} · ${fmtAuf(x.r.up)}`).addTo(altLayer);
      P.segs[b + "#" + x.a] = x.r;
    });
    $("#paltl").querySelectorAll(".alt-c").forEach(btn => (btn.onclick = () => {
      P.alt[b] = +btn.dataset.a;
      changed();
    }));
  };
  const changed = () => {
    P.stored = null;
    if (P.sel != null && P.sel > P.wp.length - 2) P.sel = P.wp.length > 1 ? P.wp.length - 2 : null;
    redraw();
    figs();
    ensure();
    later();
  };
  map.on("click", e => {
    P.wp.push([e.latlng.lat, e.latlng.lng]);
    if (P.wp.length > 1) P.sel = P.wp.length - 2;
    changed();
  });
  const fit = () => P.wp.length > 1 && map.fitBounds(L.latLngBounds(path()), {padding: [30, 30]});
  const setRt = on => {
    P.rt = on;
    $("#prt").checked = on;
    $("#prt").parentElement.classList.toggle("on", on);
  };
  const setPts = (pts, name, routed) => {
    P.wp = pts;
    setRt(!!routed && pts.length <= PLAN_MAXROUTED);
    if (name && !$("#pn").value) $("#pn").value = name;
    P.sel = null;
    changed();
    fit();
  };
  $("#ps").onchange = () => {
    changed();
  };
  $("#prt").onchange = e => {
    if (e.target.checked && P.wp.length > PLAN_MAXROUTED) {
      e.target.checked = false;
      return msg(`Zu viele Punkte (${P.wp.length}) zum Verbinden über Wege – höchstens ${PLAN_MAXROUTED}. Leere die Planung oder setze weniger Punkte.`, true);
    }
    setRt(e.target.checked);
    P.stored = null;
    changed();
  };
  $("#pundo").onclick = () => {
    P.wp.pop();
    changed();
  };
  $("#pclr").onclick = () => {
    P.wp = [];
    P.id = null;
    P.sel = null;
    msg("");
    setRt(true);
    changed();
  };
  $("#pg").onchange = async e => {
    const f = e.target.files[0];
    if (!f) return;
    const pts = parseGpxPts(await f.text());
    if (pts.length < 2) return msg("In der Datei wurde keine Strecke gefunden.", true);
    P.id = null;
    setPts(pts.length > 3000 ? pts.filter((_, i) => i % Math.ceil(pts.length / 3000) === 0) : pts, f.name.replace(/\.gpx$/i, ""), false);
  };
  if ($("#pgd"))
    $("#pgd").onchange = async e => {
      if (!e.target.value) return;
      const g = await api(`/api/plan/guide/${e.target.value}`);
      P.id = null;
      setPts(g.pts, g.title, false);
    };
  $("#pdl").onclick = () => {
    if (path().length < 2) return;
    const dense = P.dense || path(),
      blob = new Blob([planGpx($("#pn").value || "Planung", dense, P.ele)], {type: "application/gpx+xml"}),
      a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (($("#pn").value || "planung").replace(/[^\wäöüÄÖÜß\- ]+/g, "").trim() || "planung") + ".gpx";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };
  $("#psave").onclick = async () => {
    const pth = path();
    if (pth.length < 2) return msg("Bitte zuerst eine Strecke planen.", true);
    figs();
    try {
      const r = await api("/api/plans", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({id: P.id, name: $("#pn").value, sport: sw(), pts: pth, wps: {wp: P.wp, alt: P.alt, rt: P.rt}, km: P.km, up: P.up, down: P.down, max_alt: P.max, est_h: P.est, note: $("#pnote").value}),
      });
      P.id = r.id;
      history.replaceState(null, "", `#/plan/${r.id}`);
      msg("gespeichert ✓");
      await refreshList();
    } catch (e) {
      msg(e.message, true);
    }
  };
  /* Planliste: Status, Verknüpfung mit der gelaufenen Tour, Vorschläge (nie automatisch verknüpfen) */
  let PL = plans;
  const drawList = () => {
    const el = $("#plist");
    if (!el) return;
    el.innerHTML = PL.length ? PL.map(planRow).join("") : `<p class="mut">Gespeicherte Planungen erscheinen hier.</p>`;
  };
  const refreshList = async (withSug = true) => {
    PL = await api("/api/plans");
    drawList();
    if (withSug) {
      try {
        SUG = await api("/api/plans/vorschlaege");
      } catch (e) {
        SUG = {};
      }
      drawList();
    }
  };
  const post = (u, b) => api(u, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(b)});
  $("#plist").onclick = async e => {
    const d = e.target.dataset.d,
      ok = e.target.dataset.ok,
      no = e.target.dataset.no,
      un = e.target.dataset.un,
      r = e.target.closest("[data-p]");
    if (e.target.closest("a:not(.prn), select")) return;
    if (e.target.closest("a.prn")) e.preventDefault();
    if (ok) {
      const [pi, ti] = ok.split(":");
      e.target.disabled = true;
      try {
        await post(`/api/plans/${pi}/tour`, {tour_id: ti});
        await refreshList();
      } catch (er) {
        e.target.disabled = false;
        uiAlert(er.message || er);
      }
    } else if (no) {
      planSugNo(no);
      drawList();
    } else if (un) {
      try {
        await post(`/api/plans/${un}/tour`, {tour_id: null});
        await refreshList();
      } catch (er) {
        uiAlert(er.message || er);
      }
    } else if (d) {
      if (await uiConfirm({text: "Diesen Plan löschen?", danger: true, ok: "Löschen"})) {
        await api(`/api/plans/${d}`, {method: "DELETE"});
        route();
      }
    } else if (r) {
      const h = `#/plan/${r.dataset.p}`;
      if (location.hash === h) route();
      else location.hash = h;
    }
  };
  $("#plist").onchange = async e => {
    const si = e.target.dataset && e.target.dataset.s;
    if (!si) return;
    try {
      await post(`/api/plans/${si}/status`, {status: e.target.value});
    } catch (er) {
      uiAlert(er.message || er);
    }
    await refreshList();
  };
  api("/api/plans/vorschlaege").then(v => {
    if ($("#plist")) {
      SUG = v;
      drawList();
    }
  }).catch(() => {});
  /* Start: gespeicherten Plan oder Wanderführer-Tour laden */
  if (pid && /^\d+$/.test(pid)) {
    try {
      const p = await api(`/api/plans/${pid}`);
      P.id = p.id;
      $("#pn").value = p.name;
      $("#ps").value = p.sport;
      $("#pnote").value = p.note || "";
      const w = p.wps;
      if (w && w.wp && w.wp.length > 1) {
        P.wp = w.wp;
        P.alt = w.alt || {};
        setRt(!!w.rt && w.wp.length <= PLAN_MAXROUTED);
      } else {
        P.wp = p.pts;
        setRt(false);
      }
      P.stored = p.pts; // bis zur ersten Änderung die gespeicherte Strecke zeigen
      redraw();
      figs();
      later();
      fit();
    } catch (e) {
      msg(e.message, true);
    }
  } else if (q && q.get("g")) {
    try {
      const g = await api(`/api/plan/guide/${+q.get("g")}`);
      setPts(g.pts, g.title, false);
    } catch (e) {
      msg(e.message, true);
    }
  } else figs();
};

/* Einstiegspunkte: Tourenliste und Wunschliste */
const _tours27 = VIEWS.tours;
VIEWS.tours = async (...a) => {
  await _tours27(...a);
  const h = document.querySelector("#main .sec");
  if (h && !$("#plink") && (await planOn())) h.insertAdjacentHTML("beforeend", `<span class="sp"></span><a class="btn alt sm" id="plink" href="#/plan">🗺 Tour planen</a>`);
};
const _places27 = VIEWS.places;
VIEWS.places = async (...a) => {
  await _places27(...a);
  const w = $("#wlist");
  if (!w || w.dataset.plan || !(await planOn())) return;
  w.dataset.plan = "1";
  const mark = () => {
    const h = w.querySelector(".sec");
    if (h && !h.querySelector(".plan-l")) h.insertAdjacentHTML("beforeend", `<span class="sp"></span><a class="btn alt sm plan-l" href="#/plan">🗺 Tour planen</a>`);
    w.querySelectorAll("[data-w]").forEach(b => {
      const row = b.closest(".r");
      if (row && !row.querySelector(".plan-g")) b.insertAdjacentHTML("beforebegin", `<a class="btn ghost sm plan-g" href="#/plan?g=${b.dataset.w}" title="Diese Tour planen: Länge, Aufstieg und Zeit nach deinem Tempo">🗺 Planen</a> `);
    });
  };
  mark();
  new MutationObserver(mark).observe(w, {childList: true, subtree: true});
};

/* Verwaltung: Tourplanung ein/aus, Routing-Dienst wählen */
const planOn = () => api("/api/settings").then(s => (s.plan_enabled || "1") !== "0").catch(() => true);
const _admin27 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admin27(...a);
  const sv = $("#save");
  if (!sv || $("#brpanel")) return;
  const s = await api("/api/settings").catch(() => ({}));
  const on = (s.plan_enabled || "1") !== "0",
    url = s.brouter_url || "";
  let mode = s.plan_mode || (url ? "custom" : "public");
  const host = location.hostname || "SERVER-IP",
    localUrl = `http://${host}:17777/brouter`,
    cmd = "sudo bash deploy/brouter/install-brouter.sh";
  sv.closest(".row").insertAdjacentHTML(
    "beforebegin",
    `<div class="panel" id="brpanel"><h2>Tourplanung</h2>
     ${swField("plan_enabled", "Funktion „Tour planen“", "pon")}
     <div id="pbox">
      <p class="mut">Die Planung verbindet deine Punkte über Wege aus OpenStreetMap. Dafür braucht es einen Routing-Dienst (BRouter). Wähle, wo er läuft:</p>
      <label class="pmode"><input type="radio" name="pm" value="public"> <b>Öffentlicher Dienst brouter.de</b><small>Nichts zu installieren. Die Koordinaten der geplanten Punkte werden an brouter.de gesendet.</small></label>
      <label class="pmode"><input type="radio" name="pm" value="local"> <b>Eigener BRouter auf diesem Server</b><small>Kostenlos, privat und schnell. Einmalig installieren (siehe unten), die Adresse ist dann <code>${esc(localUrl)}</code>.</small></label>
      <label class="pmode"><input type="radio" name="pm" value="custom"> <b>Anderer BRouter-Server im Netz</b><small>Du trägst die Adresse eines vorhandenen BRouter ein (z. B. auf einem NAS oder Raspberry Pi).</small></label>
      <div class="field mt10" id="purlf"><label>BRouter-Adresse</label><input data-k="brouter_url" id="purl" value="${esc(url)}" placeholder="http://192.168.178.50:17777/brouter"></div>
      <div class="row g8 m6-0"><button class="btn alt sm" id="ptest" type="button">Verbindung testen</button><span id="ptm" class="mut"></span></div>
      <div id="pinst" style="display:none"><p class="mut m10-0-4"><b>Installation auf dem Server</b> (Debian/Ubuntu, einmalig; lädt BRouter und die Karten-Kacheln für Deutschland/Alpenraum, je 100–400&nbsp;MB):</p>
        <pre class="m0-0-6 p8-10 br8" style="white-space:pre-wrap;user-select:all;background:var(--surface);border:1px solid var(--rule)">cd ~/meine-touren   # bzw. dein Installationsordner
${esc(cmd)}
# andere Regionen, z. B. Kanaren: ${esc(cmd)} E5_N45 W20_N25</pre>
        <p class="mut fs13 m0">Die App installiert nichts selbst (dafür sind Administratorrechte nötig). Danach „Verbindung testen“ und speichern. Ausführliche Anleitung: README → „Eigener BRouter-Server“.</p></div>
      <input type="hidden" data-k="plan_mode" id="pmode"></div></div>`
  );
  const upd = () => {
    mode = (document.querySelector('input[name="pm"]:checked') || {}).value || "public";
    $("#pmode").value = mode;
    $("#pbox").style.display = $("#pon").checked ? "" : "none";
    $("#purlf").style.display = mode === "public" ? "none" : "";
    $("#pinst").style.display = mode === "local" ? "" : "none";
    if (mode === "local" && !$("#purl").value.trim()) $("#purl").value = localUrl;
    $("#ptest").style.display = mode === "public" ? "none" : "";
  };
  $("#pon").checked = on;
  document.querySelector(`input[name="pm"][value="${mode}"]`).checked = true;
  $("#pon").onchange = upd;
  document.querySelectorAll('input[name="pm"]').forEach(r => (r.onchange = upd));
  upd();
  $("#ptest").onclick = async () => {
    $("#ptm").textContent = "prüfe …";
    try {
      const r = await api("/api/plan/test", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({url: $("#purl").value})});
      $("#ptm").innerHTML = `<span class="${r.ok ? (r.warn ? "" : "ok") : "bad"}">${esc(r.msg)}</span>`;
    } catch (e) {
      $("#ptm").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  };
};
