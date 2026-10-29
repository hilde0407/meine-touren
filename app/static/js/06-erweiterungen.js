/* =====================  Erweiterungen  ===================== */
NAV.splice(3, 0, ["records", "Rekorde"]);
$("#nav").innerHTML = NAV.map(([k, l]) => `<a href="#/${k}" data-k="${k}">${l}</a>`).join("");
{
  const gs = document.createElement("input");
  gs.id = "gs";
  gs.type = "search";
  gs.placeholder = "Suchen …  ( / )";
  gs.setAttribute("aria-label", "Touren suchen");
  $(".top").insertBefore(gs, $("#busy"));
  let tmr;
  gs.oninput = () => {
    clearTimeout(tmr);
    tmr = setTimeout(() => {
      const v = gs.value.trim();
      location.hash = v ? `#/search?q=${encodeURIComponent(v)}` : "#/tours";
    }, 250);
  };
  addEventListener("keydown", e => {
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      e.preventDefault();
      gs.focus();
      gs.select();
    }
  });
}

/* ---- Suche ---- */
VIEWS.search = async (_, q) => {
  const term = (q.get("q") || "").toLowerCase().trim(),
    toks = term.split(/\s+/).filter(Boolean);
  const hay = t =>
    `${t.name} ${t.note || ""} ${sName(t.sport)} ${dateS(t.date)} ${MONL[t.m - 1]} ${t.y} ${t.g_place || ""} ${t.g_county || ""} ${t.g_state || ""} ${t.g_country || ""} ${(t.tags || "").replace(/\|/g, " ")}`.toLowerCase();
  const a = toks.length
    ? TOURS.filter(t => {
        const h = hay(t);
        return toks.every(k => h.includes(k));
      })
    : [];
  if (document.activeElement !== $("#gs") && $("#gs")) $("#gs").value = q.get("q") || "";
  $("#main").innerHTML =
    `<div class="sec" style="margin-top:0"><h2>Suche: „${esc(q.get("q") || "")}“</h2><span class="sub">${a.length} Touren, ${nf(
      a.reduce((c, t) => c + t.km, 0),
      0
    )} km</span></div>
   <div class="tl">${a.slice(0, 200).map(tourRow).join("") || `<div class="empty">Keine Treffer. Gesucht wird in Name, Notiz, Sportart, Datum, Monat und Region (Land, Bundesland, Landkreis, Ort).</div>`}</div>`;
};

/* ---- Ziele (Übersicht) ---- */
const GM = {km: ["km", "Kilometer"], up: ["m", "Höhenmeter"], count: ["", "Touren"], hours: ["h", "Stunden"]};
const goalVal = (g, T) =>
  T.filter(t => t.y === g.year && (!g.sport || t.sport === g.sport)).reduce(
    (c, t) => c + (g.metric === "km" ? t.km : g.metric === "up" ? t.up_m || 0 : g.metric === "hours" ? t.h : 1),
    0
  );
const _dash = VIEWS.dash;
VIEWS.dash = async (n, q) => {
  await _dash(n, q);
  const fg = $(".figs");
  if (!fg) return;
  const ys = years(),
    Y = +(q.get("y") || 0) || 0,
    cy = new Date().getFullYear(),
    yr = Y || cy;
  const goals = (await api("/api/goals").catch(() => [])).filter(g => g.year === yr),
    sp = [...new Set(TOURS.map(t => t.sport))];
  const now = new Date(),
    frac = yr === cy ? Math.max(0, (now - new Date(cy, 0, 1)) / (new Date(cy + 1, 0, 1) - new Date(cy, 0, 1))) : 1;
  const row = g => {
    const v = goalVal(g, TOURS),
      p = Math.min(100, (v / g.target) * 100),
      u = GM[g.metric][0],
      proj = frac > 0.02 && frac < 1 ? v / frac : null;
    return `<div class="goal"><div class="gh"><b>${GM[g.metric][1]}${g.sport ? " " + sName(g.sport) : ""}</b><span>${nf(v, g.metric === "count" ? 0 : 0)} / ${nf(g.target, 0)} ${u} <button class="gx" data-g="${g.id}" title="Ziel löschen">×</button></span></div>
     <div class="gb"><i style="width:${p}%"></i>${frac < 1 ? `<u style="left:${frac * 100}%" title="Soll heute"></u>` : ""}</div>
     <div class="gs">${nf(p, 0)} %${proj != null ? ` · Prognose zum Jahresende: ${nf(proj, 0)} ${u} (${nf((proj / g.target) * 100, 0)} %)` : ""}${frac < 1 && v < g.target * frac ? ` · <span class="bad">${nf(g.target * frac - v, 0)} ${u} hinter dem Plan</span>` : frac < 1 && v >= g.target * frac ? ` · <span class="ok">im Plan</span>` : ""}</div></div>`;
  };
  const box = document.createElement("div");
  box.className = "panel";
  box.id = "goals";
  box.style.marginTop = "34px";
  box.innerHTML = `<h2>Ziele ${yr}</h2>${goals.map(row).join("") || `<p class="mut">Noch kein Ziel für ${yr}. Setze dir eines, zum Beispiel 1000 km Wandern.</p>`}
   <details><summary>Ziel hinzufügen</summary><div class="row" style="margin-top:8px"><select id="gm">${Object.entries(GM)
     .map(([k, v]) => `<option value="${k}">${v[1]}</option>`)
     .join("")}</select>
   <select id="gsp"><option value="">alle Sportarten</option>${sp.map(s => `<option value="${s}">${sName(s)}</option>`).join("")}</select><input id="gt" type="number" min="1" placeholder="Zielwert" style="width:130px"><button class="btn sm" id="gadd">Speichern</button></div></details>`;
  fg.after(box);
  box.onclick = async e => {
    const g = e.target.dataset.g;
    if (g && confirm("Ziel löschen?")) {
      await api(`/api/goals/${g}`, {method: "DELETE"});
      route();
    }
  };
  $("#gadd").onclick = async () => {
    const t = +$("#gt").value;
    if (!t) return;
    await api("/api/goals", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({year: yr, metric: $("#gm").value, sport: $("#gsp").value, target: t}),
    });
    route();
  };
  const yrs = $(".years");
  if (yrs)
    yrs.insertAdjacentHTML(
      "beforeend",
      `<a class="btn ghost sm" style="margin-left:auto;align-self:center" href="#/recap/${Y || ys[0]}">Jahresrückblick ${Y || ys[0]}</a>`
    );
};

/* ---- Rekorde ---- */
VIEWS.records = async (_, q) => {
  if (!TOURS.length) {
    $("#main").innerHTML = `<div class="empty"><h2>Noch keine Touren</h2></div>`;
    return;
  }
  let fs = (q && q.get("s")) || "";
  try {
    if (!q || !q.has("s")) fs = sessionStorage.getItem("rec_s") || "";
    sessionStorage.setItem("rec_s", fs);
  } catch (e) {}
  const allSp = [...new Set(TOURS.map(t => t.sport))].sort(
    (a, b) => TOURS.filter(t => t.sport === b).length - TOURS.filter(t => t.sport === a).length
  );
  if (fs && !allSp.includes(fs)) fs = "";
  const T = fs ? TOURS.filter(t => t.sport === fs) : TOURS;
  const chips = `<div class="row" style="gap:6px;margin:-4px 0 18px;flex-wrap:wrap"><a class="chip${fs ? "" : " on"}" href="#/records?s=">Alle Aktivitäten</a>${allSp.map(x => `<a class="chip${fs === x ? " on" : ""}" href="#/records?s=${x}"><i class="sw" style="background:${sCol(x)}"></i>${sName(x)}</a>`).join("")}</div>`;
  const sum = (a, f) => a.reduce((c, t) => c + f(t), 0),
    km = sum(T, t => t.km),
    up = sum(T, t => t.up_m || 0),
    h = sum(T, t => t.h);
  const best = (a, f) => a.reduce((b, t) => (b == null || f(t) > f(b) ? t : b), null);
  const sports = [...new Set(T.map(t => t.sport))].sort(
    (a, b) => T.filter(t => t.sport === b).length - T.filter(t => t.sport === a).length
  );
  const lnk = (t, v) =>
    t
      ? `<div class="r"><span>${v[0]}<small><a href="#/tour/${t.id}">${esc(t.name)}</a>, ${dateS(t.date)}</small></span><b>${v[1]}</b></div>`
      : "";
  const wkIdx = t => Math.floor((Date.UTC(t.y, t.m - 1, +t.date.slice(8, 10)) / 864e5 + 3) / 7),
    wks = [...new Set(T.map(wkIdx))].sort((a, b) => a - b);
  let longest = 0,
    run = 0,
    prevW = null;
  wks.forEach(w => {
    run = prevW !== null && w === prevW + 1 ? run + 1 : 1;
    longest = Math.max(longest, run);
    prevW = w;
  });
  const curW = Math.floor((Date.now() / 864e5 + 3) / 7);
  let cur = 0;
  {
    let w = wks.includes(curW) ? curW : wks.includes(curW - 1) ? curW - 1 : null;
    while (w !== null && wks.includes(w)) {
      cur++;
      w--;
    }
  }
  const dayN = new Set(T.map(t => t.date.slice(0, 10))).size,
    wd = Array(7).fill(0);
  T.forEach(t => wd[(new Date(t.date.slice(0, 10) + "T12:00:00").getDay() + 6) % 7]++);
  const alts = (await api(`/api/records/altitude?limit=${fs ? 60 : 8}`).catch(() => []))
    .filter(a => !fs || (BY[a.id] && BY[a.id].sport === fs))
    .slice(0, 8);
  $("#main").innerHTML =
    `<div class="sec" style="margin-top:0"><h2>Rekorde</h2><span class="sub">${nf(T.length, 0)} Touren seit ${T[T.length - 1].y}${fs ? " · " + sName(fs) : ""}</span></div>${chips}
   <div class="figs"><div class="fig"><div class="v">${nf(km / 40075, 2)}<span class="u">×</span></div><div class="l">um die Erde (${nf(km, 0)} km)</div></div>
    <div class="fig"><div class="v">${nf(up / 8849, 1)}<span class="u">×</span></div><div class="l">Mount Everest bergauf (${nf(up, 0)} m)</div></div>
    <div class="fig"><div class="v">${nf(h / 24, 1)}<span class="u">Tage</span></div><div class="l">unterwegs (${nf(h, 0)} Std.)</div></div>
    <div class="fig"><div class="v">${nf(dayN, 0)}</div><div class="l">Tage mit Touren</div></div>
    <div class="fig"><div class="v">${longest}<span class="u">Wochen</span></div><div class="l">längste Serie · aktuell ${cur}</div></div></div>
   <div class="grid g2" style="margin-top:36px">
    <div class="panel"><h2>Bestwerte gesamt</h2><div class="rows">${lnk(
      best(T, t => t.km),
      ["Längste Strecke", nf(best(T, t => t.km).km, 1) + " km"]
    )}${lnk(
      best(T, t => t.up_m || 0),
      ["Meiste Höhenmeter", nf(best(T, t => t.up_m || 0).up_m, 0) + " m"]
    )}${lnk(
      best(T, t => t.h),
      ["Längste Dauer", nf(best(T, t => t.h).h, 1) + " h"]
    )}</div></div>
    <div class="panel"><h2>Höchste Punkte</h2><div class="rows">${alts.length ? alts.map(a => (BY[a.id] ? `<div class="r"><span><a href="#/tour/${a.id}">${esc(BY[a.id].name)}</a><small>${dateS(BY[a.id].date)}</small></span><b>${nf(a.alt, 0)} m</b></div>` : "")).join("") : `<div class="mut">Sobald die Strecken geladen sind („Routen laden“ in der Verwaltung), erscheinen hier die höchsten Punkte.</div>`}</div></div>
    <div class="panel"><h2>Nach Wochentag</h2>${barChart(wd, ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"])}</div>
    <div class="panel"><h2>Je Sportart</h2><div class="rows">${sports
      .map(s => {
        const a = T.filter(t => t.sport === s),
          l = best(a, t => t.km),
          u = best(a, t => t.up_m || 0),
          f = best(
            a.filter(t => t.km >= 3 && t.h > 0),
            t => t.km / t.h
          );
        return `<div class="r" style="display:block"><div><i class="sw" style="background:${sCol(s)}"></i><b style="font:600 20px var(--d)">${sName(s)}</b> <span class="mut">· ${a.length} Touren, ${nf(
          sum(a, t => t.km),
          0
        )} km, ${nf(
          sum(a, t => t.up_m || 0),
          0
        )} m</span></div>
       <small>Längste: <a href="#/tour/${l.id}">${nf(l.km, 1)} km</a> · Meiste Höhenmeter: <a href="#/tour/${u.id}">${nf(u.up_m, 0)} m</a>${f ? ` · Schnellste: <a href="#/tour/${f.id}">${nf(f.km / f.h, 1)} km/h</a>` : ""}</small></div>`;
      })
      .join("")}</div></div></div>`;
};

/* ---- Jahresrückblick ---- */
VIEWS.recap = async name => {
  const Y = +name || years()[0],
    sel = TOURS.filter(t => t.y === Y),
    prev = TOURS.filter(t => t.y === Y - 1);
  if (!sel.length) {
    $("#main").innerHTML = `<div class="empty"><h2>Keine Touren in ${Y}</h2></div>`;
    return;
  }
  const sum = (a, f) => a.reduce((c, t) => c + f(t), 0),
    km = sum(sel, t => t.km),
    up = sum(sel, t => t.up_m || 0),
    h = sum(sel, t => t.h);
  const mm = Array(12).fill(0),
    pm = Array(12).fill(0);
  sel.forEach(t => (mm[t.m - 1] += t.km));
  prev.forEach(t => (pm[t.m - 1] += t.km));
  const bySport = {};
  sel.forEach(t => (bySport[t.sport] = (bySport[t.sport] || 0) + t.km));
  const sp = Object.entries(bySport).sort((a, b) => b[1] - a[1]);
  const top = sel
      .slice()
      .sort((a, b) => b.km - a.km)
      .slice(0, 5),
    steep = sel.slice().sort((a, b) => (b.up_m || 0) - (a.up_m || 0))[0],
    bm = mm.indexOf(Math.max(...mm));
  const days = new Set(sel.map(t => t.date.slice(0, 10))).size,
    ph = await api(`/api/photos?year=${Y}&random=true&limit=12`).catch(() => []);
  const dl = (a, b) => (b ? `${a >= b ? "+" : "−"}${nf((Math.abs(a - b) / b) * 100, 0)} % gegenüber ${Y - 1}` : "");
  $("#main").innerHTML =
    `<div class="recap"><div class="noprint row" style="margin-bottom:10px"><a class="back" href="#/dash?y=${Y}">‹ Übersicht</a><span class="sp"></span><button class="btn ghost sm" onclick="print()">Drucken / als PDF speichern</button></div>
   <div class="rhero"><div class="k">Mein Tourenjahr</div><h1>${Y}</h1><div class="rs"><span><b>${nf(sel.length, 0)}</b> Touren</span><span><b>${nf(km, 0)}</b> km</span><span><b>${nf(up, 0)}</b> Höhenmeter</span><span><b>${nf(h, 0)}</b> Stunden</span><span><b>${days}</b> Tage unterwegs</span></div>
   <div class="rd">${[
     dl(
       km,
       sum(prev, t => t.km)
     ),
   ]
     .filter(Boolean)
     .join("")}</div></div>
   <div class="grid g2" style="margin-top:34px"><div class="panel"><h2>Kilometer pro Monat</h2>${barChart(mm, MON, {ghost: pm, ghostLabel: Y - 1})}<div class="mut" style="font-size:14px">Stärkster Monat: ${MONL[bm]} mit ${nf(mm[bm], 0)} km</div></div>
    <div class="panel"><h2>Sportarten</h2><div class="stack">${sp.map(([s, v]) => `<div style="width:${(v / km) * 100}%;background:${sCol(s)}"></div>`).join("")}</div><div class="rows" style="margin-top:10px">${sp.map(([s, v]) => `<div class="r"><span><i class="sw" style="background:${sCol(s)}"></i>${sName(s)}</span><span class="mut">${nf(v, 0)} km, ${nf((v / km) * 100, 0)} %</span></div>`).join("")}</div></div></div>
   <div class="panel" style="margin-top:34px"><h2>Die fünf längsten Touren</h2><div class="tl">${top.map(tourRow).join("")}</div><div class="mut" style="margin-top:10px">Meiste Höhenmeter: <a href="#/tour/${steep.id}">${esc(steep.name)}</a> (${nf(steep.up_m, 0)} m)</div></div>
   ${ph.length ? `<div class="panel" style="margin-top:34px"><div class="row"><h2>Fotos des Jahres</h2><span class="sp"></span><a class="btn sm noprint" target="_blank" href="slideshow.html?year=${Y}">Diashow</a></div><div class="thumbs" id="rph">${ph.map((p, i) => `<div class="th"><img loading="lazy" src="/pic/${p.id}?size=400" data-i="${i}"></div>`).join("")}</div></div>` : ""}</div>`;
  if (ph.length) bindThumbs($("#rph"), ph);
};

/* ---- Tourdetail: Notiz, GPX, Teilen ---- */
const _tourV = VIEWS.tour;
VIEWS.tour = async id => {
  await _tourV(id);
  const t = BY[id],
    r = $("#ksync") && $("#ksync").closest(".row");
  if (!t || !r) return;
  r.insertAdjacentHTML(
    "beforeend",
    `<a class="btn ghost sm" href="/api/tours/${encodeURIComponent(id)}/gpx" download title="Strecke als GPX-Datei">⬇ GPX</a><a class="btn ghost sm" href="#/flight/${encodeURIComponent(id)}" title="Die Strecke im 3D-Gelände abfliegen">🛰 3D-Flug</a>${t.photos ? `<button class="btn ghost sm" id="shr" title="Link zur Foto-Diashow dieser Tour kopieren">🔗 Diashow-Link</button>` : ""}`
  );
  if ($("#shr"))
    $("#shr").onclick = async () => {
      const u = new URL(`slideshow.html?tour=${id}`, location.href).href;
      try {
        await navigator.clipboard.writeText(u);
        $("#shr").textContent = "✓ Link kopiert";
      } catch (e) {
        prompt("Link zur Diashow:", u);
      }
    };
  r.insertAdjacentHTML(
    "afterend",
    `<div class="field" style="max-width:760px;margin:0 0 18px"><label for="note">Notiz zur Tour (Wetter, Begleitung, Einkehr …)</label><textarea id="note" rows="2" placeholder="Hier eine Notiz eintragen …">${esc(t.note || "")}</textarea><span id="notes" class="mut" style="font-size:13px"></span></div>`
  );
  $("#note").onchange = async () => {
    try {
      await api(`/api/tours/${encodeURIComponent(id)}/note`, {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({note: $("#note").value}),
      });
      t.note = $("#note").value.trim();
      $("#notes").textContent = "gespeichert ✓";
    } catch (e) {
      $("#notes").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  };
};

/* ---- Verwaltung: Sicherung und Schutz ---- */
/* ---- Updates: Prüfung auf GitHub, Installation aus der Oberfläche ---- */
const isAdmin = () => !ME.users_enabled || (ME.user && ME.user.role === "admin");
async function installUpdate(u, say) {
  if (
    !confirm(
      `Version ${u.latest} jetzt installieren?\n\nVorher wird eine Sicherung aller Daten angelegt. Die Seite ist während der Installation kurz nicht erreichbar.`
    )
  )
    return;
  const before = u.current;
  say("Sicherung wird angelegt …");
  try {
    await api("/api/update/install", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({version: u.latest}),
    });
  } catch (e) {
    return say(`<span class="bad">${esc(e.message)}</span>`);
  }
  say("Version wird installiert … (dauert etwa ein bis zwei Minuten)");
  const t0 = Date.now();
  const tick = async () => {
    let v = null,
      s = null;
    try {
      v = (await (await fetch("/api/version", {cache: "no-store"})).json()).version;
      s = (await api("/api/update/status")).status;
    } catch (e) {}
    if (v && v.split(" ")[0] !== before) {
      say(`<span class="ok">Version ${esc(v.split(" ")[0])} ist installiert ✓ – Seite wird neu geladen …</span>`);
      return setTimeout(() => location.reload(), 1500);
    }
    if (s && s.state === "error") return say(`<span class="bad">Update fehlgeschlagen: ${esc(s.message || "unbekannter Fehler")}</span>`);
    if (Date.now() - t0 > 6 * 60000)
      return say(
        `<span class="bad">Das dauert ungewöhnlich lange. Bitte im Container <code>journalctl -u ${esc(u.command.split("-update")[0])}-update</code> ansehen.</span>`
      );
    setTimeout(tick, 3000);
  };
  setTimeout(tick, 4000);
}
async function updatePanel() {
  const b = $("#upd");
  if (!b) return;
  let u;
  try {
    u = await api("/api/update-check");
  } catch (e) {
    return;
  }
  const admin = isAdmin();
  const notes = (u.notes || "").trim();
  b.innerHTML = `<div class="panel" style="margin-bottom:16px${u.newer ? ";border-color:var(--yellow)" : ""}"><h2>Updates</h2>
   <p>Installiert: <b>${esc(u.current)}</b>${u.latest ? ` · neueste Version auf GitHub: <b>${esc(u.latest)}</b>${u.published ? ` (${esc(u.published)})` : ""}` : ` · <span class="mut">GitHub war nicht erreichbar</span>`}
   ${u.newer ? `<span class="bad"> – es gibt eine neuere Version</span>` : u.ok ? `<span class="ok"> ✓ aktuell</span>` : ""}</p>
   ${notes && u.newer ? `<details><summary>Was ist neu?</summary><pre class="pre" style="white-space:pre-wrap;max-height:240px;overflow:auto">${esc(notes)}</pre></details>` : ""}
   <div class="row"><button class="btn alt" id="ucheck">Jetzt prüfen</button>
   ${u.newer && admin && u.can_install ? `<button class="btn" id="uinst">Version ${esc(u.latest)} installieren</button>` : ""}
   ${u.newer ? `<a class="btn alt" target="_blank" rel="noopener" href="${esc(u.url)}">Auf GitHub ansehen</a>` : ""}<span id="umsg"></span></div>
   ${
     u.newer && !u.can_install
       ? `<p class="mut" style="font-size:13px">Die Installation aus der Oberfläche ist hier noch nicht eingerichtet. Im Container <b>einmal</b> ausführen: <code>${esc(u.command)}</code> – danach klappt es per Knopfdruck.</p>`
       : ""
   }
   <div class="field" style="margin-top:8px"><label>Regelmäßig (alle 6 Stunden) auf neue Versionen prüfen</label><select data-k="update_check"><option value="1">ja</option><option value="0">nein</option></select></div>
   ${u.status && u.status.state === "error" ? `<p class="bad" style="font-size:13px">Letztes Update fehlgeschlagen: ${esc(u.status.message || "")}</p>` : ""}</div>`;
  const sel = b.querySelector('[data-k="update_check"]');
  if (sel) sel.value = u.enabled ? "1" : "0";
  const uc = b.querySelector("#ucheck");
  if (!uc || !b.isConnected) return;       // Seite wurde inzwischen gewechselt
  uc.onclick = async () => {
    b.querySelector("#umsg").textContent = "…";
    await api("/api/update-check?force=1").catch(() => {});
    updatePanel();
  };
  const ui = b.querySelector("#uinst");
  if (ui) ui.onclick = () => installUpdate(u, h => (b.querySelector("#umsg").innerHTML = h));
}

const _adm = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm(...a);
  const st = await api("/api/status").catch(() => ({})),
    sv = $("#save");
  if (!sv) return;
  if ($("#ver")) $("#ver").textContent = "Version: " + (st.version || "alt");
  api("/api/zustand")
    .then(h => {
      const b = $("#hlt");
      if (!b) return;
      b.innerHTML =
        `<h2>Zustand <span class="mut" style="font:400 16px var(--b)">${h.ok ? "– alles in Ordnung" : "– bitte prüfen"}</span></h2><div class="rows">${h.checks.map(c => `<div class="r"><span>${c.ok ? "✓" : "⚠"} ${esc(c.name)}</span><span class="${c.ok ? "mut" : "bad"}">${esc(c.detail)}${c.hint ? ` – ${esc(c.hint)}` : ""}</span></div>`).join("")}</div>` +
        (h.duplicates.length
          ? `<p class="mut" style="margin-top:8px">Doppelte Namen: ${h.duplicates.map(d => esc(d.name) + " (" + d.tours.map(t => `<a href="#/tour/${t.id}">${t.date}</a>`).join(", ") + ")").join(" · ")}</p>`
          : "");
    })
    .catch(() => {
      const b = $("#hlt");
      if (b) b.remove();
    });
  updatePanel();
  sv.closest(".row").insertAdjacentHTML(
    "beforebegin",
    `<div class="grid g2" style="margin-top:40px"><div class="panel"><h2>Sicherung</h2>
   <p class="mut">Täglich um 03:40 Uhr wird die Datenbank (Touren, Notizen, Ziele, Zuordnungen) automatisch nach <code>${esc(st.backup_dir || "/var/backups/meine-touren")}</code> gesichert, die letzten 14 bleiben erhalten. Wiederherstellen: <code>${esc(st.app_name || "meine-touren")}-restore &lt;Datei&gt;</code> im Container.</p>
   <div class="row"><a class="btn alt" href="/api/backup" download>Backup jetzt herunterladen</a></div><p class="mut" style="font-size:13px">Passwörter und Tokens sind im Download nicht enthalten. Fotos und Routen sind nicht enthalten, sie lassen sich neu laden.</p></div>
   <div class="panel"><h2>Zugriffsschutz</h2>${st.protected ? `<p class="ok"><b>✓ Passwortschutz ist aktiv.</b></p>` : `<p class="bad"><b>Die Oberfläche ist nicht passwortgeschützt.</b></p><p class="mut">Jeder im Netzwerk kann Touren, Fotos und Einstellungen sehen. Zum Schutz im Container <code>UI_PASSWORD=…</code> in <code>/etc/${esc(st.app_name || "meine-touren")}.env</code> setzen und <code>systemctl restart ${esc(st.app_name || "meine-touren")}</code> ausführen.</p>`}</div></div>`
  );
};

/* ---- Karte: Heatmap und Fotos ---- */
const _mapV = VIEWS.map;
VIEWS.map = async () => {
  await _mapV();
  const routes = ROUTES || {},
    box = $(".mapui");
  if (!box || !map) return;
  box.insertAdjacentHTML(
    "beforeend",
    `<div class="box"><button class="chip" id="mht" title="Alle Strecken übereinander: häufig begangene Wege leuchten stärker">Heatmap</button><button class="chip" id="mph" title="Fotos mit GPS-Position anzeigen">Fotos</button></div>`
  );
  const m = map,
    hl = L.layerGroup().addTo(m),
    pl = L.layerGroup().addTo(m);
  let heat = false,
    phs = null,
    phOn = false;
  const yearSel = () => +$("#my").value,
    off = () => new Set([...document.querySelectorAll("#ms .chip:not(.on)")].map(c => c.dataset.s));
  const drawHeat = () => {
    hl.clearLayers();
    if (!heat) return;
    const o = off(),
      y = yearSel();
    TOURS.forEach(t => {
      if ((y && t.y !== y) || o.has(t.sport)) return;
      const r = cleanPts(routes[t.id]);
      if (r.length > 1) L.polyline(r, {color: "#ff4d12", weight: 4, opacity: 0.17, interactive: false}).addTo(hl);
    });
  };
  const drawPh = () => {
    pl.clearLayers();
    if (!phOn || !phs) return;
    const y = yearSel();
    phs.forEach(p => {
      if (y && new Date(p.taken_ts * 1000).getFullYear() !== y) return;
      if (!okPt([p.lat, p.lng])) return;
      L.circleMarker([p.lat, p.lng], {radius: 5, color: "#fff", weight: 1.5, fillColor: "#e11d74", fillOpacity: 0.95})
        .addTo(pl)
        .bindPopup(
          `<img src="/pic/${p.id}?size=300" style="width:220px;border-radius:3px;display:block"><div style="margin-top:4px">${new Date(p.taken_ts * 1000).toLocaleString("de-DE")}${p.tour_id && BY[p.tour_id] ? `<br><a href="#/tour/${p.tour_id}">${esc(BY[p.tour_id].name)}</a>` : "<br>ohne Tour"}</div>`
        );
    });
  };
  const mainGrp = [];
  m.eachLayer(l => {
    if (l instanceof L.LayerGroup && !(l === hl || l === pl)) mainGrp.push(l);
  });
  $("#mht").onclick = e => {
    heat = !heat;
    e.target.classList.toggle("on", heat);
    mainGrp.forEach(g => (heat ? m.removeLayer(g) : m.addLayer(g)));
    drawHeat();
  };
  $("#mph").onclick = async e => {
    phOn = !phOn;
    e.target.classList.toggle("on", phOn);
    if (phOn && !phs) {
      try {
        phs = await api("/api/photos?gps=true&limit=20000");
      } catch (x) {
        phs = [];
      }
      if (!phs.length) e.target.title = "Keine Fotos mit GPS-Position";
    }
    drawPh();
  };
  box.insertAdjacentHTML(
    "beforeend",
    `<div class="box"><button class="chip" id="mbx" title="Alle Touren auflisten, die den sichtbaren Kartenausschnitt berühren">Touren im Ausschnitt</button></div>`
  );
  $("#mbx").onclick = () => {
    const b = m.getBounds(),
      y = yearSel(),
      o = off();
    const a = TOURS.filter(t => (!y || t.y === y) && !o.has(t.sport) && cleanPts(routes[t.id]).some(p => b.contains(p)));
    const md = document.createElement("div");
    md.className = "modal";
    md.innerHTML = `<div class="mbox" style="max-width:760px"><div class="sec" style="margin:0 0 10px"><h2>Im Kartenausschnitt</h2><span class="sub">${a.length} Touren, ${nf(
      a.reduce((c, t) => c + t.km, 0),
      0
    )} km, ${nf(
      a.reduce((c, t) => c + (t.up_m || 0), 0),
      0
    )} m auf</span></div>
      <div class="tl">${a.slice(0, 300).map(tourRow).join("") || '<div class="empty">Keine Touren in diesem Ausschnitt. Zoome heraus oder verschiebe die Karte.</div>'}</div>
      <div class="row" style="justify-content:flex-end;margin-top:14px"><button class="btn" id="mbc">Schließen</button></div></div>`;
    document.body.appendChild(md);
    md.querySelector("#mbc").onclick = () => md.remove();
    md.onclick = e => {
      if (e.target === md || e.target.closest("a")) md.remove();
    };
  };
  ["#my"].forEach(s =>
    $(s).addEventListener("change", () => {
      drawHeat();
      drawPh();
    })
  );
  $("#ms").addEventListener("click", () => setTimeout(drawHeat, 0));
};

/* ---- Foto-Zuordnung: GPS-Hinweis ---- */
const _ad = assignDialog;
assignDialog = (sp, done) => {
  loadRoutes()
    .catch(() => {})
    .then(() => {
      const first = sp.slice().sort((a, b) => a.taken_ts - b.taken_ts)[0],
        R = ROUTES || {};
      const near = t =>
        okPt([first.lat, first.lng]) &&
        cleanPts(R[t.id]).some(p => Math.abs(p[0] - first.lat) < 0.012 && Math.abs(p[1] - first.lng) < 0.02);
      const mark = TOURS.map(t => [t, near(t)])
        .filter(x => x[1])
        .map(x => x[0].id);
      _ad(sp, done);
      if (mark.length) {
        const sel = $("#at");
        [...sel.options].forEach(o => {
          if (mark.includes(o.value)) o.textContent = "📍 " + o.textContent;
        });
        const opts = [...sel.options].sort((a, b) => (b.textContent.startsWith("📍") ? 1 : 0) - (a.textContent.startsWith("📍") ? 1 : 0));
        opts.forEach(o => sel.appendChild(o));
        sel.selectedIndex = 0;
        sel.dispatchEvent(new Event("input"));
        sel.insertAdjacentHTML(
          "afterend",
          `<div class="mut" style="font-size:13px;margin-top:4px">📍 = das Foto wurde in der Nähe dieser Strecke aufgenommen (GPS)</div>`
        );
      }
    });
};
