/* =====================  Mehrtagestouren („… Tag 3“, „… Etappe 2“)  ===================== */
const SER_RE = /^(.*?)[\s\-–—:,.]*\b(?:Tag|Etappe|Day|Stage|Jour|Étape|Día|Etapa)\s*0?(\d{1,2})\b/i;
function seriesList() {
  const g = {};
  for (const t of TOURS || []) {
    const m = SER_RE.exec((t.name || "").trim());
    if (!m || !m[1].trim()) continue;
    const key = m[1].trim().toLowerCase();
    (g[key] = g[key] || {name: m[1].trim(), tours: []}).tours.push({t, n: +m[2]});
  }
  return Object.entries(g)
    .map(([key, v]) => {
      v.tours.sort((a, b) => a.n - b.n || a.t.start_ts - b.t.start_ts);
      const ts = v.tours.map(x => x.t);
      return {id: encodeURIComponent(key), name: v.name, ids: ts.map(t => t.id), n: ts.length, km: ts.reduce((c, t) => c + t.km, 0), up: ts.reduce((c, t) => c + (t.up_m || 0), 0),
              start: ts.reduce((a, t) => Math.min(a, t.start_ts), Infinity), end: ts.reduce((a, t) => Math.max(a, t.start_ts), 0), nums: new Set(v.tours.map(x => x.n)).size};
    })
    .filter(s => s.n >= 2 && s.nums >= 2)
    .sort((a, b) => b.start - a.start);
}
const _tripsS = VIEWS.trips;
VIEWS.trips = async () => {
  await _tripsS();
  const L = seriesList(),
    tr = $("#tr");
  if (!tr || !L.length) return;
  const ds = ts => new Date(ts * 1000).toLocaleDateString("de-DE");
  tr.insertAdjacentHTML(
    "afterbegin",
    `<div class="sec" style="margin-top:0"><h2>Mehrtagestouren</h2><span class="sub">erkannt an Namen wie „… Tag 3“ oder „… Etappe 2“</span></div><div class="otdg">${L.map(
      s => `<a class="otd" href="#/series/${s.id}" style="background-image:linear-gradient(#0e2a2b99,#0e2a2bee)"><b>${esc(s.name)}</b><span>${ds(s.start)}${s.end - s.start > 86400 ? " – " + ds(s.end) : ""}</span><small>${s.n} Etappen · ${nf(s.km, 0)} km · ${nf(s.up, 0)} m</small></a>`
    ).join("")}</div>`
  );
};
VIEWS.series = async id => {
  const s = seriesList().find(x => x.id === id || decodeURIComponent(x.id) === decodeURIComponent(id));
  if (!s) throw new Error("Mehrtagestour nicht gefunden");
  await collView(s.name, `${s.n} Etappen`, s.ids, "#/trips");
};
// Hinweis im Tourdetail
const _tourSer = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourSer(id, q);
  const w = $("#ewarn"),
    t = BY[id];
  if (!w || !t || $("#sernote")) return;
  const m = SER_RE.exec((t.name || "").trim());
  if (!m || !m[1].trim()) return;
  const s = seriesList().find(x => x.name.toLowerCase() === m[1].trim().toLowerCase());
  if (s) w.insertAdjacentHTML("beforebegin", `<div id="sernote" class="mut" style="margin:-4px 0 10px">Etappe der Mehrtagestour <a href="#/series/${s.id}"><b>${esc(s.name)}</b></a> (${s.n} Etappen, ${nf(s.km, 0)} km, ${nf(s.up, 0)} m Aufstieg) – <a href="#/series/${s.id}">Gesamtansicht</a></div>`);
};
