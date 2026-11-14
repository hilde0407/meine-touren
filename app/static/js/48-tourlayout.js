/* =====================  3.15.0: Neue Tourseite – Gliederung, einheitliche Abschnittsköpfe, Sprung-Leiste  =====================
   Aufbau der Tourseite (von oben): Überblick (Titel, Kennzahlen) · Abschnitts-Leiste · Gruppen
     Streckenverlauf Karte · Höhenprofil · Wegpunkte
     Aufzeichnung   je Gerät ein Block (Messwerte · Training laut Uhr · Puls), danach Wetter
     Auswertung dieser Tour  Analyse · Tempo nach Steigung · Ähnliche Touren im Vergleich · Vergleich dieser Strecke
     Fotos & Notizen
   Alle Abschnitte sind <details> mit gleichem Kopf (Symbol, Titel, Kurzaussage – auch zugeklappt sichtbar). Offen/zu merkt sich localStorage
   unter „mt_trf_<Schlüssel>“ (wie die einklappbaren Abschnitte seit 3.12.0). Die Module 36/38/43/45/46/47/08 legen ihre Karten mit tlCard() an und hängen sie
   irgendwo auf der Seite ein; tlArrange() sortiert sie – auch wenn sie erst später (nach dem Laden der Daten) erscheinen – an ihren Platz.
   Gehört eine Karte zu einem Gerät (tlDev), bekommt jedes verschiedene Gerät einen eigenen Block; ohne oder mit einem Gerät gibt es keine Zwischenüberschrift. */
const TL_ICON = {
  map: '<path d="M3 6.5l6-2.5 6 2.5 6-2.5v13.5l-6 2.5-6-2.5-6 2.5z"/><path d="M9 4v13.5M15 6.5V20"/>',
  prof: '<path d="M3 19h18"/><path d="M3 15l5-7 4 5 3-3 6 5"/>',
  pin: '<path d="M12 21s-6-5.6-6-10.5a6 6 0 0 1 12 0C18 15.4 12 21 12 21z"/><circle cx="12" cy="10.5" r="2.2"/>',
  watch: '<path d="M9 7V3.5h6V7M9 17v3.5h6V17"/><rect x="6" y="7" width="12" height="10" rx="3.5"/><path d="M12 10v2.5l1.8 1"/>',
  met: '<path d="M4 20V10M9.5 20V5M15 20v-7M20.5 20V8"/>',
  heart: '<path d="M12 20s-7.5-4.6-7.5-10A4.2 4.2 0 0 1 12 7.5 4.2 4.2 0 0 1 19.5 10C19.5 15.4 12 20 12 20z"/>',
  cloud: '<path d="M7 18a4 4 0 0 1-.6-7.96A5.5 5.5 0 0 1 17 9.5a4.2 4.2 0 0 1 0 8.5z"/>',
  trend: '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
  cmp: '<path d="M4 8h13M13 4l4 4-4 4M20 16H7M11 12l-4 4 4 4"/>',
  cam: '<path d="M4 8h3l1.5-2.5h7L17 8h3v11H4z"/><circle cx="12" cy="13" r="3.4"/>',
  note: '<path d="M6 3.5h9l3 3V20.5H6z"/><path d="M9 11h6M9 14.5h6M9 7.5h3"/>',
  dot: '<circle cx="12" cy="12" r="4"/>',
};
const tlIcon = k => `<svg class="tli" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${TL_ICON[k] || TL_ICON.dot}</svg>`;
const tlState = (k, def) => {
  try {
    const v = localStorage.getItem("mt_trf_" + k);
    return v === null ? def : v === "1";
  } catch (e) {
    return def;
  }
};
/* Ein Abschnitt: o = {id, key, icon, title, badge, body, def, cls, bodyCls}. id → #tls-<id>, Schlüssel des Zustands = key (sonst id) */
function tlSecHtml(o) {
  const k = o.key || o.id,
    open = tlState(k, !!o.def);
  return (
    `<details class="tls${o.cls ? " " + o.cls : ""}" id="tls-${o.id}" data-tls="${o.id}" data-trf="${k}"${open ? " open" : ""}>` +
    `<summary aria-controls="tlsb-${o.id}" aria-expanded="${open}">${tlIcon(o.icon)}<h3 class="tlt">${o.title}</h3><span class="tlk" id="tlk-${o.id}">${o.badge || ""}</span></summary>` +
    `<div class="tlsb${o.bodyCls ? " " + o.bodyCls : ""}" id="tlsb-${o.id}">${o.body || ""}</div></details>`
  );
}
/* Karte als eigenes Element (id = Kennung der Karte, z. B. „metcard“; die Tests und Module suchen sie weiter über diese Kennung) */
function tlCard(id, o) {
  const w = document.createElement("div");
  w.id = id;
  w.className = "tlw";
  w.innerHTML = tlSecHtml({bodyCls: "prof", ...o, id: o.sec || id});
  return w;
}
const tlBody = w => w.querySelector(".tlsb");
function tlSetBadge(w, html) {
  const k = typeof w === "string" ? document.getElementById("tlk-" + w) : w.querySelector(".tlk");
  if (k && k.dataset.src !== html) {
    k.dataset.src = html;
    k.innerHTML = html;
  }
}
const TL_DEV = {};
/* Gerät einer Karte merken: dv = {id, name, kind …} oder null; name = Ersatzname, wenn es kein angelegtes Gerät gibt */
function tlDev(w, dv, name) {
  w.dataset.tlkey = dv && dv.id != null ? "d" + dv.id : "";
  w.dataset.tlkeyname = (dv && dv.name) || name || "";
  if (dv && dv.id != null) TL_DEV["d" + dv.id] = dv;
}

const TL_CHIPS = [
  ["map", "Karte", ["map"]],
  ["prof", "Höhe", ["prof"]],
  ["wp", "Wegpunkte", ["wp"]],
  ["dev", "Gerät & Messwerte", ["met", "uhr", "puls"]],
  ["wx", "Wetter", ["wx"]],
  ["ana", "Analyse", ["ana", "steig"]],
  ["cmp", "Vergleich", ["aehn", "cmp"]],
  ["photos", "Fotos", ["photos"]],
  ["notes", "Notizen", ["notes"]],
];
/* Die Kennung „tl“ gibt es auch in anderen Ansichten (Tourenliste): nur unser Container zählt */
const tlRoot = () => {
  const r = document.getElementById("tl");
  return r && r.classList.contains("tlx") ? r : null;
};
const tlSec = id => document.getElementById("tls-" + id);
const tlVis = el => !!el && !el.closest("[hidden]");
const tlReduced = () => {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (e) {
    return false;
  }
};
/* Elemente in genau dieser Reihenfolge als erste Kinder von parent; Bereits Richtiges bleibt unberührt (keine Änderung = kein Neuzeichnen) */
function tlPlace(parent, els) {
  let ref = parent.firstElementChild;
  for (const el of els.filter(Boolean)) {
    if (el === ref) ref = ref.nextElementSibling;
    else parent.insertBefore(el, ref);
  }
}
function tlLazy(id, o, parent) {
  let s = tlSec(id);
  if (!s) {
    parent.insertAdjacentHTML("beforeend", tlSecHtml({id, ...o}));
    s = tlSec(id);
  }
  return s;
}
function tlDevHead(key, name) {
  const g = TL_DEV[key],
    nm = esc(name || (g && g.name) || "");
  return `<div class="dvrow tldh" data-tlkey="${key}">${g && typeof dvAvatar === "function" ? dvAvatar(g, "xs") : ""}<span class="dvt"><small>Aufgezeichnet mit</small><b>${nm}</b>${g && g.model ? `<small>${esc(g.model)}</small>` : ""}</span></div>`;
}

function tlArrange() {
  const root = tlRoot();
  if (!root) return false;
  const gb = n => document.getElementById("tlgb-" + n),
    t = BY[root.dataset.tid];
  // ---- Strecke
  const wp = document.getElementById("wpcard");
  tlPlace(gb("route"), [tlSec("map"), tlSec("prof"), wp]);
  const pc = document.getElementById("profcard");
  if (tlSec("prof")) tlSec("prof").hidden = !pc || pc.style.display === "none";
  // ---- Aufzeichnung: Blöcke je Gerät
  const rec = gb("rec"),
    dr = document.getElementById("devrow");
  let host = document.getElementById("tlrec");
  if (!host) {
    rec.insertAdjacentHTML("afterbegin", '<div id="tlrec" class="tlrec"></div>');
    host = document.getElementById("tlrec");
  }
  const cards = [["met", "metcard"], ["uhr", "uhrcard"], ["puls", "pulscard"]].map(([k, id]) => [k, document.getElementById(id)]).filter(x => x[1]),
    strong = [];
  cards.forEach(([, el]) => el.dataset.tlkey && !strong.includes(el.dataset.tlkey) && strong.push(el.dataset.tlkey));
  if (dr && strong.includes(dr.dataset.tlkey)) strong.splice(0, strong.length, dr.dataset.tlkey, ...strong.filter(x => x !== dr.dataset.tlkey));
  const keys = strong.length ? strong : cards.length ? [""] : [],
    multi = keys.length > 1;
  if (dr && cards.length && !(multi && keys.includes(dr.dataset.tlkey))) tlPlace(rec, [dr]);    // Einzelgerät: die Zeile „Aufgezeichnet mit“ steht einmal oben
  const blocks = keys.map(key => {
    let b = host.querySelector(`.tldev[data-tlkey="${key}"]`);
    if (!b) {
      b = document.createElement("div");
      b.className = "tldev";
      b.dataset.tlkey = key;
      host.appendChild(b);
    }
    b.classList.toggle("multi", multi);
    const mine = cards.filter(([, el]) => (el.dataset.tlkey || keys[0]) === key).map(x => x[1]);
    let head = null;
    if (multi) {
      head = dr && dr.dataset.tlkey === key ? dr : b.querySelector(".tldh");
      if (!head) {
        const nm = (mine.find(e => e.dataset.tlkeyname) || {dataset: {}}).dataset.tlkeyname;
        b.insertAdjacentHTML("afterbegin", tlDevHead(key, nm));
        head = b.querySelector(".tldh");
      }
    }
    b.querySelectorAll(":scope > .tldh").forEach(h => h !== head && h.remove());     // Kopf, der vor der Zeile „Aufgezeichnet mit“ entstand
    tlPlace(b, [head, ...mine]);
    return b;
  });
  host.querySelectorAll(":scope > .tldev").forEach(b => !blocks.includes(b) && b.remove());
  tlPlace(host, blocks);
  const wx = document.querySelector("#main .wx");
  if (wx) {
    const s = tlLazy("wx", {key: "tl_wx", icon: "cloud", title: "Wetter", def: false}, rec);
    if (!s.querySelector(".tlsb .wx") || s.querySelector(".tlsb .wx") !== wx) s.querySelector(".tlsb").appendChild(wx);
    tlSetBadge(s, esc(wx.textContent.split(" · ").slice(0, 2).join(" · ")));
  }
  tlPlace(rec, [dr && dr.parentElement === rec ? dr : null, host, tlSec("wx")]);
  // ---- Auswertung
  const ev = [document.getElementById("anacard"), document.getElementById("steigcard"), document.getElementById("aehncard"), document.getElementById("cmpseg")];
  tlPlace(gb("eval"), ev);
  // ---- Fotos und Notizen
  const nt = [document.getElementById("starrow"), document.querySelector("#note") && document.querySelector("#note").closest(".field"), document.getElementById("gearrow"), document.getElementById("safety")];
  if (nt.some(Boolean)) {
    const s = tlLazy("notes", {key: "tl_notes", icon: "note", title: "Notizen & Ausrüstung", def: true, bodyCls: "tlnotes"}, gb("more"));
    tlPlace(s.querySelector(".tlsb"), nt);
    const st = t && t.stars ? "★".repeat(t.stars) : "",
      src = [st, t && t.note ? "Notiz" : ""].filter(Boolean).join(" · ");
    tlSetBadge(s, src);
  }
  tlPlace(gb("more"), [tlSec("photos"), tlSec("notes")]);
  // ---- Gruppen ohne Inhalt ausblenden
  root.querySelectorAll(".tlg").forEach(g => {
    const any = [...g.querySelectorAll("details.tls")].some(d => !d.hidden);
    if (g.hidden === any) g.hidden = !any;
  });
  tlNav();
  return true;
}

/* Abschnitts-Leiste: nur Sprung-Chips für Abschnitte, die es auf dieser Tour gibt */
function tlNav() {
  const nav = document.getElementById("tlnav");
  if (!nav) return;
  const list = TL_CHIPS.map(([k, label, ids]) => [k, label, ids.filter(i => tlVis(tlSec(i)))]).filter(c => c[2].length),
    sig = list.map(c => c[0] + ":" + c[2].join(".")).join("|");
  nav.hidden = list.length < 2;
  if (nav.dataset.sig !== sig) {
    nav.dataset.sig = sig;
    nav.innerHTML =
      `<div class="tlchips">${list.map(([k, label, ids]) => `<button type="button" class="tlchip" data-chip="${k}" data-secs="${ids.join(" ")}" aria-controls="${ids.map(i => "tls-" + i).join(" ")}">${label}</button>`).join("")}</div>` +
      `<button type="button" class="tlall" id="tlall"></button>`;
    delete nav.dataset.all;
  }
  tlAllLabel();
  const toh = document.querySelector("header.top");
  const root = document.documentElement.style;
  root.setProperty("--toph", (toh ? toh.offsetHeight : 56) + "px");
  root.setProperty("--tlnavh", (nav.hidden ? 0 : nav.offsetHeight) + "px");
}
const tlAll = () => [...document.querySelectorAll("#tl details.tls")].filter(tlVis);
function tlAllLabel() {
  const b = document.getElementById("tlall");
  if (!b) return;
  const all = tlAll().every(d => d.open) ? "1" : "0";
  if (b.dataset.all !== all) {
    b.dataset.all = all;
    b.textContent = all === "1" ? "Alles zuklappen" : "Alles aufklappen";
    b.setAttribute("aria-pressed", all);
  }
}
function tlSetAll(open) {
  document.querySelectorAll("#tl details.tls, #tl details.tls details[data-trf]").forEach(d => tlVis(d) && (d.open = open));
}
function tlJump(chip) {
  const ids = (chip.dataset.secs || "").split(" ").filter(Boolean),
    secs = ids.map(tlSec).filter(Boolean);
  if (!secs.length) return;
  secs.forEach(s => (s.open = true));
  const first = secs[0],
    target = chip.dataset.chip === "dev" ? document.getElementById("tlg-rec") : first;
  target.scrollIntoView({behavior: tlReduced() ? "auto" : "smooth", block: "start"});
  const sm = first.querySelector("summary");
  if (sm) sm.focus({preventScroll: true});
}
/* Zustand, Karte und Leiste nach jedem Auf-/Zuklappen (das Ereignis „toggle“ steigt nicht auf, daher in der Aufnahmephase) */
document.addEventListener(
  "toggle",
  e => {
    const d = e.target;
    if (!d || !d.matches || !d.matches("details[data-trf]")) return;
    try {
      localStorage.setItem("mt_trf_" + d.dataset.trf, d.open ? "1" : "0");
    } catch (x) {}
    const sm = d.querySelector(":scope > summary");
    if (sm && d.classList.contains("tls")) sm.setAttribute("aria-expanded", d.open ? "true" : "false");
    if (d.id === "tls-map" && d.open && window.map && map.invalidateSize) {
      map.invalidateSize();
      if (map._tlStale && map._tlFit) {
        map._tlStale = false;
        map._tlFit();
      }
    }
    tlAllLabel();
  },
  true
);
document.addEventListener("click", e => {
  const c = e.target.closest && e.target.closest("#tlnav .tlchip"),
    a = e.target.closest && e.target.closest("#tlall");
  if (c) tlJump(c);
  else if (a) tlSetAll(a.dataset.all !== "1");
});
window.addEventListener("resize", () => document.getElementById("tlnav") && tlNav());

/* Beobachter: Karten, die Module später einhängen, werden sofort (vor dem nächsten Zeichnen) einsortiert */
let tlMO = null;
function tlWatch() {
  const main = document.getElementById("main");
  if (!main || typeof MutationObserver !== "function") return;
  if (tlMO) tlMO.disconnect();
  tlMO = new MutationObserver(ms => {
    if (!tlRoot()) {
      tlMO.disconnect();
      return;
    }
    if (ms.some(m => !(m.target.closest && m.target.closest(".leaflet-container, svg")))) tlArrange();
  });
  tlMO.observe(main, {childList: true, subtree: true});
}
window.tlRefresh = () => {
  try {
    tlArrange();
  } catch (e) {}
};
const _tour48 = VIEWS.tour;
VIEWS.tour = async (...a) => {
  tlWatch();
  await _tour48(...a);
  tlRefresh();
};
