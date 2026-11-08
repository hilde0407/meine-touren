/* Mobile Tour-Ansicht: die vielen Einzelknöpfe werden zu zwei klaren Menüs („Teilen & Senden“, „Bearbeiten“) zusammengefasst.
   Die ursprünglichen Knöpfe bleiben im Dokument (nur ausgeblendet); das Menü löst sie aus – so bleibt jede Funktion unverändert. */
const TACT = [
  {
    key: "view", icon: "👁", label: "Ansehen", title: "Tour ansehen",
    items: [
      ["storybtn", "Erzählung", "Zeitleiste mit Wegpunkten, Fotos und Kommentaren"],
      ["e3d", "3D-Flug", "Die Strecke im 3D-Gelände abfliegen"],
      ["esheet", "Tourblatt", "Druckbare Seite mit Karte, Profil und Fotos"],
    ],
  },
  {
    key: "share", icon: "📤", label: "Teilen & Export", title: "Teilen & Export",
    items: [
      ["-", "Senden und Links"],
      ["esnd", "Link senden", "Karte und Zahlen an WhatsApp, Signal, E-Mail …"],
      ["eshow", "Diashow senden", "Fotos als Diashow – ohne Benutzerkonto ansehbar"],
      ["shr", "Diashow-Link", "Link zur Foto-Diashow dieser Tour"],
      ["eshr", "Links verwalten", "Erzeugte Links ansehen, kopieren, widerrufen"],
      ["-", "Datei"],
      ["egpx", "GPX-Datei laden", "Strecke als GPX herunterladen"],
    ],
  },
  {
    key: "edit", icon: "✎", label: "Bearbeiten", title: "Tour bearbeiten",
    items: [
      ["-", "Beschriften"],
      ["ren", "Umbenennen", ""],
      ["etag", "Tags & Alben", "Schlagworte vergeben"],
      ["-", "Strecke und Höhen"],
      ["etc", "Streckenfarbe", "Farbe und Breite auf der Karte"],
      ["efix", "Höhen korrigieren", "Mit Geländemodell neu berechnen"],
      ["etfix", "Track korrigieren", "Fehlpunkte und Pausen bereinigen"],
      ["-", "Abgleich und Upload"],
      ["eup", "Hochladen", "Zu Strava, Komoot … senden"],
      ["ksync", "Mit Komoot abgleichen", "Daten und Track neu laden"],
      ["-", "Entfernen"],
      ["edel", "Tour löschen", "Lokale Tour entfernen", "danger"],
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
      const m = modal(`<h3>${g.title}</h3><div class="tactl">${its
        .map(([eid, l, h, cls]) => eid === "-" ? `<h4 class="tactg">${l}</h4>` : `<button class="btn alt tl ${cls || ""}" data-e="${eid}"><b>${l}</b>${h ? `<small>${h}</small>` : ""}</button>`)
        .join("")}</div><div class="row" style="justify-content:flex-end;margin-top:12px"><button class="btn alt" id="tactx">Schließen</button></div>`);
      m.classList.add("sheet");
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
};
