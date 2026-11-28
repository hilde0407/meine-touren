/* Mobile Tour-Ansicht: die vielen Einzelknöpfe werden zu Menüs („Ansehen“, „Bearbeiten“, „Teilen & Export“) zusammengefasst.
   3.61.0: dieselben Namen und dieselbe Reihenfolge wie die Knopfleiste am Computer (Leitfaden 2.8); Punkte, die einen Dialog öffnen, enden auf „ …“; Löschen zuletzt (rot).
   Die ursprünglichen Knöpfe bleiben im Dokument (nur ausgeblendet); das Menü löst sie aus – so bleibt jede Funktion unverändert. */
const TACT = [
  {
    key: "view", icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>`, label: "Ansehen", title: "Tour ansehen",
    items: [
      ["storybtn", "Erzählung", "Zeitleiste mit Wegpunkten, Fotos und Kommentaren"],
      ["e3d", "3D-Flug", "Die Strecke im 3D-Gelände abfliegen"],
      ["esheet", "Tourblatt", "Druckbare Seite mit Karte, Profil und Fotos"],
    ],
  },
  {
    key: "edit", icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/></svg>`, label: "Bearbeiten", title: "Tour bearbeiten",
    items: [
      ["-", "Beschriften"],
      ["ren", "Umbenennen …", ""],
      ["etag", "Schlagwörter & Alben …", "Schlagwörter vergeben und Alben bilden"],
      ["esport", "Sportart ändern …", "Favoriten-Sportarten zuerst, dann alle übrigen"],
      ["-", "Strecke und Höhe"],
      ["etc", "Streckenfarbe …", "Farbe und Breite auf der Karte"],
      ["efix", "Höhe korrigieren …", "aus dem Geländemodell"],
      ["ezepp", "Höhe korrigieren …", "aus der Uhr (barometrische Höhe, Zepp)"],
      ["etfix", "Track korrigieren", "Fehlpunkte und Pausen bereinigen"],
      ["-", "Hochladen und Abgleich"],
      ["eup", "Hochladen …", "Zu Strava, Komoot … senden"],
      ["ksync", "Mit Komoot abgleichen", "Daten und Strecke neu von Komoot holen"],
      ["-", "Löschen"],
      ["edel", "Löschen …", "Tour aus Meine Touren löschen", "danger"],
    ],
  },
  {
    key: "share", icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 15V3M7 8l5-5 5 5"/><path d="M5 12v7h14v-7"/></svg>`, label: "Teilen & Export", title: "Teilen & Exportieren",
    items: [
      ["-", "Senden und Links"],
      ["esnd", "Link senden …", "Du wählst, was der Link zeigt – und sendest ihn an WhatsApp, Signal, E-Mail …"],
      ["eshow", "Diashow senden …", "Fotos als Diashow – ohne Benutzerkonto ansehbar"],
      ["shr", "Diashow-Link", "Link zur Foto-Diashow dieser Tour"],
      ["eshr", "Links verwalten …", "Erzeugte Links ansehen, kopieren, widerrufen"],
      ["-", "Exportieren"],
      ["egpx", "Als GPX exportieren", "Strecke als GPX-Datei herunterladen"],
      ["ekpk", "Komoot-Paket …", "GPX mit Pins und Notiz, ausgewählte Fotos – zum Selbst-Hochladen"],
    ],
  },
];
const _tour34 = VIEWS.tour;
const setup34 = () => {
  if (typeof isViewer === "function" && isViewer()) return;
  const anchor = $("#eup") || $("#egpx"),
    row = anchor && anchor.parentElement;
  if (!row || row.classList.contains("tact")) return;
  row.classList.add("tact");
  if ($("#ren")) $("#ren").classList.add("tact-off");
  if ($("#storybtn")) $("#storybtn").classList.add("tact-off");
  const bar = document.createElement("span");
  bar.className = "tact-bar";
  bar.innerHTML = TACT.map(g => `<button class="btn tk" data-g="${g.key}"><span>${g.icon}</span> ${g.label}</button>`).join("");
  row.insertBefore(bar, row.firstChild);
  bar.querySelectorAll("button").forEach(b => {
    b.onclick = () => {
      const g = TACT.find(x => x.key === b.dataset.g),
        ok = ([eid]) => {
          const el = $("#" + eid);
          return el && !el.hidden && el.style.display !== "none";
        },
        its = g.items.filter((x, i, arr) => {
          if (x[0] !== "-") return ok(x);
          for (let j = i + 1; j < arr.length && arr[j][0] !== "-"; j++) if (ok(arr[j])) return true;   // Überschrift nur, wenn darunter etwas sichtbar ist
          return false;
        });
      if (!its.some(x => x[0] !== "-")) return;
      const m = uiModal(`<h3>${g.title}</h3><div class="tactl">${its
        .map(([eid, l, h, cls]) => eid === "-" ? `<h4 class="tactg">${l}</h4>` : `<button class="btn alt tl ${cls || ""}" data-e="${eid}"><b>${l}</b>${h ? `<small>${h}</small>` : ""}</button>`)
        .join("")}</div><div class="uifoot"><button class="btn ghost" id="tactx">Schließen</button></div>`);
      m.querySelector("#tactx").onclick = () => m.remove();
      m.querySelectorAll("[data-e]").forEach(
        x =>
          (x.onclick = () => {
            m.remove();
            const el = $("#" + x.dataset.e);
            if (el) el.click();
          })
      );
    };
  });
};
/* Die Menüleiste wird gebaut, sobald die Knöpfe im Dokument erscheinen (noch vor dem nächsten Zeichnen) – so blitzen die Einzelknöpfe nicht kurz auf. */
VIEWS.tour = async id => {
  const mo = new MutationObserver(() => { if ($("#eup") || $("#egpx")) setup34(); });
  mo.observe(document.body, {childList: true, subtree: true});
  try {
    await _tour34(id);
  } finally {
    mo.disconnect();
  }
  setup34();
  sport34(id);
};
/* 3.59.0 „Sportart ändern“ (Tour bearbeiten): alle Sportarten des Katalogs, Favoriten-Sportarten zuerst (3.61.0: sportWahlHtml, 01-grundlagen.js); gilt als eigene Wahl (bleibt beim Komoot-Abgleich) */
function sport34(id) {
  const b = $("#esport"), t = BY[id];
  if (!b || !t || (typeof isViewer === "function" && isViewer())) return;
  b.onclick = () => {
    const n = sNorm(t.sport), cur = SPORT[n] ? n : t.sport;                    // 3.60.0: entfernte Sportart (z. B. „golf“) -> ihr Rückfall ist vorgewählt; ein fremder Schlüssel bleibt wählbar
    /* 3.61.0: Muster „Zuweisen“ (sportWahlHtml): Favoriten-Sportarten zuerst, dann „Mehr …“ nach Kategorien; Hauptaktion „Speichern“ */
    const m = uiModal(`<h3>Sportart ändern</h3>${sportWahlHtml(cur, {id: "espsel", moreId: "espmore"})}
      ${t.source !== "local" ? '<label class="chk"><input type="checkbox" id="espko"> auch bei Komoot ändern</label>' : ""}<p class="bad" id="esperr" role="alert"></p>
      <div class="uifoot"><button class="btn ghost" id="espx">Abbrechen</button><button class="btn" id="espok">Speichern</button></div>`);
    const sel = m.querySelector("#espsel");
    sportWahlBind(m);
    const first = m.querySelector('.spwahl [aria-checked="true"]') || m.querySelector(".spwahl [data-sp]");
    if (first && first.offsetParent) first.focus();
    m.querySelector("#espx").onclick = () => m.remove();
    m.querySelector("#espok").onclick = async e => {
      e.currentTarget.disabled = true;
      try {
        await api(`/api/tours/${encodeURIComponent(id)}/sport`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({sport: sel.value, komoot: !!(m.querySelector("#espko") || {}).checked})});
        m.remove();
        await loadTours();
        route();
      } catch (er) {
        m.querySelector("#esperr").textContent = "Speichern nicht möglich: " + (er.message || String(er));
        e.currentTarget.disabled = false;
      }
    };
  };
}
