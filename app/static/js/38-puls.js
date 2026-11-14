/* Herzfrequenz in der Tour-Ansicht: Verlauf, Durchschnitt/Maximum und Zeit in den Pulszonen (nur wenn die Tour Pulswerte enthält) */
const HR_ZC = ["#8fb8d8", "#6bb38a", "#e2b13c", "#e0803c", "#c0504d"],
  HR_ZN = ["Sehr leicht", "Leicht (Fettverbrennung)", "Moderat (Ausdauer)", "Hart (Tempo)", "Maximal"],
  HR_CACHE = new Map();
/* Pulsdaten einer Tour (einmal je Tour geladen) */
function hrData(id) {
  if (!HR_CACHE.has(id)) HR_CACHE.set(id, api("/api/tours/" + encodeURIComponent(id) + "/hr").catch(() => ({n: 0})));
  return HR_CACHE.get(id);
}
/* Liefert eine Funktion Sekunden-seit-Start -> bpm (null, wenn im Umkreis von 90 s nichts gemessen wurde) */
function hrLookup(h) {
  const p = h.pts || [];
  return s => {
    if (!p.length) return null;
    let lo = 0,
      hi = p.length - 1;
    while (hi - lo > 1) {
      const m = (lo + hi) >> 1;
      p[m][0] <= s ? (lo = m) : (hi = m);
    }
    const c = Math.abs(p[lo][0] - s) <= Math.abs(p[hi][0] - s) ? p[lo] : p[hi];
    return Math.abs(c[0] - s) <= 90 ? c[1] : null;
  };
}
const hrZone = (v, hmax) => Math.min(4, Math.max(0, Math.floor((v / hmax - 0.5) / 0.1)));
function pulsCard(t) {
  const old = $("#pulscard");
  if (old) old.remove();
  const prof = $("#profcard");
  if (!prof || !t) return;
  hrData(t.id)
    .then(h => {
      if (!h || !h.n || $("#pulscard")) return;
      const W = 800, H = 150, L0 = 42, B = 22, T = 8;
      const dur = h.pts[h.pts.length - 1][0] || 1;
      const lo = Math.max(30, Math.floor((h.min - 5) / 10) * 10), hi = Math.ceil((h.max + 5) / 10) * 10;
      const x = s => L0 + ((W - L0 - 6) * s) / dur, y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
      // Messlücken (Pausen, Uhr ohne Signal) teilen den Verlauf in Abschnitte; jeder Abschnitt wird geglättet (gleitender Mittelwert),
      // Lücken werden als weicher, gestrichelter Übergang gezeichnet statt als harte Gerade.
      const GAP = 60, step = Math.max(10, Math.round(dur / 320)), segs = [];
      let cur = [h.pts[0]];
      for (let i = 1; i < h.pts.length; i++) {
        if (h.pts[i][0] - h.pts[i - 1][0] > GAP) {
          segs.push(cur);
          cur = [];
        }
        cur.push(h.pts[i]);
      }
      segs.push(cur);
      const smooth = seg => {
        const bk = new Map();
        seg.forEach(p => {
          const k = Math.floor(p[0] / step), e = bk.get(k) || [0, 0, 0];
          e[0] += p[0]; e[1] += p[1]; e[2]++;
          bk.set(k, e);
        });
        const m = [...bk.values()].map(e => [e[0] / e[2], e[1] / e[2]]);
        return m.map((p, i) => {                       // zusätzlich über die Nachbarn mitteln (1-2-1)
          const a = m[i - 1] || p, c = m[i + 1] || p;
          return [p[0], (a[1] + 2 * p[1] + c[1]) / 4];
        });
      };
      const sm = segs.filter(x => x.length).map(smooth);
      const line = sm.map(seg => seg.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("")).join("");
      let bridge = "";
      for (let i = 1; i < sm.length; i++) {
        const a = sm[i - 1][sm[i - 1].length - 1], c = sm[i][0], xa = x(a[0]), xb = x(c[0]), xm = (xa + xb) / 2;
        bridge += `<path d="M${xa.toFixed(1)},${y(a[1]).toFixed(1)}C${xm.toFixed(1)},${y(a[1]).toFixed(1)} ${xm.toFixed(1)},${y(c[1]).toFixed(1)} ${xb.toFixed(1)},${y(c[1]).toFixed(1)}" fill="none" stroke="#c0504d" stroke-width="1.4" stroke-dasharray="4 5" opacity=".55"><title>Keine Messwerte (Pause)</title></path>`;
      }
      let g = "";
      [lo, (lo + hi) / 2, hi].forEach(v => (g += `<line x1="${L0}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)"/><text x="${L0 - 6}" y="${y(v) + 4}" text-anchor="end">${Math.round(v)}</text>`));
      for (let k = 0; k <= 4; k++) {
        const s = (dur * k) / 4, m = Math.round(s / 60);
        g += `<text x="${x(s)}" y="${H - 6}" text-anchor="${k === 4 ? "end" : k === 0 ? "start" : "middle"}">${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")} h</text>`;
      }
      const ZC = HR_ZC, ZN = HR_ZN;
      const tot = h.zones.reduce((a, b) => a + b, 0) || 1;
      const mm = s => (s >= 3600 ? Math.floor(s / 3600) + " h " + Math.round((s % 3600) / 60) + " min" : Math.round(s / 60) + " min");
      const bar = h.zones.map((s, i) => `<span style="flex:${Math.max(s, 0.001)};background:${ZC[i]}" title="${ZN[i]}: ${mm(s)}"></span>`).join("");
      const leg = h.zones.map((s, i) => `<span class="nw"><i class="br2 mr5" style="display:inline-block;width:10px;height:10px;background:${ZC[i]}"></i>Z${i + 1} ${ZN[i]}: ${mm(s)} (${Math.round((s / tot) * 100)} %)</span>`).join("");
      const d = tlCard("pulscard", {sec: "puls", key: "tl_puls", icon: "heart", title: "Herzfrequenz", badge: `Ø ${h.avg} · max ${h.max} bpm`, def: true});
      tlBody(d).innerHTML = `<div class="g28 fxw mb8 fx hrkpi"><div><b>${h.avg}</b> <span class="mut">Ø bpm</span></div><div><b>${h.max}</b> <span class="mut">max bpm</span></div><div><b>${h.min}</b> <span class="mut">min bpm</span></div></div>` +
        `<svg viewBox="0 0 ${W} ${H}" class="w100 ha">${g}${bridge}<path d="${line}" fill="none" stroke="#c0504d" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/></svg>` +
        `<div class="br6 ovh m12-0-8 fx h12">${bar}</div>` +
        `<div class="mut g6-16 fxw fx hrleg">${leg}</div>` +
        `<div class="mut mt8 hrnote">Zonen nach ${h.hrmax} bpm Maximalpuls (einstellbar in der Verwaltung).</div>`;
      prof.after(d);
    })
    .catch(() => {});
}

/* Pulskurve im Höhenprofil: gleiche Strecke auf der x-Achse, eigener Maßstab (rechts beschriftet), geglättet */
function profileHr(h) {
  const X = window.profile && profile.ctx;
  if (!X || !h || !h.n || $("#phr")) return;
  const {c, pts, svg, W, H, B, T} = X,
    f = hrLookup(h),
    t0 = c[0][3];
  if (t0 == null) return;
  const raw = c.map((p, i) => (p[3] != null ? [pts[i][0], f((p[3] - t0) / 1000)] : [pts[i][0], null]));
  if (raw.filter(r => r[1] != null).length < 10) return;
  const step = Math.max(1, Math.round(raw.length / 200)),
    sm = [];
  for (let i = 0; i < raw.length; i += step) {                     // je Abschnitt mitteln; Lücken unterbrechen die Linie
    const part = raw.slice(i, i + step).filter(r => r[1] != null);
    sm.push(part.length ? [raw[i][0], part.reduce((a, r) => a + r[1], 0) / part.length] : null);
  }
  const vals = sm.filter(Boolean).map(r => r[1]),
    lo = Math.min(...vals) - 5,
    hi = Math.max(...vals) + 5,
    y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  let d = "",
    pen = false;
  sm.forEach(r => {
    if (!r) return (pen = false);
    d += `${pen ? "L" : "M"}${r[0].toFixed(1)},${y(r[1]).toFixed(1)}`;
    pen = true;
  });
  const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
  g.id = "phr";
  g.setAttribute("pointer-events", "none");
  g.innerHTML = `<path d="${d}" fill="none" stroke="#c0504d" stroke-width="1.6" stroke-linejoin="round" opacity=".9"/>
    <text x="${W - 4}" y="${y(hi - 5) + 4}" text-anchor="end" fill="#c0504d" font-size="12">${Math.round(hi - 5)} bpm</text>
    <text x="${W - 4}" y="${y(lo + 5) - 2}" text-anchor="end" fill="#c0504d" font-size="12">${Math.round(lo + 5)} bpm</text>`;
  svg.appendChild(g);
  const pc = $("#profcard");
  if (pc && !pc.querySelector(".phrl")) pc.insertAdjacentHTML("beforeend", `<div class="mut fs13 phrl"><span class="hrink">━</span> Puls</div>`);
}

/* =====================  Statistik → Puls: Belastung über alle Touren mit Pulsdaten  ===================== */
VIEWS.pulse = async (_, q) => {
  const main = $("#main");
  main.className = "";
  const r = await api("/api/hr/stats").catch(() => ({tours: []}));
  const rows = r.tours.map(x => ({...x, t: BY[x.id], sec: x.zones.reduce((a, b) => a + b, 0)})).filter(x => x.t && x.sec > 0);
  if (!rows.length) {
    main.innerHTML = `<h1>Puls</h1><div class="empty"><h2>Noch keine Pulsdaten</h2><p class="mut">Touren mit Herzfrequenz erkennst du am ❤ in der Tourenliste. Der Zepp-Import und FIT-, GPX- oder TCX-Dateien mit Puls bringen die Werte mit.</p></div>`;
    statTabs("pulse");
    return;
  }
  const ys = [...new Set(rows.map(x => x.t.y))].sort((a, b) => b - a),
    Y = +q.get("y") || 0,
    sel = Y ? rows.filter(x => x.t.y === Y) : rows,
    hh = s => s / 3600,
    tot = sel.reduce((a, x) => a + x.sec, 0),
    zs = [0, 1, 2, 3, 4].map(i => sel.reduce((a, x) => a + x.zones[i], 0)),
    avg = tot ? Math.round(sel.reduce((a, x) => a + x.avg * x.sec, 0) / tot) : 0,
    top = sel.reduce((a, x) => (x.max > a.max ? x : a), sel[0] || {max: 0});
  // Zeit in den Zonen je Monat (ein Jahr) bzw. je Jahr (alle Jahre)
  const keys = Y ? MON.map((_, i) => i + 1) : [...ys].reverse(),
    lab = k => (Y ? MON[k - 1] : String(k)),
    grp = keys.map(k => [0, 1, 2, 3, 4].map(i => sel.filter(x => (Y ? x.t.m === k : x.t.y === k)).reduce((a, x) => a + x.zones[i], 0))),
    mx = Math.max(1, ...grp.map(g => g.reduce((a, b) => a + b, 0))),
    W = 800, H = 220, L0 = 44, B = 26, T = 10,
    bw = (W - L0 - 8) / keys.length;
  let bars = "";
  [0, 0.5, 1].forEach(f => {
    const yy = T + (H - T - B) * (1 - f);
    bars += `<line x1="${L0}" x2="${W}" y1="${yy}" y2="${yy}" stroke="var(--rule)"/><text x="${L0 - 6}" y="${yy + 4}" text-anchor="end">${nf(hh(mx * f), mx * f >= 36000 ? 0 : 1)} h</text>`;
  });
  grp.forEach((g, i) => {
    let y0 = H - B;
    g.forEach((s, z) => {
      const h = ((H - T - B) * s) / mx;
      if (h > 0) bars += `<rect x="${(L0 + i * bw + bw * 0.16).toFixed(1)}" y="${(y0 - h).toFixed(1)}" width="${(bw * 0.68).toFixed(1)}" height="${h.toFixed(1)}" fill="${HR_ZC[z]}"><title>${lab(keys[i])} – Z${z + 1} ${HR_ZN[z]}: ${nf(hh(s), 1)} h</title></rect>`;
      y0 -= h;
    });
    bars += `<text x="${(L0 + i * bw + bw / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${lab(keys[i])}</text>`;
  });
  // Durchschnittspuls je Tour im Zeitverlauf
  const seq = [...sel].sort((a, b) => a.t.start_ts - b.t.start_ts),
    lo = Math.min(...seq.map(x => x.avg)) - 5,
    hi = Math.max(...seq.map(x => x.avg)) + 5,
    t0 = seq[0].t.start_ts,
    t1 = seq[seq.length - 1].t.start_ts,
    px = x => L0 + ((W - L0 - 12) * (t1 > t0 ? (x.t.start_ts - t0) / (t1 - t0) : 0.5)),
    py = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo || 1));
  let dots = "";
  [lo + 5, (lo + hi) / 2, hi - 5].forEach(v => (dots += `<line x1="${L0}" x2="${W}" y1="${py(v)}" y2="${py(v)}" stroke="var(--rule)"/><text x="${L0 - 6}" y="${py(v) + 4}" text-anchor="end">${Math.round(v)}</text>`));
  dots += seq.map(x => `<a href="#/tour/${x.id}"><circle cx="${px(x).toFixed(1)}" cy="${py(x.avg).toFixed(1)}" r="4.5" fill="${sCol(x.t.sport)}" stroke="var(--card)" stroke-width="1.5"><title>${esc(x.t.name)} – ${dateS(x.t.date)}: Ø ${x.avg} bpm, max ${x.max} bpm</title></circle></a>`).join("");
  dots += `<text x="${L0}" y="${H - 8}">${dateS(seq[0].t.date)}</text><text x="${W}" y="${H - 8}" text-anchor="end">${dateS(seq[seq.length - 1].t.date)}</text>`;
  const hard = [...sel].map(x => ({...x, hs: (x.zones[3] + x.zones[4]) / x.sec})).sort((a, b) => b.hs - a.hs || b.avg - a.avg).slice(0, 8),
    zbar = `<div class="zbar">${zs.map((s, i) => `<span style="flex:${Math.max(s, 0.001)};background:${HR_ZC[i]}" title="Z${i + 1} ${HR_ZN[i]}: ${nf(hh(s), 1)} h"></span>`).join("")}</div>
      <div class="mut zleg">${zs.map((s, i) => `<span><i style="background:${HR_ZC[i]}"></i>Z${i + 1} ${HR_ZN[i]}: ${nf(hh(s), 1)} h (${Math.round((s / (tot || 1)) * 100)} %)</span>`).join("")}</div>`;
  main.innerHTML = `<div class="sec mt0"><h2>Puls</h2><span class="sub">${nf(sel.length, 0)} Touren mit Herzfrequenz</span></div>
    <div class="chips mb12"><a class="chip ${Y ? "" : "on"}" href="#/pulse">Alle Jahre</a>${ys.map(y => `<a class="chip ${Y === y ? "on" : ""}" href="#/pulse?y=${y}">${y}</a>`).join("")}</div>
    <div class="figs"><div class="fig"><div class="v">${nf(hh(tot), 0)}<span class="u">h</span></div><div class="l">mit Pulsmessung</div></div>
      <div class="fig"><div class="v">${avg}<span class="u">bpm</span></div><div class="l">Puls im Schnitt</div></div>
      <div class="fig"><div class="v">${top.max}<span class="u">bpm</span></div><div class="l">höchster Puls${top.t ? ` – <a href="#/tour/${top.id}">${esc(top.t.name)}</a>` : ""}</div></div>
      <div class="fig"><div class="v">${Math.round(((zs[3] + zs[4]) / (tot || 1)) * 100)}<span class="u">%</span></div><div class="l">der Zeit in Zone 4 und 5</div></div></div>
    <div class="panel gap"><h2>Zeit in den Pulszonen</h2>${zbar}
      <svg class="chart" viewBox="0 0 ${W} ${H}">${bars}</svg>
      <div class="mut fs13">Zonen nach ${r.hrmax} bpm Maximalpuls (einstellbar in der Verwaltung). ${Y ? "Je Monat." : "Je Jahr."}</div></div>
    <div class="panel gap"><h2>Durchschnittspuls je Tour</h2><svg class="chart" viewBox="0 0 ${W} ${H}">${dots}</svg><div class="mut fs13">Ein Punkt je Tour, eingefärbt nach Sportart. Antippen öffnet die Tour.</div></div>
    <div class="panel gap"><h2>Die anstrengendsten Touren</h2><div class="rows">${hard.map(x => `<a class="r" href="#/tour/${x.id}"><span>${esc(x.t.name)} <span class="mut">${dateS(x.t.date)}</span></span><b>${Math.round(x.hs * 100)} %</b><span class="mut">in Zone 4–5, Ø ${x.avg} bpm</span></a>`).join("")}</div></div>`;
  statTabs("pulse");
};
