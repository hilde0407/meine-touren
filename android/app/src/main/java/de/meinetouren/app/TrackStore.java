package de.meinetouren.app;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

/**
 * Speichert die Punkte einer Aufzeichnung (jede Zeile sofort in eine Datei, damit nach einem Absturz nichts verloren geht),
 * berechnet Strecke und Aufstieg und erzeugt die GPX-Datei. Reines Java ohne Android-Klassen (deshalb am Rechner testbar).
 */
public class TrackStore {
    public static final class Pt {
        public final long t;          // Unix-Zeit in Millisekunden
        public final double lat, lon, alt;   // alt = NaN, wenn unbekannt
        public final boolean newSeg;  // erster Punkt nach einer Pause
        Pt(long t, double lat, double lon, double alt, boolean newSeg) {
            this.t = t; this.lat = lat; this.lon = lon; this.alt = alt; this.newSeg = newSeg;
        }
    }

    private final File file;
    private final List<Pt> pts = new ArrayList<Pt>();
    /** Wegpunkte mit Notiz: {Zeit, lat, lon, Text}. */
    private final List<Object[]> wps = new ArrayList<Object[]>();
    private boolean nextNewSeg = true;
    private double dist = 0, up = 0, down = 0;
    private double refAlt = Double.NaN;
    private double a1 = Double.NaN, a2 = Double.NaN;   // gleitender Mittelwert über 3 Höhenwerte
    private long activeMs = 0;                          // reine Bewegungszeit ohne Pausen

    public TrackStore(File file) {
        this.file = file;
    }

    public static double haversine(double la1, double lo1, double la2, double lo2) {
        double r = 6371000.0;
        double dLa = Math.toRadians(la2 - la1), dLo = Math.toRadians(lo2 - lo1);
        double a = Math.sin(dLa / 2) * Math.sin(dLa / 2)
                + Math.cos(Math.toRadians(la1)) * Math.cos(Math.toRadians(la2)) * Math.sin(dLo / 2) * Math.sin(dLo / 2);
        return 2 * r * Math.asin(Math.min(1.0, Math.sqrt(a)));
    }

    /** Punkt hinzufügen. Gibt false zurück, wenn er verworfen wurde (zu ungenau oder Stillstand-Rauschen). */
    public synchronized boolean add(long t, double lat, double lon, double alt, float acc) {
        if (acc > 50f && acc > 0f) return false;
        Pt last = pts.isEmpty() ? null : pts.get(pts.size() - 1);
        boolean seg = nextNewSeg;
        if (last != null && !seg) {
            double d = haversine(last.lat, last.lon, lat, lon);
            if (d < 2.0 && t - last.t < 15000) return false;     // Stillstand: nur Rauschen
            if (t <= last.t) return false;
            if (d > 2000 && (t - last.t) < 5000) return false;    // Sprung (GPS-Fehler)
            dist += d;
            activeMs += Math.min(t - last.t, 60000);
            addAlt(alt);
        } else {
            refAlt = Double.NaN; a1 = Double.NaN; a2 = Double.NaN;
            addAlt(alt);
        }
        Pt p = new Pt(t, lat, lon, alt, seg || last == null);
        pts.add(p);
        nextNewSeg = false;
        append(p);
        return true;
    }

    private void addAlt(double alt) {
        if (Double.isNaN(alt)) return;
        double s;
        if (Double.isNaN(a1)) { a1 = alt; a2 = alt; s = alt; }
        else { s = (a2 + a1 + alt) / 3.0; a2 = a1; a1 = alt; }
        if (Double.isNaN(refAlt)) { refAlt = s; return; }
        double diff = s - refAlt;
        if (Math.abs(diff) >= 3.0) {          // Hysterese gegen Höhenrauschen
            if (diff > 0) up += diff; else down += -diff;
            refAlt = s;
        }
    }

    public synchronized void breakSegment() {
        nextNewSeg = true;
    }

    public synchronized int count() { return pts.size(); }
    public synchronized double distanceM() { return dist; }
    public synchronized double ascentM() { return up; }
    public synchronized double descentM() { return down; }
    public synchronized long activeMs() { return activeMs; }
    public synchronized long firstTime() { return pts.isEmpty() ? 0 : pts.get(0).t; }
    public synchronized long lastTime() { return pts.isEmpty() ? 0 : pts.get(pts.size() - 1).t; }
    public synchronized double lastAlt() {
        for (int i = pts.size() - 1; i >= 0; i--) if (!Double.isNaN(pts.get(i).alt)) return pts.get(i).alt;
        return Double.NaN;
    }
    public synchronized double maxAlt() {
        double m = Double.NaN;
        for (Pt p : pts) if (!Double.isNaN(p.alt) && (Double.isNaN(m) || p.alt > m)) m = p.alt;
        return m;
    }
    /** Geschwindigkeit der letzten ca. 30 Sekunden in m/s (0 bei Stillstand oder zu wenig Punkten). */
    public synchronized double recentSpeedMs() {
        int n = pts.size();
        if (n < 2) return 0;
        long tEnd = pts.get(n - 1).t, tStart = tEnd;
        double d = 0;
        for (int i = n - 1; i > 0; i--) {
            Pt p = pts.get(i), q = pts.get(i - 1);
            if (p.newSeg) break;
            d += haversine(q.lat, q.lon, p.lat, p.lon);
            tStart = q.t;
            if (tEnd - tStart >= 30000) break;
        }
        return tEnd - tStart >= 8000 ? d / ((tEnd - tStart) / 1000.0) : 0;
    }
    public synchronized double lastLat() { return pts.isEmpty() ? Double.NaN : pts.get(pts.size() - 1).lat; }
    public synchronized double lastLon() { return pts.isEmpty() ? Double.NaN : pts.get(pts.size() - 1).lon; }

    private File wptFile() { return file == null ? null : new File(file.getPath() + ".wpt"); }

    /** Wegpunkt mit Notiz an einer Position festhalten (wird sofort gesichert). */
    public synchronized void addWaypoint(long t, double lat, double lon, String note) {
        String n = note == null ? "" : note.replace("\t", " ").replace("\r", " ").replace("\n", " ").trim();
        if (n.length() > 200) n = n.substring(0, 200);
        wps.add(new Object[]{t, lat, lon, n});
        File f = wptFile();
        if (f == null) return;
        try {
            FileWriter w = new FileWriter(f, true);
            try { w.write(String.format(Locale.US, "%d\t%.6f\t%.6f\t%s\n", t, lat, lon, n)); } finally { w.close(); }
        } catch (IOException e) { /* Zusatz */ }
    }

    public synchronized int waypointCount() { return wps.size(); }

    public synchronized String waypointsJson() {
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < wps.size(); i++) {
            Object[] w = wps.get(i);
            if (i > 0) b.append(',');
            b.append(String.format(Locale.US, "{\"t\":%d,\"lat\":%.6f,\"lon\":%.6f,\"note\":\"%s\"}", (Long) w[0], (Double) w[1], (Double) w[2],
                    ((String) w[3]).replace("\\", "\\\\").replace("\"", "\\\"")));
        }
        return b.append(']').toString();
    }

    private void loadWaypoints() {
        wps.clear();
        File f = wptFile();
        if (f == null || !f.exists()) return;
        try {
            BufferedReader r = new BufferedReader(new FileReader(f));
            try {
                String line;
                while ((line = r.readLine()) != null) {
                    String[] c = line.split("\t", 4);
                    if (c.length < 3) continue;
                    try { wps.add(new Object[]{Long.parseLong(c[0]), Double.parseDouble(c[1]), Double.parseDouble(c[2]), c.length > 3 ? c[3] : ""}); }
                    catch (NumberFormatException e) { /* Zeile überspringen */ }
                }
            } finally { r.close(); }
        } catch (IOException e) { /* ohne Wegpunkte weiter */ }
    }

    public synchronized void clear() {
        wps.clear();
        File wf = wptFile();
        if (wf != null && wf.exists()) wf.delete();
        pts.clear();
        nextNewSeg = true;
        dist = up = down = 0;
        activeMs = 0;
        refAlt = Double.NaN; a1 = Double.NaN; a2 = Double.NaN;
        if (file != null && file.exists()) file.delete();
    }

    private void append(Pt p) {
        if (file == null) return;
        try {
            FileWriter w = new FileWriter(file, true);
            try {
                w.write(String.format(Locale.US, "%d,%.6f,%.6f,%s,%d\n", p.t, p.lat, p.lon,
                        Double.isNaN(p.alt) ? "" : String.format(Locale.US, "%.1f", p.alt), p.newSeg ? 1 : 0));
            } finally {
                w.close();
            }
        } catch (IOException e) {
            // Speichern ist Zusatz – die Aufzeichnung im Speicher läuft weiter
        }
    }

    /** Punkte aus der Datei wiederherstellen (nach Absturz oder Neustart der App). Nach dem Laden beginnt ein neues Segment. */
    public synchronized void load() {
        pts.clear();
        dist = up = down = 0;
        activeMs = 0;
        refAlt = Double.NaN; a1 = Double.NaN; a2 = Double.NaN;
        loadWaypoints();
        if (file == null || !file.exists()) return;
        File keep = file;
        List<String[]> rows = new ArrayList<String[]>();
        try {
            BufferedReader r = new BufferedReader(new FileReader(keep));
            try {
                String line;
                while ((line = r.readLine()) != null) {
                    String[] f = line.split(",", -1);
                    if (f.length >= 5) rows.add(f);
                }
            } finally {
                r.close();
            }
        } catch (IOException e) {
            return;
        }
        // Datei neu schreiben, indem add() die Punkte erneut verarbeitet (stellt Strecke und Aufstieg wieder her)
        keep.delete();
        for (String[] f : rows) {
            try {
                if ("1".equals(f[4])) nextNewSeg = true;
                double alt = f[3].length() == 0 ? Double.NaN : Double.parseDouble(f[3]);
                add(Long.parseLong(f[0]), Double.parseDouble(f[1]), Double.parseDouble(f[2]), alt, 0f);
            } catch (NumberFormatException e) {
                // beschädigte Zeile überspringen
            }
        }
        nextNewSeg = true;
    }

    private static String iso(long ms) {
        SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
        f.setTimeZone(TimeZone.getTimeZone("UTC"));
        return f.format(new Date(ms));
    }

    private static String esc(String s) {
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }

    /** GPX 1.1; sport = Sportart-Kennung von Meine Touren (z. B. hike, skitour, touringbicycle). */
    public synchronized String gpx(String name, String sport) {
        StringBuilder b = new StringBuilder(pts.size() * 90 + 400);
        long start = pts.isEmpty() ? System.currentTimeMillis() : pts.get(0).t;
        b.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
        b.append("<gpx version=\"1.1\" creator=\"Meine Touren (Android)\" xmlns=\"http://www.topografix.com/GPX/1/1\">\n");
        b.append("<metadata><name>").append(esc(name)).append("</name><time>").append(iso(start)).append("</time></metadata>\n");
        for (Object[] w : wps) {
            String n = (String) w[3];
            b.append(String.format(Locale.US, "<wpt lat=\"%.6f\" lon=\"%.6f\"><time>", (Double) w[1], (Double) w[2])).append(iso((Long) w[0])).append("</time>")
                    .append("<name>").append(esc(n.length() > 0 ? n : "Wegpunkt")).append("</name></wpt>\n");
        }
        b.append("<trk><name>").append(esc(name)).append("</name><type>").append(esc(sport)).append("</type>");
        boolean open = false;
        for (Pt p : pts) {
            if (p.newSeg && open) { b.append("</trkseg>"); open = false; }
            if (!open) { b.append("<trkseg>\n"); open = true; }
            b.append(String.format(Locale.US, "<trkpt lat=\"%.6f\" lon=\"%.6f\">", p.lat, p.lon));
            if (!Double.isNaN(p.alt)) b.append(String.format(Locale.US, "<ele>%.1f</ele>", p.alt));
            b.append("<time>").append(iso(p.t)).append("</time></trkpt>\n");
        }
        if (open) b.append("</trkseg>");
        b.append("</trk></gpx>\n");
        return b.toString();
    }

    /** Punkte für die Live-Karte als JSON [[lat,lon],…], höchstens max Stück. */
    public synchronized String pointsJson(int max) {
        StringBuilder b = new StringBuilder("[");
        int n = pts.size();
        int step = Math.max(1, n / Math.max(1, max));
        boolean first = true;
        for (int i = 0; i < n; i += step) {
            Pt p = pts.get(i);
            if (!first) b.append(',');
            first = false;
            b.append(String.format(Locale.US, "[%.6f,%.6f]", p.lat, p.lon));
        }
        if (n > 0 && (n - 1) % step != 0) {
            Pt p = pts.get(n - 1);
            if (!first) b.append(',');
            b.append(String.format(Locale.US, "[%.6f,%.6f]", p.lat, p.lon));
        }
        return b.append(']').toString();
    }
}
