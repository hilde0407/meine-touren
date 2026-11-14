/* =====================  „Training laut Uhr“ (Zepp-Uhren): Trainingseffekt, Belastung, Pulszonen, Kilometer-Splits, Wetter  =====================
   Zeigt nur, was die Uhr geliefert hat und was plausibel ist (die Prüfung macht app/uhrtraining.py). Kein Wert, kein Kasten:
   Ohne Daten erscheint der Abschnitt gar nicht. Sitzt direkt hinter dem Abschnitt „Messwerte“. */
const UHR_CACHE = new Map(),
  UHR_ZC = ["#8fb8d8", "#6bb38a", "#c9b63a", "#e2b13c", "#e0803c", "#c0504d"],
  UHR_TILES = [
    ["te", "Trainingseffekt (aerob)", "", 1, "Skala laut Zepp (Rohwert in Zehnteln), nicht mit Garmin vergleichbar"],
    ["ate", "Trainingseffekt (anaerob)", "", 1, "Skala laut Zepp (Rohwert in Zehnteln), nicht mit Garmin vergleichbar"],
    ["last", "Trainingsbelastung", "", 0, "Skala laut Zepp, nicht mit Garmin vergleichbar"],
    ["rpe", "Anstrengung (deine Angabe)", "", 0, "Deine Angabe auf der Uhr, Skala laut Zepp"],
    ["kcal", "Kalorien", "kcal", 0, ""],
    ["schritte", "Schritte", "", 0, ""],
    ["frequenz", "Schrittfrequenz Ø", "Schritte/min", 0, ""],
    ["puls_avg", "Puls Ø", "bpm", 0, ""],
    ["puls_max", "Puls höchster", "bpm", 0, ""],
    ["puls_min", "Puls niedrigster", "bpm", 0, ""],
    ["pause_s", "Pausenzeit", "", 0, "Pausen laut Uhr"],
  ];
/* Einklappbare Abschnitte (3.12.0): <details> mit Kernaussage in der Zeile; offen/zu wird je Abschnitt in localStorage gemerkt (ohne Speicher gilt der Standard) */
const trOpen = (k, def) => {
  try {
    const v = localStorage.getItem("mt_trf_" + k);
    return v === null ? def : v === "1";
  } catch (e) {
    return def;
  }
};
const trFold = (k, title, key, body, def, cls) =>
  `<details class="trf ${cls || "trsub"}" data-trf="${k}"${trOpen(k, def) ? " open" : ""}><summary><span class="trft">${title}</span>${key ? `<span class="trfk">${key}</span>` : ""}</summary><div class="trfb">${body}</div></details>`;
function trBind(root) {
  root.querySelectorAll("details[data-trf]").forEach(d => {
    d.ontoggle = () => {
      try {
        localStorage.setItem("mt_trf_" + d.dataset.trf, d.open ? "1" : "0");
      } catch (e) {}
    };
  });
}
const uhrData = (id, fresh) => {
  if (fresh || !UHR_CACHE.has(id)) UHR_CACHE.set(id, api("/api/tours/" + encodeURIComponent(id) + "/uhr-training").catch(() => null));
  return UHR_CACHE.get(id);
};
const uhrHas = u => !!u && (Object.keys(u.werte || {}).length || (u.pulszonen && u.pulszonen.length) || (u.splits && u.splits.length) || u.wetter);
const uhrMin = s => (s >= 3600 ? Math.floor(s / 3600) + " h " + pad2(Math.round((s % 3600) / 60)) + " min" : Math.max(1, Math.round(s / 60)) + " min");

function uhrTiles(w) {
  return UHR_TILES.filter(k => w[k[0]] != null)
    .map(k => {
      const v = w[k[0]].wert;
      const val = k[0] === "pause_s" ? uhrMin(v) : nf(v, k[3]);
      return `<div class="utile"${k[4] ? ` title="${esc(k[4])}"` : ""}><b>${val}</b><span class="mut">${esc(k[1])}</span>${k[2] ? `<small class="mut">${esc(k[2])}</small>` : ""}</div>`;
    })
    .join("");
}

function uhrHeights(w) {
  const it = [];
  if (w.aufstieg) it.push(`<div><b>${nf(w.aufstieg.wert, 0)}</b> <span class="mut">m Aufstieg</span></div>`);
  if (w.abstieg) it.push(`<div><b>${nf(w.abstieg.wert, 0)}</b> <span class="mut">m Abstieg</span></div>`);
  if (w.hoehe_max) it.push(`<div><b>${nf(w.hoehe_max.wert, 0)}</b> <span class="mut">m höchster Punkt</span></div>`);
  if (w.hoehe_min) it.push(`<div><b>${nf(w.hoehe_min.wert, 0)}</b> <span class="mut">m tiefster Punkt</span></div>`);
  return it.length ? `<div class="uth">Höhenmeter laut Uhr</div><div class="utline fxw mb8 fx hrkpi">${it.join("")}</div>` : "";
}

function uhrZones(z) {
  if (!z || !z.length) return "";
  const bar = z.map((x, i) => `<span class="uz${(i % UHR_ZC.length) + 1}" data-f="${Math.max(x.sekunden, 0.001)}" title="Zone ${x.zone}: ${uhrMin(x.sekunden)}"></span>`).join("");
  const leg = z.map((x, i) => `<span class="nw"><i class="br2 mr5 utsw uz${(i % UHR_ZC.length) + 1}"></i><span>Zone</span> ${x.zone}: ${uhrMin(x.sekunden)} (${Math.round(x.anteil * 100)} %) <span class="mut">· <span>bis</span> ${x.bis_bpm} bpm</span></span>`).join("");
  return `<div class="uth">Pulszonen laut Uhr</div><div class="br6 ovh m12-0-8 fx h12" role="img" aria-label="Pulszonen laut Uhr">${bar}</div><div class="mut g6-16 fxw fx hrleg">${leg}</div>`;
}

function uhrSplits(sp) {
  if (!sp || sp.length < 2) return "";
  const mx = Math.max(...sp.map(s => s.min_km)),
    hasP = sp.some(s => s.puls != null),
    hasS = sp.some(s => s.schritte != null),
    part = sp.some(s => s.strecke_m < 1000);
  let h = `<div class="uth">Tempo je Kilometer</div><div class="utsp"><div class="utgrid" data-n="${sp.length}">`;
  const row = (lab, cells) => `<div class="utl">${lab}</div>` + cells.join("");
  const title = s =>
    (s.strecke_m < 1000 ? `Letztes Teilstück (${nf(s.strecke_m / 1000, 1)} km): ${metPace(s.min_km)} min/km` : `Kilometer ${s.km}: ${metPace(s.min_km)} min/km`) +
    (s.puls != null ? `, Puls ${s.puls} bpm` : "") + (s.schritte != null ? `, ${s.schritte} Schritte/min` : "");
  h += row("", sp.map(s => `<div class="utv">${metPace(s.min_km)}</div>`));
  h += row(`<span>min/km</span>`, sp.map(s => `<div class="utc${s.strecke_m < 1000 ? " part" : ""}" title="${esc(title(s))}" tabindex="0" role="img" aria-label="${esc(title(s))}"><i data-h="${Math.max(3, (s.min_km / mx) * 100).toFixed(1)}"></i></div>`));
  h += row(`<span>Kilometer</span>`, sp.map(s => `<div class="utk">${s.strecke_m < 1000 ? nf(s.strecke_m / 1000, 1) + " km" : s.km}</div>`));
  if (hasP) h += row(`<span>Puls (bpm)</span>`, sp.map(s => `<div class="utp">${s.puls != null ? s.puls : "–"}</div>`));
  if (hasS) h += row(`<span>Schritte/min</span>`, sp.map(s => `<div class="utp">${s.schritte != null ? s.schritte : "–"}</div>`));
  h += `</div></div><div class="mut hrnote"><span>Kürzere Balken = schneller.</span>${part ? ` <span>Der hellere Balken ist das letzte Teilstück (kürzer als ein Kilometer).</span>` : ""}</div>`;
  return h;
}

const UHR_ERM = {
  gleichmaessig: "Gleichmäßiges Tempo – kaum Ermüdung zu sehen.",
  leicht_langsamer: "Leicht langsamer in der zweiten Hälfte.",
  spuerbar_langsamer: "Spürbar langsamer in der zweiten Hälfte.",
  deutlich_langsamer: "Deutlich langsamer in der zweiten Hälfte.",
  schneller: "Schneller in der zweiten Hälfte (negativer Split).",
};
const uhrSign = n => (n > 0 ? "+" : n < 0 ? "−" : "±") + Math.abs(n);

/* Ermüdungsverlauf: Tempo und Puls der ersten gegen die zweite Hälfte (Berechnung und Schwellen in app/uhrtraining.py) */
function uhrFatigue(e) {
  if (!e) return "";
  const cmp = `<span>${e.k === 1 ? "Verglichen werden der erste und der letzte volle Kilometer" : `Verglichen werden die ersten ${e.k} und die letzten ${e.k} vollen Kilometer`}</span>${e.km % 2 ? " <span>(der mittlere Kilometer bleibt außen vor)</span>" : ""}`;
  if (e.status === "nur_hinweis") {
    const a = e.hoehen.erste, b = e.hoehen.zweite;
    return trFold("uhr_erm", "Ermüdungsverlauf", `<b>Zweite Hälfte:</b> <span>nicht bewertet</span>`,
      `<div class="mut hrnote utfat"><span>Bergauf-Anteil nicht herausgerechnet:</span> <span>Die Hälften unterscheiden sich stark in den Höhenmetern.</span> <span>Erste Hälfte ${nf(a.auf, 0)} m bergauf, zweite Hälfte ${nf(b.auf, 0)} m bergauf.</span></div>`, false);
  }
  const p = e.tempo_pct,
    tempo = p === 0 ? "Tempo unverändert" : p > 0 ? `Tempo ${nf(p, 0)} % langsamer` : `Tempo ${nf(-p, 0)} % schneller`,
    key = `<b>Zweite Hälfte:</b> <span>${tempo}</span>${e.puls_diff != null ? ` · <span>Puls ${uhrSign(e.puls_diff)} bpm</span>` : ""}`,
    body = `<div class="utfat">${UHR_ERM[e.stufe]}${e.puls === "steigt" ? ` <span>Der Puls stieg im Verlauf an.</span>` : e.puls === "sinkt" ? ` <span>Der Puls sank im Verlauf.</span>` : ""}</div>` +
      `<div class="mut hrnote utfat">${cmp}. <span>Die Einordnung in Worten beruht auf groben Schwellen (3, 8 und 15 %).</span>${e.hoehen_geprueft ? "" : " <span>Höhenunterschiede der Hälften konnten nicht geprüft werden (keine Höhendaten).</span>"}</div>`;
  return trFold("uhr_erm", "Ermüdungsverlauf", key, body, false);
}

function uhrWeather(w) {
  if (!w) return "";
  const it = [];
  if (w.temp_c != null) it.push(`<div><b>${nf(w.temp_c, Number.isInteger(w.temp_c) ? 0 : 1)}</b> <span class="mut">°C Temperatur</span></div>`);
  if (w.feuchte_pct != null) it.push(`<div><b>${nf(w.feuchte_pct, 0)}</b> <span class="mut">% Luftfeuchte</span></div>`);
  return it.length ? `<div class="uth">Wetter laut Uhr</div><div class="utline fxw mb8 fx hrkpi">${it.join("")}</div>` : "";
}

async function uhrCard(t) {
  const old = $("#uhrcard");
  if (old) old.remove();
  if (!t || !$("#profcard")) return;
  const u = await uhrData(t.id);
  if (!u || !uhrHas(u) || $("#uhrcard") || !$("#profcard") || !BY[t.id]) return;
  const d = document.createElement("div");
  d.className = "panel prof gap";
  d.id = "uhrcard";
  ($("#metcard") || $("#pulscard") || $("#profcard")).after(d);
  let busy = false,
    msg = "";
  const draw = () => {
    const dv = u.device || {name: "Amazfit/Zepp", kind: "zepp"},
      ge = u.geladen ? new Date(u.geladen * 1000).toLocaleDateString("de-DE") : "";
    d.innerHTML = `<h2>Training laut Uhr</h2>` +
      `<div class="mut hrnote utsrc"><span class="dvsrc">${typeof dvAvatar === "function" ? dvAvatar(dv, "xs") : ""}<span>Quelle:</span> <span>${esc(dv.name)}</span></span>${ge ? ` · <span>geladen am</span> ${ge}` : ""}</div>` +
      (u.werte && Object.keys(u.werte).length ? `<div class="utiles">${uhrTiles(u.werte)}</div>` : "") +
      uhrHeights(u.werte || {}) + uhrZones(u.pulszonen) + uhrSplits(u.splits) + uhrFatigue(u.ermuedung) + uhrWeather(u.wetter) +
      (u.hinweise && u.hinweise.length ? `<ul class="mut hrnote utnotes">${u.hinweise.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : "") +
      `<div class="utfoot">${typeof isViewer === "function" && isViewer() ? "" : `<button class="btn alt sm" id="utneu" ${busy ? "disabled" : ""}>${busy ? "Lade von Zepp …" : "Von Zepp neu laden"}</button>`}<span class="mut hrnote" id="utmsg" role="status">${esc(msg)}</span></div>`;
    trBind(d);
    d.querySelectorAll("[data-f]").forEach(e => (e.style.flex = e.dataset.f));
    d.querySelectorAll("[data-h]").forEach(e => (e.style.height = e.dataset.h + "%"));
    d.querySelectorAll("[data-n]").forEach(e => e.style.setProperty("--n", e.dataset.n));
    const b = $("#utneu");
    if (b) b.onclick = async () => {
      busy = true; msg = ""; draw();
      try {
        const r = await api("/api/tours/" + encodeURIComponent(t.id) + "/uhr-training/neu", METJ({}));
        Object.assign(u, r);
        UHR_CACHE.set(t.id, Promise.resolve(u));
        msg = r.status === "ok" ? "Neu von Zepp geladen." : r.meldung || "";
      } catch (e) {
        msg = e.message || "Fehler";
      }
      busy = false;
      if (!uhrHas(u)) return d.remove();
      draw();
    };
  };
  draw();
}

const _tour45 = VIEWS.tour;
VIEWS.tour = async (...a) => {
  await _tour45(...a);
  const t = BY[a[0]];
  if (!t) return;
  UHR_CACHE.delete(t.id);
  const tryCard = (n = 0) => {
    if ($("#profcard")) uhrCard(t).catch(() => {});
    else if (n < 20) setTimeout(() => tryCard(n + 1), 150);
  };
  tryCard();
};
