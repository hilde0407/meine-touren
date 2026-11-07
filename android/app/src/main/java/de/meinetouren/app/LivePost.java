package de.meinetouren.app;

import android.content.Context;
import android.location.Location;
import android.webkit.CookieManager;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

/** Meldet die aktuelle Position während der Aufzeichnung an den Server (nur wenn dort „Standort teilen“ eingeschaltet ist). */
final class LivePost {
    private static long last = 0;
    private static boolean busy = false;
    private static long lastLog = 0;

    private LivePost() { }

    static synchronized void send(Context ctx, Location l) {
        long now = System.currentTimeMillis();
        if (busy || now - last < 30000) return;
        final String server = ctx.getSharedPreferences("app", Context.MODE_PRIVATE).getString("server", "");
        if (server.isEmpty() || !server.startsWith("https://")) return;
        last = now;
        if ("now".equals(RecPhotos.mode(ctx))) RecPhotos.flushAsync(ctx);   // wartende Fotos erneut versuchen
        busy = true;
        final String body = String.format(Locale.US, "{\"lat\":%.6f,\"lon\":%.6f,\"acc\":%d,\"source\":\"rec\"}",
                l.getLatitude(), l.getLongitude(), Math.round(l.getAccuracy()));
        new Thread(() -> {
            HttpURLConnection c = null;
            try {
                c = (HttpURLConnection) new URL(server + "/api/live").openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(8000);
                c.setReadTimeout(8000);
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                String ck = CookieManager.getInstance().getCookie(server);
                if (ck != null) c.setRequestProperty("Cookie", ck);
                try (OutputStream o = c.getOutputStream()) { o.write(body.getBytes("UTF-8")); }
                int code = c.getResponseCode();
                if (code != 200 && code != 403) AppLog.log("Live-Standort: HTTP " + code);
            } catch (Exception e) {
                if (System.currentTimeMillis() - lastLog > 60000) { lastLog = System.currentTimeMillis(); AppLog.log("Live-Standort nicht gesendet: " + e.getClass().getSimpleName()); }
            } finally {
                if (c != null) c.disconnect();
                busy = false;
            }
        }, "livepost").start();
    }
}
