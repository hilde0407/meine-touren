/* =====================  Freigaben: alle geteilten Links (Touren, Diashows) an einem Ort ansehen und verwalten  ===================== */
VIEWS.links = async () => {
  const main = $("#main");
  main.innerHTML = `<div class="sec mt0"><h2>Freigegebene Links</h2><span class="sub">Alle Tour- und Diashow-Links, die du verschickt hast</span></div><div id="lkb" class="mut">Wird geladen …</div>`;
  let all = [], flt = "all";
  const now = () => Date.now() / 1000;
  const kind = x => (x.photos == 2 ? "show" : "tour");
  const dead = x => x.exp && x.exp < now();
  const fmtD = ts => (ts ? new Date(ts * 1000).toLocaleDateString("de-DE", {day: "2-digit", month: "2-digit", year: "numeric"}) : "");
  const left = x => {
    if (!x.exp) return "unbegrenzt gültig";
    if (dead(x)) return `abgelaufen am ${fmtD(x.exp)}`;
    const d = Math.ceil((x.exp - now()) / 86400);
    return `gültig bis ${fmtD(x.exp)} (noch ${d} ${d === 1 ? "Tag" : "Tage"})`;
  };
  const load = async () => {
    all = await api("/api/shares");
    draw();
  };
  const draw = () => {
    const el = $("#lkb");
    if (!el) return;
    const shows = all.filter(x => kind(x) === "show").length, exp = all.filter(dead).length;
    const list = all.filter(x => flt === "all" || (flt === "show" && kind(x) === "show") || (flt === "tour" && kind(x) === "tour") || (flt === "dead" && dead(x)));
    const chip = (k, l, n) => `<button class="btn sm ${flt === k ? "" : "alt"}" data-f="${k}">${l} (${n})</button>`;
    el.className = "";
    el.innerHTML = `<div class="row wrap mb12">${chip("all", "Alle", all.length)}${chip("show", "Diashows", shows)}${chip("tour", "Tourlinks", all.length - shows)}${chip("dead", "Abgelaufen", exp)}
      ${exp ? `<button class="btn alt sm" id="lkpurge" title="Alle abgelaufenen Links endgültig entfernen">Abgelaufene entfernen</button>` : ""}</div>
      ${
        list.length
          ? list
              .map(x => {
                const u = location.origin + "/s/" + x.token;
                const type = x.photos == 2 ? "Diashow" : x.photos ? "Tour mit Fotos" : "Tour ohne Fotos";
                const info = [type, x.photos == 2 && x.best ? `beste ${x.best} Fotos` : "", x.trim ? "Anfang/Ende ausgeblendet" : "", x.photos == 2 ? `${x.views || 0} Aufrufe` : "", x.photos == 2 ? (x.comments ? "Kommentare erlaubt" : "ohne Kommentare") : ""].filter(Boolean).join(" · ");
                return `<div class="panel mb12${dead(x) ? " mut" : ""}" data-t="${esc(x.token)}">
                  <div class="row" style="justify-content:space-between;gap:8px;flex-wrap:wrap"><b>${x.tour_id && x.name ? `<a href="#/tour/${encodeURIComponent(x.tour_id)}">${esc(x.name)}</a>` : "<i>Tour gelöscht</i>"}</b><small class="mut">erstellt ${esc(fmtD(x.ts))}</small></div>
                  <small class="mut">${esc(info)}</small><br><small class="${dead(x) ? "bad" : "mut"}">${esc(left(x))}</small>
                  <input readonly value="${esc(u)}" class="w100 mt8" data-act="select">
                  <div class="row wrap mt8">
                    <button class="btn sm" data-cp="${esc(u)}">Kopieren</button>
                    ${shareCanNative() ? `<button class="btn alt sm" data-sh="${esc(u)}" data-n="${esc(x.name || "")}">Senden</button>` : ""}
                    <a class="btn alt sm" href="${esc(u)}" target="_blank" rel="noopener">Öffnen</a>
                    <select data-d title="Laufzeit ab jetzt ändern"><option value="">Laufzeit ändern …</option><option value="7">7 Tage</option><option value="30">30 Tage</option><option value="365">1 Jahr</option><option value="0">Unbegrenzt</option></select>
                    ${x.photos == 2 ? `<button class="btn alt sm" data-c="${x.comments ? 0 : 1}">${x.comments ? "Kommentare sperren" : "Kommentare erlauben"}</button>` : ""}
                    <button class="btn alt sm" data-rv="1">Widerrufen</button>
                  </div></div>`;
              })
              .join("")
          : `<p class="mut">${all.length ? "Keine Links in dieser Auswahl." : "Noch keine Links freigegeben. In einer Tour findest du „Teilen“ und „Diashow senden“."}</p>`
      }
      <p class="mut fs13">Widerrufene und abgelaufene Links zeigen sofort „nicht mehr gültig“. Einen Link zu verlängern geht auch nachträglich.</p>`;
    el.querySelectorAll("[data-f]").forEach(b => (b.onclick = () => { flt = b.dataset.f; draw(); }));
    const tok = b => b.closest("[data-t]").dataset.t;
    const patch = async (b, body) => {
      await api("/api/share/" + encodeURIComponent(tok(b)), {method: "PATCH", headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
      await load();
    };
    el.querySelectorAll("[data-cp]").forEach(b => (b.onclick = async () => {
      try { await navigator.clipboard.writeText(b.dataset.cp); b.textContent = "✓ Kopiert"; } catch (e) { b.closest(".panel").querySelector("input").select(); }
    }));
    el.querySelectorAll("[data-sh]").forEach(b => (b.onclick = () => shareOut(b.dataset.n || "Meine Touren", b.dataset.n || "", b.dataset.sh)));
    el.querySelectorAll("[data-d]").forEach(s => (s.onchange = () => s.value !== "" && patch(s, {days: +s.value})));
    el.querySelectorAll("[data-c]").forEach(b => (b.onclick = () => patch(b, {comments: +b.dataset.c})));
    el.querySelectorAll("[data-rv]").forEach(b => (b.onclick = async () => {
      if (!await uiConfirm({text: "Diesen Link widerrufen? Wer ihn hat, kann die Freigabe danach nicht mehr öffnen.", danger: true, ok: "Widerrufen"})) return;
      await api("/api/share/" + encodeURIComponent(tok(b)), {method: "DELETE"});
      await load();
    }));
    if ($("#lkpurge")) $("#lkpurge").onclick = async () => {
      if (!await uiConfirm({text: `${exp} abgelaufene Links endgültig entfernen?`, danger: true, ok: "Entfernen"})) return;
      await api("/api/shares/purge-expired", {method: "POST"});
      await load();
    };
  };
  await load();
};

/* Zugang: Verwaltung und Benutzermenü */
const _admLk = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admLk(...a);
  const m = $("#main");
  if (m && !m.querySelector("#lklink")) m.insertAdjacentHTML("afterbegin", `<div class="row mb12"><a class="btn alt sm" id="lklink" href="#/links">🔗 Freigegebene Links verwalten</a></div>`);
};
document.addEventListener("click", e => {
  if (!e.target.closest || !e.target.closest("#umenu")) return;
  setTimeout(() => {
    const p = document.querySelector(".umpop");
    if (p && !p.querySelector('a[href="#/links"]')) p.insertAdjacentHTML("afterbegin", '<a href="#/links">Freigegebene Links</a>');
  }, 0);
}, true);
