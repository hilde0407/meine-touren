/* =====================  Ausrüstung: Rad, Schuhe, Ski … mit Kilometerstand und Wechsel-Hinweis  ===================== */
const GEAR_KINDS = ["Rad", "Schuhe", "Ski", "Schneeschuhe", "Sonstiges"];
const GEAR_ICON = {Rad: "🚲", Schuhe: "🥾", Ski: "🎿", Schneeschuhe: "❄️", Sonstiges: "🎒"};
const gJson = o => ({method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(o)});
const gStatus = g =>
  g.status === "over"
    ? `<span class="tag" style="background:#b2443f">Wechsel fällig</span>`
    : g.status === "soon"
      ? `<span class="tag" style="background:#d98a1f">bald wechseln</span>`
      : "";

/* ---------- Auswertung: Übersicht und Verwaltung ---------- */
function gearForm(g, done) {
  g = g || {sports: [], kind: "Rad"};
  const sp = Object.keys(SPORT);
  const m = modal(`<h2>${g.id ? "Ausrüstung bearbeiten" : "Neue Ausrüstung"}</h2>
   <label>Name<input id="gn" maxlength="80" value="${esc(g.name || "")}" placeholder="z. B. Rennrad Canyon, Wanderschuhe Lowa"></label>
   <label>Art<select id="gk">${GEAR_KINDS.map(k => `<option ${k === g.kind ? "selected" : ""}>${k}</option>`).join("")}</select></label>
   <div class="m10-0-4">Wird automatisch zugeordnet bei Touren der Sportart <span class="mut">(sonst wählst du es in der Tour selbst)</span></div>
   <div class="chips" id="gs">${sp.map(s => `<label class="chip ${g.sports.includes(s) ? "on" : ""} cp"><input type="checkbox" value="${s}" ${g.sports.includes(s) ? "checked" : ""} style="display:none"><i style="background:${sCol(s)}"></i>${sName(s)}</label>`).join("")}</div>
   <div class="row mt10"><label>Im Gebrauch ab<input type="date" id="gsince" value="${esc(g.since || "")}"></label><label>bis (leer = noch aktiv)<input type="date" id="guntil" value="${esc(g.until || "")}"></label></div>
   <label>Wechsel-Hinweis ab Kilometern<input type="number" id="glim" min="0" step="50" value="${g.limit_km || ""}" placeholder="z. B. 800 für Schuhe, 3000 für eine Kette"></label>
   <label>Notiz<input id="gnote" maxlength="300" value="${esc(g.note || "")}"></label>
   <div class="row mt14"><button class="btn" id="gsave">Speichern</button><button class="btn ghost" id="gcancel">Abbrechen</button><span class="sp"></span>${g.id ? `<button class="btn ghost" id="gdel">Löschen</button>` : ""}</div><div id="gerr" class="bad"></div>`);
  m.querySelectorAll("#gs input").forEach(i => (i.onchange = () => i.parentElement.classList.toggle("on", i.checked)));
  m.querySelector("#gcancel").onclick = () => m.remove();
  m.querySelector("#gsave").onclick = async () => {
    try {
      await api("/api/gear", gJson({id: g.id, name: $("#gn").value, kind: $("#gk").value, sports: [...m.querySelectorAll("#gs input:checked")].map(i => i.value), since: $("#gsince").value, until: $("#guntil").value, limit_km: $("#glim").value, note: $("#gnote").value}));
      m.remove();
      done();
    } catch (e) {
      $("#gerr").textContent = e.message;
    }
  };
  if (g.id)
    m.querySelector("#gdel").onclick = async () => {
      if (!confirm(`„${g.name}“ entfernen? Die Touren bleiben unverändert.`)) return;
      await api(`/api/gear/${g.id}`, {method: "DELETE"});
      m.remove();
      done();
    };
}

async function gearPanel() {
  const root = $("#gearsec");
  const list = await api("/api/gear");
  root.innerHTML = `<div class="sec"><h2>Ausrüstung</h2><span class="sub">${list.length ? "Kilometerstand je Rad, Schuh und Ski" : "Rad, Schuhe, Ski … – mit Kilometerstand und Wechsel-Hinweis"}</span><span class="sp"></span><button class="btn sm alt" id="gnew">+ Neue Ausrüstung</button></div>
   <div class="panel">${
     list.length
       ? `<div class="rows">${list
           .map(
             g => `<div class="r gr" data-g="${g.id}" style="${g.until ? "opacity:.6" : ""}"><span>${GEAR_ICON[g.kind] || "🎒"} ${esc(g.name)} ${gStatus(g)}<small>${esc(g.kind)}${g.until ? " · seit " + esc(g.until) + " nicht mehr im Gebrauch" : ""}${g.limit_km ? ` · Hinweis ab ${nf(g.limit_km, 0)} km` : ""}${g.note ? " · " + esc(g.note) : ""}</small></span><span class="tar"><b>${nf(g.km, 0)} km</b><small style="display:block">↑ ${nf(g.up, 0)} m · ${g.n} Touren</small></span></div>`
           )
           .join("")}</div>`
       : `<p class="mut">Noch nichts angelegt. Lege zum Beispiel dein Rad oder deine Wanderschuhe an und wähle die Sportart – dann zählt die App die Kilometer automatisch mit.</p>`
   }</div>`;
  $("#gnew").onclick = () => gearForm(null, gearPanel);
  root.querySelectorAll("[data-g]").forEach(r => (r.style.cursor = "pointer") && (r.onclick = () => gearForm(list.find(g => g.id === +r.dataset.g), gearPanel)));
}
const _places25 = VIEWS.places;
VIEWS.places = async (...a) => {
  await _places25(...a);
  const host = $("#plb") || $("#main");
  if (!host || $("#gearsec")) return;
  host.insertAdjacentHTML("beforeend", `<div id="gearsec"></div>`);
  gearPanel().catch(() => {});
};

/* ---------- Tourdetail: zugeordnete Ausrüstung ---------- */
const _tour25 = VIEWS.tour;
VIEWS.tour = async (...a) => {
  await _tour25(...a);
  const t = BY[a[0]],
    anchor = $("#ewarn");
  if (!t || !anchor || $("#gearrow")) return;
  const draw = async () => {
    const r = await api(`/api/tours/${encodeURIComponent(t.id)}/gear`).catch(() => null);
    if (!r || !r.all.length) return $("#gearrow") && $("#gearrow").remove();
    let row = $("#gearrow");
    if (!row) {
      anchor.insertAdjacentHTML("beforebegin", `<div id="gearrow" class="row mn4-0-12 g8"></div>`);
      row = $("#gearrow");
    }
    const mine = r.all.filter(g => r.ids.includes(g.id));
    row.innerHTML = `<span class="mut">Ausrüstung:</span>${mine.length ? mine.map(g => `<span class="chip on">${GEAR_ICON[g.kind] || "🎒"} ${esc(g.name)}</span>`).join("") : `<span class="mut">keine</span>`}<button class="btn ghost sm" id="gedit" title="Ausrüstung dieser Tour ändern">✎</button>`;
    $("#gedit").onclick = () => {
      const m = modal(`<h2>Ausrüstung dieser Tour</h2><label class="row g8"><input type="checkbox" id="gauto" ${r.auto ? "checked" : ""}> automatisch nach Sportart und Datum</label>
        <div id="glist" class="m10-0">${r.all.map(g => `<label class="row g8 m4-0"><input type="checkbox" value="${g.id}" ${r.ids.includes(g.id) ? "checked" : ""}> ${GEAR_ICON[g.kind] || "🎒"} ${esc(g.name)}</label>`).join("")}</div>
        <div class="row"><button class="btn" id="gok">Speichern</button><button class="btn ghost" id="gno">Abbrechen</button></div>`);
      const sync = () => m.querySelectorAll("#glist input").forEach(i => (i.disabled = $("#gauto").checked));
      $("#gauto").onchange = sync;
      sync();
      $("#gno").onclick = () => m.remove();
      $("#gok").onclick = async () => {
        await api(`/api/tours/${encodeURIComponent(t.id)}/gear`, gJson($("#gauto").checked ? {auto: true} : {ids: [...m.querySelectorAll("#glist input:checked")].map(i => +i.value)}));
        m.remove();
        draw();
      };
    };
  };
  draw();
};
