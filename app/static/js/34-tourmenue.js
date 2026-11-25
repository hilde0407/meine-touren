/* Mobile Tour-Ansicht: die vielen Einzelknöpfe werden zu zwei klaren Menüs („Teilen & Senden“, „Bearbeiten“) zusammengefasst.
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
    key: "share", icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 15V3M7 8l5-5 5 5"/><path d="M5 12v7h14v-7"/></svg>`, label: "Teilen & Export", title: "Teilen & Export",
    items: [
      ["-", "Senden und Links"],
      ["esnd", "Link senden", "Du wählst, was der Link zeigt – und sendest ihn an WhatsApp, Signal, E-Mail …"],
      ["eshow", "Diashow senden", "Fotos als Diashow – ohne Benutzerkonto ansehbar"],
      ["shr", "Diashow-Link", "Link zur Foto-Diashow dieser Tour"],
      ["eshr", "Links verwalten", "Erzeugte Links ansehen, kopieren, widerrufen"],
      ["-", "Datei"],
      ["egpx", "GPX-Datei laden", "Strecke als GPX herunterladen"],
      ["ekpk", "Komoot-Paket …", "GPX mit Pins und Notiz, ausgewählte Fotos – zum Selbst-Hochladen"],
    ],
  },
  {
    key: "edit", icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/></svg>`, label: "Bearbeiten", title: "Tour bearbeiten",
    items: [
      ["-", "Beschriften"],
      ["ren", "Umbenennen", ""],
      ["etag", "Tags & Alben", "Schlagworte vergeben"],
      ["esport", "Sportart ändern", "Alle Sportarten, Favoriten zuerst"],
      ["-", "Strecke und Höhen"],
      ["etc", "Streckenfarbe", "Farbe und Breite auf der Karte"],
      ["efix", "Höhen korrigieren", "Mit Geländemodell neu berechnen"],
      ["ezepp", "Höhe aus Uhr abgleichen (Zepp)", "Barometrische Höhe der Uhr übernehmen"],
      ["etfix", "Track korrigieren", "Fehlpunkte und Pausen bereinigen"],
      ["-", "Abgleich und Upload"],
      ["eup", "Hochladen", "Zu Strava, Komoot … senden"],
      ["ksync", "Mit Komoot abgleichen", "Daten und Track neu laden"],
      ["-", "Entfernen"],
      ["edel", "Tour löschen", "Aus Meine Touren entfernen", "danger"],
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
/* 3.59.0 „Sportart ändern“ (Tour bearbeiten): alle Aktivitäten des Katalogs, Favoriten zuerst (sportOptions, 01-grundlagen.js); gilt als eigene Wahl (bleibt beim Komoot-Abgleich) */
function sport34(id) {
  const b = $("#esport"), t = BY[id];
  if (!b || !t || (typeof isViewer === "function" && isViewer())) return;
  b.onclick = () => {
    const cur = sNorm(t.sport);                                                 // 3.60.0: entfernte Aktivität (z. B. „golf“) -> ihr Rückfall ist vorgewählt
    const m = uiModal(`<h3>Sportart ändern</h3><div class="field"><label for="espsel">Sportart</label><select id="espsel">${sportOptions(cur)}</select></div>
      ${t.source !== "local" ? '<label class="chk"><input type="checkbox" id="espko"> auch bei Komoot ändern</label>' : ""}<p class="bad" id="esperr" role="alert"></p>
      <div class="uifoot"><button class="btn ghost" id="espx">Abbrechen</button><button class="btn" id="espok">Übernehmen</button></div>`);
    const sel = m.querySelector("#espsel");
    if (!SPORT[cur]) sel.insertAdjacentHTML("afterbegin", `<option value="${esc(t.sport)}" selected>${esc(sName(t.sport))}</option>`);
    sel.focus();
    m.querySelector("#espx").onclick = () => m.remove();
    m.querySelector("#espok").onclick = async e => {
      e.currentTarget.disabled = true;
      try {
        await api(`/api/tours/${encodeURIComponent(id)}/sport`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({sport: sel.value, komoot: !!(m.querySelector("#espko") || {}).checked})});
        m.remove();
        await loadTours();
        route();
      } catch (er) {
        m.querySelector("#esperr").textContent = er.message || String(er);
        e.currentTarget.disabled = false;
      }
    };
  };
}
