/* =====================  3.34.0 Zeitraum der Seite (gemeinsame Zeitraum-Leiste)  =====================
   Ein Zeitraum für alle zeitbezogenen Bausteine einer Seite. Das ist derselbe Mechanismus wie der globale Filter der Statistik (56-statistik.js: Adresse, Zustand {kind, yr, von, bis}, stApply, Layout-Feld „filter“),
   hier auf die Übersicht übertragen und um „Vorjahr“ erweitert (die Statistik bekam den Knopf „Vorjahr“ in ihrer Leiste). Kein zweites System: die Übersicht benutzt stFromDoc/stToDoc/stApply und die
   Ansichts-Sicherung SLF (54-ansichten.js).
   Zustand je Seite: ZR.F[Seite] = {kind: all | y | 12m | 90d | c, yr, von, bis, sports: []} oder null (= kein Zeitraum der Seite: jeder Baustein zeigt seinen eigenen, wie vor 3.34.0).
   Quelle in dieser Reihenfolge: Adresse (#/dash?z=2025 | z=12m | z=90d | z=all | z=c&von=…&bis=…; teilbar) · zuletzt gewählt (localStorage, je Benutzer und Ansicht) · in der Ansicht gespeichert (Layout-Feld „filter“,
   „Ansicht speichern“) · keiner.
   Baustein-Einstellung: „Zeitraum der Seite verwenden“ (Standard) oder eigener Zeitraum (Feld „eigen“ in der Konfiguration; auch bei der Eigenen Kennzahl, deren range/yr/from/to dann gelten).
   Bausteine ohne Zeitbezug (ohne Feld „Zeitraum“ und nicht „zeit“) bekommen weder eine Änderung noch einen Hinweis; die Leiste erscheint nur, wenn die Seite mindestens einen zeitbezogenen Baustein zeigt. */
const ZR = {F: {}, focus: "", open: {}, key: {}, url: {}, mopen: {}, sess: {}, help: {}};
const zrFams = ["uebersicht"];
/* 3.37.2: Die Leiste ist standardmäßig ausgeblendet („Seite anpassen“ → „Zeitraum der Seite anzeigen“, Layout-Feld zrbar). Sichtbar ist sie, wenn der Schalter an ist, wenn ein Zeitraum gilt (Adresse ?z=…, zuletzt gewählt, in der Ansicht gespeichert:
   ein wirksamer Seitenzeitraum darf nie unsichtbar sein) oder wenn in dieser Sitzung ein Zeitraum gewählt und wieder aufgehoben wurde (die Leiste verschwindet nicht unter dem Finger). „Je Baustein“ ohne Schalter: unsichtbar und ohne Wirkung. */
/* 3.37.2: Erklärung der Funktion, gleicher Text im Bearbeitungsmodus (beim Schalter), in der Leiste und im Handbuch */
const zrHelpHtml = () =>
  `<ul class="zrhl"><li>Ein Zeitraum für alle Bausteine der Seite, die mit Zeit zu tun haben, statt für jeden Baustein einzeln.</li>` +
  `<li>Ein Baustein behält seinen eigenen Zeitraum, wenn du in seinen Einstellungen „Zeitraum der Seite verwenden“ abschaltest.</li>` +
  `<li>Bausteine ohne Zeitbezug, zum Beispiel „Heute vor X Jahren“ und die Erinnerungen, sind nicht betroffen.</li>` +
  `<li>Deine Auswahl merkt sich die App; „Ansicht speichern“ legt sie in der Ansicht ab. Die Adresse mit ?z=… lässt sich teilen und blendet die Leiste ein.</li></ul>`;
/* Hilfstext in den Baustein-Einstellungen: welcher Zeitraum gerade gilt (Schalter „Zeitraum der Seite verwenden“ an oder aus) */
const zrNowText = own => {
  const F = ZR.F.uebersicht;
  return own ? "Dieser Baustein nutzt seinen eigenen Zeitraum" : F ? `Gerade gilt: ${zrShort(F)} von der Seite` : "Die Seite hat keinen Zeitraum gewählt, dieser Baustein zeigt seinen eigenen";
};
const zrSwitchOn = fam => !!((SL.docs[SL_PAGE_KEY[fam]] || {}).zrbar === true);
const zrOn = fam => zrSwitchOn(fam) || !!ZR.F[fam] || !!ZR.sess[fam];
const zrHashBase = fam => ({uebersicht: "#/dash"})[fam];
const zrLsKey = fam => "mt_zr_" + slUid() + "_" + fam + "_" + (SL.view[fam] || "");
const zrOpenKey = fam => "mt_trf_zr_" + fam;
const zrDocOf = F => (F ? JSON.stringify(stToDoc({...F, sports: []})) : "");
const zrSavedF = fam => {
  const d = (SL.docs[fam] || {}).filter;
  return d && typeof d === "object" ? stFromDoc({...d, sports: []}) : null;
};
const zrSame = (a, b) => zrDocOf(a) === zrDocOf(b);
function zrParse(q) {
  if (!q || !q.get || !q.has("z")) return null;                                   // „y“ gehört auf dieser Seite dem Ziel-Jahr (06-erweiterungen.js), deshalb z=2025
  const z = q.get("z") || "", von = q.get("von") || "", bis = q.get("bis") || "", y = /^\d{4}$/.test(z) ? +z : 0;
  if (y >= 1970 && y <= 2100) return {sports: [], kind: "y", yr: y, von: "", bis: ""};
  if (z === "12m" || z === "90d") return {sports: [], kind: z, yr: 0, von: "", bis: ""};
  if (z === "all") return {sports: [], kind: "all", yr: 0, von: "", bis: ""};
  if (z === "c" && ST_DATE.test(von) && ST_DATE.test(bis) && von <= bis) return {sports: [], kind: "c", yr: 0, von, bis};
  return null;
}
function zrStored(fam) {
  try {
    const v = localStorage.getItem(zrLsKey(fam));
    return v ? stFromDoc({...JSON.parse(v), sports: []}) : null;
  } catch (e) {
    return null;
  }
}
function zrStore(fam, F) {
  try {
    if (F && !zrSame(F, zrSavedF(fam))) localStorage.setItem(zrLsKey(fam), JSON.stringify(stToDoc({...F, sports: []})));
    else localStorage.removeItem(zrLsKey(fam));
  } catch (e) {}
}
/* Zustand beim Öffnen der Seite (q = Adresse) bzw. nach einem Ansichtswechsel (ohne q) */
function zrInit(fam, q) {
  window.ZR_READY = true;
  const u = zrParse(q);
  ZR.url[fam] = !!u;
  ZR.sess[fam] = false;
  ZR.key[fam] = zrLsKey(fam);
  ZR.F[fam] = u || zrStored(fam) || zrSavedF(fam) || null;
}
/* Kommt die Ansicht (und damit Schlüssel und gespeicherter Stand) erst nach dem Start der Seite fest, wird der Zeitraum neu bestimmt; eine Adresse gilt weiter */
function zrSync(fam) {
  if (ZR.key[fam] === undefined || ZR.key[fam] === zrLsKey(fam)) return;
  if (ZR.url[fam]) ZR.key[fam] = zrLsKey(fam);
  else zrInit(fam, null);
}
function zrHash(fam, F) {
  const base = zrHashBase(fam);
  if (!F) return base;
  if (F.kind === "y") return `${base}?z=${F.yr}`;
  if (F.kind === "c") return `${base}?z=c&von=${F.von}&bis=${F.bis}`;
  return `${base}?z=${F.kind}`;
}
function zrApplyAll(items) {
  zrSync("uebersicht");
  const F = ZR.F.uebersicht;
  if (!F) return;
  items.forEach(it => it.wtype && stApply(it, F, {page: true, explicit: true}));
}
const zrAware = it => {
  const T = it.wtype && window.SL_WT[it.wtype];
  return !!T && !T.hinweis && !!(T.zeit || (T.fields || []).some(f => f.kind === "range"));
};
const zrMob = () => document.documentElement.classList.contains("mob");
/* Kurzform für den Chip der Werkzeugzeile (Handy): „Zeitraum: 2025“ */
const zrShort = F => (!F ? "Je Baustein" : F.kind === "y" ? String(F.yr) : F.kind === "all" ? "Gesamte Zeit" : stRange(F).label);
const zrLabel = F => (!F ? "Jeder Baustein zeigt seinen eigenen Zeitraum" : F.kind === "y" ? `Das Jahr ${F.yr}` : F.kind === "all" ? "Alle Touren, gesamte Zeit" : stRange(F).label);
/* Zeitraum setzen (F = null: zurück auf den gespeicherten bzw. keinen) */
function zrSet(fam, F, focus) {
  if (zrMob() && ZR.mopen[fam]) {                                                   // Handy: die Auswahl klappt nach der Wahl wieder zu, der Fokus geht zurück auf den Chip
    ZR.mopen[fam] = false;
    focus = document.getElementById("zrchip") ? "#zrchip" : ".zrtog";
  }
  ZR.F[fam] = F;
  ZR.url[fam] = false;
  ZR.key[fam] = zrLsKey(fam);
  ZR.focus = focus || "";
  zrStore(fam, F);
  try {
    history.replaceState(null, "", zrHash(fam, F));                               // teilbare Adresse, ohne die Seite neu aufzubauen
  } catch (e) {}
  slApply();
  if (typeof slBarRefresh === "function") slBarRefresh();
  if (typeof slKopfSync === "function") slKopfSync();
  slLive(`Zeitraum der Seite: ${zrLabel(F)}`);
}
function zrReset(fam) {
  const saved = zrSavedF(fam);
  try {
    localStorage.removeItem(zrLsKey(fam));
  } catch (e) {}
  zrSet(fam, saved, "");
  try {
    history.replaceState(null, "", zrHashBase(fam));
  } catch (e) {}
}
SLF.uebersicht = {
  dirty: () => !zrSame(ZR.F.uebersicht || null, zrSavedF("uebersicht")),
  apply(doc) {
    const F = ZR.F.uebersicht;
    if (F) doc.filter = stToDoc({...F, sports: []});
    else delete doc.filter;
    try {
      localStorage.removeItem(zrLsKey("uebersicht"));
    } catch (e) {}
  },
  discard(id) {
    try {
      localStorage.removeItem(id ? "mt_zr_" + slUid() + "_uebersicht_" + id : zrLsKey("uebersicht"));
    } catch (e) {}
    if (!id) zrSet("uebersicht", zrSavedF("uebersicht"), "");
  },
};
/* ---------- Leiste ---------- */
/* chip = Handy-Werkzeugzeile: der Kopf (Chip) steht in der Zeile „Seite anpassen“ (zrChip), hier bleibt nur die aufklappbare Auswahl */
function zrHtml(fam, F, open, chip, help) {
  const cy = new Date().getFullYear(), ys = years(), on = {all: F && F.kind === "all", year: F && F.kind === "y" && F.yr === cy, "12m": F && F.kind === "12m", prev: F && F.kind === "y" && F.yr === cy - 1, c: F && F.kind === "c"},
    other = F && F.kind === "y" && F.yr !== cy && F.yr !== cy - 1 ? F.yr : 0, yl = [...new Set(ys.concat(other ? [other] : []))].sort((a, b) => b - a),
    chips = [["all", "Gesamte Zeit"], ["year", "Laufendes Jahr"], ["12m", "Letzte 12 Monate"], ["prev", "Vorjahr"]];
  return (chip ? "" : `<div class="zrhead"><button type="button" class="zrtog" aria-expanded="${open}" aria-controls="zrbody"><span class="zrt">Zeitraum der Seite</span><span class="zrl">${esc(zrLabel(F))}</span></button>` +
    `<button type="button" class="btn ghost sm zrreset" data-zr="reset"${F ? "" : " hidden"}>Zurücksetzen</button>` +
    `<button type="button" class="btn ghost sm zrinfo" data-zr="help" aria-expanded="${!!help}" aria-controls="zrhelp"><span aria-hidden="true">ⓘ</span> Hilfe</button></div>` + `<div class="zrhelp" id="zrhelp"${help ? "" : " hidden"}>${zrHelpHtml()}</div>`) +
    `<div class="zrbody" id="zrbody"${open ? "" : " hidden"}><div class="chips" role="group" aria-label="Zeitraum der Seite">${chips.map(([k, l]) => `<button type="button" class="chip${on[k] ? " on" : ""}" data-zr="${k}" aria-pressed="${!!on[k]}">${l}</button>`).join("")}` +
    `<label class="zrjahr"><span class="slsr">Bestimmtes Jahr</span><select id="zrjahr" data-zr="jahr"><option value="">Jahr …</option>${yl.map(y => `<option value="${y}"${other === y ? " selected" : ""}>${y}</option>`).join("")}</select></label>` +
    `<button type="button" class="chip${on.c ? " on" : ""}" data-zr="c" aria-pressed="${!!on.c}" aria-controls="zrvon">Von–bis …</button>` +
    (chip ? `<button type="button" class="chip zrreset" data-zr="reset"${F ? "" : " hidden"}>Zurücksetzen</button><button type="button" class="chip zrinfo" data-zr="help" aria-expanded="${!!help}" aria-controls="zrhelp"><span aria-hidden="true">ⓘ</span> Hilfe</button>` : "") + `</div>` +
    (chip ? `<div class="zrhelp" id="zrhelp"${help ? "" : " hidden"}>${zrHelpHtml()}</div>` : "") +
    `<form class="stfc zrform" id="zrvon"${F && F.kind === "c" ? "" : " hidden"} novalidate><label>Von <input type="date" name="von" value="${F ? F.von : ""}"></label><label>Bis <input type="date" name="bis" value="${F ? F.bis : ""}"></label><button class="btn sm" type="submit">Anzeigen</button><span class="stfe" role="alert"></span></form>` +
    `<p class="mut zrhint">Gilt für alle Bausteine mit Zeitbezug. Ein Baustein behält seinen eigenen Zeitraum, wenn du in seinen Einstellungen „Zeitraum der Seite verwenden“ abschaltest.</p></div>`;
}
const zrSig = (F, open, chip, help) => JSON.stringify([F && zrDocOf(F), open, years().join(","), new Date().getFullYear(), chip, !!help]);
/* Handy: der Chip „Zeitraum: 2025 ▾“ in der Werkzeugzeile (#slopenw); öffnet und schließt die Auswahl in #zrbar (aria-expanded, aria-controls) */
function zrChip(fam, F, open, w) {
  let c = document.getElementById("zrchip");
  if (!w) {
    if (c) c.remove();
    return;
  }
  if (!c) {
    c = document.createElement("button");
    c.type = "button";
    c.id = "zrchip";
    c.className = "btn ghost sm zrchip";
    c.setAttribute("aria-controls", "zrbody");
  }
  const sig = [fam, F ? zrDocOf(F) : "", open].join("|");
  if (c.dataset.sig !== sig) {
    c.dataset.sig = sig;
    c.dataset.fam = fam;
    c.classList.toggle("zron", !!F);
    c.setAttribute("aria-expanded", String(!!open));
    c.title = zrLabel(F);
    c.innerHTML = `<span class="zrcl">Zeitraum:</span> <b class="zrcv">${esc(zrShort(F))}</b><i class="zrcc" aria-hidden="true"></i>`;
  }
  const after = w.querySelector("#slviews");
  if (c.parentNode !== w || (after && c.previousElementSibling !== after)) (after ? after.after(c) : w.appendChild(c));
}
/* Auswahl auf- und zuklappen (Handy, ohne die Seite neu zu bauen) */
function zrMobOpen(fam, open, focus) {
  ZR.mopen[fam] = !!open;
  const bar = document.getElementById("zrbar"), body = document.getElementById("zrbody"), c = document.getElementById("zrchip");
  if (body) body.hidden = !open;
  if (c) {
    c.setAttribute("aria-expanded", String(!!open));
    c.dataset.sig = [fam, ZR.F[fam] ? zrDocOf(ZR.F[fam]) : "", !!open].join("|");
  }
  if (bar && bar.dataset.sig) bar.dataset.sig = zrSig(ZR.F[fam] || null, !!open, bar.classList.contains("zrm"), ZR.help[fam]);
  if (focus && c) c.focus({preventScroll: true});
}
document.addEventListener("click", e => {
  const c = e.target.closest && e.target.closest("#zrchip");
  if (c) zrMobOpen(c.dataset.fam, c.getAttribute("aria-expanded") !== "true");
});
document.addEventListener("keydown", e => {
  const c = document.getElementById("zrchip");
  if (e.key !== "Escape" || !c || c.getAttribute("aria-expanded") !== "true") return;
  const a = document.activeElement;
  if (a === c || (a && a.closest && a.closest("#zrbar"))) {
    e.preventDefault();
    zrMobOpen(c.dataset.fam, false, true);
  }
});
{
  let was = zrMob();                                                                // Wechsel zwischen Handy- und Computer-Darstellung: Leiste neu aufbauen
  new MutationObserver(() => {
    if (zrMob() === was) return;
    was = zrMob();
    const m = document.getElementById("main");
    if (document.getElementById("zrbar") && m && m.classList.contains("home") && typeof slApply === "function") {
      delete document.getElementById("zrbar").dataset.sig;
      slApply();
    }
  }).observe(document.documentElement, {attributes: true, attributeFilter: ["class"]});
}
/* Wird von der Engine bei jedem Einordnen gerufen; gibt die Leiste zurück (oder null, wenn die Seite keinen zeitbezogenen Baustein zeigt) */
function zrBar(fam, pres, root, edit, op) {
  let bar = document.getElementById("zrbar");
  if (!zrFams.includes(fam) || !zrOn(fam) || !pres.some(p => (edit || !p.off) && zrAware(p.it))) {
    if (bar) bar.remove();
    zrChip(fam, null, false, null);
    return null;
  }
  const F = ZR.F[fam] || null, ow = op || document.getElementById("slopenw"), mob = zrMob(), chip = mob && !edit && !!ow;       // Handy: Chip in der Werkzeugzeile statt eigener Leiste
  let open = true;
  if (mob) open = !!ZR.mopen[fam];                                                  // Handy: standardmäßig zu, nicht gemerkt
  else
    try {
      open = localStorage.getItem(zrOpenKey(fam)) !== "0";
    } catch (e) {}
  zrChip(fam, F, open, chip ? ow : null);
  const sig = zrSig(F, open, chip, ZR.help[fam]);
  if (!bar) {
    bar = document.createElement("section");
    bar.id = "zrbar";
    bar.className = "zrbar";
    bar.setAttribute("aria-label", "Zeitraum der Seite");
    bar.addEventListener("click", zrClick);
    bar.addEventListener("change", e => {
      const s = e.target.closest("#zrjahr");
      if (s) ZR.sess[bar.dataset.fam] = true;
      if (s) zrSet(bar.dataset.fam, s.value ? {sports: [], kind: "y", yr: +s.value, von: "", bis: ""} : null, "#zrjahr");
    });
    bar.addEventListener("submit", e => {
      e.preventDefault();
      const f = e.target, von = f.von.value, bis = f.bis.value, er = f.querySelector(".stfe");
      if (!ST_DATE.test(von) || !ST_DATE.test(bis)) return (er.textContent = "Bitte beide Daten angeben."), f.von.focus();
      if (von > bis) return (er.textContent = "„Von“ darf nicht nach „Bis“ liegen."), f.von.focus();
      ZR.sess[bar.dataset.fam] = true;
      zrSet(bar.dataset.fam, {sports: [], kind: "c", yr: 0, von, bis}, '[data-zr="c"]');
    });
  }
  bar.dataset.fam = fam;
  bar.classList.toggle("zrm", chip);
  if (bar.dataset.sig !== sig) {
    const had = bar.contains(document.activeElement) ? document.activeElement : null, foc = ZR.focus || (had && (had.id ? "#" + had.id : had.dataset && had.dataset.zr ? `[data-zr="${had.dataset.zr}"]` : ""));
    bar.dataset.sig = sig;
    bar.innerHTML = zrHtml(fam, F, open, chip, ZR.help[fam]);
    ZR.focus = "";
    if (foc) {
      const el = foc === "#zrchip" ? document.getElementById("zrchip") : bar.querySelector(foc);
      if (el && !el.hidden) el.focus({preventScroll: true});
    }
  }
  return bar;
}
function zrClick(e) {
  const bar = e.currentTarget, fam = bar.dataset.fam, tog = e.target.closest(".zrtog"), b = e.target.closest("button[data-zr]");
  if (tog) {
    const open = tog.getAttribute("aria-expanded") !== "true";
    if (zrMob()) ZR.mopen[fam] = open;                                              // Handy (Bearbeitungsmodus): nur für diese Sitzung
    else
      try {
        localStorage.setItem(zrOpenKey(fam), open ? "1" : "0");
      } catch (x) {}
    delete bar.dataset.sig;
    ZR.focus = ".zrtog";
    return slApply();
  }
  if (!b) return;
  const k = b.dataset.zr, cy = new Date().getFullYear(), mk = (kind, yr = 0) => ({sports: [], kind, yr, von: "", bis: ""});
  if (k === "help") {                                                               // Hilfe auf-/zuklappen (nur für diese Sitzung)
    ZR.help[fam] = !ZR.help[fam];
    delete bar.dataset.sig;
    ZR.focus = '[data-zr="help"]';
    return slApply();
  }
  ZR.sess[fam] = true;
  if (k === "reset") return zrReset(fam);
  if (k === "c") {
    const f = bar.querySelector("#zrvon"), cur = ZR.F[fam];
    f.hidden = cur && cur.kind === "c" ? false : !f.hidden;
    if (!f.hidden) {
      const i = f.querySelector('[name="von"]'), j = f.querySelector('[name="bis"]');
      if (!i.value) i.value = `${cy}-01-01`;
      if (!j.value) j.value = slIso(new Date());
      i.focus();
    }
    return;
  }
  const same = F => zrSame(ZR.F[fam], F), F = {all: mk("all"), year: mk("y", cy), "12m": mk("12m"), prev: mk("y", cy - 1)}[k];
  if (F) zrSet(fam, same(F) ? null : F, `[data-zr="${k}"]`);                      // zweiter Klick auf den gewählten Zeitraum hebt ihn auf
}
/* Wurde die Übersicht schon gezeichnet, bevor dieses Skript geladen war (boot() läuft früher), wird sie einmal neu gezeichnet */
slLate(/^#\/dash(\?.*)?$/, "ZR_READY", "#hlast");
