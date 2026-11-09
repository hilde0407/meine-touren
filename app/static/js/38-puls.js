/* Herzfrequenz in der Tour-Ansicht: Verlauf, Durchschnitt/Maximum und Zeit in den Pulszonen (nur wenn die Tour Pulswerte enthält) */
function pulsCard(t) {
  const old = $("#pulscard");
  if (old) old.remove();
  const prof = $("#profcard");
  if (!prof || !t) return;
  api("/api/tours/" + encodeURIComponent(t.id) + "/hr")
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
      const ZC = ["#8fb8d8", "#6bb38a", "#e2b13c", "#e0803c", "#c0504d"], ZN = ["Sehr leicht", "Leicht (Fettverbrennung)", "Moderat (Ausdauer)", "Hart (Tempo)", "Maximal"];
      const tot = h.zones.reduce((a, b) => a + b, 0) || 1;
      const mm = s => (s >= 3600 ? Math.floor(s / 3600) + " h " + Math.round((s % 3600) / 60) + " min" : Math.round(s / 60) + " min");
      const bar = h.zones.map((s, i) => `<span style="flex:${Math.max(s, 0.001)};background:${ZC[i]}" title="${ZN[i]}: ${mm(s)}"></span>`).join("");
      const leg = h.zones.map((s, i) => `<span style="white-space:nowrap"><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${ZC[i]};margin-right:5px"></i>Z${i + 1} ${ZN[i]}: ${mm(s)} (${Math.round((s / tot) * 100)} %)</span>`).join("");
      const d = document.createElement("div");
      d.className = "panel prof gap";
      d.id = "pulscard";
      d.innerHTML = `<h2>Herzfrequenz</h2><div style="display:flex;gap:28px;flex-wrap:wrap;margin-bottom:8px"><div><b style="font-size:1.5em">${h.avg}</b> <span class="mut">Ø bpm</span></div><div><b style="font-size:1.5em">${h.max}</b> <span class="mut">max bpm</span></div><div><b style="font-size:1.5em">${h.min}</b> <span class="mut">min bpm</span></div></div>` +
        `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto">${g}${bridge}<path d="${line}" fill="none" stroke="#c0504d" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/></svg>` +
        `<div style="display:flex;height:12px;border-radius:6px;overflow:hidden;margin:12px 0 8px">${bar}</div>` +
        `<div class="mut" style="display:flex;gap:6px 16px;flex-wrap:wrap;font-size:.85em">${leg}</div>` +
        `<div class="mut" style="font-size:.8em;margin-top:8px">Zonen nach ${h.hrmax} bpm Maximalpuls (einstellbar in der Verwaltung).</div>`;
      prof.after(d);
    })
    .catch(() => {});
}
