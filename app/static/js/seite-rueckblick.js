/* Skript der Seite rueckblick.html (öffentlicher Jahresrückblick, 3.26.0; eigene Datei, damit die Content-Security-Policy Inline-Skripte verbieten kann).
   Gezeigt wird nur, was der Server für diesen Link ausliefert (Bausteine: Kennzahlen, Rekorde, Heatmap, Fotos). Drucken: window.print() mit eigener Druckansicht (@media print). */
const tok = location.pathname.split("/").pop();
const LG = {de: "de-DE", en: "en-GB", fr: "fr-FR", es: "es-ES"}[document.documentElement.lang] || "de-DE";
const nf = (n, d = 1) => Number(n).toLocaleString(LG, {minimumFractionDigits: d, maximumFractionDigits: d});
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const mon = (y, m, f) => new Date(Date.UTC(y, m, 1, 12)).toLocaleDateString(LG, {month: f, timeZone: "UTC"});
const dateL = iso => new Date(iso + "T12:00:00Z").toLocaleDateString(LG, {day: "numeric", month: "long", year: "numeric", timeZone: "UTC"});

function monthBars(t, kz) {
  const W = 640, H = 150, B = 24, T = 10, max = Math.max(1, ...kz.months), bw = W / 12;
  return `<svg class="mbars" viewBox="0 0 ${W} ${H}" role="img" aria-label="Kilometer pro Monat">${kz.months.map((v, i) => {
    const h = Math.max(v ? 2 : 0, v / max * (H - B - T));
    return `<rect x="${(i * bw + bw * 0.18).toFixed(1)}" y="${(H - B - h).toFixed(1)}" width="${(bw * 0.64).toFixed(1)}" height="${h.toFixed(1)}" rx="2"><title>${esc(mon(t.year, i, "long"))}: ${nf(v)} km</title></rect><text x="${(i * bw + bw / 2).toFixed(1)}" y="${H - 6}" text-anchor="middle">${esc(mon(t.year, i, "short").replace(".", "").slice(0, 3))}</text>`;
  }).join("")}</svg>`;
}

function heat(h) {
  const max = Math.max(1, ...h.days.map(d => d[1])), per = {}, lvl = v => (v <= 0 ? 0 : v <= max * 0.25 ? 1 : v <= max * 0.5 ? 2 : v <= max * 0.75 ? 3 : 4);
  h.days.forEach(d => (per[d[0]] = d[1]));
  let doy = 1;
  const months = [];
  for (let m = 0; m < 12; m++) {
    const len = new Date(Date.UTC(h.year, m + 1, 0)).getUTCDate(), wd = (h.wd0 + doy - 1) % 7;
    const cells = [];
    for (let d = 1; d <= len; d++, doy++) {
      const v = per[doy] || 0, l = lvl(v), lab = new Date(Date.UTC(h.year, m, d, 12)).toLocaleDateString(LG, {day: "numeric", month: "long", timeZone: "UTC"}) + (v ? ": " + nf(v) + " km" : "");
      cells.push(`<i class="${l ? "l" + l : ""}" title="${esc(lab)}"${d === 1 && wd ? ` data-first style="grid-row-start:${wd + 1}"` : ""}></i>`);
    }
    months.push(`<div class="mo"><h3>${esc(mon(h.year, m, "long"))}</h3><div class="cal" role="img" aria-label="${esc(mon(h.year, m, "long"))}">${cells.join("")}</div></div>`);
  }
  return `<div class="months">${months.join("")}</div><div class="leg"><span>weniger</span><i></i><i class="l1"></i><i class="l2"></i><i class="l3"></i><i class="l4"></i><span>mehr Kilometer</span></div>`;
}

const REC = {weit: "Längste Tour", hoch: "Meiste Höhenmeter", lang: "Längste Dauer"};
function recs(t) {
  return `<div class="recs">${t.rek.map(r => {
    if (r.k === "monat") return `<div class="rec"><div class="l">Stärkster Monat</div><b>${esc(mon(t.year, r.month - 1, "long"))}</b><div class="w"><span>${nf(r.v)} km</span></div></div>`;
    if (r.k === "serie") return `<div class="rec"><div class="l">Längste Serie</div><b>${r.v} ${r.v === 1 ? "Tag" : "Tage"}</b><div class="w"><span>Tage in Folge unterwegs</span></div></div>`;
    const v = r.u === "km" ? nf(r.v) + " km" : r.u === "m" ? nf(r.v, 0) + " m" : nf(r.v) + " h";
    return `<div class="rec"><div class="l">${REC[r.k]}</div><b>${v}</b><div class="w">${esc(r.name)} <span>${esc(dateL(r.date))}</span></div></div>`;
  }).join("")}</div>`;
}

fetch("/api/public/" + tok).then(r => { if (!r.ok) throw 0; return r.json(); }).then(t => {
  if (t.kind !== "rueckblick") throw 0;
  document.title = "Jahresrückblick " + t.year;
  document.getElementById("h").textContent = t.year;
  if (t.sport_name) { const s = document.getElementById("sb"); s.textContent = t.sport_name; s.hidden = false; }
  const B = document.getElementById("b"), sec = (id, title, inner) => B.insertAdjacentHTML("beforeend", `<section class="blk" id="${id}"><h2>${title}</h2>${inner}</section>`);
  const kz = t.kz;
  if (kz) {
    const fig = (v, l) => `<div class="fig"><b>${v}</b><span>${l}</span></div>`;
    const d = kz.prev_km ? (kz.km - kz.prev_km) / kz.prev_km * 100 : null;
    sec("bz", "Dein Jahr", `<div class="figs">${fig(nf(kz.count, 0), kz.count === 1 ? "Tour" : "Touren")}${fig(nf(kz.km, 0) + " km", "Strecke")}${fig(nf(kz.up_m, 0) + " m", "Aufstieg")}${fig(nf(kz.h, 0) + " h", "Stunden")}${fig(nf(kz.days, 0), "Tage unterwegs")}</div>
      ${d != null ? `<p class="cmp"><b>${d >= 0 ? "+" : "−"}${nf(Math.abs(d), 0)} %</b> <span>gegenüber ${t.year - 1}</span></p>` : ""}
      <div class="panel"><h3>Kilometer pro Monat</h3>${monthBars(t, kz)}</div>
      ${kz.sports && kz.sports.length > 1 ? `<div class="panel"><h3>Aktivitäten</h3><ul class="sp">${kz.sports.map(s => `<li><span>${esc(s.name)}</span><b>${nf(s.km, 0)} km</b></li>`).join("")}</ul></div>` : ""}`);
  }
  if (t.rek && t.rek.length) sec("br", "Rekorde", recs(t));
  if (t.heat) sec("bh", "Heatmap", heat(t.heat));
  if (t.photos && t.photos.length) {
    sec("bf", "Beste Fotos", `<div class="ph" id="p">${t.photos.map(id => `<img alt="Foto vergrößern" tabindex="0" role="button" src="/pub/${tok}/photo/${id}?size=500" data-id="${id}">`).join("")}</div>`);
    const P = document.getElementById("p"), lb = document.getElementById("lb");
    const open = i => { if (i) { lb.firstChild.src = `/pub/${tok}/photo/${i.dataset.id}?size=1600`; lb.style.display = "flex"; } };
    P.onclick = e => open(e.target.closest("img"));
    P.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(e.target.closest("img")); } };
    lb.onclick = () => lb.style.display = "none";
    document.addEventListener("keydown", e => { if (e.key === "Escape") lb.style.display = "none"; });
  }
  const pr = document.getElementById("pr");
  pr.hidden = false;
  pr.onclick = () => window.print();
  if (/[?&]print=1/.test(location.search)) {                         // „Als PDF“ aus der App: Druckdialog öffnen, sobald die Fotos geladen sind
    const imgs = [...document.querySelectorAll("#p img")];
    Promise.all(imgs.map(i => (i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r; })))).then(() => setTimeout(() => window.print(), 300));
  }
  document.body.dataset.ready = "1";
}).catch(() => { document.querySelector("main").innerHTML = '<div class="err">Dieser Link ist nicht (mehr) gültig.</div>'; document.body.dataset.ready = "1"; });
