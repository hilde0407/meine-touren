/* =====================  Reisen: Name und Zeitraum ändern  ===================== */
const _trip28 = VIEWS.trip;
VIEWS.trip = async id => {
  await _trip28(id);
  const tr = (await api("/api/trips").catch(() => [])).find(x => x.id === id),
    bar = document.querySelector("#main [data-rs=kopf] .row");                // 3.33.0: die Aktionen gehören in den Kopf (er kann auf der Seite weiter unten stehen)
  if (!tr || !bar || bar.querySelector("#tredit")) return;
  bar.insertAdjacentHTML("beforeend", `<span class="sp"></span><button class="btn alt sm" id="tredit" title="Namen oder Zeitraum dieser Reise ändern">✎ Reise bearbeiten</button>`);
  $("#tredit").onclick = () => {
    if (tr.custom) return tripDialog(tr);                                              // 3.63.0: eigene Reise: Name, Zeitraum und Touren
    const m = uiModal(`<h2>Reise bearbeiten</h2>
     <p class="mut fs14">Name und Zeitraum der automatisch erkannten Reise. Ein anderer Zeitraum nimmt alle Touren dieser Tage auf (auch solche, die nicht weit von zu Hause waren) bzw. lässt Touren außerhalb weg.</p>
     <div class="field"><label>Name</label><input id="tn" maxlength="120" value="${esc(tr.region)}" class="w100"></div>
     <div class="row g8 aic mt8"><label>Von <input id="tf" type="date" value="${tr.start}"></label><label>bis <input id="tt" type="date" value="${tr.end}"></label></div>
     <div id="ter" class="bad"></div><div class="uifoot">${tr.edited ? `<button class="btn alt" id="trs" title="Zurück zu Name und Zeitraum, wie sie erkannt wurden">Standard wiederherstellen</button><span class="sp"></span>` : ""}<button class="btn ghost" id="tno">Abbrechen</button><button class="btn" id="tok">Speichern</button></div>`);
    const send = async body => {
      try {
        await api(`/api/trips/${encodeURIComponent(id)}/edit`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
        window._sReisen = null;                                                        // Reisen der Suche neu holen (06-erweiterungen.js)
        m.remove();
        route();
      } catch (e) {
        m.querySelector("#ter").textContent = e.message;
      }
    };
    m.querySelector("#tno").onclick = () => m.remove();
    m.querySelector("#tok").onclick = () => {
      const n = m.querySelector("#tn");
      if (!n.value.trim()) {                                                           // 3.63.0: ein leerer Name entfernt nie eine Reise: der automatische Name wird eingesetzt, erst „Speichern“ übernimmt ihn
        n.value = tr.auto_region || tr.region;
        m.querySelector("#ter").textContent = "Der Name war leer – der automatische Name ist eingesetzt. Zum Übernehmen noch einmal „Speichern“.";
        return;
      }
      send({name: n.value, start: m.querySelector("#tf").value, end: m.querySelector("#tt").value});
    };
    const rs = m.querySelector("#trs");
    if (rs) rs.onclick = async () => { if (await uiConfirm({title: "Standard wiederherstellen?", text: "Name und Zeitraum der Reise werden wieder so, wie sie erkannt wurden.", ok: "Standard wiederherstellen"})) send({}); };
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
    return `<tr class="dayh"><td colspan="6"><b>${fmtDatum(d)}</b> <span class="mut">· ${fmtKm(a.reduce((c, t) => c + t.km, 0))} · ${fmtAuf(a.reduce((c, t) => c + (t.up_m || 0), 0))} · ${fmtAb(a.reduce((c, t) => c + (t.down_m || 0), 0))}</span></td></tr>` +
      a.map(t => `<tr><td>${fmtUhrzeit(t.date)}</td><td class="tal">${esc(t.name)}</td><td>${sName(t.sport)}</td><td>${nf(t.km, 1)}</td><td>${nf(t.up_m || 0, 0)}</td><td>${nf(t.down_m || 0, 0)}</td></tr>`).join("");
  }).join("");
  $("#main").innerHTML = `<div class="sheet">
   <div class="row noprint"><a class="back" href="#/trip/${esc(id)}">‹ Zurück zur Reise</a><span class="sp"></span>${pdfPhotoBar()}${pdfBtn()}<button class="btn ghost" id="shp">Drucken</button></div>
   <div class="mut mt14">${fmtDatum(tr.start)}${tr.end !== tr.start ? " – " + fmtDatum(tr.end) : ""}</div>
   <h1 class="fs34 m8-0-14">${esc(tr.region)}${tr.country && tr.country !== tr.region ? ", " + esc(tr.country) : ""}</h1>
   <div class="figs">${fig(ts.length, "", "Touren")}${fig(fmtKm(sum(t => t.km), {summe: true, einheit: false}), "km", "Strecke")}${fig(nf(sum(t => t.up_m), 0), "m", "Aufstieg")}${fig(nf(sum(t => t.down_m), 0), "m", "Abstieg")}${fig(fmtDauerTeile(sum(t => t.h) * 3600, {summe: true}).v, fmtDauerTeile(sum(t => t.h) * 3600, {summe: true}).u, "Unterwegs")}${fig(days.length, "", "Tage")}</div>
   <div class="tmap mt14" id="tm" style="height:380px"></div>
   <div id="tleg" class="mut fs13 m6-0-0"></div>
   ${collStats(ts)}
   <div class="sec"><h2>Tag für Tag</h2></div><div class="tblw"><table class="cstat"><thead><tr><th>Zeit</th><th class="tal">Tour</th><th>Sportart</th><th>Strecke (km)</th><th>Aufstieg (m)</th><th>Abstieg (m)</th></tr></thead><tbody>${perDay}</tbody></table></div>
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
  $("#tleg").innerHTML = days.map((d, i) => `<span class="mr12 nw"><i class="vam mr4" style="display:inline-block;width:14px;height:4px;background:${DAYC[i % DAYC.length]}"></i>${fmtDatumKurz(d)}</span>`).join("");
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
    $("#th").innerHTML = [...new Set(spread(all, PDFP.n))].map(p => `<div class="th"><img decoding="async" src="${picSrc(p, 500)}"></div>`).join("");
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
  const cur = (await api("/api/trips").catch(() => [])).find(x => x.id === id);
  if (b && cur && cur.custom && !$("#trdel")) {                                          // 3.63.0: eigene Reise: Löschen (mit Rückfrage) statt „Keine Reise“
    b.insertAdjacentHTML("afterend", ` <button class="btn alt sm" id="trdel" title="Diese eigene Reise löschen. Die Touren bleiben erhalten.">Löschen</button>`);
    $("#trdel").onclick = async () => {
      if (!await uiConfirm({title: `„${cur.region}“ löschen?`, text: "Die eigene Reise wird gelöscht. Die Touren selbst bleiben unverändert. Das lässt sich nicht rückgängig machen; die Reise kannst du aber neu erstellen.", danger: true, ok: "Löschen"})) return;
      await api(`/api/trips/${encodeURIComponent(id)}`, {method: "DELETE"});
      window._sReisen = null;
      location.hash = "#/trips";
    };
  }
  if (b && !(cur && cur.custom) && !$("#trhide")) {
    b.insertAdjacentHTML("afterend", ` <button class="btn alt sm" id="trhide" title="Diese Touren sind keine Reise (z. B. ein Tagesausflug) – aus der Liste entfernen. Die Touren bleiben erhalten.">Keine Reise</button>`);
    $("#trhide").onclick = async () => {
      if (!await uiConfirm({text: "Diese Touren aus den Reisen entfernen? Die Touren selbst bleiben unverändert, die Reise lässt sich später unter „Reisen“ → „Entfernte Reisen“ wiederherstellen.", danger: true, ok: "Entfernen"})) return;
      await api(`/api/trips/${encodeURIComponent(id)}/hide`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({hide: true})});
      window._sReisen = null;
      location.hash = "#/trips";
    };
  }
};

/* 3.63.0 Reise erstellen / bearbeiten (eigene Reise: Name, Zeitraum und/oder gewählte Touren; Tabelle trip_custom). Der Dialog zeigt die Touren des Zeitraums zum Abhaken (Vorgabe: alle) und die schon gewählten;
   Touren einer anderen eigenen Reise sind gesperrt (eine Tour gehört zu höchstens einer eigenen Reise). tr = die eigene Reise beim Bearbeiten. */
async function tripDialog(tr) {
  const day = t => String(t.date).slice(0, 10), trips = await api("/api/trips").catch(() => []), owner = {};
  trips.filter(x => x.custom && (!tr || x.id !== tr.id)).forEach(x => x.tours.forEach(i => (owner[i] = x.region)));
  const newest = TOURS.reduce((a, t) => (day(t) > a ? day(t) : a), "1970-01-01"), sel = new Set(tr ? tr.tours : []), seen = new Set();
  const m = uiModal(`<h2>${tr ? "Reise bearbeiten" : "Reise erstellen"}</h2>
   <p class="mut fs14">Name vergeben, Zeitraum wählen und die Touren abhaken, die zur Reise gehören. Die Reise erscheint danach wie eine erkannte Reise unter Reisen. Touren einer eigenen Reise gehören nicht mehr zur automatisch erkannten Reise.</p>
   <div class="field"><label>Name</label><input id="tcn" maxlength="120" class="w100" value="${esc(tr ? tr.region : "")}" placeholder="z. B. Rostock"></div>
   <div class="row g8 aic mt8"><label>Von <input id="tcf" type="date" value="${tr ? tr.start : flDayAdd(newest, -6)}"></label><label>bis <input id="tct" type="date" value="${tr ? tr.end : newest}"></label></div>
   <div class="row g8 aic mt8"><input id="tcs" type="search" class="fx1 mnw200" placeholder="Touren suchen …" aria-label="Touren suchen"><button class="btn ghost sm" id="tca" type="button">Alle</button><button class="btn ghost sm" id="tck" type="button">Keine</button></div>
   <div id="tcl" class="rows m10-0 ova" style="max-height:260px"></div><div id="tcc" class="mut fs14" role="status" aria-live="polite"></div>
   <div id="tcer" class="bad"></div><div class="uifoot"><button class="btn ghost" id="tcno" type="button">Abbrechen</button><button class="btn" id="tcok" type="button">Speichern</button></div>`);
  const q = s => m.querySelector(s);
  const inRange = () => TOURS.filter(t => day(t) >= q("#tcf").value && day(t) <= q("#tct").value);
  const take = () => inRange().forEach(t => {
    if (!seen.has(t.id)) {
      seen.add(t.id);
      if (!owner[t.id] && !tr) sel.add(t.id);
    }
  });
  const shown = () => {
    const need = q("#tcs").value.trim().toLowerCase(), set = new Map(inRange().map(t => [t.id, t]));
    sel.forEach(i => BY[i] && set.set(i, BY[i]));
    return [...set.values()].filter(t => !need || String(t.name).toLowerCase().includes(need)).sort((a, b) => a.start_ts - b.start_ts);
  };
  const count = () => (q("#tcc").textContent = sel.size === 1 ? "1 Tour gewählt" : `${sel.size} Touren gewählt`);
  const list = () => {
    const ts = shown();
    q("#tcl").innerHTML = ts.length
      ? ts.map(x => `<label class="r g8 aic" style="display:flex"><input type="checkbox" class="cb" data-i="${esc(x.id)}"${sel.has(x.id) ? " checked" : ""}${owner[x.id] ? " disabled" : ""}><span>${fmtDatumKurz(x.date)} · ${esc(x.name)} <span class="mut">${fmtKm(x.km)}${owner[x.id] ? ` · gehört zu „${esc(owner[x.id])}“` : ""}</span></span></label>`).join("")
      : '<p class="mut">Keine Touren in diesem Zeitraum.</p>';
    count();
  };
  if (tr) inRange().forEach(t => seen.add(t.id)); else take();
  list();
  q("#tcl").onchange = e => {
    const c = e.target.closest("[data-i]");
    if (c) (c.checked ? sel.add(c.dataset.i) : sel.delete(c.dataset.i));
    count();
  };
  m.querySelectorAll("input[type=date]").forEach(i => (i.onchange = () => { take(); list(); }));
  q("#tcs").oninput = list;
  q("#tca").onclick = () => { shown().forEach(t => !owner[t.id] && sel.add(t.id)); list(); };
  q("#tck").onclick = () => { shown().forEach(t => sel.delete(t.id)); list(); };
  q("#tcno").onclick = () => m.remove();
  q("#tcok").onclick = async () => {
    const name = q("#tcn").value.trim(), er = q("#tcer");
    if (!name) return void (er.textContent = "Bitte einen Namen für die Reise eingeben.");
    if (!sel.size) return void (er.textContent = "Bitte mindestens eine Tour wählen.");
    try {
      const body = JSON.stringify({name, start: q("#tcf").value, end: q("#tct").value, tours: [...sel]}), h = {"content-type": "application/json"};
      window._sReisen = null;
      if (tr) {
        await api(`/api/trips/${encodeURIComponent(tr.id)}/edit`, {method: "POST", headers: h, body});
        m.remove();
        route();
      } else {
        const r = await api("/api/trips", {method: "POST", headers: h, body});
        m.remove();
        location.hash = "#/trip/" + encodeURIComponent(r.id);
      }
    } catch (e) {
      er.textContent = e.message;
    }
  };
  q("#tcn").focus();
}
/* Entfernte Reisen wiederherstellen (Fenster aus der Hinweiszeile der Reisenliste) */
function tripRestoreDialog(hid) {
  const m = uiModal(`<h2>Entfernte Reisen</h2><p class="mut fs14">Diese erkannten Reisen hast du aus der Liste entfernt. Die Touren sind unverändert; „Wiederherstellen“ bringt die Reise zurück.</p>
   ${hid.map(t => `<div class="r g10 aic p8-0" style="display:flex;border-bottom:1px solid var(--rule)"><span class="fx1">${esc(t.region)} <small class="mut">${fmtDatumKurz(t.start)}${t.end !== t.start ? " – " + fmtDatumKurz(t.end) : ""}, ${t.tours.length} Touren</small></span><button class="btn alt sm" data-rt="${esc(t.id)}">Wiederherstellen</button></div>`).join("")}
   <div class="uifoot"><button class="btn ghost" id="trrx">Schließen</button></div>`);
  m.querySelector("#trrx").onclick = () => m.remove();
  m.querySelectorAll("[data-rt]").forEach(b => (b.onclick = async () => {
    await api(`/api/trips/${encodeURIComponent(b.dataset.rt)}/hide`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({hide: false})});
    window._sReisen = null;
    m.remove();
    route();
  }));
}
const _trips28c = VIEWS.trips;
VIEWS.trips = async (...a) => {
  await _trips28c(...a);
  const sec = $("#tr");
  if (!sec || $("#trnew")) return;
  const hid = await api("/api/trips?hidden=1").catch(() => []);
  if (!$("#tr") || $("#trnew")) return;
  sec.insertAdjacentHTML("afterbegin", `<div class="row g8 aic mb10"><button class="btn alt sm" id="trnew">＋ Reise erstellen …</button>${hid.length ? `<button class="btn ghost sm" id="trrest">${hid.length === 1 ? "1 entfernte Reise" : hid.length + " entfernte Reisen"} – wiederherstellen …</button>` : ""}</div>`);
  $("#trnew").onclick = () => tripDialog(null);
  if (hid.length) $("#trrest").onclick = () => tripRestoreDialog(hid);
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
        window._sReisen = null;
        route();
      })
  );
};
