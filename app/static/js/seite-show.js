/* Skript der Seite show.html (eigene Datei, damit die Content-Security-Policy Inline-Skripte verbieten kann) */
const tok = location.pathname.split("/").pop(), $ = id => document.getElementById(id), SPEEDS = [3000, 5000, 8000];
let DELAY = 5000, ids = [], TS = [], i = 0, playing = true, timer = null, T = null, map = null, hideT = null;
const url = (id, s) => `/pub/${tok}/photo/${id}?size=${s || 1600}`;
const nf = (n, d = 1) => Number(n).toLocaleString("de-DE", {minimumFractionDigits: d, maximumFractionDigits: d});
function show(n) {
  if (!ids.length) return;
  i = (n + ids.length) % ids.length;
  const st = $("st"), im = new Image();
  im.onload = () => {
    st.querySelectorAll("img").forEach(x => { x.classList.remove("on"); setTimeout(() => x.remove(), 700); });
    st.appendChild(im); requestAnimationFrame(() => im.classList.add("on"));
  };
  im.src = url(ids[i]); im.alt = "";
  if (typeof cmDraw === "function" && CMON) cmDraw();
  $("cnt").textContent = (i + 1) + " / " + ids.length;
  $("cap").textContent = TS[i] ? TS[i] + " Uhr" : "";
  new Image().src = url(ids[(i + 1) % ids.length]);       // nächstes Foto vorladen
  restart();
}
function restart() {
  clearTimeout(timer);
  const p = $("prog"); p.style.transition = "none"; p.style.width = "0";
  if (!playing) return;
  requestAnimationFrame(() => requestAnimationFrame(() => { p.style.transition = `width ${DELAY}ms linear`; p.style.width = "100%"; }));
  timer = setTimeout(() => show(i + 1), DELAY);
}
function toggle() { playing = !playing; $("pl").textContent = playing ? "❚❚" : "▶"; restart(); }
function bars() { document.body.classList.remove("hide"); clearTimeout(hideT); hideT = setTimeout(() => !$("map").classList.contains("on") && document.body.classList.add("hide"), 3500); }
$("pv").onclick = e => { e.stopPropagation(); show(i - 1); bars(); };
$("nx").onclick = e => { e.stopPropagation(); show(i + 1); bars(); };
$("pl").onclick = e => { e.stopPropagation(); toggle(); bars(); };
$("sp").onclick = e => { e.stopPropagation(); DELAY = SPEEDS[(SPEEDS.indexOf(DELAY) + 1) % SPEEDS.length]; $("sp").textContent = DELAY / 1000 + " s"; restart(); bars(); };
$("fs").onclick = e => { e.stopPropagation(); document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen && document.documentElement.requestFullscreen(); };
$("mp").onclick = e => {
  e.stopPropagation();
  const m = $("map"); m.classList.toggle("on");
  if (m.classList.contains("on")) {
    if (!map && T && T.coords.length > 1) {
      map = L.map("map"); L.tileLayer("/tiles/osm/{z}/{x}/{y}", {maxZoom: 18, attribution: "© OpenStreetMap"}).addTo(map);
      const l = L.polyline(T.coords.map(p => [p[0], p[1]]), {color: "#e11d74", weight: 5}).addTo(map); map.fitBounds(l.getBounds(), {padding: [20, 20]});
    }
    if (map) setTimeout(() => map.invalidateSize(), 50);
    document.body.classList.remove("hide"); clearTimeout(hideT);
  } else bars();
};
$("st").onclick = e => { document.body.classList.contains("hide") ? bars() : document.body.classList.add("hide"); };
let x0 = null;
$("st").addEventListener("touchstart", e => x0 = e.touches[0].clientX, {passive: true});
$("st").addEventListener("touchend", e => { if (x0 == null) return; const d = e.changedTouches[0].clientX - x0; x0 = null; if (Math.abs(d) > 50) { show(i + (d < 0 ? 1 : -1)); bars(); } });
document.addEventListener("keydown", e => { if (e.key === "ArrowRight") show(i + 1); else if (e.key === "ArrowLeft") show(i - 1); else if (e.key === " ") { e.preventDefault(); toggle(); } });
let CM = {}, CMON = false;
function cmDraw() {
  const id = ids[i], l = CM[id] || [], b = $("cb");
  b.textContent = "💬 " + (l.length || "");
  const box = $("cm");
  if (!box.classList.contains("on")) return;
  box.innerHTML = `<div class="r" style="justify-content:space-between"><b>💬 Kommentare</b><button id="cmx" style="height:36px;min-width:36px">✕</button></div>` +
    (l.length ? l.map(c => `<div class="c"><small>${esc(c.author)} · ${new Date(c.ts * 1000).toLocaleString("de-DE")}</small>${esc(c.text)}</div>`).join("") : '<p style="color:#9db3ae">Noch keine Kommentare.</p>') +
    `<input id="cma" maxlength="40" placeholder="Dein Name (optional)" value="${esc(localStorage.getItem("mt_cname") || "")}"><div class="r"><input id="cmt" maxlength="500" placeholder="Kommentar schreiben …"><button id="cms">Senden</button></div><p id="cme" style="color:#f88;font-size:13px"></p>`;
  $("cmx").onclick = e => { e.stopPropagation(); box.classList.remove("on"); playing = was; restart(); };
  const send = async () => {
    const t = $("cmt").value.trim(); if (!t) return;
    try { localStorage.setItem("mt_cname", $("cma").value); } catch (e) {}
    const r = await fetch("/api/public/" + tok + "/comments", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({photo_id: id, author: $("cma").value, text: t})});
    if (!r.ok) { let m = await r.text(); try { m = JSON.parse(m).detail || m; } catch (e) {} $("cme").textContent = m; return; }
    (CM[id] = CM[id] || []).push(await r.json()); cmDraw();
  };
  $("cms").onclick = send; $("cmt").onkeydown = e => { e.stopPropagation(); if (e.key === "Enter") send(); };
  $("cma").onkeydown = e => e.stopPropagation();
}
const esc = x => String(x).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
let was = true;
$("cb").onclick = e => { e.stopPropagation(); was = playing; playing = false; clearTimeout(timer); $("cm").classList.add("on"); cmDraw(); };
fetch("/api/public/" + tok).then(r => { if (!r.ok) throw 0; return r.json(); }).then(t => {
  T = t; ids = t.photos || []; TS = t.photo_t || [];
  document.title = t.name; $("h").textContent = t.name;
  $("sub").textContent = new Date(t.date).toLocaleDateString("de-DE", {day: "numeric", month: "long", year: "numeric"}) + " · " + nf(t.km) + " km · " + nf(t.up_m, 0) + " m aufwärts";
  if (!ids.length) { $("st").innerHTML = '<div class="err">Zu dieser Tour gibt es keine Fotos.</div>'; $("prog").style.display = "none"; return; }
  if (t.coords.length < 2) $("mp").style.display = "none";
  show(0); bars();
  fetch("/api/public/" + tok + "/comments").then(r => r.json()).then(c => { CM = c.comments || {}; CMON = !!c.enabled; if (CMON) { $("cb").style.display = "inline-block"; cmDraw(); } }).catch(() => {});
}).catch(() => { $("st").innerHTML = '<div class="err">Dieser Link ist nicht (mehr) gültig oder abgelaufen.</div>'; $("prog").style.display = "none"; document.body.classList.remove("hide"); });
