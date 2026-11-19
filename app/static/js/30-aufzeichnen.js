/* =====================  Aufzeichnen (nur in der Android-App: window.MTApp)  =====================
   3.49.0: In der App steht das Aufzeichnen im Mittelpunkt – mittiger Reiter in der Tab-Leiste (mit Zustand), Startseite der App, neu geordnete Aufzeichnungsseite
   (bereit / läuft / pausiert / fertig), automatisches Hochladen nach dem Beenden. Die App meldet sich beim Hochladen als Aufzeichnungsgerät an (deviceInfo).
   Jede neue Brückenmethode wird per typeof abgefragt: ältere installierte APKs funktionieren mit dieser Seite weiter. */
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
const recHas = fn => !!recApp() && typeof recApp()[fn] === "function";
const recJson = (fn, def) => {
  try {
    const v = JSON.parse(recApp()[fn]());
    return v == null ? def : v;
  } catch (e) {
    return def;
  }
};
const recStatus = () => {
  const s = recJson("status", null);
  return s && typeof s === "object" && s.state ? s : {state: "idle"};
};
const recDur = s => `${Math.floor(s / 3600)}:${fmtPad2(Math.floor((s % 3600) / 60))}:${fmtPad2(Math.floor(s % 60))}`;
const recLs = (k, v) => {
  try {
    if (v === undefined) return localStorage.getItem(k);
    if (v === null) localStorage.removeItem(k);
    else localStorage.setItem(k, v);
  } catch (e) {}
  return null;
};
const REC_SVG = {
  rec: `<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="currentColor"/></svg>`,
  pause: `<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="4" width="5" height="16" rx="1" fill="currentColor"/><rect x="14" y="4" width="5" height="16" rx="1" fill="currentColor"/></svg>`,
  play: `<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4l13 8-13 8z" fill="currentColor"/></svg>`,
  stop: `<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="1.5" fill="currentColor"/></svg>`,
  up: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V6M6 11l6-6 6 6"/></svg>`,
  cam: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg>`,
  pin: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>`,
};

/* ---- Startseite der App: „Aufzeichnen“ (Standard) oder „Übersicht“ – je Gerät gemerkt. Läuft oder wartet eine Aufzeichnung, immer dorthin. ---- */
const recStartPref = () => (recLs("mt_app_start") === "dash" ? "dash" : "record");
const appHome = () => (recApp() && (recStartPref() === "record" || recStatus().state !== "idle") ? "#/record" : "#/dash");
if (recApp() && /^(#\/?)?$/.test(location.hash)) {
  try {
    history.replaceState(null, "", appHome());      // Kaltstart ohne Ziel (kein Eintrag im Verlauf: „Zurück“ verlässt die App wie bisher)
  } catch (e) {}
}
const recStartChoice = () =>
  `<div class="recseg" role="group" aria-label="Startseite der App">${[
    ["record", "Aufzeichnen"],
    ["dash", "Übersicht"],
  ]
    .map(([k, l]) => `<button type="button" class="btn ${recStartPref() === k ? "" : "alt"} sm" data-as="${k}" aria-pressed="${recStartPref() === k}">${l}</button>`)
    .join("")}</div>`;
const recStartWire = (root, again) =>
  root.querySelectorAll("[data-as]").forEach(b => (b.onclick = () => (recLs("mt_app_start", b.dataset.as), again())));

/* ---- Geräteangaben der App (ab APK 3.49.0): zufällige Installationskennung, Hersteller/Modell, Android- und App-Version ---- */
const recDevice = () => {
  if (!recHas("deviceInfo")) return null;
  const d = recJson("deviceInfo", null),
    t = (v, n) => (typeof v === "string" ? v.slice(0, n) : "");
  if (!d || typeof d !== "object" || !t(d.install_id, 40)) return null;
  return {install_id: t(d.install_id, 40), hersteller: t(d.hersteller, 40), modell: t(d.modell, 40), android: t(d.android, 20), app_version: t(d.app_version, 20)};
};
const recBody = o => {
  const d = recDevice();
  return JSON.stringify(d ? {...o, device: d} : o);
};

/* ---- Navigation: in der App ist „Aufzeichnen“ der mittlere, hervorgehobene Reiter; „Fotos“ wandert dafür nach „Mehr“ ---- */
if (recApp()) {
  if (typeof MORE !== "undefined") {
    if (!MORE.some(x => x[0] === "photos")) MORE.unshift(["photos", "Fotos"]);
    if (!MORE.some(x => x[0] === "apptest")) MORE.push(["apptest", "App-Test"]);
  }
  const nav = document.querySelector("#nav");
  if (nav && !nav.querySelector('[data-k="record"]')) nav.insertAdjacentHTML("beforeend", '<a href="#/record" data-k="record">Aufzeichnen</a>');
}
const recNav = {st: {state: "idle"}, at: 0, sig: ""};
const recNavSecs = () => {
  const s = recNav.st;
  return (s.active_s || 0) + (s.state === "recording" ? Math.max(0, (Date.now() - recNav.at) / 1000) : 0);
};
/* Reiter und Menüpunkt zeigen den Zustand in Worten, Farbe und Zeit: bereit / läuft (Zeit) / pausiert / wartet auf das Hochladen */
function recNavPaint() {
  const s = recNav.st.state,
    sec = recNavSecs(),
    run = s === "recording" || s === "paused",
    word = {recording: "Läuft", paused: "Pausiert", finished: "Hochladen"}[s] || "Aufzeichnen",
    short = sec >= 3600 ? `${Math.floor(sec / 3600)}:${fmtPad2(Math.floor((sec % 3600) / 60))}` : `${Math.floor(sec / 60)}:${fmtPad2(Math.floor(sec % 60))}`,
    sig = s + "|" + (run ? short : "") + "|" + (s === "recording" ? Math.floor(sec) : "");
  if (sig === recNav.sig) return;
  recNav.sig = sig;
  const tab = document.querySelector("#tabbar a.trec");
  if (tab) {
    tab.dataset.s = s;
    const c = tab.querySelector(".trc"),
      l = tab.querySelector(".trl"),
      inner = s === "recording" ? `<span class="trt" data-notr>${short}</span>` : s === "paused" ? REC_SVG.pause : s === "finished" ? REC_SVG.up : REC_SVG.rec;
    if (c && c.dataset.i !== s + (s === "recording" ? short : "")) {
      c.dataset.i = s + (s === "recording" ? short : "");
      c.innerHTML = inner;
    }
    if (l && l.dataset.w !== word) {
      l.dataset.w = word;
      l.textContent = word;
    }
    tab.setAttribute("aria-label", s === "recording" ? "Aufzeichnung läuft" : s === "paused" ? "Aufzeichnung pausiert" : s === "finished" ? "Aufzeichnung wartet auf das Hochladen" : "Aufzeichnen");
  }
  const a = document.querySelector('#nav a[data-k="record"]');
  if (a) {
    a.dataset.s = s;
    const w = a.querySelector(".nrw"),
      t = a.querySelector(".nrt");
    if (!w) a.innerHTML = `<span class="nrw">${word}</span><span class="nrt" data-notr>${run ? recDur(sec) : ""}</span>`;
    else {
      if (w.textContent !== word && w.dataset.w !== word) w.textContent = word;
      w.dataset.w = word;
      t.textContent = run ? recDur(sec) : "";
    }
  }
}
function recNavSync(st) {
  if (!recApp()) return;
  recNav.st = st || recStatus();
  recNav.at = Date.now();
  recNav.sig = "";
  recNavPaint();
}
if (recApp()) {
  setInterval(() => recNav.st.state === "recording" && recNavPaint(), 1000);
  setInterval(() => document.visibilityState !== "hidden" && recNavSync(), 5000);
  addEventListener("hashchange", () => recNavSync());
  window.addEventListener("mtresume", () => recNavSync());
}

const recKmh = ms => (ms || 0) * 3.6;
const recAvg = n => (n.active_s > 20 ? recKmh((n.dist_m || 0) / n.active_s) : 0);
const recVals = n => ({
  rt: recDur(n.active_s || 0),
  rd: nf((n.dist_m || 0) / 1000, 2),
  ru: nf(n.up_m || 0, 0),
  rdn: nf(n.down_m || 0, 0),
  ralt: n.alt_m != null ? nf(n.alt_m, 0) : "–",
  rmax: n.max_alt_m != null ? nf(n.max_alt_m, 0) : "–",
  rspd: nf(recKmh(n.speed_ms), 1),
  ravg: nf(recAvg(n), 1),
  racc: n.fix_acc_m > 0 ? nf(n.fix_acc_m, 0) : "–",
});
const recFill = n => {
  const v = recVals(n);
  for (const id in v) {
    const e = $("#" + id);
    if (e && e.textContent !== v[id]) e.textContent = v[id];
  }
};
const recPhotoInfo = () => recJson("photoInfo", {});

/* GPS-Zustand in Worten. Während der Aufzeichnung aus dem Status der App; davor (bereit) aus der Ortung des Browsers, sofern erlaubt (wärmt das GPS zugleich vor). */
const recGpsLive = st => {
  if (st.gps === false) return ["bad", "GPS ist ausgeschaltet"];
  if (st.state === "paused") return ["", ""];
  if (st.fix_age_s === undefined) return ["", ""];                       // ältere App: keine Angabe
  if (st.fix_age_s < 0) return ["search", "Suche GPS …"];
  if (st.fix_age_s > 30) return ["warn", `Kein GPS-Signal seit ${st.fix_age_s < 120 ? st.fix_age_s + " s" : Math.round(st.fix_age_s / 60) + " min"}`];
  if (!(st.fix_acc_m > 0)) return ["ok", "GPS bereit"];
  return st.fix_acc_m > 25 ? ["warn", `GPS ungenau, ±${nf(st.fix_acc_m, 0)} m`] : ["ok", `GPS ±${nf(st.fix_acc_m, 0)} m`];
};
const recGpsIdle = g => {
  if (g.perm === false) return ["bad", "Standort-Berechtigung fehlt"];
  if (g.on === false) return ["bad", "GPS ist ausgeschaltet"];
  if (g.acc > 0) return g.acc > 25 ? ["warn", `GPS ungenau, ±${nf(g.acc, 0)} m`] : ["ok", `GPS bereit, ±${nf(g.acc, 0)} m`];
  return g.watch ? ["search", "Suche GPS …"] : ["", "GPS ist eingeschaltet"];
};

/* ---- Sportart: zuletzt genutzte zuerst (je Gerät gemerkt) ---- */
const recSportOrder = () => {
  let last = [];
  try {
    last = JSON.parse(recLs("mt_rec_sports") || "[]");
  } catch (e) {}
  if (!Array.isArray(last)) last = [];
  const known = REC_SPORTS.map(x => x[0]),
    first = last.filter((k, i) => known.includes(k) && last.indexOf(k) === i);
  return [...first, ...known.filter(k => !first.includes(k))].map(k => REC_SPORTS.find(x => x[0] === k));
};
const recSportUsed = k => {
  const o = recSportOrder().map(x => x[0]);
  recLs("mt_rec_sports", JSON.stringify([k, ...o.filter(x => x !== k)]));
};

/* ---- Sicherungen auf dem Handy: Die App legt jede abgeschlossene Aufzeichnung zusätzlich ab (die letzten 10). Hier wird je Gerät gemerkt, welche davon
   schon auf dem Server sind – die übrigen („später senden“) stehen sichtbar auf der Seite und werden gesendet, sobald der Server erreichbar ist. ---- */
const recBk = () => {
  const l = recHas("backups") ? recJson("backups", []) : [];
  return Array.isArray(l) ? l.filter(b => b && typeof b.file === "string") : [];
};
const recBkDone = () => {
  try {
    const v = JSON.parse(recLs("mt_rec_bk_done"));
    return Array.isArray(v) ? v : null;
  } catch (e) {
    return null;
  }
};
const recBkMark = files => {
  const have = recBk().map(b => b.file);
  recLs("mt_rec_bk_done", JSON.stringify([...new Set([...(recBkDone() || []), ...files])].filter(f => have.includes(f))));
};
const recBkNames = () => {
  try {
    const v = JSON.parse(recLs("mt_rec_bk_names") || "{}");
    return v && typeof v === "object" ? v : {};
  } catch (e) {
    return {};
  }
};
const recBkOpen = () => {
  const done = recBkDone() || [];
  return recBk().filter(b => !done.includes(b.file));
};
if (recApp() && recBkDone() === null) recBkMark(recBk().map(b => b.file));       // erster Lauf mit dieser Fassung: der Bestand gilt als erledigt (er bleibt unter „Einstellungen“ erreichbar)

/* ---- Hochladen: nach dem Beenden von selbst; ohne Netz wartet die Aufzeichnung auf dem Handy und wird später gesendet ---- */
const recUp = {phase: "", busy: false, id: null, msg: "", sent: "", sum: null, dev: null, left: 0, note: "", bk: "", keep: null};
/* Notnagel für „später senden“: konnte die App keine Sicherung anlegen, bleibt die Aufzeichnung im Speicher der Seite (und, wenn sie hineinpasst, im Browser-Speicher) */
const recKeep = () => {
  try {
    const v = JSON.parse(recLs("mt_rec_keep") || "null");
    if (v && v.gpx) return v;
  } catch (e) {}
  return recUp.keep || null;
};
const recTell = () => {
  recNavSync();
  window.dispatchEvent(new Event("mtrecup"));
};
/* -> {ok, id, dup, device} | {wait: true} (Netz/Server nicht erreichbar, Anmeldung nötig) | {err: "Meldung"} */
async function recPost(gpx, name, sport) {
  let r;
  try {
    if (typeof _FL !== "undefined") _FL.clear();
    r = await fetch("/api/record/upload", {method: "POST", headers: {"Content-Type": "application/json"}, body: recBody({gpx, name, sport})});
  } catch (e) {
    return {wait: true};
  }
  let j = {};
  try {
    j = JSON.parse(await r.text());
  } catch (e) {}
  if (r.status === 401) {
    if (ME.users_enabled && !document.querySelector(".authwrap")) showAuth("login", "Bitte anmelden.");
    return {wait: true, login: true};
  }
  if (r.ok && j && j.id) return {ok: true, id: j.id, dup: !!j.dup, device: j.device || null};
  if (r.status >= 500 || r.status === 408 || r.status === 429 || (r.ok && !j.id)) return {wait: true};
  return {err: String((j && j.detail) || r.status)};
}
async function recSend() {
  const A = recApp();
  if (!A || recUp.busy) return;
  const st = recStatus();
  if (st.state !== "finished" || !recHas("takeFinished")) return;
  Object.assign(recUp, {busy: true, phase: "uploading", msg: "", id: null, left: 0, sum: {dist_m: st.dist_m || 0, active_s: st.active_s || 0, up_m: st.up_m || 0}});
  recTell();
  try {
    if (navigator.onLine !== false && recHas("uploadPhotos") && recPhotoInfo().pending) {
      A.uploadPhotos();
      for (let i = 0; i < 180; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const pi = recPhotoInfo();
        recUp.msg = `Fotos werden hochgeladen … (${pi.pending || 0} übrig)`;
        recTell();
        if (!pi.pending) break;
        if (!pi.busy) {
          if (pi.error) break;
          A.uploadPhotos();
        }
      }
      recUp.left = recPhotoInfo().pending || 0;
      recUp.msg = "";
    }
    const inp = $("#rname"),
      name = inp && location.hash.startsWith("#/record") ? inp.value.trim() : st.name || "";
    const r = await recPost(A.takeFinished() || "", name, st.sport || "");
    if (r.ok) {
      A.markUploaded();
      const b = recBk();
      if (b.length) recBkMark([b[0].file]);                 // die eben angelegte Sicherung ist auf dem Server
      Object.assign(recUp, {phase: "saved", id: r.id, sent: name, dev: r.device});
      loadTours().catch(() => {});
    } else if (r.err) Object.assign(recUp, {phase: "error", msg: r.err});
    else Object.assign(recUp, {phase: "waiting", msg: r.login ? "Bitte anmelden – danach wird die Tour gesendet." : ""});
  } catch (e) {
    Object.assign(recUp, {phase: "waiting", msg: ""});
  } finally {
    recUp.busy = false;
    recTell();
  }
}
/* Später gesendete Aufzeichnungen (Sicherungen, die noch nicht auf dem Server sind) der Reihe nach hochladen */
async function recSendBackups(manual) {
  const A = recApp();
  if (!A || recUp.busy || !recHas("backupGpx")) return;
  const open = recBkOpen(),
    keep = recKeep();
  if (!open.length && !keep) return;
  recUp.busy = true;
  recUp.bk = "busy";
  recTell();
  let ok = 0,
    last = null,
    bad = "";
  try {
    let net = true;
    if (keep) {
      const r = await recPost(keep.gpx, keep.name || "", keep.sport || "");
      if (r.ok || (r.err && /GPS-Punkte/.test(r.err))) {
        if (r.ok) (ok++, (last = r.id));
        recUp.keep = null;
        recLs("mt_rec_keep", null);
      } else if (r.err) bad = r.err;
      else net = false;
    }
    for (const b of net ? [...open].reverse() : []) {       // älteste zuerst
      const r = await recPost(A.backupGpx(b.file) || "", recBkNames()[b.file] || "", "");
      if (r.ok) {
        ok++;
        last = r.id;
        recBkMark([b.file]);
      } else if (r.err) {
        bad = r.err;
        if (/GPS-Punkte/.test(r.err)) recBkMark([b.file]);  // leere Datei: nie wieder anbieten
      } else break;                                         // kein Netz: später weiter
    }
    if (ok) await loadTours().catch(() => {});
  } finally {
    recUp.busy = false;
    recUp.bk = ok ? "ok:" + ok + ":" + (last || "") : bad ? "err:" + bad : manual ? "wait" : "";
    recTell();
  }
}
const recAuto = () => {
  if (!recApp() || recUp.busy || navigator.onLine === false) return;
  if (ME.users_enabled && !ME.user) return;
  if (recStatus().state === "finished") {
    if (recUp.phase !== "error") recSend();
  } else if (recStatus().state === "idle" && (recBkOpen().length || recKeep())) recSendBackups(false);
};
if (recApp()) {
  window.addEventListener("online", recAuto);
  window.addEventListener("mtresume", recAuto);
  window.addEventListener("load", () => setTimeout(recAuto, 2500));
  setInterval(() => recUp.phase === "waiting" && recAuto(), 30000);
}

/* Route zum Folgen mit Sprachansagen (Planungen und frühere Touren) */
const recRouteInfo = () => (recHas("routeInfo") ? recJson("routeInfo", {}) : {});
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
  await recStoreProfile(pts, name);
  return pts;
}

/* Höhenprofil der Route einmal berechnen (Server, Geländemodell) und auf dem Handy merken – für die Live-Ansicht, auch ohne Netz */
const REC_WP = ["Rast", "Aussicht", "Quelle", "Gabelung", "Gefahr", "Gipfel", "Hütte"];
const recProfKey = "mt_route_prof";
const recHav = (a, b) => {
  const R = 6371000, r = Math.PI / 180, dl = (b[0] - a[0]) * r, dn = (b[1] - a[1]) * r;
  const x = Math.sin(dl / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dn / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
};
async function recStoreProfile(pts, name) {
  recLs(recProfKey, null);
  const step = Math.max(1, Math.ceil(pts.length / 600)), q = pts.filter((_, i) => i % step === 0);
  if (q[q.length - 1] !== pts[pts.length - 1]) q.push(pts[pts.length - 1]);
  let d = [0];
  for (let i = 1; i < q.length; i++) d.push(d[i - 1] + recHav(q[i - 1], q[i]));
  try {
    const r = await api("/api/plan/elevation", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({points: q})});
    if (!r || !r.ele || r.ele.length !== q.length) return;
    localStorage.setItem(recProfKey, JSON.stringify({name, d: d.map(Math.round), e: r.ele.map(Math.round), up: r.up || 0}));
  } catch (e) { /* ohne Profil geht es auch */ }
}
const recProfile = name => {
  try {
    const p = JSON.parse(localStorage.getItem(recProfKey) || "null");
    return p && p.name === name && p.d && p.d.length > 1 ? p : null;
  } catch (e) { return null; }
};

/* Live-Ansicht: nächste Abbiegung, Rest, Ankunft, Höhenprofil mit Standort */
const recWhen = h => (h <= 1 ? "in der nächsten Stunde" : `in etwa ${h} Stunden`);
function recWeather() {
  const box = $("#rwx");
  if (!box) return;
  const o = recHas("weatherInfo") ? recJson("weatherInfo", {}) : {};
  const ev = (o.events || []).slice(0, 3);
  if (!ev.length) { box.hidden = true; return; }
  const txt = e => {
    const w = recWhen(e.in_h || 0);
    return ({thunder: `⚠ Gewittergefahr ${w}`, rain: `⚠ Starkregen ${w}`, wind: `⚠ Sturmböen bis ${e.val} km/h ${w}`, snow: `⚠ Schnee oder Frost ${w}`, cold: `⚠ Temperatursturz um ${e.val} Grad ${w}`})[e.kind] || "";
  };
  box.hidden = false;
  box.dataset.l = o.level === "danger" ? "danger" : "warn";
  const html = `<b>Wetter</b>${ev.map(e => `<div>${esc(txt(e))}</div>`).join("")}`;
  if (box.dataset.h !== html) {                               // nur bei Änderung neu schreiben (sonst liest ein Vorleser alle 2 s dasselbe)
    box.dataset.h = html;
    box.innerHTML = html;
  }
}

function recLive(st) {
  const box = $("#rlive");
  if (!box) return;
  const ri = recRouteInfo();
  if (!ri.has || !ri.total_m) { box.hidden = true; return; }
  box.hidden = false;
  const prog = ri.prog_m || 0, rest = Math.max(0, ri.total_m - prog);
  const sp = (st.active_s || 0) > 180 && (st.dist_m || 0) > 200 ? st.dist_m / st.active_s : 1.2;   // m/s, anfangs Wanderschritt
  const eta = new Date(Date.now() + (rest / sp) * 1000), hh = String(eta.getHours()).padStart(2, "0") + ":" + String(eta.getMinutes()).padStart(2, "0");
  let nxt = "";
  if (ri.off) nxt = '<div class="bad fs20 fw700">⚠ Abseits der Route</div>';
  else if (ri.next_m !== undefined) {
    const a = ri.next_angle, ar = Math.abs(a) >= 150 ? "↩" : a > 0 ? "➡" : "⬅";
    nxt = `<div class="fs34 lh1_1">${ar} <b>${ri.next_m >= 1000 ? fmtKm(ri.next_m / 1000) : Math.max(10, Math.round(ri.next_m / 10) * 10) + " m"}</b></div><div class="mut fs13">Nächste Abbiegung</div>`;
  } else nxt = '<div class="fs20">Keine Abbiegung mehr</div>';
  let prof = "";
  const pr = recProfile(ri.name);
  if (pr) {
    const W = 300, H = 64, tot = pr.d[pr.d.length - 1] || 1, lo = Math.min(...pr.e), hi = Math.max(...pr.e), sp2 = Math.max(20, hi - lo);
    const X = m => (m / tot) * W, Y = e => H - 6 - ((e - lo) / sp2) * (H - 14);
    const pts = pr.d.map((m, i) => `${X(m).toFixed(1)},${Y(pr.e[i]).toFixed(1)}`).join(" ");
    let ie = 0; while (ie < pr.d.length - 1 && pr.d[ie] < prog) ie++;
    let upLeft = 0; for (let i = Math.max(1, ie); i < pr.e.length; i++) if (pr.e[i] > pr.e[i - 1] + 0.5) upLeft += pr.e[i] - pr.e[i - 1];
    prof = `<svg viewBox="0 0 ${W} ${H}" class="recprof" role="img" aria-label="Höhenprofil der Route"><polyline points="${pts}" fill="none" stroke="var(--bars)" stroke-width="2"/>` +
      `<line x1="${X(prog).toFixed(1)}" x2="${X(prog).toFixed(1)}" y1="0" y2="${H}" stroke="#2f6bd9" stroke-width="2"/><circle cx="${X(prog).toFixed(1)}" cy="${Y(pr.e[ie]).toFixed(1)}" r="4" fill="#2f6bd9"/></svg>` +
      `<div class="mut fs13">${pr.e[ie]} m · noch ↑ ${Math.round(upLeft)} m · höchster Punkt ${hi} m</div>`;
  }
  box.innerHTML = `${nxt}<div class="row g16 jcc mt6"><span>Ziel in <b>${fmtKm(rest / 1000)}</b></span><span>Ankunft ca. <b>${hh} Uhr</b></span></div>` +
    `<div class="recprog"><div style="width:${Math.min(100, (prog / ri.total_m) * 100).toFixed(0)}%"></div></div>${prof}`;
}

/* ---- Die Aufzeichnungsseite: bereit / läuft / pausiert / fertig ---- */
let recOff = null;       // räumt die gerade angezeigte Seite ab (Ortung, Ereignisse), sobald sie verlassen oder neu aufgebaut wird
const recPlural = (n, one, many) => (n === 1 ? one : many.replace("{}", n));

function recIdleHtml(A, st, g, sel) {
  const sports = recSportOrder(),
    cur = sel || sports[0][0],
    diag = recHas("diagnose") ? recJson("diagnose", {}) : {},
    open = recBkOpen().length + (recKeep() ? 1 : 0),
    photos = recHas("photoInfo") ? recPhotoInfo().pending || 0 : 0,
    bk = recBk(),
    [q, txt] = recGpsIdle(g);
  const hint = (id, title, text, btn) => `<div class="rechint" id="${id}"><span><b>${title}</b> <span>${text}</span></span>${btn || ""}</div>`;
  let hints = "",
    later = "";            // nichts, was das Starten hindert: steht unter dem Start-Knopf
  if (recUp.note) hints += hint("rhnote", esc(recUp.note), "", '<button class="btn alt sm" id="rhnotex">Verstanden</button>');
  if (!A.hasPermission()) hints += hint("rhperm", "Standort-Berechtigung fehlt.", "Für die Aufzeichnung braucht die App Zugriff auf den genauen Standort.", '<button class="btn" id="rperm">Berechtigung erteilen</button>');
  else if (g.on === false) hints += hint("rhgps", "GPS ist ausgeschaltet.", "In den Android-Schnellmenüs „Standort“ einschalten.");
  if (diag.notif_perm === false) hints += hint("rhnotif", "Benachrichtigungen blockiert.", "<span>Die Aufzeichnung zeigt eine Dauer-Benachrichtigung; ohne Erlaubnis beendet Android sie früher.</span> <span>Bitte in den Android-Einstellungen der App erlauben.</span>");
  if (diag.battery_free === false && recLs("mt_rec_bat_hide") !== "1")
    later += hint("rhbat", "Akku-Optimierung ist aktiv.", "Android kann die Aufzeichnung im Hintergrund beenden.", '<span class="rechb"><button class="btn" id="rbat2">Akku-Einstellungen öffnen</button><button class="btn ghost sm" id="rbatx">Ausblenden</button></span>');
  if (open || recUp.bk)
    later += `<div class="rechint" id="rbk" role="status"><span><b id="rbkt"></b> <span id="rbks"></span></span><span class="rechb"><button class="btn" id="rbkup">Jetzt hochladen</button><a class="btn alt" id="rbkview" hidden>Tour ansehen</a></span></div>`;
  if (photos)
    later += hint("rhph", "Fotos warten auf den Upload", `${photos} Foto(s) aus früheren Aufzeichnungen liegen noch auf dem Handy (sie sind auch in der Galerie).`, '<span class="rechb"><button class="btn" id="rphup">Jetzt hochladen</button><span id="rphupm" class="mut"></span></span>');
  const route = recHas("setRoute")
    ? `<div class="recroute"><label class="reclbl" for="rroute">Route mit Sprachansagen</label><select id="rroute"><option value="">Keine – frei aufzeichnen</option></select>
        <div id="rrinfo" class="mut fs13"></div></div>`
    : "";
  const dev = recDevice();
  return `<div class="rec" data-s="idle"><div class="sec mt0"><h2>Aufzeichnen</h2></div>
    <p class="recgps" id="rgps" data-q="${q}" role="status"><span class="rgi" aria-hidden="true"></span><span id="rgpst">${txt}</span></p>
    ${hints}
    <div class="recsports" role="radiogroup" aria-label="Sportart">${sports.map(([k, l]) => `<button type="button" class="recsp" role="radio" aria-checked="${k === cur}" data-sp="${k}">${l}</button>`).join("")}</div>
    <button type="button" class="recstart" id="rstart"><span class="rsd" aria-hidden="true"></span><span>Aufzeichnung starten</span></button>
    <p class="recnote mut">Läuft auch bei ausgeschaltetem Bildschirm weiter.</p>
    ${route}
    ${later ? `<div class="reclater">${later}</div>` : ""}
    <details class="recset" id="rset"><summary>Einstellungen der Aufzeichnung</summary><div class="recsetb">
      <div class="recf"><label class="reclbl" for="rname">Name der Tour (optional)</label><input id="rname" maxlength="120" placeholder="wird sonst automatisch vergeben" autocomplete="off"></div>
      ${recHas("takePhoto") ? `<div class="recf"><label class="reclbl" for="rphm">Fotos während der Aufzeichnung</label><select id="rphm"><option value="now">Sofort auf den Server laden</option><option value="end">Gesammelt am Ende laden</option></select></div>` : ""}
      ${recHas("setWeather") ? `<div class="recf"><label class="chk rectog"><input type="checkbox" id="rwxon" ${A.weatherOn() ? "checked" : ""}> <span>Wetterwarnung unterwegs<small class="mut">Gewitter, Starkregen, Sturm, Kälteeinbruch</small></span></label></div>` : ""}
      <div class="recf"><span class="reclbl" id="rlhl">Live-Standort für einen Kontakt</span><div class="recpair"><select id="rlh" aria-labelledby="rlhl"><option value="3">3 Stunden</option><option value="12" selected>12 Stunden</option><option value="24">24 Stunden</option><option value="72">3 Tage</option></select><button type="button" class="btn alt" id="rlink">Link teilen</button></div><div id="rlmsg" class="mut fs13" role="status"></div></div>
      <div class="recf"><span class="reclbl">Startseite der App</span>${recStartChoice()}<small class="mut"><span>Gilt auf diesem Handy.</span> <span>Läuft eine Aufzeichnung, öffnet die App immer diese Seite.</span></small></div>
      <div class="recf"><span class="reclbl">Dieses Gerät</span><div id="rdev" class="recdev" role="status">${dev ? "Wird geprüft …" : "<span>Diese App-Fassung meldet das Handy noch nicht als Aufzeichnungsgerät an.</span> <span>Mit der aktuellen App (ab 3.49.0) erscheint es unter „Meine Geräte“.</span>"}</div></div>
      ${bk.length ? `<div class="recf"><span class="reclbl">Gesicherte Aufzeichnungen</span><small class="mut">Jede beendete Aufzeichnung wird zusätzlich auf dem Handy gesichert (die letzten 10). Falls eine Tour nicht auf dem Server angekommen ist, kannst du sie hier erneut speichern.</small>
        <div class="recbks">${bk.map(b => `<div class="recbk"><span>${fmtDatumKurz(b.ts, {zeit: true})} · ${Math.round(b.size / 1024)} kB</span><button type="button" class="btn alt sm" data-bk="${esc(b.file)}">Auf den Server speichern</button></div>`).join("")}</div><div id="bkmsg" class="mut" role="status"></div></div>` : ""}
      <div class="recf recrowb"><button type="button" class="btn alt" id="rbat">Akku-Einstellungen öffnen</button><a class="btn alt" href="#/apptest">App-Test und Protokoll</a></div>
    </div></details></div>`;
}

function recLiveHtml(A, st) {
  const s = st.state,
    v = recVals(st),
    [q, txt] = recGpsLive(st),
    ri = recRouteInfo(),
    cell = (id, label) => `<div><b id="${id}">${v[id]}</b><span>${label}</span></div>`;
  return `<div class="rec" data-s="${s}"><h2 class="recsr">Aufzeichnen</h2>
    <div class="recstate" id="rstate" role="status"><span class="rsdot" aria-hidden="true">${s === "paused" ? REC_SVG.pause : ""}</span><b id="rstt">${s === "paused" ? "Pausiert" : "Aufnahme läuft"}</b><span class="rsg" id="rgps" data-q="${q}"><span class="rgi" aria-hidden="true"></span><span id="rgpst">${txt}</span></span>${s === "paused" ? '<span class="rsp">Es wird nichts aufgezeichnet, bis du fortsetzt.</span>' : ""}</div>
    <div class="recbig"><div class="rbt" id="rt" role="timer" aria-label="Dauer">${v.rt}</div><div class="rbd" aria-label="Strecke"><span id="rd">${v.rd}</span><small>km</small></div></div>
    <div class="recrow">${cell("ru", "Aufstieg m")}${cell("ralt", "Höhe m")}${cell("rspd", "Tempo km/h")}</div>
    <div id="rlive" class="reclive" hidden></div>
    <div id="rwx" class="recwx" role="status" hidden></div>
    ${ri.has ? `<div class="recgi" id="rgi"><span>🧭 ${esc(ri.name)} · ${fmtKm(ri.km)}</span><label class="chk"><input type="checkbox" id="rgon" ${ri.on ? "checked" : ""}> <span>Ansagen</span></label></div>` : ""}
    <div id="rmap" class="recmap"></div>
    <div class="recdock">
      ${recHas("takePhoto") || recHas("addWaypoint") ? `<div class="recpair">${recHas("takePhoto") ? `<button type="button" class="recb" id="rphoto">${REC_SVG.cam}<span>Foto</span></button>` : ""}${recHas("addWaypoint") ? `<button type="button" class="recb" id="rwpb">${REC_SVG.pin}<span>Wegpunkt</span></button>` : ""}</div>` : ""}
      <div class="recpair">${s === "paused" ? `<button type="button" class="recb big go" id="rres">${REC_SVG.play}<span>Fortsetzen</span></button>` : `<button type="button" class="recb big" id="rpause">${REC_SVG.pause}<span>Pausieren</span></button>`}<button type="button" class="recb big stop" id="rstop">${REC_SVG.stop}<span>Beenden</span></button></div>
    </div>
    <p class="recinfo mut"><span id="rwpm">${st.wps ? `📍 ${st.wps} Wegpunkt(e) gesetzt` : ""}</span> <span id="rphinfo"></span></p>
    <details class="recset" id="rmore"${recLs("mt_rec_more") === "1" ? " open" : ""}><summary>Weitere Werte</summary><div class="recrow four">${cell("rdn", "Abstieg m")}${cell("rmax", "Höchster Punkt m")}${cell("ravg", "Ø km/h")}${cell("racc", "GPS ± m")}</div></details></div>`;
}

function recDoneHtml(A, st) {
  const sum = st.state === "finished" ? st : recUp.sum || {},
    cell = (val, label) => `<div><b>${val}</b><span>${label}</span></div>`,
    pend = st.state === "finished" && recHas("photoInfo") ? recPhotoInfo().pending || 0 : 0;
  return `<div class="rec" data-s="done"><div class="sec mt0"><h2>Aufzeichnung beendet</h2></div>
    <div class="recrow sum">${cell(`${fmtKm((sum.dist_m || 0) / 1000, {einheit: false})}<small>km</small>`, "Strecke")}${cell(fmtDauerHtml(sum.active_s || 0).replace('<span class="u">', "<small>").replace("</span>", "</small>"), "Dauer")}${cell(`${fmtHm(sum.up_m || 0, {einheit: false})}<small>m</small>`, "Aufstieg")}</div>
    <div class="recf"><label class="reclbl" for="rname">Name der Tour</label><input id="rname" maxlength="120" value="${esc(st.state === "finished" ? st.name || "" : recUp.sent || "")}" placeholder="leer lassen = automatisch" autocomplete="off" enterkeyhint="done"><div id="rnamem" class="mut fs13" role="status"></div></div>
    <div class="recup" id="rup" role="status" aria-live="polite"><span class="rupi" aria-hidden="true"></span><span><b id="rupt"></b><span id="rups"></span></span></div>
    ${pend ? `<p class="mut fs13" id="rphn">📷 ${pend} Foto(s) werden mit hochgeladen.</p>` : ""}
    <div class="recact"><button type="button" class="recb big go" id="rview" hidden>Tour ansehen</button><button type="button" class="recb" id="rretry" hidden>Jetzt erneut versuchen</button>
      <button type="button" class="recb" id="rnew" hidden>Neue Aufzeichnung</button><button type="button" class="recb" id="rlater" hidden>Später senden, neue Aufzeichnung</button><button type="button" class="recb quiet" id="rdrop" hidden>Verwerfen</button></div></div>`;
}

/* Zustand des Hochladens in Worten (fertige Aufzeichnung) – wird ohne Neuaufbau der Seite nachgeführt, damit das Namensfeld beim Tippen stehen bleibt */
function recDoneFill() {
  const box = $("#rup");
  if (!box) return;
  const p = recUp.phase || "waiting",
    set = (id, t) => $(id) && $(id).textContent !== t && ($(id).textContent = t),
    show = (id, on) => $(id) && ($(id).hidden = !on);
  box.dataset.p = p;
  /* je Satz ein eigenes Element: so findet die Übersetzung auch Sätze mit Platzhaltern */
  const T = {
    uploading: ["Wird hochgeladen …", [recUp.msg || "Die Tour wird auf deinen Server geladen."]],
    saved: ["Gespeichert", ["Die Tour ist auf deinem Server.", recUp.dev && recUp.dev.new ? `Dieses Handy ist jetzt unter „Meine Geräte“ als „${recUp.dev.name}“ angemeldet.` : "", recUp.left ? `${recUp.left} Foto(s) konnten nicht hochgeladen werden und bleiben auf dem Handy (Aufzeichnen → „Fotos hochladen“).` : ""]],
    waiting: ["Wartet auf Netz – wird später gesendet", recUp.msg ? [recUp.msg] : ["Die Aufzeichnung bleibt sicher auf dem Handy.", "Sobald der Server erreichbar ist, wird sie von selbst hochgeladen."]],
    error: ["Speichern nicht möglich", [recUp.msg || ""]],
  }[p];
  set("#rupt", T[0]);
  const sub = T[1].filter(Boolean).map(x => `<span>${esc(x)}</span>`).join(" ");
  if ($("#rups") && $("#rups").dataset.h !== sub) ($("#rups").dataset.h = sub), ($("#rups").innerHTML = sub);
  show("#rview", p === "saved");
  show("#rnew", p === "saved");
  show("#rretry", p === "waiting" || p === "error");
  show("#rlater", p === "waiting");
  show("#rdrop", p === "waiting" || p === "error");
  if (p === "saved" && $("#rphn")) $("#rphn").remove();
}

/* Hinweis auf später gesendete Aufzeichnungen (bereit-Seite) */
function recBkFill() {
  const box = $("#rbk");
  if (!box) return;
  const n = recBkOpen().length + (recKeep() ? 1 : 0),
    b = recUp.bk || "",
    set = (id, t) => $(id) && $(id).textContent !== t && ($(id).textContent = t);
  let t = recPlural(n, "1 Aufzeichnung ist noch nicht auf dem Server.", "{} Aufzeichnungen sind noch nicht auf dem Server."),
    sub = "Sie liegen sicher auf dem Handy und werden gesendet, sobald der Server erreichbar ist.";
  if (b === "busy") (t = "Wird hochgeladen …"), (sub = "");
  else if (b.startsWith("ok:")) {
    const k = +b.split(":")[1];
    t = recPlural(k, "1 Aufzeichnung hochgeladen.", "{} Aufzeichnungen hochgeladen.");
    sub = n ? recPlural(n, "1 weitere wartet noch.", "{} weitere warten noch.") : "";
  } else if (b.startsWith("err:")) sub = "Speichern fehlgeschlagen: " + b.slice(4);
  else if (b === "wait") sub = "Der Server ist gerade nicht erreichbar – später erneut versuchen.";
  set("#rbkt", t);
  set("#rbks", sub);
  box.dataset.p = b.startsWith("ok:") && !n ? "saved" : "";
  if ($("#rbkup")) ($("#rbkup").hidden = !n), ($("#rbkup").disabled = b === "busy");
  const v = $("#rbkview"),
    id = b.startsWith("ok:") ? b.split(":")[2] : "";
  if (v) (v.hidden = !id), id && (v.href = "#/tour/" + id);
}

VIEWS.record = async () => {
  const A = recApp();
  if (!A) {
    $("#main").innerHTML = '<div class="panel"><h2>Aufzeichnen</h2><p class="mut">Das Aufzeichnen funktioniert nur in der Android-App „Meine Touren“ (siehe README → Android-App).</p></div>';
    return;
  }
  if (recOff) recOff();
  const offs = [];
  let st = recStatus(),
    kind = "",
    lastState = "",
    watch = null,
    sel = null,          // gewählte Sportart, Namensentwurf und offene Einstellungen überstehen einen Neuaufbau der Seite (Rückkehr aus den Android-Einstellungen)
    draft = "",
    setOpen = false;
  const gps = {perm: true, on: true, acc: 0, watch: false};
  const on = (id, f) => $(id) && ($(id).onclick = f);
  const listen = (ev, f, t = window) => (t.addEventListener(ev, f), offs.push(() => t.removeEventListener(ev, f)));
  const here = () => location.hash.replace(/^#\/?/, "").split(/[/?]/)[0] === "record";
  const gpsStop = () => {
    if (watch !== null) {
      try {
        navigator.geolocation.clearWatch(watch);
      } catch (e) {}
      watch = null;
    }
    gps.watch = false;
  };
  const gpsShow = () => {
    const [q, txt] = kind === "idle" ? recGpsIdle(gps) : recGpsLive(st);
    if ($("#rgps")) $("#rgps").dataset.q = q;
    if ($("#rgpst") && $("#rgpst").dataset.t !== txt) ($("#rgpst").dataset.t = txt), ($("#rgpst").textContent = txt);
  };
  /* bereit: Ortung des Browsers mitlaufen lassen (nur mit erteilter Berechtigung und sichtbarer Seite) – zeigt die Genauigkeit und wärmt das GPS vor */
  const gpsStart = () => {
    gpsStop();
    if (kind !== "idle" || !gps.perm || document.visibilityState === "hidden" || !navigator.geolocation || !window.isSecureContext) return;
    try {
      gps.watch = true;
      watch = navigator.geolocation.watchPosition(
        p => ((gps.acc = p.coords.accuracy || 0), gpsShow()),
        () => ((gps.watch = false), (gps.acc = 0), gpsShow()),
        {enableHighAccuracy: true, maximumAge: 5000, timeout: 60000}
      );
    } catch (e) {
      gps.watch = false;
    }
  };
  recOff = () => {
    gpsStop();
    offs.forEach(f => f());
    offs.length = 0;
    recOff = null;
    if (recUp.phase === "saved" || recUp.phase === "error") Object.assign(recUp, {phase: "", id: null, msg: "", sent: "", dev: null, left: 0});
    recUp.bk = recUp.bk === "busy" ? "busy" : "";
    recUp.note = "";
  };
  listen("hashchange", () => !here() && recOff && recOff());

  const stopAsk = async () => {
    const ok = await uiConfirm({title: "Aufzeichnung beenden?", text: "Die Tour wird abgeschlossen und auf deinen Server geladen. Danach lässt sie sich nicht fortsetzen.", ok: "Beenden", cancel: "Weiter aufzeichnen", danger: true});
    if (!ok || !here()) return;
    if (navigator.vibrate) navigator.vibrate(60);
    A.stopRecording("");
    for (let i = 0; i < 20 && ["recording", "paused"].includes(recStatus().state); i++) await new Promise(r => setTimeout(r, 100));
    if (recStatus().state === "idle") recUp.note = "Die Aufzeichnung enthielt keine GPS-Punkte und wurde nicht gespeichert.";
    Object.assign(recUp, {phase: "", id: null, msg: ""});
    if (here()) draw();
  };
  const waypoint = () => {
    const m = uiModal(`<h3>Wegpunkt setzen</h3><div class="recwps">${REC_WP.map(w => `<button type="button" class="recb" data-wp="${esc(w)}">${esc(w)}</button>`).join("")}</div>
      <div class="recf"><label class="reclbl" for="rwpt">Eigene Notiz</label><input id="rwpt" maxlength="200" autocomplete="off"></div>
      <div class="uifoot"><button type="button" class="btn ghost" id="rwpx">Abbrechen</button><button type="button" class="btn" id="rwps">Speichern</button></div>`);
    const save = note => {
      const ok = A.addWaypoint(note);
      m.remove();
      if ($("#rwpm")) $("#rwpm").innerHTML = ok ? `✓ „${esc(note || "Wegpunkt")}“ gespeichert · ${recStatus().wps || 1} Wegpunkt(e)` : '<span class="bad">Noch keine Position – kurz warten, bis das GPS einen Standort hat.</span>';
    };
    m.querySelectorAll("[data-wp]").forEach(b => (b.onclick = () => save(b.dataset.wp)));
    m.querySelector("#rwps").onclick = () => save(m.querySelector("#rwpt").value.trim());
    m.querySelector("#rwpx").onclick = () => m.remove();
  };
  const deviceLine = async () => {
    const box = $("#rdev"),
      d = recDevice();
    if (!box || !d) return;
    let r = null;
    try {
      r = await api("/api/my-devices/app", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({device: d})});
    } catch (e) {}
    if (!$("#rdev")) return;
    const model = [d.hersteller, d.modell].filter(Boolean).join(" "),
      tech = [model, d.android ? "Android " + d.android : "", d.app_version ? "App " + d.app_version : ""].filter(Boolean).join(" · ");
    $("#rdev").innerHTML = (r && r.known
      ? `<b data-notr>${esc(r.name)}</b><span>${r.since ? `Beim Server bekannt seit ${fmtDatum(r.since)}.` : "Beim Server bekannt."} <a href="#/admin?tab=quellen">Meine Geräte</a></span>`
      : r
        ? "<b>Noch nicht angemeldet</b><span>Wird beim ersten Hochladen angemeldet und erscheint dann unter „Meine Geräte“.</span>"
        : "<b>Nicht prüfbar</b><span>Der Server ist gerade nicht erreichbar.</span>") + `<small class="mut" data-notr>${esc(tech)}</small>`;
  };

  const wireIdle = () => {
    if ($("#rname")) $("#rname").value = draft;
    if ($("#rset")) $("#rset").open = setOpen;
    document.querySelectorAll(".recsp").forEach(
      b =>
        (b.onclick = () => {
          sel = b.dataset.sp;
          document.querySelectorAll(".recsp").forEach(x => x.setAttribute("aria-checked", x === b ? "true" : "false"));
        })
    );
    on("#rstart", () => {
      if (!A.hasPermission()) return A.requestPermission();
      const sport = sel || recSportOrder()[0][0],
        name = $("#rname") ? $("#rname").value.trim() : "";
      recSportUsed(sport);
      recUp.note = "";
      sel = null;
      draft = "";
      if ($("#rname")) $("#rname").value = "";
      A.startRecording(sport, name);
      setTimeout(() => here() && draw(), 300);
    });
    on("#rperm", () => A.requestPermission());
    on("#rbat", () => A.openBatterySettings());
    on("#rbat2", () => A.openBatterySettings());
    on("#rbatx", () => (recLs("mt_rec_bat_hide", "1"), draw()));
    on("#rhnotex", () => ((recUp.note = ""), draw()));
    on("#rbkup", () => recSendBackups(true));
    on("#rphup", () => {
      A.uploadPhotos();
      $("#rphupm").textContent = "Wird hochgeladen …";
    });
    recStartWire($("#main"), draw);
    if ($("#rwxon")) $("#rwxon").onchange = e => A.setWeather(e.target.checked);
    if ($("#rphm")) {
      $("#rphm").value = recHas("photoMode") ? A.photoMode() : "now";
      $("#rphm").onchange = () => recHas("setPhotoMode") && A.setPhotoMode($("#rphm").value);
    }
    on("#rlink", async () => {
      const m = $("#rlmsg");
      m.textContent = "Wird erstellt …";
      try {
        const r = await api("/api/live/link", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({hours: +$("#rlh").value})});
        const until = fmtUhrzeit(r.exp);
        m.innerHTML = `Link bis ${until} Uhr erstellt.${r.https ? "" : ' <span class="bad">Die App meldet den Standort nur über HTTPS – bitte eine https-Serveradresse verwenden.</span>'}`;
        const text = `Hier kannst du meinen Live-Standort verfolgen (gültig bis ${until} Uhr): ${r.url}`;
        if (recHas("shareText")) A.shareText(text);
        else if (navigator.share) navigator.share({text}).catch(() => {});
      } catch (e) {
        m.innerHTML = `<span class="bad">${esc(e.message || e)}</span>`;
      }
    });
    document.querySelectorAll("[data-bk]").forEach(b => {
      b.onclick = async () => {
        b.disabled = true;
        $("#bkmsg").textContent = "Wird gespeichert …";
        const r = await recPost(recHas("backupGpx") ? A.backupGpx(b.dataset.bk) || "" : "", recBkNames()[b.dataset.bk] || "", "");
        if (r.ok) {
          recBkMark([b.dataset.bk]);
          await loadTours().catch(() => {});
          location.hash = "#/tour/" + r.id;
        } else if ($("#bkmsg")) {
          b.disabled = false;
          $("#bkmsg").innerHTML = `<span class="bad">Speichern fehlgeschlagen: ${esc(r.err || "Server nicht erreichbar")}</span>`;
        }
      };
    });
    if ($("#rroute")) {
      const sel = $("#rroute"),
        info = $("#rrinfo");
      const loaded = ri => {
        info.innerHTML = `Geladen: <b>${esc(ri.name)}</b> · ${fmtKm(ri.km)} · ${ri.turns} Abbiegungen. Die Ansagen beginnen, sobald du auf der Route bist.<span class="recgi"><label class="chk"><input type="checkbox" id="rgon2" ${ri.on ? "checked" : ""}> <span>Ansagen</span></label><button type="button" class="btn alt sm" id="rgtest">Testansage</button></span>`;
        $("#rgon2").onchange = e => A.setGuide(e.target.checked);
        $("#rgtest").onclick = () => A.guideTest();
      };
      Promise.all([api("/api/plans").catch(() => []), TOURS.length ? Promise.resolve() : loadTours().catch(() => {})]).then(([plans]) => {
        if ($("#rroute") !== sel) return;
        let h = '<option value="">Keine – frei aufzeichnen</option>';
        if (plans && plans.length) h += `<optgroup label="Geplante Touren">${plans.map(p => `<option value="p${p.id}">${esc(p.name)} · ${fmtKm(p.km || 0)}</option>`).join("")}</optgroup>`;
        const tl = [...TOURS].sort((a, b) => (b.date || "").localeCompare(a.date || "")).slice(0, 40);
        if (tl.length) h += `<optgroup label="Frühere Touren (zum Nachgehen)">${tl.map(t => `<option value="t${t.id}">${esc(t.name)} · ${(t.date || "").slice(0, 10)} · ${fmtKm(t.km)}</option>`).join("")}</optgroup>`;
        sel.innerHTML = h;
        const ri = recRouteInfo();
        if (ri.has) loaded(ri);
      });
      sel.onchange = async () => {
        if (!sel.value) {
          A.clearRoute();
          recLs(recProfKey, null);
          info.textContent = "Keine Route – freie Aufzeichnung.";
          return;
        }
        info.textContent = "Wird geladen …";
        try {
          await recLoadRoute(sel.value);
          if ($("#rroute") === sel) loaded(recRouteInfo());
        } catch (e) {
          sel.value = "";
          info.innerHTML = `<span class="bad">Route konnte nicht geladen werden: ${esc(e.message)}</span>`;
        }
      };
    }
    recBkFill();
    deviceLine();
    gpsStart();
    gpsShow();
    recAuto();
  };

  const wireLive = () => {
    on("#rpause", () => (A.pauseRecording(), setTimeout(() => here() && draw(), 200)));
    on("#rres", () => (A.resumeRecording(), setTimeout(() => here() && draw(), 200)));
    on("#rstop", stopAsk);
    on("#rwpb", waypoint);
    on("#rphoto", () => {
      if (!A.takePhoto()) uiAlert("Fotos sind nur während einer laufenden Aufzeichnung möglich.");
    });
    if ($("#rgon")) $("#rgon").onchange = e => A.setGuide(e.target.checked);
    if ($("#rmore")) $("#rmore").addEventListener("toggle", () => recLs("mt_rec_more", $("#rmore").open ? "1" : "0"));
    map = mkMap($("#rmap"), {layers: true});
    if (recRouteInfo().has && recHas("routePoints")) {
      try {
        L.polyline(JSON.parse(A.routePoints()), {color: "#2f6bd9", weight: 5, opacity: 0.55}).addTo(map);
      } catch (e) {}
    }
    const line = L.polyline([], {color: "#d9534f", weight: 4}).addTo(map);
    let dot = null,
      fitted = false;
    const upd = () => {
      if (!map) return;
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
    const photoInfo = () => {
      if (!$("#rphinfo") || !recHas("photoInfo")) return;
      const pi = recPhotoInfo(),
        t = pi.taken || pi.pending ? `${pi.taken || 0} Foto(s) aufgenommen` + (pi.pending ? ` · ${pi.pending} warten auf den Upload${pi.error ? " (" + pi.error + ")" : ""}` : "") : "";
      if ($("#rphinfo").dataset.t !== t) ($("#rphinfo").dataset.t = t), ($("#rphinfo").textContent = t);
    };
    upd();
    recLive(st);
    recWeather();
    photoInfo();
    pollTimer = setInterval(() => {
      if (!here()) return;
      const n = recStatus();
      if (n.state !== lastState) return draw();
      st = n;
      recFill(n);
      recNavSync(n);
      gpsShow();
      recLive(n);
      recWeather();
      photoInfo();
      upd();
    }, 2000);
  };

  const wireDone = () => {
    const rename = async () => {
      const inp = $("#rname"),
        v = inp ? inp.value.trim() : "";
      if (recUp.phase !== "saved" || !recUp.id || !v || v === recUp.sent) return;
      try {
        await api(`/api/tours/${encodeURIComponent(recUp.id)}/rename`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({name: v})});
        recUp.sent = v;
        if ($("#rnamem")) $("#rnamem").textContent = "Name geändert.";
        loadTours().catch(() => {});
      } catch (e) {
        if ($("#rnamem")) $("#rnamem").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
      }
    };
    if ($("#rname")) {
      $("#rname").onchange = rename;
      $("#rname").onkeydown = e => e.key === "Enter" && e.target.blur();
    }
    on("#rview", async () => {
      await rename();
      const id = recUp.id;
      await loadTours().catch(() => {});
      location.hash = "#/tour/" + id;
    });
    on("#rnew", () => (Object.assign(recUp, {phase: "", id: null, sent: "", dev: null, left: 0}), draw()));
    on("#rretry", () => ((recUp.phase = "waiting"), recSend()));
    on("#rdrop", async () => {
      if (!(await uiConfirm({title: "Aufzeichnung verwerfen?", text: "Aufzeichnung wirklich verwerfen?", ok: "Verwerfen", danger: true}))) return;
      A.discardRecording();
      const b = recBk();
      if (b.length) recBkMark([b[0].file]);               // bewusst verworfen: nicht als „noch zu senden“ führen (die Sicherung bleibt unter „Einstellungen“)
      Object.assign(recUp, {phase: "", id: null, msg: ""});
      draw();
    });
    on("#rlater", async () => {
      if (!(await uiConfirm({title: "Später senden?", text: "Die Aufzeichnung bleibt als Sicherung auf dem Handy (die App behält die letzten 10) und wird gesendet, sobald der Server erreichbar ist. Du kannst gleich eine neue Aufzeichnung beginnen.", ok: "Später senden"}))) return;
      const before = recBk().map(b => b.file),
        name = $("#rname") ? $("#rname").value.trim() : "",
        keep = {gpx: recHas("takeFinished") ? A.takeFinished() || "" : "", name, sport: st.sport || ""};
      A.discardRecording();
      const neu = recBk().find(b => !before.includes(b.file));
      if (neu) {
        if (name) recLs("mt_rec_bk_names", JSON.stringify({...recBkNames(), [neu.file]: name}));
      } else if (keep.gpx) {
        recUp.keep = keep;                                  // die App konnte keine Sicherung anlegen: hier festhalten
        recLs("mt_rec_keep", JSON.stringify(keep));
      }
      Object.assign(recUp, {phase: "", id: null, msg: ""});
      draw();
    });
    recDoneFill();
    if (st.state === "finished" && !recUp.busy && recUp.phase !== "error") {
      if (navigator.onLine === false) (recUp.phase = "waiting"), recDoneFill();
      else recSend();
    }
  };

  function draw() {
    st = recStatus();
    lastState = st.state;
    recNavSync(st);
    clearInterval(pollTimer);
    if (map) {
      try {
        map.remove();
      } catch (e) {}
      map = null;
    }
    gpsStop();
    if (kind === "idle") {
      if ($("#rname")) draft = $("#rname").value;
      if ($("#rset")) setOpen = $("#rset").open;
    }
    const k = st.state === "recording" || st.state === "paused" ? "live" : st.state === "finished" || (st.state === "idle" && recUp.phase === "saved") ? "done" : "idle";
    kind = k;
    if (k === "idle") {
      gps.perm = !!A.hasPermission();
      gps.on = st.gps !== false && (recHas("diagnose") ? recJson("diagnose", {}).gps_on !== false : true);
    }
    $("#main").innerHTML = k === "live" ? recLiveHtml(A, st) : k === "done" ? recDoneHtml(A, st) : recIdleHtml(A, st, gps, sel);
    if (k === "live") wireLive();
    else if (k === "done") wireDone();
    else wireIdle();
  }
  listen("mtrecup", () => {
    if (!here()) return;
    const s = recStatus().state,
      k = s === "recording" || s === "paused" ? "live" : s === "finished" || (s === "idle" && recUp.phase === "saved") ? "done" : "idle";
    if (k !== kind) return draw();
    if (k === "done") recDoneFill();
    else if (k === "idle") {
      if (!$("#rbk") && (recBkOpen().length || recUp.bk)) return draw();
      recBkFill();
    }
  });
  listen("mtphoto", () => here() && kind === "live" && recFill(recStatus()));
  listen("mtperm", () => here() && kind === "idle" && draw());
  listen("mtresume", () => here() && (kind === "idle" ? draw() : recNavSync()));
  listen("visibilitychange", () => (document.visibilityState === "hidden" ? gpsStop() : kind === "idle" && here() && (gpsStart(), gpsShow())), document);
  draw();
};

/* Verwaltung → „Auf dem Handy“: Angaben der App */
const _admin30 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admin30(...a);
  const A = recApp();
  if (!A || $("#appbox")) return;
  const box = `<div class="panel" id="appbox"><h2>Android-App</h2>
    <p class="mut">Version ${esc(recHas("version") ? A.version() : "")} · Server: ${esc(recHas("serverUrl") ? A.serverUrl() : "")}</p>
    <div class="row g8"><button class="btn alt" id="appsrv">Serveradresse ändern</button><button class="btn alt" id="appbat">Akku-Einstellungen</button><a class="btn" href="#/apptest">App-Test und Protokoll</a></div>
    <h3 class="m14-0-4">Startseite der App</h3><p class="mut fs13"><span>Was die App nach dem Öffnen zeigt.</span> <span>Gilt auf diesem Handy.</span> <span>Läuft eine Aufzeichnung, öffnet die App immer die Aufzeichnung.</span></p><div id="appstart">${recStartChoice()}</div></div>`;
  const body = document.querySelector('.atab[data-t="handy"] .gbody');
  if (body) body.insertAdjacentHTML("beforeend", box);
  else if ($("#save")) $("#save").closest(".row").insertAdjacentHTML("beforebegin", box);
  const cfg = await api("/api/settings").catch(() => ({})),
    nu = (cfg.notify_url || "").trim(),
    m = nu.match(/^(https?):\/\/([^/]+)\/(.+)$/);
  $("#appbox").insertAdjacentHTML(
    "beforeend",
    `<h3 class="m14-0-4">Push-Meldungen</h3><p class="mut fs13">${
      m ? "Neue Touren und Warnungen kommen als echte Handy-Meldung, wenn die kostenlose <b>ntfy</b>-App das Thema abonniert hat." : "Trage unter Verwaltung → „Benachrichtigung“ eine ntfy-Adresse ein (z. B. https://ntfy.sh/mein-thema), dann lässt sich das hier mit einem Tipp abonnieren."
    }</p><div class="row g8"><button class="btn alt" id="apush"${m ? "" : " disabled"}>In ntfy abonnieren</button><button class="btn alt" id="apushget">ntfy-App holen</button></div>`
  );
  if ($("#apush") && m) $("#apush").onclick = () => A.openUrl(`ntfy://${m[2]}/${m[3]}${m[1] === "http" ? "?secure=false" : ""}`);
  $("#apushget").onclick = () => A.openUrl("https://ntfy.sh/app");
  if ($("#appsrv")) $("#appsrv").onclick = async () => (await uiConfirm({title: "Serveradresse ändern?", text: "Serveradresse wirklich ändern?", ok: "Ändern"})) && A.changeServer();
  if ($("#appbat")) $("#appbat").onclick = () => A.openBatterySettings();
  const startWire = () => $("#appstart") && recStartWire($("#appstart"), () => (($("#appstart").innerHTML = recStartChoice()), startWire()));
  startWire();
};

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
    $("#main").innerHTML = `<div class="sec mt0"><h2>App-Test</h2><span class="sub">Version ${esc(D.version || "")} · ${esc(D.device || "")} · Android ${esc(D.android || "")}</span></div>
    <div class="rows">
      ${ck(!!srv, srv, "Server nicht erreichbar", "Heimnetz/VPN prüfen, Adresse: " + esc(D.server || ""))}
      ${ck(D.loc_perm, "Standort-Berechtigung erteilt", "Standort-Berechtigung fehlt", "Ohne sie keine Aufzeichnung.")}
      ${ck(D.gps_on, "GPS ist eingeschaltet", "GPS ist ausgeschaltet", "In den Android-Schnellmenüs „Standort“ einschalten.")}
      ${ck(D.notif_perm, "Benachrichtigungen erlaubt", "Benachrichtigungen blockiert", "Die Aufzeichnung zeigt eine Dauer-Benachrichtigung; ohne Erlaubnis beendet Android sie früher.")}
      ${ck(D.battery_free, "Akku-Optimierung für die App aus", "Akku-Optimierung ist aktiv", "Android kann die Aufzeichnung im Hintergrund beenden. Unten „Akku-Einstellungen“ öffnen und die App ausnehmen.")}
      <div class="r"><span>Aufzeichnung: <b>${esc(st.state || "-")}</b>${st.count ? ` · ${st.count} Punkte` : ""}${st.fix_age_s >= 0 ? ` · letzter Fix vor ${st.fix_age_s} s (±${st.fix_acc_m} m)` : ""}</span></div>
    </div>
    <div class="row g8 mt12 fxw">
      <button class="btn" id="atgps">GPS-Test (15 s)</button><button class="btn alt" id="atperm">Berechtigung anfragen</button><button class="btn alt" id="atbat">Akku-Einstellungen</button></div>
    <p id="atres" class="mut mt10">${extra}</p>
    <div class="sec"><h2>Protokoll</h2></div>
    <pre id="atlog" class="reclog">${esc(A.logText() || "(leer)")}</pre>
    <div class="row g8"><button class="btn" id="atsend">Diagnose senden / kopieren</button><button class="btn alt" id="atclr">Protokoll leeren</button></div>`;
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
      const s = recStatus(),
        vorher = recBk().map(b => b.file);
      A.stopRecording("");
      A.discardRecording();
      recBkMark(recBk().map(b => b.file).filter(f => !vorher.includes(f)));      // die Sicherung des Tests ist keine Aufzeichnung, die noch gesendet werden müsste
      const ok = s.count > 0;
      A.appLog(`GPS-Test: ${s.count} Punkte, Fix-Alter ${s.fix_age_s} s, Genauigkeit ${s.fix_acc_m} m`);
      await draw(ok ? `<b>✓ GPS-Test bestanden:</b> ${s.count} Punkte aufgezeichnet, Genauigkeit ca. ${s.fix_acc_m} m.` : '<b class="bad">✗ Kein GPS-Punkt empfangen.</b> Im Freien wiederholen; GPS und Berechtigung prüfen.');
    };
  };
  await draw();
};
