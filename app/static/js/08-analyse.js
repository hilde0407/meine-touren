/* =====================  Erweiterungen 2: Wetter, Analyse, Vergleich, Hinweise  ===================== */
const GR = [
  [-1e9, -10, "#2b6cb0", "steil bergab"],
  [-10, -3, "#63b3ed", "bergab"],
  [-3, 3, "#68d391", "flach"],
  [3, 10, "#f6ad55", "bergauf"],
  [10, 1e9, "#e53e3e", "steil bergauf"],
];
const grCol = g => (GR.find(b => g >= b[0] && g < b[1]) || GR[2])[2];
function analyse(c) {
  // Pausen, Bewegungszeit, Steigungsabschnitte aus den Streckenpunkten
  const n = c.length,
    cum = [0];
  for (let i = 1; i < n; i++) cum.push(cum[i - 1] + hav(c[i - 1], c[i]));
  const hasT = c[0][3] != null && c[n - 1][3] != null,
    pauses = [];
  if (hasT)
    for (let i = 0; i < n - 1; ) {
      let j = i + 1;
      while (j < n && hav(c[i], c[j]) < 25) j++;
      const dur = (c[j - 1][3] - c[i][3]) / 1000;
      if (dur >= 180 && j - 1 > i) {
        pauses.push({t: c[i][3], dur, lat: c[i][0], lng: c[i][1]});
        i = j;
      } else i++;
    }
  const total = hasT ? (c[n - 1][3] - c[0][3]) / 1000 : null,
    pausedS = pauses.reduce((a, p) => a + p.dur, 0);
  const segs = [],
    band = GR.map(() => 0);
  let i = 0;
  while (i < n - 1) {
    let j = i + 1;
    while (j < n - 1 && cum[j] - cum[i] < 60) j++;
    const d = cum[j] - cum[i],
      a0 = c[i][2],
      a1 = c[j][2];
    if (d > 5) {
      const g = a0 != null && a1 != null ? ((a1 - a0) / d) * 100 : 0;
      segs.push({a: i, b: j, g});
      const k = GR.findIndex(b => g >= b[0] && g < b[1]);
      band[k < 0 ? 2 : k] += d;
    }
    i = j;
  }
  return {cum, pauses, total, pausedS, segs, band, dist: cum[n - 1]};
}
const fmtH = s => {
  const h = Math.floor(s / 3600),
    m = Math.round((s % 3600) / 60);
  return h ? `${h}:${pad2(m)} h` : `${m} min`;
};
const _tour2 = VIEWS.tour;
VIEWS.tour = async id => {
  await _tour2(id);
  const t = BY[id];
  if (!t || !$("#profcard")) return;
  // Wetter
  api(`/api/tours/${encodeURIComponent(id)}/weather`)
    .then(w => {
      const f = document.querySelector("#main .figs");
      if (!f || !$("#ksync")) return;
      const ic =
        w.code >= 95
          ? "⛈"
          : w.code >= 71 && w.code <= 86
            ? "❄️"
            : w.code >= 51
              ? "🌧"
              : w.code >= 45
                ? "🌫"
                : w.code >= 3
                  ? "☁️"
                  : w.code >= 1
                    ? "⛅"
                    : "☀️";
      f.insertAdjacentHTML(
        "afterend",
        `<div class="wx">${ic} <b>${esc(w.text)}</b> · ${nf(w.tmin, 0)}–${nf(w.tmax, 0)} °C · Niederschlag ${nf(w.precip, 1)} mm · Wind bis ${nf(w.wind, 0)} km/h <span class="mut">(Open-Meteo)</span></div>`
      );
    })
    .catch(() => {});
  // Analyse
  const c = cleanPts(await api(`/api/tours/${encodeURIComponent(id)}/coords`).catch(() => []));
  if (c.length < 10 || !$("#profcard")) return;
  const A = analyse(c),
    others = TOURS.filter(o => o.id !== id && o.sport === t.sport)
      .map(o => ({
        o,
        s: Math.abs(o.km - t.km) / Math.max(t.km, 1) + (o.lat != null && t.lat != null ? hav([o.lat, o.lng], [t.lat, t.lng]) / 5000 : 5),
      }))
      .sort((a, b) => a.s - b.s)
      .slice(0, 25);
  const tot = A.dist || 1,
    box = document.createElement("div");
  box.className = "panel";
  box.style.margin = "26px 0";
  box.innerHTML = `<h2>Analyse</h2><div class="rows">
    ${
      A.total
        ? `<div class="r"><span>Bewegungszeit<small>${A.pauses.length} Pause${A.pauses.length === 1 ? "" : "n"} (ab 3 Min.) mit zusammen ${fmtH(A.pausedS)}</small></span><b>${fmtH(A.total - A.pausedS)}</b></div>
    <div class="r"><span>Ø-Tempo in Bewegung<small>gesamt inkl. Pausen: ${nf(t.km / (A.total / 3600), 1)} km/h</small></span><b>${nf(t.km / Math.max(0.01, (A.total - A.pausedS) / 3600), 1)} km/h</b></div>`
        : ""
    }</div>
   <h3 style="margin:16px 0 8px;font-size:18px">Steigung (Anteil der Strecke)</h3><div class="stack">${GR.map((b, k) => `<div style="width:${(A.band[k] / tot) * 100}%;background:${b[2]}" title="${b[3]}"></div>`).join("")}</div>
   <div class="legend">${GR.map((b, k) => `<span><i style="background:${b[2]}"></i>${b[3]} ${nf(A.band[k] / 1000, 1)} km</span>`).join("")}</div>
   <div class="row" style="margin-top:12px"><button class="btn alt sm" id="gtog">Steigung auf der Karte zeigen</button>${A.pauses.length ? `<button class="btn alt sm" id="ptog">Pausen auf der Karte zeigen</button>` : ""}
    <select id="cmp" style="max-width:340px"><option value="">Mit anderer Tour vergleichen …</option>${others.map(x => `<option value="${x.o.id}">${dateS(x.o.date)} · ${esc(x.o.name)} (${nf(x.o.km, 1)} km)</option>`).join("")}</select></div>`;
  $("#profcard").after(box);
  const overlay = {};
  const withMap = fn => {
    let k = 0;
    const w = () => (map && map.addLayer ? fn() : k++ < 30 && setTimeout(w, 150));
    w();
  };
  $("#gtog").onclick = e =>
    withMap(() => {
      if (overlay.g) {
        map.removeLayer(overlay.g);
        overlay.g = null;
        e.target.textContent = "Steigung auf der Karte zeigen";
        return;
      }
      overlay.g = L.layerGroup(
        A.segs.map(sg =>
          L.polyline(
            c.slice(sg.a, sg.b + 1).map(p => [p[0], p[1]]),
            {color: grCol(sg.g), weight: 7, opacity: 0.95}
          ).bindTooltip(`${nf(sg.g, 0)} % Steigung`)
        )
      ).addTo(map);
      e.target.textContent = "Steigung ausblenden";
    });
  if ($("#ptog"))
    $("#ptog").onclick = e =>
      withMap(() => {
        if (overlay.p) {
          map.removeLayer(overlay.p);
          overlay.p = null;
          e.target.textContent = "Pausen auf der Karte zeigen";
          return;
        }
        overlay.p = L.layerGroup(
          A.pauses.map(p =>
            L.circleMarker([p.lat, p.lng], {radius: 9, color: "#fff", weight: 2, fillColor: "#7b61c9", fillOpacity: 1}).bindTooltip(
              `Pause ${fmtH(p.dur)}, ${nf(p.t / 60000, 0)} Min. nach dem Start`
            )
          )
        ).addTo(map);
        e.target.textContent = "Pausen ausblenden";
      });
  $("#cmp").onchange = e => {
    if (e.target.value) location.hash = `#/compare?a=${encodeURIComponent(id)}&b=${encodeURIComponent(e.target.value)}`;
  };
};

/* ---- Tourvergleich ---- */
function xyChart(series, o) {
  const W = 560,
    H = 230,
    L0 = 46,
    B = 26,
    T = 10,
    xs = series.flatMap(s => s.pts.map(p => p[0])),
    ys = series.flatMap(s => s.pts.map(p => p[1]));
  const X1 = Math.max(...xs),
    y0 = Math.min(...ys),
    y1 = Math.max(...ys),
    sp = Math.max(1, y1 - y0),
    lo = o.zero ? 0 : y0 - sp * 0.06,
    hi = y1 + sp * 0.06;
  const x = v => L0 + ((W - L0 - 8) * v) / X1,
    y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}">`;
  [0, 0.5, 1].forEach(f => {
    const v = lo + (hi - lo) * f;
    s += `<line x1="${L0}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)" stroke-dasharray="2 4"/><text x="${L0 - 6}" y="${y(v) + 4}" text-anchor="end">${o.fy ? o.fy(v) : nf(v, 0)}</text>`;
  });
  for (let k = 0; k <= 4; k++)
    s += `<text x="${x((X1 * k) / 4)}" y="${H - 6}" text-anchor="${k === 4 ? "end" : k === 0 ? "start" : "middle"}">${nf((X1 * k) / 4, 0)} km</text>`;
  series.forEach(
    se =>
      (s += `<path d="${se.pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("")}" fill="none" stroke="${se.color}" stroke-width="2.6"/>`)
  );
  return s + "</svg>";
}
VIEWS.compare = async (_, q) => {
  const ta = BY[q.get("a")],
    tb = BY[q.get("b")];
  if (!ta || !tb) throw new Error("Touren zum Vergleichen nicht gefunden");
  const [ca, cb] = await Promise.all(
      [ta, tb].map(t =>
        api(`/api/tours/${encodeURIComponent(t.id)}/coords`)
          .then(cleanPts)
          .catch(() => [])
      )
    ),
    cols = ["#e2b13c", "#3a86c8"];
  const info = (t, c) => {
    const A = c.length > 9 ? analyse(c) : null;
    return {
      km: t.km,
      up: t.up_m || 0,
      h: t.h,
      v: t.km / (t.h || 1),
      moving: A && A.total ? (A.total - A.pausedS) / 3600 : null,
      pauses: A ? A.pauses.length : null,
      A,
    };
  };
  const a = info(ta, ca),
    b = info(tb, cb),
    d = (x, y, u, dg = 1) => {
      const v = y - x;
      return `<span>${v > 0 ? "+" : v < 0 ? "−" : ""}${nf(Math.abs(v), dg)} ${u}</span>`;
    };
  const row = (l, x, y, u, dg = 1) =>
    x == null || y == null
      ? ""
      : `<tr><td>${l}</td><td class="n">${nf(x, dg)} ${u}</td><td class="n">${nf(y, dg)} ${u}</td><td class="n">${d(x, y, u, dg)}</td></tr>`;
  const alt = (c, A) => c.map((p, i) => [A.cum[i] / 1000, p[2] ?? 0]),
    tim = (c, A) => c.map((p, i) => [A.cum[i] / 1000, (p[3] ?? 0) / 60000]);
  const hasT = ca[0] && ca[0][3] != null && cb[0] && cb[0][3] != null;
  $("#main").innerHTML =
    `<div class="row"><a class="back" href="#/tour/${ta.id}">‹ ${esc(ta.name)}</a></div><div class="sec"><h2>Tourvergleich</h2></div>
   <div class="legend" style="margin-bottom:10px"><span><i style="background:${cols[0]}"></i><a href="#/tour/${ta.id}">${esc(ta.name)}</a> (${dateS(ta.date)})</span><span><i style="background:${cols[1]}"></i><a href="#/tour/${tb.id}">${esc(tb.name)}</a> (${dateS(tb.date)})</span></div>
   <div class="grid g2"><div id="cm" class="cmap"></div><div><table class="cmp"><tr><th></th><th class="n">A</th><th class="n">B</th><th class="n">B − A</th></tr>
    ${row("Strecke", a.km, b.km, "km")}${row("Aufstieg", a.up, b.up, "m", 0)}${row("Dauer", a.h, b.h, "h", 2)}${row("Ø-Tempo gesamt", a.v, b.v, "km/h")}${row("Bewegungszeit", a.moving, b.moving, "h", 2)}${row("Pausen", a.pauses, b.pauses, "", 0)}</table>
    <div class="panel" style="margin-top:20px"><h3>Höhenprofil</h3>${
      ca.length > 2 && cb.length > 2
        ? xyChart(
            [
              {pts: alt(ca, a.A), color: cols[0]},
              {pts: alt(cb, b.A), color: cols[1]},
            ],
            {fy: v => nf(v, 0) + " m"}
          )
        : "<div class='mut'>keine Höhendaten</div>"
    }</div></div></div>
   ${
     hasT
       ? `<div class="panel" style="margin-top:30px"><h3>Zeit über Strecke</h3><p class="mut" style="font-size:14px">Wo die Linien auseinanderlaufen, war eine Tour schneller (flacher = schneller, Stufen = Pausen).</p>${xyChart(
           [
             {pts: tim(ca, a.A), color: cols[0]},
             {pts: tim(cb, b.A), color: cols[1]},
           ],
           {zero: true, fy: v => fmtH(v * 60)}
         )}</div>`
       : ""
   }`;
  map = mkMap("cm", {layers: true});
  const g = L.featureGroup(
    [ca, cb].map((c, i) =>
      L.polyline(
        c.map(p => [p[0], p[1]]),
        {color: cols[i], weight: 5, opacity: 0.9}
      ).addTo(map)
    )
  );
  if (g.getLayers().length && g.getBounds().isValid()) map.fitBounds(g.getBounds(), {padding: [24, 24]});
};

/* ---- Hinweis: Zepp-Token + Verwaltung (Selbsttest, Eingang, Zepp-Status) ---- */
const _dash3 = VIEWS.dash;
VIEWS.dash = async (n, q) => {
  await _dash3(n, q);
  const st = await api("/api/status").catch(() => null),
    inner = $(".inner");
  if (st && st.zepp && /^fail/.test(st.zepp.state) && inner)
    inner.insertAdjacentHTML(
      "afterbegin",
      `<div class="notice">⚠ Der Zepp-Zugang funktioniert nicht mehr (Token abgelaufen?). <a href="#/admin">In der Verwaltung ein neues Token holen</a>, damit neue Zepp-Trainings weiter geprüft werden können.</div>`
    );
};
const _adm3 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm3(...a);
  const st = await api("/api/status").catch(() => ({})),
    sv = $("#save");
  if (!sv) return;
  const z = st.zepp || {},
    age = z.token_ts ? Math.floor((Date.now() / 1000 - +z.token_ts) / 86400) : null;
  const zr = $("#ztest");
  if (zr)
    zr.closest(".row").insertAdjacentHTML(
      "afterend",
      `<p class="mut" style="font-size:14px;margin:-4px 0 8px">${z.state === "ok" ? "✓ Token gültig" : /^fail/.test(z.state || "") ? `<span class="bad">✗ Token ungültig: ${esc(z.state.slice(5))}</span>` : z.state === "none" ? "Kein Token gespeichert" : "Token noch nicht geprüft"}${age != null ? ` · gespeichert vor ${age} Tag${age === 1 ? "" : "en"}` : ""}${z.checked ? ` · zuletzt geprüft ${new Date(+z.checked * 1000).toLocaleString("de-DE")}` : ""} (wird täglich mitgeprüft)</p>`
    );
  sv.closest(".row").insertAdjacentHTML(
    "beforebegin",
    `<div class="grid g2" style="margin-top:40px"><div class="panel"><h2>Foto-Eingang</h2>
    <p class="mut">Fotos einfach in den Eingangsordner kopieren (per <code>scp</code>, <code>rsync</code> oder SMB-Freigabe): <code>${esc(st.inbox || "/var/lib/meine-touren/inbox")}</code>. Sie werden automatisch verkleinert, mit Aufnahmezeit übernommen und Touren zugeordnet (Prüfung alle 5 Minuten).</p>
    <p class="mut" style="font-size:13px">Beispiel vom Mac: <code>rsync -av ~/Pictures/Wanderung/ root@SERVER:${esc(st.inbox || "/var/lib/meine-touren/inbox")}/</code></p></div>
   <div class="panel"><h2>Wanderführer (z. B. Rother)</h2><p class="mut">Lade die GPX-Dateien deiner Wanderführer hoch (bei Rother im Download-Bereich zum Buch). Folgt eine Tour einer dieser Strecken, wird der Tourtitel aus dem Buch beim Umbenennen vorgeschlagen.</p>
    <div class="field"><label>Buch (z. B. „Rother Taunus“)</label><input id="gbook"></div>
    <div class="row"><button class="btn" id="gup">GPX-Dateien auswählen …</button><input type="file" id="gfile" accept=".gpx" multiple hidden><span id="gres" class="mut"></span></div><div id="glist" style="margin-top:10px"></div></div>
   <div class="panel"><h2>Selbsttest</h2><p class="mut">Prüft Komoot-Zugang, Strecken, Zepp-Token, Internet-Dienste (Karten, Wetter, Höhendaten), Speicherplatz und Backup.</p>
    <div class="row"><button class="btn alt" id="stest">Selbsttest starten</button></div><div id="stres" style="margin-top:10px"></div></div></div>`
  );
  const gl = async () => {
    const g = await api("/api/guides").catch(() => []),
      by = {};
    g.forEach(x => (by[x.book] ||= []).push(x));
    $("#glist").innerHTML =
      Object.keys(by)
        .map(
          b =>
            `<div class="r" style="display:flex;justify-content:space-between;gap:8px"><span>${esc(b || "(ohne Buch)")} <small class="mut">${by[b].length} Touren</small></span><button class="btn alt sm" data-gb="${esc(b)}">Entfernen</button></div>`
        )
        .join("") || '<span class="mut">Noch keine Wanderführer hinterlegt.</span>';
    document.querySelectorAll("[data-gb]").forEach(
      b =>
        (b.onclick = async () => {
          if (confirm("Alle Touren dieses Buchs entfernen?")) {
            await api("/api/guides/" + encodeURIComponent("book:" + b.dataset.gb), {method: "DELETE"});
            gl();
          }
        })
    );
  };
  $("#gup").onclick = () => $("#gfile").click();
  $("#gfile").onchange = async e => {
    const fs = [...e.target.files];
    if (!fs.length) return;
    $("#gres").textContent = "Lese " + fs.length + " Dateien …";
    const items = await Promise.all(fs.map(f => f.text().then(gpx => ({name: f.name, gpx}))));
    try {
      const r = await api("/api/guides", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({book: $("#gbook").value, items}),
      });
      $("#gres").textContent = `${r.added} hinzugefügt${r.failed.length ? ", " + r.failed.length + " fehlgeschlagen: " + r.failed[0] : ""}`;
    } catch (x) {
      $("#gres").textContent = x.message;
    }
    e.target.value = "";
    gl();
  };
  gl();
  $("#stest").onclick = async () => {
    $("#stres").textContent = "Prüfe … (kann bis zu einer Minute dauern)";
    $("#stest").disabled = true;
    try {
      const r = await api("/api/selftest", {method: "POST"});
      $("#stres").innerHTML =
        `<div class="rows">${r.map(x => `<div class="r"><span>${x.ok ? "✓" : "✗"} ${esc(x.name)}<small class="${x.ok ? "" : "bad"}">${esc(x.detail)}</small></span></div>`).join("")}</div>`;
    } catch (e) {
      $("#stres").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
    $("#stest").disabled = false;
  };
};

/* ---- Übersicht: durch die letzten Touren zappen ---- */
const _dashZ = VIEWS.dash;
VIEWS.dash = async (...a) => {
  await _dashZ(...a);
  const hero = $(".hero");
  if (!hero || TOURS.length < 2) return;
  const N = Math.min(10, TOURS.length);
  let i = 0,
    tok = 0,
    auto = null;
  hero.insertAdjacentHTML(
    "beforeend",
    `<button class="hnav" id="hprev" aria-label="Neuere Tour" title="Neuere Tour (←)">‹</button><button class="hnav r" id="hnext" aria-label="Ältere Tour" title="Ältere Tour (→)">›</button>
    <div class="hdots" id="hdots"><button class="hpl" id="hpl" title="Automatisch weiterschalten">▶</button><span id="hcnt"></span></div>`
  );
  const k = hero.querySelector(".k"),
    h1 = hero.querySelector("h1"),
    w = hero.querySelector(".w"),
    btns = hero.querySelector(".btns"),
    signs = hero.querySelector(".signs");
  const show = async n => {
    i = (n + N) % N;
    const t = TOURS[i],
      my = ++tok;
    k.textContent = (i ? `${i + 1}. letzte Tour` : "Letzte Tour") + ", " + sName(t.sport);
    h1.textContent = t.name;
    w.textContent = `${dateL(t.date)}, ${timeS(t.date)} Uhr`;
    btns.innerHTML = `<a class="btn" href="#/tour/${t.id}">Tour ansehen</a>${t.photos ? `<a class="btn alt" style="color:#fff" target="_blank" href="slideshow.html?tour=${t.id}">Diashow</a>` : ""}`;
    signs.innerHTML = `<div class="sign">${nf(t.km, 1)}<small>Kilometer</small></div><div class="sign l">${nf(t.up_m, 0)}<small>Meter aufwärts</small></div><div class="sign">${nf(t.h, 1)}<small>Stunden</small></div>`;
    $("#hcnt").textContent = `${i + 1} / ${N}`;
    const old = hero.querySelector(".thumbrow");
    if (old) old.remove();
    const [ph, c] = await Promise.all([
      t.photos ? api(`/api/photos?tour_id=${t.id}&limit=4`).catch(() => []) : [],
      api(`/api/tours/${t.id}/coords`).catch(() => null),
    ]);
    if (my !== tok || !hero.isConnected) return;
    if (ph.length) {
      w.insertAdjacentHTML(
        "afterend",
        `<div class="thumbrow">${ph.map((p, x) => `<img loading="lazy" src="/pic/${p.id}?size=300" data-i="${x}">`).join("")}</div>`
      );
      bindThumbs(hero.querySelector(".thumbrow"), ph);
    }
    if (map) {
      map.eachLayer(l => {
        if (l instanceof L.Polyline) map.removeLayer(l);
      });
      const pts = cleanPts(c || []).map(p => [p[0], p[1]]);
      if (pts.length > 1) {
        const l = L.polyline(pts, {color: "#f2c230", weight: 5}).addTo(map);
        map.fitBounds(l.getBounds(), {paddingTopLeft: [window.innerWidth > 900 ? 640 : 40, 40], paddingBottomRight: [40, 40]});
      } else if (t.lat) map.setView([t.lat, t.lng], 12);
    }
  };
  $("#hprev").onclick = () => show(i - 1);
  $("#hnext").onclick = () => show(i + 1);
  $("#hpl").onclick = e => {
    if (auto) {
      clearInterval(auto);
      auto = null;
      e.target.textContent = "▶";
    } else {
      e.target.textContent = "⏸";
      auto = setInterval(() => {
        if (!hero.isConnected) {
          clearInterval(auto);
          return;
        }
        show(i + 1);
      }, 6000);
    }
  };
  const key = e => {
    if (!hero.isConnected) {
      document.removeEventListener("keydown", key);
      return;
    }
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "") || $(".modal")) return;
    if (e.key === "ArrowLeft") show(i - 1);
    else if (e.key === "ArrowRight") show(i + 1);
  };
  document.addEventListener("keydown", key);
  let sx = null;
  hero.addEventListener(
    "touchstart",
    e => {
      sx = e.touches[0].clientX;
    },
    {passive: true}
  );
  hero.addEventListener(
    "touchend",
    e => {
      if (sx == null) return;
      const dx = e.changedTouches[0].clientX - sx;
      sx = null;
      if (Math.abs(dx) > 60) show(i + (dx < 0 ? 1 : -1));
    },
    {passive: true}
  );
  $("#hcnt").textContent = `1 / ${N}`;
};
