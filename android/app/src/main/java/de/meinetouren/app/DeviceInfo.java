package de.meinetouren.app;

/**
 * Geräteangaben der App für den Server („Meine Geräte“ – die App als Aufzeichnungsgerät, ab 3.49.0).
 * Reines Java ohne Android-Klassen, damit es sich wie TrackStore außerhalb eines Geräts prüfen lässt (tests/android/DeviceInfoCheck.java).
 * Enthalten sind nur: eine zufällige Kennung dieser Installation (keine Android-ID, IMEI oder Seriennummer), Hersteller, Modell,
 * Android-Version und App-Version.
 */
final class DeviceInfo {
    private DeviceInfo() { }

    /** Gültige Installationskennung: zufällige UUID in Kleinbuchstaben, wie sie java.util.UUID#toString liefert. */
    static boolean validId(String id) {
        return id != null && id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}");
    }

    /** Steuerzeichen entfernen, Ränder kürzen, höchstens max Zeichen (ein halbes Zeichenpaar am Ende wird nicht stehen gelassen). */
    static String clean(String s, int max) {
        if (s == null) return "";
        StringBuilder b = new StringBuilder();
        String t = s.trim();
        for (int i = 0; i < t.length() && b.length() < max; i++) {
            char c = t.charAt(i);
            if (c < 0x20 || c == 0x7f) continue;
            b.append(c);
        }
        if (b.length() > 0 && Character.isHighSurrogate(b.charAt(b.length() - 1))) b.setLength(b.length() - 1);
        return b.toString().trim();
    }

    /** Text als JSON-Zeichenkette (mit Anführungszeichen). */
    static String quote(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 0x20 || c == 0x7f || c == 0x2028 || c == 0x2029) b.append(String.format("\\u%04x", (int) c));
            else b.append(c);
        }
        return b.append('"').toString();
    }

    /** JSON für die Brücke: {install_id, hersteller, modell, android, app_version}. */
    static String json(String installId, String maker, String model, String release, String appVersion) {
        return "{\"install_id\":" + quote(validId(installId) ? installId : "")
                + ",\"hersteller\":" + quote(clean(maker, 40))
                + ",\"modell\":" + quote(clean(model, 40))
                + ",\"android\":" + quote(clean(release, 20))
                + ",\"app_version\":" + quote(clean(appVersion, 20)) + "}";
    }
}
