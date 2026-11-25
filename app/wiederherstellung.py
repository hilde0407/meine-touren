"""Sicherung in der Oberfläche zurückspielen (3.40.0) – für Administratoren, ohne Root-Shell. deploy/restore.sh bleibt daneben bestehen.

Ablauf, immer in zwei Schritten:
  1. Vorprüfung (ändert nichts): ZIP und enthaltene Datenbank prüfen, Programmversion vergleichen, die Umstellung auf das heutige Schema an einer Kopie durchspielen,
     zählen, was drin ist. Ergebnis ist ein kurzlebiges Token, gebunden an den Benutzer und an den SHA-256 genau dieser Datei.
  2. Wiederherstellung (nur mit Token und ausdrücklicher Bestätigung): Sicherheitskopie des heutigen Stands über den normalen Sicherungsweg, Datenbank tauschen,
     nachprüfen, bei einem Fehler automatisch zurück auf die Sicherheitskopie. Strecken und Gerätefotos werden wie im Skript nur ergänzt, nie überschrieben.

Tausch der Datenbank im laufenden Betrieb – warum sqlite3 Connection.backup() und kein Dateitausch:
  Die App hält je Datenbankdatei genau EINE dauerhaft offene Verbindung (db._conns, WAL, check_same_thread=False); jeder Zugriff läuft über db.cur() und die
  Sperre db._plock(Datei). Ein Dateitausch (os.replace, -wal/-shm löschen) wäre nur sicher, wenn nachweislich keine Verbindung offen ist – das lässt sich für
  andere Prozesse (nächtliche Sicherung per Cron, Umzugspaket) nicht garantieren; sie würden auf der gelöschten Datei weiterarbeiten oder ein fremdes WAL sehen.
  Stattdessen wird die geprüfte, schon umgestellte Kopie unter der Sperre der Live-Datenbank mit der Online-Backup-Schnittstelle von SQLite IN die offene
  Live-Verbindung geschrieben: eine einzige Schreibtransaktion (im WAL atomar – bricht sie ab oder fällt der Strom aus, bleibt der alte Stand), die Verbindung
  und alle Dateisperren bleiben gültig, andere Leser sehen entweder den alten oder den neuen Stand, nie eine Mischung. Der Dienst muss nicht neu starten.

Nicht verändert werden: Benutzer und Anmeldungen (system.sqlite), Fotodateien, Zwischenspeicher, secret.key."""
import hashlib
import os
import re
import secrets
import shutil
import sqlite3
import time
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException, Request

from . import auth, backup_check, config, ctx, db, extras, jobs, umzug

router = APIRouter()

MAX_UPLOAD = int(os.environ.get("MT_RESTORE_MAX_MB", "2048")) * 1_000_000   # Größenlimit für hochgeladene Sicherungen (wie client_max_body_size im nginx)
MAX_ENTPACKT = 16_000_000_000        # mehr packt die Vorprüfung nie aus (Schutz vor ZIP-Bomben)
RESERVE = 50_000_000                 # so viel muss nach dem Auspacken im Datenordner noch frei bleiben
TOKEN_TTL = 600                      # Sekunden zwischen Vorprüfung und Bestätigung
ALT_S = 3600                         # ältere Reste im temporären Bereich werden bei der nächsten Gelegenheit gelöscht
DBNAME = "komoot_hub.sqlite"
TRACK_ENDEN = (".gpx", ".hr.json", ".met.json", ".uhr.json")      # wie extras._backup_files
GERAET_ENDEN = (".jpg",)
_tokens = {}                         # Token -> {"wer", "id", "sha", "exp"}; nur im Arbeitsspeicher, einmal verwendbar


class Abgelehnt(Exception):
    """Die Sicherung wird nicht zurückgespielt; der Text ist für den Benutzer gedacht. Es wurde nichts verändert."""

    def __init__(self, text, status=400):
        super().__init__(text)
        self.status = status


# ------------------------------------------------------------------------------------------------ temporärer Bereich
def _bereich():
    """Temporärer Bereich im Datenordner, je Benutzer getrennt (gleiches Dateisystem wie die Datenbank; vom Umzugspaket ausgenommen)."""
    d = config.DATA_DIR / "restore-tmp" / (ctx.uid() or "_")
    d.mkdir(parents=True, exist_ok=True)
    try:
        d.chmod(0o700)
    except OSError:
        pass
    return d


def _weg(p):
    try:
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)
    except OSError:
        pass


def aufraeumen(alles=False):
    """Liegengebliebenes löschen: Arbeitsordner und halbe Uploads älter als eine Stunde (alles=True: sofort, für den Programmstart) – für alle Benutzer."""
    root = config.DATA_DIR / "restore-tmp"
    if not root.is_dir():
        return
    now = time.time()
    for d in root.iterdir():
        for p in (d.iterdir() if d.is_dir() else [d]):
            try:
                alt = now - p.stat().st_mtime > ALT_S
            except OSError:
                continue
            if alles or alt:
                _weg(p)
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
    try:
        if not any(root.iterdir()):
            root.rmdir()
    except OSError:
        pass
    for t, e in list(_tokens.items()):
        if e["exp"] < now:
            _tokens.pop(t, None)


def _arbeitsordner():
    d = _bereich() / ("work-" + secrets.token_hex(8))
    d.mkdir()
    return d


# ------------------------------------------------------------------------------------------------ Quellen
def _wer(request):
    u = getattr(request.state, "user", None)
    return u["uid"] if u else ""


def ist_sicherheitskopie(name):
    return extras.VOR_RESTORE in name


def liste():
    """Sicherungen des Servers für den angemeldeten Benutzer, neueste zuerst."""
    out = []
    for i, d in enumerate(config.backup_dirs(ctx.uid())):
        if not d.is_dir():
            continue
        for p in d.glob("*.zip"):
            try:
                st = p.stat()
            except OSError:
                continue
            out.append({"id": f"s:{i}:{p.name}", "name": p.name, "ts": int(st.st_mtime), "groesse": st.st_size, "sicherheitskopie": ist_sicherheitskopie(p.name)})
    return sorted(out, key=lambda x: (x["ts"], x["name"]), reverse=True)


def _quelle(sid):
    """Kennung aus der Liste bzw. vom Upload -> (Pfad, Anzeigename, ist_upload). Nur Dateien aus den Sicherungsordnern dieses Benutzers oder seinem temporären Bereich."""
    sid = str(sid or "")
    m = re.fullmatch(r"s:(\d):([A-Za-z0-9._-]{1,120}\.zip)", sid)
    if m:
        dirs = config.backup_dirs(ctx.uid())
        i = int(m.group(1))
        if i < len(dirs):
            p = dirs[i] / m.group(2)
            if p.is_file() and not p.is_symlink():
                return p, p.name, False
    m = re.fullmatch(r"u:([0-9a-f]{16})", sid)
    if m:
        p = _bereich() / f"upload-{m.group(1)}.zip"
        if p.is_file():
            n = p.with_suffix(".name")
            try:
                name = n.read_text(encoding="utf-8").strip() or "Hochgeladene Sicherung"
            except OSError:
                name = "Hochgeladene Sicherung"
            return p, name, True
    raise Abgelehnt("Diese Sicherung gibt es nicht mehr. Bitte die Liste neu laden.", 404)


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ Zählen und Versionen
def _vnum(v):
    m = re.match(r"\s*(\d+)\.(\d+)(?:\.(\d+))?", str(v or ""))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def _reisen():
    from . import more2
    hid = {r["id"] for r in db.query("SELECT id FROM trip_hidden")}
    mind = max(2, db.get_int("trip_min_days", more2.TRIP_MIN_DAYS))
    return sum(1 for t in more2._apply_trip_edits(more2.build_trips()) if t["id"] not in hid and (t["days"] >= mind or t.get("edited")))


def zahlen(strecken=None):
    """Zähler der Datenbank, mit der der Aufruf gerade arbeitet (Live-Datenbank oder – innerhalb von db.andere_datei – die Kopie aus der Sicherung)."""
    n = lambda t: db.one(f"SELECT COUNT(*) n FROM {t}")["n"]
    try:
        reisen = _reisen()
    except Exception:  # noqa  (die Zahl ist nur Anzeige; ein Fehler darin darf die Wiederherstellung nicht verhindern)
        reisen = None
    if strecken is None:
        strecken = sum(1 for _ in config.TRACK_DIR.glob("*.gpx")) if config.TRACK_DIR.is_dir() else 0
    return {"touren": n("tours"), "strecken": strecken, "reisen": reisen, "plaene": n("plans"), "layouts": n("user_layout")}


def _erstellt(z, pfad, upload):
    """Zeitpunkt der Sicherung: aus INFO.txt, sonst Zeitstempel der Datenbank im ZIP, sonst (Dateien des Servers) die Änderungszeit."""
    try:
        m = re.search(r"(?:Backup|Sicherung) (\S+)", z.read("INFO.txt").decode("utf-8", "replace"))
        if m:
            return int(datetime.fromisoformat(m.group(1)).timestamp())
    except (KeyError, ValueError, OSError):
        pass
    try:
        return int(time.mktime(z.getinfo(DBNAME).date_time + (0, 0, -1)))
    except (KeyError, ValueError, OverflowError):
        return None if upload else int(pfad.stat().st_mtime)


def _dateien(z):
    """Einträge für tracks/ und devices/: [(ZipInfo, Unterordner, Dateiname)]. Unzulässige Pfade (absolut, „..“, Rückstrich) -> Abgelehnt: so ein ZIP stammt nicht aus der App."""
    out = []
    for m in z.infolist():
        n = m.filename
        if n.startswith(("/", "\\")) or "\\" in n or "\x00" in n or re.match(r"^[A-Za-z]:", n) or ".." in PurePosixPath(n).parts:
            raise Abgelehnt("Die Sicherung enthält unzulässige Dateipfade und wird nicht verwendet.")
        if m.is_dir():
            continue
        parts = PurePosixPath(n).parts
        if len(parts) != 2 or parts[0] not in ("tracks", "devices"):
            continue                                        # alles andere (INFO.txt, UID.txt, system.sqlite, Unterordner) wird nicht ausgepackt
        f = parts[1]
        if f.startswith(".") or not f.lower().endswith(TRACK_ENDEN if parts[0] == "tracks" else GERAET_ENDEN):
            continue
        out.append((m, parts[0], f))
    return out


# ------------------------------------------------------------------------------------------------ Vorprüfung (gemeinsam für beide Schritte)
def vorbereiten(pfad, name, upload, work):
    """Prüft die Sicherung vollständig und legt in `work` eine auf das heutige Schema umgestellte Kopie der Datenbank ab. Ändert nichts an den Live-Daten.
    Gibt die Angaben für die Anzeige zurück (plus „db“: Pfad der Kopie). Jede Ablehnung kommt als Abgelehnt mit verständlichem Text."""
    pfad = Path(pfad)
    try:
        groesse = pfad.stat().st_size
    except OSError:
        raise Abgelehnt("Diese Sicherung gibt es nicht mehr. Bitte die Liste neu laden.", 404)
    if groesse == 0:
        raise Abgelehnt("Die Datei ist leer.")
    if not zipfile.is_zipfile(pfad):
        raise Abgelehnt("Die Datei ist kein lesbares ZIP (abgeschnitten oder beschädigt).")
    try:
        with zipfile.ZipFile(pfad) as z:
            namen = z.namelist()
            if umzug.MARK in namen:
                raise Abgelehnt("Das ist ein Umzugspaket (kompletter Datenordner mit allen Benutzern, Fotos und Schlüsseln). Es kann nicht in der Oberfläche zurückgespielt werden, "
                                "weil dafür der Dienst angehalten werden muss. Bitte weiterhin das Skript auf dem Server verwenden.")
            if DBNAME not in namen:
                raise Abgelehnt("Die Datenbank (komoot_hub.sqlite) fehlt in der Sicherung.")
            dateien = _dateien(z)
            brauch = z.getinfo(DBNAME).file_size * 2 + sum(m.file_size for m, _, _ in dateien)
            if brauch > MAX_ENTPACKT:
                raise Abgelehnt("Die Sicherung ist ausgepackt zu groß und wird nicht verwendet.")
            try:
                frei = shutil.disk_usage(work).free
            except OSError:
                frei = None
            if frei is not None and frei < brauch + RESERVE:
                raise Abgelehnt(f"Zu wenig freier Speicher für die Prüfung: {frei // 1_000_000} MB frei, mindestens {(brauch + RESERVE) // 1_000_000} MB nötig", 507)
            chk = backup_check.pruefe_zip(pfad, tief=True)          # testzip + Integritätsprüfung der enthaltenen Datenbank (im Temp-Verzeichnis)
            if not chk["ok"]:
                f = chk["fehler"] or "Die Sicherung ist beschädigt."
                if not f.startswith(("Die ", "Beschädigter ")):          # rohe Fehlermeldung (z. B. „DatabaseError: file is not a database“) verständlich einleiten
                    f = (f"Die Datenbank in der Sicherung ist beschädigt: {f}" if "Error: " in f and "OSError" not in f else f"Die Sicherung konnte nicht gelesen werden: {f}")
                raise Abgelehnt(f)
            uid_txt = z.read("UID.txt").decode("utf-8", "replace").strip() if "UID.txt" in namen else ""
            erstellt = _erstellt(z, pfad, upload)
            kopie = Path(work) / DBNAME
            with z.open(DBNAME) as src, open(kopie, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            strecken = sum(1 for _, sub, f in dateien if sub == "tracks" and f.lower().endswith(".gpx"))
    except zipfile.BadZipFile:
        raise Abgelehnt("Die Datei ist kein lesbares ZIP (abgeschnitten oder beschädigt).")
    except (OSError, EOFError, RuntimeError, NotImplementedError) as e:
        raise Abgelehnt(f"Die Sicherung konnte nicht gelesen werden: {e.__class__.__name__}")

    # Wem gehört die Sicherung? Administratoren verwalten Benutzer, sehen aber deren Daten nicht – also nur die eigene Datenbank.
    ich = ctx.uid() or ""
    if uid_txt and uid_txt != ich:
        raise Abgelehnt("Diese Sicherung gehört zu einem anderen Benutzer und kann hier nicht zurückgespielt werden. Jeder Administrator kann nur seine eigenen Daten zurückspielen; "
                        "für andere Benutzer bitte das Skript auf dem Server verwenden.", 403)
    eigner = auth.q1("SELECT name FROM users WHERE uid=?", (ich,)) if ich else None

    # Rohdaten ansehen: gehört die Datei überhaupt zur App, aus welcher Version stammt sie, sind Zugangsdaten enthalten?
    try:
        c = sqlite3.connect(f"file:{kopie}?mode=ro", uri=True)
        try:
            tabs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"tours", "settings"} <= tabs:
                raise Abgelehnt("Die Datenbank in der Sicherung gehört nicht zu Meine Touren.")
            r = c.execute("SELECT v FROM settings WHERE k='last_version'").fetchone()
            version = (r[0] or "") if r else ""
            mit_zugang = c.execute("SELECT COUNT(*) FROM settings WHERE v<>'' AND k IN (%s)" % ",".join("?" * len(config.ENCRYPTED_KEYS)), tuple(config.ENCRYPTED_KEYS)).fetchone()[0]
        finally:
            c.close()
    except sqlite3.Error as e:
        raise Abgelehnt(f"Die Datenbank in der Sicherung ist beschädigt: {str(e)[:160]}")
    vb, vj = _vnum(version), _vnum(config.VERSION)
    if vb and vj and vb > vj:
        raise Abgelehnt(f"Die Sicherung stammt aus einer neueren Programmversion ({'.'.join(map(str, vb))}) als der installierten ({'.'.join(map(str, vj))}). "
                        "Bitte zuerst die App aktualisieren und es dann noch einmal versuchen.")

    # Umstellung auf das heutige Schema an der Kopie: derselbe Weg wie beim Öffnen der echten Datenbank (db.migrate). Die umgestellte Kopie wird später eingespielt.
    try:
        with db.andere_datei(kopie):
            db.init()
            qc = "; ".join(str(list(r.values())[0]) for r in db.query("PRAGMA quick_check")[:3])
            if qc != "ok":
                raise Abgelehnt(f"Die Datenbank in der Sicherung ist beschädigt: {qc[:200]}")
            z_sich = zahlen(strecken)
    except sqlite3.Error as e:
        raise Abgelehnt(f"Die Sicherung passt nicht zu dieser Programmversion (die Umstellung der Datenbank ist fehlgeschlagen): {str(e)[:160]}")
    jetzt_zugang = db.one("SELECT COUNT(*) n FROM settings WHERE v<>'' AND k IN (%s)" % ",".join("?" * len(config.ENCRYPTED_KEYS)), tuple(config.ENCRYPTED_KEYS))["n"]
    return {"ok": True, "name": name, "groesse": groesse, "erstellt_ts": erstellt, "alter_h": round((time.time() - erstellt) / 3600, 1) if erstellt else None,
            "version": ".".join(map(str, vb)) if vb else None, "version_jetzt": ".".join(map(str, vj)) if vj else None,
            "benutzer": {"uid": uid_txt, "name": (eigner or {}).get("name") or "", "ohne_angabe": not uid_txt and bool(ich)},
            "zahlen": {"sicherung": z_sich, "jetzt": zahlen()},
            "zugangsdaten": "enthalten" if mit_zugang else ("bleiben" if jetzt_zugang else "keine"),
            "sicherheitskopie": ist_sicherheitskopie(name), "upload": upload, "db": kopie}


# ------------------------------------------------------------------------------------------------ Tausch
def einspielen(quelle):
    """Inhalt der Datei `quelle` vollständig in die Live-Datenbank des Benutzers schreiben (Begründung des Verfahrens: siehe Kopf der Datei).
    Unter db._plock: kein anderer Thread der App benutzt die Verbindung, solange kopiert wird."""
    live = config.DB_PATH
    with db._plock(live):
        conn = db._open(live)
        conn.commit()
        ps = conn.execute("PRAGMA page_size").fetchone()[0]
        src = sqlite3.connect(str(quelle))
        try:
            if src.execute("PRAGMA page_size").fetchone()[0] != ps:      # im WAL-Betrieb lässt sich die Seitengröße des Ziels nicht ändern: die Kopie anpassen
                src.execute("PRAGMA journal_mode=DELETE")
                src.execute(f"PRAGMA page_size={int(ps)}")
                src.execute("VACUUM")
            src.backup(conn)                                            # eine Transaktion; bei einem Fehler bleibt der bisherige Inhalt
        finally:
            src.close()
        conn.commit()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")             # neuen Stand in die Hauptdatei schreiben; scheitert nur, wenn gerade ein anderer Prozess liest (dann später von selbst)
        except sqlite3.Error:
            pass


def nachpruefung(erwartet):
    """Nach dem Tausch: Live-Datenbank lesbar, in sich stimmig und mit den erwarteten Touren? Gibt '' oder den Fehlertext zurück."""
    try:
        qc = "; ".join(str(list(r.values())[0]) for r in db.query("PRAGMA quick_check")[:3])
        if qc != "ok":
            return qc[:200]
        n = db.one("SELECT COUNT(*) n FROM tours")["n"]
        if n != erwartet["touren"]:
            return f"{n} statt {erwartet['touren']} Touren"
        if (db.one("PRAGMA journal_mode") or {}).get("journal_mode", "wal") != "wal":
            return "Journal-Modus"
    except sqlite3.Error as e:
        return str(e)[:200]
    return ""


def _sicherheitskopie():
    err = "kein Sicherungsordner"
    for d in config.backup_dirs(ctx.uid()):
        try:
            d.mkdir(parents=True, exist_ok=True)
            return Path(extras.make_backup(str(d), keep=0, kennung=extras.VOR_RESTORE))      # keep=0: dabei keine ältere Sicherung löschen (auch nicht die gewählte)
        except Exception as e:  # noqa
            err = f"{d}: {e}"
    raise Abgelehnt(f"Die Sicherheitskopie des heutigen Stands konnte nicht angelegt werden. Es wurde nichts verändert. Grund: {err[:200]}", 500)


def _zurueck(kopie, work):
    """Rückfall: Datenbank aus der eben angelegten Sicherheitskopie wieder einspielen. True, wenn danach alles stimmt."""
    try:
        d = Path(work) / "rueckfall"
        d.mkdir(exist_ok=True)
        with zipfile.ZipFile(kopie) as z:
            z.extract(DBNAME, d)
        einspielen(d / DBNAME)
        qc = db.query("PRAGMA quick_check")
        return bool(qc) and list(qc[0].values())[0] == "ok"
    except Exception as e:  # noqa
        jobs.log(f"Wiederherstellung: Rückfall fehlgeschlagen: {e}")
        return False


def _ergaenzen(pfad):
    """tracks/ und devices/ aus dem ZIP ergänzen: nur Dateien, die es noch nicht gibt; nie außerhalb der beiden Ordner. Gibt (neue Strecken-Dateien, neue Gerätefotos) zurück."""
    ziel = {"tracks": config.TRACK_DIR, "devices": config.DB_PATH.parent / "devices"}
    neu = {"tracks": 0, "devices": 0}
    with zipfile.ZipFile(pfad) as z:
        for m, sub, f in _dateien(z):
            d = ziel[sub]
            d.mkdir(parents=True, exist_ok=True)
            dest = d / f
            if dest.resolve().parent != d.resolve() or dest.exists() or dest.is_symlink():
                continue
            part = d / (f + ".part")
            try:
                with z.open(m) as s, open(part, "xb") as o:
                    shutil.copyfileobj(s, o, 1 << 20)
                os.replace(part, dest)
                neu[sub] += 1
            finally:
                part.unlink(missing_ok=True)
    return neu["tracks"], neu["devices"]


def _zugang_lesen():
    return {r["k"]: r["v"] for r in db.query("SELECT k, v FROM settings WHERE v<>'' AND k IN (%s)" % ",".join("?" * len(config.ENCRYPTED_KEYS)), tuple(config.ENCRYPTED_KEYS))}


def _zugang_behalten(vorher):
    """Zugangsdaten, die in der Sicherung fehlen (der Download enthält bewusst keine), aus dem bisherigen Stand behalten – verschlüsselt, wie sie waren."""
    n = 0
    for k, v in vorher.items():
        r = db.one("SELECT v FROM settings WHERE k=?", (k,))
        if not r or not r["v"]:
            db.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
            n += 1
    return n


def _freigaben_abgleichen():
    """Das Verzeichnis der Freigabelinks (system.sqlite) an die zurückgespielte Datenbank anpassen: Links aus der Sicherung gelten wieder, spätere nicht mehr."""
    u = ctx.uid() or ""
    toks = [r["token"] for r in db.query("SELECT token FROM shares")] + [r["token"] for r in db.query("SELECT token FROM live_links")]
    auth.q("DELETE FROM share_index WHERE uid=?", (u,))
    for t in toks:
        auth.q("INSERT OR REPLACE INTO share_index(token,uid) VALUES(?,?)", (t, u))


def caches_leeren():
    """Alles im Arbeitsspeicher, was aus der Datenbank berechnet wurde (auch ohne Änderung der Dateizeit sicher neu)."""
    from . import diashow_link, hinweise, memo, plan_check, uhrtraining
    live = str(config.DB_PATH)
    with memo._L:
        for k in [k for k in memo._C if k[0] == live]:
            memo._C.pop(k, None)
    hinweise._CACHE.clear()
    diashow_link._CACHE.clear()
    plan_check._PROF.update(t=0.0, v=None)
    uhrtraining.reset_cache()


def wiederherstellen(pfad, name, upload, sha):
    """Schritt 2. Aufrufer hält extras.BACKUP_LOCK. Gibt das Ergebnis für die Anzeige zurück oder wirft Abgelehnt (dann ist der Stand der alte)."""
    work = _arbeitsordner()
    try:
        if _sha(pfad) != sha:
            raise Abgelehnt("Die Datei hat sich seit der Vorprüfung geändert. Bitte noch einmal prüfen.", 409)
        v = vorbereiten(pfad, name, upload, work)              # alle Prüfungen noch einmal, unmittelbar vor dem Tausch
        vorher = v["zahlen"]["jetzt"]
        zugang = _zugang_lesen()
        kopie = _sicherheitskopie()                            # schlägt sie fehl, wird abgebrochen – noch ist nichts verändert
        fehler = ""
        try:
            einspielen(v["db"])
        except Exception as e:  # noqa
            fehler = f"{e.__class__.__name__}: {str(e)[:160]}"
        fehler = fehler or nachpruefung(v["zahlen"]["sicherung"])
        if fehler:
            ok = _zurueck(kopie, work)
            caches_leeren()
            jobs.log(f"Wiederherstellung aus {name} fehlgeschlagen ({fehler}); Rückfall auf {kopie.name}: {'gelungen' if ok else 'FEHLGESCHLAGEN'}")
            if ok:
                raise Abgelehnt(f"Das Zurückspielen ist fehlgeschlagen. Der vorherige Stand wurde automatisch zurückgeholt, es ist nichts verloren. Grund: {fehler}", 500)
            raise Abgelehnt(f"Das Zurückspielen ist fehlgeschlagen und der vorherige Stand konnte nicht automatisch zurückgeholt werden. "
                            f"Er liegt als Sicherheitskopie vor: {kopie.name}. Bitte diese Datei mit dem Skript auf dem Server zurückspielen. Grund: {fehler}", 500)
        hinweise = []
        behalten = 0
        try:
            behalten = _zugang_behalten(zugang)
            db.put("last_version", config.VERSION)             # die Datenbank ist auf dem heutigen Schema
            _freigaben_abgleichen()
        except Exception as e:  # noqa
            hinweise.append(f"Nacharbeiten unvollständig: {str(e)[:160]}")
        s_neu = g_neu = 0
        try:
            s_neu, g_neu = _ergaenzen(pfad)
        except Exception as e:  # noqa
            hinweise.append(f"Strecken konnten nicht vollständig ergänzt werden: {str(e)[:160]}")
        caches_leeren()
        jobs.log(f"Sicherung zurückgespielt: {name} (Sicherheitskopie: {kopie.name})")
        if upload:
            _weg(Path(pfad)); _weg(Path(pfad).with_suffix(".name"))
        return {"ok": True, "name": name, "vorher": vorher, "nachher": zahlen(), "sicherheitskopie": kopie.name, "strecken_neu": s_neu, "geraete_neu": g_neu,
                "zugangsdaten_behalten": behalten, "hinweise": hinweise}
    finally:
        _weg(work)


# ------------------------------------------------------------------------------------------------ Endpunkte (nur Administratoren; Betrachter scheitern schon in main.auth_mw)
def _http(e):
    return HTTPException(e.status, str(e))


@router.get("/api/restore/list")
def api_list(request: Request):
    extras._admin_only(request)
    aufraeumen()
    u = getattr(request.state, "user", None)
    return {"sicherungen": liste(), "max_mb": MAX_UPLOAD // 1_000_000, "benutzer": u["name"] if u else "", "gueltig_s": TOKEN_TTL}


@router.post("/api/restore/upload")
async def api_upload(request: Request, name: str = ""):
    """ZIP hochladen (Rohdaten im Anfragekörper). Landet nur im temporären Bereich und wird erst nach der Vorprüfung verwendet."""
    extras._admin_only(request)
    zu_gross = HTTPException(413, f"Die Datei ist zu groß (höchstens {MAX_UPLOAD // 1_000_000} MB). Größere Sicherungen bitte in den Sicherungsordner des Servers legen.")
    try:
        if int(request.headers.get("content-length") or 0) > MAX_UPLOAD:
            raise zu_gross
    except ValueError:
        pass
    aufraeumen()
    area = _bereich()
    for alt in list(area.glob("upload-*")):                    # je Benutzer höchstens ein Upload
        _weg(alt)
    key = secrets.token_hex(8)
    part, ziel = area / f"upload-{key}.zip.part", area / f"upload-{key}.zip"
    n = 0
    try:
        with open(part, "wb") as fh:
            async for chunk in request.stream():
                n += len(chunk)
                if n > MAX_UPLOAD:
                    raise zu_gross
                fh.write(chunk)
        if n == 0:
            raise HTTPException(400, "Die Datei ist leer.")
        os.chmod(part, 0o600)
        os.replace(part, ziel)
    finally:
        part.unlink(missing_ok=True)
    anzeige = re.sub(r"[^\w .()+-]", "_", Path(str(name).replace("\\", "/")).name)[:120] or "Hochgeladene Sicherung"
    ziel.with_suffix(".name").write_text(anzeige, encoding="utf-8")
    return {"id": f"u:{key}", "name": anzeige, "groesse": n}


@router.delete("/api/restore/upload")
def api_upload_weg(request: Request):
    """Hochgeladene Datei verwerfen (Dialog geschlossen, andere Quelle gewählt)."""
    extras._admin_only(request)
    for p in list(_bereich().glob("upload-*")):
        _weg(p)
    wer = _wer(request)
    for t, e in list(_tokens.items()):
        if e["wer"] == wer and e["id"].startswith("u:"):
            _tokens.pop(t, None)
    aufraeumen()
    return {"ok": True}


@router.post("/api/restore/check")
def api_check(request: Request, body: dict):
    """Vorprüfung (Trockenlauf): ändert nichts. Liefert Zahlen, Hinweise und das Token für die Bestätigung."""
    extras._admin_only(request)
    aufraeumen()
    work = None
    try:
        pfad, name, upload = _quelle(body.get("id"))
        work = _arbeitsordner()
        sha = _sha(pfad)
        v = vorbereiten(pfad, name, upload, work)
    except Abgelehnt as e:
        raise _http(e)
    finally:
        if work is not None:
            _weg(work)
        aufraeumen()                                           # auch den leeren Ordner des temporären Bereichs wieder entfernen
    v.pop("db")
    tok = secrets.token_urlsafe(24)
    _tokens[tok] = {"wer": _wer(request), "id": str(body.get("id")), "sha": sha, "exp": time.time() + TOKEN_TTL}
    return {**v, "id": str(body.get("id")), "token": tok, "gueltig_s": TOKEN_TTL}


@router.post("/api/restore/run")
def api_run(request: Request, body: dict):
    """Wiederherstellung: nur mit dem Token der Vorprüfung (gleicher Benutzer, gleiche Datei, nicht abgelaufen) und ausdrücklicher Bestätigung."""
    extras._admin_only(request)
    if body.get("bestaetigt") is not True:
        raise HTTPException(400, "Bitte zuerst bestätigen, dass der heutige Stand ersetzt wird.")
    e = _tokens.get(str(body.get("token") or ""))
    if not e or e["exp"] < time.time():
        _tokens.pop(str(body.get("token") or ""), None)
        raise HTTPException(409, "Die Vorprüfung ist abgelaufen. Bitte die Sicherung noch einmal prüfen.")
    if e["wer"] != _wer(request) or e["id"] != str(body.get("id") or ""):
        raise HTTPException(409, "Die Bestätigung gehört nicht zu dieser Sicherung. Bitte die Sicherung noch einmal prüfen.")
    belegt = HTTPException(409, "Es läuft gerade eine Sicherung oder ein anderes Zurückspielen. Bitte gleich noch einmal versuchen.")
    if not extras.BACKUP_LOCK.acquire(blocking=False):
        raise belegt
    try:
        jl = jobs._s()["lock"]                                 # solange zurückgespielt wird, startet für diesen Benutzer kein Hintergrundjob (Abgleich, Import)
        if not jl.acquire(blocking=False):
            raise HTTPException(409, "Es läuft gerade ein Hintergrundjob. Bitte warten, bis er fertig ist, und es dann noch einmal versuchen.")
        try:
            _tokens.pop(str(body.get("token")), None)          # einmal verwendbar
            pfad, name, upload = _quelle(e["id"])
            return wiederherstellen(pfad, name, upload, e["sha"])
        except Abgelehnt as x:
            raise _http(x)
        finally:
            jl.release()
    finally:
        extras.BACKUP_LOCK.release()
        aufraeumen()
