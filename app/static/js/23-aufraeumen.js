/* =====================  Unbenutzte Fotos (ohne Tour) aufräumen  ===================== */
const _photosU = VIEWS.photos;
VIEWS.photos = async (...a) => {
  await _photosU(...a);
  const sec = $("#main .sec");
  if (!sec || $("#pclean") || !PHINFO || PHINFO.count === PHINFO.assigned) return;
  sec.insertAdjacentHTML("beforeend", `<button class="btn alt sm ml12" id="pclean" title="Fotos löschen, die keiner Tour zugeordnet sind">🧹 Unbenutzte Fotos aufräumen …</button>`);
  $("#pclean").onclick = cleanUnusedDialog;
};
async function cleanUnusedDialog() {
  const u = await api("/api/photos-unused");
  if (!u.count) {
    uiAlert("Alle Fotos sind einer Tour zugeordnet – es gibt nichts aufzuräumen.");
    return;
  }
  const mb = b => (b / 1048576 >= 1024 ? nf(b / 1073741824, 1) + " GB" : nf(b / 1048576, 0) + " MB");
  const m = modal(`<h2>Unbenutzte Fotos aufräumen</h2>
   <p>${nf(u.count, 0)} Fotos (${mb(u.bytes)}) sind keiner Tour zugeordnet. Du kannst sie löschen, um Platz zu schaffen.</p>
   <div class="thumbs m8-0" style="grid-template-columns:repeat(6,1fr)">${u.sample.map(i => `<img loading="lazy" src="/pic/${i}?size=200">`).join("")}</div>
   <p class="mut fs14">Stichprobe. Bitte zuerst prüfen, ob die Fotos wirklich nicht zu einer Tour gehören – oft liegt es an einer falsch gestellten Kamerauhr (Prüfen → „Kamerauhr“) oder an einer Tour, die noch nicht in der App ist.</p>
   <h3 class="m12-0-4">Welche Jahre löschen?</h3>
   <div class="rows" id="cuy">${u.years.map(y => `<label class="r g8 aic" style="display:flex"><input type="checkbox" data-y="${y.y}"><span class="fx1">${y.y}</span><span class="mut">${nf(y.n, 0)} Fotos · ${mb(y.b)}</span></label>`).join("")}</div>
   <div class="notice m12-0 fs14">Gelöscht werden nur die Kopien in der Fotobibliothek dieser App – <b>niemals deine Originale</b>. Die Fotos tauchen beim nächsten Import nicht wieder auf. Das Löschen lässt sich nicht rückgängig machen.</div>
   <div class="row"><button class="btn" id="cudo" disabled>Löschen</button><button class="btn ghost" id="cuno">Abbrechen</button><span id="cuer" class="bad"></span></div>`);
  const sel = () => [...m.querySelectorAll("[data-y]:checked")].map(x => +x.dataset.y);
  const upd = () => {
    const ys = sel(),
      n = u.years.filter(y => ys.includes(y.y)).reduce((c, y) => c + y.n, 0);
    m.querySelector("#cudo").disabled = !ys.length;
    m.querySelector("#cudo").textContent = ys.length ? `${nf(n, 0)} Fotos endgültig löschen` : "Löschen";
  };
  m.querySelector("#cuy").onchange = upd;
  m.querySelector("#cuno").onclick = () => m.remove();
  m.querySelector("#cudo").onclick = async () => {
    const ys = sel();
    if (!ys.length) return;
    m.querySelector("#cudo").disabled = true;
    try {
      const r = await api("/api/photos-unused/delete", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({years: ys})});
      m.remove();
      uiAlert(`${r.deleted} Fotos gelöscht.`);
      route();
    } catch (e) {
      m.querySelector("#cuer").textContent = e.message;
      m.querySelector("#cudo").disabled = false;
    }
  };
}
