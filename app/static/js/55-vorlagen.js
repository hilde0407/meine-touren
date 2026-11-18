/* =====================  3.21.0 Vorlagen für Ansichten  =====================
   Fertige Anordnungen zum Start. Eine Vorlage ist eine kurze Beschreibung, aus der das Layout-Dokument (Format wie in app/layout.py) erzeugt wird:
     items  [[Kennung, Breite, Konfiguration?]]  Reihenfolge der sichtbaren Abschnitte; „w:<Typ>“ = Baustein dieses Typs (Kennung „t-<Typ>“), sonst ein Standard-Abschnitt der Seite
     groups [{title, items: [Kennung, …], closed?}]  (3.36.0, optional) Gruppen aus den Einträgen von „items“ (einklappbarer Abschnitt, Mitglieder in der Reihenfolge von „items“)
     Standard-Abschnitte, die nicht aufgeführt sind, werden ausgeblendet (außer den Pflicht-Abschnitten, z. B. dem Einstieg in die Auswertung).
   Die Dokumente gehen durch dieselbe Prüfung wie alles, was der Benutzer speichert (der Server prüft sie beim Speichern; tests/test_ansichten_ui.py prüft jede Vorlage dagegen). */
const SL_TPL = [
  {id: "ue-wanderer", fam: "uebersicht", name: "Wanderer", desc: "Für alle, die gern draußen sind: dein Jahresziel, Meilensteine, die Kalender-Heatmap, die letzten Touren und deine Rekorde.",
    items: [["w:jahresziel", "halb"], ["w:meilensteine", "halb"], ["w:heatmap", "voll"], ["w:letzte", "halb"], ["w:rekorde", "halb"]]},
  {id: "ue-training", fam: "uebersicht", name: "Training", desc: "Für den Blick auf Form und Regelmäßigkeit: Belastung und Erholung, Wochen-Serie, diese Woche, Sportarten und der Jahresvergleich.",
    items: [["w:belastung", "halb"], ["w:serie", "halb"], ["w:periode", "halb"], ["w:sportarten", "halb"], ["w:jahresvergleich", "voll"]]},
  {id: "ue-rueckblick", fam: "uebersicht", name: "Rückblick", desc: "Für den Blick zurück: Dein Jahr, der Jahres-Rückblick, Heute vor X Jahren, Wiederentdecken und deine Rekorde.",
    items: [["jahr", "voll"], ["w:rueckblick", "voll"], ["w:heutevor", "halb"], ["w:rekorde", "halb"], ["w:wiederentdecken", "voll"]]},
  {id: "ue-kompakt", fam: "uebersicht", name: "Kompakt", desc: "Wenig auf einen Blick: vier Bausteine in halber Breite, auf dem Handy untereinander.",
    items: [["jahr", "halb"], ["w:periode", "halb"], ["w:letzte", "halb"], ["w:rekorde", "halb"]]},
  {id: "ue-hinweise", fam: "uebersicht", name: "Mit Hinweisen", desc: "Für den Alltag mit Erinnerungen: oben der Baustein „Hinweise“, der nur erscheint, wenn etwas los ist, darunter Dein Jahr, diese Woche, die letzten Touren, Jahresziel und Meilensteine.",
    items: [["w:hinweise", "voll"], ["jahr", "voll"], ["w:periode", "halb"], ["w:letzte", "halb"], ["w:jahresziel", "halb"], ["w:meilensteine", "halb"]]},
  {id: "ue-gruppe", fam: "uebersicht", name: "Mit Gruppe", desc: "Oben Dein Jahr, diese Woche und die letzten Touren, darunter die einklappbare Gruppe „Rückblick“ mit Jahres-Rückblick, Heute vor X Jahren und deinen Rekorden.",
    items: [["jahr", "voll"], ["w:periode", "halb"], ["w:letzte", "halb"], ["w:rueckblick", "voll"], ["w:heutevor", "halb"], ["w:rekorde", "halb"]],
    groups: [{title: "Rückblick", items: ["w:rueckblick", "w:heutevor", "w:rekorde"]}]},
  {id: "st-rueckblick", fam: "statistik", name: "Jahresrückblick", desc: "Für den Blick auf ein Jahr: Kennzahlen, Monate, Höhenmeter im Jahresverlauf, die besten Touren und die Kalender-Heatmap.",
    items: [["kpi", "voll"], ["kmmonat", "halb"], ["w:sthoehe", "halb"], ["w:sttop", "halb"], ["bestwerte", "halb"], ["heat", "voll"]]},
  {id: "st-training", fam: "statistik", name: "Training", desc: "Für den Blick auf Form und Entwicklung: Belastung und Erholung, dein typisches Tempo, die Entwicklung deines Tempos, der Monatsvergleich und die Streckenlängen.",
    items: [["bl", "voll"], ["tp", "voll"], ["w:stentwicklung", "halb"], ["w:stmonate", "halb"], ["w:stlaengen", "halb"], ["w:sttop", "halb", {wert: "tempo"}]]},
  {id: "st-kompakt", fam: "statistik", name: "Kompakt", desc: "Wenig auf einen Blick: Kennzahlen ganz oben, darunter vier Bausteine in halber Breite, auf dem Handy untereinander.",
    items: [["kpi", "voll"], ["kmmonat", "halb"], ["sportarten", "halb"], ["bestwerte", "halb"], ["w:sttop", "halb"]]},
  {id: "to-wandern", fam: "tour", name: "Wandern", desc: "Für Wanderungen: Karte und Höhenprofil, die Gipfel-Tafel, Tageslicht, Wetter und die Fotos der Tour.",
    items: [["map", "voll"], ["prof", "voll"], ["w:gipfel", "halb"], ["w:tageslicht", "halb"], ["w:wetter", "halb"], ["sum", "voll"], ["photos", "voll"]]},
  {id: "to-rad", fam: "tour", name: "Radtour / Training", desc: "Für Rad und Training: Karte und Profil, Kilometer-Splits, Steigungs-Verteilung, Puls-Zonen, Bewegung und Pause und der Vergleich mit früheren Touren.",
    items: [["map", "voll"], ["prof", "voll"], ["w:splits", "voll"], ["w:steigung", "halb"], ["w:pulszonen", "halb"], ["w:bewegung", "halb"], ["w:vergleich", "halb"], ["sum", "voll"]]},
  {id: "to-kompakt", fam: "tour", name: "Kompakt", desc: "Das Wichtigste auf einen Blick: Karte und Profil nebeneinander, darunter die Kennzahlen.",
    items: [["map", "halb"], ["prof", "halb"], ["w:kennzahlen", "voll"], ["sum", "voll"]]},
];
const slTplFor = fam => SL_TPL.filter(t => t.fam === fam);
const slTplCopy = o => JSON.parse(JSON.stringify(o));
/* Eintrag einer Vorlage → {id, type, std, w, cfg} */
function slTplItem(fam, [ref, w, cfg]) {
  if (ref.startsWith("w:")) {
    const type = ref.slice(2), T = window.SL_WT[type];
    return {id: "t-" + type, type, w, cfg: {...slTplCopy((T && T.defaults) || {}), ...(cfg || {})}, title: T ? T.name || T.title((T && T.defaults) || {}) : type};
  }
  const r = SL_REG[fam].find(x => x.id === ref);
  return {id: ref, std: r, w, title: r ? r.title : ref};
}
/* Layout-Dokumente je Schlüssel: Tourseite {tour-haupt, tour-auswertung}, Übersicht {uebersicht} */
function slTplDocs(t) {
  const fam = t.fam, its = t.items.map(i => slTplItem(fam, i)), keep = new Set(its.map(i => i.id)), doc = {v: 1};
  doc.order = its.map(i => i.id);
  doc.hidden = SL_REG[fam].filter(r => r.page === (fam === "tour" ? "haupt" : fam) && !r.must && !keep.has(r.id)).map(r => r.id);
  if (!doc.hidden.length) delete doc.hidden;
  const widgets = its.filter(i => i.type).map(i => ({id: i.id, type: i.type, cfg: i.cfg})), w = {};
  if (widgets.length) doc.widgets = widgets;
  its.forEach(i => {
    const T = i.type ? window.SL_WT[i.type] : null, dflt = i.type ? slTypeW(T) : (i.std && i.std.w) || "voll";
    if (i.w && i.w !== dflt) w[i.id] = i.w;
  });
  if (Object.keys(w).length) doc.w = w;
  if ((t.groups || []).length)
    doc.groups = t.groups.map((g, i) => {
      const o = {id: "grp" + (i + 1) + t.id.replace(/[^a-z0-9]/g, "").slice(0, 6), title: g.title, ids: g.items.map(r => slTplItem(fam, [r]).id)};
      if (g.closed) o.closed = true;
      return o;
    });
  return fam === "tour" ? {"tour-haupt": doc, "tour-auswertung": {v: 1}} : {[fam]: doc};
}
/* Schema der Vorlage: Zeilen aus den Breiten (ohne Lücken aufgefüllt wie auf der Seite), 120 × (8 + 12 je Zeile) */
function slTplPreview(t) {
  const its = t.items.map(i => slTplItem(t.fam, i)), cws = its.map(i => i.w), {out} = slFillRows(cws, "d");
  let x = 0, row = 0, r = "";
  out.forEach((n, i) => {
    if (x + n > 12) {
      x = 0;
      row++;
    }
    r += `<rect x="${(x * 10 + 1).toFixed(1)}" y="${row * 16 + 1}" width="${n * 10 - 2}" height="13" rx="3"/>`;
    x += n;
  });
  return `<svg class="slpvs slvpv" viewBox="0 0 120 ${row * 16 + 15}" aria-hidden="true" focusable="false">${r}</svg>`;
}
