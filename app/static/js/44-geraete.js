/* =====================  Meine Geräte (Verwaltung → Touren holen): Kartenliste, Dialoge, Foto, „Aus Zepp ermitteln“  ===================== */
const DV_SVG = {
  edit: `<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>`,
  range: `<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>`,
  photo: `<svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="14" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8.5 6l1-2h5l1 2"/></svg>`,
  off: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/></svg>`,
  on: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M8 12.5l3 3 5-6"/></svg>`,
  del: `<svg viewBox="0 0 24 24"><path d="M5 7h14M10 7V4.5h4V7M7 7l1 13h8l1-13"/></svg>`,
  info: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.1"/></svg>`,
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
/* „Das liefert diese Uhr“: Kanäle, die bei mindestens 20 % der Touren des Geräts vorkommen (aus den Messwert-Zusatzdateien) */
const dvGives = q => (!q || !q.n_tours ? "" : `<span class="dvsub dvgive"><b>Das liefert diese Uhr:</b> ${q.channels.length ? q.channels.map(c => `<span class="dvch" title="bei ${c.share} % der Touren">${esc(c.label)}</span>`).join(" ") : `<span class="mut">noch keine Messwerte erkannt (Verwaltung → „Messwerte nachladen“)</span>`}</span>`);
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
      uiAlert({title: "Touren zugeordnet", text: `${res.n} Touren zugeordnet.`});
      done();
    } catch (e) {
      $("#rerr").textContent = e.message;
    }
  };
}

/* ---------- Löschen (mit Umhängen) ---------- */
async function devDelete(dv, g, done) {
  if (!(await uiConfirm({title: "Gerät entfernen?", text: `„${g.name}“ entfernen?`, ok: "Entfernen", danger: true}))) return;
  try {
    await api("/api/devices/" + g.id, {method: "DELETE"});
    done();
  } catch (e) {
    const others = dv.devices.filter(x => x.id !== g.id);
    if (!/umhängen/.test(e.message)) return uiAlert({title: "Nicht möglich", text: e.message});
    if (!others.length) return uiAlert({title: "Nicht möglich", text: e.message + " Lege dafür zuerst ein anderes Gerät an."});
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

/* ---------- Genauigkeit der Uhren (3.10.0): Kennzahlen, Punktdiagramm, auffällige Touren, Korrekturvorschläge ---------- */
const DVQ_OPEN = new Set();
/* Zustand „Genauigkeit aufgeklappt“ je Gerät: im Speicher und im Browser (localStorage, mit try/catch) */
const dvqOpen = id => { if (DVQ_OPEN.has(id)) return true; try { return localStorage.getItem("mt_dvq_" + id) === "1"; } catch (e) { return false; } };
const DVQ_CLS = {"gut": "ok", "mäßig": "warn", "auffällig": "bad"};
const dvPct = v => (v > 0.04 ? "+" : v < -0.04 ? "−" : "") + nf(Math.abs(v), 1) + " %";
const dvQTime = ts => (ts ? new Date(ts * 1000).toLocaleDateString("de-DE", {day: "2-digit", month: "2-digit", year: "numeric"}) : "");

/* Punktdiagramm: jeder Punkt eine Tour, Balken = mittlere Hälfte (25.–75. Perzentil), Strich = Median; Hintergrund = Bewertungsstufen */
function dvDots(a, lim, good, ok, label) {
  const W = 320, H = 74, pad = 14, x = v => pad + ((Math.max(-lim, Math.min(lim, v)) + lim) / (2 * lim)) * (W - 2 * pad);
  const band = (w, c) => `<rect class="dvb ${c}" x="${x(-w)}" y="6" width="${x(w) - x(-w)}" height="34"/>`;
  const dots = a.points.map((v, i) => `<circle class="dvdot" cx="${x(v).toFixed(1)}" cy="${(13 + ((i * 37) % 9) * 2.6).toFixed(1)}" r="2.6"/>`).join("");
  const box = a.p25 != null ? `<rect class="dvbox2" x="${x(a.p25).toFixed(1)}" y="45" width="${Math.max(2, x(a.p75) - x(a.p25)).toFixed(1)}" height="9" rx="2"/><line class="dvmed" x1="${x(a.median).toFixed(1)}" x2="${x(a.median).toFixed(1)}" y1="43" y2="56"/>` : "";
  const desc = `${label}: ${a.points.length} Touren, Median ${dvPct(a.median)}, mittlere Hälfte ${dvPct(a.p25)} bis ${dvPct(a.p75)}`;
  return `<svg class="dvdots" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(desc)}"><rect class="dvb bad" x="${pad}" y="6" width="${W - 2 * pad}" height="34"/>${band(ok, "warn")}${band(good, "ok")}
    <line class="dvzero" x1="${x(0)}" x2="${x(0)}" y1="6" y2="40"/>${dots}${box}
    <text class="dvax" x="${pad}" y="70" text-anchor="start">${dvPct(-lim).replace(" %", "")} %</text><text class="dvax" x="${x(0)}" y="70" text-anchor="middle">0</text><text class="dvax" x="${W - pad}" y="70" text-anchor="end">${dvPct(lim)}</text></svg>`;
}

/* Einklappbare Abschnitte der Genauigkeit: einheitlicher Kopf (Titel + Kennzeichen), Zustand je Abschnitt im Browser (localStorage, mit try/catch).
   Wichtiges ist standardmäßig offen, Erläuterungen sind zu. */
const dvSecOpen = (id, def) => { try { const v = localStorage.getItem("mt_dvsec_" + id); return v === null ? def : v === "1"; } catch (e) { return def; } };
const dvSec = (id, title, badge, body, def = true) => { const o = dvSecOpen(id, def); return `<details class="dvsec" data-sec="${id}" ${o ? "open" : ""}><summary aria-expanded="${o}"><span class="dvsect">${title}</span>${badge || ""}</summary><div class="dvsecb">${body}</div></details>`; };
function dvSecWire(root) {
  root.querySelectorAll("details.dvsec").forEach(d => d.addEventListener("toggle", () => {
    d.querySelector("summary").setAttribute("aria-expanded", d.open ? "true" : "false");
    try { localStorage.setItem("mt_dvsec_" + d.dataset.sec, d.open ? "1" : "0"); } catch (e) {}
  }));
}
/* Fortschrittsbalken (ruhender Zustand): role=progressbar mit aria-valuenow; die Zahl steht zusätzlich als Text daneben */
const dvBar = (done, total, label) => `<div class="dvbar" role="progressbar" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${done}" aria-label="${esc(label)}"><span style="width:${total ? Math.round((100 * done) / total) : 0}%"></span></div>`;
const dvOpenText = n => (n === 1 ? "Noch 1 Tour offen – erneut starten." : `Noch ${n} Touren offen – erneut starten.`);

function dvQBody(q, g, viewer) {
  const pr = g.progress || {total: 0, done: 0, open: 0, n_detail: 0, n_summary: 0};
  const run = viewer ? "" : `<button class="btn ${pr.open && g.n_eval ? "" : "alt "}sm dvqrun" type="button">${pr.open && g.n_eval ? "Weiter auswerten" : "Genauigkeit auswerten"}</button>`;
  const prog = `<span class="dvqprog" role="status" aria-live="polite"></span>`;
  if (!g.n_eval) {
    return `<div class="dvqempty"><p><b>Noch nicht ausgewertet.</b></p>
      <p>Die App vergleicht, was die Uhr gemessen hat, mit der Strecke der Tour, dem Geländemodell und der gespeicherten GPS-Spur. Dafür braucht sie:</p>
      <ul><li>Touren, die dieser Uhr zugeordnet sind${g.n_tours ? ` (aktuell: ${g.n_tours})` : " – siehe „Touren automatisch zuordnen“"}.</li>
      ${g.kind === "zepp" ? `<li>${q.zepp_configured ? "Den Zepp-Zugang aus der Verwaltung (ist eingerichtet) – damit lassen sich auch Komoot-Touren mit dem Training der Uhr vergleichen." : "Einen Zepp-Zugang in der Verwaltung – ohne ihn bleiben Strecke und Höhe bei Komoot-Touren leer."}</li>` : ""}</ul>
      <p class="mut">Die Auswertung liest nur und verändert keine Tour.</p><div class="row">${run}${prog}</div></div>`;
  }
  const v = g.verdict, cls = DVQ_CLS[v.level] || "none";
  const tile = (lab, val, sub, a, rough) => `<div class="dvk"><span class="dvkl">${lab}</span><span class="dvkv">${val}</span><span class="dvks ${a && a.level ? DVQ_CLS[a.level] : "none"}">${a && a.level ? a.level + (rough ? " (grob)" : "") : "keine Einschätzung"}</span><span class="dvkn">${sub}</span></div>`;
  const d = g.dist, h = g.height, p = g.gps, r = g.hr;
  const tiles = [
    tile("Strecke", d.n ? dvPct(d.median) : "–", d.n ? `${d.n} ${d.n === 1 ? "Tour" : "Touren"} verglichen${d.n_implausible ? `, ${d.n_implausible} unplausibel` : ""}` : d.n_implausible ? `${d.n_implausible} unplausibel` : "nicht vergleichbar", d),
    tile("Höhe", h.n_pct ? dvPct(h.up_err_pct.median) : "–", h.n ? `${h.n} ${h.n === 1 ? "Tour" : "Touren"}${h.rough ? " (grob)" : ""}, Aufstieg ${h.up_err_m.median > 0 ? "+" : h.up_err_m.median < 0 ? "−" : ""}${nf(Math.abs(h.up_err_m.median), 0)} m` : "nicht vergleichbar", h, h.rough),
    tile("GPS-Spur", p.n ? `${nf(p.jump_tours_pct, 0)} %` : "–", p.n ? `Touren mit Sprüngen (von ${p.n})` : "keine Spur", p),
    tile("Puls", r.n ? `${nf(r.bad_tours_pct, 0)} %` : "–", r.n ? `Touren mit Aussetzern (von ${r.n})` : "kein Puls", r),
  ].join("");
  const th = q.thresholds;
  const chart = (a, lim, t, title, cap) => (a.points && a.points.length >= 2 ? `<figure class="dvfig"><figcaption>${title}</figcaption>${dvDots(a, lim, t[0], t[1], title)}<small class="dvh">${cap} ${dvPct(a.p25)} bis ${dvPct(a.p75)}, Median ${dvPct(a.median)}.</small></figure>` : "");
  const hs = h.up_err_pct;
  /* genau (Track der Uhr oder abgerufenes Zepp-Detail) und grob (nur Zusammenfassung der Uhr) bleiben getrennt und sind so benannt */
  const split = h.n_summary ? `<div class="dvsplit" role="group" aria-label="Höhenvergleich: genau und grob"><span class="dvsl">Mit Detail (genau)</span><b>${dvTours(h.n_detail || 0)}</b><span class="dvsl">Nur Zusammenfassung (grob)</span><b>${dvTours(h.n_summary)}</b></div>
    <span class="dvh dvsplith">Grobe Werte kommen aus dem Auf- und Abstieg, den die Uhr selbst meldet; sie haben großzügigere Grenzen (gut bis ${nf(th.height_summary[0], 0)} %, mäßig bis ${nf(th.height_summary[1], 0)} %) und werden nicht mit den genauen Werten vermischt.</span>${h.rough ? `<span class="dvh dvsplith">Die Einschätzung der Höhe beruht hier nur auf den groben Werten.</span>` : ""}` : "";
  const stand = `<div class="dvstand">${pr.total ? dvBar(pr.done, pr.total, "Fortschritt der Auswertung") : ""}
    <p class="mut dvqwhen">Zuletzt ausgewertet am ${esc(dvQTime(q.computed_at))}${pr.total ? `, ${pr.done} von ${pr.total} Touren` : ""}.</p>
    ${pr.open ? `<p class="dvopen" role="status"><b>${dvOpenText(pr.open)}</b><span class="dvh">Offen sind Touren, bei denen noch Geländekacheln oder Zepp-Details fehlen. Je Lauf gibt es Obergrenzen, damit nichts überlastet wird.</span></p>` : ""}
    <div class="row dvqfoot">${run}${prog}</div></div>`;
  const bat = g.batch && !viewer ? dvSec("batch", "Sammel-Korrektur", g.batch.n_done ? `<span class="dvqs ok">${g.batch.n_done}</span>` : `<span class="dvqs none">zurückgenommen</span>`,
    `<p class="dvbatchl">${g.batch.n_done ? `Letzter Sammel-Lauf am ${esc(dvQTime(g.batch.ts))}: ${g.batch.n_done} ${g.batch.n_done === 1 ? "Tour" : "Touren"} korrigiert (${g.batch.method === "zepp" ? "Höhe von der Uhr" : "Höhe aus dem Geländemodell"}), Aufstieg zusammen ${g.batch.delta_up > 0 ? "+" : g.batch.delta_up < 0 ? "−" : ""}${nf(Math.abs(g.batch.delta_up), 0)} m.` : `Der letzte Sammel-Lauf vom ${esc(dvQTime(g.batch.ts))} ist zurückgenommen.`}</p>
     ${g.batch.n_done ? `<button class="btn alt sm dvundo" type="button" data-batch="${esc(g.batch.id)}">Alles rückgängig machen</button><span class="dvh">Nur dieser Lauf wird zurückgenommen; Touren, die du inzwischen selbst geändert hast, bleiben unberührt.</span>` : ""}`, true) : "";
  const batchBtn = !viewer && g.flagged_height ? `<div class="dvbatchbar"><button class="btn sm dvbatch" type="button">Alle auffälligen Höhen korrigieren …</button><span class="dvh">Du siehst vorher eine Liste und entscheidest, was geändert wird.</span></div>` : "";
  return `<div class="dvqv ${cls}"><b>${esc(v.label)}</b>${g.period ? `<span class="mut"> · ${esc(dvDay(g.period.from))} bis ${esc(dvDay(g.period.to))}</span>` : ""}</div>
    <ul class="dvfind">${v.findings.map(f => `<li>${esc(f)}</li>`).join("")}</ul>
    <div class="dvkpi">${tiles}</div>
    ${split}
    <div class="dvfigs">${chart(d, 20, th.dist, "Strecke: Abweichung der Uhr je Tour", "Mittlere Hälfte der Touren:")}${hs.n ? chart({points: h.points, p25: hs.p25, p75: hs.p75, median: hs.median}, 60, th.height, "Aufstieg: Abweichung vom Geländemodell je Tour", "Mittlere Hälfte der Touren:") : ""}</div>
    ${g.tips.map(t => `<p class="dvtip">${esc(t.text)}</p>`).join("")}
    ${dvSec("stand", "Auswertungsstand", pr.open ? `<span class="dvqs warn">noch ${pr.open} offen</span>` : `<span class="dvqs ok">vollständig</span>`, stand, true)}
    <details class="dvhow"><summary>Wie wird bewertet?</summary><p class="dvh">Strecke: gut bis ${nf(th.dist[0], 0)} %, mäßig bis ${nf(th.dist[1], 0)} % mittlere Abweichung. Höhe: gut bis ${nf(th.height[0], 0)} %, mäßig bis ${nf(th.height[1], 0)} % gegenüber dem Geländemodell (das Modell glättet Gelände und unterschätzt Aufstiege etwas). GPS-Spur: gut, wenn höchstens ${nf(th.gps[0], 0)} % der Touren Sprünge haben, mäßig bis ${nf(th.gps[1], 0)} %. Puls: gut, wenn höchstens ${nf(th.hr[0], 0)} % der Touren Aussetzer haben, mäßig bis ${nf(th.hr[1], 0)} %. Eine Einschätzung gibt es ab ${q.min_n} verglichenen Touren. Strecke und Höhe der Touren werden dabei nie verändert.</p></details>
    ${dvSec("auff", "Auffällige Touren", g.flagged ? `<span class="dvqs warn">${g.flagged}</span>` : `<span class="dvqs ok">keine</span>`, `${batchBtn}<div class="dvbad" data-bad="${g.id}">${g.flagged ? `<div class="dvbadl mut">Wird geladen …</div>` : `<p class="mut">Keine auffälligen Touren.</p>`}</div>`, true)}
    ${bat}`;
}

const DVQ_FLAG = f => ({
  dist_implausible: `Strecke unplausibel: Uhr ${nf((f.dev_m || 0) / 1000, 1)} km, Tour ${nf((f.tour_m || 0) / 1000, 1)} km`,
  dist: `Strecke ${nf(Math.abs(f.pct), 1)} % ${f.pct < 0 ? "kürzer" : "länger"}`,
  height: `Aufstieg ${nf(f.up_dev, 0)} m laut Uhr, ${nf(f.up_dem, 0)} m laut Gelände${f.rough ? " (grob)" : ""}`,
  gps_jumps: `${f.n} ${f.n === 1 ? "GPS-Sprung" : "GPS-Sprünge"}`,
  gps_gaps: `${nf(f.pct, 0)} % Lücken oder Pausen`,
  hr: `${nf(f.pct, 0)} % Puls unplausibel`,
}[f.kind] || f.kind);

async function dvQBad(box, g, viewer, again) {
  const host = box.querySelector(".dvbadl");
  if (!host) return;
  try {
    const r = await api(`/api/devices/${g.id}/quality/tours?limit=60`);
    host.className = "dvbadl";
    host.innerHTML = r.tours.length ? `<ul class="dvbadul">${r.tours.map((t, i) => `<li><div class="dvbt"><a href="#/tour/${encodeURIComponent(t.id)}">${esc(t.name)}</a><span class="mut">${esc(dvDay(t.day))}</span></div>
        <div class="dvchips">${t.flags.map(f => `<span class="dvc fl ${f.kind === "dist_implausible" || f.kind === "gps_jumps" ? "bad" : "warn"}">${esc(DVQ_FLAG(f))}</span>`).join("")}${t.fixed ? `<span class="dvc">${t.fixed === "zepp" ? "Höhe aus Uhr übernommen" : "Höhe aus Gelände übernommen"}</span>` : ""}</div>
        ${viewer ? "" : `<button class="btn alt sm" type="button" data-i="${i}">Korrektur vorschlagen</button>`}</li>`).join("")}</ul>${r.total > r.tours.length ? `<p class="mut">Gezeigt werden die ${r.tours.length} auffälligsten von ${r.total}.</p>` : ""}` : `<p class="mut">Keine auffälligen Touren.</p>`;
    host.querySelectorAll("button[data-i]").forEach(b => (b.onclick = () => dvSuggest(r.tours[+b.dataset.i], g, again)));
    const lis = [...host.querySelectorAll(".dvbadul li")];
    if (lis.length > 8) {
      lis.slice(8).forEach(li => (li.hidden = true));
      const more = document.createElement("button");
      more.type = "button"; more.className = "btn ghost sm dvmoreb"; more.textContent = `Alle ${lis.length} zeigen`;
      more.onclick = () => { lis.forEach(li => (li.hidden = false)); more.remove(); };
      host.appendChild(more);
    }
  } catch (e) {
    host.innerHTML = `<span class="bad">${esc(e.message)}</span>`;
  }
}

/* Korrektur vorschlagen: nur Vorschläge – jede Aktion läuft erst nach Bestätigung und ist (Höhe) rückgängig zu machen */
function dvSuggest(t, g, again) {
  const info = {
    "elev-dem": "Rechnet Auf- und Abstieg aus dem Geländemodell neu (Kartendaten werden bei Bedarf aus dem Internet geladen). Das Original bleibt gespeichert.",
    "elev-zepp": "Übernimmt den Höhenverlauf der barometrischen Uhr aus der Zepp-Cloud. Das Original bleibt gespeichert.",
    "trackfix": "Öffnet die Track-Korrektur: Du siehst zuerst die gefundenen Sprünge und entscheidest dort, was entfernt wird. Das Original bleibt erhalten.",
    "elev-restore": "Stellt die ursprünglichen Höhen und Höhenmeter wieder her.",
  };
  const m = dvBox(`<h2>Korrektur vorschlagen</h2><p class="dvlead"><b>${esc(t.name)}</b> · ${esc(dvDay(t.day))}</p>
    <div class="dvchips">${t.flags.map(f => `<span class="dvc fl ${f.kind === "dist_implausible" || f.kind === "gps_jumps" ? "bad" : "warn"}">${esc(DVQ_FLAG(f))}</span>`).join("")}</div>
    <p class="mut">Es passiert nichts, bevor du es bestätigst. Strecke und Zeit der Tour werden hier nicht geändert.</p>
    <div class="dvsug">${t.suggest.map((s, i) => `<div class="dvsg"><div><b>${esc(s.label)}</b><small class="dvh">${esc(info[s.action] || s.label)}</small>${s.action === "info" ? "" : ""}</div>${s.action === "info" ? "" : `<button class="btn alt sm" data-i="${i}" type="button">${s.action === "trackfix" ? "Öffnen …" : "Ausführen …"}</button>`}</div>`).join("")}</div>
    <div class="dvsres" role="status" aria-live="polite"></div>
    <div class="dvfoot"><button class="btn ghost" id="dvsx">Schließen</button></div>`);
  let changed = false;                       // nach einer Korrektur verschwindet die Tour beim Schließen aus der Liste
  $("#dvsx").onclick = () => { m.remove(); if (changed) again(); };
  const res = m.querySelector(".dvsres");
  m.querySelectorAll(".dvsug button[data-i]").forEach(b => (b.onclick = async () => {
    const s = t.suggest[+b.dataset.i];
    if (s.action === "trackfix") { m.remove(); return trackFixDialog(t.id, () => { MET_CACHE.clear(); loadTours().catch(() => {}); again(); }); }
    if (!(await uiConfirm({title: `${s.label}?`, text: info[s.action] || "", ok: "Ausführen"}))) return;
    b.disabled = true;
    res.textContent = "Wird ausgeführt …";
    try {
      const r = await api(s.url, {method: s.method || "POST"});
      changed = true;
      MET_CACHE.clear();
      await loadTours().catch(() => {});
      if (s.undo) {
        res.innerHTML = `<p><b>Übernommen:</b> Aufstieg ${nf(r.up_m ?? r.up, 0)} m, Abstieg ${nf(r.down_m ?? r.down, 0)} m (vorher ${nf(r.orig_up, 0)} m / ${nf(r.orig_down, 0)} m).</p><button class="btn alt sm" id="dvsundo" type="button">Rückgängig machen</button>`;
        $("#dvsundo").onclick = async () => {
          try { await api(s.undo, {method: "POST"}); changed = true; MET_CACHE.clear(); await loadTours().catch(() => {}); res.textContent = "Zurückgenommen: das Original ist wieder da."; } catch (e) { res.innerHTML = `<span class="bad">${esc(e.message)}</span>`; }
        };
      } else res.textContent = "Erledigt.";
      res.insertAdjacentHTML("beforeend", `<p class="mut">Die Kennzahlen der Uhr ändern sich erst beim nächsten „Genauigkeit auswerten“.</p>`);
    } catch (e) {
      b.disabled = false;
      res.innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  }));
}

/* ---------- Hintergrundjobs: Fortschritt mit Balken ---------- */
/* Balken und Texte werden einmal angelegt und danach nur noch aktualisiert (kein Neuzeichnen: ruhig für Screenreader und ohne Flackern). */
function dvJobBar(host) {
  if (!host.querySelector(".dvbar")) host.innerHTML = `<div class="dvjobt"></div><div class="dvbar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-label="Fortschritt"><span></span></div><div class="dvjobs mut"></div>`;
  const t = host.querySelector(".dvjobt"), bar = host.querySelector(".dvbar"), fill = bar.firstElementChild, sub = host.querySelector(".dvjobs");
  return (text, done, total, note) => {
    if (total > 0) {
      bar.classList.remove("ind");
      bar.setAttribute("aria-valuemax", total);
      bar.setAttribute("aria-valuenow", done);
      bar.setAttribute("aria-valuetext", text);
      fill.style.width = Math.min(100, Math.round((100 * done) / total)) + "%";
    } else {
      bar.classList.add("ind");                               // Gesamtzahl noch unbekannt: laufender Streifen statt einer Zahl
      bar.removeAttribute("aria-valuenow");
      fill.style.width = "";
    }
    t.textContent = text;
    sub.textContent = note || "";
  };
}
const dvDoneText = (d, t) => `${d} von ${t} Touren geprüft`;
/* wartet, bis der Job fertig ist; on(j) bei jedem Stand von /api/jobs (neu: j.done / j.total). Rückgabe: letzter Stand oder null (Server nicht erreichbar) */
async function dvWatch(on) {
  for (let i = 0; i < 3000; i++) {
    await new Promise(r => setTimeout(r, i ? 1200 : 500));
    const j = await api("/api/jobs").catch(() => null);
    if (!j) return null;
    on(j);
    if (!j.running) return j;
  }
  return null;
}

/* Auswertung im Hintergrund starten und Fortschritt anzeigen */
async function dvQRun(root, btn, again) {
  const progs = [...root.querySelectorAll(".dvqprog")], btns = [...root.querySelectorAll(".dvqrun")];
  const say = t => progs.forEach(p => (p.textContent = t));
  let box = $("#dvqjob", root);
  if (!box) {
    box = document.createElement("div");
    box.id = "dvqjob"; box.className = "dvjob";
    box.setAttribute("role", "group"); box.setAttribute("aria-label", "Fortschritt der Auswertung");
    const anchor = root.querySelector(".dvintro");
    if (anchor) anchor.after(box); else root.prepend(box);
  }
  box.hidden = false;
  const upd = dvJobBar(box);
  btns.forEach(b => (b.disabled = true));
  say("Wird gestartet …");
  upd("Wird gestartet …", 0, 0);
  try {
    await api("/api/jobs/dev-quality", {method: "POST"});
    const j = await dvWatch(j => {
      const last = (j.log || []).filter(x => /Genauigkeit/.test(x)).slice(-1)[0] || "";
      const txt = j.progress || last.replace(/^\d\d:\d\d:\d\d /, "") || "Läuft …";
      if (j.running) {
        say(txt);
        upd(j.total > 0 ? dvDoneText(j.done || 0, j.total) : txt, j.done || 0, j.total || 0, j.total > 0 ? txt : "");
      }
    });
    if (j && j.ok === false) throw new Error("Die Auswertung ist fehlgeschlagen. Details stehen im Protokoll der Verwaltung.");
  } catch (e) {
    say(e.message);
    upd(e.message, 0, 0);
    btns.forEach(b => (b.disabled = false));
    return;
  }
  again();
}

/* ---------- Sammel-Korrektur der Höhen: Vorschau → Bestätigung → Hintergrundjob → „Alles rückgängig machen“ ---------- */
const dvSigned = v => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(Math.abs(v), 0) + " m";
async function dvBatch(g, again) {
  const m = dvBox(`<h2>Auffällige Höhen korrigieren</h2><p class="dvlead">${esc(g.name)}</p><div id="bxbody" aria-live="polite"><p class="mut"><span class="dvspin"></span>Liste wird geladen …</p></div>`);
  m.querySelector(".mbox").classList.add("dvbatchbox");
  const body = $("#bxbody", m);
  let changed = false;
  const close = () => { m.remove(); if (changed) again(); };
  const closeBtn = html => `<div class="dvfoot"><button class="btn ghost" id="bxclose" type="button">${html}</button></div>`;
  let pv;
  try {
    pv = await api(`/api/devices/${g.id}/quality/fix-preview`);
  } catch (e) {
    body.innerHTML = `<p class="bad">${esc(e.message)}</p>${closeBtn("Schließen")}`;
    $("#bxclose", m).onclick = close;
    return;
  }
  if (!pv.total) {
    body.innerHTML = `<p>Keine Tour mit offener Höhen-Auffälligkeit. Hier gibt es nichts zu korrigieren.</p>${closeBtn("Schließen")}`;
    $("#bxclose", m).onclick = close;
    return;
  }
  const one = pv.methods.length === 1;
  body.innerHTML = `<p class="dvbintro">Du siehst zuerst, was sich ändern würde. <b>Es passiert nichts, bevor du unten auf „Korrigieren“ klickst.</b> Jede Tour wird einzeln korrigiert, das Original bleibt erhalten, und den ganzen Lauf kannst du danach mit einem Klick zurücknehmen. Strecke und Zeit werden nicht verändert.</p>
    <fieldset class="dvf dvbmeth"><legend>Methode</legend>${pv.methods.map((x, i) => `<label class="dvpickrow"><input type="radio" name="bxm" value="${x.id}" ${i === 0 ? "checked" : ""}><span><b>${esc(x.label)}</b><small>${x.id === "dem" ? "Kartendaten werden bei Bedarf aus dem Internet geladen (begrenzt je Lauf)." : "Der Höhenverlauf der barometrischen Uhr wird aus der Zepp-Cloud übernommen."}</small></span></label>`).join("")}</fieldset>
    ${pv.zepp_missing ? `<p class="dvh">Die Methode „Uhr (Zepp)“ gibt es erst, wenn in der Verwaltung ein Zepp-Zugang eingerichtet ist.</p>` : ""}
    <div class="dvblist" role="group" aria-label="Touren">
      <div class="dvbtools"><span class="dvbcount" id="bxcount"></span><span class="sp"></span><button class="btn ghost sm" id="bxall" type="button">Alle</button><button class="btn ghost sm" id="bxnone" type="button">Keine</button></div>
      <ul class="dvbul">${pv.tours.map((t, i) => `<li><label class="dvbrow"><input type="checkbox" class="bxt" data-i="${i}" checked><span class="dvbname"><b>${esc(t.name)}</b><span class="mut">${esc(dvDay(t.day))}${t.rough ? " · Uhr: grob" : ""}</span></span>
        <span class="dvbnum"><span>Uhr <b>${nf(t.up_dev, 0)} m</b></span><span>Gelände <b>${nf(t.up_dem, 0)} m</b></span><span class="dvbnew">neu <b data-new>–</b></span></span></label></li>`).join("")}</ul></div>
    <p class="dvbsum" id="bxsum" role="status" aria-live="polite"></p>
    <div class="dvfoot"><button class="btn" id="bxgo" type="button">Korrigieren …</button><button class="btn ghost" id="bxno" type="button">Abbrechen</button></div>`;
  const boxes = [...m.querySelectorAll(".bxt")];
  const method = () => (m.querySelector("input[name=bxm]:checked") || {}).value || "dem";
  const sel = () => boxes.filter(b => b.checked).map(b => pv.tours[+b.dataset.i]);
  const refresh = () => {
    const mt = method(), s = sel();
    boxes.forEach(b => { const t = pv.tours[+b.dataset.i]; b.closest("li").querySelector("[data-new]").textContent = nf(t.new[mt] ?? 0, 0) + " m"; });
    const a = s.reduce((x, t) => x + (t.up_now || 0), 0), n = s.reduce((x, t) => x + (t.new[mt] || 0), 0);
    $("#bxcount", m).textContent = `${s.length} von ${pv.total} Touren ausgewählt`;
    $("#bxsum", m).innerHTML = s.length ? `<b>${s.length} ${s.length === 1 ? "Tour" : "Touren"}, ändert den Aufstieg um insgesamt ${esc(dvSigned(n - a))}</b><span class="dvh">Aufstieg aller gewählten Touren von ${nf(a, 0)} m auf etwa ${nf(n, 0)} m. Der genaue Wert wird beim Korrigieren neu berechnet.</span>${s.length > pv.cap ? `<span class="dvh">In einem Lauf werden höchstens ${pv.cap} Touren korrigiert; der Rest bleibt offen und lässt sich danach mit einem neuen Start erledigen.</span>` : ""}` : `<span class="mut">Keine Tour ausgewählt.</span>`;
    $("#bxgo", m).disabled = !s.length;
  };
  boxes.forEach(b => (b.onchange = refresh));
  m.querySelectorAll("input[name=bxm]").forEach(r => (r.onchange = refresh));
  $("#bxall", m).onclick = () => { boxes.forEach(b => (b.checked = true)); refresh(); };
  $("#bxnone", m).onclick = () => { boxes.forEach(b => (b.checked = false)); refresh(); };
  $("#bxno", m).onclick = close;
  refresh();
  $("#bxgo", m).onclick = async () => {
    const s = sel(), mt = method();
    if (!s.length) return;
    const lab = pv.methods.find(x => x.id === mt).label;
    const ok = await uiConfirm({title: `${s.length} ${s.length === 1 ? "Tour" : "Touren"} korrigieren?`, ok: "Korrigieren",
      text: `Methode: ${lab}.\n\n${$("#bxsum", m).firstElementChild.textContent}.\n\nDie Originale bleiben erhalten; den ganzen Lauf kannst du danach rückgängig machen.`});
    if (!ok) return;
    $("#bxgo", m).disabled = true;
    changed = true;
    body.innerHTML = `<div class="dvjob" id="bxjob" role="group" aria-label="Fortschritt der Korrektur"></div><div id="bxres" role="status" aria-live="polite"></div>`;
    const upd = dvJobBar($("#bxjob", m));
    upd("Wird gestartet …", 0, 0);
    let fin = null;
    try {
      const st = await api(`/api/devices/${g.id}/quality/fix`, METJ({method: mt, tours: s.map(t => t.id)}));
      upd(`0 von ${st.will_run} Touren korrigiert`, 0, st.will_run);
      fin = await dvWatch(j => { if (j.running) upd(j.total > 0 ? `${j.done || 0} von ${j.total} Touren korrigiert` : j.progress || "Läuft …", j.done || 0, j.total || 0, j.progress || ""); });
    } catch (e) {
      $("#bxres", m).innerHTML = `<p class="bad">${esc(e.message)}</p>${closeBtn("Schließen")}`;
      $("#bxjob", m).hidden = true;
      $("#bxclose", m).onclick = close;
      return;
    }
    MET_CACHE.clear();
    await loadTours().catch(() => {});
    let q = null;
    try { q = ((await api("/api/devices/quality")).devices || []).find(x => x.id === g.id); } catch (e) {}
    const b = q && q.batch, rest = q ? q.flagged_height : 0;
    const line = ((fin && fin.log) || []).filter(x => /Korrigiert: \d+ Touren/.test(x)).slice(-1)[0] || "";
    const nSkip = +((line.match(/(\d+) übersprungen/) || [])[1] || 0), nFail = +((line.match(/(\d+) nicht möglich/) || [])[1] || 0);
    $("#bxjob", m).hidden = true;
    $("#bxres", m).innerHTML = `<p class="dvbdone"><b>${b && b.n_done ? `${b.n_done} ${b.n_done === 1 ? "Tour" : "Touren"} korrigiert` : "Es wurde nichts korrigiert"}</b>${b && b.n_done ? `, Aufstieg zusammen ${esc(dvSigned(b.delta_up))}` : ""}.</p>
      ${nSkip || nFail ? `<p class="dvh">${nSkip ? `<span>${nSkip} übersprungen</span> ` : ""}${nFail ? `<span>${nFail} nicht möglich</span> ` : ""}<span>Einzelheiten stehen im Protokoll der Verwaltung.</span></p>` : ""}
      ${fin && fin.ok === false ? `<p class="bad">Der Lauf ist mit einem Fehler beendet worden. Schon Korrigiertes bleibt (einzeln wiederherstellbar); du kannst erneut starten.</p>` : ""}
      ${rest ? `<p class="dvopen"><b>${rest === 1 ? "Noch 1 Tour mit auffälliger Höhe offen – erneut starten." : `Noch ${rest} Touren mit auffälliger Höhe offen – erneut starten.`}</b></p>` : ""}
      <div class="dvfoot">${b && b.n_done ? `<button class="btn alt" id="bxundo" type="button" data-batch="${esc(b.id)}">Alles rückgängig machen</button>` : ""}<button class="btn ghost" id="bxclose" type="button">Schließen</button></div>`;
    $("#bxclose", m).onclick = close;
    const ub = $("#bxundo", m);
    if (ub) ub.onclick = () => dvUndo(g, ub.dataset.batch, async () => { MET_CACHE.clear(); await loadTours().catch(() => {}); close(); });
    $("#bxclose", m).focus();
  };
  $("#bxgo", m).focus();
}
/* Alles rückgängig machen – nur dieser Sammel-Lauf */
async function dvUndo(g, batch, after) {
  const ok = await uiConfirm({title: "Diesen Sammel-Lauf rückgängig machen?", ok: "Rückgängig machen", danger: true,
    text: "Alle Touren dieses Laufs bekommen ihre ursprünglichen Höhen und Höhenmeter zurück. Touren, die du inzwischen selbst geändert oder zurückgenommen hast, bleiben unberührt."});
  if (!ok) return;
  try {
    const r = await api(`/api/devices/${g.id}/quality/fix-undo`, METJ({batch}));
    MET_CACHE.clear();
    await uiAlert({title: "Rückgängig gemacht", text: `${r.restored} ${r.restored === 1 ? "Tour" : "Touren"} wiederhergestellt.` + (r.changed ? `\n\n${r.changed} unberührt gelassen (inzwischen anders geändert).` : "")});
  } catch (e) {
    await uiAlert({title: "Nicht möglich", text: e.message});
  }
  await after();
}

/* ---------- „Was liefert diese Uhr?“ (Gerät) und „Alle Felder dieser Tour“: zeigt, welche Felder die Quellen wirklich enthalten (nur lesen) ---------- */
const DVU_NF = x => (Number.isInteger(x) ? nf(x, 0) : nf(x, Math.abs(x) >= 100 ? 0 : Math.abs(x) >= 10 ? 1 : 2));
const DVU_STATE = {ok: "ok", kein_zugang: "none", fehler: "bad", kein_training: "none", nicht_zutreffend: "none", keine_datei: "none", keine_touren: "none"};
const DVU_STLAB = {kein_zugang: "kein Zepp-Zugang", fehler: "nicht erreichbar", kein_training: "kein Training zugeordnet", nicht_zutreffend: "nicht zutreffend", keine_datei: "nicht vorhanden", keine_touren: "keine Touren"};
function dvuRange(f) {
  if (f.hidden) return `<span class="mut" title="Koordinaten, Kennungen und Zeitstempel zeigt die Diagnose nie an">nicht angezeigt</span>`;
  if (f.min == null) return `<span class="mut">–</span>`;
  const u = f.unit && f.unit !== "roh" ? " " + esc(f.unit) : "";
  const r = f.min === f.max ? DVU_NF(f.min) + u : `${DVU_NF(f.min)} bis ${DVU_NF(f.max)}${u}`;
  return `<span>${r}</span>${f.median != null && f.min !== f.max ? `<small>Median ${DVU_NF(f.median)}</small>` : ""}${f.unit === "roh" ? `<small>Rohwert</small>` : ""}`;
}
function dvuRow(f, src, scope) {
  const pres = scope === "tour" ? (f.n > 0 ? `<span>vorhanden</span><small>${DVU_NF(f.n)} ${f.n === 1 ? "Wert" : "Werte"}${f.share != null && f.share < 1 ? `, ${nf(f.share * 100, 0)} % gefüllt` : ""}</small>` : `<span class="mut">leer</span>`)
    : `<span>${f.n_tours} von ${src.tours_checked}</span><small>${f.n_tours ? (f.share != null ? `${nf(f.share * 100, 0)} % gefüllt` : f.type) : "immer leer"}</small>`;
  const use = f.used ? `<span class="dvuy"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>ja</span>`
    : `<span class="dvun ${f.n_tours ? "has" : ""}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12h12"/></svg>nein</span>`;
  return `<tr class="${f.used ? "" : "unused"}${f.n_tours ? "" : " empty"}"><th scope="row"><code>${esc(f.name)}</code>${f.text ? `<small>${esc(f.text)}</small>` : ""}</th>
    <td data-l="${scope === "tour" ? "Vorhanden" : "In Touren"}">${pres}</td><td data-l="Bereich">${dvuRange(f)}</td><td data-l="Wird ausgewertet">${use}</td></tr>`;
}
function dvuBody(rep, only) {
  const scope = rep.scope, any = rep.sources.some(s => s.state === "ok");
  let h = "", one = false;
  if (!any) {
    const hints = [...new Set(rep.sources.map(s => s.hint).filter(Boolean))];
    one = hints.length === 1;                                  // gleiche Erklärung nicht je Quelle wiederholen
    h += `<div class="dvuempty"><b>Für ${scope === "tour" ? "diese Tour" : "dieses Gerät"} liegen noch keine Felder vor.</b><ul>${hints.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
  }
  rep.sources.forEach(s => {
    const fl = only ? s.fields.filter(f => !f.used && f.n_tours) : s.fields;
    const nUn = s.fields.filter(f => !f.used && f.n_tours).length;
    h += `<section class="dvusrc"><h3>${esc(s.label)}<span class="dvqs ${DVU_STATE[s.state] || "none"}">${s.state === "ok" ? (scope === "device" ? `${s.tours_checked} von ${rep.tours_checked} Touren` : `${s.fields.length} Felder`) : esc(DVU_STLAB[s.state] || s.state)}</span></h3>`;
    if (s.state !== "ok") h += one ? "" : `<p class="mut dvuh">${esc(s.hint || "")}</p>`;
    else {
      if (s.bad) h += `<p class="mut dvuh">Die FIT-Datei ist beschädigt; gezeigt wird, was gelesen werden konnte.</p>`;
      if (s.candidates > 1) h += `<p class="mut dvuh">Zu dieser Tour passen ${s.candidates} Zepp-Trainings; gezeigt wird das zeitlich nächste.</p>`;
      h += fl.length ? `<table class="dvut"><thead><tr><th scope="col">Feld</th><th scope="col">${scope === "tour" ? "Vorhanden" : "In Touren"}</th><th scope="col">Bereich</th><th scope="col">Wird ausgewertet</th></tr></thead>
        <tbody>${fl.map(f => dvuRow(f, s, scope)).join("")}</tbody></table>` : `<p class="mut dvuh">${only ? "Alles, was hier vorhanden ist, wird bereits ausgewertet." : "Keine Felder."}</p>`;
      if (!only && nUn) h += `<p class="mut dvuh">${nUn} ${nUn === 1 ? "Feld ist" : "Felder sind"} vorhanden, ${nUn === 1 ? "wird" : "werden"} aber noch nicht ausgewertet.</p>`;
    }
    h += `</section>`;
  });
  if (rep.fit_truncated) h += `<p class="mut dvuh">Die Suche nach FIT-Originaldateien wurde nach ${rep.fit_scanned} Dateien beendet (Obergrenze) – es kann weitere geben.</p>`;
  return h;
}
async function dvUhrFelder(scope, id, name) {
  const dev = scope === "device";
  const m = dvBox(`<h2>${dev ? "Was liefert diese Uhr?" : "Alle Felder dieser Tour"}</h2><p class="dvlead">${esc(name || "")}</p><label class="dvuchk"><input type="checkbox" id="dvuonly"> Nur Felder, die noch nicht ausgewertet werden</label><div id="dvubody" class="dvubody" aria-live="polite"><p class="mut">Wird gelesen … ${dev ? "Bei Zepp-Uhren kann das einige Sekunden dauern." : ""}</p></div>
    <div class="dvfoot"><span class="sp"></span>${dev ? `<a class="btn alt sm" id="dvudl" href="/api/devices/${id}/uhr-felder.json?download=1" download title="Enthält nur Feldnamen, Zähler und Wertebereiche – keine Koordinaten, Tournamen oder Zugangsdaten">Als Datei speichern</a>` : ""}<button class="btn ghost sm" id="dvuclose" type="button">Schließen</button></div>`);
  m.querySelector(".mbox").classList.add("dvubox");
  $("#dvuclose").onclick = () => m.remove();
  const body = $("#dvubody");
  try {
    const rep = await api(dev ? `/api/devices/${id}/uhr-felder` : `/api/tours/${encodeURIComponent(id)}/uhr-felder`);
    const draw = () => {
      const dl = $("#dvudl");
      if (dl) dl.hidden = !rep.tours_checked;
      body.innerHTML = (dev && !rep.tours_checked ? "" : dev ? `<p class="mut dvuh">Gelesen werden die ${rep.tours_checked} neuesten Touren dieses Geräts${rep.tours_total > rep.tours_checked ? ` (von ${rep.tours_total}; höchstens ${rep.limit})` : ` (alle ${rep.tours_total})`}. Es wird nichts gespeichert oder verändert.</p>` : `<p class="mut dvuh">Es wird nur gelesen – nichts gespeichert oder verändert. Koordinaten, Kennungen und Zeitstempel werden nie angezeigt.</p>`) + dvuBody(rep, $("#dvuonly").checked);
    };
    $("#dvuonly").onchange = draw;
    draw();
  } catch (e) {
    body.innerHTML = `<p class="bad">${esc(e.message)}</p><p class="mut">Die Diagnose konnte nicht gelesen werden. Prüfe die Verbindung und ob du angemeldet bist.</p>`;
  }
}

/* ---------- Abschnitt in der Verwaltung ---------- */
async function devPanel() {
  const root = $("#devsec");
  if (!root) return;
  const [dv, sug, mc, qa] = await Promise.all([api("/api/my-devices"), api("/api/devices/suggestions").catch(() => []), api("/api/devices/manual-check").catch(() => null), api("/api/devices/quality").catch(() => null)]);
  const qmap = {};
  ((qa && qa.devices) || []).forEach(x => (qmap[x.id] = x));
  const hidden = k => { try { return localStorage.getItem("mt_devsug_" + k) === "1"; } catch (e) { return false; } };
  const sugs = dv.devices.length ? sug.filter(s => !hidden(s.kind)) : [];
  const viewer = typeof isViewer === "function" && isViewer();
  const card = g => `<div class="dvcard ${g.active ? "" : "off"}" data-dv="${g.id}">${dvAvatar(g)}<div class="dvbody">
      <div class="dvn">${esc(g.name)}</div>
      <span class="dvsub">${esc(devKindLabel(dv, g.kind))}${g.model ? ` · ${esc(g.model)}` : ""}</span>
      ${!g.model && g.zsrc ? `<span class="dvsub">Zepp meldet: ${esc(g.zsrc)}</span>` : ""}
      <span class="dvper">${dvPeriod(g).map(x => `<span>${esc(x)}</span>`).join("")}</span>
      ${g.note ? `<span class="dvsub">${esc(g.note)}</span>` : ""}
      <div class="dvchips"><span class="dvc ${g.active ? "on" : ""}">${g.active ? "Aktiv" : "Deaktiviert"}</span><span class="dvc">${dvTours(g.n)}</span></div>
      ${dvGives(qmap[g.id])}
      <button class="dvuhr" type="button" data-uhr="${g.id}">Was liefert diese Uhr?</button></div>
      ${viewer ? "" : `<button class="dvmore" aria-haspopup="menu" aria-expanded="false" title="Aktionen" aria-label="Aktionen">${DV_SVG.dots}</button>`}
      ${qmap[g.id] ? `<details class="dvq" data-q="${g.id}" ${dvqOpen(g.id) ? "open" : ""}><summary aria-expanded="${dvqOpen(g.id)}"><span>Genauigkeit</span>${qmap[g.id].n_eval ? `<span class="dvqs ${DVQ_CLS[qmap[g.id].verdict.level] || "none"}">${esc(qmap[g.id].verdict.label)}</span>` : `<span class="dvqs none">noch nicht ausgewertet</span>`}</summary><div class="dvqb">${dvQBody(qa, qmap[g.id], viewer)}</div></details>` : ""}</div>`;
  const empty = `<div class="dvempty"><span class="dvav">${dvIcon("zepp")}</span><h3>Noch kein Gerät angelegt</h3>
      <p>Lege deine Uhren und Handys an, damit bei jeder Tour steht, womit sie aufgezeichnet wurde.</p>
      ${viewer ? "" : `<div class="row"><button class="btn" id="dvzepp">Gerät aus Zepp ermitteln</button><button class="btn alt" id="dvnew2">Gerät von Hand anlegen</button></div>`}</div>`;
  root.innerHTML = `<div class="dvhead"><h2>Meine Geräte</h2><span class="sp"></span>${viewer || !dv.devices.length ? "" : `${mc && mc.total ? `<button class="btn ghost sm" id="dvall" title="Alle ${mc.total} von Hand gesetzten Zuordnungen zurücknehmen; danach entscheidet die Automatik (Art, Zepp-Kennung, Datum)">Alle Handzuordnungen zurücksetzen</button>` : ""}<button class="btn alt sm" id="dvmatch" title="Alle Touren mit passendem Zepp-Training dem richtigen Gerät zuordnen">Touren automatisch zuordnen</button>${qa ? `<button class="btn alt sm dvqrun" id="dvqall" title="Vergleicht, was die Uhren gemessen haben, mit Strecke, Geländemodell und GPS-Spur. Verändert keine Tour.">Genauigkeit auswerten</button>` : ""}<button class="btn alt sm" id="dvzepp">Geräte aus Zepp ermitteln</button><button class="btn sm" id="dvnew">+ Gerät anlegen</button>`}</div>
    <p class="mut dvintro">Deine Aufnahmegeräte mit eigenem Namen. Der Name erscheint bei jeder Tour als „Quelle“; welche Messwerte eine Tour zeigt, richtet sich nach dem, was das Gerät wirklich geliefert hat.</p>
    ${qa && qa.progress && qa.progress.total && qa.computed_at ? `<div class="dvstat ${qa.progress.open ? "warn" : ""}" id="dvqstat" role="status"><div class="dvstatt"><b>${qa.progress.open ? dvOpenText(qa.progress.open) : "Alle Touren sind ausgewertet."}</b><span class="mut">Zuletzt ausgewertet am ${esc(dvQTime(qa.computed_at))}, ${qa.progress.done} von ${qa.progress.total} Touren.</span>${qa.progress.n_summary ? `<span class="mut">${qa.progress.n_detail} mit Detail (genau), ${qa.progress.n_summary} nur Zusammenfassung (grob).</span>` : ""}${dvBar(qa.progress.done, qa.progress.total, "Fortschritt der Auswertung")}</div>${viewer || !qa.progress.open ? "" : `<button class="btn sm dvqrun" type="button">Weiter auswerten</button>`}</div>` : ""}
    ${mc && mc.redundant && !viewer ? `<div class="dvhint" id="dvred"><span><b>${mc.redundant} ${mc.redundant === 1 ? "Tour steht" : "Touren stehen"} als „von Hand zugeordnet“, entspr${mc.redundant === 1 ? "icht" : "echen"} aber der automatischen Zuordnung</b><span class="mut">Die Zuordnung ändert sich dabei nicht – nur der Zusatz „von Hand“ entfällt, und künftige Änderungen (z. B. neues Gerät, geänderter Zeitraum) wirken wieder automatisch.</span></span>
      <button class="btn sm" id="dvredok">Auf automatisch umstellen</button></div>` : ""}
    ${mc && mc.outside && !viewer ? `<div class="dvhint" id="dvmc"><span><b>${mc.outside} von Hand gesetzte ${mc.outside === 1 ? "Zuordnung widerspricht" : "Zuordnungen widersprechen"} dem Zeitraum ihres Geräts</b><span class="mut">${Object.entries(mc.by_device).map(([n, k]) => `${esc(n)}: ${k}`).join(" · ")} – die Touren liegen vor „seit“ bzw. nach „bis“ des Geräts. Zurücksetzen übergibt sie wieder der automatischen Zuordnung (Zepp-Kennung und Datum); andere von Hand gesetzte Zuordnungen bleiben.</span></span>
      <button class="btn sm" id="dvmcok">Zurücksetzen</button></div>` : ""}
    ${sugs.map(s => `<div class="dvhint" data-sug="${esc(s.kind)}"><span><b>${esc(s.label)}: ${s.n} ${s.n === 1 ? "Tour" : "Touren"} ohne Gerät</b><span class="mut">Möchtest du dafür ein Gerät anlegen? Es wird nichts ohne deine Bestätigung angelegt.</span></span>
      <button class="btn sm" data-sy="${esc(s.kind)}" data-nm="${esc(s.name)}">Gerät anlegen …</button><button class="btn ghost sm" data-sn="${esc(s.kind)}">Nicht jetzt</button></div>`).join("")}
    ${dv.devices.length ? `<div class="dvlist">${dv.devices.map(card).join("")}</div>` : empty}`;
  const again = () => devPanel().catch(() => {});
  const bz = $("#dvzepp"), bn = $("#dvnew") || $("#dvnew2");
  if (bz) bz.onclick = () => devZepp(dv, again);
  const ab = $("#dvall");
  if (ab) ab.onclick = async () => {
    if (!(await uiConfirm({title: "Alle Handzuordnungen zurücksetzen?", ok: "Zurücksetzen", danger: true, text: `Alle ${mc.total} von Hand gesetzten Zuordnungen zurücksetzen? Danach entscheidet die automatische Zuordnung (Art, Zepp-Kennung, Datum). Bewusst gesetzte Geräte gehen dabei verloren.`}))) return;
    ab.disabled = true;
    try {
      const r = await api("/api/devices/reset-manual", METJ({mode: "all"}));
      MET_CACHE.clear();
      if ((await uiConfirm({title: "Jetzt automatisch zuordnen?", ok: "Zuordnen", cancel: "Später", text: `${r.reset} Zuordnungen zurückgesetzt. Jetzt alle Touren automatisch den Uhren zuordnen?`})) && $("#dvmatch")) { $("#dvmatch").click(); return; }
      await loadTours().catch(() => {});
    } catch (e) { await uiAlert({title: "Nicht möglich", text: e.message}); }
    again();
  };
  const rb = $("#dvredok");
  if (rb) rb.onclick = async () => {
    rb.disabled = true;
    try { const r = await api("/api/devices/reset-manual", METJ({mode: "redundant"})); MET_CACHE.clear(); await loadTours().catch(() => {}); uiAlert({title: "Umgestellt", text: `${r.reset} Touren auf automatische Zuordnung umgestellt.`}); } catch (e) { await uiAlert({title: "Nicht möglich", text: e.message}); }
    again();
  };
  const mcb = $("#dvmcok");
  if (mcb) mcb.onclick = async () => {
    mcb.disabled = true;
    try {
      const r = await api("/api/devices/reset-manual", METJ({mode: "outside"}));
      MET_CACHE.clear();
      if ((await uiConfirm({title: "Jetzt automatisch zuordnen?", ok: "Zuordnen", cancel: "Später", text: `${r.reset} Zuordnungen zurückgesetzt. Jetzt alle Touren automatisch den Uhren zuordnen?`})) && $("#dvmatch")) { $("#dvmatch").click(); return; }
      await loadTours().catch(() => {});
    } catch (e) { await uiAlert({title: "Nicht möglich", text: e.message}); }
    again();
  };
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
    } catch (e) { uiAlert({title: "Nicht möglich", text: e.message}); }
    await loadTours().catch(() => {});
    again();
  };
  if (bn) bn.onclick = () => devForm(dv, null, again);
  root.querySelectorAll("[data-dv]").forEach(r => {
    const g = dv.devices.find(x => x.id === +r.dataset.dv);
    const ub = r.querySelector(".dvuhr");
    if (ub) ub.onclick = e => { e.stopPropagation(); dvUhrFelder("device", g.id, g.name); };
    if (viewer) return;
    r.onclick = e => { if (!e.target.closest(".dvmore, .dvq, .dvuhr")) devForm(dv, g, again); };
    const mb = r.querySelector(".dvmore");
    mb.onclick = e => {
      e.stopPropagation();
      dvMenu(mb, [
        {icon: DV_SVG.edit, label: "Bearbeiten", run: () => devForm(dv, g, again)},
        {icon: DV_SVG.photo, label: g.photo ? "Foto ändern oder entfernen" : "Foto hinzufügen", run: () => devForm(dv, g, again)},
        {icon: DV_SVG.info, label: "Was liefert diese Uhr?", run: () => dvUhrFelder("device", g.id, g.name)},
        {icon: DV_SVG.range, label: "Touren zuordnen …", run: () => devRange(dv, g, again)},
        {icon: g.active ? DV_SVG.off : DV_SVG.on, label: g.active ? "Deaktivieren" : "Aktivieren", run: async () => {
          try { await api("/api/devices/" + g.id, dvJson("PATCH", {active: !g.active})); MET_CACHE.clear(); } catch (er) { await uiAlert({title: "Nicht möglich", text: er.message}); }
          again();
        }},
        "-",
        {icon: DV_SVG.del, label: "Löschen …", bad: true, run: () => devDelete(dv, g, again)},
      ]);
    };
  });
  root.querySelectorAll("details.dvq").forEach(dt => {
    const id = +dt.dataset.q, g = qmap[id];
    const load = () => { if (!dt.dataset.loaded) { dt.dataset.loaded = "1"; dvQBad(dt, g, viewer, again); } };
    dt.addEventListener("toggle", () => {
      dt.querySelector("summary").setAttribute("aria-expanded", dt.open ? "true" : "false");
      if (dt.open) { DVQ_OPEN.add(id); load(); } else DVQ_OPEN.delete(id);
      try { localStorage.setItem("mt_dvq_" + id, dt.open ? "1" : "0"); } catch (e) {}
    });
    dvSecWire(dt);
    const bb = dt.querySelector(".dvbatch");
    if (bb) bb.onclick = e => { e.stopPropagation(); dvBatch(g, again); };
    dt.querySelectorAll(".dvundo").forEach(ub => (ub.onclick = e => { e.stopPropagation(); dvUndo(g, ub.dataset.batch, async () => { MET_CACHE.clear(); await loadTours().catch(() => {}); again(); }); }));
    if (dt.open) load();
  });
  root.querySelectorAll(".dvqrun").forEach(b => (b.onclick = e => { e.stopPropagation(); dvQRun(root, b, again); }));
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
