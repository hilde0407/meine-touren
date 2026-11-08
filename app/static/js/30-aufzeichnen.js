/* =====================  Aufzeichnen (nur in der Android-App: window.MTApp)  ===================== */
const REC_SPORTS = [
  ["hike", "Wanderung"],
  ["mountaineering", "Bergtour"],
  ["jogging", "Lauf"],
  ["touringbicycle", "Radtour"],
  ["racebike", "Rennrad"],
  ["mtb", "MTB"],
  ["skitour", "Skitour"],
  ["snowshoe", "Schneeschuh"],
  ["nordic", "Langlauf"],
];
const recApp = () => (window.MTApp ? window.MTApp : null);
const recStatus = () => {
  try {
    return JSON.parse(recApp().status());
  } catch (e) {
    return {state: "idle"};
  }
};
const recDur = s => `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

if (recApp()) {
  /* Smartphone-Ansicht: Menü „Mehr“ (Tab-Leiste) */
  if (typeof MORE !== "undefined" && !MORE.some(x => x[0] === "record")) MORE.unshift(["record", "● Aufzeichnen"], ["apptest", "App-Test"]);
  const nav = document.querySelector("#nav");
  if (nav && !nav.querySelector('[data-k="record"]')) {
    nav.querySelector('[data-k="admin"]').insertAdjacentHTML("beforebegin", '<a href="#/record" data-k="record">● Aufzeichnen</a>');
  }
}

const recKmh = ms => (ms || 0) * 3.6;
const recCells = n => {
  const avg = n.active_s > 20 ? recKmh((n.dist_m || 0) / n.active_s) : 0,
    cell = (id, label, val) => `<div class="rc"><b id="${id}">${val}</b><span>${label}</span></div>`;
  return (
    cell("rd", "Strecke km", nf((n.dist_m || 0) / 1000, 2)) +
    cell("ru", "Aufstieg m", nf(n.up_m || 0, 0)) +
    cell("rdn", "Abstieg m", nf(n.down_m || 0, 0)) +
    cell("ralt", "Höhe m", n.alt_m != null ? nf(n.alt_m, 0) : "–") +
    cell("rmax", "Höchster Punkt m", n.max_alt_m != null ? nf(n.max_alt_m, 0) : "–") +
    cell("rspd", "Tempo km/h", nf(recKmh(n.speed_ms), 1)) +
    cell("ravg", "Ø km/h", nf(avg, 1)) +
    cell("racc", "GPS ± m", n.fix_acc_m > 0 ? nf(n.fix_acc_m, 0) : "–")
  );
};
const recFill = n => {
  const put = (id, v) => $("#" + id) && ($("#" + id).textContent = v),
    avg = n.active_s > 20 ? recKmh((n.dist_m || 0) / n.active_s) : 0;
  put("rt", recDur(n.active_s || 0));
  put("rd", nf((n.dist_m || 0) / 1000, 2));
  put("ru", nf(n.up_m || 0, 0));
  put("rdn", nf(n.down_m || 0, 0));
  put("ralt", n.alt_m != null ? nf(n.alt_m, 0) : "–");
  put("rmax", n.max_alt_m != null ? nf(n.max_alt_m, 0) : "–");
  put("rspd", nf(recKmh(n.speed_ms), 1));
  put("ravg", nf(avg, 1));
  put("racc", n.fix_acc_m > 0 ? nf(n.fix_acc_m, 0) : "–");
};
const recPhotoInfo = () => {
  try {
    return JSON.parse(recApp().photoInfo());
  } catch (e) {
    return {};
  }
};

/* Route zum Folgen mit Sprachansagen (Planungen und frühere Touren) */
const recRouteInfo = () => {
  try {
    return JSON.parse(recApp().routeInfo());
  } catch (e) {
    return {};
  }
};
const recRoutePts = pts => {
  const out = [];
  let last = null;
  for (const p of pts) {
    const la = +p[0], lo = +p[1];
    if (!isFinite(la) || !isFinite(lo)) continue;
    if (last && Math.abs(la - last[0]) < 0.00002 && Math.abs(lo - last[1]) < 0.00003) continue;   // Punkte unter ca. 2 m Abstand weglassen
    out.push((last = [la, lo]));
  }
  return out;
};
async function recLoadRoute(key) {
  const A = recApp();
  let pts, name;
  if (key.startsWith("p")) {
    const p = await api(`/api/plans/${key.slice(1)}`);
    pts = p.pts;
    name = p.name;
  } else {
    pts = await api(`/api/tours/${key.slice(1)}/coords`);
    name = (BY[key.slice(1)] || {}).name || "Tour";
  }
  pts = recRoutePts(pts || []);
  if (pts.length < 2) throw new Error("Die Strecke hat zu wenige Punkte");
  A.setRoute(pts.map(p => p[0].toFixed(6) + "," + p[1].toFixed(6)).join(";"), name);
  return pts;
}

VIEWS.record = async () => {
  const A = recApp();
  if (!A) {
    $("#main").innerHTML = '<div class="panel"><h2>Aufzeichnen</h2><p class="mut">Das Aufzeichnen funktioniert nur in der Android-App „Meine Touren“ (siehe README → Android-App).</p></div>';
    return;
  }
  let st = recStatus(),
    lastUpState = "";
  const draw = () => {
    st = recStatus();
    const s = st.state;
    let h = '<div class="sec" style="margin-top:0"><h2>Aufzeichnen</h2></div>';
    if (!A.hasPermission())
      h += '<div class="panel"><p><b>Standort-Berechtigung fehlt.</b> Für die Aufzeichnung braucht die App Zugriff auf den genauen Standort.</p><button class="btn" id="rperm">Berechtigung erteilen</button></div>';
    if (s === "idle") {
      h += `<div class="panel"><label class="mut">Sportart</label><select id="rsport" style="width:100%;font-size:17px;padding:10px;margin:6px 0 12px">${REC_SPORTS.map(([k, l]) => `<option value="${k}">${l}</option>`).join("")}</select>
        ${typeof A.setRoute === "function" ? `<label class="mut">Route mit Sprachansagen (optional)</label><select id="rroute" style="width:100%;font-size:17px;padding:10px;margin:6px 0 4px"><option value="">Keine – frei aufzeichnen</option></select>
        <div id="rrinfo" class="mut" style="font-size:13px;margin-bottom:12px">Lädt eine geplante oder frühere Strecke; unterwegs sagt die App an, wo du abbiegen musst.</div>` : ""}
        ${typeof A.takePhoto === "function" ? `<label class="mut">Fotos während der Aufzeichnung</label><select id="rphm" style="width:100%;font-size:17px;padding:10px;margin:6px 0 12px"><option value="now">Sofort auf den Server laden</option><option value="end">Gesammelt am Ende laden</option></select>` : ""}
        <label class="mut">Name (optional)</label><input id="rname" style="width:100%;font-size:17px;padding:10px;margin:6px 0 12px" placeholder="wird sonst automatisch vergeben">
        <button class="btn" id="rstart" style="width:100%;font-size:20px;padding:16px">● Aufzeichnung starten</button>
        <p class="mut" style="font-size:13px;margin-top:10px">Die Aufzeichnung läuft auch bei ausgeschaltetem Bildschirm weiter. Tipp: Akku-Optimierung für diese App ausschalten.</p>
        <button class="btn alt" id="rbat" style="margin-top:6px">Akku-Einstellungen öffnen</button> <a class="btn alt" href="#/apptest" style="margin-top:6px">App-Test</a></div>`;
    } else if (s === "finished") {
      h += `<div class="panel"><h2>Aufzeichnung beendet</h2><p>${nf((st.dist_m || 0) / 1000, 2)} km · ${recDur(st.active_s || 0)} h · ↑ ${nf(st.up_m || 0, 0)} m · ↓ ${nf(st.down_m || 0, 0)} m</p>
        <input id="rname" value="${esc(st.name)}" style="width:100%;font-size:17px;padding:10px;margin:6px 0 12px" placeholder="Name der Tour (leer lassen = automatisch)">
        ${(() => {
          const pi = typeof A.photoInfo === "function" ? recPhotoInfo() : {};
          return pi.pending ? `<p class="mut" style="font-size:13px">📷 ${pi.pending} Foto(s) werden mit hochgeladen.</p>` : "";
        })()}
        <button class="btn" id="rsend" style="width:100%;font-size:19px;padding:14px">Auf den Server speichern</button>
        <p id="rmsg" class="mut"></p>
        <button class="btn alt" id="rdrop" style="margin-top:6px">Verwerfen</button></div>`;
    } else {
      h += `<div class="panel" style="text-align:center"><div class="mut">${s === "paused" ? "⏸ pausiert" : st.gps ? "● nimmt auf" : "⚠ GPS ist ausgeschaltet"}</div>
        <div id="rt" style="font-size:44px;font-weight:700;margin:6px 0">${recDur(st.active_s || 0)}</div>
        <div class="recgrid">${recCells(st)}</div>
        ${typeof A.routeInfo === "function" && recRouteInfo().has ? `<div class="mut" id="rgi" style="font-size:13px;margin-top:8px">🧭 ${esc(recRouteInfo().name)} · ${nf(recRouteInfo().km, 1)} km <label style="margin-left:8px"><input type="checkbox" id="rgon" ${recRouteInfo().on ? "checked" : ""}> Ansagen</label></div>` : ""}
        ${typeof A.takePhoto === "function" ? '<button class="btn" id="rphoto" style="width:100%;font-size:20px;padding:16px;margin-top:12px">📷 Foto aufnehmen</button><div id="rphinfo" class="mut" style="font-size:13px;margin-top:4px"></div>' : ""}
        <div class="row" style="gap:8px;margin-top:14px;justify-content:center">
          ${s === "paused" ? '<button class="btn" id="rres">▶ Weiter</button>' : '<button class="btn alt" id="rpause">⏸ Pause</button>'}
          <button class="btn holdstop" id="rstop"><span class="fill"></span><span class="lbl">■ Beenden – gedrückt halten</span></button></div></div>
        <div id="rmap" style="height:300px;border-radius:12px;margin-top:12px"></div>`;
    }
    let bk = [];
    try {
      if (s === "idle" && typeof A.backups === "function") bk = JSON.parse(A.backups());
    } catch (e) {}
    if (bk.length)
      h += `<div class="panel"><h2>Gesicherte Aufzeichnungen</h2><p class="mut" style="font-size:13px">Jede beendete Aufzeichnung wird zusätzlich auf dem Handy gesichert (die letzten 10). Falls eine Tour nicht auf dem Server angekommen ist, kannst du sie hier erneut speichern.</p>${bk
        .map(b => `<div class="row" style="gap:8px;margin:6px 0"><span>${new Date(b.ts).toLocaleString("de-DE", {dateStyle: "short", timeStyle: "short"})} · ${Math.round(b.size / 1024)} kB</span><span class="sp"></span><button class="btn alt sm" data-bk="${esc(b.file)}">Auf den Server speichern</button></div>`)
        .join("")}<p id="bkmsg" class="mut"></p></div>`;
    if (s === "idle" && typeof A.photoInfo === "function" && recPhotoInfo().pending)
      h += `<div class="panel"><h2>Fotos warten auf den Upload</h2><p class="mut" style="font-size:13px">${recPhotoInfo().pending} Foto(s) aus früheren Aufzeichnungen liegen noch auf dem Handy (sie sind auch in der Galerie).</p><button class="btn alt" id="rphup">Jetzt hochladen</button> <span id="rphupm" class="mut"></span></div>`;
    $("#main").innerHTML = h;
    if ($("#rphup"))
      $("#rphup").onclick = () => {
        A.uploadPhotos();
        $("#rphupm").textContent = "Wird hochgeladen …";
      };
    document.querySelectorAll("[data-bk]").forEach(b => {
      b.onclick = async () => {
        b.disabled = true;
        $("#bkmsg").textContent = "Wird gespeichert …";
        try {
          const r = await api("/api/record/upload", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({gpx: A.backupGpx(b.dataset.bk), name: "", sport: "hike"})});
          await loadTours().catch(() => {});
          location.hash = "#/tour/" + r.id;
        } catch (e) {
          b.disabled = false;
          $("#bkmsg").innerHTML = `<span class="bad">Speichern fehlgeschlagen: ${esc(e.message)}</span>`;
        }
      };
    });
    lastUpState = s;
    const on = (id, f) => $(id) && ($(id).onclick = f);
    on("#rperm", () => A.requestPermission());
    on("#rbat", () => A.openBatterySettings());
    if ($("#rphm")) {
      $("#rphm").value = A.photoMode();
      $("#rphm").onchange = () => A.setPhotoMode($("#rphm").value);
    }
    if ($("#rroute")) {
      const sel = $("#rroute"),
        info = $("#rrinfo");
      Promise.all([api("/api/plans").catch(() => []), TOURS.length ? Promise.resolve() : loadTours().catch(() => {})]).then(([plans]) => {
        if (!$("#rroute")) return;
        let h = '<option value="">Keine – frei aufzeichnen</option>';
        if (plans.length) h += `<optgroup label="Geplante Touren">${plans.map(p => `<option value="p${p.id}">${esc(p.name)} · ${nf(p.km || 0, 1)} km</option>`).join("")}</optgroup>`;
        const tl = [...TOURS].sort((a, b) => (b.date || "").localeCompare(a.date || "")).slice(0, 40);
        if (tl.length) h += `<optgroup label="Frühere Touren (zum Nachgehen)">${tl.map(t => `<option value="t${t.id}">${esc(t.name)} · ${(t.date || "").slice(0, 10)} · ${nf(t.km, 1)} km</option>`).join("")}</optgroup>`;
        sel.innerHTML = h;
        const ri = recRouteInfo();
        if (ri.has) info.innerHTML = `Geladen: <b>${esc(ri.name)}</b> · ${nf(ri.km, 1)} km · ${ri.turns} Abbiegungen. Die Ansagen beginnen, sobald du auf der Route bist.`;
      });
      sel.onchange = async () => {
        if (!sel.value) {
          A.clearRoute();
          info.textContent = "Keine Route – freie Aufzeichnung.";
          return;
        }
        info.textContent = "Wird geladen …";
        try {
          await recLoadRoute(sel.value);
          const ri = recRouteInfo();
          info.innerHTML = `Geladen: <b>${esc(ri.name)}</b> · ${nf(ri.km, 1)} km · ${ri.turns} Abbiegungen.<br>Die Ansagen beginnen, sobald du auf der Route bist. <label><input type="checkbox" id="rgon2" ${ri.on ? "checked" : ""}> Ansagen</label> <button class="btn alt sm" id="rgtest">Testansage</button>`;
          $("#rgon2").onchange = e => A.setGuide(e.target.checked);
          $("#rgtest").onclick = () => A.guideTest();
        } catch (e) {
          sel.value = "";
          info.innerHTML = `<span class="bad">Route konnte nicht geladen werden: ${esc(e.message)}</span>`;
        }
      };
    }
    if ($("#rgon")) $("#rgon").onchange = e => A.setGuide(e.target.checked);
    on("#rphoto", () => {
      if (!A.takePhoto()) alert("Fotos sind nur während einer laufenden Aufzeichnung möglich.");
    });
    const rs = $("#rstop");
    if (rs) {
      let tm = null;
      const cancel = () => {
        clearTimeout(tm);
        tm = null;
        rs.classList.remove("holding");
      };
      rs.onpointerdown = e => {
        e.preventDefault();
        rs.classList.add("holding");
        clearTimeout(tm);
        tm = setTimeout(() => {
          cancel();
          if (navigator.vibrate) navigator.vibrate(60);
          A.stopRecording("");
          setTimeout(draw, 300);
        }, 1500);
      };
      ["pointerup", "pointercancel", "pointerleave"].forEach(ev => (rs["on" + ev] = cancel));
      rs.oncontextmenu = e => e.preventDefault();
    }
    on("#rstart", () => {
      if (!A.hasPermission()) return A.requestPermission();
      A.startRecording($("#rsport").value, $("#rname").value.trim());
      setTimeout(draw, 300);
    });
    on("#rpause", () => (A.pauseRecording(), setTimeout(draw, 200)));
    on("#rres", () => (A.resumeRecording(), setTimeout(draw, 200)));
    on("#rdrop", () => {
      if (!confirm("Aufzeichnung wirklich verwerfen?")) return;
      A.discardRecording();
      draw();
    });
    on("#rsend", async () => {
      const gpx = A.takeFinished();
      $("#rsend").disabled = true;
      $("#rmsg").textContent = "Wird gespeichert …";
      let phNote = "";
      if (typeof A.photoInfo === "function" && recPhotoInfo().pending) {
        A.uploadPhotos();
        for (let i = 0; i < 180; i++) {
          await new Promise(r => setTimeout(r, 1000));
          const pi = recPhotoInfo();
          $("#rmsg").textContent = `Fotos werden hochgeladen … (${pi.pending} übrig)`;
          if (!pi.pending) break;
          if (!pi.busy) {
            if (pi.error) break;
            A.uploadPhotos();
          }
        }
        const left = recPhotoInfo().pending;
        if (left) phNote = `${left} Foto(s) konnten nicht hochgeladen werden und bleiben auf dem Handy (Aufzeichnen → „Fotos hochladen“).`;
      }
      try {
        const r = await api("/api/record/upload", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({gpx, name: $("#rname").value.trim(), sport: st.sport}),
        });
        A.markUploaded();
        await loadTours().catch(() => {});
        if (phNote) alert(phNote);
        location.hash = "#/tour/" + r.id;
      } catch (e) {
        $("#rsend").disabled = false;
        $("#rmsg").innerHTML = `<span class="bad">Speichern fehlgeschlagen: ${esc(e.message)}</span><br>Die Aufzeichnung bleibt auf dem Handy erhalten – später erneut versuchen.`;
      }
    });
    if (s === "recording" || s === "paused") {
      const m = $("#rmap");
      map = mkMap(m, {layers: true});
      if (typeof A.routeInfo === "function" && recRouteInfo().has && A.routePoints) {
        try {
          L.polyline(JSON.parse(A.routePoints()), {color: "#2f6bd9", weight: 5, opacity: 0.55}).addTo(map);
        } catch (e) {}
      }
      let line = L.polyline([], {color: "#d9534f", weight: 4}).addTo(map),
        dot = null,
        fitted = false;
      const upd = () => {
        let pts = [];
        try {
          pts = JSON.parse(A.points(800));
        } catch (e) {}
        line.setLatLngs(pts);
        if (pts.length) {
          const p = pts[pts.length - 1];
          if (!dot) dot = L.circleMarker(p, {radius: 8, color: "#fff", weight: 3, fillColor: "#2f6bd9", fillOpacity: 1}).addTo(map);
          else dot.setLatLng(p);
          if (!fitted) {
            map.setView(p, 16);
            fitted = true;
          } else if (!map.getBounds().contains(p)) map.panTo(p);
        } else if (!fitted) map.setView([47, 11], 5);
      };
      upd();
      pollTimer = setInterval(() => {
        const n = recStatus();
        if (n.state !== lastUpState) return draw();
        recFill(n);
        if ($("#rphinfo")) {
          const pi = recPhotoInfo();
          $("#rphinfo").textContent = `${pi.taken || 0} Foto(s) aufgenommen` + (pi.pending ? ` · ${pi.pending} warten auf den Upload${pi.error ? " (" + pi.error + ")" : ""}` : "");
        }
        upd();
      }, 2000);
    }
  };
  window.addEventListener("mtphoto", () => location.hash === "#/record" && recFill(recStatus()));
  window.addEventListener("mtperm", () => location.hash === "#/record" && draw(), {once: true});
  draw();
};

/* Verwaltung → „Auf dem Handy“: Angaben der App */
const _admin30 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admin30(...a);
  const A = recApp();
  if (!A || $("#appbox")) return;
  const box = `<div class="panel" id="appbox"><h2>Android-App</h2>
    <p class="mut">Version ${esc(A.version())} · Server: ${esc(A.serverUrl())}</p>
    <div class="row" style="gap:8px"><button class="btn alt" id="appsrv">Serveradresse ändern</button><button class="btn alt" id="appbat">Akku-Einstellungen</button><a class="btn" href="#/apptest">App-Test und Protokoll</a></div></div>`;
  const body = document.querySelector('.atab[data-t="handy"] .gbody');
  if (body) body.insertAdjacentHTML("beforeend", box);
  else if ($("#save")) $("#save").closest(".row").insertAdjacentHTML("beforebegin", box);
  const cfg = await api("/api/settings").catch(() => ({})),
    nu = (cfg.notify_url || "").trim(),
    m = nu.match(/^(https?):\/\/([^/]+)\/(.+)$/);
  $("#appbox").insertAdjacentHTML(
    "beforeend",
    `<h3 style="margin:14px 0 4px">Push-Meldungen</h3><p class="mut" style="font-size:13px">${
      m ? "Neue Touren und Warnungen kommen als echte Handy-Meldung, wenn die kostenlose <b>ntfy</b>-App das Thema abonniert hat." : "Trage unter Verwaltung → „Benachrichtigung“ eine ntfy-Adresse ein (z. B. https://ntfy.sh/mein-thema), dann lässt sich das hier mit einem Tipp abonnieren."
    }</p><div class="row" style="gap:8px"><button class="btn alt" id="apush"${m ? "" : " disabled"}>In ntfy abonnieren</button><button class="btn alt" id="apushget">ntfy-App holen</button></div>`
  );
  if ($("#apush") && m) $("#apush").onclick = () => A.openUrl(`ntfy://${m[2]}/${m[3]}${m[1] === "http" ? "?secure=false" : ""}`);
  $("#apushget").onclick = () => A.openUrl("https://ntfy.sh/app");
  if ($("#appsrv")) $("#appsrv").onclick = () => confirm("Serveradresse wirklich ändern?") && A.changeServer();
  if ($("#appbat")) $("#appbat").onclick = () => A.openBatterySettings();
};

/* Aufzeichnung wiederfinden: ist eine unbeendete/ungesendete da, einmalig auf die Seite hinweisen */
window.addEventListener("load", () => {
  const A = recApp();
  if (!A) return;
  const s = recStatus();
  if (s.state !== "idle" && !location.hash.startsWith("#/record")) {
    const b = document.createElement("div");
    b.className = "offbar noprint";
    b.style.cursor = "pointer";
    b.textContent = s.state === "finished" ? "Eine Aufzeichnung wartet auf das Speichern – tippen." : "Aufzeichnung läuft – tippen zum Anzeigen.";
    b.onclick = () => ((location.hash = "#/record"), b.remove());
    document.body.prepend(b);
  }
});

/* =====================  App-Selbsttest und Protokoll (nur in der Android-App)  ===================== */
VIEWS.apptest = async () => {
  const A = recApp();
  if (!A) {
    $("#main").innerHTML = '<div class="panel"><h2>App-Test</h2><p class="mut">Nur in der Android-App verfügbar.</p></div>';
    return;
  }
  let D = {};
  const ck = (ok, good, bad, hint) => `<div class="r"><span>${ok ? "✓" : "✗"} ${ok ? good : `<b class="bad">${bad}</b>`}${!ok && hint ? `<small>${hint}</small>` : ""}</span></div>`;
  const draw = async (extra = "") => {
    try {
      D = JSON.parse(A.diagnose());
    } catch (e) {
      D = {};
    }
    let srv = "",
      t0 = performance.now();
    try {
      const v = await fetch("/api/me", {cache: "no-store"});
      srv = v.ok || v.status === 401 ? `Server erreichbar (${Math.round(performance.now() - t0)} ms)` : "";
    } catch (e) {}
    const st = D.status || {};
    $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>App-Test</h2><span class="sub">Version ${esc(D.version || "")} · ${esc(D.device || "")} · Android ${esc(D.android || "")}</span></div>
    <div class="rows">
      ${ck(!!srv, srv, "Server nicht erreichbar", "Heimnetz/VPN prüfen, Adresse: " + esc(D.server || ""))}
      ${ck(D.loc_perm, "Standort-Berechtigung erteilt", "Standort-Berechtigung fehlt", "Ohne sie keine Aufzeichnung.")}
      ${ck(D.gps_on, "GPS ist eingeschaltet", "GPS ist ausgeschaltet", "In den Android-Schnellmenüs „Standort“ einschalten.")}
      ${ck(D.notif_perm, "Benachrichtigungen erlaubt", "Benachrichtigungen blockiert", "Die Aufzeichnung zeigt eine Dauer-Benachrichtigung; ohne Erlaubnis beendet Android sie früher.")}
      ${ck(D.battery_free, "Akku-Optimierung für die App aus", "Akku-Optimierung ist aktiv", "Android kann die Aufzeichnung im Hintergrund beenden. Unten „Akku-Einstellungen“ öffnen und die App ausnehmen.")}
      <div class="r"><span>Aufzeichnung: <b>${esc(st.state || "-")}</b>${st.count ? ` · ${st.count} Punkte` : ""}${st.fix_age_s >= 0 ? ` · letzter Fix vor ${st.fix_age_s} s (±${st.fix_acc_m} m)` : ""}</span></div>
    </div>
    <div class="row" style="gap:8px;margin-top:12px;flex-wrap:wrap">
      <button class="btn" id="atgps">GPS-Test (15 s)</button><button class="btn alt" id="atperm">Berechtigung anfragen</button><button class="btn alt" id="atbat">Akku-Einstellungen</button></div>
    <p id="atres" class="mut" style="margin-top:10px">${extra}</p>
    <div class="sec"><h2>Protokoll</h2></div>
    <pre id="atlog" style="white-space:pre-wrap;font-size:11px;max-height:320px;overflow:auto;background:#f3f5f1;padding:8px;border-radius:8px">${esc(A.logText() || "(leer)")}</pre>
    <div class="row" style="gap:8px"><button class="btn" id="atsend">Diagnose senden / kopieren</button><button class="btn alt" id="atclr">Protokoll leeren</button></div>`;
    const lg = $("#atlog");
    lg.scrollTop = lg.scrollHeight;
    $("#atperm").onclick = () => A.requestPermission();
    $("#atbat").onclick = () => A.openBatterySettings();
    $("#atclr").onclick = () => (A.clearLog(), draw());
    $("#atsend").onclick = () => {
      const txt = `Meine Touren Diagnose\n${JSON.stringify(D)}\n\n${A.logText()}`;
      A.shareText(txt);
    };
    $("#atgps").onclick = async () => {
      if (st.state !== "idle") return ($("#atres").textContent = "Es läuft gerade eine Aufzeichnung – Test nicht möglich.");
      if (!A.hasPermission()) return A.requestPermission();
      $("#atgps").disabled = true;
      A.startRecording("hike", "GPS-Test");
      for (let i = 15; i > 0; i--) {
        $("#atres").textContent = `Test läuft … ${i} s (am besten im Freien, Bildschirm ruhig halten)`;
        await new Promise(r => setTimeout(r, 1000));
      }
      const s = recStatus();
      A.stopRecording("");
      A.discardRecording();
      const ok = s.count > 0;
      A.appLog(`GPS-Test: ${s.count} Punkte, Fix-Alter ${s.fix_age_s} s, Genauigkeit ${s.fix_acc_m} m`);
      await draw(ok ? `<b>✓ GPS-Test bestanden:</b> ${s.count} Punkte aufgezeichnet, Genauigkeit ca. ${s.fix_acc_m} m.` : '<b class="bad">✗ Kein GPS-Punkt empfangen.</b> Im Freien wiederholen; GPS und Berechtigung prüfen.');
    };
  };
  await draw();
};
