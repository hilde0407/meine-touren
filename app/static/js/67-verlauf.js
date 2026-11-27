/* =====================  3.36.0 Rückgängig und Wiederholen im Bearbeitungsmodus  =====================
   Verlauf der Layoutänderungen der angezeigten Ansicht (verschieben, Breite, entfernen, hinzufügen, duplizieren, Einstellungen, Gruppen, Handy-Anordnung, Standard wiederherstellen).
   Jeder Schritt ist ein Schnappschuss der Layout-Dokumente der Seite vor der Änderung (SL.hist.undo); „Wiederholen“ gibt die rückgängig gemachten zurück (SL.hist.redo).
   Höchstens SL_HMAX Schritte. Der Verlauf beginnt mit dem Bearbeiten und endet mit „Fertig“, „Verwerfen“, dem Verlassen der Seite und jedem Wechsel der Ansicht (er gilt nur für die angezeigte Ansicht).
   Tastatur: Strg/Cmd+Z und Strg/Cmd+Umschalt+Z (auch Strg+Y), nur im Bearbeitungsmodus und nie in Eingabefeldern oder offenen Dialogen. Jeder Schritt wird angesagt (Bereich „sllive“). */
const SL_HMAX = 50;
SL.hist = {undo: [], redo: [], cur: ""};
const slHistState = () => JSON.stringify({view: SL.view[SL.fam], d: Object.fromEntries(slKeys(SL.fam).map(k => [k, slLayEmpty(SL.docs[k]) ? null : SL.docs[k]]))});
function slHistReset() {
  SL.hist = {undo: [], redo: [], cur: SL.edit ? slHistState() : ""};
  SL.hlast = null;
  slBarSync();
}
/* Aufruf aus slTouch (nach der Änderung): den Stand von vor der Änderung als Schritt ablegen */
function slHistPush() {
  if (SL.hold) return;
  const now = slHistState();
  if (now === SL.hist.cur) return;
  const e = {s: SL.hist.cur, l: ""};
  if (SL.hist.cur) {
    SL.hist.undo.push(e);
    if (SL.hist.undo.length > SL_HMAX) SL.hist.undo.shift();
    SL.hlast = e;
    setTimeout(() => SL.hlast === e && (SL.hlast = null), 0);              // die Ansage der Änderung (slLive) folgt im selben Ablauf
  }
  SL.hist.redo = [];
  SL.hist.cur = now;
  slBarSync();
}
function slHistApply(state) {
  const st = JSON.parse(state);
  if (st.view !== SL.view[SL.fam]) return false;
  const before = {};
  slKeys(SL.fam).forEach(k => (before[k] = JSON.stringify(SL.docs[k] || null)));
  SL.hold = true;
  try {
    slKeys(SL.fam).forEach(k => {
      if (st.d[k]) SL.docs[k] = st.d[k];
      else delete SL.docs[k];
    });
    slTouch(...slKeys(SL.fam));
  } finally {
    SL.hold = false;
  }
  SL.hist.cur = state;
  const has = (d, f, id) => ((d && d[f]) || []).includes(id);
  slKeys(SL.fam).forEach(k => {                                             // „Standardmäßig offen“ geänderter Abschnitte auch am gebauten Abschnitt nachführen
    const o = JSON.parse(before[k]), n = SL.docs[k], ch = new Set();
    ["open", "closed"].forEach(f => [...((o && o[f]) || []), ...((n && n[f]) || [])].forEach(i => ch.add(i)));
    ch.forEach(id => {
      const it = slItems(SL.fam).find(i => i.id === id);
      if (it && (has(o, "open", id) !== has(n, "open", id) || has(o, "closed", id) !== has(n, "closed", id))) slOpenDom(it, slDef(id, !!it.def));
    });
  });
  SL.focus = null;
  slApply();
  return true;
}
function slUndo() {
  if (!SL.edit) return;
  const h = SL.hist, e = h.undo.pop();
  if (!e) return slLive("Nichts zum Rückgängigmachen");
  SL.hlast = null;
  const now = slHistState();
  if (!slHistApply(e.s)) return;
  h.redo.push({s: now, l: e.l});
  slBarSync();
  slLive(`Rückgängig: ${e.l || "Änderung"}`);
}
function slRedo() {
  if (!SL.edit) return;
  const h = SL.hist, e = h.redo.pop();
  if (!e) return slLive("Nichts zum Wiederholen");
  SL.hlast = null;
  const now = slHistState();
  if (!slHistApply(e.s)) return;
  h.undo.push({s: now, l: e.l});
  slBarSync();
  slLive(`Wiederholt: ${e.l || "Änderung"}`);
}
const slUndoIcon = '<svg class="sli" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></svg>';
const slRedoIcon = '<svg class="sli" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/></svg>';
const slHistHtml = () =>
  `<span class="slbu" role="group" aria-label="Verlauf der Änderungen">` +
  `<button type="button" class="slb slbub" data-a="undo" aria-disabled="true" aria-keyshortcuts="Control+Z Meta+Z">${slUndoIcon}<span>Rückgängig</span></button>` +
  `<button type="button" class="slb slbub" data-a="redo" aria-disabled="true" aria-keyshortcuts="Control+Shift+Z Meta+Shift+Z">${slRedoIcon}<span>Wiederholen</span></button></span>`;
/* Zustand der Knöpfe in der Leiste (aria-disabled, damit der Fokus beim Leerwerden bleibt) */
function slBarSync() {
  const bar = document.getElementById("slbar");
  if (!bar) return;
  const u = bar.querySelector('[data-a="undo"]'), r = bar.querySelector('[data-a="redo"]'), h = SL.hist;
  const set = (b, list, name) => {
    if (!b) return;
    const e = list[list.length - 1];
    b.setAttribute("aria-disabled", list.length ? "false" : "true");
    b.title = e ? `${name}: ${e.l || "Änderung"} (${list.length})` : `${name}: nichts vorhanden`;
  };
  set(u, h.undo, "Rückgängig");
  set(r, h.redo, "Wiederholen");
  slDevSync();
  slBarH();
}
document.addEventListener("keydown", e => {
  if (!SL.edit || !(e.ctrlKey || e.metaKey) || e.altKey) return;
  const k = String(e.key).toLowerCase();
  if (k !== "z" && k !== "y") return;
  const t = e.target;
  if (t && t.closest && t.closest("input,textarea,select,[contenteditable],[contenteditable=true]")) return;          // dort gilt das Rückgängig des Eingabefelds
  if (document.querySelector(".sldlg, .uidlg")) return;                                                                // offener Dialog
  e.preventDefault();
  if (k === "y" || e.shiftKey) slRedo();
  else slUndo();
});
