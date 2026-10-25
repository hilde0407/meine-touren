/* ---------- Verwaltung ---------- */
const STATUS_DE = {
  local: "lokal übernommen",
  new: "noch nicht übernommen",
  in_komoot: "bereits in Komoot",
  uploaded: "hochgeladen",
  skipped_dup: "bereits in Komoot",
  no_gps: "ohne GPS",
};
VIEWS.admin = async (_, q) => {
  const [st, w, s, pi, pf, dv] = await Promise.all([
    api("/api/status"),
    api("/api/workouts"),
    api("/api/settings"),
    api("/api/photo-info"),
    api("/api/portals"),
    api("/api/devices").catch(() => ({garmin: {}, suunto: {}})),
  ]);
  const gm = dv.garmin || {},
    su = dv.suunto || {},
    sunres = q && q.get("suunto");
  const sv = pf.portals.find(x => x.id === "strava") || {},
    sres = q && q.get("strava");
  const pend = w.filter(x => x.status === "new");
  const f = (k, l, t = "text", ph = "") =>
    `<div class="field"><label>${l}</label><input data-k="${k}" type="${t}" value="${esc(s[k])}" placeholder="${ph}"></div>`;
  $("#main").innerHTML = `
  <div class="sec admin" style="margin-top:0"><h2>Verwaltung</h2><span class="sub" id="st"></span><span class="sp"></span><span class="mut" style="font-size:13px" id="ver"></span></div>
  <div id="upd"></div><div class="panel" id="hlt" style="margin-bottom:16px"><h2>Zustand</h2><p class="mut">wird geprüft …</p></div>
  <div class="grid g2">
   <div class="panel"><h2>Komoot <span class="mut" style="font:400 16px var(--b)">(optional)</span></h2><p class="mut">${nf(st.tours, 0)} Touren (davon ${nf(st.local_tours, 0)} nur lokal) · ${nf(st.routes, 0)} Strecken lokal gespeichert. Karten und Tourdetails nutzen immer die lokal gespeicherten Strecken; Komoot wird nur zum Laden und Hochladen gebraucht.</p>
    <div class="row"><button class="btn" data-job="refresh">Komoot aktualisieren</button><button class="btn alt" data-job="tours">Nur Touren</button><button class="btn alt" data-job="routes" title="Fehlende Strecken von Komoot lokal speichern">Strecken lokal sichern</button><button class="btn alt" data-job="geo" title="Land, Bundesland und Ort jeder Tour per OpenStreetMap bestimmen (für Suche und Filter)">Regionen bestimmen</button><button class="btn alt" id="diag">Komoot-Test</button></div>
    <p class="mut" style="font-size:13px">„Aktualisieren“ lädt neue Touren und deren Strecken von Komoot und liest die Fotos ein. Es wird <b>nichts</b> zu Komoot hochgeladen. <span id="dres"></span></p>
    <div class="field"><label>Komoot-E-Mail</label><input data-k="komoot_email" value="${esc(s.komoot_email)}"></div><div class="field"><label>Komoot-Passwort</label><input data-k="komoot_password" type="password" value="${esc(s.komoot_password)}"></div></div>
   <div class="panel"><h2>Fotos</h2><p class="mut">${nf(pi.count, 0)} Fotos in der Bibliothek, ${nf(pi.assigned, 0)} einer Tour zugeordnet.<br>Bibliothek: <code>${esc(pi.lib_dir)}</code></p>
    <div class="row"><button class="btn" id="pdirb">Ordner auswählen und hochladen …</button><button class="btn alt" data-job="photos">Bibliothek neu einlesen</button></div>
    <input type="file" id="pdir" webkitdirectory multiple hidden><div id="pup2" style="display:none;margin-top:10px"><div class="stack" style="height:10px"><div id="pbar" style="width:0;background:var(--acc)"></div></div><div class="row" style="margin-top:6px"><span id="ptxt" class="mut"></span><span class="sp"></span><button class="btn alt sm" id="pstop">Abbrechen</button></div></div>
    <details><summary>Weitere Wege (SMB-Ordner, Mac-Skript)</summary><div class="row" style="margin:8px 0"><button class="btn alt sm" data-job="photo-import" ${pi.folder_exists ? "" : 'disabled title="Quellordner nicht gefunden"'}>Fotos aus Ordner übernehmen</button></div>
    <p class="mut" style="font-size:13px">„Übernehmen“ verkleinert die Originale aus <code>${esc(pi.source_dir)}</code> ${pi.folder_exists ? "" : "<b class='bad'>(Ordner nicht gefunden)</b>"} für die Bildschirmdarstellung und legt sie in der Bibliothek ab. Alternativ vom Mac aus mit dem Skript <code>mac/fotos_senden.sh</code>.</p></details><p class="mut" style="font-size:13px">Beim Hochladen werden die Bilder <b>im Browser</b> für die Bildschirmdarstellung verkleinert; nur die kleinen Dateien gehen übers Netz. Originale werden nie verändert.</p>
    <details><summary>Bildeinstellungen</summary>${f("photo_max_side", "Längste Bildseite (Pixel)", "number")}${f("photo_quality", "JPEG-Qualität (1–95)", "number")}${f("photo_margin_min", "Zuordnung: Toleranz vor/nach der Tour (Min.)", "number")}${f("photo_only_tracked", "Beim Foto-Import nur Fotos mit passender GPS-Strecke übernehmen (1 = ja, 0 = alle)")}${f("camera_utc_offset_h", "Kamerazeit-Versatz zu UTC in Stunden (leer = lokale Zeit)")}${f("slideshow_seconds", "Diashow: Sekunden pro Bild", "number")}</details></div></div>
  <div class="panel" style="margin-top:40px"><h2>Portale <span class="mut" style="font:400 16px var(--b)">(Upload)</span></h2>
   <p class="mut">Touren liegen lokal vor und können einzeln (Tourdetail → „⬆ Hochladen“) oder gesammelt (Zepp/Dateien unten) zu Komoot und Strava gesendet werden – immer nur auf deinen ausdrücklichen Wunsch.</p>
   ${sres ? `<p class="${sres === "ok" ? "ok" : "bad"}"><b>${sres === "ok" ? "Strava ist verbunden ✓" : "Strava: " + esc(sres)}</b></p>` : ""}
   <div class="grid g2"><div><h3 style="margin-top:0">Strava ${sv.connected ? `<span class="ok" style="font-size:15px">✓ verbunden${sv.account ? " als " + esc(sv.account) : ""}</span>` : ""}</h3>
    ${f("strava_client_id", "Client-ID")}${f("strava_client_secret", "Client-Secret", "password")}
    <div class="row"><button class="btn" id="sconn">${sv.connected ? "Neu verbinden" : "Mit Strava verbinden"}</button>${sv.connected ? `<button class="btn alt" id="sdis">Trennen</button>` : ""}<span id="sres"></span></div></div>
    <ol class="mut" style="padding-left:18px;margin-top:0"><li>Auf <a target="_blank" href="https://www.strava.com/settings/api">strava.com/settings/api</a> eine eigene App anlegen (Name frei).</li><li>„Authorization Callback Domain“: <code>${esc(location.hostname)}</code> (bei Fehlermeldung: <code>localhost</code>).</li><li>Client-ID und -Secret hier eintragen, „Einstellungen speichern“, dann „Mit Strava verbinden“.</li><li>Falls Strava nach der Freigabe nicht zurückfindet: Adresse der leeren Seite kopieren und hier einfügen:<div class="row" style="margin-top:6px"><input id="scode" placeholder="http://…?code=…" style="flex:1"><button class="btn alt sm" id="scodeb">Code einlösen</button></div></li></ol></div>
   <details><summary>Komoot</summary><p class="mut">Zugang siehe Panel „Komoot“ oben. Touren, die von Komoot stammen, können nicht erneut zu Komoot hochgeladen werden; zu Strava schon.</p></details></div>
  <div class="panel" style="margin-top:40px"><h2>Zepp-Import <span class="mut" style="font:400 16px var(--b)">(optional)</span></h2>
   <p class="mut">Holt GPS-Trainings aus deinem Zepp-Konto (als GPX-Dateien). Ausgewählte Trainings werden lokal als Tour gespeichert (Karte, Statistik); ein Upload zu Komoot/Strava passiert <b>nur</b>, wenn du es unten ausdrücklich anhakst.</p>
   <div class="row"><button class="btn" data-job="export">Zepp-Import starten</button><button class="btn alt" data-job="elev-local" title="Falsche Höhenwerte (z. B. Platzhalter) aus bereits importierten Touren entfernen und Auf-/Abstieg neu berechnen">Höhenmeter neu berechnen</button><button class="btn alt" id="ztest">Token testen</button><span id="zres"></span></div>
   <details><summary>Zepp-Zugang / Token holen</summary><div class="grid g2"><div>${f("zepp_email", "E-Mail (nur wenn dein Konto ein Zepp-Passwort hat)")}${f("zepp_password", "Passwort", "password")}${f("zepp_token", "Token (für Mi-/Google-/Apple-Konten)", "password")}${f("zepp_host", "Server (leer = automatisch)")}</div>
    <ol class="mut" style="padding-left:18px"><li>Diesen Knopf in die <b>Lesezeichenleiste</b> ziehen: <a id="bm" class="btn alt sm" href="#">Token an Meine Touren</a></li><li>Im selben Browser <a target="_blank" href="https://user.huami.com/privacy2/index.html?platform_app=com.xiaomi.hm.health&loginPlatform=web">user.huami.com/privacy2</a> öffnen, anmelden und dort <b>nichts</b> anklicken (die Seite bietet „Konto löschen“ an).</li><li>Das Lesezeichen anklicken – das Token wird gespeichert und geprüft.</li></ol></div></details>
   <h3 style="margin-top:14px">Zepp-Trainings ${pend.length ? "noch nicht übernommen" : ""}</h3>
   <p class="mut">${w.length} exportiert · ${w.filter(x => x.status === "local").length} lokal übernommen · ${w.filter(x => x.status === "in_komoot" || x.status === "uploaded").length} bereits in Komoot · ${w.filter(x => x.status === "no_gps").length} ohne GPS · ${pend.length} noch offen</p>
   ${
     pend.length
       ? `<details${pend.length <= 8 ? " open" : ""}><summary>${pend.length} offene Trainings anzeigen</summary><div style="max-height:300px;overflow:auto"><table><tr><th></th><th>Datum</th><th>Sport</th><th class="n">km</th></tr>${pend.map(x => `<tr><td><input type="checkbox" class="pk" value="${x.trackid}"></td><td>${dateS(x.date)} ${timeS(x.date)}</td><td>${sName(x.sport)}</td><td class="n">${nf(x.dist_m / 1000, 1)}</td></tr>`).join("")}</table></div></details>
   <div class="row" style="margin-top:10px"><button class="btn alt sm" id="pall">Alle wählen</button><button class="btn alt sm" id="pdry">Probelauf</button><button class="btn" id="plocal">Lokal übernehmen</button></div>
   <div class="row" style="margin-top:8px"><span class="mut">Zusätzlich hochladen zu:</span>${pf.portals.map(p => `<label class="chk" style="margin:0"><input type="checkbox" class="zp" value="${p.id}" ${p.connected ? "" : "disabled"}> ${p.name}${p.connected ? "" : `<span class="mut" style="font-size:12px"> (${p.id === "komoot" ? "Zugang fehlt: im Panel „Komoot“ (Komoot-E-Mail und -Passwort) speichern" : "nicht verbunden: bei „Portale“ verbinden"})</span>`}</label>`).join("")}<button class="btn" id="pup">Übernehmen und hochladen</button></div>
   <div class="field" style="margin-top:8px"><label>Neue Zepp-Trainings automatisch lokal übernehmen (ohne Upload)</label><select data-k="zepp_auto_adopt"><option value="0">aus</option><option value="1">an</option></select></div>`
       : ""
   }
   </div>
  <div class="panel" style="margin-top:40px"><h2>Garmin, Suunto &amp; andere Uhren <span class="mut" style="font:400 16px var(--b)">(Import)</span></h2>
   <p class="mut">Aktivitäten werden <b>lokal</b> als Touren gespeichert (Karte, Statistik, Fotozuordnung), mit Doppelten-Prüfung. Hochgeladen wird nur, wenn du es unten ausdrücklich ankreuzt.<br>
   <b>Tipp:</b> Ist deine Uhr in Garmin Connect bzw. der Suunto-App mit <b>Komoot</b> verbunden, kommen die Touren ohnehin über „Komoot aktualisieren“.</p>
   <h3>Dateien importieren <span class="ok" style="font-size:14px">funktioniert immer</span></h3>
   <div class="field"><label>FIT-, GPX-, TCX- oder ZIP-Dateien (mehrere möglich; ZIP darf viele Aktivitäten enthalten, auch der komplette Garmin-Export)</label><div class="row"><input type="file" id="files" multiple accept=".fit,.gpx,.tcx,.zip,.gz"><span class="mut">zusätzlich zu:</span>${pf.portals.map(p => `<label class="chk" style="margin:0"><input type="checkbox" class="fp" value="${p.id}" ${p.connected ? "" : "disabled"}> ${p.name}${p.connected ? "" : `<span class="mut" style="font-size:12px"> (${p.id === "komoot" ? "Zugang fehlt: im Panel „Komoot“ (Komoot-E-Mail und -Passwort) speichern" : "nicht verbunden: bei „Portale“ verbinden"})</span>`}</label>`).join("")}<button class="btn alt sm" id="upl">Importieren</button><label style="margin:0"><input type="checkbox" id="dry"> Probelauf</label></div></div>
   <details><summary>So kommst du an die Dateien</summary><ul class="mut" style="padding-left:18px">
    <li><b>Garmin, alles auf einmal:</b> auf <a target="_blank" rel="noopener" href="https://www.garmin.com/account/datamanagement/">garmin.com/account/datamanagement</a> „Daten exportieren“ anfordern (Garmin schickt nach ein bis zwei Tagen eine ZIP-Datei per E-Mail) und die ZIP-Datei hier importieren.</li>
    <li><b>Garmin, einzelne Aktivität:</b> connect.garmin.com → Aktivität öffnen → Zahnrad ⚙ → „Original exportieren“ (FIT in einer ZIP) oder „Als GPX exportieren“.</li>
    <li><b>Suunto:</b> Suunto-App → Training öffnen → ⋮ (oben rechts) → Exportieren → FIT (alle Daten) oder GPX. Trainings ohne GPS lassen sich nur als FIT exportieren und werden hier ohnehin übersprungen.</li>
    <li><b>Große ZIP-Dateien</b> (über 1 GB): statt Hochladen in den Eingangsordner legen: <code>${esc(st.inbox || "")}/touren</code> – sie werden automatisch übernommen und danach nach „erledigt“ verschoben.</li>
    <li>Andere Hersteller (Polar, Coros, Wahoo, Amazfit …) exportieren ebenfalls FIT oder GPX – das geht genauso.</li></ul></details>
   <div class="grid g2" style="margin-top:14px">
    <div><h3 style="margin-top:0">Garmin-Konto ${gm.connected ? `<span class="ok" style="font-size:15px">✓ verbunden${gm.email ? " als " + esc(gm.email) : ""}</span>` : ""} <span class="mut" style="font-size:12px">experimentell</span></h3>
     ${
       gm.available === false
         ? `<p class="mut">Nicht verfügbar: ${esc(gm.why)}</p>`
         : gm.connected
           ? `<p class="mut">${nf(gm.imported || 0, 0)} Aktivitäten übernommen${gm.checked ? ", zuletzt geprüft " + new Date(+gm.checked * 1000).toLocaleString("de-DE") : ""}.</p>
     <div class="field"><label>Nur Aktivitäten ab Datum (JJJJ-MM-TT, leer = alle)</label><input data-k="garmin_since" value="${esc(s.garmin_since)}" placeholder="2024-01-01"></div>
     <div class="field"><label>Neue Aktivitäten täglich automatisch übernehmen</label><select data-k="garmin_auto"><option value="0">aus</option><option value="1">an</option></select></div>
     <div class="row"><button class="btn" id="gsync">Jetzt importieren</button><button class="btn alt" id="gdis">Trennen</button><span id="gres"></span></div>`
           : `<p class="mut">Anmeldung wie im Browser (E-Mail und Passwort von Garmin Connect). Das Passwort wird <b>nicht gespeichert</b>, nur der Anmelde-Schlüssel (verschlüsselt). Konten mit Google-/Apple-Login haben kein Garmin-Passwort – dann bitte den Dateiweg nehmen.</p>
     <div class="field"><label>Garmin-E-Mail</label><input id="gem" autocomplete="off"></div><div class="field"><label>Garmin-Passwort</label><input id="gpw" type="password" autocomplete="off"></div>
     <div class="field" id="gmfa" style="display:none"><label>Bestätigungscode (Zwei-Faktor, per E-Mail/App)</label><input id="gcode" inputmode="numeric" autocomplete="off"></div>
     <div class="row"><button class="btn" id="glogin">Verbinden</button><span id="gres"></span></div>
     <p class="mut" style="font-size:12px">Garmin bietet Privatpersonen keine offizielle Schnittstelle; die Anmeldung kann von Garmin jederzeit geändert oder zeitweise gebremst werden. Der Dateiweg bleibt davon unberührt.</p>`
     }</div>
    <div><h3 style="margin-top:0">Suunto-Konto ${su.connected ? `<span class="ok" style="font-size:15px">✓ verbunden</span>` : ""} <span class="mut" style="font-size:12px">nur mit API-Zugang</span></h3>
     ${sunres ? `<p class="${sunres === "ok" ? "ok" : "bad"}"><b>${sunres === "ok" ? "Suunto ist verbunden ✓" : "Suunto: " + esc(sunres)}</b></p>` : ""}
     <p class="mut">Suunto gibt seine Cloud-Schnittstelle nur an Firmen und Organisationen, nicht an Privatpersonen. Wer einen Zugang über das <a target="_blank" rel="noopener" href="https://apizone.suunto.com/how-to-start">Suunto-Partnerprogramm</a> hat, trägt ihn hier ein. Alle anderen nutzen den Dateiweg oben.</p>
     <details${su.configured || su.connected ? " open" : ""}><summary>Zugangsdaten der Suunto API Zone</summary>
      ${f("suunto_client_id", "Client-ID")}${f("suunto_client_secret", "Client-Secret", "password")}${f("suunto_key", "Subscription-Key (Primary Key)", "password")}
      <p class="mut" style="font-size:13px">Weiterleitungsadresse (in der API Zone eintragen): <code>${esc(su.redirect || "")}</code></p>
      <div class="field"><label>Nur Workouts ab Datum (JJJJ-MM-TT, leer = alle)</label><input data-k="suunto_since" value="${esc(s.suunto_since)}"></div>
      <div class="field"><label>Neue Workouts täglich automatisch übernehmen</label><select data-k="suunto_auto"><option value="0">aus</option><option value="1">an</option></select></div>
      <div class="row"><button class="btn" id="sunconn">${su.connected ? "Neu verbinden" : "Mit Suunto verbinden"}</button>${su.connected ? `<button class="btn" id="sunsync">Jetzt importieren</button><button class="btn alt" id="sundis">Trennen</button>` : ""}<span id="sunres"></span></div></details></div></div></div>
  <div class="grid g2" style="margin-top:40px">
   <div class="panel"><h2>Automatik</h2><div class="field"><label>Täglich aktualisieren (Komoot, Routen, Fotos)</label><select data-k="auto_sync"><option value="0">aus</option><option value="1">an</option></select></div>${f("auto_sync_hour", "Uhrzeit (Stunde)", "number")}</div>
   <div class="panel"><h2>Protokoll</h2><div class="pre" id="log">–</div></div></div>
  <div class="row" style="margin-top:34px"><button class="btn" id="save">Einstellungen speichern</button><span id="ok" class="ok"></span></div>`;
  document.querySelector('[data-k="auto_sync"]').value = s.auto_sync;
  ["garmin_auto", "suunto_auto"].forEach(
    k => document.querySelector(`[data-k="${k}"]`) && (document.querySelector(`[data-k="${k}"]`).value = s[k])
  );
  if (document.querySelector('[data-k="zepp_auto_adopt"]')) document.querySelector('[data-k="zepp_auto_adopt"]').value = s.zepp_auto_adopt;
  const run = async (u, o) => {
    try {
      await api(u, o);
    } catch (e) {
      alert(e.message);
    }
    poll();
  };
  document.querySelectorAll("[data-job]").forEach(b => (b.onclick = () => run(`/api/jobs/${b.dataset.job}`, {method: "POST"})));
  $("#diag").onclick = async () => {
    $("#dres").textContent = "…";
    try {
      const r = await api("/api/diag/coords");
      $("#dres").innerHTML = `<span class="ok">Streckenpunkte erreichbar (${r.punkte} Punkte)</span>`;
    } catch (e) {
      $("#dres").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  };
  $("#ztest").onclick = async () => {
    $("#zres").textContent = "…";
    try {
      const r = await api("/api/zepp-token/test", {method: "POST"});
      $("#zres").innerHTML = `<span class="ok">Token funktioniert ✓</span>`;
    } catch (e) {
      $("#zres").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  };
  const ZK = await api("/api/zepp-key").catch(() => ({u: "", k: ""}));
  const code =
    "(function(){var m=document.cookie.match(/(?:^|; )apptoken=([^;]+)/);if(!m){alert('Kein apptoken gefunden – bitte zuerst bei Zepp anmelden.');return;}var f=document.createElement('form');f.method='POST';f.action='" +
    location.origin +
    "/api/zepp-token';f.target='_blank';var i=document.createElement('input');i.type='hidden';i.name='token';i.value=m[1];f.appendChild(i);var u=document.createElement('input');u.type='hidden';u.name='u';u.value='" +
    ZK.u +
    "';f.appendChild(u);var k=document.createElement('input');k.type='hidden';k.name='k';k.value='" +
    ZK.k +
    "';f.appendChild(k);document.body.appendChild(f);f.submit();})()";
  $("#bm").setAttribute("href", "javascript:" + encodeURIComponent(code));
  $("#bm").onclick = e => {
    e.preventDefault();
    alert("Bitte den Knopf mit der Maus in die Lesezeichenleiste ziehen, nicht anklicken.");
  };
  const picked = () => [...document.querySelectorAll(".pk:checked")].map(c => +c.value);
  if ($("#pall")) {
    $("#pall").onclick = () => document.querySelectorAll(".pk").forEach(c => (c.checked = true));
    const up = (dry, local) => {
      const ids = picked();
      if (!ids.length) return alert("Bitte zuerst Trainings auswählen.");
      const ps = local ? [] : [...document.querySelectorAll(".zp:checked")].map(c => c.value);
      if (!local && !ps.length) return alert("Bitte mindestens ein Portal ankreuzen – oder „Lokal übernehmen“ wählen.");
      if (!dry && ps.length && !confirm(`${ids.length} Training(s) lokal übernehmen und zu ${ps.join(" + ")} hochladen?`)) return;
      run("/api/zepp-upload", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({trackids: ids, dry_run: dry, portals: ps, local_only: local}),
      });
    };
    $("#plocal").onclick = () => up(false, true);
    $("#pup").onclick = () => up(false);
    $("#pdry").onclick = () => up(true, false);
  }
  folderUpload();
  $("#upl").onclick = () => {
    const fd = new FormData();
    [...$("#files").files].forEach(x => fd.append("files", x));
    if (!$("#files").files.length) return;
    const ps = [...document.querySelectorAll(".fp:checked")].map(c => c.value);
    if (!$("#dry").checked && ps.length && !confirm(`Dateien lokal speichern und zu ${ps.join(" + ")} hochladen?`)) return;
    run(`/api/import-activity-files?dry_run=${$("#dry").checked}&portals=${ps.join(",")}`, {method: "POST", body: fd});
  };
  const dres = (id, html) => $(id) && ($(id).innerHTML = html);
  if ($("#glogin"))
    $("#glogin").onclick = async () => {
      dres("#gres", "…");
      try {
        let r;
        if ($("#gmfa").style.display !== "none" && $("#gcode").value.trim())
          r = await api("/api/garmin/mfa", {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify({code: $("#gcode").value}),
          });
        else
          r = await api("/api/garmin/login", {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify({email: $("#gem").value, password: $("#gpw").value}),
          });
        if (r.mfa) {
          $("#gmfa").style.display = "";
          $("#glogin").textContent = "Code bestätigen";
          return dres("#gres", `<span class="mut">Garmin hat einen Code geschickt – bitte oben eintragen.</span>`);
        }
        route();
      } catch (e) {
        dres("#gres", `<span class="bad">${esc(e.message)}</span>`);
      }
    };
  if ($("#gsync"))
    $("#gsync").onclick = async () => {
      await save();
      run("/api/garmin/sync", {method: "POST"});
    };
  if ($("#gdis"))
    $("#gdis").onclick = async () => {
      if (!confirm("Garmin-Verbindung trennen? Bereits übernommene Touren bleiben erhalten.")) return;
      await api("/api/garmin/disconnect", {method: "POST"});
      route();
    };
  $("#sunconn").onclick = async () => {
    try {
      await save();
      const r = await api("/api/suunto/connect");
      location.href = r.url;
    } catch (e) {
      dres("#sunres", `<span class="bad">${esc(e.message)}</span>`);
    }
  };
  if ($("#sunsync"))
    $("#sunsync").onclick = async () => {
      await save();
      run("/api/suunto/sync", {method: "POST"});
    };
  if ($("#sundis"))
    $("#sundis").onclick = async () => {
      if (!confirm("Suunto-Verbindung trennen? Bereits übernommene Touren bleiben erhalten.")) return;
      await api("/api/suunto/disconnect", {method: "POST"});
      route();
    };
  $("#sconn").onclick = async () => {
    try {
      await save();
      const r = await api("/api/strava/connect");
      location.href = r.url;
    } catch (e) {
      $("#sres").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  };
  if ($("#sdis"))
    $("#sdis").onclick = async () => {
      if (!confirm("Strava-Verbindung trennen?")) return;
      await api("/api/strava/disconnect", {method: "POST"});
      route();
    };
  $("#scodeb").onclick = async () => {
    try {
      await api("/api/strava/code", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({code: $("#scode").value}),
      });
      route();
    } catch (e) {
      $("#sres").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    }
  };
  const save = async () => {
    const d = {};
    document.querySelectorAll("[data-k]").forEach(e => (d[e.dataset.k] = e.value));
    await api("/api/settings", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(d)});
  };
  $("#save").onclick = async () => {
    await save();
    $("#ok").textContent = "Gespeichert ✓";
  };
  const poll = async () => {
    const j = await api("/api/jobs").catch(() => null);
    if (!j || !$("#log")) return;
    $("#log").textContent = j.log.join("\n") || "–";
    $("#log").scrollTop = 1e9;
    $("#st").textContent = j.running ? `⏳ ${j.running} ${j.progress}` : j.ok === false ? "zuletzt: Fehler" : j.ok ? "zuletzt: ok ✓" : "";
    $("#busy").textContent = j.running ? "⏳ " + j.running : "";
    if (j.running) window._wasRun = true;
    else if (window._wasRun) {
      window._wasRun = false;
      ROUTES = null;
      loadTours();
    }
  };
  poll();
  pollTimer = setInterval(poll, 2000);
};
