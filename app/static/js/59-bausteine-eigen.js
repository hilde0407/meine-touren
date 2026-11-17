/* =====================  3.28.0 Eigene Kennzahl  =====================
   Ein Baustein, den der Benutzer im Dialog „Eigene Kennzahl“ ohne Programmieren zusammenstellt: Name, Symbol, Messgröße, Rechenart, Filter, optional Vorjahresvergleich, Ziel und eine
   Formel A ÷ B – alles Auswahlen aus festen Listen (die gleichen Listen prüft der Server, app/kennzahl.py; dort steht auch die Beschreibung der Einstellung).
   Die Definition steht als Baustein vom Typ „eigenkz“ im Layout-Dokument (cfg), also gelten Ansichten, Vorlagen, Export, Reihenfolge, Breite und „Standard wiederherstellen“ wie bei allen Bausteinen.
   Gerechnet wird NUR im Server (POST /api/bausteine/eigen); die Oberfläche formatiert Zahl, Einheit, Vergleich, Mini-Verlauf (Inline-SVG) und Zielbalken. */
const KZ_TYPE = "eigenkz";
const KZ_MAX = 24;
const KZ_MESS = [["touren", "Anzahl Touren"], ["km", "Strecke"], ["hm", "Aufstieg (Höhenmeter)"], ["abstieg", "Abstieg (Höhenmeter)"], ["dauer", "Dauer"], ["gehzeit", "Gehzeit (Bewegungszeit ohne Pausen)"], ["puls", "Durchschnittspuls einer Tour"], ["pulsmax", "Höchstpuls einer Tour"], ["tempo", "Geschwindigkeit (Tempo)"], ["steigung", "Steigung"], ["hmkm", "Höhenmeter je Kilometer"]];
const KZ_PULS = ["avg", "max", "min", "count", "record"];
const KZ_ALLE = ["sum", "avg", "max", "min", "count", "record", "monat"];
const KZ_OK = {touren: ["sum", "count", "monat"], km: KZ_ALLE, hm: KZ_ALLE, abstieg: KZ_ALLE, dauer: KZ_ALLE, gehzeit: KZ_ALLE, puls: KZ_PULS, pulsmax: KZ_PULS, tempo: ["avg", "max", "min", "count", "record"], steigung: ["avg", "max", "min", "count", "record"], hmkm: ["avg", "max", "min", "count", "record"]};
const KZ_RATIO = ["tempo", "steigung", "hmkm"];
const KZ_FORMEL = ["sum", "avg", "max", "min", "count"];
const KZ_AGG = {sum: "Summe", avg: "Durchschnitt", max: "Maximum (größter Wert)", min: "Minimum (kleinster Wert)", count: "Anzahl (Touren mit dieser Angabe)", record: "Rekord mit Tourname", monat: "Durchschnitt pro Monat"};
const KZ_RANGES = [["year", "Laufendes Jahr"], ["12m", "Letzte 12 Monate"], ["90d", "Letzte 90 Tage"], ["all", "Gesamte Zeit"], ["y", "Bestimmtes Jahr"], ["c", "Eigener Bereich"]];
const KZ_SYMS = ["🥾", "🚴", "⛰️", "⏱️", "📈", "🏆", "🎯", "🔥", "🌲", "☀️"];
const KZ_UNIT = {touren: "touren", km: "km", hm: "m", abstieg: "m", dauer: "h", gehzeit: "h", puls: "bpm", pulsmax: "bpm", tempo: "kmh", steigung: "pct", hmkm: "m_km"};
const KZ_UL = {km: "km", m: "m", h: "Std.", kmh: "km/h", pct: "%", m_km: "m/km", bpm: "bpm", monat: "Monat"};
const kzT = s => (typeof window.TL === "function" ? window.TL(s) : s);                          // Übersetzung zur Laufzeit (nur nicht-deutsch vorhanden)
/* Vorlagen zum Start: ein Klick übernimmt die Einstellung in den Dialog */
const KZ_TPL = [
  {name: "Höhenmeter je km", desc: "Wie steil deine Touren im Schnitt sind: Aufstieg geteilt durch Strecke.", cfg: {title: "Höhenmeter je km", symbol: "⛰️", mess: "hm", agg: "sum", durch: {mess: "km", agg: "sum"}, op: "div", range: "year", vgl: true}},
  {name: "Touren pro Monat", desc: "Wie oft du im Schnitt pro Monat unterwegs bist.", cfg: {title: "Touren pro Monat", symbol: "📅", mess: "touren", agg: "monat", range: "12m", vgl: true}},
  {name: "Längste Wanderung", desc: "Deine längste Wanderung mit Name und Datum der Tour.", cfg: {title: "Längste Wanderung", symbol: "🥾", mess: "km", agg: "record", sports: ["hike"], range: "all"}},
  {name: "Ziel: 1000 km im Jahr", desc: "Fortschrittsbalken für dein Jahresziel in Kilometern.", cfg: {title: "1000 km im Jahr", symbol: "🎯", mess: "km", agg: "sum", range: "year", ziel: 1000, vgl: true}},
  {name: "Durchschnittstempo", desc: "Deine mittlere Geschwindigkeit der letzten 12 Monate.", cfg: {title: "Durchschnittstempo", symbol: "⚡", mess: "tempo", agg: "avg", range: "12m", vgl: true}},
  {name: "Größter Aufstieg", desc: "Die Tour mit den meisten Höhenmetern.", cfg: {title: "Größter Aufstieg", symbol: "🏔️", mess: "hm", agg: "record", range: "all"}},
];

/* ---------- Einheit, Zahl, Text ---------- */
const kzEinheit = c => {
  const one = (m, a) => (a === "count" ? "touren" : KZ_UNIT[m]);
  if (!c.durch) return {z: one(c.mess, c.agg), n: c.agg === "monat" ? "monat" : null};
  if (c.op === "pct") return {z: "pct", n: null};
  const z = one(c.mess, c.agg), n = one(c.durch.mess, c.durch.agg);
  return z === n ? {z: null, n: null} : {z, n};
};
const kzPart = (u, v) => (u === "touren" ? (Math.abs(v) === 1 ? "Tour" : "Touren") : KZ_UL[u] || "");
function kzUnitText(e, v) {
  if (!e || !e.z) return "";
  return e.n ? `${kzT(kzPart(e.z, 2))}/${kzT(e.n === "touren" ? "Tour" : kzPart(e.n, 2))}` : kzT(kzPart(e.z, v));
}
function kzNum(v, e) {
  if (v == null) return "–";
  if (e && e.z === "h" && !e.n) return fmtHM(v * 3600);
  const a = Math.abs(v);
  let d;
  if (!e || !e.z || e.n) d = a >= 100 ? 0 : a >= 10 ? 1 : 2;
  else if (e.z === "touren" || e.z === "m") d = a >= 100 || Number.isInteger(v) ? 0 : 1;
  else d = a >= 100 && e.z === "km" ? 0 : 1;
  return nf(v, d);
}
const kzAggLab = (mess, agg) => (agg === "avg" && KZ_RATIO.includes(mess) ? "Durchschnitt (gewichtet)" : agg === "sum" && mess === "touren" ? "Summe (Anzahl der Touren)" : KZ_AGG[agg]);
const kzVglLab = c => (c.range === "y" ? `gegenüber ${(+c.yr || 0) - 1}` : {year: "gegenüber dem Vorjahr bis zum selben Tag", "12m": "gegenüber den 12 Monaten davor", "90d": "gegenüber den 90 Tagen davor", c: "gegenüber dem gleich langen Zeitraum davor"}[c.range || "year"] || "");
const kzLab = (art, l) => (art === "monat" ? `${l.slice(5, 7)}/${l.slice(0, 4)}` : l);
/* Kurztext der Filter für den Kopf des Bausteins */
function kzKurz(cfg) {
  const s = cfg.sports || [], out = [];
  if (s.length) s.length <= 2 ? s.forEach(x => out.push(sName(x))) : out.push(`${s.length} Aktivitäten`);
  out.push(flRange(cfg, "year").label);
  if (cfg.tag) out.push(`„${cfg.tag}“`);
  if (cfg.minkm) out.push(`≥ ${nf(cfg.minkm, cfg.minkm % 1 ? 1 : 0)} km`);
  return out;
}
const kzCount = () => Object.values(SL.docs).reduce((n, d) => n + ((d && d.widgets) || []).filter(w => w.type === KZ_TYPE).length, 0);
const KZ_KEYS = ["title", "symbol", "mess", "agg", "durch", "op", "sports", "range", "yr", "from", "to", "tag", "minkm", "vgl", "ziel"];
/* nur die Felder der Definition senden (die Statistikseite hängt interne Merker mit „_“ an die Einstellung) */
const kzPost = cfg => api("/api/bausteine/eigen", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(Object.fromEntries(KZ_KEYS.filter(k => cfg[k] !== undefined).map(k => [k, cfg[k]])))});

/* ---------- Darstellung (Baustein und Vorschau im Dialog) ---------- */
function kzHtml(cfg, d) {
  const e = d.einheit || {}, v = d.wert, un = v == null ? "" : kzUnitText(e, v), sym = cfg.symbol ? `<span class="kzsy" aria-hidden="true">${esc(cfg.symbol)}</span>` : "";
  let h = `<div class="kz"><p class="kzmain">${sym}<b class="kzval">${esc(kzNum(v, e))}</b>${un ? `<span class="kzun">${esc(un)}</span>` : ""}</p>`;
  if (v == null) h += `<p class="mut kzsub">${d.n ? "Für diese Rechenart fehlen Angaben in den Touren." : "Im Zeitraum gibt es keine passenden Touren."}</p>`;
  if (d.offen) h += `<p class="mut kzsub">${d.offen === 1 ? "Für 1 Tour wird die Gehzeit noch berechnet. Öffne die Seite später erneut." : `Für ${d.offen} Touren wird die Gehzeit noch berechnet. Öffne die Seite später erneut.`}</p>`;
  if (d.rekord) h += `<p class="kzsub"><span class="mut">Rekord-Tour</span> <a href="#/tour/${slEnc(d.rekord.id)}">${esc(d.rekord.name || "Tour")}</a> <span class="mut">${dateS(d.rekord.datum)}</span></p>`;
  if (cfg.vgl) {
    const o = d.vorher;
    if (o && o.pct != null) {
      const up = o.pct >= 0;
      h += `<p class="kzvgl"><b class="kzd ${up ? "kzup" : "kzdn"}"><span aria-hidden="true">${up ? "▲" : "▼"}</span> ${up ? "+" : "−"}${nf(Math.abs(o.pct), 1)} %</b> <span class="mut">${kzVglLab(cfg)}</span></p>` +
        (o.wert != null ? `<p class="mut kzvv"><span>Vorher</span> ${esc(kzNum(o.wert, e))} <span>${esc(kzUnitText(e, o.wert))}</span></p>` : "");
    } else h += `<p class="mut kzsub">${d.vorher ? "Im Vergleichszeitraum gibt es keinen Wert." : "Für diesen Zeitraum gibt es keinen Vergleich."}</p>`;
  }
  const w = (d.reihe && d.reihe.werte) || [];
  if (w.length > 1 && w.some(x => x)) {
    const vals = w.map(x => x || 0), best = vals.indexOf(Math.max(...vals)), L = d.reihe.labels, art = d.reihe.art;
    h += `<div class="kzsp">${slCols(vals, {hl: best, cls: "kzsc", label: `Verlauf je ${art === "jahr" ? "Jahr" : "Monat"} von ${kzLab(art, L[0])} bis ${kzLab(art, L[L.length - 1])}, höchster Wert ${kzNum(vals[best], e)} ${kzUnitText(e, vals[best])} (${kzLab(art, L[best])})`})}` +
      `<div class="slxl sb" aria-hidden="true"><span>${esc(kzLab(art, L[0]))}</span><span>${esc(kzLab(art, L[L.length - 1]))}</span></div></div>`;
  }
  if (d.ziel) {
    const p = d.ziel.pct;
    h += `<div class="kzgoal" role="group" aria-label="Ziel">${slBr(p, p >= 100 ? "kzfull" : "")}<p class="kzgt"><b>${nf(p, 0)} % von</b> <span>${esc(kzNum(d.ziel.ziel, e))} ${esc(kzUnitText(e, d.ziel.ziel))}</span>${p >= 100 ? ' <span class="kzok">✓ Ziel erreicht</span>' : ""}</p></div>`;
  }
  return h + "</div>";
}
async function kzRender(c, b, cfg) {
  let d;
  try {
    d = await kzPost(cfg);
  } catch (e) {
    return slNote(b, "Diese Kennzahl konnte nicht berechnet werden. Prüfe die Einstellung im Zahnrad.");
  }
  b.innerHTML = kzHtml(cfg, d);
  slBadge(c, d.wert == null ? "" : `${esc(kzNum(d.wert, d.einheit))} ${esc(kzUnitText(d.einheit, d.wert))}`.trim());
}

/* ---------- Dialog ---------- */
const kzOpts = (list, cur) => list.map(([v, l]) => `<option value="${esc(v)}"${v === cur ? " selected" : ""}>${esc(l)}</option>`).join("");
function kzForm(cfg) {
  const yrs = flYears(), yr = +cfg.yr || new Date().getFullYear();
  if (!yrs.includes(yr)) yrs.push(yr);
  return `<form class="slform kzform" novalidate>` +
    `<details class="kztplb"${cfg.mess ? "" : " open"}><summary>Mit einer Vorlage starten</summary><div class="kztpls">${KZ_TPL.map((t, i) => `<button type="button" class="kztpl" data-i="${i}"><b>${esc(t.name)}</b><small class="mut">${esc(t.desc)}</small></button>`).join("")}</div></details>` +
    `<section class="kzpv"><h3 class="kzpvh">Vorschau</h3><div class="kzpvb" role="status" aria-live="polite"></div></section>` +
    `<fieldset class="slfs kzfs"><legend>Name und Symbol</legend><div class="kzrow kzrow2"><div><label for="kz-title">Name</label><input id="kz-title" type="text" maxlength="60" autocomplete="off" required placeholder="Zum Beispiel: Höhenmeter je km"></div>` +
    `<div><label for="kz-sym">Symbol (Emoji, optional)</label><input id="kz-sym" type="text" maxlength="8" autocomplete="off"></div></div>` +
    `<div class="kzsyl" role="group" aria-label="Symbol wählen">${KZ_SYMS.map(s => `<button type="button" class="kzsyb" data-s="${s}" aria-label="Symbol ${s}">${s}</button>`).join("")}</div></fieldset>` +
    `<fieldset class="slfs kzfs"><legend>Was wird gerechnet?</legend><div class="kzrow"><div><label for="kz-mess">Messgröße</label><select id="kz-mess" class="flsel">${kzOpts(KZ_MESS, "")}</select></div>` +
    `<div><label for="kz-agg">Rechenart</label><select id="kz-agg" class="flsel"></select></div></div>` +
    `<label class="slck kzck"><input type="checkbox" id="kz-formel"><span>Formel: durch eine zweite Kennzahl teilen</span></label>` +
    `<div class="kzformel" hidden><div class="kzrow kzrow3"><div><label for="kz-op">Rechnung</label><select id="kz-op" class="flsel"><option value="div">A ÷ B</option><option value="pct">A in Prozent von B</option></select></div>` +
    `<div><label for="kz-bmess">B: Messgröße</label><select id="kz-bmess" class="flsel">${kzOpts(KZ_MESS, "km")}</select></div><div><label for="kz-bagg">B: Rechenart</label><select id="kz-bagg" class="flsel"></select></div></div>` +
    `<p class="mut kzhint">A ist die Messgröße und Rechenart oben, zum Beispiel Höhenmeter (Summe) ÷ Strecke (Summe) = Höhenmeter je km.</p></div></fieldset>` +
    `<fieldset class="slfs kzfs"><legend>Filter</legend>${flField({kind: "sports", label: "Aktivität"}, cfg, 0)}` +
    `<div class="kzrow"><div><label for="kz-range">Zeitraum</label><select id="kz-range" class="flsel">${kzOpts(KZ_RANGES, "year")}</select></div>` +
    `<div class="kzyr" hidden><label for="kz-yr">Jahr</label><select id="kz-yr" class="flsel">${yrs.sort((a, b) => b - a).map(y => `<option value="${y}"${y === yr ? " selected" : ""}>${y}</option>`).join("")}</select></div></div>` +
    (SL.fam === "uebersicht" || SL.fam === "statistik" ? `<label class="slck kzck kzpg"><input type="checkbox" id="kz-page"><span>Zeitraum der Seite verwenden</span></label><p class="mut kzhint kzph">Ist oben auf der Seite ein Zeitraum gewählt, gilt er hier statt des Zeitraums oben. Ohne Haken behält diese Kennzahl ihren eigenen Zeitraum.</p>` : "") +
    `<div class="kzrow kzrow2 kzdates" hidden><div><label for="kz-from">Von</label><input id="kz-from" type="date"></div><div><label for="kz-to">Bis</label><input id="kz-to" type="date"></div></div>` +
    `<div class="kzrow kzrow2"><div><label for="kz-tag">Schlagwort (optional)</label><input id="kz-tag" type="text" maxlength="40" autocomplete="off" list="kz-tags"><datalist id="kz-tags"></datalist></div>` +
    `<div><label for="kz-minkm">Mindeststrecke in km (optional)</label><input id="kz-minkm" type="number" inputmode="decimal" min="0" max="1000" step="any"></div></div></fieldset>` +
    `<fieldset class="slfs kzfs"><legend>Anzeige</legend><label class="slck kzck"><input type="checkbox" id="kz-vgl"><span>Mit dem Zeitraum davor vergleichen (±&nbsp;%)</span></label><p class="mut kzhint kzvh" hidden>Für „Gesamte Zeit“ gibt es keinen Vergleichszeitraum.</p>` +
    `<div class="kzrow kzrow2"><div><label for="kz-ziel">Ziel (optional)</label><input id="kz-ziel" type="number" inputmode="decimal" min="0" step="any"></div><p class="mut kzzu" id="kz-zu"></p></div></fieldset>` +
    `<p class="slerr kzerr" role="alert"></p><div class="uifoot"><button type="button" class="btn ghost" data-close>Abbrechen</button><button type="submit" class="btn">${cfg.mess ? "Speichern" : "Hinzufügen"}</button></div></form>`;
}
/* Einstellung → Formular (auch beim Übernehmen einer Vorlage) */
function kzFill(form, cfg) {
  const g = id => form.querySelector("#" + id), set = (id, v) => (g(id).value = v == null ? "" : v);
  set("kz-title", cfg.title);
  set("kz-sym", cfg.symbol);
  set("kz-mess", cfg.mess || "km");
  g("kz-formel").checked = !!cfg.durch;
  set("kz-op", cfg.op || "div");
  set("kz-bmess", (cfg.durch && cfg.durch.mess) || "km");
  kzAggs(form, cfg.agg, (cfg.durch && cfg.durch.agg) || "sum");
  const sp = form.querySelector(".flsp");
  sp.outerHTML = flField({kind: "sports", label: "Aktivität"}, {sports: cfg.sports || []}, 0);
  set("kz-range", cfg.range || "year");
  if (form.querySelector("#kz-page")) form.querySelector("#kz-page").checked = cfg.eigen !== true;
  if (cfg.yr) set("kz-yr", cfg.yr);
  set("kz-from", cfg.from);
  set("kz-to", cfg.to);
  set("kz-tag", cfg.tag);
  set("kz-minkm", cfg.minkm);
  g("kz-vgl").checked = !!cfg.vgl;
  set("kz-ziel", cfg.ziel);
  kzSync(form);
}
/* Rechenarten passend zur Messgröße (bei einer Formel für A nur die, die in Formeln erlaubt sind) */
function kzAggs(form, a, b) {
  const g = id => form.querySelector("#" + id), formel = g("kz-formel").checked,
    fill = (sel, mess, cur, only) => {
      const L = KZ_OK[mess].filter(x => !only || only.includes(x));
      sel.innerHTML = L.map(x => `<option value="${x}"${x === cur ? " selected" : ""}>${esc(kzAggLab(mess, x))}</option>`).join("");
      if (!L.includes(cur)) sel.value = L[0];
    };
  if (a !== undefined) fill(g("kz-agg"), g("kz-mess").value, a, formel ? KZ_FORMEL : null);
  if (b !== undefined) fill(g("kz-bagg"), g("kz-bmess").value, b, KZ_FORMEL);
}
function kzSync(form) {
  const g = id => form.querySelector("#" + id), r = g("kz-range").value;
  kzAggs(form, g("kz-agg").value, g("kz-bagg").value);
  form.querySelector(".kzformel").hidden = !g("kz-formel").checked;
  form.querySelector(".kzyr").hidden = r !== "y";
  form.querySelector(".kzdates").hidden = r !== "c";
  g("kz-vgl").disabled = r === "all";
  if (r === "all") g("kz-vgl").checked = false;
  form.querySelector(".kzvh").hidden = r !== "all";
  const c = kzRead(form, true), e = c ? kzEinheit(c) : null;
  g("kz-zu").textContent = e && e.z ? `${kzT("Einheit")}: ${kzUnitText(e, 2)}` : "";
}
/* Formular → Einstellung; bei Fehlern {err, el} (strict = Pflichtangaben prüfen) */
function kzRead(form, soft) {
  const g = id => form.querySelector("#" + id), out = {}, bad = (msg, el) => (soft ? null : {err: msg, el});
  const title = g("kz-title").value.trim();
  if (!title && !soft) return bad("Bitte gib der Kennzahl einen Namen.", g("kz-title"));
  out.title = title || "…";
  const sym = g("kz-sym").value.trim();
  if (sym) out.symbol = sym.slice(0, 8);
  out.mess = g("kz-mess").value;
  out.agg = g("kz-agg").value;
  if (g("kz-formel").checked) {
    out.durch = {mess: g("kz-bmess").value, agg: g("kz-bagg").value};
    out.op = g("kz-op").value;
  }
  flRead({kind: "sports"}, form, 0, out);
  const r = g("kz-range").value;
  out.range = r;
  if (g("kz-page") && !g("kz-page").checked) out.eigen = true;                                  // 3.34.0: eigener Zeitraum (der Zeitraum der Seite gilt hier nicht)
  if (r === "y") out.yr = +g("kz-yr").value;
  if (r === "c") {
    const a = g("kz-from").value, z = g("kz-to").value;
    if (!/^\d{4}-\d\d-\d\d$/.test(a) || !/^\d{4}-\d\d-\d\d$/.test(z)) return soft ? out : bad("Bitte Anfang und Ende des Bereichs wählen.", g(a ? "kz-to" : "kz-from"));
    if (a > z) return soft ? out : bad("Der Anfang darf nicht nach dem Ende liegen.", g("kz-from"));
    out.from = a;
    out.to = z;
  }
  const tag = g("kz-tag").value.trim();
  if (tag) out.tag = tag.slice(0, 40);
  const mk = g("kz-minkm").value.trim();
  if (mk) {
    const v = parseFloat(mk.replace(",", "."));
    if (!(v >= 0 && v <= 1000)) return soft ? out : bad("Die Mindeststrecke liegt zwischen 0 und 1000 km.", g("kz-minkm"));
    if (v > 0) out.minkm = v;
  }
  if (g("kz-vgl").checked && r !== "all") out.vgl = true;
  const zl = g("kz-ziel").value.trim();
  if (zl) {
    const v = parseFloat(zl.replace(",", "."));
    if (!(v > 0 && v <= 1e7)) return soft ? out : bad("Das Ziel muss größer als 0 sein.", g("kz-ziel"));
    out.ziel = v;
  }
  return out;
}
/* id = null: neuer Baustein; sonst Bearbeiten des Bausteins mit dieser Kennung */
function kzDialog(id, cfg0) {
  const cfg = JSON.parse(JSON.stringify(cfg0 || {}));
  if (!id && kzCount() >= KZ_MAX) return uiAlert(`Es sind höchstens ${KZ_MAX} eigene Kennzahlen möglich.`);
  slModal(id ? "Eigene Kennzahl bearbeiten" : "Eigene Kennzahl erstellen", (body, close) => {
    body.innerHTML = kzForm(cfg);
    const form = body.querySelector("form"), pv = form.querySelector(".kzpvb");
    let timer = null, seq = 0;
    const preview = () => {
      const c = kzRead(form, true), n = ++seq;
      kzPost(c).then(d => n === seq && (pv.innerHTML = kzHtml(c, d))).catch(() => n === seq && (pv.innerHTML = `<p class="mut kzsub">Mit dieser Einstellung lässt sich nichts berechnen.</p>`));
    };
    const later = () => {
      clearTimeout(timer);
      timer = setTimeout(preview, 250);
    };
    kzFill(form, cfg.mess ? cfg : {mess: "km", agg: "sum", range: "year"});
    flBind(form);
    form.addEventListener("input", later);
    form.addEventListener("change", () => {
      kzSync(form);
      later();
    });
    form.onclick = e => {
      const t = e.target.closest(".kztpl"), s = e.target.closest(".kzsyb");
      if (e.target.closest("[data-close]")) close();
      else if (t) {
        const tp = KZ_TPL[+t.dataset.i], c = JSON.parse(JSON.stringify(tp.cfg));
        c.title = kzT(c.title);
        kzFill(form, c);
        form.querySelector(".kztplb").open = false;
        form.querySelector(".kzerr").textContent = "";
        clearTimeout(timer);
        preview();
        form.querySelector("#kz-title").focus();
      } else if (s) {
        form.querySelector("#kz-sym").value = s.dataset.s;
        later();
      }
    };
    form.onsubmit = e => {
      e.preventDefault();
      const c = kzRead(form);
      if (c.err) {
        form.querySelector(".kzerr").textContent = c.err;
        c.el.focus();
        return;
      }
      close();
      if (id) slSetCfg(id, c);
      else slAddWidget(KZ_TYPE, c);
    };
    api("/api/tags").then(l => {                                                                    // Schlagwörter zum Auswählen (kein Muss)
      const dl = form.querySelector("#kz-tags");
      (Array.isArray(l) ? l : []).slice(0, 200).forEach(t => t && t.tag && dl.appendChild(Object.assign(document.createElement("option"), {value: t.tag})));
    }).catch(() => {});
    preview();
  }, "slkz");
}

SL_CATS.push(["eigene", "Eigene Kennzahlen"]);
Object.assign(window.SL_WT, {
  [KZ_TYPE]: {
    fam: "uebersicht", cat: "eigene", icon: "met", name: "Eigene Kennzahl", title: cfg => (cfg && cfg.title) || "Eigene Kennzahl", multi: true, w: "drittel", seiten: ["uebersicht", "statistik"],
    fields: [{kind: "eigen"}], zeit: true, kurz: kzKurz, neu: () => kzDialog(null, {}), dialog: (id, cfg) => kzDialog(id, cfg),
    grenze: () => (kzCount() >= KZ_MAX ? `Es sind höchstens ${KZ_MAX} eigene Kennzahlen möglich.` : ""),
    dup: cfg => ({...cfg, title: `${String(cfg.title || "").slice(0, 50)} (${kzT("Kopie")})`}),
    desc: "Stelle selbst zusammen, was du wissen willst: Messgröße, Rechenart, Filter, Vergleich mit dem Vorjahr, Ziel mit Fortschrittsbalken oder eine Formel wie Höhenmeter je km. Ohne Programmieren, mit Vorlagen zum Start.",
    preview: () => slPrev(`<div class="kz kzpvx"><p class="kzmain"><span class="kzsy">🎯</span><b class="kzval">762</b><span class="kzun">km</span></p>${slBr(76)}</div>`),
    render: (c, b, cfg) => kzRender(c, b, cfg),
  },
});
