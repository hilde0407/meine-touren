package de.meinetouren.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;

import java.util.Locale;

/** Vordergrunddienst: hält die GPS-Aufzeichnung am Laufen, auch bei ausgeschaltetem Bildschirm. */
public class RecorderService extends Service implements LocationListener {
    public static final String ACT_START = "de.meinetouren.app.START";
    public static final String ACT_PAUSE = "de.meinetouren.app.PAUSE";
    public static final String ACT_RESUME = "de.meinetouren.app.RESUME";
    public static final String ACT_STOP = "de.meinetouren.app.STOP";
    private static final String CHANNEL = "rec";
    private static final int NID = 42;

    private LocationManager lm;
    private PowerManager.WakeLock wl;
    private long lastNotify = 0;
    private boolean listening = false;

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Recorder r = Recorder.get(this);
        String a = intent == null ? null : intent.getAction();
        if (a == null) {                                      // vom System nach einem Beenden des Prozesses neu gestartet
            if (Recorder.RECORDING.equals(r.state())) {
                r.resumeAfterKill();
                foreground(r);
                listen(r);
            } else {
                stopSelf();
            }
            return START_STICKY;
        }
        if (ACT_START.equals(a) || ACT_RESUME.equals(a)) {
            foreground(r);
            listen(r);
        } else if (ACT_PAUSE.equals(a) || ACT_STOP.equals(a)) {
            unlisten();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
        }
        return START_STICKY;
    }

    private void foreground(Recorder r) {
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        NotificationChannel ch = new NotificationChannel(CHANNEL, getString(R.string.rec_channel), NotificationManager.IMPORTANCE_LOW);
        nm.createNotificationChannel(ch);
        Notification n = build(r);
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(NID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION);
            else startForeground(NID, n);
        } catch (RuntimeException e) {                         // z. B. fehlende Standort-Berechtigung
            AppLog.log("Vordergrunddienst konnte nicht starten: " + e);
            stopSelf();
        }
    }

    private Notification build(Recorder r) {
        Intent open = new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        double km = r.store().distanceM() / 1000.0;
        long s = r.store().activeMs() / 1000;
        String txt = String.format(Locale.GERMANY, "%.2f km · %d:%02d h", km, s / 3600, (s % 3600) / 60);
        return new Notification.Builder(this, CHANNEL)
                .setSmallIcon(R.drawable.ic_stat_rec)
                .setContentTitle(getString(R.string.rec_title))
                .setContentText(txt)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(pi)
                .build();
    }

    private void listen(Recorder r) {
        if (listening) return;
        lm = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
        try {
            lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, r.minTimeMs(), r.minDistM(), this, Looper.getMainLooper());
            listening = true;
        } catch (SecurityException e) {
            AppLog.log("Keine Standort-Berechtigung");
            stopSelf();
            return;
        } catch (IllegalArgumentException e) {
            stopSelf();
            return;
        }
        if (wl == null) {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "MeineTouren:rec");
            wl.acquire(12L * 60 * 60 * 1000);
        }
    }

    private void unlisten() {
        if (lm != null && listening) {
            try { lm.removeUpdates(this); } catch (SecurityException e) { /* nichts zu tun */ }
        }
        listening = false;
        if (wl != null && wl.isHeld()) wl.release();
        wl = null;
    }

    @Override
    public void onDestroy() {
        unlisten();
        super.onDestroy();
    }

    @Override
    public void onLocationChanged(Location l) {
        Recorder r = Recorder.get(this);
        r.onLocation(l);
        LivePost.send(this, l);
        long now = System.currentTimeMillis();
        if (now - lastNotify > 15000) {
            lastNotify = now;
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            nm.notify(NID, build(r));
        }
    }

    @Override
    public void onStatusChanged(String provider, int status, Bundle extras) { }

    @Override
    public void onProviderEnabled(String provider) { AppLog.log("GPS eingeschaltet"); }

    @Override
    public void onProviderDisabled(String provider) { AppLog.log("GPS ausgeschaltet"); }
}
