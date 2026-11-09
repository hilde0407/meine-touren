/* =====================  Wie oft bin ich diese Strecke gegangen?  ===================== */
let REP = {};
const _loadToursR = loadTours;
loadTours = async (...a) => {
  await _loadToursR(...a);
  // Die Auswertung kann bei großen Bibliotheken ein paar Sekunden dauern: nicht darauf warten, sondern nachreichen
  window.REPP = api("/api/repeats")
    .then(r => {
      REP = r;
      if (location.hash.startsWith("#/tours") && $("#q") && window.scrollY < 40) $("#q").dispatchEvent(new Event("input")); // Liste mit 🔁 neu zeichnen
    })
    .catch(() => (REP = {}));
};
const _tourRowR = tourRow;
tourRow = t => {
  const h = _tourRowR(t),
    r = REP[t.id];
  return r ? h.replace(/(<div class="nm">[\s\S]*?)(<\/div>)/, `$1 <span class="rep" title="Diese Strecke bist du ${r.n}-mal gegangen">🔁 ${r.n}×</span>$2`) : h;
};
const _tourRep = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourRep(id, q);
  const go = () => {
    if (location.hash.includes(id)) showRepNote(id);
  };
  if (window.REPP) window.REPP.then(go);   // nicht warten: die Auswertung kann bei großen Bibliotheken dauern
  else go();
};
function showRepNote(id) {
  const t = BY[id],
    r = REP[id],
    w = $("#ewarn");
  if (!t || !r || !w || $("#repnote")) return;
  const rank = 1 + r.with.filter(x => x.start_ts < r.start_ts).length,
    ds = ts => new Date(ts * 1000).toLocaleDateString("de-DE");
  w.insertAdjacentHTML(
    "beforebegin",
    `<div id="repnote" class="mn4-0-10">🔁 Diese Strecke bist du schon <b>${r.n}-mal</b> gegangen – diese Tour war das <b>${rank}. Mal</b>. <span class="mut">Weitere: ${r.with
      .map(x => `<a href="#/tour/${esc(x.id)}">${ds(x.start_ts)}</a>`)
      .join(", ")}</span></div>`
  );
}
