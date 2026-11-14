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
      `<div class="mut mt8 hrnote"><span class="dvsrc">${m.device ? dvAvatar(m.device, "xs") : ""}<span>Quelle:</span> <span>${src}</span></span>${der ? " · * aus GPS-Strecke und Zeit berechnet (kein Messwert des Geräts)" : ""}</div>`;
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

/* ---------- Symbole und Bilder der Geräte (ohne Markenlogos, einfarbig) ---------- */
const DV_STRAP = `<path d="M18 13V6.5A1.5 1.5 0 0 1 19.5 5h9A1.5 1.5 0 0 1 30 6.5V13M18 35v6.5a1.5 1.5 0 0 0 1.5 1.5h9a1.5 1.5 0 0 0 1.5-1.5V35"/>`,
  DV_ICON = {
    zepp: `${DV_STRAP}<rect x="13" y="13" width="22" height="22" rx="7"/><path d="M35 22h2.5v4H35M24 19v5.5l3.5 2"/>`,
    garmin: `${DV_STRAP}<circle cx="24" cy="24" r="11"/><path d="M24 16v2M24 30v2M16 24h2M30 24h2M24 24l3 2"/>`,
    suunto: `${DV_STRAP}<circle cx="24" cy="24" r="11"/><path d="M24 17.5l3 6.5-3 6.5-3-6.5z"/>`,
    polar: `${DV_STRAP}<rect x="13" y="13" width="22" height="22" rx="4"/><path d="M17 25h4l2-5 3 9 2-4h3"/>`,
    phone: `<rect x="14" y="5" width="20" height="38" rx="4.5"/><path d="M21 9.5h6"/><circle cx="24" cy="37.5" r="1.3"/>`,
    other: `<path d="M24 6a10 10 0 0 1 10 10c0 7.5-10 18-10 18S14 23.5 14 16A10 10 0 0 1 24 6z"/><circle cx="24" cy="16" r="3.5"/><path d="M15 41h18"/>`,
  };
const dvIcon = k => `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${DV_ICON[k] || DV_ICON.other}</svg>`;
const dvAvatar = (g, cls) => `<span class="dvav ${cls || ""}">${g.photo ? `<img src="/api/my-devices/${g.id}/photo?v=${g.photo}" alt="" loading="lazy">` : dvIcon(g.kind)}</span>`;
const dvMonth = d => (d && /^\d{4}-\d\d/.test(d) ? d.slice(5, 7) + "/" + d.slice(0, 4) : "");

/* Zeile „Quelle: …“ auf der Tourseite (mit Auswahl, falls die automatische Zuordnung nicht stimmt) */
async function metDevRow(t) {
  const anchor = $("#ewarn");
  if (!t || !anchor) return;
  const draw = async () => {
    const [m, dv] = await Promise.all([metData(t.id, true), api("/api/my-devices").catch(() => ({devices: []}))]);
    if (!m) return;
    let row = $("#devrow");
    if (!m.device && !m.source && !dv.devices.length) return row && row.remove();
    if (!row) {
      anchor.insertAdjacentHTML("beforebegin", `<div id="devrow" class="dvrow"></div>`);
      row = $("#devrow");
    }
    const g = m.device,
      name = g ? g.name : m.source || "unbekannt",
      sub = g ? [g.model, !g.active ? "deaktiviert" : "", g.manual ? "von Hand zugeordnet" : ""].filter(Boolean) : [];
    row.innerHTML = (g ? dvAvatar(g, "xs") : `<span class="dvav xs">${dvIcon("other")}</span>`) +
      `<span class="dvt"><small>Aufgezeichnet mit</small><b>${esc(name)}</b>${sub.length ? `<small>${sub.map(x => `<span>${esc(x)}</span>`).join(" · ")}</small>` : ""}</span>` +
      (typeof isViewer === "function" && isViewer() ? "" : `<button class="dvedit" id="devedit" title="Gerät dieser Tour ändern"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg><span>Ändern</span></button>`);
    const be = $("#devedit");
    if (be) be.onclick = () => {
      const cur = m.device && m.device.manual ? m.device.id : 0;
      const pick = (val, av, title, small, on) => `<label class="dvpickrow"><input type="radio" name="dvm" value="${val}" ${on ? "checked" : ""}>${av}<span><b>${title}</b><small>${small}</small></span></label>`;
      const mo = modal(`<h2>Gerät dieser Tour</h2><p class="dvlead">Welches Gerät hat diese Tour aufgezeichnet?</p>
        ${pick("", `<span class="dvav xs">${dvIcon("other")}</span>`, "Automatisch", "nach Art der Quelle und Datum", !cur)}
        ${dv.devices.map(x => pick(x.id, dvAvatar(x, "xs"), esc(x.name) + (x.active ? "" : " (deaktiviert)"), esc([devKindLabel(dv, x.kind), x.model].filter(Boolean).join(" · ")), cur === x.id)).join("")}
        ${dv.devices.length ? "" : `<p class="mut">Noch kein Gerät angelegt – in der Verwaltung unter „Meine Geräte“.</p>`}
        <div class="dvfoot"><button class="btn" id="dvok">Speichern</button><button class="btn ghost" id="dvno">Abbrechen</button></div><div id="dverr" class="bad"></div>`);
      mo.querySelector(".mbox").classList.add("dvbox");
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
