/* =====================  Handy: Installation, Teilen-Ziel, Ergebnisseite  ===================== */
let _installEv = null;
window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  _installEv = e;
  const b = document.querySelector("#pwainst");
  if (b) b.style.display = "";
});
window.addEventListener("appinstalled", () => (_installEv = null));

/* Ergebnis nach „Teilen mit Meine Touren“ */
VIEWS.shared = async (id, q) => {
  q = q || new URLSearchParams(location.hash.split("?")[1] || "");
  const g = k => +(q.get(k) || 0),
    t = g("t"),
    d = g("d"),
    a = g("a"),
    p = g("p"),
    x = g("x");
  await loadTours().catch(() => {});
  const line = (ok, txt) => `<div class="r"><span>${ok ? "✓" : "•"} ${txt}</span></div>`;
  $("#main").innerHTML = `<div class="sec" style="margin-top:0"><h2>Mit Meine Touren geteilt</h2></div><div class="rows">${
    (a ? line(t > 0, t ? `${t} Tour${t === 1 ? "" : "en"} importiert` : d ? "Die Tour war schon vorhanden" : "Aus der Datei konnte keine Tour übernommen werden (keine GPS-Punkte?)") : "") +
    (d && t ? line(false, `${d} schon vorhanden`) : "") +
    (p ? line(true, `${p} Foto${p === 1 ? "" : "s"} empfangen – werden im Hintergrund den Touren zugeordnet`) : "") +
    (x ? line(false, `${x} Datei${x === 1 ? "" : "en"} mit nicht unterstütztem Typ übersprungen`) : "") ||
    '<p class="mut">Es wurde nichts empfangen.</p>'
  }</div><div class="row" style="margin-top:14px"><a class="btn" href="#/tours">Zu den Touren</a></div>`;
};

/* Verwaltung → Übersicht: „Auf dem Handy“ */
const _admin29 = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admin29(...a);
  if ($("#handy") || !$("#save")) return;
  const secure = window.isSecureContext,
    standalone = matchMedia("(display-mode: standalone)").matches;
  const html = `<div class="panel" id="handy"><h2>Auf dem Handy</h2>
    <p class="mut">Meine Touren lässt sich wie eine App auf dem Startbildschirm installieren. Danach erscheint sie im <b>Teilen-Menü</b> von Android: GPX-/FIT-Dateien und Fotos aus anderen Apps (Garmin, Komoot, Galerie …) lassen sich direkt an Meine Touren senden.</p>
    <p>${standalone ? "✓ Läuft gerade als installierte App." : secure ? "✓ Gesicherte Verbindung (HTTPS) – Installation möglich." : '<span class="bad">Diese Adresse ist nicht gesichert (HTTP).</span> Chrome installiert die App dann nur als einfache Verknüpfung, ohne Teilen-Menü und ohne Offline-Funktion.'}</p>
    <div class="row" style="gap:8px"><button class="btn" id="pwainst" style="${_installEv ? "" : "display:none"}">App installieren</button></div>
    ${secure ? "" : `<p class="mut" style="font-size:13px;margin-top:8px"><b>So bekommst du HTTPS:</b> am einfachsten mit <b>Tailscale</b> (kostenlos): auf Server und Handy installieren, auf dem Server <code>tailscale serve --bg 80</code> ausführen und die angezeigte Adresse <code>https://…ts.net</code> öffnen. Alternativ ein Reverse-Proxy mit eigener Domain (Caddy, Nginx Proxy Manager). Einzelheiten: README → „Handy und HTTPS“.</p>`}
    <p class="mut" style="font-size:13px;margin-top:8px">Ohne Installation: In Chrome ⋮ → „Zum Startbildschirm hinzufügen“.</p></div>`;
  const body = document.querySelector('.atab[data-t="handy"] .gbody');
  if (body) body.insertAdjacentHTML("beforeend", html);
  else $("#save").closest(".row").insertAdjacentHTML("beforebegin", html);
  const b = $("#pwainst");
  if (b)
    b.onclick = async () => {
      if (!_installEv) return;
      _installEv.prompt();
      await _installEv.userChoice.catch(() => {});
      _installEv = null;
      b.style.display = "none";
    };
};

/* Offline-Hinweis: ohne Verbindung zeigt die App zuletzt gesehene Daten (Service Worker) */
(() => {
  const upd = () => {
    let b = document.querySelector("#offbar");
    if (navigator.onLine === false) {
      if (!b) {
        b = document.createElement("div");
        b.id = "offbar";
        b.className = "offbar noprint";
        b.textContent = "Offline – es werden zuletzt gesehene Daten angezeigt. Speichern und Hochladen sind erst mit Verbindung möglich.";
        document.body.prepend(b);
      }
    } else if (b) b.remove();
  };
  window.addEventListener("offline", upd);
  window.addEventListener("online", upd);
  upd();
})();
