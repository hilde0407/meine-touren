/* =====================  Wie oft bin ich diese Strecke gegangen?  ===================== */
let REP = {};
const _loadToursR = loadTours;
loadTours = async (...a) => {
  await _loadToursR(...a);
  // Auswertung kann bei großen Bibliotheken ein paar Sekunden dauern: höchstens 3 s warten, sonst später nachreichen
  const p = api("/api/repeats").then(r => (REP = r)).catch(() => (REP = {}));
  await Promise.race([p, new Promise(r => setTimeout(r, 3000))]);
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
  const r = REP[id],
    w = $("#ewarn");
  if (!r || !w || $("#repnote")) return;
  const rank = 1 + r.with.filter(x => x.start_ts < r.start_ts).length,
    ds = ts => new Date(ts * 1000).toLocaleDateString("de-DE");
  w.insertAdjacentHTML(
    "beforebegin",
    `<div id="repnote" style="margin:-4px 0 10px">🔁 Diese Strecke bist du schon <b>${r.n}-mal</b> gegangen – diese Tour war das <b>${rank}. Mal</b>. <span class="mut">Weitere: ${r.with
      .map(x => `<a href="#/tour/${esc(x.id)}">${ds(x.start_ts)}</a>`)
      .join(", ")}</span></div>`
  );
};
