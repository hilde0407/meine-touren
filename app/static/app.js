/* Meine Touren – Einzelseiten-App ohne Build-Schritt */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const api = async (u, o) => { const r = await fetch(u, o); if (r.status === 401 && ME.users_enabled && !(u + "").startsWith("/api/login")) { showAuth("login", "Bitte anmelden."); throw new Error("Bitte anmelden"); } if (!r.ok) { let m = await r.text(); try { m = JSON.parse(m).detail || m; } catch (e) {} throw new Error(m || r.status); } return r.json(); };
const pad2 = n => String(n).padStart(2, "0");
const nf = (n, d = 1) => Number(n ?? 0).toLocaleString("de-DE", {minimumFractionDigits: d, maximumFractionDigits: d});
const MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const MONL = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const dateL = iso => { const d = iso.slice(0, 10).split("-"); return `${+d[2]}. ${MONL[+d[1] - 1]} ${d[0]}`; };
const dateS = iso => iso.slice(8, 10) + "." + iso.slice(5, 7) + "." + iso.slice(0, 4);
const timeS = iso => iso.slice(11, 16);
const SPORT = {
  hike: ["Wandern", "--hike"], touringbicycle: ["Radtour", "--bike"], e_touringbicycle: ["E-Bike", "--ebike"], racebike: ["Rennrad", "--bike"],
  mtb: ["MTB", "--bike"], jogging: ["Laufen", "--run"], skialpin: ["Skifahren", "--ski"], skitour: ["Skitour", "--ski"], nordic: ["Langlauf", "--ski"],
  snowshoe: ["Schneeschuh", "--snow"], mountaineering: ["Bergtour", "--hike"], nordicwalking: ["Nordic Walking", "--hike"],
};
const sName = s => (SPORT[s] || [s || "Sonstiges"])[0];
const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const sCol = s => cssv((SPORT[s] || [0, "--other"])[1]);
/* ---- Streckenfarbe (pro Gerät gemerkt) ---- */
const TS = (() => { let s = {}; try { s = JSON.parse(localStorage.getItem("trackstyle")) || {}; } catch (e) {} return Object.assign({mode: "sport", color: "#ff2d95", weight: 4, casing: false, by: "none"}, s); })();
let prefTimer = null;
const pushPrefs = () => { clearTimeout(prefTimer); prefTimer = setTimeout(() => { let ms = null; try { ms = localStorage.getItem("mapstyle"); } catch (e) {}
  fetch("/api/settings", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({ui_prefs: JSON.stringify({ts: TS, mapstyle: ms})})}).catch(() => {}); }, 600); };
const saveTS = () => { try { localStorage.setItem("trackstyle", JSON.stringify(TS)); } catch (e) {} pushPrefs(); };
async function loadPrefs() {   // Einstellungen gelten auf allen Geräten: Server hat Vorrang, sonst lokale Werte hochladen
  try { const s = await fetch("/api/settings").then(r => r.json()), p = s.ui_prefs ? JSON.parse(s.ui_prefs) : null;
    if (p) { Object.assign(TS, p.ts || {}); try { localStorage.setItem("trackstyle", JSON.stringify(TS)); if (p.mapstyle) localStorage.setItem("mapstyle", p.mapstyle); } catch (e) {} }
    else if (localStorage.getItem("trackstyle") || localStorage.getItem("mapstyle")) pushPrefs(); } catch (e) {}
}
const trackStyle = (t, w) => ({color: TS.mode === "one" ? TS.color : sCol(t.sport), weight: w || TS.weight, opacity: .92, ...(TS.casing ? {} : {})});
function trackPanel(anchor, onChange, withBy) {
  document.querySelector(".tpanel")?.remove();
  const sw = ["#ff2d95", "#ff4d12", "#f2c230", "#00e5ff", "#7cff3a", "#ffffff", "#111111"];
  const d = document.createElement("div"); d.className = "tpanel";
  d.innerHTML = `<b>Streckenfarbe</b>
    <label><input type="radio" name="tsm" value="sport"> je Sportart</label><label><input type="radio" name="tsm" value="one"> einheitlich</label>
    <div class="tsw">${sw.map(c => `<button type="button" data-c="${c}" style="background:${c}" aria-label="${c}"></button>`).join("")}<input type="color" id="tsc" aria-label="Eigene Farbe"></div>
    ${withBy ? `<label>Einfärben nach <select id="tby"><option value="none">einfarbig</option><option value="grade">Steigung</option><option value="speed">Tempo</option></select></label>` : ""}
    <label>Breite <input type="range" id="tsb" min="2" max="9" step="1"> <span id="tsbv"></span></label>
    <label><input type="checkbox" id="tsk"> weiße Umrandung (besser sichtbar auf Satellit/Topo)</label>
    <button class="btn sm alt" type="button" id="tsx">Schließen</button>`;
  anchor.parentElement.appendChild(d);
  const sync = () => { d.querySelector(`[name=tsm][value=${TS.mode}]`).checked = true; $("#tsc").value = TS.color; $("#tsb").value = TS.weight; $("#tsbv").textContent = TS.weight; $("#tsk").checked = TS.casing; if ($("#tby")) $("#tby").value = TS.by; };
  const ch = () => { saveTS(); sync(); onChange(); };
  d.querySelectorAll("[name=tsm]").forEach(r => r.onchange = () => { TS.mode = r.value; ch(); });
  d.querySelectorAll("[data-c]").forEach(b => b.onclick = () => { TS.color = b.dataset.c; TS.mode = "one"; ch(); });
  $("#tsc").oninput = e => { TS.color = e.target.value; TS.mode = "one"; ch(); };
  $("#tsb").oninput = e => { TS.weight = +e.target.value; ch(); }; $("#tsk").onchange = e => { TS.casing = e.target.checked; ch(); };
  if ($("#tby")) $("#tby").onchange = e => { TS.by = e.target.value; ch(); };
  $("#tsx").onclick = () => d.remove(); sync();
}
const casePane = m => { if (!m.getPane("casing")) m.createPane("casing").style.zIndex = 390; };


const regionKey = t => ({c: t.g_country || "", s: t.g_state || "", k: t.g_county || ""});
const allTags = () => [...new Set(TOURS.flatMap(t => (t.tags || "").split("|")).filter(Boolean))].sort((a, b) => a.localeCompare(b, "de"));
const inRegion = (t, v) => { if (!v) return true; const [kind, a, b] = v.split("|"); if (kind === "c") return t.g_country === a; return t.g_country === a && t.g_state === b; };
function regionOpts() {
  const m = {}; TOURS.forEach(t => { if (!t.g_country) return; const c = m[t.g_country] ||= {n: 0, s: {}}; c.n++; if (t.g_state) c.s[t.g_state] = (c.s[t.g_state] || 0) + 1; });
  return Object.keys(m).sort().map(c => `<option value="c|${esc(c)}">${esc(c)} (${m[c].n})</option>` + Object.keys(m[c].s).sort().map(s => `<option value="s|${esc(c)}|${esc(s)}">\u2003${esc(s)} (${m[c].s[s]})</option>`).join("")).join("");
}
let TOURS = [], BY = {}, ROUTES = null, PHINFO = null, pollTimer = null, map = null;
const NAV = [["dash", "Übersicht"], ["map", "Karte"], ["tours", "Touren"], ["trips", "Reisen"], ["places", "Auswertung"], ["photos", "Fotos"], ["check", "Prüfen"], ["admin", "Verwaltung"]];
$("#nav").innerHTML = NAV.map(([k, l]) => `<a href="#/${k}" data-k="${k}">${l}</a>`).join("");

async function loadTours() {
  TOURS = await api("/api/tours");
  TOURS.forEach(t => { t.y = +t.date.slice(0, 4); t.m = +t.date.slice(5, 7); t.km = t.dist_m / 1000; t.h = (t.dur_s || 0) / 3600; BY[t.id] = t; });
}
const years = () => [...new Set(TOURS.map(t => t.y))].sort((a, b) => b - a);

/* ---------- Router ---------- */
async function route() {
  const [path, qs] = (location.hash || "#/dash").replace(/^#\/?/, "").split("?");
  const [k = "dash", name] = path.split("/");
  document.querySelectorAll("nav a").forEach(a => a.classList.toggle("on", a.dataset.k === (k === "tour" || k === "flight" ? "tours" : k)));
  document.querySelectorAll(".modal").forEach(m => m.remove());
  clearInterval(pollTimer); if (map) { map.remove(); map = null; }
  if (k !== "search" && $("#gs")) $("#gs").value = "";
  $("#main").className = k === "map" ? "wide" : "";
  window.scrollTo(0, 0);
  try {
    if (!TOURS.length) await loadTours();
    await (VIEWS[k] || VIEWS.dash)(name, new URLSearchParams(qs || ""));
  } catch (e) { $("#main").innerHTML = `<div class="card bad">${esc(e.message)}</div>`; }
}
addEventListener("hashchange", route);

function miniRoute(id, sport) {
  const r = ROUTES && ROUTES[id]; if (!r || r.length < 2) return `<svg class="mini" viewBox="0 0 78 50"><rect x="1" y="1" width="76" height="48" rx="3" fill="none" stroke="var(--rule)"/></svg>`;
  const la = r.map(p => p[0]), lo = r.map(p => p[1]), k = Math.cos(la[0] * Math.PI / 180), x0 = Math.min(...lo), y1 = Math.max(...la);
  const w = (Math.max(...lo) - x0) * k || 1e-6, h = (y1 - Math.min(...la)) || 1e-6, sc = Math.min(70 / w, 42 / h), ox = (78 - w * sc) / 2, oy = (50 - h * sc) / 2;
  const d = r.map((p, i) => `${i ? "L" : "M"}${(ox + (p[1] - x0) * k * sc).toFixed(1)},${(oy + (y1 - p[0]) * sc).toFixed(1)}`).join("");
  return `<svg class="mini" viewBox="0 0 78 50"><path d="${d}" fill="none" stroke="${sCol(sport)}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}
/* ---------- SVG-Diagramme ---------- */
function barChart(vals, labels, o = {}) {
  const W = 520, H = 210, L = 38, B = 24, T = 10, n = vals.length, mx = Math.max(1, ...vals, ...(o.ghost || [0])) * 1.08;
  const bw = (W - L) / n, y = v => T + (H - T - B) * (1 - v / mx), best = vals.indexOf(Math.max(...vals));
  const ticks = [0, .5, 1].map(f => mx * f / 1.08);
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}">`;
  ticks.forEach(v => s += `<line x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)" stroke-dasharray="2 4"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${nf(v, 0)}</text>`);
  vals.forEach((v, i) => {
    const x = L + i * bw + bw * .14, w = bw * .72, hgt = Math.max(0, H - B - y(v));
    s += `<rect class="bar${i === best && vals[i] > 0 && !o.href ? " best" : ""}" ${o.href ? `data-h="${o.href[i]}" style="cursor:pointer"` : ""} x="${x}" y="${y(v)}" width="${w}" height="${hgt}" rx="3" ${o.colors ? `fill="${o.colors[i]}"` : ""}><title>${labels[i]}: ${nf(v)} ${o.unit || "km"}</title></rect>`;
    s += `<text x="${x + w / 2}" y="${H - 6}" text-anchor="middle">${labels[i]}</text>`;
  });
  if (o.ghost) o.ghost.forEach((v, i) => { const x = L + i * bw + bw * .1, w = bw * .8; if (v > 0) s += `<line x1="${x}" x2="${x + w}" y1="${y(v)}" y2="${y(v)}" stroke="var(--accent2)" stroke-width="3" stroke-linecap="round"><title>${o.ghostLabel}: ${labels[i]} ${nf(v)} km</title></line>`; });
  return s + "</svg>";
}
function lineChart(series, o = {}) {
  const W = 520, H = 210, L = 40, B = 24, T = 10, mx = Math.max(1, ...series.flatMap(s => s.pts.map(p => p[1]))) * 1.06;
  const x = d => L + (W - L - 6) * d / 366, y = v => T + (H - T - B) * (1 - v / mx);
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}">`;
  [0, .5, 1].forEach(f => { const v = mx * f / 1.06; s += `<line x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)" stroke-dasharray="2 4"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${nf(v, 0)}</text>`; });
  [0, 2, 4, 6, 8, 10].forEach(m => s += `<text x="${x(m * 30.5)}" y="${H - 6}">${MON[m]}</text>`);
  series.forEach(se => { const d = se.pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(""); s += `<path d="${d}" fill="none" stroke="${se.color}" stroke-width="${se.w || 2.4}" ${se.dash ? 'stroke-dasharray="4 4"' : ""} stroke-linejoin="round"/>`; });
  return s + "</svg>";
}
function heat(year, byDay) {
  const start = new Date(Date.UTC(year, 0, 1)), off = (start.getUTCDay() + 6) % 7, cell = 12, gap = 3, W = 54 * (cell + gap) + 24;
  const mx = Math.max(10, ...Object.values(byDay));
  let s = `<svg class="heat" viewBox="0 0 ${W} ${7 * (cell + gap) + 22}">`;
  for (let d = 0; d < 366; d++) {
    const dt = new Date(Date.UTC(year, 0, 1 + d)); if (dt.getUTCFullYear() !== year) break;
    const k = dt.toISOString().slice(0, 10), v = byDay[k] || 0, i = d + off, cx = 22 + Math.floor(i / 7) * (cell + gap), cy = (i % 7) * (cell + gap);
    const a = v ? .25 + .75 * Math.min(1, v / mx) : 0;
    s += `<rect x="${cx}" y="${cy}" width="${cell}" height="${cell}" rx="3" fill="${v ? `color-mix(in srgb,var(--bars) ${Math.round(a * 100)}%,var(--surface))` : "var(--soft)"}"><title>${dateS(k)}${v ? ": " + nf(v) + " km" : ""}</title></rect>`;
  }
  ["Mo", "Mi", "Fr"].forEach((l, i) => s += `<text x="0" y="${i * 2 * (cell + gap) + 10}">${l}</text>`);
  for (let m = 0; m < 12; m++) { const i = Math.floor(((new Date(Date.UTC(year, m, 1)) - start) / 864e5 + off) / 7); s += `<text x="${22 + i * (cell + gap)}" y="${7 * (cell + gap) + 14}">${MON[m]}</text>`; }
  return s + "</svg>";
}

/* ---------- Karten ---------- */
const TBASE = location.origin + location.pathname.replace(/[^/]*$/, "");
function tileL(style, direct, o) {   // Kacheln über den Cache des Servers, bei Fehlern direkt vom Anbieter
  const l = L.tileLayer(TBASE + `tiles/${style}/{z}/{x}/{y}`, o); let err = 0;
  l.on("tileerror", () => { if (++err === 4) l.setUrl(direct); }); return l;
}
function mkMap(el, opt = {}) {
  const m = L.map(el, {zoomControl: opt.zoom !== false, attributionControl: opt.attr !== false, ...opt.leaflet});
  const osm = tileL("osm", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 19, attribution: "© OpenStreetMap"});
  const topo = tileL("topo", "https://tile.opentopomap.org/{z}/{x}/{y}.png", {maxZoom: 17, attribution: "© OpenTopoMap, © OpenStreetMap"});
  let sv = null; try { sv = localStorage.getItem("mapstyle"); } catch (e) {}
  (sv === "topo" ? topo : osm).addTo(m);
  if (opt.layers) {
    L.control.layers({"Straßenkarte": osm, "Topografisch": topo}, null, {position: "bottomright"}).addTo(m);
    m.on("baselayerchange", e => { try { localStorage.setItem("mapstyle", e.layer === topo ? "topo" : "osm"); } catch (x) {} pushPrefs(); });
  }
  return m;
}
const okPt = p => Array.isArray(p) && p[0] != null && p[1] != null && isFinite(p[0]) && isFinite(p[1]);
const cleanPts = a => Array.isArray(a) ? a.filter(okPt) : [];
const loadRoutes = async () => ROUTES || (ROUTES = await api("/api/routes"));

/* ---------- Übersicht ---------- */
const VIEWS = {};
VIEWS.dash = async (_, q) => {
  if (!TOURS.length) { $("#main").className = ""; $("#main").innerHTML = `<div class="empty"><h2>Noch keine Touren</h2><p>Unter <a href="#/admin"><b>Verwaltung</b></a> kannst du Zepp-Trainings oder GPX/TCX-Dateien importieren – sie werden lokal gespeichert. Optional: Komoot-Zugangsdaten eintragen und „Komoot aktualisieren“.</p></div>`; return; }
  $("#main").className = "flush";
  await loadRoutes().catch(() => {});
  const ys = years(), Y = +(q.get("y") || 0) || 0, S = q.get("s") || "";
  const A = S ? TOURS.filter(t => t.sport === S) : TOURS, yearAll = Y ? TOURS.filter(t => t.y === Y) : TOURS, sel = Y ? A.filter(t => t.y === Y) : A;
  const dh = (y, s) => "#/dash" + (y || s ? "?" + [y ? "y=" + y : "", s ? "s=" + encodeURIComponent(s) : ""].filter(Boolean).join("&") : "");
  const last = TOURS[0], prev = Y ? A.filter(t => t.y === Y - 1) : [];
  const sum = (a, f) => a.reduce((x, t) => x + f(t), 0);
  const km = sum(sel, t => t.km), up = sum(sel, t => t.up_m || 0), hh = sum(sel, t => t.h), pk = sum(prev, t => t.km);
  const delta = (a, b) => b ? `<div class="d ${a >= b ? "up" : "down"}">${a >= b ? "+" : "−"}${nf(Math.abs(a - b) / b * 100, 0)} % gegenüber ${Y - 1}</div>` : "";
  const longest = [...sel].sort((a, b) => b.km - a.km)[0], steepest = [...sel].sort((a, b) => (b.up_m || 0) - (a.up_m || 0))[0], longT = [...sel].sort((a, b) => b.h - a.h)[0];
  const mm = Array(12).fill(0); sel.forEach(t => mm[t.m - 1] += t.km); const bestM = mm.indexOf(Math.max(...mm));
  const pm = Array(12).fill(0); prev.forEach(t => pm[t.m - 1] += t.km);
  const byYear = ys.slice().reverse().map(y => sum(A.filter(t => t.y === y), t => t.km));
  const bySport = {}; yearAll.forEach(t => bySport[t.sport] = (bySport[t.sport] || 0) + t.km);
  const sports = Object.entries(bySport).sort((a, b) => b[1] - a[1]), tot = sum(yearAll, t => t.km) || 1;
  const hy = Y || ys[0], byDay = {}; A.filter(t => t.y === hy).forEach(t => { const k = t.date.slice(0, 10); byDay[k] = (byDay[k] || 0) + t.km; });
  const cum = yr => { let c = 0; const pts = [[0, 0]]; A.filter(t => t.y === yr).slice().reverse().forEach(t => { const d = (Date.UTC(yr, t.m - 1, +t.date.slice(8, 10)) - Date.UTC(yr, 0, 1)) / 864e5; c += t.km; pts.push([d, c]); }); return pts; };
  const cy = Y || ys[0], cs = [{pts: cum(cy), color: cssv("--bars"), w: 3.2}]; if (ys.includes(cy - 1)) cs.unshift({pts: cum(cy - 1), color: cssv("--accent2"), dash: 1, w: 2});
  const today = new Date(), md = `${pad2(today.getMonth() + 1)}-${pad2(today.getDate())}`;
  const otd = TOURS.filter(t => t.date.slice(5, 10) === md && t.y !== today.getFullYear());
  const ph = last.photos ? await api(`/api/photos?tour_id=${last.id}&limit=4`) : [];
  $("#main").innerHTML = `
  <section class="hero"><div id="hm"></div><div class="in"><div class="t">
    <div class="k">Letzte Tour, ${sName(last.sport)}</div><h1>${esc(last.name)}</h1><div class="w">${dateL(last.date)}, ${timeS(last.date)} Uhr</div>
    ${ph.length ? `<div class="thumbrow">${ph.map((p, i) => `<img loading="lazy" src="/photo/${p.id}?size=300" data-i="${i}">`).join("")}</div>` : ""}
    <div class="btns"><a class="btn" href="#/tour/${last.id}">Tour ansehen</a>${last.photos ? `<a class="btn alt" style="color:#fff" target="_blank" href="slideshow.html?tour=${last.id}">Diashow</a>` : ""}</div></div>
    <div class="signs"><div class="sign">${nf(last.km, 1)}<small>Kilometer</small></div><div class="sign l">${nf(last.up_m, 0)}<small>Meter aufwärts</small></div><div class="sign">${nf(last.h, 1)}<small>Stunden</small></div></div></div></section>
  <div class="inner">
  <div class="sec"><h2>${Y ? "Das Jahr " + Y : "Alle Touren"}${S ? ", " + sName(S) : ""}</h2><span class="sub">${nf(sel.length, 0)} Touren</span></div>
  <div class="years"><button data-y="0" class="${Y ? "" : "on"}">Gesamt</button>${ys.map(y => `<button data-y="${y}" class="${Y === y ? "on" : ""}">${y}</button>`).join("")}</div>
  <div class="chips" id="sch" style="margin-top:14px"><button class="chip ${S ? "" : "on"}" data-s="">Alle Sportarten</button>${sports.map(([s]) => `<button class="chip ${S === s ? "on" : ""}" data-s="${esc(s)}"><i style="background:${sCol(s)}"></i>${sName(s)}</button>`).join("")}${S && !bySport[S] ? `<button class="chip on" data-s="${esc(S)}"><i style="background:${sCol(S)}"></i>${sName(S)}</button>` : ""}</div>
  <div class="figs">
    <div class="fig"><div class="v">${nf(sel.length, 0)}</div><div class="l">Touren</div>${delta(sel.length, prev.length)}</div>
    <div class="fig"><div class="v">${nf(km, 0)}<span class="u">km</span></div><div class="l">Strecke</div>${delta(km, pk)}</div>
    <div class="fig"><div class="v">${nf(up, 0)}<span class="u">m</span></div><div class="l">Aufstieg</div>${delta(up, sum(prev, t => t.up_m || 0))}</div>
    <div class="fig"><div class="v">${nf(hh, 0)}<span class="u">h</span></div><div class="l">Unterwegs</div>${delta(hh, sum(prev, t => t.h))}</div>
    <div class="fig"><div class="v">${nf(km / (sel.length || 1), 1)}<span class="u">km</span></div><div class="l">pro Tour im Schnitt</div></div></div>
  <div class="grid g2" style="margin-top:44px">
    <div class="panel"><h2>${Y ? "Kilometer pro Monat" : "Kilometer pro Jahr"}</h2>${Y ? barChart(mm, MON, {ghost: pm, ghostLabel: Y - 1}) : barChart(byYear, ys.slice().reverse().map(String), {href: ys.slice().reverse()})}
      <div class="legend">${Y ? `<span><i style="background:var(--yellow);border:1px solid var(--ink)"></i>stärkster Monat</span>${prev.length ? `<span><i style="background:var(--accent2)"></i>${Y - 1}</span>` : ""}` : "<span>Ein Klick auf einen Balken öffnet das Jahr.</span>"}</div></div>
    <div class="panel"><h2>Kilometer im Jahresverlauf</h2>${lineChart(cs)}<div class="legend"><span><i style="background:var(--bars)"></i>${cy}</span>${ys.includes(cy - 1) ? `<span><i style="background:var(--accent2)"></i>${cy - 1}</span>` : ""}</div></div>
    <div class="panel"><h2>Sportarten</h2><div class="stack">${sports.map(([s, v]) => `<div style="width:${v / tot * 100}%;background:${sCol(s)}" title="${sName(s)}"></div>`).join("")}</div>
      <div class="rows" style="margin-top:10px">${sports.map(([s, v]) => `<div class="r"><span><i class="sw" style="background:${sCol(s)}"></i>${sName(s)}</span><span class="mut">${nf(v, 0)} km, ${nf(v / tot * 100, 0)} %</span></div>`).join("")}</div></div>
    <div class="panel"><h2>Bestwerte ${Y || "gesamt"}</h2><div class="rows">
      ${longest ? `<div class="r"><span><a href="#/tour/${longest.id}">Längste Tour</a><small>${esc(longest.name)}</small></span><b>${nf(longest.km, 1)} km</b></div>
      <div class="r"><span><a href="#/tour/${steepest.id}">Meiste Höhenmeter</a><small>${esc(steepest.name)}</small></span><b>${nf(steepest.up_m, 0)} m</b></div>
      <div class="r"><span><a href="#/tour/${longT.id}">Längste Dauer</a><small>${esc(longT.name)}</small></span><b>${nf(longT.h, 1)} h</b></div>
      <div class="r"><span>Stärkster Monat<small>${MONL[bestM]}</small></span><b>${nf(mm[bestM], 0)} km</b></div>` : '<div class="mut">Keine Touren</div>'}</div></div></div>
  <div class="panel" style="margin-top:44px"><h2>Aktivität im Jahr ${hy}</h2>${heat(hy, byDay)}</div>
  ${otd.length ? `<div class="sec"><h2>An diesem Tag</h2><span class="sub">in früheren Jahren</span></div><div class="tl">${otd.map(tourRow).join("")}</div>` : ""}
  <div class="sec" id="memh"><h2>Erinnerungen</h2><span class="sub" id="memsub"></span></div><div id="mem" class="thumbs"></div></div>`;
  $(".years").onclick = e => { const y = e.target.dataset.y; if (y !== undefined) location.hash = dh(+y, S); };
  $("#sch").onclick = e => { const b = e.target.closest("[data-s]"); if (b) location.hash = dh(Y, b.dataset.s); };
  document.querySelectorAll("rect[data-h]").forEach(r => r.onclick = () => location.hash = dh(+r.dataset.h, S));
  bindThumbs($(".thumbrow") || document.createElement("div"), ph);
  map = mkMap("hm", {zoom: false, attr: false, leaflet: {dragging: false, scrollWheelZoom: false, doubleClickZoom: false, touchZoom: false, boxZoom: false, keyboard: false}});
  map.setView([last.lat || 50, last.lng || 8], 12);
  api(`/api/tours/${last.id}/coords`).then(c => { const l = L.polyline(cleanPts(c).map(p => [p[0], p[1]]), {color: "#f2c230", weight: 5}).addTo(map); map.fitBounds(l.getBounds(), {paddingTopLeft: [window.innerWidth > 900 ? 640 : 40, 40], paddingBottomRight: [40, 40]}); }).catch(() => {});
  try {
    const r = await api("/api/photos?random=true&limit=8");
    if (r.length) { $("#mem").innerHTML = r.map((p, i) => `<img loading="lazy" src="/photo/${p.id}?size=400" data-i="${i}" title="${esc(p.tour_name || "")}">`).join(""); $("#memsub").innerHTML = `<a target="_blank" href="slideshow.html?random=1">Zufalls-Diashow starten</a>`; bindThumbs($("#mem"), r); }
    else { $("#memh").remove(); $("#mem").remove(); }
  } catch (e) {}
};
function tourRow(t) {
  return `<a class="tr" href="#/tour/${t.id}">${miniRoute(t.id, t.sport)}<span><div class="nm">${esc(t.name)}</div><div class="s"><span>${dateS(t.date)}, ${timeS(t.date)}</span><span><i style="background:${sCol(t.sport)}"></i>${sName(t.sport)}</span>${t.photos ? `<span>${t.photos} Fotos</span>` : ""}</div></span>
  <span class="n"><span>${nf(t.km, 1)}<small>km</small></span><span>${nf(t.up_m, 0)}<small>m auf</small></span><span>${nf(t.h, 1)}<small>Std.</small></span></span></a>`;
}

/* ---------- Gesamtkarte ---------- */
VIEWS.map = async () => {
  const routes = await loadRoutes(), ys = years(), sp = [...new Set(TOURS.map(t => t.sport))];
  $("#main").className = "wide";
  $("#main").innerHTML = `<div class="mapbox"><div id="bigmap"></div><div class="mapui">
    <div class="box"><select id="my"><option value="0">Alle Jahre</option>${ys.map(y => `<option>${y}</option>`).join("")}</select><span id="mc" class="cnt"></span></div>
    <div class="box" id="ms">${sp.map(s => `<button class="chip on" data-s="${s}"><i style="background:${sCol(s)}"></i>${sName(s)}</button>`).join("")}</div><div class="box" id="mn" style="display:none"></div></div></div>`;
  map = mkMap("bigmap", {layers: true, leaflet: {preferCanvas: true}});
  const grp = L.layerGroup().addTo(map), off = new Set(), FULL = window._full || (window._full = {}), lines = {}, casings = {}, busy = new Set();
  let shown = [];
  const popup = t => `<b>${esc(t.name)}</b><br>${dateS(t.date)}, ${nf(t.km, 1)} km, ${nf(t.up_m, 0)} m auf<br><a href="#/tour/${t.id}">Tour öffnen</a>`;
  const line = (t, pts) => { if (lines[t.id]) grp.removeLayer(lines[t.id]); if (casings[t.id]) { grp.removeLayer(casings[t.id]); delete casings[t.id]; }
    if (TS.casing) { casePane(map); casings[t.id] = L.polyline(pts, {pane: "casing", color: "#fff", weight: TS.weight + 3, opacity: .9, interactive: false}).addTo(grp); }
    const l = L.polyline(pts, trackStyle(t)).addTo(grp); l.bindPopup(popup(t)); lines[t.id] = l;
    l.on("mouseover", () => l.setStyle({weight: TS.weight + 3, opacity: 1})); l.on("mouseout", () => l.setStyle(trackStyle(t))); };
  const draw = () => {
    grp.clearLayers(); for (const k in lines) delete lines[k]; for (const k in casings) delete casings[k]; shown = []; const y = +$("#my").value; let n = 0, b = null;
    TOURS.forEach(t => { if ((y && t.y !== y) || off.has(t.sport)) return;
      const r = cleanPts(FULL[t.id] || routes[t.id]), st = r.length ? [r[0][0], r[0][1]] : (okPt([t.lat, t.lng]) ? [t.lat, t.lng] : null); if (!st) return; n++; shown.push({t, st});
      L.circleMarker(st, {radius: 5, color: "#fff", weight: 1.5, fillColor: sCol(t.sport), fillOpacity: .95}).addTo(grp).bindPopup(popup(t));
      b = b ? b.extend(L.latLng(st)) : L.latLngBounds([st, st]);
      if (r.length > 1) line(t, r.map(p => [p[0], p[1]])); });
    $("#mc").textContent = `${n} Touren`; return b;
  };
  // Beim Hineinzoomen: fehlende bzw. grob vereinfachte Strecken der sichtbaren Touren in voller Genauigkeit nachladen
  const detail = async () => {
    if (!map || !$("#mn") || map.getZoom() < 11) { $("#mn").style.display = "none"; return; }
    const bd = map.getBounds().pad(.1), c = map.getCenter();
    const need = shown.filter(x => bd.contains(x.st) && !FULL[x.t.id] && !busy.has(x.t.id)).sort((a, z) => map.distance(c, a.st) - map.distance(c, z.st)).slice(0, 30);
    if (!need.length) { $("#mn").style.display = "none"; return; }
    let done = 0, fail = 0; $("#mn").style.display = ""; $("#mn").textContent = `Strecken werden geladen (${need.length}) …`;
    const q = need.slice(); need.forEach(x => busy.add(x.t.id));
    await Promise.all([0, 1, 2, 3].map(async () => { while (q.length) { const x = q.shift();
      try { const pts = cleanPts(await api(`/api/tours/${x.t.id}/coords`)); if (pts.length < 2) throw new Error("leer"); FULL[x.t.id] = pts; line(x.t, pts.map(p => [p[0], p[1]])); } catch (e) { fail++; FULL[x.t.id] = null; delete FULL[x.t.id]; }
      done++; busy.delete(x.t.id); $("#mn").textContent = `Strecken werden geladen (${done}/${need.length}) …`; } }));
    if (fail) { $("#mn").textContent = `${fail} Strecken nicht lokal vorhanden – in der Verwaltung „Routen laden“ (Komoot-Zugang nötig)`; need.forEach(x => busy.add(x.t.id)); } else $("#mn").style.display = "none";
  };
  document.querySelector(".mapui").insertAdjacentHTML("beforeend", `<div class="box" style="position:relative"><button class="chip" id="mtc" title="Farbe und Breite der Strecken ändern">🎨 Strecken</button></div>`);
  $("#mtc").onclick = e => { if (document.querySelector(".tpanel")) { document.querySelector(".tpanel").remove(); return; } trackPanel(e.target, () => { draw(); }); };
  let tm; map.on("moveend", () => { clearTimeout(tm); tm = setTimeout(detail, 350); });
  map.on("zoomend", () => { const z = map.getZoom(); grp.eachLayer(l => { if (l.setRadius) l.setRadius(z < 9 ? 6 : z < 12 ? 5 : 4); }); });
  $("#my").onchange = () => { const b = draw(); if (b) map.fitBounds(b, {padding: [40, 40]}); };
  $("#ms").onclick = e => { const s = e.target.closest("[data-s]"); if (!s) return; s.classList.toggle("on"); off.has(s.dataset.s) ? off.delete(s.dataset.s) : off.add(s.dataset.s); const b = draw(); if (b) map.fitBounds(b, {padding: [40, 40]}); };
  map.setView([50.5, 9], 6); const b0 = draw(); if (b0) map.fitBounds(b0, {padding: [40, 40]});
  if (!Object.keys(routes).length) $("#mc").textContent += " (Strecken werden beim Hineinzoomen nachgeladen)";
};

/* ---------- Tourenliste ---------- */
VIEWS.tours = async () => {
  await loadRoutes().catch(() => {});
  const ys = years(), sp = [...new Set(TOURS.map(t => t.sport))];
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Alle Touren</h2><span class="sub" id="cnt"></span></div>
   <div class="filters"><input id="q" placeholder="Name suchen" style="min-width:230px"><select id="fy"><option value="0">Alle Jahre</option>${ys.map(y => `<option>${y}</option>`).join("")}</select>
   <select id="fs"><option value="">Alle Sportarten</option>${sp.map(s => `<option value="${s}">${sName(s)}</option>`).join("")}</select>
   <select id="fr" title="Region"><option value="">Alle Regionen</option>${regionOpts()}</select>
   <select id="ft" title="Tag / Album"><option value="">Alle Tags</option>${allTags().map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join("")}</select>
   <select id="so"><option value="date">Neueste zuerst</option><option value="old">Älteste zuerst</option><option value="km">Längste Strecke</option><option value="up">Meiste Höhenmeter</option><option value="h">Längste Dauer</option></select></div>
   <div class="tl" id="tl"></div><div class="row" style="justify-content:center;margin-top:20px"><button class="btn ghost" id="more">Mehr anzeigen</button></div>`;
  let lim = 80;
  const KEY = "tf", ld = () => { try { return JSON.parse(sessionStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
  const sv = () => { try { sessionStorage.setItem(KEY, JSON.stringify({q: $("#q").value, fy: $("#fy").value, fs: $("#fs").value, fr: $("#fr").value, ft: $("#ft").value, so: $("#so").value, lim})); } catch (e) {} };
  const f0 = ld(); ["q", "fy", "fs", "fr", "ft", "so"].forEach(i => { if (f0[i] !== undefined) $("#" + i).value = f0[i]; }); if (f0.lim) lim = f0.lim;
  const draw = () => {
    sv();
    const q = $("#q").value.toLowerCase(), y = +$("#fy").value, s = $("#fs").value, so = $("#so").value, rg = $("#fr").value, tg = $("#ft").value;
    let a = TOURS.filter(t => (!y || t.y === y) && (!s || t.sport === s) && inRegion(t, rg) && (!tg || (t.tags || "").split("|").includes(tg)) && (!q || t.name.toLowerCase().includes(q)));
    const k = {date: t => -t.start_ts, old: t => t.start_ts, km: t => -t.km, up: t => -(t.up_m || 0), h: t => -t.h}[so]; a.sort((x, z) => k(x) - k(z));
    $("#cnt").textContent = `${a.length} Touren, ${nf(a.reduce((c, t) => c + t.km, 0), 0)} km`;
    $("#tl").innerHTML = a.slice(0, lim).map(tourRow).join("") || `<div class="empty">Keine Treffer</div>`; $("#more").style.display = a.length > lim ? "" : "none";
  };
  ["q", "fy", "fs", "fr", "ft", "so"].forEach(i => $("#" + i).oninput = () => { lim = 80; draw(); }); $("#more").onclick = () => { lim += 120; draw(); }; draw();
  try { const y = +sessionStorage.getItem("tfy"); if (y) setTimeout(() => window.scrollTo(0, y), 30); sessionStorage.removeItem("tfy"); } catch (e) {}
  $("#tl").onclick = () => { try { sessionStorage.setItem("tfy", window.scrollY); } catch (e) {} };
};

/* ---------- Upload zu Portalen ---------- */
const UPST = {uploaded: "hochgeladen", linked: "bei Komoot vorhanden", duplicate: "dort schon vorhanden", pending: "wird verarbeitet", error: "Fehler"};
async function uploadChips(t) {
  const box = $("#upst"); if (!box) return;
  const st = await api(`/api/tours/${encodeURIComponent(t.id)}/uploads`).catch(() => ({}));
  const nm = {komoot: "Komoot", strava: "Strava"};
  box.innerHTML = Object.entries(st).filter(([, v]) => v.status !== "error").map(([k, v]) => `<span class="chip">${v.url ? `<a target="_blank" href="${esc(v.url)}">${nm[k] || k} ↗</a>` : (nm[k] || k)} · ${UPST[v.status] || v.status}</span>`).join(" ");
}
async function uploadDialog(t) {
  let pf, st;
  try { [pf, st] = await Promise.all([api("/api/portals"), api(`/api/tours/${encodeURIComponent(t.id)}/uploads`)]); } catch (e) { return alert(e.message); }
  const m = document.createElement("div"); m.className = "modal";
  const rows = pf.portals.map(p => {
    const fromHere = p.id === "komoot" && t.source !== "local", s = st[p.id], done = s && ["uploaded", "linked", "duplicate", "pending"].includes(s.status);
    const why = fromHere ? "Die Tour stammt von Komoot" : !p.connected ? (p.id === "strava" ? "nicht verbunden (Verwaltung → Portale)" : "Zugang fehlt (Verwaltung)") : done ? (UPST[s.status] + (s.url ? ` – <a target="_blank" href="${esc(s.url)}">öffnen</a>` : "")) : (s && s.status === "error" ? `<span class="bad">letzter Versuch: ${esc(s.msg)}</span>` : "");
    return `<label class="chk" style="display:block;margin:8px 0"><input type="checkbox" class="pp" value="${p.id}" ${fromHere || !p.connected || done ? "disabled" : ""}> <b>${p.name}</b> <span class="mut">${why}</span></label>`;
  }).join("");
  m.innerHTML = `<div class="mbox"><h3>Tour hochladen</h3><p class="mut">„${esc(t.name)}“ wird mit der lokal gespeicherten Strecke zu den gewählten Portalen gesendet. Es passiert nichts ohne dein Häkchen.</p>${rows}<div id="upr" style="margin-top:10px"></div>
    <div style="margin-top:18px;display:flex;gap:8px;justify-content:flex-end"><button class="btn alt" id="ucx">Schließen</button><button class="btn" id="uok">Hochladen</button></div></div>`;
  document.body.appendChild(m);
  const close = () => m.remove(); m.querySelector("#ucx").onclick = close; m.onclick = e => { if (e.target === m) close(); };
  m.querySelector("#uok").onclick = async e => {
    const ps = [...m.querySelectorAll(".pp:checked")].map(c => c.value); if (!ps.length) return;
    e.target.disabled = true; m.querySelector("#upr").innerHTML = '<span class="mut">Wird hochgeladen … (Strava kann bis zu 50 s brauchen)</span>';
    try {
      const r = await api(`/api/tours/${encodeURIComponent(t.id)}/upload`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({portals: ps})});
      m.querySelector("#upr").innerHTML = Object.entries(r).map(([k, v]) => `<div class="${v.status === "error" ? "bad" : "ok"}"><b>${k === "komoot" ? "Komoot" : "Strava"}:</b> ${v.status === "uploaded" ? "hochgeladen ✓" : v.status === "duplicate" ? "dort schon vorhanden" : v.status === "already" ? "schon erledigt" : esc(v.msg || v.status)}${v.url ? ` – <a target="_blank" href="${esc(v.url)}">öffnen</a>` : ""}</div>`).join("");
    } catch (er) { m.querySelector("#upr").innerHTML = `<span class="bad">${esc(er.message)}</span>`; }
    e.target.disabled = false; uploadChips(t);
  };
}

/* ---------- Tourdetail ---------- */
VIEWS.tour = async id => {
  const t = BY[id]; if (!t) throw new Error("Tour nicht gefunden");
  const i = TOURS.indexOf(t), nx = TOURS[i - 1], pv = TOURS[i + 1];
  $("#main").innerHTML = `<div class="row"><a class="back" href="#/tours">‹ Alle Touren</a><span class="sp"></span>${pv ? `<a class="btn ghost sm" href="#/tour/${pv.id}">Vorherige</a>` : ""}${nx ? `<a class="btn ghost sm" href="#/tour/${nx.id}">Nächste</a>` : ""}</div>
   <div style="margin-top:18px"><span class="tag" style="background:${sCol(t.sport)}">${sName(t.sport)}</span> <span class="mut" style="margin-left:8px">${dateL(t.date)}, ${timeS(t.date)} Uhr</span>${t.g_country ? `<span class="mut" style="margin-left:8px">· ${esc([t.g_place, t.g_state, t.g_country].filter(Boolean).join(", "))}</span>` : ""}</div>
   <h1 style="font-size:clamp(34px,5vw,56px);margin:10px 0 18px"><span id="tname">${esc(t.name)}</span> <button class="btn ghost sm" id="ren" title="Tour umbenennen" style="vertical-align:middle;font-size:15px">✎ Umbenennen</button></h1>
   <div class="row" style="margin:-6px 0 14px">${t.source === "local" ? `<span class="tag" style="background:var(--yellow);color:#000" title="Diese Tour liegt nur lokal vor (Strecke als GPX im Datenordner)">lokal gespeichert</span>` : `<button class="btn ghost sm" id="ksync" title="Daten und GPS-Track neu von Komoot laden">⟳ Mit Komoot abgleichen</button>`}<button class="btn ghost sm" id="eup" title="Zu Komoot, Strava … hochladen">⬆ Hochladen</button><a class="btn ghost sm" id="egpx" href="/api/tours/${encodeURIComponent(t.id)}/gpx" title="Strecke als GPX-Datei herunterladen">⬇ GPX</a>${t.source === "local" ? `<button class="btn ghost sm" id="edel" title="Lokale Tour löschen">🗑 Löschen</button>` : ""}<button class="btn ghost sm" id="etag" title="Schlagworte / Alben">🏷 Tags</button><button class="btn ghost sm" id="eshr" title="Öffentlichen Link erzeugen">🔗 Teilen</button><button class="btn ghost sm" id="etc" title="Farbe und Breite der Strecke">🎨 Streckenfarbe</button><button class="btn ghost sm" id="efix" title="Höhen mit Geländemodell neu berechnen"></button><span id="ksm" class="mut" style="font-size:14px"></span></div><div id="upst" class="chips" style="margin:-4px 0 10px"></div><div id="tagl" class="chips" style="margin:-4px 0 12px"></div><div id="ewarn"></div>
   <div class="figs"><div class="fig"><div class="v">${nf(t.km, 2)}<span class="u">km</span></div><div class="l">Strecke</div></div><div class="fig"><div class="v">${nf(t.up_m, 0)}<span class="u">m</span></div><div class="l">Aufstieg</div></div>
   <div class="fig"><div class="v">${nf(t.down_m, 0)}<span class="u">m</span></div><div class="l">Abstieg</div></div><div class="fig"><div class="v">${Math.floor(t.h)}:${pad2(Math.round(t.h % 1 * 60))}<span class="u">Std.</span></div><div class="l">Dauer</div></div>
   <div class="fig"><div class="v">${t.h ? nf(t.km / t.h, 1) : "–"}<span class="u">km/h</span></div><div class="l">Tempo im Schnitt</div></div><div id="kmax" class="fig" style="display:none"><div class="v" id="kmaxv"></div><div class="l">Höchster Punkt</div></div></div>
   <div class="tmap" id="tm"></div>
   <div class="panel prof" style="margin-top:34px" id="profcard"><h2>Höhenprofil</h2><div id="prof" class="mut">Wird geladen …</div></div>
   <div class="sec"><h2>Fotos</h2><span class="sub" id="pc"></span><span class="sp"></span><a class="btn sm" id="ss" style="display:none" target="_blank">Diashow</a></div><div class="thumbs" id="th"></div>
   ${t.source === "local" ? "" : `<p style="margin-top:30px"><a class="back" target="_blank" href="https://www.komoot.com/tour/${t.id}">In Komoot öffnen</a></p>`}`;
  map = mkMap("tm", {layers: true});
  map.setView([t.lat || 50, t.lng || 8], 12);
  let tl = null, cl = null, tseg = null, tcc = [], tleg = null;
  const paintBy = () => {
    if (tseg) { map.removeLayer(tseg); tseg = null; } if (tleg) { tleg.remove(); tleg = null; }
    if (!tl) return; const on = TS.by !== "none" && tcc.length > 8; tl.setStyle({opacity: on ? 0 : .92}); if (!on) return;
    const n = tcc.length, d = [0]; for (let i = 1; i < n; i++) d.push(d[i - 1] + hav(tcc[i - 1], tcc[i]));
    const w = 3, val = i => { const a = Math.max(0, i - w), b = Math.min(n - 1, i + w + 1), dd = d[b] - d[a] || 1;
      if (TS.by === "grade") return tcc[a][2] != null && tcc[b][2] != null ? (tcc[b][2] - tcc[a][2]) / dd * 100 : 0;
      return tcc[a][3] != null && tcc[b][3] != null && tcc[b][3] > tcc[a][3] ? dd / ((tcc[b][3] - tcc[a][3]) / 1000) * 3.6 : null; };
    const v = tcc.slice(0, n - 1).map((_, i) => val(i)), s = v.filter(x => x != null).sort((a, b) => a - b);
    const q = f => s.length ? s[Math.min(s.length - 1, Math.floor(f * s.length))] : 0, cuts = [q(.2), q(.4), q(.6), q(.8)], SC = ["#2b6cb0", "#63b3ed", "#68d391", "#f6ad55", "#e53e3e"];
    const col = x => TS.by === "grade" ? grCol(x) : x == null ? "#999" : SC[cuts.filter(c => x >= c).length];
    tseg = L.layerGroup(v.map((x, i) => L.polyline([[tcc[i][0], tcc[i][1]], [tcc[i + 1][0], tcc[i + 1][1]]], {color: col(x), weight: TS.weight + 1, opacity: .95, lineCap: "butt"}).bindTooltip(x == null ? "–" : TS.by === "grade" ? `${nf(x, 0)} % Steigung` : `${nf(x, 1)} km/h`))).addTo(map);
    tleg = document.createElement("div"); tleg.className = "tleg";
    tleg.innerHTML = TS.by === "grade" ? GR.map(g => `<span><i style="background:${g[2]}"></i>${g[3]}</span>`).join("") : SC.map((c, i) => `<span><i style="background:${c}"></i>${i === 0 ? "langsam" : i === 4 ? "schnell" : ""}</span>`).join("");
    document.getElementById("tm").appendChild(tleg);
  };
  const mk = api(`/api/tours/${t.id}/coords`).then(c => {
    const ll = cleanPts(c).map(p => [p[0], p[1]]), l = L.polyline(ll, {...trackStyle(t, TS.weight + 1)}).addTo(map); tl = l; if (TS.casing) { casePane(map); cl = L.polyline(ll, {pane: "casing", color: "#fff", weight: TS.weight + 4, opacity: .9, interactive: false}).addTo(map); } tcc = cleanPts(c); paintBy(); map.fitBounds(l.getBounds(), {padding: [30, 30]});
    L.circleMarker(ll[0], {radius: 7, color: "#fff", fillColor: "#2f8f5f", fillOpacity: 1, weight: 2}).addTo(map).bindTooltip("Start");
    L.circleMarker(ll[ll.length - 1], {radius: 7, color: "#fff", fillColor: "#c0504d", fillOpacity: 1, weight: 2}).addTo(map).bindTooltip("Ziel");
    profile(c, t); return c;
  }).catch(e => { $("#profcard").style.display = "none"; return null; });
  const ph = await api(`/api/photos?tour_id=${t.id}&limit=400`);
  $("#pc").textContent = ph.length ? `${ph.length} Fotos` : "Zu dieser Tour gibt es noch keine Fotos.";
  if (ph.length) { $("#ss").style.display = ""; $("#ss").href = `slideshow.html?tour=${t.id}`; }
  $("#th").innerHTML = ph.map((p, k) => `<div class="th"><img loading="lazy" src="/photo/${p.id}?size=500" data-i="${k}"><span class="cap">${new Date(p.taken_ts * 1000).toLocaleString("de-DE", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"})}${p.manual === 1 ? " 📌" : ""}</span></div>`).join(""); bindThumbs($("#th"), ph);
  if (ph.length) photoSelect(ph, 0, {box: "#th", anchor: "#pc", tour: true});
  mk.then(c => { if (!c || !ph.length || (!c[0][3] && c[0][3] !== 0)) return;
    ph.forEach(p => { const rel = (p.taken_ts - t.start_ts) * 1000; let b = c[0], bd = 1e18; c.forEach(q => { const d = Math.abs((q[3] || 0) - rel); if (d < bd) { bd = d; b = q; } });
      const ic = L.divIcon({className: "", html: `<div class="pm" style="background-image:url(/photo/${p.id}?size=120)"></div>`, iconSize: [36, 36]});
      L.marker([b[0], b[1]], {icon: ic}).addTo(map).on("click", () => openLb(ph, ph.indexOf(p))); }); });
  $("#eup").onclick = () => uploadDialog(t); uploadChips(t);
  if ($("#edel")) $("#edel").onclick = async () => { if (!confirm(`Lokale Tour „${t.name}“ samt gespeicherter Strecke löschen? Bereits hochgeladene Kopien bei Komoot/Strava bleiben bestehen.`)) return; try { await api(`/api/tours/${encodeURIComponent(t.id)}`, {method: "DELETE"}); ROUTES = null; await loadTours(); location.hash = "#/tours"; } catch (e) { alert(e.message); } };
  if ($("#ksync")) $("#ksync").onclick = async () => {
    const o = t.km; $("#ksync").disabled = true; $("#ksm").textContent = "Lade von Komoot …";
    try {
      await api(`/api/tours/${encodeURIComponent(t.id)}/sync`, {method: "POST"});
      ROUTES = null; window._full = {}; await loadTours(); const n = BY[t.id];
      await route(); const m = $("#ksm"); if (m) m.textContent = `Abgeglichen: ${nf(o, 2)} km → ${nf(n.km, 2)} km`;
    } catch (e) { $("#ksync").disabled = false; $("#ksm").innerHTML = `<span class="bad">${esc(e.message)}</span>`; }
  };
  (() => {
    const b = $("#efix"), w = $("#ewarn"), fixed = t.fix_up != null, sus = !fixed && t.km > 0.5 && (t.up_m || 0) > 120 * t.km && t.up_m > 400;
    b.textContent = fixed ? "⛰ Höhenkorrektur zurücknehmen" : "⛰ Höhen korrigieren";
    if (fixed) w.innerHTML = `<div class="panel" style="margin-bottom:14px;padding:12px 16px">Höhen mit Geländemodell korrigiert (Komoot/GPS meldete ${nf(t.fix_up, 0)} m Aufstieg).</div>`;
    else if (sus) w.innerHTML = `<div class="panel" style="margin-bottom:14px;padding:12px 16px;border-left:4px solid var(--yellow)"><b>Auffällige Höhendaten:</b> ${nf(t.up_m, 0)} m Aufstieg auf ${nf(t.km, 1)} km sind unwahrscheinlich. Mit „Höhen korrigieren“ werden sie aus dem Geländemodell berechnet.</div>`;
    b.onclick = async () => {
      b.disabled = true; $("#ksm").textContent = fixed ? "Stelle Original wieder her …" : "Berechne Höhen aus Geländedaten …";
      try {
        if (fixed) await api(`/api/tours/${encodeURIComponent(t.id)}/elev-restore`, {method: "POST"});
        else {
          const r = await api(`/api/tours/${encodeURIComponent(t.id)}/elev-fix`, {method: "POST"});
          if (!confirm(`Neu berechnet: ${nf(r.up_m, 0)} m Aufstieg, ${nf(r.down_m, 0)} m Abstieg (vorher ${nf(r.orig_up, 0)} m / ${nf(r.orig_down, 0)} m).\n\nOK = übernehmen, Abbrechen = Original behalten`)) await api(`/api/tours/${encodeURIComponent(t.id)}/elev-restore`, {method: "POST"});
        }
        await loadTours(); location.reload();
      } catch (e) { b.disabled = false; $("#ksm").textContent = ""; alert("Höhenkorrektur fehlgeschlagen: " + e.message); }
    };
  })();
  $("#etc").onclick = e => { if (document.querySelector(".tpanel")) { document.querySelector(".tpanel").remove(); return; }
    trackPanel(e.target, () => { if (!tl) return; tl.setStyle(trackStyle(t, TS.weight + 1)); paintBy(); if (cl) { map.removeLayer(cl); cl = null; } if (TS.casing) { casePane(map); cl = L.polyline(tl.getLatLngs(), {pane: "casing", color: "#fff", weight: TS.weight + 4, opacity: .9, interactive: false}).addTo(map); } }, true); };
  $("#ren").onclick = () => {
    const m = document.createElement("div"); m.className = "modal";
    m.innerHTML = `<div class="mbox"><h3>Tour umbenennen</h3>
      <input id="rnn" type="text" style="width:100%" maxlength="200">
      <div style="margin-top:12px"><b>Vorschläge aus den Kartendaten</b></div>
      <div id="rsg" class="chips" style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px"><span class="mut">Suche Orte und Gipfel …</span></div>
      ${t.source === "local" ? "" : '<label class="chk"><input type="checkbox" id="rkom"> auch bei Komoot umbenennen</label>'}
      <div style="margin-top:18px;display:flex;gap:8px;justify-content:flex-end"><button class="btn alt" id="rcx">Abbrechen</button><button class="btn" id="rok">Umbenennen</button></div></div>`;
    document.body.appendChild(m);
    const inp = m.querySelector("#rnn"); inp.value = t.name; inp.focus(); inp.select();
    const close = () => m.remove();
    m.querySelector("#rcx").onclick = close; m.onclick = e => { if (e.target === m) close(); };
    const box = m.querySelector("#rsg"); let pend = 4, got = 0, fail = 0; const have = new Set();
    const add = (list, front) => list.forEach(x => { if (have.has(x) || x === t.name || !box.isConnected) return; have.add(x); got++;
      const b = document.createElement("button"); b.className = "btn alt"; b.type = "button"; b.textContent = x; b.onclick = () => { inp.value = x; inp.focus(); };
      if (front) box.querySelector(".mut")?.remove(), box.prepend(b); else { box.querySelector(".mut")?.remove(); box.appendChild(b); } });
    const done = () => { if (--pend || !box.isConnected) return; if (!got) box.innerHTML = `<span class="mut">${fail ? "Keine Vorschläge möglich (Internetzugang des Servers prüfen)." : "Keine Vorschläge gefunden."}</span>`; };
    ["places", "peak", "trails", "guides"].forEach(p => api(`/api/tours/${encodeURIComponent(t.id)}/name-suggestions?part=${p}`)
      .then(r => add(r.suggestions, p === "trails" || p === "guides")).catch(() => { fail++; }).finally(done));
    inp.onkeydown = e => { if (e.key === "Enter") m.querySelector("#rok").click(); if (e.key === "Escape") close(); };
    m.querySelector("#rok").onclick = async () => {
      const nn = inp.value.trim(), kom = !!(m.querySelector("#rkom") && m.querySelector("#rkom").checked);
      if (!nn || nn === t.name) { close(); return; }
      try {
        const r = await api(`/api/tours/${encodeURIComponent(t.id)}/rename`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({name: nn, komoot: kom})});
        t.name = nn; $("#tname").textContent = t.name; close();
        if (kom && !r.komoot) alert("Hier umbenannt, aber bei Komoot hat es nicht geklappt:\n" + r.warning);
      } catch (e) { alert("Umbenennen fehlgeschlagen: " + e.message); }
    };
  };
};
function profile(c, t) {
  const alts = c.map(p => p[2]).filter(v => v != null); if (alts.length < 3) { $("#profcard").style.display = "none"; return; }
  const R = 6371000, rad = Math.PI / 180, dist = [0];
  for (let i = 1; i < c.length; i++) { const a = c[i - 1], b = c[i], dl = (b[0] - a[0]) * rad, dn = (b[1] - a[1]) * rad, h = Math.sin(dl / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dn / 2) ** 2; dist.push(dist[i - 1] + 2 * R * Math.asin(Math.sqrt(h))); }
  const W = 800, H = 200, L0 = 42, B = 22, T = 8, mn = Math.min(...alts), mxA = Math.max(...alts), span = Math.max(20, mxA - mn), lo = mn - span * .08, hi = mxA + span * .08, D = dist[dist.length - 1] || 1;
  const x = d => L0 + (W - L0 - 6) * d / D, y = a => T + (H - T - B) * (1 - (a - lo) / (hi - lo));
  const pts = c.map((p, i) => [x(dist[i]), y(p[2] ?? lo)]), line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");
  let g = ""; [lo + (hi - lo) * .05, (lo + hi) / 2, hi - (hi - lo) * .05].forEach(v => g += `<line x1="${L0}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)"/><text x="${L0 - 6}" y="${y(v) + 4}" text-anchor="end">${nf(v, 0)} m</text>`);
  for (let k = 0; k <= 4; k++) g += `<text x="${x(D * k / 4)}" y="${H - 6}" text-anchor="${k === 4 ? "end" : k === 0 ? "start" : "middle"}">${nf(D * k / 4000, 1)} km</text>`;
  $("#prof").className = ""; $("#prof").innerHTML = `<svg viewBox="0 0 ${W} ${H}" id="psvg">${g}<path d="${line}L${x(D)},${H - B}L${L0},${H - B}Z" fill="${sCol(t.sport)}" opacity=".22"/><path d="${line}" fill="none" stroke="${sCol(t.sport)}" stroke-width="2.4"/><line id="pl" y1="${T}" y2="${H - B}" stroke="var(--ink)" opacity="0" /></svg><div class="tip" id="ptip" style="display:none"></div>`;
  $("#kmax").style.display = ""; $("#kmaxv").innerHTML = `${nf(mxA, 0)}<span class="u">m</span>`;
  let mkr = null; const svg = $("#psvg");
  svg.onmousemove = svg.ontouchmove = e => { const r = svg.getBoundingClientRect(), cx = (e.touches ? e.touches[0].clientX : e.clientX), fx = (cx - r.left) / r.width * W; if (fx < L0) return;
    const d = (fx - L0) / (W - L0 - 6) * D; let k = dist.findIndex(v => v >= d); if (k < 0) k = dist.length - 1;
    $("#pl").setAttribute("x1", pts[k][0]); $("#pl").setAttribute("x2", pts[k][0]); $("#pl").setAttribute("opacity", .5);
    const tp = $("#ptip"); tp.style.display = ""; tp.style.left = (pts[k][0] / W * r.width) + "px"; tp.style.top = (pts[k][1] / H * r.height + 34) + "px"; tp.textContent = `${nf(dist[k] / 1000, 2)} km · ${nf(c[k][2], 0)} m`;
    if (map) { if (!mkr) mkr = L.circleMarker([c[k][0], c[k][1]], {radius: 8, color: "#fff", fillColor: "#e2b13c", fillOpacity: 1, weight: 3}).addTo(map); else mkr.setLatLng([c[k][0], c[k][1]]); } };
  svg.onmouseleave = () => { $("#ptip").style.display = "none"; $("#pl").setAttribute("opacity", 0); if (mkr && map) { map.removeLayer(mkr); mkr = null; } };
}

/* ---------- Fotos ---------- */
let PH_LIST = [], LB_I = 0;
function openLb(list, i) { PH_LIST = list; LB_I = i; showLb(); $("#lb").classList.add("on"); }
function showLb() { const p = PH_LIST[LB_I]; if (!p) return; $("#lbi").src = p.src || `/photo/${p.id}?size=2000`; $("#lbc").textContent = `${p.tour_name ? p.tour_name + " · " : ""}${new Date(p.taken_ts * 1000).toLocaleString("de-DE", {dateStyle: "long", timeStyle: "short"})} · ${LB_I + 1}/${PH_LIST.length}`; }
function bindThumbs(box, list) { box.querySelectorAll("img[data-i]").forEach(im => im.onclick = () => openLb(list, +im.dataset.i)); }
$("#lb").onclick = e => { const a = e.target.dataset.a; if (a === "next") { LB_I = (LB_I + 1) % PH_LIST.length; showLb(); } else if (a === "prev") { LB_I = (LB_I - 1 + PH_LIST.length) % PH_LIST.length; showLb(); } else if (a === "close" || e.target.id === "lb") $("#lb").classList.remove("on"); };
addEventListener("keydown", e => { if (!$("#lb").classList.contains("on")) return; if (e.key === "Escape") $("#lb").classList.remove("on"); if (e.key === "ArrowRight") { LB_I = (LB_I + 1) % PH_LIST.length; showLb(); } if (e.key === "ArrowLeft") { LB_I = (LB_I - 1 + PH_LIST.length) % PH_LIST.length; showLb(); } });

VIEWS.photos = async (_, q) => {
  PHINFO = await api("/api/photo-info");
  if (!PHINFO.count) { $("#main").innerHTML = `<div class="empty"><h2>Noch keine Fotos</h2><p>Lade unter <a href="#/admin"><b>Verwaltung, Fotos</b></a> einen Ordner mit Bildern hoch.</p></div>`; return; }
  const Y = +(q.get("y") || PHINFO.years[0]);
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Fotos</h2><span class="sub">${nf(PHINFO.count, 0)} Bilder, ${nf(PHINFO.assigned, 0)} einer Tour zugeordnet</span><span class="sp"></span><a class="btn" target="_blank" href="slideshow.html?year=${Y}">Diashow ${Y}</a><a class="btn ghost" target="_blank" href="slideshow.html?random=1">Zufall</a></div>
   <div class="years">${PHINFO.years.map(y => `<button data-y="${y}" class="${y === Y ? "on" : ""}">${y}</button>`).join("")}</div><div id="pg" style="margin-top:26px"></div>`;
  $(".years").onclick = e => e.target.dataset.y && (location.hash = `#/photos?y=${e.target.dataset.y}`);
  const ph = await api(`/api/photos?year=${Y}&limit=4000`); PH_LIST = ph;
  const groups = new Map(); ph.forEach(p => { const k = p.tour_id || "-"; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(p); });
  $("#pg").innerHTML = [...groups.entries()].map(([k, a]) => { const t = BY[k]; return `<div class="pgroup"><div class="ph"><h3>${t ? `<a href="#/tour/${k}">${esc(t.name)}</a>` : "Ohne Tour"}</h3><span>${t ? dateL(t.date) : new Date(a[0].taken_ts * 1000).toLocaleDateString("de-DE")}, ${a.length} Fotos</span><span class="sp"></span>${t ? `<a class="btn ghost sm" target="_blank" href="slideshow.html?tour=${k}">Diashow</a>` : ""}</div>
    <div class="thumbs">${a.map(p => `<div class="th"><img loading="lazy" src="/photo/${p.id}?size=400" data-i="${ph.indexOf(p)}"><span class="cap">${new Date(p.taken_ts * 1000).toLocaleString("de-DE", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"})}${p.manual === 1 ? " 📌" : ""}</span></div>`).join("")}</div></div>`; }).join("");
  bindThumbs($("#pg"), ph); photoSelect(ph, Y);
};

/* ---------- Fotos manuell zuordnen ---------- */
function photoSelect(ph, Y, o = {box: "#pg", anchor: ".sec .sp"}) {
  const BOX = o.box;
  const sel = new Set(); let on = false; document.body.classList.remove("selmode"); document.querySelectorAll(".seltb").forEach(x => x.remove());
  const tb = document.createElement("div"); tb.className = "seltb"; tb.style.display = "none"; document.body.appendChild(tb);
  const btn = document.createElement("button"); btn.className = "btn ghost"; btn.textContent = "Fotos zuordnen"; btn.title = "Fotos auswählen und einer Tour zuordnen";
  $(o.anchor).after(btn); if (o.tour) { btn.textContent = "Fotos bearbeiten"; btn.style.marginLeft = "12px"; }
  const paint = () => {
    document.querySelectorAll(BOX + " img[data-i]").forEach(im => im.classList.toggle("sel", sel.has(ph[+im.dataset.i].id)));
    tb.style.display = on ? "" : "none";
    tb.innerHTML = `<b>${sel.size}</b> ausgewählt <button class="btn sm" data-a="assign" ${sel.size ? "" : "disabled"}>${o.tour ? "Andere Tour …" : "Einer Tour zuordnen …"}</button>${o.tour ? `<button class="btn alt sm" data-a="rm" ${sel.size ? "" : "disabled"}>Aus dieser Tour entfernen</button>` : `<button class="btn alt sm" data-a="un" ${sel.size ? "" : "disabled"}>Zuordnung lösen</button>`}<button class="btn alt sm" data-a="off">Fertig</button>`;
    btn.classList.toggle("on", on);
  };
  btn.onclick = () => { on = !on; if (!on) sel.clear(); document.body.classList.toggle("selmode", on); paint(); };
  $(BOX).addEventListener("click", e => {
    if (!on) return;
    const im = e.target.closest("img[data-i]");
    if (im) { e.stopPropagation(); e.preventDefault(); const p0 = ph[+im.dataset.i], id = p0.id;
      if (!sel.size) { const dk = x => new Date(x.taken_ts * 1000).toLocaleDateString("de-DE"), k = dk(p0); ph.forEach(x => { if (dk(x) === k) sel.add(x.id); }); }  // erstes Foto: alle vom selben Tag vorauswählen
      else sel.has(id) ? sel.delete(id) : sel.add(id);
      paint(); return; }
    const g = e.target.closest("[data-g]");
    if (g) { const grp = g.closest(".pgroup"); const ids = [...grp.querySelectorAll("img[data-i]")].map(i => ph[+i.dataset.i].id); const all = ids.every(i => sel.has(i)); ids.forEach(i => all ? sel.delete(i) : sel.add(i)); paint(); }
  }, true);
  if (!o.tour) document.querySelectorAll("#pg .pgroup .ph").forEach(h => { const b = document.createElement("button"); b.className = "btn ghost sm gsel"; b.dataset.g = "1"; b.textContent = "Gruppe wählen"; h.appendChild(b); });
  tb.onclick = async e => {
    const a = e.target.dataset.a; if (!a) return;
    if (a === "off") return btn.click();
    const ids = [...sel];
    if (a === "rm") {
      if (!confirm(`${ids.length} Foto(s) aus dieser Tour entfernen?\n\nSie werden keiner Tour mehr zugeordnet (auch nicht automatisch) und erscheinen unter „Fotos“ bei „Ohne Tour“.`)) return;
      await api("/api/photo-unassign", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({ids, exclude: true})}); return route();
    }
    if (a === "un") {
      const rs = confirm("Zeitkorrektur dieser Fotos ebenfalls zurücksetzen?\n\nOK = Zuordnung lösen und Zeitkorrektur zurücksetzen\nAbbrechen = nur Zuordnung lösen (danach wieder automatisch nach Zeit)");
      await api("/api/photo-unassign", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({ids, reset_time: rs})}); return route();
    }
    assignDialog(ids.map(i => ph.find(p => p.id === i)), async () => route());
  };
  paint();
}
let assignDialog = function (sp, done) {
  const first = sp.slice().sort((a, b) => a.taken_ts - b.taken_ts)[0];
  const tours = TOURS.slice().sort((a, b) => Math.abs(a.start_ts - first.taken_ts) - Math.abs(b.start_ts - first.taken_ts));
  const m = document.createElement("div"); m.className = "modal";
  m.innerHTML = `<div class="mbox"><h2>${sp.length} Foto${sp.length > 1 ? "s" : ""} zuordnen</h2>
   <div class="field"><label>Tour (nächstgelegene zuerst)</label><select id="at">${tours.map(t => `<option value="${t.id}">${dateS(t.date)} · ${esc(t.name)} (${sName(t.sport)})</option>`).join("")}</select></div>
   <label class="chk"><input type="checkbox" id="as"> Zeit der Fotos anpassen: Das erste gewählte Foto (${new Date(first.taken_ts * 1000).toLocaleString("de-DE")}) wurde</label>
   <div id="aso" style="margin:6px 0 0 24px;display:none"><input id="am" type="number" value="0" step="5" style="width:80px"> Minuten nach dem Start der Tour aufgenommen.
     <div class="field"><label>Zeitversatz anwenden auf</label><select id="asc"><option value="selected">nur die gewählten Fotos</option><option value="day">alle Fotos desselben Aufnahmetags</option><option value="unassigned">alle noch nicht zugeordneten Fotos</option></select></div>
     <div class="mut" id="ap" style="font-size:14px"></div></div>
   <div class="row" style="margin-top:18px"><button class="btn" id="aok">Zuordnen</button><button class="btn alt" id="ano">Abbrechen</button><span id="aer" class="bad"></span></div></div>`;
  document.body.appendChild(m);
  const upd = () => { $("#aso").style.display = $("#as").checked ? "" : "none"; const t = BY[$("#at").value]; const off = Math.round(t.start_ts + (+$("#am").value || 0) * 60 - first.taken_ts); const a = Math.abs(off), h = Math.floor(a / 3600), mi = Math.round(a % 3600 / 60);
    $("#ap").textContent = `Zeitversatz: ${off < 0 ? "−" : "+"}${h > 23 ? Math.floor(h / 24) + " Tage " + (h % 24) : h} Std. ${mi} Min.`; };
  ["at", "as", "am", "asc"].forEach(i => $("#" + i).oninput = upd); upd();
  $("#ano").onclick = () => m.remove();
  $("#aok").onclick = async () => { try { const r = await api("/api/photo-assign", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({ids: sp.map(p => p.id), tour_id: $("#at").value, shift: $("#as").checked, minutes: +$("#am").value || 0, scope: $("#asc").value})}); m.remove(); await done(r); } catch (e) { $("#aer").textContent = e.message; } };
}

/* ---------- Foto-Upload im Browser ---------- */
function exifDate(buf) {  // liest DateTimeOriginal aus dem JPEG-Kopf
  const v = new DataView(buf); if (v.getUint16(0) !== 0xFFD8) return null;
  let o = 2;
  while (o + 4 < v.byteLength) { const m = v.getUint16(o), len = v.getUint16(o + 2);
    if (m === 0xFFE1 && v.getUint32(o + 4) === 0x45786966) { const t = o + 10, le = v.getUint16(t) === 0x4949, g16 = x => v.getUint16(x, le), g32 = x => v.getUint32(x, le);
      const ifd = (off, tag) => { const n = g16(t + off); for (let i = 0; i < n; i++) { const e = t + off + 2 + i * 12; if (g16(e) === tag) return e; } return null; };
      const e1 = ifd(g32(t + 4), 0x8769); if (e1 === null) return null; const e2 = ifd(g32(e1 + 8), 0x9003) ?? ifd(g32(e1 + 8), 0x9004); if (e2 === null) return null;
      const so = t + g32(e2 + 8); let r = ""; for (let i = 0; i < 19; i++) r += String.fromCharCode(v.getUint8(so + i)); return r; }
    if ((m & 0xFF00) !== 0xFF00) break; o += 2 + len; }
  return null;
}
async function folderUpload() {
  const inp = $("#pdir"); if (!inp) return; let stop = false;
  $("#pdirb").onclick = () => inp.click(); $("#pstop").onclick = () => stop = true;
  inp.onchange = async () => {
    const files = [...inp.files].filter(f => /\.(jpe?g|png|webp)$/i.test(f.name) && !f.name.startsWith("."));
    inp.value = ""; if (!files.length) return alert("Im gewählten Ordner wurden keine JPG/PNG-Bilder gefunden.");
    const have = new Set(await api("/api/photo-library"));
    const rel = f => (f.webkitRelativePath || f.name).split("/").slice(1).join("/").replace(/\.[^.]+$/, "") || f.name.replace(/\.[^.]+$/, "");
    const todo = files.filter(f => !have.has(rel(f)));
    if (!confirm(`${files.length} Bilder gefunden, davon ${todo.length} neu. Jetzt verkleinern und hochladen?`)) return;
    $("#pup2").style.display = ""; let done = 0, fail = 0; const mx = +s_max() || 2200, q = (+s_q() || 82) / 100, t0 = Date.now(); stop = false;
    const one = async f => {
      try {
        const head = f.type === "image/jpeg" ? exifDate(await f.slice(0, 262144).arrayBuffer()) : null;
        const d = new Date(f.lastModified), taken = head || `${d.getFullYear()}:${pad2(d.getMonth() + 1)}:${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
        const bmp = await createImageBitmap(f, {imageOrientation: "from-image"}), k = Math.min(1, mx / Math.max(bmp.width, bmp.height));
        const c = document.createElement("canvas"); c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k); c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height); bmp.close();
        const blob = await new Promise(r => c.toBlob(r, "image/jpeg", q)); const fd = new FormData();
        fd.append("file", blob, "x.jpg"); fd.append("rel", rel(f)); fd.append("taken", taken); fd.append("mtime", Math.floor(f.lastModified / 1000));
        await api("/api/photo-upload", {method: "POST", body: fd}); done++;
      } catch (e) { fail++; }
      const n = done + fail, eta = n ? Math.round((Date.now() - t0) / n * (todo.length - n) / 1000) : 0;
      $("#pbar").style.width = (n / todo.length * 100) + "%"; $("#ptxt").textContent = `${n} / ${todo.length}${fail ? ` · ${fail} Fehler` : ""} · noch ca. ${Math.floor(eta / 60)} min`;
    };
    const queue = todo.slice(); await Promise.all([0, 1, 2].map(async () => { while (queue.length && !stop) await one(queue.shift()); }));
    $("#ptxt").textContent = `${stop ? "Abgebrochen" : "Fertig"}: ${done} hochgeladen${fail ? `, ${fail} Fehler` : ""}. Bibliothek wird eingelesen …`;
    await api("/api/jobs/photos", {method: "POST"}).catch(() => {});
  };
}
const s_max = () => document.querySelector('[data-k="photo_max_side"]')?.value, s_q = () => document.querySelector('[data-k="photo_quality"]')?.value;

/* ---------- Verwaltung ---------- */
const STATUS_DE = {local: "lokal übernommen", new: "noch nicht übernommen", in_komoot: "bereits in Komoot", uploaded: "hochgeladen", skipped_dup: "bereits in Komoot", no_gps: "ohne GPS"};
VIEWS.admin = async (_, q) => {
  const [st, w, s, pi, pf] = await Promise.all([api("/api/status"), api("/api/workouts"), api("/api/settings"), api("/api/photo-info"), api("/api/portals")]);
  const sv = (pf.portals.find(x => x.id === "strava") || {}), sres = q && q.get("strava");
  const pend = w.filter(x => x.status === "new");
  const f = (k, l, t = "text", ph = "") => `<div class="field"><label>${l}</label><input data-k="${k}" type="${t}" value="${esc(s[k])}" placeholder="${ph}"></div>`;
  $("#main").innerHTML = `
  <div class="sec admin" style="margin-top:0"><h2>Verwaltung</h2><span class="sub" id="st"></span><span class="sp"></span><span class="mut" style="font-size:13px" id="ver"></span></div>
  <div class="grid g2">
   <div class="panel"><h2>Komoot <span class="mut" style="font:400 16px var(--b)">(optional)</span></h2><p class="mut">${nf(st.tours, 0)} Touren (davon ${nf(st.local_tours, 0)} nur lokal) · ${nf(st.routes, 0)} Strecken lokal gespeichert. Karten und Tourdetails nutzen immer die lokal gespeicherten Strecken; Komoot wird nur zum Laden und Hochladen gebraucht.</p>
    <div class="row"><button class="btn" data-job="refresh">Komoot aktualisieren</button><button class="btn alt" data-job="tours">Nur Touren</button><button class="btn alt" data-job="routes" title="Fehlende Strecken von Komoot lokal speichern">Strecken lokal sichern</button><button class="btn alt" data-job="geo" title="Land, Bundesland und Ort jeder Tour per OpenStreetMap bestimmen (für Suche und Filter)">Regionen bestimmen</button><button class="btn alt" id="diag">Komoot-Test</button></div>
    <p class="mut" style="font-size:13px">„Aktualisieren“ lädt neue Touren und deren Strecken von Komoot und liest die Fotos ein. Es wird <b>nichts</b> zu Komoot hochgeladen. <span id="dres"></span></p>
    <div class="field"><label>Komoot-E-Mail</label><input data-k="komoot_email" value="${esc(s.komoot_email)}"></div><div class="field"><label>Komoot-Passwort</label><input data-k="komoot_password" type="password" value="${esc(s.komoot_password)}"></div></div>
   <div class="panel"><h2>Fotos</h2><p class="mut">${nf(pi.count, 0)} Fotos in der Bibliothek, ${nf(pi.assigned, 0)} einer Tour zugeordnet.<br>Bibliothek: <code>${esc(pi.lib_dir)}</code></p>
    <div class="row"><button class="btn" id="pdirb">Ordner auswählen und hochladen …</button><button class="btn alt" data-job="photos">Bibliothek neu einlesen</button></div>
    <input type="file" id="pdir" webkitdirectory multiple hidden><div id="pup2" style="display:none;margin-top:10px"><div class="stack" style="height:10px"><div id="pbar" style="width:0;background:var(--acc)"></div></div><div class="row" style="margin-top:6px"><span id="ptxt" class="mut"></span><span class="sp"></span><button class="btn alt sm" id="pstop">Abbrechen</button></div></div>
    <details><summary>Weitere Wege (SMB-Ordner, Mac-Skript)</summary><div class="row" style="margin:8px 0"><button class="btn alt sm" data-job="photo-import">Fotos aus Serverordner übernehmen</button></div>
    <p class="mut" style="font-size:13px">„Übernehmen“ verkleinert die Originale aus <code>${esc(pi.source_dir)}</code> ${pi.folder_exists ? "" : "<b class='bad'>(Ordner nicht gefunden)</b>"} für die Bildschirmdarstellung und legt sie in der Bibliothek ab. Alternativ vom Mac aus mit dem Skript <code>mac/fotos_senden.sh</code>.</p></details><p class="mut" style="font-size:13px">Beim Hochladen werden die Bilder <b>im Browser</b> für die Bildschirmdarstellung verkleinert; nur die kleinen Dateien gehen übers Netz. Originale werden nie verändert.</p>
    <details><summary>Bildeinstellungen</summary>${f("photo_max_side", "Längste Bildseite (Pixel)", "number")}${f("photo_quality", "JPEG-Qualität (1–95)", "number")}${f("photo_margin_min", "Zuordnung: Toleranz vor/nach der Tour (Min.)", "number")}${f("camera_utc_offset_h", "Kamerazeit-Versatz zu UTC in Stunden (leer = lokale Zeit)")}${f("slideshow_seconds", "Diashow: Sekunden pro Bild", "number")}</details></div></div>
  <div class="panel" style="margin-top:40px"><h2>Portale <span class="mut" style="font:400 16px var(--b)">(Upload)</span></h2>
   <p class="mut">Touren liegen lokal vor und können einzeln (Tourdetail → „⬆ Hochladen“) oder gesammelt (Zepp/Dateien unten) zu Komoot und Strava gesendet werden – immer nur auf deinen ausdrücklichen Wunsch.</p>
   ${sres ? `<p class="${sres === "ok" ? "ok" : "bad"}"><b>${sres === "ok" ? "Strava ist verbunden ✓" : "Strava: " + esc(sres)}</b></p>` : ""}
   <div class="grid g2"><div><h3 style="margin-top:0">Strava ${sv.connected ? `<span class="ok" style="font-size:15px">✓ verbunden${sv.account ? " als " + esc(sv.account) : ""}</span>` : ""}</h3>
    ${f("strava_client_id", "Client-ID")}${f("strava_client_secret", "Client-Secret", "password")}
    <div class="row"><button class="btn" id="sconn">${sv.connected ? "Neu verbinden" : "Mit Strava verbinden"}</button>${sv.connected ? `<button class="btn alt" id="sdis">Trennen</button>` : ""}<span id="sres"></span></div></div>
    <ol class="mut" style="padding-left:18px;margin-top:0"><li>Auf <a target="_blank" href="https://www.strava.com/settings/api">strava.com/settings/api</a> eine eigene App anlegen (Name frei).</li><li>„Authorization Callback Domain“: <code>${esc(location.hostname)}</code> (bei Fehlermeldung: <code>localhost</code>).</li><li>Client-ID und -Secret hier eintragen, „Einstellungen speichern“, dann „Mit Strava verbinden“.</li><li>Falls Strava nach der Freigabe nicht zurückfindet: Adresse der leeren Seite kopieren und hier einfügen:<div class="row" style="margin-top:6px"><input id="scode" placeholder="http://…?code=…" style="flex:1"><button class="btn alt sm" id="scodeb">Code einlösen</button></div></li></ol></div>
   <details><summary>Komoot</summary><p class="mut">Zugang siehe Panel „Komoot“ oben. Touren, die von Komoot stammen, können nicht erneut zu Komoot hochgeladen werden; zu Strava schon.</p></details></div>
  <div class="panel" style="margin-top:40px"><h2>Zepp-Import <span class="mut" style="font:400 16px var(--b)">(optional)</span></h2>
   <p class="mut">Holt GPS-Trainings aus deinem Zepp-Konto (als GPX-Dateien). Ausgewählte Trainings werden lokal als Tour gespeichert (Karte, Statistik); ein Upload zu Komoot/Strava passiert <b>nur</b>, wenn du es unten ausdrücklich anhakst.</p>
   <div class="row"><button class="btn" data-job="export">Zepp-Import starten</button><button class="btn alt" id="ztest">Token testen</button><span id="zres"></span></div>
   <details><summary>Zepp-Zugang / Token holen</summary><div class="grid g2"><div>${f("zepp_email", "E-Mail (nur wenn dein Konto ein Zepp-Passwort hat)")}${f("zepp_password", "Passwort", "password")}${f("zepp_token", "Token (für Mi-/Google-/Apple-Konten)", "password")}${f("zepp_host", "Server (leer = automatisch)")}</div>
    <ol class="mut" style="padding-left:18px"><li>Diesen Knopf in die <b>Lesezeichenleiste</b> ziehen: <a id="bm" class="btn alt sm" href="#">Token an Meine Touren</a></li><li>Im selben Browser <a target="_blank" href="https://user.huami.com/privacy2/index.html?platform_app=com.xiaomi.hm.health&loginPlatform=web">user.huami.com/privacy2</a> öffnen, anmelden und dort <b>nichts</b> anklicken (die Seite bietet „Konto löschen“ an).</li><li>Das Lesezeichen anklicken – das Token wird gespeichert und geprüft.</li></ol></div></details>
   <h3 style="margin-top:14px">Zepp-Trainings ${pend.length ? "noch nicht übernommen" : ""}</h3>
   <p class="mut">${w.length} exportiert · ${w.filter(x => x.status === "local").length} lokal übernommen · ${w.filter(x => x.status === "in_komoot" || x.status === "uploaded").length} bereits in Komoot · ${w.filter(x => x.status === "no_gps").length} ohne GPS · ${pend.length} noch offen</p>
   ${pend.length ? `<details${pend.length <= 8 ? " open" : ""}><summary>${pend.length} offene Trainings anzeigen</summary><div style="max-height:300px;overflow:auto"><table><tr><th></th><th>Datum</th><th>Sport</th><th class="n">km</th></tr>${pend.map(x => `<tr><td><input type="checkbox" class="pk" value="${x.trackid}"></td><td>${dateS(x.date)} ${timeS(x.date)}</td><td>${sName(x.sport)}</td><td class="n">${nf(x.dist_m / 1000, 1)}</td></tr>`).join("")}</table></div></details>
   <div class="row" style="margin-top:10px"><button class="btn alt sm" id="pall">Alle wählen</button><button class="btn alt sm" id="pdry">Probelauf</button><button class="btn" id="plocal">Lokal übernehmen</button></div>
   <div class="row" style="margin-top:8px"><span class="mut">Zusätzlich hochladen zu:</span>${pf.portals.map(p => `<label class="chk" style="margin:0"><input type="checkbox" class="zp" value="${p.id}" ${p.connected ? "" : "disabled"}> ${p.name}</label>`).join("")}<button class="btn" id="pup">Übernehmen und hochladen</button></div>
   <div class="field" style="margin-top:8px"><label>Neue Zepp-Trainings automatisch lokal übernehmen (ohne Upload)</label><select data-k="zepp_auto_adopt"><option value="0">aus</option><option value="1">an</option></select></div>` : ""}
   </div>
  <div class="panel" style="margin-top:40px"><h2>GPX/TCX-Dateien <span class="mut" style="font:400 16px var(--b)">(Import)</span></h2><div class="field"><label>GPX/TCX-Dateien importieren (lokal speichern, Doppelten-Prüfung; Upload nur mit Häkchen)</label><div class="row"><input type="file" id="files" multiple accept=".gpx,.tcx"><span class="mut">zusätzlich zu:</span>${pf.portals.map(p => `<label class="chk" style="margin:0"><input type="checkbox" class="fp" value="${p.id}" ${p.connected ? "" : "disabled"}> ${p.name}</label>`).join("")}<button class="btn alt sm" id="upl">Importieren</button><label style="margin:0"><input type="checkbox" id="dry"> Probelauf</label></div></div></div>
  <div class="grid g2" style="margin-top:40px">
   <div class="panel"><h2>Automatik</h2><div class="field"><label>Täglich aktualisieren (Komoot, Routen, Fotos)</label><select data-k="auto_sync"><option value="0">aus</option><option value="1">an</option></select></div>${f("auto_sync_hour", "Uhrzeit (Stunde)", "number")}</div>
   <div class="panel"><h2>Protokoll</h2><div class="pre" id="log">–</div></div></div>
  <div class="row" style="margin-top:34px"><button class="btn" id="save">Einstellungen speichern</button><span id="ok" class="ok"></span></div>`;
  document.querySelector('[data-k="auto_sync"]').value = s.auto_sync; if (document.querySelector('[data-k="zepp_auto_adopt"]')) document.querySelector('[data-k="zepp_auto_adopt"]').value = s.zepp_auto_adopt;
  const run = async (u, o) => { try { await api(u, o); } catch (e) { alert(e.message); } poll(); };
  document.querySelectorAll("[data-job]").forEach(b => b.onclick = () => run(`/api/jobs/${b.dataset.job}`, {method: "POST"}));
  $("#diag").onclick = async () => { $("#dres").textContent = "…"; try { const r = await api("/api/diag/coords"); $("#dres").innerHTML = `<span class="ok">Streckenpunkte erreichbar (${r.punkte} Punkte)</span>`; } catch (e) { $("#dres").innerHTML = `<span class="bad">${esc(e.message)}</span>`; } };
  $("#ztest").onclick = async () => { $("#zres").textContent = "…"; try { const r = await api("/api/zepp-token/test", {method: "POST"}); $("#zres").innerHTML = `<span class="ok">Token funktioniert ✓</span>`; } catch (e) { $("#zres").innerHTML = `<span class="bad">${esc(e.message)}</span>`; } };
  const ZK = await api("/api/zepp-key").catch(() => ({u: "", k: ""}));
  const code = "(function(){var m=document.cookie.match(/(?:^|; )apptoken=([^;]+)/);if(!m){alert('Kein apptoken gefunden – bitte zuerst bei Zepp anmelden.');return;}var f=document.createElement('form');f.method='POST';f.action='" + location.origin + "/api/zepp-token';f.target='_blank';var i=document.createElement('input');i.type='hidden';i.name='token';i.value=m[1];f.appendChild(i);var u=document.createElement('input');u.type='hidden';u.name='u';u.value='" + ZK.u + "';f.appendChild(u);var k=document.createElement('input');k.type='hidden';k.name='k';k.value='" + ZK.k + "';f.appendChild(k);document.body.appendChild(f);f.submit();})()";
  $("#bm").setAttribute("href", "javascript:" + encodeURIComponent(code)); $("#bm").onclick = e => { e.preventDefault(); alert("Bitte den Knopf mit der Maus in die Lesezeichenleiste ziehen, nicht anklicken."); };
  const picked = () => [...document.querySelectorAll(".pk:checked")].map(c => +c.value);
  if ($("#pall")) { $("#pall").onclick = () => document.querySelectorAll(".pk").forEach(c => c.checked = true);
    const up = (dry, local) => { const ids = picked(); if (!ids.length) return alert("Bitte zuerst Trainings auswählen."); const ps = local ? [] : [...document.querySelectorAll(".zp:checked")].map(c => c.value);
      if (!local && !ps.length) return alert("Bitte mindestens ein Portal ankreuzen – oder „Lokal übernehmen“ wählen.");
      if (!dry && ps.length && !confirm(`${ids.length} Training(s) lokal übernehmen und zu ${ps.join(" + ")} hochladen?`)) return;
      run("/api/zepp-upload", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({trackids: ids, dry_run: dry, portals: ps, local_only: local})}); };
    $("#plocal").onclick = () => up(false, true);
    $("#pup").onclick = () => up(false); $("#pdry").onclick = () => up(true, false); }
  folderUpload();
  $("#upl").onclick = () => { const fd = new FormData(); [...$("#files").files].forEach(x => fd.append("files", x)); if (!$("#files").files.length) return; const ps = [...document.querySelectorAll(".fp:checked")].map(c => c.value);
    if (!$("#dry").checked && ps.length && !confirm(`Dateien lokal speichern und zu ${ps.join(" + ")} hochladen?`)) return; run(`/api/import-files?dry_run=${$("#dry").checked}&portals=${ps.join(",")}`, {method: "POST", body: fd}); };
  $("#sconn").onclick = async () => { try { await save(); const r = await api("/api/strava/connect"); location.href = r.url; } catch (e) { $("#sres").innerHTML = `<span class="bad">${esc(e.message)}</span>`; } };
  if ($("#sdis")) $("#sdis").onclick = async () => { if (!confirm("Strava-Verbindung trennen?")) return; await api("/api/strava/disconnect", {method: "POST"}); route(); };
  $("#scodeb").onclick = async () => { try { await api("/api/strava/code", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({code: $("#scode").value})}); route(); } catch (e) { $("#sres").innerHTML = `<span class="bad">${esc(e.message)}</span>`; } };
  const save = async () => { const d = {}; document.querySelectorAll("[data-k]").forEach(e => d[e.dataset.k] = e.value); await api("/api/settings", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(d)}); };
  $("#save").onclick = async () => { await save(); $("#ok").textContent = "Gespeichert ✓"; };
  const poll = async () => { const j = await api("/api/jobs").catch(() => null); if (!j || !$("#log")) return;
    $("#log").textContent = j.log.join("\n") || "–"; $("#log").scrollTop = 1e9;
    $("#st").textContent = j.running ? `⏳ ${j.running} ${j.progress}` : (j.ok === false ? "zuletzt: Fehler" : j.ok ? "zuletzt: ok ✓" : "");
    $("#busy").textContent = j.running ? "⏳ " + j.running : ""; if (j.running) window._wasRun = true; else if (window._wasRun) { window._wasRun = false; ROUTES = null; loadTours(); } };
  poll(); pollTimer = setInterval(poll, 2000);
};
/* =====================  Erweiterungen  ===================== */
NAV.splice(3, 0, ["records", "Rekorde"]);
$("#nav").innerHTML = NAV.map(([k, l]) => `<a href="#/${k}" data-k="${k}">${l}</a>`).join("");
{ const gs = document.createElement("input"); gs.id = "gs"; gs.type = "search"; gs.placeholder = "Suchen …  ( / )"; gs.setAttribute("aria-label", "Touren suchen");
  $(".top").insertBefore(gs, $("#busy"));
  let tmr; gs.oninput = () => { clearTimeout(tmr); tmr = setTimeout(() => { const v = gs.value.trim(); location.hash = v ? `#/search?q=${encodeURIComponent(v)}` : "#/tours"; }, 250); };
  addEventListener("keydown", e => { if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); gs.focus(); gs.select(); } }); }

/* ---- Suche ---- */
VIEWS.search = async (_, q) => {
  const term = (q.get("q") || "").toLowerCase().trim(), toks = term.split(/\s+/).filter(Boolean);
  const hay = t => `${t.name} ${t.note || ""} ${sName(t.sport)} ${dateS(t.date)} ${MONL[t.m - 1]} ${t.y} ${t.g_place || ""} ${t.g_county || ""} ${t.g_state || ""} ${t.g_country || ""} ${(t.tags || "").replace(/\|/g, " ")}`.toLowerCase();
  const a = toks.length ? TOURS.filter(t => { const h = hay(t); return toks.every(k => h.includes(k)); }) : [];
  if (document.activeElement !== $("#gs") && $("#gs")) $("#gs").value = q.get("q") || "";
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Suche: „${esc(q.get("q") || "")}“</h2><span class="sub">${a.length} Touren, ${nf(a.reduce((c, t) => c + t.km, 0), 0)} km</span></div>
   <div class="tl">${a.slice(0, 200).map(tourRow).join("") || `<div class="empty">Keine Treffer. Gesucht wird in Name, Notiz, Sportart, Datum, Monat und Region (Land, Bundesland, Landkreis, Ort).</div>`}</div>`;
};

/* ---- Ziele (Übersicht) ---- */
const GM = {km: ["km", "Kilometer"], up: ["m", "Höhenmeter"], count: ["", "Touren"], hours: ["h", "Stunden"]};
const goalVal = (g, T) => T.filter(t => t.y === g.year && (!g.sport || t.sport === g.sport)).reduce((c, t) => c + (g.metric === "km" ? t.km : g.metric === "up" ? (t.up_m || 0) : g.metric === "hours" ? t.h : 1), 0);
const _dash = VIEWS.dash;
VIEWS.dash = async (n, q) => {
  await _dash(n, q);
  const fg = $(".figs"); if (!fg) return;
  const ys = years(), Y = +(q.get("y") || 0) || 0, cy = new Date().getFullYear(), yr = Y || cy;
  const goals = (await api("/api/goals").catch(() => [])).filter(g => g.year === yr), sp = [...new Set(TOURS.map(t => t.sport))];
  const now = new Date(), frac = yr === cy ? Math.max(0, (now - new Date(cy, 0, 1)) / (new Date(cy + 1, 0, 1) - new Date(cy, 0, 1))) : 1;
  const row = g => { const v = goalVal(g, TOURS), p = Math.min(100, v / g.target * 100), u = GM[g.metric][0], proj = frac > .02 && frac < 1 ? v / frac : null;
    return `<div class="goal"><div class="gh"><b>${GM[g.metric][1]}${g.sport ? " " + sName(g.sport) : ""}</b><span>${nf(v, g.metric === "count" ? 0 : 0)} / ${nf(g.target, 0)} ${u} <button class="gx" data-g="${g.id}" title="Ziel löschen">×</button></span></div>
     <div class="gb"><i style="width:${p}%"></i>${frac < 1 ? `<u style="left:${frac * 100}%" title="Soll heute"></u>` : ""}</div>
     <div class="gs">${nf(p, 0)} %${proj != null ? ` · Prognose zum Jahresende: ${nf(proj, 0)} ${u} (${nf(proj / g.target * 100, 0)} %)` : ""}${frac < 1 && v < g.target * frac ? ` · <span class="bad">${nf(g.target * frac - v, 0)} ${u} hinter dem Plan</span>` : frac < 1 && v >= g.target * frac ? ` · <span class="ok">im Plan</span>` : ""}</div></div>`; };
  const box = document.createElement("div"); box.className = "panel"; box.id = "goals"; box.style.marginTop = "34px";
  box.innerHTML = `<h2>Ziele ${yr}</h2>${goals.map(row).join("") || `<p class="mut">Noch kein Ziel für ${yr}. Setze dir eines, zum Beispiel 1000 km Wandern.</p>`}
   <details><summary>Ziel hinzufügen</summary><div class="row" style="margin-top:8px"><select id="gm">${Object.entries(GM).map(([k, v]) => `<option value="${k}">${v[1]}</option>`).join("")}</select>
   <select id="gsp"><option value="">alle Sportarten</option>${sp.map(s => `<option value="${s}">${sName(s)}</option>`).join("")}</select><input id="gt" type="number" min="1" placeholder="Zielwert" style="width:130px"><button class="btn sm" id="gadd">Speichern</button></div></details>`;
  fg.after(box);
  box.onclick = async e => { const g = e.target.dataset.g; if (g && confirm("Ziel löschen?")) { await api(`/api/goals/${g}`, {method: "DELETE"}); route(); } };
  $("#gadd").onclick = async () => { const t = +$("#gt").value; if (!t) return; await api("/api/goals", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({year: yr, metric: $("#gm").value, sport: $("#gsp").value, target: t})}); route(); };
  const yrs = $(".years"); if (yrs) yrs.insertAdjacentHTML("beforeend", `<a class="btn ghost sm" style="margin-left:auto;align-self:center" href="#/recap/${Y || ys[0]}">Jahresrückblick ${Y || ys[0]}</a>`);
};

/* ---- Rekorde ---- */
VIEWS.records = async () => {
  if (!TOURS.length) { $("#main").innerHTML = `<div class="empty"><h2>Noch keine Touren</h2></div>`; return; }
  const sum = (a, f) => a.reduce((c, t) => c + f(t), 0), km = sum(TOURS, t => t.km), up = sum(TOURS, t => t.up_m || 0), h = sum(TOURS, t => t.h);
  const best = (a, f) => a.reduce((b, t) => (b == null || f(t) > f(b)) ? t : b, null);
  const sports = [...new Set(TOURS.map(t => t.sport))].sort((a, b) => TOURS.filter(t => t.sport === b).length - TOURS.filter(t => t.sport === a).length);
  const lnk = (t, v) => t ? `<div class="r"><span>${v[0]}<small><a href="#/tour/${t.id}">${esc(t.name)}</a>, ${dateS(t.date)}</small></span><b>${v[1]}</b></div>` : "";
  const wkIdx = t => Math.floor((Date.UTC(t.y, t.m - 1, +t.date.slice(8, 10)) / 864e5 + 3) / 7), wks = [...new Set(TOURS.map(wkIdx))].sort((a, b) => a - b);
  let longest = 0, run = 0, prevW = null; wks.forEach(w => { run = prevW !== null && w === prevW + 1 ? run + 1 : 1; longest = Math.max(longest, run); prevW = w; });
  const curW = Math.floor((Date.now() / 864e5 + 3) / 7); let cur = 0; { let w = wks.includes(curW) ? curW : wks.includes(curW - 1) ? curW - 1 : null; while (w !== null && wks.includes(w)) { cur++; w--; } }
  const dayN = new Set(TOURS.map(t => t.date.slice(0, 10))).size, wd = Array(7).fill(0); TOURS.forEach(t => wd[(new Date(t.date.slice(0, 10) + "T12:00:00").getDay() + 6) % 7]++);
  const alts = await api("/api/records/altitude?limit=8").catch(() => []);
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Rekorde</h2><span class="sub">${nf(TOURS.length, 0)} Touren seit ${TOURS[TOURS.length - 1].y}</span></div>
   <div class="figs"><div class="fig"><div class="v">${nf(km / 40075, 2)}<span class="u">×</span></div><div class="l">um die Erde (${nf(km, 0)} km)</div></div>
    <div class="fig"><div class="v">${nf(up / 8849, 1)}<span class="u">×</span></div><div class="l">Mount Everest bergauf (${nf(up, 0)} m)</div></div>
    <div class="fig"><div class="v">${nf(h / 24, 1)}<span class="u">Tage</span></div><div class="l">unterwegs (${nf(h, 0)} Std.)</div></div>
    <div class="fig"><div class="v">${nf(dayN, 0)}</div><div class="l">Tage mit Touren</div></div>
    <div class="fig"><div class="v">${longest}<span class="u">Wochen</span></div><div class="l">längste Serie · aktuell ${cur}</div></div></div>
   <div class="grid g2" style="margin-top:36px">
    <div class="panel"><h2>Bestwerte gesamt</h2><div class="rows">${lnk(best(TOURS, t => t.km), ["Längste Strecke", nf(best(TOURS, t => t.km).km, 1) + " km"])}${lnk(best(TOURS, t => t.up_m || 0), ["Meiste Höhenmeter", nf(best(TOURS, t => t.up_m || 0).up_m, 0) + " m"])}${lnk(best(TOURS, t => t.h), ["Längste Dauer", nf(best(TOURS, t => t.h).h, 1) + " h"])}</div></div>
    <div class="panel"><h2>Höchste Punkte</h2><div class="rows">${alts.length ? alts.map(a => BY[a.id] ? `<div class="r"><span><a href="#/tour/${a.id}">${esc(BY[a.id].name)}</a><small>${dateS(BY[a.id].date)}</small></span><b>${nf(a.alt, 0)} m</b></div>` : "").join("") : `<div class="mut">Sobald die Strecken geladen sind („Routen laden“ in der Verwaltung), erscheinen hier die höchsten Punkte.</div>`}</div></div>
    <div class="panel"><h2>Nach Wochentag</h2>${barChart(wd, ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"])}</div>
    <div class="panel"><h2>Je Sportart</h2><div class="rows">${sports.map(s => { const a = TOURS.filter(t => t.sport === s), l = best(a, t => t.km), u = best(a, t => t.up_m || 0), f = best(a.filter(t => t.km >= 3 && t.h > 0), t => t.km / t.h);
      return `<div class="r" style="display:block"><div><i class="sw" style="background:${sCol(s)}"></i><b style="font:600 20px var(--d)">${sName(s)}</b> <span class="mut">· ${a.length} Touren, ${nf(sum(a, t => t.km), 0)} km, ${nf(sum(a, t => t.up_m || 0), 0)} m</span></div>
       <small>Längste: <a href="#/tour/${l.id}">${nf(l.km, 1)} km</a> · Meiste Höhenmeter: <a href="#/tour/${u.id}">${nf(u.up_m, 0)} m</a>${f ? ` · Schnellste: <a href="#/tour/${f.id}">${nf(f.km / f.h, 1)} km/h</a>` : ""}</small></div>`; }).join("")}</div></div></div>`;
};

/* ---- Jahresrückblick ---- */
VIEWS.recap = async name => {
  const Y = +name || years()[0], sel = TOURS.filter(t => t.y === Y), prev = TOURS.filter(t => t.y === Y - 1);
  if (!sel.length) { $("#main").innerHTML = `<div class="empty"><h2>Keine Touren in ${Y}</h2></div>`; return; }
  const sum = (a, f) => a.reduce((c, t) => c + f(t), 0), km = sum(sel, t => t.km), up = sum(sel, t => t.up_m || 0), h = sum(sel, t => t.h);
  const mm = Array(12).fill(0), pm = Array(12).fill(0); sel.forEach(t => mm[t.m - 1] += t.km); prev.forEach(t => pm[t.m - 1] += t.km);
  const bySport = {}; sel.forEach(t => bySport[t.sport] = (bySport[t.sport] || 0) + t.km); const sp = Object.entries(bySport).sort((a, b) => b[1] - a[1]);
  const top = sel.slice().sort((a, b) => b.km - a.km).slice(0, 5), steep = sel.slice().sort((a, b) => (b.up_m || 0) - (a.up_m || 0))[0], bm = mm.indexOf(Math.max(...mm));
  const days = new Set(sel.map(t => t.date.slice(0, 10))).size, ph = await api(`/api/photos?year=${Y}&random=true&limit=12`).catch(() => []);
  const dl = (a, b) => b ? `${a >= b ? "+" : "−"}${nf(Math.abs(a - b) / b * 100, 0)} % gegenüber ${Y - 1}` : "";
  $("#main").innerHTML = `<div class="recap"><div class="noprint row" style="margin-bottom:10px"><a class="back" href="#/dash?y=${Y}">‹ Übersicht</a><span class="sp"></span><button class="btn ghost sm" onclick="print()">Drucken / als PDF speichern</button></div>
   <div class="rhero"><div class="k">Mein Tourenjahr</div><h1>${Y}</h1><div class="rs"><span><b>${nf(sel.length, 0)}</b> Touren</span><span><b>${nf(km, 0)}</b> km</span><span><b>${nf(up, 0)}</b> Höhenmeter</span><span><b>${nf(h, 0)}</b> Stunden</span><span><b>${days}</b> Tage unterwegs</span></div>
   <div class="rd">${[dl(km, sum(prev, t => t.km))].filter(Boolean).join("")}</div></div>
   <div class="grid g2" style="margin-top:34px"><div class="panel"><h2>Kilometer pro Monat</h2>${barChart(mm, MON, {ghost: pm, ghostLabel: Y - 1})}<div class="mut" style="font-size:14px">Stärkster Monat: ${MONL[bm]} mit ${nf(mm[bm], 0)} km</div></div>
    <div class="panel"><h2>Sportarten</h2><div class="stack">${sp.map(([s, v]) => `<div style="width:${v / km * 100}%;background:${sCol(s)}"></div>`).join("")}</div><div class="rows" style="margin-top:10px">${sp.map(([s, v]) => `<div class="r"><span><i class="sw" style="background:${sCol(s)}"></i>${sName(s)}</span><span class="mut">${nf(v, 0)} km, ${nf(v / km * 100, 0)} %</span></div>`).join("")}</div></div></div>
   <div class="panel" style="margin-top:34px"><h2>Die fünf längsten Touren</h2><div class="tl">${top.map(tourRow).join("")}</div><div class="mut" style="margin-top:10px">Meiste Höhenmeter: <a href="#/tour/${steep.id}">${esc(steep.name)}</a> (${nf(steep.up_m, 0)} m)</div></div>
   ${ph.length ? `<div class="panel" style="margin-top:34px"><div class="row"><h2>Fotos des Jahres</h2><span class="sp"></span><a class="btn sm noprint" target="_blank" href="slideshow.html?year=${Y}">Diashow</a></div><div class="thumbs" id="rph">${ph.map((p, i) => `<div class="th"><img loading="lazy" src="/photo/${p.id}?size=400" data-i="${i}"></div>`).join("")}</div></div>` : ""}</div>`;
  if (ph.length) bindThumbs($("#rph"), ph);
};

/* ---- Tourdetail: Notiz, GPX, Teilen ---- */
const _tourV = VIEWS.tour;
VIEWS.tour = async id => {
  await _tourV(id); const t = BY[id], r = $("#ksync") && $("#ksync").closest(".row"); if (!t || !r) return;
  r.insertAdjacentHTML("beforeend", `<a class="btn ghost sm" href="/api/tours/${encodeURIComponent(id)}/gpx" download title="Strecke als GPX-Datei">⬇ GPX</a><a class="btn ghost sm" href="#/flight/${encodeURIComponent(id)}" title="Die Strecke im 3D-Gelände abfliegen">🛰 3D-Flug</a>${t.photos ? `<button class="btn ghost sm" id="shr" title="Link zur Foto-Diashow dieser Tour kopieren">🔗 Diashow-Link</button>` : ""}`);
  if ($("#shr")) $("#shr").onclick = async () => { const u = new URL(`slideshow.html?tour=${id}`, location.href).href; try { await navigator.clipboard.writeText(u); $("#shr").textContent = "✓ Link kopiert"; } catch (e) { prompt("Link zur Diashow:", u); } };
  r.insertAdjacentHTML("afterend", `<div class="field" style="max-width:760px;margin:0 0 18px"><label for="note">Notiz zur Tour (Wetter, Begleitung, Einkehr …)</label><textarea id="note" rows="2" placeholder="Hier eine Notiz eintragen …">${esc(t.note || "")}</textarea><span id="notes" class="mut" style="font-size:13px"></span></div>`);
  $("#note").onchange = async () => { try { await api(`/api/tours/${encodeURIComponent(id)}/note`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({note: $("#note").value})}); t.note = $("#note").value.trim(); $("#notes").textContent = "gespeichert ✓"; } catch (e) { $("#notes").innerHTML = `<span class="bad">${esc(e.message)}</span>`; } };
};

/* ---- Verwaltung: Sicherung und Schutz ---- */
const _adm = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm(...a); const st = await api("/api/status").catch(() => ({})), sv = $("#save"); if (!sv) return;
  if ($("#ver")) $("#ver").textContent = "Version: " + (st.version || "alt");
  sv.closest(".row").insertAdjacentHTML("beforebegin", `<div class="grid g2" style="margin-top:40px"><div class="panel"><h2>Sicherung</h2>
   <p class="mut">Täglich um 03:40 Uhr wird die Datenbank (Touren, Notizen, Ziele, Zuordnungen) automatisch nach <code>${esc(st.backup_dir || "/var/backups/meine-touren")}</code> gesichert, die letzten 14 bleiben erhalten. Wiederherstellen: <code>${esc(st.app_name || "meine-touren")}-restore &lt;Datei&gt;</code> im Container.</p>
   <div class="row"><a class="btn alt" href="/api/backup" download>Backup jetzt herunterladen</a></div><p class="mut" style="font-size:13px">Passwörter und Tokens sind im Download nicht enthalten. Fotos und Routen sind nicht enthalten, sie lassen sich neu laden.</p></div>
   <div class="panel"><h2>Zugriffsschutz</h2>${st.protected ? `<p class="ok"><b>✓ Passwortschutz ist aktiv.</b></p>` : `<p class="bad"><b>Die Oberfläche ist nicht passwortgeschützt.</b></p><p class="mut">Jeder im Netzwerk kann Touren, Fotos und Einstellungen sehen. Zum Schutz im Container <code>UI_PASSWORD=…</code> in <code>/etc/${esc(st.app_name || "meine-touren")}.env</code> setzen und <code>systemctl restart ${esc(st.app_name || "meine-touren")}</code> ausführen.</p>`}</div></div>`);
};

/* ---- Karte: Heatmap und Fotos ---- */
const _mapV = VIEWS.map;
VIEWS.map = async () => {
  await _mapV(); const routes = ROUTES || {}, box = $(".mapui"); if (!box || !map) return;
  box.insertAdjacentHTML("beforeend", `<div class="box"><button class="chip" id="mht" title="Alle Strecken übereinander: häufig begangene Wege leuchten stärker">Heatmap</button><button class="chip" id="mph" title="Fotos mit GPS-Position anzeigen">Fotos</button></div>`);
  const m = map, hl = L.layerGroup().addTo(m), pl = L.layerGroup().addTo(m); let heat = false, phs = null, phOn = false;
  const yearSel = () => +$("#my").value, off = () => new Set([...document.querySelectorAll("#ms .chip:not(.on)")].map(c => c.dataset.s));
  const drawHeat = () => { hl.clearLayers(); if (!heat) return; const o = off(), y = yearSel(); TOURS.forEach(t => { if ((y && t.y !== y) || o.has(t.sport)) return; const r = cleanPts(routes[t.id]); if (r.length > 1) L.polyline(r, {color: "#ff4d12", weight: 4, opacity: .17, interactive: false}).addTo(hl); }); };
  const drawPh = () => { pl.clearLayers(); if (!phOn || !phs) return; const y = yearSel();
    phs.forEach(p => { if (y && new Date(p.taken_ts * 1000).getFullYear() !== y) return; if (!okPt([p.lat, p.lng])) return;
      L.circleMarker([p.lat, p.lng], {radius: 5, color: "#fff", weight: 1.5, fillColor: "#e11d74", fillOpacity: .95}).addTo(pl).bindPopup(`<img src="/photo/${p.id}?size=300" style="width:220px;border-radius:3px;display:block"><div style="margin-top:4px">${new Date(p.taken_ts * 1000).toLocaleString("de-DE")}${p.tour_id && BY[p.tour_id] ? `<br><a href="#/tour/${p.tour_id}">${esc(BY[p.tour_id].name)}</a>` : "<br>ohne Tour"}</div>`); }); };
  const mainGrp = []; m.eachLayer(l => { if (l instanceof L.LayerGroup && !(l === hl || l === pl)) mainGrp.push(l); });
  $("#mht").onclick = e => { heat = !heat; e.target.classList.toggle("on", heat); mainGrp.forEach(g => heat ? m.removeLayer(g) : m.addLayer(g)); drawHeat(); };
  $("#mph").onclick = async e => { phOn = !phOn; e.target.classList.toggle("on", phOn); if (phOn && !phs) { try { phs = await api("/api/photos?gps=true&limit=20000"); } catch (x) { phs = []; } if (!phs.length) e.target.title = "Keine Fotos mit GPS-Position"; } drawPh(); };
  box.insertAdjacentHTML("beforeend", `<div class="box"><button class="chip" id="mbx" title="Alle Touren auflisten, die den sichtbaren Kartenausschnitt berühren">Touren im Ausschnitt</button></div>`);
  $("#mbx").onclick = () => {
    const b = m.getBounds(), y = yearSel(), o = off();
    const a = TOURS.filter(t => (!y || t.y === y) && !o.has(t.sport) && cleanPts(routes[t.id]).some(p => b.contains(p)));
    const md = document.createElement("div"); md.className = "modal";
    md.innerHTML = `<div class="mbox" style="max-width:760px"><div class="sec" style="margin:0 0 10px"><h2>Im Kartenausschnitt</h2><span class="sub">${a.length} Touren, ${nf(a.reduce((c, t) => c + t.km, 0), 0)} km, ${nf(a.reduce((c, t) => c + (t.up_m || 0), 0), 0)} m auf</span></div>
      <div class="tl">${a.slice(0, 300).map(tourRow).join("") || '<div class="empty">Keine Touren in diesem Ausschnitt. Zoome heraus oder verschiebe die Karte.</div>'}</div>
      <div class="row" style="justify-content:flex-end;margin-top:14px"><button class="btn" id="mbc">Schließen</button></div></div>`;
    document.body.appendChild(md); md.querySelector("#mbc").onclick = () => md.remove(); md.onclick = e => { if (e.target === md || e.target.closest("a")) md.remove(); };
  };
  ["#my"].forEach(s => $(s).addEventListener("change", () => { drawHeat(); drawPh(); })); $("#ms").addEventListener("click", () => setTimeout(drawHeat, 0));
};

/* ---- Foto-Zuordnung: GPS-Hinweis ---- */
const _ad = assignDialog;
assignDialog = (sp, done) => {
  loadRoutes().catch(() => {}).then(() => {
    const first = sp.slice().sort((a, b) => a.taken_ts - b.taken_ts)[0], R = ROUTES || {};
    const near = t => okPt([first.lat, first.lng]) && cleanPts(R[t.id]).some(p => Math.abs(p[0] - first.lat) < .012 && Math.abs(p[1] - first.lng) < .02);
    const mark = TOURS.map(t => [t, near(t)]).filter(x => x[1]).map(x => x[0].id);
    _ad(sp, done);
    if (mark.length) { const sel = $("#at"); [...sel.options].forEach(o => { if (mark.includes(o.value)) o.textContent = "📍 " + o.textContent; });
      const opts = [...sel.options].sort((a, b) => (b.textContent.startsWith("📍") ? 1 : 0) - (a.textContent.startsWith("📍") ? 1 : 0)); opts.forEach(o => sel.appendChild(o)); sel.selectedIndex = 0; sel.dispatchEvent(new Event("input"));
      sel.insertAdjacentHTML("afterend", `<div class="mut" style="font-size:13px;margin-top:4px">📍 = das Foto wurde in der Nähe dieser Strecke aufgenommen (GPS)</div>`); }
  });
};

/* =====================  3D-Flug  ===================== */
const loadLib = () => window.maplibregl ? Promise.resolve() : new Promise((ok, no) => {
  const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "vendor/maplibre-gl.css"; document.head.appendChild(l);
  const s = document.createElement("script"); s.src = "vendor/maplibre-gl.js"; s.onload = ok; s.onerror = () => no(new Error("3D-Bibliothek konnte nicht geladen werden")); document.head.appendChild(s); });
const hav = (a, b) => { const R = 6371000, r = Math.PI / 180, dl = (b[0] - a[0]) * r, dn = (b[1] - a[1]) * r, x = Math.sin(dl / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dn / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(x)); };
const brg = (a, b) => { const r = Math.PI / 180, y = Math.sin((b[1] - a[1]) * r) * Math.cos(b[0] * r), x = Math.cos(a[0] * r) * Math.sin(b[0] * r) - Math.sin(a[0] * r) * Math.cos(b[0] * r) * Math.cos((b[1] - a[1]) * r); return (Math.atan2(y, x) / r + 360) % 360; };
function flightPath(raw) {   // gleichmäßig nach Strecke abtasten, Höhe auffüllen, Kamerapfad glätten
  const cum = [0]; for (let i = 1; i < raw.length; i++) cum.push(cum[i - 1] + hav(raw[i - 1], raw[i]));
  const total = cum[cum.length - 1] || 1, N = Math.max(60, Math.min(900, Math.round(total / 8))), P = [];
  let la = raw.find(p => p[2] != null)?.[2] ?? 0; const alt = raw.map(p => (la = p[2] ?? la));
  for (let k = 0, j = 0; k < N; k++) { const d = total * k / (N - 1); while (j < raw.length - 2 && cum[j + 1] < d) j++; const f = (d - cum[j]) / ((cum[j + 1] - cum[j]) || 1);
    P.push({lat: raw[j][0] + (raw[j + 1][0] - raw[j][0]) * f, lng: raw[j][1] + (raw[j + 1][1] - raw[j][1]) * f, alt: alt[j] + (alt[j + 1] - alt[j]) * f, d}); }
  const w = Math.max(3, Math.round(N / 80)), S = P.map((p, i) => { let a = 0, b = 0, c = 0; for (let k = Math.max(0, i - w); k <= Math.min(N - 1, i + w); k++) { a += P[k].lat; b += P[k].lng; c++; } return {lat: a / c, lng: b / c}; });
  let up = 0; P.forEach((p, i) => { if (i) up += Math.max(0, (p.alt - P[i - 1].alt) > .3 ? p.alt - P[i - 1].alt : 0); p.up = up; });
  return {P, S, total, cum};
}
VIEWS.flight = async id => {
  id = decodeURIComponent(id || "");
  const SET = id.startsWith("set:"), t = SET ? {id, name: "Flug über " + id.slice(4).split(",").length + " Touren", sport: (BY[id.slice(4).split(",")[0]] || {}).sport || "hike", start_ts: 0, lat: 50, lng: 8} : BY[id]; if (!t) throw new Error("Tour nicht gefunden");
  $("#main").className = "wide";
  $("#main").innerHTML = `<div class="flight" id="fl"><div id="fm"></div><div class="fbar"><a class="btn ghost sm" href="${SET ? "javascript:history.back()" : "#/tour/" + t.id}">‹ Zurück</a><b class="ft">${esc(t.name)}</b><span class="sp"></span><span id="fh" class="fh"></span></div>
   <div class="fctl"><button class="btn sm" id="fp">⏸ Pause</button><input type="range" id="fs" min="0" max="1000" value="0" aria-label="Position">
    <select id="fv" title="Tempo"><option value=".5">0,5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option><option value="8">8×</option></select>
    <select id="fc" title="Kamera"><option value="follow">Kamera folgt</option><option value="free">Kamera frei</option></select>
    <select id="fz" title="Flughöhe"><option value="16">nah</option><option value="14.8" selected>mittel</option><option value="13.4">weit</option></select>
    <select id="fpi" title="Neigung"><option value="55">flach</option><option value="68" selected>schräg</option><option value="78">sehr schräg</option></select>
    <select id="fb" title="Karte"><option value="osm">Straßenkarte</option><option value="topo">Topografisch</option><option value="sat">Satellit</option></select>
    <button class="btn ghost sm" id="frec" title="Flug als Video aufnehmen und speichern">⏺ Video</button><button class="btn ghost sm" id="ffs" title="Vollbild">⛶</button></div><div class="fph" id="fph"><img id="fphi" alt=""><span id="fphc"></span></div><div class="fmsg" id="fmsg">Lade Strecke …</div></div>`;
  const raw = cleanPts(await api(SET ? `/api/collection/coords?ids=${encodeURIComponent(id.slice(4))}` : `/api/tours/${t.id}/coords`).catch(() => []));
  if (raw.length < 2) { $("#fmsg").textContent = "Für diese Tour liegt noch keine Strecke vor (Tour mit Komoot abgleichen)."; return; }
  await loadLib();
  const PHS0 = SET ? [] : (await api(`/api/photos?tour_id=${t.id}&limit=60`).catch(() => [])).filter(p => p.taken_ts);
  if (!document.createElement("canvas").getContext("webgl")) { $("#fmsg").textContent = "Dieser Browser unterstützt kein WebGL, die 3D-Ansicht ist nicht möglich."; return; }
  const {P, S, total, cum} = flightPath(raw), N = P.length, lnglat = p => [p.lng, p.lat];
  const ras = (tiles, max, attr) => ({type: "raster", tiles, tileSize: 256, maxzoom: max, attribution: attr}), tp = k => TBASE + `tiles/${k}/{z}/{x}/{y}`;
  let sty = "osm"; try { sty = localStorage.getItem("mapstyle3d") || (localStorage.getItem("mapstyle") === "topo" ? "topo" : "osm"); } catch (e) {} $("#fb").value = sty;
  const m = new maplibregl.Map({container: "fm", pitch: 68, bearing: brg([P[0].lat, P[0].lng], [S[Math.min(10, N - 1)].lat, S[Math.min(10, N - 1)].lng]), center: lnglat(P[0]), zoom: 14.8, maxPitch: 85, attributionControl: {compact: true},
    style: {version: 8, sources: {
      osm: ras([tp("osm")], 19, "© OpenStreetMap"),
      topo: ras([tp("topo")], 17, "© OpenTopoMap, © OpenStreetMap"),
      sat: ras([tp("sat")], 19, "Esri, Maxar, Earthstar Geographics"),
      dem: {type: "raster-dem", tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"], tileSize: 256, maxzoom: 15, encoding: "terrarium", attribution: "Höhendaten: Mapzen/AWS Terrain Tiles"}},
     layers: [{id: "bg", type: "background", paint: {"background-color": "#cfd8d3"}}, ...["osm", "topo", "sat"].map(k => ({id: k, type: "raster", source: k, layout: {visibility: k === sty ? "visible" : "none"}}))]}});
  map = m;
  const setStyle = k => ["osm", "topo", "sat"].forEach(x => m.setLayoutProperty(x, "visibility", x === k ? "visible" : "none"));
  const dot = document.createElement("div"); dot.className = "fdot"; const mk = new maplibregl.Marker({element: dot}).setLngLat(lnglat(P[0])).addTo(m);
  const line = (a, b) => ({type: "Feature", geometry: {type: "LineString", coordinates: P.slice(a, b).map(lnglat)}});
  m.once("style.load", () => {
    m.setTerrain({source: "dem", exaggeration: 1.5});
    m.addSource("full", {type: "geojson", data: line(0, N)}); m.addSource("done", {type: "geojson", data: line(0, 2)});
    m.addLayer({id: "full-c", type: "line", source: "full", paint: {"line-color": "#fff", "line-width": 7, "line-opacity": .55}, layout: {"line-cap": "round", "line-join": "round"}});
    m.addLayer({id: "full", type: "line", source: "full", paint: {"line-color": "#6fb5a5", "line-width": 4}, layout: {"line-cap": "round", "line-join": "round"}});
    m.addLayer({id: "done", type: "line", source: "done", paint: {"line-color": "#f2c230", "line-width": 5}, layout: {"line-cap": "round", "line-join": "round"}});
    $("#fmsg").style.display = "none"; last = performance.now(); requestAnimationFrame(tick);
  });
  let u = 0, playing = true, bear = m.getBearing(), last = 0, follow = true, dragged = false, lastDone = -1;
  const at = (A, f, key) => { const i = Math.min(N - 2, Math.floor(f)), r = f - i; return A[i][key] + (A[i + 1][key] - A[i][key]) * r; };
  const place = () => { const f = u * (N - 1), lat = at(S, f, "lat"), lng = at(S, f, "lng"), cur = {lat: at(P, f, "lat"), lng: at(P, f, "lng")}; mk.setLngLat([cur.lng, cur.lat]);
    const i = Math.min(N - 1, Math.round(f)); if (i !== lastDone && m.getSource("done")) { lastDone = i; m.getSource("done").setData(line(0, Math.max(2, i + 1))); }
    const look = S[Math.min(N - 1, Math.round(f) + Math.max(6, Math.round(N / 60)))], tgt = brg([lat, lng], [look.lat, look.lng]);
    return {lat, lng, tgt, f}; };
  const hud = f => { const i = Math.min(N - 1, Math.round(f)), p = P[i]; $("#fh").innerHTML = `<b>${nf(p.d / 1000, 1)}</b> / ${nf(total / 1000, 1)} km · <b>${nf(p.alt, 0)}</b> m · ↑ ${nf(p.up, 0)} m`; };
  // Fotos entlang der Strecke: Marker + Einblendung beim Vorbeifliegen
  const phs = PHS0;
  const phU = p => { const rel = (p.taken_ts - t.start_ts) * 1000; if (raw[0][3] != null) { let i = raw.findIndex(q => (q[3] ?? 0) >= rel); if (i < 0) i = raw.length - 1; return cum[i] / total; }
    return Math.min(1, Math.max(0, (p.taken_ts - t.start_ts) / (((t.end_ts || t.start_ts + 1) - t.start_ts) || 1))); };
  phs.forEach(p => { p.u = phU(p); const k = P[Math.max(0, Math.min(N - 1, Math.round(p.u * (N - 1)) || 0))], el = document.createElement("div"); el.className = "fcam"; el.title = "Foto"; new maplibregl.Marker({element: el}).setLngLat([k.lng, k.lat]).addTo(m); });
  let phUntil = 0, prevU = 0; const phi = $("#fphi");
  const showPh = p => { phi.src = `/photo/${p.id}?size=500`; $("#fphc").textContent = new Date(p.taken_ts * 1000).toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"}) + " Uhr"; $("#fph").classList.add("on"); phUntil = performance.now() + 4500; };
  // Video-Aufnahme: Karte + Kopfzeile + Fotos auf eine Zeichenfläche, per MediaRecorder gespeichert
  let rec = null;
  const compose = () => { if (!rec) return; const c = m.getCanvas(), W = rec.c.width, H = rec.c.height, x = rec.x; x.drawImage(c, 0, 0, W, H);
    const p = P[Math.min(N - 1, Math.round(u * (N - 1)))]; x.fillStyle = "rgba(14,42,43,.8)"; x.fillRect(0, 0, W, 48); x.textBaseline = "middle"; x.font = "600 24px sans-serif"; x.fillStyle = "#fff"; x.textAlign = "left"; x.fillText(t.name, 16, 25);
    x.textAlign = "right"; x.fillStyle = "#f2c230"; x.fillText(`${nf(p.d / 1000, 1)} km · ${nf(p.alt, 0)} m`, W - 16, 25); x.fillStyle = "#f2c230"; x.fillRect(0, H - 6, W * u, 6);
    if (performance.now() < phUntil && phi.complete && phi.naturalWidth) { const w = Math.min(340, W * .32), h = w * phi.naturalHeight / phi.naturalWidth; x.fillStyle = "#fff"; x.fillRect(14, H - h - 34, w + 4, h + 4); x.drawImage(phi, 16, H - h - 32, w, h); } };
  m.on("render", compose);
  const stopRec = () => { if (!rec) return; const r = rec; rec = null; r.mr.stop(); $("#frec").textContent = "⏺ Video"; };
  $("#frec").onclick = () => {
    if (rec) return stopRec();
    const mime = window.MediaRecorder && ["video/mp4;codecs=avc1.42E01E", "video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"].find(x => MediaRecorder.isTypeSupported(x));
    if (!mime) return alert("Dieser Browser kann keine Videos aufnehmen (Chrome, Edge, Firefox oder Safari 14.1+ verwenden).");
    const c = m.getCanvas(), W = Math.min(c.width, 1280), oc = document.createElement("canvas"); oc.width = W; oc.height = Math.round(W * c.height / c.width);
    const mr = new MediaRecorder(oc.captureStream(30), {mimeType: mime, videoBitsPerSecond: 6e6}), chunks = [];
    mr.ondataavailable = e => e.data.size && chunks.push(e.data);
    mr.onstop = () => { const a = document.createElement("a"), ext = mime.includes("mp4") ? "mp4" : "webm"; a.href = URL.createObjectURL(new Blob(chunks, {type: mime.split(";")[0]})); a.download = (t.name.replace(/[^\w\-äöüÄÖÜß ]+/g, "_").trim() || "flug") + "." + ext; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 60000); };
    rec = {c: oc, x: oc.getContext("2d"), mr, ending: false}; u = 0; prevU = 0; playing = true; follow = true; $("#fc").value = "follow"; bear = m.getBearing(); last = performance.now(); $("#fp").textContent = "⏸ Pause";
    mr.start(500); $("#frec").textContent = "⏹ Aufnahme beenden (läuft …)";
  };
  const tick = now => {
    if (map !== m) return; const dt = Math.max(0, Math.min(100, now - last)); last = now;
    if (playing) { u += dt / 1000 / 100 * (+$("#fv").value); if (u >= 1) { u = 1; playing = false; $("#fp").textContent = "↻ Nochmal"; } $("#fs").value = Math.round(u * 1000); }
    const {lat, lng, tgt, f} = place(); hud(f);
    if (playing) phs.forEach(p => { if (prevU < p.u && u >= p.u) showPh(p); }); prevU = u; if ($("#fph").classList.contains("on") && performance.now() > phUntil) $("#fph").classList.remove("on");
    if (rec && u >= 1 && !rec.ending) { rec.ending = true; setTimeout(stopRec, 1800); }
    if (follow) { const d = ((tgt - bear + 540) % 360) - 180; bear = (bear + d * Math.min(1, dt / 600) + 360) % 360; m.jumpTo({center: [lng, lat], bearing: bear}); }
    requestAnimationFrame(tick); };
  $("#fp").onclick = () => { if (u >= 1) { u = 0; playing = true; } else playing = !playing; $("#fp").textContent = playing ? "⏸ Pause" : "▶ Weiter"; if (playing) last = performance.now(); };
  $("#fs").oninput = () => { u = +$("#fs").value / 1000; };
  $("#fc").onchange = () => { follow = $("#fc").value === "follow"; if (follow) bear = m.getBearing(); };
  $("#fz").onchange = () => m.setZoom(+$("#fz").value); $("#fpi").onchange = () => m.setPitch(+$("#fpi").value);
  $("#fb").onchange = () => { setStyle($("#fb").value); try { localStorage.setItem("mapstyle3d", $("#fb").value); } catch (e) {} };
  $("#ffs").onclick = () => { const el = $("#fl"); document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen && el.requestFullscreen(); };
  m.on("dragstart", () => { if (follow) { follow = false; $("#fc").value = "free"; } });
  let terr = 0; const DIRECT = {osm: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", topo: "https://tile.opentopomap.org/{z}/{x}/{y}.png", sat: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"};
  m.on("error", e => { console.warn("3D:", e && e.error && e.error.message); if (e.sourceId && DIRECT[e.sourceId] && ++terr === 4) { const sc = m.getSource(e.sourceId); sc && sc.setTiles && sc.setTiles([DIRECT[e.sourceId]]); }
    if (e && e.error && /terrain|dem/i.test(String(e.error.message))) { const g = $("#fmsg"); g.textContent = "Höhendaten nicht erreichbar – Gelände wird flach dargestellt"; g.classList.add("small"); g.style.display = ""; } });
};

/* =====================  Erweiterungen 2: Wetter, Analyse, Vergleich, Hinweise  ===================== */
const GR = [[-1e9, -10, "#2b6cb0", "steil bergab"], [-10, -3, "#63b3ed", "bergab"], [-3, 3, "#68d391", "flach"], [3, 10, "#f6ad55", "bergauf"], [10, 1e9, "#e53e3e", "steil bergauf"]];
const grCol = g => (GR.find(b => g >= b[0] && g < b[1]) || GR[2])[2];
function analyse(c) {   // Pausen, Bewegungszeit, Steigungsabschnitte aus den Streckenpunkten
  const n = c.length, cum = [0]; for (let i = 1; i < n; i++) cum.push(cum[i - 1] + hav(c[i - 1], c[i]));
  const hasT = c[0][3] != null && c[n - 1][3] != null, pauses = [];
  if (hasT) for (let i = 0; i < n - 1;) { let j = i + 1; while (j < n && hav(c[i], c[j]) < 25) j++; const dur = (c[j - 1][3] - c[i][3]) / 1000; if (dur >= 180 && j - 1 > i) { pauses.push({t: c[i][3], dur, lat: c[i][0], lng: c[i][1]}); i = j; } else i++; }
  const total = hasT ? (c[n - 1][3] - c[0][3]) / 1000 : null, pausedS = pauses.reduce((a, p) => a + p.dur, 0);
  const segs = [], band = GR.map(() => 0); let i = 0;
  while (i < n - 1) { let j = i + 1; while (j < n - 1 && cum[j] - cum[i] < 60) j++; const d = cum[j] - cum[i], a0 = c[i][2], a1 = c[j][2];
    if (d > 5) { const g = a0 != null && a1 != null ? (a1 - a0) / d * 100 : 0; segs.push({a: i, b: j, g}); const k = GR.findIndex(b => g >= b[0] && g < b[1]); band[k < 0 ? 2 : k] += d; } i = j; }
  return {cum, pauses, total, pausedS, segs, band, dist: cum[n - 1]};
}
const fmtH = s => { const h = Math.floor(s / 3600), m = Math.round(s % 3600 / 60); return h ? `${h}:${pad2(m)} h` : `${m} min`; };
const _tour2 = VIEWS.tour;
VIEWS.tour = async id => {
  await _tour2(id); const t = BY[id]; if (!t || !$("#profcard")) return;
  // Wetter
  api(`/api/tours/${encodeURIComponent(id)}/weather`).then(w => { const f = document.querySelector("#main .figs"); if (!f || !$("#ksync")) return;
    const ic = w.code >= 95 ? "⛈" : w.code >= 71 && w.code <= 86 ? "❄️" : w.code >= 51 ? "🌧" : w.code >= 45 ? "🌫" : w.code >= 3 ? "☁️" : w.code >= 1 ? "⛅" : "☀️";
    f.insertAdjacentHTML("afterend", `<div class="wx">${ic} <b>${esc(w.text)}</b> · ${nf(w.tmin, 0)}–${nf(w.tmax, 0)} °C · Niederschlag ${nf(w.precip, 1)} mm · Wind bis ${nf(w.wind, 0)} km/h <span class="mut">(Open-Meteo)</span></div>`); }).catch(() => {});
  // Analyse
  const c = cleanPts(await api(`/api/tours/${encodeURIComponent(id)}/coords`).catch(() => [])); if (c.length < 10 || !$("#profcard")) return;
  const A = analyse(c), others = TOURS.filter(o => o.id !== id && o.sport === t.sport).map(o => ({o, s: Math.abs(o.km - t.km) / Math.max(t.km, 1) + (o.lat != null && t.lat != null ? hav([o.lat, o.lng], [t.lat, t.lng]) / 5000 : 5)})).sort((a, b) => a.s - b.s).slice(0, 25);
  const tot = A.dist || 1, box = document.createElement("div"); box.className = "panel"; box.style.margin = "26px 0";
  box.innerHTML = `<h2>Analyse</h2><div class="rows">
    ${A.total ? `<div class="r"><span>Bewegungszeit<small>${A.pauses.length} Pause${A.pauses.length === 1 ? "" : "n"} (ab 3 Min.) mit zusammen ${fmtH(A.pausedS)}</small></span><b>${fmtH(A.total - A.pausedS)}</b></div>
    <div class="r"><span>Ø-Tempo in Bewegung<small>gesamt inkl. Pausen: ${nf(t.km / (A.total / 3600), 1)} km/h</small></span><b>${nf(t.km / Math.max(.01, (A.total - A.pausedS) / 3600), 1)} km/h</b></div>` : ""}</div>
   <h3 style="margin:16px 0 8px;font-size:18px">Steigung (Anteil der Strecke)</h3><div class="stack">${GR.map((b, k) => `<div style="width:${A.band[k] / tot * 100}%;background:${b[2]}" title="${b[3]}"></div>`).join("")}</div>
   <div class="legend">${GR.map((b, k) => `<span><i style="background:${b[2]}"></i>${b[3]} ${nf(A.band[k] / 1000, 1)} km</span>`).join("")}</div>
   <div class="row" style="margin-top:12px"><button class="btn alt sm" id="gtog">Steigung auf der Karte zeigen</button>${A.pauses.length ? `<button class="btn alt sm" id="ptog">Pausen auf der Karte zeigen</button>` : ""}
    <select id="cmp" style="max-width:340px"><option value="">Mit anderer Tour vergleichen …</option>${others.map(x => `<option value="${x.o.id}">${dateS(x.o.date)} · ${esc(x.o.name)} (${nf(x.o.km, 1)} km)</option>`).join("")}</select></div>`;
  $("#profcard").after(box);
  const overlay = {}; const withMap = fn => { let k = 0; const w = () => map && map.addLayer ? fn() : (k++ < 30 && setTimeout(w, 150)); w(); };
  $("#gtog").onclick = e => withMap(() => { if (overlay.g) { map.removeLayer(overlay.g); overlay.g = null; e.target.textContent = "Steigung auf der Karte zeigen"; return; }
    overlay.g = L.layerGroup(A.segs.map(sg => L.polyline(c.slice(sg.a, sg.b + 1).map(p => [p[0], p[1]]), {color: grCol(sg.g), weight: 7, opacity: .95}).bindTooltip(`${nf(sg.g, 0)} % Steigung`))).addTo(map); e.target.textContent = "Steigung ausblenden"; });
  if ($("#ptog")) $("#ptog").onclick = e => withMap(() => { if (overlay.p) { map.removeLayer(overlay.p); overlay.p = null; e.target.textContent = "Pausen auf der Karte zeigen"; return; }
    overlay.p = L.layerGroup(A.pauses.map(p => L.circleMarker([p.lat, p.lng], {radius: 9, color: "#fff", weight: 2, fillColor: "#7b61c9", fillOpacity: 1}).bindTooltip(`Pause ${fmtH(p.dur)}, ${nf(p.t / 60000, 0)} Min. nach dem Start`))).addTo(map); e.target.textContent = "Pausen ausblenden"; });
  $("#cmp").onchange = e => { if (e.target.value) location.hash = `#/compare?a=${encodeURIComponent(id)}&b=${encodeURIComponent(e.target.value)}`; };
};

/* ---- Tourvergleich ---- */
function xyChart(series, o) {
  const W = 560, H = 230, L0 = 46, B = 26, T = 10, xs = series.flatMap(s => s.pts.map(p => p[0])), ys = series.flatMap(s => s.pts.map(p => p[1]));
  const X1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), sp = Math.max(1, y1 - y0), lo = o.zero ? 0 : y0 - sp * .06, hi = y1 + sp * .06;
  const x = v => L0 + (W - L0 - 8) * v / X1, y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}">`;
  [0, .5, 1].forEach(f => { const v = lo + (hi - lo) * f; s += `<line x1="${L0}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)" stroke-dasharray="2 4"/><text x="${L0 - 6}" y="${y(v) + 4}" text-anchor="end">${o.fy ? o.fy(v) : nf(v, 0)}</text>`; });
  for (let k = 0; k <= 4; k++) s += `<text x="${x(X1 * k / 4)}" y="${H - 6}" text-anchor="${k === 4 ? "end" : k === 0 ? "start" : "middle"}">${nf(X1 * k / 4, 0)} km</text>`;
  series.forEach(se => s += `<path d="${se.pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("")}" fill="none" stroke="${se.color}" stroke-width="2.6"/>`);
  return s + "</svg>";
}
VIEWS.compare = async (_, q) => {
  const ta = BY[q.get("a")], tb = BY[q.get("b")]; if (!ta || !tb) throw new Error("Touren zum Vergleichen nicht gefunden");
  const [ca, cb] = (await Promise.all([ta, tb].map(t => api(`/api/tours/${encodeURIComponent(t.id)}/coords`).then(cleanPts).catch(() => [])))), cols = ["#e2b13c", "#3a86c8"];
  const info = (t, c) => { const A = c.length > 9 ? analyse(c) : null; return {km: t.km, up: t.up_m || 0, h: t.h, v: t.km / (t.h || 1), moving: A && A.total ? (A.total - A.pausedS) / 3600 : null, pauses: A ? A.pauses.length : null, A}; };
  const a = info(ta, ca), b = info(tb, cb), d = (x, y, u, dg = 1) => { const v = y - x; return `<span>${v > 0 ? "+" : v < 0 ? "−" : ""}${nf(Math.abs(v), dg)} ${u}</span>`; };
  const row = (l, x, y, u, dg = 1) => x == null || y == null ? "" : `<tr><td>${l}</td><td class="n">${nf(x, dg)} ${u}</td><td class="n">${nf(y, dg)} ${u}</td><td class="n">${d(x, y, u, dg)}</td></tr>`;
  const alt = (c, A) => c.map((p, i) => [A.cum[i] / 1000, p[2] ?? 0]), tim = (c, A) => c.map((p, i) => [A.cum[i] / 1000, (p[3] ?? 0) / 60000]);
  const hasT = ca[0] && ca[0][3] != null && cb[0] && cb[0][3] != null;
  $("#main").innerHTML = `<div class="row"><a class="back" href="#/tour/${ta.id}">‹ ${esc(ta.name)}</a></div><div class="sec"><h2>Tourvergleich</h2></div>
   <div class="legend" style="margin-bottom:10px"><span><i style="background:${cols[0]}"></i><a href="#/tour/${ta.id}">${esc(ta.name)}</a> (${dateS(ta.date)})</span><span><i style="background:${cols[1]}"></i><a href="#/tour/${tb.id}">${esc(tb.name)}</a> (${dateS(tb.date)})</span></div>
   <div class="grid g2"><div id="cm" class="cmap"></div><div><table class="cmp"><tr><th></th><th class="n">A</th><th class="n">B</th><th class="n">B − A</th></tr>
    ${row("Strecke", a.km, b.km, "km")}${row("Aufstieg", a.up, b.up, "m", 0)}${row("Dauer", a.h, b.h, "h", 2)}${row("Ø-Tempo gesamt", a.v, b.v, "km/h")}${row("Bewegungszeit", a.moving, b.moving, "h", 2)}${row("Pausen", a.pauses, b.pauses, "", 0)}</table>
    <div class="panel" style="margin-top:20px"><h3>Höhenprofil</h3>${ca.length > 2 && cb.length > 2 ? xyChart([{pts: alt(ca, a.A), color: cols[0]}, {pts: alt(cb, b.A), color: cols[1]}], {fy: v => nf(v, 0) + " m"}) : "<div class='mut'>keine Höhendaten</div>"}</div></div></div>
   ${hasT ? `<div class="panel" style="margin-top:30px"><h3>Zeit über Strecke</h3><p class="mut" style="font-size:14px">Wo die Linien auseinanderlaufen, war eine Tour schneller (flacher = schneller, Stufen = Pausen).</p>${xyChart([{pts: tim(ca, a.A), color: cols[0]}, {pts: tim(cb, b.A), color: cols[1]}], {zero: true, fy: v => fmtH(v * 60)})}</div>` : ""}`;
  map = mkMap("cm", {layers: true}); const g = L.featureGroup([ca, cb].map((c, i) => L.polyline(c.map(p => [p[0], p[1]]), {color: cols[i], weight: 5, opacity: .9}).addTo(map))); if (g.getLayers().length && g.getBounds().isValid()) map.fitBounds(g.getBounds(), {padding: [24, 24]});
};

/* ---- Hinweis: Zepp-Token + Verwaltung (Selbsttest, Eingang, Zepp-Status) ---- */
const _dash3 = VIEWS.dash;
VIEWS.dash = async (n, q) => {
  await _dash3(n, q); const st = await api("/api/status").catch(() => null), inner = $(".inner");
  if (st && st.zepp && /^fail/.test(st.zepp.state) && inner) inner.insertAdjacentHTML("afterbegin", `<div class="notice">⚠ Der Zepp-Zugang funktioniert nicht mehr (Token abgelaufen?). <a href="#/admin">In der Verwaltung ein neues Token holen</a>, damit neue Zepp-Trainings weiter geprüft werden können.</div>`);
};
const _adm3 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm3(...a); const st = await api("/api/status").catch(() => ({})), sv = $("#save"); if (!sv) return;
  const z = st.zepp || {}, age = z.token_ts ? Math.floor((Date.now() / 1000 - +z.token_ts) / 86400) : null;
  const zr = $("#ztest"); if (zr) zr.closest(".row").insertAdjacentHTML("afterend", `<p class="mut" style="font-size:14px;margin:-4px 0 8px">${z.state === "ok" ? "✓ Token gültig" : /^fail/.test(z.state || "") ? `<span class="bad">✗ Token ungültig: ${esc(z.state.slice(5))}</span>` : z.state === "none" ? "Kein Token gespeichert" : "Token noch nicht geprüft"}${age != null ? ` · gespeichert vor ${age} Tag${age === 1 ? "" : "en"}` : ""}${z.checked ? ` · zuletzt geprüft ${new Date(+z.checked * 1000).toLocaleString("de-DE")}` : ""} (wird täglich mitgeprüft)</p>`);
  sv.closest(".row").insertAdjacentHTML("beforebegin", `<div class="grid g2" style="margin-top:40px"><div class="panel"><h2>Foto-Eingang</h2>
    <p class="mut">Fotos einfach in den Eingangsordner kopieren (per <code>scp</code>, <code>rsync</code> oder SMB-Freigabe): <code>${esc(st.inbox || "/var/lib/meine-touren/inbox")}</code>. Sie werden automatisch verkleinert, mit Aufnahmezeit übernommen und Touren zugeordnet (Prüfung alle 5 Minuten).</p>
    <p class="mut" style="font-size:13px">Beispiel vom Mac: <code>rsync -av ~/Pictures/Wanderung/ root@SERVER:${esc(st.inbox || "/var/lib/meine-touren/inbox")}/</code></p></div>
   <div class="panel"><h2>Wanderführer (z. B. Rother)</h2><p class="mut">Lade die GPX-Dateien deiner Wanderführer hoch (bei Rother im Download-Bereich zum Buch). Folgt eine Tour einer dieser Strecken, wird der Tourtitel aus dem Buch beim Umbenennen vorgeschlagen.</p>
    <div class="field"><label>Buch (z. B. „Rother Taunus“)</label><input id="gbook"></div>
    <div class="row"><button class="btn" id="gup">GPX-Dateien auswählen …</button><input type="file" id="gfile" accept=".gpx" multiple hidden><span id="gres" class="mut"></span></div><div id="glist" style="margin-top:10px"></div></div>
   <div class="panel"><h2>Selbsttest</h2><p class="mut">Prüft Komoot-Zugang, Strecken, Zepp-Token, Internet-Dienste (Karten, Wetter, Höhendaten), Speicherplatz und Backup.</p>
    <div class="row"><button class="btn alt" id="stest">Selbsttest starten</button></div><div id="stres" style="margin-top:10px"></div></div></div>`);
  const gl = async () => { const g = await api("/api/guides").catch(() => []), by = {}; g.forEach(x => (by[x.book] ||= []).push(x));
    $("#glist").innerHTML = Object.keys(by).map(b => `<div class="r" style="display:flex;justify-content:space-between;gap:8px"><span>${esc(b || "(ohne Buch)")} <small class="mut">${by[b].length} Touren</small></span><button class="btn alt sm" data-gb="${esc(b)}">Entfernen</button></div>`).join("") || '<span class="mut">Noch keine Wanderführer hinterlegt.</span>';
    document.querySelectorAll("[data-gb]").forEach(b => b.onclick = async () => { if (confirm("Alle Touren dieses Buchs entfernen?")) { await api("/api/guides/" + encodeURIComponent("book:" + b.dataset.gb), {method: "DELETE"}); gl(); } }); };
  $("#gup").onclick = () => $("#gfile").click();
  $("#gfile").onchange = async e => { const fs = [...e.target.files]; if (!fs.length) return; $("#gres").textContent = "Lese " + fs.length + " Dateien …";
    const items = await Promise.all(fs.map(f => f.text().then(gpx => ({name: f.name, gpx}))));
    try { const r = await api("/api/guides", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({book: $("#gbook").value, items})});
      $("#gres").textContent = `${r.added} hinzugefügt${r.failed.length ? ", " + r.failed.length + " fehlgeschlagen: " + r.failed[0] : ""}`; } catch (x) { $("#gres").textContent = x.message; }
    e.target.value = ""; gl(); };
  gl();
  $("#stest").onclick = async () => { $("#stres").textContent = "Prüfe … (kann bis zu einer Minute dauern)"; $("#stest").disabled = true;
    try { const r = await api("/api/selftest", {method: "POST"}); $("#stres").innerHTML = `<div class="rows">${r.map(x => `<div class="r"><span>${x.ok ? "✓" : "✗"} ${esc(x.name)}<small class="${x.ok ? "" : "bad"}">${esc(x.detail)}</small></span></div>`).join("")}</div>`; }
    catch (e) { $("#stres").innerHTML = `<span class="bad">${esc(e.message)}</span>`; } $("#stest").disabled = false; };
};

/* ---- Übersicht: durch die letzten Touren zappen ---- */
const _dashZ = VIEWS.dash;
VIEWS.dash = async (...a) => {
  await _dashZ(...a);
  const hero = $(".hero"); if (!hero || TOURS.length < 2) return;
  const N = Math.min(10, TOURS.length); let i = 0, tok = 0, auto = null;
  hero.insertAdjacentHTML("beforeend", `<button class="hnav" id="hprev" aria-label="Neuere Tour" title="Neuere Tour (←)">‹</button><button class="hnav r" id="hnext" aria-label="Ältere Tour" title="Ältere Tour (→)">›</button>
    <div class="hdots" id="hdots"><button class="hpl" id="hpl" title="Automatisch weiterschalten">▶</button><span id="hcnt"></span></div>`);
  const k = hero.querySelector(".k"), h1 = hero.querySelector("h1"), w = hero.querySelector(".w"), btns = hero.querySelector(".btns"), signs = hero.querySelector(".signs");
  const show = async n => {
    i = (n + N) % N; const t = TOURS[i], my = ++tok;
    k.textContent = (i ? `${i + 1}. letzte Tour` : "Letzte Tour") + ", " + sName(t.sport); h1.textContent = t.name; w.textContent = `${dateL(t.date)}, ${timeS(t.date)} Uhr`;
    btns.innerHTML = `<a class="btn" href="#/tour/${t.id}">Tour ansehen</a>${t.photos ? `<a class="btn alt" style="color:#fff" target="_blank" href="slideshow.html?tour=${t.id}">Diashow</a>` : ""}`;
    signs.innerHTML = `<div class="sign">${nf(t.km, 1)}<small>Kilometer</small></div><div class="sign l">${nf(t.up_m, 0)}<small>Meter aufwärts</small></div><div class="sign">${nf(t.h, 1)}<small>Stunden</small></div>`;
    $("#hcnt").textContent = `${i + 1} / ${N}`;
    const old = hero.querySelector(".thumbrow"); if (old) old.remove();
    const [ph, c] = await Promise.all([t.photos ? api(`/api/photos?tour_id=${t.id}&limit=4`).catch(() => []) : [], api(`/api/tours/${t.id}/coords`).catch(() => null)]);
    if (my !== tok || !hero.isConnected) return;
    if (ph.length) { w.insertAdjacentHTML("afterend", `<div class="thumbrow">${ph.map((p, x) => `<img loading="lazy" src="/photo/${p.id}?size=300" data-i="${x}">`).join("")}</div>`); bindThumbs(hero.querySelector(".thumbrow"), ph); }
    if (map) { map.eachLayer(l => { if (l instanceof L.Polyline) map.removeLayer(l); });
      const pts = cleanPts(c || []).map(p => [p[0], p[1]]);
      if (pts.length > 1) { const l = L.polyline(pts, {color: "#f2c230", weight: 5}).addTo(map); map.fitBounds(l.getBounds(), {paddingTopLeft: [window.innerWidth > 900 ? 640 : 40, 40], paddingBottomRight: [40, 40]}); }
      else if (t.lat) map.setView([t.lat, t.lng], 12); }
  };
  $("#hprev").onclick = () => show(i - 1); $("#hnext").onclick = () => show(i + 1);
  $("#hpl").onclick = e => { if (auto) { clearInterval(auto); auto = null; e.target.textContent = "▶"; } else { e.target.textContent = "⏸"; auto = setInterval(() => { if (!hero.isConnected) { clearInterval(auto); return; } show(i + 1); }, 6000); } };
  const key = e => { if (!hero.isConnected) { document.removeEventListener("keydown", key); return; } if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "") || $(".modal")) return;
    if (e.key === "ArrowLeft") show(i - 1); else if (e.key === "ArrowRight") show(i + 1); };
  document.addEventListener("keydown", key);
  let sx = null; hero.addEventListener("touchstart", e => { sx = e.touches[0].clientX; }, {passive: true});
  hero.addEventListener("touchend", e => { if (sx == null) return; const dx = e.changedTouches[0].clientX - sx; sx = null; if (Math.abs(dx) > 60) show(i + (dx < 0 ? 1 : -1)); }, {passive: true});
  $("#hcnt").textContent = `1 / ${N}`;
};


/* =====================  Prüfen / Aufräumen  ===================== */
VIEWS.check = async () => {
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Prüfen &amp; Aufräumen</h2><span class="sub" id="chs"></span></div><div id="chb" class="mut">Wird geprüft …</div>`;
  const r = await api("/api/check"), G = r.gaps, body = $("#chb"); body.className = "";
  const nm = id => BY[id] ? `<a href="#/tour/${id}">${esc(BY[id].name)}</a> <span class="mut">${BY[id].km.toFixed(1)} km</span>` : esc(id);
  body.innerHTML = `
   <div class="panel"><h2>Überblick</h2><div class="rows">
    <div class="r"><span>Touren insgesamt</span><b>${r.total}</b></div>
    <div class="r"><span>Mögliche Duplikate</span><b class="${r.duplicates.length ? "bad" : ""}">${r.duplicates.length}</b></div>
    <div class="r"><span>Auffällige Höhenmeter</span><b class="${r.suspicious.length ? "bad" : ""}">${r.suspicious.length}</b></div>
    <div class="r"><span>Noch mit Standardname</span><b>${r.default_names.length}</b></div>
    <div class="r"><span>Ohne gespeicherte Strecke / ohne Region / ohne Fotos</span><b>${G.no_route} / ${G.no_region} / ${G.no_photos}</b></div></div>
    <p class="mut" style="font-size:13px">Fehlende Strecken: Verwaltung → „Routen laden“. Fehlende Regionen: „Regionen bestimmen“.</p></div>
   <div class="panel" style="margin-top:22px"><h2>Mögliche Duplikate</h2>${r.duplicates.length ? `<div class="rows">${r.duplicates.map(d => `<div class="r" style="display:block">${nm(d.a)}<br>${nm(d.b)}<small class="mut">${BY[d.a] ? dateS(BY[d.a].date) : ""} – gleiche Zeit, Startort und Länge</small></div>`).join("")}</div><p class="mut" style="font-size:13px">Zum Löschen die Tour bei Komoot entfernen und dann „Komoot aktualisieren“ ausführen.</p>` : '<p class="ok">✓ Keine Duplikate gefunden.</p>'}</div>
   <div class="panel" style="margin-top:22px"><h2>Auffällige Höhenmeter</h2>${r.suspicious.length ? `<div class="row"><button class="btn" id="fixall">Alle ${r.suspicious.length} korrigieren</button><span id="fixm" class="mut"></span></div><div class="rows" id="fixl">${r.suspicious.map(t => `<div class="r" data-id="${t.id}"><span>${nm(t.id)}<small class="bad">${nf(t.up_m, 0)} m Aufstieg auf ${nf(t.km, 1)} km</small></span><button class="btn alt sm" data-fix="${t.id}">Korrigieren</button></div>`).join("")}</div>` : '<p class="ok">✓ Keine auffälligen Höhen.</p>'}</div>
   <div class="panel" style="margin-top:22px"><h2>Namen vergeben</h2>${r.default_names.length ? `<p class="mut">${r.default_names.length} Touren heißen noch wie vorgegeben. Mit „Vorschläge laden“ werden Namen aus Karte, Routen und Wanderführern vorbelegt; gespeichert wird erst mit „Speichern“.</p>
    <div class="row"><button class="btn" id="sugall">Vorschläge für die nächsten 10 laden</button><label class="chk" style="margin:0"><input type="checkbox" id="rkomall"> auch bei Komoot umbenennen</label><span id="sugm" class="mut"></span></div>
    <div class="rows" id="nml">${r.default_names.map(t => `<div class="r nm" data-id="${t.id}" style="display:block"><div class="mut" style="font-size:13px">${dateS(BY[t.id]?.date || "0000-00-00")} · ${esc(sName(t.sport))} · ${t.km} km · <a href="#/tour/${t.id}">öffnen</a></div>
      <div class="row" style="margin:4px 0"><input class="nin" value="${esc(t.name)}" style="flex:1;min-width:220px"><button class="btn alt sm" data-sug="${t.id}">💡</button><button class="btn sm" data-save="${t.id}">Speichern</button></div><div class="chips sugs"></div></div>`).join("")}</div>` : '<p class="ok">✓ Alle Touren haben einen eigenen Namen.</p>'}</div>`;
  const fix1 = async id => { const b = body.querySelector(`[data-fix="${id}"]`); if (b) { b.disabled = true; b.textContent = "…"; }
    try { const x = await api(`/api/tours/${encodeURIComponent(id)}/elev-fix`, {method: "POST"}); if (b) b.closest(".r").innerHTML = `<span>${nm(id)}<small class="ok">korrigiert: ${nf(x.up_m, 0)} m Aufstieg (vorher ${nf(x.orig_up, 0)} m)</small></span>`; return true; }
    catch (e) { if (b) { b.disabled = false; b.textContent = "Fehler – nochmal"; b.title = e.message; } return false; } };
  body.querySelectorAll("[data-fix]").forEach(b => b.onclick = async () => { await fix1(b.dataset.fix); loadTours(); });
  if ($("#fixall")) $("#fixall").onclick = async e => { e.target.disabled = true; let n = 0; for (const t of r.suspicious) { $("#fixm").textContent = `Korrigiere ${++n}/${r.suspicious.length} …`; await fix1(t.id); } $("#fixm").textContent = "Fertig."; await loadTours(); };
  const sug = async row => { const id = row.dataset.id, box = row.querySelector(".sugs"), inp = row.querySelector(".nin"); box.innerHTML = '<span class="mut">Suche …</span>';
    try { const s = (await api(`/api/tours/${encodeURIComponent(id)}/name-suggestions?part=all`)).suggestions; box.innerHTML = "";
      if (!s.length) { box.innerHTML = '<span class="mut">Keine Vorschläge.</span>'; return; }
      if (DEFAULT_RX.test(inp.value)) inp.value = s[0];
      s.forEach(x => { const b = document.createElement("button"); b.type = "button"; b.className = "btn alt sm"; b.textContent = x; b.onclick = () => { inp.value = x; }; box.appendChild(b); });
    } catch (e) { box.innerHTML = `<span class="mut">Keine Vorschläge (${esc(e.message)})</span>`; } };
  const DEFAULT_RX = /\d{2}\.\d{2}\.\d{4}/;
  body.querySelectorAll("[data-sug]").forEach(b => b.onclick = () => sug(b.closest(".nm")));
  body.querySelectorAll("[data-save]").forEach(b => b.onclick = async () => { const row = b.closest(".nm"), nn = row.querySelector(".nin").value.trim(); if (!nn) return; b.disabled = true;
    try { const x = await api(`/api/tours/${encodeURIComponent(b.dataset.save)}/rename`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({name: nn, komoot: $("#rkomall").checked})});
      row.innerHTML = `<span class="ok">✓ ${esc(nn)}</span>${$("#rkomall").checked && !x.komoot ? ` <span class="bad">(bei Komoot nicht geklappt: ${esc(x.warning || "")})</span>` : ""}`; if (BY[b.dataset.save]) BY[b.dataset.save].name = nn;
    } catch (e) { b.disabled = false; alert("Umbenennen fehlgeschlagen: " + e.message); } });
  if ($("#sugall")) $("#sugall").onclick = async e => { e.target.disabled = true; const rows = [...body.querySelectorAll(".nm")].filter(x => !x.querySelector(".sugs").children.length).slice(0, 10); let n = 0;
    for (const row of rows) { $("#sugm").textContent = `Lade ${++n}/${rows.length} …`; await sug(row); } $("#sugm").textContent = rows.length ? "Fertig – bitte prüfen und speichern." : "Alle schon geladen."; e.target.disabled = false; };
};

/* =====================  Orte & Gipfel, Wanderführer  ===================== */
VIEWS.places = async () => {
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Auswertung</h2><span class="sub">Orte, Gipfel, Leistung, Wetter, Neuland</span></div><div id="plb" class="mut">Wird geladen …</div>`;
  const [p, gp] = await Promise.all([api("/api/places"), api("/api/guides/progress").catch(() => [])]), box = $("#plb"); box.className = "";
  const mx = Math.max(1, ...p.starts.map(s => s.n));
  box.innerHTML = `<div class="grid g2">
   <div class="panel"><h2>Häufigste Startorte</h2>${p.starts.length ? `<div class="rows">${p.starts.map(s => `<div class="r"><span><a href="#/search?q=${encodeURIComponent(s.place)}">${esc(s.place)}</a><small>${esc(s.state || "")} · ${nf(s.km, 0)} km</small></span><b>${s.n}×</b></div>`).join("")}</div>` : '<p class="mut">Noch keine Regionen bestimmt: Verwaltung → „Regionen bestimmen“.</p>'}</div>
   <div class="panel"><h2>Gipfel &amp; Pässe</h2>${p.peaks.length ? `<div class="rows">${p.peaks.map(s => `<div class="r"><span>${esc(s.name)}<small>${s.alt ? nf(s.alt, 0) + " m · " : ""}${s.tours.slice(0, 4).map(id => `<a href="#/tour/${id}">${BY[id] ? dateS(BY[id].date) : id}</a>`).join(", ")}${s.tours.length > 4 ? " …" : ""}</small></span><b>${s.n}×</b></div>`).join("")}</div>` : '<p class="mut">Noch keine Gipfel bestimmt.</p>'}
    <div class="row" style="margin-top:12px"><button class="btn alt" id="pkb">Gipfel bestimmen${p.pending_peaks ? ` (${p.pending_peaks} Touren offen)` : ""}</button><span id="pkm" class="mut"></span></div></div></div>
   <div class="sec"><h2>Wanderführer-Fortschritt</h2></div>
   ${gp.length ? gp.map(b => `<div class="panel" style="margin-bottom:16px"><h2>${esc(b.book)} <span class="mut" style="font:500 16px var(--b)">${b.done} von ${b.total} gewandert</span></h2>
     <div class="stack" style="height:10px;margin:8px 0 12px"><div style="width:${b.total ? 100 * b.done / b.total : 0}%;background:var(--acc)"></div></div>
     <div class="rows">${b.tours.map(x => `<div class="r"><span>${x.tour ? "✓" : "○"} ${esc(x.title)}</span>${x.tour ? `<a href="#/tour/${x.tour}">${BY[x.tour] ? dateS(BY[x.tour].date) : "Tour"}</a>` : '<span class="mut">offen</span>'}</div>`).join("")}</div></div>`).join("") : '<p class="mut">Noch keine Wanderführer hinterlegt: Verwaltung → „Wanderführer“ (GPX-Dateien hochladen).</p>'}`;
  $("#pkb").onclick = async e => { e.target.disabled = true; try { await api("/api/jobs/peaks", {method: "POST"}); $("#pkm").textContent = "Läuft im Hintergrund (ca. 1 Sekunde pro Tour). Seite später neu öffnen."; } catch (x) { $("#pkm").textContent = x.message; e.target.disabled = false; } };
};

/* ---- Übersicht: Jahrestag mit Foto ---- */
const _dashJ = VIEWS.dash;
VIEWS.dash = async (...a) => {
  await _dashJ(...a);
  const h = [...document.querySelectorAll("#main .sec h2")].find(x => x.textContent === "An diesem Tag"); if (!h) return;
  const now = new Date(), md = `${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`, ot = TOURS.filter(t => t.date.slice(5, 10) === md && t.y !== now.getFullYear()).slice(0, 3);
  const cards = await Promise.all(ot.map(async t => { const ph = t.photos ? await api(`/api/photos?tour_id=${t.id}&limit=1`).catch(() => []) : [];
    return `<a class="otd" href="#/tour/${t.id}" style="${ph[0] ? `background-image:linear-gradient(transparent 40%,#000b),url(/photo/${ph[0].id}?size=600)` : ""}"><b>Vor ${now.getFullYear() - t.y} ${now.getFullYear() - t.y === 1 ? "Jahr" : "Jahren"}</b><span>${esc(t.name)}</span><small>${nf(t.km, 1)} km · ${nf(t.up_m, 0)} m</small></a>`; }));
  const sec = h.closest(".sec"); if (sec && cards.length && !sec.nextElementSibling?.classList.contains("otdg")) sec.insertAdjacentHTML("afterend", `<div class="otdg">${cards.join("")}</div>`);
};

/* =====================  Tags, Teilen, Neuland (Tourdetail)  ===================== */
const modal = html => { const m = document.createElement("div"); m.className = "modal"; m.innerHTML = `<div class="mbox">${html}</div>`; document.body.appendChild(m); m.onclick = e => { if (e.target === m) m.remove(); return m; }; return m; };
const _tourT = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourT(id, q); const t = BY[id]; if (!t || !$("#etag")) return;
  const showTags = () => { $("#tagl").innerHTML = (t.tags || "").split("|").filter(Boolean).map(x => `<a class="chip on" href="#/album/${encodeURIComponent(x)}" style="text-decoration:none">🏷 ${esc(x)}</a>`).join(""); };
  showTags();
  $("#etag").onclick = () => {
    let cur = (t.tags || "").split("|").filter(Boolean);
    const m = modal(`<h3>Tags &amp; Alben</h3><p class="mut" style="font-size:14px">Mit Schlagworten wie „Urlaub Réunion 2026“ oder „Rother Taunus“ entsteht ein Album mit eigener Seite (Karte, Summen, Fotos, 3D-Flug).</p>
      <div id="tgc" class="chips"></div><input id="tgi" list="tgl" placeholder="Neuer Tag + Enter" style="width:100%;margin-top:10px"><datalist id="tgl">${allTags().map(x => `<option value="${esc(x)}">`).join("")}</datalist>
      <div class="row" style="justify-content:flex-end;margin-top:16px"><button class="btn alt" id="tgx">Abbrechen</button><button class="btn" id="tgs">Speichern</button></div>`);
    const draw = () => { m.querySelector("#tgc").innerHTML = cur.map((x, i) => `<button class="chip on" data-i="${i}" title="Entfernen">${esc(x)} ×</button>`).join("") || '<span class="mut">Noch keine Tags</span>'; m.querySelectorAll("[data-i]").forEach(b => b.onclick = () => { cur.splice(+b.dataset.i, 1); draw(); }); };
    draw(); const inp = m.querySelector("#tgi"); inp.focus();
    const add = () => { const v = inp.value.trim(); if (v && !cur.includes(v)) cur.push(v); inp.value = ""; draw(); };
    inp.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); add(); } }; inp.onchange = add;
    m.querySelector("#tgx").onclick = () => m.remove();
    m.querySelector("#tgs").onclick = async () => { add(); try { const r = await api(`/api/tours/${encodeURIComponent(t.id)}/tags`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({tags: cur})}); t.tags = r.tags.join("|"); showTags(); m.remove(); } catch (e) { alert(e.message); } };
  };
  $("#eshr").onclick = async () => {
    const m = modal(`<h3>Tour teilen</h3><p class="mut" style="font-size:14px">Erzeugt einen Link, den man <b>ohne Anmeldung</b> öffnen kann (Karte, Zahlen, optional Fotos). Er funktioniert nur, wenn dein Server von außen erreichbar ist, z. B. per VPN oder Reverse-Proxy.</p>
      <label class="chk"><input type="checkbox" id="shp"> Fotos mitsenden</label><label class="chk"><input type="checkbox" id="sht" checked> Anfang und Ende (300 m) ausblenden – schützt deinen Wohnort</label>
      <div class="row" style="margin-top:14px"><button class="btn" id="shn">Link erstellen</button></div><div id="shl" style="margin-top:14px"></div><div class="row" style="justify-content:flex-end;margin-top:12px"><button class="btn alt" id="shx">Schließen</button></div>`);
    m.querySelector("#shx").onclick = () => m.remove();
    const list = async () => { const s = await api(`/api/tours/${encodeURIComponent(t.id)}/shares`).catch(() => []);
      m.querySelector("#shl").innerHTML = s.map(x => { const u = location.origin + "/s/" + x.token; return `<div class="r" style="display:block;border-top:1px solid var(--rule);padding:8px 0"><input readonly value="${esc(u)}" style="width:100%" onclick="this.select()"><small class="mut">${x.photos ? "mit Fotos" : "ohne Fotos"}${x.trim ? ", Anfang/Ende ausgeblendet" : ""}</small> <button class="btn alt sm" data-cp="${esc(u)}">Kopieren</button> <button class="btn alt sm" data-rv="${x.token}">Widerrufen</button></div>`; }).join("") || '<span class="mut">Noch kein Link.</span>';
      m.querySelectorAll("[data-cp]").forEach(b => b.onclick = async () => { try { await navigator.clipboard.writeText(b.dataset.cp); b.textContent = "✓"; } catch (e) { b.previousElementSibling; } });
      m.querySelectorAll("[data-rv]").forEach(b => b.onclick = async () => { await api("/api/share/" + b.dataset.rv, {method: "DELETE"}); list(); }); };
    m.querySelector("#shn").onclick = async () => { await api(`/api/tours/${encodeURIComponent(t.id)}/share`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({photos: m.querySelector("#shp").checked, trim: m.querySelector("#sht").checked})}); list(); };
    list();
  };
  api("/api/newground").then(n => { const r = n.tours[t.id], f = $("#main .figs"); if (!r || !f) return;
    f.insertAdjacentHTML("beforeend", `<div class="fig" title="Anteil der Strecke, der auf keiner früheren Tour lag"><div class="v">${r.pct}<span class="u">%</span></div><div class="l">Neuland (${nf(r.new_km, 1)} km)</div></div>`); }).catch(() => {});
};

/* =====================  Sammlungen: Reisen & Alben  ===================== */
const DAYC = ["#e11d74", "#f2c230", "#00a6d6", "#7cc43a", "#ff6a1a", "#8e5bd6", "#16a085", "#c0392b"];
async function collView(title, sub, ids, back) {
  const ts = ids.map(i => BY[i]).filter(Boolean).sort((a, b) => a.start_ts - b.start_ts), sum = f => ts.reduce((c, t) => c + f(t), 0);
  const days = [...new Set(ts.map(t => t.date.slice(0, 10)))];
  $("#main").innerHTML = `<div class="row"><a class="back" href="${back}">‹ Zurück</a></div><div class="sec" style="margin-top:12px"><h1 style="font-size:clamp(30px,5vw,52px)">${esc(title)}</h1></div><div class="mut">${esc(sub)}</div>
   <div class="figs" style="margin-top:14px"><div class="fig"><div class="v">${ts.length}</div><div class="l">Touren</div></div><div class="fig"><div class="v">${nf(sum(t => t.km), 0)}<span class="u">km</span></div><div class="l">Strecke</div></div>
    <div class="fig"><div class="v">${nf(sum(t => t.up_m || 0), 0)}<span class="u">m</span></div><div class="l">Aufstieg</div></div><div class="fig"><div class="v">${nf(sum(t => t.h), 0)}<span class="u">h</span></div><div class="l">Unterwegs</div></div><div class="fig"><div class="v">${days.length}</div><div class="l">Tage</div></div></div>
   <div class="row" style="margin:6px 0 12px"><a class="btn" href="#/flight/${encodeURIComponent("set:" + ts.map(t => t.id).join(","))}">3D-Flug über alles</a><button class="btn alt" id="coff" title="Kartenkacheln dieser Strecken zwischenspeichern">Karte offline speichern</button><span id="cofm" class="mut"></span></div>
   <div class="tmap" id="cm" style="height:460px"></div><div class="sec"><h2>Fotos</h2></div><div class="thumbs" id="cph"></div><div class="sec"><h2>Touren</h2></div><div class="tl">${ts.map(tourRow).join("")}</div>`;
  map = mkMap("cm", {layers: true}); const fg = L.featureGroup().addTo(map);
  const co = await Promise.all(ts.map(t => api(`/api/tours/${t.id}/coords`).catch(() => [])));
  ts.forEach((t, i) => { const p = cleanPts(co[i]).map(x => [x[0], x[1]]); if (p.length > 1) L.polyline(p, {color: DAYC[days.indexOf(t.date.slice(0, 10)) % DAYC.length], weight: 4}).bindTooltip(`${dateS(t.date)} · ${esc(t.name)}`).addTo(fg); });
  if (fg.getLayers().length) map.fitBounds(fg.getBounds(), {padding: [30, 30]}); else map.setView([50, 9], 6);
  Promise.all(ts.slice(0, 14).map(t => t.photos ? api(`/api/photos?tour_id=${t.id}&limit=6`).catch(() => []) : [])).then(a => { const ph = a.flat(); if (!$("#cph")) return;
    $("#cph").innerHTML = ph.map((p, i) => `<img loading="lazy" src="/photo/${p.id}?size=300" data-i="${i}">`).join("") || '<span class="mut">Keine Fotos.</span>'; bindThumbs($("#cph"), ph); });
  const plan = await api(`/api/tiles/plan?ids=${ts.map(t => t.id).join(",")}`).catch(() => null);
  if (plan) $("#cofm").textContent = plan.missing ? `${plan.missing} von ${plan.total} Kacheln fehlen noch (ca. ${Math.ceil(plan.missing / 60)} Min.)` : "✓ Karte ist offline verfügbar";
  $("#coff").onclick = async e => { e.target.disabled = true; try { await api("/api/tiles/prefetch", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({ids: ts.map(t => t.id)})}); $("#cofm").textContent = "Läuft im Hintergrund (1 Kachel/Sekunde, höchstens 1500). Danach Seite neu öffnen."; } catch (x) { $("#cofm").textContent = x.message; e.target.disabled = false; } };
}
VIEWS.trips = async () => {
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Reisen</h2><span class="sub">automatisch erkannt: Touren weit weg von zu Hause an aufeinanderfolgenden Tagen</span></div><div id="tr" class="mut">Wird geladen …</div>`;
  const [tr, tg] = await Promise.all([api("/api/trips"), api("/api/tags")]); $("#tr").className = "";
  $("#tr").innerHTML = (tr.length ? `<div class="otdg">${tr.map(x => `<a class="otd" href="#/trip/${x.id}" style="background-image:linear-gradient(#0e2a2b99,#0e2a2bee)"><b>${esc(x.region)}</b><span>${dateS(x.start)}${x.end !== x.start ? " – " + dateS(x.end) : ""}</span><small>${x.tours.length} Touren · ${nf(x.km, 0)} km · ${nf(x.up_m, 0)} m</small></a>`).join("")}</div>` : '<p class="mut">Keine Reisen erkannt (es braucht mindestens zwei Touren am Stück, über 60 km von deinem üblichen Startort entfernt). Eigene Gruppen legst du mit Tags an.</p>')
   + `<div class="sec"><h2>Alben &amp; Tags</h2><span class="sub">in der Tour über „🏷 Tags“ vergeben</span></div>` + (tg.length ? `<div class="otdg">${tg.map(x => `<a class="otd" href="#/album/${encodeURIComponent(x.tag)}"><b>🏷 ${esc(x.tag)}</b><small>${x.n} Touren · ${nf(x.km, 0)} km</small></a>`).join("")}</div>` : '<p class="mut">Noch keine Tags vergeben.</p>');
};
VIEWS.trip = async id => { const tr = (await api("/api/trips")).find(x => x.id === id); if (!tr) throw new Error("Reise nicht gefunden");
  await collView(`${tr.region}${tr.country && tr.country !== tr.region ? ", " + tr.country : ""}`, `${dateL(tr.start)}${tr.end !== tr.start ? " – " + dateL(tr.end) : ""}`, tr.tours, "#/trips"); };
VIEWS.album = async tag => { tag = decodeURIComponent(tag || ""); const ts = TOURS.filter(t => (t.tags || "").split("|").includes(tag)); if (!ts.length) throw new Error("Album ist leer");
  await collView("🏷 " + tag, `Album mit ${ts.length} Touren`, ts.map(t => t.id), "#/trips"); };

/* =====================  Auswertung: Leistung, Wetter, Neuland  ===================== */
function yearChart(series, xs, unit) {
  const W = 560, H = 200, L0 = 44, B = 26, T = 10, all = series.flatMap(s => s.v.filter(v => v != null)); if (!all.length) return "";
  const mx = Math.max(...all) * 1.1, mn = Math.min(0, ...all), X = i => L0 + i * (W - L0 - 12) / Math.max(1, xs.length - 1), Y = v => T + (H - T - B) * (1 - (v - mn) / ((mx - mn) || 1));
  let g = ""; for (let k = 0; k <= 4; k++) { const v = mn + (mx - mn) * k / 4; g += `<line x1="${L0}" x2="${W - 8}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--rule)"/><text x="${L0 - 6}" y="${Y(v) + 4}" text-anchor="end" font-size="11" fill="var(--mut)">${nf(v, v < 10 ? 1 : 0)}</text>`; }
  g += xs.map((x, i) => `<text x="${X(i)}" y="${H - 6}" text-anchor="middle" font-size="11" fill="var(--mut)">${x}</text>`).join("");
  g += series.map(s => { const pts = s.v.map((v, i) => v == null ? null : [X(i), Y(v)]).filter(Boolean); return `<polyline fill="none" stroke="${s.color}" stroke-width="2.6" points="${pts.map(p => p.join(",")).join(" ")}"/>` + pts.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="${s.color}"/>`).join(""); }).join("");
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:640px">${g}</svg><div class="chips">${series.map(s => `<span class="chip" style="cursor:default"><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join("")}<span class="mut" style="font-size:13px;margin-left:6px">${unit}</span></div>`;
}
const _plA = VIEWS.places;
VIEWS.places = async (...a) => {
  await _plA(...a); const box = $("#plb"); if (!box) return;
  const [ng, wx] = await Promise.all([api("/api/newground").catch(() => null), api("/api/weather/stats").catch(() => null)]);
  const ys = years().slice().reverse(), sp = [...new Set(TOURS.map(t => t.sport))].map(s => [s, TOURS.filter(t => t.sport === s).length]).sort((a, b) => b[1] - a[1]).slice(0, 3).map(x => x[0]);
  const perf = (f) => sp.map(s => ({name: sName(s), color: sCol(s), v: ys.map(y => { const a = TOURS.filter(t => t.sport === s && t.y === y && t.h > 0); return a.length >= 2 ? f(a) : null; })}));
  const sm = (a, f) => a.reduce((c, t) => c + f(t), 0);
  let h = `<div class="sec"><h2>Leistung über die Jahre</h2><span class="sub">nur Jahre mit mindestens 2 Touren der Sportart</span></div><div class="grid g2"><div class="panel"><h2>Tempo</h2>${yearChart(perf(a => sm(a, t => t.km) / sm(a, t => t.h)), ys, "km/h im Schnitt")}</div><div class="panel"><h2>Höhenmeter pro Stunde</h2>${yearChart(perf(a => sm(a, t => t.up_m || 0) / sm(a, t => t.h)), ys, "m Aufstieg pro Stunde")}</div></div>`;
  if (wx) { const r = wx.rows, bins = [["unter 0 °", x => x.tmax < 0], ["0–10 °", x => x.tmax >= 0 && x.tmax < 10], ["10–20 °", x => x.tmax >= 10 && x.tmax < 20], ["20–30 °", x => x.tmax >= 20 && x.tmax < 30], ["über 30 °", x => x.tmax >= 30]];
    const mxn = Math.max(1, ...bins.map(b => r.filter(b[1]).length)), top = (f, l) => r.length ? r.slice().sort(f)[0] : null, hot = top((a, b) => b.tmax - a.tmax), cold = top((a, b) => a.tmin - b.tmin), wet = top((a, b) => b.precip - a.precip);
    h += `<div class="sec"><h2>Wetter</h2><span class="sub">${r.length} Touren mit Wetterdaten</span></div><div class="grid g2"><div class="panel"><h2>Bei welcher Temperatur bist du unterwegs?</h2><div class="rows">${bins.map(b => { const n = r.filter(b[1]).length; return `<div class="r"><span>${b[0]}<div class="stack" style="width:${100 * n / mxn}%;min-width:2px;margin-top:4px"><div style="width:100%;background:var(--yellow)"></div></div></span><b>${n}</b></div>`; }).join("")}</div></div>
     <div class="panel"><h2>Extreme &amp; Regen</h2><div class="rows">${r.length ? `<div class="r"><span>Trocken (unter 1 mm)</span><b>${r.filter(x => x.precip < 1).length} von ${r.length}</b></div>
       <div class="r"><span><a href="#/tour/${hot.id}">Wärmste Tour</a><small>${esc(hot.name)}</small></span><b>${nf(hot.tmax, 0)} °</b></div><div class="r"><span><a href="#/tour/${cold.id}">Kälteste Tour</a><small>${esc(cold.name)}</small></span><b>${nf(cold.tmin, 0)} °</b></div>
       <div class="r"><span><a href="#/tour/${wet.id}">Nasseste Tour</a><small>${esc(wet.name)}</small></span><b>${nf(wet.precip, 1)} mm</b></div>` : '<div class="mut">Noch keine Wetterdaten.</div>'}</div>
       <div class="row" style="margin-top:12px"><button class="btn alt" id="wxb">Wetter für alle Touren laden${wx.missing ? ` (${wx.missing} offen)` : ""}</button><span id="wxm" class="mut"></span></div></div></div>`; }
  if (ng && Object.keys(ng.years).length) { const mxy = Math.max(1, ...Object.values(ng.years).map(v => v.km)), tops = Object.entries(ng.tours).sort((a, b) => b[1].new_km - a[1].new_km).slice(0, 8);
    h += `<div class="sec"><h2>Neuland</h2><span class="sub">Anteil der Strecke, der auf keiner früheren Tour lag</span></div><div class="grid g2"><div class="panel"><h2>Je Jahr</h2><div class="rows">${Object.entries(ng.years).reverse().map(([y, v]) => `<div class="r"><span>${y}<div class="stack" style="width:${100 * v.km / mxy}%;margin-top:4px"><div style="width:${v.km ? 100 * v.new_km / v.km : 0}%;background:var(--yellow)"></div></div></span><b>${nf(v.new_km, 0)} von ${nf(v.km, 0)} km neu</b></div>`).join("")}</div></div>
     <div class="panel"><h2>Größte Entdeckungen</h2><div class="rows">${tops.map(([id, v]) => `<div class="r"><span><a href="#/tour/${id}">${esc(BY[id]?.name || id)}</a><small>${BY[id] ? dateS(BY[id].date) : ""} · ${v.pct} % neu</small></span><b>${nf(v.new_km, 1)} km</b></div>`).join("")}</div></div></div>`; }
  box.insertAdjacentHTML("beforeend", h);
  if ($("#wxb")) $("#wxb").onclick = async e => { e.target.disabled = true; try { await api("/api/jobs/weather", {method: "POST"}); $("#wxm").textContent = "Läuft im Hintergrund. Seite später neu öffnen."; } catch (x) { $("#wxm").textContent = x.message; e.target.disabled = false; } };
};

/* =====================  Prüfen: Umbenennen nach Regeln  ===================== */
const _chk = VIEWS.check;
VIEWS.check = async (...a) => {
  await _chk(...a); const body = $("#chb"); if (!body) return;
  body.insertAdjacentHTML("beforeend", `<div class="panel" style="margin-top:22px"><h2>Umbenennen nach Regeln</h2><p class="mut">Wähle Touren aus, lege eine Regel fest, prüfe die Vorschau und wende sie an.</p>
   <div class="filters"><input id="rn_q" placeholder="Name enthält …"><select id="rn_r"><option value="">Alle Regionen</option>${regionOpts()}</select><select id="rn_s"><option value="">Alle Sportarten</option>${[...new Set(TOURS.map(t => t.sport))].map(s => `<option value="${s}">${sName(s)}</option>`).join("")}</select></div>
   <div class="filters"><select id="rn_a"><option value="pre">Vorsilbe hinzufügen</option><option value="suf">Nachsilbe hinzufügen</option><option value="rep">Text ersetzen (Suchen → Ersetzen)</option><option value="date">Datum und Uhrzeit am Ende entfernen</option></select><input id="rn_x" placeholder="Text / Suchen"><input id="rn_y" placeholder="Ersetzen durch"></div>
   <div class="row"><label class="chk" style="margin:0"><input type="checkbox" id="rn_k"> auch bei Komoot umbenennen</label><button class="btn alt" id="rn_p">Vorschau</button><button class="btn" id="rn_go" disabled>Anwenden</button><span id="rn_m" class="mut"></span></div><div class="rows" id="rn_l" style="margin-top:10px"></div></div>`);
  let plan = [];
  const calc = () => { const q = $("#rn_q").value.toLowerCase(), r = $("#rn_r").value, s = $("#rn_s").value, act = $("#rn_a").value, x = $("#rn_x").value, y = $("#rn_y").value;
    plan = TOURS.filter(t => (!q || t.name.toLowerCase().includes(q)) && (!r || inRegion(t, r)) && (!s || t.sport === s)).map(t => { let n = t.name;
      if (act === "pre") n = x + n; else if (act === "suf") n = n + x; else if (act === "rep") n = x ? n.split(x).join(y) : n; else n = n.replace(/\s*\d{2}\.\d{2}\.\d{4}(\s+\d{1,2}:\d{2})?\s*$/, "");
      return [t, n.trim()]; }).filter(([t, n]) => n && n !== t.name);
    $("#rn_l").innerHTML = plan.slice(0, 60).map(([t, n]) => `<div class="r" style="display:block"><span class="mut">${esc(t.name)}</span><br><b>${esc(n)}</b></div>`).join("") + (plan.length > 60 ? `<div class="mut">… und ${plan.length - 60} weitere</div>` : "") || '<div class="mut">Nichts zu ändern.</div>';
    $("#rn_m").textContent = `${plan.length} Touren betroffen`; $("#rn_go").disabled = !plan.length; };
  $("#rn_p").onclick = calc;
  $("#rn_go").onclick = async e => { if (!confirm(`${plan.length} Touren umbenennen${$("#rn_k").checked ? " (auch bei Komoot)" : ""}?`)) return; e.target.disabled = true; let n = 0, bad = 0;
    for (const [t, nn] of plan) { $("#rn_m").textContent = `Benenne um ${++n}/${plan.length} …`; try { await api(`/api/tours/${encodeURIComponent(t.id)}/rename`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({name: nn, komoot: $("#rn_k").checked})}); t.name = nn; } catch (x) { bad++; } }
    $("#rn_m").textContent = `Fertig${bad ? `, ${bad} fehlgeschlagen` : ""}.`; plan = []; $("#rn_l").innerHTML = ""; await loadTours(); };
};

/* ---- Verwaltung: Benachrichtigung ---- */
const _adm9 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm9(...a); const sv = $("#save"); if (!sv) return; const s = await api("/api/settings").catch(() => ({}));
  sv.closest(".row").insertAdjacentHTML("beforebegin", `<div class="panel" style="margin-top:30px"><h2>Benachrichtigung (optional)</h2><p class="mut">Trage eine Webhook-Adresse ein (z. B. ntfy, Gotify oder ein eigener Dienst). Bei einer neuen Warnung (Zepp-Token, Backup, Job-Fehler, Speicher) wird dort eine Textnachricht abgeliefert, höchstens stündlich geprüft. Leer = aus. Die App stellt keine Verbindung zu Home Assistant her.</p>
   <div class="field"><label>Webhook-Adresse</label><input data-k="notify_url" value="${esc(s.notify_url || "")}" placeholder="https://ntfy.sh/mein-thema"></div><div class="row"><button class="btn alt" id="ntest">Testnachricht senden (nach „Speichern“)</button><span id="ntm" class="mut"></span></div></div>`);
  $("#ntest").onclick = async () => { try { await api("/api/notify/test", {method: "POST"}); $("#ntm").textContent = "✓ Gesendet"; } catch (e) { $("#ntm").textContent = e.message; } };
};

/* =====================  Benutzer, Anmeldung, Freigaben, Mobilansicht  ===================== */
let ME = {users_enabled: false, user: null};
const initials = n => (n || "?").split(/\s+/).map(x => x[0]).join("").slice(0, 2).toUpperCase();
function showAuth(kind, msg = "") {
  document.querySelector(".authwrap")?.remove();
  const setup = kind === "setup", w = document.createElement("div"); w.className = "authwrap";
  w.innerHTML = `<form class="authbox" autocomplete="on"><div class="brandl">Meine Touren</div><h2>${setup ? "Benutzerverwaltung einrichten" : "Anmelden"}</h2>
    ${setup ? `<p class="mut">Du legst jetzt den ersten Benutzer an, er wird Administrator. Alle bisherigen Touren, Fotos und Einstellungen gehören danach ihm. Weitere Benutzer legst du anschließend selbst an.</p>` : ""}
    <label>Name<input id="au_n" name="username" autocomplete="username" required></label>
    <label>Passwort<input id="au_p" name="password" type="password" autocomplete="${setup ? "new-password" : "current-password"}" required minlength="${setup ? 8 : 1}"></label>
    ${setup ? `<label>Passwort wiederholen<input id="au_p2" type="password" autocomplete="new-password" required></label><p class="mut" style="font-size:13px">Mindestens 8 Zeichen.</p>` : ""}
    <div class="bad" id="au_e">${esc(msg)}</div><div class="row"><button class="btn" type="submit">${setup ? "Einrichten" : "Anmelden"}</button>${setup ? '<button class="btn alt" type="button" id="au_x">Später</button>' : ""}</div></form>`;
  document.body.appendChild(w); $("#au_n").focus();
  if (setup) $("#au_x").onclick = () => w.remove();
  w.querySelector("form").onsubmit = async e => { e.preventDefault(); $("#au_e").textContent = "";
    if (setup && $("#au_p").value !== $("#au_p2").value) { $("#au_e").textContent = "Die Passwörter sind nicht gleich."; return; }
    try { await fetch(setup ? "/api/setup" : "/api/login", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({name: $("#au_n").value, password: $("#au_p").value})}).then(async r => { if (!r.ok) { let m = await r.text(); try { m = JSON.parse(m).detail || m; } catch (x) {} throw new Error(m); } });
      location.hash = "#/dash"; location.reload(); } catch (x) { $("#au_e").textContent = x.message; } };
}
/* Ansicht: automatisch / mobil / Desktop */
const viewPref = () => { try { return localStorage.getItem("viewmode") || "auto"; } catch (e) { return "auto"; } };
const MORE = [["trips", "Reisen"], ["places", "Auswertung"], ["check", "Prüfen"], ["shared", "Geteilte Fotos"], ["account", "Konto & Freigaben"], ["admin", "Verwaltung"]];
function applyView() {
  const m = viewPref(), mob = m === "mobile" || (m === "auto" && matchMedia("(max-width: 760px)").matches);
  document.documentElement.classList.toggle("mob", mob);
  let tb = $("#tabbar");
  if (!tb) { tb = document.createElement("div"); tb.id = "tabbar"; document.body.appendChild(tb); }
  const T = [["dash", "Übersicht", "🏠"], ["map", "Karte", "🗺"], ["tours", "Touren", "🥾"], ["photos", "Fotos", "🖼"]];
  tb.innerHTML = T.map(([k, l, i]) => `<a href="#/${k}" data-k="${k}"><span class="ti">${i}</span><span>${l}</span></a>`).join("") + `<button id="tmore"><span class="ti">☰</span><span>Mehr</span></button>`;
  $("#tmore").onclick = () => { const m2 = modal(`<h3>Mehr</h3><div class="moregrid">${MORE.map(([k, l]) => `<a class="btn alt" href="#/${k}">${l}</a>`).join("")}</div>
      <h4 style="margin:16px 0 6px">Ansicht</h4><div class="row">${[["auto", "Automatisch"], ["mobile", "Smartphone"], ["desktop", "Computer"]].map(([k, l]) => `<button class="btn ${viewPref() === k ? "" : "alt"} sm" data-vm="${k}">${l}</button>`).join("")}</div>
      ${ME.user ? `<div class="row" style="margin-top:16px"><button class="btn alt" id="mlo">Abmelden (${esc(ME.user.name)})</button></div>` : ""}`); m2.classList.add("sheet");
    m2.querySelectorAll("a").forEach(a => a.onclick = () => m2.remove()); m2.querySelectorAll("[data-vm]").forEach(b => b.onclick = () => { try { localStorage.setItem("viewmode", b.dataset.vm); } catch (e) {} m2.remove(); applyView(); });
    if ($("#mlo")) $("#mlo").onclick = doLogout; };
  markTabs();
}
const markTabs = () => { const k = (location.hash || "#/dash").replace(/^#\/?/, "").split(/[/?]/)[0], kk = k === "tour" || k === "flight" ? "tours" : k; document.querySelectorAll("#tabbar a").forEach(a => a.classList.toggle("on", a.dataset.k === kk)); };
addEventListener("hashchange", markTabs); let rzT; addEventListener("resize", () => { clearTimeout(rzT); rzT = setTimeout(applyView, 150); });
async function doLogout() { try { await fetch("/api/logout", {method: "POST"}); } catch (e) {} location.hash = "#/dash"; location.reload(); }

function userMenu() {
  const top = document.querySelector("header.top"); if (!top || $("#umenu")) return;
  const b = document.createElement("button"); b.id = "umenu"; b.className = "umenu";
  b.innerHTML = ME.user ? `<span class="av">${esc(initials(ME.user.name))}</span><span class="un">${esc(ME.user.name)}</span>` : `<span class="av">👥</span><span class="un">Benutzer</span>`;
  top.insertBefore(b, $("#busy"));
  b.onclick = () => { document.querySelector(".umpop")?.remove(); const p = document.createElement("div"); p.className = "umpop";
    p.innerHTML = ME.user ? `<div class="mut" style="padding:6px 12px">${esc(ME.user.name)} · ${ME.user.role === "admin" ? "Administrator" : "Benutzer"}</div><a href="#/account">Konto &amp; Freigaben</a><a href="#/shared">Geteilte Fotos</a><button id="umo">Abmelden</button>`
      : `<div class="mut" style="padding:6px 12px">Noch keine Benutzerverwaltung</div><button id="ums">Benutzer einrichten …</button>`;
    document.body.appendChild(p); setTimeout(() => document.addEventListener("click", function h(e) { if (!p.contains(e.target)) { p.remove(); document.removeEventListener("click", h); } }), 0);
    p.querySelectorAll("a").forEach(a => a.onclick = () => p.remove()); if ($("#umo")) $("#umo").onclick = doLogout; if ($("#ums")) $("#ums").onclick = () => { p.remove(); showAuth("setup"); }; };
}

VIEWS.account = async () => {
  const [gr, us] = await Promise.all([api("/api/grants").catch(() => ({mine: [], received: []})), api("/api/users").catch(() => [])]), me = ME.user, adm = me && me.role === "admin";
  if (!me) { $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Konto &amp; Freigaben</h2></div><div class="panel"><p>Die Benutzerverwaltung ist noch nicht eingerichtet. Mit „Einrichten“ legst du den ersten Benutzer (Administrator) an; deine bisherigen Daten werden ihm zugeordnet.</p><button class="btn" id="setupb">Einrichten …</button></div>`; $("#setupb").onclick = () => showAuth("setup"); return; }
  const others = us.filter(u => u.uid !== me.uid && (u.active === undefined || u.active));
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Konto &amp; Freigaben</h2><span class="sub">${esc(me.name)} · ${adm ? "Administrator" : "Benutzer"}</span></div>
   <div class="grid g2"><div class="panel"><h2>Passwort ändern</h2><div class="field"><label>Altes Passwort</label><input id="pw0" type="password" autocomplete="current-password"></div><div class="field"><label>Neues Passwort (mind. 8 Zeichen)</label><input id="pw1" type="password" autocomplete="new-password"></div>
     <div class="row"><button class="btn" id="pwb">Ändern</button><span id="pwm" class="mut"></span></div></div>
    <div class="panel"><h2>Ansicht</h2><p class="mut">Gilt nur auf diesem Gerät.</p><div class="row">${[["auto", "Automatisch"], ["mobile", "Smartphone-Ansicht"], ["desktop", "Computer-Ansicht"]].map(([k, l]) => `<button class="btn ${viewPref() === k ? "" : "alt"} sm" data-vm="${k}">${l}</button>`).join("")}</div></div></div>
   <div class="sec"><h2>Fotos freigeben</h2><span class="sub">Andere Benutzer können freigegebene Fotos ansehen und in ihre Bibliothek übernehmen. Deine Originale bleiben bei dir.</span></div>
   <div class="grid g2"><div class="panel"><h2>Neue Freigabe</h2>
     <div class="field"><label>Für</label><select id="gg"><option value="*">Alle Benutzer</option>${others.map(u => `<option value="${esc(u.uid)}">${esc(u.name)}</option>`).join("")}</select></div>
     <div class="field"><label>Was</label><select id="gs2"><option value="all">Meine ganze Fotobibliothek</option><option value="tour">Nur die Fotos einer Tour</option></select></div>
     <div class="field" id="gtw" style="display:none"><label>Tour</label><select id="gt">${TOURS.slice(0, 400).map(t => `<option value="${t.id}">${dateS(t.date)} · ${esc(t.name)}</option>`).join("")}</select></div>
     <div class="row"><button class="btn" id="gadd">Freigeben</button><span id="gm" class="mut"></span></div></div>
    <div class="panel"><h2>Von mir freigegeben</h2><div class="rows">${gr.mine.map(g => `<div class="r"><span>${esc(g.grantee_name)}<small>${g.scope === "all" ? "ganze Fotobibliothek" : "Tour: " + esc(g.ref_name || g.ref)}</small></span><button class="btn alt sm" data-gd="${g.id}">Entfernen</button></div>`).join("") || '<div class="mut">Noch nichts freigegeben.</div>'}</div>
     <h2 style="margin-top:18px">Mit mir geteilt</h2><div class="rows">${gr.received.map(g => `<div class="r"><span>${esc(g.owner_name)}<small>${g.scope === "all" ? "ganze Fotobibliothek" : "einzelne Tour"}</small></span></div>`).join("") || '<div class="mut">Noch nichts geteilt.</div>'}</div>
     <div class="row"><a class="btn alt sm" href="#/shared">Geteilte Fotos ansehen</a></div></div></div>
   ${adm ? `<div class="sec"><h2>Benutzer verwalten</h2></div><div class="panel"><div class="rows">${us.map(u => `<div class="r" style="display:block"><b>${esc(u.name)}</b> <span class="mut">${u.role === "admin" ? "Administrator" : "Benutzer"}${u.active ? "" : " · gesperrt"}${u.me ? " · du" : ""}</span>
      <div class="row" style="margin:6px 0 0"><button class="btn alt sm" data-ur="${u.uid}">${u.role === "admin" ? "Zum Benutzer machen" : "Zum Admin machen"}</button><button class="btn alt sm" data-up="${u.uid}">Passwort setzen</button>${u.me ? "" : `<button class="btn alt sm" data-ua="${u.uid}">${u.active ? "Sperren" : "Entsperren"}</button><button class="btn alt sm" data-ud="${u.uid}">Löschen</button>`}</div></div>`).join("")}</div>
     <h3 style="margin-top:20px">Neuer Benutzer</h3><div class="filters"><input id="nu_n" placeholder="Name"><input id="nu_p" type="password" placeholder="Passwort (mind. 8 Zeichen)" autocomplete="new-password"><select id="nu_r"><option value="user">Benutzer</option><option value="admin">Administrator</option></select><button class="btn" id="nu_b">Anlegen</button><span id="nu_m" class="mut"></span></div>
     <p class="mut" style="font-size:13px">Jeder Benutzer hat eigene Touren, Fotos, Notizen, Ziele und sein eigenes Komoot-Konto (Verwaltung). Fotos aus einem Ordner <code>/mnt/fotos/&lt;Benutzername&gt;</code> werden dem jeweiligen Benutzer zugeordnet.</p></div>` : ""}`;
  document.querySelectorAll("[data-vm]").forEach(b => b.onclick = () => { try { localStorage.setItem("viewmode", b.dataset.vm); } catch (e) {} applyView(); VIEWS.account(); });
  $("#pwb").onclick = async () => { try { await api("/api/me/password", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({old: $("#pw0").value, new: $("#pw1").value})}); $("#pwm").textContent = "✓ Geändert"; $("#pw0").value = $("#pw1").value = ""; } catch (e) { $("#pwm").textContent = e.message; } };
  $("#gs2").onchange = () => { $("#gtw").style.display = $("#gs2").value === "tour" ? "" : "none"; };
  $("#gadd").onclick = async () => { try { await api("/api/grants", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({grantee: $("#gg").value, scope: $("#gs2").value, ref: $("#gs2").value === "tour" ? $("#gt").value : ""})}); VIEWS.account(); } catch (e) { $("#gm").textContent = e.message; } };
  document.querySelectorAll("[data-gd]").forEach(b => b.onclick = async () => { await api("/api/grants/" + b.dataset.gd, {method: "DELETE"}); VIEWS.account(); });
  const J = {"content-type": "application/json"}, patch = async (u, d) => { try { await api("/api/users/" + u, {method: "PATCH", headers: J, body: JSON.stringify(d)}); VIEWS.account(); } catch (e) { alert(e.message); } };
  document.querySelectorAll("[data-ur]").forEach(b => b.onclick = () => patch(b.dataset.ur, {role: us.find(u => u.uid === b.dataset.ur).role === "admin" ? "user" : "admin"}));
  document.querySelectorAll("[data-up]").forEach(b => b.onclick = () => { const p = prompt("Neues Passwort für diesen Benutzer (mind. 8 Zeichen):"); if (p) patch(b.dataset.up, {password: p}); });
  document.querySelectorAll("[data-ua]").forEach(b => b.onclick = () => patch(b.dataset.ua, {active: !us.find(u => u.uid === b.dataset.ua).active}));
  document.querySelectorAll("[data-ud]").forEach(b => b.onclick = async () => { const u = us.find(x => x.uid === b.dataset.ud); const all = confirm(`„${u.name}“ löschen?\n\nOK = Benutzer UND alle seine Touren, Fotos und Daten unwiderruflich löschen.\nAbbrechen = nichts tun.`); if (!all) return; try { await api(`/api/users/${b.dataset.ud}?data=1`, {method: "DELETE"}); VIEWS.account(); } catch (e) { alert(e.message); } });
  if ($("#nu_b")) $("#nu_b").onclick = async () => { try { await api("/api/users", {method: "POST", headers: J, body: JSON.stringify({name: $("#nu_n").value, password: $("#nu_p").value, role: $("#nu_r").value})}); VIEWS.account(); } catch (e) { $("#nu_m").textContent = e.message; } };
};

VIEWS.shared = async () => {
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Geteilte Fotos</h2><span class="sub">Fotos, die andere Benutzer für dich freigegeben haben</span></div><div id="shb" class="mut">Wird geladen …</div>`;
  const data = await api("/api/shared/photos"); $("#shb").className = "";
  if (!data.length) { $("#shb").innerHTML = '<div class="empty"><h2>Noch nichts geteilt</h2><p>Sobald jemand Fotos für dich freigibt, erscheinen sie hier.</p></div>'; return; }
  $("#shb").innerHTML = data.map((o, oi) => { const by = {}; o.photos.forEach(p => (by[p.tour_id || ""] ||= []).push(p));
    return `<div class="sec"><h2>${esc(o.name)}</h2><span class="sub">${o.photos.length} Fotos</span><span class="sp"></span><button class="btn sm" data-all="${oi}">Alle übernehmen</button></div>` + Object.entries(by).map(([tid, ps]) => `<div class="pgroup"><div class="ph"><h3>${esc(tid ? o.tours[tid] || "Tour" : "Ohne Tour")}</h3><span>${ps.length} Fotos</span><button class="btn alt sm" data-grp="${oi}|${esc(tid)}">Übernehmen</button></div>
      <div class="thumbs" data-g="${oi}|${esc(tid)}">${ps.map((p, i) => `<img loading="lazy" src="/sphoto/${esc(o.owner)}/${p.id}?size=300" data-i="${i}" title="${new Date(p.taken_ts * 1000).toLocaleString("de-DE")}">`).join("")}</div></div>`).join(""); }).join("");
  data.forEach((o, oi) => { const by = {}; o.photos.forEach(p => (by[p.tour_id || ""] ||= []).push(p));
    document.querySelectorAll(`[data-g^="${oi}|"]`).forEach(box => { const tid = box.dataset.g.split("|")[1], list = by[tid].map(p => ({...p, src: `/sphoto/${o.owner}/${p.id}?size=2000`})); bindThumbs(box, list); }); });
  const imp = async (oi, ids, btn) => { btn.disabled = true; try { const r = await api("/api/shared/import", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({owner: data[oi].owner, ids})}); btn.textContent = `✓ ${r.total} übernommen`; } catch (e) { btn.disabled = false; alert(e.message); } };
  document.querySelectorAll("[data-all]").forEach(b => b.onclick = () => imp(+b.dataset.all, data[+b.dataset.all].photos.map(p => p.id), b));
  document.querySelectorAll("[data-grp]").forEach(b => b.onclick = () => { const [oi, tid] = b.dataset.grp.split("|"); imp(+oi, data[+oi].photos.filter(p => (p.tour_id || "") === tid).map(p => p.id), b); });
};

/* Tourdetail: Fotos anderer + Foto-Freigabe */
const _tourU = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourU(id, q); const t = BY[id]; if (!t || !ME.users_enabled || !ME.user) return;
  const row = $("#etag")?.parentElement; if (row && !$("#efsh")) row.insertAdjacentHTML("beforeend", `<button class="btn ghost sm" id="efsh" title="Fotos dieser Tour für andere Benutzer freigeben">👥 Fotos freigeben</button>`);
  if ($("#efsh")) $("#efsh").onclick = async () => { const us = (await api("/api/users").catch(() => [])).filter(u => u.uid !== ME.user.uid && (u.active === undefined || u.active));
    const m = modal(`<h3>Fotos dieser Tour freigeben</h3><p class="mut" style="font-size:14px">Die Freigabe gilt für alle Fotos, die dieser Tour zugeordnet sind.</p><div class="field"><label>Für</label><select id="fg"><option value="*">Alle Benutzer</option>${us.map(u => `<option value="${esc(u.uid)}">${esc(u.name)}</option>`).join("")}</select></div>
      <div class="row" style="justify-content:flex-end"><button class="btn alt" id="fgx">Abbrechen</button><button class="btn" id="fgo">Freigeben</button></div>`);
    m.querySelector("#fgx").onclick = () => m.remove(); m.querySelector("#fgo").onclick = async () => { try { await api("/api/grants", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({grantee: m.querySelector("#fg").value, scope: "tour", ref: t.id})}); m.remove(); alert("Freigegeben. Verwalten unter „Konto & Freigaben“."); } catch (e) { alert(e.message); } }; };
  api(`/api/shared/for-tour/${encodeURIComponent(id)}`).then(list => { if (!list.length || !$("#th")) return; const by = {}; list.forEach(p => (by[p.owner] ||= {name: p.owner_name, ids: []}).ids.push(p.id));
    $("#th").insertAdjacentHTML("beforebegin", `<div class="panel" id="shn" style="margin-bottom:14px;padding:12px 16px"><b>Fotos von anderen aus diesem Zeitraum:</b> ${Object.entries(by).map(([o, v]) => `${esc(v.name)} (${v.ids.length}) <button class="btn sm" data-imp="${esc(o)}">In meine Tour übernehmen</button>`).join(" ")}</div>`);
    document.querySelectorAll("[data-imp]").forEach(b => b.onclick = async () => { b.disabled = true; try { await api("/api/shared/import", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({owner: b.dataset.imp, ids: by[b.dataset.imp].ids})}); await loadTours(); VIEWS.tour(id, q); } catch (e) { b.disabled = false; alert(e.message); } }); }).catch(() => {});
};

/* Start */
async function boot() {
  try { ME = await fetch("/api/me").then(r => r.json()); } catch (e) {}
  applyView();
  if (ME.users_enabled && !ME.user) { showAuth("login"); return; }
  userMenu(); await loadPrefs(); route();
}


/* ---- Verwaltung: Bereiche gruppieren und einklappbar machen ---- */
const _admG = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admG(...a); const main = $("#main"), save = $("#save"); if (!save) return;
  const GROUPS = [
    ["import", "Import", "Touren und Fotos in die App holen", ["Komoot", "Zepp-Import", "GPX/TCX-Dateien", "Fotos", "Foto-Eingang"], true],
    ["portale", "Upload-Portale", "Strava, Komoot", ["Portale"], false],
    ["auto", "Automatik & Benachrichtigung", "", ["Automatik", "Benachrichtigung"], false],
    ["log", "Protokoll", "", ["Protokoll"], true],
    ["wartung", "Wartung & Sicherheit", "Sicherung, Zugriffsschutz, Selbsttest, Wanderführer", ["Sicherung", "Zugriffsschutz", "Selbsttest", "Wanderführer"], false],
  ];
  let mem = {}; try { mem = JSON.parse(localStorage.getItem("admgrp") || "{}"); } catch (e) {}
  const panels = [...main.querySelectorAll(".panel")].filter(p => p.parentElement && p.querySelector(":scope > h2"));
  const title = p => p.querySelector(":scope > h2").firstChild.textContent.trim();
  const anchor = save.closest(".row"), frag = document.createDocumentFragment();
  const open = new URLSearchParams(location.hash.split("?")[1] || "").get("strava");
  GROUPS.forEach(([id, name, sub, titles, dflt]) => {
    const mine = titles.map(t => panels.find(p => title(p).startsWith(t))).filter(Boolean); if (!mine.length) return;
    const d = document.createElement("details"); d.className = "agrp";
    d.open = id in mem ? !!mem[id] : (dflt || (id === "portale" && !!open));
    d.innerHTML = `<summary><span class="gt">${name}</span><span class="gs">${sub}</span></summary><div class="grid g2 gbody"></div>`;
    mine.forEach(p => { p.style.marginTop = "6px"; if (mine.length === 1 && title(p) === name) { p.style.borderTop = "0"; p.querySelector(":scope > h2").style.display = "none"; } d.querySelector(".gbody").appendChild(p); });
    d.addEventListener("toggle", () => { mem[id] = d.open; try { localStorage.setItem("admgrp", JSON.stringify(mem)); } catch (e) {} });
    frag.appendChild(d);
  });
  main.querySelectorAll(":scope > .grid, :scope > .panel").forEach(g => { if (!g.querySelector(".panel") && !g.matches(".panel") && !g.textContent.trim()) g.remove(); });
  main.querySelectorAll(":scope > .grid").forEach(g => { if (!g.children.length) g.remove(); });
  anchor.parentNode.insertBefore(frag, anchor);
};

/* ---- Warnbanner (Gesundheitscheck) ---- */
let _hl = {t: 0, v: []};
async function healthBanner() {
  try { if (Date.now() - _hl.t > 60000) _hl = {t: Date.now(), v: await api("/api/health")};
    const m = $("#main"); if (!m || !_hl.v.length || m.querySelector(".warnbar")) return;
    m.insertAdjacentHTML("afterbegin", `<div class="warnbar">${_hl.v.map(w => `<div>⚠ ${esc(w.text)}</div>`).join("")}<a href="#/admin">Verwaltung öffnen</a></div>`); } catch (e) {}
}
Object.keys(VIEWS).forEach(k => { const f = VIEWS[k]; VIEWS[k] = async (...a) => { await f(...a); healthBanner(); }; });

boot();
