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
/* Wetter und Analyse: Karten für die Unterseite „Auswertung“ (auf der Hauptseite nur, damit der Einstieg Kurzaussagen hat – 48-tourlayout.js nimmt sie wieder heraus).
   Liefert {wx: Promise} – die Unterseite wartet darauf, bevor sie „keine Auswertung“ meldet. */
async function anaRun(id) {
  const t = BY[id],
    none = {wx: null};
  if (!t || !tlAnc()) return none;
  const onSub = !$("#profcard");
  window.tlSlope = null;
  window.tlWantSlope = false;
  // Wetter
  const wxp = api(`/api/tours/${encodeURIComponent(id)}/weather`)
    .then(w => {
      const f = document.querySelector("#main .figs") || $("#tlsubanc");
      if (!f || t.source === "local" || !tlAnc()) return;
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
        `<div class="wx">${symHtml(ic)} <b>${esc(w.text)}</b> · ${nf(w.tmin, 0)}–${nf(w.tmax, 0)} °C · Niederschlag ${nf(w.precip, 1)} mm · Wind bis ${fmtTempo(w.wind, {d: 0})}${w.snow_depth != null && (w.snow_depth > 0 || w.snow72 > 0 || w.snowfall > 0) ? ` · ${symHtml('❄', 15)} Schneehöhe ca. ${nf(w.snow_depth, 0)} cm${w.snow72 > 0 ? `, Neuschnee 3 Tage davor ${nf(w.snow72, 0)} cm` : ""}${w.snowfall > 0 ? `, während der Tour ${nf(w.snowfall, 0)} cm` : ""}` : ""} <span class="mut">(Open-Meteo, grobe Modelldaten)</span></div>`
      );
    })
    .catch(() => {});
  // Analyse
  const c = cleanPts(await api(`/api/tours/${encodeURIComponent(id)}/coords`).catch(() => []));
  if (c.length < 10 || !tlAnc()) return {wx: wxp};
  const A = analyse(c),
    others = TOURS.filter(o => o.id !== id && o.sport === t.sport)
      .map(o => ({
        o,
        s: Math.abs(o.km - t.km) / Math.max(t.km, 1) + (o.lat != null && t.lat != null ? hav([o.lat, o.lng], [t.lat, t.lng]) / 5000 : 5),
      }))
      .sort((a, b) => a.s - b.s)
      .slice(0, 25);
  const tot = A.dist || 1,
    box = tlCard("anacard", {sec: "ana", key: "tl_ana", icon: "trend", title: "Analyse", def: false, bodyCls: "tlana",
      badge: A.total ? `<span>Bewegungszeit</span> <b>${fmtDauer(A.total - A.pausedS)}</b>${A.pauses.length ? ` · ${A.pauses.length} Pause${A.pauses.length === 1 ? "" : "n"}` : ""}` : "Steigungsanteile"});
  tlBody(box).innerHTML = `<div class="rows">
    ${
      A.total
        ? `<div class="r"><span>Bewegungszeit<small>${A.pauses.length} Pause${A.pauses.length === 1 ? "" : "n"} (ab 3 Min.) mit zusammen ${fmtDauer(A.pausedS)}</small></span><b>${fmtDauer(A.total - A.pausedS)}</b></div>
    <div class="r"><span>Ø-Tempo in Bewegung<small>gesamt inkl. Pausen: ${fmtTempo(t.km / (A.total / 3600))}</small></span><b>${fmtTempo(t.km / Math.max(0.01, (A.total - A.pausedS) / 3600))}</b></div>`
        : ""
    }</div>
   <h3 class="m16-0-8 fs18">Steigung (Anteil der Strecke)</h3><div class="stack">${GR.map((b, k) => `<div style="width:${(A.band[k] / tot) * 100}%;background:${b[2]}" title="${b[3]}"></div>`).join("")}</div>
   <div class="legend">${GR.map((b, k) => `<span><i style="background:${b[2]}"></i>${b[3]} ${fmtKm(A.band[k] / 1000)}</span>`).join("")}</div>
   <div class="row mt12"><a class="btn alt sm" id="gtog" href="#/tour/${esc(String(id))}?karte=steigung">Steigung auf der Karte zeigen</a>${A.pauses.length ? `<a class="btn alt sm" id="ptog" href="#/tour/${esc(String(id))}?karte=pausen">Pausen auf der Karte zeigen</a>` : ""}
    <select id="cmp" class="mw340"><option value="">Mit anderer Tour vergleichen …</option>${others.map(x => `<option value="${x.o.id}">${fmtDatumKurz(x.o.date)} · ${esc(x.o.name)} (${fmtKm(x.o.km)})</option>`).join("")}</select></div>`;
  tlAnc().after(box);
  $("#cmp").onchange = e => {
    if (e.target.value) location.hash = `#/compare?a=${encodeURIComponent(id)}&b=${encodeURIComponent(e.target.value)}`;
  };
  if (onSub) return {wx: wxp};                      // die Karte gibt es nur auf der Hauptseite: die Knöpfe oben verweisen dorthin (?karte=steigung / ?karte=pausen)
  const withMap = fn => {
    let k = 0;
    const w = () => (map && map.addLayer ? fn() : k++ < 30 && setTimeout(w, 150));
    w();
  };
  /* Steigungsfärbung auf der Karte: der Knopf „⛰ Steigung“ auf der Karte (24-sport.js) schaltet sie über window.tlSlope; gibt zurück, ob sie jetzt an ist */
  let slope = null;
  window.tlSlope = () => {
    if (!map || !map.addLayer) return false;
    if (slope) {
      map.removeLayer(slope);
      slope = null;
      return false;
    }
    slope = L.layerGroup(
      A.segs.map(sg =>
        L.polyline(
          c.slice(sg.a, sg.b + 1).map(p => [p[0], p[1]]),
          {color: (typeof sportGrp === "function" && (sportGrp(t.sport) === "ski" || isSnowshoe(t))) && Math.abs(sg.g) >= STEEP30 ? "#7e22ce" : grCol(sg.g), weight: 7, opacity: 0.95}
        ).bindTooltip(`${nf(sg.g, 0)}\u00a0% Steigung`)
      )
    ).addTo(map);
    return true;
  };
  const want = new URLSearchParams(location.hash.split("?")[1] || "").get("karte");
  if (want === "steigung") window.tlWantSlope = true;                 // Verweis aus der Unterseite: steepButton (24-sport.js) schaltet die Färbung ein
  else if (want === "pausen" && A.pauses.length)
    withMap(() =>
      L.layerGroup(
        A.pauses.map(p =>
          L.circleMarker([p.lat, p.lng], {radius: 9, color: "#fff", weight: 2, fillColor: "#7b61c9", fillOpacity: 1}).bindTooltip(
            `Pause ${fmtDauer(p.dur)}, ${nf(p.t / 60000, 0)}\u00a0Min. nach dem Start`
          )
        )
      ).addTo(map)
    );
  return {wx: wxp};
}
const _tour2 = VIEWS.tour;
VIEWS.tour = async id => {
  await _tour2(id);
  await anaRun(id);
};
tlOnSub(t => anaRun(t.id).then(r => r && r.wx));

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
    s += `<text x="${x((X1 * k) / 4)}" y="${H - 6}" text-anchor="${k === 4 ? "end" : k === 0 ? "start" : "middle"}">${fmtKm((X1 * k) / 4, {d: 0})}</text>`;
  series.forEach(
    se =>
      (s += `<path d="${se.pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("")}" fill="none" stroke="${se.color}" stroke-width="2.6"/>`)
  );
  return s + "</svg>";
}
VIEWS.compare = async (_, q) => {
  const ta = BY[q.get("a")],
    tb = BY[q.get("b")];
  if (!ta || !tb) throw notFound("Touren zum Vergleichen", "#/tours", "Alle Touren", "Zum Vergleichen braucht die Adresse zwei vorhandene Touren.");
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
    VF = {km: v => fmtKm(v), m: v => fmtHm(v), h: v => fmtDauer(v * 3600), "km/h": v => fmtTempo(v), "": v => nf(v, 0)},
    d = (x, y, u) => {
      const v = y - x;
      return `<span>${v > 0 ? "+" : v < 0 ? "−" : ""}${VF[u](Math.abs(v))}</span>`;
    };
  const row = (l, x, y, u) =>
    x == null || y == null
      ? ""
      : `<tr><td>${l}</td><td class="n">${VF[u](x)}</td><td class="n">${VF[u](y)}</td><td class="n">${d(x, y, u)}</td></tr>`;
  const alt = (c, A) => c.map((p, i) => [A.cum[i] / 1000, p[2] ?? 0]),
    tim = (c, A) => c.map((p, i) => [A.cum[i] / 1000, (p[3] ?? 0) / 60000]);
  const hasT = ca[0] && ca[0][3] != null && cb[0] && cb[0][3] != null;
  $("#main").innerHTML =
    `<div class="row"><a class="back" href="#/tour/${ta.id}">‹ ${esc(ta.name)}</a></div><div class="sec"><h2>Tourvergleich</h2></div>
   <div class="legend mb10"><span><i style="background:${cols[0]}"></i><a href="#/tour/${ta.id}">${esc(ta.name)}</a> (${fmtDatumKurz(ta.date)})</span><span><i style="background:${cols[1]}"></i><a href="#/tour/${tb.id}">${esc(tb.name)}</a> (${fmtDatumKurz(tb.date)})</span></div>
   <div class="grid g2"><div id="cm" class="cmap"></div><div><table class="cmp"><tr><th></th><th class="n">A</th><th class="n">B</th><th class="n">B − A</th></tr>
    ${row("Strecke", a.km, b.km, "km")}${row("Aufstieg", a.up, b.up, "m")}${row("Dauer", a.h, b.h, "h")}${row("Ø-Tempo gesamt", a.v, b.v, "km/h")}${row("Bewegungszeit", a.moving, b.moving, "h")}${row("Pausen", a.pauses, b.pauses, "")}</table>
    <div class="panel gap"><h3>Höhenprofil</h3>${
      ca.length > 2 && cb.length > 2
        ? xyChart(
            [
              {pts: alt(ca, a.A), color: cols[0]},
              {pts: alt(cb, b.A), color: cols[1]},
            ],
            {fy: v => fmtHm(v)}
          )
        : "<div class='mut'>keine Höhendaten</div>"
    }</div></div></div>
   ${
     hasT
       ? `<div class="panel gap"><h3>Zeit über Strecke</h3><p class="mut fs14">Wo die Linien auseinanderlaufen, war eine Tour schneller (flacher = schneller, Stufen = Pausen).</p>${xyChart(
           [
             {pts: tim(ca, a.A), color: cols[0]},
             {pts: tim(cb, b.A), color: cols[1]},
           ],
           {zero: true, fy: v => fmtDauer(v * 60)}
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
      `<p class="mut fs14 mn4-0-8">${z.state === "ok" ? "✓ Token gültig" : /^fail/.test(z.state || "") ? `<span class="bad">✗ Token ungültig: ${esc(z.state.slice(5))}</span>` : z.state === "none" ? "Kein Token gespeichert" : "Token noch nicht geprüft"}${age != null ? ` · gespeichert vor ${age} Tag${age === 1 ? "" : "en"}` : ""}${z.checked ? ` · zuletzt geprüft ${fmtDatumKurz(+z.checked, {zeit: true})}` : ""} (wird täglich mitgeprüft)</p>`
    );
  sv.closest(".row").insertAdjacentHTML(
    "beforebegin",
    `<div class="grid g2 mt40"><div class="panel"><h2>Foto-Eingang</h2>
    <p class="mut">Fotos einfach in den Eingangsordner kopieren (per <code>scp</code>, <code>rsync</code> oder SMB-Freigabe): <code>${esc(st.inbox || "/var/lib/meine-touren/inbox")}</code>. Sie werden automatisch verkleinert, mit Aufnahmezeit übernommen und Touren zugeordnet (Prüfung alle 5 Minuten).</p>
    <p class="mut fs13">Beispiel vom Mac: <code>rsync -av ~/Pictures/Wanderung/ root@SERVER:${esc(st.inbox || "/var/lib/meine-touren/inbox")}/</code></p></div>
   <div class="panel" id="gpanel"><h2>Wanderführer (z. B. Rother)</h2><p class="mut">Die GPX-Dateien deiner Wanderführer legst du jetzt unter Statistik → Orte &amp; Ausrüstung → Wanderführer an – dort gibt es auch Ordner, Umbenennen, Exportieren und Importieren. Folgt eine Tour einer dieser Strecken, wird der Tourtitel aus dem Buch beim Umbenennen vorgeschlagen.</p>
    <div class="row"><a class="btn alt" href="#/places" id="gup">Zu den Wanderführern</a><span id="gres" class="mut"></span></div><div id="glist" class="mt10"></div></div>
   <div class="panel"><h2>Selbsttest</h2><p class="mut">Prüft Komoot-Zugang, Strecken, Zepp-Token, Internet-Dienste (Karten, Wetter, Höhendaten), Speicherplatz und Sicherung.</p>
    <div class="row"><button class="btn alt" id="stest">Selbsttest starten</button></div><div id="stres" class="mt10"></div></div></div>`
  );
  const gl = async () => {
    const g = await api("/api/guides").catch(() => []),
      by = {};
    g.forEach(x => (by[x.book] ||= []).push(x));
    if (!$("#glist")) return; // Seite inzwischen verlassen
    $("#glist").innerHTML =
      Object.keys(by)
        .map(b => `<div class="r jcsb g8" style="display:flex"><span translate="no">${esc(b || "(ohne Buch)")}</span> <small class="mut">${fmtAnzahl(by[b].length, "Buchtour", "Buchtouren")}</small></div>`)
        .join("") || '<span class="mut">Noch keine Wanderführer hinterlegt.</span>';
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
    w.textContent = `${fmtDatum(t.date, {zeit: true})}`;
    btns.innerHTML = `<a class="btn" href="#/tour/${t.id}">Tour ansehen</a>${t.photos ? `<a class="btn alt c-white" target="_blank" href="slideshow.html?tour=${t.id}">Diashow</a>` : ""}`;
    signs.innerHTML = `<div class="sign">${fmtSignWert(fmtKm(t.km, {einheit: false}), "km")}<small>Strecke</small></div><div class="sign l">${fmtSignWert(fmtHm(t.up_m, {einheit: false}), "m")}<small>Aufstieg</small></div><div class="sign">${(p => fmtSignWert(p.v, p.u))(fmtDauerTeile(t.h * 3600))}<small>Dauer</small></div>`;
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
        `<div class="thumbrow">${ph.map((p, x) => `<img loading="lazy" decoding="async" src="${picSrc(p, 300)}" data-i="${x}">`).join("")}</div>`
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
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "") || $(".uidlg")) return;
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
