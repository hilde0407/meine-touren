/* =====================  3.19.0 Konfigurierbare Bausteine: gemeinsamer Filter (Sportart, Zeitraum)  =====================
   Eigenständig und wiederverwendbar (3.22.0: auch der globale Filter der Statistikseite, 56-statistik.js, rechnet mit flRange/flSelect). Nichts hier kennt einen bestimmten Baustein.
   Konfiguration (cfg, gespeichert im Layout-Dokument, geprüft in app/layout.py):
     sports   [Sportart]   leer oder fehlend = alle Sportarten
     range    year | y | 12m | 90d | all     (y braucht yr = Jahr)      yr    Jahreszahl
     compare  false = ohne Vorjahresvergleich (Standard: an)             title  eigener Titel
     eigen    true = der Baustein behält seinen eigenen Filter (nur auf der Statistikseite; sonst gilt dort der globale Filter)
   3.22.0: range "c" = frei von–bis (cfg.from, cfg.to als JJJJ-MM-TT); nur im globalen Filter der Statistikseite (Adresse), nicht im Einstellungs-Dialog und nicht im Layout.
   Rechnen (ohne Seiteneffekte, gleiche Regeln wie GET /api/bausteine/jahr in app/bausteine_daten.py):
     flRange(cfg, def, o)    -> {kind, from, to, prev: {from, to}|null, year, label}   def = Zeitraum, wenn cfg.range fehlt; o.fallback: ohne Touren im laufenden Jahr das letzte Jahr mit Touren
     flSelect(cfg, def, o)   -> {R, base (nur nach Sportart gefiltert), list (im Zeitraum), prev (im Vorzeitraum oder null)}
     flParts / flKurz / flPlain  Kurztext der aktiven Filterung ("Wandern, 2025"), leer ohne Abweichung vom Standard des Bausteins
   Dialog (vom Einstellungs-Dialog in 49-seitenlayout.js genutzt): Feldarten sports, range, compare, title mit flField / flRead / flBind.
   Kopfzeile: flHead(card, Typ, cfg) setzt den Kurztext (auch zugeklappt sichtbar) hinter den Titel. */
const FL_KINDS = new Set(["sports", "range", "compare", "title", "global"]);
const FL_RANGE_ALL = ["year", "y", "12m", "90d", "all"];
const FL_RLAB = {year: "Laufendes Jahr", "12m": "Letzte 12 Monate", "90d": "Letzte 90 Tage", all: "Gesamte Zeit"};
const FL_MET = {
  count: {name: "Touren", unit: "Touren", f: () => 1, fmt: v => nf(v, 0)},
  km: {name: "Strecke", unit: "km", f: t => t.km, fmt: v => fmtKm(v, {summe: true})},
  up: {name: "Aufstieg", unit: "m", f: t => t.up_m || 0, fmt: v => fmtHm(v)},
  h: {name: "Zeit unterwegs", unit: "Std.", f: t => t.h, fmt: v => fmtDauer(v * 3600, {summe: true})},
};
const flVal = (list, m) => list.reduce((x, t) => x + FL_MET[m].f(t), 0);
const flDayAdd = (iso, n) => new Date(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10) + n)).toISOString().slice(0, 10);
const flYearBack = (iso, n = 1) => {
  const y = +iso.slice(0, 4) - n, m = +iso.slice(5, 7);
  return `${y}-${pad2(m)}-${pad2(Math.min(+iso.slice(8, 10), new Date(Date.UTC(y, m, 0)).getUTCDate()))}`;
};
const flSport = (t, cfg) => !(cfg && cfg.sports && cfg.sports.length) || cfg.sports.includes(t.sport);
const flIn = (t, r) => {
  const d = t.date.slice(0, 10);
  return (!r.from || d >= r.from) && d <= r.to;
};

function flRange(cfg, def = "year", o = {}) {
  cfg = cfg || {};
  const now = o.now || new Date(), cy = now.getFullYear(), today = slIso(now);
  const kind = FL_RANGE_ALL.includes(cfg.range) || (cfg.range === "c" && cfg.from && cfg.to) ? cfg.range : def;
  let yr = +cfg.yr;
  if (!(yr >= 1970 && yr <= 2100)) yr = cy;
  if (kind === "year" && o.fallback && TOURS.length && !TOURS.some(t => t.y === cy)) {
    const ly = Math.max(...TOURS.map(t => t.y));
    return {kind: "y", from: `${ly}-01-01`, to: `${ly}-12-31`, prev: null, year: ly, label: String(ly)};
  }
  if (kind === "c") return {kind, from: cfg.from, to: cfg.to, prev: null, year: null, label: `${fmtDatumKurz(cfg.from)} – ${fmtDatumKurz(cfg.to)}`};
  if (kind === "y") return {kind, from: `${yr}-01-01`, to: `${yr}-12-31`, prev: {from: `${yr - 1}-01-01`, to: `${yr - 1}-12-31`}, year: yr, label: String(yr)};
  if (kind === "12m") {
    const m = cy * 12 + now.getMonth() - 11, from = `${Math.floor(m / 12)}-${pad2((m % 12) + 1)}-01`;           // der laufende und die 11 Kalendermonate davor
    return {kind, from, to: today, prev: {from: flYearBack(from), to: flDayAdd(from, -1)}, year: null, label: FL_RLAB[kind]};
  }
  if (kind === "90d") {
    const from = flDayAdd(today, -89);
    return {kind, from, to: today, prev: {from: flDayAdd(from, -90), to: flDayAdd(from, -1)}, year: null, label: FL_RLAB[kind]};
  }
  if (kind === "all") return {kind, from: null, to: today, prev: null, year: null, label: FL_RLAB[kind]};
  return {kind: "year", from: `${cy}-01-01`, to: today, prev: {from: `${cy - 1}-01-01`, to: flYearBack(today)}, year: cy, label: String(cy)};
}
function flSelect(cfg, def, o = {}) {
  const R = flRange(cfg, def, o), base = TOURS.filter(t => flSport(t, cfg));
  return {R, base, list: base.filter(t => flIn(t, R)), prev: R.prev ? base.filter(t => flIn(t, R.prev)) : null};
}
/* Sportarten des Nutzers, häufigste zuerst; schon gewählte, aber nicht mehr vorhandene bleiben wählbar */
function flSportOptions(sel = []) {
  const n = {};
  TOURS.forEach(t => t.sport && (n[t.sport] = (n[t.sport] || 0) + 1));
  const keys = Object.keys(n).sort((a, b) => n[b] - n[a] || sName(a).localeCompare(sName(b)));
  sel.forEach(s => !keys.includes(s) && keys.push(s));
  return keys.map(k => [k, sName(k)]);
}
const flYears = () => {
  const ys = new Set(TOURS.map(t => t.y));
  return [...ys].sort((a, b) => b - a);
};

/* ---------- Kurztext ---------- */
function flParts(cfg, rangeDef, o = {}) {
  cfg = cfg || {};
  const s = cfg.sports || [], out = [];
  if (s.length) {
    if (s.length <= 2) s.forEach(x => out.push(sName(x)));
    else out.push(`${s.length} Sportarten`);
  }
  if (rangeDef && !o.noRange && !cfg._nr && (s.length || (cfg.range && cfg.range !== rangeDef))) out.push(flRange(cfg, rangeDef).label);
  return out;
}
const flKurz = (cfg, rangeDef, o) => flParts(cfg, rangeDef, o).map(p => `<span>${esc(p)}</span>`).join(", ");
const flPlain = (cfg, rangeDef, o) => flParts(cfg, rangeDef, o).join(", ");
/* Kopfzeile einer Karte: Kurztext hinter dem Titel (T.filter = {range: Standard-Zeitraum oder null}, T.kurz(cfg) = eigene Teile) */
function flHead(c, T, cfg) {
  const sm = c.querySelector("summary"), t = sm && sm.querySelector(".tlt");
  if (!t) return;
  const old = sm.querySelector(".flk");
  if (old) old.remove();
  const parts = T.kurz ? T.kurz(cfg) : T.filter ? flParts(cfg, T.filter.range) : [];
  if (!parts.length) return;
  const e = document.createElement("span");
  e.className = "flk";
  e.innerHTML = parts.map(p => `<span>${esc(p)}</span>`).join(", ");
  t.after(e);
}
const flNone = (b, what) => slNote(b, what || "Keine Touren mit diesem Filter.");

/* ---------- Felder im Einstellungs-Dialog ---------- */
function flField(f, cfg, i) {
  const id = "slf" + i;
  if (f.kind === "sports") {
    const sel = cfg.sports || [];
    return `<fieldset class="slfs flsp"><legend>${esc(f.label || "Sportart")}</legend><div class="flchips">` +
      `<label class="flchip"><input type="checkbox" data-all${sel.length ? "" : " checked"}><span>Alle</span></label>` +
      flSportOptions(sel).map(([v, l]) => `<label class="flchip"><input type="checkbox" name="f${i}" value="${esc(v)}"${sel.includes(v) ? " checked" : ""}><span>${esc(l)}</span></label>`).join("") +
      `</div></fieldset>`;
  }
  if (f.kind === "range") {
    const opts = f.opts || FL_RANGE_ALL, def = f.def || "year", kind = FL_RANGE_ALL.includes(cfg.range) ? cfg.range : def,
      cur = kind === "y" ? "y" + (+cfg.yr || new Date().getFullYear()) : kind,
      ys = flYears();
    if (kind === "y" && !ys.includes(+cur.slice(1))) ys.push(+cur.slice(1));
    const o1 = opts.filter(k => k !== "y").map(k => `<option value="${k}"${cur === k ? " selected" : ""}>${esc(FL_RLAB[k])}</option>`).join(""),
      o2 = opts.includes("y") ? `<optgroup label="Bestimmtes Jahr">${ys.sort((a, b) => b - a).map(y => `<option value="y${y}"${cur === "y" + y ? " selected" : ""}>${y}</option>`).join("")}</optgroup>` : "";
    return `<div class="slfs"><label for="${id}">${esc(f.label || "Zeitraum")}</label><select id="${id}" name="f${i}" class="flsel">${o1}${o2}</select></div>`;
  }
  if (f.kind === "global")
    return `<div class="slfs"><label class="slck"><input type="checkbox" name="f${i}" data-global${f.zr ? " data-zr" : ""}${cfg.eigen === true ? "" : " checked"}><span>${esc(f.label || "Globalen Filter verwenden")}</span></label>` +
      (f.zr ? '<p class="mut slgh">Ist oben auf der Seite ein Zeitraum gewählt, gilt er hier. Ohne Haken behält dieser Baustein seinen eigenen Zeitraum.</p><p class="mut slgh zrnow" data-zrnow role="status"></p></div>' : '<p class="mut slgh">Gilt der Filter oben auf der Seite, sind Sportart und Zeitraum hier nicht einstellbar.</p></div>');
  if (f.kind === "compare")
    return `<div class="slfs"><label class="slck"><input type="checkbox" name="f${i}"${cfg.compare === false ? "" : " checked"}><span>${esc(f.label || "Mit dem Vorjahr vergleichen")}</span></label></div>`;
  return `<div class="slfs"><label for="${id}">${esc(f.label || "Eigener Titel (optional)")}</label><input id="${id}" name="f${i}" type="text" maxlength="60" autocomplete="off" value="${esc(cfg.title || "")}" placeholder="${esc(f.ph || "")}"></div>`;
}
/* Wert des Feldes aus dem Formular in out schreiben; Standardwerte werden nicht gespeichert (das Layout bleibt klein, „Standard“ bleibt Standard) */
function flRead(f, form, i, out) {
  if (f.kind === "sports") {
    const v = [...form.querySelectorAll(`input[name="f${i}"]:checked`)].map(x => x.value);
    if (v.length) out.sports = v;
    else delete out.sports;
  } else if (f.kind === "range") {
    const v = form.querySelector(`[name="f${i}"]`).value, def = f.def || "year";
    delete out.range;
    delete out.yr;
    if (/^y\d{4}$/.test(v)) {
      out.range = "y";
      out.yr = +v.slice(1);
    } else if (v !== def) out.range = v;
    delete out.year;                                                          // ältere Einstellung „Dieses/Letztes Jahr“ des Jahres-Rückblicks
  } else if (f.kind === "global") {
    if (form.querySelector(`[name="f${i}"]`).checked) delete out.eigen;
    else out.eigen = true;
  } else if (f.kind === "compare") {
    if (form.querySelector(`[name="f${i}"]`).checked) delete out.compare;
    else out.compare = false;
  } else {
    const v = form.querySelector(`[name="f${i}"]`).value.trim().slice(0, 60);
    if (v) out.title = v;
    else delete out.title;
  }
}
/* „Alle“ und einzelne Aktivitäten schließen sich aus; ohne Auswahl gilt „Alle“ */
function flBind(form) {
  const gl = form.querySelector("[data-global]");
  const zr = !!gl && gl.hasAttribute("data-zr");                                           // 3.34.0: „Zeitraum der Seite verwenden“ (Übersicht) betrifft nur den Zeitraum und nur, solange oben ein Zeitraum gewählt ist
  const sync = () => form.querySelectorAll(zr ? ".slfs:has(.flsel)" : ".flsp, .slfs:has(.flsel)").forEach(x => {
    const off = !!gl && gl.checked && (!zr || !!(window.ZR && ZR.F && ZR.F.uebersicht));
    x.classList.toggle("sl-gdis", off);
    x.querySelectorAll("input,select").forEach(i => (i.disabled = off));
  });
  const now = form.querySelector("[data-zrnow]");                                           // 3.37.2: Hilfstext „Gerade gilt: 2025 von der Seite“
  const say = () => {
    if (now && gl && typeof zrNowText === "function") now.textContent = zrNowText(!gl.checked);
  };
  if (gl) {
    gl.addEventListener("change", sync);
    gl.addEventListener("change", say);
    sync();
    say();
  }
  form.addEventListener("change", e => {
    const ch = e.target.closest && e.target.closest(".flchip input");
    if (!ch) return;
    const box = ch.closest(".flchips"), all = box.querySelector("[data-all]");
    if (!all) return;
    const some = [...box.querySelectorAll("input:not([data-all])")];
    if (ch === all) {
      if (all.checked) some.forEach(x => (x.checked = false));
      else all.checked = true;
    } else {
      if (ch.checked) all.checked = false;
      if (!some.some(x => x.checked)) all.checked = true;
    }
  });
}
