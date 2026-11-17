/* =====================  3.34.0 Zeitraum der Seite (gemeinsame Zeitraum-Leiste)  =====================
   Ein Zeitraum für alle zeitbezogenen Bausteine einer Seite. Das ist derselbe Mechanismus wie der globale Filter der Statistik (56-statistik.js: Adresse, Zustand {kind, yr, von, bis}, stApply, Layout-Feld „filter“),
   hier auf die Übersicht übertragen und um „Vorjahr“ erweitert (die Statistik bekam den Knopf „Vorjahr“ in ihrer Leiste). Kein zweites System: die Übersicht benutzt stFromDoc/stToDoc/stApply und die
   Ansichts-Sicherung SLF (54-ansichten.js).
   Zustand je Seite: ZR.F[Seite] = {kind: all | y | 12m | 90d | c, yr, von, bis, sports: []} oder null (= kein Zeitraum der Seite: jeder Baustein zeigt seinen eigenen, wie vor 3.34.0).
   Quelle in dieser Reihenfolge: Adresse (#/dash?z=2025 | z=12m | z=90d | z=all | z=c&von=…&bis=…; teilbar) · zuletzt gewählt (localStorage, je Benutzer und Ansicht) · in der Ansicht gespeichert (Layout-Feld „filter“,
   „Ansicht speichern“) · keiner.
   Baustein-Einstellung: „Zeitraum der Seite verwenden“ (Standard) oder eigener Zeitraum (Feld „eigen“ in der Konfiguration; auch bei der Eigenen Kennzahl, deren range/yr/from/to dann gelten).
   Bausteine ohne Zeitbezug (ohne Feld „Zeitraum“ und nicht „zeit“) bekommen weder eine Änderung noch einen Hinweis; die Leiste erscheint nur, wenn die Seite mindestens einen zeitbezogenen Baustein zeigt. */
const ZR = {F: {}, focus: "", open: {}, key: {}, url: {}};
const zrFams = ["uebersicht"];
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
const zrLabel = F => (!F ? "Jeder Baustein zeigt seinen eigenen Zeitraum" : F.kind === "y" ? `Das Jahr ${F.yr}` : F.kind === "all" ? "Alle Touren, gesamte Zeit" : stRange(F).label);
/* Zeitraum setzen (F = null: zurück auf den gespeicherten bzw. keinen) */
function zrSet(fam, F, focus) {
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
function zrHtml(fam, F, open) {
  const cy = new Date().getFullYear(), ys = years(), on = {all: F && F.kind === "all", year: F && F.kind === "y" && F.yr === cy, "12m": F && F.kind === "12m", prev: F && F.kind === "y" && F.yr === cy - 1, c: F && F.kind === "c"},
    other = F && F.kind === "y" && F.yr !== cy && F.yr !== cy - 1 ? F.yr : 0, yl = [...new Set(ys.concat(other ? [other] : []))].sort((a, b) => b - a),
    chips = [["all", "Alle"], ["year", "Dieses Jahr"], ["12m", "Letzte 12 Monate"], ["prev", "Vorjahr"]];
  return `<div class="zrhead"><button type="button" class="zrtog" aria-expanded="${open}" aria-controls="zrbody"><span class="zrt">Zeitraum der Seite</span><span class="zrl">${esc(zrLabel(F))}</span></button>` +
    `<button type="button" class="btn ghost sm zrreset" data-zr="reset"${F ? "" : " hidden"}>Zurücksetzen</button></div>` +
    `<div class="zrbody" id="zrbody"${open ? "" : " hidden"}><div class="chips" role="group" aria-label="Zeitraum der Seite">${chips.map(([k, l]) => `<button type="button" class="chip${on[k] ? " on" : ""}" data-zr="${k}" aria-pressed="${!!on[k]}">${l}</button>`).join("")}` +
    `<label class="zrjahr"><span class="slsr">Bestimmtes Jahr</span><select id="zrjahr" data-zr="jahr"><option value="">Jahr …</option>${yl.map(y => `<option value="${y}"${other === y ? " selected" : ""}>${y}</option>`).join("")}</select></label>` +
    `<button type="button" class="chip${on.c ? " on" : ""}" data-zr="c" aria-pressed="${!!on.c}" aria-controls="zrvon">Von–bis …</button></div>` +
    `<form class="stfc zrform" id="zrvon"${F && F.kind === "c" ? "" : " hidden"} novalidate><label>Von <input type="date" name="von" value="${F ? F.von : ""}"></label><label>Bis <input type="date" name="bis" value="${F ? F.bis : ""}"></label><button class="btn sm" type="submit">Übernehmen</button><span class="stfe" role="alert"></span></form>` +
    `<p class="mut zrhint">Gilt für alle Bausteine mit Zeitbezug. Ein Baustein behält seinen eigenen Zeitraum, wenn du in seinen Einstellungen „Zeitraum der Seite verwenden“ abschaltest.</p></div>`;
}
/* Wird von der Engine bei jedem Einordnen gerufen; gibt die Leiste zurück (oder null, wenn die Seite keinen zeitbezogenen Baustein zeigt) */
function zrBar(fam, pres, root, edit) {
  let bar = document.getElementById("zrbar");
  if (!zrFams.includes(fam) || !pres.some(p => (edit || !p.off) && zrAware(p.it))) {
    if (bar) bar.remove();
    return null;
  }
  const F = ZR.F[fam] || null;
  let open = true;
  try {
    open = localStorage.getItem(zrOpenKey(fam)) !== "0";
  } catch (e) {}
  const sig = JSON.stringify([F && zrDocOf(F), open, years().join(","), new Date().getFullYear()]);
  if (!bar) {
    bar = document.createElement("section");
    bar.id = "zrbar";
    bar.className = "zrbar";
    bar.setAttribute("aria-label", "Zeitraum der Seite");
    bar.addEventListener("click", zrClick);
    bar.addEventListener("change", e => {
      const s = e.target.closest("#zrjahr");
      if (s) zrSet(bar.dataset.fam, s.value ? {sports: [], kind: "y", yr: +s.value, von: "", bis: ""} : null, "#zrjahr");
    });
    bar.addEventListener("submit", e => {
      e.preventDefault();
      const f = e.target, von = f.von.value, bis = f.bis.value, er = f.querySelector(".stfe");
      if (!ST_DATE.test(von) || !ST_DATE.test(bis)) return (er.textContent = "Bitte beide Daten angeben."), f.von.focus();
      if (von > bis) return (er.textContent = "„Von“ darf nicht nach „Bis“ liegen."), f.von.focus();
      zrSet(bar.dataset.fam, {sports: [], kind: "c", yr: 0, von, bis}, '[data-zr="c"]');
    });
  }
  bar.dataset.fam = fam;
  if (bar.dataset.sig !== sig) {
    const had = bar.contains(document.activeElement) ? document.activeElement : null, foc = ZR.focus || (had && (had.id ? "#" + had.id : had.dataset && had.dataset.zr ? `[data-zr="${had.dataset.zr}"]` : ""));
    bar.dataset.sig = sig;
    bar.innerHTML = zrHtml(fam, F, open);
    ZR.focus = "";
    if (foc) {
      const el = bar.querySelector(foc);
      if (el && !el.hidden) el.focus({preventScroll: true});
    }
  }
  return bar;
}
function zrClick(e) {
  const bar = e.currentTarget, fam = bar.dataset.fam, tog = e.target.closest(".zrtog"), b = e.target.closest("button[data-zr]");
  if (tog) {
    const open = tog.getAttribute("aria-expanded") !== "true";
    try {
      localStorage.setItem(zrOpenKey(fam), open ? "1" : "0");
    } catch (x) {}
    delete bar.dataset.sig;
    ZR.focus = ".zrtog";
    return slApply();
  }
  if (!b) return;
  const k = b.dataset.zr, cy = new Date().getFullYear(), mk = (kind, yr = 0) => ({sports: [], kind, yr, von: "", bis: ""});
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
