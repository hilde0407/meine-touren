/* Skript der Seite share.html (eigene Datei, damit die Content-Security-Policy Inline-Skripte verbieten kann) */
const tok = location.pathname.split("/").pop(), nf = (n, d = 1) => Number(n).toLocaleString("de-DE", {minimumFractionDigits: d, maximumFractionDigits: d});
fetch("/api/public/" + tok).then(r => { if (!r.ok) throw 0; return r.json(); }).then(t => {
  document.title = t.name; document.getElementById("h").textContent = t.name;
  document.getElementById("k").textContent = new Date(t.date).toLocaleDateString("de-DE", {weekday: "long", day: "numeric", month: "long", year: "numeric"});
  document.getElementById("f").innerHTML = [[nf(t.km) + " km", "Strecke"], [nf(t.up_m, 0) + " m", "Aufstieg"], [nf(t.down_m, 0) + " m", "Abstieg"], [nf(t.h) + " h", "Dauer"]].map(x => `<div class="fig"><b>${x[0]}</b><span>${x[1]}</span></div>`).join("");
  const m = L.map("m"); L.tileLayer("/tiles/osm/{z}/{x}/{y}", {maxZoom: 18, attribution: "© OpenStreetMap"}).addTo(m);
  const ll = t.coords.map(p => [p[0], p[1]]);
  if (ll.length > 1) { const l = L.polyline(ll, {color: "#e11d74", weight: 5}).addTo(m); m.fitBounds(l.getBounds(), {padding: [20, 20]}); } else m.setView([50, 9], 5);
  const P = document.getElementById("p"), lb = document.getElementById("lb");
  P.innerHTML = t.photos.map(id => `<img loading="lazy" src="/pub/${tok}/photo/${id}?size=400" data-id="${id}">`).join("");
  P.onclick = e => { const i = e.target.closest("img"); if (i) { lb.firstChild.src = `/pub/${tok}/photo/${i.dataset.id}?size=1600`; lb.style.display = "flex"; } };
  lb.onclick = () => lb.style.display = "none";
}).catch(() => { document.querySelector("main").innerHTML = '<div class="err">Dieser Link ist nicht (mehr) gültig.</div>'; });
