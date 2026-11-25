/* Skript der Seite share.html (eigene Datei, damit die Content-Security-Policy Inline-Skripte verbieten kann).
   3.25.0: Gezeigt wird nur, was der Server für diesen Link ausliefert (Bausteine: Kennzahlen, Karte, Höhenprofil, Wegpunkte, Pulsverlauf, Wetter, Notiz, Fotos). */
const tok = location.pathname.split("/").pop(), nf = (n, d = 1) => fmtZahl(n, d);
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const has = (t, k, v) => v !== undefined && (!t.blocks || t.blocks.includes(k));
/* Linien-/Flächendiagramm als SVG: pts = [[x, y], …] */
function chart(pts, label, fx, fy, unit) {
  const W = 640, H = 200, L = 64, R = 12, T = 12, B = 26;
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), dy = (y1 - y0) || 1, dx = (x1 - x0) || 1;
  const X = x => L + (x - x0) / dx * (W - L - R), Y = y => T + (1 - (y - y0) / dy) * (H - T - B);
  const d = pts.map((p, i) => (i ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1)).join("");
  return `<svg class="cht" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}"><path class="ar" d="${d}L${X(x1).toFixed(1)} ${H - B}L${X(x0).toFixed(1)} ${H - B}Z"/><path class="ln" d="${d}"/>
    <text x="${L - 6}" y="${T + 10}" text-anchor="end">${fy(y1)}</text><text x="${L - 6}" y="${H - B}" text-anchor="end">${fy(y0)}</text>
    <text x="${L}" y="${H - 6}">${fx(x0)}</text><text x="${W - R}" y="${H - 6}" text-anchor="end">${fx(x1)}</text></svg>`;
}
fetch("/api/public/" + tok).then(r => { if (!r.ok) throw 0; return r.json(); }).then(t => {
  document.title = t.name; document.getElementById("h").textContent = t.name;
  document.getElementById("k").textContent = fmtDatum(t.date, {wochentag: true});
  const B = document.getElementById("b"), sec = (id, title, inner) => B.insertAdjacentHTML("beforeend", `<section class="blk" id="${id}">${title ? `<h2>${title}</h2>` : ""}${inner}</section>`);
  if (has(t, "zahlen", t.km)) sec("bz", "", `<div class="figs">${[[fmtKm(t.km), "Strecke"], [fmtHm(t.up_m), "Aufstieg"], [fmtHm(t.down_m), "Abstieg"], [fmtDauer(t.h * 3600), "Dauer"]].map(x => `<div class="fig"><b>${x[0]}</b><span>${x[1]}</span></div>`).join("")}</div>`);
  if (has(t, "karte", t.coords)) {
    sec("bk", "", `<div id="m" role="img" aria-label="Karte der Tour"></div>`);
    const m = L.map("m"); L.tileLayer("/tiles/osm/{z}/{x}/{y}", {maxZoom: 18, attribution: "© OpenStreetMap"}).addTo(m);
    const ll = t.coords.map(p => [p[0], p[1]]);
    if (ll.length > 1) { const l = L.polyline(ll, {color: "#e11d74", weight: 5}).addTo(m); m.fitBounds(l.getBounds(), {padding: [20, 20]}); } else m.setView([50, 9], 5);
    (t.wps || []).forEach((w, i) => L.circleMarker([w.lat, w.lng], {radius: 7, color: "#10282a", weight: 2, fillColor: "#f2c230", fillOpacity: 1}).addTo(m).bindTooltip(String(i + 1)));
  }
  if (has(t, "hoehe", t.prof) && t.prof.length > 1) sec("bh", "Höhenprofil", chart(t.prof, "Höhenprofil", x => nf(x) + " km", y => nf(y, 0) + " m"));
  if (has(t, "wege", t.wps) && t.wps.length) sec("bw", "Wegpunkte", `<ol class="wl">${t.wps.map((w, i) => `<li><b>${i + 1}${w.t ? " · " + esc(w.t) : ""}</b>${w.note ? esc(w.note) : ""}</li>`).join("")}</ol>`);
  if (has(t, "puls", t.hr) && t.hr) sec("bp", "Pulsverlauf", chart(t.hr.pts, "Pulsverlauf", x => Math.round(x / 60) + " min", y => Math.round(y) + " bpm") + `<p class="k2">Ø ${nf(t.hr.avg, 0)}\u00a0bpm · max. ${nf(t.hr.max, 0)}\u00a0bpm</p>`);
  if (has(t, "wetter", t.wx) && t.wx) sec("bx", "Wetter", `<div class="wx">${t.wx.text ? `<div>${esc(t.wx.text)}</div>` : ""}${t.wx.tmin != null ? `<div>${nf(t.wx.tmin, 0)} – ${nf(t.wx.tmax, 0)} °C<span>Temperatur</span></div>` : ""}${t.wx.precip != null ? `<div>${nf(t.wx.precip)} mm<span>Niederschlag</span></div>` : ""}${t.wx.wind != null ? `<div>${nf(t.wx.wind, 0)}\u00a0km/h<span>Wind</span></div>` : ""}</div>`);
  if (has(t, "notiz", t.note) && t.note) sec("bn", "Notiz", `<p class="note">${esc(t.note)}</p>`);
  if (has(t, "fotos", t.photos) && t.photos.length) {
    sec("bf", "Fotos", `<div class="ph" id="p">${t.photos.map(id => `<img loading="lazy" alt="Foto vergrößern" tabindex="0" role="button" src="/pub/${tok}/photo/${id}?size=400" data-id="${id}">`).join("")}</div>`);
    const P = document.getElementById("p"), lb = document.getElementById("lb");
    const open = i => { if (i) { lb.firstChild.src = `/pub/${tok}/photo/${i.dataset.id}?size=1600`; lb.style.display = "flex"; } };
    P.onclick = e => open(e.target.closest("img"));
    P.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(e.target.closest("img")); } };
    lb.onclick = () => lb.style.display = "none";
    document.addEventListener("keydown", e => { if (e.key === "Escape") lb.style.display = "none"; });
  }
  document.body.dataset.ready = "1";
}).catch(() => { document.querySelector("main").innerHTML = '<div class="err">Dieser Link ist nicht (mehr) gültig.</div>'; });
