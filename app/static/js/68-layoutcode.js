/* =====================  3.36.0 Ansichten teilen: Layoutcode und Link  =====================
   Ein Layoutcode ist die Export-Datei einer Ansicht (54-ansichten.js, slExportDoc) als kompakter Text: „MTA1.“ + JSON (UTF-8) als base64url. Er enthält nur das Layout und die Einstellungen der Bausteine
   (auch eigene Titel und Notiztexte), nie Tourdaten, Fotos oder Zugangsdaten, und gibt keinen Zugriff auf Daten. Der Server prüft jeden Code beim Einfügen mit denselben Regeln wie eine Datei
   (POST /api/layout/code → app/layout.py check_export): erlaubte Felder, Kennungen, Größen, Whitelist der Bausteine.
   „Link kopieren“ erzeugt <Adresse der App>#/layoutcode/<Code>; öffnet jemand den Link, wird die passende Seite aufgerufen und der Import-Dialog mit dem Code geöffnet (angemeldet, nie ohne Rückfrage). */
const SL_CODE_PREFIX = "MTA1.";
const SL_CODE_MAX = 100000;                                               // wie CODE_MAX im Server
const SL_LINK_WARN = 8000;                                                // sehr lange Links kürzen manche Programme
function slB64u(text) {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function slUnB64u(t) {
  const b = atob(t.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (t.length % 4)) % 4)), a = new Uint8Array(b.length);
  for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i);
  return new TextDecoder().decode(a);
}
/* Code einer Ansicht (ohne Zeitstempel, damit derselbe Stand immer denselben Code ergibt) */
function slCodeMake(fam, id) {
  const d = slExportDoc(fam, id);
  delete d.exported;
  return SL_CODE_PREFIX + slB64u(JSON.stringify(d));
}
const slCodeLink = code => `${location.origin}${location.pathname}#/layoutcode/${code}`;
/* Seite des Codes (nur zum Navigieren; geprüft wird immer auf dem Server) */
function slCodePage(code) {
  try {
    const t = String(code).trim().split("layoutcode/").pop().replace(/\s+/g, "");
    return String(JSON.parse(slUnB64u(t.slice(SL_CODE_PREFIX.length))).page || "");
  } catch (e) {
    return "";
  }
}
async function slCheckCode(text) {
  const bad = m => ({ok: false, errors: [m], ignored: []});
  if (String(text).length > SL_CODE_MAX + 2000) return bad("Der Layoutcode ist zu lang für eine Ansicht.");
  try {
    const r = await fetch("/api/layout/code", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({code: String(text)}), credentials: "same-origin"});
    if (!r.ok) throw new Error(String(r.status));
    return await r.json();
  } catch (e) {
    return bad("Die Prüfung ist nicht möglich (keine Verbindung zum Server?). Es wurde nichts übernommen.");
  }
}
async function slCopyText(text, ta) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) {}
  try {
    const t = ta || Object.assign(document.createElement("textarea"), {value: text});
    if (!ta) document.body.appendChild(t);
    const v = t.value;
    t.value = text;
    t.select();
    const ok = document.execCommand("copy");
    t.value = v;
    if (!ta) t.remove();
    return ok;
  } catch (e) {
    return false;
  }
}
function slCodeDialog(fam, id) {
  const v = slVm(fam).find(x => x.id === id);
  if (!v) return;
  slModal("Ansicht teilen", (body, close) => {
    const code = slCodeMake(fam, id), n = code.length, link = slCodeLink(code);
    body.innerHTML = `<p class="slcatin"><b class="slcn"></b></p><p class="mut slcatin">Wer den Code bekommt, kann ihn bei „Ansichten“ → „Importieren …“ einfügen oder den Link öffnen. Der Code enthält nur die Anordnung und die Einstellungen der Bausteine ` +
      `(auch eigene Titel und Notizen), keine Touren, Fotos oder Zugangsdaten.</p>` +
      `<div class="slfs"><label for="slcode">Layoutcode</label><textarea id="slcode" rows="5" readonly spellcheck="false" aria-describedby="slcodeh"></textarea>` +
      `<p class="mut slimphint" id="slcodeh">${n.toLocaleString("de-DE")} Zeichen</p>${n > SL_LINK_WARN ? `<p class="mut slimphint">Der Link wäre sehr lang. Manche Programme kürzen so lange Links, dann den Code selbst weitergeben.</p>` : ""}</div>` +
      `<div class="slcodego"><button type="button" class="btn sm" data-a="copy">Code kopieren</button><button type="button" class="btn ghost sm" data-a="link">Link kopieren</button></div>` +
      `<p class="slcodeok" id="slcodeok" role="status" aria-live="polite"></p>` +
      `<div class="uifoot"><button type="button" class="btn ghost" data-close>Schließen</button></div>`;
    body.querySelector(".slcn").textContent = v.name;
    const ta = body.querySelector("#slcode"), ok = body.querySelector("#slcodeok");
    ta.value = code;
    const say = t => {
      ok.textContent = "";
      setTimeout(() => (ok.textContent = t), 30);
    };
    ta.addEventListener("focus", () => ta.select());
    body.addEventListener("click", async e => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.hasAttribute("data-close")) return close();
      if (b.dataset.a === "copy") say((await slCopyText(code, ta)) ? "Code kopiert" : "Kopieren nicht möglich: Der Code ist markiert, bitte mit Strg+C kopieren.");
      else if (b.dataset.a === "link") {
        const done = await slCopyText(link);
        say(done ? "Link kopiert" : "Kopieren nicht möglich: Bitte den Code markieren und mit Strg+C kopieren.");
        if (!done) ta.select();
      }
    });
  }, "slcode");
}

/* ---------- Link öffnen: #/layoutcode/<Code> ---------- */
const SL_CODE_PAGES = {uebersicht: "#/dash", statistik: "#/stats", reisen: "#/trips", fotos: "#/photos", karte: "#/map"};
VIEWS.layoutcode = async name => {
  const code = String(name || ""), main = document.getElementById("main"), page = slCodePage(code);
  let hash = SL_CODE_PAGES[page] || "";
  if (page === "tour" && TOURS.length) hash = "#/tour/" + encodeURIComponent(TOURS[0].id);
  if (!slCan() || !hash) {
    main.innerHTML = `<div class="card"><h2>Layoutcode</h2><p>${!slCan() ? "Mit diesem Zugang lassen sich keine Ansichten importieren." : page === "reise" ? "Dieser Code gehört zu einer Reise-Seite. Öffne eine Reise, der Import öffnet sich dort." : "Dieser Code kann nicht geöffnet werden."}</p></div>`;
    if (slCan() && page === "reise") SL.codePending = {code, page, fam: "reise"};
    return;
  }
  SL.codePending = {code, page, fam: page === "tour" ? "tour" : page};
  location.replace(hash);
};
/* Auf der passenden Seite (aus slOpener): Import-Dialog mit dem Code öffnen, einmal */
function slCodePending() {
  const p = SL.codePending;
  if (!p || SL.edit || p.fam !== SL.fam || !slCan()) return;
  SL.codePending = null;
  setTimeout(() => !document.querySelector(".sldlg") && slImportDialog(SL.fam, null, p.code), 400);
}
