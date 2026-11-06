package de.meinetouren.app;

import android.content.Context;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Kleines Protokoll für die Fehlersuche (Datei im App-Speicher, wird auf ca. 100 KB begrenzt). */
public final class AppLog {
    private static File file;
    private static final SimpleDateFormat F = new SimpleDateFormat("dd.MM. HH:mm:ss", Locale.GERMANY);

    private AppLog() { }

    public static synchronized void init(Context c) {
        if (file == null) file = new File(c.getApplicationContext().getFilesDir(), "app.log");
    }

    public static synchronized void log(String msg) {
        if (file == null) return;
        try {
            if (file.length() > 100_000) {
                String all = new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
                Files.write(file.toPath(), all.substring(all.length() / 2).getBytes(StandardCharsets.UTF_8));
            }
            try (FileWriter w = new FileWriter(file, true)) {
                w.write(F.format(new Date()) + "  " + msg + "\n");
            }
        } catch (IOException | RuntimeException e) {
            // Protokoll darf nie etwas kaputt machen
        }
    }

    public static synchronized String tail(int maxChars) {
        if (file == null || !file.exists()) return "";
        try {
            String s = new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
            return s.length() > maxChars ? s.substring(s.length() - maxChars) : s;
        } catch (IOException e) {
            return "";
        }
    }

    public static synchronized void clear() {
        if (file != null) file.delete();
    }
}
