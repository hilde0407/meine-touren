/* =====================  Kamerauhr-Hinweis (Prüfen)  ===================== */
const _checkU = VIEWS.check;
VIEWS.check = async () => {
  await _checkU();
  const b = $("#chb");
  if (!b || $("#clk")) return;
  const panel = document.createElement("div");
  panel.className = "panel";
  panel.id = "clk";
  panel.style.marginTop = "22px";
  panel.innerHTML = `<h2>Kamerauhr</h2><p class="mut">Wird geprüft …</p>`;
  b.querySelector(".panel").after(panel);
  let list = [];
  try {
    list = await api("/api/clock-check");
  } catch (e) {
    panel.remove();
    return;
  }
  const fmt = s => {
    const a = Math.abs(s),
      [h, m] = hmParts(a);
    return (s > 0 ? "+" : "−") + (h ? h + " Std. " : "") + (m ? m + " Min." : "");
  };
  const draw = () => {
    panel.innerHTML = `<h2>Kamerauhr</h2>${
      list.length
        ? `<p class="mut">Bei diesen Touren passen die Foto-Zeiten nicht zum Aufnahmeort (Kamerauhr falsch gestellt, z. B. Zeitzone der Reise). Mit „Korrigieren“ werden die Fotos um den Unterschied verschoben und der Tour zugeordnet.</p><div class="rows">${list
            .map(
              x => `<div class="r db" data-t="${esc(x.tour_id)}"><a href="#/tour/${encodeURIComponent(x.tour_id)}" class="fw600">${esc(x.name)}</a> <span class="mut">${fmtDatumKurz(x.start_ts)}</span><br>
        <span class="bad fs14">Foto-Zeiten müssen um ${fmt(x.delta_s)} korrigiert werden (${x.n} von ${fmtAnzahl(x.of, "Foto", "Fotos")} mit Aufnahmeort stimmen überein)</span>
        <div class="row m4-0"><button class="btn sm" data-ck>Korrigieren (${fmt(x.delta_s)})</button><button class="btn alt sm" data-ci>Ignorieren</button></div></div>`
            )
            .join("")}</div>`
        : '<p class="ok">✓ Die Kamerauhr passt zu den Strecken der letzten Touren.</p>'
    }`;
    panel.querySelectorAll("[data-ck]").forEach(
      btn =>
        (btn.onclick = async () => {
          const id = btn.closest("[data-t]").dataset.t,
            x = list.find(y => y.tour_id === id);
          btn.disabled = true;
          try {
            await api("/api/photo-offset", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({tour_id: id, delta_s: x.delta_s, ids: x.ids})});
            list = list.filter(y => y.tour_id !== id);
            draw();
          } catch (e) {
            uiAlert(e.message);
            btn.disabled = false;
          }
        })
    );
    panel.querySelectorAll("[data-ci]").forEach(
      btn =>
        (btn.onclick = async () => {
          const id = btn.closest("[data-t]").dataset.t;
          await api("/api/clock-check/ignore", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({tour_id: id})});
          list = list.filter(y => y.tour_id !== id);
          draw();
        })
    );
  };
  draw();
};
