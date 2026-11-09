/* =====================  Reisen: Name und Zeitraum ändern  ===================== */
const _trip28 = VIEWS.trip;
VIEWS.trip = async id => {
  await _trip28(id);
  const tr = (await api("/api/trips").catch(() => [])).find(x => x.id === id),
    bar = document.querySelector("#main .row");
  if (!tr || !bar || bar.querySelector("#tredit")) return;
  bar.insertAdjacentHTML("beforeend", `<span class="sp"></span><button class="btn alt sm" id="tredit" title="Namen oder Zeitraum dieser Reise ändern">✎ Reise bearbeiten</button>`);
  $("#tredit").onclick = () => {
    const m = modal(`<h2>Reise bearbeiten</h2>
     <p class="mut fs14">Name und Zeitraum der automatisch erkannten Reise. Ein anderer Zeitraum nimmt alle Touren dieser Tage auf (auch solche, die nicht weit von zu Hause waren) bzw. lässt Touren außerhalb weg.</p>
     <div class="field"><label>Name</label><input id="tn" maxlength="120" value="${esc(tr.region)}" class="w100"></div>
     <div class="row g8 aic mt8"><label>Von <input id="tf" type="date" value="${tr.start}"></label><label>bis <input id="tt" type="date" value="${tr.end}"></label></div>
     <div class="row mt12"><button class="btn" id="tok">Speichern</button>${tr.edited ? `<button class="btn alt" id="trs" title="Zurück zu Name und Zeitraum, wie sie erkannt wurden">Zurücksetzen</button>` : ""}<button class="btn ghost" id="tno">Abbrechen</button><span id="ter" class="bad"></span></div>`);
    const send = async body => {
      try {
        await api(`/api/trips/${encodeURIComponent(id)}/edit`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
        m.remove();
        route();
      } catch (e) {
        m.querySelector("#ter").textContent = e.message;
      }
    };
    m.querySelector("#tno").onclick = () => m.remove();
    m.querySelector("#tok").onclick = () => send({name: m.querySelector("#tn").value, start: m.querySelector("#tf").value, end: m.querySelector("#tt").value});
    const rs = m.querySelector("#trs");
    if (rs) rs.onclick = () => send({});
  };
};

/* ---- Reisebericht: druckbare Seite / PDF ---- */
VIEWS.tripsheet = async id => {
  const tr = (await api("/api/trips")).find(x => x.id === id);
  if (!tr) throw new Error("Reise nicht gefunden");
  await pdfPhotoLoad();
  const ts = tr.tours.map(i => BY[i]).filter(Boolean).sort((a, b) => a.start_ts - b.start_ts),
    sum = f => ts.reduce((c, t) => c + (f(t) || 0), 0),
    days = [...new Set(ts.map(t => t.date.slice(0, 10)))],
    fig = (v, u, l) => `<div class="fig"><div class="v">${v}${u ? `<span class="u">${u}</span>` : ""}</div><div class="l">${l}</div></div>`;
  const perDay = days.map(d => {
    const a = ts.filter(t => t.date.slice(0, 10) === d);
    return `<tr class="dayh"><td colspan="6"><b>${dateL(d)}</b> <span class="mut">· ${nf(a.reduce((c, t) => c + t.km, 0), 1)} km · ↑ ${nf(a.reduce((c, t) => c + (t.up_m || 0), 0), 0)} m · ↓ ${nf(a.reduce((c, t) => c + (t.down_m || 0), 0), 0)} m</span></td></tr>` +
      a.map(t => `<tr><td>${timeS(t.date)}</td><td class="tal">${esc(t.name)}</td><td>${sName(t.sport)}</td><td>${nf(t.km, 1)}</td><td>${nf(t.up_m || 0, 0)}</td><td>${nf(t.down_m || 0, 0)}</td></tr>`).join("");
  }).join("");
  $("#main").innerHTML = `<div class="sheet">
   <div class="row noprint"><a class="back" href="#/trip/${esc(id)}">‹ Zurück zur Reise</a><span class="sp"></span>${pdfPhotoBar()}${pdfBtn()}<button class="btn ghost" id="shp">Drucken</button></div>
   <div class="mut mt14">${dateL(tr.start)}${tr.end !== tr.start ? " – " + dateL(tr.end) : ""}</div>
   <h1 class="fs34 m8-0-14">${esc(tr.region)}${tr.country && tr.country !== tr.region ? ", " + esc(tr.country) : ""}</h1>
   <div class="figs">${fig(ts.length, "", "Touren")}${fig(nf(sum(t => t.km), 1), "km", "Strecke")}${fig(nf(sum(t => t.up_m), 0), "m", "Aufstieg")}${fig(nf(sum(t => t.down_m), 0), "m", "Abstieg")}${fig(nf(sum(t => t.h), 1), "h", "Unterwegs")}${fig(days.length, "", "Tage")}</div>
   <div class="tmap mt14" id="tm" style="height:380px"></div>
   <div id="tleg" class="mut fs13 m6-0-0"></div>
   ${collStats(ts)}
   <div class="sec"><h2>Tag für Tag</h2></div><div class="tblw"><table class="cstat"><thead><tr><th>Zeit</th><th class="tal">Tour</th><th>Aktivität</th><th>km</th><th>↑ m</th><th>↓ m</th></tr></thead><tbody>${perDay}</tbody></table></div>
   <div class="thumbs sheetph" id="th"></div></div>`;
  map = mkMap("tm", {layers: false});
  map.setView([tr.lat || 50, tr.lng || 8], 8);
  const fg = L.featureGroup().addTo(map);
  const co = await Promise.all(ts.map(t => api(`/api/tours/${t.id}/coords`).catch(() => [])));
  ts.forEach((t, i) => {
    const p = cleanPts(co[i]).map(x => [x[0], x[1]]);
    if (p.length > 1) L.polyline(p, {color: DAYC[days.indexOf(t.date.slice(0, 10)) % DAYC.length], weight: 4}).addTo(fg);
  });
  if (fg.getLayers().length) map.fitBounds(fg.getBounds(), {padding: [20, 20]});
  $("#tleg").innerHTML = days.map((d, i) => `<span class="mr12 nw"><i class="vam mr4" style="display:inline-block;width:14px;height:4px;background:${DAYC[i % DAYC.length]}"></i>${dateS(d)}</span>`).join("");
  $("#shp").onclick = () => {
    map.invalidateSize();
    setTimeout(() => print(), 300);
  };
  // Fotos: je Tour die besten, insgesamt höchstens so viele wie eingestellt, gleichmäßig über die Reise verteilt
  let all = null;
  const photos = async () => {
    if (!$("#th")) return;
    if (!PDFP.on) {
      $("#th").innerHTML = "";
      return;
    }
    if (!all) {
      const per = Math.max(2, Math.ceil(24 / Math.max(1, ts.length)));
      all = (await Promise.all(ts.map(t => (t.photos ? api(`/api/tours/${t.id}/best-photos?n=${per}`).then(r => r.photos || []).catch(() => []) : Promise.resolve([]))))).flat();
    }
    $("#th").innerHTML = [...new Set(spread(all, PDFP.n))].map(p => `<div class="th"><img src="/pic/${p.id}?size=500"></div>`).join("");
  };
  pdfPhotoBind(photos);
  pdfBindDl(`/api/trips/${encodeURIComponent(id)}/pdf`);
  await photos();
};
const _trip28b = VIEWS.trip;
VIEWS.trip = async id => {
  await _trip28b(id);
  const b = $("#tredit");
  if (b && !$("#trpdf")) b.insertAdjacentHTML("beforebegin", `<a class="btn alt sm" id="trpdf" href="#/tripsheet/${encodeURIComponent(id)}" title="Reisebericht mit Karte, Statistik und Fotos – als PDF herunterladbar">Reisebericht (PDF)</a> `);
  if (b && !$("#trhide")) {
    b.insertAdjacentHTML("afterend", ` <button class="btn alt sm" id="trhide" title="Diese Gruppe ist keine Reise (z. B. ein Tagesausflug) – aus der Liste entfernen. Die Touren bleiben erhalten.">Keine Reise</button>`);
    $("#trhide").onclick = async () => {
      if (!confirm("Diese Gruppe aus den Reisen entfernen? Die Touren selbst bleiben unverändert, die Reise lässt sich später unter „Reisen“ wiederherstellen.")) return;
      await api(`/api/trips/${encodeURIComponent(id)}/hide`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({hide: true})});
      location.hash = "#/trips";
    };
  }
};

/* Reisenliste: ausgeblendete Reisen wiederherstellen */
const _trips28 = VIEWS.trips;
VIEWS.trips = async (...a) => {
  await _trips28(...a);
  const hid = await api("/api/trips?hidden=1").catch(() => []);
  if (!hid.length || $("#trhidbox")) return;
  $("#main").insertAdjacentHTML("beforeend", `<details id="trhidbox" class="mt28"><summary class="mut cp">Entfernte Reisen (${hid.length})</summary>${hid
    .map(t => `<div class="r g10 aic p8-0" style="display:flex;border-bottom:1px solid var(--rule)"><span class="fx1">${esc(t.region)} <small class="mut">${esc(t.start)}${t.end !== t.start ? " – " + esc(t.end) : ""}, ${t.tours.length} Touren</small></span><button class="btn alt sm" data-rt="${esc(t.id)}">Wiederherstellen</button></div>`)
    .join("")}</details>`);
  document.querySelectorAll("[data-rt]").forEach(
    b =>
      (b.onclick = async () => {
        await api(`/api/trips/${encodeURIComponent(b.dataset.rt)}/hide`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({hide: false})});
        route();
      })
  );
};
