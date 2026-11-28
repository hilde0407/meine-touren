/* =====================  Oberfläche: aufgeräumte Navigation, Statistik (Auswertung + Rekorde), Entwickleransichten hinter einem Schalter  ===================== */
const dbgOn = () => {
  try {
    return localStorage.getItem("mt_debug") === "1";
  } catch (e) {
    return false;
  }
};
document.documentElement.classList.toggle("dbg", dbgOn());

/* ---- Menüleiste: sechs Hauptpunkte; Verwaltung als Zahnrad rechts, „Prüfen“ liegt in der Verwaltung ---- */
{
  const std = ["dash", "map", "tours", "records", "trips", "areas", "places", "photos", "check", "admin", "stats"],
    extra = NAV.filter(([k]) => !std.includes(k));           // z. B. „Aufzeichnen“ in der Android-App
  NAV.length = 0;
  NAV.push(["dash", "Übersicht"], ["map", "Karte"], ["tours", "Touren"], ["trips", "Reisen"], ["areas", "Gebiete"], ["photos", "Fotos"], ["stats", "Statistik"], ...extra);
  if (typeof recApp === "function" && recApp() && !NAV.some(x => x[0] === "record")) NAV.unshift(["record", "Aufzeichnen"]);       // in der App vorn und hervorgehoben (style.css), Zustand über recNavPaint
}
$("#nav").innerHTML = NAV.map(([k, l]) => `<a href="#/${k}" data-k="${k}">${l}</a>`).join("");
{
  const a = document.createElement("a");
  a.id = "hadm";
  a.href = "#/admin";
  a.title = "Verwaltung";
  a.setAttribute("aria-label", "Verwaltung");
  a.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>`;
  $(".top").insertBefore(a, $("#busy"));
}
const NAV_OF = {tour: "tours", story: "tours", flight: "tours", plan: "tours", sheet: "tours", compare: "tours", series: "tours", trip: "trips", tripsheet: "trips", album: "photos", shared: "photos", records: "stats", recap: "stats", places: "stats", pulse: "stats"};
function navFix() {
  const h = (location.hash || "#/dash").replace(/^#\/?/, "");
  let k = h.split(/[/?]/)[0] || "dash";
  if (k === "dash" && h.includes("?") && !/\?(?:(?:z|von|bis)=[^&]*&?)+$/.test(h)) k = "stats";  // (z/von/bis = Zeitraum der Seite, bleibt Übersicht)
                 // Übersicht mit gewähltem Jahr/Sport = Statistik
  const on = NAV_OF[k] || k;
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.k === on));
  $("#hadm") && $("#hadm").classList.toggle("on", k === "admin" || k === "check" || k === "apptest");
  document.documentElement.dataset.view = k;
}
addEventListener("hashchange", () => setTimeout(navFix, 0));
new MutationObserver(navFix).observe($("#main"), {childList: true});

/* ---- Handy: „Mehr“-Menü mit denselben Bezeichnungen; App-Test nur im Entwicklermodus ---- */
if (typeof MORE !== "undefined") {
  MORE.forEach(x => x[0] === "places" && ((x[0] = "stats"), (x[1] = "Statistik")));
  const drop = k => {
    const i = MORE.findIndex(x => x[0] === k);
    if (i >= 0) MORE.splice(i, 1);
  };
  if (!dbgOn()) drop("apptest");
}

/* ---- Statistik: Auswertung und Rekorde unter einem Menüpunkt, umschaltbar ---- */
function statTabs(cur) {
  const main = $("#main");
  if (!main || main.querySelector(".segtabs") || main.querySelector(".empty")) return;
  const inner = cur === "stats" ? main.querySelector(".inner") : null,
    wb = inner ? null : main.querySelector(":scope > .warnbar");
  (wb || inner || main).insertAdjacentHTML(wb ? "afterend" : "afterbegin", `<div class="segtabs" role="tablist"><a role="tab" href="#/stats" class="${cur === "stats" ? "on" : ""}">Übersicht</a><a role="tab" href="#/places" class="${cur === "places" ? "on" : ""}">Orte & Ausrüstung</a><a role="tab" href="#/records" class="${cur === "records" ? "on" : ""}">Bestwerte</a>${TOURS.some(t => t.has_hr) ? `<a role="tab" href="#/pulse" class="${cur === "pulse" ? "on" : ""}">Puls</a>` : ""}</div>`);
}
{
  const p0 = VIEWS.places,
    r0 = VIEWS.records;
  VIEWS.places = async (...a) => {
    await p0(...a);
    statTabs("places");
  };
  VIEWS.records = async (...a) => {
    await r0(...a);
    statTabs("records");
  };
}

/* ---- Verwaltung: „Prüfen & Aufräumen“ als Reiter, Entwickleransichten markieren, Schalter für den Entwicklermodus ---- */
const DEV_PANELS = ["Selbsttest", "Verlorene App-Aufzeichnungen"];
{
  const a0 = VIEWS.admin;
  VIEWS.admin = async (...a) => {
    await a0(...a);
    const tabs = $("#atabs");
    if (!tabs || tabs.querySelector(".atlink")) return;
    tabs.insertAdjacentHTML("beforeend", `<a class="atlink" href="#/check">Prüfen &amp; Aufräumen</a>`);
    if (typeof admTabsView === "function") admTabsView(tabs);                   // 3.61.0: Verlauf am Rand neu prüfen
    document.querySelectorAll("#main .panel").forEach(p => {
      const t = ((p.querySelector(":scope > h2") || {}).textContent || "").trim();
      if (DEV_PANELS.some(k => t.startsWith(k))) p.dataset.dev = "1";
      if (t.startsWith("Protokoll")) p.classList.add("logpanel");
    });
    const zt = $("#ztest");
    if (zt) zt.dataset.dev = "1";
    const host = document.querySelector('.atab[data-t="allgemein"] .gbody');
    if (host && !$("#slfacp") && typeof slFactoryAll === "function" && slCan()) {                        // 3.66.0: Werkseinstellung für alle Seiten (dieselbe Funktion wie im Dialog „Ansichten“)
      host.insertAdjacentHTML(
        "beforeend",
        `<div class="panel" id="slfacp"><h2>Seitenanordnung</h2><p class="mut">Setzt die Anordnung aller Seiten (Übersicht, Tourseite, Statistik, Reisen, Gebiete, Fotos, Karte) auf die Werkseinstellung zurück: Reihenfolge, Breiten, entfernte und hinzugefügte Bausteine und Ansichten. Touren, Ziele und Einstellungen bleiben unberührt.</p>
         <div class="row"><button type="button" class="btn ghost" id="slfacb" aria-haspopup="dialog">Alle Seiten auf Werkseinstellung zurücksetzen …</button><span class="ok" id="slfacok" role="status" aria-live="polite"></span></div></div>`
      );
      $("#slfacb").onclick = async () => {
        const r = await slFactoryAll();
        if (r) $("#slfacok").textContent = r;
      };
    }
    if (host && !$("#dbgsw")) {
      host.insertAdjacentHTML(
        "beforeend",
        `<div class="panel"><h2>Entwicklermodus</h2><p class="mut">Blendet Ansichten ein, die nur zur Fehlersuche gebraucht werden: Selbsttest, vollständiges Protokoll, App-Test, Suche nach verlorenen Aufzeichnungen und Token-Test.</p>
         <label class="chk m0"><input type="checkbox" id="dbgsw" ${dbgOn() ? "checked" : ""}> Entwickleransichten anzeigen</label></div>`
      );
      $("#dbgsw").onchange = e => {
        try {
          localStorage.setItem("mt_debug", e.target.checked ? "1" : "0");
        } catch (err) {}
        location.reload();
      };
    }
  };
  const c0 = VIEWS.check;
  VIEWS.check = async (...a) => {
    await c0(...a);
    const main = $("#main");
    if (main && !main.querySelector(".backl")) main.insertAdjacentHTML("afterbegin", `<a class="backl" href="#/admin">‹ Verwaltung</a>`);
  };
  const t0 = VIEWS.apptest;
  if (t0)
    VIEWS.apptest = async (...a) => {
      if (!dbgOn()) {
        $("#main").innerHTML = `<div class="empty"><h2>Nur im Entwicklermodus</h2><p class="mut">Den App-Test schaltest du unter Verwaltung → Allgemein → Entwicklermodus ein.</p><a class="btn" href="#/admin">Zur Verwaltung</a></div>`;
        return;
      }
      await t0(...a);
    };
}

/* ---- Gezeichnete Symbole statt Emojis am Anfang von Knöpfen, Chips und Links ----
   Die Vorlagen schreiben weiterhin z. B. „🗑 Löschen“; hier wird das führende Zeichen durch ein Liniensymbol in Schriftfarbe ersetzt.
   So sehen alle Knöpfe einheitlich aus – unabhängig davon, wie das Betriebssystem Emojis zeichnet. */
const BTN_ICONS = {
  "⛰": '<path d="M3 19l6-11 4 7 2-3 6 7z"/>',
  "✎": '<path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/>',
  "⬆": '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M5 20h14"/>',
  "⬇": '<path d="M12 4v12M7 11l5 5 5-5"/><path d="M5 20h14"/>',
  "🎨": '<path d="M12 3a9 9 0 1 0 0 18c1.4 0 2-1 2-2 0-1.6 1-2 2.5-2H18a3 3 0 0 0 3-3c0-6-4-11-9-11z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10.5" cy="7.5" r="1"/><circle cx="15" cy="7.5" r="1"/>',
  "🏷": '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.3"/>',
  "📍": '<path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.500c0 5.300 7 11.500 7 11.500z"/><circle cx="12" cy="9.500" r="2.500"/>',
  "📌": '<path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.500c0 5.300 7 11.500 7 11.500z"/><circle cx="12" cy="9.500" r="2.500"/>',
  "📖": '<path d="M3 5c3-1 6-1 9 1v14c-3-2-6-2-9-1z"/><path d="M21 5c-3-1-6-1-9 1v14c3-2 6-2 9-1z"/>',
  "📡": '<path d="M5 19a9 9 0 0 1 0-14M8 16a5 5 0 0 1 0-8M19 19a9 9 0 0 0 0-14M16 16a5 5 0 0 0 0-8"/><circle cx="12" cy="12" r="1.500"/>',
  "🔗": '<path d="M10 14a4 4 0 0 0 5.700 0l3-3a4 4 0 0 0-5.700-5.700l-1 1"/><path d="M14 10a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1"/>',
  "🖨": '<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
  "🗑": '<path d="M4 7h16M10 4h4M6 7l1 13h10l1-13"/><path d="M10 11v6M14 11v6"/>',
  "🗺": '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/>',
  "🧹": '<path d="M5 19c2-1 3-3 3-6"/><path d="M3 21l18-18"/><path d="M14 4l6 6"/><path d="M9 15l2 2"/>',
  "⏺": '<circle cx="12" cy="12" r="6" fill="currentColor"/>',
  "⏸": '<path d="M9 5v14M15 5v14"/>',
  "▶": '<path d="M7 5l12 7-12 7z" fill="currentColor"/>',
  "⏹": '<rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor"/>',
  "⌖": '<circle cx="12" cy="12" r="6"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
  "↶": '<path d="M9 7L4 12l5 5"/><path d="M4 12h10a6 6 0 0 1 0 12"/>',
  "⟳": '<path d="M20 12a8 8 0 1 1-2.300-5.700"/><path d="M20 4v5h-5"/>',
  "📷": '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.500"/>',
  "💬": '<path d="M4 5h16v11H9l-5 4z"/>',
  "🔁": '<path d="M4 9h13l-3-3M20 15H7l3 3"/>',
  "👥": '<circle cx="9" cy="9" r="3"/><path d="M3 20c0-3.300 2.700-6 6-6s6 2.700 6 6"/><path d="M16 6.500a3 3 0 0 1 0 5.500M18 14.500c2 .8 3 2.800 3 5.500"/>',
  "🏆": '<path d="M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 6H4a3 3 0 0 0 3 4M17 6h3a3 3 0 0 1-3 4M12 14v4M8 20h8"/>',
  "🎒": '<rect x="6" y="8" width="12" height="13" rx="3"/><path d="M9 8V6a3 3 0 0 1 6 0v2M9 15h6"/>',
  "🧭": '<circle cx="12" cy="12" r="9"/><path d="M15.500 8.500l-2 5-5 2 2-5z"/>',
  "🎯": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
  "🏁": '<path d="M5 21V4M5 4h13l-2 4 2 4H5"/>',
  "💡": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.500 10.900c.6.500 1 1.300 1 2.100h5c0-.8.400-1.600 1-2.100A6 6 0 0 0 12 3z"/>',
  "⛶": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
};
/* 3.72.0 (N-05): ein Symbolsystem für die ganze Oberfläche. Alle Symbole sind Liniensymbole im 24er Raster (currentColor, Strichstärke 2, runde Enden); Emoji und Zeichen wie ✓ ⚠ ✕ ↑ ↓ ⋯ ℹ ❤
   erscheinen nicht mehr. Die Vorlagen dürfen das Zeichen weiter schreiben; es wird ersetzt (1) am Anfang von Knöpfen, Chips und Links (iconize), (2) wenn ein Element nur aus dem Zeichen besteht
   und ein Symbol ist (aria-hidden, .slem, .av, .hrt …), und (3) in Vorlagen über symHtml(). Texte von Nutzern (Namen, Notizen, Schlagwörter) bleiben unverändert: ersetzt wird nur, was die App selbst schreibt. */
{
const heart = '<path d="M12 20s-7.500-4.600-7.500-10A4.200 4.200 0 0 1 12 7.500 4.200 4.200 0 0 1 19.500 10C19.500 15.400 12 20 12 20z"/>',
  sun = '<circle cx="12" cy="12" r="4"/><path d="M12 2.500v2.500M12 19v2.500M2.500 12H5M19 12h2.500M5.300 5.300l1.800 1.800M16.900 16.900l1.800 1.800M5.300 18.700l1.800-1.800M16.900 7.100l1.800-1.800"/>',
  cloud = '<path d="M7 18a4 4 0 0 1-.6-7.960A5.500 5.500 0 0 1 17 9.500a4.200 4.200 0 0 1 0 8.500z"/>',
  flake = '<path d="M12 3v18M4.200 7.500l15.600 9M19.800 7.500l-15.600 9M9.500 4.500L12 7l2.500-2.500M9.500 19.500L12 17l2.500 2.500"/>',
  bike = '<circle cx="6" cy="16" r="3.500"/><circle cx="18" cy="16" r="3.500"/><path d="M6 16l4-8h5l3 8M10 8H8M15 8l-3 8H6"/>',
  foot = '<path d="M9 3h5v7l5 3v6H5v-5l4-2z"/>',
  run = '<circle cx="15" cy="5" r="2"/><path d="M5 12l4-3 3 2 3 3h3M13 11l-2 5-4 4M13 16l3 5"/>',
  ski = '<circle cx="15" cy="5" r="2"/><path d="M3 19l16-6M5 22l16-6M9 15l3-6 4 2"/>',
  wave = '<path d="M3 18c2 0 2-1.500 4.500-1.500S10 18 12 18s2.500-1.500 4.500-1.500S19 18 21 18"/>',
  shoe = '<path d="M3 15l4-1 3-4 3 2 5 1.500c1.500.500 2 1.500 2 3v1H3z"/>',
  wind = '<path d="M3 9h11a3 3 0 1 0-3-3M3 14h15a3 3 0 1 1-3 3M3 19h7"/>',
  pin = '<path d="M12 21s7-6.200 7-11.500A7 7 0 0 0 5 9.500c0 5.300 7 11.500 7 11.500z"/><circle cx="12" cy="9.500" r="2.500"/>',
  mount = '<path d="M3 19l6-11 4 7 2-3 6 7z"/>';
Object.assign(BTN_ICONS, {
  /* Zeichen der Oberfläche */
  "✓": '<path d="M5 13l4 4L19 7"/>', "✔": '<path d="M5 13l4 4L19 7"/>', "✅": '<circle cx="12" cy="12" r="9"/><path d="M8 12.500l3 3 5-6"/>',
  "✕": '<path d="M6 6l12 12M18 6L6 18"/>', "✗": '<path d="M6 6l12 12M18 6L6 18"/>', "❌": '<path d="M6 6l12 12M18 6L6 18"/>',
  "⚠": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.500h.010"/>',
  "ℹ": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.500h.010"/>', "ⓘ": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.500h.010"/>',
  "○": '<circle cx="12" cy="12" r="6"/>', "▲": '<path d="M12 6l7 12H5z"/>', "▼": '<path d="M12 18L5 6h14z"/>', "▾": '<path d="M7 10l5 5 5-5"/>', "▸": '<path d="M10 7l5 5-5 5"/>',
  "↑": '<path d="M12 19V5M6 11l6-6 6 6"/>', "↓": '<path d="M12 5v14M6 13l6 6 6-6"/>', "⋯": '<circle cx="5" cy="12" r="1.200" fill="currentColor"/><circle cx="12" cy="12" r="1.200" fill="currentColor"/><circle cx="19" cy="12" r="1.200" fill="currentColor"/>',
  "↩": '<path d="M9 14L4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3"/>', "➡": '<path d="M5 12h14M13 6l6 6-6 6"/>', "⬅": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  "⇧": '<path d="M12 19V5M6 11l6-6 6 6"/>', "↗": '<path d="M7 17L17 7M9 7h8v8"/>', "↔": '<path d="M4 12h16M8 8l-4 4 4 4M16 8l4 4-4 4"/>',
  "❤": heart, "♥": heart, "⭐": '<path d="M12 3.500l2.600 5.400 5.900.800-4.300 4.100 1 5.900-5.200-2.800-5.200 2.800 1-5.900-4.300-4.100 5.900-.800z"/>',
  "⚙": '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.600 5.600l2.100 2.100M16.300 16.300l2.100 2.100M5.600 18.400l2.100-2.100M16.300 7.700l2.100-2.100"/>',
  "⏳": '<path d="M7 3h10M7 21h10M8 3v3l4 6-4 6v3M16 3v3l-4 6 4 6v3"/>', "✈": '<path d="M21 4L3 11l7 3 3 7z"/>', "🛰": '<path d="M5 19a9 9 0 0 1 0-14M8 16a5 5 0 0 1 0-8M19 19a9 9 0 0 0 0-14M16 16a5 5 0 0 0 0-8"/><circle cx="12" cy="12" r="1.500"/>',
  "━": '<path d="M3 12h18"/>', "❚": '<path d="M9 5v14M15 5v14"/>', "🗗": '<rect x="5" y="9" width="10" height="10" rx="1"/><path d="M9 9V5h10v10h-4"/>', "📤": '<path d="M12 16V4M7 9l5-5 5 5M5 20h14"/>',
  "⏱": '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9 2h6"/>', "📈": '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>', "📅": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
  "🔥": '<path d="M12 21c4 0 7-2.500 7-6.500 0-3-2-5-3-7-1 2-2.500 2.500-3.500 2C13 7 12 5 10 3c0 4-5 6-5 11 0 4 3 7 7 7z"/>', "🌲": '<path d="M12 3l6 8h-3l4 6H5l4-6H6zM12 17v4"/>',
  "🏔": mount + '<path d="M9 8l1.500 2M13 15l-2-2"/>', "⚡": '<path d="M13 2L5 14h6l-1 8 8-12h-6z"/>', "🍽": '<path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M17 21V3c-3 1-4 4-4 8h4"/>',
  "👟": shoe, "🥾": foot, "🏕": '<path d="M3 20L12 5l9 15zM12 20v-6"/>', "🚲": bike, "🚴": bike, "🚵": bike,
  "🌅": '<path d="M3 18h18M7 18a5 5 0 0 1 10 0M12 6v3M5.500 9.500l1.800 1.800M18.500 9.500l-1.800 1.800"/>', "🌇": '<path d="M3 18h18M7 18a5 5 0 0 1 10 0M12 8v-4M9 6l3-3 3 3"/>',
  "🌙": '<path d="M20 14.500A8 8 0 0 1 9.500 4 8 8 0 1 0 20 14.500z"/>', "☀": sun, "🌞": sun, "☁": cloud,
  "🌤": '<circle cx="9" cy="8" r="3"/><path d="M9 2v1.500M3 8h1.500M4.800 3.800l1 1M13.200 3.800l-1 1"/><path d="M8 20a3.500 3.500 0 0 1-.4-7A5 5 0 0 1 17 13.500a3.200 3.200 0 0 1 0 6.500z"/>',
  "⛅": '<circle cx="9" cy="8" r="3"/><path d="M9 2v1.500M3 8h1.500M4.800 3.800l1 1M13.200 3.800l-1 1"/><path d="M8 20a3.500 3.500 0 0 1-.4-7A5 5 0 0 1 17 13.500a3.200 3.200 0 0 1 0 6.500z"/>',
  "🌦": '<path d="M7 14a4 4 0 0 1-.6-7.900A5.500 5.500 0 0 1 17 5.500 4.200 4.200 0 0 1 17 14zM8 17l-1 3M12 17l-1 3M16 17l-1 3"/>', "🌧": '<path d="M7 14a4 4 0 0 1-.6-7.900A5.500 5.500 0 0 1 17 5.500 4.200 4.200 0 0 1 17 14zM8 17l-1 3M12 17l-1 3M16 17l-1 3"/>',
  "☔": '<path d="M4 12a8 8 0 0 1 16 0zM12 12v7a2 2 0 0 0 4 0"/>', "⛈": '<path d="M7 14a4 4 0 0 1-.6-7.900A5.500 5.500 0 0 1 17 5.500 4.200 4.200 0 0 1 17 14zM12 14l-2 4h3l-2 4"/>',
  "🌫": '<path d="M7 11a4 4 0 0 1-.6-7.900A5.500 5.500 0 0 1 17 2.500 4.200 4.200 0 0 1 17 11zM4 15h16M6 19h12"/>', "❄": flake, "🌡": '<path d="M10 14.500V5a2 2 0 0 1 4 0v9.500a4 4 0 1 1-4 0z"/><path d="M12 9v7"/>',
  "🥶": flake, "🧥": '<path d="M10 14.500V5a2 2 0 0 1 4 0v9.500a4 4 0 1 1-4 0z"/><path d="M12 12v4"/>', "🙂": '<path d="M10 14.500V5a2 2 0 0 1 4 0v9.500a4 4 0 1 1-4 0z"/><path d="M12 10v6"/>', "😎": sun, "🥵": sun,
  "🍃": wind, "💨": wind, "🌬": wind,
  /* Sportarten (Schlüssel „sp:<Sportart>“, siehe sIcon) und Ausrüstung */
  "sp:hike": foot, "sp:walk": '<circle cx="12" cy="5" r="2"/><path d="M12 8v6l-3 7M12 14l3 7M8 11l4-3 4 3"/>', "sp:mountaineering": mount, "sp:climbing": mount + '<path d="M13 4V1l4 1.500-4 1.500"/>',
  "sp:nordicwalking": '<circle cx="11" cy="5" r="2"/><path d="M11 8v6l-3 7M11 14l3 7M7 21l2-12M16 9l3 12"/>', "sp:jogging": run, "sp:trailrun": run + '<path d="M3 22l4-4"/>',
  "sp:touringbicycle": bike, "sp:racebike": bike, "sp:mtb": bike, "sp:mtb_easy": bike, "sp:bikepacking": bike + '<path d="M9 5h4"/>',
  "sp:e_touringbicycle": bike + '<path d="M20 2l-3 4h3l-3 4"/>', "sp:e_mtb": bike + '<path d="M20 2l-3 4h3l-3 4"/>',
  "sp:skialpin": ski, "sp:skitour": ski + '<path d="M3 10l3 3"/>', "sp:nordic": ski, "sp:snowboard": '<path d="M3 17L17 6a2.500 2.500 0 0 1 3.500 3.500L6.500 20.500A2.500 2.500 0 0 1 3 17zM9 12l3 3M13 9l3 3"/>', "sp:snowshoe": flake,
  "sp:kayak": '<path d="M3 13c5-3 13-3 18 0-5 3-13 3-18 0zM8 8l8 10"/>', "sp:rowing": wave + '<path d="M4 12h16M12 12V5M12 5l5 2"/>', "sp:dragonboat": wave + '<path d="M3 14c3 1 15 1 18 0l-2-4H5z"/>',
  "sp:rafting": wave + '<path d="M4 12c3 1 13 1 16 0l-1-3H5zM9 9l-2-5M15 9l2-5"/>', "sp:boat": wave + '<path d="M4 14h16l-3 3H7zM12 14V4l6 8"/>',
  "sp:skateboard": '<path d="M3 11h18l-1 3H4z"/><circle cx="7" cy="18" r="1.500"/><circle cx="17" cy="18" r="1.500"/>', "sp:skaten": '<path d="M5 4h6v9h8v5H5z"/><circle cx="8" cy="20" r="1.200"/><circle cx="16" cy="20" r="1.200"/>',
  "sp:horse": '<path d="M7 21c0-6 2-10 5-12l-1-5 4 2 4 5v2l-4 1-2-1v8"/>', "sp:paraglide": '<path d="M3 10a9 7 0 0 1 18 0c-2.500-1.500-4-1.500-6 0-1.500-1.500-4.500-1.500-6 0-2-1.500-3.500-1.500-6 0zM8 11l4 9 4-9"/>', "sp:other": pin,
  "ic:plus": '<path d="M12 5v14M5 12h14"/>', "ic:folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',      /* 3.74.0: Ordner, Neu (nur über symHtml, nie als Zeichen am Anfang eines Knopfs) */
  "gear:Rad": bike, "gear:Schuhe": foot, "gear:Ski": ski, "gear:Schneeschuhe": flake, "gear:Sonstiges": BTN_ICONS["🎒"],
});
}
/* Zeichen, die nur als ganzes Element ein Symbol sind, und Anfänge, die in Knöpfen ersetzt werden (die Namen, die mit „sp:“ oder „gear:“ beginnen, sind keine Zeichen) */
const SYM_CHARS = Object.keys(BTN_ICONS).filter(k => !/^(sp|gear|ic):/.test(k));
const symKey = k => String(k || "").replace(/️/g, "").trim();
const symSvg = (key, size = 17, cls = "ic") => {
  const p = BTN_ICONS[symKey(key)];
  return p ? `<svg class="${cls}" data-g="${symKey(key)}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>` : "";
};
/* Symbol für Vorlagen: symHtml("⚠"), symHtml("sp:hike"), symHtml("gear:Rad"); bei unbekanntem Schlüssel (z. B. eigenes Zeichen eines Nutzers) bleibt das Zeichen */
const symHtml = (key, size = 18) => symSvg(key, size, "ic ics") || esc(key);
const BTN_ICON_RE = new RegExp("^\\s*(" + SYM_CHARS.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")\\uFE0F?\\s*");
const SYM_LEAD = "button, a.btn, .chip, a.back, a.hmore, summary, #busy, #st, .bad, .ok, .notice, .tcw, [data-sym]";
const SYM_LEAF = '[aria-hidden="true"], .slem, .av, .hrt, .gfst, .wbi, .kzsy, i[style*="font-style"], [data-sym]';
function iconize() {
  document.querySelectorAll(SYM_LEAD).forEach(e => {
    const n = e.firstChild;
    if (!n || n.nodeType !== 3) return;
    const m = n.nodeValue.match(BTN_ICON_RE);
    if (!m || (/^(↑|↓)$/.test(m[1]) && n.nodeValue.trim().length > 1)) return;          // „↑ 450 m“ ist Text, „↑“ allein ein Knopf
    n.nodeValue = n.nodeValue.slice(m[0].length);
    e.insertAdjacentHTML("afterbegin", symSvg(m[1], e.matches("button, a.btn, .chip, a.back, a.hmore, summary") ? 17 : 16, "ic"));
  });
  document.querySelectorAll(SYM_LEAF).forEach(e => {                                                 // Element besteht nur aus dem Zeichen: ganzes Symbol
    if (e.children.length || e.closest("svg")) return;
    const t = e.textContent.trim();
    if (t && SYM_CHARS.includes(symKey(t)) && !e.matches("textarea, input, option")) e.innerHTML = symSvg(t, 16, "ic ics");
  });
}
/* ---- 3.71.0 (N-01/N-02/N-04): Alternativtexte, Feldbeschriftungen und Orientierungspunkte zentral ergänzen ---- */
const A11Y_LABEL = {gs: "Suche", so: "Sortierung", fy: "Jahr", my: "Zeitraum", cmp: "Tour zum Vergleich", q: "Name suchen"};
document.addEventListener("click", e => {
  const a = e.target.closest && e.target.closest("a.skip");
  if (!a) return;
  e.preventDefault();
  const m = document.getElementById("main");
  m && m.focus({preventScroll: false});
});
function a11y() {
  document.querySelectorAll("img:not([alt])").forEach(i => {
    const c = i.closest("[title],[aria-label]"),
      t = i.title || (c && (c.getAttribute("aria-label") || c.title)) || "";
    i.setAttribute("alt", t || "Foto");
  });
  Object.keys(A11Y_LABEL).forEach(id => {
    const e = document.getElementById(id);
    if (e && !e.getAttribute("aria-label") && !e.labels?.length) e.setAttribute("aria-label", A11Y_LABEL[id]);
  });
  const tb = document.getElementById("tabbar");
  if (tb && tb.tagName !== "NAV") {
    tb.setAttribute("role", "navigation");
    tb.setAttribute("aria-label", "Hauptmenü");
  }
  const nv = document.getElementById("nav");
  if (nv && !nv.getAttribute("aria-label")) nv.setAttribute("aria-label", "Bereiche");
}
{
  let pend = false;
  new MutationObserver(() => {
    if (pend) return;
    pend = true;
    requestAnimationFrame(() => {
      pend = false;
      iconize();
      a11y();
    });
  }).observe(document.body, {childList: true, subtree: true, characterData: true});
  iconize();
  a11y();
}
