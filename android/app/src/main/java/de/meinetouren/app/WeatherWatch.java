package de.meinetouren.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.location.Location;
import android.webkit.CookieManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/** Wetterwarnung unterwegs: fragt während der Aufzeichnung alle 15 Minuten beim Server die Vorhersage für den Standort ab und warnt (Benachrichtigung + Sprachansage). */
final class WeatherWatch {
    private static final long EVERY_MS = 15 * 60 * 1000L, REPEAT_MS = 60 * 60 * 1000L;
    private static final String CHANNEL = "mt_weather";
    private static long last = 0;
    private static boolean busy = false;
    private static final Map<String, Long> said = new HashMap<>();
    private static volatile String lastJson = "{}";

    private WeatherWatch() { }

    private static android.content.SharedPreferences prefs(Context c) { return c.getSharedPreferences("app", Context.MODE_PRIVATE); }
    static boolean enabled(Context c) { return prefs(c).getBoolean("weather_on", true); }
    static void setEnabled(Context c, boolean on) { prefs(c).edit().putBoolean("weather_on", on).apply(); }
    static String info() { return lastJson; }

    /** Bei jeder neuen Position aufgerufen; macht höchstens alle 15 Minuten eine Anfrage. */
    static void check(final Context ctx, Location l) {
        final long now = System.currentTimeMillis();
        synchronized (WeatherWatch.class) {
            if (busy || now - last < EVERY_MS || !enabled(ctx)) return;
            busy = true;
            last = now;
        }
        final String server = prefs(ctx).getString("server", "");
        if (server.isEmpty()) { busy = false; return; }
        final String url = server + String.format(Locale.US, "/api/weather/alert?lat=%.4f&lon=%.4f", l.getLatitude(), l.getLongitude());
        new Thread(() -> {
            HttpURLConnection c = null;
            try {
                c = (HttpURLConnection) new URL(url).openConnection();
                c.setConnectTimeout(8000);
                c.setReadTimeout(15000);
                String ck = CookieManager.getInstance().getCookie(server);
                if (ck != null) c.setRequestProperty("Cookie", ck);
                if (c.getResponseCode() != 200) { AppLog.log("Wetterwarnung: HTTP " + c.getResponseCode()); return; }
                ByteArrayOutputStream b = new ByteArrayOutputStream();
                try (InputStream in = c.getInputStream()) {
                    byte[] buf = new byte[4096];
                    int n;
                    while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
                }
                JSONObject o = new JSONObject(b.toString("UTF-8"));
                lastJson = o.toString();
                JSONArray ev = o.optJSONArray("events");
                if (ev == null) return;
                for (int i = 0; i < ev.length(); i++) {
                    JSONObject e = ev.getJSONObject(i);
                    String kind = e.optString("kind");
                    Long t = said.get(kind);
                    if (t != null && now - t < REPEAT_MS) continue;
                    said.put(kind, now);
                    String text = GuideText.weather(kind, e.optInt("in_h"), e.optInt("val"));
                    AppLog.log("Wetterwarnung: " + kind + " in " + e.optInt("in_h") + " h");
                    notify(ctx, kind, text, "danger".equals(o.optString("level")));
                    Navi.speak(ctx, text);
                }
            } catch (Exception e) {
                AppLog.log("Wetterwarnung nicht abgerufen: " + e.getClass().getSimpleName());
            } finally {
                if (c != null) c.disconnect();
                synchronized (WeatherWatch.class) { busy = false; }
            }
        }, "weather").start();
    }

    private static void notify(Context ctx, String kind, String text, boolean danger) {
        try {
            NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;
            Context lc = Navi.lc(ctx);
            nm.createNotificationChannel(new NotificationChannel(CHANNEL, GuideText.weatherTitle(), NotificationManager.IMPORTANCE_HIGH));
            Notification n = new Notification.Builder(ctx, CHANNEL).setSmallIcon(R.drawable.ic_stat_rec).setContentTitle((danger ? "⚠ " : "") + GuideText.weatherTitle())
                    .setContentText(text).setStyle(new Notification.BigTextStyle().bigText(text)).setAutoCancel(true).build();
            nm.notify(7100 + Math.abs(kind.hashCode() % 50), n);
        } catch (Exception e) {
            AppLog.log("Wetter-Benachrichtigung: " + e.getClass().getSimpleName());
        }
    }
}
