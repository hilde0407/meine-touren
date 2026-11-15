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

/* =====================  3.25.0 Teilen mit Ansicht: Auswahl „Was wird gezeigt?“ (Dialog für neue Links und zum nachträglichen Ändern)  ===================== */
const SHR_BLOCKS = [["karte", "Karte"], ["hoehe", "Höhenprofil"], ["zahlen", "Kennzahlen"], ["fotos", "Fotos"], ["notiz", "Notiz und Beschreibung"], ["wege", "Wegpunkte"], ["puls", "Pulsverlauf"], ["wetter", "Wetter"]];
const SHR_ALL = SHR_BLOCKS.map(b => b[0]);
const SHR_PRESETS = [["komplett", "Komplett", ["karte", "zahlen", "fotos"]], ["kf", "Nur Karte und Fotos", ["karte", "fotos"]],
  ["ohne", "Alles außer Notizen", SHR_ALL.filter(k => k !== "notiz")], ["alles", "Alles zeigen", SHR_ALL]];
const shrTL = x => (typeof window.TL === "function" ? window.TL(x) : x);
const shrLabel = bl => (bl && bl.length ? SHR_BLOCKS.filter(b => bl.includes(b[0])).map(b => shrTL(b[1])).join(", ") : "–");
const shrPref = (v) => {
  try { if (v === undefined) return JSON.parse(localStorage.getItem("mt_shr") || "null"); localStorage.setItem("mt_shr", JSON.stringify(v)); } catch (e) {}
  return null;
};

/* Dialog: liefert {blocks, trim, days} oder null (abgebrochen). edit = nur die Auswahl (bestehender Link). */
async function shrDialog({blocks, edit, hasPhotos}) {
  const pf = !edit && shrPref();
  const st = {b: new Set(blocks || (pf && pf.blocks) || ["karte", "fotos"]), trim: pf && pf.trim === false ? false : true, days: pf && pf.days != null ? pf.days : 30};
  const on = k => st.b.has(k);
  const html = `<div class="shrdlg">
    <p class="mut fs14">${edit ? "Wähle neu, was Besucher dieses Links sehen." : "Wähle, was Besucher des Links sehen – ohne Benutzerkonto."} Was du nicht wählst, schickt der Server gar nicht erst mit.</p>
    <fieldset class="shrfs"><legend>Voreinstellung</legend><div class="slchips" data-shr="pre">${SHR_PRESETS.map(p => `<button type="button" class="slchip" data-p="${p[0]}" aria-pressed="false">${p[1]}</button>`).join("")}</div></fieldset>
    <fieldset class="shrfs"><legend>Was wird gezeigt?</legend><div class="flchips" data-shr="blk">${SHR_BLOCKS.map(b => `<label class="flchip"><input type="checkbox" data-b="${b[0]}"> ${b[1]}</label>`).join("")}</div></fieldset>
    <p class="shrsum" role="status" aria-live="polite"><b>Dieser Link zeigt:</b> <span data-shr="sum"></span></p>
    <p class="shrnote mut fs13">Auswertung, Uhr-Daten und Vergleiche sind nie Teil eines Links.</p>
    <p class="shrwarn fs14" data-shr="warn" hidden>Notizen können Persönliches enthalten. Bitte vor dem Teilen prüfen.</p>
    <p class="shrwarn fs14" data-shr="nophoto" hidden>Zu dieser Tour gibt es keine Fotos.</p>
    <p class="shrwarn fs14" data-shr="none" hidden>Bitte mindestens einen Inhalt wählen.</p>
    ${edit ? "" : `<label class="shrck"><input type="checkbox" data-shr="trim"> Anfang und Ende der Strecke ausblenden (300 m)</label>
    <label class="shrsel">Link gültig<select data-shr="days"><option value="7">7 Tage</option><option value="30">30 Tage</option><option value="0">Unbegrenzt (bis ich ihn widerrufe)</option></select></label>`}
  </div>`;
  const ok = await uiConfirm({
    title: edit ? "Auswahl ändern" : "Tour teilen", html, ok: edit ? "Speichern" : "Link erstellen",
    onOpen: (box, bOk) => {
      const q = sel => box.querySelector(sel), qa = sel => [...box.querySelectorAll(sel)];
      const sync = () => {
        if (!on("karte")) st.b.delete("wege");
        qa("[data-b]").forEach(i => { i.checked = on(i.dataset.b); i.disabled = i.dataset.b === "wege" && !on("karte"); i.closest("label").classList.toggle("off", i.disabled); });
        qa("[data-p]").forEach(b => { const p = SHR_PRESETS.find(x => x[0] === b.dataset.p)[2]; b.setAttribute("aria-pressed", String(p.length === st.b.size && p.every(k => on(k)))); });
        q('[data-shr="sum"]').textContent = shrLabel([...st.b]);
        q('[data-shr="warn"]').hidden = !on("notiz");
        q('[data-shr="nophoto"]').hidden = !(on("fotos") && hasPhotos === false);
        q('[data-shr="none"]').hidden = st.b.size > 0;
        bOk.disabled = st.b.size === 0;
      };
      qa("[data-b]").forEach(i => (i.onchange = () => { i.checked ? st.b.add(i.dataset.b) : st.b.delete(i.dataset.b); sync(); }));
      qa("[data-p]").forEach(b => (b.onclick = () => { st.b = new Set(SHR_PRESETS.find(x => x[0] === b.dataset.p)[2]); sync(); }));
      const tr = q('[data-shr="trim"]'), dy = q('[data-shr="days"]');
      if (tr) { tr.checked = st.trim; tr.onchange = () => (st.trim = tr.checked); }
      if (dy) { dy.value = String(st.days); dy.onchange = () => (st.days = +dy.value); }
      sync();
    },
  });
  if (!ok) return null;
  const blocks2 = SHR_ALL.filter(k => st.b.has(k));
  if (!edit) shrPref({blocks: blocks2, trim: st.trim, days: st.days});
  return {blocks: blocks2, trim: st.trim, days: st.days};
}

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
      const pick = await shrDialog({hasPhotos: t.photos == null ? undefined : t.photos > 0});
      if (!pick) return;
      const s = await api(`/api/tours/${encodeURIComponent(t.id)}/share`, {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({blocks: pick.blocks, trim: pick.trim, days: pick.days}),
      });
      await shareOut(t.name, tourShareText(t), location.origin + s.url);
    } catch (e) {
      uiAlert("Link konnte nicht erstellt werden: " + e.message);
    } finally {
      b.disabled = false;
    }
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
