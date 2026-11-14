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
    uiAlert("In die Zwischenablage kopiert");
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
  {
    $("#esnd").insertAdjacentHTML("afterend", ` <button class="btn sm" id="eshow" title="Diashow der Fotos als Link senden – ohne Benutzerkonto ansehbar">Diashow senden</button>`);
    $("#eshow").onclick = async () => {
      const keep = k => { try { return localStorage.getItem("mt_show_" + k); } catch (e) { return null; } };
      const m = modal(`<h3>Diashow senden</h3><p class="mut fs14">Erzeugt einen Link, den man <b>ohne Benutzerkonto</b> öffnen kann. Es werden nur die Fotos dieser Tour gezeigt.</p>
        <label>Fotos<br><select id="sh_b"><option value="0">Alle Fotos</option><option value="20">Nur die besten 20</option><option value="50">Nur die besten 50</option></select></label>
        <label class="mt10" style="display:block">Link gültig<br><select id="sh_d"><option value="7">7 Tage</option><option value="30">30 Tage</option><option value="0">Unbegrenzt (bis ich ihn widerrufe)</option></select></label>
        <label class="mt10" style="display:block"><input type="checkbox" id="sh_c"> Besucher dürfen Fotos kommentieren</label><p class="mut fs13 m4-0-0">Kommentare sind für alle mit dem Link sichtbar; Gäste brauchen kein Konto. Du kannst sie in der Erzählung löschen.</p>
        <div class="row mt14 jce"><button class="btn alt" id="sh_x">Abbrechen</button><button class="btn" id="sh_go">Senden</button></div>`);
      m.querySelector("#sh_c").checked = keep("c") === "1";
      m.querySelector("#sh_b").value = keep("b") || "0";
      m.querySelector("#sh_d").value = keep("d") || "30";
      m.querySelector("#sh_x").onclick = () => m.remove();
      m.querySelector("#sh_go").onclick = async () => {
        const best = +m.querySelector("#sh_b").value, days = +m.querySelector("#sh_d").value, comments = m.querySelector("#sh_c").checked;
        try { localStorage.setItem("mt_show_c", comments ? "1" : "0"); localStorage.setItem("mt_show_b", best); localStorage.setItem("mt_show_d", days); } catch (e) {}
        const b = m.querySelector("#sh_go");
        b.disabled = true;
        try {
          const n = (await api(`/api/photos?tour_id=${encodeURIComponent(t.id)}`).catch(() => null)) || [];
          if (Array.isArray(n) && !n.filter(x => x.manual !== 2).length && !await uiConfirm("Zu dieser Tour wurden keine Fotos gefunden. Trotzdem Link erstellen?")) { b.disabled = false; return; }
          const s = await api(`/api/tours/${encodeURIComponent(t.id)}/share`, {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify({show: true, trim: true, days, best, comments}),
          });
          m.remove();
          await shareOut(t.name, `Diashow: ${t.name} (${dateL(t.date)})`, location.origin + s.url);
        } catch (e) {
          b.disabled = false;
          uiAlert("Link konnte nicht erstellt werden: " + e.message);
        }
      };
    };
  }
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
      uiAlert("Link konnte nicht erstellt werden: " + e.message);
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
