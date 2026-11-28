/* =====================  Orte & Gipfel, Wanderführer  ===================== */
VIEWS.places = async (...a) => {
  $("#main").innerHTML =
    `<div class="sec mt0"><h2>Orte & Ausrüstung</h2><span class="sub">Orte, Gipfel, Leistung, Wetter, Neuland</span></div><div id="plb" class="mut">Wird geladen …</div>`;
  const [p, gp, gfo] = await Promise.all([api("/api/places"), api("/api/guides/progress").catch(() => []), api("/api/guides/folders").catch(() => ({folders: []}))]),
    box = $("#plb");
  box.className = "";
  const mx = Math.max(1, ...p.starts.map(s => s.n));
  box.innerHTML = `<div class="grid g2">
   <div class="panel"><h2>Häufigste Startorte</h2>${p.starts.length ? `<div class="rows">${p.starts.map(s => `<div class="r"><span><a href="#/search?q=${encodeURIComponent(s.place)}">${esc(s.place)}</a><small>${esc(s.state || "")} · ${fmtKm(s.km, {d: 0})}</small></span><b>${s.n}×</b></div>`).join("")}</div>` : '<p class="mut">Noch keine Regionen bestimmt: Verwaltung → Touren holen → Komoot „Regionen bestimmen“.</p>'}</div>
   <div class="panel"><h2>Gipfel &amp; Pässe</h2>${
     p.peaks.length
       ? `<div class="rows">${p.peaks
           .map(
             s =>
               `<div class="r"><span>${esc(s.name)}<small>${s.alt ? nf(s.alt, 0) + " m · " : ""}${s.tours
                 .slice(0, 4)
                 .map(id => `<a href="#/tour/${id}">${BY[id] ? fmtDatumKurz(BY[id].date) : id}</a>`)
                 .join(", ")}${s.tours.length > 4 ? " …" : ""}</small></span><b>${s.n}×</b></div>`
           )
           .join("")}</div>`
       : '<p class="mut">Noch keine Gipfel bestimmt.</p>'
   }
    <div class="row mt12"><button class="btn alt" id="pkb">Gipfel bestimmen${p.pending_peaks ? ` (${fmtAnzahl(p.pending_peaks, "Tour", "Touren")} offen)` : ""}</button><span id="pkm" class="mut"></span></div></div></div>
   <div class="sec"><h2>Wanderführer</h2>${gp.length ? `<span class="sub">${gfSum(gp)}</span>` : ""}</div>
   <div id="gfx"></div>`;
  gfMount($("#gfx"), gp, a[1], gfo.folders || []);                 // 3.73.0: immer eingehängt (Knöpfe „Buch anlegen …“, Ordner, Übertragen); ohne Bücher zeigt es den Leerzustand
  $("#pkb").onclick = async e => {
    e.target.disabled = true;
    try {
      await api("/api/jobs/peaks", {method: "POST"});
    } catch (x) {
      $("#pkm").textContent = x.message;
      e.target.disabled = false;
      return;
    }
    const tick = async () => {
      if (!$("#pkm")) return;
      const j = await api("/api/jobs").catch(() => null);
      if (j && j.running) {
        $("#pkm").textContent =
          `⏳ ${j.progress || "läuft"} (wird nach jedem Gipfel gespeichert; du kannst die Seite verlassen und später fortsetzen)`;
        return setTimeout(tick, 2500);
      }
      $("#pkm").textContent =
        (j &&
          j.log
            .filter(l => /Gipfel/.test(l))
            .slice(-2)
            .join(" · ")) ||
        "Fertig";
      e.target.disabled = false;
      setTimeout(() => {
        if (location.hash.startsWith("#/places")) route();
      }, 2500);
    };
    setTimeout(tick, 1500);
  };
};

/* ---- Übersicht: Jahrestag mit Foto ---- */
const _dashJ = VIEWS.dash;
VIEWS.dash = async (...a) => {
  await _dashJ(...a);
  const h = [...document.querySelectorAll("#main .sec h2")].find(x => x.textContent === "An diesem Tag");
  if (!h) return;
  const now = new Date(),
    md = `${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`,
    ot = TOURS.filter(t => t.date.slice(5, 10) === md && t.y !== now.getFullYear()).slice(0, 3);
  const cards = await Promise.all(
    ot.map(async t => {
      const ph = t.photos ? await api(`/api/photos?tour_id=${t.id}&limit=1`).catch(() => []) : [];
      return `<a class="otd" href="#/tour/${t.id}" style="${ph[0] ? `background-image:linear-gradient(transparent 40%,#000b),url(${picSrc(ph[0], 500)})` : ""}"><b>Vor ${now.getFullYear() - t.y} ${now.getFullYear() - t.y === 1 ? "Jahr" : "Jahren"}</b><span>${esc(t.name)}</span><small>${fmtKm(t.km)} · ${fmtHm(t.up_m)}</small></a>`;
    })
  );
  const sec = h.closest(".sec");
  if (sec && cards.length && !sec.nextElementSibling?.classList.contains("otdg"))
    sec.insertAdjacentHTML("afterend", `<div class="otdg">${cards.join("")}</div>`);
};

/* =====================  Tags, Teilen, Neuland (Tourdetail)  ===================== */
const _tourT = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourT(id, q);
  const t = BY[id];
  if (!t || !$("#etag")) return;
  const showTags = () => {
    $("#tagl").innerHTML = (t.tags || "")
      .split("|")
      .filter(Boolean)
      .map(x => `<a class="chip on tdn" href="#/album/${encodeURIComponent(x)}">🏷 ${esc(x)}</a>`)
      .join("");
  };
  showTags();
  $("#etag").onclick = () => {
    let cur = (t.tags || "").split("|").filter(Boolean);
    const m =
      uiModal(`<h3>Schlagwörter &amp; Alben</h3><p class="mut fs14">Mit Schlagwörtern wie „Urlaub Réunion 2026“ oder „Rother Taunus“ entsteht ein Album mit eigener Seite (Karte, Summen, Fotos, 3D-Flug).</p>
      <div id="tgc" class="chips"></div><input id="tgi" list="tgl" placeholder="Neues Schlagwort + Enter" aria-label="Neues Schlagwort" class="w100 mt10"><datalist id="tgl">${allTags()
        .map(x => `<option value="${esc(x)}">`)
        .join("")}</datalist>
      <div class="uifoot"><button class="btn ghost" id="tgx">Abbrechen</button><button class="btn" id="tgs">Speichern</button></div>`);
    const draw = () => {
      m.querySelector("#tgc").innerHTML =
        cur.map((x, i) => `<button class="chip on" data-i="${i}" title="Entfernen">${esc(x)} ×</button>`).join("") ||
        '<span class="mut">Noch keine Schlagwörter</span>';
      m.querySelectorAll("[data-i]").forEach(
        b =>
          (b.onclick = () => {
            cur.splice(+b.dataset.i, 1);
            draw();
          })
      );
    };
    draw();
    const inp = m.querySelector("#tgi");
    inp.focus();
    const add = () => {
      const v = inp.value.trim();
      if (v && !cur.includes(v)) cur.push(v);
      inp.value = "";
      draw();
    };
    inp.onkeydown = e => {
      if (e.key === "Enter") {
        e.preventDefault();
        add();
      }
    };
    inp.onchange = add;
    m.querySelector("#tgx").onclick = () => m.remove();
    m.querySelector("#tgs").onclick = async () => {
      add();
      try {
        const r = await api(`/api/tours/${encodeURIComponent(t.id)}/tags`, {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({tags: cur}),
        });
        t.tags = r.tags.join("|");
        showTags();
        m.remove();
      } catch (e) {
        uiAlert(e.message);
      }
    };
  };
  $("#eshr").onclick = async () => {
    const m =
      uiModal(`<h3>Links dieser Tour</h3><p class="mut fs14">Erzeugt einen Link, den man <b>ohne Anmeldung</b> öffnen kann – du wählst, was er zeigt (Karte, Höhenprofil, Fotos …). Er funktioniert nur, wenn dein Server von außen erreichbar ist, z. B. per VPN oder Reverse-Proxy.</p>
      <div class="row mt16"><button class="btn" id="shn">Neuen Link erstellen …</button></div><div id="shl" class="mt16"></div><div class="uifoot"><button class="btn ghost" id="shx">Schließen</button></div>`);
    m.querySelector("#shx").onclick = () => m.remove();
    const list = async () => {
      const s = await api(`/api/tours/${encodeURIComponent(t.id)}/shares`).catch(() => []);
      m.querySelector("#shl").innerHTML =
        s
          .map(x => {
            const u = location.origin + "/s/" + x.token;
            return `<div class="r p8-0" style="display:block;border-top:1px solid var(--rule)"><input readonly value="${esc(u)}" class="w100" data-act="select"><small class="mut">${x.photos == 2 ? "Diashow" : `<b>Zeigt:</b> ${esc(shrLabel(x.blocks))}`}${x.trim ? ", Anfang/Ende ausgeblendet" : ""}${x.best ? `, beste ${fmtAnzahl(x.best, "Foto", "Fotos")}` : ""} · ${x.exp ? (x.exp * 1000 < Date.now() ? "abgelaufen" : "gültig bis " + fmtDatumKurz(x.exp)) : "unbegrenzt"}${x.photos == 2 ? ` · ${x.views || 0}× angesehen` : ""}</small> <button class="btn alt sm" data-cp="${esc(u)}">Kopieren</button> ${x.photos != 2 ? `<button class="btn alt sm" data-bl="${x.token}">Auswahl ändern</button> ` : ""}<button class="btn alt sm" data-rv="${x.token}">Widerrufen</button></div>`;
          })
          .join("") || '<span class="mut">Noch kein Link.</span>';
      m.querySelectorAll("[data-cp]").forEach(
        b =>
          (b.onclick = async () => {
            try {
              await navigator.clipboard.writeText(b.dataset.cp);
              b.textContent = "✓";
            } catch (e) {
              b.previousElementSibling;
            }
          })
      );
      m.querySelectorAll("[data-rv]").forEach(
        b =>
          (b.onclick = async () => {
            await api("/api/share/" + b.dataset.rv, {method: "DELETE"});
            list();
          })
      );
      m.querySelectorAll("[data-bl]").forEach(
        b =>
          (b.onclick = async () => {
            const x = s.find(y => y.token === b.dataset.bl),
              pick = await shrDialog({edit: true, blocks: x.blocks});
            if (!pick) return;
            try {
              await api("/api/share/" + encodeURIComponent(x.token), {method: "PATCH", headers: {"content-type": "application/json"}, body: JSON.stringify({blocks: pick.blocks})});
            } catch (e) {
              uiAlert("Auswahl speichern nicht möglich: " + e.message);
            }
            list();
          })
      );
    };
    m.querySelector("#shn").onclick = async () => {
      const pick = await shrDialog({hasPhotos: t.photos == null ? undefined : t.photos > 0});
      if (!pick) return;
      try {
        await api(`/api/tours/${encodeURIComponent(t.id)}/share`, {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({blocks: pick.blocks, trim: pick.trim, days: pick.days}),
        });
      } catch (e) {
        uiAlert("Link erstellen nicht möglich: " + e.message);
      }
      list();
    };
    list();
  };
  api("/api/newground")
    .then(n => {
      const r = n.tours[t.id],
        f = $("#main .figs");
      if (!r || !f) return;
      f.insertAdjacentHTML(
        "beforeend",
        `<div class="fig" title="Anteil der Strecke, der auf keiner früheren Tour lag"><div class="v">${r.pct}<span class="u">%</span></div><div class="l">Neuland (${fmtKm(r.new_km)})</div></div>`
      );
    })
    .catch(() => {});
};

/* =====================  Sammlungen: Reisen & Alben  ===================== */
const DAYC = ["#e11d74", "#f2c230", "#00a6d6", "#7cc43a", "#ff6a1a", "#8e5bd6", "#16a085", "#c0392b"];
/* Statistik je Sportart (Sportart) für Reisen, Alben und Etappen */
function collStats(ts) {
  const g = {};
  ts.forEach(t => (g[t.sport || "other"] = g[t.sport || "other"] || []).push(t));
  const keys = Object.keys(g).sort((a, b) => g[b].reduce((c, t) => c + t.km, 0) - g[a].reduce((c, t) => c + t.km, 0));
  if (!ts.length) return "";
  const row = (name, col, a) => {
    const sm = f => a.reduce((c, t) => c + (f(t) || 0), 0),
      km = sm(t => t.km),
      h = sm(t => t.h);
    return `<tr><td>${col ? `<i class="dot" style="background:${col}"></i>` : ""}${esc(name)}</td><td>${a.length}</td><td>${fmtKm(km, {summe: true, einheit: false})}</td><td>${nf(sm(t => t.up_m), 0)}</td><td>${nf(sm(t => t.down_m), 0)}</td><td>${fmtDauer(h * 3600, {summe: true})}</td><td>${h > 0 ? nf(km / h, 1) : "–"}</td><td>${fmtKm(Math.max(...a.map(t => t.km || 0)), {einheit: false})}</td></tr>`;
  };
  return `<div class="sec"><h2>Statistik nach Sportart</h2></div><div class="tblw"><table class="cstat"><thead><tr><th>Sportart</th><th>Touren</th><th>Strecke (km)</th><th>Aufstieg (m)</th><th>Abstieg (m)</th><th>Dauer</th><th>Ø km/h</th><th>Längste (km)</th></tr></thead><tbody>${keys.map(k => row(sName(k), typeof sCol === "function" ? sCol(k) : "", g[k])).join("")}</tbody>${keys.length > 1 ? `<tfoot>${row("Gesamt", "", ts).replace(/<td>/g, "<td><b>").replace(/<\/td>/g, "</b></td>")}</tfoot>` : ""}</table></div>`;
}
/* 3.33.0: Die Abschnitte tragen data-rs; bei einer Reise (opt.reise = die Reise) steckt rsFrame() (62-reiseseiten.js) sie sofort, noch vor dem Zeichnen der Karte, in Karten der anpassbaren Seite. */
async function collView(title, sub, ids, back, opt = {}) {
  const ts = ids
      .map(i => BY[i])
      .filter(Boolean)
      .sort((a, b) => a.start_ts - b.start_ts),
    sum = f => ts.reduce((c, t) => c + f(t), 0);
  const days = [...new Set(ts.map(t => t.date.slice(0, 10)))];
  $("#main").innerHTML =
    `<div data-rs="kopf"><div class="row"><a class="back" href="${back}">‹ Zurück</a></div><div class="sec mt12"><h1 style="font-size:clamp(30px,5vw,52px)">${esc(title)}</h1></div><div class="mut">${esc(sub)}</div></div>
   <div class="figs mt14" data-rs="kennzahlen"><div class="fig"><div class="v">${ts.length}</div><div class="l">Touren</div></div><div class="fig"><div class="v">${fmtKm(sum(t => t.km), {summe: true, einheit: false})}<span class="u">km</span></div><div class="l">Strecke</div></div>
    <div class="fig"><div class="v">${nf(
      sum(t => t.up_m || 0),
      0
    )}<span class="u">m</span></div><div class="l">Aufstieg</div></div><div class="fig"><div class="v">${nf(
      sum(t => t.down_m || 0),
      0
    )}<span class="u">m</span></div><div class="l">Abstieg</div></div><div class="fig"><div class="v">${fmtDauerHtml(sum(t => t.h) * 3600, {summe: true})}</div><div class="l">Unterwegs</div></div><div class="fig"><div class="v">${days.length}</div><div class="l">Tage</div></div></div>
   <div data-rs="stat">${collStats(ts)}</div>
   <div class="row m6-0-12" data-rs="flug"><a class="btn" href="#/flight/${encodeURIComponent("set:" + ts.map(t => t.id).join(","))}">3D-Flug über alles</a><button class="btn alt" id="coff" title="Kartenkacheln dieser Strecken zwischenspeichern">Karte offline speichern</button><span id="cofm" class="mut"></span></div>
   <div data-rs="karte"><div class="tmap" id="cm" style="height:460px"></div></div><div data-rs="fotos"><div class="sec"><h2>Fotos</h2></div><div class="thumbs" id="cph"></div></div><div data-rs="touren"><div class="sec"><h2>Touren</h2></div><div class="tl">${ts.map(tourRow).join("")}</div></div>`;
  const rsTr = opt.reise || opt.serie;                                      // 3.63.0: auch die Mehrtagestour (opt.serie) nutzt die anpassbare Seite
  if (rsTr && typeof rsFrame === "function") rsFrame(rsTr, ts, days);
  map = mkMap("cm", {layers: true});
  const fg = L.featureGroup().addTo(map);
  const co = await Promise.all(ts.map(t => api(`/api/tours/${t.id}/coords`).catch(() => [])));
  ts.forEach((t, i) => {
    const p = cleanPts(co[i]).map(x => [x[0], x[1]]);
    if (p.length > 1) {
      const ln = L.polyline(p, {color: DAYC[days.indexOf(t.date.slice(0, 10)) % DAYC.length], weight: 5, className: "clk"})
        .bindTooltip(`${fmtDatumKurz(t.date)} · ${esc(t.name)} – anklicken für Einzelheiten`, {sticky: true})
        .addTo(fg);
      ln.on("click", () => {
        location.hash = `#/tour/${t.id}`;
      });
      ln.on("mouseover", () => ln.setStyle({weight: 8}));
      ln.on("mouseout", () => ln.setStyle({weight: 5}));
    }
  });
  const cmap = map;
  cmap._cvFit = () => (fg.getLayers().length ? cmap.fitBounds(fg.getBounds(), {padding: [30, 30], animate: false}) : cmap.setView([50, 9], 6, {animate: false}));
  if (rsTr && typeof rsMapBind === "function") rsMapBind(cmap);
  if ($("#cm").clientWidth && !$("#cm").closest("details:not([open])")) cmap._cvFit();
  else {
    cmap._cvStale = true;
    cmap.setView([50, 9], 6, {animate: false});                          // vorläufig, damit Leaflet lesbar ist
  }                                                 // Karte steckt in einer zugeklappten oder ausgeblendeten Karte: angepasst, sobald sie sichtbar ist (62-reiseseiten.js)
  (!$("#cph") ? Promise.resolve([]) : Promise.all(ts.slice(0, 14).map(t => (t.photos ? api(`/api/photos?tour_id=${t.id}&limit=6`).catch(() => []) : [])))).then(a => {
    const ph = a.flat();
    if (!$("#cph")) return;
    $("#cph").innerHTML =
      ph.map((p, i) => `<img loading="lazy" decoding="async" src="${picSrc(p, 300)}" data-i="${i}">`).join("") ||
      '<span class="mut">Keine Fotos.</span>';
    bindThumbs($("#cph"), ph);
    if (rsTr && typeof rsBadge === "function") rsBadge("fotos", ph.length ? (ph.length === 1 ? "1 Foto" : `${fmtAnzahl(ph.length, "Foto", "Fotos")}`) : "");
  });
  const plan = await api(`/api/tiles/plan?ids=${ts.map(t => t.id).join(",")}`).catch(() => null);
  if (plan)
    $("#cofm").textContent = plan.missing
      ? `${plan.missing} von ${plan.total} Kacheln fehlen noch (ca. ${Math.ceil(plan.missing / 60)}\u00a0Min.)`
      : "✓ Karte ist offline verfügbar";
  $("#coff").onclick = async e => {
    e.target.disabled = true;
    try {
      await api("/api/tiles/prefetch", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({ids: ts.map(t => t.id)}),
      });
      $("#cofm").textContent = "Läuft im Hintergrund (1 Kachel/Sekunde, höchstens 1500). Danach Seite neu öffnen.";
    } catch (x) {
      $("#cofm").textContent = x.message;
      e.target.disabled = false;
    }
  };
}
/* 3.62.1: Karte einer Reise (Reisen-Seite und Reisen-Abschnitt der Suche): Name, Zeitraum, Touren, Strecke, Aufstieg */
function tripKarte(x) {
  return `<a class="otd" href="#/trip/${x.id}" style="background-image:${x.photo ? `linear-gradient(#0e2a2b33 20%,#0e2a2bf0),url(${picSrc({id: x.photo, v: x.photo_v}, 500)})` : "linear-gradient(#0e2a2b99,#0e2a2bee)"}"><b>${esc(x.region)}</b><span>${fmtDatumKurz(x.start)}${x.end !== x.start ? " – " + fmtDatumKurz(x.end) : ""}</span><small>${fmtAnzahl(x.tours.length, "Tour", "Touren")} · ${fmtKm(x.km, {d: 0})} · ${fmtHm(x.up_m)}</small></a>`;
}
VIEWS.trips = async () => {
  $("#main").innerHTML =
    `<div class="sec mt0"><h2>Reisen</h2><span class="sub">automatisch erkannt: Touren weit weg von zu Hause an mindestens 4 Tagen</span></div><div id="tr" class="mut">Wird geladen …</div>`;
  const [tr, tg] = await Promise.all([api("/api/trips"), api("/api/tags")]);
  window.RS_TRIPS = tr;
  $("#tr").className = "";
  $("#tr").innerHTML =
    (tr.length
      ? `<div class="otdg">${tr.map(tripKarte).join("")}</div>`
      : '<p class="mut">Noch keine Reisen erkannt. Es braucht Touren an mindestens 4 Tagen am Stück, über 60 km von deinem üblichen Startort entfernt – Wochenendausflüge zählen nicht. Eigene Alben legst du mit Schlagwörtern an.</p>') +
    `<div id="rnalb"><div class="sec"><h2>Schlagwörter &amp; Alben</h2><span class="sub">in der Tour über „Schlagwörter & Alben“ vergeben</span></div>` +
    (tg.length
      ? `<div class="otdg">${tg.map(x => `<a class="otd" href="#/album/${encodeURIComponent(x.tag)}"${x.photo ? ` style="background-image:linear-gradient(#0e2a2b33 20%,#0e2a2bf0),url(${picSrc({id: x.photo, v: x.photo_v}, 500)})"` : ""}><b data-sym>🏷 ${esc(x.tag)}</b><small>${fmtAnzahl(x.n, "Tour", "Touren")} · ${fmtKm(x.km, {d: 0})}</small></a>`).join("")}</div>`
      : '<p class="mut">Noch keine Schlagwörter vergeben.</p>') + "</div>";
};
VIEWS.trip = async id => {
  const tr = (await api("/api/trips")).find(x => x.id === id);
  if (!tr) throw notFound("Reise", "#/trips", "Alle Reisen");
  await collView(
    `${tr.region}${tr.country && tr.country !== tr.region ? ", " + tr.country : ""}`,
    `${fmtDatum(tr.start)}${tr.end !== tr.start ? " – " + fmtDatum(tr.end) : ""}`,
    tr.tours,
    "#/trips",
    {reise: tr}
  );
};
VIEWS.album = async tag => {
  tag = decodeURIComponent(tag || "");
  const ts = TOURS.filter(t => (t.tags || "").split("|").includes(tag));
  if (!ts.length) throw new Error("Album ist leer");
  await collView(
    "🏷 " + tag,
    `Album mit ${fmtAnzahl(ts.length, "Tour", "Touren")}`,
    ts.map(t => t.id),
    "#/trips"
  );
};

/* =====================  Auswertung: Leistung, Wetter, Neuland  ===================== */
function yearChart(series, xs, unit) {
  const W = 560,
    H = 200,
    L0 = 44,
    B = 26,
    T = 10,
    all = series.flatMap(s => s.v.filter(v => v != null));
  if (!all.length) return "";
  const mx = Math.max(...all) * 1.1,
    mn = Math.min(0, ...all),
    X = i => L0 + (i * (W - L0 - 12)) / Math.max(1, xs.length - 1),
    Y = v => T + (H - T - B) * (1 - (v - mn) / (mx - mn || 1));
  let g = "";
  for (let k = 0; k <= 4; k++) {
    const v = mn + ((mx - mn) * k) / 4;
    g += `<line x1="${L0}" x2="${W - 8}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--rule)"/><text x="${L0 - 6}" y="${Y(v) + 4}" text-anchor="end" font-size="11" fill="var(--mut)">${nf(v, v < 10 ? 1 : 0)}</text>`;
  }
  g += xs.map((x, i) => `<text x="${X(i)}" y="${H - 6}" text-anchor="middle" font-size="11" fill="var(--mut)">${x}</text>`).join("");
  g += series
    .map(s => {
      const pts = s.v.map((v, i) => (v == null ? null : [X(i), Y(v)])).filter(Boolean);
      return (
        `<polyline fill="none" stroke="${s.color}" stroke-width="2.6" points="${pts.map(p => p.join(",")).join(" ")}"/>` +
        pts.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="${s.color}"/>`).join("")
      );
    })
    .join("");
  return `<svg viewBox="0 0 ${W} ${H}" class="w100 mw640">${g}</svg><div class="chips chwrap">${series.map(s => `<span class="chip" style="cursor:default"><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join("")}<span class="mut fs13 ml6">${unit}</span></div>`;
}
const _plA = VIEWS.places;
VIEWS.places = async (...a) => {
  await _plA(...a);
  const box = $("#plb");
  if (!box) return;
  const [ng, wx] = await Promise.all([api("/api/newground").catch(() => null), api("/api/weather/stats").catch(() => null)]);
  const ys = years().slice().reverse(),
    sp = [...new Set(TOURS.map(t => t.sport))]
      .map(s => [s, TOURS.filter(t => t.sport === s).length])
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(x => x[0]);
  const perf = f =>
    sp.map(s => ({
      name: sName(s),
      color: sCol(s),
      v: ys.map(y => {
        const a = TOURS.filter(t => t.sport === s && t.y === y && t.h > 0);
        return a.length >= 2 ? f(a) : null;
      }),
    }));
  const sm = (a, f) => a.reduce((c, t) => c + f(t), 0);
  let h = `<div class="sec"><h2>Leistung über die Jahre</h2><span class="sub">nur Jahre mit mindestens 2 Touren der Sportart</span></div><div class="grid g2"><div class="panel"><h2>Tempo</h2>${yearChart(
    perf(a => sm(a, t => t.km) / sm(a, t => t.h)),
    ys,
    "km/h im Schnitt"
  )}</div><div class="panel"><h2>Aufstieg pro Stunde</h2>${yearChart(
    perf(a => sm(a, t => t.up_m || 0) / sm(a, t => t.h)),
    ys,
    "m Aufstieg pro Stunde"
  )}</div></div>`;
  if (wx) {
    const r = wx.rows,
      bins = [
        ["unter 0 °", x => x.tmax < 0],
        ["0–10 °", x => x.tmax >= 0 && x.tmax < 10],
        ["10–20 °", x => x.tmax >= 10 && x.tmax < 20],
        ["20–30 °", x => x.tmax >= 20 && x.tmax < 30],
        ["über 30 °", x => x.tmax >= 30],
      ];
    const mxn = Math.max(1, ...bins.map(b => r.filter(b[1]).length)),
      top = (f, l) => (r.length ? r.slice().sort(f)[0] : null),
      hot = top((a, b) => b.tmax - a.tmax),
      cold = top((a, b) => a.tmin - b.tmin),
      wet = top((a, b) => b.precip - a.precip);
    h += `<div class="sec"><h2>Wetter</h2><span class="sub">${fmtAnzahl(r.length, "Tour", "Touren")} mit Wetterdaten</span></div><div class="grid g2"><div class="panel"><h2>Bei welcher Temperatur bist du unterwegs?</h2><div class="rows">${bins
      .map(b => {
        const n = r.filter(b[1]).length;
        return `<div class="r"><span>${b[0]}<div class="stack mnw2 mt4" style="width:${(100 * n) / mxn}%"><div class="w100" style="background:var(--yellow)"></div></div></span><b>${n}</b></div>`;
      })
      .join("")}</div></div>
     <div class="panel"><h2>Extreme &amp; Regen</h2><div class="rows">${
       r.length
         ? `<div class="r"><span>Trocken (unter 1 mm)</span><b>${r.filter(x => x.precip < 1).length} von ${r.length}</b></div>
       <div class="r"><span><a href="#/tour/${hot.id}">Wärmste Tour</a><small>${esc(hot.name)}</small></span><b>${nf(hot.tmax, 0)} °</b></div><div class="r"><span><a href="#/tour/${cold.id}">Kälteste Tour</a><small>${esc(cold.name)}</small></span><b>${nf(cold.tmin, 0)} °</b></div>
       <div class="r"><span><a href="#/tour/${wet.id}">Nasseste Tour</a><small>${esc(wet.name)}</small></span><b>${nf(wet.precip, 1)} mm</b></div>`
         : '<div class="mut">Noch keine Wetterdaten.</div>'
     }</div>
       <div class="row mt12"><button class="btn alt" id="wxb">Wetter für alle Touren holen${wx.missing ? ` (${wx.missing} offen)` : ""}</button><span id="wxm" class="mut"></span></div></div></div>`;
  }
  if (ng && Object.keys(ng.years).length) {
    const mxy = Math.max(1, ...Object.values(ng.years).map(v => v.km)),
      tops = Object.entries(ng.tours)
        .sort((a, b) => b[1].new_km - a[1].new_km)
        .slice(0, 8);
    h += `<div class="sec"><h2>Neuland</h2><span class="sub">Anteil der Strecke, der auf keiner früheren Tour lag</span></div><div class="grid g2"><div class="panel"><h2>Je Jahr</h2><div class="rows">${Object.entries(
      ng.years
    )
      .reverse()
      .map(
        ([y, v]) =>
          `<div class="r"><span>${y}<div class="stack mt4" style="width:${(100 * v.km) / mxy}%"><div style="width:${v.km ? (100 * v.new_km) / v.km : 0}%;background:var(--yellow)"></div></div></span><b>${nf(v.new_km, 0)} von ${fmtKm(v.km, {d: 0})} neu</b></div>`
      )
      .join("")}</div></div>
     <div class="panel"><h2>Größte Entdeckungen</h2><div class="rows">${tops.map(([id, v]) => `<div class="r"><span><a href="#/tour/${id}">${esc(BY[id]?.name || id)}</a><small>${BY[id] ? fmtDatumKurz(BY[id].date) : ""} · ${v.pct}\u00a0% neu</small></span><b>${fmtKm(v.new_km)}</b></div>`).join("")}</div></div></div>`;
  }
  box.insertAdjacentHTML("beforeend", h);
  if ($("#wxb"))
    $("#wxb").onclick = async e => {
      e.target.disabled = true;
      try {
        await api("/api/jobs/weather", {method: "POST"});
        $("#wxm").textContent = "Läuft im Hintergrund. Seite später neu öffnen.";
      } catch (x) {
        $("#wxm").textContent = x.message;
        e.target.disabled = false;
      }
    };
};

/* =====================  Prüfen: Umbenennen nach Regeln  ===================== */
const _chk = VIEWS.check;
VIEWS.check = async (...a) => {
  await _chk(...a);
  const body = $("#chb");
  if (!body) return;
  body.insertAdjacentHTML(
    "beforeend",
    `<div class="panel gap"><h2>Umbenennen nach Regeln</h2><p class="mut">Wähle Touren aus, lege eine Regel fest, prüfe die Vorschau und wende sie an.</p>
   <div class="filters"><input id="rn_q" placeholder="Name enthält …"><select id="rn_r"><option value="">Alle Regionen</option>${regionOpts()}</select><select data-gsheet id="rn_g" aria-label="Gebiet">${gebietOpts()}</select><select data-spsheet id="rn_s" aria-label="Sportart">${sportFilterOptions(TOURS.map(t => t.sport))}</select></div>
   <div class="filters"><select id="rn_a"><option value="pre">Vorsilbe hinzufügen</option><option value="suf">Nachsilbe hinzufügen</option><option value="rep">Text ersetzen (Suchen → Ersetzen)</option><option value="date">Datum und Uhrzeit am Ende entfernen</option></select><input id="rn_x" placeholder="Text / Suchen"><input id="rn_y" placeholder="Ersetzen durch"></div>
   <div class="row"><label class="chk m0"><input type="checkbox" id="rn_k"> auch bei Komoot umbenennen</label><button class="btn alt" id="rn_p">Vorschau</button><button class="btn" id="rn_go" disabled>Umbenennen</button><span id="rn_m" class="mut"></span></div><div class="rows mt10" id="rn_l"></div></div>`
  );
  let plan = [];
  const calc = () => {
    const q = $("#rn_q").value,
      r = $("#rn_r").value,
      gb = $("#rn_g").value,
      s = $("#rn_s").value,
      act = $("#rn_a").value,
      x = $("#rn_x").value,
      y = $("#rn_y").value;
    plan = TOURS.filter(t => (!q.trim() || smatch(t.name, q)) && (!r || inRegion(t, r)) && inGebiet(t, gb) && (!s || sgMatch(t.sport, [s])))
      .map(t => {
        let n = t.name;
        if (act === "pre") n = x + n;
        else if (act === "suf") n = n + x;
        else if (act === "rep") n = x ? n.split(x).join(y) : n;
        else n = n.replace(/\s*\d{2}\.\d{2}\.\d{4}(\s+\d{1,2}:\d{2})?\s*$/, "");
        return [t, n.trim()];
      })
      .filter(([t, n]) => n && n !== t.name);
    $("#rn_l").innerHTML =
      plan
        .slice(0, 60)
        .map(([t, n]) => `<div class="r" style="display:block"><span class="mut">${esc(t.name)}</span><br><b>${esc(n)}</b></div>`)
        .join("") + (plan.length > 60 ? `<div class="mut">… und ${plan.length - 60} weitere</div>` : "") ||
      '<div class="mut">Nichts zu ändern.</div>';
    $("#rn_m").textContent = `${fmtAnzahl(plan.length, "Tour", "Touren")} betroffen`;
    $("#rn_go").disabled = !plan.length;
  };
  $("#rn_p").onclick = calc;
  $("#rn_go").onclick = async e => {
    if (!await uiConfirm({title: `${fmtAnzahl(plan.length, "Tour", "Touren")} umbenennen?`, ok: "Umbenennen", text: $("#rn_k").checked ? "Die Namen werden auch bei Komoot geändert." : "Die Namen werden nur in Meine Touren geändert."})) return;
    e.target.disabled = true;
    let n = 0,
      bad = 0;
    for (const [t, nn] of plan) {
      $("#rn_m").textContent = `Benenne um ${++n}/${plan.length} …`;
      try {
        await api(`/api/tours/${encodeURIComponent(t.id)}/rename`, {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({name: nn, komoot: $("#rn_k").checked}),
        });
        t.name = nn;
      } catch (x) {
        bad++;
      }
    }
    $("#rn_m").textContent = `Fertig${bad ? `, ${bad} fehlgeschlagen` : ""}.`;
    plan = [];
    $("#rn_l").innerHTML = "";
    await loadTours();
  };
};

/* ---- Verwaltung: Benachrichtigung ---- */
const _adm9 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm9(...a);
  const sv = $("#save");
  if (!sv) return;
  const s = await api("/api/settings").catch(() => ({}));
  sv.closest(".row").insertAdjacentHTML(
    "beforebegin",
    `<div class="panel gap"><h2>Benachrichtigung (optional)</h2><p class="mut">Trage eine Webhook-Adresse ein (z. B. ntfy, Gotify oder ein eigener Dienst). Bei einer neuen Warnung (Zepp-Token, Sicherung, Job-Fehler, Speicher) wird dort eine Textnachricht abgeliefert, höchstens stündlich geprüft. Leer = aus. Die App stellt keine Verbindung zu Home Assistant her.</p>
   <div class="field"><label>Webhook-Adresse</label><input data-k="notify_url" value="${esc(s.notify_url || "")}" placeholder="https://ntfy.sh/mein-thema"></div><div class="field"><label class="slck"><input type="checkbox" data-k="notify_events"${s.notify_events !== "0" ? " checked" : ""}><span>Auch bei neuen Touren melden</span></label></div><div class="row"><button class="btn alt" id="ntest">Testnachricht senden (nach „Speichern“)</button><span id="ntm" class="mut"></span></div></div>`
  );
  $("#ntest").onclick = async () => {
    try {
      await api("/api/notify/test", {method: "POST"});
      $("#ntm").textContent = "✓ Gesendet";
    } catch (e) {
      $("#ntm").textContent = e.message;
    }
  };
};

/* =====================  3.53.0 Wanderführer übersichtlich  =====================
   Je Buch eine eingeklappte Karte (Titelbild, Name, „x von y gewandert“, Ring); die Tourenliste entsteht erst beim Aufklappen und in Blöcken zu 60.
   Filter Alle/Offen/Gewandert, Suche über Bücher und Touren, Reihenfolge der Touren; Zustand in der Adresse (#/places?wf=…&wo=…&wq=…),
   aufgeklappte Bücher je Gerät (localStorage). Titelbild wählt der Benutzer selbst (nie aus dem Netz), es wird im Browser verkleinert. */
const GF_BLOCK = 60;
const GF = {f: "", o: "", q: "", lim: {}, books: [], covers: {}};
const GF_FILTER = [["", "Alle"], ["offen", "Offen"], ["gewandert", "Gewandert"]];
const GF_ORDER = [["", "Buchreihenfolge"], ["laenge", "Nach Strecke"], ["zuletzt", "Zuletzt gewandert"]];
const GF_BOOK_ICON = `<svg viewBox="0 0 24 24" class="gfico" aria-hidden="true"><path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5zM5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M9 7h6M9 10h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`;
const gfSum = gp => {
  const d = gp.reduce((c, b) => c + b.done, 0),
    t = gp.reduce((c, b) => c + b.total, 0);
  return `${gp.length === 1 ? "1 Buch" : gp.length + " Bücher"} · ${d} von ${t} gewandert`;
};
const gfLs = (k, v) => {
  try {
    if (v === undefined) return localStorage.getItem("mt_gf_" + k);
    localStorage.setItem("mt_gf_" + k, v);
  } catch (e) {}
  return null;
};
const gfNorm = s => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");
const gfCover = b => (b.cover ? `/api/guides/cover?book=${encodeURIComponent(b.key)}&v=${b.cover}` : "");
/* Ring (Donut) ohne Bibliothek: Umfang 100 (r = 15,9155), Anteil als stroke-dasharray; Farben aus dem Stylesheet (hell und dunkel) */
function gfRing(done, total) {
  const p = total ? done / total : 0,
    pc = fmtProzent(p);
  return `<svg class="gfring" viewBox="0 0 36 36" role="img" aria-label="Anteil gewandert: ${pc}"><circle class="gfr0" cx="18" cy="18" r="15.9155"/>${done ? `<circle class="gfr1" cx="18" cy="18" r="15.9155" stroke-dasharray="${(100 * p).toFixed(2)} 100" transform="rotate(-90 18 18)"/>` : ""}<text x="18" y="18" class="gfrt" font-size="9" aria-hidden="true">${pc}</text></svg>`;
}
/* Buchreihenfolge: tragen die meisten Titel eine Nummer vorn („3 Feldberg“, „Tour 12 …“), natürlich nach Titel („2“ vor „10“), sonst in der Reihenfolge der Dateien beim Hochladen */
const GF_COLL = new Intl.Collator("de", {numeric: true, sensitivity: "base"});
function gfOrder(ts, o) {
  const num = ts.filter(x => /^\D{0,8}\d/.test(x.title || "")).length * 2 >= ts.length,
    base = ts.slice().sort((a, b) => (num ? GF_COLL.compare(a.title || "", b.title || "") : 0) || a.id - b.id);
  if (o === "laenge") return base.sort((a, b) => (a.km == null) - (b.km == null) || (a.km || 0) - (b.km || 0));
  if (o === "zuletzt") return base.sort((a, b) => (b.ts || 0) - (a.ts || 0));
  return base;
}
/* Treffer der Suche je Buch: null = Buch ausblenden; {all: true} = Buchname passt (alle Touren); {ids} = nur diese Touren (Karte klappt auf) */
function gfMatch(b) {
  if (!GF.q) return {all: true};
  const q = gfNorm(GF.q);
  if (gfNorm(b.book).includes(q)) return {all: true};
  const ids = new Set(b.tours.filter(x => gfNorm(x.title).includes(q) || (x.tour && BY[x.tour] && gfNorm(BY[x.tour].name).includes(q))).map(x => x.id));
  return ids.size ? {ids} : null;
}
const gfVisible = (b, m) => b.tours.filter(x => (!GF.f || (GF.f === "offen" ? !x.tour : !!x.tour)) && (!m || m.all || m.ids.has(x.id)));
function gfCount(b, m) {
  const n = gfVisible(b, m).length;
  if (GF.q && m && !m.all) return n === 1 ? "1 Treffer" : `${n} Treffer`;
  return GF.f === "gewandert" ? `gewandert: ${n}` : `offen: ${GF.f ? n : b.total - b.done}`;
}
function gfHash() {
  const u = new URLSearchParams();
  if (GF.f) u.set("wf", GF.f);
  if (GF.o) u.set("wo", GF.o);
  if (GF.q) u.set("wq", GF.q);
  const h = "#/places" + (u.toString() ? "?" + u : "");
  if (location.hash !== h) history.replaceState(null, "", h);                 // teilbar, ohne die Seite neu aufzubauen
}
function gfMount(host, gp, q, folders) {
  q = q || new URLSearchParams();
  GF.books = gp;
  GF.folders = folders || [];
  GF.ro = typeof isViewer === "function" && isViewer();                      // Betrachter: nur ansehen und exportieren
  GF.f = GF_FILTER.some(x => x[0] === q.get("wf")) ? q.get("wf") || "" : "";
  GF.o = GF_ORDER.some(x => x[0] === q.get("wo")) ? q.get("wo") || "" : "";
  GF.q = (q.get("wq") || "").slice(0, 80);
  GF.lim = {};
  GF.covers = {};
  gp.forEach(b => b.cover && (GF.covers[b.key] = gfCover(b)));
  const ic = (k, n) => symHtml(k, n || 17);
  host.innerHTML = `<p class="gfmsg" id="gfmsg" role="status" aria-live="polite"></p>
    ${GF.ro ? "" : `<div class="row gftool"><button type="button" class="btn sm" id="gfadd" aria-haspopup="dialog">${ic("ic:plus")} Buch anlegen …</button><button type="button" class="btn sm" id="gffold" aria-haspopup="dialog">${ic("ic:folder")} Neuer Ordner …</button>${
      gp.length ? `<button type="button" class="btn sm" id="gfnames" aria-haspopup="dialog">${ic("✎")} Tournamen angleichen …</button>` : ""
    }</div>`}
    ${
      gp.length
        ? `<div class="gfbar"><div class="chips" role="group" aria-label="Touren zeigen">${GF_FILTER.map(([k, l]) => `<button type="button" class="chip${GF.f === k ? " on" : ""}" data-gff="${k}" aria-pressed="${GF.f === k}">${l}</button>`).join("")}</div>
    <input type="search" id="gfq" class="gfq" value="${esc(GF.q)}" placeholder="Buch oder Buchtour suchen" aria-label="Buch oder Buchtour suchen" autocomplete="off">
    <select id="gfo" class="gfo" aria-label="Reihenfolge der Buchtouren im Buch">${GF_ORDER.map(([k, l]) => `<option value="${k}"${GF.o === k ? " selected" : ""}>${l}</option>`).join("")}</select></div>
    <div id="gfl" class="gfl"></div>`
        : `<p class="mut" id="gfempty">${GF.ro ? "Noch keine Wanderführer." : "Noch keine Wanderführer. Lege ein Buch an und wähle die GPX-Dateien dazu (bei Rother im Download-Bereich zum Buch)."}</p>`
    }
    <input type="file" id="gffile" accept="image/jpeg,image/png,image/webp,image/gif" hidden>
    <div class="gfxfer"><h3 class="gfh3">Übertragen</h3><p class="mut fs14">Bücher als Datei sichern oder auf ein anderes Gerät bringen. Mein Tourentagebuch liest dieselbe Datei.</p>
     <div class="row"><button type="button" class="btn sm" id="gfexp" aria-haspopup="dialog">${ic("⬇")} Wanderführer exportieren …</button>${GF.ro ? "" : `<button type="button" class="btn sm" id="gfimp" aria-haspopup="dialog">${ic("⬆")} Wanderführer importieren …</button>`}</div></div>`;
  const on = (id, fn) => $(id) && ($(id).onclick = fn);
  on("#gfadd", () => gfBookAdd(null));
  on("#gffold", () => gfFolderNew());
  on("#gfnames", () => gfNamesOpen());
  on("#gfexp", () => gfExport());
  on("#gfimp", () => gfImport());
  const msg = GF.msg;                                                       // Meldung der Aktion, die die Seite neu aufgebaut hat: erst zeigen, wenn die Liste steht
  GF.msg = "";
  if (!gp.length) return msg && gfMsg(msg);
  host.querySelectorAll("[data-gff]").forEach(
    c =>
      (c.onclick = () => {
        GF.f = c.dataset.gff;
        host.querySelectorAll("[data-gff]").forEach(x => (x.classList.toggle("on", x === c), x.setAttribute("aria-pressed", x === c)));
        gfHash();
        gfDraw();
      })
  );
  let tq = 0;
  $("#gfq").oninput = e => {
    clearTimeout(tq);
    tq = setTimeout(() => {
      GF.q = e.target.value.trim().slice(0, 80);
      gfHash();
      gfDraw();
    }, 180);
  };
  $("#gfo").onchange = e => {
    GF.o = e.target.value;
    gfHash();
    gfDraw();
  };
  $("#gffile").onchange = gfCoverPick;
  gfDraw();
  if (msg) gfMsg(msg);
}
/* Meldung an der Stelle der Aktion (Leitfaden 2.5): „<Sache> gespeichert“, Fehler „<Vorgang> nicht möglich: <Grund>“ */
function gfMsg(t, bad) {
  const m = $("#gfmsg");
  if (!m) return;
  m.textContent = t || "";
  m.classList.toggle("bad", !!bad);
}
function gfCard(b, i) {
  const m = gfMatch(b);
  if (!m) return "";
  const forced = !!(GF.q && !m.all),
    open = forced || gfLs("o_" + b.key) === "1",
    cv = GF.covers[b.key];
  return `<details class="gfb" data-i="${i}" data-sy="${open ? 1 : 0}"${forced ? ' data-forced="1"' : ""}${open ? " open" : ""}>
       <summary class="gfh"><span class="gfc">${cv ? `<img src="${cv}" alt="" loading="lazy" decoding="async">` : GF_BOOK_ICON}</span>
        <span class="gft"><span class="gfname" translate="no">${esc(b.book)}</span><span class="gfn">${b.done} von ${b.total} gewandert</span><span class="gfz">${gfCount(b, m)}</span></span>${gfRing(b.done, b.total)}</summary>
       <div class="gfbody"></div></details>`;
}
function gfDraw() {
  const box = $("#gfl");
  if (!box) return;
  const cards = GF.books.map((b, i) => ({b, html: gfCard(b, i)})),
    none = `<p class="mut">Kein Buch und keine Buchtour passt zu „${esc(GF.q)}“.</p>`;
  if (!GF.folders.length) box.innerHTML = cards.map(c => c.html).join("") || none;
  else {
    /* 3.73.0 Ordner wie „Geplante Touren“ im Tagebuch: Ordner alphabetisch (auch leere), danach „Ohne Ordner“; bei Suche oder Filter nur Ordner mit Treffern */
    const filtered = !!(GF.q || GF.f),
      sec = (name, i) => {
        const mine = cards.filter(c => (c.b.folder || "") === (name || "")),
          shown = mine.filter(c => c.html);
        if (filtered && !shown.length) return "";
        if (name === null && !shown.length) return "";
        const zu = name !== null && gfLs("f_" + name) === "z" && !filtered,
          n = mine.length,
          label = name === null ? "Ohne Ordner" : name,
          cnt = fmtAnzahl(n, "Buch", "Bücher");
        return `<section class="gfsec${zu ? " zu" : ""}" data-fi="${i}"><div class="gfoh"><button type="button" class="gfot" aria-expanded="${!zu}"><span class="gfpf" aria-hidden="true"></span>${symHtml("ic:folder", 20)}<b translate="no">${esc(label)}</b><span class="gfanz mut" aria-label="${cnt}">${n}</span></button>${
          name === null || GF.ro
            ? ""
            : `<button type="button" class="ico gfoi" data-a="ren" aria-label="Ordner „${esc(name)}“ umbenennen" title="Umbenennen">${symHtml("✎", 18)}</button><button type="button" class="ico gfoi" data-a="del" aria-label="Ordner „${esc(name)}“ löschen" title="Löschen">${symHtml("🗑", 18)}</button>`
        }</div><div class="gfoc"${zu ? " hidden" : ""}>${shown.map(c => c.html).join("") || (n ? "" : '<p class="mut fs14 gfleer">Leer. Lege Bücher hierher mit „In Ordner verschieben …“.</p>')}</div></section>`;
      };
    box.innerHTML = GF.folders.map((f, i) => sec(f, i)).join("") + sec(null, -1) || none;
    box.querySelectorAll(".gfsec").forEach(s => {
      const fi = +s.dataset.fi,
        nm = fi >= 0 ? GF.folders[fi] : null;
      s.querySelector(".gfot").onclick = e => {
        const c = s.querySelector(".gfoc"),
          zu = !c.hidden;
        c.hidden = zu;
        s.classList.toggle("zu", zu);
        e.currentTarget.setAttribute("aria-expanded", String(!zu));
        if (nm !== null) gfLs("f_" + nm, zu ? "z" : "o");
      };
      s.querySelectorAll(".gfoi").forEach(b => (b.onclick = () => (b.dataset.a === "ren" ? gfFolderRename(nm) : gfFolderDelete(nm))));
    });
  }
  box.querySelectorAll("details.gfb").forEach(d => {
    if (d.open) gfBody(d);
    d.addEventListener("toggle", () => {
      const v = d.open ? "1" : "0";
      if (d.open && !d.dataset.r) gfBody(d);
      if (d.dataset.sy === v) return;                                         // vom Programm gesetzt
      d.dataset.sy = v;
      if (!d.dataset.forced) gfLs("o_" + GF.books[+d.dataset.i].key, v);     // von der Suche aufgeklappt: nicht merken
    });
  });
}
function gfRow(x, b) {
  const t = x.tour && BY[x.tour],
    meta = [x.km != null ? fmtKm(x.km) : "", x.up != null ? fmtAuf(x.up) : ""].filter(Boolean).join(" · ");
  return `<div class="r gfr${x.tour ? " done" : ""}" data-t="${x.id}"><span><span class="gfst" aria-hidden="true">${x.tour ? "✓" : "○"}</span><span translate="no">${esc(x.title)}</span>${meta ? `<small>${meta}</small>` : ""}</span><span class="gfend">${
    x.tour ? `<a href="#/tour/${x.tour}" aria-label="Gewandert am ${t ? fmtDatumKurz(t.date) : ""}">${t ? fmtDatumKurz(t.date) : "Tour"}</a>` : '<span class="mut">offen</span>'
  }${GF.ro ? "" : `<button type="button" class="ico gfrm" data-t="${x.id}" aria-haspopup="dialog" aria-label="Weitere Aktionen für „${esc(x.title)}“" title="Weitere Aktionen">${symHtml("⋯", 18)}</button>`}</span></div>`;
}
function gfBody(d) {
  const b = GF.books[+d.dataset.i],
    body = d.querySelector(".gfbody"),
    m = gfMatch(b),
    ls = gfOrder(gfVisible(b, m), GF.o),
    lim = GF.lim[b.key] || GF_BLOCK,
    ro = typeof isViewer === "function" && isViewer(),
    nOpen = b.tours.filter(x => !x.tour && x.s).length;
  d.dataset.r = "1";
  const empty = GF.f === "offen" ? "Alle Buchtouren dieses Buchs sind gewandert." : GF.f === "gewandert" ? "Aus diesem Buch ist noch keine Buchtour gewandert." : "Keine Buchtouren.";
  body.innerHTML = `<div class="row gfacts">${nOpen ? `<button type="button" class="btn alt sm gfmapb" aria-expanded="false">Offene Touren auf der Karte</button>` : ""}${
    ro ? "" : `<button type="button" class="btn ghost sm gfcov">Titelbild wählen</button>${b.cover ? '<button type="button" class="btn ghost sm gfcovx">Titelbild entfernen</button>' : ""}<button type="button" class="btn ghost sm gfact" aria-haspopup="dialog">Aktionen …</button>`
  }</div><div class="gfmap" hidden></div>
   ${ls.length ? `<div class="rows gfrows">${ls.slice(0, lim).map(x => gfRow(x, b)).join("")}</div>` : `<p class="mut">${empty}</p>`}
   ${ls.length > lim ? `<div class="row jcc gfmore"><button type="button" class="btn ghost sm gfmoreb">Mehr anzeigen</button><span class="mut fs13">${lim} von ${ls.length}</span></div>` : ""}`;
  const ab = body.querySelector(".gfact");
  if (ab) ab.onclick = () => gfBookMenu(b);
  body.querySelectorAll(".gfrm").forEach(bt => (bt.onclick = () => gfTourMenu(b, b.tours.find(x => String(x.id) === bt.dataset.t))));
  const mb = body.querySelector(".gfmoreb");
  if (mb)
    mb.onclick = () => {
      GF.lim[b.key] = lim + GF_BLOCK;
      gfBody(d);
      const rows = d.querySelectorAll(".gfrows .r");
      if (rows[lim]) rows[lim].scrollIntoView({block: "nearest"});
    };
  const cb = body.querySelector(".gfcov");
  if (cb)
    cb.onclick = () => {
      GF.pick = b;
      $("#gffile").click();
    };
  const cx = body.querySelector(".gfcovx");
  if (cx)
    cx.onclick = async () => {
      if (!(await uiConfirm({text: `Titelbild von „${b.book}“ entfernen?`, ok: "Entfernen", danger: true}))) return;
      try {
        await api(`/api/guides/cover?book=${encodeURIComponent(b.key)}`, {method: "DELETE"});
        b.cover = null;
        delete GF.covers[b.key];
        gfRefresh(d);
      } catch (e) {
        uiAlert({title: "Titelbild", text: e.message});
      }
    };
  const mp = body.querySelector(".gfmapb");
  if (mp) mp.onclick = () => gfMap(d, b, mp);
}
/* Karte der offenen Touren: erst auf Wunsch aufgebaut (Startpunkte), beim Schließen wieder abgebaut */
function gfMap(d, b, btn) {
  const el = d.querySelector(".gfmap");
  if (!el.hidden) {
    if (el._m) el._m.remove();
    el.replaceWith(Object.assign(document.createElement("div"), {className: "gfmap", hidden: true}));     // Karte ganz abbauen
    btn.setAttribute("aria-expanded", "false");
    return;
  }
  el.hidden = false;
  btn.setAttribute("aria-expanded", "true");
  const pts = b.tours.filter(x => !x.tour && x.s);
  const m = (el._m = mkMap(el, {layers: true}));
  const grp = L.featureGroup(
    pts.map(x =>
      L.circleMarker(x.s, {radius: 7, weight: 2, color: "#fff", fillColor: "#d0652a", fillOpacity: 0.95}).bindPopup(
        `<b translate="no">${esc(x.title)}</b>${x.km != null ? "<br>" + fmtKm(x.km) + (x.up != null ? " · " + fmtAuf(x.up) : "") : ""}`
      )
    )
  ).addTo(m);
  m.fitBounds(grp.getBounds(), {padding: [24, 24], maxZoom: 13});
}
function gfRefresh(d) {
  const b = GF.books[+d.dataset.i],
    c = d.querySelector(".gfc"),
    cv = GF.covers[b.key];
  c.innerHTML = cv ? `<img src="${cv}" alt="" decoding="async">` : GF_BOOK_ICON;
  gfBody(d);
}
/* Titelbild: im Browser auf ~400 px Kante verkleinern (JPEG), dann hochladen; der Server prüft und kodiert neu */
async function gfCoverPick(e) {
  const f = e.target.files[0],
    b = GF.pick;
  e.target.value = "";
  if (!f || !b) return;
  let blob = f;
  try {
    const bmp = await createImageBitmap(f, {imageOrientation: "from-image"}),
      k = Math.min(1, 400 / Math.max(bmp.width, bmp.height)),
      c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(bmp.width * k));
    c.height = Math.max(1, Math.round(bmp.height * k));
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    bmp.close();
    blob = (await new Promise(r => c.toBlob(r, "image/jpeg", 0.85))) || f;
  } catch (x) {
    blob = f; // Browser kann das Bild nicht lesen: der Server versucht es (und lehnt Nicht-Bilder ab)
  }
  const fd = new FormData();
  fd.append("file", blob, "cover.jpg");
  try {
    const r = await api(`/api/guides/cover?book=${encodeURIComponent(b.key)}`, {method: "POST", body: fd});
    b.cover = r.v;
    GF.covers[b.key] = gfCover(b);
    const d = [...document.querySelectorAll("details.gfb")].find(x => GF.books[+x.dataset.i] === b);
    if (d) gfRefresh(d);
  } catch (x) {
    uiAlert({title: "Titelbild", text: x.message});
  }
}
