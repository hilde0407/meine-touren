/* =====================  Wunschliste (Wanderführer-Touren, die ich noch gehen möchte)  ===================== */
const _placesW = VIEWS.places;
VIEWS.places = async (...a) => {
  await _placesW(...a);
  const sec = [...document.querySelectorAll("#plb .sec")].find(x => /Wanderführer/.test(x.textContent));
  if (!sec || $("#wlist")) return;
  let all = [];
  try {
    all = await api("/api/wishlist");
  } catch (e) {
    return;
  }
  if (!all.length) return;
  const draw = () => {
    const w = all.filter(x => x.wish),
      open = w.filter(x => !x.tour),
      sum = (l, k) => l.reduce((c, x) => c + (x[k] || 0), 0);
    const cand = all.filter(x => !x.wish && !x.tour);
    $("#wlist").innerHTML = `<div class="sec mt0"><h2>Wunschliste</h2><span class="sub">${w.length ? `${open.length} offen · ${nf(sum(open, "km"), 0)} km${sum(open, "up") ? " · " + nf(sum(open, "up"), 0) + " m Aufstieg" : ""}` : "noch leer"}</span></div>
     <div class="panel mb16">${w.length ? `<div class="rows">${w
       .map(
         x => `<div class="r"><span>${x.tour ? "✓" : "○"} ${esc(x.title)}<small>${esc(x.book)} · ${nf(x.km, 1)} km${x.up != null ? " · ↑ " + nf(x.up, 0) + " m" : ""}</small></span><span>${x.tour ? `<a href="#/tour/${x.tour}">${BY[x.tour] ? dateS(BY[x.tour].date) : "gegangen"}</a> ` : ""}<button class="btn ghost sm" data-w="${x.id}" title="Von der Wunschliste entfernen">✕</button></span></div>`
       )
       .join("")}</div>` : '<p class="mut">Noch keine Touren vorgemerkt.</p>'}
     ${cand.length ? `<div class="row mt12"><select id="wsel" style="max-width:100%">${cand.map(x => `<option value="${x.id}">${esc(x.book ? x.book + " – " : "")}${esc(x.title)} (${nf(x.km, 1)} km${x.up != null ? ", ↑ " + nf(x.up, 0) + " m" : ""})</option>`).join("")}</select><button class="btn alt" id="wadd">Zur Wunschliste</button></div>` : ""}</div>`;
    $("#wlist").querySelectorAll("[data-w]").forEach(b => (b.onclick = async () => {
      await api("/api/wishlist", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({id: +b.dataset.w, on: false})});
      all.find(x => x.id === +b.dataset.w).wish = 0;
      draw();
    }));
    if ($("#wadd")) $("#wadd").onclick = async () => {
      const id = +$("#wsel").value;
      await api("/api/wishlist", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({id, on: true})});
      all.find(x => x.id === id).wish = 1;
      draw();
    };
  };
  sec.insertAdjacentHTML("beforebegin", '<div id="wlist"></div>');
  draw();
};
