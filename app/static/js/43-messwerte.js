/* =====================  Messwerte der Aufzeichnungsgeräte (Tempo, Kadenz, Leistung, Temperatur …) und „Meine Geräte“  ===================== */
const MET_COL = {speed: "#2f8f5f", pace: "#2f8f5f", cad: "#8a6bb3", stride: "#c9892f", pow: "#c0504d", temp: "#3d7fb8", resp: "#4aa3a0", gct: "#8c7b5a", vosc: "#a35d86", press: "#6b7f8c"},
  MET_CACHE = new Map(),
  METJ = o => ({method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(o)});
const metData = (id, fresh) => {
  if (fresh || !MET_CACHE.has(id)) MET_CACHE.set(id, api("/api/tours/" + encodeURIComponent(id) + "/metrics").catch(() => null));
  return MET_CACHE.get(id);
};
const metPace = v => {
  let m = Math.floor(v), s = Math.round((v - m) * 60);
  if (s === 60) { m++; s = 0; }
  return m + ":" + pad2(s);
};
const metFmt = (k, v, ch) => (v == null ? "–" : k === "pace" ? metPace(v) : nf(v, ch.dec));
function metSel(keys) {
  let s = [];
  try { s = JSON.parse(localStorage.getItem("mt_met_sel") || "[]"); } catch (e) {}
  s = s.filter(k => keys.includes(k));
  return s.length ? s : keys.slice(0, 1);
}
function metSave(s) {
  try { localStorage.setItem("mt_met_sel", JSON.stringify(s)); } catch (e) {}
}
const metDur = m => Math.max(1, ...Object.values(m.channels).map(c => (c.t || m.t)[(c.t || m.t).length - 1] || 0));

/* Liniendiagramm eines Kanals im Stil des Pulsdiagramms; Lücken (kein Messwert) unterbrechen die Linie */
function metChart(k, ch, m, dur) {
  const W = 800, H = 150, L0 = 46, B = 22, T = 8, t = ch.t || m.t, col = MET_COL[k] || "#555";
  const vals = ch.series.filter(v => v != null);
  if (!vals.length) return "";
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.1 || Math.max(1, Math.abs(hi) * 0.1);
  lo -= pad; hi += pad;
  if (lo < 0 && ["speed", "pace", "cad", "stride", "pow", "gct", "vosc", "resp", "press"].includes(k)) lo = 0;
  const x = s => L0 + ((W - L0 - 6) * s) / dur,
    y = v => T + (H - T - B) * (ch.inv ? (v - lo) / (hi - lo) : 1 - (v - lo) / (hi - lo));
  let d = "", pen = false;
  ch.series.forEach((v, i) => {
    if (v == null) return (pen = false);
    d += `${pen ? "L" : "M"}${x(t[i]).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
  });
  let g = "";
  [lo, (lo + hi) / 2, hi].forEach(v => (g += `<line x1="${L0}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)"/><text x="${L0 - 6}" y="${y(v) + 4}" text-anchor="end">${k === "pace" ? metPace(v) : nf(v, ch.dec > 1 ? 1 : ch.dec)}</text>`));
  for (let q = 0; q <= 4; q++) {
    const s = (dur * q) / 4, mi = Math.round(s / 60);
    g += `<text x="${x(s)}" y="${H - 6}" text-anchor="${q === 4 ? "end" : q === 0 ? "start" : "middle"}">${Math.floor(mi / 60)}:${pad2(mi % 60)} h</text>`;
  }
  return `<svg viewBox="0 0 ${W} ${H}" class="w100 ha metsvg" data-k="${k}">${g}<path d="${d}" fill="none" stroke="${col}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/><line class="metcur" y1="${T}" y2="${H - B}" stroke="var(--mut)" stroke-dasharray="3 3" display="none"/></svg>`;
}

function metKpi(k, ch) {
  const u = esc(ch.unit),
    f = v => metFmt(k, v, ch),
    items = [[ch.avg, k === "pace" ? "Ø " + u : "Ø " + u], [k === "pace" ? ch.max : ch.max, k === "pace" ? "schnellster " + u : "max " + u]];
  if (k !== "pace" && ch.min != null && ["temp", "press", "resp"].includes(k)) items.push([ch.min, "min " + u]);
  if (k === "speed" && ch.avg_mov != null) items.splice(1, 0, [ch.avg_mov, "Ø in Bewegung " + u]);
  return items.filter(i => i[0] != null).map(i => `<div><b>${f(i[0])}</b> <span class="mut">${i[1]}</span></div>`).join("");
}

const MET_SUM = [["kcal", "Kalorien", "kcal", 0], ["te", "Trainingseffekt aerob", "", 1], ["ate", "Trainingseffekt anaerob", "", 1]];

async function metCard(t) {
  const old = $("#metcard");
  if (old) old.remove();
  const anchor = $("#pulscard") || $("#profcard");
  if (!anchor || !t) return;
  const m = await metData(t.id);
  if (!m || $("#metcard")) return;
  const keys = Object.keys(m.channels || {}),
    sums = MET_SUM.filter(s => m.sum && m.sum[s[0]] != null);
  if (!keys.length && !sums.length) return;
  const off = m.device && !m.device.active;                       // Gerät deaktiviert: Auswertungen eingeklappt
  let show = !off;
  const d = document.createElement("div");
  d.className = "panel prof gap";
  d.id = "metcard";
  (($("#pulscard") || $("#profcard")).after(d));
  const draw = () => {
    if (!show) {
      d.innerHTML = `<h2>Messwerte</h2><p class="mut">Das Gerät „${esc(m.device.name)}“ ist deaktiviert – die Messwerte sind ausgeblendet.</p><button class="btn alt sm" id="metshow">Trotzdem anzeigen</button>`;
      $("#metshow").onclick = () => { show = true; draw(); };
      return;
    }
    const sel = metSel(keys),
      dur = keys.length ? metDur(m) : 1;
    const chips = keys.map(k => `<button class="chip ${sel.includes(k) ? "on" : ""}" data-k="${k}" title="${esc(m.channels[k].derived ? "aus GPS und Zeit berechnet" : "vom Gerät gemessen")}"><i data-c="${MET_COL[k] || "#555"}"></i>${esc(m.channels[k].label)}${m.channels[k].derived ? " *" : ""}</button>`).join("");
    const charts = sel.map(k => {
      const ch = m.channels[k];
      return `<div class="m12-0-8"><div class="g28 fxw mb8 fx hrkpi"><span class="fw600">${esc(ch.label)}</span>${metKpi(k, ch)}</div>${metChart(k, ch, m, dur)}</div>`;
    }).join("");
    const sm = sums.length ? `<div class="g28 fxw mb8 fx hrkpi">${sums.map(s => `<div><b>${nf(m.sum[s[0]], s[3])}</b> <span class="mut">${s[2] || s[1]}${s[2] ? " " + s[1] : ""}</span></div>`).join("")}</div>` : "";
    const der = keys.some(k => m.channels[k].derived);
    const src = m.device ? esc(m.device.name) + (m.source && m.source !== m.device.name ? ` (${esc(m.source)})` : "") : esc(m.source || "unbekannt");
    d.innerHTML = `<h2>Messwerte</h2>${keys.length ? `<div class="chips mb8" id="metchips">${chips}</div>` : ""}${sm}${charts}<div class="tip" id="mettip" hidden></div>` +
      `<div class="mut mt8 hrnote">Quelle: ${src}${der ? " · * aus GPS-Strecke und Zeit berechnet (kein Messwert des Geräts)" : ""}</div>`;
    d.querySelectorAll("#metchips i[data-c]").forEach(i => (i.style.background = i.dataset.c));
    d.querySelectorAll("#metchips [data-k]").forEach(b => (b.onclick = () => {
      const cur = metSel(keys), k = b.dataset.k;
      metSave(cur.includes(k) ? cur.filter(x => x !== k) : [...cur, k]);
      draw();
    }));
    d.querySelectorAll(".metsvg").forEach(svg => {
      const k = svg.dataset.k, ch = m.channels[k], tt = ch.t || m.t, tip = $("#mettip"), cur = svg.querySelector(".metcur");
      const mv = e => {
        const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal, px = ((e.clientX - r.left) / r.width) * vb.width;
        const s = ((px - 46) / (vb.width - 46 - 6)) * dur;
        let best = -1, bd = 1e9;
        tt.forEach((v, i) => { if (ch.series[i] != null && Math.abs(v - s) < bd) { bd = Math.abs(v - s); best = i; } });
        if (best < 0 || px < 46) { tip.hidden = true; cur.setAttribute("display", "none"); return; }
        const cx = 46 + ((vb.width - 46 - 6) * tt[best]) / dur, mi = Math.round(tt[best] / 60);
        cur.setAttribute("x1", cx); cur.setAttribute("x2", cx); cur.removeAttribute("display");
        const dr = d.getBoundingClientRect();
        tip.textContent = `${Math.floor(mi / 60)}:${pad2(mi % 60)} h · ${metFmt(k, ch.series[best], ch)} ${ch.unit}`;
        tip.hidden = false;
        tip.style.left = Math.min(Math.max(e.clientX - dr.left, 60), dr.width - 60) + "px";
        tip.style.top = e.clientY - dr.top - 4 + "px";
      };
      svg.onpointermove = mv;
      svg.onpointerleave = () => { tip.hidden = true; cur.setAttribute("display", "none"); };
    });
  };
  draw();
}

/* Zeile „Gerät: …“ auf der Tourseite (mit Auswahl, falls die automatische Zuordnung nicht stimmt) */
async function metDevRow(t) {
  const anchor = $("#ewarn");
  if (!t || !anchor) return;
  const draw = async () => {
    const [m, dv] = await Promise.all([metData(t.id, true), api("/api/my-devices").catch(() => ({devices: []}))]);
    if (!m) return;
    let row = $("#devrow");
    if (!m.device && !m.source && !dv.devices.length) return row && row.remove();
    if (!row) {
      anchor.insertAdjacentHTML("beforebegin", `<div id="devrow" class="row mn4-0-12 g8"></div>`);
      row = $("#devrow");
    }
    const name = m.device ? m.device.name : m.source || "unbekannt";
    row.innerHTML = `<span class="mut">Quelle:</span><span class="chip on">${esc(name)}${m.device && !m.device.active ? " (deaktiviert)" : ""}</span>` +
      (typeof isViewer === "function" && isViewer() ? "" : `<button class="btn ghost sm" id="devedit" title="Gerät dieser Tour ändern">✎</button>`);
    const be = $("#devedit");
    if (be) be.onclick = () => {
      const mo = modal(`<h2>Gerät dieser Tour</h2>
        <label class="row g8"><input type="radio" name="dvm" value="" ${m.device && m.device.manual ? "" : "checked"}> automatisch (nach Art der Quelle und Datum)</label>
        ${dv.devices.map(g => `<label class="row g8 m4-0"><input type="radio" name="dvm" value="${g.id}" ${m.device && m.device.manual && m.device.id === g.id ? "checked" : ""}> ${esc(g.name)}${g.active ? "" : " (deaktiviert)"} <span class="mut">${esc(devKindLabel(dv, g.kind))}</span></label>`).join("")}
        ${dv.devices.length ? "" : `<p class="mut">Noch kein Gerät angelegt – in der Verwaltung unter „Meine Geräte“.</p>`}
        <div class="row mt14"><button class="btn" id="dvok">Speichern</button><button class="btn ghost" id="dvno">Abbrechen</button></div><div id="dverr" class="bad"></div>`);
      $("#dvno").onclick = () => mo.remove();
      $("#dvok").onclick = async () => {
        const v = (mo.querySelector("input[name=dvm]:checked") || {}).value;
        try {
          await api(`/api/tours/${encodeURIComponent(t.id)}/device`, METJ(v ? {device_id: +v} : {auto: true}));
          mo.remove();
          MET_CACHE.delete(t.id);
          draw();
          metCard(t);
        } catch (e) {
          $("#dverr").textContent = e.message;
        }
      };
    };
  };
  draw().catch(() => {});
}
const devKindLabel = (dv, k) => ((dv.kinds || []).find(x => x.kind === k) || {label: k}).label;

const _tour43 = VIEWS.tour;
VIEWS.tour = async (...a) => {
  await _tour43(...a);
  const t = BY[a[0]];
  if (!t) return;
  MET_CACHE.delete(t.id);
  metDevRow(t);
  const tryCard = (n = 0) => {
    if ($("#profcard")) metCard(t).catch(() => {});
    else if (n < 20) setTimeout(() => tryCard(n + 1), 150);
  };
  tryCard();
};

/* ---------- Verwaltung: Meine Geräte ---------- */
function devForm(dv, g, done) {
  g = g || {kind: "zepp", active: true};
  const m = modal(`<h2>${g.id ? "Gerät bearbeiten" : "Neues Gerät"}</h2>
   <label>Name<input id="dvn" maxlength="80" value="${esc(g.name || "")}" placeholder="z. B. Amazfit Balance 2, Garmin Fenix – alt"></label>
   <label>Art<select id="dvk">${dv.kinds.map(k => `<option value="${k.kind}" ${k.kind === g.kind ? "selected" : ""}>${esc(k.label)}</option>`).join("")}</select></label>
   <label>Modell (optional)<input id="dvm" maxlength="80" value="${esc(g.model || "")}"></label>
   <div class="row mt10"><label>Im Gebrauch ab<input type="date" id="dvs" value="${esc(g.since || "")}"></label><label>bis (leer = noch im Gebrauch)<input type="date" id="dvu" value="${esc(g.until || "")}"></label></div>
   <p class="mut fs13">Mit mehreren Geräten gleicher Art entscheidet das Tourdatum, zu welchem Gerät eine Tour gehört.</p>
   <label class="chk"><input type="checkbox" id="dva" ${g.active ? "checked" : ""}> aktiv (deaktivierte Geräte behalten ihre Touren, ihre Messwerte werden aber eingeklappt)</label>
   <label>Notiz<input id="dvt" maxlength="300" value="${esc(g.note || "")}"></label>
   <div class="row mt14"><button class="btn" id="dvsave">Speichern</button><button class="btn ghost" id="dvcancel">Abbrechen</button><span class="sp"></span>${g.id ? `<button class="btn ghost" id="dvrange">Touren zuordnen …</button><button class="btn ghost" id="dvdel">Löschen</button>` : ""}</div><div id="dverr" class="bad"></div>`);
  $("#dvcancel").onclick = () => m.remove();
  $("#dvsave").onclick = async () => {
    const body = {name: $("#dvn").value, kind: $("#dvk").value, model: $("#dvm").value, since: $("#dvs").value, until: $("#dvu").value, active: $("#dva").checked, note: $("#dvt").value};
    try {
      if (g.id) await api("/api/devices/" + g.id, {method: "PATCH", headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
      else await api("/api/devices", METJ(body));
      MET_CACHE.clear();
      m.remove();
      done();
    } catch (e) {
      $("#dverr").textContent = e.message;
    }
  };
  if (!g.id) return;
  $("#dvrange").onclick = () => {
    m.remove();
    const r = modal(`<h2>Touren „${esc(g.name)}“ zuordnen</h2><p class="mut">Alle Touren im Zeitraum werden fest diesem Gerät zugeordnet (jederzeit je Tour änderbar).</p>
      <div class="row"><label>von<input type="date" id="rf"></label><label>bis<input type="date" id="rt"></label></div>
      <div class="row mt14"><button class="btn" id="rok">Zuordnen</button><button class="btn ghost" id="rno">Abbrechen</button></div><div id="rerr" class="bad"></div>`);
    $("#rno").onclick = () => r.remove();
    $("#rok").onclick = async () => {
      try {
        const res = await api("/api/devices/assign-range", METJ({device_id: g.id, from: $("#rf").value, to: $("#rt").value}));
        r.remove();
        MET_CACHE.clear();
        alert(`${res.n} Touren zugeordnet.`);
        done();
      } catch (e) {
        $("#rerr").textContent = e.message;
      }
    };
  };
  $("#dvdel").onclick = async () => {
    if (!confirm(`„${g.name}“ entfernen?`)) return;
    try {
      await api("/api/devices/" + g.id, {method: "DELETE"});
      m.remove();
      done();
    } catch (e) {
      const others = dv.devices.filter(x => x.id !== g.id);
      if (!/umhängen/.test(e.message)) return ($("#dverr").textContent = e.message);
      if (!others.length) return ($("#dverr").textContent = e.message + " Lege dafür zuerst ein anderes Gerät an.");
      m.remove();
      const mv = modal(`<h2>Touren umhängen</h2><p>${esc(e.message)}</p><label>Auf dieses Gerät umhängen<select id="mvto">${others.map(x => `<option value="${x.id}">${esc(x.name)}</option>`).join("")}</select></label>
        <div class="row mt14"><button class="btn" id="mvok">Umhängen und löschen</button><button class="btn ghost" id="mvno">Abbrechen</button></div><div id="mverr" class="bad"></div>`);
      $("#mvno").onclick = () => mv.remove();
      $("#mvok").onclick = async () => {
        try {
          await api(`/api/devices/${g.id}?move_to=${$("#mvto").value}`, {method: "DELETE"});
          mv.remove();
          MET_CACHE.clear();
          done();
        } catch (e2) {
          $("#mverr").textContent = e2.message;
        }
      };
    }
  };
}

async function devPanel() {
  const root = $("#devsec");
  if (!root) return;
  const [dv, sug] = await Promise.all([api("/api/my-devices"), api("/api/devices/suggestions").catch(() => [])]);
  const hidden = k => { try { return localStorage.getItem("mt_devsug_" + k) === "1"; } catch (e) { return false; } };
  const sugs = sug.filter(s => !hidden(s.kind));
  root.innerHTML = `<h2>Meine Geräte</h2><p class="mut">Lege deine Aufnahmegeräte an und benenne sie selbst – der Name erscheint bei jeder Tour („Quelle“). Welche Messwerte eine Tour zeigt, richtet sich nach dem, was das Gerät wirklich geliefert hat.</p>
    ${sugs.map(s => `<div class="panel mb12" data-sug="${esc(s.kind)}"><b>${esc(s.label)}-Touren gefunden (${s.n})</b><div class="mut">Möchtest du dafür ein Gerät anlegen? Es wird nichts ohne deine Bestätigung angelegt.</div>
      <div class="row mt8"><button class="btn sm" data-sy="${esc(s.kind)}" data-nm="${esc(s.name)}">Gerät „${esc(s.name)}“ anlegen …</button><button class="btn ghost sm" data-sn="${esc(s.kind)}">Nicht jetzt</button></div></div>`).join("")}
    ${dv.devices.length
      ? `<div class="rows">${dv.devices.map(g => `<div class="r cp${g.active ? "" : " mut"}" data-dv="${g.id}"><span>${esc(g.name)}${g.active ? "" : " (deaktiviert)"}<small>${esc(devKindLabel(dv, g.kind))}${g.model ? " · " + esc(g.model) : ""}${g.since ? " · ab " + esc(g.since) : ""}${g.until ? " · bis " + esc(g.until) : ""}${g.note ? " · " + esc(g.note) : ""}</small></span><span class="tar"><b>${g.n}</b><small>Touren</small></span></div>`).join("")}</div>`
      : `<p class="mut">Noch kein Gerät angelegt.</p>`}
    <div class="row mt10"><button class="btn sm alt" id="dvnew">+ Neues Gerät</button></div>`;
  $("#dvnew").onclick = () => devForm(dv, null, devPanel);
  root.querySelectorAll("[data-dv]").forEach(r => (r.onclick = () => devForm(dv, dv.devices.find(g => g.id === +r.dataset.dv), devPanel)));
  root.querySelectorAll("[data-sy]").forEach(b => (b.onclick = () => devForm(dv, {kind: b.dataset.sy, name: b.dataset.nm, active: true}, devPanel)));
  root.querySelectorAll("[data-sn]").forEach(b => (b.onclick = () => {
    try { localStorage.setItem("mt_devsug_" + b.dataset.sn, "1"); } catch (e) {}
    devPanel();
  }));
}
const _adm43 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm43(...a);
  const host = document.querySelector('.atab[data-t="quellen"] .gbody') || $("#main");
  if (!host || $("#devsec")) return;
  host.insertAdjacentHTML("afterbegin", `<div class="panel acard" id="devsec"></div>`);
  devPanel().catch(() => {});
};
