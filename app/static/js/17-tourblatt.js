/* =====================  Tourblatt: druckbare Seite / PDF einer Tour  ===================== */
VIEWS.sheet = async id => {
  const t = BY[id];
  if (!t) throw new Error("Tour nicht gefunden");
  $("#main").innerHTML = `<div class="sheet">
   <div class="row noprint"><a class="back" href="#/tour/${esc(t.id)}">‹ Zurück zur Tour</a><span class="sp"></span><button class="btn" id="shp">🖨 Drucken / als PDF speichern</button></div>
   <div style="margin-top:14px"><span class="tag" style="background:${sCol(t.sport)}">${sName(t.sport)}</span> <span class="mut" style="margin-left:8px">${dateL(t.date)}, ${timeS(t.date)} Uhr${t.g_country ? " · " + esc([t.g_place, t.g_state, t.g_country].filter(Boolean).join(", ")) : ""}</span></div>
   <h1 style="font-size:34px;margin:8px 0 14px">${esc(t.name)}</h1>
   <div class="figs"><div class="fig"><div class="v">${nf(t.km, 2)}<span class="u">km</span></div><div class="l">Strecke</div></div><div class="fig"><div class="v">${nf(t.up_m, 0)}<span class="u">m</span></div><div class="l">Aufstieg</div></div>
   <div class="fig"><div class="v">${nf(t.down_m, 0)}<span class="u">m</span></div><div class="l">Abstieg</div></div><div class="fig"><div class="v">${Math.floor(t.h)}:${pad2(Math.round((t.h % 1) * 60))}<span class="u">Std.</span></div><div class="l">Dauer</div></div>
   <div class="fig"><div class="v">${t.h ? nf(t.km / t.h, 1) : "–"}<span class="u">km/h</span></div><div class="l">Tempo</div></div><div id="kmax" class="fig" style="display:none"><div class="v" id="kmaxv"></div><div class="l">Höchster Punkt</div></div></div>
   <div class="tmap" id="tm" style="height:360px"></div>
   <div class="panel prof" style="margin-top:18px" id="profcard"><h2>Höhenprofil</h2><div id="prof" class="mut">Wird geladen …</div></div>
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
  let pick = [];
  try {
    pick = (await api(`/api/tours/${t.id}/best-photos?n=6`)).photos; // beste Fotos: Sterne, Schärfe, verteilt
  } catch (e) {
    const ph = await api(`/api/photos?tour_id=${t.id}&limit=400`).catch(() => []),
      n = Math.min(6, ph.length);
    pick = n ? Array.from({length: n}, (_, i) => ph[Math.round((i * (ph.length - 1)) / Math.max(1, n - 1))]) : [];
  }
  $("#th").innerHTML = [...new Set(pick)].map(p => `<div class="th"><img src="/pic/${p.id}?size=500"></div>`).join("");
  $("#shp").onclick = () => {
    map.invalidateSize();
    setTimeout(() => print(), 300);
  };
};
const _tourSh = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourSh(id, q);
  const a = $("#egpx");
  if (a && !$("#esheet")) a.insertAdjacentHTML("afterend", `<a class="btn ghost sm" id="esheet" href="#/sheet/${encodeURIComponent(id)}" title="Druckbares Tourblatt mit Karte, Höhenprofil und Fotos">📄 Tourblatt</a>`);
};
