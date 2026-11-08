package de.meinetouren.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.location.Location;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Sprachansagen entlang einer geladenen Strecke: hält Strecke und Sprachausgabe, läuft im Aufzeichnungsdienst (auch bei ausgeschaltetem Bildschirm). */
final class Navi {
    private static Guide guide;
    private static boolean loaded = false;
    private static TextToSpeech tts;
    private static boolean ttsReady = false, ttsFailed = false;
    private static final List<String> queue = new ArrayList<>();
    private static AudioFocusRequest focus;

    private Navi() { }

    private static SharedPreferences prefs(Context c) { return c.getSharedPreferences("app", Context.MODE_PRIVATE); }
    private static File file(Context c) { return new File(c.getFilesDir(), "route.txt"); }

    /** Sprache der Ansagen (de/en/fr/es) setzen und merken; die Sprachausgabe wird bei Wechsel neu aufgebaut. */
    static synchronized void setLang(Context c, String l) {
        String n = GuideText.norm(l);
        prefs(c).edit().putString("lang", n).apply();
        if (!n.equals(GuideText.lang)) { GuideText.lang = n; shutdown(); }
    }

    static void initLang(Context c) {
        String l = prefs(c).getString("lang", null);
        GuideText.lang = GuideText.norm(l != null ? l : Locale.getDefault().getLanguage());
    }

    /** Kontext mit der Ansage-/App-Sprache (für Texte aus den Ressourcen, z. B. die Benachrichtigung). */
    static Context lc(Context c) {
        android.content.res.Configuration cf = new android.content.res.Configuration(c.getResources().getConfiguration());
        cf.setLocale(GuideText.locale());
        return c.createConfigurationContext(cf);
    }

    static boolean enabled(Context c) { return prefs(c).getBoolean("guide_on", true); }
    static void setEnabled(Context c, boolean on) { prefs(c).edit().putBoolean("guide_on", on).apply(); }

    static synchronized void setRoute(Context c, String text, String name) {
        try (FileOutputStream o = new FileOutputStream(file(c))) {
            o.write(text.getBytes("UTF-8"));
        } catch (Exception e) {
            AppLog.log("Route speichern: " + e.getClass().getSimpleName());
            return;
        }
        prefs(c).edit().putString("route_name", name == null ? "" : name).apply();
        guide = Guide.parse(text);
        loaded = true;
        AppLog.log("Route geladen: \"" + name + "\", " + (guide == null ? "ungültig" : Math.round(guide.totalM()) + " m, " + guide.turnCount() + " Abbiegungen"));
    }

    static synchronized void clear(Context c) {
        file(c).delete();
        prefs(c).edit().remove("route_name").apply();
        guide = null;
        loaded = true;
    }

    /** Fortschritt zurücksetzen (neue Aufzeichnung auf derselben Strecke). */
    static synchronized void reset(Context c) {
        loaded = false;
        guide = null;
    }

    private static synchronized Guide guide(Context c) {
        if (!loaded) {
            loaded = true;
            File f = file(c);
            if (f.exists()) {
                try (FileInputStream in = new FileInputStream(f)) {
                    ByteArrayOutputStream b = new ByteArrayOutputStream();
                    byte[] buf = new byte[16384];
                    int n;
                    while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
                    guide = Guide.parse(b.toString("UTF-8"));
                } catch (Exception e) {
                    guide = null;
                }
            }
        }
        return guide;
    }

    static synchronized String info(Context c) {
        Guide g = guide(c);
        try {
            org.json.JSONObject o = new org.json.JSONObject();
            o.put("on", enabled(c));
            o.put("has", g != null);
            if (g != null) {
                o.put("name", prefs(c).getString("route_name", ""));
                o.put("km", Math.round(g.totalM() / 10.0) / 100.0);
                o.put("turns", g.turnCount());
                o.put("off", g.offRoute());
                o.put("prog_m", Math.round(g.progressM()));
                o.put("total_m", Math.round(g.totalM()));
                Guide.Turn t = g.nextTurn();
                if (t != null) { o.put("next_m", Math.round(t.at - g.progressM())); o.put("next_angle", Math.round(t.angle)); }
            }
            return o.toString();
        } catch (Exception e) {
            return "{}";
        }
    }

    static synchronized String points(Context c) {
        Guide g = guide(c);
        return g == null ? "[]" : g.pointsJson();
    }

    static void onFix(Context c, Location l) {
        Guide g = guide(c);
        if (g == null || !enabled(c)) return;
        List<String> say;
        synchronized (Navi.class) {
            say = g.fix(l.getLatitude(), l.getLongitude(), l.hasAccuracy() ? l.getAccuracy() : 0f, l.hasSpeed() ? l.getSpeed() : 0.0, System.currentTimeMillis());
        }
        for (String s : say) speak(c, s);
    }

    static synchronized void speak(final Context c, final String text) {
        AppLog.log("Ansage: " + text);
        if (ttsFailed) return;
        if (tts == null) {
            final Context app = c.getApplicationContext();
            queue.add(text);
            tts = new TextToSpeech(app, status -> {
                synchronized (Navi.class) {
                    if (status != TextToSpeech.SUCCESS) { ttsFailed = true; AppLog.log("Sprachausgabe nicht verfügbar"); return; }
                    int r = tts.setLanguage(GuideText.locale());
                    if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) AppLog.log("Stimme für " + GuideText.lang + " fehlt – Standardstimme wird verwendet");
                    tts.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());
                    tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                        @Override public void onStart(String id) { }
                        @Override public void onDone(String id) { release(app); }
                        @Override public void onError(String id) { release(app); }
                    });
                    ttsReady = true;
                    for (String q : queue) say(app, q);
                    queue.clear();
                }
            });
            return;
        }
        if (!ttsReady) { queue.add(text); return; }
        say(c.getApplicationContext(), text);
    }

    private static void say(Context c, String text) {
        AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
        if (am != null) {
            focus = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                    .setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()).build();
            am.requestAudioFocus(focus);
        }
        tts.speak(text, TextToSpeech.QUEUE_ADD, null, "mt" + System.nanoTime());
    }

    private static void release(Context c) {
        AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
        if (am != null && focus != null) am.abandonAudioFocusRequest(focus);
    }

    static synchronized void shutdown() {
        if (tts != null) { tts.stop(); tts.shutdown(); }
        tts = null;
        ttsReady = false;
        queue.clear();
    }
}
