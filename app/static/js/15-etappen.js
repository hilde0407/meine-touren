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
    `<div class="sec mt0"><h2>Mehrtagestouren</h2><span class="sub">erkannt an Namen wie „… Tag 3“ oder „… Etappe 2“</span></div><div class="otdg">${L.map(
      s => `<a class="otd" href="#/series/${s.id}" style="background-image:linear-gradient(#0e2a2b99,#0e2a2bee)"><b>${esc(s.name)}</b><span>${ds(s.start)}${s.end - s.start > 86400 ? " – " + ds(s.end) : ""}</span><small>${s.n} Etappen · ${nf(s.km, 0)} km · ${nf(s.up, 0)} m</small></a>`
    ).join("")}</div>`
  );
  // Titelfoto je Mehrtagestour: ein Foto aus der Mitte der Reihe
  try {
    const cv = await api("/api/tour-covers");
    L.forEach((s, i) => {
      // Tour der Reihe mit den meisten Fotos; davon das Foto aus der Mitte
      const best = s.ids.filter(id => cv[id]).sort((x, y) => cv[y].n - cv[x].n)[0],
        el = tr.querySelectorAll(".otdg .otd")[i];
      if (best && el) el.style.backgroundImage = `linear-gradient(#0e2a2b33,#0e2a2bdd),url(/pic/${cv[best].id}?size=500)`;
    });
  } catch (e) {}
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
  if (s) w.insertAdjacentHTML("beforebegin", `<div id="sernote" class="mut mn4-0-10">Etappe der Mehrtagestour <a href="#/series/${s.id}"><b>${esc(s.name)}</b></a> (${s.n} Etappen, ${nf(s.km, 0)} km, ${nf(s.up, 0)} m Aufstieg) – <a href="#/series/${s.id}">Gesamtansicht</a></div>`);
};

/* ---- Reihe bilden / umbenennen ---- */
async function seriesRename(items, name, word) {
  await api("/api/series/rename", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({items, name, word})});
  await loadTours();
}
function seriesBuildDialog() {
  const iso = ts => new Date(ts * 1000).toISOString().slice(0, 10);
  const newest = TOURS.reduce((a, t) => Math.max(a, t.start_ts), 0);
  const m = modal(`<h2>Mehrtagestour bilden</h2>
   <p class="mut fs14">Wähle den Zeitraum der Etappen. Die Touren dieser Tage werden „Name – Tag N“ genannt (N = Tag seit Beginn), danach erscheinen sie als Mehrtagestour unter Reisen.</p>
   <div class="row g8 aic"><label>Von <input id="sbf" type="date" value="${iso(newest - 6 * 86400)}"></label><label>bis <input id="sbt" type="date" value="${iso(newest)}"></label></div>
   <div class="row g8 aic mt8"><input id="sbn" placeholder="Name, z. B. Alpenüberquerung E5" class="fx1 mnw200"><select id="sbw" style="width:auto"><option>Tag</option><option>Etappe</option></select></div>
   <div id="sbl" class="rows m10-0 ova" style="max-height:260px"></div>
   <div class="row"><button class="btn" id="sbok">Benennen</button><button class="btn ghost" id="sbno">Abbrechen</button><span id="sber" class="bad"></span></div>`);
  const list = () => {
    const f = m.querySelector("#sbf").value,
      t = m.querySelector("#sbt").value;
    const ts = TOURS.filter(x => iso(x.start_ts) >= f && iso(x.start_ts) <= t).sort((a, b) => a.start_ts - b.start_ts);
    m.querySelector("#sbl").innerHTML = ts.length
      ? ts.map(x => `<label class="r g8 aic" style="display:flex"><input type="checkbox" data-i="${esc(x.id)}" data-s="${x.start_ts}" checked><span>${dateS(x.date)} · ${esc(x.name)} <span class="mut">${nf(x.km, 1)} km</span></span></label>`).join("")
      : '<p class="mut">Keine Touren in diesem Zeitraum.</p>';
  };
  m.querySelectorAll("input[type=date]").forEach(i => (i.onchange = list));
  list();
  m.querySelector("#sbno").onclick = () => m.remove();
  m.querySelector("#sbok").onclick = async () => {
    const name = m.querySelector("#sbn").value.trim(),
      chosen = [...m.querySelectorAll("[data-i]:checked")];
    if (!name || chosen.length < 2) {
      m.querySelector("#sber").textContent = "Bitte einen Namen eingeben und mindestens zwei Touren wählen.";
      return;
    }
    const day0 = Math.floor(Math.min(...chosen.map(c => +c.dataset.s)) / 86400);
    const items = chosen.map(c => ({id: c.dataset.i, n: Math.floor(+c.dataset.s / 86400) - day0 + 1}));
    try {
      await seriesRename(items, name, m.querySelector("#sbw").value);
      m.remove();
      location.hash = "#/series/" + encodeURIComponent(name.toLowerCase());
    } catch (e) {
      m.querySelector("#sber").textContent = e.message;
    }
  };
}
const _tripsB = VIEWS.trips;
VIEWS.trips = async () => {
  await _tripsB();
  const sec = $("#tr");
  if (!sec || $("#sbbtn")) return;
  sec.insertAdjacentHTML("afterbegin", `<div class="row mb10"><button class="btn alt sm" id="sbbtn">＋ Mehrtagestour bilden …</button></div>`);
  $("#sbbtn").onclick = seriesBuildDialog;
};
const _serV = VIEWS.series;
VIEWS.series = async id => {
  await _serV(id);
  const s = seriesList().find(x => x.id === id || decodeURIComponent(x.id) === decodeURIComponent(id));
  const row = document.querySelector("#main .row .btn");
  if (!s || !row || $("#serren")) return;
  row.parentElement.insertAdjacentHTML("beforeend", `<button class="btn alt" id="serren">✎ Reihe umbenennen</button>`);
  $("#serren").onclick = () => {
    const m = modal(`<h2>Mehrtagestour umbenennen</h2><p class="mut fs14">Alle ${s.n} Etappen heißen danach „Neuer Name – Tag N“ (die Nummern bleiben).</p><input id="srn" value="${esc(s.name)}" class="w100"><div class="row mt12"><button class="btn" id="srok">Umbenennen</button><button class="btn ghost" id="srno">Abbrechen</button><span id="srer" class="bad"></span></div>`);
    m.querySelector("#srno").onclick = () => m.remove();
    m.querySelector("#srok").onclick = async () => {
      const name = m.querySelector("#srn").value.trim();
      if (!name) return;
      const items = s.ids.map(i => {
        const mm = SER_RE.exec((BY[i].name || "").trim());
        return {id: i, n: mm ? +mm[2] : 1};
      });
      const word = /(Tag|Etappe|Day|Stage|Jour|Étape|Día|Etapa)/i.exec(BY[s.ids[0]].name)?.[1] || "Tag";
      try {
        await seriesRename(items, name, word);
        m.remove();
        location.hash = "#/series/" + encodeURIComponent(name.toLowerCase());
      } catch (e) {
        m.querySelector("#srer").textContent = e.message;
      }
    };
  };
};
