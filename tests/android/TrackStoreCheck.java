import de.meinetouren.app.TrackStore;
import java.io.File;
import java.io.FileWriter;

public class TrackStoreCheck {
    static void check(boolean ok, String msg) {
        if (!ok) { System.err.println("FEHLER: " + msg); System.exit(1); }
    }
    public static void main(String[] a) throws Exception {
        File f = File.createTempFile("track", ".csv");
        f.delete();
        TrackStore s = new TrackStore(f);
        long t0 = 1750000000000L;
        // Rundweg: 300 Punkte, alle 5 s, Höhe steigt um 60 m und fällt wieder
        int ok = 0;
        for (int i = 0; i < 300; i++) {
            double ang = 2 * Math.PI * i / 299;
            double alt = 500 + 60 * Math.sin(Math.PI * i / 299);
            if (s.add(t0 + i * 5000L, 48.0 + 0.004 * Math.sin(ang), 8.0 + 0.006 * (1 - Math.cos(ang)), alt, 8f)) ok++;
        }
        check(ok > 290, "zu viele Punkte verworfen: " + ok);
        check(s.distanceM() > 2000 && s.distanceM() < 4500, "Strecke unplausibel: " + s.distanceM());
        check(s.ascentM() > 40 && s.ascentM() < 80, "Aufstieg unplausibel: " + s.ascentM());
        check(s.descentM() > 40 && s.descentM() < 80, "Abstieg unplausibel: " + s.descentM());
        // ungenaue Punkte und Stillstand werden verworfen
        check(!s.add(t0 + 400000L, 48.5, 8.5, 500, 120f), "ungenauer Punkt angenommen");
        double la = s.lastLat(), lo = s.lastLon();
        check(!s.add(t0 + 301 * 5000L, la + 0.0000001, lo, 500, 5f), "Stillstand-Rauschen angenommen");
        // Pause: neues Segment
        s.breakSegment();
        check(s.add(t0 + 2000000L, 48.01, 8.01, 520, 6f), "Punkt nach Pause abgelehnt");
        String gpx = s.gpx("Test & <Tour>", "skitour");
        check(gpx.contains("<type>skitour</type>"), "Sportart fehlt");
        check(gpx.contains("Test &amp; &lt;Tour&gt;"), "Name nicht maskiert");
        int segs = gpx.split("<trkseg>", -1).length - 1;
        check(segs == 2, "Segmente: " + segs);
        // Wiederherstellung aus der Datei
        TrackStore r = new TrackStore(f);
        r.load();
        check(r.count() == s.count(), "Wiederherstellung: " + r.count() + " statt " + s.count());
        check(Math.abs(r.distanceM() - s.distanceM()) < 1.0, "Strecke nach Laden verschieden");
        check(r.gpx("x", "hike").split("<trkseg>", -1).length - 1 == 2, "Segmente nach Laden");
        String js = s.pointsJson(50);
        check(js.startsWith("[[") && js.endsWith("]]"), "pointsJson");
        if (a.length > 0) {
            FileWriter w = new FileWriter(a[0]);
            w.write(gpx);
            w.close();
        }
        System.out.println("OK");
    }
}
