/* =====================  3.15.0 Neue Tourseite · 3.16.0 Tourseite schlanker, Auswertung als Unterseite  =====================
   Hauptseite #/tour/<id> (von oben): Überblick (Titel, Kennzahlen) · Streckenverlauf (Karte · Höhenprofil · Puls · Wegpunkte) · Einstieg „Detaillierte Auswertung“ · Fotos
   Unterseite #/tour/<id>/auswertung (VIEWS.tourauswertung in 03-tour.js): Abschnitts-Leiste · Gruppen
     Aufzeichnung   je Gerät ein Block (Messwerte · Training laut Uhr), danach Wetter
     Auswertung dieser Tour  Analyse · Tempo nach Steigung · Ähnliche Touren im Vergleich · Vergleich dieser Strecke
   Alle Abschnitte sind <details> mit gleichem Kopf (Symbol, Titel, Kurzaussage – auch zugeklappt sichtbar). Offen/zu merkt sich localStorage
   unter „mt_trf_<Schlüssel>“ (wie die einklappbaren Abschnitte seit 3.12.0). Die Module 36/38/43/45/46/47/08/26 legen ihre Karten mit tlCard() an und hängen sie
   an tlAnc(); tlArrange() sortiert sie – auch wenn sie erst später (nach dem Laden der Daten) erscheinen – an ihren Platz.
   Auf der Hauptseite werden die Detail-Karten (Messwerte, Training laut Uhr, Analyse, Tempo, Ähnliche, Vergleich, Wetter) nicht gezeigt: tlArrange() nimmt sie sofort wieder heraus
   und merkt sich nur ihre Kurzaussage (TL_SUM) für den Einstieg. Gehört eine Karte zu einem Gerät (tlDev), bekommt auf der Unterseite jedes verschiedene Gerät einen eigenen Block;
   ohne oder mit einem Gerät gibt es keine Zwischenüberschrift.
   3.17.0 „Seite anpassen“: Dieses Modul sammelt und fasst zusammen, die Anordnung (Reihenfolge, Ausblenden, Seite, Gruppen-Überschriften) übernimmt die Layout-Engine
   in 49-seitenlayout.js (slPlace). Ohne gespeichertes Layout ist alles wie in 3.16.x. */
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
    open = tlState(k, typeof slDef === "function" ? slDef(o.id, !!o.def) : !!o.def);      // 3.17.0: „Standardmäßig offen“ aus dem Layout, sonst der Standard des Abschnitts
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
  ["dev", "Gerät & Messwerte", ["met", "uhr"]],
  ["wx", "Wetter", ["wx"]],
  ["ana", "Analyse", ["ana", "steig"]],
  ["cmp", "Vergleich", ["aehn", "cmp"]],
];
/* Detail-Karten (Kennung → Abschnitt), die nur auf der Unterseite stehen */
const TL_DET = [["metcard", "met"], ["uhrcard", "uhr"], ["steigcard", "steig"], ["aehncard", "aehn"], ["anacard", "ana"], ["cmpseg", "cmp"]];
/* Reihenfolge der Kernaussagen im Einstieg (die ersten drei mit Aussage) */
const TL_SUMPRIO = ["uhr", "ana", "steig", "wx", "aehn", "cmp", "met"];
const TL_SUMORDER = ["met", "uhr", "wx", "ana", "steig", "aehn", "cmp"];
let TL_SUM = {};
/* Die Kennung „tl“ gibt es auch in anderen Ansichten (Tourenliste): nur unser Container zählt */
const tlRoot = () => {
  const r = document.getElementById("tl");
  return r && r.classList.contains("tlx") ? r : null;
};
const tlSec = id => document.getElementById("tls-" + id);
const tlVis = el => !!el && !el.closest("[hidden],.sl-off");      // .sl-off = vom Benutzer ausgeblendet (Seite anpassen)
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
  if (root.classList.contains("tlsub")) tlArrangeSub(root);
  else tlArrangeMain(root);
  if (typeof slPlace === "function") slPlace(root);          // Reihenfolge, Ausblenden, Gruppen-Überschriften (leere Gruppen entfallen) – 49-seitenlayout.js
  tlNav();
  return true;
}

/* Hauptseite: Strecke, Einstieg, Fotos; Detail-Karten werden herausgenommen und nur als Kurzaussage gemerkt */
function tlArrangeMain(root) {
  const t = BY[root.dataset.tid];
  // ---- Detail-Karten und Wetter: nicht hier, nur die Kurzaussage merken
  TL_DET.forEach(([id, sec]) => {
    const el = document.getElementById(id);
    if (!el || el.closest(".tlsub")) return;
    if (slOn(sec, "haupt")) return;                                 // vom Benutzer auf die Hauptseite gelegt: bleibt hier, die Engine ordnet sie ein
    const ti = el.querySelector(".tlt"),
      k = el.querySelector(".tlk");
    TL_SUM[sec] = {title: ti ? ti.textContent : "", badge: k ? k.innerHTML : ""};
    el.remove();
  });
  const wxs = tlSec("wx");
  if (wxs && !slOn("wx", "haupt")) {                                 // Wetter wurde auf die Unterseite verschoben: wieder herausnehmen, Kurzaussage merken
    const w0 = wxs.querySelector(".wx");
    if (w0) TL_SUM.wx = {title: "Wetter", badge: esc(w0.textContent.split(" · ").slice(0, 2).join(" · "))};
    wxs.remove();
  }
  const wx = document.querySelector("#main .figs + .wx, #main #tl .wx");
  if (wx && !wx.closest("#tls-wx")) {
    if (slOn("wx", "haupt")) {                                      // Wetter liegt auf der Hauptseite: als Abschnitt „Wetter“ zeigen
      const s = tlLazy("wx", {key: "tl_wx", icon: "cloud", title: "Wetter", def: false}, root);
      s.querySelector(".tlsb").appendChild(wx);
      tlSetBadge(s, esc(wx.textContent.split(" · ").slice(0, 2).join(" · ")));
    } else {
      TL_SUM.wx = {title: "Wetter", badge: esc(wx.textContent.split(" · ").slice(0, 2).join(" · "))};
      wx.remove();
    }
  }
  const dr = document.getElementById("devrow");
  if (dr) dr.remove();
  const pc = document.getElementById("profcard");
  if (tlSec("prof")) tlSec("prof").hidden = !pc || pc.style.display === "none";
  // ---- Einstieg in die Unterseite
  tlSumDraw(root, t);
  // Fotos (Bewertung, Notiz, Ausrüstung und Sicherheitsnotiz stehen wie in 3.14.0 oben im Kopf der Seite und werden hier nicht umgesetzt)
}

/* Einstieg „Detaillierte Auswertung ansehen ›“ mit zwei bis drei Kernaussagen – nur, wenn es überhaupt Auswertungsdaten gibt */
function tlSumDraw(root, t) {
  const g = document.getElementById("tlg-sum"),
    box = document.getElementById("tlgb-sum");
  if (!g || !box || !t) return;
  const on = k => slOn(k === "met" || k === "uhr" ? "geraet" : k, "auswertung") && !slHid(k === "met" || k === "uhr" ? "geraet" : k);      // nur, was auf der Unterseite liegt und nicht ausgeblendet ist
  const have = TL_SUMORDER.filter(k => TL_SUM[k] && on(k)),
    rows = TL_SUMPRIO.filter(k => TL_SUM[k] && on(k) && TL_SUM[k].badge.trim()).slice(0, 3),
    sig = have.join(".") + "|" + rows.map(k => k + TL_SUM[k].badge).join("|");
  if (g.hidden === !have.length && box.dataset.sig === sig) return;
  g.hidden = !have.length;
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  if (!have.length) {
    box.innerHTML = "";
    return;
  }
  if (!document.getElementById("tlsum"))                                     // Der Link bleibt stehen (kein Neuaufbau, wenn weitere Kurzaussagen eintreffen)
    box.innerHTML = `<div class="tlsum" id="tlsum"><ul class="tlsrows"></ul><p class="tlsin"></p><a class="btn tlsgo" id="tlsgo" href="#/tour/${esc(String(t.id))}/auswertung">Detaillierte Auswertung ansehen ›</a></div>`;
  const ul = box.querySelector(".tlsrows");
  ul.hidden = !rows.length;
  ul.innerHTML = rows.map(k => `<li>${tlIcon(TL_ICONOF[k])}<span class="tlsn">${esc(TL_SUM[k].title)}</span><span class="tlsv">${TL_SUM[k].badge}</span></li>`).join("");
  box.querySelector(".tlsin").innerHTML = `<span>Enthält:</span> ${have.map(k => esc(TL_SUM[k].title)).join(" · ")}`;
}
const TL_ICONOF = {met: "met", uhr: "watch", wx: "cloud", ana: "trend", steig: "trend", aehn: "cmp", cmp: "cmp"};

/* Unterseite: Aufzeichnung (Blöcke je Gerät, Wetter) und Auswertung */
function tlArrangeSub(root) {
  // ---- Aufzeichnung: Blöcke je Gerät
  const dr = document.getElementById("devrow");
  let host = document.getElementById("tlrec");
  if (!host) {
    root.insertAdjacentHTML("beforeend", '<div id="tlrec" class="tlrec"></div>');
    host = document.getElementById("tlrec");
  }
  // Karten, die der Benutzer auf die Hauptseite gelegt hat, gehören nicht hierher (die Module bauen sie auf beiden Seiten auf)
  TL_DET.forEach(([id, sec]) => {
    const el = document.getElementById(id);
    if (el && el.closest(".tlsub") && ["ana", "steig", "aehn", "cmp"].includes(sec) && !slOn(sec, "auswertung")) el.remove();
  });
  const cards = [["met", "metcard"], ["uhr", "uhrcard"]].map(([k, id]) => [k, document.getElementById(id)]).filter(x => x[1]),
    strong = [];
  cards.forEach(([, el]) => el.dataset.tlkey && !strong.includes(el.dataset.tlkey) && strong.push(el.dataset.tlkey));
  if (dr && strong.includes(dr.dataset.tlkey)) strong.splice(0, strong.length, dr.dataset.tlkey, ...strong.filter(x => x !== dr.dataset.tlkey));
  const keys = strong.length ? strong : cards.length ? [""] : [],
    multi = keys.length > 1;
  const lead = dr && cards.length && !(multi && keys.includes(dr.dataset.tlkey)) ? dr : null;       // Einzelgerät: die Zeile „Aufgezeichnet mit“ steht einmal oben
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
  tlPlace(host, [lead, ...blocks]);
  const wx = document.querySelector("#main .wx");
  if (wx && !slOn("wx", "auswertung")) {
    if (!wx.closest("#tls-wx")) wx.remove();
    if (tlSec("wx")) tlSec("wx").remove();
  } else if (wx) {
    const s = tlLazy("wx", {key: "tl_wx", icon: "cloud", title: "Wetter", def: false}, root);
    if (!s.querySelector(".tlsb .wx") || s.querySelector(".tlsb .wx") !== wx) s.querySelector(".tlsb").appendChild(wx);
    tlSetBadge(s, esc(wx.textContent.split(" · ").slice(0, 2).join(" · ")));
  }
}

/* Abschnitts-Leiste: nur Sprung-Chips für Abschnitte, die es auf dieser Tour gibt */
function tlNav() {
  const nav = document.getElementById("tlnav");
  if (!nav) {
    document.documentElement.style.setProperty("--tlnavh", "0px");
    return;
  }
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
  TL_SUM = {};
  tlWatch();
  await _tour48(...a);
  tlRefresh();
};
const _aus48 = VIEWS.tourauswertung;
VIEWS.tourauswertung = async (...a) => {
  tlWatch();
  await _aus48(...a);
  tlRefresh();
};
