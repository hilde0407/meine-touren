/* ---------- Verwaltung ---------- */
/* 3.42.0 Ein Schalter für jede An/Aus-Einstellung (statt Auswahlfeld „an/aus“, „ja/nein“): Schalter lesen/setzen für Felder mit data-k (Werte "1"/"0") */
const swField = (k, label, id = "", cls = "") => `<div class="field ${cls}"><label class="slck"><input type="checkbox" data-k="${k}"${id ? ` id="${id}"` : ""}><span>${label}</span></label></div>`;
const swSet = (k, v) => { const e = document.querySelector(`[data-k="${k}"]`); if (e) e.checked = String(v) === "1"; };
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
  <div class="sec admin mt0"><h2>Verwaltung</h2><span class="sub" id="st"></span><span class="sp"></span><span class="mut fs13" id="ver"></span></div>
  <div id="upd"></div><div class="panel mb16" id="hlt"><h2>Zustand</h2><p class="mut">wird geprüft …</p></div>
  <div class="grid g2">
   <div class="panel"><h2>Komoot <span class="mut h2sub">(optional)</span></h2><p class="mut">${fmtAnzahl(st.tours, "Tour", "Touren")} (davon ${nf(st.local_tours, 0)} nur lokal) · ${nf(st.routes, 0)} Strecken lokal gespeichert. Karten und Tourdetails nutzen immer die lokal gespeicherten Strecken; Komoot wird nur zum Holen und Hochladen gebraucht.</p>
    <div class="row"><button class="btn" data-job="refresh">Komoot aktualisieren</button><button class="btn alt" data-job="tours">Nur Touren</button><button class="btn alt" data-job="routes" title="Fehlende Strecken von Komoot holen und lokal speichern">Fehlende Strecken holen</button><button class="btn alt" data-job="geo" title="Land, Bundesland und Ort jeder Tour per OpenStreetMap bestimmen (für Suche und Filter)">Regionen bestimmen</button><button class="btn alt" id="diag">Komoot-Test</button></div>
    <p class="mut fs13">„Komoot aktualisieren“ holt neue Touren und deren Strecken von Komoot und durchsucht die Fotobibliothek. Es wird <b>nichts</b> zu Komoot hochgeladen. <span id="dres"></span></p>
    <div class="field"><label>Komoot-E-Mail</label><input data-k="komoot_email" value="${esc(s.komoot_email)}"></div><div class="field"><label>Komoot-Passwort</label><input data-k="komoot_password" type="password" value="${esc(s.komoot_password)}"></div></div>
   <div class="panel"><h2>Fotos</h2><p class="mut">${fmtAnzahl(pi.count, "Foto", "Fotos")} in der Bibliothek, ${nf(pi.assigned, 0)} einer Tour zugeordnet.<br>Bibliothek: <code>${esc(pi.lib_dir)}</code></p>
    <div class="row"><button class="btn" id="photoimp">Fotos importieren …</button><button class="btn alt" data-job="photos">Bibliothek neu durchsuchen</button></div>
    
    <details><summary>Weitere Wege (SMB-Ordner, Mac-Skript)</summary><div class="row m8-0"><button class="btn alt sm" data-job="photo-import" ${pi.folder_exists ? "" : 'disabled title="Quellordner nicht gefunden"'}>Fotos aus Ordner übernehmen</button></div>
    <p class="mut fs13">„Übernehmen“ verkleinert die Originale aus <code>${esc(pi.source_dir)}</code> ${pi.folder_exists ? "" : "<b class='bad'>(Ordner nicht gefunden)</b>"} für die Bildschirmdarstellung und legt sie in der Bibliothek ab. Alternativ vom Mac aus mit dem Skript <code>mac/fotos_senden.sh</code>.</p></details><p class="mut fs13">Beim Hochladen werden die Fotos <b>im Browser</b> für die Bildschirmdarstellung verkleinert; nur die kleinen Dateien gehen übers Netz. Originale werden nie verändert.</p>
    <details><summary>Fotoeinstellungen</summary>${f("photo_max_side", "Längste Seite eines Fotos (Pixel)", "number")}${f("photo_quality", "JPEG-Qualität (1–95)", "number")}${f("photo_margin_min", "Zuordnung: Toleranz vor/nach der Tour (Min.)", "number")}${f("photo_only_tracked", "Beim Foto-Import nur Fotos mit passender GPS-Strecke übernehmen (1 = ja, 0 = alle)")}${f("camera_utc_offset_h", "Kamerazeit-Versatz zu UTC in Stunden (leer = lokale Zeit)")}${f("slideshow_seconds", "Diashow: Sekunden pro Foto", "number")}</details></div></div>
  <div class="panel gap"><h2>Portale <span class="mut h2sub">(Upload)</span></h2>
   <p class="mut">Touren liegen lokal vor und können einzeln (Tourdetail → „⬆ Hochladen“) oder gesammelt (Zepp/Dateien unten) zu Komoot und Strava gesendet werden – immer nur auf deinen ausdrücklichen Wunsch.</p>
   ${sres ? `<p class="${sres === "ok" ? "ok" : "bad"}"><b>${sres === "ok" ? "Strava ist verbunden ✓" : "Strava: " + esc(sres)}</b></p>` : ""}
   <div class="grid g2"><div><h3 class="mt0">Strava ${sv.connected ? `<span class="ok fs15">✓ verbunden${sv.account ? " als " + esc(sv.account) : ""}</span>` : ""}</h3>
    ${f("strava_client_id", "Client-ID")}${f("strava_client_secret", "Client-Secret", "password")}
    <div class="row"><button class="btn" id="sconn">${sv.connected ? "Neu verbinden" : "Mit Strava verbinden"}</button>${sv.connected ? `<button class="btn alt" id="sdis">Verbindung trennen</button>` : ""}<span id="sres"></span></div></div>
    <ol class="mut pl18 mt0"><li>Auf <a target="_blank" href="https://www.strava.com/settings/api">strava.com/settings/api</a> eine eigene App anlegen (Name frei).</li><li>„Authorization Callback Domain“: <code>${esc(location.hostname)}</code> (bei Fehlermeldung: <code>localhost</code>).</li><li>Client-ID und -Secret hier eintragen, „Einstellungen speichern“, dann „Mit Strava verbinden“.</li><li>Falls Strava nach der Freigabe nicht zurückfindet: Adresse der leeren Seite kopieren und hier einfügen:<div class="row mt6"><input id="scode" placeholder="http://…?code=…" class="fx1"><button class="btn alt sm" id="scodeb">Code einlösen</button></div></li></ol></div>
   <details class="kvdet" open><summary>Komoot: Sichtbarkeit, Notiz und Pins</summary><p class="mut">Zugang siehe Panel „Komoot“ oben. Touren, die von Komoot stammen, können nicht erneut zu Komoot hochgeladen werden; zu Strava schon.</p>
    <p class="kvnote">Komoot gibt jeder hochgeladenen Tour zuerst die Standard-Sichtbarkeit deines Kontos. Meine Touren setzt sie deshalb gleich danach auf „privat“ und prüft das. Touren aus früheren Versionen können öffentlich sein – prüfe sie hier.</p>
    ${swField("komoot_with_notes", "Beim Hochladen Notiz und Pins mitsenden (als Beschreibung und Wegpunkte; die Tour wird danach auf „privat“ gesetzt)")}
    <div class="row"><button class="btn alt" id="kvchk">Sichtbarkeit bei Komoot prüfen …</button></div></details></div>
  <div class="panel gap"><h2>Zepp-Import <span class="mut h2sub">(optional)</span></h2>
   <p class="mut">Holt GPS-Trainings aus deinem Zepp-Konto (als GPX-Dateien). Ausgewählte Trainings werden lokal als Tour gespeichert (Karte, Statistik); ein Upload zu Komoot/Strava passiert <b>nur</b>, wenn du es unten ausdrücklich anhakst.</p>
   <div class="row"><button class="btn" data-job="export">Zepp-Import starten</button><button class="btn alt" data-job="elev-local" title="Falsche Höhenwerte (z. B. Platzhalter) aus bereits importierten Touren entfernen und Auf-/Abstieg neu berechnen">Aufstieg neu berechnen</button><button class="btn alt" data-job="hr-backfill" title="Herzfrequenz für bereits importierte Zepp-Touren aus der Zepp-Cloud nachladen (Touren bleiben unverändert)">Puls holen</button><button class="btn alt" data-job="dev-match" title="Alle Touren, zu denen es ein Zepp-Training gibt (auch Komoot- und Datei-Touren), als mit der Uhr aufgezeichnet markieren und dem passenden Gerät zuordnen. Von Hand zugeordnete Touren bleiben unverändert.">Touren den Uhren zuordnen</button><button class="btn alt" data-job="met-backfill" title="Messwerte (Tempo, Kadenz, Leistung, Temperatur …) für bereits importierte Touren aus der Zepp-Cloud bzw. aus Original-Dateien im Eingang/Export nachladen. Vorhandene Daten bleiben unverändert.">Messwerte holen</button><button class="btn alt" data-job="elev-zepp" title="Auf-/Abstieg von Komoot- und Datei-Touren mit der barometrischen Höhe der Uhr (Zepp) neu berechnen, wenn es ein passendes Training gibt. Bereits korrigierte Touren bleiben unberührt; je Tour wiederherstellbar.">Höhe korrigieren (aus der Uhr)</button><button class="btn alt" id="ztest">Token testen</button><span id="zres"></span></div>
   <details><summary>Zepp-Zugang / Token holen</summary><div class="grid g2"><div>${f("zepp_email", "E-Mail (nur wenn dein Konto ein Zepp-Passwort hat)")}${f("zepp_password", "Passwort", "password")}${f("zepp_token", "Token (für Mi-/Google-/Apple-Konten)", "password")}${f("zepp_host", "Server (leer = automatisch)")}</div>
    <ol class="mut pl18"><li>Diesen Knopf in die <b>Lesezeichenleiste</b> ziehen: <a id="bm" class="btn alt sm" href="#">Token an Meine Touren</a></li><li>Im selben Browser <a target="_blank" href="https://user.huami.com/privacy2/index.html?platform_app=com.xiaomi.hm.health&loginPlatform=web">user.huami.com/privacy2</a> öffnen, anmelden und dort <b>nichts</b> anklicken (die Seite bietet „Konto löschen“ an).</li><li>Das Lesezeichen anklicken – das Token wird gespeichert und geprüft.</li></ol></div></details>
   <h3 class="mt14">Zepp-Trainings ${pend.length ? "noch nicht übernommen" : ""}</h3>
   <p class="mut">${w.length} exportiert · ${w.filter(x => x.status === "local").length} lokal übernommen · ${w.filter(x => x.status === "in_komoot" || x.status === "uploaded").length} bereits in Komoot · ${w.filter(x => x.status === "no_gps").length} ohne GPS · ${pend.length} noch offen</p>
   ${
     pend.length
       ? `<details${pend.length <= 8 ? " open" : ""}><summary>${pend.length} offene Trainings anzeigen</summary><div class="ova" style="max-height:300px"><table><tr><th></th><th>Datum</th><th>Sport</th><th class="n">km</th></tr>${pend.map(x => `<tr><td><input type="checkbox" class="pk cb" value="${x.trackid}"></td><td>${fmtDatumKurz(x.date, {zeit: true})}</td><td>${sName(x.sport)}</td><td class="n">${nf(x.dist_m / 1000, 1)}</td></tr>`).join("")}</table></div></details>
   <div class="row mt10"><button class="btn alt sm" id="pall">Alle wählen</button><button class="btn alt sm" id="pdry">Probelauf</button><button class="btn" id="plocal">Holen</button></div>
   <div class="row mt8"><span class="mut">Zusätzlich hochladen zu:</span>${pf.portals.map(p => `<label class="chk m0"><input type="checkbox" class="zp cb" value="${p.id}" ${p.connected ? "" : "disabled"}> ${p.name}${p.connected ? "" : `<span class="mut fs12"> (${p.id === "komoot" ? "Zugang fehlt: im Panel „Komoot“ (Komoot-E-Mail und -Passwort) speichern" : "nicht verbunden: bei „Portale“ verbinden"})</span>`}</label>`).join("")}<button class="btn" id="pup">Holen und hochladen</button></div>
   ${swField("zepp_auto_adopt", "Neue Zepp-Trainings automatisch lokal übernehmen (ohne Upload)", "", "mt8")}`
       : ""
   }
   </div>
  <div class="panel gap"><h2>Garmin, Suunto &amp; andere Uhren <span class="mut h2sub">(Import)</span></h2>
   <p class="mut">Aktivitäten werden <b>lokal</b> als Touren gespeichert (Karte, Statistik, Fotozuordnung), mit Doppelten-Prüfung. Hochgeladen wird nur, wenn du es unten ausdrücklich ankreuzt.<br>
   <b>Tipp:</b> Ist deine Uhr in Garmin Connect bzw. der Suunto-App mit <b>Komoot</b> verbunden, kommen die Touren ohnehin über „Komoot aktualisieren“.</p>
   <h3>Dateien importieren <span class="ok fs14">funktioniert immer</span></h3>
   <div class="field"><label>FIT-, GPX-, TCX- oder ZIP-Dateien (mehrere möglich; ZIP darf viele Aktivitäten enthalten, auch der komplette Garmin-Export)</label><div class="row"><input type="file" id="files" multiple accept=".fit,.gpx,.tcx,.zip,.gz"><span class="mut">zusätzlich zu:</span>${pf.portals.map(p => `<label class="chk m0"><input type="checkbox" class="fp cb" value="${p.id}" ${p.connected ? "" : "disabled"}> ${p.name}${p.connected ? "" : `<span class="mut fs12"> (${p.id === "komoot" ? "Zugang fehlt: im Panel „Komoot“ (Komoot-E-Mail und -Passwort) speichern" : "nicht verbunden: bei „Portale“ verbinden"})</span>`}</label>`).join("")}<button class="btn alt sm" id="upl">Importieren</button><label class="m0"><input type="checkbox" id="dry"> Probelauf</label></div></div>
   <details><summary>So kommst du an die Dateien</summary><ul class="mut pl18">
    <li><b>Garmin, alles auf einmal:</b> auf <a target="_blank" rel="noopener" href="https://www.garmin.com/account/datamanagement/">garmin.com/account/datamanagement</a> „Daten exportieren“ anfordern (Garmin schickt nach ein bis zwei Tagen eine ZIP-Datei per E-Mail) und die ZIP-Datei hier importieren.</li>
    <li><b>Garmin, einzelne Aktivität:</b> connect.garmin.com → Aktivität öffnen → Zahnrad ⚙ → „Original exportieren“ (FIT in einer ZIP) oder „Als GPX exportieren“.</li>
    <li><b>Suunto:</b> Suunto-App → Training öffnen → ⋮ (oben rechts) → Exportieren → FIT (alle Daten) oder GPX. Trainings ohne GPS lassen sich nur als FIT exportieren und werden hier ohnehin übersprungen.</li>
    <li><b>Große ZIP-Dateien</b> (über 1 GB): statt Hochladen in den Eingangsordner legen: <code>${esc(st.inbox || "")}/touren</code> – sie werden automatisch übernommen und danach nach „erledigt“ verschoben.</li>
    <li>Andere Hersteller (Polar, Coros, Wahoo, Amazfit …) exportieren ebenfalls FIT oder GPX – das geht genauso.</li></ul></details>
   <div class="grid g2 mt14">
    <div><h3 class="mt0">Garmin-Konto ${gm.connected ? `<span class="ok fs15">✓ verbunden${gm.email ? " als " + esc(gm.email) : ""}</span>` : ""} <span class="mut fs12">experimentell</span></h3>
     ${
       gm.available === false
         ? `<p class="mut">Nicht verfügbar: ${esc(gm.why)}</p>`
         : gm.connected
           ? `<p class="mut">${nf(gm.imported || 0, 0)} Aktivitäten übernommen${gm.checked ? ", zuletzt geprüft " + fmtDatumKurz(+gm.checked, {zeit: true}) : ""}.</p>
     <div class="field"><label>Nur Touren ab Datum (TT.MM.JJJJ, leer = alle)</label><input data-k="garmin_since" data-datum value="${esc(fmtDatumFeld(s.garmin_since))}" placeholder="01.01.2024" inputmode="numeric"></div>
     ${swField("garmin_auto", "Neue Touren täglich automatisch holen")}
     <div class="row"><button class="btn" id="gsync">Jetzt importieren</button><button class="btn alt" id="gdis">Verbindung trennen</button><span id="gres"></span></div>`
           : `<p class="mut">Anmeldung wie im Browser (E-Mail und Passwort von Garmin Connect). Das Passwort wird <b>nicht gespeichert</b>, nur der Anmelde-Schlüssel (verschlüsselt). Konten mit Google-/Apple-Login haben kein Garmin-Passwort – dann bitte den Dateiweg nehmen.</p>
     <div class="field"><label>Garmin-E-Mail</label><input id="gem" autocomplete="off"></div><div class="field"><label>Garmin-Passwort</label><input id="gpw" type="password" autocomplete="off"></div>
     <div class="field" id="gmfa" style="display:none"><label>Bestätigungscode (Zwei-Faktor, per E-Mail/App)</label><input id="gcode" inputmode="numeric" autocomplete="off"></div>
     <div class="row"><button class="btn" id="glogin">Verbinden</button><span id="gres"></span></div>
     <p class="mut fs12">Garmin bietet Privatpersonen keine offizielle Schnittstelle; die Anmeldung kann von Garmin jederzeit geändert oder zeitweise gebremst werden. Der Dateiweg bleibt davon unberührt.</p>`
     }</div>
    <div><h3 class="mt0">Suunto-Konto ${su.connected ? `<span class="ok fs15">✓ verbunden</span>` : ""} <span class="mut fs12">nur mit API-Zugang</span></h3>
     ${sunres ? `<p class="${sunres === "ok" ? "ok" : "bad"}"><b>${sunres === "ok" ? "Suunto ist verbunden ✓" : "Suunto: " + esc(sunres)}</b></p>` : ""}
     <p class="mut">Suunto gibt seine Cloud-Schnittstelle nur an Firmen und Organisationen, nicht an Privatpersonen. Wer einen Zugang über das <a target="_blank" rel="noopener" href="https://apizone.suunto.com/how-to-start">Suunto-Partnerprogramm</a> hat, trägt ihn hier ein. Alle anderen nutzen den Dateiweg oben.</p>
     <details${su.configured || su.connected ? " open" : ""}><summary>Zugangsdaten der Suunto API Zone</summary>
      ${f("suunto_client_id", "Client-ID")}${f("suunto_client_secret", "Client-Secret", "password")}${f("suunto_key", "Subscription-Key (Primary Key)", "password")}
      <p class="mut fs13">Weiterleitungsadresse (in der API Zone eintragen): <code>${esc(su.redirect || "")}</code></p>
      <div class="field"><label>Nur Touren ab Datum (TT.MM.JJJJ, leer = alle)</label><input data-k="suunto_since" data-datum value="${esc(fmtDatumFeld(s.suunto_since))}" placeholder="01.01.2024" inputmode="numeric"></div>
      ${swField("suunto_auto", "Neue Touren täglich automatisch holen")}
      <div class="row"><button class="btn" id="sunconn">${su.connected ? "Neu verbinden" : "Mit Suunto verbinden"}</button>${su.connected ? `<button class="btn" id="sunsync">Jetzt importieren</button><button class="btn alt" id="sundis">Verbindung trennen</button>` : ""}<span id="sunres"></span></div></details></div></div></div>
  <div class="panel gap sgp" id="katp"><h2>Sportarten-Katalog</h2><div id="katbody"></div></div>
  <div class="panel gap sgp" id="favp"><h2>Favoriten-Sportarten</h2><div id="favbody"><p class="mut">Wird geladen …</p></div></div>
  <div class="panel gap sgp" id="sgp"><h2>Statistik-Gruppen</h2><div id="sgbody"><p class="mut">Wird geladen …</p></div></div>
  <div class="grid g2 mt40">
   <div class="panel"><h2>Automatik</h2>${swField("auto_sync", "Täglich aktualisieren (Komoot, Strecken, Fotos)")}${f("auto_sync_hour", "Uhrzeit (Stunde)", "number")}</div>
   <div class="panel"><h2>Protokoll</h2><div class="pre" id="log">–</div></div></div>
  <div class="row mt34"><button class="btn" id="save">Einstellungen speichern</button><span id="ok" class="ok"></span></div>`;
  ["auto_sync", "garmin_auto", "suunto_auto", "zepp_auto_adopt", "komoot_with_notes"].forEach(k => swSet(k, s[k]));
  if ($("#kvchk")) $("#kvchk").onclick = () => komootVisDialog();
  katAdmin($("#katbody"));
  sgAdmin($("#sgbody"));
  favAdmin($("#favbody"));
  const run = async (u, o) => {
    try {
      await api(u, o);
    } catch (e) {
      uiAlert(e.message);
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
    uiAlert("Bitte den Knopf mit der Maus in die Lesezeichenleiste ziehen, nicht anklicken.");
  };
  const picked = () => [...document.querySelectorAll(".pk:checked")].map(c => +c.value);
  if ($("#pall")) {
    $("#pall").onclick = () => document.querySelectorAll(".pk").forEach(c => (c.checked = true));
    const up = async (dry, local) => {
      const ids = picked();
      if (!ids.length) return uiAlert("Bitte zuerst Trainings auswählen.");
      const ps = local ? [] : [...document.querySelectorAll(".zp:checked")].map(c => c.value);
      if (!local && !ps.length) return uiAlert("Bitte mindestens ein Portal ankreuzen – oder „Holen“ wählen.");
      if (!dry && ps.length && !await uiConfirm({title: "Holen und hochladen?", ok: "Holen und hochladen", text: `${ids.length === 1 ? "1 Zepp-Training" : ids.length + " Zepp-Trainings"} als Touren holen und zu ${ps.join(" + ")} hochladen?`})) return;
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
  $("#upl").onclick = async () => {
    const fd = new FormData();
    [...$("#files").files].forEach(x => fd.append("files", x));
    if (!$("#files").files.length) return;
    const ps = [...document.querySelectorAll(".fp:checked")].map(c => c.value);
    if (!$("#dry").checked && ps.length && !await uiConfirm({title: "Importieren und hochladen?", ok: "Importieren und hochladen", text: `Dateien als Touren importieren und zu ${ps.join(" + ")} hochladen?`})) return;
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
      if (!await uiConfirm({text: "Garmin-Verbindung trennen? Bereits übernommene Touren bleiben erhalten.", danger: true, ok: "Verbindung trennen"})) return;
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
      if (!await uiConfirm({text: "Suunto-Verbindung trennen? Bereits übernommene Touren bleiben erhalten.", danger: true, ok: "Verbindung trennen"})) return;
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
      if (!await uiConfirm({text: "Strava-Verbindung trennen?", danger: true, ok: "Verbindung trennen"})) return;
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
    document.querySelectorAll("[data-k]").forEach(e => (d[e.dataset.k] = e.type === "checkbox" ? (e.checked ? "1" : "0") : e.value));
    /* 3.61.0: Datumsfelder werden als TT.MM.JJJJ eingegeben und wie bisher als JJJJ-MM-TT gespeichert */
    for (const e of document.querySelectorAll("[data-k][data-datum]")) {
      const v = fmtDatumLesen(e.value);
      if (v === null) throw new Error(`Datum bitte als TT.MM.JJJJ eingeben (${e.value})`);
      d[e.dataset.k] = v;
    }
    await api("/api/settings", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(d)});
  };
  $("#save").onclick = async () => {
    try {
      await save();
      $("#ok").textContent = "Einstellungen gespeichert";
    } catch (e) {
      $("#ok").textContent = "Speichern nicht möglich: " + (e.message || e);
    }
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

/* 3.58.0 Rückprüfung: Sichtbarkeit aller zu Komoot hochgeladenen Touren nachlesen (nur lesend, in kleinen Gruppen nacheinander, mit Fortschritt).
   Auf „privat“ setzen nur per Klick – je Tour oder, nach Rückfrage, für alle gefundenen öffentlichen. Nie von selbst. */
async function komootVisDialog() {
  let h;
  try {
    h = await api("/api/komoot/hochgeladen");
  } catch (e) {
    return uiAlert(e.message);
  }
  const L = h.touren || [];
  const m = uiModal(`<h3>Sichtbarkeit bei Komoot</h3>
    <p class="mut">${L.length === 1 ? "1 Tour liegt" : `${L.length} Touren liegen`} laut Meine Touren bei Komoot (hochgeladen oder dort gefunden). Die Prüfung liest bei Komoot nur nach, eine Tour nach der anderen, und ändert nichts.</p>
    <p class="kvsum" id="kvsum" role="status"></p><progress class="kvprog" id="kvprog" max="${Math.max(1, L.length)}" value="0" hidden></progress>
    <ul class="kvlist" id="kvlist"></ul>
    <div class="uifoot"><button class="btn ghost" id="kvx">Schließen</button><button class="btn alt" id="kvall" hidden>Alle öffentlichen auf privat setzen …</button><button class="btn" id="kvgo" ${L.length ? "" : "disabled"}>Alle hochgeladenen prüfen</button></div>`);
  let open = true;
  const zahl = () => {
    const z = {oeffentlich: 0, freunde: 0, privat: 0, unbekannt: 0, fehlt: 0};
    L.forEach(x => z[{public: "oeffentlich", friends: "freunde", private: "privat", fehlt: "fehlt"}[x.vis] || "unbekannt"]++);
    return z;
  };
  const render = () => {
    const z = zahl();
    m.querySelector("#kvsum").innerHTML = `<b>${z.oeffentlich} öffentlich, ${z.privat} privat, ${z.unbekannt} unbekannt</b>${z.freunde ? ` <span>${z.freunde} für Freunde sichtbar</span>` : ""}${z.fehlt ? ` <span>${z.fehlt} nicht mehr bei Komoot</span>` : ""}`;
    m.querySelector("#kvlist").innerHTML = L.map(
      x => `<li><a href="#/tour/${encodeURIComponent(x.id)}">${esc(x.name)}</a> <span class="mut fs13">${x.start_ts ? fmtDatumKurz(x.start_ts) : ""}</span>
        ${x.vis === "fehlt" ? '<span class="kvis warn">Bei Komoot nicht gefunden</span>' : x.vis ? kvisChip(x.vis) : '<span class="kvis">noch nicht geprüft</span>'}
        ${x.url && x.vis !== "fehlt" ? `<a class="fs13" target="_blank" href="${esc(x.url)}">in Komoot öffnen ↗</a>` : ""}
        ${x.vis && !["private", "fehlt"].includes(x.vis) ? `<button class="btn ghost sm" data-kp="${esc(x.id)}">Auf privat setzen</button>` : ""}</li>`
    ).join("") || '<li class="mut">Keine Touren bei Komoot bekannt.</li>';
    m.querySelectorAll("[data-kp]").forEach(b => (b.onclick = () => privat([L.find(x => x.id === b.dataset.kp)])));
    const pub = L.filter(x => x.vis === "public" || x.vis === "friends");
    const all = m.querySelector("#kvall");
    all.hidden = pub.length < 2;
    all.textContent = `Alle ${pub.length} nicht privaten auf privat setzen …`;
  };
  const privat = async list => {
    for (const x of list) {
      if (!open) return;
      try {
        const r = await api(`/api/tours/${encodeURIComponent(x.id)}/komoot-privat`, {method: "POST"});
        x.vis = r.vis;
      } catch (e) {
        x.vis = "unbekannt";
      }
      render();
    }
  };
  m.querySelector("#kvx").onclick = () => {
    open = false;
    m.remove();
  };
  m.querySelector("#kvall").onclick = async () => {
    const pub = L.filter(x => x.vis === "public" || x.vis === "friends");
    if (!pub.length) return;
    if (!(await uiConfirm({text: `${fmtAnzahl(pub.length, "Tour", "Touren")} bei Komoot auf „privat“ (nur ich) setzen? Touren, die du absichtlich geteilt hast, sieht danach nur noch du.`, ok: "Auf privat setzen"}))) return;
    await privat(pub);
  };
  m.querySelector("#kvgo").onclick = async e => {
    const prog = m.querySelector("#kvprog");
    e.target.disabled = true;
    prog.hidden = false;
    prog.value = 0;
    for (let i = 0; i < L.length && open; i += 5) {
      const part = L.slice(i, i + 5);
      m.querySelector("#kvsum").textContent = `Wird geprüft … ${i} von ${L.length}`;
      try {
        const r = await api("/api/komoot/sichtbarkeit", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({ids: part.map(x => x.id)})});
        part.forEach(x => (x.vis = (r.ergebnis[x.id] || {}).vis || "unbekannt"));
      } catch (er) {
        part.forEach(x => (x.vis = "unbekannt"));
      }
      prog.value = Math.min(L.length, i + part.length);
    }
    if (!open) return;
    prog.hidden = true;
    e.target.disabled = false;
    e.target.textContent = "Erneut prüfen";
    render();
  };
  render();
}

/* 3.59.0 Statistik-Gruppen bearbeiten (3.60.0: Verwaltung → Aktivitäten): welche Aktivitäten die Statistik gemeinsam zählt – jeder entscheidet selbst. Ohne Gruppen zählt jede
   Aktivität einzeln. Speichern über PUT /api/stats/gruppen (app/stat_gruppen.py prüft und bereinigt: höchstens 8 Gruppen, Name 1–30 Zeichen, mindestens 2 Sportarten,
   jede Sportart in höchstens einer Gruppe). Die Vorschläge (Wandern + Bergsteigen + Schneeschuh, alle Rad-Arten, alle Ski-Arten) übernimmt nur ein Klick – nie automatisch. */
async function sgAdmin(box) {
  if (!box) return;
  let d;
  try {
    d = await api("/api/stats/gruppen");
  } catch (e) {
    box.innerHTML = `<p class="mut">${esc(e.message || "Fehler")}</p>`;
    return;
  }
  const MAX = d.max || 8, NMAX = d.name_max || 30, VOR = d.vorschlaege || [];
  let G = (d.gruppen || []).map(g => ({id: g.id, name: g.name, sports: g.sports.slice()})), msg = "", err = "";
  const ALL = SPORT_CAT.flatMap(c => c[2]).concat((d.sportarten || []).filter(s => !SPORT[s]));
  const owner = (s, i) => G.findIndex((g, j) => j !== i && g.sports.includes(s));
  const canSug = v => G.length < MAX && !G.some(g => g.id === v.id) && v.sports.every(s => owner(s, -1) < 0);
  const chip = (g, i, s) => {
    const o = owner(s, i), id = `sgc${i}_${s}`;
    return `<label class="flchip sgchip${o >= 0 ? " sgoff" : ""}" for="${id}"><input type="checkbox" id="${id}" data-g="${i}" value="${esc(s)}"${g.sports.includes(s) ? " checked" : ""}${o >= 0 ? " disabled" : ""}><span>${esc(sName(s))}</span>${o >= 0 ? `<small class="sgin">in „${esc(G[o].name || "…")}“</small>` : ""}</label>`;
  };
  const cats = (g, i) => SPORT_CAT.map(([id, l, ks]) => `<div class="sgcat"><span class="sgcl" id="sgcl${i}_${id}">${esc(l)}</span><div class="flchips sgchips" role="group" aria-labelledby="sgcl${i}_${id}">${ks.map(s => chip(g, i, s)).join("")}</div></div>`).join("") +
    (ALL.some(s => !SPORT[s]) ? `<div class="sgcat"><span class="sgcl">Weitere aus deinen Touren</span><div class="flchips sgchips">${ALL.filter(s => !SPORT[s]).map(s => chip(g, i, s)).join("")}</div></div>` : "");
  const draw = (focus = "") => {
    box.innerHTML = `<p class="mut">Ohne Statistik-Gruppen zählt die Statistik jede Sportart einzeln. Wenn du Sportarten gemeinsam sehen möchtest – zum Beispiel Wandern, Bergsteigen und Schneeschuhwandern –, lege hier eine Statistik-Gruppe an. Jede Statistik-Gruppe ist im Sportartfilter als eigener Eintrag „Name = Sportart + Sportart“ wählbar, und die Aufteilungen nach Sportart (Sportarten, Bestwerte, Jahresrückblick) zeigen sie als eine Zeile. Die Touren und ihre Sportart bleiben unverändert.</p>
      <div class="sglist">${G.map((g, i) => `<fieldset class="sgg" data-i="${i}"><legend class="slsr">${esc(`Statistik-Gruppe ${i + 1}`)}</legend>
        <div class="row g6 sgrow"><label class="sgnl" for="sgn${i}">Name</label><input id="sgn${i}" class="sgn fx1" data-i="${i}" maxlength="${NMAX}" value="${esc(g.name)}" autocomplete="off" aria-describedby="sgw${i}"${sgNameClash(g.name) ? ' aria-invalid="true"' : ""}><button type="button" class="btn ghost sm sgdel" data-i="${i}" aria-label="${esc(`Statistik-Gruppe „${g.name}“ löschen`)}">🗑 Löschen</button></div>
        <p class="bad fs13 sgwarn" id="sgw${i}"${sgNameClash(g.name) ? "" : " hidden"}>Name wie eine Sportart – bitte umbenennen</p>
        <div class="sgcats" role="group" aria-label="${esc(`Sportarten der Statistik-Gruppe „${g.name}“`)}">${cats(g, i)}</div></fieldset>`).join("") || '<p class="mut sgnone">Keine Statistik-Gruppen: Die Statistik zählt jede Sportart einzeln.</p>'}</div>
      <div class="row mt10 sgbtns"><button type="button" class="btn alt sm" id="sgadd"${G.length >= MAX ? " disabled" : ""}>Statistik-Gruppe hinzufügen</button></div>
      <div class="sgvor"><span class="mut fs13">Vorschläge (ein Klick legt die Statistik-Gruppe an, gespeichert wird erst mit „Speichern“):</span><div class="row g6 mt6">${VOR.map(v => `<button type="button" class="btn alt sm sgsug" data-v="${esc(v.id)}"${canSug(v) ? "" : " hidden"}>${esc(`Vorschlag: ${v.name}`)}</button>`).join("")}</div></div>
      ${G.length >= MAX ? `<p class="mut fs13">${esc(`Höchstens ${MAX} Statistik-Gruppen.`)}</p>` : ""}
      <div class="row mt10"><button type="button" class="btn" id="sgsave">Speichern</button><span class="ok" id="sgok" role="status">${esc(msg)}</span></div>
      <p class="bad sgerr" id="sgerr" role="alert">${esc(err)}</p>`;
    msg = err = "";
    if (focus) {
      const f = box.querySelector(focus);
      if (f) f.focus();
    }
  };
  /* Häkchen und Namen ändern nichts am Aufbau: nur Sperren und Hinweise „in …“ der übrigen Gruppen nachziehen (der Fokus bleibt, wo er ist) */
  const sync = () => {
    box.querySelectorAll(".sgchip input").forEach(x => {
      const i = +x.dataset.g, o = owner(x.value, i), lab = x.closest("label");
      x.disabled = o >= 0;
      lab.classList.toggle("sgoff", o >= 0);
      let sm = lab.querySelector(".sgin");
      if (o >= 0 && !sm) lab.insertAdjacentHTML("beforeend", '<small class="sgin"></small>');
      if (o < 0 && sm) sm.remove();
      sm = lab.querySelector(".sgin");
      if (sm) sm.textContent = `in „${G[o].name || "…"}“`;
    });
    box.querySelectorAll(".sgg").forEach(f => {
      const i = +f.dataset.i, nm = G[i].name, cl = sgNameClash(nm);          // 3.60.1: Hinweis, solange der Name wie eine Aktivität lautet (auch bei bestehenden Gruppen)
      f.querySelector(".sgwarn").hidden = !cl;
      if (cl) f.querySelector(".sgn").setAttribute("aria-invalid", "true");
      else f.querySelector(".sgn").removeAttribute("aria-invalid");
      f.querySelector(".sgdel").setAttribute("aria-label", `Statistik-Gruppe „${nm}“ löschen`);
      f.querySelector(".sgcats").setAttribute("aria-label", `Sportarten der Statistik-Gruppe „${nm}“`);
    });
    box.querySelectorAll(".sgsug").forEach(b => (b.hidden = !canSug(VOR.find(v => v.id === b.dataset.v))));
  };
  box.addEventListener("input", e => {
    const n = e.target.closest(".sgn");
    if (!n) return;
    G[+n.dataset.i].name = n.value;
    sync();
  });
  box.addEventListener("change", e => {
    const x = e.target.closest(".sgchip input");
    if (!x) return;
    const g = G[+x.dataset.g];
    g.sports = x.checked ? g.sports.concat([x.value]).filter((s, k, a) => a.indexOf(s) === k) : g.sports.filter(s => s !== x.value);
    sync();
  });
  box.addEventListener("click", async e => {
    const del = e.target.closest(".sgdel"), b = e.target.closest("button");
    if (del) {
      const i = +del.dataset.i;
      G.splice(i, 1);
      return draw(G.length ? `#sgn${Math.min(i, G.length - 1)}` : "#sgadd");
    }
    if (!b) return;
    if (b.id === "sgadd" && G.length < MAX) {
      G.push({id: "", name: "", sports: []});
      return draw(`#sgn${G.length - 1}`);
    }
    if (b.classList.contains("sgsug")) {
      const v = VOR.find(x => x.id === b.dataset.v);
      if (!v || !canSug(v)) return;
      G.push({id: v.id, name: v.name, sports: v.sports.slice()});
      msg = "Vorschlag eingetragen – gespeichert wird mit „Speichern“.";
      return draw("#sgsave");
    }
    if (b.id === "sgsave") {
      const bad = G.findIndex(g => !g.name.trim() || g.name.trim().length > NMAX), few = G.findIndex(g => g.sports.length < 2), cl = G.findIndex(g => sgNameClash(g.name));
      const er = box.querySelector("#sgerr");
      box.querySelector("#sgok").textContent = "";
      if (bad >= 0) {
        er.textContent = `Statistik-Gruppe ${bad + 1}: Bitte einen Namen mit 1 bis ${NMAX} Zeichen eingeben.`;
        return box.querySelector(`#sgn${bad}`).focus();
      }
      if (cl >= 0) {
        er.textContent = `Statistik-Gruppe ${cl + 1}: „${G[cl].name.trim()}“ heißt schon eine Sportart – bitte einen anderen Gruppennamen wählen`;
        return box.querySelector(`#sgn${cl}`).focus();
      }
      if (few >= 0) {
        er.textContent = `„${G[few].name.trim()}“: Eine Statistik-Gruppe braucht mindestens 2 Sportarten.`;
        return (box.querySelector(`.sgg[data-i="${few}"] .sgchip input:not([disabled])`) || box.querySelector(`#sgn${few}`)).focus();
      }
      b.disabled = true;
      try {
        const r = await api("/api/stats/gruppen", {method: "PUT", headers: {"content-type": "application/json"}, body: JSON.stringify({gruppen: G.map(g => ({id: g.id, name: g.name.trim(), sports: g.sports}))})});
        G = r.gruppen.map(g => ({id: g.id, name: g.name, sports: g.sports.slice()}));
        await sgLoad();
        msg = "Statistik-Gruppen gespeichert – gelten ab sofort in der Statistik";
      } catch (x) {
        err = x.message || String(x);
      }
      draw("#sgsave");
    }
  });
  draw();
}

/* 3.59.0 Favoriten-Aktivitäten (3.60.0: Verwaltung → Aktivitäten, „Favoriten für „Tour aufnehmen““): Stern wählt, Pfeile ordnen (höchstens 12). Die Favoriten erscheinen zuerst, wo eine Tour aufgenommen oder
   angelegt wird (Aufzeichnen, Planung); alle übrigen stehen dort unter „Mehr …“. Speichern über PUT /api/aktivitaeten/favoriten (app/aktivitaeten.py). */
async function favAdmin(box) {
  if (!box) return;
  let d;
  try {
    d = await api("/api/aktivitaeten/favoriten");
  } catch (e) {
    box.innerHTML = `<p class="mut">${esc(e.message || "Fehler")}</p>`;
    return;
  }
  const MAX = d.max || 12;
  let F = (d.favoriten || FAV_DEF).filter(k => SPORT[k]), msg = "", err = "";
  const draw = (focus = "") => {
    box.innerHTML = `<p class="mut">Für „Tour aufzeichnen“: Diese Sportarten stehen dort zuerst – ebenso beim Planen, bei „Sportart ändern“ und bei Zielen. Alle übrigen Sportarten findest du dort unter „Mehr …“.</p>
      <ol class="favlist" aria-label="Reihenfolge der Favoriten-Sportarten">${F.map((k, i) => `<li><span aria-hidden="true">${sIcon(k)}</span> <span class="favn">${esc(sName(k))}</span>
        <button type="button" class="btn ghost sm favup" data-k="${k}"${i ? "" : " disabled"} aria-label="${esc(`${sName(k)} nach oben`)}">↑</button><button type="button" class="btn ghost sm favdn" data-k="${k}"${i < F.length - 1 ? "" : " disabled"} aria-label="${esc(`${sName(k)} nach unten`)}">↓</button></li>`).join("")}</ol>
      ${SPORT_CAT.map(([id, l, ks]) => `<div class="sgcat"><span class="sgcl" id="favc-${id}">${esc(l)}</span><div class="flchips favchips" role="group" aria-labelledby="favc-${id}">${ks.map(k => `<button type="button" class="flchip favst" data-k="${k}" aria-pressed="${F.includes(k)}"${!F.includes(k) && F.length >= MAX ? " disabled" : ""}><span aria-hidden="true">${F.includes(k) ? "★" : "☆"}</span> <span>${esc(sName(k))}</span></button>`).join("")}</div></div>`).join("")}
      ${F.length >= MAX ? `<p class="mut fs13">${esc(`Höchstens ${MAX} Favoriten-Sportarten.`)}</p>` : ""}
      <div class="row mt10"><button type="button" class="btn" id="favsave">Speichern</button><button type="button" class="btn ghost" id="favstd">Standard wiederherstellen</button><span class="ok" id="favok" role="status">${esc(msg)}</span></div>
      <p class="bad sgerr" id="faverr" role="alert">${esc(err)}</p>`;
    msg = err = "";
    if (focus) {
      const f = box.querySelector(focus);
      if (f && !f.disabled) f.focus();
    }
  };
  box.addEventListener("click", async e => {
    const b = e.target.closest("button");
    if (!b) return;
    const k = b.dataset.k, i = F.indexOf(k);
    if (b.classList.contains("favst")) {
      if (i >= 0) F.splice(i, 1);
      else if (F.length < MAX) F.push(k);
      return draw(`.favst[data-k="${k}"]`);
    }
    if (b.classList.contains("favup") && i > 0) {
      [F[i - 1], F[i]] = [F[i], F[i - 1]];
      return draw(`.favup[data-k="${k}"]`);
    }
    if (b.classList.contains("favdn") && i >= 0 && i < F.length - 1) {
      [F[i + 1], F[i]] = [F[i], F[i + 1]];
      return draw(`.favdn[data-k="${k}"]`);
    }
    const put = async ok => {
      b.disabled = true;
      try {
        const r = await api("/api/aktivitaeten/favoriten", {method: "PUT", headers: {"content-type": "application/json"}, body: JSON.stringify({favoriten: F})});
        F = r.favoriten.slice();
        FAV = F.slice();
        msg = ok;
      } catch (x) {
        err = "Speichern nicht möglich: " + (x.message || String(x));
      }
      draw("#favsave");
    };
    if (b.id === "favstd") {                                                    // 3.61.0: „Standard wiederherstellen“ mit Rückfrage, speichert gleich (Leitfaden 2.3)
      const std = (d.standard || FAV_DEF).filter(k => SPORT[k]);
      if (!(await uiConfirm({title: "Standard wiederherstellen?", text: `Die Favoriten-Sportarten werden wieder: ${std.map(k => sName(k)).join(", ")}.`, ok: "Standard wiederherstellen"}))) return;
      F = std.slice();
      return put("Standard wiederhergestellt");
    }
    if (b.id === "favsave") {
      if (!F.length) {
        box.querySelector("#faverr").textContent = "Bitte mindestens eine Favoriten-Sportart wählen.";
        return;
      }
      return put("Favoriten-Sportarten gespeichert");
    }
  });
  draw();
}

/* 3.60.0 Aktivitäten-Katalog (Verwaltung → Aktivitäten, nur lesen): die 29 Aktivitäten nach Kategorien mit Symbol und Kartenfarbe (SPORT_TABLE, 01-grundlagen.js).
   (3.67.0: der Abschnitt „Frühere Sportarten“ ist entfernt; der Rückfall SPORT_ALIAS / sport_alt bleibt, ältere Touren zählen weiter als die Sportart, auf die er verweist.) */
function katAdmin(box) {
  if (!box) return;
  const T = typeof TOURS !== "undefined" && Array.isArray(TOURS) ? TOURS : [];
  const n = k => T.filter(t => t && (t.sport_alt || t.sport) === k).length;      // loadTours merkt sich den entfernten Schlüssel in sport_alt
  const item = k => `<li class="katit" data-k="${k}"><span class="katdot" style="background:var(${SPORT[k][1]})" aria-hidden="true"></span><span class="katic" aria-hidden="true">${SPORT[k][2]}</span><span class="katn">${esc(SPORT[k][0])}</span></li>`;
  box.innerHTML = `<p class="mut">Diese Sportarten bietet Meine Touren überall an – beim Aufzeichnen, Importieren und Planen, in Filtern und in der Statistik. Symbol und Farbe erscheinen in Listen und auf der Karte.</p>
    ${SPORT_CAT.map(([id, l, ks]) => `<div class="sgcat"><span class="sgcl" id="katc-${id}">${esc(l)}</span><ul class="katlist" aria-labelledby="katc-${id}">${ks.map(item).join("")}</ul></div>`).join("")}`;
}
