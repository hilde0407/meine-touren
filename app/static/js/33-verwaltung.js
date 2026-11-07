/* Verwaltung: einheitliche Gliederung – jeder Bereich ist eine gleich gestaltete Karte (Titel, Erklärung, Inhalt) */
const _admV = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admV(...a);
  if (!$("#atabs") || $("#atabs").dataset.v) return;
  $("#atabs").dataset.v = "1";
  // Reihenfolge im Reiter „Handy & App“
  const hb = document.querySelector('.atab[data-t="handy"] .gbody');
  if (hb) {
    ["appbox", "livebox", "rescue", "handy"].forEach(id => $("#" + id) && hb.appendChild($("#" + id)));
  }
  // Protokoll: eingeklappt (selten gebraucht)
  const lg = $("#log");
  if (lg && !lg.closest("details")) {
    const card = lg.closest(".panel"),
      h = card && card.querySelector(":scope > h2");
    if (card && h) {
      const d = document.createElement("details");
      d.innerHTML = "<summary>Protokoll anzeigen</summary>";
      d.appendChild(lg);
      card.appendChild(d);
    }
  }
  // jede Karte bekommt die gleiche Klasse
  document.querySelectorAll(".atab .gbody > *").forEach(c => c.classList.add("acard"));
};
