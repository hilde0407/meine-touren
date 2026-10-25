"""Aktivitäten von Garmin- und Suunto-Konten sowie aus Dateien (FIT/GPX/TCX/ZIP) als lokale Touren übernehmen.

Wichtig vorab (Stand 2026):
* Garmin hat für Privatpersonen keine offizielle Schnittstelle. Die Anmeldung geschieht wie im Browser über das
  optionale Paket „garminconnect“ (Python ≥ 3.12). Garmin darf das jederzeit ändern oder bremsen – dann bleibt der
  Dateiweg (Gesamtexport oder einzelne FIT/GPX-Dateien), der immer funktioniert.
* Suunto vergibt API-Zugang nur an Firmen/Organisationen (Partnerprogramm). Wer einen solchen Zugang hat, kann ihn hier
  eintragen. Alle anderen nutzen den Dateiweg (Suunto-App → Training → ⋮ → Exportieren, FIT oder GPX).
* Hängt die Uhr bereits an Komoot (Garmin und Suunto bieten das an), erscheinen die Touren ohnehin über „Komoot aktualisieren“.
Nichts wird je zu Garmin, Suunto oder einem Portal hochgeladen.
"""
import json
import re
import threading
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse

from . import config, ctx, db, fitfile, gpxtools, jobs, portals, sync
from .jobs import log

router = APIRouter()

PAGE = 100
GARMIN_SPORT = {
    "hiking": "hike", "walking": "hike", "casual_walking": "hike", "speed_walking": "hike", "mountaineering": "mountaineering",
    "running": "jogging", "trail_running": "jogging", "treadmill_running": "jogging", "street_running": "jogging",
    "cycling": "touringbicycle", "gravel_cycling": "touringbicycle", "touring": "touringbicycle", "road_biking": "racebike",
    "mountain_biking": "mtb", "e_bike_mountain": "e_touringbicycle", "e_bike_fitness": "e_touringbicycle", "e_touring": "e_touringbicycle",
    "resort_skiing_snowboarding_ws": "skialpin", "resort_skiing": "skialpin", "backcountry_skiing_snowboarding_ws": "skitour",
    "backcountry_skiing": "skitour", "cross_country_skiing_ws": "nordic", "snow_shoe": "snowshoe", "snowshoeing": "snowshoe",
}
SUUNTO_SPORT = {            # Suunto-activityId -> Sportart (nur eindeutige; sonst entscheidet die FIT-Datei)
    1: "jogging", 2: "touringbicycle", 3: "nordic", 11: "hike", 5: "mountaineering", 82: "snowshoe", 21: "skialpin", 22: "skitour",
    23: "skitour", 10: "mtb", 24: "touringbicycle", 25: "racebike",
}


class DeviceError(Exception):
    pass


# --------------------------------------------------------------------------- gemeinsame Übernahme
def _ts_of(v):
    """Zeitangabe (ISO-Text, 'JJJJ-MM-TT hh:mm:ss' UTC, Sekunden oder Millisekunden) -> Unix-Sekunden."""
    if v in (None, ""):
        return 0
    if isinstance(v, (int, float)):
        return int(v / 1000) if v > 1e11 else int(v)
    try:
        return int(gpxtools.parse_time(str(v).replace(" ", "T")).timestamp())
    except Exception:  # noqa
        return 0


def _known(src):
    return {r["ext_id"] for r in db.query("SELECT ext_id FROM ext_imports WHERE src=?", (src,))}


def ingest(src, entries, portals_=()):
    """entries: [(ext_id, gpx_oder_tcx_text, dateiname, name_or_None, sport_or_None)]. Legt lokale Touren an
    (Doppelten-Prüfung wie beim Datei-Import) und merkt sich jede Aktivität, damit sie nicht erneut geladen wird.
    Gibt {'imported': n, 'dup': n, 'nogps': n, 'error': n} zurück."""
    cnt = {"imported": 0, "dup": 0, "nogps": 0, "error": 0}
    if not entries:
        return cnt
    items = [(e[0], e[1], e[2]) for e in entries]
    res = sync.import_items(items, tuple(portals_ or ()), False)
    meta = {e[0]: e for e in entries}
    now = int(time.time())
    for label, state, tid in res:
        e = meta.get(label)
        if state == "no_gps":
            cnt["nogps"] += 1
            db.execute("INSERT OR REPLACE INTO ext_imports VALUES(?,?,?,?,?)", (src, str(label), "", "no_gps", now))
        elif state in ("imported", "uploaded"):
            cnt["imported"] += 1
            if tid and e:
                if e[3]:
                    db.execute("UPDATE tours SET name=? WHERE id=?", (e[3], tid))
                if e[4] and e[4] in gpxtools.LABEL:
                    db.execute("UPDATE tours SET sport=? WHERE id=?", (e[4], tid))
            db.execute("INSERT OR REPLACE INTO ext_imports VALUES(?,?,?,?,?)", (src, str(label), tid, "imported", now))
        elif state == "skipped_dup":
            cnt["dup"] += 1
            db.execute("INSERT OR REPLACE INTO ext_imports VALUES(?,?,?,?,?)", (src, str(label), tid, "dup", now))
        else:
            cnt["error"] += 1
    return cnt


def _sum(cnt, what=""):
    log(f"{what}: {cnt['imported']} neu · {cnt['dup']} schon vorhanden · {cnt['nogps']} ohne GPS" + (f" · {cnt['error']} Fehler" if cnt["error"] else ""))


# --------------------------------------------------------------------------- Dateien (FIT/GPX/TCX/ZIP)
def import_paths(paths, portals_=(), dry_run=False):
    """Dateien oder ZIP-Archive (auch Garmin-Gesamtexport) lesen und übernehmen. Arbeitet stückweise (wenig Speicher)."""
    tot = {"imported": 0, "dup": 0, "nogps": 0, "error": 0, "bad": 0, "files": 0}
    batch = []

    def flush():
        nonlocal batch
        if not batch:
            return
        if dry_run:
            res = sync.import_items([(a, b, c) for a, b, c, *_ in batch], (), True)
            tot["imported"] += sum(1 for _, s, _ in res if s == "would_upload")
            tot["dup"] += sum(1 for _, s, _ in res if s == "skipped_dup")
            tot["nogps"] += sum(1 for _, s, _ in res if s == "no_gps")
        else:
            c = ingest("datei", batch, portals_)
            for k in ("imported", "dup", "nogps", "error"):
                tot[k] += c[k]
        batch = []

    for path in paths:
        try:
            for name, text, kind in fitfile.iter_expand(str(path)):
                tot["files"] += 1
                jobs.progress(f"{tot['files']} Datei(en) gelesen")
                if kind == "bad":
                    tot["bad"] += 1; continue
                if kind == "nogps":
                    tot["nogps"] += 1; continue
                nm = Path(name).name
                known = db.one("SELECT 1 x FROM ext_imports WHERE src='datei' AND ext_id=?", (nm + ":" + str(len(text)),))
                if known and not dry_run:
                    tot["dup"] += 1; continue
                batch.append((nm + ":" + str(len(text)), text, nm, None, None))
                if len(batch) >= 40:
                    flush()
        except ValueError as e:
            log(f"{Path(path).name}: {e}")
            tot["bad"] += 1
        except Exception as e:  # noqa
            log(f"{Path(path).name}: {e}")
            tot["bad"] += 1
    flush()
    log(f"Dateien: {tot['files']} gelesen → {tot['imported']} " + ("wären neu" if dry_run else "neu übernommen") +
        f" · {tot['dup']} schon vorhanden · {tot['nogps']} ohne GPS" + (f" · {tot['bad']} unlesbar" if tot["bad"] else ""))
    if not dry_run:
        from . import photos
        photos.assign_all()
    return tot


def import_inbox_activities():
    """Dateien im Eingangsordner „touren“ (FIT/GPX/TCX/ZIP) übernehmen und nach „touren/erledigt“ verschieben.
    Praktisch für große Garmin-Exporte: ZIP einfach in den Ordner legen."""
    root = config.INBOX_DIR / "touren"
    if not root.is_dir():
        return 0
    files = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in (".fit", ".gpx", ".tcx", ".zip", ".gz")]
    if not files:
        return 0
    done = root / "erledigt"
    done.mkdir(exist_ok=True)
    tot = import_paths(files)
    for p in files:
        try:
            p.replace(done / p.name)
        except OSError:
            pass
    return tot["imported"]


# --------------------------------------------------------------------------- Garmin
_pending = {}            # uid -> (Garmin-Objekt, client_state, Zeit)  (Mehrfaktor-Anmeldung, nur im Speicher)
_plock = threading.Lock()


def garmin_module():
    try:
        import garminconnect
        return garminconnect
    except Exception as e:  # noqa
        raise DeviceError("Das Zusatzpaket „garminconnect“ ist nicht installiert (braucht Python 3.12 oder neuer). "
                          "Installation: pip install garminconnect curl_cffi im Programm-venv – oder den Dateiweg nutzen "
                          f"(Garmin-Gesamtexport als ZIP importieren). Technisch: {e}")


def garmin_available():
    try:
        garmin_module(); return True, ""
    except DeviceError as e:
        return False, str(e)


def _garmin_err(e):
    s = str(e)
    low = s.lower()
    if "429" in s or "too many" in low or "rate" in low:
        return "Garmin bremst gerade (zu viele Anfragen, HTTP 429). Bitte später (in einigen Stunden) erneut versuchen."
    if "401" in s or "credential" in low or "password" in low or "authentication" in low or "unauthorized" in low:
        return "Garmin hat die Anmeldung abgelehnt (E-Mail/Passwort prüfen). Mit Google-/Apple-Login gibt es kein Garmin-Passwort – dann den Dateiweg nutzen."
    return "Garmin-Anmeldung fehlgeschlagen: " + s[:200]


def garmin_login(email, password):
    """Gibt {'ok': True} oder {'mfa': True} zurück; bei Fehlern DeviceError."""
    g = garmin_module()
    cl = g.Garmin(email, password, return_on_mfa=True)
    try:
        status, state = cl.login()
    except Exception as e:  # noqa
        raise DeviceError(_garmin_err(e))
    if status == "needs_mfa":
        with _plock:
            _pending[ctx.uid()] = (cl, state, time.time(), email)
        return {"mfa": True}
    _garmin_save(cl, email)
    return {"ok": True}


def garmin_mfa(code):
    with _plock:
        p = _pending.get(ctx.uid())
    if not p or time.time() - p[2] > 600:
        raise DeviceError("Die Anmeldung ist abgelaufen – bitte E-Mail und Passwort erneut senden.")
    cl, state, _, email = p
    try:
        cl.resume_login(state, str(code).strip())
    except Exception as e:  # noqa
        raise DeviceError("Code abgelehnt oder abgelaufen: " + str(e)[:160])
    with _plock:
        _pending.pop(ctx.uid(), None)
    _garmin_save(cl, email)
    return {"ok": True}


def _garmin_save(cl, email=None):
    db.put("garmin_tokens", cl.client.dumps())
    if email:
        db.put("garmin_email", email)


def garmin_connected():
    return bool(db.get("garmin_tokens"))


def _garmin_client():
    g = garmin_module()
    tok = db.get("garmin_tokens")
    if not tok:
        raise DeviceError("Garmin ist nicht verbunden (Verwaltung → Garmin).")
    cl = g.Garmin()
    try:
        cl.login(tok)
    except Exception as e:  # noqa
        raise DeviceError("Die gespeicherte Garmin-Anmeldung ist abgelaufen – bitte neu verbinden. " + _garmin_err(e))
    return cl


def _since_ts(key):
    v = (db.get(key) or "").strip()
    if not v:
        return 0
    try:
        return int(datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=gpxtools.TZ).timestamp())
    except ValueError:
        return 0


def garmin_sync(limit=None):
    cl = _garmin_client()
    since = _since_ts("garmin_since")
    known = _known("garmin")
    new, start, stop = [], 0, False
    while not stop:
        page = cl.get_activities(start, PAGE)
        if isinstance(page, dict):
            page = page.get("activities") or []
        if not page:
            break
        all_known = True
        for a in page:
            ts = _ts_of(a.get("startTimeGMT") or a.get("startTimeLocal"))
            if since and ts and ts < since:
                stop = True; break
            if str(a.get("activityId")) in known:
                continue
            all_known = False
            if a.get("hasPolyline") is False:                       # drinnen, ohne GPS
                db.execute("INSERT OR REPLACE INTO ext_imports VALUES('garmin',?,?,?,?)", (str(a["activityId"]), "", "no_gps", int(time.time())))
                continue
            new.append(a)
        if all_known or len(page) < PAGE:
            break
        start += PAGE
        jobs.progress(f"{len(new)} neue Aktivitäten gefunden …")
        time.sleep(0.5)
    if limit:
        new = new[:limit]
    log(f"Garmin: {len(new)} neue Aktivitäten mit Strecke")
    tot = {"imported": 0, "dup": 0, "nogps": 0, "error": 0}
    blocked = False
    for i in range(0, len(new), 20):
        if blocked:
            break
        chunk, entries = new[i:i + 20], []
        for a in chunk:
            aid = a["activityId"]
            jobs.progress(f"Garmin {len(entries) + i + 1}/{len(new)}")
            try:
                got = _garmin_download(cl, aid)
            except Exception as e:  # noqa
                msg = _garmin_err(e)
                log(f"  Aktivität {aid}: {msg}")
                tot["error"] += 1
                if "bremst" in msg:
                    blocked = True
                    break
                continue
            if not got:
                db.execute("INSERT OR REPLACE INTO ext_imports VALUES('garmin',?,?,?,?)", (str(aid), "", "no_gps", int(time.time())))
                tot["nogps"] += 1
                continue
            tk = ((a.get("activityType") or {}).get("typeKey") or "").lower()
            nm = a.get("activityName")
            entries.append((str(aid), got[0], got[1], nm if nm and not nm.startswith("Garmin") else None, GARMIN_SPORT.get(tk)))
            time.sleep(0.8)
        c = ingest("garmin", entries)
        for k in c:
            tot[k] += c[k]
    db.put("garmin_checked", str(int(time.time())))
    _garmin_refresh_tokens(cl)
    _sum(tot, "Garmin")
    from . import photos
    photos.assign_all()
    return tot


def _garmin_refresh_tokens(cl):
    try:
        db.put("garmin_tokens", cl.client.dumps())
    except Exception:  # noqa
        pass


def _garmin_download(cl, aid):
    """(text, dateiname) der Aktivität oder None, wenn sie keine Strecke hat."""
    fmt = cl.ActivityDownloadFormat
    data = cl.download_activity(aid, dl_fmt=fmt.ORIGINAL)
    for name, text, kind in fitfile.iter_expand(f"{aid}.zip", bytes(data)):
        if kind in ("fit", "gpx"):
            return text, f"{aid}.gpx"
    data = cl.download_activity(aid, dl_fmt=fmt.GPX)                  # Rückfall, falls das Original keine Strecke enthält
    txt = bytes(data).decode("utf-8", "replace")
    return (txt, f"{aid}.gpx") if "<trkpt" in txt else None


# --------------------------------------------------------------------------- Suunto (offizielle Cloud-API, nur mit Partnerzugang)
SU_OAUTH = "https://cloudapi-oauth.suunto.com"
SU_API = "https://cloudapi.suunto.com"


def suunto_configured():
    return bool(db.get("suunto_client_id") and db.get("suunto_client_secret") and db.get("suunto_key"))


def suunto_tokens():
    try:
        return json.loads(db.get("suunto_tokens") or "{}")
    except ValueError:
        return {}


def suunto_connected():
    return bool(suunto_tokens().get("refresh_token") or suunto_tokens().get("access_token"))


def _su_token(data):
    r = requests.post(f"{SU_OAUTH}/oauth/token", data=data, auth=(db.get("suunto_client_id"), db.get("suunto_client_secret")), timeout=30)
    if r.status_code != 200:
        raise DeviceError(f"Suunto lehnt die Anmeldung ab (HTTP {r.status_code}). Client-ID/-Secret und Weiterleitungsadresse in der API Zone prüfen.")
    j = r.json()
    old = suunto_tokens()
    new = {"access_token": j.get("access_token"), "refresh_token": j.get("refresh_token") or old.get("refresh_token"),
           "expires_at": int(time.time()) + int(j.get("expires_in") or 3600) - 120}
    db.put("suunto_tokens", json.dumps(new))
    return new


def suunto_auth_url(redirect):
    if not (db.get("suunto_client_id") and db.get("suunto_client_secret")):
        raise DeviceError("Suunto: Client-ID und Client-Secret eintragen und speichern.")
    return f"{SU_OAUTH}/oauth/authorize?" + urllib.parse.urlencode({"response_type": "code", "client_id": db.get("suunto_client_id"), "redirect_uri": redirect})


def suunto_exchange(code, redirect):
    return _su_token({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect})


def _su_access():
    t = suunto_tokens()
    if not t:
        raise DeviceError("Suunto ist nicht verbunden (Verwaltung → Suunto).")
    if t.get("expires_at", 0) < time.time() and t.get("refresh_token"):
        t = _su_token({"grant_type": "refresh_token", "refresh_token": t["refresh_token"]})
    return t["access_token"]


def _su_get(path, params=None, raw=False):
    tok = _su_access()
    for auth in (f"Bearer {tok}", tok):                      # die Dokumentation zeigt beide Schreibweisen
        r = requests.get(SU_API + path, params=params, timeout=60, headers={"Authorization": auth, "Ocp-Apim-Subscription-Key": db.get("suunto_key") or ""})
        if r.status_code != 401:
            break
    if r.status_code == 429:
        raise DeviceError("Suunto bremst gerade (HTTP 429) – später erneut versuchen.")
    if r.status_code in (401, 403):
        raise DeviceError("Suunto: Zugriff verweigert – Subscription-Key prüfen bzw. Suunto neu verbinden.")
    if r.status_code != 200:
        raise DeviceError(f"Suunto-Anfrage {path} fehlgeschlagen (HTTP {r.status_code}).")
    return r.content if raw else r.json()


def suunto_sync(limit=None):
    if not suunto_configured():
        raise DeviceError("Suunto: Client-ID, Client-Secret und Subscription-Key eintragen.")
    since = _since_ts("suunto_since")
    known = _known("suunto")
    new, offset = [], 0
    while True:
        j = _su_get("/v2/workouts", {"since": since * 1000, "limit": PAGE, "offset": offset})
        page = j.get("payload") if isinstance(j, dict) else j
        if not page:
            break
        for w in page:
            key = str(w.get("workoutKey") or w.get("workoutId") or "")
            if key and key not in known:
                new.append(w)
        if len(page) < PAGE:
            break
        offset += PAGE
        time.sleep(0.5)
    if limit:
        new = new[:limit]
    log(f"Suunto: {len(new)} neue Workouts")
    tot = {"imported": 0, "dup": 0, "nogps": 0, "error": 0}
    for i in range(0, len(new), 20):
        entries = []
        for w in new[i:i + 20]:
            key = str(w.get("workoutKey") or w.get("workoutId"))
            jobs.progress(f"Suunto {i + len(entries) + 1}/{len(new)}")
            try:
                data = _su_get(f"/v2/workout/exportFit/{urllib.parse.quote(key, safe='')}", raw=True)
            except DeviceError as e:
                log(f"  Workout {key}: {e}")
                tot["error"] += 1
                if "bremst" in str(e):
                    break
                continue
            got = next(((t, k) for n, t, k in fitfile.iter_expand(f"{key}.fit", bytes(data)) if k in ("fit", "gpx")), None)
            if not got:
                db.execute("INSERT OR REPLACE INTO ext_imports VALUES('suunto',?,?,?,?)", (key, "", "no_gps", int(time.time())))
                tot["nogps"] += 1
                continue
            entries.append((key, got[0], f"{key}.gpx", None, SUUNTO_SPORT.get(int(w.get("activityId") or -1))))
            time.sleep(0.5)
        c = ingest("suunto", entries)
        for k in c:
            tot[k] += c[k]
    db.put("suunto_checked", str(int(time.time())))
    _sum(tot, "Suunto")
    from . import photos
    photos.assign_all()
    return tot


# --------------------------------------------------------------------------- tägliche Automatik
def auto_sync():
    """Aus der täglichen Aktualisierung: Konten, bei denen „automatisch“ aktiv ist. Fehler brechen nichts anderes ab."""
    if db.get("garmin_auto") == "1" and garmin_connected():
        try:
            garmin_sync()
        except Exception as e:  # noqa
            log(f"Garmin (automatisch): {e}")
    if db.get("suunto_auto") == "1" and suunto_connected():
        try:
            suunto_sync()
        except Exception as e:  # noqa
            log(f"Suunto (automatisch): {e}")
    try:
        import_inbox_activities()
    except Exception as e:  # noqa
        log(f"Tourendateien im Eingang: {e}")


# --------------------------------------------------------------------------- API
def _redirect(request: Request, name):
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}/api/{name}/callback"


@router.get("/api/devices")
def api_devices(request: Request):
    ok, why = garmin_available()
    cnt = lambda s: (db.one("SELECT COUNT(*) n FROM ext_imports WHERE src=? AND status='imported'", (s,)) or {"n": 0})["n"]
    return {
        "garmin": {"available": ok, "why": why, "connected": garmin_connected(), "email": db.get("garmin_email") or "",
                   "imported": cnt("garmin"), "checked": db.get("garmin_checked") or ""},
        "suunto": {"configured": suunto_configured(), "connected": suunto_connected(), "imported": cnt("suunto"),
                   "checked": db.get("suunto_checked") or "", "redirect": _redirect(request, "suunto")},
        "files": cnt("datei"),
    }


@router.post("/api/garmin/login")
def api_garmin_login(body: dict):
    em, pw = (body.get("email") or "").strip(), body.get("password") or ""
    if not em or not pw:
        raise HTTPException(400, "E-Mail und Passwort eingeben")
    try:
        return garmin_login(em, pw)
    except DeviceError as e:
        raise HTTPException(400, str(e))


@router.post("/api/garmin/mfa")
def api_garmin_mfa(body: dict):
    try:
        return garmin_mfa(body.get("code", ""))
    except DeviceError as e:
        raise HTTPException(400, str(e))


@router.post("/api/garmin/disconnect")
def api_garmin_disconnect():
    db.put("garmin_tokens", "")
    return {"ok": True}


@router.post("/api/garmin/sync")
def api_garmin_sync(limit: int = 0):
    if not garmin_connected():
        raise HTTPException(400, "Garmin ist nicht verbunden")
    if not jobs.start("Garmin-Import", lambda: garmin_sync(limit or None)):
        raise HTTPException(409, "Es läuft bereits ein Job")
    return {"started": True}


@router.get("/api/suunto/connect")
def api_suunto_connect(request: Request):
    try:
        return {"url": suunto_auth_url(_redirect(request, "suunto")), "redirect": _redirect(request, "suunto")}
    except DeviceError as e:
        raise HTTPException(400, str(e))


@router.get("/api/suunto/callback")
def api_suunto_callback(request: Request, code: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse("/#/admin?suunto=abgelehnt")
    try:
        suunto_exchange(code, _redirect(request, "suunto"))
    except Exception as e:  # noqa
        return RedirectResponse("/#/admin?suunto=" + urllib.parse.quote(str(e)[:120]))
    return RedirectResponse("/#/admin?suunto=ok")


@router.post("/api/suunto/disconnect")
def api_suunto_disconnect():
    db.put("suunto_tokens", "")
    return {"ok": True}


@router.post("/api/suunto/sync")
def api_suunto_sync(limit: int = 0):
    if not suunto_connected():
        raise HTTPException(400, "Suunto ist nicht verbunden")
    if not jobs.start("Suunto-Import", lambda: suunto_sync(limit or None)):
        raise HTTPException(409, "Es läuft bereits ein Job")
    return {"started": True}


@router.post("/api/import-activity-files")
async def api_import_activity_files(files: list[UploadFile] = File(...), dry_run: bool = False, portals_: str = Query("", alias="portals")):
    """FIT/GPX/TCX/ZIP-Dateien (z. B. Garmin-Gesamtexport, Suunto-Export) – wird in eine Datei gestreamt, nicht in den Speicher geladen."""
    tmp = config.user_dir(ctx.uid()) / "upload-tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, f in enumerate(files):
        dest = tmp / f"{int(time.time())}-{i}-{re.sub(r'[^A-Za-z0-9._-]', '_', f.filename or 'datei')}"
        with open(dest, "wb") as out:
            while chunk := await f.read(1024 * 1024):
                out.write(chunk)
        saved.append(dest)
    ps = tuple(p for p in portals_.split(",") if p in portals.PORTALS)

    def work():
        try:
            import_paths(saved, ps, dry_run)
        finally:
            for p in saved:
                p.unlink(missing_ok=True)

    if not jobs.start("Datei-Import", work):
        for p in saved:
            p.unlink(missing_ok=True)
        raise HTTPException(409, "Es läuft bereits ein Job")
    return {"started": len(saved)}
