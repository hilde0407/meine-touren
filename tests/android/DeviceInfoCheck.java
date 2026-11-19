package de.meinetouren.app;

/** Prüft die Geräteangaben der App (reines Java): gültiges JSON, Bereinigung, Längen, Kennung. Aufruf: java -cp <out> de.meinetouren.app.DeviceInfoCheck */
public class DeviceInfoCheck {
    static void check(boolean ok, String what) {
        if (!ok) throw new AssertionError(what);
    }

    public static void main(String[] a) {
        String id = java.util.UUID.randomUUID().toString();
        check(DeviceInfo.validId(id), "UUID gilt als Kennung");
        check(!DeviceInfo.validId(null) && !DeviceInfo.validId("") && !DeviceInfo.validId("abc") && !DeviceInfo.validId(id.toUpperCase()) && !DeviceInfo.validId(id + "x"), "ungültige Kennungen");
        String j = DeviceInfo.json(id, "Google", "Pixel 8", "14", "3.49.0");
        check(j.equals("{\"install_id\":\"" + id + "\",\"hersteller\":\"Google\",\"modell\":\"Pixel 8\",\"android\":\"14\",\"app_version\":\"3.49.0\"}"), j);
        // fehlende Werte und eine kaputte Kennung ergeben leere Felder, nie null und nie eine Ausnahme
        j = DeviceInfo.json("kaputt", null, null, null, null);
        check(j.equals("{\"install_id\":\"\",\"hersteller\":\"\",\"modell\":\"\",\"android\":\"\",\"app_version\":\"\"}"), j);
        // Anführungszeichen, Rückstrich, Steuerzeichen und Überlänge
        StringBuilder lang = new StringBuilder();
        for (int i = 0; i < 300; i++) lang.append('M');
        j = DeviceInfo.json(id, "  Sam\"sung\\ ", "SM\n-G\t991" + lang, "14\u0000", "3.49.0");
        check(j.contains("\"hersteller\":\"Sam\\\"sung\\\\\""), j);
        check(!j.contains("\n") && !j.contains("\t") && !j.contains("\u0000"), "keine Steuerzeichen");
        check(j.contains("\"android\":\"14\""), j);
        check(DeviceInfo.clean("SM\n-G\t991" + lang, 40).length() == 40 && DeviceInfo.clean("SM\n-G\t991" + lang, 40).startsWith("SM-G991M"), "Länge begrenzt");
        check(DeviceInfo.clean("ab😀", 3).equals("ab"), "kein halbes Zeichenpaar");
        check(DeviceInfo.quote("a b").equals("\"a\\u2028b\""), "Zeilentrenner maskiert");
        check(DeviceInfo.clean("   ", 10).isEmpty() && DeviceInfo.clean(null, 10).isEmpty(), "leer");
        System.out.println("OK DeviceInfo");
    }
}
