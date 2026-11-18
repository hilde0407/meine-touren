/* 3D-Flug, freie Kamera: Steuerung für Touchpad und Tastatur (3.39.0). Reine Funktionen ohne Zugriff auf die Karte, damit sie sich allein prüfen lassen (tests/test_flug_steuerung_339.py, Node);
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
/* Wheel-Ereignis (Zweifinger-Wischen auf dem Touchpad): seitwärts dreht, mit Alt/Option kippt; Strg/Meta (Pinch) und senkrechtes Wischen bleiben beim Zoomen (Rückgabe null) */
function flWheelDelta(e) {
  if (!e || e.ctrlKey || e.metaKey) return null;
  const k = e.deltaMode === 1 ? 16 : 1, dx = (e.deltaX || 0) * k, dy = (e.deltaY || 0) * k;
  if (e.altKey) {
    const v = Math.abs(dy) >= Math.abs(dx) ? dy : dx;
    return v ? {bearing: 0, pitch: v * FL_WHEEL_PITCH} : null;
  }
  if (dx && Math.abs(dx) > Math.abs(dy)) return {bearing: dx * FL_WHEEL_BEARING, pitch: 0};
  return null;
}
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
/* Safari-Touchpad-Geste: rotation (Grad, im Uhrzeigersinn) gegenüber dem letzten Ereignis → Änderung der Richtung (MapLibre: Karte dreht mit den Fingern) */
const flGestureDelta = (prev, rot) => -(rot - prev);
if (typeof module !== "undefined") module.exports = {flDragDelta, flWheelDelta, flKeyDelta, flGestureDelta, flClampPitch, flNorm};
