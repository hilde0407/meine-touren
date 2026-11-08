package de.meinetouren.app;

import android.content.Context;
import android.webkit.CookieManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * Zwischenspeicher für alles, was die App vom Server lädt (Seiten, Daten, Strecken, kleine Fotos, Kartenkacheln).
 * Mit Verbindung wird immer frisch geladen und gespeichert; ohne Verbindung kommt die zuletzt gespeicherte Fassung.
 * Funktioniert auch bei http im Heimnetz, wo der Service Worker des Browsers nicht läuft.
 */
final class OfflineCache {
    private static final long MAX_ENTRY = 12L * 1024 * 1024;
    private static final long MAX_TOTAL = 600L * 1024 * 1024;
    /** Nie speichern: Anmeldung, Jobs, Live-Daten, Downloads, große Originale. */
    private static final Pattern SKIP = Pattern.compile("^/(api/(jobs|update|selftest|health|login|logout|setup|me/password|clock-check|live|backup|export|record)|photo/|sphoto/|download|sw\\.js)");
    private static volatile long servedAt = 0;
    private static long lastTrim = 0;

    private OfflineCache() { }

    /** Wurde in den letzten Sekunden etwas aus dem Speicher statt vom Server geliefert? */
    static boolean offline() { return System.currentTimeMillis() - servedAt < 20000; }

    private static File dir(Context c) {
        File d = new File(c.getFilesDir(), "offline");
        if (!d.exists()) d.mkdirs();
        return d;
    }

    static String key(String url) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-1");
            byte[] h = md.digest(url.getBytes("UTF-8"));
            StringBuilder b = new StringBuilder();
            for (byte x : h) b.append(String.format("%02x", x));
            return b.toString();
        } catch (Exception e) {
            return Integer.toHexString(url.hashCode());
        }
    }

    static boolean wanted(String server, WebResourceRequest r) {
        if (server == null || server.length() == 0) return false;
        String u = r.getUrl().toString();
        if (!u.startsWith(server) || !"GET".equals(r.getMethod())) return false;
        if (r.getRequestHeaders() != null && r.getRequestHeaders().containsKey("Range")) return false;
        String p = r.getUrl().getPath();
        return p != null && !SKIP.matcher(p).find();
    }

    /** Antwort für eine Anfrage: frisch vom Server (und gespeichert) oder bei fehlender Verbindung aus dem Speicher; null = WebView macht es selbst. */
    static WebResourceResponse serve(Context c, WebResourceRequest r) {
        String url = r.getUrl().toString();
        int hash = url.indexOf('#');
        if (hash > 0) url = url.substring(0, hash);
        try {
            HttpURLConnection h = (HttpURLConnection) new URL(url).openConnection();
            h.setInstanceFollowRedirects(false);
            h.setConnectTimeout(4000);
            h.setReadTimeout(20000);
            Map<String, String> hd = r.getRequestHeaders();
            if (hd != null) for (Map.Entry<String, String> e : hd.entrySet()) h.setRequestProperty(e.getKey(), e.getValue());
            String ck = CookieManager.getInstance().getCookie(url);
            if (ck != null) h.setRequestProperty("Cookie", ck);
            h.setRequestProperty("Accept-Encoding", "identity");
            int code = h.getResponseCode();
            if (code >= 300 && code < 400) return null;                    // Weiterleitungen übernimmt das WebView
            Map<String, java.util.List<String>> hf = h.getHeaderFields();
            java.util.List<String> sc = hf == null ? null : hf.get("Set-Cookie");
            if (sc != null) for (String s : sc) CookieManager.getInstance().setCookie(url, s);
            String type = h.getContentType() == null ? "application/octet-stream" : h.getContentType();
            InputStream in = code >= 400 ? h.getErrorStream() : h.getInputStream();
            byte[] body = in == null ? new byte[0] : readAll(in, MAX_ENTRY + 1);
            if (code == 200 && body.length <= MAX_ENTRY) store(c, url, type, body);
            if (code == 401 || code == 403 || code >= 500) { byte[] old = load(c, url); if (old != null && code >= 500) return build(c, url, true); }
            return response(type, code, h.getResponseMessage(), body, false);
        } catch (java.net.UnknownServiceException | java.net.ProtocolException e) {
            return null;
        } catch (Exception e) {                                              // keine Verbindung
            WebResourceResponse cached = build(c, url, true);
            if (cached != null) return cached;
            return null;
        }
    }

    private static WebResourceResponse build(Context c, String url, boolean flag) {
        File f = new File(dir(c), key(url));
        File m = new File(dir(c), key(url) + ".t");
        if (!f.exists() || !m.exists()) return null;
        try {
            byte[] body = readAll(new FileInputStream(f), MAX_ENTRY + 1);
            byte[] t = readAll(new FileInputStream(m), 512);
            f.setLastModified(System.currentTimeMillis());
            if (flag) servedAt = System.currentTimeMillis();
            return response(new String(t, "UTF-8"), 200, "OK", body, true);
        } catch (Exception e) {
            return null;
        }
    }

    private static byte[] load(Context c, String url) {
        File f = new File(dir(c), key(url));
        if (!f.exists()) return null;
        try { return readAll(new FileInputStream(f), MAX_ENTRY + 1); } catch (Exception e) { return null; }
    }

    private static WebResourceResponse response(String type, int code, String msg, byte[] body, boolean cached) {
        String mime = type.split(";")[0].trim();
        String enc = null;
        int i = type.toLowerCase().indexOf("charset=");
        if (i >= 0) enc = type.substring(i + 8).trim();
        if (enc == null && (mime.startsWith("text/") || mime.contains("json") || mime.contains("javascript"))) enc = "UTF-8";
        Map<String, String> hd = new HashMap<>();
        hd.put("Access-Control-Allow-Origin", "*");
        if (cached) hd.put("X-MT-Offline", "1");
        WebResourceResponse w = new WebResourceResponse(mime, enc, new ByteArrayInputStream(body));
        try {
            w.setStatusCodeAndReasonPhrase(code, msg == null || msg.length() == 0 ? "OK" : msg);
            w.setResponseHeaders(hd);
        } catch (Exception e) { /* ungültiger Statuscode – Standard */ }
        return w;
    }

    private static void store(Context c, String url, String type, byte[] body) {
        try {
            File f = new File(dir(c), key(url));
            File tmp = new File(dir(c), key(url) + ".tmp");
            try (FileOutputStream o = new FileOutputStream(tmp)) { o.write(body); }
            if (!tmp.renameTo(f)) { f.delete(); tmp.renameTo(f); }
            try (FileOutputStream o = new FileOutputStream(new File(dir(c), key(url) + ".t"))) { o.write(type.getBytes("UTF-8")); }
            long now = System.currentTimeMillis();
            if (now - lastTrim > 60000) { lastTrim = now; trim(c); }
        } catch (Exception e) {
            AppLog.log("Offline-Speicher: " + e.getClass().getSimpleName());
        }
    }

    /** Älteste Einträge löschen, wenn der Speicher größer als MAX_TOTAL wird. */
    static void trim(Context c) {
        File[] fs = dir(c).listFiles((d, n) -> !n.endsWith(".t") && !n.endsWith(".tmp"));
        if (fs == null) return;
        long sum = 0;
        for (File f : fs) sum += f.length();
        if (sum <= MAX_TOTAL) return;
        Arrays.sort(fs, (a, b) -> Long.compare(a.lastModified(), b.lastModified()));
        for (File f : fs) {
            if (sum <= MAX_TOTAL * 0.8) break;
            sum -= f.length();
            f.delete();
            new File(f.getPath() + ".t").delete();
        }
    }

    /** Alles löschen (beim Abmelden / auf Wunsch). */
    static void clear(Context c) {
        File[] fs = dir(c).listFiles();
        if (fs != null) for (File f : fs) f.delete();
    }

    static String stats(Context c) {
        File[] fs = dir(c).listFiles((d, n) -> !n.endsWith(".t") && !n.endsWith(".tmp"));
        long sum = 0;
        int n = 0;
        if (fs != null) for (File f : fs) { sum += f.length(); n++; }
        return "{\"files\":" + n + ",\"bytes\":" + sum + "}";
    }

    private static byte[] readAll(InputStream in, long max) throws java.io.IOException {
        try (InputStream i = in) {
            ByteArrayOutputStream b = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = i.read(buf)) > 0) {
                b.write(buf, 0, n);
                if (b.size() > max) break;
            }
            return b.toByteArray();
        }
    }
}
