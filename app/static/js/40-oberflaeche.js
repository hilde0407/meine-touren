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
const NAV_OF = {tour: "tours", story: "tours", flight: "tours", plan: "tours", sheet: "tours", compare: "tours", series: "tours", trip: "trips", tripsheet: "trips", album: "photos", shared: "photos", records: "stats", recap: "stats", places: "stats"};
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
  (wb || inner || main).insertAdjacentHTML(wb ? "afterend" : "afterbegin", `<div class="segtabs" role="tablist"><a role="tab" href="#/stats" class="${cur === "stats" ? "on" : ""}">Übersicht</a><a role="tab" href="#/places" class="${cur === "places" ? "on" : ""}">Auswertung</a><a role="tab" href="#/records" class="${cur === "records" ? "on" : ""}">Rekorde</a></div>`);
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
