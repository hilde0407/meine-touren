/* =====================  3.21.0 Ansichten: mehrere benannte Layouts je Seite  =====================
   Daten und Auswahl-Logik stehen in 49-seitenlayout.js (Behälter SL.store, slResolve, slPack); hier: Auswahl in der Kopfzeile, Verwaltung (Dialog), Vorlagen, Export und Import.
   Tourseite: Hauptseite und Auswertung sind zwei Schlüssel; jede Änderung an den Ansichten (anlegen, umbenennen, löschen, Standard, Regeln) wird in beiden geführt
   (slAlign), der Inhalt bleibt je Schlüssel eigen. Die Vorgabe der Anzeige: von Hand gewählt (diese Sitzung) vor Regel „Sportart → Ansicht“ (beim Öffnen einer Tour) vor Standardansicht. */
const SL_APPV = "3.64.0";
const SL_EXPORT_FORMAT = "meine-touren-ansicht";
const SL_MAXFILE = 200000;
const slVm = fam => slMaster(fam).views;
const slUniq = (fam, base, except) => {
  const names = slVm(fam).filter(v => v.id !== except).map(v => v.name.toLowerCase());
  base = (base || "Ansicht").replace(/\s+/g, " ").trim().slice(0, 40) || "Ansicht";
  let n = base, i = 1;
  while (names.includes(n.toLowerCase())) {
    i++;
    const suf = " " + i;
    n = base.slice(0, 40 - suf.length) + suf;
  }
  return n;
};
const slNewViewId = fam => {
  let id;
  do id = "v" + Math.random().toString(36).slice(2, 7);
  while (slVm(fam).some(v => v.id === id));
  return id;
};

/* ---------- Ändern (immer in beiden Dokumenten der Tourseite) ---------- */
function slViewsChange(fam, fn) {
  slKeys(fam).forEach(slSync);                                         // Bearbeitungen der angezeigten Ansicht zuerst in den Behälter
  const was = SL.view[fam], out = fn(slKeys(fam).map(slStore));
  slAlign(fam);
  slResolve(fam);
  slTouch(...slKeys(fam));
  slApply();
  if (SL.edit) slHistReset();                                          // 3.36.0: der Verlauf (Rückgängig) gilt nur für die angezeigte Ansicht
  if (fam === "statistik" && SL.view[fam] !== was && typeof stReload === "function") stReload(SL.edit);      // andere Ansicht = anderer gespeicherter Filter
  return out;
}
function slViewAdd(fam, name, layouts) {
  const id = slNewViewId(fam);
  slViewsChange(fam, stores => stores.forEach((st, i) => st.views.push({id, name, layout: slTplCopy(layouts[slKeys(fam)[i]] || {v: 1})})));
  return id;
}
const slViewRename = (fam, id, name) => slViewsChange(fam, stores => stores.forEach(st => (st.views.find(v => v.id === id).name = name)));
const slViewDefault = (fam, id) => slViewsChange(fam, stores => stores.forEach(st => (st.active = id)));
const slViewReplace = (fam, id, layouts) => slViewsChange(fam, stores => stores.forEach((st, i) => (st.views.find(v => v.id === id).layout = slTplCopy(layouts[slKeys(fam)[i]] || {v: 1}))));
function slViewRemove(fam, id) {
  if (slMaster(fam).views.length < 2) return;
  if (SL.manual[fam] === id) slSetManual(fam, "");
  slViewsChange(fam, stores => stores.forEach(st => {
    st.views = st.views.filter(v => v.id !== id);
    Object.keys(st.rules || {}).forEach(k => st.rules[k] === id && delete st.rules[k]);
    if (st.active === id) st.active = st.views[0].id;
  }));
}
function slViewRule(fam, sport, id) {
  slViewsChange(fam, stores => stores.forEach(st => {
    st.rules = st.rules || {};
    if (id) st.rules[sport] = id;
    else delete st.rules[sport];
  }));
}
const slLayoutsOf = (fam, id) => {
  slKeys(fam).forEach(slSync);
  const o = {};
  slKeys(fam).forEach(k => (o[k] = slTplCopy((slStore(k).views.find(v => v.id === id) || {}).layout || {v: 1})));
  return o;
};

/* ---------- Auswahl in der Kopfzeile ---------- */
function slApplyOpen(fam) {                                           // „Standardmäßig offen“ der gewählten Ansicht gilt auch für schon gebaute Abschnitte
  if (fam !== "tour" && fam !== "reise" && fam !== "serie" && fam !== "reisen") return;          // 3.33.0: auch die Karten der Reisen-Seiten (Zustand „mt_trf_…“)
  slItems(fam).forEach(it => {
    if (it.widget) return;
    (it.ckeys || []).forEach(k => {
      try {
        localStorage.removeItem("mt_trf_" + k);
      } catch (e) {}
    });
    (it.id === "geraet" ? ["met", "uhr"] : [it.id]).forEach(s => {
      const d = tlSec(s);
      if (d && d.tagName === "DETAILS") d.open = slDef(it.id, !!it.def);
    });
  });
}
function slSwitch(fam, id) {
  slSetManual(fam, id);
  slKeys(fam).forEach(slSync);
  const was = SL.view[fam];
  slResolve(fam);
  if (SL.edit) slHistReset();
  if (SL.view[fam] === was && id) return slViewPick(document.getElementById("slopenw"));
  SL.focus = null;
  if (fam === "statistik" && typeof stReload === "function") return stReload(SL.edit);          // der Filter gehört zur Ansicht: Seite neu aufbauen
  slApplyOpen(fam);
  slApply();
  slLive(`Ansicht „${slViewName(fam, SL.view[fam])}“`);
}
function slViewPick(w) {
  if (!w) return false;
  const fam = SL.fam, m = slMaster(fam), n = m.views.length, cur = SL.view[fam] || m.active,
    bn = document.getElementById("slvn");
  if (bn) bn.textContent = n > 1 ? `Ansicht: ${slViewName(fam, cur)}` : "";
  let box = w.querySelector(".slvw");
  if (n < 2) {
    if (box) box.remove();
    return false;
  }
  const auto = fam === "tour" && Object.keys(m.rules || {}).length > 0, man = slManual(fam) && m.views.some(v => v.id === slManual(fam)) ? slManual(fam) : "",
    sig = [auto ? "a:" + slViewName(fam, cur) : "", ...m.views.map(v => v.id + "=" + v.name)].join("|");
  if (!box) {
    box = document.createElement("label");
    box.className = "slvw";
    box.innerHTML = `<span class="slvl">Ansicht</span><select id="slview" class="slvs"></select>`;
    w.insertBefore(box, w.firstChild);
  }
  const sel = box.querySelector("select");
  if (box.dataset.sig !== sig) {
    box.dataset.sig = sig;
    sel.innerHTML = (auto ? `<option value=""></option>` : "") + m.views.map(v => `<option value="${esc(v.id)}"></option>`).join("");
    [...sel.options].forEach(o => (o.textContent = o.value ? slViewName(fam, o.value) : `Automatisch (${slViewName(fam, cur)})`));
  }
  sel.value = auto && !man ? "" : man || cur;
  return true;
}
document.addEventListener("change", e => {
  if (e.target && e.target.id === "slview") slSwitch(SL.fam, e.target.value);
  const r = e.target && e.target.closest && e.target.closest("select[data-rule]");
  if (r) slViewRule(SL.fam, r.dataset.rule, r.value);
});

/* ---------- 3.37.1 Handy: Ansichten als Menü statt dauerhaft sichtbarer Auswahl ----------
   Auf dem Handy (html.mob) steht in der Werkzeugzeile nur der Knopf „Ansichten“. Er öffnet ein Menü: Ansicht wählen (wie die Auswahlliste #slview, die dort ausgeblendet bleibt), „Ansicht speichern …“
   (solange der Filter vom gespeicherten Stand abweicht; ein Punkt am Knopf zeigt das an) und „Ansichten verwalten …“ (der Dialog). Das Menü liegt fest am Bildschirm (nichts wird abgeschnitten, auch nicht auf der Karte). */
const slvMenuOn = () => document.documentElement.classList.contains("mob") && !SL.edit;
const slvMenuEl = () => document.getElementById("slvmenu");
function slvMenuClose(focus) {
  const m = slvMenuEl(), b = document.getElementById("slviews");
  if (m) m.remove();
  if (b) b.setAttribute("aria-expanded", "false");
  document.removeEventListener("pointerdown", slvOutside, true);
  document.removeEventListener("keydown", slvKey, true);
  window.removeEventListener("resize", slvMenuClose);
  window.removeEventListener("hashchange", slvMenuClose);
  if (focus && b) b.focus({preventScroll: true});
}
const slvOutside = e => {
  const m = slvMenuEl();
  if (m && !m.contains(e.target) && !e.target.closest("#slviews")) slvMenuClose(false);
};
function slvKey(e) {
  const m = slvMenuEl();
  if (!m) return;
  if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    return slvMenuClose(true);
  }
  if (e.key === "Tab") return slvMenuClose(false);
  const it = [...m.querySelectorAll("button")], i = it.indexOf(document.activeElement), k = {ArrowDown: 1, ArrowUp: -1}[e.key];
  if (k) {
    e.preventDefault();
    it[(i + k + it.length) % it.length].focus();
  } else if (e.key === "Home" || e.key === "End") {
    e.preventDefault();
    it[e.key === "Home" ? 0 : it.length - 1].focus();
  }
}
function slvMenuToggle(btn) {
  if (slvMenuEl()) return slvMenuClose(true);
  const fam = SL.fam, h = SLF[fam], dirty = !!(h && h.dirty && h.dirty()), sel = document.getElementById("slview"), m = document.createElement("div");
  m.id = "slvmenu";
  m.className = "slvmenu";
  m.setAttribute("role", "menu");
  m.setAttribute("aria-label", "Ansichten");
  const item = (cls, role, txt, attrs) => `<button type="button" class="${cls}" role="${role}"${attrs || ""}>${esc(txt)}</button>`;
  let html = "";
  if (sel && sel.options.length) {
    html += `<div class="slvmh" role="presentation">Ansicht wählen</div>` + [...sel.options].map(o => item("slvmi", "menuitemradio", o.textContent, ` data-v="${esc(o.value)}" aria-checked="${o.value === sel.value}"`)).join("");
    html += `<div class="slvms" role="separator"></div>`;
  }
  if (dirty) html += item("slvmi", "menuitem", "Ansicht speichern …", ' data-m="save"');
  html += item("slvmi", "menuitem", "Ansichten verwalten …", ' data-m="manage"');
  m.innerHTML = html;
  m.addEventListener("click", e => {
    const b = e.target.closest("button");
    if (!b) return;
    slvMenuClose(true);
    if (b.dataset.m === "save") slSaveMenu();
    else if (b.dataset.m === "manage") slViewsDialog();
    else if (b.dataset.v !== undefined && b.getAttribute("aria-checked") !== "true") slSwitch(SL.fam, b.dataset.v);
  });
  document.body.appendChild(m);
  const r = btn.getBoundingClientRect();
  m.style.setProperty("--slvt", Math.round(r.bottom + 6) + "px");
  btn.setAttribute("aria-expanded", "true");
  btn.setAttribute("aria-controls", "slvmenu");
  document.addEventListener("pointerdown", slvOutside, true);
  document.addEventListener("keydown", slvKey, true);
  window.addEventListener("resize", slvMenuClose);
  window.addEventListener("hashchange", slvMenuClose);
  (m.querySelector('[aria-checked="true"]') || m.querySelector("button")).focus({preventScroll: true});
}
/* Zustand des Knopfs „Ansichten“: Menü (Handy) oder Dialog */
function slvBtnSync(w) {
  const b = (w || document).querySelector("#slviews");
  if (!b) return;
  const menu = document.documentElement.classList.contains("mob");
  b.setAttribute("aria-haspopup", menu ? "menu" : "dialog");
  if (!menu) {
    b.removeAttribute("aria-expanded");
    b.removeAttribute("aria-controls");
  } else if (!b.hasAttribute("aria-expanded")) b.setAttribute("aria-expanded", "false");
}

/* ---------- Dialoge ---------- */
/* Kleiner Dialog mit einem Namensfeld (Neu, Umbenennen); opt = {title, value, ok, except, extra (HTML), hint}; Ergebnis {name, form} oder null */
function slAskName(fam, opt) {
  return new Promise(res => {
    let done = false;
    const fin = (v, close) => {
      if (done) return;
      done = true;
      close();
      res(v);
    };
    slModal(opt.title, (body, close) => {
      body.innerHTML = `<form class="slform" novalidate><div class="slfs"><label for="slvname">Name der Ansicht</label><input id="slvname" type="text" maxlength="40" autocomplete="off" value="${esc(opt.value || "")}" aria-describedby="slverr"><p class="slerr" id="slverr" role="alert"></p></div>${opt.extra || ""}` +
        `<div class="uifoot"><button type="button" class="btn ghost" data-close>Abbrechen</button><button type="submit" class="btn">${esc(opt.ok || "Speichern")}</button></div></form>`;
      const form = body.querySelector("form"), inp = form.querySelector("#slvname"), err = form.querySelector("#slverr");
      inp.select();
      form.onsubmit = e => {
        e.preventDefault();
        const name = inp.value.replace(/\s+/g, " ").trim();
        if (!name) {
          err.textContent = "Bitte einen Namen eingeben.";
          return inp.focus();
        }
        if (/[<>]/.test(name)) {
          err.textContent = "Spitze Klammern sind im Namen nicht erlaubt.";
          return inp.focus();
        }
        if (slVm(fam).some(v => v.id !== opt.except && v.name.toLowerCase() === name.toLowerCase())) {
          err.textContent = "Eine Ansicht mit diesem Namen gibt es schon.";
          return inp.focus();
        }
        fin({name, form}, close);
      };
      form.onclick = e => e.target.closest("[data-close]") && fin(null, close);
      inp.oninput = () => (err.textContent = "");
    });
    const host = [...document.querySelectorAll(".sldlg")].pop();
    if (host) new MutationObserver((m, ob) => {
      if (!host.isConnected) {                                         // Esc oder Klick daneben
        ob.disconnect();
        if (!done) {
          done = true;
          res(null);
        }
      }
    }).observe(document.body, {childList: true});
  });
}
function slVLine(t) {
  const l = document.getElementById("slvlive");
  if (l) {
    l.textContent = "";
    setTimeout(() => (l.textContent = t), 30);
  }
  slLive(t);
}
const slFamName = f => ({tour: "Tourseite", uebersicht: "Übersicht", statistik: "Statistik", reise: "Reise-Seite", serie: "Mehrtagestour-Seite", reisen: "Reisen-Übersicht", fotos: "Fotos-Seite", karte: "Karte"})[f] || f;
const slSports = () => [...new Set([...(typeof TOURS !== "undefined" ? TOURS : []).map(t => t.sport), ...Object.keys(slMaster("tour").rules || {})])].filter(s => s && /^[A-Za-z0-9_]{1,40}$/.test(s)).sort((a, b) => sName(a).localeCompare(sName(b), "de"));
function slViewsDialog() {
  const fam = SL.fam, famLabel = slFamName(fam);
  let focus = null, closeDlg = null, redraw = null;
  slModal("Ansichten", (body, close) => {
    closeDlg = close;
    const draw = () => {
      const m = slMaster(fam), cur = SL.view[fam], full = m.views.length >= SL_MAXV;
      const row = v => {
        const nm = esc(v.name), b = (a, label, extra) => `<button type="button" class="slb" data-a="${a}" data-id="${esc(v.id)}" aria-label="${esc(label)}: ${nm}"${extra || ""}>${label}</button>`;
        return `<li class="slvr${v.id === cur ? " cur" : ""}" data-id="${esc(v.id)}"><div class="slvh"><b class="slvnm">${nm}</b>` +
          (v.id === m.active ? `<span class="slvbd">Standardansicht</span>` : "") + (v.id === cur ? `<span class="slvbd on">Angezeigt</span>` : "") + `</div><div class="slvbt">` +
          (v.id === cur ? "" : b("show", "Anzeigen")) + b("rename", "Umbenennen") + b("dup", "Duplizieren", full ? " disabled" : "") +
          (v.id === m.active ? "" : b("def", "Als Standard festlegen")) + b("exp", "Exportieren") + b("share", "Teilen …", ' aria-haspopup="dialog"') + (m.views.length > 1 ? b("del", "Löschen") : "") + `</div></li>`;
      };
      let h = `<p class="mut slvin">Eine Ansicht ist eine gespeicherte Anordnung dieser Seite (${famLabel}). Die Standardansicht erscheint, wenn nichts anderes gewählt ist.</p>` +
        `<ul class="slvl" aria-label="Ansichten der ${famLabel}">${m.views.map(row).join("")}</ul>` +
        `<div class="slvadd"><button type="button" class="btn sm" data-a="new"${full ? " disabled" : ""}>Neue Ansicht</button><button type="button" class="btn ghost sm" data-a="tpl"${full ? " disabled" : ""}>Aus Vorlage …</button>` +
        `<button type="button" class="btn ghost sm" data-a="imp"${full ? " disabled" : ""}>Importieren …</button></div>` +
        (full ? `<p class="mut slvmax">Mehr als ${SL_MAXV} Ansichten sind nicht möglich. Lösche zuerst eine.</p>` : "");
      if (fam === "tour") {
        const sp = slSports();
        h += `<section class="slvru" aria-labelledby="slvruh"><h3 id="slvruh">Automatisch nach Sportart</h3><p class="mut slvin">Beim Öffnen einer Tour wird die Ansicht der Sportart gezeigt. Ohne Zuordnung gilt die Standardansicht. Wer oben von Hand eine Ansicht wählt, behält sie für diese Sitzung.</p>` +
          (sp.length ? `<div class="slvrg">${sp.map((s, i) => `<label class="slvrl" for="slvr${i}">${esc(sName(s))}</label><select id="slvr${i}" data-rule="${esc(s)}"><option value="">Standardansicht (${esc(slViewName(fam, m.active))})</option>` +
            m.views.map(v => `<option value="${esc(v.id)}"${(m.rules || {})[s] === v.id ? " selected" : ""}>${esc(v.name)}</option>`).join("") + `</select>`).join("")}</div>` : `<p class="mut">Sobald es Touren gibt, kannst du hier Sportarten zuordnen.</p>`) + `</section>`;
      }
      h += `<p class="slsr" id="slvlive" role="status" aria-live="polite"></p><div class="uifoot"><button type="button" class="btn ghost" data-close>Schließen</button></div>`;
      body.innerHTML = h;
      if (focus) {
        const f = body.querySelector(focus) || body.querySelector(".slvr .slb, [data-a=new]");
        focus = null;
        if (f) f.focus();
      }
    };
    redraw = draw;
    draw();
    body.addEventListener("click", async e => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.hasAttribute("data-close")) return close();
      const a = b.dataset.a, id = b.dataset.id, v = id && slVm(fam).find(x => x.id === id);
      if (!a || b.disabled) return;
      if (a === "show") {
        slSwitch(fam, id);
        focus = `[data-id="${id}"][data-a="rename"]`;
        draw();
        slVLine(`Ansicht „${v.name}“ wird angezeigt`);
      } else if (a === "rename") {
        const r = await slAskName(fam, {title: "Ansicht umbenennen", value: v.name, ok: "Umbenennen", except: id});
        focus = `[data-id="${id}"][data-a="rename"]`;
        if (r) {
          slViewRename(fam, id, r.name);
          slVLine(`Umbenannt in „${r.name}“`);
        }
        draw();
      } else if (a === "dup") {
        const nid = slViewAdd(fam, slUniq(fam, v.name + " (Kopie)"), slLayoutsOf(fam, id));
        slSetManual(fam, nid);
        slSwitch(fam, nid);
        focus = `[data-id="${nid}"][data-a="rename"]`;
        draw();
        slVLine(`Ansicht „${slViewName(fam, nid)}“ angelegt`);
      } else if (a === "def") {
        slViewDefault(fam, id);
        focus = `[data-id="${id}"][data-a="rename"]`;
        draw();
        slVLine(`„${v.name}“ ist jetzt die Standardansicht`);
      } else if (a === "exp") {
        slViewExport(fam, id);
        slVLine(`Ansicht „${v.name}“ exportiert`);
      } else if (a === "share") {
        focus = `[data-id="${id}"][data-a="share"]`;
        slCodeDialog(fam, id);
        slVLine(`Ansichtscode der Ansicht „${v.name}“`);
      } else if (a === "del") {
        const ok = await uiConfirm({title: "Ansicht löschen?", text: `Die Ansicht „${v.name}“ wird gelöscht. Das lässt sich nicht rückgängig machen. Tipp: Mit „Exportieren“ kannst du sie vorher sichern.`, ok: "Löschen", danger: true});
        if (ok) {
          slViewRemove(fam, id);
          focus = ".slvr .slb";
          slVLine(`Ansicht „${v.name}“ gelöscht`);
        } else focus = `[data-id="${id}"][data-a="del"]`;
        draw();
      } else if (a === "new") {
        const r = await slAskName(fam, {
          title: "Neue Ansicht", value: slUniq(fam, "Ansicht"), ok: "Anlegen",
          extra: `<fieldset class="slfs"><legend>Start mit</legend><div class="flchips"><label class="flchip"><input type="radio" name="slvsrc" value="copy" checked><span>Kopie der angezeigten Ansicht</span></label><label class="flchip"><input type="radio" name="slvsrc" value="empty"><span>Standard-Anordnung</span></label></div></fieldset>`,
        });
        focus = "[data-a=new]";
        if (r) {
          const copy = (r.form.querySelector('input[name="slvsrc"]:checked') || {}).value !== "empty",
            nid = slViewAdd(fam, r.name, copy ? slLayoutsOf(fam, SL.view[fam]) : {});
          slSwitch(fam, nid);
          focus = `[data-id="${nid}"][data-a="rename"]`;
          slVLine(`Ansicht „${r.name}“ angelegt`);
        }
        draw();
      } else if (a === "tpl") {
        slTplDialog(fam, nid => {
          focus = `[data-id="${nid}"][data-a="rename"]`;
          draw();
        });
      } else if (a === "imp") {
        slImportDialog(fam, nid => {
          focus = `[data-id="${nid}"][data-a="rename"]`;
          draw();
        });
      }
    });
  }, "slvws");
  return {close: () => closeDlg && closeDlg(), redraw: () => redraw && redraw()};
}

/* ---------- Vorlagen ---------- */
function slTplDialog(fam, done) {
  const list = slTplFor(fam);
  slModal("Vorlage wählen", (body, close) => {
    body.innerHTML = `<p class="mut slcatin">Eine Vorlage wird als neue Ansicht übernommen. Du kannst sie danach beliebig ändern; deine anderen Ansichten bleiben unberührt.</p><div class="slcats slvt">` +
      list.map(t => {
        const names = t.items.map(i => slTplItem(fam, i).title);
        return `<article class="slcard" data-tpl="${t.id}"><div class="slpv" aria-hidden="true">${slTplPreview(t)}</div><div class="slci"><h3>${esc(t.name)}</h3><p>${esc(t.desc)}</p>` +
          `<p class="mut slvcont"><span>Enthält:</span> ${names.map(esc).join(" · ")}</p><button type="button" class="btn sm" data-use="${t.id}" aria-label="${esc(t.name)}: Als neue Ansicht übernehmen">Als neue Ansicht übernehmen</button></div></article>`;
      }).join("") + `</div><div class="uifoot"><button type="button" class="btn ghost" data-close>Abbrechen</button></div>`;
    body.onclick = e => {
      if (e.target.closest("[data-close]")) return close();
      const u = e.target.closest("[data-use]");
      if (!u) return;
      const t = list.find(x => x.id === u.dataset.use);
      if (slVm(fam).length >= SL_MAXV) return uiAlert(`Mehr als ${SL_MAXV} Ansichten sind nicht möglich.`);
      const nid = slViewAdd(fam, slUniq(fam, t.name), slTplDocs(t));
      slSwitch(fam, nid);
      close();
      slVLine(`Ansicht „${slViewName(fam, nid)}“ aus der Vorlage angelegt`);
      done && done(nid);
    };
  }, "slcat");
}

/* ---------- Export ---------- */
function slExportDoc(fam, id) {
  const v = slVm(fam).find(x => x.id === id);
  return {format: SL_EXPORT_FORMAT, format_version: 1, app_version: SL_APPV, page: fam, name: v.name, exported: new Date().toISOString(), layouts: slLayoutsOf(fam, id)};
}
function slViewExport(fam, id) {
  const doc = slExportDoc(fam, id), blob = new Blob([JSON.stringify(doc, null, 2)], {type: "application/json"}),
    a = document.createElement("a"), slug = doc.name.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "ansicht";
  a.href = URL.createObjectURL(blob);
  a.download = `ansicht-${fam}-${slug}.json`;
  a.hidden = true;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    a.remove();
    URL.revokeObjectURL(a.href);
  }, 1000);
}

/* ---------- Import: Datei lesen, vom Server prüfen lassen (dieselben Regeln wie beim Speichern), Vorschau, dann übernehmen ---------- */
async function slCheckFile(file) {
  if (file.size > SL_MAXFILE) return {ok: false, errors: ["Die Datei ist zu groß für eine Ansicht."], ignored: []};
  let text;
  try {
    text = await file.text();
  } catch (e) {
    return {ok: false, errors: ["Die Datei konnte nicht gelesen werden."], ignored: []};
  }
  try {
    JSON.parse(text);
  } catch (e) {
    return {ok: false, errors: ["Die Datei ist kein gültiges JSON."], ignored: []};
  }
  try {
    const r = await fetch("/api/layout/check", {method: "POST", headers: {"Content-Type": "application/json"}, body: text, credentials: "same-origin"});
    if (!r.ok) throw new Error(String(r.status));
    return await r.json();
  } catch (e) {
    return {ok: false, errors: ["Die Prüfung ist nicht möglich (keine Verbindung zum Server?). Es wurde nichts übernommen."], ignored: []};
  }
}
function slImportDialog(fam, done, preset) {
  slModal("Ansicht importieren", (body, close) => {
    body.innerHTML = `<p class="mut slcatin">Wähle eine Datei, die du mit „Exportieren“ gespeichert hast, oder füge einen Ansichtscode ein (aus „Teilen …“). Sie wird zuerst geprüft; erst danach entscheidest du, was übernommen wird.</p>` +
      `<div class="slimpbar"><button type="button" class="btn ghost sm" data-a="pick">Datei wählen …</button><span class="mut slimpf" id="slimpf">Keine Datei gewählt</span><input type="file" id="slimpin" accept=".json,application/json" hidden></div>` +
      `<div class="slfs slimpcode"><label for="slimpcode">Ansichtscode oder Link einfügen</label><textarea id="slimpcode" rows="3" spellcheck="false" autocomplete="off" autocapitalize="off" placeholder="MTA1.…" aria-describedby="slimpch"></textarea>` +
      `<p class="mut slimphint" id="slimpch">Ein Ansichtscode enthält nur die Anordnung und die Einstellungen der Bausteine, keine Touren oder Fotos.</p><button type="button" class="btn ghost sm" data-a="code">Code prüfen</button></div>` +
      `<div class="slimpres" id="slimpres" role="status" aria-live="polite"></div><div class="uifoot"><button type="button" class="btn ghost" data-close>Schließen</button></div>`;
    const inp = body.querySelector("#slimpin"), res = body.querySelector("#slimpres"), ta = body.querySelector("#slimpcode");
    body.addEventListener("click", e => {
      if (e.target.closest("[data-close]")) close();
      else if (e.target.closest('[data-a="pick"]')) inp.click();
      else if (e.target.closest('[data-a="code"]')) checkCode();
    });
    const show = (r, isCode) => {
      const errs = (r.errors || []).slice();
      if (r.ok && r.page !== fam) errs.push(`Diese Datei gehört zur ${slFamName(r.page)}. Öffne dort „Seite anpassen“ → „Ansichten“, um sie zu importieren.`);
      if (errs.length) {
        res.innerHTML = `<div class="slimpbad" role="alert"><h3>${isCode ? "Der Code kann nicht importiert werden" : "Die Datei kann nicht importiert werden"}</h3><ul>${errs.map(x => `<li>${esc(x)}</li>`).join("")}</ul><p class="mut">Es wurde nichts verändert.</p></div>`;
        return;
      }
      const L = r.layouts || {}, st = r.stats || {}, types = new Set(Object.values(st).flatMap(s => s.types || [])), unknown = [...types].filter(t => !window.SL_WT[t]),
        nWid = Object.values(st).reduce((n, s) => n + (s.widgets || 0), 0), nHid = Object.values(st).reduce((n, s) => n + (s.hidden || 0), 0),
        nGrp = Object.values(st).reduce((n, s) => n + (s.groups || 0), 0), hasMob = Object.values(st).some(s => s.mob);
      res.innerHTML = `<div class="slimpok"><h3>${isCode ? "Code geprüft" : "Datei geprüft"}</h3><p>Ansicht „<b class="slimpn"></b>“ für die ${slFamName(fam)}: ${nWid === 1 ? "1 Baustein" : nWid + " Bausteine"}, ${nHid === 1 ? "1 ausgeblendeter Baustein" : nHid + " ausgeblendete Bausteine"}.</p>` +
        (nGrp || hasMob ? `<ul class="slimpx">${nGrp ? `<li>${nGrp === 1 ? "1 Bausteingruppe" : nGrp + " Bausteingruppen"}</li>` : ""}${hasMob ? "<li>Eigene Handy-Anordnung</li>" : ""}</ul>` : "") +
        ((r.ignored || []).length ? `<p class="mut">Ignoriert:</p><ul class="mut">${r.ignored.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : "") +
        (unknown.length ? `<p class="mut">${unknown.length === 1 ? "1 Baustein-Typ ist" : unknown.length + " Baustein-Typen sind"} in dieser Version nicht bekannt und werden nicht angezeigt.</p>` : "") +
        `<div class="slfs"><label for="slimpname">Name der neuen Ansicht</label><input id="slimpname" type="text" maxlength="40" autocomplete="off"><p class="mut slimphint" id="slimphint"></p></div>` +
        `<div class="slimpgo"><button type="button" class="btn sm" data-a="new">Als neue Ansicht importieren</button><button type="button" class="btn ghost sm" data-a="repl" hidden>Bestehende Ansicht ersetzen …</button></div></div>`;
      res.querySelector(".slimpn").textContent = r.name;
      const nm = res.querySelector("#slimpname"), hint = res.querySelector("#slimphint"), bNew = res.querySelector('[data-a="new"]'), bRep = res.querySelector('[data-a="repl"]');
      nm.value = r.name;
      const same = () => slVm(fam).find(v => v.name.toLowerCase() === nm.value.replace(/\s+/g, " ").trim().toLowerCase());
      const upd = () => {
        const s = same(), full = slVm(fam).length >= SL_MAXV;
        bRep.hidden = !s;
        bNew.disabled = full || !nm.value.trim() || /[<>]/.test(nm.value);
        hint.textContent = full ? `Mehr als ${SL_MAXV} Ansichten sind nicht möglich. Lösche zuerst eine Ansicht oder ersetze eine bestehende.` : s ? `Es gibt schon eine Ansicht „${s.name}“. Die neue heißt „${slUniq(fam, nm.value)}“, oder du ersetzt die bestehende.` : "";
        if (full && !s) bNew.disabled = true;
      };
      nm.addEventListener("input", upd);
      upd();
      res.onclick = async e => {
        const b = e.target.closest("button");
        if (!b || b.disabled) return;
        if (b.dataset.a === "new") {
          const nid = slViewAdd(fam, slUniq(fam, nm.value.trim()), L);
          slSwitch(fam, nid);
          close();
          slVLine(`Ansicht „${slViewName(fam, nid)}“ importiert`);
          done && done(nid);
        } else if (b.dataset.a === "repl") {
          const s = same();
          if (!s) return;
          const ok = await uiConfirm({title: "Ansicht ersetzen?", text: `Die Ansicht „${s.name}“ wird mit dem Inhalt der Datei überschrieben. Das lässt sich nicht rückgängig machen.`, ok: "Ersetzen", danger: true});
          if (!ok) return;
          slViewReplace(fam, s.id, L);
          slSwitch(fam, s.id);
          close();
          slVLine(`Ansicht „${s.name}“ ersetzt`);
          done && done(s.id);
        }
      };
      nm.focus();
    };
    async function checkCode() {
      if (!ta.value.trim()) {
        res.innerHTML = `<div class="slimpbad" role="alert"><h3>Der Code kann nicht importiert werden</h3><ul><li>Bitte zuerst einen Ansichtscode oder Link einfügen.</li></ul><p class="mut">Es wurde nichts verändert.</p></div>`;
        return ta.focus();
      }
      res.innerHTML = `<p class="mut">Code wird geprüft …</p>`;
      show(await slCheckCode(ta.value), true);
    }
    inp.addEventListener("change", async () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      body.querySelector("#slimpf").textContent = f.name;
      res.innerHTML = `<p class="mut">Datei wird geprüft …</p>`;
      show(await slCheckFile(f));
    });
    if (preset) {
      ta.value = preset;
      checkCode();
    } else body.querySelector('[data-a="pick"]').focus();
  }, "slimp");
}

/* ---------- 3.22.0 Anordnung und Filter sichern ---------- */
/* Filter einer Ansicht: Seiten mit eigenem Filter (Statistik) melden sich in SLF an: {dirty(): Wahrheitswert, apply(layout): schreibt den Filter in das Layout, discard()} */
const SLF = {};
/* Neue Ansicht aus der aktuellen Anordnung. fromEdit: Bearbeitungsmodus, die bisherige Ansicht bleibt auf dem Stand von vor dem Bearbeiten.
   Sonst (Filter): Kopie der angezeigten Ansicht mit dem gerade gewählten Filter; die bisherige bleibt, wie gespeichert. */
async function slSaveNew(fam, fromEdit) {
  if (slVm(fam).length >= SL_MAXV) return uiAlert(`Mehr als ${SL_MAXV} Ansichten sind nicht möglich. Lösche zuerst eine.`);
  const r = await slAskName(fam, {title: "Als neue Ansicht speichern", ok: "Speichern", value: slUniq(fam, slViewName(fam, SL.view[fam]) + " (Kopie)")});
  if (!r) return;
  const cur = SL.view[fam], master = slKeys(fam)[0], snap = SL.snap;
  const layouts = slLayoutsOf(fam, cur);
  if (!fromEdit && SLF[fam]) SLF[fam].apply(layouts[master]);
  if (fromEdit && snap && snap.fam === fam) {                          // bisherige Ansicht zurück auf den Stand des Schnappschusses
    slKeys(fam).forEach(k => {
      const o = (JSON.parse(snap.st[k]).views.find(x => x.id === cur) || {}).layout;
      if (o && !slLayEmpty(o)) SL.docs[k] = slTplCopy(o);
      else delete SL.docs[k];
    });
  }
  document.querySelectorAll(".tlw[data-wid]").forEach(e => e.remove());
  const id = slViewAdd(fam, r.name, layouts);
  if (SLF[fam] && SLF[fam].discard) SLF[fam].discard(cur);
  slSwitch(fam, id);
  if (SL.edit) slSnap();
  slChg();
  slAnnounce(`Als neue Ansicht „${r.name}“ gespeichert`);
}
/* Knopf „Ansicht speichern“ neben der Auswahl, solange der Filter vom gespeicherten Stand der Ansicht abweicht */
function slSaveBar(w) {
  const h = SLF[SL.fam], on = !!(h && h.dirty && h.dirty()), old = w.querySelector(".slsv"), vb = w.querySelector("#slviews");
  if (vb) vb.classList.toggle("slvd", on);                                  // Handy: Punkt am Knopf „Ansichten“ statt der Zeile „geändert / Ansicht speichern“ (die Zeile bleibt für Desktop)
  if (!on) {
    if (old) old.remove();
    return false;
  }
  if (!old) {
    w.insertAdjacentHTML("beforeend", `<span class="slsv"><span class="slchg" id="slfchg">geändert</span><button type="button" class="btn sm" id="slsave" aria-haspopup="dialog">Ansicht speichern</button></span>`);
  }
  return true;
}
function slBarRefresh() {
  const w = document.getElementById("slopenw");
  if (w && slSaveBar(w)) w.hidden = false;
}
function slSaveMenu() {
  const fam = SL.fam, h = SLF[fam];
  if (!h) return;
  slModal("Ansicht speichern", (body, close) => {
    body.innerHTML = `<p class="mut">Der Filter (Sportart und Zeitraum) gehört zur Ansicht „${esc(slViewName(fam, SL.view[fam]))}“. Er ist noch nicht gespeichert.</p>` +
      `<div class="slmenu"><button type="button" class="btn" data-m="here">In dieser Ansicht speichern</button><button type="button" class="btn ghost" data-m="new">Als neue Ansicht speichern …</button><button type="button" class="btn ghost" data-m="drop">Verwerfen</button></div>`;
    body.onclick = e => {
      const b = e.target.closest("[data-m]");
      if (!b) return;
      const m = b.dataset.m;
      close();
      if (m === "here") {
        const k = slKeys(fam)[0];
        h.apply(SL.docs[k] || (SL.docs[k] = {v: 1}));
        slTouch(k);
        slBarRefresh();
        slAnnounce("Ansicht gespeichert");
      } else if (m === "new") slSaveNew(fam, false);
      else {
        h.discard();
        slAnnounce("Änderung am Filter verworfen");
      }
    };
  });
}
document.addEventListener("click", e => e.target.closest && e.target.closest("#slsave") && slSaveMenu());
