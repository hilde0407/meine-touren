/* Skript der Seite slideshow.html (eigene Datei, damit die Content-Security-Policy Inline-Skripte verbieten kann) */
const q = new URLSearchParams(location.search);
const pic = p => `/pic/${p.id}?size=2000${p.v ? `&v=${p.v}` : ""}`;          // 3.54.0: mit Bildversion (der Browser behält das Bild); die Freigabe-Diashow (/spic) bleibt ohne
(async () => {
  const info = await (await fetch("/api/photo-info")).json();
  let sec = (+q.get("sec") || +(() => { try { return localStorage.getItem("showSec"); } catch (e) { return 0; } })() || info.slideshow_seconds || 6) * 1000;
  const u = new URLSearchParams({limit: 1500}); ["tour","year"].forEach(k => q.get(k) && u.set(k === "tour" ? "tour_id" : k, q.get(k))); if (q.get("random")) u.set("random", "true");
  // 3.32.0 (Kachel „Erinnerungen“): Sportart, Zeitraum, Kalendertag, neueste und beste Fotos – der Server prüft jeden Wert (app/fotofilter.py)
  [["sport", "sport"], ["from", "date_from"], ["to", "date_to"], ["day", "day"], ["before", "before"], ["gebiet", "gebiet"]].forEach(([a, b]) => q.get(a) && u.set(b, q.get(a)));
  if (q.get("recent")) u.set("recent", "true");
  if (q.get("best") && !q.get("tour")) { u.set("best", "true"); u.set("limit", Math.max(3, Math.min(300, +q.get("best") || 60))); }
  let list = await (await fetch("/api/photos?" + u)).json();
  if (q.get("best") && q.get("tour")) { const b = await (await fetch(`/api/tours/${encodeURIComponent(q.get("tour"))}/best-photos?n=${+q.get("best") || 10}`)).json(); const nm = (list[0] || {}).tour_name; list = b.photos.map(p => ({...p, tour_name: nm})); }
  if (!list.length) { document.getElementById("msg").style.display = "flex"; return; }
  if (q.get("shuffle")) list.sort(() => Math.random() - .5);
  let i = -1, cur = "a", paused = false, timer;
  const show = n => { i = (n + list.length) % list.length; document.getElementById("prog").firstChild.style.width = ((i + 1) / list.length * 100) + "%"; const p = list[i], el = document.getElementById(cur === "a" ? "b" : "a"), old = document.getElementById(cur);
    const img = new Image(); img.onload = () => { el.style.backgroundImage = `url(${img.src})`; el.classList.add("on"); old.classList.remove("on"); cur = cur === "a" ? "b" : "a"; };
    img.src = pic(p);
    document.getElementById("cap").innerHTML = (p.tour_name ? `<b>${p.tour_name.replace(/</g, "&lt;")}</b>` : "") + fmtDatum(p.taken_ts, {zeit: true}) + `  (${i + 1}/${list.length})`;
    const nx = new Image(); nx.src = pic(list[(i + 1) % list.length]); };
  const loop = () => { clearTimeout(timer); if (!paused) timer = setTimeout(() => { show(i + 1); loop(); }, sec); };
  addEventListener("keydown", e => { if (e.key === " ") { paused = !paused; loop(); } else if (e.key === "ArrowRight") { show(i + 1); loop(); } else if (e.key === "ArrowLeft") { show(i - 1); loop(); } else if (e.key.toLowerCase() === "f") toggleFs(); });
  // Bedienelemente (auch für Touchgeräte): Vollbild, Pause, Schließen; blenden sich nach 3 s aus
  const ctl = document.getElementById("ctl"), de = document.documentElement;
  let hideT, swiped = 0;
  const poke = () => { ctl.classList.remove("off"); clearTimeout(hideT); hideT = setTimeout(() => ctl.classList.add("off"), 3000); };
  const fsEl = () => document.fullscreenElement || document.webkitFullscreenElement;
  const canFs = !!(de.requestFullscreen || de.webkitRequestFullscreen);
  const setFs = () => { document.getElementById("bfs").textContent = fsEl() ? "🗗" : "⛶"; document.getElementById("bfs").title = fsEl() ? "Vollbild beenden" : "Vollbild"; };
  const toggleFs = async () => {
    try {
      if (fsEl()) await (document.exitFullscreen || document.webkitExitFullscreen).call(document);
      else if (canFs) await (de.requestFullscreen || de.webkitRequestFullscreen).call(de);
      else { const h = document.getElementById("fsh"); h.innerHTML = "Dieses Gerät (iPhone) erlaubt keinen Vollbildmodus im Browser.<br>Tipp: Teilen ▸ „Zum Home-Bildschirm“ – dann öffnet die App ohne Leiste."; h.style.display = "block"; setTimeout(() => (h.style.display = "none"), 7000); }
    } catch (err) {}
    setFs();
  };
  document.addEventListener("fullscreenchange", setFs); document.addEventListener("webkitfullscreenchange", setFs);
  document.getElementById("bfs").onclick = e => { e.stopPropagation(); toggleFs(); poke(); };
  document.getElementById("bpp").onclick = e => { e.stopPropagation(); paused = !paused; document.getElementById("bpp").textContent = paused ? "▶" : "⏸"; loop(); poke(); };
  document.getElementById("bx").onclick = e => { e.stopPropagation(); if (fsEl()) toggleFs(); if (history.length > 1 && document.referrer) history.back(); else window.close(); };
  addEventListener("keydown", e => { if (e.key === "Escape") poke(); });
  addEventListener("mousemove", poke);
  // Zurück/Weiter und Tempo (3 · 6 · 10 · 15 s, wird gemerkt)
  document.getElementById("bprv").onclick = e => { e.stopPropagation(); show(i - 1); loop(); poke(); };
  document.getElementById("bnxt").onclick = e => { e.stopPropagation(); show(i + 1); loop(); poke(); };
  const bspd = document.getElementById("bspd"), spdTxt = () => { bspd.textContent = Math.round(sec / 1000) + " s"; };
  bspd.onclick = e => { e.stopPropagation(); const o = [3, 6, 10, 15], n = o[(o.indexOf(Math.round(sec / 1000)) + 1) % o.length]; sec = n * 1000; try { localStorage.setItem("showSec", n); } catch (err) {} spdTxt(); loop(); poke(); };
  spdTxt();
  // Teilen (Tour, Jahr oder alle Fotos; nicht bei der Zufalls-Diashow): Link ohne Konto, 24 Stunden gültig, ohne Kommentare; Jahr/alle: Fotos mit Tourname (seit 3.31.1), höchstens 300 beste
  const bshr = document.getElementById("bshr"), fsh = document.getElementById("fsh");
  // 3.32.0: ein Link teilt nur „Tour“, „Jahr“ oder „alle“, keine gefilterte Auswahl; 3.61.5 auch einen Zeitraum (from und to, z. B. die Reise), aber ohne weiteren Filter
  const zeitraum = !!(q.get("from") && q.get("to")) && !["tour", "year", "sport", "day", "recent", "before"].some(k => q.get(k));
  const gefiltert = ["sport", "day", "recent", "gebiet"].some(k => q.get(k)) || (["from", "to"].some(k => q.get(k)) && !zeitraum);
  if (!gefiltert && (zeitraum || q.get("tour") || q.get("year") || !q.get("random"))) bshr.style.display = "";
  const note = txt => { fsh.textContent = txt; fsh.style.display = "block"; setTimeout(() => { fsh.style.display = "none"; }, 4000); };
  bshr.onclick = async e => {
    e.stopPropagation(); paused = true; clearTimeout(timer); document.getElementById("bpp").textContent = "▶"; poke(); bshr.disabled = true;
    try {
      const best = q.get("best") ? +q.get("best") || 10 : 0;
      const r = q.get("tour") ? await fetch(`/api/tours/${encodeURIComponent(q.get("tour"))}/share`, {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({show: true, trim: true, days: 1, best, comments: false})})
        : await fetch("/api/diashow/share", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(zeitraum ? {from: q.get("from"), to: q.get("to"), days: 1, best} : {year: +q.get("year") || 0, days: 1, best})});
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.status);
      const j = await r.json(), url = location.origin + j.url, title = j.title || (list[0] || {}).tour_name || document.title, hinweis = !q.get("tour");   // Jahr/alle: Tournamen stehen im Link (ein Name kann einen Ort verraten)
      if (navigator.share) { try { await navigator.share({title, url}); } catch (err) { /* abgebrochen */ } if (hinweis) note("Tournamen sind im Link sichtbar"); }
      else { await navigator.clipboard.writeText(url); note(hinweis ? "Link kopiert (24 Stunden gültig, ohne Konto ansehbar; Tournamen sind sichtbar)" : "Link kopiert (24 Stunden gültig, ohne Konto ansehbar)"); }
    } catch (err) { note("Link erstellen nicht möglich: " + err.message); }
    bshr.disabled = false;
  };
  // Wischen: links/rechts = nächstes/vorheriges Foto; Tippen: linkes Drittel zurück, rechtes Drittel weiter, Mitte zeigt die Bedienelemente
  let tx = null, ty = null;
  addEventListener("touchstart", e => { tx = e.touches[0].clientX; ty = e.touches[0].clientY; }, {passive: true});
  addEventListener("touchend", e => {
    if (tx == null) return;
    const dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty; tx = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > 1.5 * Math.abs(dy)) { swiped = Date.now(); show(dx < 0 ? i + 1 : i - 1); loop(); poke(); }
  }, {passive: true});
  addEventListener("click", e => {
    if (Date.now() - swiped < 500) return;
    const x = e.clientX / innerWidth;
    if (x > 1 / 3 && x < 2 / 3) { poke(); return; }
    show(x < 1 / 3 ? i - 1 : i + 1); loop(); poke();
  });
  // Bildschirm während der Diashow wach halten (wo unterstützt)
  let wl = null; const keepAwake = async () => { try { wl = await navigator.wakeLock.request("screen"); } catch (err) {} };
  keepAwake(); document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") keepAwake(); });
  poke(); show(0); loop();
})();
