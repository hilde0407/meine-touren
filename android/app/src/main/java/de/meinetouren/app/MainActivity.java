package de.meinetouren.app;

import android.Manifest;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.UUID;

/** Hülle um die Meine-Touren-Weboberfläche: WebView, GPS-Aufzeichnung, Teilen-Ziel, PDF-Downloads. */
public class MainActivity extends Activity {
    private static final int REQ_PERM = 11, REQ_FILE = 12, REQ_PHOTO = 13;
    private WebView web;
    private SharedPreferences prefs;
    private ValueCallback<Uri[]> fileCb;
    private GeolocationPermissions.Callback geoCb;
    private String geoOrigin;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        prefs = getSharedPreferences("app", MODE_PRIVATE);
        AppLog.init(this);
        Navi.initLang(this);
        AppLog.log("App gestartet, Server: " + prefs.getString("server", "-"));
        web = new WebView(this);
        setContentView(web, new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setGeolocationEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUserAgentString(s.getUserAgentString() + " MeineTourenApp/2.2");
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        web.addJavascriptInterface(new Bridge(), "MTApp");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest r) {
                try {
                    if (OfflineCache.wanted(server(), r)) return OfflineCache.serve(MainActivity.this, r);
                } catch (Throwable t) { AppLog.log("Offline-Speicher: " + t.getClass().getSimpleName()); }
                return null;
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                String u = r.getUrl().toString();
                String base = server();
                if (base.length() > 0 && u.startsWith(base)) return false;
                if (u.startsWith("file:///android_asset/")) return false;
                if (sameHost(u, base)) {                       // z. B. Weiterleitung http -> https: in der App bleiben
                    if (r.isForMainFrame() && u.startsWith("https://") && base.startsWith("http://")) {
                        prefs.edit().putString("server", u.replaceAll("^(https://[^/]+).*$", "$1")).apply();
                        AppLog.log("Server auf HTTPS umgestellt: " + server());
                    }
                    return false;
                }
                try { startActivity(new Intent(Intent.ACTION_VIEW, r.getUrl())); } catch (Exception e) { /* keine App */ }
                return true;
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) AppLog.log("Ladefehler: " + e.getDescription());
                if (r.isForMainFrame()) v.loadUrl("file:///android_asset/error.html?u=" + Uri.encode(server()));
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback cb) {
                if (hasLoc()) { cb.invoke(origin, true, false); return; }
                geoCb = cb;
                geoOrigin = origin;
                requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_PERM);
            }

            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (fileCb != null) fileCb.onReceiveValue(null);
                fileCb = cb;
                try {
                    startActivityForResult(p.createIntent(), REQ_FILE);
                } catch (Exception e) {
                    fileCb = null;
                    return false;
                }
                return true;
            }
        });
        web.setDownloadListener((url, ua, cd, mime, len) -> {
            try {
                DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
                r.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url));
                r.addRequestHeader("User-Agent", ua);
                String fn = URLUtil.guessFileName(url, cd, mime);
                r.setTitle(fn);
                r.setMimeType(mime);
                r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fn);
                ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(r);
                Toast.makeText(this, getString(R.string.download, fn), Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                Toast.makeText(this, getString(R.string.download_failed), Toast.LENGTH_LONG).show();
            }
        });
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_PERM + 1);
        if (b != null) web.restoreState(b);
        else start(getIntent());
    }

    private static String hostOf(String u) {
        try { return u == null ? "" : Uri.parse(u).getHost() == null ? "" : Uri.parse(u).getHost().toLowerCase(); }
        catch (Exception e) { return ""; }
    }

    private static boolean sameHost(String a, String b) {
        String x = hostOf(a);
        return x.length() > 0 && x.equals(hostOf(b));
    }

    /** Ohne Schema: Adressen im Heimnetz (IP, .local, localhost) mit http, alles andere (z. B. Tailscale/Funnel) mit https. */
    static String normalizeServer(String u) {
        u = u == null ? "" : u.trim();
        while (u.endsWith("/")) u = u.substring(0, u.length() - 1);
        if (u.length() == 0 || u.startsWith("http://") || u.startsWith("https://")) return u;
        String h = u.split("[/:]")[0];
        boolean local = h.matches("\\d{1,3}(\\.\\d{1,3}){3}") || h.endsWith(".local") || h.equals("localhost") || !h.contains(".");
        return (local ? "http://" : "https://") + u;
    }

    private String server() {
        return prefs.getString("server", "");
    }

    private boolean hasLoc() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private void start(Intent in) {
        String act = in == null ? null : in.getAction();
        if (server().length() == 0) {
            web.loadUrl("file:///android_asset/setup.html");
            return;
        }
        if (Intent.ACTION_SEND.equals(act) || Intent.ACTION_SEND_MULTIPLE.equals(act)) {
            share(in);
            return;
        }
        String cur = web.getUrl();
        if (cur == null || !cur.startsWith(server())) web.loadUrl(server() + "/");
    }

    @Override
    protected void onNewIntent(Intent in) {
        super.onNewIntent(in);
        setIntent(in);
        start(in);
    }

    @Override
    protected void onSaveInstanceState(Bundle o) {
        super.onSaveInstanceState(o);
        web.saveState(o);
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
        web.evaluateJavascript("window.dispatchEvent(new Event('mtresume'))", null);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        if (req == REQ_PHOTO) {
            final String pf = prefs.getString("pend_file", "");
            final double la = Double.longBitsToDouble(prefs.getLong("pend_lat", Double.doubleToLongBits(Double.NaN)));
            final double lo = Double.longBitsToDouble(prefs.getLong("pend_lon", Double.doubleToLongBits(Double.NaN)));
            final long ts = prefs.getLong("pend_ts", System.currentTimeMillis());
            prefs.edit().remove("pend_file").apply();
            final java.io.File f = new java.io.File(RecPhotos.dir(this), pf);
            if (res == RESULT_OK && !pf.isEmpty() && f.length() > 0) {
                prefs.edit().putInt("photos_taken", prefs.getInt("photos_taken", 0) + 1).apply();
                new Thread(() -> {
                    RecPhotos.finish(getApplicationContext(), f, la, lo, ts);
                    runOnUiThread(() -> web.evaluateJavascript("window.dispatchEvent(new Event('mtphoto'))", null));
                }).start();
            } else if (!pf.isEmpty()) {
                f.delete();
            }
            return;
        }
        if (req == REQ_FILE && fileCb != null) {
            Uri[] r = null;
            if (res == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    r = new Uri[data.getClipData().getItemCount()];
                    for (int i = 0; i < r.length; i++) r[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) r = new Uri[]{data.getData()};
            }
            fileCb.onReceiveValue(r);
            fileCb = null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
        boolean ok = res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED;
        if (geoCb != null) {
            geoCb.invoke(geoOrigin, hasLoc(), false);
            geoCb = null;
        }
        web.evaluateJavascript("window.dispatchEvent(new CustomEvent('mtperm',{detail:" + (hasLoc() ? "true" : "false") + "}))", null);
    }

    /* ---------- Teilen: Dateien an /api/share-target schicken ---------- */
    private void share(Intent in) {
        final ArrayList<Uri> uris = new ArrayList<>();
        if (Intent.ACTION_SEND.equals(in.getAction())) {
            Uri u = in.getParcelableExtra(Intent.EXTRA_STREAM);
            if (u != null) uris.add(u);
        } else {
            ArrayList<Uri> l = in.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (l != null) uris.addAll(l);
        }
        if (uris.isEmpty()) {
            web.loadUrl(server() + "/");
            return;
        }
        Toast.makeText(this, R.string.sending, Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            String target = null;
            try {
                target = upload(uris);
            } catch (Exception e) {
                // fällt unten auf Fehlermeldung zurück
            }
            final String go = target;
            runOnUiThread(() -> {
                if (go == null) {
                    Toast.makeText(this, getString(R.string.send_failed), Toast.LENGTH_LONG).show();
                    web.loadUrl(server() + "/");
                } else web.loadUrl(go);
            });
        }).start();
    }

    private String upload(ArrayList<Uri> uris) throws Exception {
        String boundary = "----mt" + UUID.randomUUID().toString().replace("-", "");
        URL url = new URL(server() + "/api/share-target");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setInstanceFollowRedirects(false);
        c.setDoOutput(true);
        c.setConnectTimeout(15000);
        c.setReadTimeout(300000);
        c.setChunkedStreamingMode(64 * 1024);
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
        String ck = CookieManager.getInstance().getCookie(server());
        if (ck != null) c.setRequestProperty("Cookie", ck);
        OutputStream o = c.getOutputStream();
        byte[] buf = new byte[64 * 1024];
        for (Uri u : uris) {
            String name = "datei";
            try (android.database.Cursor cur = getContentResolver().query(u, new String[]{android.provider.OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                if (cur != null && cur.moveToFirst()) name = cur.getString(0);
            } catch (Exception e) { /* Name aus Pfad */ }
            if (name == null || name.isEmpty()) name = "datei";
            String type = getContentResolver().getType(u);
            if (!name.contains(".") && type != null) {
                if (type.contains("gpx")) name += ".gpx";
                else if (type.startsWith("image/")) name += ".jpg";
            }
            String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"files\"; filename=\"" + name.replace("\"", "_") + "\"\r\nContent-Type: application/octet-stream\r\n\r\n";
            o.write(head.getBytes("UTF-8"));
            try (InputStream in = getContentResolver().openInputStream(u)) {
                int n;
                while (in != null && (n = in.read(buf)) > 0) o.write(buf, 0, n);
            }
            o.write("\r\n".getBytes("UTF-8"));
        }
        o.write(("--" + boundary + "--\r\n").getBytes("UTF-8"));
        o.close();
        int code = c.getResponseCode();
        String loc = c.getHeaderField("Location");
        c.disconnect();
        if (code >= 300 && code < 400 && loc != null) return loc.startsWith("http") ? loc : server() + (loc.startsWith("/") ? "" : "/") + loc;
        if (code >= 200 && code < 300) return server() + "/";
        return null;
    }

    /* ---------- Brücke zur Weboberfläche ---------- */
    public class Bridge {
        @JavascriptInterface public String version() { return "2.9.0"; }
        @JavascriptInterface public String serverUrl() { return server(); }

        @JavascriptInterface
        public void setServer(String u) {
            final String v = normalizeServer(u);
            prefs.edit().putString("server", v).apply();
            runOnUiThread(() -> web.loadUrl(v.length() == 0 ? "file:///android_asset/setup.html" : v + "/"));
        }

        @JavascriptInterface
        public void changeServer() {
            prefs.edit().remove("server").apply();
            runOnUiThread(() -> web.loadUrl("file:///android_asset/setup.html"));
        }

        @JavascriptInterface public void startRecording(String sport, String name) { prefs.edit().putInt("photos_taken", 0).apply(); Recorder.get(MainActivity.this).start(sport, name); }
        @JavascriptInterface public boolean addWaypoint(String note) { return Recorder.get(MainActivity.this).addWaypoint(note); }
        @JavascriptInterface public String waypoints() { return Recorder.get(MainActivity.this).store().waypointsJson(); }
        @JavascriptInterface public void pauseRecording() { Recorder.get(MainActivity.this).pause(); }
        @JavascriptInterface public void resumeRecording() { Recorder.get(MainActivity.this).resume(); }
        @JavascriptInterface public void stopRecording(String name) { Recorder.get(MainActivity.this).stop(name); }
        @JavascriptInterface public String status() { return Recorder.get(MainActivity.this).statusJson(); }
        @JavascriptInterface public String points(int max) { return Recorder.get(MainActivity.this).store().pointsJson(max); }
        @JavascriptInterface public String takeFinished() { return Recorder.get(MainActivity.this).finishedGpx(); }
        @JavascriptInterface
        public boolean takePhoto() {
            Recorder r = Recorder.get(MainActivity.this);
            String st = r.state();
            if (!"recording".equals(st) && !"paused".equals(st)) return false;
            final java.io.File f = RecPhotos.newFile(MainActivity.this);
            try { f.createNewFile(); } catch (Exception e) { return false; }
            prefs.edit().putString("pend_file", f.getName())
                    .putLong("pend_lat", Double.doubleToLongBits(r.store().lastLat()))
                    .putLong("pend_lon", Double.doubleToLongBits(r.store().lastLon()))
                    .putLong("pend_ts", System.currentTimeMillis()).apply();
            runOnUiThread(() -> {
                try {
                    Uri u = PhotoProvider.uriFor(f);
                    Intent i = new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
                    i.putExtra(android.provider.MediaStore.EXTRA_OUTPUT, u);
                    i.setClipData(android.content.ClipData.newRawUri("", u));
                    i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivityForResult(i, REQ_PHOTO);
                } catch (Exception e) {
                    prefs.edit().remove("pend_file").apply();
                    f.delete();
                    Toast.makeText(MainActivity.this, getString(R.string.no_camera), Toast.LENGTH_LONG).show();
                }
            });
            return true;
        }
        @JavascriptInterface public String photoMode() { return RecPhotos.mode(MainActivity.this); }
        @JavascriptInterface public void setPhotoMode(String m) { prefs.edit().putString("photo_mode", "end".equals(m) ? "end" : "now").apply(); }
        @JavascriptInterface public void setRoute(String pts, String name) { Navi.setRoute(MainActivity.this, pts, name); }
        @JavascriptInterface public String routePoints() { return Navi.points(MainActivity.this); }
        @JavascriptInterface public void clearRoute() { Navi.clear(MainActivity.this); }
        @JavascriptInterface public String routeInfo() { return Navi.info(MainActivity.this); }
        @JavascriptInterface public boolean offlineServed() { return OfflineCache.offline(); }
        @JavascriptInterface public String offlineStats() { return OfflineCache.stats(MainActivity.this); }
        @JavascriptInterface public void clearOffline() { OfflineCache.clear(MainActivity.this); }
        @JavascriptInterface public boolean weatherOn() { return WeatherWatch.enabled(MainActivity.this); }
        @JavascriptInterface public void setWeather(boolean on) { WeatherWatch.setEnabled(MainActivity.this, on); }
        @JavascriptInterface public String weatherInfo() { return WeatherWatch.info(); }
        @JavascriptInterface public String lang() { return GuideText.lang; }
        @JavascriptInterface public void setLang(String l) { Navi.setLang(MainActivity.this, l); }
        @JavascriptInterface public void setGuide(boolean on) { Navi.setEnabled(MainActivity.this, on); }
        @JavascriptInterface public void guideTest() { Navi.speak(MainActivity.this, GuideText.test()); }
        @JavascriptInterface public void uploadPhotos() { RecPhotos.flushAsync(MainActivity.this); }
        @JavascriptInterface
        public String photoInfo() {
            try {
                return new org.json.JSONObject().put("taken", prefs.getInt("photos_taken", 0)).put("pending", RecPhotos.pending(MainActivity.this).length)
                        .put("busy", RecPhotos.busy()).put("error", RecPhotos.error()).toString();
            } catch (Exception e) { return "{}"; }
        }
        @JavascriptInterface public String backups() { return Recorder.get(MainActivity.this).backupsJson(); }
        @JavascriptInterface public String backupGpx(String f) { return Recorder.get(MainActivity.this).backupGpx(f); }
        @JavascriptInterface public void markUploaded() { Recorder.get(MainActivity.this).discard(); }
        @JavascriptInterface public void discardRecording() { Recorder.get(MainActivity.this).discard(); }
        @JavascriptInterface
        public String diagnose() {
            org.json.JSONObject o = new org.json.JSONObject();
            try {
                android.os.PowerManager pm = (android.os.PowerManager) getSystemService(POWER_SERVICE);
                android.location.LocationManager lm = (android.location.LocationManager) getSystemService(LOCATION_SERVICE);
                o.put("version", "2.6.0");
                o.put("android", Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")");
                o.put("device", Build.MANUFACTURER + " " + Build.MODEL);
                o.put("server", server());
                o.put("loc_perm", hasLoc());
                o.put("notif_perm", Build.VERSION.SDK_INT < 33 || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED);
                o.put("gps_on", lm != null && lm.isProviderEnabled(android.location.LocationManager.GPS_PROVIDER));
                o.put("battery_free", pm != null && pm.isIgnoringBatteryOptimizations(getPackageName()));
                o.put("status", new org.json.JSONObject(Recorder.get(MainActivity.this).statusJson()));
            } catch (Exception e) {
                // unvollständig ist besser als nichts
            }
            return o.toString();
        }

        @JavascriptInterface
        public void openUrl(String u) {
            runOnUiThread(() -> {
                try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(u)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); }
                catch (Exception e) { Toast.makeText(MainActivity.this, R.string.no_app, Toast.LENGTH_LONG).show(); }
            });
        }

        @JavascriptInterface public String logText() { return AppLog.tail(30000); }
        @JavascriptInterface public void clearLog() { AppLog.clear(); }
        @JavascriptInterface public void appLog(String m) { AppLog.log("[Web] " + m); }

        @JavascriptInterface
        public void shareText(String text) {
            runOnUiThread(() -> {
                Intent i = new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text).putExtra(Intent.EXTRA_SUBJECT, text.split("\n")[0].length() > 80 ? "Meine Touren" : text.split("\n")[0]);
                startActivity(Intent.createChooser(i, getString(R.string.send_with)));
            });
        }

        @JavascriptInterface public boolean hasPermission() { return hasLoc(); }

        @JavascriptInterface
        public void requestPermission() {
            runOnUiThread(() -> requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_PERM));
        }

        @JavascriptInterface
        public void openBatterySettings() {
            runOnUiThread(() -> {
                try { startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)); }
                catch (Exception e) { startActivity(new Intent(Settings.ACTION_SETTINGS)); }
            });
        }
    }
}
