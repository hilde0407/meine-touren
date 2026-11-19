/* 3.40.0 Verwaltung → Sicherung & Zugang: „Sicherung zurückspielen“ (nur Administratoren).
   Schritt 1 (im Bereich, einklappbar): Quelle wählen – Sicherung des Servers aus der Liste oder ZIP hochladen.
   Schritt 2 (Dialog): Ergebnis der Vorprüfung, was ersetzt wird und was nicht, Häkchen, dann erst der Knopf „Jetzt zurückspielen“.
   Der Server spielt nur zurück, was er unmittelbar vorher geprüft hat (Token aus der Vorprüfung). Kein window.confirm.
   Texte stehen deutsch im Markup und werden von der Übersetzungsschicht (00-i18n.js, Zeilen in 00-i18n-neu.js) ersetzt; Zahlen und Namen stehen in eigenen Elementen. */
const rsMb = n => (n >= 1e8 ? nf(n / 1e9, 2) + " GB" : n >= 1e5 ? nf(n / 1e6, 1) + " MB" : Math.max(1, Math.round(n / 1e3)) + " kB");
const rsDt = ts => fmtDatumKurz(ts, {zeit: true});
const rsAlter = h => (h == null ? "" : h < 1 ? "(weniger als eine Stunde alt)" : h < 48 ? `(vor ${Math.round(h)} Stunden)` : `(vor ${Math.round(h / 24)} Tagen)`);
const RS_ZEILEN = [["touren", "Touren"], ["strecken", "Strecken (GPX-Dateien)"], ["reisen", "Reisen"], ["plaene", "Geplante Touren"], ["layouts", "Seitenlayouts"]];
const rsZahl = v => (v == null ? "–" : String(v));

function rsTabelle(kopfA, a, kopfB, b) {
  return `<table class="rstab"><thead><tr><td></td><th scope="col">${kopfA}</th><th scope="col">${kopfB}</th></tr></thead><tbody>${RS_ZEILEN.map(
    ([k, t]) => `<tr><th scope="row">${t}</th><td>${rsZahl(a[k])}</td><td>${rsZahl(b[k])}</td></tr>`
  ).join("")}</tbody></table>`;
}

/* Dialog im Muster von uiConfirm (gleiche Klassen): Hintergrund inert, Tab bleibt im Dialog, Esc schließt (außer während des Zurückspielens), Fokus danach zurück zum Auslöser. */
function rsDialog(v, trigger, onDone) {
  const host = document.createElement("div");
  host.className = "uidlg";
  const box = document.createElement("div");
  box.className = "uibox danger rsbox";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  box.setAttribute("aria-labelledby", "rsdt");
  box.setAttribute("aria-describedby", "rsdd");
  box.tabIndex = -1;
  const z = v.zahlen, b = v.benutzer || {};
  const wem = b.ohne_angabe
    ? `<p class="rshin"><span aria-hidden="true">ℹ</span> <span>Die Sicherung nennt keinen Benutzer. Sie wird in dein Konto zurückgespielt.</span></p>`
    : b.name
      ? `<div class="rsk"><span>Gehört zu</span><b>${esc(b.name)}</b></div>`
      : "";
  box.innerHTML = `<h2 id="rsdt">Sicherung zurückspielen</h2>
  <div class="uitext" id="rsdd">
   <div id="rsv">
    <p class="rsgut"><span aria-hidden="true">✓</span> <span>Geprüft: Die Sicherung ist lesbar und vollständig.</span></p>
    <div class="rsk"><span>Sicherung vom</span><b>${v.erstellt_ts ? rsDt(v.erstellt_ts) : "–"}</b><span class="mut">${rsAlter(v.alter_h)}</span></div>
    <div class="rsk"><span>Datei</span><code class="rsfn">${esc(v.name)}</code><span class="mut">${rsMb(v.groesse)}</span></div>
    ${wem}
    ${v.sicherheitskopie ? `<p class="rshin"><span aria-hidden="true">ℹ</span> <span>Das ist eine Sicherheitskopie, die vor einem früheren Zurückspielen angelegt wurde.</span></p>` : ""}
    ${rsTabelle("In der Sicherung", z.sicherung, "Heute", z.jetzt)}
    <h3>Das wird ersetzt</h3>
    <p>Touren, Notizen, Ziele, geplante Touren, Seitenlayouts und Einstellungen. Alles, was seit dieser Sicherung dazugekommen ist oder geändert wurde, geht verloren.</p>
    <h3>Das bleibt, wie es ist</h3>
    <ul class="rsul"><li>Fotodateien – sie sind nicht in der Sicherung.</li><li>Zwischenspeicher (geladene Strecken, Vorschaubilder).</li><li>Der Schlüssel für gespeicherte Zugangsdaten (secret.key).</li><li>Benutzer, Passwörter und Anmeldungen.</li><li>Vorhandene Strecken-Dateien: Fehlende werden ergänzt, keine wird überschrieben.</li></ul>
    ${v.zugangsdaten === "bleiben" ? `<p class="rshin"><span aria-hidden="true">ℹ</span> <span>Die Sicherung enthält keine Zugangsdaten. Die heute gespeicherten bleiben erhalten.</span></p>` : ""}
    <p class="rshin"><span aria-hidden="true">ℹ</span> <span>Vorher wird der heutige Stand automatisch gesichert. Damit kannst du diesen Schritt hier wieder rückgängig machen.</span></p>
    <label class="rschk"><input type="checkbox" id="rsok"><span>Ich habe verstanden, dass der heutige Stand ersetzt wird</span></label>
   </div>
   <div id="rsr" role="status" aria-live="polite"></div>
  </div>
  <div class="uifoot"><button type="button" class="btn ghost" id="rsno">Abbrechen</button><button type="button" class="btn alt uidanger" id="rsyes" data-danger disabled>Jetzt zurückspielen</button></div>`;
  host.appendChild(box);
  const inerted = [];
  [...document.body.children].forEach(el => {
    if (!el.inert) { el.inert = true; inerted.push(el); }
  });
  document.body.appendChild(host);
  const q = s => box.querySelector(s);
  const ok = q("#rsok"), yes = q("#rsyes"), no = q("#rsno"), res = q("#rsr");
  let busy = false, fertig = false, closed = false;
  const close = () => {
    if (closed || busy) return;
    closed = true;
    host.removeEventListener("keydown", key, true);
    host.remove();
    inerted.forEach(el => (el.inert = false));
    if (fertig) { location.reload(); return; }
    onDone();                                                // gibt den Auslöser wieder frei (er war während der Prüfung gesperrt) – erst danach kann er den Fokus bekommen
    if (trigger && trigger.isConnected && typeof trigger.focus === "function") { try { trigger.focus(); } catch (e) {} }
  };
  const key = e => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === "Tab") {
      const f = [...box.querySelectorAll("button:not([disabled]), input:not([disabled])")].filter(el => el.offsetParent !== null);
      if (!f.length) { e.preventDefault(); box.focus(); return; }
      const i = f.indexOf(document.activeElement);
      if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && (i === f.length - 1 || i < 0)) { e.preventDefault(); f[0].focus(); }
    }
  };
  host.addEventListener("keydown", key, true);
  host.addEventListener("mousedown", e => { if (e.target === host) close(); });
  ok.onchange = () => (yes.disabled = !ok.checked);
  no.onclick = close;
  yes.onclick = async () => {
    if (!ok.checked || busy) return;
    busy = true;
    yes.disabled = no.disabled = ok.disabled = true;
    box.setAttribute("aria-busy", "true");
    res.innerHTML = `<p class="rslauf"><span>Wird zurückgespielt … Bitte die Seite nicht schließen.</span></p>`;
    let r = null, err = "";
    try {
      r = await api("/api/restore/run", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({id: v.id, token: v.token, bestaetigt: true})});
    } catch (e) {
      err = String(e.message || e);
    }
    busy = false;
    box.removeAttribute("aria-busy");
    q("#rsv").hidden = true;
    yes.hidden = true;
    no.disabled = false;
    if (r) {
      fertig = true;
      box.classList.remove("danger");
      res.innerHTML = `<p class="rsgut" id="rsdone"><span aria-hidden="true">✓</span> <span>Fertig: Die Sicherung wurde zurückgespielt.</span></p>
       ${rsTabelle("Vorher", r.vorher, "Jetzt", r.nachher)}
       ${r.strecken_neu ? `<div class="rsk"><span>Ergänzte Strecken-Dateien</span><b>${r.strecken_neu}</b></div>` : ""}
       <p><span>Der vorherige Stand liegt als Sicherheitskopie in der Liste:</span> <code class="rsfn">${esc(r.sicherheitskopie)}</code></p>
       ${(r.hinweise || []).map(h => `<p class="bad"><span aria-hidden="true">⚠</span> <span>${esc(h)}</span></p>`).join("")}
       <p class="mut">Mit „Seite neu laden“ siehst du überall den neuen Stand.</p>`;
      no.textContent = "Seite neu laden";
      no.className = "btn";
    } else {
      res.innerHTML = `<p class="bad" id="rsfail" role="alert"><span aria-hidden="true">✗</span> <span>${esc(err)}</span></p>`;
      no.textContent = "Schließen";
    }
    no.focus();
  };
  no.focus();
}

async function rsInit() {
  const slot = $("#rsbox");
  if (!slot || slot.dataset.init) return;
  slot.dataset.init = "1";
  slot.innerHTML = `<details class="rsd" id="rsd"><summary>Sicherung zurückspielen</summary>
   <div class="rsb">
    <p class="mut">Setzt deine Touren, Notizen, Pläne und Einstellungen auf den Stand einer Sicherung zurück. Die Sicherung wird zuerst geprüft, und der heutige Stand wird vorher automatisch gesichert.</p>
    <fieldset class="rsl"><legend>Sicherung auf diesem Server</legend><div id="rsls" class="rsls"><span class="mut">Lade …</span></div></fieldset>
    <div class="rsup"><label for="rsf">Oder eine Sicherungsdatei (ZIP) hochladen</label><input type="file" id="rsf" accept=".zip,application/zip"><small class="mut" id="rsmax"></small></div>
    <div class="row g8"><button class="btn alt" id="rsgo" type="button" disabled>Sicherung prüfen …</button><span id="rsmsg" class="mut" role="status" aria-live="polite"></span></div>
    <p class="bad" id="rserr" role="alert" hidden></p>
    <p class="mut fs13">Ein Umzugspaket lässt sich hier nicht zurückspielen – dafür bleibt das Skript auf dem Server.</p>
   </div></details>`;
  const ls = $("#rsls"), file = $("#rsf"), go = $("#rsgo"), msg = $("#rsmsg"), err = $("#rserr");
  let maxMb = 2048;
  const fail = t => { err.innerHTML = `<span aria-hidden="true">✗</span> <span>${esc(t)}</span>`; err.hidden = false; };
  const sel = () => ls.querySelector("input[name=rsq]:checked");
  const upd = () => (go.disabled = !(sel() || (file.files && file.files.length)));
  const load = async () => {
    let d;
    try {
      d = await api("/api/restore/list");
    } catch (e) {
      if (ls.isConnected) ls.innerHTML = `<span class="bad">${esc(e.message || e)}</span>`;
      return;
    }
    if (!ls.isConnected) return;
    const gewaehlt = sel() ? sel().value : null;             // Auswahl über das Neuladen der Liste hinweg behalten
    maxMb = d.max_mb || maxMb;
    $("#rsmax").innerHTML = `<span>Höchstens</span> <span>${maxMb} MB</span>`;
    ls.innerHTML = d.sicherungen.length
      ? d.sicherungen.map((x, i) => `<label class="rsi"><input type="radio" name="rsq" value="${esc(x.id)}" aria-describedby="rsi${i}"><span class="rsn">${rsDt(x.ts)}</span><span class="mut rsg">${rsMb(x.groesse)}</span><span class="rsx" id="rsi${i}">${x.sicherheitskopie ? `<span class="rstag">Sicherheitskopie vor dem Zurückspielen</span>` : ""}<code class="mut rsfn">${esc(x.name)}</code></span></label>`).join("")
      : `<span class="mut">Auf diesem Server liegt noch keine Sicherung.</span>`;
    ls.querySelectorAll("input[name=rsq]").forEach(r => {
      if (r.value === gewaehlt) r.checked = true;
      r.onchange = () => { file.value = ""; err.hidden = true; upd(); };
    });
    upd();
  };
  file.onchange = () => {
    const s = sel();
    if (s && file.files.length) s.checked = false;
    err.hidden = true;
    upd();
  };
  go.onclick = async () => {
    err.hidden = true;
    go.disabled = true;
    let id = sel() ? sel().value : null, hochgeladen = false;
    try {
      if (!id) {
        const f = file.files[0];
        if (f.size > maxMb * 1e6) throw new Error(`Die Datei ist zu groß (höchstens ${maxMb} MB). Größere Sicherungen bitte in den Sicherungsordner des Servers legen.`);
        msg.textContent = "Wird hochgeladen …";
        id = (await api("/api/restore/upload?name=" + encodeURIComponent(f.name), {method: "POST", headers: {"content-type": "application/zip"}, body: f})).id;
        hochgeladen = true;
      }
      msg.textContent = "Prüfe …";
      const v = await api("/api/restore/check", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({id})});
      msg.textContent = "";
      rsDialog(v, go, () => {
        if (hochgeladen) { api("/api/restore/upload", {method: "DELETE"}).catch(() => {}); file.value = ""; }
        upd();
        load();
      });
    } catch (e) {
      msg.textContent = "";
      fail(String(e.message || e));
      if (hochgeladen) { api("/api/restore/upload", {method: "DELETE"}).catch(() => {}); file.value = ""; }
      upd();
    }
  };
  $("#rsd").addEventListener("toggle", e => { if (e.target.open) load(); });
  load();
}
