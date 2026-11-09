/* =====================  Geteilte Touren übernehmen (Familie)  ===================== */
const _sharedT = VIEWS.shared;
VIEWS.shared = async (...a) => {
  await _sharedT(...a);
  let list = [];
  try {
    list = await api("/api/shared/tours");
  } catch (e) {
    return;
  }
  if (!list.length || $("#shtours")) return;
  const by = {};
  list.forEach(t => (by[t.owner] = by[t.owner] || {name: t.owner_name, t: []}).t.push(t));
  const html = Object.entries(by)
    .map(
      ([o, v]) => `<div class="sec"><h2>Touren von ${esc(v.name)}</h2><span class="sub">${v.t.length} freigegeben</span></div><div class="panel mb16"><div class="rows">${v.t
        .map(
          t => `<label class="r g8 aic" style="display:flex"><input type="checkbox" data-o="${esc(o)}" data-i="${esc(t.id)}" ${t.imported ? "disabled" : ""}><span class="fx1">${esc(t.name)}<small>${dateS(new Date(t.start_ts * 1000).toISOString())} · ${nf(t.dist_m / 1000, 1)} km${t.up_m ? " · ↑ " + nf(t.up_m, 0) + " m" : ""}</small></span>${t.imported ? '<span class="mut">✓ übernommen</span>' : ""}</label>`
        )
        .join("")}</div><div class="row mt12"><button class="btn" data-imp="${esc(o)}">Ausgewählte Touren übernehmen</button><span class="mut" data-m="${esc(o)}"></span></div></div>`
    )
    .join("");
  $("#main").insertAdjacentHTML("afterbegin", `<div id="shtours">${html}</div>`);
  $("#shtours").querySelectorAll("[data-imp]").forEach(b => (b.onclick = async () => {
    const o = b.dataset.imp,
      ids = [...$("#shtours").querySelectorAll(`input[data-o="${o}"]:checked`)].map(x => x.dataset.i),
      msg = $("#shtours").querySelector(`[data-m="${o}"]`);
    if (!ids.length) {
      msg.textContent = "Bitte Touren ankreuzen.";
      return;
    }
    b.disabled = true;
    msg.textContent = "Wird übernommen …";
    try {
      const r = await api("/api/shared/tours-import", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({owner: o, ids})});
      msg.textContent = `${r.imported} Touren und ${r.photos} Fotos übernommen.${r.failed.length ? " Nicht möglich: " + r.failed.join("; ") : ""}`;
      await loadTours();
    } catch (e) {
      msg.textContent = e.message;
    }
    b.disabled = false;
  }));
};
