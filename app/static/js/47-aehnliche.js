/* =====================  3.14.0: „Ähnliche Touren im Vergleich“ (Tourseite)  =====================
   Zeigt frühere und spätere Wiederholungen derselben Strecke (erkannt von app/wiederholungen.py, berechnet von app/aehnliche.py): je Lauf Datum, Dauer,
   Strecke, Aufstieg, Durchschnittstempo, Abweichung zur geöffneten Tour und Gerät, dazu einen kleinen Tempo-Verlauf und eine Kurzaussage.
   Ohne Wiederholung erscheint nichts. Fehlt einem Lauf Zeit oder Strecke, steht „–“ (nie 0). Einklappbar wie die anderen Abschnitte (trFold, Zustand in localStorage).
   Farben: nur vorhandene Variablen (--bars für andere Läufe, --accent2 für die geöffnete Tour), Text immer in Textfarben. */
const aeDur = s => {
  if (s == null) return "–";
  const m = Math.round(s / 60);
  return m >= 60 ? Math.floor(m / 60) + " h " + pad2(m % 60) + " min" : Math.max(1, m) + " min";
};
const aeSign = v => (v > 0 ? "+" : v < 0 ? "−" : "±");
function aeClock(s) {                                    // Abweichung der Dauer als mm:ss bzw. h:mm:ss
  const a = Math.abs(Math.round(s)), h = Math.floor(a / 3600), m = Math.floor((a % 3600) / 60), x = a % 60;
  return aeSign(s) + (h ? h + ":" + pad2(m) + ":" + pad2(x) : m + ":" + pad2(x));
}
/* Eine Zelle: Beschriftung, Wert, darunter die Abweichung zur geöffneten Tour (Zahl und Wort getrennt, damit beide übersetzt werden) */
function aeCell(label, val, delta) {
  return `<div class="aec"><span class="aecl">${label}</span><b>${val}</b>${delta ? `<small class="aed"><i>${delta[0]}</i> <span>${delta[1]}</span></small>` : ""}</div>`;
}
function aeDeltas(r) {
  const a = r.abweichung || {}, o = {};
  if (a.dauer_s != null) o.dauer = a.dauer_s === 0 ? ["±0:00", "gleich"] : [aeClock(a.dauer_s), a.dauer_s > 0 ? "länger" : "kürzer"];
  if (a.strecke_m != null) o.strecke = Math.abs(a.strecke_m) < 50 ? ["±0,0 km", "gleich"] : [aeSign(a.strecke_m) + nf(Math.abs(a.strecke_m) / 1000, 1) + " km", a.strecke_m > 0 ? "länger" : "kürzer"];
  if (a.auf_m != null) o.auf = a.auf_m === 0 ? ["±0 m", "gleich"] : [aeSign(a.auf_m) + nf(Math.abs(a.auf_m), 0) + " m", a.auf_m > 0 ? "mehr" : "weniger"];
  if (a.tempo_pct != null) o.tempo = Math.round(a.tempo_pct) === 0 ? ["±0 %", "gleich"] : [aeSign(a.tempo_pct) + nf(Math.abs(a.tempo_pct), 0) + " %", a.tempo_pct > 0 ? "schneller" : "langsamer"];
  return o;
}
function aeRow(r, bestId) {
  const dl = r.aktuell ? {} : aeDeltas(r),
    head = r.aktuell ? `<span class="aedt">${esc(dateS(r.datum))}</span>` : `<a class="aedt" href="#/tour/${encodeURIComponent(r.id)}">${esc(dateS(r.datum))}</a>`,
    tags = (r.aktuell ? `<span class="aetag cur">Diese Tour</span>` : "") + (r.id === bestId ? `<span class="aetag">Schnellster Lauf</span>` : ""),
    sub = [r.name ? `<span>${esc(r.name)}</span>` : "", r.geraet ? `<span class="aedev">${esc(r.geraet)}</span>` : ""].filter(Boolean).join(" · ");
  return `<li class="aer${r.aktuell ? " cur" : ""}"><div class="aeh">${head}${tags}</div>${sub ? `<div class="aesub">${sub}</div>` : ""}<div class="aem">` +
    aeCell("Dauer", aeDur(r.dauer_s), dl.dauer) + aeCell("Strecke", r.strecke_m == null ? "–" : nf(r.strecke_m / 1000, 1) + " km", dl.strecke) +
    aeCell("Aufstieg", r.auf_m == null ? "–" : nf(r.auf_m, 0) + " m", dl.auf) + aeCell("Tempo", r.tempo_kmh == null ? "–" : nf(r.tempo_kmh, 1) + " km/h", dl.tempo) + `</div></li>`;
}
/* Kurzaussage: [fett, Zusatz] – der Text steht in der Zeile des Abschnitts und im Kopf des Inhalts */
function aeSaid(a) {
  if (!a) return null;
  if (a.art === "bestes_bisher") return "Bestes Tempo bisher";
  if (a.art === "erster") return "Erster Lauf dieser Strecke";
  if (a.art === "langsamer_als_alle") return a.frueher === 1 ? "Langsamer als der frühere Lauf" : `Langsamer als alle ${a.frueher} früheren Läufe`;
  return `Schneller als ${a.schneller_als} von ${a.frueher} früheren Läufen`;
}
function aeLater(a) {
  if (!a || !a.spaeter) return "";
  if (a.spaeter === 1) return a.spaeter_schneller ? "Der spätere Lauf war schneller." : "Der spätere Lauf war nicht schneller.";
  if (!a.spaeter_schneller) return `Keiner der ${a.spaeter} späteren Läufe war schneller.`;
  return `Von ${a.spaeter} späteren Läufen waren ${a.spaeter_schneller} schneller.`;
}
/* Verlauf: Linie mit Punkten, ein Punkt je Lauf in zeitlicher Reihenfolge, Abstand gleichmäßig; die geöffnete Tour ist größer und in der Akzentfarbe */
function aeChart(rows, bestId, width) {
  const pts = rows.filter(r => r.tempo_kmh != null);
  if (pts.length < 2) return "";
  const L = 44, R = 16, T = 30, B = 28, H = 176, n = pts.length,
    W = Math.max(width, L + R + n * 46),
    vs = pts.map(r => r.tempo_kmh), lo0 = Math.min(...vs), hi0 = Math.max(...vs),
    pad = Math.max((hi0 - lo0) * 0.3, 0.4), lo = Math.max(0, Math.floor((lo0 - pad) * 2) / 2), hi = Math.ceil((hi0 + pad) * 2) / 2,
    y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo)),
    slot = (W - L - R) / n, x = i => L + slot * (i + 0.5),
    years = pts.map(r => r.datum.slice(0, 4)), dupYear = new Set(years).size !== years.length,
    lab = r => (dupYear ? r.datum.slice(5, 7) + "/" + r.datum.slice(2, 4) : r.datum.slice(0, 4)),
    step = Math.max(1, Math.ceil(48 / slot)), all = n <= 8;
  let g = "";
  [lo, (lo + hi) / 2, hi].forEach(v => (g += `<line class="aegrid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text x="${L - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${nf(v, 1)}</text>`));
  g += `<text x="${L - 6}" y="12" text-anchor="end">km/h</text>`;
  g += `<polyline class="aeline" points="${pts.map((r, i) => x(i).toFixed(1) + "," + y(r.tempo_kmh).toFixed(1)).join(" ")}"/>`;
  pts.forEach((r, i) => {
    const cx = x(i).toFixed(1), cy = y(r.tempo_kmh).toFixed(1), show = r.aktuell || all || r.id === bestId;
    if (i % step === 0 || r.aktuell) g += `<text x="${cx}" y="${H - 8}" text-anchor="middle"${r.aktuell ? ' class="aeval"' : ""}>${esc(lab(r))}</text>`;
    g += `<g class="aept"><title>${esc(dateS(r.datum) + ": " + nf(r.tempo_kmh, 1) + " km/h")}</title><circle class="aedot${r.aktuell ? " cur" : ""}" cx="${cx}" cy="${cy}" r="${r.aktuell ? 8 : 5}"/>` +
      (show ? `<text class="${r.aktuell ? "aeval" : ""}" x="${cx}" y="${(y(r.tempo_kmh) - (r.aktuell ? 14 : 11)).toFixed(1)}" text-anchor="middle">${nf(r.tempo_kmh, 1)}</text>` : "") + `</g>`;
  });
  return `<div class="aescroll"><svg class="aesvg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Liniendiagramm: Durchschnittstempo der Läufe über die Zeit">${g}</svg></div>` +
    `<div class="legend aelegend"><span><i class="aelg"></i>Andere Läufe</span><span><i class="aelg cur"></i>Diese Tour</span></div>`;
}
function aeDrawChart(card, d) {
  const box = card.querySelector(".aechart");
  if (!box || !box.clientWidth) return;
  const w = box.clientWidth;
  if (box.dataset.w === String(w)) return;
  box.dataset.w = w;
  box.innerHTML = aeChart(d.touren, d.bestes_id, w - 2);
}
async function aeCard(t) {
  const old = $("#aehncard");
  if (old) old.remove();
  if (!t || !$("#profcard")) return;
  let d;
  try {
    d = await api("/api/tours/" + encodeURIComponent(t.id) + "/aehnliche");
  } catch (e) {
    return;
  }
  let cur = "";
  try {
    cur = decodeURIComponent((location.hash.split("?")[0].split("/")[2]) || "");
  } catch (e) {}
  if (!d || d.status !== "ok" || $("#aehncard") || !$("#profcard") || !BY[t.id] || cur !== String(t.id)) return;
  const a = d.aussage, said = aeSaid(a), n = d.anzahl - 1,
    key = (said ? `<b>${said}</b> · ` : "") + `<span>${n === 1 ? "1 Wiederholung" : n + " Wiederholungen"}</span>`,
    nowT = d.touren.find(r => r.aktuell),
    rows = d.touren.slice().reverse(),
    later = aeLater(a),
    note = nowT && nowT.tempo_kmh == null ? `<p class="mut hrnote">Für diese Tour fehlen Zeit oder Strecke – deshalb gibt es keinen Tempovergleich.</p>` : "",
    body = (later ? `<div class="aesaid">${later}</div>` : "") + note +
      `<div class="aechart" aria-live="off"></div><ul class="aelist">${rows.map(r => aeRow(r, d.mit_tempo > 1 ? d.bestes_id : null)).join("")}</ul>` +
      `<div class="mut hrnote"><span>Als Wiederholung gilt, wer weitgehend denselben Weg nimmt (dieselbe Erkennung wie das 🔁 in der Tourenliste).</span> <span>Tempo = Strecke geteilt durch die gesamte Dauer, Pausen eingeschlossen.</span> <span>Die Abweichung vergleicht jeden Lauf mit dieser Tour.</span></div>`;
  const c = document.createElement("div");
  c.id = "aehncard";
  c.className = "panel prof gap trcard";
  c.innerHTML = trFold("aehn", "Ähnliche Touren im Vergleich", key, body, false, "trsub trmain");
  trBind(c);
  const det = c.querySelector("details");
  const draw = () => det.open && aeDrawChart(c, d);
  det.addEventListener("toggle", draw);
  if (typeof ResizeObserver === "function") {
    const ro = new ResizeObserver(() => (c.isConnected ? draw() : ro.disconnect()));
    ro.observe(c);
  }
  ($("#steigcard") || $("#uhrcard") || $("#metcard") || $("#pulscard") || $("#profcard")).after(c);
  draw();
}

const _tour47 = VIEWS.tour;
VIEWS.tour = async (...a) => {
  await _tour47(...a);
  const t = BY[a[0]];
  if (!t) return;
  const tryCard = (n = 0) => {
    if ($("#profcard")) aeCard(t).catch(() => {});
    else if (n < 20) setTimeout(() => tryCard(n + 1), 150);
  };
  tryCard();
};
