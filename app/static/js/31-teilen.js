/* =====================  Teilen: Android-Auswahlmenü (WhatsApp, Signal, Mail …)  ===================== */
/* In der Android-App über die Brücke, im Browser über die Web-Share-Funktion, sonst in die Zwischenablage. */
async function shareOut(title, text, url) {
  const full = url ? `${text}\n${url}` : text;
  try {
    if (window.MTApp && MTApp.shareText) return MTApp.shareText(full), true;
    if (navigator.share) {
      await navigator.share({title, text, url});
      return true;
    }
    await navigator.clipboard.writeText(full);
    alert("In die Zwischenablage kopiert");
  } catch (e) {}
  return false;
}
const shareCanNative = () => !!(window.MTApp || navigator.share);

const tourShareText = t => `${t.name} – ${nf(t.km, 1)} km, ${nf(t.up_m || 0, 0)} m aufwärts, ${nf(t.h, 1)} h (${dateL(t.date)})`;

/* Tour: Knopf „Teilen“ → Link (ohne Anmeldung) erzeugen und sofort an eine App senden */
const _tour31 = VIEWS.tour;
VIEWS.tour = async id => {
  await _tour31(id);
  const t = BY[id],
    old = $("#eshr");
  if (!t || !old || $("#esnd")) return;
  old.insertAdjacentHTML("beforebegin", `<button class="btn sm" id="esnd" title="Link zur Tour an WhatsApp, Signal, E-Mail … senden">Senden</button> `);
  $("#esnd").onclick = async () => {
    const b = $("#esnd");
    b.disabled = true;
    try {
      const s = await api(`/api/tours/${encodeURIComponent(t.id)}/share`, {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({photos: false, trim: true}),
      });
      await shareOut(t.name, tourShareText(t), location.origin + s.url);
    } catch (e) {
      alert("Link konnte nicht erstellt werden: " + e.message);
    }
    b.disabled = false;
  };
};

/* Reise: Zusammenfassung als Text teilen */
const _trip31 = VIEWS.trip;
VIEWS.trip = async id => {
  await _trip31(id);
  const b = $("#tredit");
  if (!b || $("#trsnd")) return;
  b.insertAdjacentHTML("beforebegin", `<button class="btn sm" id="trsnd">Senden</button> `);
  $("#trsnd").onclick = () => {
    const h1 = (document.querySelector("#main h1") || {}).textContent || "Reise",
      figs = [...document.querySelectorAll("#main .figs .fig")].map(f => `${f.querySelector(".v").textContent.replace(/\s+/g, " ")} ${f.querySelector(".l").textContent}`);
    shareOut(h1, `${h1.trim()}\n${figs.join(" · ")}`);
  };
};

/* Jahresrückblick: Zusammenfassung als Text teilen */
const _recap31 = VIEWS.recap;
if (_recap31)
  VIEWS.recap = async y => {
    await _recap31(y);
    const row = document.querySelector(".recap .noprint.row");
    if (!row || $("#rcsnd")) return;
    row.insertAdjacentHTML("beforeend", `<button class="btn sm" id="rcsnd">Senden</button>`);
    $("#rcsnd").onclick = () => {
      const n = TOURS.filter(t => String(t.y) === String(y)),
        s = f => n.reduce((a, t) => a + (f(t) || 0), 0);
      shareOut(`Mein Tourenjahr ${y}`, `Mein Tourenjahr ${y}: ${n.length} Touren, ${nf(s(t => t.km), 0)} km, ${nf(s(t => t.up_m), 0)} m aufwärts, ${nf(s(t => t.h), 0)} Stunden unterwegs.`);
    };
  };
