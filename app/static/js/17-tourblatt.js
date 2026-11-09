/* =====================  Tourblatt: druckbare Seite / PDF einer Tour  ===================== */
/* ---- Fotos im PDF: appweit wählbar (an/aus, Anzahl); gilt für Tourblatt, Reisebericht und Jahresrückblick ---- */
const PDFP = {on: true, n: 6};
async function pdfPhotoLoad() {
  const s = await api("/api/settings").catch(() => ({}));
  PDFP.on = s.pdf_photos !== "0";
  PDFP.n = Math.max(1, Math.min(24, +s.pdf_photo_n || 6));
}
const pdfPhotoBar = () =>
  `<label class="pdfctl" title="Gilt für alle PDF-Berichte der App"><input type="checkbox" id="pdfon" ${PDFP.on ? "checked" : ""}> Fotos im PDF <select id="pdfn" ${PDFP.on ? "" : "disabled"}>${[3, 6, 9, 12, 18, 24].map(n => `<option value="${n}" ${n === PDFP.n ? "selected" : ""}>${n}</option>`).join("")}</select></label>`;
function pdfPhotoBind(onChange) {
  const save = async () => {
    PDFP.on = $("#pdfon").checked;
    PDFP.n = +$("#pdfn").value;
    $("#pdfn").disabled = !PDFP.on;
    await api("/api/settings", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({pdf_photos: PDFP.on ? "1" : "0", pdf_photo_n: String(PDFP.n)})}).catch(() => {});
    onChange();
  };
  $("#pdfon").onchange = save;
  $("#pdfn").onchange = save;
}
/* echte PDF-Datei vom Server (Vektor-Text, Karte, Höhenprofil, Fotos) */
const pdfBtn = () => `<button class="btn" id="pdfdl" title="Fertige PDF-Datei herunterladen">PDF herunterladen</button>`;
const pdfBindDl = path => {
  const b = $("#pdfdl");
  if (b) b.onclick = () => (location.href = `${path}?photos_on=${PDFP.on ? 1 : 0}&n=${PDFP.n}`);
};
/* gleichmäßig verteilte Auswahl von höchstens n Einträgen */
const spread = (a, n) => (a.length <= n ? a : Array.from({length: n}, (_, i) => a[Math.round((i * (a.length - 1)) / Math.max(1, n - 1))]));

VIEWS.sheet = async id => {
  const t = BY[id];
  if (!t) throw new Error("Tour nicht gefunden");
  await pdfPhotoLoad();
  $("#main").innerHTML = `<div class="sheet">
   <div class="row noprint"><a class="back" href="#/tour/${esc(t.id)}">‹ Zurück zur Tour</a><span class="sp"></span>${pdfPhotoBar()}${pdfBtn()}<button class="btn ghost" id="shp">Drucken</button></div>
   <div style="margin-top:14px"><span class="tag" style="background:${sCol(t.sport)}">${sName(t.sport)}</span> <span class="mut" style="margin-left:8px">${dateL(t.date)}, ${timeS(t.date)} Uhr${t.g_country ? " · " + esc([t.g_place, t.g_state, t.g_country].filter(Boolean).join(", ")) : ""}</span></div>
   <h1 style="font-size:34px;margin:8px 0 14px">${esc(t.name)}</h1>
   <div class="figs"><div class="fig"><div class="v">${nf(t.km, 2)}<span class="u">km</span></div><div class="l">Strecke</div></div><div class="fig"><div class="v">${nf(t.up_m, 0)}<span class="u">m</span></div><div class="l">Aufstieg</div></div>
   <div class="fig"><div class="v">${nf(t.down_m, 0)}<span class="u">m</span></div><div class="l">Abstieg</div></div><div class="fig"><div class="v">${Math.floor(t.h)}:${pad2(Math.round((t.h % 1) * 60))}<span class="u">Std.</span></div><div class="l">Dauer</div></div>
   <div class="fig"><div class="v">${t.h ? nf(t.km / t.h, 1) : "–"}<span class="u">km/h</span></div><div class="l">Tempo</div></div><div id="kmax" class="fig" style="display:none"><div class="v" id="kmaxv"></div><div class="l">Höchster Punkt</div></div></div>
   <div class="tmap" id="tm" style="height:360px"></div>
   <div class="panel prof gap" id="profcard"><h2>Höhenprofil</h2><div id="prof" class="mut">Wird geladen …</div></div>
   <div class="thumbs sheetph" id="th"></div></div>`;
  map = mkMap("tm", {layers: false});
  map.setView([t.lat || 50, t.lng || 8], 12);
  try {
    const c = await api(`/api/tours/${t.id}/coords`),
      pts = cleanPts(c),
      ll = pts.map(p => [p[0], p[1]]),
      l = L.polyline(ll, {color: sCol(t.sport), weight: 4}).addTo(map);
    map.fitBounds(l.getBounds(), {padding: [20, 20]});
    L.circleMarker(ll[0], {radius: 6, color: "#fff", fillColor: "#2f8f5f", fillOpacity: 1, weight: 2}).addTo(map);
    L.circleMarker(ll[ll.length - 1], {radius: 6, color: "#fff", fillColor: "#c0504d", fillOpacity: 1, weight: 2}).addTo(map);
    profile(c, t);
  } catch (e) {
    $("#profcard").style.display = "none";
  }
  const photos = async () => {
    if (!PDFP.on) {
      $("#th").innerHTML = "";
      return;
    }
    let pick = [];
    try {
      pick = (await api(`/api/tours/${t.id}/best-photos?n=${PDFP.n}`)).photos; // beste Fotos: Sterne, Schärfe, verteilt
    } catch (e) {
      pick = spread(await api(`/api/photos?tour_id=${t.id}&limit=400`).catch(() => []), PDFP.n);
    }
    $("#th").innerHTML = [...new Set(pick)].slice(0, PDFP.n).map(p => `<div class="th"><img src="/pic/${p.id}?size=500"></div>`).join("");
  };
  pdfPhotoBind(photos);
  pdfBindDl(`/api/tours/${encodeURIComponent(t.id)}/pdf`);
  await photos();
  $("#shp").onclick = () => {
    map.invalidateSize();
    setTimeout(() => print(), 300);
  };
};
const _tourSh = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourSh(id, q);
  const a = $("#egpx");
  if (a && !$("#esheet")) a.insertAdjacentHTML("afterend", `<a class="btn ghost sm" id="esheet" href="#/sheet/${encodeURIComponent(id)}" title="Druckbares Tourblatt mit Karte, Höhenprofil und Fotos">Tourblatt</a>`);
};
