/* =====================  Startseite: zuletzt unterwegs, das laufende Jahr, letzte Touren, an diesem Tag, Erinnerungen.
   Die bisherige Übersicht (alle Zahlen, Diagramme, Ziele) ist jetzt der erste Reiter der Statistik (#/stats).  ===================== */
const homeRoute = pts => {
  if (!pts || pts.length < 2) return "";
  const la = pts.map(p => p[0]),
    lo = pts.map(p => p[1]),
    k = Math.cos((la[0] * Math.PI) / 180),
    x0 = Math.min(...lo),
    y1 = Math.max(...la),
    w = (Math.max(...lo) - x0) * k || 1e-6,
    h = y1 - Math.min(...la) || 1e-6,
    sc = Math.min(700 / w, 400 / h),
    ox = (800 - w * sc) / 2,
    oy = (500 - h * sc) / 2,
    P = p => [(ox + (p[1] - x0) * k * sc).toFixed(1), (oy + (y1 - p[0]) * sc).toFixed(1)],
    d = pts.map((p, i) => (i ? "L" : "M") + P(p).join(",")).join(""),
    a = P(pts[0]),
    z = P(pts[pts.length - 1]);
  return `<svg viewBox="0 0 800 500" preserveAspectRatio="xMidYMid meet" aria-hidden="true"><path d="${d}" fill="none" stroke="#0b1d1e" stroke-opacity=".35" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/><path d="${d}" fill="none" stroke="var(--yellow)" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${a[0]}" cy="${a[1]}" r="8" fill="#fff" stroke="#0b1d1e" stroke-width="3"/><circle cx="${z[0]}" cy="${z[1]}" r="8" fill="var(--yellow)" stroke="#0b1d1e" stroke-width="3"/></svg>`;
};
const homeDur = h => `${Math.floor(h)}:${String(Math.round((h % 1) * 60) % 60).padStart(2, "0")}`;

async function homeView() {
  const main = $("#main");
  main.className = "home";
  loadRoutesLater();
  const now = new Date(),
    cy = now.getFullYear(),
    sum = (a, f) => a.reduce((x, t) => x + f(t), 0),
    doy = d => (d - new Date(d.getFullYear(), 0, 1)) / 864e5,
    ys = TOURS.some(t => t.y === cy) ? cy : Math.max(...TOURS.map(t => t.y)),     // laufendes Jahr; ohne Touren darin das letzte Jahr mit Touren
    yr = TOURS.filter(t => t.y === ys),
    lyTo = ys === cy ? TOURS.filter(t => t.y === cy - 1 && doy(new Date(t.date)) <= doy(now)) : [],
    km = sum(yr, t => t.km),
    kmL = sum(lyTo, t => t.km),
    mm = Array(12).fill(0);
  yr.forEach(t => (mm[t.m - 1] += t.km));
  const mx = Math.max(...mm, 1),
    md = `${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`,
    otd = TOURS.filter(t => t.date.slice(5, 10) === md && t.y !== cy),
    recent = TOURS.slice(0, 9),
    cmp = kmL > 0 && km > 0 ? `<span class="hcmp ${km >= kmL ? "up" : "down"}">${km >= kmL ? "+" : "−"}${nf((Math.abs(km - kmL) / kmL) * 100, 0)} % gegenüber ${cy - 1} bis heute</span>` : "";
  const card = t => `<a class="hcard" href="#/tour/${t.id}" data-t="${t.id}">
      <div class="hcm" data-m="${t.id}">${miniRoute(t.id, t.sport)}</div>
      <div class="hcb"><b>${esc(t.name)}</b><span class="mut">${dateL(t.date)}</span>
      <span class="hcf">${nf(t.km, 1)} km<i></i>${nf(t.up_m || 0, 0)} m<i></i>${homeDur(t.h)} h${t.has_hr ? `<span class="hrt" title="Mit Herzfrequenz">❤</span>` : ""}</span></div></a>`;
  main.innerHTML = `
  <section class="hlast" id="hlast"></section>
  <section class="hyear">
    <div class="hyh"><h2>Dein Jahr ${ys}</h2>${cmp}<span class="sp"></span><a class="hmore" href="#/stats">Zur Statistik</a></div>
    <div class="hyg">
      <div class="hyn"><b>${nf(yr.length, 0)}</b><span>Touren</span></div>
      <div class="hyn"><b>${nf(km, 0)}</b><span>Kilometer</span></div>
      <div class="hyn"><b>${nf(sum(yr, t => t.up_m || 0), 0)}</b><span>Höhenmeter</span></div>
      <div class="hyn"><b>${nf(sum(yr, t => t.h), 0)}</b><span>Stunden unterwegs</span></div>
      <div class="hym" title="Kilometer pro Monat">${mm.map((v, i) => `<div class="${ys === cy && i === now.getMonth() ? "cur" : ""}" title="${MONL[i]}: ${nf(v, 0)} km"><i style="height:${Math.max(v ? 6 : 2, (v / mx) * 100)}%"></i><span>${MON[i].slice(0, 1)}</span></div>`).join("")}</div>
    </div>
    <div id="hgoals"></div>
  </section>
  ${recent.length > 1 ? `<section><div class="hsh"><h2>Zuletzt unterwegs</h2><span class="sp"></span><a class="hmore" href="#/tours">Alle ${nf(TOURS.length, 0)} Touren</a></div><div class="hcards">${recent.slice(1).map(card).join("")}</div></section>` : ""}
  <div class="hcols">
    ${otd.length ? `<section><div class="hsh"><h2>An diesem Tag</h2><span class="sub">in früheren Jahren</span></div><div class="tl">${otd.map(tourRow).join("")}</div></section>` : ""}
    <section id="hmemsec" hidden><div class="hsh"><h2>Erinnerungen</h2><span class="sp"></span><a class="hmore" target="_blank" href="slideshow.html?random=1">Zufalls-Diashow</a></div><div id="hmem" class="hmem"></div></section>
  </div>`;

  /* --- Aufmacher: die letzten Touren zum Durchblättern --- */
  const N = Math.min(8, TOURS.length);
  let cur = 0,
    tok = 0;
  const show = async i => {
    cur = (i + N) % N;
    const t = TOURS[cur],
      my = ++tok,
      box = $("#hlast");
    if (!box) return;
    box.innerHTML = `
      <div class="hlm" id="hlm"><div class="hlr" id="hlr"></div></div>
      <div class="hli">
        <div class="hlk">${cur ? `${cur + 1}. letzte Tour` : "Zuletzt unterwegs"}<span class="tag" style="background:${sCol(t.sport)}">${sName(t.sport)}</span></div>
        <h1>${esc(t.name)}</h1>
        <div class="hlw">${dateL(t.date)}, ${timeS(t.date)} Uhr</div>
        <div class="signs"><div class="sign">${nf(t.km, 1)}<small>Kilometer</small></div><div class="sign l">${nf(t.up_m || 0, 0)}<small>Meter aufwärts</small></div><div class="sign">${homeDur(t.h)}<small>Stunden</small></div></div>
        <div class="hlx" id="hlx">${t.has_hr ? `<span><span class="hrt">❤</span> <span id="hlhr">Puls aufgezeichnet</span></span>` : ""}${t.stars ? `<span class="stars">${"★".repeat(t.stars)}</span>` : ""}</div>
        <div class="btns"><a class="btn" href="#/tour/${t.id}">Tour ansehen</a>${t.photos ? `<a class="btn alt" href="#/story/${t.id}">Erzählung</a>` : ""}<a class="btn alt" href="#/flight/${encodeURIComponent(t.id)}">3D-Flug</a></div>
        ${N > 1 ? `<div class="hlnav"><button id="hprev" aria-label="Neuere Tour" title="Neuere Tour">‹</button><span>${cur + 1} / ${N}</span><button id="hnext" aria-label="Ältere Tour" title="Ältere Tour">›</button></div>` : ""}
      </div>`;
    if ($("#hprev")) {
      $("#hprev").onclick = () => show(cur - 1);
      $("#hnext").onclick = () => show(cur + 1);
    }
    const ph = t.photos ? await api(`/api/photos?tour_id=${t.id}&limit=4`).catch(() => []) : [];
    if (my !== tok || !$("#hlm")) return;
    if (ph.length) {
      $("#hlm").classList.add("ph");
      $("#hlm").insertAdjacentHTML("afterbegin", `<img class="hlp" src="/pic/${ph[0].id}?size=1200" alt="" data-i="0">${ph.length > 1 ? `<div class="hlt">${ph.slice(1).map((p, j) => `<img loading="lazy" src="/pic/${p.id}?size=300" alt="" data-i="${j + 1}">`).join("")}</div>` : ""}`);
      bindThumbs($("#hlm"), ph);
    }
    api(`/api/tours/${t.id}/coords`)
      .then(c => {
        if (my === tok && $("#hlr")) $("#hlr").innerHTML = homeRoute(cleanPts(c));
      })
      .catch(() => {});
    if (t.has_hr)
      api(`/api/tours/${encodeURIComponent(t.id)}/hr`)
        .then(h => {
          if (my === tok && h && h.n && $("#hlhr")) $("#hlhr").textContent = `Ø ${h.avg} bpm, max ${h.max}`;
        })
        .catch(() => {});
  };
  show(0);

  /* --- Streckenformen nachtragen, sobald die Strecken geladen sind; Titelbilder der letzten Touren --- */
  if (!ROUTES)
    loadRoutes()
      .then(() => document.querySelectorAll(".hcm:not(.ph)").forEach(el => BY[el.dataset.m] && (el.innerHTML = miniRoute(el.dataset.m, BY[el.dataset.m].sport))))
      .catch(() => {});
  recent.slice(1).forEach(t => {
    if (!t.photos) return;
    api(`/api/photos?tour_id=${t.id}&limit=1`)
      .then(p => {
        const el = document.querySelector(`.hcm[data-m="${t.id}"]`);
        if (el && p.length) {
          el.classList.add("ph");
          el.innerHTML = `<img loading="lazy" src="/pic/${p[0].id}?size=500" alt="">`;
        }
      })
      .catch(() => {});
  });

  /* --- Ziele des Jahres (höchstens zwei), Verwaltung der Ziele in der Statistik --- */
  api("/api/goals")
    .then(all => {
      const gs = all.filter(g => g.year === ys).slice(0, 2),
        box = $("#hgoals");
      if (!box || !gs.length || typeof goalVal !== "function") return;
      const frac = ys === cy ? Math.max(0, (now - new Date(cy, 0, 1)) / (new Date(cy + 1, 0, 1) - new Date(cy, 0, 1))) : 1;
      box.innerHTML = gs
        .map(g => {
          const v = goalVal(g, TOURS),
            p = Math.min(100, (v / g.target) * 100);
          return `<a class="hgoal" href="#/stats"><span>${GM[g.metric][1]}${g.sport ? " " + goalSportName(g.sport) : ""}</span><div class="gb"><i style="width:${p}%"></i><u style="left:${frac * 100}%" title="Soll heute"></u></div><b>${nf(v, 0)} / ${nf(g.target, 0)} ${GM[g.metric][0]}</b></a>`;
        })
        .join("");
    })
    .catch(() => {});

  /* --- Erinnerungen --- */
  api("/api/photos?random=true&limit=6")
    .then(r => {
      if (!r.length || !$("#hmem")) return;
      $("#hmemsec").hidden = false;
      $("#hmem").innerHTML = r.map((p, i) => `<img loading="lazy" src="/pic/${p.id}?size=400" data-i="${i}" title="${esc(p.tour_name || "")}" alt="">`).join("");
      bindThumbs($("#hmem"), r);
    })
    .catch(() => {});
}

{
  const dashOld = VIEWS.dash;
  VIEWS.stats = async (n, q) => {
    await dashOld(n, q || new URLSearchParams(""));
    if (TOURS.length) statTabs("stats");
  };
  VIEWS.dash = async (n, q) => {
    if (!TOURS.length) return dashOld(n, q);
    if (q && [...q.keys()].length) return VIEWS.stats(n, q);        // Jahr/Sportart gewählt: das ist die Statistik-Übersicht
    await homeView();
  };
}
