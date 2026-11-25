/* =====================  Sportart-Kennzahlen, Steigung auf der Karte, Jahreszeit der Wunschliste  ===================== */
/* Aktivitäten-Familien (intern, wie gpxtools.FAMILIE): Tempo-Kennzahlen, Steilheit, Planung (Tempo aus ähnlichen Touren, Routing-Profil) und ältere Ziele „grp:…“.
   3.59.0: KEINE Zusammenfassung in der Statistik mehr – dafür gibt es die eigenen Statistik-Gruppen (01-grundlagen.js, sgKey). Neue Aktivitäten sind ergänzt;
   Schneeschuh ist wieder eigene Sportart und gehört zur Familie „Zu Fuß“ (so zählen ältere Ziele „Zu Fuß (Wandern, Bergtour, Schneeschuh)“ wie bisher).
   3.60.0: nur noch Aktivitäten des Katalogs; entfernte Schlüssel älterer Touren zählen über ihren Rückfall (sNorm), z. B. Radpendeln als Radtour. */
const SPORT_GRP = {
  bike: ["touringbicycle", "e_touringbicycle", "racebike", "mtb", "mtb_easy", "e_mtb", "bikepacking"],
  ski: ["skitour", "skialpin", "snowboard"],
  foot: ["hike", "mountaineering", "nordicwalking", "snowshoe", "walk", "climbing"],
  run: ["jogging", "nordic", "trailrun"],
};
const sportGrp = s => Object.keys(SPORT_GRP).find(k => SPORT_GRP[k].includes(sNorm(s))) || "other";
const STEEP30 = 58; // 30° Hangneigung entsprechen ≈ 58 % Steigung

/* Kennzahlen aus den Streckenpunkten [lat, lng, Höhe, ms seit Start]; Abschnitte von mindestens 30 m glätten das GPS-Rauschen. */
function sportMetrics(c) {
  const P = [c[0]];
  for (const p of c) if (hav(P[P.length - 1], p) >= 30) P.push(p);
  const n = P.length;
  if (n < 4) return null;
  const el = P.map((p, i) => {
    const v = [P[i - 1], p, P[i + 1]].filter(q => q && q[2] != null).map(q => q[2]);
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
  });
  const hasT = P.every(p => p[3] != null);
  const m = {dist: 0, up: 0, down: 0, dUp: 0, dDown: 0, tUp: 0, tDown: 0, tMove: 0, tPause: 0, steep: 0, maxG: 0, maxV: 0, hasT, cum: [0]};
  for (let i = 0; i < n - 1; i++) {
    const d = hav(P[i], P[i + 1]),
      dz = el[i] != null && el[i + 1] != null ? el[i + 1] - el[i] : 0,
      g = (dz / d) * 100,
      dt = hasT ? (P[i + 1][3] - P[i][3]) / 1000 : 0,
      mov = hasT && dt > 0 && d / dt >= 0.3;
    m.cum.push(m.cum[i] + d);
    m.dist += d;
    if (dz > 0) m.up += dz;
    else m.down -= dz;
    if (g >= 3) m.dUp += d;
    else if (g <= -3) m.dDown += d;
    if (hasT && dt > 0) {
      if (mov) {
        m.tMove += dt;
        if (g >= 3) m.tUp += dt;
        else if (g <= -3) m.tDown += dt;
      } else m.tPause += dt;
    }
  }
  // steilster Abschnitt, Anteil über 30° und Höchsttempo in gleitenden Fenstern
  let steepD = 0,
    cover = 0;
  for (let i = 0, j = 1; i < n - 1; i++) {
    j = Math.max(j, i + 1);
    while (j < n - 1 && m.cum[j] - m.cum[i] < 100) j++;
    const d = m.cum[j] - m.cum[i];
    if (d >= 60 && el[i] != null && el[j] != null) {
      const g = ((el[j] - el[i]) / d) * 100;
      if (Math.abs(g) > Math.abs(m.maxG) && Math.abs(g) < 150) m.maxG = g;
    }
    if (hasT && d >= 50) {
      const dt = (P[j][3] - P[i][3]) / 1000;
      if (dt > 0) m.maxV = Math.max(m.maxV, (d / dt) * 3.6);
    }
  }
  for (let i = 0, j = 1; i < n - 1; i++) {
    j = Math.max(j, i + 1);
    while (j < n - 1 && m.cum[j] - m.cum[i] < 60) j++;
    const d = m.cum[j] - m.cum[i];
    if (d >= 40 && el[i] != null && el[j] != null) {
      cover += m.cum[i + 1] - m.cum[i];
      if (Math.abs(((el[j] - el[i]) / d) * 100) >= STEEP30) steepD += m.cum[i + 1] - m.cum[i];
    }
  }
  m.steep = cover ? steepD / cover : 0;
  return m;
}

/* Welche Kennzahlen passen zur Sportart? Liefert [[Wert, Einheit, Beschriftung], …] */
function sportFigs(t, m) {
  const km = m.dist / 1000,
    H = (s, l) => [...Object.values(fmtDauerTeile(s)), l],
    deg = g => Math.round((Math.atan(Math.abs(g) / 100) * 180) / Math.PI),
    f = [],
    g = sportGrp(t.sport),
    mov = m.hasT && m.tMove > 0;
  const pause = () => m.hasT && f.push(H(m.tPause, "Pausen"));
  if (g === "bike") {
    if (mov) f.push([nf(km / (m.tMove / 3600), 1), "km/h", "Ø in Bewegung"]);
    if (m.maxV) f.push([nf(m.maxV, 0), "km/h", "Höchstes Tempo"]);
    pause();
    f.push([`${Math.round((m.dUp / m.dist) * 100)} / ${Math.round((m.dDown / m.dist) * 100)}`, "%", "bergauf / bergab"]);
  } else if (g === "ski") {
    if (m.hasT) f.push(H(m.tUp, "Aufstieg"), H(m.tDown, "Abfahrt"));
    f.push([nf(m.down, 0), "m", "Abstieg"]);
    if (m.maxV) f.push([nf(m.maxV, 0), "km/h", "Höchstes Tempo"]);
    f.push([`${deg(m.maxG)}`, "°", "steilster Abschnitt"]);
    f.push([`${Math.round(m.steep * 100)}`, "%", "der Strecke über 30°"]);
  } else if (g === "foot") {
    if (mov) f.push(H(m.tMove, "Gehzeit"));
    pause();
    if (m.tUp > 600 && m.up > 50) f.push([nf(m.up / (m.tUp / 3600), 0), "m/h", "Steigrate"]);
    f.push([`${deg(m.maxG)}`, "°", "steilster Abschnitt"]);
    if (isSnowshoe(t)) f.push([`${Math.round(m.steep * 100)}`, "%", "der Strecke über 30°"]);
  } else if (g === "run") {
    if (mov) f.push([fmtMS(m.tMove / km), "min/km", "Pace in Bewegung"]);
    pause();
  } else {
    if (mov) f.push(H(m.tMove, "Zeit in Bewegung"));
    pause();
  }
  return f;
}

const _tour24 = VIEWS.tour;
VIEWS.tour = async (...a) => {
  await _tour24(...a);
  const t = BY[a[0]],
    box = document.querySelector("#main .tmap");
  if (!t || !box || $("#sfigs")) return;
  const c = cleanPts(await api(`/api/tours/${encodeURIComponent(t.id)}/coords`).catch(() => []));
  if (c.length < 10 || !document.querySelector("#main .tmap") || $("#sfigs")) return;
  const m = sportMetrics(c);
  if (!m) return;
  const f = sportFigs(t, m);
  if (f.length)
    document
      .querySelector("#main .tmap")
      .insertAdjacentHTML(
        "beforebegin",
        `<div class="figs sm" id="sfigs">${f.map(x => `<div class="fig"><div class="v">${x[0]}<span class="u">${x[1]}</span></div><div class="l">${x[2]}</div></div>`).join("")}</div>`
      );
  steepButton(t);
};

/* Knopf „Steigung“ direkt auf der Karte: schaltet die Steigungsfärbung der Analyse ein und aus */
function steepButton(t) {
  let k = 0;
  const go = () => {
    if (!window.tlSlope || !map || !map.addControl) return k++ < 40 && setTimeout(go, 200);
    if (document.querySelector("#tm .smap")) return;
    const ski = sportGrp(t.sport) === "ski" || isSnowshoe(t);
    const C = L.Control.extend({
      options: {position: "topleft"},
      onAdd() {
        const b = L.DomUtil.create("button", "smap");
        b.type = "button";
        b.title = "Strecke nach Steigung einfärben";
        b.textContent = "⛰ Steigung";
        L.DomEvent.disableClickPropagation(b);
        b.onclick = () => {
          const on = window.tlSlope();
          b.classList.toggle("on", on);
          const old = document.querySelector("#tm .sleg");
          if (old) old.remove();
          if (on) {
            const d = document.createElement("div");
            d.className = "tleg sleg";
            d.innerHTML = GR.map(x => `<span><i style="background:${x[2]}"></i>${x[3]}</span>`).join("") + (ski ? `<span><i style="background:#7e22ce"></i>über 30°</span>` : "");
            $("#tm").appendChild(d);
          }
        };
        return b;
      },
    });
    map.addControl(new C());
    if (window.tlWantSlope) {                    // Verweis „Steigung auf der Karte zeigen“ aus der Unterseite Auswertung
      window.tlWantSlope = false;
      document.querySelector("#tm .smap").click();
    }
  };
  go();
}

/* ---------- Wunschliste: Jahreszeit ---------- */
const _places24 = VIEWS.places;
VIEWS.places = async (...a) => {
  await _places24(...a);
  const root = $("#wlist");
  if (!root || root.dataset.season) return;
  root.dataset.season = "1";
  const now = seasonOfMonth(new Date().getMonth() + 1);
  let all = [];
  try {
    all = await api("/api/wishlist");
  } catch (e) {
    return;
  }
  let again = false;
  const mark = () =>
    root.querySelectorAll("[data-w]").forEach(b => {
      const row = b.closest(".r"),
        x = all.find(z => z.id === +b.dataset.w);
      if (!x && !again) {
        again = true; // neu vorgemerkt: Liste einmal neu laden
        api("/api/wishlist").then(l => {
          all = l;
          mark();
          again = false;
        });
      }
      if (!x || !row || row.querySelector(".wseason")) return;
      const fits = x.season && x.season === now;
      b.insertAdjacentHTML(
        "beforebegin",
        `<select class="wseason" data-ws="${x.id}" title="Beste Jahreszeit für diese Tour"><option value="">ganzjährig</option><option value="sommer">☀ Sommer</option><option value="winter">❄ Winter</option></select> ${fits ? '<span class="tag" style="background:var(--green,#2f8f5f)">passt jetzt</span> ' : ""}`
      );
      row.querySelector(".wseason").value = x.season || "";
      row.querySelector(".wseason").onchange = async e => {
        x.season = e.target.value;
        await api("/api/wishlist", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({id: x.id, season: x.season})});
        row.querySelector(".tag")?.remove();
        if (x.season && x.season === now) e.target.insertAdjacentHTML("afterend", ' <span class="tag" style="background:var(--green,#2f8f5f)">passt jetzt</span>');
      };
    });
  mark();
  new MutationObserver(() => mark()).observe(root, {childList: true, subtree: true});
};
