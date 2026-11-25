/* Start */
async function boot() {
  /* 3.27.0: Touren und Einstellungen gleichzeitig mit „me“ anfragen statt nacheinander (bei langsamer Verbindung drei Wartezeiten weniger). Antworten ohne Anmeldung (401) werden verworfen. */
  window._preSet = fetch("/api/settings").catch(() => null);
  window._preTours = fetch("/api/tours")
    .then(r => (r.ok ? r.json() : null))
    .catch(() => null);
  window._preCovers = (() => {                 // 3.52.0: Titelfotos der Tourenliste gleich mit (eine kleine Antwort für alle Touren)
    try {
      return localStorage.getItem("mt_tlfotos") === "0" ? null : fetch("/api/tour-covers").then(r => (r.ok ? r.json() : null)).catch(() => null);
    } catch (e) {
      return null;
    }
  })();
  try {
    ME = await fetch("/api/me").then(r => r.json());
  } catch (e) {}
  applyView();
  if (ME.users_enabled && !ME.user) {
    showAuth("login");
    return;
  }
  userMenu();
  await loadPrefs();
  route();
  if (typeof waechterInit === "function") waechterInit();   // 3.48.0: Sicherungs-Wächter
}

/* ---- Verwaltung: nach Aufgaben geordnet in Reitern (statt einer langen Seite) ----
   3.60.0 Gliederung: Allgemein (3.61.0, vorher „Übersicht“; Zustand und Grundeinstellungen) · Sportarten (Katalog, Favoriten, Statistik-Gruppen; 3.60.1: Begriff „Sportart“, Schlüssel „sportarten“,
   die Adresse ?tab=aktivitaeten aus 3.60.0 bleibt als Alias) · Touren holen · Hochladen & Planen · Fotos ·
   Automatik & Meldungen · Handy & App · Sicherung & Zugang. Jeder Bereich ist eine gleich gestaltete Karte (Titel h2, Erklärung, Inhalt; Unterabschnitte h3). */
const ADM_TABS = [
  ["allgemein", "Allgemein", "Zustand der App, Updates, Heimatort und Puls sowie Protokoll und Fehlersuche.", ["#hlt", "#upd", "#homep", "Protokoll", "Selbsttest"]],
  ["sportarten", "Sportarten", "Welche Sportarten es gibt, welche beim Aufzeichnen einer Tour zuerst erscheinen und wie die Statistik sie zusammenfasst.", ["#katp", "#favp", "#sgp"]],
  ["quellen", "Touren holen", "Woher deine Touren kommen: Komoot, Zepp, Uhren und Dateien, dazu Wanderführer.", ["Komoot", "Zepp-Import", "Garmin", "Wanderführer"]],
  ["weitergabe", "Hochladen & Planen", "Wohin Touren hochgeladen werden dürfen (nur auf deinen Wunsch) und wie Touren geplant werden.", ["Portale", "Tourplanung"]],
  ["fotos", "Fotos", "Fotobibliothek, Import und Eingangsordner.", ["Fotos", "Foto-Eingang"]],
  ["auto", "Automatik & Meldungen", "Tägliche Aktualisierung und Benachrichtigungen.", ["Automatik", "Benachrichtigung", "E-Mail-Versand"]],
  ["handy", "Handy & App", "Android-App, Standort teilen und die App auf dem Startbildschirm.", ["Android-App", "Standort teilen", "Verlorene", "Auf dem Handy"]],
  ["sicher", "Sicherung & Zugang", "Sicherungen, Zugriffsschutz und Offline-Nutzung.", ["Sicherung", "Zugriffsschutz", "Offline-Nutzung"]],
];
const ADM_TAB_ALIAS = {aktivitaeten: "sportarten", uebersicht: "allgemein"};   // ältere Links und gemerkter Reiter (3.60.0 „aktivitaeten“; bis 3.60.1 hieß „Allgemein“ „Übersicht“)
const _admG = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admG(...a);
  const main = $("#main"),
    save = $("#save"),
    q = a[1];
  if (!save || $("#atabs")) return;
  /* Reiter-Zuordnung über den deutschen Originaltitel: die Übersetzung (00-i18n.js) merkt ihn sich in data-de der Überschrift, bevor sie den Text ersetzt */
  const title = p => {
    const h = p.querySelector(":scope > h2");
    return h ? (h.dataset.de || h.textContent || "").trim() : "";
  };
  const panels = [...main.querySelectorAll(".panel")].filter(p => p.querySelector(":scope > h2"));
  const used = new Set();
  const secs = ADM_TABS.map(([id, name, intro, keys]) => {
    const sec = document.createElement("section");
    sec.className = "atab";
    sec.dataset.t = id;
    sec.innerHTML = `<p class="mut atintro">${intro}</p><div class="gbody"></div>`;
    const body = sec.querySelector(".gbody");
    keys.forEach(k => {
      const el = k[0] === "#" ? $(k) : panels.find(p => !used.has(p) && title(p).startsWith(k));
      if (!el) return;
      used.add(el);
      panels.forEach(p => el.contains(p) && used.add(p));       // Bereiche in verschobenen Containern (z. B. #upd) nicht noch einmal verschieben
      if (k[0] !== "#" && el.querySelector(":scope > h2")) el.style.setProperty("margin-top", "0", "important");
      body.appendChild(el);
    });
    return sec;
  });
  const rest = panels.filter(p => !used.has(p));       // unbekannte Bereiche gehen nicht verloren
  if (rest.length) rest.forEach(p => secs[0].querySelector(".gbody").appendChild(p));
  const nav = document.createElement("div");
  nav.id = "atabs";
  nav.className = "atabs";
  nav.setAttribute("role", "tablist");
  nav.innerHTML = ADM_TABS.map(([id, name]) => `<button role="tab" data-t="${id}">${name}</button>`).join("");
  const anchor = save.closest(".row");
  anchor.classList.add("savebar");
  anchor.parentNode.insertBefore(nav, anchor);
  secs.forEach(sec => anchor.parentNode.insertBefore(sec, anchor));
  main.querySelectorAll(":scope > .grid, :scope > .panel").forEach(g => {
    if (!g.children.length || (!g.querySelector(".panel") && !g.matches(".panel") && !g.textContent.trim())) g.remove();
  });
  let tab = (q && q.get && q.get("tab")) || "";
  if (!tab && q && q.get) tab = q.get("strava") ? "weitergabe" : q.get("suunto") ? "quellen" : "";
  try {
    if (!tab) tab = localStorage.getItem("admtab") || "";
  } catch (e) {}
  const show = id => {
    if (ADM_TAB_ALIAS[id]) id = ADM_TAB_ALIAS[id];
    if (!ADM_TABS.some(t => t[0] === id)) id = "allgemein";
    nav.querySelectorAll("button").forEach(b => {
      b.classList.toggle("on", b.dataset.t === id);
      b.setAttribute("aria-selected", b.dataset.t === id ? "true" : "false");
    });
    secs.forEach(sec => (sec.style.display = sec.dataset.t === id ? "" : "none"));
    admTabsView(nav);
    anchor.style.display = id === "sportarten" ? "none" : "";            // 3.60.0: die Abschnitte „Sportarten“ speichern mit eigenen Knöpfen – keine zweite Speichern-Leiste
    try {
      localStorage.setItem("admtab", id);
    } catch (e) {}
    const hq = location.hash.split("?")[1];
    if (!hq || /^tab=/.test(hq)) history.replaceState(null, "", "#/admin?tab=" + id);   // ohne Neuaufbau der Seite
  };
  nav.onclick = e => e.target.dataset.t && show(e.target.dataset.t);
  nav.addEventListener("scroll", () => admTabsEnd(nav), {passive: true});
  window.addEventListener("resize", () => nav.isConnected && admTabsView(nav));
  show(tab);
};

/* 3.61.0 Reiterleiste: am Handy waagerecht wischbar – der aktive Reiter wird in Sicht gerollt, data-end blendet den Verlauf am rechten Rand aus, wenn nichts mehr folgt */
const admTabsEnd = nav => nav.toggleAttribute("data-end", nav.scrollLeft + nav.clientWidth >= nav.scrollWidth - 4);
function admTabsView(nav) {
  const on = nav.querySelector("button.on");
  if (on && nav.scrollWidth > nav.clientWidth + 1) nav.scrollLeft = Math.max(0, on.offsetLeft - (nav.clientWidth - on.offsetWidth) / 2);
  admTabsEnd(nav);
}
/* ---- Warnbanner (Gesundheitscheck) und Hinweis auf neue Version (nur Administratoren) ---- */
let _hl = {t: 0, v: []},
  _up = {t: 0, v: null};
async function healthBanner() {
  try {
    if (Date.now() - _hl.t > 60000) _hl = {t: Date.now(), v: await api("/api/health")};
    if (isAdmin() && Date.now() - _up.t > 6 * 3600 * 1000) _up = {t: Date.now(), v: await api("/api/update-check").catch(() => null)};
    const m = $("#main");
    if (!m || m.querySelector(".warnbar")) return;
    const u = isAdmin() && _up.v && _up.v.newer && _up.v.enabled !== false && !location.hash.startsWith("#/admin") ? _up.v : null;
    if (!_hl.v.length && !u) return;
    m.insertAdjacentHTML(
      "afterbegin",
      `<div class="warnbar">${_hl.v.map(w => `<div><span aria-hidden="true">⚠</span> <span>${esc(w.text)}</span>${w.action === "backup" ? ` <button class="btn sm" data-act="backup">Jetzt sichern</button>` : ""}</div>`).join("")}${
        u
          ? `<div>⬆ Neue Version <b>${esc(u.latest)}</b> verfügbar (installiert: ${esc(u.current)}). <a href="#/admin">${u.can_install ? "Jetzt installieren" : "Details"}</a></div>`
          : ""
      }${_hl.v.length ? '<a href="#/admin">Verwaltung öffnen</a>' : ""}</div>`
    );
    const bb = m.querySelector('[data-act="backup"]');
    if (bb)
      bb.onclick = async () => {
        bb.disabled = true;
        bb.textContent = "Sichere …";
        try {
          await api("/api/backup/now", {method: "POST"});
          _hl.t = 0;
          m.querySelector(".warnbar")?.remove();
          healthBanner();
        } catch (e) {
          bb.disabled = false;
          bb.textContent = "Jetzt sichern";
          uiAlert(e.message || e);
        }
      };
  } catch (e) {}
}
Object.keys(VIEWS).forEach(k => {
  const f = VIEWS[k];
  VIEWS[k] = async (...a) => {
    await f(...a);
    healthBanner();
  };
});
/* 3.39.0: boot() wird erst vom letzten Skript (69-start.js) aufgerufen – vorher konnte eine fetch-Antwort die Seite zeichnen, bevor spätere Skripte (49–68) ausgeführt waren. */
