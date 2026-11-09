"use strict";
/* Heimatort in der Verwaltung: Ort suchen und übernehmen. Er dient dazu, Touren zu Hause von Reisen zu unterscheiden. */
const _admH = VIEWS.admin;
VIEWS.admin = async (...a) => {
  await _admH(...a);
  const sv = $("#save");
  if (!sv || $("#homep")) return;
  const s = await api("/api/settings").catch(() => ({}));
  const row = sv.parentElement;
  row.insertAdjacentHTML("beforebegin", `<div class="panel" id="homep" style="margin-top:34px"><h2>Heimatort</h2>
    <p class="mut" style="font-size:14px;margin:0 0 8px">Touren in der Nähe (bis etwa 60 km) zählen nicht als Reise. Leer lassen, dann erkennt die App den Heimatort aus deinen Touren.</p>
    <div class="field"><label>Heimatort</label><div class="row" style="gap:6px"><input id="hsq" placeholder="Ort oder Adresse suchen …" value="${esc(s.home_name || "")}" style="flex:1"><button class="btn sm" id="hsb">Suchen</button><button class="btn alt sm" id="hsc" title="Heimatort entfernen">✕</button></div></div>
    <div id="hsr"></div>
    <input type="hidden" data-k="home_name" id="hn" value="${esc(s.home_name || "")}"><input type="hidden" data-k="home_lat" id="hla" value="${esc(s.home_lat || "")}"><input type="hidden" data-k="home_lng" id="hlo" value="${esc(s.home_lng || "")}">
    <div class="mut" id="hst" style="font-size:13px">${s.home_lat ? `📍 ${esc(s.home_name || "")} (${(+s.home_lat).toFixed(3)}, ${(+s.home_lng).toFixed(3)}) – zum Übernehmen unten „Einstellungen speichern“` : "Noch kein Heimatort eingetragen."}</div></div>`);
  const pick = (name, la, lo) => {
    $("#hn").value = name; $("#hla").value = la; $("#hlo").value = lo; $("#hsq").value = name;
    $("#hst").textContent = `📍 ${name} (${(+la).toFixed(3)}, ${(+lo).toFixed(3)}) – zum Übernehmen unten „Einstellungen speichern“`;
    $("#hsr").innerHTML = "";
  };
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
  $("#hsc").onclick = () => { $("#hn").value = $("#hla").value = $("#hlo").value = ""; $("#hsq").value = ""; $("#hsr").innerHTML = ""; $("#hst").textContent = "Heimatort entfernt – zum Übernehmen unten „Einstellungen speichern“"; };
};
