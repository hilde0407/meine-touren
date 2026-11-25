/* =====================  3.36.0 Gruppen und Handy-Anordnung (Seite anpassen)  =====================
   Gruppen: mehrere Abschnitte und Bausteine einer Seite bilden einen einklappbaren Abschnitt mit eigenem Titel. Im Layout-Dokument der Seite: groups [{id, title, ids, closed}]
   (Regeln und Grenzen: app/layout.py, _groups). Die Reihenfolge der Mitglieder ist die Reihenfolge der Seite (order); eine Gruppe steht an der Stelle ihres ersten sichtbaren Mitglieds.
   Zustand offen/zu: Standard je Ansicht im Dokument (closed), der aktuelle Zustand je Benutzer wird im Browser gemerkt (localStorage „mt_slg_<Benutzer>_<Gruppe>“). Im Bearbeitungsmodus sind alle Gruppen offen.
   Handy: das Dokument kann eine eigene Reihenfolge und Sichtbarkeit für schmale Bildschirme tragen (mob {order, hidden}); im Bearbeitungsmodus wählt der Umschalter „Desktop | Handy“,
   welche Anordnung geändert wird, und die Seite erscheint bei „Handy“ in einem schmalen Rahmen (CSS: body.sl-dev-mob). Die Auswahl der Anordnung selbst steht in 49-seitenlayout.js (slMobEff). */
const SL_GMAX = 10;                                                        // Gruppen je Seite (wie MAX_GROUPS im Server)
const SL_GMEM = 30;                                                        // Mitglieder je Gruppe
const SL_GTITLE = 60;

/* ---------- Daten ---------- */
const slGrpDoc = () => SL.docs[SL_PAGE_KEY[SL.page]];
const slGrpList = () => (SL.fam !== "karte" && slGrpDoc() && slGrpDoc().groups) || [];
const slGrpDefs = (fam, page) => {
  const d = fam === "karte" ? null : SL.docs[SL_PAGE_KEY[page]];
  return (d && Array.isArray(d.groups) ? d.groups : []).filter(g => g && Array.isArray(g.ids));
};
const slGrpOf = id => slGrpList().find(g => g.ids.includes(id)) || null;
const slGrpHas = (gid, id) => slGrpList().some(g => g.id === gid && g.ids.includes(id));
const slGrpName = g => g.title || `Bausteingruppe ${slGrpList().indexOf(g) + 1}`;
const slGrpOk = it => !!it && !it.must && !it.own && SL.fam !== "karte";
const slGrpCan = id => slGrpOk(slItems(SL.fam).find(i => i.id === id));
const slGrpNewId = () => {
  let id;
  do id = "grp" + Math.random().toString(36).slice(2, 7);
  while (slGrpList().some(g => g.id === id) || id.length < 5);
  return id;
};
const slGrpClear = d => {
  if (d.groups) {
    d.groups = d.groups.filter(g => g.ids.length);
    if (!d.groups.length) delete d.groups;
  }
};
/* Mitgliedschaft still ändern (der Aufrufer speichert und zeichnet): gid null = ohne Gruppe; Rückgabe: hat sich etwas geändert? */
function slGrpSet(id, gid) {
  const d = slGrpDoc();
  if (!d) return false;
  const was = (d.groups || []).find(g => g.ids.includes(id));
  if ((was ? was.id : null) === (gid || null)) return false;
  if (was) was.ids = was.ids.filter(x => x !== id);
  if (gid) {
    const g = (d.groups || []).find(x => x.id === gid);
    if (g && !g.ids.includes(id)) g.ids.push(id);
  }
  slGrpClear(d);
  return true;
}
/* Kopie eines Bausteins: gleiche Gruppe wie das Original (still) */
function slGrpLike(id, orig) {
  const g = slGrpOf(orig);
  if (g && g.ids.length < SL_GMEM && !g.ids.includes(id)) g.ids.push(id);
}
/* Baustein entfernt: aus allen Gruppen aller Dokumente der Seite nehmen (still) */
function slGrpDrop(id) {
  slKeys(SL.fam).forEach(k => {
    const d = SL.docs[k];
    if (!d || !d.groups) return;
    d.groups.forEach(g => (g.ids = g.ids.filter(x => x !== id)));
    slGrpClear(d);
  });
}
/* Mitglieder einer Gruppe zusammenziehen: Die Gruppe steht an der Stelle ihres ersten vorhandenen Mitglieds (stabil, wie slRegroup) */
function slGrpOrder(pres, defs) {
  if (!defs.length) return;
  const out = [], done = new Set();
  pres.forEach(p => {
    const g = defs.find(x => x.ids.includes(p.it.id));
    if (!g) return out.push(p);
    if (done.has(g)) return;
    done.add(g);
    out.push(...pres.filter(q => g.ids.includes(q.it.id)));
  });
  pres.splice(0, pres.length, ...out);
}

/* ---------- Zustand offen/zu ---------- */
const slGrpKey = gid => "mt_slg_" + slUid() + "_" + gid;
function slGrpState(g) {
  try {
    const v = localStorage.getItem(slGrpKey(g.id));
    if (v === "1" || v === "0") return v === "1";
  } catch (e) {}
  return !g.closed;
}
function slGrpSetOpen(d, on) {
  d.dataset.sy = on ? "1" : "0";
  if (d.open !== on) d.open = on;
}
document.addEventListener("toggle", e => {
  const d = e.target;
  if (!d || !d.classList || !d.classList.contains("slgd") || SL.edit) return;
  const v = d.open ? "1" : "0";
  if (d.dataset.sy === v) return;                                         // vom Programm gesetzt, nicht vom Benutzer
  d.dataset.sy = v;
  const g = d.closest(".slgrp");
  try {
    localStorage.setItem(slGrpKey(g.dataset.gid), v);
  } catch (x) {}
}, true);

/* ---------- Darstellung ---------- */
const slGrpCount = n => (n === 1 ? "1 Baustein" : `${n} Bausteine`);
function slGrpStrip(g, i, n) {
  const nm = esc(slGrpName(g));
  return `<span class="slgtag">Bausteingruppe</span><span class="slnm" title="${nm}">${nm}</span><span class="slbs">` +
    `<button type="button" class="slb" data-a="gname" aria-haspopup="dialog" aria-label="Bausteingruppe umbenennen: ${nm}">Umbenennen</button>` +
    `<label class="slsw"><input type="checkbox" data-a="gopen"${g.closed ? "" : " checked"}><span>Standardmäßig offen</span></label>` +
    `<button type="button" class="slb" data-a="gup" aria-label="Bausteingruppe nach oben: ${nm}" title="Bausteingruppe nach oben">↑</button>` +
    `<button type="button" class="slb" data-a="gdown" aria-label="Bausteingruppe nach unten: ${nm}" title="Bausteingruppe nach unten">↓</button>` +
    `<button type="button" class="slb slrm" data-a="gdel" aria-label="Bausteingruppe lösen: ${nm}" title="Die Bausteingruppe auflösen, die Bausteine bleiben auf der Seite">Bausteingruppe lösen</button></span>`;
}
/* Element einer Gruppe bauen bzw. aktualisieren; die Mitglieder (ps) werden hineingestellt */
function slGrpBlock(root, g, ps, edit) {
  let el = [...root.children].find(c => c.classList && c.classList.contains("slgrp") && c.dataset.gid === g.id);
  if (!el) {
    el = document.createElement("section");
    el.className = "slgrp slcell w-voll";
    el.dataset.gid = g.id;
    el.dataset.cw = "voll";
    el.innerHTML = `<details class="slgd"><summary class="slgs"><span class="slgt"></span><span class="slgc mut"></span></summary><div class="slgb"></div></details>`;
  }
  const det = el.querySelector(":scope > details"), body = det.querySelector(":scope > .slgb"), tid = "slgt-" + g.id,
    shown = ps.filter(p => edit || !p.off).length;
  el.setAttribute("aria-labelledby", tid);
  const t = det.querySelector(".slgt");
  t.id = tid;
  if (t.textContent !== slGrpName(g)) t.textContent = slGrpName(g);
  const c = slGrpCount(shown);
  if (det.querySelector(".slgc").textContent !== c) det.querySelector(".slgc").textContent = c;
  slPlaceIn(body, ps.map(p => p.unit));
  el.hidden = !shown;
  slGrpSetOpen(det, edit ? true : slGrpState(g));
  det.classList.toggle("slgd-edit", !!edit);
  let st = el.querySelector(":scope > .slgst");
  if (!edit) {
    if (st) st.remove();
  } else {
    const all = slGrpList(), i = all.indexOf(g), sig = [slGrpName(g), g.closed ? 1 : 0, i, all.length].join("|");
    if (!st) {
      st = document.createElement("div");
      st.className = "slgst";
      st.setAttribute("role", "group");
      el.insertBefore(st, el.firstChild);
    }
    if (st.dataset.sig !== sig) {
      st.dataset.sig = sig;
      st.setAttribute("aria-label", `Bausteingruppe: ${slGrpName(g)}`);
      st.innerHTML = slGrpStrip(g, i, all.length);
    }
  }
  return el;
}
/* Gruppen, die nicht mehr gebraucht werden, entfernen; Reste (nicht eingeordnete Elemente) bleiben auf der Seite */
function slGrpClean(root, used) {
  root.querySelectorAll(":scope > .slgrp").forEach(g => {
    if (used.has(g)) return;
    g.querySelectorAll(":scope .slgb > *").forEach(x => root.appendChild(x));
    g.remove();
  });
}

/* ---------- Bedienung ---------- */
function slGrpFinish(gid, a, text) {
  SL.focus = gid ? {gid, a} : null;
  slApply();
  slLive(text);
}
/* In eine Gruppe (gid), in eine neue Gruppe („new“) oder aus der Gruppe (null): Reihenfolge so, dass der Baustein hinter den anderen Mitgliedern steht */
function slGrpAssign(id, gid) {
  if (!slGrpCan(id)) return;
  const d = slDocOf(SL.page);
  let target = gid, msg;
  if (gid === "new") {
    if ((d.groups || []).length >= SL_GMAX) return uiAlert(`Es sind höchstens ${SL_GMAX} Bausteingruppen je Seite möglich.`);
    slGrpSet(id, null);
    target = slGrpNewId();
    (d.groups = d.groups || []).push({id: target, title: "", ids: [id]});
    msg = `${slTitle(id)}: neue Bausteingruppe angelegt`;
  } else if (gid) {
    const g = (d.groups || []).find(x => x.id === gid);
    if (!g) return;
    if (g.ids.length >= SL_GMEM && !g.ids.includes(id)) return uiAlert(`Eine Bausteingruppe kann höchstens ${SL_GMEM} Bausteine enthalten.`);
    slGrpSet(id, gid);
    const ord = slOrder(SL.fam, SL.page).map(i => i.id).filter(x => x !== id), last = ord.map((x, i) => (g.ids.includes(x) ? i : -1)).filter(i => i >= 0).pop();
    ord.splice(last === undefined ? ord.length : last + 1, 0, id);
    const cur = slDocOf(SL.page);
    if (slMobEff()) (cur.mob = cur.mob || {}).order = ord;
    else cur.order = ord;
    msg = `${slTitle(id)}: jetzt in der Bausteingruppe „${slGrpName(g)}“`;
  } else {
    if (!slGrpSet(id, null)) return;
    msg = `${slTitle(id)}: aus der Bausteingruppe gelöst`;
  }
  slTouch(SL_PAGE_KEY[SL.page]);
  SL.focus = {id, a: "grip"};
  slApply();
  slLive(msg);
}
function slGrpUngroup(id) {
  const g = slGrpOf(id);
  if (!g) return;
  slGrpAssign(id, null);
}
function slGrpDialog(id) {
  if (!slGrpCan(id)) return;
  const cur = slGrpOf(id), list = slGrpList();
  slModal("Bausteingruppe wählen", (body, close) => {
    body.innerHTML = `<p class="mut slcatin">Eine Bausteingruppe bündelt mehrere Bausteine unter einer einklappbaren Überschrift. „${esc(slTitle(id))}“ soll:</p><ul class="slgl">` +
      list.map(g => `<li><button type="button" class="btn ghost sm" data-g="${esc(g.id)}"${cur === g ? ' aria-current="true" disabled' : ""}>In Bausteingruppe „${esc(slGrpName(g))}“${cur === g ? " (aktuell)" : ""}</button></li>`).join("") +
      `<li><button type="button" class="btn sm" data-g="new"${list.length >= SL_GMAX ? " disabled" : ""}>In eine neue Bausteingruppe</button></li>` +
      (cur ? `<li><button type="button" class="btn ghost sm" data-g="">Aus Bausteingruppe lösen</button></li>` : "") +
      `</ul>` + (list.length >= SL_GMAX ? `<p class="mut">Es sind höchstens ${SL_GMAX} Bausteingruppen je Seite möglich.</p>` : "") +
      `<div class="uifoot"><button type="button" class="btn ghost" data-close>Abbrechen</button></div>`;
    body.onclick = e => {
      if (e.target.closest("[data-close]")) return close();
      const b = e.target.closest("[data-g]");
      if (!b || b.disabled) return;
      close();
      slGrpAssign(id, b.dataset.g || null);
    };
  });
}
function slGrpRename(gid) {
  const g = slGrpList().find(x => x.id === gid);
  if (!g) return;
  slModal("Bausteingruppe umbenennen", (body, close) => {
    body.innerHTML = `<form class="slform" novalidate><div class="slfs"><label for="slgname">Titel der Bausteingruppe</label><input id="slgname" type="text" maxlength="${SL_GTITLE}" autocomplete="off" value="${esc(g.title || "")}" placeholder="Bausteingruppe" aria-describedby="slgerr"><p class="slerr" id="slgerr" role="alert"></p></div>` +
      `<div class="uifoot"><button type="button" class="btn ghost" data-close>Abbrechen</button><button type="submit" class="btn">Speichern</button></div></form>`;
    const f = body.querySelector("form"), inp = f.querySelector("input");
    inp.select();
    f.onsubmit = e => {
      e.preventDefault();
      const t = inp.value.replace(/\s+/g, " ").trim();
      if (/[<>]/.test(t)) {
        f.querySelector("#slgerr").textContent = "Spitze Klammern sind im Titel nicht erlaubt.";
        return inp.focus();
      }
      close();
      g.title = t.slice(0, SL_GTITLE);
      slTouch(SL_PAGE_KEY[SL.page]);
      slGrpFinish(gid, "gname", `Bausteingruppe umbenannt in „${slGrpName(g)}“`);
    };
    f.onclick = e => e.target.closest("[data-close]") && close();
  });
}
function slGrpMove(gid, d) {
  const g = slGrpList().find(x => x.id === gid);
  if (!g) return;
  const ord = SL.present.slice(), blocks = [];
  ord.forEach(id => {
    const o = slGrpOf(id);
    if (o && blocks.length && blocks[blocks.length - 1].g === o) blocks[blocks.length - 1].ids.push(id);
    else blocks.push({g: o, ids: [id]});
  });
  const i = blocks.findIndex(b => b.g === g), j = i + d;
  if (i < 0 || j < 0 || j >= blocks.length) return slGrpFinish(gid, d < 0 ? "gup" : "gdown", `${slGrpName(g)}: ${d < 0 ? "ganz oben" : "ganz unten"}`);
  const mine = blocks[i].ids, nb = blocks[j],
    full = slOrder(SL.fam, SL.page).map(x => x.id).filter(x => !mine.includes(x));
  const at = d < 0 ? full.indexOf(nb.ids[0]) : full.indexOf(nb.ids[nb.ids.length - 1]) + 1;
  full.splice(at, 0, ...mine);
  slSaveOrder(full);
  slGrpFinish(gid, d < 0 ? "gup" : "gdown", `${slGrpName(g)}: Position ${j + 1} von ${blocks.length}`);
}
function slGrpAction(b) {
  if (b.tagName === "INPUT") return;
  const gid = b.closest(".slgrp").dataset.gid, a = b.dataset.a, g = slGrpList().find(x => x.id === gid);
  if (!g) return;
  if (b.getAttribute("aria-disabled") === "true") return slLive(`${slGrpName(g)}: ${a === "gup" ? "ganz oben" : "ganz unten"}`);
  if (a === "gname") slGrpRename(gid);
  else if (a === "gup") slGrpMove(gid, -1);
  else if (a === "gdown") slGrpMove(gid, 1);
  else if (a === "gdel") {
    const nm = slGrpName(g), d = slGrpDoc();
    d.groups = d.groups.filter(x => x !== g);
    slGrpClear(d);
    slTouch(SL_PAGE_KEY[SL.page]);
    SL.focus = {id: SL.present[0] || "", a: "grip", ps: true};
    slApply();
    slLive(`Bausteingruppe „${nm}“ gelöst, die Bausteine bleiben auf der Seite`);
  }
}
document.addEventListener("change", e => {
  const c = e.target.closest && e.target.closest(".slgst input[data-a=gopen]");
  if (!c) return;
  const gid = c.closest(".slgrp").dataset.gid, g = slGrpList().find(x => x.id === gid);
  if (!g) return;
  if (c.checked) delete g.closed;
  else g.closed = true;
  try {
    localStorage.removeItem(slGrpKey(g.id));                               // sonst überstimmt der zuletzt gemerkte Zustand den neuen Standard
  } catch (x) {}
  slTouch(SL_PAGE_KEY[SL.page]);
  SL.focus = {gid, a: "gopen"};
  slApply();
  slLive(`${slGrpName(g)}: ${c.checked ? "standardmäßig offen" : "standardmäßig zu"}`);
});

/* ---------- Handy: Umschalter und Vorschau ---------- */
const slDevHtml = () =>
  `<span class="slbdv" id="slbdv" role="group" aria-label="Anordnung für"><span class="slbdl">Anordnung für</span>` +
  `<button type="button" class="slb slbdb" data-a="dev" data-d="desk" aria-pressed="true">Computer</button><button type="button" class="slb slbdb" data-a="dev" data-d="mob" aria-pressed="false">Handy</button></span>` +
  `<button type="button" class="slb" data-a="mobreset" hidden>Handy-Anordnung: Standard wiederherstellen</button>` +
  `<span class="slsr" id="slmobinfo" role="status" aria-live="polite"></span><p class="mut slbn" id="slbn" hidden></p>`;
const slHasMob = () => slKeys(SL.fam).some(k => SL.docs[k] && SL.docs[k].mob && Object.keys(SL.docs[k].mob).length);
function slDevSync() {
  const w = document.getElementById("slbdv");
  if (!w) return;
  const none = SL.fam === "karte";
  w.hidden = none;
  w.querySelectorAll("[data-d]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.d === SL.dev)));
  const r = document.querySelector('#slbar [data-a="mobreset"]'), n = document.getElementById("slbn");
  if (r) r.hidden = none || SL.dev !== "mob" || !slHasMob();
  if (n) {
    n.hidden = none || SL.dev !== "mob";
    n.textContent = slHasMob() ? "Handy: eigene Anordnung. Änderungen gelten nur für schmale Bildschirme." : "Handy: noch keine eigene Anordnung, es gilt die Computer-Reihenfolge. Die erste Änderung hier legt eine Handy-Anordnung an.";
  }
}
function slSetDev(d) {
  if (!SL.edit || SL.fam === "karte" || (d !== "desk" && d !== "mob") || SL.dev === d) return;
  SL.dev = d;
  document.body.classList.toggle("sl-dev-mob", d === "mob");
  SL.focus = null;
  slApply();
  slBarSync();
  slLive(d === "mob" ? "Handy-Darstellung: Reihenfolge und Sichtbarkeit gelten nur für schmale Bildschirme" : "Computer-Darstellung");
}
function slMobReset() {
  if (!slHasMob()) return;
  slKeys(SL.fam).forEach(k => SL.docs[k] && delete SL.docs[k].mob);
  slTouch(...slKeys(SL.fam));
  slApply();
  slLive("Handy-Anordnung: Standard wiederhergestellt, es gilt wieder die Computer-Reihenfolge");
}
/* Wechselt der Bildschirm zwischen Desktop und Handy (Fenstergröße, Einstellung „Ansicht“), wird die Seite neu eingeordnet */
if (typeof MutationObserver === "function") {
  let was = slMobNow();
  new MutationObserver(() => {
    const now = slMobNow();
    if (now === was) return;
    was = now;
    if (!SL.edit && SL.root && SL.root.isConnected && !SL.drag) slApply();
  }).observe(document.documentElement, {attributes: true, attributeFilter: ["class"]});
}
