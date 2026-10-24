/* =====================  Orte & Gipfel, Wanderführer  ===================== */
VIEWS.places = async () => {
  $("#main").innerHTML =
    `<div class="sec" style="margin-top:0"><h2>Auswertung</h2><span class="sub">Orte, Gipfel, Leistung, Wetter, Neuland</span></div><div id="plb" class="mut">Wird geladen …</div>`;
  const [p, gp] = await Promise.all([api("/api/places"), api("/api/guides/progress").catch(() => [])]),
    box = $("#plb");
  box.className = "";
  const mx = Math.max(1, ...p.starts.map(s => s.n));
  box.innerHTML = `<div class="grid g2">
   <div class="panel"><h2>Häufigste Startorte</h2>${p.starts.length ? `<div class="rows">${p.starts.map(s => `<div class="r"><span><a href="#/search?q=${encodeURIComponent(s.place)}">${esc(s.place)}</a><small>${esc(s.state || "")} · ${nf(s.km, 0)} km</small></span><b>${s.n}×</b></div>`).join("")}</div>` : '<p class="mut">Noch keine Regionen bestimmt: Verwaltung → „Regionen bestimmen“.</p>'}</div>
   <div class="panel"><h2>Gipfel &amp; Pässe</h2>${
     p.peaks.length
       ? `<div class="rows">${p.peaks
           .map(
             s =>
               `<div class="r"><span>${esc(s.name)}<small>${s.alt ? nf(s.alt, 0) + " m · " : ""}${s.tours
                 .slice(0, 4)
                 .map(id => `<a href="#/tour/${id}">${BY[id] ? dateS(BY[id].date) : id}</a>`)
                 .join(", ")}${s.tours.length > 4 ? " …" : ""}</small></span><b>${s.n}×</b></div>`
           )
           .join("")}</div>`
       : '<p class="mut">Noch keine Gipfel bestimmt.</p>'
   }
    <div class="row" style="margin-top:12px"><button class="btn alt" id="pkb">Gipfel bestimmen${p.pending_peaks ? ` (${p.pending_peaks} Touren offen)` : ""}</button><span id="pkm" class="mut"></span></div></div></div>
   <div class="sec"><h2>Wanderführer-Fortschritt</h2></div>
   ${
     gp.length
       ? gp
           .map(
             b => `<div class="panel" style="margin-bottom:16px"><h2>${esc(b.book)} <span class="mut" style="font:500 16px var(--b)">${b.done} von ${b.total} gewandert</span></h2>
     <div class="stack" style="height:10px;margin:8px 0 12px"><div style="width:${b.total ? (100 * b.done) / b.total : 0}%;background:var(--acc)"></div></div>
     <div class="rows">${b.tours.map(x => `<div class="r"><span>${x.tour ? "✓" : "○"} ${esc(x.title)}</span>${x.tour ? `<a href="#/tour/${x.tour}">${BY[x.tour] ? dateS(BY[x.tour].date) : "Tour"}</a>` : '<span class="mut">offen</span>'}</div>`).join("")}</div></div>`
           )
           .join("")
       : '<p class="mut">Noch keine Wanderführer hinterlegt: Verwaltung → „Wanderführer“ (GPX-Dateien hochladen).</p>'
   }`;
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
      return `<a class="otd" href="#/tour/${t.id}" style="${ph[0] ? `background-image:linear-gradient(transparent 40%,#000b),url(/pic/${ph[0].id}?size=600)` : ""}"><b>Vor ${now.getFullYear() - t.y} ${now.getFullYear() - t.y === 1 ? "Jahr" : "Jahren"}</b><span>${esc(t.name)}</span><small>${nf(t.km, 1)} km · ${nf(t.up_m, 0)} m</small></a>`;
    })
  );
  const sec = h.closest(".sec");
  if (sec && cards.length && !sec.nextElementSibling?.classList.contains("otdg"))
    sec.insertAdjacentHTML("afterend", `<div class="otdg">${cards.join("")}</div>`);
};

/* =====================  Tags, Teilen, Neuland (Tourdetail)  ===================== */
const modal = html => {
  const m = document.createElement("div");
  m.className = "modal";
  m.innerHTML = `<div class="mbox">${html}</div>`;
  document.body.appendChild(m);
  m.onclick = e => {
    if (e.target === m) m.remove();
    return m;
  };
  return m;
};
const _tourT = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourT(id, q);
  const t = BY[id];
  if (!t || !$("#etag")) return;
  const showTags = () => {
    $("#tagl").innerHTML = (t.tags || "")
      .split("|")
      .filter(Boolean)
      .map(x => `<a class="chip on" href="#/album/${encodeURIComponent(x)}" style="text-decoration:none">🏷 ${esc(x)}</a>`)
      .join("");
  };
  showTags();
  $("#etag").onclick = () => {
    let cur = (t.tags || "").split("|").filter(Boolean);
    const m =
      modal(`<h3>Tags &amp; Alben</h3><p class="mut" style="font-size:14px">Mit Schlagworten wie „Urlaub Réunion 2026“ oder „Rother Taunus“ entsteht ein Album mit eigener Seite (Karte, Summen, Fotos, 3D-Flug).</p>
      <div id="tgc" class="chips"></div><input id="tgi" list="tgl" placeholder="Neuer Tag + Enter" style="width:100%;margin-top:10px"><datalist id="tgl">${allTags()
        .map(x => `<option value="${esc(x)}">`)
        .join("")}</datalist>
      <div class="row" style="justify-content:flex-end;margin-top:16px"><button class="btn alt" id="tgx">Abbrechen</button><button class="btn" id="tgs">Speichern</button></div>`);
    const draw = () => {
      m.querySelector("#tgc").innerHTML =
        cur.map((x, i) => `<button class="chip on" data-i="${i}" title="Entfernen">${esc(x)} ×</button>`).join("") ||
        '<span class="mut">Noch keine Tags</span>';
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
        alert(e.message);
      }
    };
  };
  $("#eshr").onclick = async () => {
    const m =
      modal(`<h3>Tour teilen</h3><p class="mut" style="font-size:14px">Erzeugt einen Link, den man <b>ohne Anmeldung</b> öffnen kann (Karte, Zahlen, optional Fotos). Er funktioniert nur, wenn dein Server von außen erreichbar ist, z. B. per VPN oder Reverse-Proxy.</p>
      <label class="chk"><input type="checkbox" id="shp"> Fotos mitsenden</label><label class="chk"><input type="checkbox" id="sht" checked> Anfang und Ende (300 m) ausblenden – schützt deinen Wohnort</label>
      <div class="row" style="margin-top:14px"><button class="btn" id="shn">Link erstellen</button></div><div id="shl" style="margin-top:14px"></div><div class="row" style="justify-content:flex-end;margin-top:12px"><button class="btn alt" id="shx">Schließen</button></div>`);
    m.querySelector("#shx").onclick = () => m.remove();
    const list = async () => {
      const s = await api(`/api/tours/${encodeURIComponent(t.id)}/shares`).catch(() => []);
      m.querySelector("#shl").innerHTML =
        s
          .map(x => {
            const u = location.origin + "/s/" + x.token;
            return `<div class="r" style="display:block;border-top:1px solid var(--rule);padding:8px 0"><input readonly value="${esc(u)}" style="width:100%" onclick="this.select()"><small class="mut">${x.photos ? "mit Fotos" : "ohne Fotos"}${x.trim ? ", Anfang/Ende ausgeblendet" : ""}</small> <button class="btn alt sm" data-cp="${esc(u)}">Kopieren</button> <button class="btn alt sm" data-rv="${x.token}">Widerrufen</button></div>`;
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
    };
    m.querySelector("#shn").onclick = async () => {
      await api(`/api/tours/${encodeURIComponent(t.id)}/share`, {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({photos: m.querySelector("#shp").checked, trim: m.querySelector("#sht").checked}),
      });
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
        `<div class="fig" title="Anteil der Strecke, der auf keiner früheren Tour lag"><div class="v">${r.pct}<span class="u">%</span></div><div class="l">Neuland (${nf(r.new_km, 1)} km)</div></div>`
      );
    })
    .catch(() => {});
};

/* =====================  Sammlungen: Reisen & Alben  ===================== */
const DAYC = ["#e11d74", "#f2c230", "#00a6d6", "#7cc43a", "#ff6a1a", "#8e5bd6", "#16a085", "#c0392b"];
async function collView(title, sub, ids, back) {
  const ts = ids
      .map(i => BY[i])
      .filter(Boolean)
      .sort((a, b) => a.start_ts - b.start_ts),
    sum = f => ts.reduce((c, t) => c + f(t), 0);
  const days = [...new Set(ts.map(t => t.date.slice(0, 10)))];
  $("#main").innerHTML =
    `<div class="row"><a class="back" href="${back}">‹ Zurück</a></div><div class="sec" style="margin-top:12px"><h1 style="font-size:clamp(30px,5vw,52px)">${esc(title)}</h1></div><div class="mut">${esc(sub)}</div>
   <div class="figs" style="margin-top:14px"><div class="fig"><div class="v">${ts.length}</div><div class="l">Touren</div></div><div class="fig"><div class="v">${nf(
     sum(t => t.km),
     0
   )}<span class="u">km</span></div><div class="l">Strecke</div></div>
    <div class="fig"><div class="v">${nf(
      sum(t => t.up_m || 0),
      0
    )}<span class="u">m</span></div><div class="l">Aufstieg</div></div><div class="fig"><div class="v">${nf(
      sum(t => t.h),
      0
    )}<span class="u">h</span></div><div class="l">Unterwegs</div></div><div class="fig"><div class="v">${days.length}</div><div class="l">Tage</div></div></div>
   <div class="row" style="margin:6px 0 12px"><a class="btn" href="#/flight/${encodeURIComponent("set:" + ts.map(t => t.id).join(","))}">3D-Flug über alles</a><button class="btn alt" id="coff" title="Kartenkacheln dieser Strecken zwischenspeichern">Karte offline speichern</button><span id="cofm" class="mut"></span></div>
   <div class="tmap" id="cm" style="height:460px"></div><div class="sec"><h2>Fotos</h2></div><div class="thumbs" id="cph"></div><div class="sec"><h2>Touren</h2></div><div class="tl">${ts.map(tourRow).join("")}</div>`;
  map = mkMap("cm", {layers: true});
  const fg = L.featureGroup().addTo(map);
  const co = await Promise.all(ts.map(t => api(`/api/tours/${t.id}/coords`).catch(() => [])));
  ts.forEach((t, i) => {
    const p = cleanPts(co[i]).map(x => [x[0], x[1]]);
    if (p.length > 1) {
      const ln = L.polyline(p, {color: DAYC[days.indexOf(t.date.slice(0, 10)) % DAYC.length], weight: 5, className: "clk"})
        .bindTooltip(`${dateS(t.date)} · ${esc(t.name)} – anklicken für Einzelheiten`, {sticky: true})
        .addTo(fg);
      ln.on("click", () => {
        location.hash = `#/tour/${t.id}`;
      });
      ln.on("mouseover", () => ln.setStyle({weight: 8}));
      ln.on("mouseout", () => ln.setStyle({weight: 5}));
    }
  });
  if (fg.getLayers().length) map.fitBounds(fg.getBounds(), {padding: [30, 30]});
  else map.setView([50, 9], 6);
  Promise.all(ts.slice(0, 14).map(t => (t.photos ? api(`/api/photos?tour_id=${t.id}&limit=6`).catch(() => []) : []))).then(a => {
    const ph = a.flat();
    if (!$("#cph")) return;
    $("#cph").innerHTML =
      ph.map((p, i) => `<img loading="lazy" src="/pic/${p.id}?size=300" data-i="${i}">`).join("") ||
      '<span class="mut">Keine Fotos.</span>';
    bindThumbs($("#cph"), ph);
  });
  const plan = await api(`/api/tiles/plan?ids=${ts.map(t => t.id).join(",")}`).catch(() => null);
  if (plan)
    $("#cofm").textContent = plan.missing
      ? `${plan.missing} von ${plan.total} Kacheln fehlen noch (ca. ${Math.ceil(plan.missing / 60)} Min.)`
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
VIEWS.trips = async () => {
  $("#main").innerHTML =
    `<div class="sec" style="margin-top:0"><h2>Reisen</h2><span class="sub">automatisch erkannt: Touren weit weg von zu Hause an aufeinanderfolgenden Tagen</span></div><div id="tr" class="mut">Wird geladen …</div>`;
  const [tr, tg] = await Promise.all([api("/api/trips"), api("/api/tags")]);
  $("#tr").className = "";
  $("#tr").innerHTML =
    (tr.length
      ? `<div class="otdg">${tr.map(x => `<a class="otd" href="#/trip/${x.id}" style="background-image:${x.photo ? `linear-gradient(#0e2a2b33 20%,#0e2a2bf0),url(/pic/${x.photo}?size=600)` : "linear-gradient(#0e2a2b99,#0e2a2bee)"}"><b>${esc(x.region)}</b><span>${dateS(x.start)}${x.end !== x.start ? " – " + dateS(x.end) : ""}</span><small>${x.tours.length} Touren · ${nf(x.km, 0)} km · ${nf(x.up_m, 0)} m</small></a>`).join("")}</div>`
      : '<p class="mut">Keine Reisen erkannt (es braucht mindestens zwei Touren am Stück, über 60 km von deinem üblichen Startort entfernt). Eigene Gruppen legst du mit Tags an.</p>') +
    `<div class="sec"><h2>Alben &amp; Tags</h2><span class="sub">in der Tour über „🏷 Tags“ vergeben</span></div>` +
    (tg.length
      ? `<div class="otdg">${tg.map(x => `<a class="otd" href="#/album/${encodeURIComponent(x.tag)}"${x.photo ? ` style="background-image:linear-gradient(#0e2a2b33 20%,#0e2a2bf0),url(/pic/${x.photo}?size=600)"` : ""}><b>🏷 ${esc(x.tag)}</b><small>${x.n} Touren · ${nf(x.km, 0)} km</small></a>`).join("")}</div>`
      : '<p class="mut">Noch keine Tags vergeben.</p>');
};
VIEWS.trip = async id => {
  const tr = (await api("/api/trips")).find(x => x.id === id);
  if (!tr) throw new Error("Reise nicht gefunden");
  await collView(
    `${tr.region}${tr.country && tr.country !== tr.region ? ", " + tr.country : ""}`,
    `${dateL(tr.start)}${tr.end !== tr.start ? " – " + dateL(tr.end) : ""}`,
    tr.tours,
    "#/trips"
  );
};
VIEWS.album = async tag => {
  tag = decodeURIComponent(tag || "");
  const ts = TOURS.filter(t => (t.tags || "").split("|").includes(tag));
  if (!ts.length) throw new Error("Album ist leer");
  await collView(
    "🏷 " + tag,
    `Album mit ${ts.length} Touren`,
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
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:640px">${g}</svg><div class="chips">${series.map(s => `<span class="chip" style="cursor:default"><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join("")}<span class="mut" style="font-size:13px;margin-left:6px">${unit}</span></div>`;
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
  )}</div><div class="panel"><h2>Höhenmeter pro Stunde</h2>${yearChart(
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
    h += `<div class="sec"><h2>Wetter</h2><span class="sub">${r.length} Touren mit Wetterdaten</span></div><div class="grid g2"><div class="panel"><h2>Bei welcher Temperatur bist du unterwegs?</h2><div class="rows">${bins
      .map(b => {
        const n = r.filter(b[1]).length;
        return `<div class="r"><span>${b[0]}<div class="stack" style="width:${(100 * n) / mxn}%;min-width:2px;margin-top:4px"><div style="width:100%;background:var(--yellow)"></div></div></span><b>${n}</b></div>`;
      })
      .join("")}</div></div>
     <div class="panel"><h2>Extreme &amp; Regen</h2><div class="rows">${
       r.length
         ? `<div class="r"><span>Trocken (unter 1 mm)</span><b>${r.filter(x => x.precip < 1).length} von ${r.length}</b></div>
       <div class="r"><span><a href="#/tour/${hot.id}">Wärmste Tour</a><small>${esc(hot.name)}</small></span><b>${nf(hot.tmax, 0)} °</b></div><div class="r"><span><a href="#/tour/${cold.id}">Kälteste Tour</a><small>${esc(cold.name)}</small></span><b>${nf(cold.tmin, 0)} °</b></div>
       <div class="r"><span><a href="#/tour/${wet.id}">Nasseste Tour</a><small>${esc(wet.name)}</small></span><b>${nf(wet.precip, 1)} mm</b></div>`
         : '<div class="mut">Noch keine Wetterdaten.</div>'
     }</div>
       <div class="row" style="margin-top:12px"><button class="btn alt" id="wxb">Wetter für alle Touren laden${wx.missing ? ` (${wx.missing} offen)` : ""}</button><span id="wxm" class="mut"></span></div></div></div>`;
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
          `<div class="r"><span>${y}<div class="stack" style="width:${(100 * v.km) / mxy}%;margin-top:4px"><div style="width:${v.km ? (100 * v.new_km) / v.km : 0}%;background:var(--yellow)"></div></div></span><b>${nf(v.new_km, 0)} von ${nf(v.km, 0)} km neu</b></div>`
      )
      .join("")}</div></div>
     <div class="panel"><h2>Größte Entdeckungen</h2><div class="rows">${tops.map(([id, v]) => `<div class="r"><span><a href="#/tour/${id}">${esc(BY[id]?.name || id)}</a><small>${BY[id] ? dateS(BY[id].date) : ""} · ${v.pct} % neu</small></span><b>${nf(v.new_km, 1)} km</b></div>`).join("")}</div></div></div>`;
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
    `<div class="panel" style="margin-top:22px"><h2>Umbenennen nach Regeln</h2><p class="mut">Wähle Touren aus, lege eine Regel fest, prüfe die Vorschau und wende sie an.</p>
   <div class="filters"><input id="rn_q" placeholder="Name enthält …"><select id="rn_r"><option value="">Alle Regionen</option>${regionOpts()}</select><select id="rn_s"><option value="">Alle Sportarten</option>${[...new Set(TOURS.map(t => t.sport))].map(s => `<option value="${s}">${sName(s)}</option>`).join("")}</select></div>
   <div class="filters"><select id="rn_a"><option value="pre">Vorsilbe hinzufügen</option><option value="suf">Nachsilbe hinzufügen</option><option value="rep">Text ersetzen (Suchen → Ersetzen)</option><option value="date">Datum und Uhrzeit am Ende entfernen</option></select><input id="rn_x" placeholder="Text / Suchen"><input id="rn_y" placeholder="Ersetzen durch"></div>
   <div class="row"><label class="chk" style="margin:0"><input type="checkbox" id="rn_k"> auch bei Komoot umbenennen</label><button class="btn alt" id="rn_p">Vorschau</button><button class="btn" id="rn_go" disabled>Anwenden</button><span id="rn_m" class="mut"></span></div><div class="rows" id="rn_l" style="margin-top:10px"></div></div>`
  );
  let plan = [];
  const calc = () => {
    const q = $("#rn_q").value.toLowerCase(),
      r = $("#rn_r").value,
      s = $("#rn_s").value,
      act = $("#rn_a").value,
      x = $("#rn_x").value,
      y = $("#rn_y").value;
    plan = TOURS.filter(t => (!q || t.name.toLowerCase().includes(q)) && (!r || inRegion(t, r)) && (!s || t.sport === s))
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
    $("#rn_m").textContent = `${plan.length} Touren betroffen`;
    $("#rn_go").disabled = !plan.length;
  };
  $("#rn_p").onclick = calc;
  $("#rn_go").onclick = async e => {
    if (!confirm(`${plan.length} Touren umbenennen${$("#rn_k").checked ? " (auch bei Komoot)" : ""}?`)) return;
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
    `<div class="panel" style="margin-top:30px"><h2>Benachrichtigung (optional)</h2><p class="mut">Trage eine Webhook-Adresse ein (z. B. ntfy, Gotify oder ein eigener Dienst). Bei einer neuen Warnung (Zepp-Token, Backup, Job-Fehler, Speicher) wird dort eine Textnachricht abgeliefert, höchstens stündlich geprüft. Leer = aus. Die App stellt keine Verbindung zu Home Assistant her.</p>
   <div class="field"><label>Webhook-Adresse</label><input data-k="notify_url" value="${esc(s.notify_url || "")}" placeholder="https://ntfy.sh/mein-thema"></div><div class="row"><button class="btn alt" id="ntest">Testnachricht senden (nach „Speichern“)</button><span id="ntm" class="mut"></span></div></div>`
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
