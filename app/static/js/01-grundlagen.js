/* Meine Touren – Einzelseiten-App ohne Build-Schritt */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const STALE = () => new Promise(() => {}); // Antwort für eine inzwischen verlassene Seite: nie auflösen, damit die alte Ansicht nichts mehr zeichnet
const api = async (u, o) => {
  const tok = window._rt,
    r = await fetch(u, o);
  if (tok && tok !== window._rt && (!o || !o.method || o.method === "GET")) return STALE();
  if (r.status === 401 && ME.users_enabled && !(u + "").startsWith("/api/login")) {
    showAuth("login", "Bitte anmelden.");
    throw new Error("Bitte anmelden");
  }
  if (!r.ok) {
    let m = await r.text();
    try {
      m = JSON.parse(m).detail || m;
    } catch (e) {}
    throw new Error(m || r.status);
  }
  return r.json();
};
if (window.L) {
  // Leaflet: Zoom-Übergang, der erst nach dem Verlassen der Seite endet, nicht mehr auf die entfernte Karte anwenden
  for (const m of ["_onZoomTransitionEnd", "_onPanTransitionEnd"]) {
    const f = L.Map.prototype[m];
    if (f)
      L.Map.prototype[m] = function (...a) {
        if (!this._mapPane) return;
        return f.apply(this, a);
      };
  }
  // Canvas-Ebene: verspätetes Neuzeichnen nach dem Entfernen der Karte überspringen
  for (const m of ["_redraw", "_updatePaths", "_draw"]) {
    const f = L.Canvas && L.Canvas.prototype[m];
    if (f)
      L.Canvas.prototype[m] = function (...a) {
        if (!this._ctx || !this._map) return;
        return f.apply(this, a);
      };
  }
}
const pad2 = n => String(n).padStart(2, "0");
const nf = (n, d = 1) => Number(n ?? 0).toLocaleString("de-DE", {minimumFractionDigits: d, maximumFractionDigits: d});
const MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const MONL = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const dateL = iso => {
  const d = iso.slice(0, 10).split("-");
  return `${+d[2]}. ${MONL[+d[1] - 1]} ${d[0]}`;
};
const dateS = iso => iso.slice(8, 10) + "." + iso.slice(5, 7) + "." + iso.slice(0, 4);
const timeS = iso => iso.slice(11, 16);
const SPORT = {
  hike: ["Wandern", "--hike"],
  touringbicycle: ["Radtour", "--bike"],
  e_touringbicycle: ["E-Bike", "--ebike"],
  racebike: ["Rennrad", "--bike"],
  mtb: ["MTB", "--bike"],
  jogging: ["Laufen", "--run"],
  skialpin: ["Skifahren", "--ski"],
  skitour: ["Skitour", "--ski"],
  nordic: ["Langlauf", "--ski"],
  snowshoe: ["Schneeschuh", "--snow"],
  mountaineering: ["Bergtour", "--hike"],
  nordicwalking: ["Nordic Walking", "--hike"],
};
const sName = s => (SPORT[s] || [s || "Sonstiges"])[0];
const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const sCol = s => cssv((SPORT[s] || [0, "--other"])[1]);
/* ---- Streckenfarbe (pro Gerät gemerkt) ---- */
const TS = (() => {
  let s = {};
  try {
    s = JSON.parse(localStorage.getItem("trackstyle")) || {};
  } catch (e) {}
  return Object.assign({mode: "sport", color: "#ff2d95", weight: 4, casing: false, by: "none"}, s);
})();
let prefTimer = null;
const pushPrefs = () => {
  clearTimeout(prefTimer);
  prefTimer = setTimeout(() => {
    let ms = null;
    try {
      ms = localStorage.getItem("mapstyle");
    } catch (e) {}
    fetch("/api/settings", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({ui_prefs: JSON.stringify({ts: TS, mapstyle: ms})}),
    }).catch(() => {});
  }, 600);
};
const saveTS = () => {
  try {
    localStorage.setItem("trackstyle", JSON.stringify(TS));
  } catch (e) {}
  pushPrefs();
};
async function loadPrefs() {
  // Einstellungen gelten auf allen Geräten: Server hat Vorrang, sonst lokale Werte hochladen
  try {
    const s = await fetch("/api/settings").then(r => r.json()),
      p = s.ui_prefs ? JSON.parse(s.ui_prefs) : null;
    if (p) {
      Object.assign(TS, p.ts || {});
      try {
        localStorage.setItem("trackstyle", JSON.stringify(TS));
        if (p.mapstyle) localStorage.setItem("mapstyle", p.mapstyle);
      } catch (e) {}
    } else if (localStorage.getItem("trackstyle") || localStorage.getItem("mapstyle")) pushPrefs();
  } catch (e) {}
}
const trackStyle = (t, w) => ({
  color: TS.mode === "one" ? TS.color : sCol(t.sport),
  weight: w || TS.weight,
  opacity: 0.92,
  ...(TS.casing ? {} : {}),
});
function trackPanel(anchor, onChange, withBy) {
  document.querySelector(".tpanel")?.remove();
  const sw = ["#ff2d95", "#ff4d12", "#f2c230", "#00e5ff", "#7cff3a", "#ffffff", "#111111"];
  const d = document.createElement("div");
  d.className = "tpanel";
  d.innerHTML = `<b>Streckenfarbe</b>
    <label><input type="radio" name="tsm" value="sport"> je Sportart</label><label><input type="radio" name="tsm" value="one"> einheitlich</label>
    <div class="tsw">${sw.map(c => `<button type="button" data-c="${c}" style="background:${c}" aria-label="${c}"></button>`).join("")}<input type="color" id="tsc" aria-label="Eigene Farbe"></div>
    ${withBy ? `<label>Einfärben nach <select id="tby"><option value="none">einfarbig</option><option value="grade">Steigung</option><option value="speed">Tempo</option></select></label>` : ""}
    <label>Breite <input type="range" id="tsb" min="2" max="9" step="1"> <span id="tsbv"></span></label>
    <label><input type="checkbox" id="tsk"> weiße Umrandung (besser sichtbar auf Satellit/Topo)</label>
    <button class="btn sm alt" type="button" id="tsx">Schließen</button>`;
  anchor.parentElement.appendChild(d);
  const sync = () => {
    d.querySelector(`[name=tsm][value=${TS.mode}]`).checked = true;
    $("#tsc").value = TS.color;
    $("#tsb").value = TS.weight;
    $("#tsbv").textContent = TS.weight;
    $("#tsk").checked = TS.casing;
    if ($("#tby")) $("#tby").value = TS.by;
  };
  const ch = () => {
    saveTS();
    sync();
    onChange();
  };
  d.querySelectorAll("[name=tsm]").forEach(
    r =>
      (r.onchange = () => {
        TS.mode = r.value;
        ch();
      })
  );
  d.querySelectorAll("[data-c]").forEach(
    b =>
      (b.onclick = () => {
        TS.color = b.dataset.c;
        TS.mode = "one";
        ch();
      })
  );
  $("#tsc").oninput = e => {
    TS.color = e.target.value;
    TS.mode = "one";
    ch();
  };
  $("#tsb").oninput = e => {
    TS.weight = +e.target.value;
    ch();
  };
  $("#tsk").onchange = e => {
    TS.casing = e.target.checked;
    ch();
  };
  if ($("#tby"))
    $("#tby").onchange = e => {
      TS.by = e.target.value;
      ch();
    };
  $("#tsx").onclick = () => d.remove();
  sync();
}
const casePane = m => {
  if (!m.getPane("casing")) m.createPane("casing").style.zIndex = 390;
};

const regionKey = t => ({c: t.g_country || "", s: t.g_state || "", k: t.g_county || ""});
const allTags = () => [...new Set(TOURS.flatMap(t => (t.tags || "").split("|")).filter(Boolean))].sort((a, b) => a.localeCompare(b, "de"));
const inRegion = (t, v) => {
  if (!v) return true;
  const [kind, a, b] = v.split("|");
  if (kind === "c") return t.g_country === a;
  return t.g_country === a && t.g_state === b;
};
function regionOpts() {
  const m = {};
  TOURS.forEach(t => {
    if (!t.g_country) return;
    const c = (m[t.g_country] ||= {n: 0, s: {}});
    c.n++;
    if (t.g_state) c.s[t.g_state] = (c.s[t.g_state] || 0) + 1;
  });
  return Object.keys(m)
    .sort()
    .map(
      c =>
        `<option value="c|${esc(c)}">${esc(c)} (${m[c].n})</option>` +
        Object.keys(m[c].s)
          .sort()
          .map(s => `<option value="s|${esc(c)}|${esc(s)}">\u2003${esc(s)} (${m[c].s[s]})</option>`)
          .join("")
    )
    .join("");
}
let TOURS = [],
  BY = {},
  ROUTES = null,
  PHINFO = null,
  pollTimer = null,
  map = null;
const NAV = [
  ["dash", "Übersicht"],
  ["map", "Karte"],
  ["tours", "Touren"],
  ["trips", "Reisen"],
  ["places", "Auswertung"],
  ["photos", "Fotos"],
  ["check", "Prüfen"],
  ["admin", "Verwaltung"],
];
$("#nav").innerHTML = NAV.map(([k, l]) => `<a href="#/${k}" data-k="${k}">${l}</a>`).join("");

async function loadTours() {
  TOURS = await api("/api/tours");
  TOURS.forEach(t => {
    t.y = +t.date.slice(0, 4);
    t.m = +t.date.slice(5, 7);
    t.km = t.dist_m / 1000;
    t.h = (t.dur_s || 0) / 3600;
    BY[t.id] = t;
  });
}
const years = () => [...new Set(TOURS.map(t => t.y))].sort((a, b) => b - a);

/* ---------- Router ---------- */
async function route() {
  const [path, qs] = (location.hash || "#/dash").replace(/^#\/?/, "").split("?");
  const [k = "dash", name] = path.split("/");
  document.querySelectorAll("nav a").forEach(a => a.classList.toggle("on", a.dataset.k === (k === "tour" || k === "flight" ? "tours" : k)));
  document.querySelectorAll(".modal").forEach(m => m.remove());
  clearInterval(pollTimer);
  if (map) {
    try {
      map.stop();
      map.off();
      map.remove();
    } catch (e) {}
    map = null;
  }
  if (k !== "search" && $("#gs")) $("#gs").value = "";
  $("#main").className = k === "map" ? "wide" : "";
  window.scrollTo(0, 0);
  if (k === "tour" && /^#\/(trip|album)\//.test(window._cur || ""))
    window._from = window._cur; // Rücksprung zur Reise bzw. zum Album merken
  else if (k !== "tour" && k !== "flight") window._from = null;
  window._cur = location.hash;
  const tok = (window._rt = (window._rt || 0) + 1); // nur die zuletzt geöffnete Seite darf Fehler anzeigen
  try {
    if (!TOURS.length) await loadTours();
    await (VIEWS[k] || VIEWS.dash)(name, new URLSearchParams(qs || ""));
  } catch (e) {
    if (tok === window._rt) $("#main").innerHTML = `<div class="card bad">${esc(e.message)}</div>`;
  }
}
addEventListener("hashchange", route);

function miniRoute(id, sport) {
  const r = ROUTES && ROUTES[id];
  if (!r || r.length < 2)
    return `<svg class="mini" viewBox="0 0 78 50"><rect x="1" y="1" width="76" height="48" rx="3" fill="none" stroke="var(--rule)"/></svg>`;
  const la = r.map(p => p[0]),
    lo = r.map(p => p[1]),
    k = Math.cos((la[0] * Math.PI) / 180),
    x0 = Math.min(...lo),
    y1 = Math.max(...la);
  const w = (Math.max(...lo) - x0) * k || 1e-6,
    h = y1 - Math.min(...la) || 1e-6,
    sc = Math.min(70 / w, 42 / h),
    ox = (78 - w * sc) / 2,
    oy = (50 - h * sc) / 2;
  const d = r.map((p, i) => `${i ? "L" : "M"}${(ox + (p[1] - x0) * k * sc).toFixed(1)},${(oy + (y1 - p[0]) * sc).toFixed(1)}`).join("");
  return `<svg class="mini" viewBox="0 0 78 50"><path d="${d}" fill="none" stroke="${sCol(sport)}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}
/* ---------- SVG-Diagramme ---------- */
function barChart(vals, labels, o = {}) {
  const W = 520,
    H = 210,
    L = 38,
    B = 24,
    T = 10,
    n = vals.length,
    mx = Math.max(1, ...vals, ...(o.ghost || [0])) * 1.08;
  const bw = (W - L) / n,
    y = v => T + (H - T - B) * (1 - v / mx),
    best = vals.indexOf(Math.max(...vals));
  const ticks = [0, 0.5, 1].map(f => (mx * f) / 1.08);
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}">`;
  ticks.forEach(
    v =>
      (s += `<line x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)" stroke-dasharray="2 4"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${nf(v, 0)}</text>`)
  );
  vals.forEach((v, i) => {
    const x = L + i * bw + bw * 0.14,
      w = bw * 0.72,
      hgt = Math.max(0, H - B - y(v));
    s += `<rect class="bar${i === best && vals[i] > 0 && !o.href ? " best" : ""}" ${o.href ? `data-h="${o.href[i]}" style="cursor:pointer"` : ""} x="${x}" y="${y(v)}" width="${w}" height="${hgt}" rx="3" ${o.colors ? `fill="${o.colors[i]}"` : ""}><title>${labels[i]}: ${nf(v)} ${o.unit || "km"}</title></rect>`;
    s += `<text x="${x + w / 2}" y="${H - 6}" text-anchor="middle">${labels[i]}</text>`;
  });
  if (o.ghost)
    o.ghost.forEach((v, i) => {
      const x = L + i * bw + bw * 0.1,
        w = bw * 0.8;
      if (v > 0)
        s += `<line x1="${x}" x2="${x + w}" y1="${y(v)}" y2="${y(v)}" stroke="var(--accent2)" stroke-width="3" stroke-linecap="round"><title>${o.ghostLabel}: ${labels[i]} ${nf(v)} km</title></line>`;
    });
  return s + "</svg>";
}
function lineChart(series, o = {}) {
  const W = 520,
    H = 210,
    L = 40,
    B = 24,
    T = 10,
    mx = Math.max(1, ...series.flatMap(s => s.pts.map(p => p[1]))) * 1.06;
  const x = d => L + ((W - L - 6) * d) / 366,
    y = v => T + (H - T - B) * (1 - v / mx);
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}">`;
  [0, 0.5, 1].forEach(f => {
    const v = (mx * f) / 1.06;
    s += `<line x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)" stroke-dasharray="2 4"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${nf(v, 0)}</text>`;
  });
  [0, 2, 4, 6, 8, 10].forEach(m => (s += `<text x="${x(m * 30.5)}" y="${H - 6}">${MON[m]}</text>`));
  series.forEach(se => {
    const d = se.pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
    s += `<path d="${d}" fill="none" stroke="${se.color}" stroke-width="${se.w || 2.4}" ${se.dash ? 'stroke-dasharray="4 4"' : ""} stroke-linejoin="round"/>`;
  });
  return s + "</svg>";
}
function heat(year, byDay) {
  const start = new Date(Date.UTC(year, 0, 1)),
    off = (start.getUTCDay() + 6) % 7,
    cell = 12,
    gap = 3,
    W = 54 * (cell + gap) + 24;
  const mx = Math.max(10, ...Object.values(byDay));
  let s = `<svg class="heat" viewBox="0 0 ${W} ${7 * (cell + gap) + 22}">`;
  for (let d = 0; d < 366; d++) {
    const dt = new Date(Date.UTC(year, 0, 1 + d));
    if (dt.getUTCFullYear() !== year) break;
    const k = dt.toISOString().slice(0, 10),
      v = byDay[k] || 0,
      i = d + off,
      cx = 22 + Math.floor(i / 7) * (cell + gap),
      cy = (i % 7) * (cell + gap);
    const a = v ? 0.25 + 0.75 * Math.min(1, v / mx) : 0;
    s += `<rect x="${cx}" y="${cy}" width="${cell}" height="${cell}" rx="3" fill="${v ? `color-mix(in srgb,var(--bars) ${Math.round(a * 100)}%,var(--surface))` : "var(--soft)"}"><title>${dateS(k)}${v ? ": " + nf(v) + " km" : ""}</title></rect>`;
  }
  ["Mo", "Mi", "Fr"].forEach((l, i) => (s += `<text x="0" y="${i * 2 * (cell + gap) + 10}">${l}</text>`));
  for (let m = 0; m < 12; m++) {
    const i = Math.floor(((new Date(Date.UTC(year, m, 1)) - start) / 864e5 + off) / 7);
    s += `<text x="${22 + i * (cell + gap)}" y="${7 * (cell + gap) + 14}">${MON[m]}</text>`;
  }
  return s + "</svg>";
}

/* ---------- Karten ---------- */
const TBASE = location.origin + location.pathname.replace(/[^/]*$/, "");
function tileL(style, direct, o) {
  // Kacheln über den Cache des Servers, bei Fehlern direkt vom Anbieter
  const l = L.tileLayer(TBASE + `tiles/${style}/{z}/{x}/{y}`, o);
  let err = 0;
  l.on("tileerror", () => {
    if (++err === 4) l.setUrl(direct);
  });
  return l;
}
function mkMap(el, opt = {}) {
  const m = L.map(el, {zoomControl: opt.zoom !== false, attributionControl: opt.attr !== false, ...opt.leaflet});
  const osm = tileL("osm", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 19, attribution: "© OpenStreetMap"});
  const topo = tileL("topo", "https://tile.opentopomap.org/{z}/{x}/{y}.png", {
    maxZoom: 17,
    attribution: "© OpenTopoMap, © OpenStreetMap",
  });
  let sv = null;
  try {
    sv = localStorage.getItem("mapstyle");
  } catch (e) {}
  (sv === "topo" ? topo : osm).addTo(m);
  if (opt.layers) {
    L.control.layers({Straßenkarte: osm, Topografisch: topo}, null, {position: "bottomright"}).addTo(m);
    m.on("baselayerchange", e => {
      try {
        localStorage.setItem("mapstyle", e.layer === topo ? "topo" : "osm");
      } catch (x) {}
      pushPrefs();
    });
  }
  return m;
}
const okPt = p => Array.isArray(p) && p[0] != null && p[1] != null && isFinite(p[0]) && isFinite(p[1]);
const cleanPts = a => (Array.isArray(a) ? a.filter(okPt) : []);
const loadRoutes = async () => ROUTES || (ROUTES = await api("/api/routes"));
