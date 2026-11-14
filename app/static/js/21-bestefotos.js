/* =====================  Beste Fotos einer Tour (Sterne, Schärfe, Verteilung)  ===================== */
const _tourBF = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourBF(id, q);
  const b0 = $("#pgps");
  if (!b0 || $("#pbest") || !$("#th") || !$("#th").children.length) return;
  b0.insertAdjacentHTML("afterend", `<button class="btn sm alt" id="pbest" title="Wählt aus den Fotos der Tour die besten aus: Sterne aus Lightroom (XMP), unscharfe und abgelehnte Fotos fallen heraus, verteilt über die ganze Tour">⭐ Beste Fotos</button>`);
  let on = false;
  const all = $("#th").innerHTML;
  $("#pbest").onclick = async () => {
    const b = $("#pbest");
    if (on) {
      on = false;
      route();
      return;
    }
    b.disabled = true;
    b.textContent = "Wird ausgewählt …";
    try {
      const r = await api(`/api/tours/${encodeURIComponent(id)}/best-photos?n=10`);
      on = true;
      $("#th").innerHTML = r.photos
        .map(
          (p, k) =>
            `<div class="th"><img loading="lazy" src="/pic/${p.id}?size=500" data-i="${k}"><span class="cap">${"★".repeat(Math.max(0, p.rating || 0))}${p.rating ? " " : ""}${new Date(p.taken_ts * 1000).toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"})}</span></div>`
        )
        .join("");
      bindThumbs($("#th"), r.photos);
      $("#pc").textContent = `${r.photos.length} beste von ${r.total} Fotos${r.rated ? ` (${r.rated} mit Sternen)` : " (keine Sternebewertung gefunden – Auswahl nach Schärfe und Verteilung)"}`;
      b.textContent = "Alle Fotos zeigen";
      const ss = $("#ss");
      if (ss) {
        ss.style.display = "";
        ss.href = `slideshow.html?tour=${encodeURIComponent(id)}&best=10`;
        ss.textContent = "Diashow der besten";
      }
    } catch (e) {
      uiAlert("Auswahl nicht möglich: " + e.message);
      b.textContent = "⭐ Beste Fotos";
    }
    b.disabled = false;
  };
};
