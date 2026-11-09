/* =====================  E-Mail, Zwei-Faktor-Anmeldung (Konto) und E-Mail-Versand (Verwaltung)  ===================== */
const J35 = {"content-type": "application/json"};
const post35 = (u, d) => api(u, {method: "POST", headers: J35, body: JSON.stringify(d || {})});

function codesBox(codes) {
  const txt = codes.join("\n"),
    m = modal(`<h3>Wiederherstellungscodes</h3><p class="mut fs14">Bewahre diese Codes sicher auf (z. B. ausgedruckt oder im Passwort-Manager). Jeder Code funktioniert <b>einmal</b> und ersetzt den Authenticator-Code, falls dein Handy weg ist. <b>Sie werden nur jetzt angezeigt.</b></p>
      <pre class="fs18 lh1_6 p10-14 br8" style="background:var(--paper,#0001);user-select:all">${esc(txt)}</pre>
      <div class="row jce"><button class="btn alt" id="cdc">Kopieren</button><button class="btn" id="cdx">Ich habe sie gespeichert</button></div>`);
  m.querySelector("#cdc").onclick = async e => {
    try {
      await navigator.clipboard.writeText(txt);
      e.target.textContent = "✓ Kopiert";
    } catch (x) {}
  };
  m.querySelector("#cdx").onclick = () => m.remove();
}

function loadQr() {
  return window.qrcode
    ? Promise.resolve()
    : new Promise((res, rej) => {
        const s = document.createElement("script");
        s.src = "/vendor/qrcode.js";
        s.onload = res;
        s.onerror = rej;
        document.head.appendChild(s);
      });
}

/* Zwei-Faktor einrichten: QR-Code scannen, Code bestätigen, Wiederherstellungscodes anzeigen */
async function setup2fa(done) {
  const s = await post35("/api/me/2fa/setup");
  let qr = "";
  try {
    await loadQr();
    const q = qrcode(0, "M");
    q.addData(s.uri);
    q.make();
    qr = q.createSvgTag(5, 3).replace("<svg ", '<svg style="width:100%;height:auto;display:block" ');
  } catch (e) {}
  const spaced = s.secret.replace(/(.{4})/g, "$1 ").trim(),
    m = modal(`<h3>Zwei-Faktor-Anmeldung einrichten</h3>
      <ol class="pl20 lh1_5"><li>Installiere eine Authenticator-App (z. B. Google Authenticator, Microsoft Authenticator, Aegis, 2FAS oder Bitwarden).</li>
      <li>Scanne den QR-Code – oder tippe auf „In der App öffnen“, falls die App auf diesem Handy ist.</li>
      <li>Gib den angezeigten 6-stelligen Code ein.</li></ol>
      <div class="mw230 br8 p4" style="margin:8px auto;background:#fff">${qr || '<p class="mut p20">QR-Code nicht verfügbar – bitte den Schlüssel unten eingeben.</p>'}</div>
      <p class="mut fs13 tac">Schlüssel zum Abtippen:<br><code class="fs15" style="user-select:all">${esc(spaced)}</code><br><a href="${esc(s.uri)}">In der App öffnen</a></p>
      <label>6-stelliger Code<input id="t2c" inputmode="numeric" autocomplete="one-time-code" maxlength="8" class="w100"></label>
      <div class="bad" id="t2e" style="min-height:1.3em"></div>
      <div class="row jce"><button class="btn alt" id="t2x">Abbrechen</button><button class="btn" id="t2ok">Einschalten</button></div>`);
  m.querySelector("#t2x").onclick = () => m.remove();
  m.querySelector("#t2ok").onclick = async () => {
    try {
      const r = await post35("/api/me/2fa/enable", {code: m.querySelector("#t2c").value});
      m.remove();
      codesBox(r.codes);
      done();
    } catch (e) {
      m.querySelector("#t2e").textContent = e.message;
    }
  };
}

const _acc35 = VIEWS.account;
VIEWS.account = async (...a) => {
  await _acc35(...a);
  if (!ME.user || ME.user.role === "viewer" || $("#sec35")) return;
  const st = await api("/api/me/2fa").catch(() => null),
    grid = document.querySelector("#main .grid.g2");
  if (!st || !grid) return;
  const mail = st.email;
  grid.insertAdjacentHTML(
    "beforebegin",
    `<div class="grid g2" id="sec35"><div class="panel"><h2>E-Mail-Adresse</h2>
      <p class="mut fs14">${mail ? `Hinterlegt: <b>${esc(mail)}</b>` : `<b>Noch keine E-Mail-Adresse hinterlegt.</b>`} Sie wird zum Zurücksetzen des Passworts („Passwort vergessen?“) und für Sicherheitshinweise benutzt.</p>
      <div class="field"><label>Neue E-Mail-Adresse</label><input id="em1" type="email" autocomplete="email" value="${esc(mail || "")}"></div>
      <div class="field"><label>Zur Bestätigung dein Passwort</label><input id="em2" type="password" autocomplete="current-password"></div>
      <div class="row"><button class="btn" id="emb">Speichern</button><span id="emm" class="mut"></span></div></div>
     <div class="panel"><h2>Zwei-Faktor-Anmeldung</h2>
      ${
        st.on
          ? `<p>✅ <b>Eingeschaltet.</b> Bei der Anmeldung wird nach dem Passwort ein Code aus deiner Authenticator-App abgefragt.</p><p class="mut fs14">Noch ${st.recovery_left} Wiederherstellungscode${st.recovery_left === 1 ? "" : "s"} übrig.</p>
             <div class="field"><label>Dein Passwort</label><input id="tf1" type="password" autocomplete="current-password"></div><div class="field"><label>Aktueller Code (oder Wiederherstellungscode)</label><input id="tf2" inputmode="numeric" autocomplete="one-time-code"></div>
             <div class="row"><button class="btn alt" id="tfoff">Ausschalten</button><button class="btn alt" id="tfrec">Neue Wiederherstellungscodes</button><span id="tfm" class="mut"></span></div>`
          : `<p class="mut">Schützt dein Konto zusätzlich: Nach dem Passwort wird ein 6-stelliger Code aus einer Authenticator-App auf deinem Handy verlangt. Auch wenn jemand dein Passwort kennt, kommt er so nicht hinein.</p>
             <div class="row"><button class="btn" id="tfon">Einrichten …</button><span id="tfm" class="mut"></span></div>`
      }</div></div>`
  );
  if (!mail) $("#sec35").scrollIntoView?.({block: "nearest"});
  $("#emb").onclick = async () => {
    try {
      await post35("/api/me/email", {email: $("#em1").value, password: $("#em2").value});
      $("#emm").textContent = "✓ Gespeichert";
      ME.user.email = $("#em1").value;
      $("#em2").value = "";
    } catch (e) {
      $("#emm").textContent = e.message;
    }
  };
  const again = () => VIEWS.account();
  if ($("#tfon")) $("#tfon").onclick = () => setup2fa(() => ((ME.user.totp_on = 1), $("#sec35").remove(), again())).catch(e => ($("#tfm").textContent = e.message));
  if ($("#tfoff"))
    $("#tfoff").onclick = async () => {
      try {
        await post35("/api/me/2fa/disable", {password: $("#tf1").value, code: $("#tf2").value});
        ME.user.totp_on = 0;
        $("#sec35").remove();
        again();
      } catch (e) {
        $("#tfm").textContent = e.message;
      }
    };
  if ($("#tfrec"))
    $("#tfrec").onclick = async () => {
      try {
        const r = await post35("/api/me/2fa/recovery", {password: $("#tf1").value, code: $("#tf2").value});
        codesBox(r.codes);
        $("#tf1").value = $("#tf2").value = "";
      } catch (e) {
        $("#tfm").textContent = e.message;
      }
    };
};

/* Verwaltung → Automatik & Meldungen: E-Mail-Versand (SMTP) */
const _adm35 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _adm35(...a);
  if ($("#mailbox") || !isAdmin() || !$("#save")) return;
  const c = await api("/api/mail/settings").catch(() => null);
  if (!c) return;
  const box = `<div class="panel" id="mailbox"><h2>E-Mail-Versand</h2>
    <p class="mut fs13">Wird für „Passwort vergessen?“ und Sicherheitshinweise gebraucht. Trage die Zugangsdaten deines E-Mail-Anbieters ein (z. B. Yahoo, GMX, web.de, Gmail – dort meist ein eigenes „App-Passwort“). Das Passwort wird nur auf dem Server gespeichert und nie wieder angezeigt.</p>
    <div class="grid g2"><div class="field"><label>SMTP-Server</label><input id="ml_h" value="${esc(c.smtp_host)}" placeholder="smtp.mail.yahoo.com"></div>
    <div class="field"><label>Port</label><input id="ml_p" inputmode="numeric" value="${esc(c.smtp_port)}" placeholder="587"></div>
    <div class="field"><label>Verschlüsselung</label><select id="ml_m"><option value="starttls">STARTTLS (Port 587)</option><option value="ssl">SSL/TLS (Port 465)</option><option value="none">keine (nicht empfohlen)</option></select></div>
    <div class="field"><label>Benutzername</label><input id="ml_u" value="${esc(c.smtp_user)}" autocomplete="off"></div>
    <div class="field"><label>Passwort ${c.pw_set ? "(gespeichert – leer lassen zum Behalten)" : ""}</label><input id="ml_w" type="password" autocomplete="new-password"></div>
    <div class="field"><label>Absenderadresse</label><input id="ml_f" type="email" value="${esc(c.smtp_from)}" placeholder="meine-touren@example.com"></div></div>
    <div class="field"><label>Öffentliche Adresse dieser App (für den Link in der Mail)</label><input id="ml_a" value="${esc(c.public_url || location.origin)}" placeholder="https://meine-touren.example.ts.net"></div>
    <div class="row"><button class="btn" id="ml_s">Speichern</button><button class="btn alt" id="ml_t">Testmail an mich senden</button><span id="ml_x" class="mut">${c.ready ? "✓ eingerichtet" : "noch nicht eingerichtet"}</span></div></div>`;
  $("#save").closest(".row").insertAdjacentHTML("beforebegin", box);
  $("#ml_m").value = c.smtp_mode;
  const save = async () => {
    await post35("/api/mail/settings", {smtp_host: $("#ml_h").value, smtp_port: $("#ml_p").value, smtp_mode: $("#ml_m").value, smtp_user: $("#ml_u").value, smtp_from: $("#ml_f").value, public_url: $("#ml_a").value, smtp_pw: $("#ml_w").value});
    $("#ml_w").value = "";
  };
  $("#ml_s").onclick = async () => {
    try {
      await save();
      $("#ml_x").textContent = "✓ Gespeichert";
    } catch (e) {
      $("#ml_x").textContent = e.message;
    }
  };
  $("#ml_t").onclick = async () => {
    $("#ml_x").textContent = "Sende …";
    try {
      await save();
      const r = await post35("/api/mail/test");
      $("#ml_x").textContent = "✓ Testmail an " + r.to + " gesendet";
    } catch (e) {
      $("#ml_x").textContent = e.message;
    }
  };
};
