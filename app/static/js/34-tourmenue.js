/* Mobile Tour-Ansicht: die vielen Einzelknöpfe werden zu zwei klaren Menüs („Teilen & Senden“, „Bearbeiten“) zusammengefasst.
   Die ursprünglichen Knöpfe bleiben im Dokument (nur ausgeblendet); das Menü löst sie aus – so bleibt jede Funktion unverändert. */
const TACT = [
  {
    key: "share", icon: "📤", label: "Teilen & Senden", title: "Teilen & Senden",
    items: [
      ["esnd", "Link senden", "Karte und Zahlen an WhatsApp, Signal, E-Mail …"],
      ["eshow", "Diashow senden", "Fotos als Diashow – ohne Benutzerkonto ansehbar"],
      ["eshr", "Links verwalten", "Erzeugte Links ansehen, kopieren, widerrufen"],
      ["egpx", "GPX-Datei laden", "Strecke als GPX herunterladen"],
      ["esheet", "Tourblatt", "Druckbare Seite mit Karte, Profil und Fotos"],
    ],
  },
  {
    key: "edit", icon: "✎", label: "Bearbeiten", title: "Tour bearbeiten",
    items: [
      ["ren", "Umbenennen", ""],
      ["etag", "Tags & Alben", "Schlagworte vergeben"],
      ["etc", "Streckenfarbe", "Farbe und Breite auf der Karte"],
      ["efix", "Höhen korrigieren", "Mit Geländemodell neu berechnen"],
      ["etfix", "Track korrigieren", "Fehlpunkte und Pausen bereinigen"],
      ["eup", "Hochladen", "Zu Strava, Komoot … senden"],
      ["ksync", "Mit Komoot abgleichen", "Daten und Track neu laden"],
      ["edel", "Tour löschen", "Lokale Tour entfernen", "danger"],
    ],
  },
];
const _tour34 = VIEWS.tour;
VIEWS.tour = async id => {
  await _tour34(id);
  if (!document.documentElement.classList.contains("mob") || (typeof isViewer === "function" && isViewer())) return;
  const anchor = $("#eup") || $("#egpx"),
    row = anchor && anchor.parentElement;
  if (!row || row.classList.contains("tact")) return;
  row.classList.add("tact");
  if ($("#ren")) $("#ren").classList.add("tact-off");
  const bar = document.createElement("span");
  bar.className = "tact-bar";
  bar.innerHTML = TACT.map(g => `<button class="btn tk" data-g="${g.key}"><span>${g.icon}</span> ${g.label}</button>`).join("");
  row.insertBefore(bar, row.firstChild);
  bar.querySelectorAll("button").forEach(b => {
    b.onclick = () => {
      const g = TACT.find(x => x.key === b.dataset.g),
        its = g.items.filter(([eid]) => {
          const el = $("#" + eid);
          return el && !el.hidden && el.style.display !== "none";
        });
      if (!its.length) return;
      const m = modal(`<h3>${g.title}</h3><div class="tactl">${its
        .map(([eid, l, h, cls]) => `<button class="btn alt tl ${cls || ""}" data-e="${eid}"><b>${l}</b>${h ? `<small>${h}</small>` : ""}</button>`)
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
