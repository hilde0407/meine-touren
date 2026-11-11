/* Skript der Seite reset.html (eigene Datei, damit die Content-Security-Policy Inline-Skripte verbieten kann) */
const tok = location.pathname.split("/").pop(), c = document.getElementById("c");
fetch("/api/reset/" + encodeURIComponent(tok)).then(r => { if (!r.ok) throw 0; return r.json(); }).then(u => {
  c.innerHTML = `<p class="mut">Konto: <b></b></p><form><label for="p1">Neues Passwort (mindestens 8 Zeichen)</label><input id="p1" type="password" autocomplete="new-password" minlength="8" required>
    <label for="p2">Passwort wiederholen</label><input id="p2" type="password" autocomplete="new-password" minlength="8" required><div class="bad" id="e"></div><button type="submit">Passwort speichern</button></form>`;
  c.querySelector("b").textContent = u.name;
  c.querySelector("form").onsubmit = async ev => {
    ev.preventDefault();
    const e = document.getElementById("e"); e.textContent = "";
    if (p1.value !== p2.value) { e.textContent = "Die Passwörter sind nicht gleich."; return; }
    const r = await fetch("/api/reset", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({token: tok, password: p1.value})});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { e.textContent = j.detail || "Das hat nicht geklappt."; return; }
    c.innerHTML = `<p class="ok"><b>Dein Passwort wurde geändert.</b></p><p class="mut">Du kannst dich jetzt mit dem neuen Passwort anmelden.${j.totp ? " Danach wird noch der Code aus deiner Authenticator-App abgefragt." : ""}</p><a class="b" href="/">Zur Anmeldung</a>`;
  };
}).catch(() => { c.innerHTML = '<p class="bad">Dieser Link ist abgelaufen oder wurde schon benutzt.</p><p class="mut">Du kannst auf der Anmeldeseite einen neuen anfordern („Passwort vergessen?“).</p><a class="b" href="/">Zur Anmeldung</a>'; });
