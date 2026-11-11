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
  const std = ["dash", "map", "tours", "records", "trips", "places", "photos", "check", "admin", "stats"],
    extra = NAV.filter(([k]) => !std.includes(k));           // z. B. „Aufzeichnen“ in der Android-App
  NAV.length = 0;
  NAV.push(["dash", "Übersicht"], ["map", "Karte"], ["tours", "Touren"], ["trips", "Reisen"], ["photos", "Fotos"], ["stats", "Statistik"], ...extra);
  if (typeof recApp === "function" && recApp() && !NAV.some(x => x[0] === "record")) NAV.push(["record", "● Aufzeichnen"]);
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
  if (k === "dash" && h.includes("?")) k = "stats";                 // Übersicht mit gewähltem Jahr/Sport = Statistik
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
  (wb || inner || main).insertAdjacentHTML(wb ? "afterend" : "afterbegin", `<div class="segtabs" role="tablist"><a role="tab" href="#/stats" class="${cur === "stats" ? "on" : ""}">Übersicht</a><a role="tab" href="#/places" class="${cur === "places" ? "on" : ""}">Auswertung</a><a role="tab" href="#/records" class="${cur === "records" ? "on" : ""}">Rekorde</a>${TOURS.some(t => t.has_hr) ? `<a role="tab" href="#/pulse" class="${cur === "pulse" ? "on" : ""}">Puls</a>` : ""}</div>`);
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
    document.querySelectorAll("#main .panel").forEach(p => {
      const t = ((p.querySelector(":scope > h2") || {}).textContent || "").trim();
      if (DEV_PANELS.some(k => t.startsWith(k))) p.dataset.dev = "1";
      if (t.startsWith("Protokoll")) p.classList.add("logpanel");
    });
    const zt = $("#ztest");
    if (zt) zt.dataset.dev = "1";
    const host = document.querySelector('.atab[data-t="uebersicht"] .gbody');
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
        $("#main").innerHTML = `<div class="empty"><h2>Nur im Entwicklermodus</h2><p class="mut">Den App-Test schaltest du in der Verwaltung unter „Übersicht → Entwicklermodus“ ein.</p><a class="btn" href="#/admin">Zur Verwaltung</a></div>`;
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
const BTN_ICON_RE = new RegExp("^\\s*(" + Object.keys(BTN_ICONS).join("|") + ")\\uFE0F?\\s*");
function iconize() {
  document.querySelectorAll("button, a.btn, .chip, a.back, a.hmore, summary").forEach(e => {
    const n = e.firstChild;
    if (!n || n.nodeType !== 3) return;
    const m = n.nodeValue.match(BTN_ICON_RE);
    if (!m) return;
    n.nodeValue = n.nodeValue.slice(m[0].length);
    e.insertAdjacentHTML("afterbegin", `<svg class="ic" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${BTN_ICONS[m[1]]}</svg>`);
  });
}
{
  let pend = false;
  new MutationObserver(() => {
    if (pend) return;
    pend = true;
    requestAnimationFrame(() => {
      pend = false;
      iconize();
    });
  }).observe(document.body, {childList: true, subtree: true, characterData: true});
  iconize();
}
