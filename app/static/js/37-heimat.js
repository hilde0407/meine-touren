"use strict";
/* Heimatort in der Verwaltung: Ort suchen und wählen (wird sofort gespeichert). Er dient dazu, Touren zu Hause von Reisen zu unterscheiden. */
const _admH = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admH(...a);
  const sv = $("#save");
  if (!sv || $("#homep")) return;
  const s = await api("/api/settings").catch(() => ({}));
  const row = sv.parentElement;
  row.insertAdjacentHTML("beforebegin", `<div class="panel gap" id="homep"><h2>Heimatort und Puls</h2>
    <p class="mut fs14 m0-0-8">Touren in der Nähe (bis etwa 60 km) zählen nicht als Reise. Leer lassen, dann erkennt die App den Heimatort aus deinen Touren.</p>
    <div class="field"><label>Heimatort <span class="mut fs13">(wird sofort gespeichert)</span></label><div class="row g6"><input id="hsq" placeholder="Ort oder Adresse suchen …" value="${esc(s.home_name || "")}" class="fx1"><button class="btn sm" id="hsb">Suchen</button><button class="btn alt sm" id="hsc" title="Heimatort entfernen">✕</button></div></div>
    <div id="hsr"></div>
    <input type="hidden" data-k="home_name" id="hn" value="${esc(s.home_name || "")}"><input type="hidden" data-k="home_lat" id="hla" value="${esc(s.home_lat || "")}"><input type="hidden" data-k="home_lng" id="hlo" value="${esc(s.home_lng || "")}">
    <div class="field mt14"><label>Maximalpuls (bpm) für die Pulszonen</label><input type="number" min="100" max="230" data-k="hr_max" value="${esc(s.hr_max || "")}" placeholder="leer = 185 bzw. höchster gemessener Wert" class="mw320"></div>
    <div class="mut fs13" id="hst">${s.home_lat ? `📍 ${esc(s.home_name || "")} (${nf(+s.home_lat, 3)}, ${nf(+s.home_lng, 3)})` : "Noch kein Heimatort eingetragen."}</div></div>`);
  /* 3.61.0: Auswahl und Entfernen speichern sofort (Leitfaden 2.4: Auswahlen speichern sofort) – kein Umweg über „Einstellungen speichern“ mehr */
  const store = async (name, la, lo, ok) => {
    $("#hn").value = name; $("#hla").value = la; $("#hlo").value = lo; $("#hsq").value = name;
    $("#hsr").innerHTML = "";
    try {
      await api("/api/settings", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({home_name: name, home_lat: la, home_lng: lo})});
      $("#hst").textContent = ok;
    } catch (e) {
      $("#hst").textContent = "Speichern nicht möglich: " + (e.message || e);
    }
  };
  const pick = (name, la, lo) => store(name, la, lo, `📍 ${name} (${nf(+la, 3)}, ${nf(+lo, 3)}) – Heimatort gespeichert`);
  const search = async () => {
    const q = $("#hsq").value.trim();
    if (q.length < 2) return;
    $("#hsr").innerHTML = '<p class="mut">Suche …</p>';
    try {
      const r = await api("/api/geo/search?q=" + encodeURIComponent(q));
      $("#hsr").innerHTML = r.length ? r.map((e, i) => `<div><a href="#" class="hsp" data-i="${i}">📍 ${esc(e.name)}</a></div>`).join("") : '<p class="mut">Nichts gefunden.</p>';
      $("#hsr").querySelectorAll(".hsp").forEach(x => x.onclick = ev => { ev.preventDefault(); const e = r[+x.dataset.i]; pick(e.name.split(",").slice(0, 2).join(",").trim(), e.lat.toFixed(5), e.lng.toFixed(5)); });
    } catch (e) { $("#hsr").innerHTML = `<p class="mut">${esc(e.message || "Fehler")}</p>`; }
  };
  $("#hsb").onclick = search;
  $("#hsq").onkeydown = ev => { if (ev.key === "Enter") { ev.preventDefault(); search(); } };
  $("#hsc").onclick = () => store("", "", "", "Heimatort entfernt");
};
