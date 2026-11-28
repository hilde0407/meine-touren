/* =====================  3.73.0 Wanderführer: Ordner, Umbenennen, Verschieben, Übertragen, Tournamen angleichen  =====================
   Gehört zur Seite „Orte & Ausrüstung“ (gfMount/gfDraw in 10-auswertung.js) und folgt dem Tagebuch (Wanderführer ab 2.4.0, Ordner ab 2.25.0, Datei ab 2.13.0):
   - Ordner enthalten Bücher (anlegen, umbenennen, löschen – nie Bücher; Bücher in Ordner verschieben oder aus dem Ordner entfernen)
   - Buch: umbenennen, GPX-Dateien hinzufügen, löschen; Buchtour: umbenennen, in ein anderes Buch verschieben, löschen
   - Übertragen: Wanderführer exportieren (GET /api/guides/export, Format „tourentagebuch-wanderfuehrer“) und importieren (Vorschau, nichts wird überschrieben)
   - Tournamen angleichen: Vorschlag Buchtour-Titel -> Tourname aus dem Abgleich „gewandert“, Vorschau Alt -> Neu, Protokoll und Rückgängig; optional auch bei Komoot (Vorgabe aus, nur mit Bestätigung)
   Dialoge: uiConfirm/uiPrompt/uiAlert (Abbrechen links, Hauptaktion rechts, klebende Fußzeile .uifoot); Meldungen an der Stelle der Aktion (#gfmsg). */
const gfJson = (u, body, method) => api(u, {method: method || "POST", headers: {"content-type": "application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
const gfFail = (vorgang, e) => uiAlert({text: `${vorgang} nicht möglich: ${(e && e.message) || e}`});
/* Seite neu aufbauen (Daten frisch, Scrollstand und Filter bleiben), Meldung steht danach an der Stelle der Aktion */
async function gfReload(msg) {
  GF.msg = msg || "";
  const y = window.scrollY;
  await route();
  window.scrollTo(0, y);
}
const gfBuch = b => (b && b.book) || "(ohne Buch)";
const gfBTitel = n => fmtAnzahl(n, "Buchtour", "Buchtouren");
/* Auswahl-Menü im Dialog: Eintrag = [Kennung, Symbolschlüssel, Text, gefährlich?]; gibt die gewählte Kennung zurück (oder null) */
async function gfMenu(title, items) {
  let choice = null;
  const btn = ([k, ic, tx, danger]) => `<button type="button" class="btn ghost${danger ? " gfdanger" : ""}" data-m="${k}">${ic.startsWith("ic:") ? symHtml(ic, 17) + " " : ic + " "}${tx}</button>`;
  await uiAlert({
    title,
    html: `<div class="slmenu">${items.filter(Boolean).map(btn).join("")}</div>`,
    ok: "Schließen",
    onOpen: (box, ok) => box.querySelectorAll("[data-m]").forEach(x => (x.onclick = () => ((choice = x.dataset.m), ok.click()))),
  });
  return choice;
}

/* ---------- Ordner ---------- */
async function gfFolderNew() {
  const n = await uiPrompt({title: "Neuer Ordner", label: "Name", ok: "Anlegen", min: 1});
  if (n == null) return;
  try {
    const r = await gfJson("/api/guides/folders", {name: n});
    await gfReload(`Ordner „${r.name}“ gespeichert`);
  } catch (e) {
    gfFail("Ordner anlegen", e);
  }
}
async function gfFolderRename(name) {
  const n = await uiPrompt({title: "Ordner umbenennen", label: "Name", value: name, ok: "Speichern", min: 1});
  if (n == null || n.trim() === name) return;
  try {
    const r = await gfJson("/api/guides/folders/rename", {name, new: n});
    await gfReload(`Ordner „${r.name}“ gespeichert`);
  } catch (e) {
    gfFail("Ordner umbenennen", e);
  }
}
async function gfFolderDelete(name) {
  const n = GF.books.filter(b => b.folder === name).length;
  const text = n
    ? n === 1
      ? "Das Buch darin bleibt erhalten und kommt zurück nach „Ohne Ordner“."
      : `Die ${n} Bücher darin bleiben erhalten und kommen zurück nach „Ohne Ordner“.`
    : "Der Ordner ist leer.";
  if (!(await uiConfirm({title: `Ordner „${name}“ löschen?`, text, ok: "Löschen", danger: true}))) return;
  try {
    await api("/api/guides/folders?name=" + encodeURIComponent(name), {method: "DELETE"});
    await gfReload("Ordner gelöscht");
  } catch (e) {
    gfFail("Löschen", e);
  }
}
/* Auswahl „Ordner oder Buch“ für Verschieben: Auswahlfeld mit den vorhandenen Einträgen und „Neu …“ (dann Namensfeld); gibt {name, neu} zurück oder null */
async function gfPickTarget(o) {
  let sel = o.first,
    inp = null;
  const html = `${o.lead || ""}<label class="uiplbl">${o.label}<select class="uipin" id="gfsel">${o.options.map(([v, t]) => `<option value="${esc(v)}"${v === o.first ? " selected" : ""}>${esc(t)}</option>`).join("")}<option value="\u0001"${o.first === "\u0001" ? " selected" : ""}>${o.neuText}</option></select></label>
    <label class="uiplbl" id="gfnl">${o.neuLabel}<input class="uipin" id="gfnn" maxlength="${o.max}" autocomplete="off"></label>`;
  const ok = await uiConfirm({
    title: o.title,
    html,
    ok: "Verschieben",
    onOpen: (box, bOk) => {
      const s = box.querySelector("#gfsel"),
        l = box.querySelector("#gfnl");
      inp = box.querySelector("#gfnn");
      const chk = () => {
        sel = s.value;
        l.hidden = sel !== "\u0001";
        bOk.disabled = sel === "\u0001" && !inp.value.trim();
      };
      s.onchange = chk;
      inp.oninput = chk;
      inp.addEventListener("keydown", e => {
        if (e.key === "Enter" && !bOk.disabled) {
          e.preventDefault();
          bOk.click();
        }
      });
      chk();
      if (sel === "\u0001") setTimeout(() => inp.focus(), 0);
      else s.focus();
    },
  });
  if (!ok) return null;
  return sel === "\u0001" ? {name: inp.value.trim(), neu: true} : {name: sel, neu: false};
}
async function gfBookMove(b) {
  const t = await gfPickTarget({
    title: "In Ordner verschieben",
    lead: `<p class="mut" translate="no">${esc(gfBuch(b))}</p>`,
    label: "Ordner",
    neuText: "Neuer Ordner …",
    neuLabel: "Name des neuen Ordners",
    max: 60,
    options: GF.folders.map(f => [f, f]),
    first: b.folder || GF.folders[0] || "\u0001",
  });
  if (!t) return;
  try {
    await gfJson("/api/guides/folders/move", {books: [b.key], folder: t.name});
    await gfReload(`„${gfBuch(b)}“ in „${t.name}“ verschoben`);
  } catch (e) {
    gfFail("Verschieben", e);
  }
}
async function gfBookUnfolder(b) {
  try {
    await gfJson("/api/guides/folders/move", {books: [b.key], folder: null});
    await gfReload(`„${gfBuch(b)}“ aus dem Ordner entfernt`);
  } catch (e) {
    gfFail("Entfernen", e);
  }
}

/* ---------- Buch ---------- */
async function gfBookMenu(b) {
  const k = await gfMenu(gfBuch(b), [
    ["ren", "✎", "Umbenennen …"],
    ["mv", "ic:folder", "In Ordner verschieben …"],
    b.folder ? ["un", "✕", "Aus Ordner entfernen"] : null,
    ["add", "ic:plus", "GPX-Dateien hinzufügen …"],
    ["del", "🗑", "Buch löschen …", true],
  ]);
  if (k === "ren") return gfBookRename(b);
  if (k === "mv") return gfBookMove(b);
  if (k === "un") return gfBookUnfolder(b);
  if (k === "add") return gfBookAdd(b);
  if (k === "del") return gfBookDelete(b);
}
async function gfBookRename(b) {
  const n = await uiPrompt({title: "Buch umbenennen", label: "Name des Buchs", value: b.key, ok: "Speichern", min: 1});
  if (n == null || n.trim() === b.key) return;
  try {
    await gfJson("/api/guides/book/rename", {book: b.key, name: n});
    await gfReload("Name gespeichert");
  } catch (e) {
    gfFail("Umbenennen", e);
  }
}
async function gfBookDelete(b) {
  const text = `Das Buch mit ${gfBTitel(b.total)} wird gelöscht, samt Titelbild. Deine eigenen Touren bleiben. Zurückholen lässt es sich nur aus einer Sicherung oder mit den GPX-Dateien.`;
  if (!(await uiConfirm({title: `Buch „${gfBuch(b)}“ löschen?`, text, ok: "Löschen", danger: true}))) return;
  try {
    await api("/api/guides/" + encodeURIComponent("book:" + b.key), {method: "DELETE"});
    await gfReload("Buch gelöscht");
  } catch (e) {
    gfFail("Löschen", e);
  }
}
/* „Buch anlegen …“ (b = null) und „GPX-Dateien hinzufügen …“ (b = Buch): Name und Dateien im selben Dialog (die Dateiwahl braucht einen Klick im Dialog, nicht danach) */
async function gfBookAdd(b) {
  let name = null,
    files = null;
  const html = `${b ? `<p class="mut" translate="no">${esc(gfBuch(b))}</p>` : `<label class="uiplbl">Name des Buchs<input class="uipin" id="gfbn" maxlength="80" autocomplete="off" placeholder="z. B. Rother Wanderführer Gran Canaria"></label>`}
    <label class="uiplbl">GPX-Dateien<input class="uipin" id="gfbf" type="file" accept=".gpx,application/gpx+xml,text/xml" multiple></label>
    <p class="mut fs14">Wähle die GPX-Dateien des Buchs (bei Rother im Download-Bereich zum Buch). Du kannst mehrere auf einmal wählen. Eine Buchtour mit gleichem Titel und gleicher Länge wird nicht doppelt angelegt.</p>`;
  const ok = await uiConfirm({
    title: b ? "GPX-Dateien hinzufügen" : "Buch anlegen",
    html,
    ok: b ? "Hinzufügen" : "Anlegen",
    onOpen: (box, bOk) => {
      const nn = box.querySelector("#gfbn"),
        ff = box.querySelector("#gfbf"),
        chk = () => ((name = nn ? nn.value : null), (files = ff.files), (bOk.disabled = !files.length || (nn && !nn.value.trim())));
      if (nn) nn.oninput = chk;
      ff.onchange = chk;
      chk();
      setTimeout(() => (nn || ff).focus(), 0);
    },
  });
  if (!ok || !files || !files.length) return;
  const fs = [...files],
    book = b ? b.key : name.trim();
  let added = 0,
    schon = 0,
    bad = [];
  try {
    for (let i = 0; i < fs.length; i += 25) {
      gfMsg(`Lese Datei ${Math.min(i + 25, fs.length)} von ${fs.length} …`);
      const items = await Promise.all(fs.slice(i, i + 25).map(f => f.text().then(gpx => ({name: f.name, gpx}))));
      const r = await gfJson("/api/guides", {book, items});
      added += r.added;
      schon += r.schon || 0;
      bad = bad.concat(r.failed || []);
    }
  } catch (e) {
    gfMsg(`${b ? "GPX-Dateien hinzufügen" : "Buch anlegen"} nicht möglich: ${e.message}`, true);
    return;
  }
  const teile = [`${gfBTitel(added)} ${b ? "hinzugefügt" : "angelegt"}`];
  if (schon) teile.push(`${schon} schon vorhanden`);
  if (bad.length) teile.push(`${bad.length} nicht lesbar (${bad.slice(0, 2).map(x => x.split(":")[0]).join(", ")}${bad.length > 2 ? " …" : ""})`);
  await gfReload(added || b ? teile.join(" · ") : `Keine Buchtour gefunden: ${bad.length ? bad[0] : "die Dateien enthalten keine Strecke"}`);
}

/* ---------- Buchtour ---------- */
async function gfTourMenu(b, x) {
  if (!x) return;
  const k = await gfMenu(x.title, [["ren", "✎", "Umbenennen …"], ["mv", "ic:folder", "In ein anderes Buch verschieben …"], ["del", "🗑", "Buchtour löschen …", true]]);
  if (k === "ren") {
    const n = await uiPrompt({title: "Buchtour umbenennen", label: "Name der Buchtour", value: x.title, ok: "Speichern", min: 1});
    if (n == null || n.trim() === x.title) return;
    try {
      await gfJson("/api/guides/tour/" + x.id, {title: n});
      await gfReload("Name gespeichert");
    } catch (e) {
      gfFail("Umbenennen", e);
    }
  } else if (k === "mv") {
    const others = GF.books.filter(y => y !== b && y.key);
    const last = b.total === 1 ? `<p class="mut fs14">Das ist die einzige Buchtour von „${esc(gfBuch(b))}“. Das Buch ist danach leer und verschwindet samt Titelbild.</p>` : "";
    const t = await gfPickTarget({
      title: "Buchtour verschieben",
      lead: `<p class="mut" translate="no">${esc(x.title)}</p>${last}`,
      label: "In dieses Buch",
      neuText: "Neues Buch …",
      neuLabel: "Name des neuen Buchs",
      max: 80,
      options: others.map(y => [y.key, y.key]),
      first: others.length ? others[0].key : "\u0001",
    });
    if (!t) return;
    try {
      const r = await gfJson("/api/guides/tour/" + x.id, {book: t.name});
      await gfReload(`„${x.title}“ in „${r.book}“ verschoben`);
    } catch (e) {
      gfFail("Verschieben", e);
    }
  } else if (k === "del") {
    const text = "Die Buchtour wird aus dem Buch gelöscht. Deine eigenen Touren bleiben. Zurückholen lässt sie sich nur aus einer Sicherung oder mit der GPX-Datei.";
    if (!(await uiConfirm({title: `Buchtour „${x.title}“ löschen?`, text, ok: "Löschen", danger: true}))) return;
    try {
      await api("/api/guides/" + x.id, {method: "DELETE"});
      await gfReload("Buchtour gelöscht");
    } catch (e) {
      gfFail("Löschen", e);
    }
  }
}

/* ---------- Übertragen: exportieren und importieren ---------- */
async function gfExport() {
  let cover = false;
  const ok = await uiConfirm({
    title: "Wanderführer exportieren",
    html: `<p>Speichert deine Bücher mit allen Buchtouren (Titel, Strecke, Aufstieg, Ordner) als Datei – zum Übertragen auf ein anderes Gerät oder zum Aufheben.</p>
      <p class="mut fs14">Keine Spuren deiner Touren, keine Fotos, keine Zugangsdaten.</p>
      <label class="chk"><input type="checkbox" id="gfexc"> Titelbilder mitnehmen (deine eigenen Bilder, größere Datei)</label>`,
    ok: "Exportieren",
    onOpen: box => (box.querySelector("#gfexc").onchange = e => (cover = e.target.checked)),
  });
  if (!ok) return;
  try {
    const d = await api("/api/guides/export" + (cover ? "?cover=1" : ""));
    if (!d.buecher || !d.buecher.length) return gfMsg("Noch kein Buch angelegt.");
    const t = new Date(),
      p2 = n => String(n).padStart(2, "0"),
      name = `Meine-Touren-Wanderfuehrer-${t.getFullYear()}-${p2(t.getMonth() + 1)}-${p2(t.getDate())}.json`,
      a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(d)], {type: "application/json"}));
    a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    gfMsg(`Wanderführer exportiert: ${fmtAnzahl(d.buecher.length, "Buch", "Bücher")}`);
  } catch (e) {
    gfMsg(`Export nicht möglich: ${e.message}`, true);
  }
}
/* Zusammenfassung der Vorschau – dieselben Sätze wie im Tagebuch („1 neues Buch · 3 neue Buchtouren in vorhandenen Büchern · 2 Buchtouren sind schon da“) */
function gfPlanText(p) {
  const t = [],
    erg = p.neueTourenInVorhandenen;
  if (p.neueBuecher) t.push(p.neueBuecher === 1 ? "1 neues Buch" : `${p.neueBuecher} neue Bücher`);
  if (erg) t.push(erg === 1 ? "1 neue Buchtour in einem vorhandenen Buch" : `${erg} neue Buchtouren in vorhandenen Büchern`);
  if (p.schon) t.push(p.schon === 1 ? "1 Buchtour ist schon da" : `${p.schon} Buchtouren sind schon da`);
  if (p.titelbilder) t.push(p.titelbilder === 1 ? "1 Titelbild" : `${p.titelbilder} Titelbilder`);
  return t.length ? t.join(" · ") : "Nichts Neues in der Datei";
}
const gfKm = km => fmtKm(km);
function gfKonflikt(k) {
  return k.art === "cover" ? `Titelbild von „${k.buch}“: deines bleibt.` : `„${k.titel}“ in „${k.buch}“: in der Datei ${gfKm(k.km_datei)}, bei dir ${gfKm(k.km_hier)} – nicht übernommen.`;
}
async function gfImport() {
  let text = null,
    plan = null;
  const html = `<p>Wähle eine Wanderführer-Datei (aus Meine Touren oder aus Mein Tourentagebuch). Vor dem Importieren siehst du, was dazukommt.</p>
    <label class="uiplbl">Datei<input class="uipin" id="gfif" type="file" accept=".json,application/json"></label>
    <div id="gfip" role="status" aria-live="polite"></div>
    <p class="mut fs14">Vorhandenes bleibt, wie es ist: Es kommen nur neue Bücher und neue Buchtouren dazu. Welche Buchtouren gewandert sind, rechnet Meine Touren danach selbst mit deinen Touren aus.</p>`;
  const ok = await uiConfirm({
    title: "Wanderführer importieren",
    html,
    ok: "Importieren",
    onOpen: (box, bOk) => {
      const ff = box.querySelector("#gfif"),
        out = box.querySelector("#gfip");
      bOk.disabled = true;
      ff.onchange = async () => {
        plan = text = null;
        bOk.disabled = true;
        out.innerHTML = "";
        if (!ff.files.length) return;
        out.textContent = "Datei wird geprüft …";
        try {
          text = await ff.files[0].text();
          plan = await api("/api/guides/import/preview", {method: "POST", headers: {"content-type": "application/json"}, body: text});
        } catch (e) {
          text = plan = null;
          out.innerHTML = `<p class="bad" role="alert"></p>`;
          out.firstChild.textContent = `Import nicht möglich: ${e.message}`;
          return;
        }
        const kon = plan.konflikte;
        out.innerHTML = `<p id="gfisum"><b></b></p>${plan.defekt ? `<p class="mut fs14" id="gfidef"></p>` : ""}${
          kon.length ? `<h3 class="gfh3 sub"></h3><ul class="gfkonf"></ul>` : ""
        }`;
        out.querySelector("#gfisum b").textContent = gfPlanText(plan) + ".";
        if (plan.defekt) out.querySelector("#gfidef").textContent = plan.defekt === 1 ? "1 Eintrag ist nicht lesbar und bleibt draußen." : `${plan.defekt} Einträge sind nicht lesbar und bleiben draußen.`;
        if (kon.length) {
          out.querySelector("h3").textContent = kon.length === 1 ? "1 Unterschied" : `${kon.length} Unterschiede`;
          const ul = out.querySelector("ul");
          kon.slice(0, 30).forEach(k => ul.append(Object.assign(document.createElement("li"), {textContent: gfKonflikt(k)})));
          if (kon.length > 30) ul.append(Object.assign(document.createElement("li"), {className: "mut", textContent: `… und ${kon.length - 30} weitere.`}));
        }
        bOk.disabled = !(plan.neueBuecher || plan.neueTourenInVorhandenen || plan.titelbilder);
      };
    },
  });
  if (!ok || !text || !plan) return;
  try {
    const r = await api("/api/guides/import", {method: "POST", headers: {"content-type": "application/json"}, body: text});
    await gfReload(`Importiert: ${gfPlanText(r)}`);
  } catch (e) {
    gfMsg(`Import nicht möglich: ${e.message}`, true);
  }
}

/* ---------- Tournamen an die Buchtouren angleichen ---------- */
const gfDatum = ts => (ts ? fmtDatumKurz(new Date(ts * 1000).toISOString().slice(0, 10)) : "");
async function gfNamesOpen() {
  const m = uiModal(`<h3>Tournamen angleichen</h3><div id="gfnb" class="gfnb"><p class="mut" role="status">Wird geladen …</p></div><div class="uifoot" id="gfnf"><button type="button" class="btn ghost" data-x>Abbrechen</button></div>`);
  const body = m.querySelector("#gfnb"),
    foot = m.querySelector("#gfnf"),
    close = () => m.remove();
  foot.querySelector("[data-x]").onclick = close;
  let d;
  try {
    d = await api("/api/guides/rename-suggestions");
  } catch (e) {
    body.innerHTML = errCard(e);                    // Fehlerkarte mit Titel, Grund und Rückweg
    return;
  }
  if (!d.items.length) {
    body.innerHTML = `<p id="gfnone">Alle Touren, die zu einer Buchtour passen, heißen schon wie die Buchtour.</p><p class="mut fs14">Hier erscheinen deine gewanderten Touren, deren Name vom Titel der Buchtour abweicht.</p>`;
    foot.innerHTML = `<button type="button" class="btn ghost" data-log>Protokoll …</button><button type="button" class="btn" data-x>Schließen</button>`;
    foot.querySelector("[data-x]").onclick = close;
    foot.querySelector("[data-log]").onclick = () => gfLogOpen(m);
    return;
  }
  const sel = new Set();
  body.innerHTML = `<p class="mut">Der Name einer gewanderten Tour wird zum Titel der Buchtour. Nichts geschieht, bevor du „Umbenennen“ wählst; die alten Namen stehen danach im Protokoll.</p>
    <div class="row gfnbar"><button type="button" class="btn sm ghost" data-all>Alle</button><button type="button" class="btn sm ghost" data-none>Keine</button><span class="mut" id="gfncnt" role="status"></span></div>
    <div class="gfnl" id="gfnl"></div>
    <label class="chk gfnk"><input type="checkbox" id="gfnkom"${d.komoot_moeglich ? "" : " disabled"}> Auch bei Komoot umbenennen</label>
    <p class="mut fs14" id="gfnkh"></p>`;
  const list = body.querySelector("#gfnl");
  d.items.forEach((x, i) => {
    const row = document.createElement("label");
    row.className = "gfnr";
    row.innerHTML = `<input type="checkbox" data-i="${i}"><span class="gfnt"><span class="gfnn" translate="no"><s class="gfnalt"></s> <span aria-hidden="true">→</span> <b></b></span><small translate="no"></small></span>`;
    row.querySelector("s").textContent = x.name;
    row.querySelector("b").textContent = x.title;
    row.querySelector("small").textContent = [x.book || "(ohne Buch)", gfDatum(x.ts), x.mehrere ? "passt auch zu weiteren Buchtouren" : ""].filter(Boolean).join(" · ");
    row.querySelector("input").setAttribute("aria-label", `„${x.name}“ in „${x.title}“ umbenennen`);
    row.querySelector("input").onchange = e => {
      e.target.checked ? sel.add(i) : sel.delete(i);
      upd();
    };
    list.append(row);
  });
  const go = document.createElement("button");
  go.type = "button";
  go.className = "btn";
  go.id = "gfngo";
  go.textContent = "Umbenennen";
  foot.innerHTML = `<button type="button" class="btn ghost" data-log>Protokoll …</button><button type="button" class="btn ghost" data-x>Abbrechen</button>`;
  foot.append(go);
  foot.querySelector("[data-x]").onclick = close;
  foot.querySelector("[data-log]").onclick = () => gfLogOpen(m);
  const kom = () => body.querySelector("#gfnkom").checked && d.komoot_moeglich,
    nK = () => [...sel].filter(i => d.items[i].komoot).length;
  function upd() {
    go.disabled = !sel.size;
    body.querySelector("#gfncnt").textContent = `${sel.size} von ${d.items.length} gewählt`;
    list.querySelectorAll("input").forEach(c => (c.checked = sel.has(+c.dataset.i)));
    body.querySelector("#gfnkh").textContent = !d.komoot_moeglich
      ? "Komoot ist nicht verbunden: Verwaltung → Touren holen → Komoot."
      : kom()
        ? nK() === 1
          ? "1 Tour liegt bei Komoot und wird dort umbenannt, du bestätigst das vor dem Umbenennen."
          : `${nK()} Touren liegen bei Komoot und werden dort umbenannt, du bestätigst das vor dem Umbenennen.`
        : "Ändert die Namen nur hier. Bei Komoot bleiben sie, wie sie sind.";
  }
  body.querySelector("[data-all]").onclick = () => (d.items.forEach((_, i) => sel.add(i)), upd());
  body.querySelector("[data-none]").onclick = () => (sel.clear(), upd());
  body.querySelector("#gfnkom").onchange = upd;
  upd();
  go.onclick = async () => {
    const items = [...sel].map(i => ({tour: d.items[i].tour, name: d.items[i].title})),
      k = kom(),
      n = nK();
    if (k && n) {
      const ok = await uiConfirm({
        title: "Bei Komoot umbenennen?",
        text: `${n === 1 ? "1 Tour wird" : n + " Touren werden"} auch bei Komoot umbenannt. Das ändert die Namen in deinem Komoot-Konto. Die alten Namen stehen vorher im Protokoll.`,
        ok: "Bei Komoot umbenennen",
      });
      if (!ok) return;
    }
    go.disabled = true;
    body.querySelector("#gfncnt").textContent = "Wird umbenannt …";
    try {
      const r = await gfJson("/api/guides/rename-tours", Object.assign({items}, k ? {komoot: true, bestaetigt: n} : {}));
      gfNamesResult(m, r, d, k);
    } catch (e) {
      go.disabled = false;
      body.querySelector("#gfncnt").textContent = "";
      gfFail(k ? "Bei Komoot umbenennen" : "Umbenennen", e);
    }
  };
}
function gfNamesResult(m, r, d, k) {
  const body = m.querySelector("#gfnb"),
    foot = m.querySelector("#gfnf"),
    name = {};
  d.items.forEach(x => (name[x.tour] = x.name));
  const lines = [];
  r.ergebnisse.forEach(e => {
    if (!e.ok) lines.push(`„${name[e.tour] || e.tour}“: Umbenennen nicht möglich: ${e.fehler}`);
    else if (e.komoot_fehler) lines.push(`„${e.alt}“: Bei Komoot umbenennen nicht möglich: ${e.komoot_fehler}`);
  });
  body.innerHTML = `<p id="gfnres"><b></b></p>${k ? `<p id="gfnkres"></p>` : ""}${lines.length ? `<h3 class="gfh3 sub">Das hat nicht geklappt</h3><ul class="gfkonf bad" id="gfnerr"></ul>` : ""}`;
  body.querySelector("#gfnres b").textContent = `${r.umbenannt === 1 ? "1 Tour" : r.umbenannt + " Touren"} umbenannt`;
  if (k) body.querySelector("#gfnkres").textContent = `Bei Komoot umbenannt: ${r.bei_komoot}`;
  lines.forEach(t => body.querySelector("#gfnerr").append(Object.assign(document.createElement("li"), {textContent: t})));
  foot.innerHTML = `<button type="button" class="btn ghost" data-undo${r.umbenannt ? "" : " hidden"}>Rückgängig machen</button><button type="button" class="btn" data-x>Schließen</button>`;
  foot.querySelector("[data-x]").onclick = () => (m.remove(), gfReload(r.umbenannt ? "Namen gespeichert" : ""));
  foot.querySelector("[data-undo]").onclick = async () => {
    if (await gfUndo({batch: r.batch}, r.bei_komoot)) (m.remove(), gfReload("Alte Namen wiederhergestellt"));
  };
}
/* Namen aus dem Protokoll wiederherstellen; war ein Name auch bei Komoot geändert, fragt der Dialog (Vorgabe aus) nach dem Rückgängigmachen dort. Gibt true zurück, wenn etwas rückgängig gemacht wurde. */
async function gfUndo(sel, nKom) {
  let kom = false;
  const ok = await uiConfirm({
    title: "Umbenennung rückgängig machen?",
    html: `<p>Die Touren bekommen ihre alten Namen zurück. Eine Tour, die inzwischen anders heißt, bleibt, wie sie ist.</p>${
      nKom ? `<label class="chk"><input type="checkbox" id="gfuk"> Auch bei Komoot rückgängig machen (${nKom === 1 ? "1 Tour" : nKom + " Touren"})</label>` : ""
    }`,
    ok: "Rückgängig machen",
    onOpen: box => {
      const c = box.querySelector("#gfuk");
      if (c) c.onchange = () => (kom = c.checked);
    },
  });
  if (!ok) return false;
  try {
    const r = await gfJson("/api/guides/rename-undo", Object.assign({}, sel, kom ? {komoot: true, bestaetigt: nKom} : {}));
    if (r.fehler) {
      const t = r.ergebnisse.filter(e => !e.ok || e.komoot_fehler).map(e => (e.fehler ? e.fehler : `Bei Komoot rückgängig machen nicht möglich: ${e.komoot_fehler}`));
      await uiAlert({title: "Rückgängig machen nicht überall möglich", text: t.slice(0, 5).join("\n\n")});
    }
    return r.zurueckgesetzt > 0;
  } catch (e) {
    gfFail("Rückgängig machen", e);
    return false;
  }
}
async function gfLogOpen(parent) {
  const m = uiModal(`<h3>Protokoll der Tournamen</h3><div id="gflb" class="gfnb"><p class="mut" role="status">Wird geladen …</p></div><div class="uifoot"><button type="button" class="btn" data-x>Schließen</button></div>`);
  m.querySelector("[data-x]").onclick = () => m.remove();
  const body = m.querySelector("#gflb");
  let d;
  try {
    d = await api("/api/guides/rename-log");
  } catch (e) {
    body.innerHTML = errCard(e);
    return;
  }
  if (!d.items.length) {
    body.innerHTML = '<p id="gflnone">Noch keine Tour umbenannt.</p>';
    return;
  }
  const by = new Map();
  d.items.forEach(x => (by.get(x.batch) || by.set(x.batch, []).get(x.batch)).push(x));
  body.innerHTML = "";
  [...by.entries()].slice(0, 20).forEach(([batch, es]) => {
    const sec = document.createElement("section"),
      open = es.filter(x => !x.undone),
      nK = open.filter(x => x.komoot).length;
    sec.className = "gflb";
    sec.dataset.batch = batch;
    sec.innerHTML = `<div class="gflh"><b></b><button type="button" class="btn sm ghost" data-undo></button></div><ul class="gfkonf"></ul>`;
    sec.querySelector("b").textContent = `${gfDatum(es[0].ts)} · ${es.length === 1 ? "1 Tour" : es.length + " Touren"}`;
    const ub = sec.querySelector("[data-undo]");
    ub.textContent = "Rückgängig machen";
    ub.hidden = !open.length;
    ub.onclick = async () => {
      if (await gfUndo({batch}, nK)) (m.remove(), parent && parent.remove(), gfReload("Alte Namen wiederhergestellt"));
    };
    es.forEach(x => {
      const li = document.createElement("li");
      li.setAttribute("translate", "no");
      li.textContent = `${x.old} → ${x.new}${x.komoot ? " · bei Komoot" : ""}${x.undone ? " · zurückgesetzt" : ""}`;
      sec.querySelector("ul").append(li);
    });
    body.append(sec);
  });
}
