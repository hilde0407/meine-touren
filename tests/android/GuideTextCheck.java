import de.meinetouren.app.GuideText;

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
        System.out.println("OK GuideText");
    }
}
