/* 3D-Flug flüssiger (3.61.4): Rechenlogik ohne Oberfläche für js/07-flug.js (Vorbild: Mein Tourentagebuch 2.16.0, calc-flug.js). Läuft im Browser (globales `FlugCalc`) und in Node (tests/test_flug_fluessig_3614.py).
   - Darstellungsstufen „Flüssig / Normal / Schön“ (Auflösung der Karte, Höhenkacheln, Überhöhung, Takt der Anzeigen)
   - Ausdünnen der gelben „schon geflogen“-Linie (Douglas-Peucker in Metern)
   - Anpassung im Flug: zu langsame Bilder → eine Stufe herunter, mit Hysterese (kein Hin und Her)
   - Kamera als reine Funktion der Flugposition f (Punktindex, gebrochen): gleiche Position → gleiche Kamera, unabhängig davon, wie viele Bilder vorher gezeichnet wurden. */
const FlugCalc = (() => {
  /** Stufen. pr = höchstes pixelRatio der Karte (Zeichenfläche); dem = höchste Zoomstufe der Höhenkacheln (weniger = weniger Kacheln);
   *  ueber = Überhöhung des Geländes; neig = Grundneigung der Kamera (flacher = weniger Kacheln bis zum Horizont);
   *  hud/spur = kürzester Abstand (ms) zwischen zwei Aktualisierungen der Kopfzeile bzw. der gelben Linie; tol = Toleranz (m) beim Ausdünnen der Linie.
   *  „Schön“ entspricht dem bisherigen Aussehen am Computer (Höhendaten bis Zoomstufe 15, Überhöhung 1,5, Neigung 68°). */
  const STUFEN = {
    fluessig: {name: "Flüssig", pr: 1, dem: 12, ueber: 1.3, neig: 60, hud: 200, spur: 250, tol: 5},
    normal: {name: "Normal", pr: 1.5, dem: 13, ueber: 1.4, neig: 64, hud: 150, spur: 160, tol: 3},
    schoen: {name: "Schön", pr: 3, dem: 15, ueber: 1.5, neig: 68, hud: 100, spur: 100, tol: 1.5},
  };
  const FOLGE = ["schoen", "normal", "fluessig"];
  const WAHL = [["fluessig", "Flüssig"], ["normal", "Normal"], ["schoen", "Schön"]];
  const ADAPT = {fenster: 30, grenze: 40, ruhe: 60, ausreisser: 1000};

  /** Gültige Stufe; leer/unbekannt → Vorgabe: am Handy „Flüssig“, am Computer „Schön“ (wie bisher; die Anpassung im Flug schaltet bei Bedarf herunter). */
  const stufe = (v, handy) => (STUFEN[v] ? v : handy ? "fluessig" : "schoen");
  /** pixelRatio der Karte: nie über dem des Geräts und nie über der Grenze der Stufe. */
  const pixelRatio = (st, dpr) => Math.min(+dpr > 0 ? +dpr : 1, (STUFEN[st] || STUFEN.fluessig).pr);
  /** Nächst einfachere Stufe oder null. */
  const tiefer = st => {
    const i = FOLGE.indexOf(st);
    return i >= 0 && i < FOLGE.length - 1 ? FOLGE[i + 1] : null;
  };
  /** Mindestabstand zwischen zwei gezeichneten Bildern (ms): bei 120/144 Hz nur jedes zweite Bild (60/72 je Sekunde), bei 60 und 90 Hz jedes. */
  const BILD_MIN_MS = 10;
  /** Fälligkeit einer gedrosselten Aktualisierung (Kopfzeile, Linie). */
  const faellig = (letzte, jetzt, ms) => letzte == null || jetzt - letzte >= ms;

  /** Douglas-Peucker auf Punkten [lng, lat] (Toleranz in Metern, örtlich flach gerechnet). Liefert die Indizes der behaltenen Punkte
   *  (aufsteigend, erster und letzter immer dabei). Ohne Rekursion, damit lange Spuren den Stapel nicht sprengen. */
  function duenneIdx(pts, tol) {
    const n = pts.length;
    if (n <= 2) return pts.map((_, i) => i);
    const lat0 = (pts[0][1] * Math.PI) / 180, kx = 111320 * Math.cos(lat0), ky = 110540;
    const X = new Float64Array(n), Y = new Float64Array(n);
    for (let i = 0; i < n; i++) { X[i] = pts[i][0] * kx; Y[i] = pts[i][1] * ky; }
    const keep = new Uint8Array(n);
    keep[0] = keep[n - 1] = 1;
    const st = [0, n - 1], t2 = tol * tol;
    while (st.length) {
      const b = st.pop(), a = st.pop(), dx = X[b] - X[a], dy = Y[b] - Y[a], L = dx * dx + dy * dy;
      let best = -1, bi = -1;
      for (let i = a + 1; i < b; i++) {
        let d;
        if (L === 0) d = (X[i] - X[a]) ** 2 + (Y[i] - Y[a]) ** 2;
        else { const c = dx * (Y[a] - Y[i]) - dy * (X[a] - X[i]); d = (c * c) / L; }
        if (d > best) { best = d; bi = i; }
      }
      if (bi > 0 && best > t2) { keep[bi] = 1; st.push(a, bi, bi, b); }
    }
    const out = [];
    for (let i = 0; i < n; i++) if (keep[i]) out.push(i);
    return out;
  }

  /* ---------- Anpassung im Flug (Hysterese) ----------
     Fenster aus 30 Bildzeiten; ist der Schnitt über 40 ms (unter 25 Bildern je Sekunde), geht es eine Stufe herunter. Danach werden 60 Bilder lang keine Zeiten gezählt
     (Karte stellt sich um, Kacheln laden neu), und ein neues volles Fenster ist nötig. Hochgeschaltet wird im laufenden Flug nie – so springt es nicht zwischen zwei Stufen.
     Einzelne sehr lange Abstände (> 1 s: App im Hintergrund, Laden) zählen nicht. */
  const adaptiv = st => ({stufe: stufe(st, true), buf: [], ruhe: 0});
  /** Eine Bildzeit verbuchen. Rückgabe: neue Stufe, wenn heruntergeschaltet wurde, sonst null. Ändert den Zustand a. */
  function adaptivSchritt(a, ms) {
    if (!(ms > 0) || ms > ADAPT.ausreisser) return null;
    if (a.ruhe > 0) { a.ruhe--; return null; }
    a.buf.push(ms);
    if (a.buf.length > ADAPT.fenster) a.buf.shift();
    if (a.buf.length < ADAPT.fenster) return null;
    const m = a.buf.reduce((x, y) => x + y, 0) / a.buf.length, t = m > ADAPT.grenze ? tiefer(a.stufe) : null;
    if (!t) return null;
    a.stufe = t; a.buf = []; a.ruhe = ADAPT.ruhe;
    return t;
  }

  /* ---------- Kamera als Funktion der Position ---------- */
  const peil = (a, b) => {
    const r = Math.PI / 180, y = Math.sin((b.lng - a.lng) * r) * Math.cos(b.lat * r),
      x = Math.cos(a.lat * r) * Math.sin(b.lat * r) - Math.sin(a.lat * r) * Math.cos(b.lat * r) * Math.cos((b.lng - a.lng) * r);
    return ((Math.atan2(y, x) / r) + 360) % 360;
  };
  /** Blickrichtung je Punkt: zum Punkt `vor` Schritte weiter, dann über ±w Punkte gemittelt (als Einheitsvektoren, damit 359°/1° stimmt).
   *  Ersetzt die frühere Glättung „pro Bild in Echtzeit“: das Ergebnis hängt nur von der Strecke ab. */
  function peilungen(S, vor, w) {
    const N = S.length, raw = new Float64Array(N), out = new Float64Array(N);
    for (let i = 0; i < N; i++) {
      const j = Math.min(N - 1, i + vor);
      raw[i] = j > i ? peil(S[i], S[j]) : i > 0 ? raw[i - 1] : 0;
    }
    const cx = new Float64Array(N + 1), cy = new Float64Array(N + 1);
    for (let i = 0; i < N; i++) { cx[i + 1] = cx[i] + Math.sin((raw[i] * Math.PI) / 180); cy[i + 1] = cy[i] + Math.cos((raw[i] * Math.PI) / 180); }
    for (let i = 0; i < N; i++) {
      const a = Math.max(0, i - w), b = Math.min(N - 1, i + w), sx = cx[b + 1] - cx[a], sy = cy[b + 1] - cy[a];
      out[i] = sx === 0 && sy === 0 ? raw[i] : ((Math.atan2(sx, sy) * 180) / Math.PI + 360) % 360;
    }
    return out;
  }
  const winkelLerp = (a, b, f) => (a + (((b - a + 540) % 360) - 180) * f + 360) % 360;

  /** Neigungstabelle: Stützstellen alle `schritt` Punkte; Wert null = noch nicht berechnet (dann Grundneigung). */
  const neigTabelle = (N, schritt) => ({schritt: Math.max(1, schritt), w: new Array(Math.ceil(N / Math.max(1, schritt)) + 1).fill(null)});
  /** Neigung an der Stelle f (Punktindex, gebrochen): je Stützstelle das Minimum aus ihr und den zwei folgenden (Berge früh vorwegnehmen), dazwischen linear. */
  function neigBei(T, f, basis) {
    if (!T) return basis;
    const v = k => {
      let m = basis;
      for (let j = k - 1; j <= k + 2; j++) { const x = T.w[Math.max(0, Math.min(T.w.length - 1, j))]; if (x != null && x < m) m = x; }
      return m;
    };
    const q = f / T.schritt, k = Math.floor(q);
    return v(k) + (v(k + 1) - v(k)) * (q - k);
  }

  /** Kamera bei Flugposition f (Punktindex 0 … N−1, gebrochen). B = { S (geglättete Mitte), P (Punkte, im Reiseflug mit trans/tq/lift), brg (peilungen), neig (Tabelle) };
   *  o = { zBase, neigung: 'auto' | Zahl | null, basis (Grundneigung der Stufe), set (Reiseflug), rec (Aufnahme) }.
   *  zoom ist null, wenn der Flug den Zoom dem Menschen überlässt (Einzelflug ohne Aufnahme); pitch ist null bei fester Neigung. Reine Funktion. */
  function kamera(f, B, o) {
    const N = B.S.length, ff = Math.max(0, Math.min(N - 1, f)), i = Math.min(N - 2, Math.floor(ff)), r = ff - i;
    const a = B.S[i], b = B.S[i + 1] || a, p = B.P[Math.min(N - 1, Math.round(ff))];
    const out = {center: [a.lng + (b.lng - a.lng) * r, a.lat + (b.lat - a.lat) * r], bearing: winkelLerp(B.brg[i], B.brg[Math.min(N - 1, i + 1)], r), pitch: null, zoom: null};
    const sinT = p && p.trans ? Math.sin(Math.PI * p.tq) : 0;
    if (o.neigung === "auto") {
      let pi = neigBei(B.neig, ff, o.basis);
      if (o.set && p && p.trans) pi = Math.min(pi, o.basis - 22 * sinT);        // im Übergang steiler von oben
      out.pitch = pi;
    }
    if (o.set || o.rec) out.zoom = o.zBase + (o.rec ? 0.9 : 0) - (o.set && p && p.trans ? p.lift * sinT : 0);   // Aufnahme etwas näher; im Übergang aufsteigen (herauszoomen), danach wieder absinken
    return out;
  }

  /** Steilster Neigungswinkel (≤ base), bei dem die Sicht von der Kamera zum Streckenpunkt frei ist (Berge im Weg). elev(lng, lat) → Meter oder null.
   *  voll = false, wenn Höhendaten fehlten (dann später noch einmal rechnen). */
  function freieNeigung(elev, lng, lat, bearing, base, D, floor) {
    floor = floor == null ? 28 : floor;
    const br = (bearing * Math.PI) / 180, kx = 111320 * Math.cos((lat * Math.PI) / 180), ky = 110540, aim = 25;
    let voll = true;
    for (let th = base; th >= floor; th -= 4) {
      const al = (th * Math.PI) / 180, dh = D * Math.sin(al), hz = D * Math.cos(al);
      let ok = true;
      for (let k = 1; k <= 14 && ok; k++) {
        const f = k / 15, e = elev(lng - (Math.sin(br) * dh * (1 - f)) / kx, lat - (Math.cos(br) * dh * (1 - f)) / ky);
        if (e == null) voll = false;
        else if (e > aim + (hz - aim) * (1 - f) - 25) ok = false;
      }
      if (ok) return {th, voll};
    }
    return {th: floor, voll};
  }

  const api = {STUFEN, FOLGE, WAHL, ADAPT, BILD_MIN_MS, stufe, pixelRatio, tiefer, duenneIdx, faellig, adaptiv, adaptivSchritt, peil, peilungen, winkelLerp, neigTabelle, neigBei, kamera, freieNeigung};
  if (typeof module !== "undefined") module.exports = api;
  return api;
})();
