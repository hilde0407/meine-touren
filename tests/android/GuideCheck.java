import de.meinetouren.app.Guide;
import java.util.ArrayList;
import java.util.List;

public class GuideCheck {
    static void check(boolean ok, String msg) {
        if (!ok) { System.err.println("FEHLER: " + msg); System.exit(1); }
    }
    static final double LAT0 = 48.0, LON0 = 8.0, MLAT = 1 / 110540.0, MLON = 1 / (111320.0 * Math.cos(Math.toRadians(48.0)));

    /** Strecke aus (Ost,Nord)-Eckpunkten in Metern, alle 10 m ein Punkt. */
    static Guide route(double[][] c, double jitter) {
        List<double[]> p = new ArrayList<>();
        java.util.Random r = new java.util.Random(1);
        for (int i = 0; i + 1 < c.length; i++) {
            double len = Math.hypot(c[i + 1][0] - c[i][0], c[i + 1][1] - c[i][1]);
            int k = (int) (len / 10);
            for (int j = 0; j < k; j++) {
                double u = j / (double) k;
                p.add(new double[]{c[i][0] + u * (c[i + 1][0] - c[i][0]) + r.nextGaussian() * jitter, c[i][1] + u * (c[i + 1][1] - c[i][1]) + r.nextGaussian() * jitter});
            }
        }
        p.add(c[c.length - 1]);
        double[] la = new double[p.size()], lo = new double[p.size()];
        for (int i = 0; i < la.length; i++) { la[i] = LAT0 + p.get(i)[1] * MLAT; lo[i] = LON0 + p.get(i)[0] * MLON; }
        return new Guide(la, lo);
    }

    static List<String> walk(Guide g, double[][] c, double step, double speed) {
        List<String> said = new ArrayList<>();
        long t = 0;
        for (int i = 0; i + 1 < c.length; i++) {
            double len = Math.hypot(c[i + 1][0] - c[i][0], c[i + 1][1] - c[i][1]);
            for (double d = 0; d < len; d += step) {
                double u = d / len;
                said.addAll(g.fix(LAT0 + (c[i][1] + u * (c[i + 1][1] - c[i][1])) * MLAT, LON0 + (c[i][0] + u * (c[i + 1][0] - c[i][0])) * MLON, 5f, speed, t += 4000));
            }
        }
        said.addAll(g.fix(LAT0 + c[c.length - 1][1] * MLAT, LON0 + c[c.length - 1][0] * MLON, 5f, speed, t += 4000));
        return said;
    }

    public static void main(String[] a) {
        // 1) Rechtsknick nach 600 m, dann Linksknick nach weiteren 700 m (sauberer Weg, 3 km lang)
        double[][] c = {{0, 0}, {0, 600}, {700, 600}, {700, 1800}, {1300, 1800}};
        Guide g = route(c, 0);
        check(g.turnCount() == 3, "Abbiegungen: " + g.turnCount());
        check(g.turn(0).angle > 80 && g.turn(0).angle < 100, "Winkel 1: " + g.turn(0).angle);
        check(g.turn(1).angle < -80 && g.turn(1).angle > -100, "Winkel 2: " + g.turn(1).angle);
        check(Math.abs(g.turn(0).at - 600) < 15, "Ort 1: " + g.turn(0).at);
        List<String> s = walk(g, c, 4, 1.4);
        String all = String.join(" | ", s);
        System.out.println(all);
        check(all.contains("In 100 Metern rechts abbiegen") || all.contains("In 150 Metern rechts abbiegen"), "Vorankündigung rechts fehlt: " + all);
        check(all.contains("Jetzt rechts abbiegen"), "Jetzt rechts fehlt: " + all);
        check(all.contains("Jetzt links abbiegen"), "Jetzt links fehlt");
        check(all.contains("Du bist auf der Route"), "Start fehlt");
        check(all.contains("Noch ein Kilometer"), "Kilometer fehlt");
        check(all.contains("Du hast das Ziel erreicht"), "Ziel fehlt");
        check(!all.contains("abgekommen"), "fälschlich abgekommen");
        check(s.size() <= 12, "zu viele Ansagen: " + s.size());

        // 2) Gerader Weg mit GPS-Rauschen (±3 m): keine Abbiegung
        Guide gs = route(new double[][]{{0, 0}, {0, 1500}}, 3);
        check(gs.turnCount() == 0, "Rauschen als Abbiegung erkannt: " + gs.turnCount());

        // 3) Weiche Kurve über 80 m (90°) zählt als eine Abbiegung
        double[][] cur = new double[12][];
        cur[0] = new double[]{0, 0}; cur[1] = new double[]{0, 300};
        for (int i = 0; i < 8; i++) { double w = Math.toRadians(90.0 * (i + 1) / 9); cur[i + 2] = new double[]{40 * (1 - Math.cos(w)), 300 + 40 * Math.sin(w)}; }
        cur[10] = new double[]{40, 340}; cur[11] = new double[]{400, 340};
        Guide gc = route(cur, 0);
        check(gc.turnCount() == 1 && gc.turn(0).angle > 45, "Kurve: " + gc.turnCount() + " / " + (gc.turnCount() > 0 ? gc.turn(0).angle : 0));

        // 4) Vom Weg abkommen und zurückkehren
        Guide g4 = route(c, 0);
        List<String> o = new ArrayList<>();
        long t = 0;
        for (double n = 0; n <= 200; n += 5) o.addAll(g4.fix(LAT0 + n * MLAT, LON0, 5f, 1.4, t += 4000));
        for (int i = 0; i < 6; i++) o.addAll(g4.fix(LAT0 + 220 * MLAT, LON0 + 120 * MLON, 5f, 1.4, t += 4000));
        check(String.join("|", o).contains("vom Weg abgekommen"), "Abkommen nicht gemeldet: " + o);
        check(g4.offRoute(), "nicht im Zustand abgekommen");
        List<String> back = g4.fix(LAT0 + 230 * MLAT, LON0 + 3 * MLON, 5f, 1.4, t += 4000);
        check(String.join("|", back).contains("Wieder auf dem Weg"), "Rückkehr nicht gemeldet: " + back);

        // 5) Weit weg vom Start: nur einmal Hinweis, keine Führung
        Guide g5 = route(c, 0);
        List<String> f1 = g5.fix(LAT0 + 0.01, LON0, 5f, 1.4, 1000), f2 = g5.fix(LAT0 + 0.01, LON0, 5f, 1.4, 5000);
        check(f1.size() == 1 && f1.get(0).contains("entfernt") && f2.isEmpty(), "Entfernung am Start: " + f1 + f2);

        // 6) Rundweg: Start und Ziel am selben Punkt – nicht gleich „Ziel erreicht“
        double[][] loop = {{0, 0}, {0, 800}, {800, 800}, {800, 0}, {0, 0}};
        Guide g6 = route(loop, 0);
        List<String> l1 = g6.fix(LAT0 + 3 * MLAT, LON0, 5f, 1.4, 1000);
        check(!String.join("|", l1).contains("Ziel"), "Rundweg: Ziel am Start gemeldet");
        String ls = String.join(" | ", walk(route(loop, 0), loop, 4, 1.4));
        check(ls.contains("Ziel erreicht"), "Rundweg: Ziel fehlt");
        check(Guide.parse("48.0,8.0;48.001,8.0;x;48.002,8.001") != null && Guide.parse("1,2") == null, "parse");
        System.out.println("OK");
    }
}
