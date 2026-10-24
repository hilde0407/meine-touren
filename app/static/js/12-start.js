/* Start */
async function boot() {
  try {
    ME = await fetch("/api/me").then(r => r.json());
  } catch (e) {}
  applyView();
  if (ME.users_enabled && !ME.user) {
    showAuth("login");
    return;
  }
  userMenu();
  await loadPrefs();
  route();
}

/* ---- Verwaltung: Bereiche gruppieren und einklappbar machen ---- */
const _admG = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admG(...a);
  const main = $("#main"),
    save = $("#save");
  if (!save) return;
  const GROUPS = [
    ["import", "Import", "Touren und Fotos in die App holen", ["Komoot", "Zepp-Import", "GPX/TCX-Dateien", "Fotos", "Foto-Eingang"], true],
    ["portale", "Upload-Portale", "Strava, Komoot", ["Portale"], false],
    ["auto", "Automatik & Benachrichtigung", "", ["Automatik", "Benachrichtigung"], false],
    ["log", "Protokoll", "", ["Protokoll"], true],
    [
      "wartung",
      "Wartung & Sicherheit",
      "Sicherung, Zugriffsschutz, Selbsttest, Wanderführer",
      ["Sicherung", "Zugriffsschutz", "Selbsttest", "Wanderführer"],
      false,
    ],
  ];
  let mem = {};
  try {
    mem = JSON.parse(localStorage.getItem("admgrp") || "{}");
  } catch (e) {}
  const panels = [...main.querySelectorAll(".panel")].filter(p => p.parentElement && p.querySelector(":scope > h2"));
  const title = p => p.querySelector(":scope > h2").firstChild.textContent.trim();
  const anchor = save.closest(".row"),
    frag = document.createDocumentFragment();
  const open = new URLSearchParams(location.hash.split("?")[1] || "").get("strava");
  GROUPS.forEach(([id, name, sub, titles, dflt]) => {
    const mine = titles.map(t => panels.find(p => title(p).startsWith(t))).filter(Boolean);
    if (!mine.length) return;
    const d = document.createElement("details");
    d.className = "agrp";
    d.open = id in mem ? !!mem[id] : dflt || (id === "portale" && !!open);
    d.innerHTML = `<summary><span class="gt">${name}</span><span class="gs">${sub}</span></summary><div class="grid g2 gbody"></div>`;
    mine.forEach(p => {
      p.style.marginTop = "6px";
      if (mine.length === 1 && title(p) === name) {
        p.style.borderTop = "0";
        p.querySelector(":scope > h2").style.display = "none";
      }
      d.querySelector(".gbody").appendChild(p);
    });
    d.addEventListener("toggle", () => {
      mem[id] = d.open;
      try {
        localStorage.setItem("admgrp", JSON.stringify(mem));
      } catch (e) {}
    });
    frag.appendChild(d);
  });
  main.querySelectorAll(":scope > .grid, :scope > .panel").forEach(g => {
    if (!g.querySelector(".panel") && !g.matches(".panel") && !g.textContent.trim()) g.remove();
  });
  main.querySelectorAll(":scope > .grid").forEach(g => {
    if (!g.children.length) g.remove();
  });
  anchor.parentNode.insertBefore(frag, anchor);
};

/* ---- Warnbanner (Gesundheitscheck) ---- */
let _hl = {t: 0, v: []};
async function healthBanner() {
  try {
    if (Date.now() - _hl.t > 60000) _hl = {t: Date.now(), v: await api("/api/health")};
    const m = $("#main");
    if (!m || !_hl.v.length || m.querySelector(".warnbar")) return;
    m.insertAdjacentHTML(
      "afterbegin",
      `<div class="warnbar">${_hl.v.map(w => `<div>⚠ ${esc(w.text)}</div>`).join("")}<a href="#/admin">Verwaltung öffnen</a></div>`
    );
  } catch (e) {}
}
Object.keys(VIEWS).forEach(k => {
  const f = VIEWS[k];
  VIEWS[k] = async (...a) => {
    await f(...a);
    healthBanner();
  };
});

boot();
