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
     <p class="mut" style="font-size:14px">Name und Zeitraum der automatisch erkannten Reise. Ein anderer Zeitraum nimmt alle Touren dieser Tage auf (auch solche, die nicht weit von zu Hause waren) bzw. lässt Touren außerhalb weg.</p>
     <div class="field"><label>Name</label><input id="tn" maxlength="120" value="${esc(tr.region)}" style="width:100%"></div>
     <div class="row" style="gap:8px;align-items:center;margin-top:8px"><label>Von <input id="tf" type="date" value="${tr.start}"></label><label>bis <input id="tt" type="date" value="${tr.end}"></label></div>
     <div class="row" style="margin-top:12px"><button class="btn" id="tok">Speichern</button>${tr.edited ? `<button class="btn alt" id="trs" title="Zurück zu Name und Zeitraum, wie sie erkannt wurden">Zurücksetzen</button>` : ""}<button class="btn ghost" id="tno">Abbrechen</button><span id="ter" class="bad"></span></div>`);
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
      a.map(t => `<tr><td>${timeS(t.date)}</td><td style="text-align:left">${esc(t.name)}</td><td>${sName(t.sport)}</td><td>${nf(t.km, 1)}</td><td>${nf(t.up_m || 0, 0)}</td><td>${nf(t.down_m || 0, 0)}</td></tr>`).join("");
  }).join("");
  $("#main").innerHTML = `<div class="sheet">
   <div class="row noprint"><a class="back" href="#/trip/${esc(id)}">‹ Zurück zur Reise</a><span class="sp"></span>${pdfPhotoBar()}<button class="btn" id="shp">🖨 Drucken / als PDF speichern</button></div>
   <div class="mut" style="margin-top:14px">${dateL(tr.start)}${tr.end !== tr.start ? " – " + dateL(tr.end) : ""}</div>
   <h1 style="font-size:34px;margin:8px 0 14px">${esc(tr.region)}${tr.country && tr.country !== tr.region ? ", " + esc(tr.country) : ""}</h1>
   <div class="figs">${fig(ts.length, "", "Touren")}${fig(nf(sum(t => t.km), 1), "km", "Strecke")}${fig(nf(sum(t => t.up_m), 0), "m", "Aufstieg")}${fig(nf(sum(t => t.down_m), 0), "m", "Abstieg")}${fig(nf(sum(t => t.h), 1), "h", "Unterwegs")}${fig(days.length, "", "Tage")}</div>
   <div class="tmap" id="tm" style="height:380px;margin-top:14px"></div>
   <div id="tleg" class="mut" style="font-size:13px;margin:6px 0 0"></div>
   ${collStats(ts)}
   <div class="sec"><h2>Tag für Tag</h2></div><div class="tblw"><table class="cstat"><thead><tr><th>Zeit</th><th style="text-align:left">Tour</th><th>Aktivität</th><th>km</th><th>↑ m</th><th>↓ m</th></tr></thead><tbody>${perDay}</tbody></table></div>
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
  $("#tleg").innerHTML = days.map((d, i) => `<span style="margin-right:12px;white-space:nowrap"><i style="display:inline-block;width:14px;height:4px;background:${DAYC[i % DAYC.length]};vertical-align:middle;margin-right:4px"></i>${dateS(d)}</span>`).join("");
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
  await photos();
};
const _trip28b = VIEWS.trip;
VIEWS.trip = async id => {
  await _trip28b(id);
  const b = $("#tredit");
  if (b && !$("#trpdf")) b.insertAdjacentHTML("beforebegin", `<a class="btn alt sm" id="trpdf" href="#/tripsheet/${encodeURIComponent(id)}" title="Druckbarer Reisebericht mit Karte, Statistik und Fotos – als PDF speicherbar">📄 Reisebericht (PDF)</a> `);
};
