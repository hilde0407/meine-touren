/* =====================  Benutzer, Anmeldung, Freigaben, Mobilansicht  ===================== */
let ME = {users_enabled: false, user: null};
const initials = n =>
  (n || "?")
    .split(/\s+/)
    .map(x => x[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
/* „Info“: laufende Versionen und Ersteller */
async function aboutBox() {
  let sv = "";
  try {
    sv = (await (await fetch("/api/version")).json()).version || "";
  } catch (e) {}
  let app = "";
  try {
    if (window.MTApp && MTApp.version) app = MTApp.version();
  } catch (e) {}
  const m = modal(`<h3>Meine Touren</h3>
    <div class="rows"><div class="r"><span>Android-App<small>${app ? "läuft auf diesem Gerät" : "du nutzt gerade den Browser"}</small></span><b>${app ? esc(app) : "–"}</b></div>
    <div class="r"><span>Server<small>dein Meine-Touren-Server</small></span><b>${esc((sv.split(" ·")[0] || "?").trim())}</b></div></div>
    <p class="mut fs13 m6-0-0">${esc(sv)}</p>
    <h4 class="m18-0-6">Ersteller</h4>
    <p class="m0">Entwickelt von <b>Volker Hildebrand</b> gemeinsam mit <b>Claude</b> (KI-Assistent von Anthropic).</p>
    <p class="mut fs13 m10-0-0">Karten © OpenStreetMap-Mitwirkende. Freie Software, Quellcode auf GitHub (hilde0407/meine-touren).</p>
    <div class="row jce mt14"><button class="btn" id="abx">Schließen</button></div>`);
  m.classList.add("sheet");
  m.querySelector("#abx").onclick = () => m.remove();
}
/* Anmeldehelfer: JSON senden, Fehlermeldung des Servers lesbar machen */
async function postJson(url, body) {
  const r = await fetch(url, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
  let t = await r.text(),
    j = {};
  try {
    j = JSON.parse(t);
  } catch (x) {}
  if (!r.ok) throw new Error(j.detail || t || "Fehler " + r.status);
  return j;
}
/* Zweiter Schritt der Anmeldung: Code aus der Authenticator-App (oder Wiederherstellungscode) */
function codeBox(w, ticket) {
  w.querySelector("form").innerHTML = `<div class="brandl">Meine Touren</div><h2>Bestätigungscode</h2>
    <p class="mut">Gib den 6-stelligen Code aus deiner Authenticator-App ein. Hast du dein Handy nicht zur Hand, kannst du einen Wiederherstellungscode (z. B. a1b2c3-d4e5f6) verwenden.</p>
    <label>Code<input id="au_c" inputmode="numeric" autocomplete="one-time-code" autocapitalize="off" required></label>
    <div class="bad" id="au_e"></div><div class="row"><button class="btn" type="submit">Anmelden</button></div>`;
  $("#au_c").focus();
  w.querySelector("form").onsubmit = async e => {
    e.preventDefault();
    try {
      const j = await postJson("/api/login/2fa", {ticket, code: $("#au_c").value});
      location.hash = "#/dash";
      location.reload();
    } catch (x) {
      $("#au_e").textContent = x.message;
    }
  };
}
/* „Passwort vergessen?“ */
function forgotBox(w, who) {
  w.querySelector("form").innerHTML = `<div class="brandl">Meine Touren</div><h2>Passwort vergessen</h2>
    <p class="mut">Gib deine E-Mail-Adresse oder deinen Namen ein. Du bekommst einen Link zum Festlegen eines neuen Passworts.</p>
    <label>E-Mail-Adresse oder Name<input id="au_w" autocomplete="username" value="${esc(who || "")}" required></label>
    <div class="bad" id="au_e"></div><div class="row"><button class="btn" type="submit">Link senden</button><button class="btn alt" type="button" id="au_b">Zurück</button></div>`;
  $("#au_w").focus();
  $("#au_b").onclick = () => showAuth("login");
  w.querySelector("form").onsubmit = async e => {
    e.preventDefault();
    try {
      await postJson("/api/forgot", {who: $("#au_w").value});
      w.querySelector("form").innerHTML = `<div class="brandl">Meine Touren</div><h2>E-Mail ist unterwegs</h2><p>Wenn zu deinen Angaben ein Konto mit E-Mail-Adresse gehört, haben wir einen Link zum Zurücksetzen geschickt. Er gilt eine Stunde. Schau bitte auch im Spam-Ordner nach.</p><div class="row"><button class="btn" type="button" id="au_b">Zur Anmeldung</button></div>`;
      $("#au_b").onclick = () => showAuth("login");
    } catch (x) {
      $("#au_e").textContent = x.message;
    }
  };
}
function showAuth(kind, msg = "") {
  document.querySelector(".authwrap")?.remove();
  const setup = kind === "setup",
    w = document.createElement("div");
  w.className = "authwrap";
  w.innerHTML = `<form class="authbox" autocomplete="on"><div class="brandl">Meine Touren</div><h2>${setup ? "Benutzerverwaltung einrichten" : "Anmelden"}</h2>
    ${setup ? `<p class="mut">Du legst jetzt den ersten Benutzer an, er wird Administrator. Alle bisherigen Touren, Fotos und Einstellungen gehören danach ihm. Weitere Benutzer legst du anschließend selbst an.</p>` : ""}
    <label>Name<input id="au_n" name="username" autocomplete="username" required></label>
    ${setup ? `<label>E-Mail-Adresse<input id="au_m" type="email" autocomplete="email" required><small class="mut">Wird zum Zurücksetzen des Passworts verwendet.</small></label>` : ""}
    <label>Passwort<input id="au_p" name="password" type="password" autocomplete="${setup ? "new-password" : "current-password"}" required minlength="${setup ? 8 : 1}"></label>
    ${setup ? `<label>Passwort wiederholen<input id="au_p2" type="password" autocomplete="new-password" required></label><p class="mut fs13">Mindestens 8 Zeichen.</p>` : ""}
    <div class="bad" id="au_e">${esc(msg)}</div><div class="row"><button class="btn" type="submit">${setup ? "Einrichten" : "Anmelden"}</button>${setup ? '<button class="btn alt" type="button" id="au_x">Später</button>' : ""}</div>${setup ? "" : '<p class="m14-0-0"><a href="#" id="au_f">Passwort vergessen?</a></p>'}</form>`;
  document.body.appendChild(w);
  $("#au_n").focus();
  if (setup) $("#au_x").onclick = () => w.remove();
  if ($("#au_f")) $("#au_f").onclick = e => (e.preventDefault(), forgotBox(w, $("#au_n").value));
  w.querySelector("form").onsubmit = async e => {
    e.preventDefault();
    $("#au_e").textContent = "";
    if (setup && $("#au_p").value !== $("#au_p2").value) {
      $("#au_e").textContent = "Die Passwörter sind nicht gleich.";
      return;
    }
    try {
      const j = await postJson(setup ? "/api/setup" : "/api/login", {name: $("#au_n").value, password: $("#au_p").value, email: setup ? $("#au_m").value : undefined});
      if (j && j.need_2fa) return codeBox(w, j.ticket);
      location.hash = "#/dash";
      location.reload();
    } catch (x) {
      $("#au_e").textContent = x.message;
    }
  };
}
/* Ansicht: automatisch / mobil / Desktop */
const viewPref = () => {
  try {
    return localStorage.getItem("viewmode") || "auto";
  } catch (e) {
    return "auto";
  }
};
const MORE = [
  ["trips", "Reisen"],
  ["places", "Auswertung"],
  ["check", "Prüfen"],
  ["shared", "Geteilte Fotos"],
  ["account", "Konto & Freigaben"],
  ["admin", "Verwaltung"],
];
// Einträge, die unter „Einstellungen & Prüfung“ stehen (alles andere ist ein Hauptpunkt oben im Menü)
const MORE_SET = ["account", "check", "admin", "apptest"];
const isViewer = () => !!(ME.user && ME.user.role === "viewer");
function applyView() {
  document.documentElement.classList.toggle("viewer", isViewer());
  const m = viewPref(),
    mob = m === "mobile" || (m === "auto" && matchMedia("(max-width: 760px)").matches);
  document.documentElement.classList.toggle("mob", mob);
  let tb = $("#tabbar");
  if (!tb) {
    tb = document.createElement("div");
    tb.id = "tabbar";
    document.body.appendChild(tb);
  }
  const T = [
    ["dash", "Übersicht", "🏠"],
    ["map", "Karte", "🗺"],
    ["tours", "Touren", "🥾"],
    ["photos", "Fotos", "🖼"],
  ];
  tb.innerHTML =
    T.map(([k, l, i]) => `<a href="#/${k}" data-k="${k}"><span class="ti">${i}</span><span>${l}</span></a>`).join("") +
    `<button id="tmore"><span class="ti">☰</span><span>Mehr</span></button>`;
  $("#tmore").onclick = () => {
    const items = isViewer() ? MORE.filter(x => ["trips", "places"].includes(x[0])) : MORE,
      lnk = ([k, l]) => `<a class="btn alt" href="#/${k}">${l}</a>`,
      main = items.filter(x => !MORE_SET.includes(x[0])),
      sett = items.filter(x => MORE_SET.includes(x[0]));
    const m2 = modal(`<h3>Mehr</h3><div class="moregrid">${main.map(lnk).join("")}</div>
      ${sett.length ? `<h4 class="m16-0-6">Einstellungen & Prüfung</h4><div class="moregrid sm">${sett.map(lnk).join("")}</div>` : ""}
      <h4 class="m16-0-6">Ansicht</h4><div class="row">${[
        ["auto", "Automatisch"],
        ["mobile", "Smartphone"],
        ["desktop", "Computer"],
      ]
        .map(([k, l]) => `<button class="btn ${viewPref() === k ? "" : "alt"} sm" data-vm="${k}">${l}</button>`)
        .join("")}</div>
      <div class="row mt16"><button class="btn alt sm" id="mab">ℹ️ Info: Version &amp; Ersteller</button></div>
      ${ME.user ? `<div class="row mt16"><button class="btn alt" id="mlo">Abmelden (${esc(ME.user.name)})</button></div>` : ""}`);
    m2.classList.add("sheet");
    m2.querySelectorAll("a").forEach(a => (a.onclick = () => m2.remove()));
    m2.querySelectorAll("[data-vm]").forEach(
      b =>
        (b.onclick = () => {
          try {
            localStorage.setItem("viewmode", b.dataset.vm);
          } catch (e) {}
          m2.remove();
          applyView();
        })
    );
    if ($("#mlo")) $("#mlo").onclick = doLogout;
    m2.querySelector("#mab").onclick = () => (m2.remove(), aboutBox());
  };
  markTabs();
}
const markTabs = () => {
  const k = (location.hash || "#/dash").replace(/^#\/?/, "").split(/[/?]/)[0],
    kk = k === "tour" || k === "flight" ? "tours" : k;
  document.querySelectorAll("#tabbar a").forEach(a => a.classList.toggle("on", a.dataset.k === kk));
};
addEventListener("hashchange", markTabs);
let rzT;
addEventListener("resize", () => {
  clearTimeout(rzT);
  rzT = setTimeout(applyView, 150);
});
async function doLogout() {
  try {
    await fetch("/api/logout", {method: "POST"});
  } catch (e) {}
  location.hash = "#/dash";
  location.reload();
}

function userMenu() {
  const top = document.querySelector("header.top");
  if (!top || $("#umenu")) return;
  const b = document.createElement("button");
  b.id = "umenu";
  b.className = "umenu";
  b.innerHTML = ME.user
    ? `<span class="av">${esc(initials(ME.user.name))}</span><span class="un">${esc(ME.user.name)}</span>`
    : `<span class="av">👥</span><span class="un">Benutzer</span>`;
  top.insertBefore(b, $("#busy"));
  b.onclick = () => {
    document.querySelector(".umpop")?.remove();
    const p = document.createElement("div");
    p.className = "umpop";
    p.innerHTML = ME.user
      ? `<div class="mut p6-12">${esc(ME.user.name)} · ${ME.user.role === "admin" ? "Administrator" : "Benutzer"}</div><a href="#/account">Konto &amp; Freigaben</a><a href="#/shared">Geteilte Fotos</a><button id="uma">Info</button><button id="umo">Abmelden</button>`
      : `<div class="mut p6-12">Noch keine Benutzerverwaltung</div><button id="ums">Benutzer einrichten …</button><button id="uma">Info</button>`;
    document.body.appendChild(p);
    setTimeout(
      () =>
        document.addEventListener("click", function h(e) {
          if (!p.contains(e.target)) {
            p.remove();
            document.removeEventListener("click", h);
          }
        }),
      0
    );
    p.querySelectorAll("a").forEach(a => (a.onclick = () => p.remove()));
    if ($("#umo")) $("#umo").onclick = doLogout;
    if ($("#uma")) $("#uma").onclick = () => (p.remove(), aboutBox());
    if ($("#ums"))
      $("#ums").onclick = () => {
        p.remove();
        showAuth("setup");
      };
  };
}

VIEWS.account = async () => {
  const [gr, us] = await Promise.all([api("/api/grants").catch(() => ({mine: [], received: []})), api("/api/users").catch(() => [])]),
    me = ME.user,
    adm = me && me.role === "admin";
  if (!me) {
    $("#main").innerHTML =
      `<div class="sec mt0"><h2>Konto &amp; Freigaben</h2></div><div class="panel"><p>Die Benutzerverwaltung ist noch nicht eingerichtet. Mit „Einrichten“ legst du den ersten Benutzer (Administrator) an; deine bisherigen Daten werden ihm zugeordnet.</p><button class="btn" id="setupb">Einrichten …</button></div>`;
    $("#setupb").onclick = () => showAuth("setup");
    return;
  }
  const others = us.filter(u => u.uid !== me.uid && (u.active === undefined || u.active));
  $("#main").innerHTML =
    `<div class="sec mt0"><h2>Konto &amp; Freigaben</h2><span class="sub">${esc(me.name)} · ${adm ? "Administrator" : "Benutzer"}</span></div>
   <div class="grid g2"><div class="panel"><h2>Passwort ändern</h2><div class="field"><label>Altes Passwort</label><input id="pw0" type="password" autocomplete="current-password"></div><div class="field"><label>Neues Passwort (mind. 8 Zeichen)</label><input id="pw1" type="password" autocomplete="new-password"></div>
     <div class="row"><button class="btn" id="pwb">Ändern</button><span id="pwm" class="mut"></span></div></div>
    <div class="panel"><h2>Ansicht</h2><p class="mut">Gilt nur auf diesem Gerät.</p><div class="row">${[
      ["auto", "Automatisch"],
      ["mobile", "Smartphone-Ansicht"],
      ["desktop", "Computer-Ansicht"],
    ]
      .map(([k, l]) => `<button class="btn ${viewPref() === k ? "" : "alt"} sm" data-vm="${k}">${l}</button>`)
      .join("")}</div></div></div>
   <div class="sec"><h2>Fotos freigeben</h2><span class="sub">Andere Benutzer können freigegebene Fotos ansehen und in ihre Bibliothek übernehmen. Deine Originale bleiben bei dir.</span></div>
   <div class="grid g2"><div class="panel"><h2>Neue Freigabe</h2>
     <div class="field"><label>Für</label><select id="gg"><option value="*">Alle Benutzer</option>${others.map(u => `<option value="${esc(u.uid)}">${esc(u.name)}</option>`).join("")}</select></div>
     <div class="field"><label>Was</label><select id="gs2"><option value="all">Meine ganze Fotobibliothek</option><option value="tour">Nur die Fotos einer Tour</option></select></div>
     <div class="field" id="gtw" style="display:none"><label>Tour</label><select id="gt">${TOURS.slice(0, 400)
       .map(t => `<option value="${t.id}">${dateS(t.date)} · ${esc(t.name)}</option>`)
       .join("")}</select></div>
     <div class="row"><button class="btn" id="gadd">Freigeben</button><span id="gm" class="mut"></span></div></div>
    <div class="panel"><h2>Von mir freigegeben</h2><div class="rows">${gr.mine.map(g => `<div class="r"><span>${esc(g.grantee_name)}<small>${g.scope === "all" ? "ganze Fotobibliothek" : "Tour: " + esc(g.ref_name || g.ref)}</small></span><button class="btn alt sm" data-gd="${g.id}">Entfernen</button></div>`).join("") || '<div class="mut">Noch nichts freigegeben.</div>'}</div>
     <h2 class="mt18">Mit mir geteilt</h2><div class="rows">${gr.received.map(g => `<div class="r"><span>${esc(g.owner_name)}<small>${g.scope === "all" ? "ganze Fotobibliothek" : "einzelne Tour"}</small></span></div>`).join("") || '<div class="mut">Noch nichts geteilt.</div>'}</div>
     <div class="row"><a class="btn alt sm" href="#/shared">Geteilte Fotos ansehen</a></div></div></div>
   ${
     adm
       ? `<div class="sec"><h2>Benutzer verwalten</h2></div><div class="panel"><div class="rows">${us
           .map(
             u => `<div class="r" style="display:block"><b>${esc(u.name)}</b> <span class="mut">${u.role === "admin" ? "Administrator" : u.role === "viewer" ? "Betrachter (sieht die Daten von " + esc((us.find(x => x.uid === u.owner) || {}).name || "?") + ")" : "Benutzer"}${u.active ? "" : " · gesperrt"}${u.me ? " · du" : ""}</span><br><small class="mut">${u.email ? esc(u.email) : "keine E-Mail-Adresse"}${u.totp_on ? " · Zwei-Faktor an" : ""}</small>
      <div class="row m6-0-0">${u.role === "viewer" ? "" : `<button class="btn alt sm" data-ur="${u.uid}">${u.role === "admin" ? "Zum Benutzer machen" : "Zum Admin machen"}</button>`}<button class="btn alt sm" data-up="${u.uid}">Passwort setzen</button><button class="btn alt sm" data-um="${u.uid}">E-Mail ändern</button>${u.totp_on && !u.me ? `<button class="btn alt sm" data-u2="${u.uid}">Zwei-Faktor zurücksetzen</button>` : ""}${u.me ? "" : `<button class="btn alt sm" data-ua="${u.uid}">${u.active ? "Sperren" : "Entsperren"}</button><button class="btn alt sm" data-ud="${u.uid}">Löschen</button>`}</div></div>`
           )
           .join("")}</div>
     <h3 class="mt20">Neuer Benutzer</h3><div class="filters"><input id="nu_n" placeholder="Name"><input id="nu_m" type="email" placeholder="E-Mail-Adresse" autocomplete="off"><input id="nu_p" type="password" placeholder="Passwort (mind. 8 Zeichen)" autocomplete="new-password"><select id="nu_r"><option value="user">Benutzer</option><option value="admin">Administrator</option><option value="viewer">Betrachter (nur ansehen)</option></select><select id="nu_o" style="display:none" title="Dessen Touren, Fotos und Standort sieht der Betrachter">${us.filter(u => u.role !== "viewer" && u.active).map(u => `<option value="${u.uid}">sieht: ${esc(u.name)}</option>`).join("")}</select><button class="btn" id="nu_b">Anlegen</button><span id="nu_m" class="mut"></span></div>
     <p class="mut fs13">Jeder Benutzer hat eigene Touren, Fotos, Notizen, Ziele und sein eigenes Komoot-Konto (Verwaltung). Fotos aus einem Ordner <code>/mnt/fotos/&lt;Benutzername&gt;</code> werden dem jeweiligen Benutzer zugeordnet.</p></div>`
       : ""
   }`;
  document.querySelectorAll("[data-vm]").forEach(
    b =>
      (b.onclick = () => {
        try {
          localStorage.setItem("viewmode", b.dataset.vm);
        } catch (e) {}
        applyView();
        VIEWS.account();
      })
  );
  $("#pwb").onclick = async () => {
    try {
      await api("/api/me/password", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({old: $("#pw0").value, new: $("#pw1").value}),
      });
      $("#pwm").textContent = "✓ Geändert";
      $("#pw0").value = $("#pw1").value = "";
    } catch (e) {
      $("#pwm").textContent = e.message;
    }
  };
  $("#gs2").onchange = () => {
    $("#gtw").style.display = $("#gs2").value === "tour" ? "" : "none";
  };
  $("#gadd").onclick = async () => {
    try {
      await api("/api/grants", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({grantee: $("#gg").value, scope: $("#gs2").value, ref: $("#gs2").value === "tour" ? $("#gt").value : ""}),
      });
      VIEWS.account();
    } catch (e) {
      $("#gm").textContent = e.message;
    }
  };
  document.querySelectorAll("[data-gd]").forEach(
    b =>
      (b.onclick = async () => {
        await api("/api/grants/" + b.dataset.gd, {method: "DELETE"});
        VIEWS.account();
      })
  );
  const J = {"content-type": "application/json"},
    patch = async (u, d) => {
      try {
        await api("/api/users/" + u, {method: "PATCH", headers: J, body: JSON.stringify(d)});
        VIEWS.account();
      } catch (e) {
        alert(e.message);
      }
    };
  document
    .querySelectorAll("[data-ur]")
    .forEach(
      b => (b.onclick = () => patch(b.dataset.ur, {role: us.find(u => u.uid === b.dataset.ur).role === "admin" ? "user" : "admin"}))
    );
  document.querySelectorAll("[data-up]").forEach(
    b =>
      (b.onclick = () => {
        const p = prompt("Neues Passwort für diesen Benutzer (mind. 8 Zeichen):");
        if (p) patch(b.dataset.up, {password: p});
      })
  );
  document.querySelectorAll("[data-um]").forEach(
    b =>
      (b.onclick = () => {
        const u = us.find(x => x.uid === b.dataset.um),
          e = prompt(`E-Mail-Adresse für ${u.name}:`, u.email || "");
        if (e !== null) patch(b.dataset.um, {email: e});
      })
  );
  document.querySelectorAll("[data-u2]").forEach(
    b =>
      (b.onclick = () => {
        const u = us.find(x => x.uid === b.dataset.u2);
        if (confirm(`Zwei-Faktor-Anmeldung von „${u.name}“ ausschalten? Der Benutzer kann sie danach neu einrichten.`)) patch(b.dataset.u2, {reset_2fa: true});
      })
  );
  document
    .querySelectorAll("[data-ua]")
    .forEach(b => (b.onclick = () => patch(b.dataset.ua, {active: !us.find(u => u.uid === b.dataset.ua).active})));
  document.querySelectorAll("[data-ud]").forEach(
    b =>
      (b.onclick = async () => {
        const u = us.find(x => x.uid === b.dataset.ud);
        const all = confirm(
          `„${u.name}“ löschen?\n\nOK = Benutzer UND alle seine Touren, Fotos und Daten unwiderruflich löschen.\nAbbrechen = nichts tun.`
        );
        if (!all) return;
        try {
          await api(`/api/users/${b.dataset.ud}?data=1`, {method: "DELETE"});
          VIEWS.account();
        } catch (e) {
          alert(e.message);
        }
      })
  );
  if ($("#nu_r")) $("#nu_r").onchange = () => ($("#nu_o").style.display = $("#nu_r").value === "viewer" ? "" : "none");
  if ($("#nu_b"))
    $("#nu_b").onclick = async () => {
      try {
        await api("/api/users", {
          method: "POST",
          headers: J,
          body: JSON.stringify({name: $("#nu_n").value, email: $("#nu_m").value, password: $("#nu_p").value, role: $("#nu_r").value, owner: $("#nu_r").value === "viewer" ? $("#nu_o").value : undefined}),
        });
        VIEWS.account();
      } catch (e) {
        $("#nu_m").textContent = e.message;
      }
    };
};

VIEWS.shared = async () => {
  $("#main").innerHTML =
    `<div class="sec mt0"><h2>Geteilte Fotos</h2><span class="sub">Fotos, die andere Benutzer für dich freigegeben haben</span></div><div id="shb" class="mut">Wird geladen …</div>`;
  const data = await api("/api/shared/photos");
  $("#shb").className = "";
  if (!data.length) {
    $("#shb").innerHTML =
      '<div class="empty"><h2>Noch nichts geteilt</h2><p>Sobald jemand Fotos für dich freigibt, erscheinen sie hier.</p></div>';
    return;
  }
  $("#shb").innerHTML = data
    .map((o, oi) => {
      const by = {};
      o.photos.forEach(p => (by[p.tour_id || ""] ||= []).push(p));
      return (
        `<div class="sec"><h2>${esc(o.name)}</h2><span class="sub">${o.photos.length} Fotos</span><span class="sp"></span><button class="btn sm" data-all="${oi}">Alle übernehmen</button></div>` +
        Object.entries(by)
          .map(
            ([
              tid,
              ps,
            ]) => `<div class="pgroup"><div class="ph"><h3>${esc(tid ? o.tours[tid] || "Tour" : "Ohne Tour")}</h3><span>${ps.length} Fotos</span><button class="btn alt sm" data-grp="${oi}|${esc(tid)}">Übernehmen</button></div>
      <div class="thumbs" data-g="${oi}|${esc(tid)}">${ps.map((p, i) => `<img loading="lazy" src="/spic/${esc(o.owner)}/${p.id}?size=300" data-i="${i}" title="${new Date(p.taken_ts * 1000).toLocaleString("de-DE")}">`).join("")}</div></div>`
          )
          .join("")
      );
    })
    .join("");
  data.forEach((o, oi) => {
    const by = {};
    o.photos.forEach(p => (by[p.tour_id || ""] ||= []).push(p));
    document.querySelectorAll(`[data-g^="${oi}|"]`).forEach(box => {
      const tid = box.dataset.g.split("|")[1],
        list = by[tid].map(p => ({...p, src: `/spic/${o.owner}/${p.id}?size=2000`}));
      bindThumbs(box, list);
    });
  });
  const imp = async (oi, ids, btn) => {
    btn.disabled = true;
    try {
      const r = await api("/api/shared/import", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({owner: data[oi].owner, ids}),
      });
      btn.textContent = `✓ ${r.total} übernommen`;
    } catch (e) {
      btn.disabled = false;
      alert(e.message);
    }
  };
  document.querySelectorAll("[data-all]").forEach(
    b =>
      (b.onclick = () =>
        imp(
          +b.dataset.all,
          data[+b.dataset.all].photos.map(p => p.id),
          b
        ))
  );
  document.querySelectorAll("[data-grp]").forEach(
    b =>
      (b.onclick = () => {
        const [oi, tid] = b.dataset.grp.split("|");
        imp(
          +oi,
          data[+oi].photos.filter(p => (p.tour_id || "") === tid).map(p => p.id),
          b
        );
      })
  );
};

/* Tourdetail: Fotos anderer + Foto-Freigabe */
const _tourU = VIEWS.tour;
VIEWS.tour = async (id, q) => {
  await _tourU(id, q);
  const t = BY[id];
  if (!t || !ME.users_enabled || !ME.user) return;
  const row = $("#etag")?.parentElement;
  if (row && !$("#efsh"))
    row.insertAdjacentHTML(
      "beforeend",
      `<button class="btn ghost sm" id="efsh" title="Fotos dieser Tour für andere Benutzer freigeben">👥 Fotos freigeben</button>`
    );
  if ($("#efsh"))
    $("#efsh").onclick = async () => {
      const us = (await api("/api/users").catch(() => [])).filter(u => u.uid !== ME.user.uid && (u.active === undefined || u.active));
      const m =
        modal(`<h3>Fotos dieser Tour freigeben</h3><p class="mut fs14">Die Freigabe gilt für alle Fotos, die dieser Tour zugeordnet sind.</p><div class="field"><label>Für</label><select id="fg"><option value="*">Alle Benutzer</option>${us.map(u => `<option value="${esc(u.uid)}">${esc(u.name)}</option>`).join("")}</select></div>
      <div class="row jce"><button class="btn alt" id="fgx">Abbrechen</button><button class="btn" id="fgo">Freigeben</button></div>`);
      m.querySelector("#fgx").onclick = () => m.remove();
      m.querySelector("#fgo").onclick = async () => {
        try {
          await api("/api/grants", {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify({grantee: m.querySelector("#fg").value, scope: "tour", ref: t.id}),
          });
          m.remove();
          alert("Freigegeben. Verwalten unter „Konto & Freigaben“.");
        } catch (e) {
          alert(e.message);
        }
      };
    };
  api(`/api/shared/for-tour/${encodeURIComponent(id)}`)
    .then(list => {
      if (!list.length || !$("#th")) return;
      const by = {};
      list.forEach(p => (by[p.owner] ||= {name: p.owner_name, ids: []}).ids.push(p.id));
      $("#th").insertAdjacentHTML(
        "beforebegin",
        `<div class="panel mb14 p12-16" id="shn"><b>Fotos von anderen aus diesem Zeitraum:</b> ${Object.entries(
          by
        )
          .map(([o, v]) => `${esc(v.name)} (${v.ids.length}) <button class="btn sm" data-imp="${esc(o)}">In meine Tour übernehmen</button>`)
          .join(" ")}</div>`
      );
      document.querySelectorAll("[data-imp]").forEach(
        b =>
          (b.onclick = async () => {
            b.disabled = true;
            try {
              await api("/api/shared/import", {
                method: "POST",
                headers: {"content-type": "application/json"},
                body: JSON.stringify({owner: b.dataset.imp, ids: by[b.dataset.imp].ids}),
              });
              await loadTours();
              VIEWS.tour(id, q);
            } catch (e) {
              b.disabled = false;
              alert(e.message);
            }
          })
      );
    })
    .catch(() => {});
};
