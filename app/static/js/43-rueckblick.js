/* =====================  3.26.0 Jahresrückblick als teilbare Seite: Dialog „Was wird gezeigt?“, Link, PDF (Druckansicht der öffentlichen Seite)  =====================
   Server: app/rueckblick.py (POST /api/rueckblick/share). Öffentliche Seite: rueckblick.html + seite-rueckblick.js. Link-Liste: 42-freigaben.js. */
const RB_BLOCKS = [["kennzahlen", "Kennzahlen"], ["rekorde", "Bestwerte"], ["heatmap", "Heatmap"], ["fotos", "Beste Fotos"]];
const RB_ALL = RB_BLOCKS.map(b => b[0]);
const rbTL = x => (typeof window.TL === "function" ? window.TL(x) : x);
const rbLabel = bl => (bl && bl.length ? RB_BLOCKS.filter(b => bl.includes(b[0])).map(b => rbTL(b[1])).join(", ") : "–");
const rbPref = v => {
  try { if (v === undefined) return JSON.parse(localStorage.getItem("mt_rb") || "null"); localStorage.setItem("mt_rb", JSON.stringify(v)); } catch (e) {}
  return null;
};

/* Dialog: liefert {year, sport, blocks, days} oder null. edit = nur die Auswahl eines bestehenden Links. */
async function rbDialog({year, sport, blocks, edit}) {
  const pf = !edit && rbPref(), ys = years();
  const st = {y: year || ys[0], sp: sport || "", b: new Set(blocks || (pf && pf.blocks) || RB_ALL), days: pf && pf.days != null ? pf.days : 30};
  const sports = y => [...new Set(TOURS.filter(t => t.y === y).map(t => t.sport))].sort((a, b) => TOURS.filter(t => t.y === y && t.sport === b).length - TOURS.filter(t => t.y === y && t.sport === a).length);
  const html = `<div class="shrdlg rbdlg">
    <p class="mut fs14">${edit ? "Wähle neu, was Besucher dieses Links sehen." : "Erzeugt eine Seite mit deinem Tourenjahr, die man ohne Benutzerkonto öffnen und als PDF speichern kann."} Was du nicht wählst, schickt der Server gar nicht erst mit.</p>
    ${edit ? "" : `<div class="rbrow"><label class="shrsel">Jahr<select data-rb="year">${ys.map(y => `<option value="${y}">${y}</option>`).join("")}</select></label>
    <label class="shrsel">Sportart<select data-rb="sport"></select></label></div>`}
    <fieldset class="shrfs"><legend>Was wird gezeigt?</legend><div class="flchips">${RB_BLOCKS.map(b => `<label class="flchip"><input type="checkbox" data-b="${b[0]}"> ${b[1]}</label>`).join("")}</div></fieldset>
    <p class="shrsum" role="status" aria-live="polite"><b>Dieser Link zeigt:</b> <span data-rb="sum"></span></p>
    <p class="shrnote mut fs13">Bestwerte nennen Tourname und Datum. Strecken, Startorte, Notizen, Wegpunkte und Uhr-Daten sind nie Teil eines Links.</p>
    <p class="shrwarn fs14" data-rb="none" hidden>Bitte mindestens einen Inhalt wählen.</p>
    ${edit ? "" : `<label class="shrsel">Link gültig<select data-rb="days"><option value="7">7 Tage</option><option value="30">30 Tage</option><option value="0">Unbegrenzt (bis ich ihn widerrufe)</option></select></label>`}
  </div>`;
  const ok = await uiConfirm({
    title: edit ? "Auswahl ändern" : "Jahresrückblick teilen", html, ok: edit ? "Speichern" : "Link erstellen",
    onOpen: (box, bOk) => {
      const q = s => box.querySelector(s), qa = s => [...box.querySelectorAll(s)];
      const sync = () => {
        qa("[data-b]").forEach(i => (i.checked = st.b.has(i.dataset.b)));
        q('[data-rb="sum"]').textContent = rbLabel([...st.b]);
        q('[data-rb="none"]').hidden = st.b.size > 0;
        bOk.disabled = st.b.size === 0;
      };
      const fillSports = () => {
        const sel = q('[data-rb="sport"]');
        if (!sel) return;
        const l = sports(st.y);
        if (!l.includes(st.sp)) st.sp = "";
        sel.innerHTML = `<option value="">${rbTL("Alle Sportarten")}</option>` + l.map(s => `<option value="${esc(s)}">${esc(sName(s))}</option>`).join("");
        sel.value = st.sp;
      };
      qa("[data-b]").forEach(i => (i.onchange = () => { i.checked ? st.b.add(i.dataset.b) : st.b.delete(i.dataset.b); sync(); }));
      const ye = q('[data-rb="year"]'), sp = q('[data-rb="sport"]'), dy = q('[data-rb="days"]');
      if (ye) { ye.value = String(st.y); ye.onchange = () => { st.y = +ye.value; fillSports(); }; }
      if (sp) sp.onchange = () => (st.sp = sp.value);
      if (dy) { dy.value = String(st.days); dy.onchange = () => (st.days = +dy.value); }
      fillSports();
      sync();
    },
  });
  if (!ok) return null;
  const bl = RB_ALL.filter(k => st.b.has(k));
  if (!edit) rbPref({blocks: bl, days: st.days});
  return {year: st.y, sport: st.sp, blocks: bl, days: st.days};
}

/* Ergebnis: Link kopieren/senden/öffnen und die Seite als PDF drucken */
function rbResult(s, name) {
  const u = location.origin + s.url;
  return uiAlert({
    title: "Link ist bereit", ok: "Fertig",
    html: `<div class="rbres"><p class="mut fs14">${esc(name)} – jeder mit diesem Link kann den Jahresrückblick ansehen, ohne Konto.</p>
      <input readonly class="w100" value="${esc(u)}" data-rb="url" aria-label="Link">
      <div class="row wrap mt8"><button type="button" class="btn sm" data-rb="cp">Kopieren</button>${shareCanNative() ? `<button type="button" class="btn alt sm" data-rb="sh">Senden</button>` : ""}
      <a class="btn alt sm" data-rb="open" href="${esc(u)}" target="_blank" rel="noopener">Öffnen</a><a class="btn alt sm" data-rb="pdf" href="${esc(u)}?print=1" target="_blank" rel="noopener">Als PDF speichern</a></div>
      <p class="mut fs13">„Als PDF speichern“ öffnet die Seite und startet den Druckdialog – dort „Als PDF speichern“ wählen.</p></div>`,
    onOpen: box => {
      const q = s => box.querySelector(s);
      q('[data-rb="cp"]').onclick = async e => { try { await navigator.clipboard.writeText(u); e.target.textContent = rbTL("Link kopiert"); } catch (err) { q('[data-rb="url"]').select(); } };
      const sh = q('[data-rb="sh"]');
      if (sh) sh.onclick = () => shareOut(name, name, u);
    },
  });
}

async function rbCreate(year, sport) {
  const pick = await rbDialog({year, sport});
  if (!pick) return;
  try {
    const s = await api("/api/rueckblick/share", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(pick)});
    await rbResult(s, s.title);
  } catch (e) {
    uiAlert("Link erstellen nicht möglich: " + e.message);
  }
}

/* Jahresrückblick-Seite: Knopf „Als Link teilen“ */
const _recap43 = VIEWS.recap;
if (_recap43)
  VIEWS.recap = async y => {
    await _recap43(y);
    const row = document.querySelector(".recap .noprint.row");
    if (!row || $("#rcshare")) return;
    row.insertAdjacentHTML("beforeend", `<button class="btn sm" id="rcshare" title="Jahresrückblick als Link ohne Konto teilen oder als PDF exportieren">Als Link teilen</button>`);
    $("#rcshare").onclick = () => rbCreate(+y || years()[0], "");
  };
