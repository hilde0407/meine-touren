/* =====================  Wegpunkte (unterwegs in der App gesetzt) und Erzählung zur Tour  ===================== */
const wpTime = ts => new Date(ts * 1000).toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"});
const wpIcon = (n, cls = "") => L.divIcon({className: "", html: `<div style="background:#d9534f;color:#fff;border:2px solid #fff;border-radius:50%;width:26px;height:26px;line-height:22px;text-align:center;font:700 13px system-ui;box-shadow:0 1px 4px #0006" class="${cls}">${n}</div>`, iconSize: [26, 26], iconAnchor: [13, 13]});

const _tourW = VIEWS.tour;
VIEWS.tour = async id => {
  await _tourW(id);
  const t = BY[id];
  if (!t || !$("#tm") || !$("#main")) return;
  const ren = $("#ren");
  if (ren && !$("#storybtn")) ren.insertAdjacentHTML("afterend", ` <a class="btn ghost sm" id="storybtn" href="#/story/${esc(id)}" title="Wegpunkte, Fotos und Eckdaten als Zeitleiste" style="vertical-align:middle;font-size:15px">📖 Erzählung</a>`);
  let w = [];
  try { w = await api(`/api/tours/${id}/wps`); } catch (e) { return; }
  if (!w.length || !$("#profcard")) return;
  w.forEach((p, i) => L.marker([p.lat, p.lng], {icon: wpIcon(i + 1)}).addTo(map).bindPopup(`<b>${esc(p.note || "Wegpunkt")}</b><br>${wpTime(p.ts)} Uhr`));
  const rows = () => w.map((p, i) => `<div class="row" style="gap:8px;margin:6px 0;align-items:center" data-w="${p.id}"><span class="tag" style="background:#d9534f">${i + 1}</span><span class="mut">${wpTime(p.ts)}</span><span style="flex:1" class="wpn">${esc(p.note || "Wegpunkt")}</span><button class="btn ghost sm" data-wed="${p.id}" title="Notiz ändern">✎</button><button class="btn ghost sm" data-wdel="${p.id}" title="Wegpunkt löschen">✕</button></div>`).join("");
  $("#profcard").insertAdjacentHTML("afterend", `<div class="panel" id="wpcard" style="margin-top:20px"><h2>Wegpunkte</h2><div id="wplist">${rows()}</div></div>`);
  $("#wpcard").onclick = async e => {
    const ed = e.target.closest("[data-wed]"), dl = e.target.closest("[data-wdel]");
    if (ed) {
      const p = w.find(x => x.id == ed.dataset.wed), row = ed.closest("[data-w]");
      row.querySelector(".wpn").innerHTML = `<input value="${esc(p.note)}" maxlength="200" style="width:100%;padding:6px">`;
      const inp = row.querySelector("input");
      inp.focus();
      inp.onkeydown = async k => {
        if (k.key !== "Enter") return;
        await api(`/api/tours/${id}/wps/${p.id}`, {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({note: inp.value})});
        route();
      };
    } else if (dl) {
      if (!confirm("Wegpunkt löschen?")) return;
      await api(`/api/tours/${id}/wps/${dl.dataset.wdel}`, {method: "DELETE"});
      route();
    }
  };
};

/* ---- Erzählung: Zeitleiste aus Start, Wegpunkten, Fotos und Ziel ---- */
VIEWS.story = async id => {
  const t = BY[id];
  if (!t) throw new Error("Tour nicht gefunden");
  $("#main").innerHTML = `<div class="row"><a class="back" href="#/tour/${esc(id)}">‹ Zur Tour</a></div><p class="mut">Wird geladen …</p>`;
  const [wps, ph, co] = await Promise.all([api(`/api/tours/${id}/wps`).catch(() => []), api(`/api/photos?tour_id=${id}&limit=400`).catch(() => []), api(`/api/tours/${id}/coords`).catch(() => [])]);
  const t0 = t.start_ts || 0, T = Math.max(1, Math.round((t.h || 0) * 3600));
  const ev = [{ts: t0, kind: "start", txt: "Start", pos: co.length ? [co[0][0], co[0][1]] : null}];
  wps.forEach(p => ev.push({ts: p.ts || t0, kind: "wp", txt: p.note || "Wegpunkt", pos: [p.lat, p.lng]}));
  let grp = null;
  ph.slice().sort((a, b) => a.taken_ts - b.taken_ts).forEach(p => {
    if (grp && p.taken_ts - grp.last < 600) { grp.ph.push(p); grp.last = p.taken_ts; return; }
    grp = {ts: p.taken_ts, last: p.taken_ts, kind: "ph", ph: [p], pos: p.lat != null ? [p.lat, p.lng] : null};
    ev.push(grp);
  });
  ev.push({ts: t0 + T, kind: "end", txt: "Ziel", pos: co.length ? [co[co.length - 1][0], co[co.length - 1][1]] : null});
  ev.sort((a, b) => a.ts - b.ts);
  const rel = ts => { const m = Math.max(0, Math.round((ts - t0) / 60)); return `+${Math.floor(m / 60)}:${pad2(m % 60)} h`; };
  const icon = k => ({start: "🏁", end: "🎯", wp: "📍", ph: "📷"})[k];
  const item = (e, i) => `<div class="stev" data-e="${i}" style="display:flex;gap:12px;margin:0 0 18px;cursor:${e.pos ? "pointer" : "default"}"><div style="min-width:78px;text-align:right"><b>${wpTime(e.ts)}</b><div class="mut" style="font-size:12px">${rel(e.ts)}</div></div><div style="flex:1;border-left:3px solid var(--line,#ccc);padding-left:14px"><div style="font-size:18px">${icon(e.kind)} ${e.kind === "ph" ? `${e.ph.length} Foto${e.ph.length > 1 ? "s" : ""}` : esc(e.txt)}</div>` +
    (e.kind === "ph" ? `<div class="row" style="gap:6px;flex-wrap:wrap;margin-top:6px">${e.ph.slice(0, 8).map(p => `<img loading="lazy" src="/pic/${p.id}?size=500" style="height:120px;border-radius:8px">`).join("")}${e.ph.length > 8 ? `<span class="mut">+${e.ph.length - 8}</span>` : ""}</div>` : "") + `</div></div>`;
  $("#main").innerHTML = `<div class="row"><a class="back" href="#/tour/${esc(id)}">‹ Zur Tour</a></div>
   <h1 style="font-size:clamp(30px,5vw,48px);margin:14px 0 4px">${esc(t.name)}</h1><p class="mut">${dateL(t.date)} · ${nf(t.km, 1)} km · ↑ ${nf(t.up_m, 0)} m · ${Math.floor(t.h)}:${pad2(Math.round((t.h % 1) * 60))} h${t.h ? ` · ${nf(t.km / t.h, 1)} km/h` : ""}</p>
   <div class="tmap" id="sm" style="height:320px"></div><div style="margin-top:22px" id="stl">${ev.map(item).join("")}</div>`;
  map = mkMap("sm", {layers: true});
  if (co.length > 1) {
    const ln = L.polyline(co.map(c => [c[0], c[1]]), {color: "#d9534f", weight: 4}).addTo(map);
    map.fitBounds(ln.getBounds(), {padding: [20, 20]});
  } else map.setView([t.lat || 50, t.lng || 8], 12);
  ev.forEach((e, i) => { if (e.pos && e.kind !== "ph") L.marker(e.pos, {icon: wpIcon(icon(e.kind))}).addTo(map).bindPopup(esc(e.txt)); });
  $("#stl").onclick = e => {
    const el = e.target.closest(".stev");
    if (!el) return;
    const p = ev[+el.dataset.e];
    if (p && p.pos) { map.setView(p.pos, 16); $("#sm").scrollIntoView({behavior: "smooth", block: "center"}); }
  };
};
