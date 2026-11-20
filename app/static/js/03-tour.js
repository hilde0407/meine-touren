/* ---------- Upload zu Portalen ---------- */
const UPST = {
  uploaded: "hochgeladen",
  linked: "bei Komoot vorhanden",
  duplicate: "dort schon vorhanden",
  pending: "wird verarbeitet",
  error: "Fehler",
};
async function uploadChips(t) {
  const box = $("#upst");
  if (!box) return;
  let st = await api(`/api/tours/${encodeURIComponent(t.id)}/uploads`).catch(() => ({}));
  const nm = {komoot: "Komoot", strava: "Strava"};
  if (st.komoot && ["uploaded", "pending"].includes(st.komoot.status)) {
    const c = await api(`/api/tours/${encodeURIComponent(t.id)}/komoot-check`, {method: "POST"}).catch(() => ({}));
    if (c.checked && !c.exists) {
      st = await api(`/api/tours/${encodeURIComponent(t.id)}/uploads`).catch(() => ({}));
      box.dataset.warn = "1";
      box.insertAdjacentHTML(
        "beforebegin",
        '<p class="bad m6-0">Die Tour wurde bei Komoot nicht gefunden – sie kann jetzt erneut hochgeladen werden.</p>'
      );
    }
  }
  box.innerHTML = Object.entries(st)
    .filter(([, v]) => v.status !== "error")
    .map(
      ([k, v]) =>
        `<span class="chip">${v.url ? `<a target="_blank" href="${esc(v.url)}">${nm[k] || k} ↗</a>` : nm[k] || k} · ${UPST[v.status] || v.status}</span>`
    )
    .join(" ");
}
async function uploadDialog(t) {
  let pf, st;
  try {
    [pf, st] = await Promise.all([api("/api/portals"), api(`/api/tours/${encodeURIComponent(t.id)}/uploads`)]);
  } catch (e) {
    return uiAlert(e.message);
  }
  const rows = pf.portals
    .map(p => {
      const fromHere = p.id === "komoot" && t.source !== "local",
        s = st[p.id],
        done = s && ["uploaded", "linked", "duplicate", "pending"].includes(s.status);
      const why = fromHere
        ? "Die Tour stammt von Komoot"
        : !p.connected
          ? p.id === "strava"
            ? "nicht verbunden (Verwaltung → Portale)"
            : "Zugang fehlt (Verwaltung)"
          : done
            ? UPST[s.status] +
              (s.url ? ` – <a target="_blank" href="${esc(s.url)}">öffnen</a>` : "") +
              (s.msg ? `<br><span class="fs12">${esc(s.msg)}</span>` : "") +
              `<br><span class="fs12">„hochgeladen“ = vom Portal angenommen und geprüft; bei Komoot erscheint die Tour in der Tourenliste bzw. unter „Geplant“.</span>`
            : s && s.status === "error"
              ? `<span class="bad">letzter Versuch: ${esc(s.msg)}</span>`
              : "";
      return `<label class="chk m8-0" style="display:block"><input type="checkbox" class="pp cb" value="${p.id}" ${fromHere || !p.connected || done ? "disabled" : ""}> <b>${p.name}</b> <span class="mut">${why}</span>${done && p.connected && !fromHere ? `<br><label class="fs12 ml22"><input type="checkbox" class="ff cb" data-p="${p.id}"> trotzdem erneut hochladen (z. B. wenn die Tour bei ${p.name} fehlt)</label>` : ""}</label>`;
    })
    .join("");
  const m = uiModal(`<h3>Tour hochladen</h3><p class="mut">„${esc(t.name)}“ wird mit der lokal gespeicherten Strecke zu den gewählten Portalen gesendet. Es passiert nichts ohne dein Häkchen.</p>${rows}<div id="upr" class="mt10"></div>
    <div class="uifoot"><button class="btn ghost" id="ucx">Schließen</button><button class="btn" id="uok">Hochladen</button></div>`);
  m.querySelector("#ucx").onclick = () => m.remove();
  m.querySelectorAll(".ff").forEach(
    f =>
      (f.onchange = () => {
        const c = m.querySelector(`.pp[value="${f.dataset.p}"]`);
        c.disabled = !f.checked;
        c.checked = f.checked;
      })
  );
  m.querySelector("#uok").onclick = async e => {
    const ps = [...m.querySelectorAll(".pp:checked")].map(c => c.value);
    if (!ps.length) return;
    const force = !!m.querySelector(".ff:checked");
    e.target.disabled = true;
    m.querySelector("#upr").innerHTML = '<span class="mut">Wird hochgeladen … (Strava kann bis zu 50 s brauchen)</span>';
    try {
      const r = await api(`/api/tours/${encodeURIComponent(t.id)}/upload`, {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({portals: ps, force}),
      });
      m.querySelector("#upr").innerHTML = Object.entries(r)
        .map(
          ([k, v]) =>
            `<div class="${v.status === "error" ? "bad" : "ok"}"><b>${k === "komoot" ? "Komoot" : "Strava"}:</b> ${v.status === "uploaded" ? "hochgeladen ✓" : v.status === "duplicate" ? "dort schon vorhanden" : v.status === "already" ? "schon erledigt" : esc(v.msg || v.status)}${v.url ? ` – <a target="_blank" href="${esc(v.url)}">öffnen</a>` : ""}</div>`
        )
        .join("");
    } catch (er) {
      m.querySelector("#upr").innerHTML = `<span class="bad">${esc(er.message)}</span>`;
    }
    e.target.disabled = false;
    uploadChips(t);
  };
}

/* ---------- Tourseite und Unterseite „Auswertung“ (3.16.0) ----------
   #/tour/<id>            Hauptseite: Kopf, Karte, Höhenprofil (mit Puls), Wegpunkte, Einstieg „Detaillierte Auswertung“, Fotos (Bewertung, Notiz, Ausrüstung, Sicherheit stehen wie in 3.14.0 im Kopf)
   #/tour/<id>/auswertung Unterseite: Aufzeichnung (Gerät, Messwerte, Training laut Uhr, Wetter) und Auswertung (Analyse, Tempo nach Steigung, Ähnliche Touren, Vergleich)
   Die Module für die Detail-Karten (08, 26, 43, 45, 46, 47) hängen ihre Karten an tlAnc(): auf der Hauptseite das Höhenprofil (dort nimmt 48-tourlayout.js sie
   sofort wieder heraus und merkt sich nur die Kurzaussage für den Einstieg), auf der Unterseite ein unsichtbarer Anker im Container der Unterseite. */
const tlAnc = () => $("#profcard") || $("#tlsubanc");
const TL_DETAIL = [];
/* Ein Modul meldet hier, wie es seine Karte(n) für die Unterseite aufbaut: fn(t) → Promise (fertig, wenn Daten geladen und Karten eingehängt sind) */
const tlOnSub = fn => TL_DETAIL.push(fn);
VIEWS.tourauswertung = async id => {
  const t = BY[id];
  if (!t) throw new Error("Tour nicht gefunden");
  const hm = fmtDauer(t.h * 3600);
  $("#main").innerHTML =
    `<div class="row"><a class="back" id="tlback" href="#/tour/${esc(String(t.id))}">‹ Zurück zur Tour</a></div>
   <div class="tlsubhead"><span class="tlsubeb">Detaillierte Auswertung</span>
   <h1 class="tlsubt">${esc(t.name)}</h1>
   <p class="tlsubfig"><span class="tag" style="background:${sCol(t.sport)}">${sName(t.sport)}</span> <span>${fmtDatum(t.date)}</span> <span>${fmtKm(t.km)}</span> <span>${fmtAuf(t.up_m)}</span> <span>${hm}</span>${t.h ? ` <span>${fmtTempo(t.km / t.h)}</span>` : ""}</p></div>
   <nav class="tlnav" id="tlnav" aria-label="Abschnitte dieser Auswertung" hidden></nav>
   <p class="mut tlload" id="tlload" role="status">Auswertung wird geladen …</p>
   <div class="tlx tlsub" id="tl" data-tid="${esc(String(t.id))}"><div id="tlsubanc" hidden></div>
   <section class="tlg" id="tlg-rec" aria-labelledby="tlgh-rec" hidden><h2 class="tlgh" id="tlgh-rec">Aufzeichnung</h2><div class="tlgb" id="tlgb-rec"></div></section>
   <section class="tlg" id="tlg-eval" aria-labelledby="tlgh-eval" hidden><h2 class="tlgh" id="tlgh-eval">Auswertung dieser Tour</h2><div class="tlgb" id="tlgb-eval"></div></section>
   <div class="empty tlempty" id="tlempty" hidden><h2>Für diese Tour gibt es keine Auswertung</h2><p class="mut">Es liegen weder Messwerte noch Uhr-Daten oder eine Strecke mit Höhen vor.</p><p><a class="btn alt" href="#/tour/${esc(String(t.id))}">‹ Zurück zur Tour</a></p></div></div>`;
  await Promise.allSettled(TL_DETAIL.map(f => Promise.resolve().then(() => f(t))));
  if (!$("#tl.tlsub")) return;                                     // inzwischen eine andere Seite
  if (window.tlRefresh) tlRefresh();
  $("#tlload").hidden = true;
  const any = [...document.querySelectorAll("#tl details.tls")].some(d => !d.hidden && !d.closest(".sl-off"));
  $("#tlempty").hidden = any;
  if ($("#tlnav") && !any) $("#tlnav").hidden = true;
};

/* ---------- Fotos der Tourseite (3.51.0): fester Foto-Streifen mit den besten Fotos, volles Raster erst auf Wunsch, seitenweise ---------- */
const PH_STRIP_N = 12,
  PH_STRIP_PX = 300,        // Kantenlänge der Streifenbilder (Server: photos.STRIP_SIZE)
  PH_PAGE = 60;
/* Gerüst mit fester Höhe, bevor die Fotoliste da ist: t.photos (Tourenliste) sagt schon, ob und wie viele Fotos es gibt – nichts springt */
function phSecHtml(t) {
  const n = +t.photos || 0,
    sk = Array.from({length: Math.min(n, PH_STRIP_N)}, () => '<span class="phi phsk"></span>').join("");
  return (
    `<div id="phbox"><div class="phstrip" id="phs" role="list" aria-label="Ausgewählte Fotos"${n ? "" : " hidden"}>${sk}</div>` +
    `<div class="phmore" id="phm"${n > PH_STRIP_N ? "" : " hidden"}><button class="btn sm ghost" id="phall" aria-expanded="false" aria-controls="th">Alle ${n} Fotos</button></div>` +
    `<div class="thumbs" id="th" hidden></div><div class="phpg" id="phpg" hidden><button class="btn sm alt" id="phnext">Mehr anzeigen</button></div></div>`
  );
}
/* Streifen zeichnen; liefert das Raster-Objekt {open(on)} (Raster erst beim Öffnen, in Blöcken zu PH_PAGE Fotos) */
function phStrip(ph) {
  const strip = $("#phs"),
    more = $("#phm"),
    th = $("#th"),
    pg = $("#phpg"),
    box = $("#phbox");
  let pick = ph.map((p, i) => [p, i]).filter(([p]) => p.s);
  if (!pick.length) pick = ph.slice(0, PH_STRIP_N).map((p, i) => [p, i]);
  const showAll = ph.length > pick.length;
  strip.hidden = !ph.length;
  strip.innerHTML = pick
    .map(
      ([p, i]) =>
        `<span class="phi" role="listitem"><img src="${picSrc(p, PH_STRIP_PX)}" width="104" height="104" loading="lazy" decoding="async" alt="" title="${fmtDatumKurz(p.taken_ts, {zeit: true})}" data-i="${i}"></span>`
    )
    .join("");
  more.hidden = !showAll;
  const btn = $("#phall");
  let shown = 0,
    isOpen = false,
    io = null;
  const label = () => (btn.textContent = isOpen ? "Weniger zeigen" : `Alle ${ph.length} Fotos`);
  const page = () => {
    const part = ph.slice(shown, shown + PH_PAGE);
    th.insertAdjacentHTML(
      "beforeend",
      part
        .map(
          (p, j) =>
            `<div class="th"><img loading="lazy" decoding="async" src="${picSrc(p, 500)}" data-i="${shown + j}" alt=""><span class="cap">${fmtDatumKurz(p.taken_ts, {zeit: true})}${p.manual === 1 ? " 📌" : ""}</span></div>`
        )
        .join("")
    );
    shown += part.length;
    pg.hidden = shown >= ph.length;
    bindThumbs(th, ph);
    if (box._selPaint) box._selPaint();
    if (shown >= ph.length && io) io.disconnect();
  };
  const open = on => {
    if (on === isOpen) return;
    isOpen = on;
    if (on && !shown) page();
    th.hidden = !on;
    pg.hidden = !on || shown >= ph.length;
    strip.hidden = on || !ph.length;
    more.hidden = !showAll && !on;
    btn.setAttribute("aria-expanded", String(on));
    label();
    if (on && !io && "IntersectionObserver" in window && shown < ph.length) {
      io = new IntersectionObserver(es => es.some(e => e.isIntersecting) && !pg.hidden && page(), {rootMargin: "400px 0px"});
      io.observe(pg);
    }
  };
  label();
  btn.onclick = () => open(!isOpen);
  $("#phnext").onclick = page;
  bindThumbs(strip, ph);
  return {open};
}

/* ---------- Tourdetail ---------- */
VIEWS.tour = async id => {
  const t = BY[id];
  if (!t) throw new Error("Tour nicht gefunden");
  const i = TOURS.indexOf(t),
    nx = TOURS[i - 1],
    pv = TOURS[i + 1];
  $("#main").innerHTML =
    `<div class="row"><a class="back" href="${window._from || "#/tours"}">${window._from ? (window._from.startsWith("#/trip/") ? "‹ Zurück zur Reise" : "‹ Zurück zum Album") : "‹ Alle Touren"}</a><span class="sp"></span>${pv ? `<a class="btn ghost sm" href="#/tour/${pv.id}">Vorherige</a>` : ""}${nx ? `<a class="btn ghost sm" href="#/tour/${nx.id}">Nächste</a>` : ""}</div>
   <div class="mt18"><span class="tag" style="background:${sCol(t.sport)}">${sName(t.sport)}</span> <span class="mut ml8">${fmtDatum(t.date, {zeit: true})}</span>${t.g_country ? `<span class="mut ml8">· ${esc([t.g_place, t.g_state, t.g_country].filter(Boolean).join(", "))}</span>` : ""}</div>
   <h1 class="m10-0-18" style="font-size:clamp(34px,5vw,56px)"><span id="tname">${esc(t.name)}</span> <button class="btn ghost sm vam fs15" id="ren" title="Tour umbenennen">✎ Umbenennen</button></h1>
   <div class="row mn6-0-14">${t.source === "local" ? `<span class="tag" style="background:var(--yellow);color:#000" title="Diese Tour liegt nur lokal vor (Strecke als GPX im Datenordner)">lokal gespeichert</span>` : `<button class="btn ghost sm" id="ksync" title="Daten und GPS-Track neu von Komoot laden">⟳ Mit Komoot abgleichen</button>`}<button class="btn ghost sm" id="eup" title="Zu Komoot, Strava … hochladen">⬆ Hochladen</button><a class="btn ghost sm" id="egpx" href="/api/tours/${encodeURIComponent(t.id)}/gpx" title="Strecke als GPX-Datei herunterladen">⬇ GPX</a><button class="btn ghost sm" id="edel" title="Tour löschen">🗑 Löschen</button><button class="btn ghost sm" id="etag" title="Schlagworte / Alben">🏷 Tags</button><button class="btn ghost sm" id="eshr" title="Öffentlichen Link erzeugen">🔗 Teilen</button><button class="btn ghost sm" id="etc" title="Farbe und Breite der Strecke">🎨 Streckenfarbe</button><button class="btn ghost sm" id="efix" title="Höhen mit Geländemodell neu berechnen"></button><button class="btn ghost sm" id="ezepp" title="Auf-/Abstieg aus der barometrischen Höhe der Zepp-Uhr übernehmen">⌚ Höhe aus Uhr abgleichen (Zepp)</button><span id="ksm" class="mut fs14"></span></div><div id="upst" class="chips mn4-0-10"></div><div id="tagl" class="chips mn4-0-12"></div><div id="ewarn"></div>
   <div class="figs"><div class="fig"><div class="v">${fmtKm(t.km, {einheit: false})}<span class="u">km</span></div><div class="l">Strecke</div></div><div class="fig"><div class="v">${nf(t.up_m, 0)}<span class="u">m</span></div><div class="l">Aufstieg</div></div>
   <div class="fig"><div class="v">${nf(t.down_m, 0)}<span class="u">m</span></div><div class="l">Abstieg</div></div><div class="fig"><div class="v">${fmtDauerTeile(t.h * 3600).v}<span class="u">${fmtDauerTeile(t.h * 3600).u}</span></div><div class="l">Dauer</div></div>
   <div class="fig"><div class="v">${t.h ? nf(t.km / t.h, 1) : "–"}<span class="u">km/h</span></div><div class="l">Tempo im Schnitt</div></div><div id="kmax" class="fig" style="display:none"><div class="v" id="kmaxv"></div><div class="l">Höchster Punkt</div></div></div>
   <div class="tlx" id="tl" data-tid="${esc(String(t.id))}">
   <section class="tlg" id="tlg-route" aria-labelledby="tlgh-route"><h2 class="tlgh" id="tlgh-route">Streckenverlauf</h2><div class="tlgb" id="tlgb-route">
   ${tlSecHtml({id: "map", key: "tl_map", icon: "map", title: "Karte", badge: `${fmtKm(t.km)}`, def: true, bodyCls: "tlmap", body: '<div class="tmap" id="tm"></div>'})}
   ${tlSecHtml({id: "prof", key: "tl_prof", icon: "prof", title: "Höhenprofil", def: true, bodyCls: "tlprof", body: '<div class="prof" id="profcard"><div id="prof" class="mut">Wird geladen …</div></div>'})}
   </div></section>
   <section class="tlg tlsumg" id="tlg-sum" aria-labelledby="tlgh-sum" hidden><h2 class="tlgh" id="tlgh-sum">Auswertung dieser Tour</h2><div class="tlgb" id="tlgb-sum"></div></section>
   <section class="tlg" id="tlg-more" aria-labelledby="tlgh-more"><h2 class="tlgh" id="tlgh-more">Fotos zur Tour</h2><div class="tlgb" id="tlgb-more">
   ${tlSecHtml({id: "photos", key: "tl_photos", icon: "cam", title: "Fotos", def: true, body: '<div class="tlbar"><span class="sub" id="pc"></span><span class="sp"></span><button class="btn sm alt" id="padd">Fotos hinzufügen …</button><button class="btn sm alt" id="pgps" title="Vergleicht den Aufnahmeort der Fotos mit der Strecke und korrigiert eine falsch gestellte Kamerauhr">Zeit per GPS prüfen</button><a class="btn sm" id="ss" hidden target="_blank">Diashow</a></div>' + phSecHtml(t)})}
   </div></section></div>
   ${t.source === "local" ? "" : `<p class="mt30"><a class="back" target="_blank" href="https://www.komoot.com/tour/${t.id}">In Komoot öffnen</a></p>`}`;
  map = mkMap("tm", {layers: true});
  map.setView([t.lat || 50, t.lng || 8], 12);
  let tl = null,
    cl = null,
    tseg = null,
    tcc = [],
    tleg = null,
    hrF = null,
    hrMax = 185;
  const paintBy = () => {
    if (tseg) {
      map.removeLayer(tseg);
      tseg = null;
    }
    if (tleg) {
      tleg.remove();
      tleg = null;
    }
    if (!tl) return;
    const on = TS.by !== "none" && tcc.length > 8 && (TS.by !== "hr" || hrF);
    tl.setStyle({opacity: on ? 0 : 0.92});
    if (!on) return;
    const n = tcc.length,
      d = [0];
    for (let i = 1; i < n; i++) d.push(d[i - 1] + hav(tcc[i - 1], tcc[i]));
    const w = 3,
      val = i => {
        const a = Math.max(0, i - w),
          b = Math.min(n - 1, i + w + 1),
          dd = d[b] - d[a] || 1;
        if (TS.by === "hr") return tcc[i][3] != null ? hrF((tcc[i][3] - tcc[0][3]) / 1000) : null;
        if (TS.by === "grade") return tcc[a][2] != null && tcc[b][2] != null ? ((tcc[b][2] - tcc[a][2]) / dd) * 100 : 0;
        return tcc[a][3] != null && tcc[b][3] != null && tcc[b][3] > tcc[a][3] ? (dd / ((tcc[b][3] - tcc[a][3]) / 1000)) * 3.6 : null;
      };
    const v = tcc.slice(0, n - 1).map((_, i) => val(i)),
      s = v.filter(x => x != null).sort((a, b) => a - b);
    const q = f => (s.length ? s[Math.min(s.length - 1, Math.floor(f * s.length))] : 0),
      cuts = [q(0.2), q(0.4), q(0.6), q(0.8)],
      SC = ["#2b6cb0", "#63b3ed", "#68d391", "#f6ad55", "#e53e3e"];
    const col = x => (TS.by === "grade" ? grCol(x) : x == null ? "#999" : TS.by === "hr" ? HR_ZC[hrZone(x, hrMax)] : SC[cuts.filter(c => x >= c).length]);
    tseg = L.layerGroup(
      v.map((x, i) =>
        L.polyline(
          [
            [tcc[i][0], tcc[i][1]],
            [tcc[i + 1][0], tcc[i + 1][1]],
          ],
          {color: col(x), weight: TS.weight + 1, opacity: 0.95, lineCap: "butt"}
        ).bindTooltip(x == null ? "–" : TS.by === "grade" ? `${nf(x, 0)} % Steigung` : TS.by === "hr" ? `${x} bpm` : `${fmtTempo(x)}`)
      )
    ).addTo(map);
    tleg = document.createElement("div");
    tleg.className = "tleg";
    tleg.innerHTML =
      TS.by === "hr"
        ? HR_ZC.map((c, i) => `<span title="${HR_ZN[i]}"><i style="background:${c}"></i>Z${i + 1}</span>`).join("")
        : TS.by === "grade"
        ? GR.map(g => `<span><i style="background:${g[2]}"></i>${g[3]}</span>`).join("")
        : SC.map((c, i) => `<span><i style="background:${c}"></i>${i === 0 ? "langsam" : i === 4 ? "schnell" : ""}</span>`).join("");
    document.getElementById("tm").appendChild(tleg);
  };
  const mk = api(`/api/tours/${t.id}/coords`)
    .then(c => {
      const ll = cleanPts(c).map(p => [p[0], p[1]]),
        l = L.polyline(ll, {...trackStyle(t, TS.weight + 1)}).addTo(map);
      tl = l;
      if (TS.casing) {
        casePane(map);
        cl = L.polyline(ll, {pane: "casing", color: "#fff", weight: TS.weight + 4, opacity: 0.9, interactive: false}).addTo(map);
      }
      tcc = cleanPts(c);
      paintBy();
      map._tlFit = () => map.fitBounds(l.getBounds(), {padding: [30, 30]});
      map._tlStale = !$("#tm").clientWidth;        // Karte war beim Laden zugeklappt: beim Aufklappen neu einpassen
      map._tlFit();
      L.circleMarker(ll[0], {radius: 7, color: "#fff", fillColor: "#2f8f5f", fillOpacity: 1, weight: 2}).addTo(map).bindTooltip("Start");
      L.circleMarker(ll[ll.length - 1], {radius: 7, color: "#fff", fillColor: "#c0504d", fillOpacity: 1, weight: 2})
        .addTo(map)
        .bindTooltip("Ziel");
      profile(c, t);
      if (window.pulsCard) pulsCard(t);
      if (window.hrData)
        hrData(t.id).then(h => {
          if (!h || !h.n) return;
          hrF = hrLookup(h);
          hrMax = h.hrmax;
          profileHr(h);
          if (TS.by === "hr") paintBy();
        });
      return c;
    })
    .catch(e => {
      if ($("#profcard")) $("#profcard").style.display = "none";
      if (window.tlRefresh) tlRefresh();
      return null;
    });
  const ph = await api(`/api/photos?tour_id=${encodeURIComponent(t.id)}&limit=400&strip=${PH_STRIP_N}`);     // nur Metadaten (id, Zeit, Ort, Version), ein Aufruf
  $("#pc").textContent = ph.length ? `${ph.length} Fotos` : "Zu dieser Tour gibt es noch keine Fotos.";
  tlSetBadge("photos", ph.length ? `${ph.length} Fotos` : "keine");
  if (ph.length) {
    $("#ss").hidden = false;
    $("#ss").href = `slideshow.html?tour=${t.id}`;
  }
  const grid = phStrip(ph);
  $("#padd").onclick = () => photoImportModal({tour: t});
  $("#pgps").onclick = async () => {
    try {
      await gpsAlign(t);
    } catch (e) {
      uiAlert(e.message || e);
    }
  };
  if (ph.length) photoSelect(ph, 0, {box: "#phbox", anchor: "#pc", tour: true, onMode: on => on && grid.open(true)});
  mk.then(c => {
    if (c && ph.length) {
      photoChain(map, t, c, ph); // Fotos auf der Strecke; verschiebbar (12-fotokette.js)
      profilePhotos(ph, t);
    }
  });
  $("#eup").onclick = () => uploadDialog(t);
  uploadChips(t);
  if ($("#edel") && t.source !== "local")
    $("#edel").onclick = () => {
      // Tour von Komoot: nur hier entfernen (kommt beim Abgleich nicht wieder) oder auch bei Komoot endgültig löschen
      const m = uiModal(`<h3>Tour löschen?</h3><p>„${esc(t.name)}“ (${fmtKm(t.km)}) wird aus Meine Touren entfernt – mit Strecke, Notizen und Tags. Zugeordnete Fotos bleiben erhalten.</p>
        <label class="chk"><input type="checkbox" id="dk"> <b>auch bei Komoot endgültig löschen</b> <span class="mut">(lässt sich nicht rückgängig machen)</span></label>
        <p class="mut fs13">Ohne Häkchen bleibt die Tour bei Komoot und wird beim nächsten Abgleich nicht wieder übernommen.</p>
        <div id="dm" class="mut"></div><div class="uifoot"><button class="btn ghost" id="dx">Abbrechen</button><button class="btn alt uidanger" data-danger id="dok">Löschen</button></div>`);
      m.querySelector("#dx").onclick = () => m.remove();
      m.querySelector("#dok").onclick = async e => {
        const k = !!m.querySelector("#dk").checked;
        if (k && !await uiConfirm({text: `„${t.name}“ wirklich auch bei Komoot endgültig löschen?`, danger: true, ok: "Löschen"})) return;
        e.target.disabled = true;
        m.querySelector("#dm").textContent = "Wird gelöscht …";
        try {
          const r = await api(`/api/tours/${encodeURIComponent(t.id)}/delete`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({komoot: k})});
          m.remove();
          if (r.komoot) uiAlert("Gelöscht – " + r.komoot + ".");
          ROUTES = null;
          await loadTours();
          location.hash = "#/tours";
        } catch (x) {
          m.querySelector("#dm").innerHTML = `<span class="bad">${esc(x.message)}</span>`;
          e.target.disabled = false;
        }
      };
    };
  else if ($("#edel"))
    $("#edel").onclick = async () => {
      if (
        !await uiConfirm({text: `Lokale Tour „${t.name}“ samt gespeicherter Strecke löschen? Bereits hochgeladene Kopien bei Komoot/Strava bleiben bestehen.`, danger: true, ok: "Löschen"})
      )
        return;
      try {
        await api(`/api/tours/${encodeURIComponent(t.id)}`, {method: "DELETE"});
        ROUTES = null;
        await loadTours();
        location.hash = "#/tours";
      } catch (e) {
        uiAlert(e.message);
      }
    };
  if ($("#ksync"))
    $("#ksync").onclick = async () => {
      const o = t.km;
      $("#ksync").disabled = true;
      $("#ksm").textContent = "Lade von Komoot …";
      try {
        await api(`/api/tours/${encodeURIComponent(t.id)}/sync`, {method: "POST"});
        ROUTES = null;
        window._full = {};
        await loadTours();
        const n = BY[t.id];
        await route();
        const m = $("#ksm");
        if (m) m.textContent = `Abgeglichen: ${fmtKm(o)} → ${fmtKm(n.km)}`;
      } catch (e) {
        $("#ksync").disabled = false;
        $("#ksm").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
      }
    };
  (() => {
    const b = $("#efix"),
      w = $("#ewarn"),
      fixed = t.fix_up != null,
      sus = !fixed && t.km > 0.5 && (t.up_m || 0) > 120 * t.km && t.up_m > 400;
    b.textContent = fixed ? "⛰ Höhenkorrektur zurücknehmen" : "⛰ Höhen korrigieren";
    const z = $("#ezepp");
    if (z) {
      z.onclick = async () => {
        z.disabled = b.disabled = true;
        $("#ksm").textContent = "Gleiche Höhe mit der Uhr ab …";
        try {
          const r = await api(`/api/tours/${encodeURIComponent(t.id)}/elev-zepp`, {method: "POST"});
          await loadTours();
          route();   // Seite neu zeichnen (nicht neu laden), damit die Meldung stehen bleibt
          const n = document.createElement("div");
          n.className = "panel";
          n.setAttribute("role", "status");
          n.style.cssText = "position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:9999;padding:10px 16px;max-width:90vw;box-shadow:0 4px 18px rgba(0,0,0,.3)";
          n.textContent = `Höhe aus Zepp übernommen: ${fmtAuf(r.up)} (vorher ${fmtHm(r.orig_up)})`;
          document.body.appendChild(n);
          setTimeout(() => n.remove(), 6000);
        } catch (e) {
          z.disabled = b.disabled = false;
          $("#ksm").textContent = "";
          uiAlert("Höhenabgleich fehlgeschlagen: " + e.message);
        }
      };
    }
    if (fixed)
      w.innerHTML = `<div class="panel mb14 p12-16">${t.fix_src === "zepp" ? `Höhen aus der Zepp-Uhr übernommen (Komoot/GPS meldete ${fmtHm(t.fix_up)} Aufstieg).` : `Höhen mit Geländemodell korrigiert (Komoot/GPS meldete ${fmtHm(t.fix_up)} Aufstieg).`}</div>`;
    else if (sus)
      w.innerHTML = `<div class="panel mb14 p12-16" style="border-left:4px solid var(--yellow)"><b>Auffällige Höhendaten:</b> ${fmtHm(t.up_m)} Aufstieg auf ${fmtKm(t.km)} sind unwahrscheinlich. Mit „Höhen korrigieren“ werden sie aus dem Geländemodell berechnet.</div>`;
    b.onclick = async () => {
      b.disabled = true;
      $("#ksm").textContent = fixed ? "Stelle Original wieder her …" : "Berechne Höhen aus Geländedaten …";
      try {
        if (fixed) await api(`/api/tours/${encodeURIComponent(t.id)}/elev-restore`, {method: "POST"});
        else {
          const r = await api(`/api/tours/${encodeURIComponent(t.id)}/elev-fix`, {method: "POST"});
          if (
            !(await uiConfirm({title: "Neu berechnete Höhen übernehmen?", ok: "Übernehmen", cancel: "Original behalten",
              text: `Neu berechnet: ${fmtHm(r.up_m)} Aufstieg, ${fmtHm(r.down_m)} Abstieg (vorher ${fmtHm(r.orig_up)} / ${fmtHm(r.orig_down)}).`}))
          )
            await api(`/api/tours/${encodeURIComponent(t.id)}/elev-restore`, {method: "POST"});
        }
        await loadTours();
        location.reload();
      } catch (e) {
        b.disabled = false;
        $("#ksm").textContent = "";
        uiAlert("Höhenkorrektur fehlgeschlagen: " + e.message);
      }
    };
  })();
  $("#etc").onclick = e => {
    if (document.querySelector(".tpanel")) {
      document.querySelector(".tpanel").remove();
      return;
    }
    trackPanel(
      e.target,
      () => {
        if (!tl) return;
        tl.setStyle(trackStyle(t, TS.weight + 1));
        paintBy();
        if (cl) {
          map.removeLayer(cl);
          cl = null;
        }
        if (TS.casing) {
          casePane(map);
          cl = L.polyline(tl.getLatLngs(), {pane: "casing", color: "#fff", weight: TS.weight + 4, opacity: 0.9, interactive: false}).addTo(
            map
          );
        }
      },
      true
    );
  };
  $("#ren").onclick = () => {
    const m = uiModal(`<h3>Tour umbenennen</h3>
      <input id="rnn" type="text" class="w100" maxlength="200">
      <div class="mt12"><b>Vorschläge aus den Kartendaten</b></div>
      <div id="rsg" class="chips mt6 fxw g6" style="display:flex"><span class="mut">Suche Orte und Gipfel …</span></div>
      ${t.source === "local" ? "" : '<label class="chk"><input type="checkbox" id="rkom"> auch bei Komoot umbenennen</label>'}
      <div class="uifoot"><button class="btn ghost" id="rcx">Abbrechen</button><button class="btn" id="rok">Umbenennen</button></div>`);
    const inp = m.querySelector("#rnn");
    inp.value = t.name;
    inp.focus();
    inp.select();
    m.querySelector("#rcx").onclick = () => m.remove();
    const box = m.querySelector("#rsg");
    let pend = 4,
      got = 0,
      fail = 0;
    const have = new Set();
    const add = (list, front) =>
      list.forEach(x => {
        if (have.has(x) || x === t.name || !box.isConnected) return;
        have.add(x);
        got++;
        const b = document.createElement("button");
        b.className = "btn alt";
        b.type = "button";
        b.textContent = x;
        b.onclick = () => {
          inp.value = x;
          inp.focus();
        };
        if (front) (box.querySelector(".mut")?.remove(), box.prepend(b));
        else {
          box.querySelector(".mut")?.remove();
          box.appendChild(b);
        }
      });
    const done = () => {
      if (--pend || !box.isConnected) return;
      if (!got)
        box.innerHTML = `<span class="mut">${fail ? "Keine Vorschläge möglich (Internetzugang des Servers prüfen)." : "Keine Vorschläge gefunden."}</span>`;
    };
    ["places", "peak", "trails", "guides"].forEach(p =>
      api(`/api/tours/${encodeURIComponent(t.id)}/name-suggestions?part=${p}`)
        .then(r => add(r.suggestions, p === "trails" || p === "guides"))
        .catch(() => {
          fail++;
        })
        .finally(done)
    );
    inp.onkeydown = e => {
      if (e.key === "Enter") m.querySelector("#rok").click();
      if (e.key === "Escape") close();
    };
    m.querySelector("#rok").onclick = async () => {
      const nn = inp.value.trim(),
        kom = !!(m.querySelector("#rkom") && m.querySelector("#rkom").checked);
      if (!nn || nn === t.name) {
        close();
        return;
      }
      try {
        const r = await api(`/api/tours/${encodeURIComponent(t.id)}/rename`, {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({name: nn, komoot: kom}),
        });
        t.name = nn;
        $("#tname").textContent = t.name;
        close();
        if (kom && !r.komoot) uiAlert("Hier umbenannt, aber bei Komoot hat es nicht geklappt:\n" + r.warning);
      } catch (e) {
        uiAlert("Umbenennen fehlgeschlagen: " + e.message);
      }
    };
  };
};
function profile(c, t) {
  const alts = c.map(p => p[2]).filter(v => v != null);
  if (alts.length < 3) {
    $("#profcard").style.display = "none";
    if (window.tlRefresh) tlRefresh();
    return;
  }
  const R = 6371000,
    rad = Math.PI / 180,
    dist = [0];
  for (let i = 1; i < c.length; i++) {
    const a = c[i - 1],
      b = c[i],
      dl = (b[0] - a[0]) * rad,
      dn = (b[1] - a[1]) * rad,
      h = Math.sin(dl / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dn / 2) ** 2;
    dist.push(dist[i - 1] + 2 * R * Math.asin(Math.sqrt(h)));
  }
  const W = 800,
    H = 200,
    L0 = 42,
    B = 22,
    T = 8,
    mn = Math.min(...alts),
    mxA = Math.max(...alts),
    span = Math.max(20, mxA - mn),
    lo = mn - span * 0.08,
    hi = mxA + span * 0.08,
    D = dist[dist.length - 1] || 1;
  const x = d => L0 + ((W - L0 - 6) * d) / D,
    y = a => T + (H - T - B) * (1 - (a - lo) / (hi - lo));
  const pts = c.map((p, i) => [x(dist[i]), y(p[2] ?? lo)]),
    line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");
  let g = "";
  [lo + (hi - lo) * 0.05, (lo + hi) / 2, hi - (hi - lo) * 0.05].forEach(
    v =>
      (g += `<line x1="${L0}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)"/><text x="${L0 - 6}" y="${y(v) + 4}" text-anchor="end">${fmtHm(v)}</text>`)
  );
  for (let k = 0; k <= 4; k++)
    g += `<text x="${x((D * k) / 4)}" y="${H - 6}" text-anchor="${k === 4 ? "end" : k === 0 ? "start" : "middle"}">${fmtKm((D * k) / 4000)}</text>`;
  $("#prof").className = "";
  $("#prof").innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" id="psvg">${g}<path d="${line}L${x(D)},${H - B}L${L0},${H - B}Z" fill="${sCol(t.sport)}" opacity=".22"/><path d="${line}" fill="none" stroke="${sCol(t.sport)}" stroke-width="2.4"/><line id="pl" y1="${T}" y2="${H - B}" stroke="var(--ink)" opacity="0" /></svg><div class="tip" id="ptip" style="display:none"></div>`;
  $("#kmax").style.display = "";
  $("#kmaxv").innerHTML = `${nf(mxA, 0)}<span class="u">m</span>`;
  tlSetBadge("prof", `höchster Punkt ${fmtHm(mxA)}`);
  let mkr = null;
  const svg = $("#psvg");
  svg.onmousemove = svg.ontouchmove = e => {
    const r = svg.getBoundingClientRect(),
      cx = e.touches ? e.touches[0].clientX : e.clientX,
      fx = ((cx - r.left) / r.width) * W;
    if (fx < L0) return;
    const d = ((fx - L0) / (W - L0 - 6)) * D;
    let k = dist.findIndex(v => v >= d);
    if (k < 0) k = dist.length - 1;
    $("#pl").setAttribute("x1", pts[k][0]);
    $("#pl").setAttribute("x2", pts[k][0]);
    $("#pl").setAttribute("opacity", 0.5);
    const tp = $("#ptip");
    tp.style.display = "";
    tp.style.left = (pts[k][0] / W) * r.width + "px";
    tp.style.top = (pts[k][1] / H) * r.height + 34 + "px";
    tp.textContent = `${fmtKm(dist[k] / 1000)} · ${fmtHm(c[k][2])}`;
    if (map) {
      if (!mkr)
        mkr = L.circleMarker([c[k][0], c[k][1]], {radius: 8, color: "#fff", fillColor: "#e2b13c", fillOpacity: 1, weight: 3}).addTo(map);
      else mkr.setLatLng([c[k][0], c[k][1]]);
    }
  };
  profile.ctx = {c, dist, pts, svg, W, H, B, T};
  svg.onmouseleave = () => {
    $("#ptip").style.display = "none";
    $("#pl").setAttribute("opacity", 0);
    if (mkr && map) {
      map.removeLayer(mkr);
      mkr = null;
    }
  };
}

/* Fotos im Höhenprofil: Marker an der Stelle der Aufnahme; Klick zeigt das Foto, Zeiger darüber setzt den Punkt auf der Karte */
function profilePhotos(ph, t) {
  const X = profile.ctx;
  if (!X || !ph || !ph.length || $("#pphotos")) return;
  const {c, pts, svg, H, B} = X,
    hasT = c.some(p => p[3] != null);
  const idxOf = p => {
    if (p.lat != null && p.lng != null) {
      let bi = 0,
        bd = 1e18;
      c.forEach((q, i) => {
        const d = (q[0] - p.lat) ** 2 + ((q[1] - p.lng) * Math.cos((p.lat * Math.PI) / 180)) ** 2;
        if (d < bd) (bd = d), (bi = i);
      });
      return bi;
    }
    if (!hasT) return -1;
    const ms = (p.taken_ts - t.start_ts) * 1000; // Streckenzeiten sind Millisekunden seit Tourstart
    let bi = -1,
      bd = 1e18;
    c.forEach((q, i) => {
      if (q[3] == null) return;
      const d = Math.abs(q[3] - ms);
      if (d < bd) (bd = d), (bi = i);
    });
    return bd < 6 * 3600e3 ? bi : -1;
  };
  let h = '<g id="pphotos">',
    n = 0;
  ph.forEach((p, k) => {
    const i = idxOf(p);
    if (i < 0) return;
    n++;
    const x = pts[i][0].toFixed(1);
    h += `<g class="pph cp" data-k="${k}" data-i="${i}"><line x1="${x}" x2="${x}" y1="${pts[i][1].toFixed(1)}" y2="${H - B}" stroke="var(--ink)" opacity=".25"/><circle cx="${x}" cy="${pts[i][1].toFixed(1)}" r="5" fill="#e2b13c" stroke="#fff" stroke-width="1.5"><title>Foto ${k + 1} anzeigen</title></circle></g>`;
  });
  if (!n) return;
  svg.insertAdjacentHTML("beforeend", h + "</g>");
  svg.querySelectorAll(".pph").forEach(g => {
    g.onclick = e => {
      e.stopPropagation();
      openLb(ph, +g.dataset.k);
    };
    g.onmousemove = e => {
      e.stopPropagation();
      const q = c[+g.dataset.i];
      if (map && q) {
        if (!profilePhotos.m) profilePhotos.m = L.circleMarker([q[0], q[1]], {radius: 9, color: "#fff", fillColor: "#e2b13c", fillOpacity: 1, weight: 3}).addTo(map);
        else profilePhotos.m.setLatLng([q[0], q[1]]);
      }
    };
    g.onmouseleave = () => {
      if (profilePhotos.m && map) map.removeLayer(profilePhotos.m);
      profilePhotos.m = null;
    };
  });
  $("#profcard").insertAdjacentHTML("beforeend", `<p class="mut fs13 m4-0-0">Gelbe Punkte = Fotos – anklicken zum Ansehen.</p>`);
}
