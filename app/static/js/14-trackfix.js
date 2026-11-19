/* =====================  GPS-Track korrigieren  ===================== */
function trackFixDialog(id, done) {
  const m = modal(`<h2>GPS-Track korrigieren</h2><div id="tfb" class="mut">Track wird untersucht …</div>`);
  m.querySelector(".uibox").classList.add("tfbox");
  (async () => {
    const b = m.querySelector("#tfb");
    let a;
    try {
      a = await api(`/api/tours/${encodeURIComponent(id)}/trackfix`);
    } catch (e) {
      b.innerHTML = `<p class="bad">${esc(e.message)}</p><div class="uifoot"><button class="btn ghost" id="tfx">Schließen</button></div>`;
      b.querySelector("#tfx").onclick = () => m.remove();
      return;
    }
    const lim = a.limit_sustain;
    const fmtMin = s => fmtDauer(s);
    const clock = s => {
      const t = BY[id];
      return t ? fmtUhrzeit(t.start_ts + s, {uhr: false}) : "";
    };
    const none = !a.n_spikes && !a.fast.length;
    const hm = ts => fmtUhrzeit(ts, {uhr: false});
    const avg = a.dur_s > 0 ? a.dist_km / (a.dur_s / 3600) : 0;
    const showT = a.timing.uniform || !!(a.photos && avg > a.limit_sustain * 0.6);
    const initS = a.photos ? a.photos.last - a.photos.first : a.timing.est_s || a.dur_s;
    b.className = "";
    b.innerHTML = `
     <p class="mut fs14 mt0">Gesucht wird nach <b>Ausreißern</b> (Punkte, die mit unmöglichem Tempo vom Weg wegspringen) und nach <b>schnellen Abschnitten</b> (dauerhaft über ${lim} km/h, z. B. Seilbahn, Bus oder Auto) sowie nach <b>GPS-Zittern</b>, das die Strecke künstlich verlängert. Das Original bleibt erhalten und lässt sich zurückholen.</p>
     <div id="tfm" class="br6 m8-0" style="height:280px"></div>
     ${a.fixed ? `<p class="ok">✓ Bereits korrigiert: ${a.applied.spikes} Ausreißer entfernt, ${a.applied.excluded} Abschnitt(e) herausgerechnet (Strecke vorher ${fmtKm(a.dist_km)}, jetzt ${fmtKm(a.now_km)}). Die Liste unten zeigt, was vom Original aus gefunden wird.</p>` : ""}
     ${none && !a.timing.uniform ? `<p class="ok">✓ Im Track wurde nichts Auffälliges gefunden.</p><div id="tfack" class="panel p10-14 m10-0" hidden></div>` : ""}
     ${showT ? `<div class="panel p10-14 m10-0" style="border-left:4px solid var(--yellow)">${a.timing.uniform ? `<b>Die Zeitangaben stammen nicht von einer echten Aufzeichnung.</b> In jedem Abschnitt der Tour ist das Tempo exakt gleich (Ø ${fmtTempo(a.dist_km / (a.dur_s / 3600))}) – die Zeitpunkte sind nur gleichmäßig über die Strecke verteilt, z. B. bei einer geplanten Route. Die Dauer von ${fmtMin(a.dur_s)} ist deshalb nicht glaubwürdig.` : `<b>Das Durchschnittstempo (${fmtTempo(a.dist_km / (a.dur_s / 3600))}) ist für diese Sportart ungewöhnlich hoch.</b> Vielleicht stimmt die Dauer nicht.`}
       <label class="chk mt8"><input type="checkbox" id="tfd" ${a.timing.uniform ? "checked" : ""}> <b>Dauer korrigieren auf</b> <input id="tfdh" type="number" min="0" max="99" style="width:64px" value="${hmParts(initS)[0]}"> Std. <input id="tfdm" type="number" min="0" max="59" style="width:64px" value="${hmParts(initS)[1]}"> Min.</label>
       ${a.photos ? `<div class="row m4-0 g6 aic"><button class="btn alt sm" type="button" id="tfph">Aus den Fotos übernehmen</button><span class="mut fs13">${a.photos.n} Fotos von ${hm(a.photos.first)} bis ${hm(a.photos.last)} Uhr = ${fmtMin(a.photos.last - a.photos.first)}</span></div><label class="chk m2-0"><input type="checkbox" id="tfst"> Start der Tour auf die Zeit des ersten Fotos (${hm(a.photos.first)} Uhr) setzen</label>` : ""}
       <span class="mut fs13">${a.timing.est_s ? "Vorschlag nach Strecke und Aufstieg (Wanderzeit nach SAC-Formel, ohne Pausen); du kannst den Wert ändern. " : ""}Die Zeitpunkte im Track werden entsprechend gestreckt, schnelle Abschnitte werden bei solchen Zeiten nicht gesucht.</span></div>` : ""}
     ${a.anchors ? `<div class="panel p10-14 m10-0" style="border-left:4px solid var(--green,#2a7f62)"><label class="chk m0"><input type="checkbox" id="tfa" ${a.timing.uniform || avg > a.limit_sustain * 0.6 ? "checked" : ""}> <b>Zeit aus den Foto-Positionen ableiten</b></label>
       <span class="mut fs13">${a.anchors.n} Fotos mit Aufnahmeort liegen auf dem Track. Ihre Aufnahmezeiten legen fest, wann du wo warst (Pausen eingeschlossen): Start ${hm(a.anchors.start)} Uhr, Ende ${hm(a.anchors.end)} Uhr, Dauer ${fmtMin(a.anchors.dur_s)}. Das ist genauer als eine Schätzung und ersetzt „Dauer korrigieren“.</span></div>` : ""}
     ${a.n_spikes ? `<label class="chk"><input type="checkbox" id="tfs" checked> <b>${a.n_spikes} Ausreißer-Punkt${a.n_spikes > 1 ? "e" : ""}</b> in ${a.spikes.length} Stelle${a.spikes.length > 1 ? "n" : ""} entfernen</label>` : ""}
     ${a.fast.length ? `<h3 class="m16-0-4">Schnelle Abschnitte</h3><p class="mut fs13 m0-0-6">Nichts ist vorgewählt. Anhaken = als Fahrt aus Strecke und Dauer herausrechnen (der Weg bleibt auf der Karte sichtbar). Bitte Karte und Uhrzeit prüfen: Nur echte Fahrten (Seilbahn, Bus, Auto) anhaken, keine Wegstücke, die du gelaufen bist.</p>
      <div class="rows">${a.fast
        .map(
          f => `<label class="r cp g8 aic" style="display:flex"><input type="checkbox" data-f="${f.id}"><span>${a.has_time ? clock(f.t0) + " Uhr · " : ""}${fmtKm(f.m / 1000)} in ${fmtMin(f.s)}<small class="mut"> · Ø ${fmtTempo(f.avg)}, bis ${fmtTempo(f.max, {d: 0})}</small></span></label>`
        )
        .join("")}</div>` : ""}
     ${a.jitter_m >= 200 && a.jitter_m >= a.raw_m * 0.03 ? `<label class="chk"><input type="checkbox" id="tfj"> <b>GPS-Zittern glätten:</b> der Track ist durch Messrauschen etwa ${fmtKm(a.jitter_m / 1000)} (${Math.round((a.jitter_m / a.raw_m) * 100)} %) zu lang. Die Länge wird entsprechend verringert, der Weg bleibt unverändert.</label>` : ""}
     <p id="tfp" class="panel p10-14 m14-0-0 fs14"></p>
     ${!a.has_time ? `<p class="mut fs13">Dieser Track hat keine Zeitstempel – schnelle Abschnitte lassen sich daher nicht erkennen.</p>` : ""}
     <div id="tfer" class="bad"></div><div class="uifoot"><button class="btn ghost" id="tfno">Schließen</button>${a.fixed ? `<button class="btn alt" id="tfre">Original wiederherstellen</button>` : ""}${none && !a.fixed && !a.timing.uniform ? "" : `<button class="btn" id="tfok">${a.fixed ? "Erneut anwenden" : "Korrigieren"}</button>`}</div>`;
    const preview = () => {
      let d = a.dist_km * 1000,
        s = a.dur_s;
      if (b.querySelector("#tfa")?.checked) s = a.anchors.dur_s;
      else if (b.querySelector("#tfd")?.checked) s = (+b.querySelector("#tfdh").value || 0) * 3600 + (+b.querySelector("#tfdm").value || 0) * 60;
      if (b.querySelector("#tfs")?.checked) d -= a.spike_m;
      b.querySelectorAll("[data-f]:checked").forEach(x => {
        const f = a.fast[+x.dataset.f];
        d -= f.m;
        s -= f.s;
      });
      if (b.querySelector("#tfj")?.checked) d -= a.jitter_m;
      const v = (km, sec) => (sec > 0 ? nf(km / (sec / 3600), 1) : "–");
      b.querySelector("#tfp").innerHTML = `Original: <b>${fmtKm(a.dist_km)}</b> in ${fmtMin(a.dur_s)} (Ø ${v(a.dist_km, a.dur_s)} km/h)<br>Nach der Korrektur: <b>${fmtKm(Math.max(0, d) / 1000)}</b> in ${fmtMin(Math.max(0, s))} (Ø ${v(Math.max(0, d) / 1000, s)} km/h)`;
    };
    const ph = b.querySelector("#tfph");
    if (ph)
      ph.onclick = () => {
        const d = a.photos.last - a.photos.first;
        b.querySelector("#tfdh").value = hmParts(d)[0];
        b.querySelector("#tfdm").value = hmParts(d)[1];
        b.querySelector("#tfd").checked = true;
        b.querySelector("#tfst").checked = true;
        preview();
      };
    b.querySelectorAll("input").forEach(x => (x.onchange = x.oninput = preview));
    preview();
    // Karte
    try {
      const mp = L.map(b.querySelector("#tfm"), {zoomControl: true});
      tileL("osm", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 18, attribution: "© OpenStreetMap"}).addTo(mp);
      const base = L.polyline(a.line, {color: "#2a7f62", weight: 4}).addTo(mp);
      a.fast.forEach(f => L.polyline(f.line, {color: "#e8a200", weight: 6, opacity: 0.9}).addTo(mp).bindTooltip(`${fmtTempo(f.avg, {d: 0})}`));
      a.spikes.forEach(s => L.circleMarker(s.at, {radius: 7, color: "#c0392b", fillColor: "#c0392b", fillOpacity: 0.8}).addTo(mp).bindTooltip(`${s.n} Ausreißer`));
      mp.fitBounds(base.getBounds(), {padding: [20, 20]});
      setTimeout(() => mp.invalidateSize(), 50);
    } catch (e) {}
    const close = () => m.remove();
    b.querySelector("#tfno").onclick = close;
    // 3.16.1: Steht die Tour noch in „Auffällige Touren“ (z. B. nur wegen Pausen), kann sie hier als geprüft markiert werden.
    const ackBox = b.querySelector("#tfack");
    if (ackBox)
      api(`/api/tours/${encodeURIComponent(id)}/quality-flags`)
        .then(q => {
          if (!q.flags || !q.flags.length) return;
          ackBox.innerHTML = `<p class="m0">Diese Tour steht noch in der Liste „Auffällige Touren“. Als geprüft markieren?</p><div class="row mt8"><button class="btn alt sm" type="button" id="tfack1">Als geprüft markieren</button><span id="tfacke" class="bad"></span></div>`;
          ackBox.hidden = false;
          ackBox.querySelector("#tfack1").onclick = async ev => {
            ev.target.disabled = true;
            try {
              await api(`/api/tours/${encodeURIComponent(id)}/quality-ack`, {method: "POST"});
              await loadTours().catch(() => {});
              close();
              if (done) done();
            } catch (e) {
              ev.target.disabled = false;
              ackBox.querySelector("#tfacke").textContent = e.message;
            }
          };
        })
        .catch(() => {});
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
            body: JSON.stringify({spikes: b.querySelector("#tfs") ? b.querySelector("#tfs").checked : false, exclude: [...b.querySelectorAll("[data-f]:checked")].map(x => +x.dataset.f), smooth: !!b.querySelector("#tfj")?.checked, start_ts: b.querySelector("#tfst")?.checked && !b.querySelector("#tfa")?.checked ? a.photos.first : null, anchors: !!b.querySelector("#tfa")?.checked, dur_s: b.querySelector("#tfd")?.checked && !b.querySelector("#tfa")?.checked ? (+b.querySelector("#tfdh").value || 0) * 3600 + (+b.querySelector("#tfdm").value || 0) * 60 : null}),
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
