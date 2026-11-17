/* =====================  3.34.0 Fotos-Seite als anpassbare Seite (Layout-Schlüssel „fotos“)  =====================
   Die Fotos-Seite (#/photos, Aufbau in 04-fotos.js, „Unbenutzte Fotos aufräumen“ in 23-aufraeumen.js) ist wie Übersicht, Statistik und Reisen anpassbar (Engine 49-seitenlayout.js, Ansichten 54, Vorlagen 55).
   Kapselung statt Neuschreibung: Die Seite baut sich wie vorher auf; danach steckt foFrame() ihre drei Bereiche unverändert (mit allen Kennungen, Knöpfen und Ereignissen: Foto-Zuordnung, Auswahl,
   Aufräumen, Jahresleiste) in das Raster #fox und übergibt es der Engine (slPlace). Ohne gespeichertes Layout sieht die Seite aus wie vorher: kein Kartenrahmen, keine zusätzlichen Abstände
   (#fox ist ohne Anpassung ein einfacher Block, erst mit anderer Breite, Baustein oder Bearbeitungsmodus ein Raster).
   Bereiche: kopf (Titel, Zahlen, Knöpfe; Pflicht)  jahre (Jahresleiste)  raster (die Fotos des Jahres, nach Touren gruppiert).
   Bausteine (Katalog „Fotos“, nur hier): fkennzahl (Foto-Kennzahlen: Fotos, zugeordnet, Touren mit Fotos, Jahre, Länder – nur was vorhanden ist), fjahre (Fotos je Jahr, Säulen). Beide rechnen aus
   GET /api/photo-info (3.34.0: Feld year_counts) und den geladenen Touren. */
SL_REG.fotos = [
  {id: "kopf", w: "voll", title: "Kopf: Titel, Zahlen und Aktionen", page: "fotos", plain: true, must: true, ws: ["voll"]},
  {id: "jahre", w: "voll", title: "Jahresleiste", page: "fotos", plain: true, ws: ["voll", "zweidrittel", "halb"]},
  {id: "raster", w: "voll", title: "Fotos des Jahres (nach Touren)", page: "fotos", plain: true, ws: ["voll"]},
];
SL_EL.fotos = {kopf: () => document.getElementById("fo-kopf"), jahre: () => document.getElementById("fo-jahre"), raster: () => document.getElementById("pg")};
/* Aufbau: die drei Bereiche der fertigen Seite in das Raster einordnen (läuft nach VIEWS.photos, die Seite ist dann vollständig) */
function foFrame() {
  const main = document.getElementById("main");
  if (!main || document.getElementById("fox")) return;
  const kopf = main.querySelector(":scope > .sec"), jahre = main.querySelector(":scope > .years"), pg = document.getElementById("pg");
  if (!kopf || !jahre || !pg) return;                                                    // „Noch keine Fotos“: nichts zu ordnen
  const host = document.createElement("div");
  host.id = "fox";
  host.className = "stx fox";
  kopf.id = "fo-kopf";
  jahre.id = "fo-jahre";
  [kopf, jahre, pg].forEach(e => host.appendChild(e));
  main.appendChild(host);
  slPlace(host);
}
const FO_VALUES = [["fotos", "Fotos"], ["zugeordnet", "Einer Tour zugeordnet"], ["touren", "Touren mit Fotos"], ["jahre", "Jahre"], ["orte", "Länder"]];
const FO_DEF = ["fotos", "zugeordnet", "jahre", "orte"];
const foInfo = () => api("/api/photo-info");
/* Jahr, das die Seite gerade zeigt (Adresse #/photos?y=…), sonst das neueste */
const foYear = info => {
  const m = /[?&]y=(\d{4})/.exec(location.hash);
  return m ? +m[1] : (info.years || [])[0];
};
Object.assign(window.SL_WT, {
  fkennzahl: {
    fam: "fotos", cat: "foto", icon: "cam", name: "Foto-Kennzahlen", title: () => "Foto-Kennzahlen", multi: true, w: "halb", seiten: ["fotos"], defaults: {values: FO_DEF},
    desc: "Wie viele Fotos du hast, wie viele davon einer Tour zugeordnet sind, aus wie vielen Touren, Jahren und Ländern sie stammen. Länder erscheinen nur, wenn sie zu den Touren schon bekannt sind.",
    fields: [{k: "values", kind: "checks", label: "Angezeigte Werte", min: 1, def: FO_DEF, options: FO_VALUES}, {kind: "title"}],
    preview: () => slPvTiles([["1 240", "Fotos"], ["86 %", "Einer Tour zugeordnet"], ["2019–2026", "Jahre"]]),
    async render(c, b, cfg) {
      const d = await foInfo();
      if (!d || !d.count) return slNote(b, "Noch keine Fotos.");
      const want = (cfg.values && cfg.values.length ? cfg.values : FO_DEF).filter(v => FO_VALUES.some(k => k[0] === v)),
        withPh = TOURS.filter(t => t.photos > 0), land = [...new Set(withPh.map(t => t.g_country).filter(Boolean))], ys = d.years || [],
        tile = {
          fotos: [nf(d.count, 0), d.count === 1 ? "Foto" : "Fotos", d.undated ? `${nf(d.undated, 0)} ohne Aufnahmezeit` : ""],
          zugeordnet: [nf(d.assigned, 0), "Einer Tour zugeordnet", `${Math.round((d.assigned / d.count) * 100)} %`],
          touren: withPh.length ? [nf(withPh.length, 0), withPh.length === 1 ? "Tour mit Fotos" : "Touren mit Fotos"] : null,
          jahre: ys.length ? [ys.length === 1 ? String(ys[0]) : `${Math.min(...ys)}–${Math.max(...ys)}`, ys.length === 1 ? "Jahr" : "Jahre", ys.length > 1 ? `${ys.length} Jahre mit Fotos` : ""] : null,
          orte: land.length ? [String(land.length), land.length === 1 ? "Land" : "Länder", land.slice(0, 3).join(", ") + (land.length > 3 ? " …" : "")] : null,
        }, list = want.map(v => tile[v]).filter(Boolean);
      if (!list.length) return slNote(b, "Für die gewählten Werte liegen keine Daten vor.");
      b.innerHTML = slTiles(list);
      slBadge(c, `${nf(d.count, 0)} Fotos`);
    },
  },
  fjahre: {
    fam: "fotos", cat: "foto", icon: "trend", name: "Fotos je Jahr", title: () => "Fotos je Jahr", multi: true, w: "halb", seiten: ["fotos"], defaults: {n: 8},
    desc: "Ein Säulendiagramm über die Jahre: wie viele Fotos auf jedes Jahr entfallen. Das Jahr, das die Seite gerade zeigt, ist hervorgehoben.",
    fields: [{k: "n", kind: "radio", num: true, def: 8, label: "Anzahl der Jahre", options: [[5, "5"], [8, "8"], [12, "12"]]}, {kind: "title"}],
    preview: () => slPvBars([8, 14, 20, 12, 30, 24, 34]),
    async render(c, b, cfg) {
      const d = await foInfo(), yc = (d && d.year_counts) || {}, all = Object.keys(yc).map(Number).filter(y => y > 0).sort((x, y) => x - y);
      if (!all.length) return slNote(b, "Noch keine Fotos mit Aufnahmedatum.");
      const n = [5, 8, 12].includes(+cfg.n) ? +cfg.n : 8, y1 = Math.max(...all), y0 = Math.max(Math.min(...all), y1 - n + 1), ys = Array.from({length: y1 - y0 + 1}, (_, i) => y0 + i),
        v = ys.map(y => yc[y] || 0), cur = foYear(d), hl = ys.includes(cur) ? ys.indexOf(cur) : v.indexOf(Math.max(...v)), best = v.indexOf(Math.max(...v));
      b.innerHTML = slCols(v, {hl, label: `Säulendiagramm: Fotos je Jahr, am meisten ${ys[best]} mit ${nf(v[best], 0)}`, labels: ys.map(y => (ys.length > 8 ? "’" + String(y).slice(2) : String(y))), cls: "slsm rscol"}) +
        `<p class="slcmp">Meiste Fotos: ${ys[best]}</p><p class="mut slcmpn">${nf(v[best], 0)} Fotos${ys.includes(cur) ? `; hervorgehoben: ${cur} (${nf(yc[cur] || 0, 0)})` : ""}</p>`;
      slBadge(c, String(ys[best]));
    },
  },
});
SL_TPL.push(
  {id: "fo-zahlen", fam: "fotos", name: "Mit Kennzahlen", desc: "Oben die Foto-Kennzahlen und die Fotos je Jahr nebeneinander, darunter wie gewohnt die Jahresleiste und die Fotos.",
    items: [["kopf", "voll"], ["w:fkennzahl", "halb"], ["w:fjahre", "halb"], ["jahre", "voll"], ["raster", "voll"]]},
  {id: "fo-ruhig", fam: "fotos", name: "Nur Fotos", desc: "Ruhig und kurz: Kopf und Fotos des Jahres, ohne Jahresleiste (das Jahr steht in der Adresse).",
    items: [["kopf", "voll"], ["raster", "voll"]]},
  {id: "fo-verlauf", fam: "fotos", name: "Jahresverlauf", desc: "Für den Blick über die Jahre: die Fotos je Jahr in ganzer Breite, darunter die Jahresleiste und die Fotos.",
    items: [["kopf", "voll"], ["w:fjahre", "voll"], ["jahre", "voll"], ["raster", "voll"]]},
);
/* ---------- Anbindung an die Ansicht ---------- */
{
  const _ph63 = VIEWS.photos;
  VIEWS.photos = async (...a) => {
    window.FO_WRAPPED = true;
    slViewStart("fotos");
    const tok = window._rt;
    await slEnsure("fotos");
    if (tok !== window._rt) return STALE();
    slResolve("fotos");
    await _ph63(...a);
    if (tok !== window._rt) return;
    foFrame();
  };
}
/* Dieses Skript lädt vor 64-kartenseite.js; hat die Seite schon gezeichnet, bevor die Ansicht hier eingehängt war (boot() läuft früher), wird sie jetzt mit dem Layout neu gezeichnet */
slLate(/^#\/photos(\?.*)?$/, "FO_WRAPPED", "#pg .pgroup, #pg:not(:empty)");
