/* =====================  3.23.0 Hinweis-Bausteine („Alarm-Bausteine“)  =====================
   Bausteine, die NUR erscheinen, wenn etwas los ist. Ist nichts los, ist der Baustein im normalen Modus unsichtbar (display:none, belegt keinen Platz im Raster) und im Bearbeitungsmodus
   ein gestrichelter Platzhalter „Wird nur angezeigt, wenn …“. Gleiches Muster wie 50-bausteine.js (Katalog, tlCard-Kopf, Zahnrad je Instanz, Raster-Breite), alles Weitere (Ansichten, Vorlagen,
   Export) läuft über die Layout-Engine.
   Gerechnet wird NUR im Server (GET /api/bausteine/hinweise, app/hinweise.py – dort die Regeln und die Referenz); die Oberfläche baut aus den Zahlen die Texte (vier Sprachen, je Satz ein Textknoten).
   Zustand der Karte: data-hn = lade | aus | an (style.css „3.23.0“). Ausblenden („Snooze“): cfg.snoozes = ["Art:Sekunden seit 1970"] im Layout-Dokument der Instanz, abgelaufen = wieder sichtbar.
   Typen: hnmeilenstein, hnauffaellig, hnpause, hnrekord, hnerholung, hnsicherung und die Sammel-Variante „hinweise“ (alle aktiven Hinweise gebündelt, Auswahl der Arten im Zahnrad).
   3.45.0: „Jahresziel in Gefahr“ (hnziel) und „Wochenziel“ (hnwoche) sind jetzt der Baustein „Ziele“ mit der Darstellung „Nur Warnung“ bzw. „Balken“ (unten registriert, Code in
   52-bausteine-uebersicht.js); die Arten „ziel“ und „woche“ gibt es weiter im Sammel-Baustein. Wochenziele stehen in den Zielen der Statistik, nicht mehr im Baustein. */
Object.assign(TL_ICON, {
  flag: '<path d="M5 21V4"/><path d="M5 4h12l-2.5 4.5L17 13H5"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  trophy: '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 6H4.5c0 3 1.5 4.5 3.5 4.5M16 6h3.5c0 3-1.5 4.5-3.5 4.5"/><path d="M12 13v4M8.5 20h7"/>',
  cal: '<rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M4 10h16M9 3.5v4M15 3.5v4"/>',
  shield: '<path d="M12 3l7 3v5.5c0 4.4-2.9 7.7-7 9.5-4.1-1.8-7-5.1-7-9.5V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
  bell: '<path d="M6 17V11a6 6 0 0 1 12 0v6l1.5 2h-15z"/><path d="M10 21h4"/>',
});
SL_CATS.push(["hinweise", "Hinweise"]);

/* Schweregrad: Symbol (Form unterscheidet sich), Wort und Farbe (CSS-Variablen) – nie nur Farbe */
const HN_STUFE = {
  info: ["Info", '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><circle cx="12" cy="7.8" r=".6"/>'],
  hinweis: ["Hinweis", '<rect x="4" y="4" width="16" height="16" rx="4"/><path d="M12 8v5"/><circle cx="12" cy="16.3" r=".6"/>'],
  warnung: ["Warnung", '<path d="M12 3.5l9.5 16.5h-19z"/><path d="M12 10v4.5"/><circle cx="12" cy="17.4" r=".6"/>'],
};
const hnIcon = s => `<svg class="hnsi" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${HN_STUFE[s][1]}</svg>`;
const HN_ARTEN = ["ziel", "meilenstein", "auffaellig", "pause", "rekord", "woche", "erholung", "sicherung"];
const HN_SAMMEL = HN_ARTEN.filter(a => a !== "woche");                                             // Standardauswahl des Sammel-Bausteins (wie bisher ohne Wochenziel; das Wochenziel steht seit 3.45.0 in den Zielen der Statistik)
const HN_AUS = [[0, "Nicht anbieten"], [1, "1 Tag"], [3, "3 Tage"], [7, "7 Tage"], [14, "14 Tage"], [30, "30 Tage"]];
const HN = {pending: new Map(), focus: null};
const hnPl = (n, one, many) => (n === 1 ? one : many);
const hnTours = n => (n === 1 ? "1 Tour" : `${fmtAnzahl(n, "Tour", "Touren")}`);
const hnVal = (m, x) => (m === "km" ? `${fmtKm(x, {d: 0})}` : m === "up" ? `${fmtHm(x)}` : m === "hours" ? fmtDauer(x * 3600, {summe: true}) : hnTours(Math.round(x)));
const hnMetric = {km: "Strecke", up: "Aufstieg", count: "Touren", hours: "Dauer"};
const hnNum = x => nf(x, x % 1 ? 1 : 0);
const hnNow = () => Math.floor(Date.now() / 1000);
const hnSnoozeTs = (cfg, art) => {
  const e = ((cfg && cfg.snoozes) || []).find(x => typeof x === "string" && x.startsWith(art + ":"));
  return e ? +e.slice(art.length + 1) || 0 : 0;
};
const hnSnoozed = (cfg, art) => hnSnoozeTs(cfg, art) > hnNow();
const hnTrLink = (href, txt) => `<a href="${href}">${txt}</a>`;
const hnTour = t => `<a href="#/tour/${slEnc(t.tour)}">${esc(t.name || "Tour")}</a>`;
const hnAdminLink = tab => (typeof isAdmin === "function" && isAdmin() ? `<a href="#/admin?tab=${tab}">${tab === "sicher" ? "Zur Sicherung ›" : "In der Verwaltung ansehen ›"}</a>` : "");

/* ---- Abfrage: je Art die Server-Parameter aus der Konfiguration (Sammel-Baustein: Standardwerte, nur das Wochenziel ist einstellbar) ---- */
function hnQuery(arts, cfg, sammel) {
  const q = new URLSearchParams(), c = cfg || {};
  q.set("arten", arts.join(","));
  if (c.sports && c.sports.length) q.set("sport", c.sports.join(","));
  const set = (k, v) => v !== undefined && v !== null && v !== "" && q.set(k, String(v));
  if (!sammel) {
    set("ziel_schwelle", c.schwelle);
    set("meilenstein_tage", c.tage);
    set("auffaellig_min", c.min);
    set("pause_tage", c.tage);
    set("rekord_tage", c.tage);
    set("erholung_stufe", c.stufe);
    set("sicherung_tage", c.tage);
  }
  return q.toString();
}
/* Gleiche Abfragen gleichzeitig (mehrere Bausteine beim Aufbau der Seite) teilen sich einen Aufruf; nichts wird länger gemerkt, der Server hat den kurzen Zwischenspeicher */
function hnGet(qs) {
  if (!HN.pending.has(qs)) {
    const p = api("/api/bausteine/hinweise?" + qs);
    HN.pending.set(qs, p);
    const done = () => HN.pending.delete(qs);
    p.then(done, done);
  }
  return HN.pending.get(qs);
}

/* ---- Texte der Arten: je Art Titel, Bedingung (Platzhalter), Inhalt (HTML aus den Server-Werten), Link, Kurzaussage ---- */
const hnRows = rows => `<ul class="hnrows">${rows.join("")}</ul>`;
const HN_ART = {
  ziel: {
    name: "Jahresziel in Gefahr", icon: "flag", wtype: "", seiten: ["uebersicht", "statistik"], defaults: {schwelle: 10, ausblenden: 7},          // 3.45.0: nur noch als Art (Baustein „Ziele“, Darstellung „Nur Warnung“)
    desc: "Erscheint nur, wenn die Prognose zum Jahresende deutlich unter einem deiner Jahresziele liegt. Sonst ist der Baustein unsichtbar.",
    sample: ["warnung", "Prognose 780 km bei einem Ziel von 1.000 km (22 % darunter)."],
    fields: [{k: "schwelle", kind: "number", label: "Schwelle: Prognose liegt um mehr als so viele Prozent unter dem Ziel", min: 1, max: 90, step: 1, int: true}, {kind: "sports", label: "Sportart (nur Ziele, die sie betreffen)"}],
    cond: c => [`Wird nur angezeigt, wenn die Prognose zum Jahresende um mehr als ${hnNum(c.schwelle ?? 10)}\u00a0% unter einem deiner Jahresziele liegt.`, "Voraussetzung: ein Jahresziel (Statistik → Ziele); die Prognose gibt es ab dem 14. Tag des Jahres."],
    body(h) {
      const L = h.daten.ziele, more = L.length - 3;
      return hnRows(L.slice(0, 3).map(z => `<li><b>${hnMetric[z.metrik]}</b>${z.sport ? ` <span class="mut">${esc(goalSportName(z.sport))}</span>` : ""}<span class="hnt">Prognose ${hnVal(z.metrik, z.prognose)} bei einem Ziel von ${hnVal(z.metrik, z.ziel)} (${nf(z.abweichung_pct, 0)}\u00a0% darunter).</span></li>`)) +
        (more > 0 ? `<p class="mut hnmore">${more === 1 ? "Dazu 1 weiteres Ziel." : `Dazu ${more} weitere Ziele.`}</p>` : "");
    },
    link: () => hnTrLink("#/stats", "Zu den Zielen ›"),
    badge: h => `${nf(h.daten.ziele[0].abweichung_pct, 0)}\u00a0% darunter`,
  },
  meilenstein: {
    name: "Meilenstein erreicht", icon: "pin", wtype: "hnmeilenstein", seiten: ["uebersicht", "statistik"], defaults: {tage: 7, ausblenden: 7},
    desc: "Erscheint nur, wenn du kürzlich eine runde Marke überschritten hast: 100, 250, 500, 1.000 … Kilometer, 10.000 m Aufstieg oder die 25., 50. und 100. Tour.",
    sample: ["info", "1.000 km insgesamt überschritten"],
    fields: [{k: "tage", kind: "number", label: "Zeitraum in Tagen (so lange nach dem Überschreiten bleibt der Hinweis)", min: 1, max: 365, step: 1, int: true}, {kind: "sports"}],
    cond: c => [(c.tage ?? 7) === 1 ? "Wird nur angezeigt, wenn du heute oder gestern eine runde Marke überschritten hast: 100, 250, 500, 1.000 … Kilometer, 10.000 m Aufstieg oder die 25., 50., 100. Tour."
      : `Wird nur angezeigt, wenn du in den letzten ${nf(c.tage ?? 7, 0)} Tagen eine runde Marke überschritten hast: 100, 250, 500, 1.000 … Kilometer, 10.000 m Aufstieg oder die 25., 50., 100. Tour.`],
    body: h => hnRows(h.daten.marken.slice(0, 3).map(m => `<li><b>${m.typ === "km" ? `${fmtKm(m.wert, {d: 0})} insgesamt überschritten` : m.typ === "hm" ? `${nf(m.wert, 0)}\u00a0m Aufstieg insgesamt überschritten` : `${nf(m.wert, 0)}. Tour erreicht`}</b> ${hnTour(m)} <span class="mut">${fmtDatumKurz(m.datum)}</span></li>`)),
    link: () => "",
    badge: h => (h.daten.marken[0].typ === "km" ? `${fmtKm(h.daten.marken[0].wert, {d: 0})}` : h.daten.marken[0].typ === "hm" ? `${fmtHm(h.daten.marken[0].wert)}` : `${nf(h.daten.marken[0].wert, 0)}. Tour`),
  },
  auffaellig: {
    name: "Neue Auffälligkeiten", icon: "watch", wtype: "hnauffaellig", seiten: ["uebersicht"], defaults: {min: 1, ausblenden: 7},
    desc: "Erscheint nur, wenn Touren in der Genauigkeitsliste der Geräte auffällig sind und noch nicht als geprüft markiert wurden, mit Zähler und Link zur Verwaltung.",
    sample: ["hinweis", "3 Touren sind auffällig und noch nicht geprüft."],
    fields: [{k: "min", kind: "number", label: "Mindestanzahl auffälliger Touren", min: 1, max: 1000, step: 1, int: true}],
    cond: c => [(c.min ?? 1) === 1 ? "Wird nur angezeigt, wenn mindestens eine Tour in der Genauigkeitsliste auffällig und noch nicht als geprüft markiert ist."
      : `Wird nur angezeigt, wenn mindestens ${fmtAnzahl(c.min, "Tour", "Touren")} in der Genauigkeitsliste auffällig und noch nicht als geprüft markiert sind.`],
    body: h => `<p class="hnt">${h.daten.anzahl === 1 ? "1 Tour ist auffällig und noch nicht geprüft." : `${nf(h.daten.anzahl, 0)} Touren sind auffällig und noch nicht geprüft.`}</p>`,
    link: () => hnAdminLink("quellen"),
    badge: h => String(h.daten.anzahl),
  },
  pause: {
    name: "Lange Pause", icon: "clock", wtype: "hnpause", seiten: ["uebersicht"], defaults: {tage: 14, ausblenden: 7},
    desc: "Erscheint nur, wenn seit einer einstellbaren Zahl von Tagen keine Tour mehr gemacht wurde, auf Wunsch nur für eine Sportart.",
    sample: ["info", "Seit 20 Tagen keine Tour."],
    fields: [{k: "tage", kind: "number", label: "Pause ab so vielen Tagen", min: 1, max: 365, step: 1, int: true}, {kind: "sports"}],
    cond: c => [(c.tage ?? 14) === 1 ? "Wird nur angezeigt, wenn seit mindestens einem Tag keine Tour mehr gemacht wurde." : `Wird nur angezeigt, wenn seit mindestens ${nf(c.tage ?? 14, 0)} Tagen keine Tour mehr gemacht wurde.`],
    body: h => `<p class="hnt">${h.daten.tage === 1 ? "Seit 1 Tag keine Tour." : `Seit ${nf(h.daten.tage, 0)} Tagen keine Tour.`}</p><p class="hnsub"><span class="mut">Letzte Tour:</span> ${hnTour(h.daten)} <span class="mut">${fmtDatumKurz(h.daten.letzte)}</span></p>`,
    link: () => (typeof isViewer === "function" && isViewer() ? "" : hnTrLink("#/plan", "Tour planen ›")),
    badge: h => (h.daten.tage === 1 ? "1 Tag" : `${nf(h.daten.tage, 0)} Tage`),
  },
  rekord: {
    name: "Neuer Bestwert", icon: "trophy", wtype: "hnrekord", seiten: ["uebersicht", "statistik"], defaults: {tage: 7, ausblenden: 7},
    desc: "Erscheint nur, wenn du kürzlich deine längste Tour, deinen größten Aufstieg oder dein schnellstes Tempo aller Zeiten erreicht hast.",
    sample: ["info", "Längste Tour 32,4 km"],
    fields: [{k: "tage", kind: "number", label: "Zeitraum in Tagen (so lange bleibt der Hinweis)", min: 1, max: 365, step: 1, int: true}, {kind: "sports"}],
    cond: c => [(c.tage ?? 7) === 1 ? "Wird nur angezeigt, wenn du heute oder gestern deine längste Tour, deinen größten Aufstieg oder das schnellste Tempo aller Zeiten erreicht hast."
      : `Wird nur angezeigt, wenn du in den letzten ${nf(c.tage ?? 7, 0)} Tagen deine längste Tour, deinen größten Aufstieg oder das schnellste Tempo aller Zeiten erreicht hast.`, "Voraussetzung: mindestens 5 Touren."],
    body: h => hnRows(h.daten.rekorde.map(r => `<li><b>${r.metrik === "km" ? `${fmtKm(r.wert)}` : r.metrik === "hm" ? `${fmtHm(r.wert)}` : `${fmtTempo(r.wert)}`}</b><span>${r.metrik === "km" ? "Längste Tour" : r.metrik === "hm" ? "Größter Aufstieg" : "Schnellstes Tempo"}</span> ${hnTour(r)} <span class="mut">${fmtDatumKurz(r.datum)}</span></li>`)),
    link: () => "",
    badge: h => (h.daten.rekorde.length === 1 ? "1 Bestwert" : `${h.daten.rekorde.length} Bestwerte`),
  },
  woche: {                                                                     // 3.45.0: nur noch als Art (Sammel-Baustein, Baustein „Ziele“); die Ziele kommen aus der Statistik
    name: "Wochenziel", icon: "cal", wtype: "", seiten: ["uebersicht"], defaults: {ausblenden: 7},
    desc: "", sample: ["info", "Wochenziel offen: noch 18 km (bisher 32 von 50 km)."], fields: [],
    cond: () => ["Wird nur angezeigt, wenn ein Wochenziel gesetzt ist (Statistik → Ziele)."],
    body(h) {
      const L = h.daten.ziele || [h.daten];
      return L.map(d => {
        const dec = x => (d.einheit === "km" || d.einheit === "hours" ? (x % 1 ? 1 : 0) : 0),
          u = x => (d.einheit === "km" ? fmtKm(x, {d: dec(x)}) : d.einheit === "up" ? fmtHm(x) : d.einheit === "hours" ? fmtDauer(x * 3600, {summe: true}) : hnTours(Math.round(x))),
          pct = d.ziel > 0 ? Math.min(100, (d.ist / d.ziel) * 100) : 0, nm = d.sport ? ` <span class="mut">${esc(goalSportName(d.sport))}</span>` : "",
          left = d.tage_rest === 0 ? "Heute ist der letzte Tag der Woche." : d.tage_rest === 1 ? "Noch 1 Tag in dieser Woche." : `Noch ${d.tage_rest} Tage in dieser Woche.`;
        return `<p class="hnt">${d.erreicht ? `Wochenziel erreicht: ${u(d.ist)} von ${u(d.ziel)}.` : `Wochenziel offen: noch ${u(d.rest)} (bisher ${nf(d.ist, d.einheit === "km" || d.einheit === "hours" ? 1 : 0)} von ${u(d.ziel)}).`}${nm}</p>` +
          `<div class="hnbar" role="progressbar" aria-label="Fortschritt zum Wochenziel" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct)}">${slBr(pct, d.erreicht ? "hnok" : "")}</div>` +
          (d.erreicht ? "" : `<p class="mut hnsub">${left}</p>`);
      }).join("");
    },
    link: () => hnTrLink("#/stats", "Zu den Zielen ›"),
    badge: h => `${nf(Math.min(100, h.daten.ziel > 0 ? (h.daten.ist / h.daten.ziel) * 100 : 0), 0)}\u00a0%`,
  },
  erholung: {
    name: "Erholung empfohlen", icon: "heart", wtype: "hnerholung", seiten: ["uebersicht", "statistik"], defaults: {stufe: "deutlich_mehr", ausblenden: 7},
    desc: "Erscheint nur, wenn deine Belastung laut Uhr deutlich über dem Üblichen liegt und du zuletzt trainiert hast. Braucht Trainingsdaten der Uhr.",
    sample: ["warnung", "Deutlich mehr Belastung als sonst: Erholung empfohlen."],
    fields: [{k: "stufe", kind: "radio", def: "deutlich_mehr", label: "Hinweis ab", options: [["deutlich_mehr", "Deutlich mehr Belastung"], ["mehr", "Etwas mehr Belastung"]]}],
    cond: c => [c.stufe === "mehr" ? "Wird nur angezeigt, wenn deine Belastung laut Uhr über dem Üblichen liegt und du in den letzten 7 Tagen trainiert hast." : "Wird nur angezeigt, wenn deine Belastung laut Uhr deutlich über dem Üblichen liegt und du in den letzten 7 Tagen trainiert hast.",
      "Voraussetzung: Trainingsdaten der Uhr."],
    body: h => `<p class="hnt">${h.daten.stufe === "deutlich_mehr" ? "Deutlich mehr Belastung als sonst: Erholung empfohlen." : "Etwas mehr Belastung als sonst: Erholung empfohlen."}</p>` +
      `<p class="mut hnsub">${h.daten.abweichung_pct > 0 ? "+" : ""}${h.daten.abweichung_pct}\u00a0% gegenüber dem Schnitt der 12 Wochen davor</p><p class="mut hnsub">Die Belastung stammt aus den Trainingsdaten deiner Uhr und ist keine medizinische Empfehlung.</p>`,
    link: () => hnTrLink("#/stats", "Mehr in der Statistik ›"),
    badge: h => `${h.daten.abweichung_pct > 0 ? "+" : ""}${h.daten.abweichung_pct}\u00a0%`,
  },
  sicherung: {
    name: "Sicherung", icon: "shield", wtype: "hnsicherung", seiten: ["uebersicht"], defaults: {tage: 7, ausblenden: 7},
    desc: "Erscheint nur, wenn die letzte Sicherung deiner Daten zu alt ist, fehlt oder fehlgeschlagen ist.",
    sample: ["hinweis", "Die letzte Sicherung ist 9 Tage alt."],
    fields: [{k: "tage", kind: "number", label: "Hinweis, wenn die letzte Sicherung so viele Tage alt ist", min: 1, max: 365, step: 1, int: true}],
    cond: c => [(c.tage ?? 7) === 1 ? "Wird nur angezeigt, wenn die letzte Sicherung mindestens einen Tag alt ist, fehlt oder fehlgeschlagen ist." : `Wird nur angezeigt, wenn die letzte Sicherung mindestens ${nf(c.tage ?? 7, 0)} Tage alt ist, fehlt oder fehlgeschlagen ist.`],
    body(h) {
      const d = h.daten;
      return `<p class="hnt">${d.fehler ? "Die letzte Sicherung ist fehlgeschlagen." : d.alter_tage === null ? "Es gibt noch keine Sicherung deiner Daten." : d.alter_tage === 1 ? "Die letzte Sicherung ist 1 Tag alt." : `Die letzte Sicherung ist ${nf(d.alter_tage, 0)} Tage alt.`}</p>` +
        (d.datum ? `<p class="mut hnsub">Letzte Sicherung: ${fmtDatumKurz(d.datum)}</p>` : "");
    },
    link: () => hnAdminLink("sicher"),
    badge: h => (h.daten.alter_tage === null ? "fehlt" : h.daten.alter_tage === 1 ? "1 Tag" : `${nf(h.daten.alter_tage, 0)} Tage`),
  },
};

/* ---- Darstellung eines Hinweises: Symbol + Wort + Farbe; Warnung als role="alert", sonst role="status" ---- */
function hnBox(h, cfg, o = {}) {
  const A = HN_ART[h.art], S = HN_STUFE[h.stufe], days = +(cfg.ausblenden ?? 7) || 0, can = days > 0 && typeof slCan === "function" && slCan(),
    snooze = can ? `<button type="button" class="btn ghost sm hnsn" data-art="${h.art}" data-days="${days}" aria-label="${esc(`${A.name}: für ${days === 1 ? "1 Tag" : days + " Tage"} ausblenden`)}">${days === 1 ? "Für 1 Tag ausblenden" : `Für ${days} Tage ausblenden`}</button>` : "",
    link = A.link(h);
  return `<div class="hnbox hn-${h.stufe}" role="${h.stufe === "warnung" ? "alert" : "status"}" data-art="${h.art}">${hnIcon(h.stufe)}<div class="hnmain">` +
    `<p class="hnlbl">${S[0]}${o.titel ? ` <span class="hnti">${esc(A.name)}</span>` : ""}</p>${A.body(h)}${link || snooze ? `<p class="hnact">${link}${snooze}</p>` : ""}</div></div>`;
}
function hnPlaceholder(T, cfg, d, snoozed, failed) {
  const conds = T.sammel
    ? [`Wird nur angezeigt, wenn mindestens einer der gewählten Hinweise aktiv ist: ${hnArten(cfg).map(a => HN_ART[a].name).join(" · ")}.`]
    : HN_ART[T.art].cond({...T.defaults, ...cfg}),
    sn = (snoozed || []).filter(Boolean);
  return conds.map((x, i) => `<p class="${i ? "mut hnphs" : "hnphc"}">${esc(x)}</p>`).join("") +
    `<p class="mut hnphs">${failed ? "Die Hinweise konnten nicht geladen werden." : sn.length ? "" : "Gerade ist nichts los: Der Baustein ist unsichtbar."}</p>` +
    sn.map(a => `<p class="mut hnphs"><span>Ausgeblendet bis ${fmtDatumKurz(slIso(new Date(hnSnoozeTs(cfg, a) * 1000)))}.</span> ${slCan() ? `<button type="button" class="btn ghost sm hnun" data-art="${a}">Wieder anzeigen</button>` : ""}</p>`).join("");
}
const hnArten = cfg => (cfg.arten && cfg.arten.length ? HN_ARTEN.filter(a => cfg.arten.includes(a)) : HN_SAMMEL);

/* Gemeinsame Darstellung: Zustand der Karte setzen, Raster neu auffüllen (eine unsichtbare Karte belegt keinen Platz) */
function hnState(c, state) {
  if (c.dataset.hn === state) return;
  c.dataset.hn = state;
  if (typeof slRasterSoon === "function") slRasterSoon();
}
async function hnRender(T, c, b, cfg) {
  cfg = cfg || {};
  const arts = T.sammel ? hnArten(cfg) : [T.art];
  let d;
  try {
    d = await hnGet(hnQuery(arts, cfg, !!T.sammel));
  } catch (e) {
    b.innerHTML = hnPlaceholder(T, cfg, null, [], true);
    slBadge(c, "");
    return hnState(c, "aus");
  }
  const all = d.hinweise.filter(h => arts.includes(h.art) && HN_ART[h.art]), items = all.filter(h => !hnSnoozed(cfg, h.art)), hidden = all.filter(h => hnSnoozed(cfg, h.art)).map(h => h.art);
  if (!items.length) {
    b.innerHTML = hnPlaceholder(T, cfg, d, hidden);
    slBadge(c, hidden.length ? "ausgeblendet" : "nichts los");
    return hnState(c, "aus");
  }
  b.innerHTML = T.sammel ? `<div class="hnlist">${items.map(h => hnBox(h, cfg, {titel: true})).join("")}</div>` : hnBox(items[0], cfg);
  slBadge(c, T.sammel ? (items.length === 1 ? "1 Hinweis" : `${items.length} Hinweise`) : HN_ART[T.art].badge(items[0]));
  hnState(c, "an");
  if (HN.focus && HN.focus.id === (c.dataset.wid || "")) {                                            // nach „Ausblenden“ im Sammel-Baustein: Fokus auf den nächsten Knopf
    const bs = b.querySelectorAll(".hnsn"), f = bs[Math.min(HN.focus.i, bs.length - 1)];
    HN.focus = null;
    if (f) f.focus();
  }
}
/* Ausblenden für N Tage: Zeitstempel je Art in der Konfiguration der Instanz (wird mit dem Layout gespeichert) */
function hnSnooze(id, art, days) {
  const w = typeof slWidgetOf === "function" && slWidgetOf(id);
  if (!w) return;
  const cfg = JSON.parse(JSON.stringify(w.cfg || {})), until = hnNow() + Math.round(days * 86400);
  cfg.snoozes = (cfg.snoozes || []).filter(x => !String(x).startsWith(art + ":"));
  if (days > 0) cfg.snoozes.push(`${art}:${until}`);
  if (!cfg.snoozes.length) delete cfg.snoozes;
  slSetCfg(id, cfg);
  hnLive(days > 0 ? `${HN_ART[art].name}: ausgeblendet bis ${fmtDatumKurz(slIso(new Date(until * 1000)))}` : `${HN_ART[art].name}: wieder sichtbar`);
}
function hnLive(text) {
  let l = document.getElementById("hnlive");
  if (!l) {
    l = document.createElement("div");
    l.id = "hnlive";
    l.className = "slsr";
    l.setAttribute("role", "status");
    l.setAttribute("aria-live", "polite");
    document.body.appendChild(l);
  }
  l.textContent = "";
  setTimeout(() => (l.textContent = text), 30);
}
document.addEventListener("click", e => {
  const s = e.target.closest && e.target.closest(".hnsn, .hnun");
  if (!s) return;
  const card = s.closest(".tlw[data-wid]");
  if (!card) return;
  e.preventDefault();
  const id = card.dataset.wid, snz = [...card.querySelectorAll(".hnsn")];
  if (s.classList.contains("hnsn")) HN.focus = {id, i: snz.indexOf(s)};
  hnSnooze(id, s.dataset.art, s.classList.contains("hnsn") ? +s.dataset.days : 0);
});

/* ---- Typen im Katalog (Muster wie 50-bausteine.js) ---- */
const hnPreview = (s, text, art) => slPrev(`<div class="hnbox hn-${s} hnpv">${hnIcon(s)}<div class="hnmain"><p class="hnlbl">${HN_STUFE[s][0]}</p><p class="hnt">${esc(text)}</p></div></div>`);
const HN_FIELD_AUS = {k: "ausblenden", kind: "radio", num: true, def: 7, label: "Knopf „Ausblenden“ (Hinweis für diese Zeit verbergen)", options: HN_AUS};
window.SL_WT.hinweise = {
  fam: "uebersicht", cat: "hinweise", icon: "bell", name: "Hinweise", title: () => "Hinweise", multi: true, hinweis: true, sammel: true, w: "voll", seiten: ["uebersicht", "statistik"],
  defaults: {arten: HN_SAMMEL.slice(), ausblenden: 7}, kurz: cfg => flParts(cfg, null),
  desc: "Alle gerade aktiven Hinweise gebündelt in einer Liste: Jahresziel, Meilenstein, Auffälligkeiten, Pause, Bestwert, Wochenziel, Erholung, Sicherung. Nur sichtbar, wenn mindestens einer aktiv ist. Ziele und Wochenziele legst du in der Statistik unter „Ziele“ fest.",
  fields: [{k: "arten", kind: "checks", def: HN_SAMMEL, label: "Berücksichtigte Hinweise", min: 1, options: HN_ARTEN.map(a => [a, HN_ART[a].name])}, {kind: "sports", label: "Sportart (für Ziele, Pause, Bestwert, Meilenstein und Wochenziel)"},
    {kind: "title"}, HN_FIELD_AUS],
  preview: () => slPrev(`<div class="hnpv2"><div class="hnbox hn-warnung hnpv">${hnIcon("warnung")}<div class="hnmain"><p class="hnlbl">${HN_STUFE.warnung[0]}</p><p class="hnt">${esc(HN_ART.ziel.name)}</p></div></div>` +
    `<div class="hnbox hn-info hnpv">${hnIcon("info")}<div class="hnmain"><p class="hnlbl">${HN_STUFE.info[0]}</p><p class="hnt">${esc(HN_ART.meilenstein.name)}</p></div></div></div>`),
  render(c, b, cfg) {
    return hnRender(this, c, b, cfg);
  },
};
Object.entries(HN_ART).forEach(([art, A]) => {
  if (!A.wtype) return;                                                                            // 3.45.0: ziel und woche sind Teil des Bausteins „Ziele“
  window.SL_WT[A.wtype] = {
    fam: "uebersicht", cat: "hinweise", icon: A.icon, name: A.name, title: () => A.name, multi: true, defaults: A.defaults, hinweis: true, art, w: "voll", seiten: A.seiten, cfgOnAdd: !!A.cfgOnAdd,
    kurz: cfg => flParts(cfg, null), desc: A.desc, fields: [...A.fields, {kind: "title"}, HN_FIELD_AUS],
    preview: () => hnPreview(A.sample[0], A.sample[1], art),
    render(c, b, cfg) {
      return hnRender(this, c, b, cfg);
    },
  };
});
/* 3.45.0 Baustein „Ziele“ (Code in 52-bausteine-uebersicht.js; nutzt die Hinweis-Hilfen dieser Datei für die Darstellung „Nur Warnung“) */
window.SL_WT.ziele = zlType();


/* ---- 3.48.0 Sicherungs-Wächter: schmale Warnleiste unter der Kopfzeile (nur Admin-Konten, nie für Betrachter) ----
   Daten: GET /api/backup/waechter (nutzt die Hinweis-Regel „Sicherung“ und den Sicherungszustand; keine zweite Berechnung im Browser).
   Abfrage einmal beim Laden und beim Seitenwechsel höchstens alle 5 Minuten, sonst aus dem Speicher. „Morgen erinnern“ merkt sich den Tag je Browser und Konto (nicht im Fehlerfall). */
const WB_TTL = 5 * 60 * 1000;
let wbData = null, wbAt = 0, wbLoad = null, wbMem = "", wbRO = null;
/* Höhe der Leiste als --wbh: Seiten, die die ganze Fensterhöhe füllen (Karte, 3D-Flug), ziehen sie ab und scrollen dadurch nicht */
const wbHoehe = () => {
  const b = document.getElementById("wbar");
  document.documentElement.style.setProperty("--wbh", (b ? Math.round(b.getBoundingClientRect().height) : 0) + "px");
};
const wbTag = () => {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
};
const wbKey = () => "wachterBis:" + (ME.user ? ME.user.uid : "0");
const wbVerborgen = () => {
  try { return localStorage.getItem(wbKey()) === wbTag(); } catch (e) { return wbMem === wbTag(); }
};
function wbText(d) {
  if (d.art === "fehler") return d.grund === "pruefung" ? "Die letzte Sicherung ist nicht lesbar oder beschädigt." : "Die letzte Sicherung ist fehlgeschlagen.";
  if (d.art === "keine") return "Es gibt noch keine Sicherung deiner Touren.";
  if (d.alter_tage === 1) return "Letzte Sicherung vor 1 Tag.";
  return `Letzte Sicherung vor ${nf(d.alter_tage, 0)} Tagen.`;
}
/* 3.71.0 (M-11): Kurzfassung für schmale Bildschirme (eine Zeile statt drei) */
function wbKurz(d) {
  if (d.art === "fehler") return d.grund === "pruefung" ? "Letzte Sicherung beschädigt." : "Letzte Sicherung fehlgeschlagen.";
  if (d.art === "keine") return "Noch keine Sicherung.";
  return d.alter_tage === 1 ? "Letzte vor 1 Tag." : `Letzte vor ${nf(d.alter_tage, 0)} Tagen.`;
}
function wbZeichnen(d) {
  let bar = document.getElementById("wbar");
  const top = document.querySelector("header.top");
  /* 3.49.0: Auf der Aufzeichnungsseite der App bleibt die Leiste weg – dort zählt nur die Aufnahme; auf jeder anderen Seite erscheint sie wieder. */
  const aufnahme = !!window.MTApp && location.hash.startsWith("#/record");
  if (!d || !d.zeige || !top || !isAdmin() || isViewer() || aufnahme || location.hash.startsWith("#/admin") || (d.ausblendbar && wbVerborgen())) {      // 3.71.0: in der Verwaltung steht dieselbe Meldung schon in „Zustand“ und „Sicherung & Zugang“
    if (bar) bar.remove();
    wbHoehe();
    return;
  }
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "wbar";
    top.insertAdjacentElement("afterend", bar);
  }
  const fehler = d.art === "fehler";
  bar.className = "wbar" + (fehler ? " bad" : "");
  bar.setAttribute("role", fehler ? "alert" : "status");
  bar.innerHTML = `<span class="wbi" aria-hidden="true">${fehler ? "✗" : "⚠"}</span><span class="wbt"><b>Sicherung</b> <span class="wbl">${wbText(d)}</span><span class="wbk">${wbKurz(d)}</span></span>` +
    `<span class="wba">${d.ausblendbar ? `<button type="button" class="btn alt sm" id="wbhide" title="Morgen wieder erinnern">Später</button>` : ""}<a class="btn sm" id="wbgo" href="#/admin?tab=sicher">Jetzt sichern</a></span>`;
  const h = bar.querySelector("#wbhide");
  if (h) h.onclick = () => {
    try { localStorage.setItem(wbKey(), wbTag()); } catch (e) {}
    wbMem = wbTag();
    bar.remove();
    wbHoehe();
  };
  wbHoehe();
  if (typeof ResizeObserver === "function" && !wbRO) {
    wbRO = new ResizeObserver(wbHoehe);
    wbRO.observe(bar);
  }
}
function wbAktualisieren(erzwingen) {
  if (typeof isAdmin !== "function" || !isAdmin() || isViewer()) return wbZeichnen(null);
  if (wbData && !erzwingen && Date.now() - wbAt < WB_TTL) return wbZeichnen(wbData);
  if (!wbLoad) wbLoad = api("/api/backup/waechter").then(d => { wbData = d; wbAt = Date.now(); }).catch(() => {}).finally(() => { wbLoad = null; });
  return wbLoad.then(() => wbZeichnen(wbData));
}
function waechterInit() {
  wbAktualisieren(true);
  addEventListener("hashchange", () => wbAktualisieren(false));
}
