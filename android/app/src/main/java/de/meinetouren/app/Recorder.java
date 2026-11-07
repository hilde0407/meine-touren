package de.meinetouren.app;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.location.Location;
import android.location.LocationManager;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Writer;

/** Zustand einer Aufzeichnung (läuft in der ganzen App-Prozess-Lebenszeit, Zustand zusätzlich in Datei/Einstellungen gesichert). */
public final class Recorder {
    public static final String IDLE = "idle", RECORDING = "recording", PAUSED = "paused", FINISHED = "finished";
    private static Recorder inst;

    public static synchronized Recorder get(Context c) {
        if (inst == null) inst = new Recorder(c.getApplicationContext());
        return inst;
    }

    public volatile long lastFixMs = 0;
    public volatile float lastAcc = -1;
    private int fixes = 0;
    private final Context ctx;
    private final SharedPreferences prefs;
    private final TrackStore store;
    private final File finalFile;

    private Recorder(Context c) {
        ctx = c;
        AppLog.init(c);
        prefs = c.getSharedPreferences("rec", Context.MODE_PRIVATE);
        File dir = c.getFilesDir();
        store = new TrackStore(new File(dir, "rec_current.csv"));
        finalFile = new File(dir, "rec_finished.gpx");
        String s = state();
        if (RECORDING.equals(s) || PAUSED.equals(s)) store.load();
    }

    public TrackStore store() { return store; }
    public synchronized String state() { return prefs.getString("state", IDLE); }
    public synchronized String sport() { return prefs.getString("sport", "hike"); }
    public synchronized String name() { return prefs.getString("name", ""); }

    private void setState(String s) { prefs.edit().putString("state", s).apply(); }

    /** Abstand/Zeit der GPS-Abfrage je nach Sportart: Rad schneller, zu Fuß sparsamer. */
    public long minTimeMs() {
        String s = sport();
        if (s.contains("bicycle") || s.equals("racebike") || s.equals("mtb") || s.equals("jogging")) return 3000;
        return 5000;
    }
    public float minDistM() {
        String s = sport();
        if (s.contains("bicycle") || s.equals("racebike") || s.equals("mtb")) return 8f;
        return 4f;
    }

    private void service(String action) {
        Intent i = new Intent(ctx, RecorderService.class).setAction(action);
        if (RecorderService.ACT_STOP.equals(action) || RecorderService.ACT_PAUSE.equals(action)) ctx.startService(i);
        else ctx.startForegroundService(i);
    }

    public synchronized void start(String sport, String name) {
        store.clear();
        finalFile.delete();
        prefs.edit().putString("state", RECORDING).putString("sport", sport == null || sport.isEmpty() ? "hike" : sport)
                .putString("name", name == null ? "" : name).putLong("start", System.currentTimeMillis()).apply();
        AppLog.log("Start: " + sport + " \"" + name + "\"");
        service(RecorderService.ACT_START);
    }

    public synchronized void pause() {
        if (!RECORDING.equals(state())) return;
        setState(PAUSED);
        store.breakSegment();
        AppLog.log("Pause bei " + store.count() + " Punkten");
        service(RecorderService.ACT_PAUSE);
    }

    public synchronized void resume() {
        if (!PAUSED.equals(state())) return;
        setState(RECORDING);
        store.breakSegment();
        AppLog.log("Weiter");
        service(RecorderService.ACT_RESUME);
    }

    /** Wird vom Dienst nach einem Neustart durch das System aufgerufen: die Lücke bekommt ein neues Segment. */
    public synchronized void resumeAfterKill() {
        AppLog.log("Dienst vom System neu gestartet - neues Segment");
        store.breakSegment();
    }

    public synchronized void stop(String name) {
        String s = state();
        if (!RECORDING.equals(s) && !PAUSED.equals(s)) return;
        if (name != null && name.trim().length() > 0) prefs.edit().putString("name", name.trim()).apply();
        AppLog.log("Ende: " + store.count() + " Punkte, " + Math.round(store.distanceM()) + " m");
        service(RecorderService.ACT_STOP);
        String gpx = store.gpx(name(), sport());
        try {
            Writer w = new OutputStreamWriter(new FileOutputStream(finalFile), "UTF-8");
            try { w.write(gpx); } finally { w.close(); }
            setState(store.count() > 1 ? FINISHED : IDLE);
        } catch (IOException e) {
            setState(IDLE);
        }
        new File(ctx.getFilesDir(), "rec_current.csv").delete();
    }

    /** Aufzeichnung verwerfen bzw. nach erfolgreichem Hochladen aufräumen. */
    public synchronized void discard() {
        AppLog.log("Aufzeichnung verworfen/abgeschlossen");
        backupFinished();
        if (RECORDING.equals(state()) || PAUSED.equals(state())) service(RecorderService.ACT_STOP);
        store.clear();
        finalFile.delete();
        setState(IDLE);
    }

    /** Fertige Aufzeichnung vor dem Löschen als Sicherung ablegen (die letzten 10 bleiben), damit nichts verloren geht. */
    private void backupFinished() {
        try {
            if (!finalFile.exists() || finalFile.length() < 200) return;
            File dir = new File(ctx.getFilesDir(), "backup");
            dir.mkdirs();
            String stamp = new java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.US).format(new java.util.Date());
            File to = new File(dir, "rec_" + stamp + ".gpx");
            java.io.InputStream in = new FileInputStream(finalFile);
            java.io.OutputStream out = new FileOutputStream(to);
            try {
                byte[] b = new byte[8192];
                int n;
                while ((n = in.read(b)) > 0) out.write(b, 0, n);
            } finally { in.close(); out.close(); }
            File[] all = dir.listFiles();
            if (all != null && all.length > 10) {
                java.util.Arrays.sort(all);
                for (int i = 0; i < all.length - 10; i++) all[i].delete();
            }
            AppLog.log("Sicherung angelegt: " + to.getName());
        } catch (Exception e) {
            AppLog.log("Sicherung fehlgeschlagen: " + e.getClass().getSimpleName());
        }
    }

    /** Liste der Sicherungen als JSON: [{"file","size","ts"}], neueste zuerst. */
    public String backupsJson() {
        org.json.JSONArray a = new org.json.JSONArray();
        File[] all = new File(ctx.getFilesDir(), "backup").listFiles();
        if (all != null) {
            java.util.Arrays.sort(all, java.util.Collections.reverseOrder());
            for (File f : all) {
                try { a.put(new JSONObject().put("file", f.getName()).put("size", f.length()).put("ts", f.lastModified())); } catch (JSONException e) { }
            }
        }
        return a.toString();
    }

    public String backupGpx(String name) {
        if (name == null || name.contains("/") || name.contains("..")) return "";
        try {
            BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(new File(new File(ctx.getFilesDir(), "backup"), name)), "UTF-8"));
            StringBuilder b = new StringBuilder();
            char[] buf = new char[8192];
            int n;
            try { while ((n = r.read(buf)) > 0) b.append(buf, 0, n); } finally { r.close(); }
            return b.toString();
        } catch (IOException e) {
            return "";
        }
    }

    public synchronized String finishedGpx() {
        if (!finalFile.exists()) return "";
        try {
            BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(finalFile), "UTF-8"));
            StringBuilder b = new StringBuilder();
            char[] buf = new char[8192];
            int n;
            try { while ((n = r.read(buf)) > 0) b.append(buf, 0, n); } finally { r.close(); }
            return b.toString();
        } catch (IOException e) {
            return "";
        }
    }

    public void onLocation(Location l) {
        if (!RECORDING.equals(state())) return;
        lastFixMs = System.currentTimeMillis();
        lastAcc = l.hasAccuracy() ? l.getAccuracy() : -1;
        if (++fixes % 25 == 1) AppLog.log("Fix #" + fixes + " Genauigkeit " + Math.round(lastAcc) + " m, Punkte " + store.count());
        store.add(l.getTime() > 0 ? l.getTime() : System.currentTimeMillis(), l.getLatitude(), l.getLongitude(),
                l.hasAltitude() ? l.getAltitude() : Double.NaN, l.hasAccuracy() ? l.getAccuracy() : 0f);
    }

    public String statusJson() {
        JSONObject o = new JSONObject();
        try {
            String s = state();
            o.put("state", s);
            o.put("sport", sport());
            o.put("name", name());
            o.put("start", prefs.getLong("start", 0));
            o.put("count", store.count());
            o.put("dist_m", Math.round(store.distanceM()));
            o.put("up_m", Math.round(store.ascentM()));
            o.put("down_m", Math.round(store.descentM()));
            long act = store.activeMs();
            long last = store.lastTime();
            if (RECORDING.equals(s) && last > 0 && System.currentTimeMillis() - last < 60000) act += System.currentTimeMillis() - last;
            o.put("active_s", act / 1000);
            if (store.count() > 0) {
                o.put("lat", store.lastLat());
                o.put("lon", store.lastLon());
            }
            LocationManager lm = (LocationManager) ctx.getSystemService(Context.LOCATION_SERVICE);
            o.put("gps", lm != null && lm.isProviderEnabled(LocationManager.GPS_PROVIDER));
            o.put("unsent", finalFile.exists());
            o.put("fix_age_s", lastFixMs > 0 ? (System.currentTimeMillis() - lastFixMs) / 1000 : -1);
            o.put("fix_acc_m", Math.round(lastAcc));
        } catch (JSONException e) {
            // nicht erreichbar: nur Zahlen und Texte
        }
        return o.toString();
    }
}
