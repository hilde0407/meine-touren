package de.meinetouren.app;

import android.content.ContentValues;
import android.content.Context;
import android.content.SharedPreferences;
import android.media.ExifInterface;
import android.net.Uri;
import android.os.Build;
import android.provider.MediaStore;
import android.webkit.CookieManager;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Date;
import java.util.Locale;
import java.util.UUID;

/** Fotos während der Aufzeichnung: Warteschlange im privaten Ordner, Upload sofort oder gesammelt am Ende. */
final class RecPhotos {
    private static boolean busy = false;
    private static String lastError = "";

    private RecPhotos() { }

    static File dir(Context c) {
        File d = new File(c.getFilesDir(), "recphotos");
        d.mkdirs();
        return d;
    }

    static File[] pending(Context c) {
        final String busyName = prefs(c).getString("pend_file", "");
        File[] a = dir(c).listFiles((d, n) -> n.toLowerCase(Locale.US).endsWith(".jpg") && !n.equals(busyName) && new File(d, n).length() > 0);
        if (a == null) return new File[0];
        Arrays.sort(a);
        return a;
    }

    static File newFile(Context c) {
        String st = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
        return new File(dir(c), "MT_" + st + ".jpg");
    }

    static SharedPreferences prefs(Context c) { return c.getSharedPreferences("app", Context.MODE_PRIVATE); }

    static String mode(Context c) { return prefs(c).getString("photo_mode", "now"); }

    static synchronized String error() { return lastError; }

    static synchronized boolean busy() { return busy; }

    /** Nach der Aufnahme: GPS und Zeit ins Foto schreiben, Kopie in die Galerie, dann (bei Modus „sofort“) hochladen. */
    static void finish(Context c, File f, double lat, double lon, long ts) {
        try {
            ExifInterface ex = new ExifInterface(f.getAbsolutePath());
            if (!Double.isNaN(lat) && !Double.isNaN(lon)) {
                ex.setAttribute(ExifInterface.TAG_GPS_LATITUDE, dms(lat));
                ex.setAttribute(ExifInterface.TAG_GPS_LATITUDE_REF, lat >= 0 ? "N" : "S");
                ex.setAttribute(ExifInterface.TAG_GPS_LONGITUDE, dms(lon));
                ex.setAttribute(ExifInterface.TAG_GPS_LONGITUDE_REF, lon >= 0 ? "E" : "W");
            }
            String dt = new SimpleDateFormat("yyyy:MM:dd HH:mm:ss", Locale.US).format(new Date(ts));
            if (ex.getAttribute(ExifInterface.TAG_DATETIME_ORIGINAL) == null) ex.setAttribute(ExifInterface.TAG_DATETIME_ORIGINAL, dt);
            if (ex.getAttribute(ExifInterface.TAG_DATETIME) == null) ex.setAttribute(ExifInterface.TAG_DATETIME, dt);
            ex.saveAttributes();
        } catch (Exception e) {
            AppLog.log("Foto-EXIF: " + e.getClass().getSimpleName());
        }
        toGallery(c, f);
        AppLog.log("Foto aufgenommen: " + f.getName());
        if ("now".equals(mode(c))) flushAsync(c);
    }

    /** Zeitzone des Telefons als „+01:00“ – der Server braucht sie, um die Kamerazeit richtig einzuordnen. */
    static String utcOffset() {
        int m = java.util.TimeZone.getDefault().getOffset(System.currentTimeMillis()) / 60000;
        return String.format(Locale.US, "%s%02d:%02d", m < 0 ? "-" : "+", Math.abs(m) / 60, Math.abs(m) % 60);
    }

    /** Dezimalgrad als EXIF-Wert „Grad/1,Minuten/1,Sekunden*1000/1000“. */
    static String dms(double v) {
        v = Math.abs(v);
        int d = (int) v;
        double m = (v - d) * 60;
        int mi = (int) m;
        long s = Math.round((m - mi) * 60 * 1000);
        if (s >= 60000) { s -= 60000; mi++; }
        if (mi >= 60) { mi -= 60; d++; }
        return d + "/1," + mi + "/1," + s + "/1000";
    }

    private static void toGallery(Context c, File f) {
        if (Build.VERSION.SDK_INT < 29) return;
        try {
            ContentValues v = new ContentValues();
            v.put(MediaStore.Images.Media.DISPLAY_NAME, f.getName());
            v.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
            v.put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/Meine Touren");
            Uri u = c.getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
            if (u == null) return;
            try (OutputStream o = c.getContentResolver().openOutputStream(u); InputStream in = new FileInputStream(f)) {
                byte[] b = new byte[64 * 1024];
                int n;
                while ((n = in.read(b)) > 0) o.write(b, 0, n);
            }
        } catch (Exception e) {
            AppLog.log("Galerie-Kopie: " + e.getClass().getSimpleName());
        }
    }

    static void flushAsync(final Context c) {
        synchronized (RecPhotos.class) {
            if (busy || pending(c).length == 0) return;
            busy = true;
        }
        new Thread(() -> {
            try { flush(c); } finally { synchronized (RecPhotos.class) { busy = false; } }
        }, "photoup").start();
    }

    /** Wartende Fotos in Paketen von höchstens 6 Stück hochladen; erfolgreiche werden gelöscht (die Galerie-Kopie bleibt). */
    private static void flush(Context c) {
        String server = prefs(c).getString("server", "");
        if (server.isEmpty()) return;
        File[] all = pending(c);
        int i = 0;
        while (i < all.length) {
            File[] batch = Arrays.copyOfRange(all, i, Math.min(all.length, i + 6));
            i += batch.length;
            HttpURLConnection h = null;
            try {
                String boundary = "----mt" + UUID.randomUUID().toString().replace("-", "");
                h = (HttpURLConnection) new URL(server + "/api/rec-photos").openConnection();
                h.setRequestMethod("POST");
                h.setConnectTimeout(15000);
                h.setReadTimeout(120000);
                h.setDoOutput(true);
                h.setChunkedStreamingMode(64 * 1024);
                h.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
                h.setRequestProperty("X-UTC-Offset", utcOffset());
                String ck = CookieManager.getInstance().getCookie(server);
                if (ck != null) h.setRequestProperty("Cookie", ck);
                OutputStream o = h.getOutputStream();
                byte[] buf = new byte[64 * 1024];
                for (File f : batch) {
                    o.write(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"files\"; filename=\"" + f.getName() + "\"\r\nContent-Type: image/jpeg\r\n\r\n").getBytes("UTF-8"));
                    try (InputStream in = new FileInputStream(f)) {
                        int n;
                        while ((n = in.read(buf)) > 0) o.write(buf, 0, n);
                    }
                    o.write("\r\n".getBytes("UTF-8"));
                }
                o.write(("--" + boundary + "--\r\n").getBytes("UTF-8"));
                o.close();
                int code = h.getResponseCode();
                if (code >= 200 && code < 300) {
                    for (File f : batch) f.delete();
                    synchronized (RecPhotos.class) { lastError = ""; }
                } else {
                    synchronized (RecPhotos.class) { lastError = "Server antwortet mit " + code; }
                    AppLog.log("Foto-Upload: HTTP " + code);
                    return;
                }
            } catch (Exception e) {
                synchronized (RecPhotos.class) { lastError = "Keine Verbindung"; }
                AppLog.log("Foto-Upload fehlgeschlagen: " + e.getClass().getSimpleName());
                return;
            } finally {
                if (h != null) h.disconnect();
            }
        }
    }
}
