import de.meinetouren.app.Guide;
import de.meinetouren.app.GuideText;
import java.util.ArrayList;
import java.util.List;

public class GuideTextCheck {
    static void check(boolean ok, String msg) { if (!ok) { System.err.println("FEHLER: " + msg); System.exit(1); } }

    public static void main(String[] a) {
        check(GuideText.norm("fr-CA").equals("fr") && GuideText.norm("it").equals("en") && GuideText.norm(null).equals("en"), "Sprachwahl");
        String[][] exp = {{"de", "In 100 Metern links abbiegen."}, {"en", "In 100 metres, turn left."}, {"fr", "Dans 100 mètres, tournez à gauche."}, {"es", "En 100 metros gira a la izquierda."}};
        for (String[] e : exp) {
            GuideText.lang = e[0];
            String s = GuideText.ahead(100, -90, "");
            check(s.equals(e[1]), e[0] + ": " + s);
            check(!GuideText.arrived().isEmpty() && !GuideText.test().isEmpty() && !GuideText.oneKm().isEmpty(), e[0] + " Texte");
            for (double ang : new double[]{-170, 170, -130, 130, -90, 90, -45, 45}) check(!GuideText.instruction(ang).isEmpty(), "Richtung");
            check(GuideText.dist(1500).startsWith("1,5") || GuideText.dist(1500).startsWith("1.5"), e[0] + " km: " + GuideText.dist(1500));
            check(GuideText.now(90, GuideText.thenPart(45)).endsWith("."), e[0] + " now");
        }
        // lange gerade Strecke (12 km): Halbzeit und „noch fünf Kilometer“ werden je einmal angesagt
        GuideText.lang = "de";
        int n = 121;
        double[] la = new double[n], lo = new double[n];
        for (int i = 0; i < n; i++) { la[i] = 48.0 + i * 100 / 110540.0; lo[i] = 8.0; }
        Guide g = new Guide(la, lo);
        List<String> said = new ArrayList<>();
        for (int i = 0; i < n; i++) said.addAll(g.fix(la[i], lo[i], 5f, 1.4, i * 70000L));
        String all = String.join(" | ", said);
        check(all.contains("Halbzeit") && all.indexOf("Halbzeit") == all.lastIndexOf("Halbzeit"), "Halbzeit: " + all);
        check(all.contains("fünf Kilometer") && all.contains("ein Kilometer") && all.contains("Ziel erreicht"), "Restansagen: " + all);
        check(g.nextTurn() == null, "keine Abbiegung auf der Geraden");
        for (String l : new String[]{"de", "en", "fr", "es"}) {
            GuideText.lang = l;
            for (String k : new String[]{"thunder", "rain", "wind", "snow", "cold"}) {
                String w = GuideText.weather(k, 2, 70);
                check(w.length() > 20, l + " " + k);
                check(k.equals("wind") || k.equals("cold") ? w.contains("70") : true, l + " Wert " + k + ": " + w);
                check(w.contains("2"), l + " Stunden " + k + ": " + w);
            }
            check(GuideText.weather("thunder", 0, 0).length() > 20 && !GuideText.weatherTitle().isEmpty(), l + " jetzt");
        }
        GuideText.lang = "de";
        System.out.println("OK GuideText");
    }
}
