/* =====================  Meine Geräte (Verwaltung → Touren holen): Kartenliste, Dialoge, Foto, „Aus Zepp ermitteln“  ===================== */
const DV_SVG = {
  edit: `<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>`,
  range: `<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>`,
  photo: `<svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="14" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8.5 6l1-2h5l1 2"/></svg>`,
  off: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/></svg>`,
  on: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M8 12.5l3 3 5-6"/></svg>`,
  del: `<svg viewBox="0 0 24 24"><path d="M5 7h14M10 7V4.5h4V7M7 7l1 13h8l1-13"/></svg>`,
  dots: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5.5" r="1.9"/><circle cx="12" cy="12" r="1.9"/><circle cx="12" cy="18.5" r="1.9"/></svg>`,
};
const dvJson = (m, o) => ({method: m, headers: {"content-type": "application/json"}, body: JSON.stringify(o)});
const dvBox = html => {
  const m = modal(html);
  m.querySelector(".mbox").classList.add("dvbox");
  return m;
};
const dvPeriod = g => {
  const a = dvMonth(g.since), b = dvMonth(g.until);
  if (!a && !b) return [`Zeitraum unbegrenzt`];
  return [a ? `seit ${a}` : "", b ? `bis ${b}` : "aktuell"].filter(Boolean);
};
const dvTours = n => (n === 0 ? "Noch keine Touren" : `${n} ${n === 1 ? "Tour" : "Touren"}`);

/* Aktionsmenü an einem Knopf (fest positioniert, damit nichts abgeschnitten wird) */
function dvMenu(btn, items) {
  document.querySelectorAll(".dvmenu").forEach(x => x.remove());
  const m = document.createElement("div");
  m.className = "dvmenu";
  m.setAttribute("role", "menu");
  m.innerHTML = items.map(i => (i === "-" ? "<hr>" : `<button role="menuitem" class="${i.bad ? "bad" : ""}">${i.icon || ""}<span>${i.label}</span></button>`)).join("");
  document.body.appendChild(m);
  btn.setAttribute("aria-expanded", "true");
  const r = btn.getBoundingClientRect();
  m.style.top = Math.min(r.bottom + 4, innerHeight - m.offsetHeight - 8) + "px";
  m.style.left = Math.max(8, Math.min(r.right - m.offsetWidth, innerWidth - m.offsetWidth - 8)) + "px";
  const close = () => {
    m.remove();
    btn.setAttribute("aria-expanded", "false");
    document.removeEventListener("pointerdown", out, true);
    document.removeEventListener("keydown", key, true);
    window.removeEventListener("scroll", close, true);
  };
  const out = e => { if (!m.contains(e.target) && e.target !== btn && !btn.contains(e.target)) close(); };
  const key = e => { if (e.key === "Escape") { close(); btn.focus(); } };
  document.addEventListener("pointerdown", out, true);
  document.addEventListener("keydown", key, true);
  window.addEventListener("scroll", close, true);
  [...m.querySelectorAll("button")].forEach((b, i) => (b.onclick = () => { close(); items.filter(x => x !== "-")[i].run(); }));
  const f = m.querySelector("button");
  if (f) f.focus();
}

/* ---------- Anlegen / Bearbeiten ---------- */
function devForm(dv, g, done) {
  g = g || {kind: "zepp", active: true};
  const st = {file: null, del: false, url: ""};
  const m = dvBox(`<h2>${g.id ? "Gerät bearbeiten" : "Neues Gerät"}</h2>
   <div class="dvtop"><span id="dvpv"></span><div><div class="row"><button class="btn alt sm" id="dvpick" type="button">Foto wählen</button><button class="btn ghost sm" id="dvpclr" type="button">Foto entfernen</button></div>
     <small class="dvh">Dein eigenes Foto, zum Beispiel von der Uhr am Handgelenk. Es bleibt auf deinem Server und wird auf höchstens 512 Pixel verkleinert.</small><input type="file" id="dvfile" accept="image/*" hidden></div></div>
   <div class="dvf"><label for="dvn">Name</label><input id="dvn" maxlength="80" value="${esc(g.name || "")}" placeholder="z. B. Amazfit Balance 2"><small class="dvh">So heißt das Gerät bei allen Touren („Quelle“). Du kannst es jederzeit umbenennen.</small></div>
   <div class="dvf"><label for="dvk">Art</label><select id="dvk">${dv.kinds.map(k => `<option value="${k.kind}" ${k.kind === g.kind ? "selected" : ""}>${esc(k.label)}</option>`).join("")}</select><small class="dvh">Touren einer Zepp-Uhr gehören zu einem Zepp-Gerät, Garmin-Touren zu einem Garmin-Gerät usw.</small></div>
   <div class="dvf"><label for="dvm">Modell (optional)</label><input id="dvm" maxlength="80" value="${esc(g.model || "")}" placeholder="z. B. Balance 2"><small class="dvh">Nur zur Anzeige: Das Modell steht in der Geräteliste unter dem Namen und hilft, ähnliche Geräte auseinanderzuhalten. An der Auswertung ändert es nichts.</small></div>
   <fieldset class="dvf"><legend>Im Gebrauch</legend><div class="dvf2"><div><label for="dvs">Seit</label><input type="date" id="dvs" value="${esc(g.since || "")}"></div><div><label for="dvu">Bis</label><input type="date" id="dvu" value="${esc(g.until || "")}"></div></div>
     <small class="dvh">Beides ist optional, leer heißt unbegrenzt. Hast du mehrere Geräte gleicher Art, entscheidet das Tourdatum: beim alten Gerät „Bis“, beim neuen „Seit“ eintragen.</small></fieldset>
   <div class="dvf"><label for="dvt">Notiz (optional)</label><input id="dvt" maxlength="300" value="${esc(g.note || "")}"></div>
   <label class="chk"><input type="checkbox" id="dva" ${g.active ? "checked" : ""}> Aktiv</label><small class="dvh">Deaktivierte Geräte behalten ihre Touren, ihre Messwerte werden aber eingeklappt.</small>
   <details class="dvadv" id="dvadv" ${g.zsrc ? "open" : ""}><summary>Erweitert</summary><div class="dvf"><label for="dvz">Zepp-Kennung</label><input id="dvz" maxlength="120" value="${esc(g.zsrc || "")}" placeholder="z. B. run.46.huami.com"><small class="dvh">So meldet sich die Uhr in der Zepp-Cloud. Mit Kennung werden Touren dieser Uhr auch dann richtig zugeordnet, wenn sich die Zeiträume überschneiden. Am einfachsten über „Geräte aus Zepp ermitteln“ eintragen lassen.</small></div></details>
   <div class="dvfoot"><button class="btn" id="dvsave">Speichern</button><button class="btn ghost" id="dvcancel">Abbrechen</button></div><div id="dverr" class="bad mt8"></div>`);
  const preview = () => {
    const k = $("#dvk").value;
    $("#dvpv").innerHTML = st.url ? `<span class="dvav lg"><img src="${st.url}" alt=""></span>` : g.photo && !st.del ? dvAvatar(g, "lg") : dvAvatar({kind: k}, "lg");
    $("#dvpclr").hidden = !(st.url || (g.photo && !st.del));
    $("#dvadv").hidden = !(k === "zepp" || g.zsrc);
  };
  preview();
  $("#dvk").onchange = preview;
  $("#dvpick").onclick = () => $("#dvfile").click();
  $("#dvfile").onchange = e => {
    const f = e.target.files[0];
    if (!f) return;
    if (f.size > 8 * 1048576) return ($("#dverr").textContent = "Das Bild ist zu groß (höchstens 8 MB).");
    $("#dverr").textContent = "";
    if (st.url) URL.revokeObjectURL(st.url);
    st.file = f; st.del = false; st.url = URL.createObjectURL(f);
    preview();
  };
  $("#dvpclr").onclick = () => {
    if (st.url) URL.revokeObjectURL(st.url);
    st.file = null; st.url = ""; st.del = true;
    preview();
  };
  $("#dvcancel").onclick = () => m.remove();
  $("#dvsave").onclick = async () => {
    const body = {name: $("#dvn").value, kind: $("#dvk").value, model: $("#dvm").value, since: $("#dvs").value, until: $("#dvu").value, active: $("#dva").checked, note: $("#dvt").value, zsrc: $("#dvz").value};
    $("#dvsave").disabled = true;
    try {
      let id = g.id;
      if (id) await api("/api/devices/" + id, dvJson("PATCH", body));
      else id = (await api("/api/devices", METJ(body))).id;
      if (st.file) {
        const fd = new FormData();
        fd.append("file", st.file);
        await api(`/api/my-devices/${id}/photo`, {method: "POST", body: fd});
      } else if (st.del && g.photo) await api(`/api/my-devices/${id}/photo`, {method: "DELETE"});
      MET_CACHE.clear();
      m.remove();
      done();
    } catch (e) {
      $("#dverr").textContent = e.message;
      $("#dvsave").disabled = false;
    }
  };
  setTimeout(() => $("#dvn") && $("#dvn").focus(), 30);
}

/* ---------- Touren von … bis … zuordnen ---------- */
function devRange(dv, g, done) {
  const m = dvBox(`<h2>Touren zuordnen</h2>
    <div class="dvpickrow">${dvAvatar(g, "xs")}<span><b>${esc(g.name)}</b><small>${esc(devKindLabel(dv, g.kind))}</small></span></div>
    <p>Alle Touren zwischen zwei Daten gehören ab jetzt fest zu diesem Gerät. Das ist nützlich, wenn die automatische Zuordnung nicht stimmt – zum Beispiel weil du die Uhr zwischendurch gewechselt hast.</p>
    <p class="mut">Du kannst das jederzeit bei einzelnen Touren ändern („Quelle“ → „Ändern“ → „Automatisch“).</p>
    <div class="dvf2"><div><label for="rf">Von (einschließlich)</label><input type="date" id="rf" value="${esc(g.since || "")}"></div><div><label for="rt">Bis (einschließlich)</label><input type="date" id="rt" value="${esc(g.until || "")}"></div></div>
    <p class="dvh" id="rcnt"></p>
    <div class="dvfoot"><button class="btn" id="rok">Touren zuordnen</button><button class="btn ghost" id="rno">Abbrechen</button></div><div id="rerr" class="bad mt8"></div>`);
  const count = () => {
    const a = $("#rf").value, b = $("#rt").value;
    const n = (window.TOURS || []).filter(t => { const d = String(t.date || "").slice(0, 10); return d && (!a || d >= a) && (!b || d <= b); }).length;
    $("#rcnt").innerHTML = a || b ? `<span>Das betrifft ${n} ${n === 1 ? "Tour" : "Touren"}.</span>` : `<span>Bitte mindestens ein Datum angeben.</span>`;
    $("#rok").disabled = !(a || b);
  };
  $("#rf").oninput = $("#rt").oninput = count;
  count();
  $("#rno").onclick = () => m.remove();
  $("#rok").onclick = async () => {
    try {
      const res = await api("/api/devices/assign-range", METJ({device_id: g.id, from: $("#rf").value, to: $("#rt").value}));
      m.remove();
      MET_CACHE.clear();
      alert(`${res.n} Touren zugeordnet.`);
      done();
    } catch (e) {
      $("#rerr").textContent = e.message;
    }
  };
}

/* ---------- Löschen (mit Umhängen) ---------- */
async function devDelete(dv, g, done) {
  if (!confirm(`„${g.name}“ entfernen?`)) return;
  try {
    await api("/api/devices/" + g.id, {method: "DELETE"});
    done();
  } catch (e) {
    const others = dv.devices.filter(x => x.id !== g.id);
    if (!/umhängen/.test(e.message)) return alert(e.message);
    if (!others.length) return alert(e.message + " Lege dafür zuerst ein anderes Gerät an.");
    const mv = dvBox(`<h2>Touren umhängen</h2><p>${esc(e.message)}</p><div class="dvf"><label for="mvto">Auf dieses Gerät umhängen</label><select id="mvto">${others.map(x => `<option value="${x.id}">${esc(x.name)}</option>`).join("")}</select></div>
      <div class="dvfoot"><button class="btn" id="mvok">Umhängen und löschen</button><button class="btn ghost" id="mvno">Abbrechen</button></div><div id="mverr" class="bad mt8"></div>`);
    $("#mvno").onclick = () => mv.remove();
    $("#mvok").onclick = async () => {
      try {
        await api(`/api/devices/${g.id}?move_to=${$("#mvto").value}`, {method: "DELETE"});
        mv.remove();
        MET_CACHE.clear();
        done();
      } catch (e2) {
        $("#mverr").textContent = e2.message;
      }
    };
  }
}

/* ---------- Geräte aus Zepp ermitteln ---------- */
function devZepp(dv, done) {
  const m = dvBox(`<h2>Geräte aus Zepp ermitteln</h2><p class="dvlead">Zepp merkt sich bei jedem Training, von welchem Gerät es kam. Daraus lässt sich ablesen, welche Uhren du hattest und wann.</p><div id="zbody"><span class="dvspin"></span><span>Zepp-Verlauf wird gelesen – das kann bei vielen Trainings eine Weile dauern …</span></div>`);
  const body = $("#zbody");
  const fail = msg => {
    body.innerHTML = `<p class="bad">${esc(msg)}</p><p class="mut">Zugangsdaten bzw. Token prüfst du in der Verwaltung beim Zepp-Import.</p><div class="dvfoot"><button class="btn ghost" id="zclose">Schließen</button></div>`;
    $("#zclose").onclick = () => m.remove();
  };
  api("/api/devices/zepp-probe", {method: "POST"}).then(res => {
    const src = res.sources;
    if (!src.length) return fail("Zepp hat keine Trainings mit Quellenkennung gemeldet." + (res.sample_keys.length ? " Felder eines Trainings: " + res.sample_keys.join(", ") : ""));
    const latest = src.reduce((a, b) => (b.last > a.last ? b : a));
    const free = dv.devices.filter(x => x.kind === "zepp" && !x.zsrc);
    body.innerHTML = `<p>${src.length === 1 ? `Zepp meldet ${res.total} Trainings von einer Quelle.` : `Zepp meldet ${res.total} Trainings von ${src.length} Quellen.`}</p><p class="mut">Prüfe die Vorschläge, ändere sie nach Bedarf und wähle, was angelegt werden soll. Vorher wird nichts gespeichert.</p>
      <div class="dvprobe">${src.map((x, i) => `<div class="dvpr ${x.device ? "dis" : ""}" data-i="${i}">
        <label class="chk"><input type="checkbox" class="zon" ${x.device ? "disabled" : "checked"}> <span>${x.device ? `Bereits angelegt als „${esc(x.device.name)}“` : x.model || (src.length > 1 ? `Zepp-Uhr ${i + 1}` : "Zepp-Uhr")}</span></label>
        <div class="dvmeta"><span>Zepp meldet: </span><code>${esc(x.zsrc)}</code> · <span>${x.n} Trainings</span> · <span>${esc(dvDay(x.first))} bis ${esc(dvDay(x.last))}</span><br><span>${x.sports.slice(0, 4).map(s => `${esc(s.label)} ${s.n}`).join(", ")}</span></div>
        ${x.model && !x.model_sure && !x.device ? `<div class="dvwarn"><b>Vermutlich ${esc(x.model)}.</b> Die Kennung ist nur ein Codename der Uhren-Generation, kein Modell. Bitte prüfen und bei Bedarf ändern.</div>` : ""}
        ${!x.model && !x.device ? `<div class="dvwarn">Zepp nennt hier nur eine allgemeine Altnummer, kein Modell. Vergib selbst einen Namen – am Zeitraum erkennst du die Uhr.</div>` : ""}
        ${x.overlaps.length ? `<div class="dvwarn">Der Zeitraum überschneidet sich mit einer anderen Quelle. Zepp kann Uhr und Handy-App parallel melden – bitte prüfen, ob das wirklich zwei Geräte sind.</div>` : ""}
        ${x.device ? "" : `<div class="zfields">
          ${free.length ? `<div class="dvf"><label>Was soll damit passieren?</label><select class="zat"><option value="0">Als neues Gerät anlegen</option>${free.map(f => `<option value="${f.id}">Kennung zu „${esc(f.name)}“ hinzufügen</option>`).join("")}</select></div>` : ""}
          <div class="dvf2 zn"><div><label>Name</label><input class="znm" maxlength="80" value="${esc(x.model || (src.length > 1 ? `Zepp-Uhr ${i + 1}` : "Zepp-Uhr"))}"></div><div><label>Modell (optional)</label><input class="zmo" maxlength="80" value="${esc(x.model)}" placeholder="z. B. Balance 2"></div></div>
          <div class="dvf2 zd"><div><label>Seit</label><input type="date" class="zs" value="${esc(x.first)}"></div><div><label>Bis (leer = aktuell)</label><input type="date" class="zu" value="${x === latest ? "" : esc(x.last)}"></div></div></div>`}</div>`).join("")}</div>
      <small class="dvh">Das Modell wird anhand der Zepp-Geräteliste erkannt, soweit die Kennung dort vorkommt; sonst trage es selbst ein.</small>
      <details class="dvadv"><summary>Technische Angaben</summary><p class="dvmeta">Felder eines Zepp-Trainings: ${res.sample_keys.map(k => `<code>${esc(k)}</code>`).join(" ")}</p></details>
      <div class="dvfoot"><button class="btn" id="zok">Ausgewählte übernehmen</button><button class="btn ghost" id="zno">Abbrechen</button></div><div id="zerr" class="bad mt8"></div>`;
    $("#zno").onclick = () => m.remove();
    body.querySelectorAll(".dvpr").forEach(r => {
      const upd = () => {
        const on = r.querySelector(".zon").checked, at = r.querySelector(".zat");
        r.querySelectorAll(".zfields input").forEach(x => (x.disabled = !on || !!(at && +at.value)));
        if (at) at.disabled = !on;
        r.classList.toggle("dis", !on);
      };
      r.querySelector(".zon").onchange = upd;
      if (r.querySelector(".zat")) r.querySelector(".zat").onchange = upd;
    });
    $("#zok").onclick = async () => {
      const items = [];
      body.querySelectorAll(".dvpr").forEach(r => {
        const x = src[+r.dataset.i], on = r.querySelector(".zon");
        if (x.device || !on.checked) return;
        const at = r.querySelector(".zat");
        items.push({zsrc: x.zsrc, attach_to: at ? +at.value : 0, name: r.querySelector(".znm").value, model: r.querySelector(".zmo").value, since: r.querySelector(".zs").value, until: r.querySelector(".zu").value});
      });
      if (!items.length) return ($("#zerr").textContent = "Bitte mindestens eine Quelle auswählen.");
      $("#zok").disabled = true;
      try {
        await api("/api/devices/zepp-apply", METJ({devices: items}));
        MET_CACHE.clear();
        m.remove();
        done();
      } catch (e) {
        $("#zerr").textContent = e.message;
        $("#zok").disabled = false;
      }
    };
  }).catch(e => fail(e.message));
}
const dvDay = d => (/^\d{4}-\d\d-\d\d$/.test(d || "") ? `${d.slice(8)}.${d.slice(5, 7)}.${d.slice(0, 4)}` : d || "");

/* ---------- Abschnitt in der Verwaltung ---------- */
async function devPanel() {
  const root = $("#devsec");
  if (!root) return;
  const [dv, sug] = await Promise.all([api("/api/my-devices"), api("/api/devices/suggestions").catch(() => [])]);
  const hidden = k => { try { return localStorage.getItem("mt_devsug_" + k) === "1"; } catch (e) { return false; } };
  const sugs = dv.devices.length ? sug.filter(s => !hidden(s.kind)) : [];
  const viewer = typeof isViewer === "function" && isViewer();
  const card = g => `<div class="dvcard ${g.active ? "" : "off"}" data-dv="${g.id}">${dvAvatar(g)}<div class="dvbody">
      <div class="dvn">${esc(g.name)}</div>
      <span class="dvsub">${esc(devKindLabel(dv, g.kind))}${g.model ? ` · ${esc(g.model)}` : ""}</span>
      ${!g.model && g.zsrc ? `<span class="dvsub">Zepp meldet: ${esc(g.zsrc)}</span>` : ""}
      <span class="dvper">${dvPeriod(g).map(x => `<span>${esc(x)}</span>`).join("")}</span>
      ${g.note ? `<span class="dvsub">${esc(g.note)}</span>` : ""}
      <div class="dvchips"><span class="dvc ${g.active ? "on" : ""}">${g.active ? "Aktiv" : "Deaktiviert"}</span><span class="dvc">${dvTours(g.n)}</span></div></div>
      ${viewer ? "" : `<button class="dvmore" aria-haspopup="menu" aria-expanded="false" title="Aktionen" aria-label="Aktionen">${DV_SVG.dots}</button>`}</div>`;
  const empty = `<div class="dvempty"><span class="dvav">${dvIcon("zepp")}</span><h3>Noch kein Gerät angelegt</h3>
      <p>Lege deine Uhren und Handys an, damit bei jeder Tour steht, womit sie aufgezeichnet wurde.</p>
      ${viewer ? "" : `<div class="row"><button class="btn" id="dvzepp">Gerät aus Zepp ermitteln</button><button class="btn alt" id="dvnew2">Gerät von Hand anlegen</button></div>`}</div>`;
  root.innerHTML = `<div class="dvhead"><h2>Meine Geräte</h2><span class="sp"></span>${viewer || !dv.devices.length ? "" : `<button class="btn alt sm" id="dvmatch" title="Alle Touren mit passendem Zepp-Training dem richtigen Gerät zuordnen">Touren automatisch zuordnen</button><button class="btn alt sm" id="dvzepp">Geräte aus Zepp ermitteln</button><button class="btn sm" id="dvnew">+ Gerät anlegen</button>`}</div>
    <p class="mut dvintro">Deine Aufnahmegeräte mit eigenem Namen. Der Name erscheint bei jeder Tour als „Quelle“; welche Messwerte eine Tour zeigt, richtet sich nach dem, was das Gerät wirklich geliefert hat.</p>
    ${sugs.map(s => `<div class="dvhint" data-sug="${esc(s.kind)}"><span><b>${esc(s.label)}: ${s.n} ${s.n === 1 ? "Tour" : "Touren"} ohne Gerät</b><span class="mut">Möchtest du dafür ein Gerät anlegen? Es wird nichts ohne deine Bestätigung angelegt.</span></span>
      <button class="btn sm" data-sy="${esc(s.kind)}" data-nm="${esc(s.name)}">Gerät anlegen …</button><button class="btn ghost sm" data-sn="${esc(s.kind)}">Nicht jetzt</button></div>`).join("")}
    ${dv.devices.length ? `<div class="dvlist">${dv.devices.map(card).join("")}</div>` : empty}`;
  const again = () => devPanel().catch(() => {});
  const bz = $("#dvzepp"), bn = $("#dvnew") || $("#dvnew2");
  if (bz) bz.onclick = () => devZepp(dv, again);
  const bm = $("#dvmatch");
  if (bm) bm.onclick = async () => {
    bm.disabled = true; bm.textContent = "Wird zugeordnet …";
    try {
      await api("/api/jobs/dev-match", {method: "POST"});
      for (let i = 0; i < 120; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const j = await api("/api/jobs").catch(() => null);
        if (!j || !j.running) break;
      }
    } catch (e) { alert(e.message); }
    await loadTours().catch(() => {});
    again();
  };
  if (bn) bn.onclick = () => devForm(dv, null, again);
  root.querySelectorAll("[data-dv]").forEach(r => {
    const g = dv.devices.find(x => x.id === +r.dataset.dv);
    if (viewer) return;
    r.onclick = e => { if (!e.target.closest(".dvmore")) devForm(dv, g, again); };
    const mb = r.querySelector(".dvmore");
    mb.onclick = e => {
      e.stopPropagation();
      dvMenu(mb, [
        {icon: DV_SVG.edit, label: "Bearbeiten", run: () => devForm(dv, g, again)},
        {icon: DV_SVG.photo, label: g.photo ? "Foto ändern oder entfernen" : "Foto hinzufügen", run: () => devForm(dv, g, again)},
        {icon: DV_SVG.range, label: "Touren zuordnen …", run: () => devRange(dv, g, again)},
        {icon: g.active ? DV_SVG.off : DV_SVG.on, label: g.active ? "Deaktivieren" : "Aktivieren", run: async () => {
          try { await api("/api/devices/" + g.id, dvJson("PATCH", {active: !g.active})); MET_CACHE.clear(); } catch (er) { alert(er.message); }
          again();
        }},
        "-",
        {icon: DV_SVG.del, label: "Löschen …", bad: true, run: () => devDelete(dv, g, again)},
      ]);
    };
  });
  root.querySelectorAll("[data-sy]").forEach(b => (b.onclick = () => devForm(dv, {kind: b.dataset.sy, name: b.dataset.nm, active: true}, again)));
  root.querySelectorAll("[data-sn]").forEach(b => (b.onclick = () => {
    try { localStorage.setItem("mt_devsug_" + b.dataset.sn, "1"); } catch (e) {}
    again();
  }));
}
const _adm44 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm44(...a);
  const host = document.querySelector('.atab[data-t="quellen"] .gbody') || $("#main");
  if (!host || $("#devsec")) return;
  host.insertAdjacentHTML("afterbegin", `<div class="panel acard" id="devsec"></div>`);
  devPanel().catch(() => {});
};
