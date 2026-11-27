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
  const gk = document.querySelector("#main [data-rs=kopf] > .mut"), gx = cur && cur.area && Gebiete.nach[cur.area];                 // 3.65.0: das Gebiet der Reise (Name der erkannten Reise) als Sprung zu den Touren dort
  if (gk && gx && !gk.querySelector(".rsgeb")) gk.insertAdjacentHTML("beforeend", ` · <span class="rsgeb">Gebiet: <a class="gblink" href="#/tours?g=${encodeURIComponent(gx.id)}" title="Alle Touren in diesem Gebiet">${esc(gx.name)}</a></span>`);
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

/* 3.63.0 Reise erstellen / bearbeiten (eigene Reise: Name, Zeitraum und/oder gewählte Touren; Tabelle trip_custom).
   3.67.0 Auswahl der Touren neu: nichts ist vorgewählt (vorher: die Touren der letzten 7 Tage und jeder Tag, den man im Zeitraum nachträglich erweiterte); die Touren stehen nach Tag (oder Gebiet) gruppiert,
   neueste zuerst, mit Datum, Name, Ort/Gebiet und Strecke. „Zeitraum markieren“ (Knopf), Gruppenkopf mit Kontrollkästchen (auch teilweise gewählt), Suchfeld, Alle/Keine für die gefilterte Liste.
   Immer sichtbar: Anzahl, Zeitraum und Gebiete der Auswahl; nicht blockierende Warnung bei weit entfernten Gebieten/Ländern, vielen Gebieten oder Lücken über 14 Tage. Touren einer anderen eigenen Reise sind gesperrt,
   Touren einer erkannten Reise tragen „in Reise X“ (sie wechseln beim Speichern in die eigene Reise). tr = die eigene Reise beim Bearbeiten. */
const TRIP_LUECKE_TAGE = 14, TRIP_FERN_KM = 300, TRIP_GEB_MAX = 2, TRIP_ZEILEN = 300;
function tripAuswahlInfo(ts) {                                                   // reine Auswertung einer Auswahl: Anzahl, Zeitraum, Gebiete, Warnungen (auch einzeln testbar)
  const day = t => String(t.date).slice(0, 10), nm = t => { const a = Gebiete.anzeige(t); return (a && a.name) || t.g_state || t.g_country || ""; };
  const days = [...new Set(ts.map(day))].sort(), gc = {}, ld = new Set();
  ts.forEach(t => { const g = nm(t); if (g) gc[g] = (gc[g] || 0) + 1; if (t.g_country) ld.add(t.g_country); });
  const geb = Object.entries(gc).sort((a, b) => b[1] - a[1]).map(x => x[0]);
  const km = (a, b) => { const r = Math.PI / 180, dl = (b.lng - a.lng) * r, p1 = a.lat * r, p2 = b.lat * r; return 6371 * Math.acos(Math.min(1, Math.sin(p1) * Math.sin(p2) + Math.cos(p1) * Math.cos(p2) * Math.cos(dl))); };
  const pts = ts.filter(t => Number.isFinite(t.lat) && Number.isFinite(t.lng) && (t.lat || t.lng));
  let fern = 0;
  if (pts.length > 1) {                                                           // zwei Durchläufe: weitester Punkt vom ersten, dann weitester von diesem (genau genug für eine Warnung)
    const far = p => pts.reduce((m, q) => (km(p, q) > km(p, m) ? q : m), p), b = far(pts[0]);
    fern = km(b, far(b));
  }
  const luecken = [];
  for (let i = 1; i < days.length; i++) { const d = Math.round((Date.parse(days[i]) - Date.parse(days[i - 1])) / 864e5); if (d > TRIP_LUECKE_TAGE) luecken.push({von: days[i - 1], bis: days[i], tage: d}); }
  return {n: ts.length, von: days[0] || "", bis: days[days.length - 1] || "", geb, laender: [...ld], fern: Math.round(fern), luecken};
}
function tripZeitraumText(von, bis) {                                            // „17.09.–21.11.“ (Jahr nur, wenn nicht das laufende Jahr oder zwei Jahre)
  if (!von) return "";
  const lg = FMT_LG(), cut = s => s.replace(/[./]\d{4}$/, lg === "de" ? "." : ""), y = new Date().getFullYear(), same = von.slice(0, 4) === bis.slice(0, 4);
  if (von === bis) return fmtDatumKurz(von);
  return same && +von.slice(0, 4) === y ? `${cut(fmtDatumKurz(von))}–${cut(fmtDatumKurz(bis))}` : `${fmtDatumKurz(von)}–${fmtDatumKurz(bis)}`;
}
async function tripDialog(tr) {
  const day = t => String(t.date).slice(0, 10), trips = await api("/api/trips").catch(() => []), owner = {}, erkannt = {};
  trips.forEach(x => (!tr || x.id !== tr.id) && x.tours.forEach(i => (x.custom ? (owner[i] = x.region) : (erkannt[i] = x.region))));
  const sel = new Set(tr ? tr.tours : []), nm = t => { const a = Gebiete.anzeige(t); return (a && a.name) || t.g_state || t.g_country || ""; };
  let modus = "tag", zeilen = TRIP_ZEILEN;
  const m = uiModal(`<h2>${tr ? "Reise bearbeiten" : "Reise erstellen"}</h2>
   <p class="mut fs14">Name vergeben und die Touren abhaken, die zur Reise gehören. Es ist nichts vorgewählt. Die Reise erscheint danach wie eine erkannte Reise unter Reisen. Touren einer eigenen Reise gehören nicht mehr zur automatisch erkannten Reise.</p>
   <div class="field"><label for="tcn">Name</label><input id="tcn" maxlength="120" class="w100" value="${esc(tr ? tr.region : "")}" placeholder="z. B. Rostock"></div>
   <div class="row g8 aic mt8 tcz"><span class="mut fs14">Zeitraum markieren:</span><label>Von <input id="tcf" type="date"></label><label>bis <input id="tct" type="date"></label><button class="btn alt sm" id="tcz" type="button">Markieren</button></div>
   <div class="row g8 aic mt8"><input id="tcs" type="search" class="fx1 mnw200" placeholder="Touren suchen …" aria-label="Touren suchen"><button class="btn ghost sm" id="tca" type="button" title="Alle Touren der gefilterten Liste wählen">Alle</button><button class="btn ghost sm" id="tck" type="button" title="Alle Touren der gefilterten Liste abwählen">Keine</button></div>
   <div class="row g8 aic mt8"><span class="mut fs14">Gruppieren:</span><button class="chip on" id="tcgt" type="button" aria-pressed="true">Nach Tag</button><button class="chip" id="tcgg" type="button" aria-pressed="false">Nach Gebiet</button></div>
   <div class="tcbar"><div id="tcc" class="tcsum" role="status" aria-live="polite"></div><div id="tcw" class="tcwarn" role="status" aria-live="polite"></div></div>
   <div id="tcl" class="tclist ova"></div>
   <div id="tcer" class="bad"></div><div class="uifoot"><button class="btn ghost" id="tcno" type="button">Abbrechen</button><button class="btn" id="tcok" type="button">Speichern</button></div>`);
  const q = s => m.querySelector(s);
  const frei = t => !owner[t.id];
  const alle = () => TOURS.filter(t => t.date).sort((a, b) => b.start_ts - a.start_ts);          // neueste zuerst, wie die Tourenliste
  const gefiltert = () => {
    const need = Gebiete.fold(q("#tcs").value.trim());
    return alle().filter(t => !need || Gebiete.fold(`${t.name} ${Gebiete.regionText(t)} ${fmtDatumKurz(t.date)} ${day(t)}`).includes(need));
  };
  const gruppen = ts => {
    const g = new Map();
    ts.forEach(t => { const k = modus === "tag" ? day(t) : nm(t) || "~"; (g.get(k) || g.set(k, []).get(k)).push(t); });
    return [...g.entries()].map(([k, l]) => ({k, l, geb: modus === "tag" ? [...new Set(l.map(nm).filter(Boolean))].join(", ") : ""}));
  };
  const summe = () => {
    const ts = [...sel].map(i => BY[i]).filter(Boolean), i = tripAuswahlInfo(ts), w = [];
    q("#tcc").innerHTML = ts.length ? `<b>${ts.length === 1 ? "1 Tour" : `${ts.length} Touren`}</b> · ${esc(tripZeitraumText(i.von, i.bis))}${i.geb.length ? " · " + esc(i.geb.slice(0, 4).join(", ") + (i.geb.length > 4 ? ` und ${i.geb.length - 4} weitere` : "")) : ""}` : "0 Touren gewählt";
    if (i.laender.length > 1) w.push(`Die Touren liegen in ${i.laender.length} Ländern (${i.laender.slice(0, 4).join(", ")}) – wirklich eine Reise?`);
    else if (i.fern > TRIP_FERN_KM) w.push(`Die Touren liegen bis zu ${fmtZahl(i.fern, 0)} km auseinander – wirklich eine Reise?`);
    else if (i.geb.length > TRIP_GEB_MAX) w.push(`Die Touren liegen in ${i.geb.length} Gebieten – wirklich eine Reise?`);
    if (i.luecken.length) { const l = i.luecken.reduce((a, b) => (b.tage > a.tage ? b : a)); w.push(`Zwischen ${fmtDatumKurz(l.von)} und ${fmtDatumKurz(l.bis)} liegen ${l.tage} Tage ohne gewählte Tour${i.luecken.length > 1 ? ` (insgesamt ${i.luecken.length} Lücken über ${TRIP_LUECKE_TAGE} Tage)` : ""}.`); }
    const aus = ts.filter(t => erkannt[t.id]), von = [...new Set(aus.map(t => erkannt[t.id]))];
    if (aus.length) w.push(`${aus.length === 1 ? "1 Tour gehört" : `${aus.length} Touren gehören`} zu ${von.length === 1 ? `der Reise „${von[0]}“` : `${von.length} anderen Reisen`} und ${aus.length === 1 ? "wechselt" : "wechseln"} beim Speichern in diese Reise.`);
    q("#tcw").innerHTML = w.map(x => `<p class="tcw">⚠ ${esc(x)}</p>`).join("");
  };
  const zeile = t => {
    const o = owner[t.id], e = erkannt[t.id], reg = Gebiete.regionText(t);
    return `<label class="tcr${o ? " off" : ""}"><input type="checkbox" class="cb" data-i="${esc(t.id)}"${sel.has(t.id) ? " checked" : ""}${o ? " disabled" : ""}><span class="tcd">${fmtDatumKurz(t.date)}</span><span class="tcn"><b>${esc(t.name)}</b>${reg ? `<small class="mut">${esc(reg)}</small>` : ""}${o ? `<small class="tcin">in eigener Reise „${esc(o)}“</small>` : e ? `<small class="tcin">in Reise „${esc(e)}“</small>` : ""}</span><span class="tck mut">${fmtKm(t.km)}</span></label>`;
  };
  let gmap = new Map();
  const kopf = () => {                                                              // Gruppenköpfe nachziehen (gewählt / teilweise), ohne die Liste neu zu zeichnen (Bildlauf und Fokus bleiben)
    q("#tcl").querySelectorAll(".tcg").forEach(el => {
      const g = gmap.get(el.dataset.k), c = el.querySelector(".cg"), fr = g ? g.l.filter(frei) : [], n = fr.filter(t => sel.has(t.id)).length;
      if (!c) return;
      c.checked = fr.length > 0 && n === fr.length;
      c.indeterminate = n > 0 && n < fr.length;
      el.querySelector(".tcgn").textContent = n && n < fr.length ? ` · ${n} gewählt` : "";
    });
    summe();
  };
  const list = () => {
    const sc = q("#tcl").scrollTop, ts = gefiltert(), gs = gruppen(ts);
    let rest = zeilen, h = "";
    gmap = new Map(gs.map(g => [g.k, g]));
    for (const g of gs) {
      if (rest <= 0) break;
      const l = g.l.slice(0, rest);
      rest -= l.length;
      const fr = g.l.filter(frei), titel = modus === "tag" ? fmtDatum(g.k, {wochentag: true}) : g.k === "~" ? "Ohne Gebiet" : g.k;
      h += `<div class="tcg" data-k="${esc(g.k)}"><label class="tch${fr.length ? "" : " off"}"><input type="checkbox" class="cg" data-g="${esc(g.k)}"${fr.length ? "" : " disabled"} aria-label="${esc(`${titel}: ${modus === "tag" ? "alle dieses Tages" : "alle dieses Gebiets"} wählen`)}"><b>${esc(titel)}</b><small class="mut">${g.l.length === 1 ? "1 Tour" : `${g.l.length} Touren`}<span class="tcgn"></span>${g.geb ? " · " + esc(g.geb) : ""}</small></label>${l.map(zeile).join("")}</div>`;
    }
    q("#tcl").innerHTML = ts.length ? h + (ts.length > zeilen && rest <= 0 ? `<button class="btn ghost sm" id="tcmore" type="button">Weitere Touren anzeigen</button>` : "") : `<p class="mut p8">${q("#tcs").value.trim() ? "Keine Tour passt zur Suche." : "Keine Touren vorhanden."}</p>`;
    q("#tcl").scrollTop = sc;
    kopf();
  };
  list();
  q("#tcl").onchange = e => {
    const c = e.target.closest("[data-i]"), g = e.target.closest("[data-g]");
    if (c) (c.checked ? sel.add(c.dataset.i) : sel.delete(c.dataset.i));
    if (g) {
      const gr = gmap.get(g.dataset.g), fr = gr ? gr.l.filter(frei) : [], on = !fr.every(x => sel.has(x.id));
      fr.forEach(t => (on ? sel.add(t.id) : sel.delete(t.id)));
      q("#tcl").querySelectorAll(".tcg").forEach(el => el.dataset.k === g.dataset.g && el.querySelectorAll(".cb").forEach(b => (b.checked = sel.has(b.dataset.i))));
    }
    kopf();
  };
  q("#tcl").onclick = e => { if (e.target.closest("#tcmore")) { zeilen += TRIP_ZEILEN; list(); } };
  q("#tcz").onclick = () => {
    const a = q("#tcf").value, b = q("#tct").value, er = q("#tcer");
    er.textContent = "";
    if (!a && !b) return void (er.textContent = "Bitte Anfang und Ende des Zeitraums wählen.");
    if (a && b && a > b) return void (er.textContent = "Das Ende liegt vor dem Beginn.");
    const ts = alle().filter(t => frei(t) && (!a || day(t) >= a) && (!b || day(t) <= b));
    ts.forEach(t => sel.add(t.id));
    list();
    q("#tcc").insertAdjacentHTML("beforeend", ` <span class="mut">(${ts.length === 1 ? "1 Tour" : `${ts.length} Touren`} im Zeitraum markiert)</span>`);
  };
  q("#tcs").oninput = () => { zeilen = TRIP_ZEILEN; list(); };
  const gr = mo => { modus = mo; zeilen = TRIP_ZEILEN; [["tcgt", "tag"], ["tcgg", "gebiet"]].forEach(([id, k]) => { q("#" + id).classList.toggle("on", k === mo); q("#" + id).setAttribute("aria-pressed", String(k === mo)); }); list(); };
  q("#tcgt").onclick = () => gr("tag");
  q("#tcgg").onclick = () => gr("gebiet");
  q("#tca").onclick = () => { gefiltert().forEach(t => frei(t) && sel.add(t.id)); list(); };
  q("#tck").onclick = () => { gefiltert().forEach(t => sel.delete(t.id)); list(); };
  q("#tcno").onclick = () => m.remove();
  q("#tcok").onclick = async () => {
    const name = q("#tcn").value.trim(), er = q("#tcer");
    if (!name) return void (er.textContent = "Bitte einen Namen für die Reise eingeben.");
    if (!sel.size) return void (er.textContent = "Bitte mindestens eine Tour wählen.");
    try {
      const i = tripAuswahlInfo([...sel].map(x => BY[x]).filter(Boolean));
      const body = JSON.stringify({name, start: i.von, end: i.bis, tours: [...sel]}), h = {"content-type": "application/json"};
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
