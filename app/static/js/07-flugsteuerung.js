/* 3D-Flug, freie Kamera: Steuerung für Maus, Touchpad und Tastatur (3.39.0, in 3.40.0 neu geordnet: Bedienleiste statt Drehen-Modus, Zweifinger-Wischen dreht und neigt). Reine Funktionen ohne Zugriff auf die Karte, damit sie sich allein prüfen lassen (tests/test_flug_steuerung_340.py, Node);
   die Verdrahtung mit MapLibre steht in 07-flug.js. MapLibre kennt Drehen und Kippen nur mit rechter Maustaste, Strg+Ziehen oder zwei Fingern auf dem Touchscreen – ein Touchpad hat nichts davon. */
const FL_DEG_PX = 0.5;               // Grad Drehung je Pixel Ziehen (wie MapLibre bei der rechten Maustaste: 0,8; etwas feiner)
const FL_PITCH_PX = 0.5;             // Grad Neigung je Pixel Ziehen
const FL_WHEEL_BEARING = 0.25;       // Grad je Wheel-Einheit beim seitlichen Zweifinger-Wischen
const FL_WHEEL_PITCH = 0.2;          // Grad je Wheel-Einheit bei Alt/Option + Wischen
const FL_KEY_BEARING = 10;           // Grad je Tastendruck (Umschalt: doppelt)
const FL_KEY_PITCH = 5;
const FL_MAX_PITCH = 85;
const flClampPitch = p => Math.max(0, Math.min(FL_MAX_PITCH, p));
const flNorm = x => ((((x + 180) % 360) + 360) % 360) - 180;                       // Richtung in −180 … 180
/* Ziehen (Pixel seit dem letzten Ereignis) → Änderung von Richtung und Neigung */
function flDragDelta(dx, dy) {
  return {bearing: dx * FL_DEG_PX, pitch: -dy * FL_PITCH_PX};
}
/* ---- 3.40.0: Maus oder Touchpad? ----
   Ein wheel-Ereignis sagt nicht, woher es kommt. Entschieden wird einmal je Geste (am ersten Ereignis nach mindestens FL_GESTE_MS Ruhe) und dann beibehalten:
   deltaMode ≠ 0 (Zeilen/Seiten) → Maus; feste Rastschritte (Vielfache von 100 oder 120, große ganzzahlige Schritte ohne Querbewegung, Vielfache von 4,000244140625 = Mausrad unter macOS)
   → Maus; kleine, wechselnde Werte oder eine Querbewegung (deltaX ≠ 0 ohne Umschalt) → Touchpad. Die Einstellung „Maus“/„Touchpad“ geht immer vor. */
const FL_GESTE_MS = 400;
const FL_MAC_RAD = 4.000244140625;
const flVielfach = (v, q) => { const r = v / q; return r >= 1 && Math.abs(r - Math.round(r)) < 1e-6; };
function flWheelGuess(e) {
  if (e.deltaMode) return "maus";
  const ax = Math.abs(e.deltaX || 0), ay = Math.abs(e.deltaY || 0), v = Math.max(ax, ay);
  if (!v) return "touchpad";
  if (!Number.isInteger(v) && flVielfach(v, FL_MAC_RAD)) return "maus";
  const quer = e.shiftKey ? 0 : Math.min(ax, ay) || (ax > ay ? ax : 0);       // Umschalt + Mausrad liefert deltaX statt deltaY: keine Querbewegung
  if (Number.isInteger(v) && (flVielfach(v, 100) || flVielfach(v, 120)) && Math.min(ax, ay) === 0) return "maus";
  if (quer) return "touchpad";
  if (Number.isInteger(v) && v >= 50) return "maus";
  return "touchpad";
}
/* st = {t, kind} merkt sich die laufende Geste; pref = "auto" | "maus" | "touchpad" */
function flWheelKind(e, st, now, pref) {
  if (pref === "maus" || pref === "touchpad") { st.t = now; st.kind = pref; return pref; }
  if (!st.kind || now - st.t > FL_GESTE_MS) st.kind = flWheelGuess(e);
  st.t = now;
  return st.kind;
}
/* Was ein wheel-Ereignis in der freien Kamera tut: null = MapLibre zoomt wie gewohnt; {skip:true} = verwerfen (Safari meldet die Pinch-Geste zusätzlich als Strg+wheel);
   sonst Änderung von Richtung und Neigung. Strg/Meta + wheel ist der Pinch des Touchpads (zoomt), Alt/Option + Rad neigt bei Maus und Touchpad. */
function flWheelAction(e, kind, inGeste) {
  if (!e) return null;
  if (e.ctrlKey || e.metaKey) return inGeste ? {skip: true} : null;
  const k = e.deltaMode === 1 ? 16 : 1, dx = (e.deltaX || 0) * k, dy = (e.deltaY || 0) * k;
  if (e.altKey) {
    const v = Math.abs(dy) >= Math.abs(dx) ? dy : dx;
    return v ? {bearing: 0, pitch: v * FL_WHEEL_PITCH} : null;
  }
  if (kind !== "touchpad" || (!dx && !dy)) return null;
  return {bearing: dx * FL_WHEEL_BEARING, pitch: dy * FL_WHEEL_PITCH};
}
/* Orbit: die Karte dreht sich um einen festen Punkt am Boden (den aktuellen Tourpunkt), nicht um die Bildmitte. Neue Kartenmitte nach einer Drehung um d Grad;
   der Punkt bleibt dabei an derselben Stelle im Bild. Gerechnet in der Web-Mercator-Ebene (x nach Osten, y nach Süden). */
const flMercY = lat => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
const flLatY = y => (Math.atan(Math.exp(y)) * 360) / Math.PI - 90;
function flOrbit(center, pivot, d) {
  const a = (d * Math.PI) / 180, R = Math.PI / 180;
  const x = (center.lng - pivot.lng) * R, y = -(flMercY(center.lat) - flMercY(pivot.lat));
  const nx = x * Math.cos(a) - y * Math.sin(a), ny = x * Math.sin(a) + y * Math.cos(a);
  return {lng: pivot.lng + nx / R, lat: flLatY(flMercY(pivot.lat) - ny)};
}
/* Kamera-Voreinstellungen der Bedienleiste; tour = Laufrichtung der Tour am aktuellen Punkt. zentrieren: Kartenmitte auf den Tourpunkt setzen */
function flPreset(name, now, tour) {
  switch (name) {
    case "nord": return {bearing: 0, pitch: 0, zentrieren: false};
    case "oben": return {bearing: now.bearing, pitch: 0, zentrieren: true};
    case "schraeg": return {bearing: now.bearing, pitch: 55, zentrieren: true};
    case "hinter": return {bearing: flNorm(tour), pitch: 72, zentrieren: true};
    default: return null;
  }
}
/* Richtung und Neigung in Worten (für Screenreader) */
const FL_RICHTUNG = ["Norden", "Nordosten", "Osten", "Südosten", "Süden", "Südwesten", "Westen", "Nordwesten"];
const flRichtung = b => FL_RICHTUNG[Math.round((((b % 360) + 360) % 360) / 45) % 8];
/* Pfeiltasten: links/rechts drehen, oben/unten kippen (Umschalt: doppelter Schritt); andere Tasten null */
function flKeyDelta(key, shift) {
  const f = shift ? 2 : 1;
  switch (key) {
    case "ArrowLeft": return {bearing: -FL_KEY_BEARING * f, pitch: 0};
    case "ArrowRight": return {bearing: FL_KEY_BEARING * f, pitch: 0};
    case "ArrowUp": return {bearing: 0, pitch: FL_KEY_PITCH * f};
    case "ArrowDown": return {bearing: 0, pitch: -FL_KEY_PITCH * f};
    default: return null;
  }
}
/* Safari-Touchpad-Geste (gesturechange): rotation in Grad im Uhrzeigersinn, scale relativ zum Beginn. Schritt gegenüber dem letzten Ereignis → Änderung von Richtung
   (die Karte dreht mit den Fingern) und Zoomstufe (Verdoppeln des Abstands = eine Stufe). */
const flGestureDelta = (prev, rot) => -(rot - prev);
function flGestureStep(prev, cur) {
  const s0 = prev.scale > 0 ? prev.scale : 1, s1 = cur.scale > 0 ? cur.scale : 1;
  return {bearing: flGestureDelta(prev.rotation || 0, cur.rotation || 0), zoom: Math.log2(s1 / s0)};
}
if (typeof module !== "undefined") module.exports = {flDragDelta, flWheelGuess, flWheelKind, flWheelAction, flOrbit, flPreset, flRichtung, flKeyDelta, flGestureDelta, flGestureStep, flClampPitch, flNorm, FL_GESTE_MS};
