package de.meinetouren.app;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;

import java.io.File;
import java.io.FileNotFoundException;

/** Gibt der Kamera-App Schreibzugriff auf genau eine Datei im privaten Ordner der App (ohne AndroidX/FileProvider). */
public class PhotoProvider extends ContentProvider {
    public static final String AUTH = "de.meinetouren.app.fileprovider";

    public static Uri uriFor(File f) {
        return Uri.parse("content://" + AUTH + "/p/" + Uri.encode(f.getName()));
    }

    @Override public boolean onCreate() { return true; }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        String name = uri.getLastPathSegment();
        if (name == null || name.contains("/") || name.contains("..")) throw new FileNotFoundException();
        File f = new File(RecPhotos.dir(getContext()), name);
        int m = mode.contains("w") ? ParcelFileDescriptor.MODE_READ_WRITE | ParcelFileDescriptor.MODE_CREATE : ParcelFileDescriptor.MODE_READ_ONLY;
        return ParcelFileDescriptor.open(f, m);
    }

    @Override public String getType(Uri uri) { return "image/jpeg"; }
    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) { return null; }
    @Override public Uri insert(Uri u, ContentValues v) { return null; }
    @Override public int delete(Uri u, String s, String[] a) { return 0; }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { return 0; }
}
