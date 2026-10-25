/* ---------- Fotos auf der Strecke ausrichten („Perlenkette“) ----------
   Ein Foto wird auf die Stelle der Strecke gezogen, an der es sicher entstanden ist. Alle anderen Fotos der Tour wandern
   entsprechend ihrem zeitlichen Abstand mit. „Speichern“ verschiebt die Aufnahmezeiten dauerhaft um diesen Betrag. */
const _zoomP = 18; // Rechengenauigkeit für das Einrasten (unabhängig vom Kartenzoom)

function photoChain(map, t, coords, ph) {
  const pts = cleanPts(coords)
    .filter(p => p[3] != null)
    .sort((a, b) => a[3] - b[3]);
  const mkIcon = p =>
    L.divIcon({className: "", html: `<div class="pm" style="background-image:url(/pic/${p.id}?size=120)"></div>`, iconSize: [36, 36]});
  const fmtT = s => new Date(s * 1000).toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit", second: "2-digit"});
  const hasTime = pts.length > 1;
  const T = pts.map(p => p[3]);
  // Punkt der Strecke zu einer Zeit (ms seit Start), an den Enden begrenzt
  const atTime = ms => {
    if (!hasTime) return pts[0] || [t.lat, t.lng];
    let lo = 0,
      hi = T.length - 1;
    if (ms <= T[0]) return pts[0];
    if (ms >= T[hi]) return pts[hi];
    while (hi - lo > 1) {
      const m = (lo + hi) >> 1;
      T[m] <= ms ? (lo = m) : (hi = m);
    }
    const u = (ms - T[lo]) / (T[hi] - T[lo] || 1);
    return [pts[lo][0] + (pts[hi][0] - pts[lo][0]) * u, pts[lo][1] + (pts[hi][1] - pts[lo][1]) * u];
  };
  const X = [],
    Y = [];
  const proj = ll => map.project(L.latLng(ll[0], ll[1]), _zoomP);
  pts.forEach(p => {
    const q = proj(p);
    X.push(q.x);
    Y.push(q.y);
  });
  // nächster Punkt auf der Strecke (auf den Teilstücken) -> {lat, lng, ms}
  const snap = latlng => {
    const c = proj([latlng.lat, latlng.lng]);
    let best = 1e30,
      res = null;
    for (let i = 0; i < pts.length - 1; i++) {
      const dx = X[i + 1] - X[i],
        dy = Y[i + 1] - Y[i],
        l2 = dx * dx + dy * dy;
      let u = l2 ? ((c.x - X[i]) * dx + (c.y - Y[i]) * dy) / l2 : 0;
      u = Math.max(0, Math.min(1, u));
      const px = X[i] + u * dx - c.x,
        py = Y[i] + u * dy - c.y,
        d = px * px + py * py;
      if (d < best) {
        best = d;
        res = {
          lat: pts[i][0] + (pts[i + 1][0] - pts[i][0]) * u,
          lng: pts[i][1] + (pts[i + 1][1] - pts[i][1]) * u,
          ms: T[i] + (T[i + 1] - T[i]) * u,
        };
      }
    }
    return res;
  };
  const rel = (p, delta = 0) => (p.taken_ts + delta - t.start_ts) * 1000;
  if (!hasTime) return; // ohne Zeitangaben in der Strecke lassen sich Fotos nicht einordnen
  const items = ph.map((p, i) => {
    const b = atTime(rel(p));
    const m = L.marker([b[0], b[1]], {icon: mkIcon(p)})
      .addTo(map)
      .on("click", () => openLb(ph, i));
    return {p, m};
  });
  items.forEach(it =>
    it.m.on("drag", e => {
      if (!active) return;
      const s = snap(e.latlng || it.m.getLatLng());
      if (!s) return;
      it.m.setLatLng([s.lat, s.lng]);
      delta = t.start_ts + s.ms / 1000 - it.p.taken_ts;
      items.forEach(o => {
        if (o === it) return;
        const b = atTime(rel(o.p, delta));
        o.m.setLatLng([b[0], b[1]]);
        o.m.setTooltipContent(fmtT(o.p.taken_ts + delta));
      });
      it.m.setTooltipContent(fmtT(it.p.taken_ts + delta));
      if ($("#chi")) $("#chi").innerHTML = info();
      if ($("#chok")) $("#chok").disabled = !delta;
    })
  );
  window._chain = {items, snap, atTime}; // für Tests und Fehlersuche

  // ---- Bedienung ----
  const head = document.querySelector("#ss");
  if (!head) return;
  head.insertAdjacentHTML(
    "beforebegin",
    `<button class="btn alt sm" id="chb" title="Ein Foto auf die richtige Stelle der Strecke ziehen – die anderen wandern zeitlich mit">📍 Fotos ausrichten</button>`
  );
  const bar = document.createElement("div");
  bar.className = "panel";
  bar.style.cssText = "display:none;margin:0 0 12px";
  document.getElementById("tm").insertAdjacentElement("afterend", bar);
  let delta = 0,
    active = false;
  const info = () => {
    const a = Math.abs(Math.round(delta)),
      h = Math.floor(a / 3600),
      m = Math.floor((a % 3600) / 60),
      s = a % 60;
    return delta ? `Zeitversatz: <b>${delta < 0 ? "−" : "+"}${h ? h + " Std. " : ""}${m} Min. ${s} Sek.</b>` : "Noch nichts verschoben";
  };
  const show = () => {
    bar.innerHTML = `<b>Fotos ausrichten:</b> Ziehe ein Foto auf der Karte an die Stelle der Strecke, an der du sicher bist, dass es dort aufgenommen wurde. Alle anderen Fotos wandern wie auf einer Perlenkette im gleichen zeitlichen Abstand mit.
     <div class="row" style="margin-top:8px"><span id="chi">${info()}</span><span class="sp"></span>
      <select id="chs" title="Welche Fotos verschoben werden"><option value="tour">nur Fotos dieser Tour</option><option value="day">auch andere Fotos desselben Tages</option></select>
      <button class="btn sm" id="chok" ${delta ? "" : "disabled"}>Speichern</button><button class="btn alt sm" id="chre" title="Alle bisherigen Zeitverschiebungen der Fotos dieser Tour zurücknehmen">Original-Zeiten</button><button class="btn alt sm" id="chno">Abbrechen</button><span id="cher" class="bad"></span></div>`;
    $("#chno").onclick = () => end(true);
    $("#chre").onclick = async () => {
      if (!confirm("Alle Zeitverschiebungen der Fotos dieser Tour zurücknehmen (zurück auf die Aufnahmezeit der Kamera)?")) return;
      try {
        await api("/api/photo-shift", {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({tour_id: t.id, reset: true, scope: $("#chs").value}),
        });
        route();
      } catch (e) {
        $("#cher").textContent = e.message;
      }
    };
    $("#chok").onclick = async () => {
      try {
        await api("/api/photo-shift", {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({tour_id: t.id, delta_s: Math.round(delta), scope: $("#chs").value}),
        });
        route();
      } catch (e) {
        $("#cher").textContent = e.message;
      }
    };
  };
  const place = d =>
    items.forEach(it => {
      const b = atTime(rel(it.p, d));
      it.m.setLatLng([b[0], b[1]]);
      if (active) it.m.setTooltipContent(fmtT(it.p.taken_ts + d));
    });
  function end(cancel) {
    active = false;
    bar.style.display = "none";
    $("#chb").style.display = "";
    items.forEach(it => {
      it.m.dragging.disable();
      it.m.unbindTooltip();
    });
    if (cancel) {
      delta = 0;
      place(0);
    }
  }
  $("#chb").onclick = () => {
    active = true;
    delta = 0;
    bar.style.display = "";
    document.getElementById("tm").scrollIntoView({block: "center", behavior: "instant"}); // die Karte steht über den Fotos
    $("#chb").style.display = "none";
    show();
    items.forEach(it => {
      it.m.bindTooltip(fmtT(it.p.taken_ts), {permanent: true, direction: "top", offset: [0, -20], className: "chtip"});
      it.m.dragging.enable();
    });
    place(0);
  };
}
