/* Zentrale Formatierer (3.41.0): EIN Helfer je Art von Wert – Dauer, Strecke, Aufstieg/Abstieg, Tempo, Zahl, Datum, Uhrzeit.
   Alle sichtbaren Zahlen und Zeiten der Oberfläche laufen hierüber; die Sprache kommt aus window.LANG (de/en/fr/es, siehe 00-i18n.js).
   Keine Abhängigkeit von anderen Dateien – wird in tests/test_format_341.py einzeln geladen.
   Regeln:  Dauer „1:55 Std.“ (h:mm; en/fr/es „1:55 h“), unter einer Stunde „45 Min.“, Summen ab 24 Stunden ganzzahlig „388 Std.“
            Strecke eine Nachkommastelle, Summen ab 100 km ganzzahlig · Aufstieg/Abstieg ganze Meter „300 m“ (Liste „↑ 300 m“)
            Dezimalkomma bzw. -punkt und Tausendertrennung je Sprache · Datum lang „18. November 2026“ (Köpfe), kurz „18.11.2026“ (Listen) · Dateigröße „12,3 MB“. */
const FMT_LG = () => (["de", "en", "fr", "es"].includes(window.LANG) ? window.LANG : "de");
const FMT_NUM = {de: "de-DE", en: "en-US", fr: "fr-FR", es: "es-ES"};
const FMT_MONATE = {
  de: ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  fr: ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
  es: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
};
const FMT_MON_KURZ = {
  de: ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  fr: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
  es: ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
};
const FMT_WT = {   // Wochentage, Sonntag zuerst (Date.getDay)
  de: ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"],
  en: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
  fr: ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"],
  es: ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"],
};
const FMT_E = {   // Einheiten je Sprache: Stunde, Minute
  de: {h: "Std.", min: "Min."},
  en: {h: "h", min: "min"},
  fr: {h: "h", min: "min"},
  es: {h: "h", min: "min"},
};
const fmtPad2 = n => String(n).padStart(2, "0");

/* Zahl mit Nachkommastellen im Format der Sprache */
const fmtZahl = (n, d = 1) => {
  const v = Number(n ?? 0);
  return (Number.isFinite(v) ? v : 0).toLocaleString(FMT_NUM[FMT_LG()], {minimumFractionDigits: d, maximumFractionDigits: d});
};

/* Dauer. s = Sekunden. Zuerst auf ganze Minuten runden, dann teilen (nie „2:60“).
   o.summe: ab 24 Stunden ganze Stunden („388 Std.“) · o.einheit=false: ohne Einheit · o.hmm: immer h:mm, auch unter einer Stunde („0:45“) */
const fmtDauerTeile = (s, o = {}) => {
  const t = Math.max(0, Math.round((+s || 0) / 60)),
    h = Math.floor(t / 60),
    m = t % 60,
    E = FMT_E[FMT_LG()];
  if (o.summe && t >= 24 * 60) return {v: fmtZahl(Math.round(t / 60), 0), u: E.h};
  return h || o.hmm ? {v: `${h}:${fmtPad2(m)}`, u: E.h} : {v: String(m), u: E.min};
};
const fmtDauer = (s, o = {}) => {
  const p = fmtDauerTeile(s, o);
  return o.einheit === false ? p.v : `${p.v} ${p.u}`;
};

/* Dauer für Kennzahl-Kacheln: Zahl und Einheit getrennt gesetzt („1:55<span class="u">Std.</span>“) */
const fmtDauerHtml = (s, o = {}) => {
  const p = fmtDauerTeile(s, o);
  return `${p.v}<span class="u">${p.u}</span>`;
};

/* Strecke. km = Kilometer. Standard: eine Nachkommastelle; o.summe: ab 100 km ganzzahlig; o.d: feste Stellenzahl; o.einheit=false: ohne „km“ */
const fmtKm = (km, o = {}) => {
  const k = Number(km) || 0,
    d = o.d != null ? o.d : o.summe && Math.abs(k) >= 100 ? 0 : 1;
  return fmtZahl(k, d) + (o.einheit === false ? "" : " km");
};
/* Höhe / Aufstieg / Abstieg in Metern, ganze Zahl. o.pfeil: „↑ 300 m“ (auf) bzw. „↓“ (ab) für Listen und Karten */
const fmtHm = (m, o = {}) => (o.pfeil ? o.pfeil + " " : "") + fmtZahl(m, 0) + (o.einheit === false ? "" : " m");
const fmtAuf = m => fmtHm(m, {pfeil: "↑"});
const fmtAb = m => fmtHm(m, {pfeil: "↓"});
/* Dateigröße in Bytes: „12,3 MB“ (ab 1 GB „1,2 GB“, unter 100 kB ganze „kB“); französisch mit Go/Mo/ko. Eine Funktion für alle Größenangaben (3.46.0). */
const FMT_BYTE = {de: ["kB", "MB", "GB"], en: ["kB", "MB", "GB"], fr: ["ko", "Mo", "Go"], es: ["kB", "MB", "GB"]};
const fmtGroesse = n => {
  const b = Math.max(0, Number(n) || 0),
    U = FMT_BYTE[FMT_LG()];
  return b >= 1e9 ? `${fmtZahl(b / 1e9, 1)} ${U[2]}` : b >= 1e5 ? `${fmtZahl(b / 1e6, 1)} ${U[1]}` : `${Math.max(1, Math.round(b / 1e3))} ${U[0]}`;
};
/* Tempo (km/h) und Pace (min/km; nur dort, wo ausdrücklich „Pace“ steht) */
const fmtTempo = (kmh, o = {}) => fmtZahl(kmh, o.d != null ? o.d : 1) + " km/h";
const fmtPace = minProKm => {
  const t = Math.max(0, Math.round((+minProKm || 0) * 60));
  return `${Math.floor(t / 60)}:${fmtPad2(t % 60)} min/km`;
};

/* Datum und Uhrzeit. x = ISO-Text („2026-11-18“, „2026-11-18T03:43:00“ – ohne Zeitzonenumrechnung), Date, oder Sekunden seit 1970 (Zahl) */
const fmtTeile = x => {
  if (typeof x === "string") {
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(x);
    return m ? {y: +m[1], mo: +m[2], d: +m[3], hh: m[4] != null ? +m[4] : null, mi: m[5] != null ? +m[5] : null} : null;
  }
  const dt = x instanceof Date ? x : typeof x === "number" ? new Date(x < 1e11 ? x * 1000 : x) : null;
  if (!dt || isNaN(dt)) return null;
  return {y: dt.getFullYear(), mo: dt.getMonth() + 1, d: dt.getDate(), hh: dt.getHours(), mi: dt.getMinutes()};
};
const fmtTagMonat = (lg, d, mo, y, ohneJahr) => {
  const M = FMT_MONATE[lg][mo - 1];
  if (lg === "de") return `${d}. ${M}${ohneJahr ? "" : " " + y}`;
  if (lg === "es") return `${d} de ${M}${ohneJahr ? "" : " de " + y}`;
  return `${lg === "fr" && d === 1 ? "1er" : d} ${M}${ohneJahr ? "" : " " + y}`;
};
/* Uhrzeit „03:43 Uhr“ (en/fr/es „03:43“); o.uhr=false: ohne „Uhr“ (Zeitspannen, an die der Satz selbst „Uhr“ hängt) */
const fmtUhrzeit = (x, o = {}) => {
  const p = fmtTeile(x);
  if (!p || p.hh == null) return "";
  return `${fmtPad2(p.hh)}:${fmtPad2(p.mi)}` + (FMT_LG() === "de" && o.uhr !== false ? " Uhr" : "");
};
/* o.wochentag: „Mittwoch, 18. November 2026“ · lang: „18. November 2026“ (Köpfe, Aufmacher, Kacheln) · kurz: „18.11.2026“ (Listen, Tabellen; en/fr/es „18/11/2026“) */
const fmtDatum = (x, o = {}) => {
  const p = fmtTeile(x);
  if (!p) return "";
  const lg = FMT_LG(),
    kurz = o.kurz ? `${fmtPad2(p.d)}${lg === "de" ? "." : "/"}${fmtPad2(p.mo)}${lg === "de" ? "." : "/"}${p.y}` : null,
    s = kurz || (o.wochentag ? FMT_WT[lg][new Date(p.y, p.mo - 1, p.d).getDay()] + ", " : "") + fmtTagMonat(lg, p.d, p.mo, p.y);
  return o.zeit && p.hh != null ? `${s}, ${fmtUhrzeit(x)}` : s;
};
const fmtDatumKurz = (x, o = {}) => fmtDatum(x, {...o, kurz: true});
/* Monat und Jahr: „November 2026“, kurz „Nov. 2026“ */
const fmtMonat = (x, o = {}) => {
  const p = typeof x === "object" && x && !(x instanceof Date) ? x : fmtTeile(x);
  if (!p) return "";
  const lg = FMT_LG();
  return `${(o.kurz ? FMT_MON_KURZ : FMT_MONATE)[lg][p.mo - 1]} ${o.jahr2 ? String(p.y).slice(2) : p.y}`;
};
/* Tag und kurzer Monat ohne Jahr: „18. Nov.“ */
const fmtTagKurz = x => {
  const p = fmtTeile(x);
  if (!p) return "";
  const lg = FMT_LG();
  return `${p.d}${lg === "de" ? "." : ""} ${FMT_MON_KURZ[lg][p.mo - 1]}`;
};
/* Zeitraum: „10.–28. Oktober 2026“; über Monats- oder Jahresgrenzen „30. Oktober – 2. November 2026“ */
const fmtZeitraum = (a, b, o = {}) => {
  const p = fmtTeile(a),
    q = fmtTeile(b);
  if (!p) return "";
  if (!q || (p.y === q.y && p.mo === q.mo && p.d === q.d)) return fmtDatum(a, o);
  const lg = FMT_LG();
  if (o.kurz) return `${fmtDatum(a, {kurz: true})} – ${fmtDatum(b, {kurz: true})}`;
  if (p.y === q.y && p.mo === q.mo) {
    const M = FMT_MONATE[lg][p.mo - 1];
    if (lg === "de") return `${p.d}.–${q.d}. ${M} ${p.y}`;
    if (lg === "es") return `${p.d}–${q.d} de ${M} de ${p.y}`;
    return `${lg === "fr" && p.d === 1 ? "1er" : p.d}–${q.d} ${M} ${p.y}`;
  }
  if (p.y === q.y) return `${fmtTagMonat(lg, p.d, p.mo, p.y, true)} – ${fmtTagMonat(lg, q.d, q.mo, q.y)}`;
  return `${fmtDatum(a)} – ${fmtDatum(b)}`;
};
