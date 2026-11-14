/* =====================  3.12.0: Belastung und Erholung, Tempo nach Steigung (Statistik) und Tourseite  =====================
   Statistik (Übersicht): „Belastung und Erholung“ (Uhr-Werte je Woche/Monat) und „Dein typisches Tempo“ mit Gehzeit-Rechner.
   Tourseite: Kachelzeile „Tempo nach Steigung“. Es erscheint nur, was Daten hat; Touren ohne Uhr-Wert gelten als „ohne Angabe“, nie als 0.
   Berechnung und Prüfung machen app/belastung.py und app/steigung.py. Farben: ein einziger Balkenton (--utbar), Text immer in Textfarben. */
const BL = {mode: "w", range: "6", sport: "wandern", jahr: 0},
  BL_RANGES = [["3", "Letzte 3 Monate"], ["6", "Letzte 6 Monate"], ["12", "Letzte 12 Monate"], ["0", "Alles"]],
  blDate = d => d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()),
  blParse = iso => new Date(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)),
  blDay = iso => blParse(iso).toLocaleDateString("de-DE", {day: "numeric", month: "short"}),
  blRange = b => (b.von === b.bis ? blDay(b.von) : blDay(b.von) + " – " + blDay(b.bis)),
  blDur = s => {
    const m = Math.round(s / 60);
    return m >= 60 ? Math.floor(m / 60) + " h " + pad2(m % 60) + " min" : Math.max(1, m) + " min";
  },
  blLabel = (b, mode) => (mode === "m" ? blParse(b.von).toLocaleDateString("de-DE", {month: "long", year: "numeric"}) : b.label);

function blRangeQuery() {
  const n = +BL.range;
  if (!n) return "";
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  return "?von=" + blDate(d) + "&bis=" + blDate(new Date());
}

/* Texte zu einem Balken: [Beschriftung, Datum, Belastung, Touren] – jede Zeile ein eigener Textknoten (damit sie übersetzt werden kann) */
function blLines(b, mode) {
  const l = [blLabel(b, mode), blRange(b)];
  if (!b.touren) l.push("Keine Tour");
  else if (b.belastung == null) l.push(b.touren === 1 ? `${b.touren} Tour ohne Uhr-Daten (keine Angabe)` : `${b.touren} Touren ohne Uhr-Daten (keine Angabe)`);
  else l.push(`Belastung ${nf(b.belastung, 0)}`, `${b.mit_daten} von ${b.touren} Touren mit Uhr-Daten`);
  return l;
}

function blNice(v) {
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(v, 1)))),
    f = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find(x => x * p >= v) || 10;
  return f * p;
}

function blChart(buckets, mode, width) {
  const L = 40, R = 6, T = 22, B = 26, H = 190, SLOT = 12,
    n = buckets.length,
    W = Math.max(width, L + R + n * SLOT),
    slot = (W - L - R) / n,
    bw = Math.max(5, Math.min(26, slot * 0.7)),
    vals = buckets.map(b => b.belastung).filter(v => v != null),
    ymax = blNice(Math.max(1, ...vals)),
    y = v => T + (H - T - B) * (1 - v / ymax),
    base = y(0),
    step = Math.max(1, Math.ceil(46 / slot)),
    top = vals.length ? Math.max(...vals) : -1;
  let g = `<defs><pattern id="blhatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect class="blhr" width="6" height="6"/><line class="blhl" x1="0" y1="0" x2="0" y2="6"/></pattern></defs>`;
  [0, ymax / 2, ymax].forEach(v => (g += `<line class="blgrid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text x="${L - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${nf(v, 0)}</text>`));
  let lastFocus = -1;
  buckets.forEach((b, i) => {
    if (b.touren) lastFocus = i;
  });
  buckets.forEach((b, i) => {
    const x = L + i * slot + (slot - bw) / 2;
    if (i % step === 0) {
      const t = mode === "m" ? blParse(b.von).toLocaleDateString("de-DE", {month: "short", year: "2-digit"}) : b.label.replace(/\/\d{4}$/, "");
      g += `<text x="${(L + i * slot + slot / 2).toFixed(1)}" y="${H - 6}" text-anchor="middle">${esc(t)}</text>`;
    }
    if (!b.touren) return;
    const lines = blLines(b, mode);
    let mark = "";
    if (b.belastung != null) {
      const h = Math.max(2, base - y(b.belastung));
      mark = `<rect class="${b.ohne_angabe ? "blpart" : "blbar"}" x="${x.toFixed(1)}" y="${(base - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3"/>`;
      if (b.belastung === top) mark += `<text class="blval" x="${(x + bw / 2).toFixed(1)}" y="${(base - h - 5).toFixed(1)}" text-anchor="middle">${nf(b.belastung, 0)}</text>`;
    } else mark = `<rect class="blnone" x="${x.toFixed(1)}" y="${(base - 8).toFixed(1)}" width="${bw.toFixed(1)}" height="8" rx="2"/>`;
    g += `<g class="blg" data-i="${i}" tabindex="${i === lastFocus ? 0 : -1}" role="img" aria-label="${esc(lines.join(" · "))}"><rect class="blhit" x="${(L + i * slot).toFixed(1)}" y="${T - 14}" width="${slot.toFixed(1)}" height="${(H - T - B + 14).toFixed(1)}"/>${mark}</g>`;
  });
  return `<svg class="blsvg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="group" aria-label="${mode === "m" ? "Balkendiagramm: Trainingsbelastung je Monat" : "Balkendiagramm: Trainingsbelastung je Woche"}">${g}<line class="blbase" x1="${L}" x2="${W - R}" y1="${base.toFixed(1)}" y2="${base.toFixed(1)}"/></svg>`;
}

function blBind(root, buckets, mode) {
  const tip = root.querySelector("#bltip"),
    wrap = root.querySelector(".blwrap"),
    scr = root.querySelector(".blscroll"),
    gs = [...root.querySelectorAll(".blg")];
  const show = g => {
    const b = buckets[+g.dataset.i],
      l = blLines(b, mode);
    tip.innerHTML = `<b>${esc(l[0])}</b> <span>${esc(l[1])}</span>` + l.slice(2).map(x => `<div>${esc(x)}</div>`).join("");
    tip.hidden = false;
    const r = g.getBoundingClientRect(),
      w = wrap.getBoundingClientRect(),
      half = tip.offsetWidth / 2;
    tip.style.left = Math.min(Math.max(r.left - w.left + r.width / 2, half + 4), w.width - half - 4) + "px";
    tip.style.top = Math.max(r.top - w.top - 6, tip.offsetHeight + 4) + "px";
  };
  const hide = () => (tip.hidden = true);
  gs.forEach((g, k) => {
    g.onpointerenter = () => show(g);
    g.onpointerleave = () => {
      if (document.activeElement !== g) hide();
    };
    g.onfocus = () => show(g);
    g.onblur = hide;
    g.onclick = () => show(g);
    g.onkeydown = e => {
      const to = {ArrowLeft: k - 1, ArrowRight: k + 1, Home: 0, End: gs.length - 1}[e.key];
      if (e.key === "Escape") return hide();
      if (to === undefined) return;
      e.preventDefault();
      const t = gs[Math.max(0, Math.min(gs.length - 1, to))];
      gs.forEach(x => x.setAttribute("tabindex", "-1"));
      t.setAttribute("tabindex", "0");
      t.focus();
    };
  });
  if (scr) scr.scrollLeft = scr.scrollWidth;                          // neueste Wochen zuerst sichtbar
}

const BL_STUFE = {
  deutlich_mehr: "Deutlich mehr Belastung als sonst",
  mehr: "Etwas mehr Belastung als sonst",
  aehnlich: "Ähnlich viel Belastung wie sonst",
  weniger: "Etwas weniger Belastung als sonst",
  deutlich_weniger: "Deutlich weniger Belastung als sonst",
};

function blAktuell(a) {
  if (!a) return "";
  let h = `<div class="blcore"><div class="uth">Aktuell im Vergleich</div>`;
  if (a.status === "ok") {
    const p = a.abweichung_pct;
    h += `<div class="blnow"><b>${BL_STUFE[a.stufe]}</b></div><div class="mut blnowd"><span>Letzte 4 Wochen: Ø ${nf(a.aktuell_schnitt, 0)} pro Woche</span> · <span>die 12 Wochen davor: Ø ${nf(a.basis_schnitt, 0)} pro Woche</span> · <span>${p > 0 ? "+" : p < 0 ? "−" : "±"}${nf(Math.abs(p), 0)} %</span></div>`;
  } else if (a.status === "keine_aktuellen_daten") h += `<div class="mut">In den letzten 4 Wochen liegen keine Uhr-Daten vor.</div>`;
  else h += `<div class="mut">Für den Vergleich fehlen noch Daten: Es braucht mindestens ${a.mindestens} Wochen mit Uhr-Daten in den 12 Wochen vor den letzten 4 (bisher ${a.wochen_mit_daten_basis}).</div>`;
  return h + `</div>`;
}

const BL_NOTE = `<div class="mut hrnote"><span>Vergleich: Wochenschnitt der letzten 4 Wochen gegen den der 12 Wochen davor.</span> <span>„Etwas“ heißt mehr als 15 %, „deutlich“ mehr als 40 % Unterschied (grobe Schwellen).</span> <span>Wochen mit Touren, aber ohne Uhr-Daten, bleiben außen vor.</span></div>`;

function blTop(d) {
  const wk = d.haertest_wochen.length
      ? d.haertest_wochen.map(b => `<div class="r"><span>${esc(b.label)}<small>${esc(blRange(b))}${b.ohne_angabe ? " · " + (b.mit_daten + " von " + b.touren + " Touren mit Uhr-Daten") : ""}</small></span><b>${nf(b.belastung, 0)}</b></div>`).join("")
      : `<div class="mut">Noch keine Uhr-Daten im Zeitraum.</div>`,
    to = d.haertest_touren.length
      ? d.haertest_touren.map(t => `<div class="r"><span><a href="#/tour/${esc(t.id)}">${esc(t.name)}</a><small>${esc(dateS(t.datum))} · ${nf(t.km, 1)} km</small></span><b>${nf(t.belastung, 0)}</b></div>`).join("")
      : `<div class="mut">Noch keine Uhr-Daten im Zeitraum.</div>`;
  return trFold("bl_top", "Die härtesten Wochen und Touren", "", `<div class="grid g2"><div><div class="uth">Die härtesten Wochen</div><div class="rows">${wk}</div></div><div><div class="uth">Die härtesten Touren</div><div class="rows">${to}</div></div></div>`, true);
}

function blTable(buckets, mode) {
  const rows = buckets.filter(b => b.touren).map(b => `<tr><td>${esc(blLabel(b, mode))} <span class="mut">${esc(blRange(b))}</span></td><td class="n">${b.belastung == null ? "–" : nf(b.belastung, 0)}</td><td class="n">${b.touren}</td><td class="n">${b.mit_daten}</td></tr>`).join("");
  return trFold("bl_tab", "Zahlen als Tabelle", "", `<div class="tblw"><table><thead><tr><th>Zeitraum</th><th class="n">Belastung</th><th class="n">Touren</th><th class="n">mit Uhr-Daten</th></tr></thead><tbody>${rows}</tbody></table></div>`, false);
}

async function blDraw(root) {
  const box = root.querySelector("#blbody");
  let d;
  try {
    d = await api("/api/stats/belastung" + blRangeQuery());
  } catch (e) {
    box.innerHTML = `<p class="mut" role="status">${esc(e.message || "Fehler")}</p>`;
    return;
  }
  if (!root.isConnected) return;
  const bk = BL.mode === "m" ? d.monate : d.wochen,
    g = d.gesamt,
    wd = d.wochen.filter(b => b.belastung != null),
    avg = wd.length ? wd.reduce((s, b) => s + b.belastung, 0) / wd.length : null,
    pend = d.offen.zepp_ohne_werte;
  const tiles = g.touren
    ? `<div class="utiles"><div class="utile"><b>${g.mit_daten} von ${g.touren}</b><span class="mut">Touren mit Uhr-Daten</span><small class="mut">${g.anteil_pct} % aller Touren im Zeitraum</small></div>` +
      `<div class="utile"><b>${g.belastung == null ? "–" : nf(g.belastung, 0)}</b><span class="mut">Belastung im Zeitraum</span><small class="mut">Summe laut Uhr</small></div>` +
      `<div class="utile"><b>${avg == null ? "–" : nf(avg, 0)}</b><span class="mut">Ø je Woche mit Daten</span><small class="mut">Wochen ohne Uhr-Daten zählen nicht</small></div></div>`
    : "";
  const chart = g.touren
    ? `<div class="blwrap"><div class="blscroll" id="blscroll" role="region" aria-label="Diagramm Belastung" tabindex="-1">${blChart(bk, BL.mode, root.querySelector("#blbody").clientWidth - 2)}</div><div class="tip bltip" id="bltip" hidden></div></div>` +
      `<div class="legend bllegend"><span><i class="lgbar"></i>Belastung (Summe laut Uhr)</span><span><i class="lgpart"></i>Schraffiert: ein Teil der Touren ohne Uhr-Daten (Wert ist dann zu niedrig)</span><span><i class="lgnone"></i>Gestrichelt: nur Touren ohne Uhr-Daten (keine Angabe)</span></div>` +
      blTable(bk, BL.mode)
    : `<p class="mut">Keine Touren im gewählten Zeitraum.</p>`;
  const note = trFold("bl_note", "So wird verglichen", "", BL_NOTE, false) ;
  box.innerHTML = blAktuell(d.aktuell) + tiles + chart + (g.touren ? blTop(d) : "") + note;
  trBind(box);
  const key = root.querySelector("#blkey");
  if (key) key.textContent = d.aktuell && d.aktuell.status === "ok" ? BL_STUFE[d.aktuell.stufe] : g.touren ? g.mit_daten + " von " + g.touren + " Touren mit Uhr-Daten" : "";
  const sv = box.querySelector(".blsvg");
  if (sv) blBind(root, bk, BL.mode);
  const hint = root.querySelector("#blhint");
  hint.innerHTML = (pend ? `<div class="blpend"><span>Für ${pend} Zepp-Touren liegen noch keine Uhr-Werte vor.</span></div>` : "") +
    trFold("bl_hint", "Hinweise zur Quelle", "", `<div class="mut hrnote"><span>Zepp-Werte werden beim ersten Öffnen einer Tour gespeichert.</span> <span>Belastung: Skala laut Zepp, nicht mit Garmin oder Suunto vergleichbar.</span></div>`, false);
  trBind(hint);
  const jb = root.querySelector("#bljob");
  jb.hidden = !pend || (typeof isViewer === "function" && isViewer());
}

async function blJob(root) {
  const b = root.querySelector("#bljob"),
    m = root.querySelector("#bljobm");
  b.disabled = true;
  m.textContent = "Wird geladen …";
  try {
    await api("/api/jobs/uhr-alle", {method: "POST"});
  } catch (x) {
    m.textContent = x.message || "Fehler";
    b.disabled = false;
    return;
  }
  const tick = async () => {
    if (!root.isConnected) return;
    const j = await api("/api/jobs").catch(() => null);
    if (j && j.running) return setTimeout(tick, 1500);
    m.textContent = (j && j.log.filter(l => /Uhr-Daten:/.test(l)).slice(-2).join(" · ")) || "Fertig";
    b.disabled = false;
    blDraw(root);
  };
  setTimeout(tick, 1200);
}

function blSection(host) {
  const d = document.createElement("div");
  d.id = "blsec";
  d.innerHTML = `<details class="agrp trf trsec" data-trf="bl_sec"${trOpen("bl_sec", true) ? " open" : ""}><summary><span class="gt">Belastung und Erholung</span><span class="gs">laut Uhr (Zepp)</span><span class="trfk" id="blkey"></span></summary><div class="gbody"><div class="panel" id="blpanel">
    <div class="row blctl"><div class="chips" role="group" aria-label="Ansicht"><button class="chip on" data-m="w" aria-pressed="true">Wochen</button><button class="chip" data-m="m" aria-pressed="false">Monate</button></div>
    <label class="blsel"><span class="mut">Zeitraum</span> <select id="blrange">${BL_RANGES.map(r => `<option value="${r[0]}"${r[0] === BL.range ? " selected" : ""}>${r[1]}</option>`).join("")}</select></label></div>
    <div id="blbody" class="mut" role="status">Wird geladen …</div>
    <div id="blhint"></div>
    <div class="utfoot"><button class="btn alt sm" id="bljob" hidden>Uhr-Daten aller Touren laden</button><span class="mut hrnote" id="bljobm" role="status"></span></div></div></div></details>`;
  host.after(d);
  trBind(d);
  const set = () => d.querySelectorAll(".blctl [data-m]").forEach(b => {
    b.classList.toggle("on", b.dataset.m === BL.mode);
    b.setAttribute("aria-pressed", b.dataset.m === BL.mode);
  });
  d.querySelectorAll(".blctl [data-m]").forEach(b => (b.onclick = () => {
    BL.mode = b.dataset.m;
    if (BL.mode === "m" && +BL.range && +BL.range < 12) {
      BL.range = "12";
      d.querySelector("#blrange").value = "12";
    }
    if (BL.mode === "w" && (BL.range === "0" || +BL.range > 12)) {
      BL.range = "6";
      d.querySelector("#blrange").value = "6";
    }
    set();
    blDraw(d);
  }));
  d.querySelector("#blrange").onchange = e => {
    BL.range = e.target.value;
    blDraw(d);
  };
  d.querySelector("#bljob").onclick = () => blJob(d);
  blDraw(d);
}

/* ---------------------------  Dein typisches Tempo  --------------------------- */
const TP_CLS = [["auf_kmh", "Bergauf", "Steigung über 5 %"], ["eben_kmh", "Eben", "Steigung zwischen −5 % und 5 %"], ["ab_kmh", "Bergab", "Gefälle über 5 %"]];

async function tpDraw(root) {
  const box = root.querySelector("#tpbody");
  let d;
  try {
    d = await api("/api/stats/tempo" + (BL.jahr ? "?jahr=" + BL.jahr : ""));
  } catch (e) {
    box.innerHTML = `<p class="mut" role="status">${esc(e.message || "Fehler")}</p>`;
    return;
  }
  if (!root.isConnected) return;
  const sel = root.querySelector("#tpyear");
  if (!sel.dataset.ok) {
    sel.innerHTML = `<option value="0">Alle Jahre</option>` + d.jahre.map(y => `<option value="${y}">${y}</option>`).join("");
    sel.dataset.ok = "1";
  }
  sel.value = String(BL.jahr);
  const e = d.gruppen[BL.sport] || {touren: 0};
  let h = "";
  if (e.touren) {
    h += `<div class="utiles">` + TP_CLS.filter(c => e[c[0]] != null).map(c => `<div class="utile" title="${esc(c[2])}"><b>${nf(e[c[0]], 1)} km/h</b><span class="mut">${c[1]}</span><small class="mut">${e["n_" + c[0]]} Touren</small></div>`).join("") +
      (e.vert_mh != null ? `<div class="utile" title="Steigung über 5 %"><b>${nf(e.vert_mh, 0)} m/h</b><span class="mut">Aufstieg pro Stunde</span><small class="mut">${e.n_vert_mh} Touren</small></div>` : "") + `</div>`;
    h += `<div class="mut hrnote"><span>Median über ${e.touren} Touren (mindestens 2 km, mit Höhendaten).</span> <span>Nur Bewegungszeit: Pausen unter 0,3 km/h sind herausgenommen; die Steigung ist über etwa 50 m geglättet.</span></div>`;
  } else h += `<p class="mut">Keine Touren mit Höhendaten und mindestens 2 km.</p>`;
  if (d.offen) h += `<div class="mut hrnote" role="status">${d.offen} Touren werden noch berechnet …</div>`;
  box.innerHTML = h;
  const tk = root.querySelector("#tpkey");
  if (tk) tk.innerHTML = e.touren ? TP_CLS.filter(c => e[c[0]] != null).map(c => `<span>${c[1]}</span> <b>${nf(e[c[0]], 1)} km/h</b>`).join(" · ") : "";
  if (d.offen && root.isConnected && (root.dataset.retry = +(root.dataset.retry || 0) + 1) <= 40) setTimeout(() => tpDraw(root), 700);
}

async function tpCalc(root) {
  const out = root.querySelector("#tpres"),
    v = id => root.querySelector(id).value.replace(",", ".").trim();
  const km = v("#tpkm"), auf = v("#tpup") || "0", ab = v("#tpdown") || "0";
  if (!km || isNaN(+km) || isNaN(+auf) || isNaN(+ab)) {
    out.textContent = "Bitte Strecke, Aufstieg und Abstieg als Zahlen eingeben.";
    return;
  }
  try {
    const r = await api(`/api/stats/gehzeit?km=${encodeURIComponent(km)}&auf=${encodeURIComponent(auf)}&ab=${encodeURIComponent(ab)}&sport=${BL.sport}${BL.jahr ? "&jahr=" + BL.jahr : ""}`);
    const src = r.quelle === "eigene" ? `Grundlage: deine Werte aus ${r.touren} Touren.` : r.quelle === "teilweise" ? `Teilweise deine Werte (aus ${r.touren} Touren), der Rest sind Standardwerte (Naismith).` : "Noch zu wenig eigene Daten – es gelten Standardwerte (Naismith: 5 km/h, 1 Stunde je 600 m Aufstieg).";
    out.innerHTML = `<div class="tpbig"><span>Geschätzte Gehzeit:</span> <b>${blDur(r.sekunden)}</b></div><div class="mut hrnote"><span>Reine Gehzeit ohne Pausen.</span> <span>${src}</span></div>`;
  } catch (e) {
    out.textContent = e.message || "Fehler";
  }
}

function tpSection(host) {
  const d = document.createElement("div");
  d.id = "tpsec";
  d.innerHTML = `<details class="agrp trf trsec" data-trf="tp_sec"${trOpen("tp_sec", false) ? " open" : ""}><summary><span class="gt">Dein typisches Tempo</span><span class="gs">bergauf, eben, bergab</span><span class="trfk" id="tpkey"></span></summary><div class="gbody"><div class="panel" id="tppanel">
    <div class="row blctl"><div class="chips" role="group" aria-label="Sportart"><button class="chip on" data-s="wandern" aria-pressed="true">Wandern</button><button class="chip" data-s="laufen" aria-pressed="false">Laufen</button></div>
    <label class="blsel"><span class="mut">Jahr</span> <select id="tpyear"><option value="0">Alle Jahre</option></select></label></div>
    <div id="tpbody" class="mut" role="status">Wird geladen …</div>
    <div class="uth">Gehzeit schätzen</div>
    <form class="tpform" id="tpform" novalidate><label>Strecke (km)<input id="tpkm" inputmode="decimal" autocomplete="off" placeholder="z. B. 12,5"></label><label>Aufstieg (m)<input id="tpup" inputmode="numeric" autocomplete="off" placeholder="0"></label><label>Abstieg (m)<input id="tpdown" inputmode="numeric" autocomplete="off" placeholder="0"></label><button class="btn" type="submit">Schätzen</button></form>
    <div id="tpres" role="status" aria-live="polite"></div></div></div></details>`;
  host.after(d);
  trBind(d);
  const set = () => d.querySelectorAll("[data-s]").forEach(b => {
    b.classList.toggle("on", b.dataset.s === BL.sport);
    b.setAttribute("aria-pressed", b.dataset.s === BL.sport);
  });
  d.querySelectorAll("[data-s]").forEach(b => (b.onclick = () => {
    BL.sport = b.dataset.s;
    set();
    d.dataset.retry = 0;
    tpDraw(d);
    d.querySelector("#tpres").innerHTML = "";
  }));
  d.querySelector("#tpyear").onchange = e => {
    BL.jahr = +e.target.value;
    d.dataset.retry = 0;
    tpDraw(d);
    d.querySelector("#tpres").innerHTML = "";
  };
  d.querySelector("#tpform").onsubmit = e => {
    e.preventDefault();
    tpCalc(d);
  };
  tpDraw(d);
}

const _stats46 = VIEWS.stats;
VIEWS.stats = async (...a) => {
  await _stats46(...a);
  if (!TOURS.length || $("#blsec")) return;
  const anchor = $("#main .inner > .panel.gap") || $("#main .inner > .grid");
  if (!anchor) return;
  const [b, t] = await Promise.all([api("/api/stats/belastung?von=" + blDate(new Date(Date.now() - 86400000)) + "&bis=" + blDate(new Date())).catch(() => null), api("/api/stats/tempo").catch(() => null)]);
  if ($("#blsec") || !$("#main .inner")) return;
  let host = anchor;
  const bl = b && (b.daten_insgesamt > 0 || b.offen.zepp_ohne_werte > 0),
    tp = t && Object.values(t.gruppen).some(g => g.touren > 0);
  if (bl) {
    blSection(host);
    host = $("#blsec");
  }
  if (tp || (t && t.offen)) tpSection(host);
};

/* ---------------------------  Tourseite: Tempo nach Steigung  --------------------------- */
async function steigCard(t) {
  const old = $("#steigcard");
  if (old) old.remove();
  if (!t || !$("#profcard")) return;
  let d;
  try {
    d = await api("/api/tours/" + encodeURIComponent(t.id) + "/tempo");
  } catch (e) {
    return;
  }
  if (!d || d.status !== "ok" || $("#steigcard") || !$("#profcard") || !BY[t.id]) return;
  const k = d.klassen,
    tile = (key, lab, tip, extra) => (k[key] ? `<div class="utile" title="${esc(tip)}"><b>${nf(k[key].kmh, 1)} km/h</b><span class="mut">${lab}</span><small class="mut">${extra}</small></div>` : ""),
    km = key => nf(k[key].dist_m / 1000, 1) + " km";
  const tiles = tile("auf", "Bergauf", "Steigung über 5 %", (d.vert_mh != null ? `<span>${nf(d.vert_mh, 0)} m/h Aufstieg</span> · ` : "") + (k.auf ? `<span>${km("auf")}</span>` : "")) +
    tile("eben", "Eben", "Steigung zwischen −5 % und 5 %", k.eben ? km("eben") : "") + tile("ab", "Bergab", "Gefälle über 5 %", k.ab ? km("ab") : "");
  if (!tiles) return;
  const first = k.auf ? "auf" : k.eben ? "eben" : "ab",
    key = [k.auf ? `<span>Bergauf</span> <b>${nf(k.auf.kmh, 1)} km/h</b>${d.vert_mh != null ? ` · <b>${nf(d.vert_mh, 0)} m/h</b>` : ""}` : "", k.eben ? `<span>Eben</span> <b>${nf(k.eben.kmh, 1)} km/h</b>` : "", k.ab ? `<span>Bergab</span> <b>${nf(k.ab.kmh, 1)} km/h</b>` : ""].filter(Boolean).join(" · ");
  const c = document.createElement("div");
  c.id = "steigcard";
  c.className = "panel prof gap trcard";
  c.innerHTML = trFold("steig", "Tempo nach Steigung", key,
    `<div class="utiles">${tiles}</div><div class="mut hrnote"><span>Aus Strecke, Höhe und Zeit berechnet.</span> <span>Nur Bewegungszeit: Pausen unter 0,3 km/h sind herausgenommen; die Steigung ist über etwa 50 m geglättet (bergauf über 5 %, bergab unter −5 %).</span></div>`, false, "trsub trmain");
  trBind(c);
  ($("#uhrcard") || $("#metcard") || $("#pulscard") || $("#profcard")).after(c);
}

const _tour46 = VIEWS.tour;
VIEWS.tour = async (...a) => {
  await _tour46(...a);
  const t = BY[a[0]];
  if (!t) return;
  const tryCard = (n = 0) => {
    if ($("#profcard")) steigCard(t).catch(() => {});
    else if (n < 20) setTimeout(() => tryCard(n + 1), 150);
  };
  tryCard();
};
