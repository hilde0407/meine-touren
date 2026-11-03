/* =====================  GPS-Track korrigieren  ===================== */
function trackFixDialog(id, done) {
  const m = modal(`<h2>GPS-Track korrigieren</h2><div id="tfb" class="mut">Track wird untersucht …</div>`);
  m.querySelector(".mbox").style.maxWidth = "760px";
  (async () => {
    const b = m.querySelector("#tfb");
    let a;
    try {
      a = await api(`/api/tours/${encodeURIComponent(id)}/trackfix`);
    } catch (e) {
      b.innerHTML = `<p class="bad">${esc(e.message)}</p><div class="row"><button class="btn ghost" id="tfx">Schließen</button></div>`;
      b.querySelector("#tfx").onclick = () => m.remove();
      return;
    }
    const lim = a.limit_sustain;
    const fmtMin = s => (s >= 3600 ? Math.floor(s / 3600) + " Std. " : "") + Math.round((s % 3600) / 60) + " Min.";
    const clock = s => {
      const t = BY[id];
      return t ? new Date((t.start_ts + s) * 1000).toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"}) : "";
    };
    const none = !a.n_spikes && !a.fast.length;
    b.className = "";
    b.innerHTML = `
     <p class="mut" style="font-size:14px;margin-top:0">Gesucht wird nach <b>Ausreißern</b> (Punkte, die mit unmöglichem Tempo vom Weg wegspringen) und nach <b>schnellen Abschnitten</b> (dauerhaft über ${lim} km/h, z. B. Seilbahn, Bus oder Auto). Das Original bleibt erhalten und lässt sich zurückholen.</p>
     <div id="tfm" style="height:280px;border-radius:6px;margin:8px 0"></div>
     ${a.fixed ? `<p class="ok">✓ Bereits korrigiert: ${a.applied.spikes} Ausreißer entfernt, ${a.applied.excluded} Abschnitt(e) herausgerechnet (Strecke vorher ${nf(a.dist_km, 1)} km, jetzt ${nf(a.now_km, 1)} km). Die Liste unten zeigt, was vom Original aus gefunden wird.</p>` : ""}
     ${none ? `<p class="ok">✓ Im Track wurde nichts Auffälliges gefunden.</p>` : ""}
     ${a.n_spikes ? `<label class="chk"><input type="checkbox" id="tfs" checked> <b>${a.n_spikes} Ausreißer-Punkt${a.n_spikes > 1 ? "e" : ""}</b> in ${a.spikes.length} Stelle${a.spikes.length > 1 ? "n" : ""} entfernen</label>` : ""}
     ${a.fast.length ? `<h3 style="margin:16px 0 4px">Schnelle Abschnitte</h3><p class="mut" style="font-size:13px;margin:0 0 6px">Angehakt = als Fahrt aus Strecke und Dauer der Tour herausrechnen (der Weg bleibt auf der Karte sichtbar). Nicht angehakt = zählt als echte Bewegung.</p>
      <div class="rows">${a.fast
        .map(
          f => `<label class="r" style="cursor:pointer;display:flex;gap:8px;align-items:center"><input type="checkbox" data-f="${f.id}" checked><span>${a.has_time ? clock(f.t0) + " Uhr · " : ""}${nf(f.m / 1000, 2)} km in ${fmtMin(f.s)}<small class="mut"> · Ø ${nf(f.avg, 1)} km/h, bis ${nf(f.max, 0)} km/h</small></span></label>`
        )
        .join("")}</div>` : ""}
     ${!a.has_time ? `<p class="mut" style="font-size:13px">Dieser Track hat keine Zeitstempel – schnelle Abschnitte lassen sich daher nicht erkennen.</p>` : ""}
     <div class="row" style="margin-top:16px">${none && !a.fixed ? "" : `<button class="btn" id="tfok">${a.fixed ? "Erneut anwenden" : "Korrigieren"}</button>`}${a.fixed ? `<button class="btn alt" id="tfre">Original wiederherstellen</button>` : ""}<button class="btn ghost" id="tfno">Schließen</button><span id="tfer" class="bad"></span></div>`;
    // Karte
    try {
      const mp = L.map(b.querySelector("#tfm"), {zoomControl: true});
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 18, attribution: "© OpenStreetMap"}).addTo(mp);
      const base = L.polyline(a.line, {color: "#2a7f62", weight: 4}).addTo(mp);
      a.fast.forEach(f => L.polyline(f.line, {color: "#e8a200", weight: 6, opacity: 0.9}).addTo(mp).bindTooltip(`${nf(f.avg, 0)} km/h`));
      a.spikes.forEach(s => L.circleMarker(s.at, {radius: 7, color: "#c0392b", fillColor: "#c0392b", fillOpacity: 0.8}).addTo(mp).bindTooltip(`${s.n} Ausreißer`));
      mp.fitBounds(base.getBounds(), {padding: [20, 20]});
      setTimeout(() => mp.invalidateSize(), 50);
    } catch (e) {}
    const close = () => m.remove();
    b.querySelector("#tfno").onclick = close;
    const run = async fn => {
      b.querySelectorAll("button").forEach(x => (x.disabled = true));
      try {
        await fn();
        await loadTours();
        close();
        if (done) done(); else location.reload();
      } catch (e) {
        b.querySelectorAll("button").forEach(x => (x.disabled = false));
        b.querySelector("#tfer").textContent = e.message;
      }
    };
    const ok = b.querySelector("#tfok");
    if (ok)
      ok.onclick = () =>
        run(() =>
          api(`/api/tours/${encodeURIComponent(id)}/trackfix`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({spikes: b.querySelector("#tfs") ? b.querySelector("#tfs").checked : false, exclude: [...b.querySelectorAll("[data-f]:checked")].map(x => +x.dataset.f)}),
          })
        );
    const re = b.querySelector("#tfre");
    if (re) re.onclick = () => run(() => api(`/api/tours/${encodeURIComponent(id)}/trackfix-restore`, {method: "POST"}));
  })();
}

// Knopf im Tourdetail
const _tourTF = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourTF(id, q);
  const ef = $("#efix");
  if (!ef || $("#etfix")) return;
  const b = document.createElement("button");
  b.className = "btn ghost sm";
  b.id = "etfix";
  b.title = "Ausreißer im GPS-Track entfernen, Seilbahn-/Autofahrten aus der Wertung nehmen";
  b.textContent = "🧹 Track korrigieren";
  b.onclick = () => trackFixDialog(id);
  ef.after(b);
};
