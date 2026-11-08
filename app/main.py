import asyncio
import base64
import contextvars
import os
import re
import hmac
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from . import auth, gear, health, pdfgen, gpxtools, plan, uipw, config, ctx, db, devices, elev, extras, jobs, more, more2, photos, portals, routes, stats, sync, tracks, updater, users_api, security, zepp
from .gpxtools import TZ

STATIC = Path(__file__).parent / "static"
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    startup()
    yield


app = FastAPI(title="Meine Touren", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def no_stale_static(request: Request, call_next):
    r = await call_next(request)
    p = request.url.path
    if not p.startswith(("/photo/", "/pic/", "/api/")) and "cache-control" not in r.headers:
        r.headers["Cache-Control"] = "no-cache"      # Browser prüft bei jedem Aufruf auf neue Programmdateien
    return r


VIEWER_GET = re.compile(
    r"^(/api/(me|version|tour-covers|routes|photos|photo-info|collection/coords|trips|stats|workouts|places|repeats|tags|newground|goals|live|settings"
    r"|tours|tours/[^/]+|tours/[^/]+/(coords|best-photos|weather|gpx)|trips/[^/]+|records/altitude|weather/stats)"
    r"|/photo/[^/]+|/pic/[^/]+|/tiles/.+)$")
OPEN_API = ("/api/version", "/api/me", "/api/login", "/api/logout", "/api/setup", "/api/zepp-token", "/api/forgot", "/api/reset")
PROTECTED = ("/api/", "/photo/", "/sphoto/", "/pic/", "/spic/")


@app.middleware("http")
async def auth_mw(request: Request, call_next):
    path = request.url.path
    request.state.user = None
    public = path.startswith(more2.PUBLIC_PREFIXES) or path == "/share.html"
    if not auth.users_exist():
        # Altbetrieb ohne Benutzer: wie bisher, optional mit einem gemeinsamen Passwort (UI_PASSWORD)
        if uipw.is_set() and not public:
            ok = False
            h = request.headers.get("authorization", "")
            if h.lower().startswith("basic "):
                try:
                    _, _, p = base64.b64decode(h[6:]).decode().partition(":")
                    ok = uipw.check(p)
                except Exception:  # noqa
                    ok = False
            if not ok:
                return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Meine Touren"'})
        return await call_next(request)
    u = auth.session_user(request.cookies.get(auth.COOKIE))
    if u and u["role"] == "viewer":
        # Betrachter: sieht die Daten eines Benutzers, darf aber nichts ändern und nur Touren, Fotos und Standort abrufen
        owner = auth.viewer_owner(u["uid"])
        if not owner or not auth.q1("SELECT 1 x FROM users WHERE uid=? AND active=1", (owner,)):
            return JSONResponse({"detail": "Dieser Zugang ist keinem Benutzer zugeordnet"}, status_code=403)
        request.state.user = u
        if path.startswith(("/api/", "/photo/", "/pic/", "/tiles/")) and path != "/api/login":
            ok = (request.method in ("GET", "HEAD") and bool(VIEWER_GET.match(path))) or path in ("/api/logout", "/api/me")
            if not ok:
                return JSONResponse({"detail": "Dieser Zugang darf nur ansehen"}, status_code=403)
        ctx._uid.set(owner)
    elif u:
        request.state.user = u
        ctx._uid.set(u["uid"])
    elif path.startswith(PROTECTED) and not path.startswith(OPEN_API) and not public:
        return JSONResponse({"detail": "Bitte anmelden"}, status_code=401)
    return await call_next(request)


def startup():
    auth.load_first()
    for u in auth.active_uids():
        with ctx.as_user(u):
            db.init()
            config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    if os.environ.get("MT_DEMO") == "1":              # Demo-Modus: Beispieldaten anlegen, falls noch leer
        from . import demo
        for u in auth.active_uids():
            with ctx.as_user(u):
                demo.seed()
    if os.environ.get("MT_NO_SCHEDULER") != "1":      # Tests: kein Hintergrundplaner (würde nach 60 s Sicherungen anlegen)
        threading.Thread(target=scheduler, daemon=True).start()
        threading.Thread(target=_warm_all, daemon=True).start()


def _user_tick(tick, now, last_day):
    if tick % 5 == 0:                      # alle 5 Minuten: neue Fotos im Eingangsordner?
        newest = sync.inbox_newest()
        if newest and str(newest) != (db.get("inbox_seen") or "") and time.time() - newest > 90:
            if jobs.start("Fotos aus Eingang", sync.import_inbox):
                db.put("inbox_seen", str(newest))
    if (tick == 2 or tick % 360 == 5) and db.get("update_check") != "0":      # alle 6 Stunden: neue Version auf GitHub?
        health.update_check()
    if tick == 1:                          # neue Programmversion: gleich eine Sicherung anlegen
        extras.backup_on_update()
    if tick % 10 == 1:                     # fehlt eine Sicherung der letzten 23 Stunden, selbst eine anlegen
        extras.auto_backup()
    if tick % 60 == 20:                    # stündlich: Warnungen per Webhook melden (nur wenn eingerichtet)
        more2.notify_check()
    if db.get("auto_sync") == "1" and now.hour == db.get_int("auto_sync_hour", 3) and last_day != now.date():
        if jobs.start("Tägliche Aktualisierung", sync.refresh_all):
            return now.date()
    return last_day


def _warm_all():
    """Nach dem Start (und dann alle 3 Stunden) Vorschaubilder und Wiederholungs-Auswertung vorbereiten."""
    time.sleep(20)
    while True:
        for u in auth.active_uids():
            try:
                with ctx.as_user(u):
                    more.api_repeats()
                    photos.warm_thumbs()
            except Exception:  # noqa
                pass
        time.sleep(3 * 3600)


def scheduler():
    last_day, tick = {}, 0
    while True:
        time.sleep(60)
        tick += 1
        now = datetime.now(TZ)
        for u in auth.active_uids():
            try:
                with ctx.as_user(u):
                    last_day[u] = _user_tick(tick, now, last_day.get(u))
            except Exception as e:  # noqa
                with ctx.as_user(u):
                    jobs.log(f"Zeitplaner: {e}")
        try:
            if tick % 1440 == 7:
                extras.prune_tiles()
            if tick % 1440 == 11:
                auth.q("DELETE FROM sessions WHERE exp<?", (int(time.time()),))
        except Exception:  # noqa
            pass


# ---------- Einstellungen ----------
@app.get("/api/settings")
def get_settings(request: Request):
    u = getattr(request.state, "user", None)
    if u and u["role"] == "viewer":
        return {"pdf_photos": db.get("pdf_photos"), "pdf_photo_n": db.get("pdf_photo_n"), "plan_enabled": "0"}
    out = {}
    for k in config.DEFAULTS:
        v = db.get(k)
        out[k] = ("***" if v else "") if k in config.SECRET_KEYS else v
    return out


@app.post("/api/settings")
async def set_settings(request: Request):
    data = await request.json()
    for k, v in data.items():
        if k not in config.DEFAULTS:
            continue
        if k in config.SECRET_KEYS and v == "***":
            continue
        db.put(k, v)
    return {"ok": True}


# ---------- Zepp-Token ----------
def _token_page(msg, ok):
    color = "#2f6b4f" if ok else "#c0392b"
    return HTMLResponse(f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Zepp-Token</title><body style="font:16px system-ui;max-width:560px;margin:12vh auto;padding:0 16px">
<h2 style="color:{color}">{msg}</h2><p><a href="/#cfg">Zurück zu Meine Touren</a></p></body>""")


@app.post("/api/zepp-token")
async def zepp_token_form(request: Request):
    """Wird vom Lesezeichen (Bookmarklet) per Formular aufgerufen oder per JSON/Formular von der Oberfläche."""
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        form = await request.json()
    else:
        form = await request.form()
    if auth.users_exist() and not request.state.user:
        # Lesezeichen kommt von einer fremden Seite (ohne Anmelde-Cookie): Benutzerschlüssel prüfen
        u, k = str(form.get("u", "")), str(form.get("k", ""))
        with ctx.as_user(u):
            good = bool(k) and hmac.compare_digest(db.get("zepp_key") or "x", k)
        if not good:
            return _token_page("Das Lesezeichen ist ungültig oder abgelaufen – bitte in der Verwaltung neu anlegen.", False)
        ctx._uid.set(u)
    token = str(form.get("token", "")).strip()
    if len(token) < 40:
        return _token_page("Kein gültiges Token empfangen.", False)
    db.put("zepp_token", token); db.put("zepp_token_ts", str(int(time.time())))
    try:
        host, n = zepp.ZeppApi(token, db.get("zepp_host")).ping()
        return _token_page(f"Token gespeichert und geprüft ✓ (Server {host})", True)
    except Exception as e:  # noqa
        return _token_page(f"Token gespeichert, aber die Prüfung schlug fehl: {e}", False)


@app.get("/api/zepp-key")
def zepp_key(request: Request):
    """Schlüssel für das Zepp-Lesezeichen (je Benutzer)."""
    k = db.get("zepp_key")
    if not k:
        import secrets
        k = secrets.token_urlsafe(18); db.put("zepp_key", k)
    return {"u": ctx.uid() or "", "k": k}


@app.post("/api/zepp-token/test")
def zepp_token_test():
    token = db.get("zepp_token")
    if not token:
        raise HTTPException(400, "Kein Token gespeichert")
    try:
        host, n = zepp.ZeppApi(token, db.get("zepp_host")).ping()
    except Exception as e:  # noqa
        raise HTTPException(502, str(e))
    return {"ok": True, "host": host}


# ---------- Dashboard / Touren ----------
@app.get("/api/stats")
def api_stats():
    return stats.compute()


@app.get("/api/tours")
def api_tours(year: int = 0, q: str = "", limit: int = 20000):
    rows = db.query(
        "SELECT t.*, (SELECT COUNT(*) FROM photos p WHERE p.tour_id=t.id) AS photos, (SELECT note FROM tour_notes n WHERE n.id=t.id) AS note, (SELECT stars FROM tour_rating r WHERE r.id=t.id) AS stars, (SELECT orig_up FROM elev_fix e WHERE e.id=t.id) AS fix_up, (SELECT group_concat(tag, '|') FROM tour_tags x WHERE x.id=t.id) AS tags, g.country AS g_country, g.state AS g_state, g.county AS g_county, g.place AS g_place FROM tours t LEFT JOIN tour_geo g ON g.id=t.id "
        "WHERE t.start_ts IS NOT NULL ORDER BY t.start_ts DESC LIMIT ?", (limit,))
    out = []
    for t in rows:
        d = datetime.fromtimestamp(t["start_ts"], tz=TZ)
        if year and d.year != year:
            continue
        if q and q.lower() not in (t["name"] or "").lower():
            continue
        t["date"] = d.isoformat()
        t["sport_de"] = stats.SPORT_DE.get(t["sport"], t["sport"])
        out.append(t)
    if out:
        more.warm_repeats()               # Wiederholungs-Auswertung schon vorrechnen, während die Seite lädt
    return out


@app.post("/api/tours/{tour_id}/rename")
def api_rename(tour_id: str, body: dict):
    try:
        k, msg = sync.rename_tour(tour_id, body.get("name", ""), bool(body.get("komoot")))
    except KeyError:
        raise HTTPException(404, "Tour nicht gefunden")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "komoot": k, "warning": msg}


@app.post("/api/tours/{tour_id}/sync")
def api_sync_tour(tour_id: str):
    try:
        return sync.sync_tour(tour_id)
    except KeyError:
        raise HTTPException(404, "Tour nicht gefunden")
    except Exception as e:  # noqa
        raise HTTPException(502, str(e))


@app.get("/api/tours/{tour_id}/coords")
def api_coords(tour_id: str):
    data = routes.load(tour_id)
    if data is None:
        gf = tracks.gpx_file(tour_id)
        if gf.exists():                      # lokale Tour: Strecke aus der gespeicherten GPX-Datei wiederherstellen
            return routes.store(tour_id, tracks.points_from_gpx(gf.read_text(encoding="utf-8")))
        row = db.one("SELECT source FROM tours WHERE id=?", (tour_id,))
        if not row:
            raise HTTPException(404, "Tour nicht gefunden")
        if row["source"] == "local":
            raise HTTPException(404, "Keine Streckenpunkte")
        if not (db.get("komoot_email") and db.get("komoot_password")):
            raise HTTPException(404, "Strecke nicht lokal vorhanden und kein Komoot-Zugang eingetragen")
        items = None
        for fresh in (False, True):          # beim zweiten Versuch neu bei Komoot anmelden
            try:
                items = sync._komoot(fresh).coordinates(tour_id)
                break
            except Exception as e:  # noqa
                err = e
        if items is None:
            raise HTTPException(502, str(err))
        if not items:
            raise HTTPException(404, "Keine Streckenpunkte")
        data = routes.store(tour_id, items)
    return data


@app.post("/api/ui-password")
def api_ui_password(body: dict, request: Request):
    """Gemeinsames Oberflächenpasswort setzen, ändern oder (leer) aufheben. Nur im Betrieb ohne Benutzerverwaltung."""
    if auth.users_exist():
        raise HTTPException(409, "Mit Benutzerverwaltung melden sich Benutzer mit ihrem eigenen Passwort an.")
    pw = str(body.get("password") or "")
    if pw and len(pw) < 6:
        raise HTTPException(400, "Das Passwort braucht mindestens 6 Zeichen")
    try:
        uipw.set_password(pw)
    except PermissionError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "protected": uipw.is_set()}


@app.get("/api/version")
def api_version():
    return {"version": config.VERSION}


@app.get("/api/status")
def api_status():
    n = len(list(routes.D.glob("*.s.json"))) if routes.D.exists() else 0
    return {"tours": db.one("SELECT COUNT(*) n FROM tours")["n"], "local_tours": db.one("SELECT COUNT(*) n FROM tours WHERE source='local'")["n"], "routes": n, "protected": uipw.is_set(), "ui_pw_env": uipw.env_set(), "users": auth.users_exist(), "version": config.VERSION,
            "zepp": {"state": db.get("zepp_state") or "", "checked": db.get("zepp_checked") or "", "token_ts": db.get("zepp_token_ts") or ""},
            "inbox": str(config.INBOX_DIR), "app_name": config.APP_NAME, "backup_dir": str(config.BACKUP_ROOT)}


@app.get("/api/routes")
def api_routes(request: Request):
    """Vereinfachte Linien aller zwischengespeicherten Touren für die Gesamtkarte (mit ETag: bei unveränderten Daten 304)."""
    body, etag = routes.overview_bytes()
    h = {"ETag": etag, "Cache-Control": "private, no-cache"}
    if etag in (request.headers.get("if-none-match") or ""):
        return Response(status_code=304, headers=h)
    return Response(body, media_type="application/json", headers=h)


@app.get("/api/diag/coords")
def api_diag_coords():
    """Prüft, ob Komoot Streckenpunkte liefert (für die Fehlersuche)."""
    t = db.one("SELECT id FROM tours ORDER BY start_ts DESC LIMIT 1")
    if not t:
        raise HTTPException(400, "Noch keine Touren geladen")
    k = sync._komoot()
    items = k.coordinates(t["id"])
    return {"tour": t["id"], "punkte": len(items)}


# ---------- Workouts / Jobs ----------
@app.get("/api/workouts")
def api_workouts():
    rows = db.query("SELECT * FROM workouts ORDER BY start_ts DESC")
    for r in rows:
        r["date"] = datetime.fromtimestamp(r["start_ts"], tz=TZ).isoformat()
        r["uploads"] = {k: v["status"] for k, v in portals.status_of(f"z{r['trackid']}").items()}
    return rows


@app.post("/api/workouts/adopt")
def api_workouts_adopt(body: dict):
    """Gewählte Zepp-Trainings lokal als Tour übernehmen (kein Upload)."""
    out = []
    for t in body.get("trackids", []):
        try:
            out.append(sync.adopt_workout(int(t)))
        except Exception as e:  # noqa
            raise HTTPException(400, str(e))
    photos.assign_all()
    return {"tours": out}


JOBS = {
    "refresh": ("Komoot aktualisieren", lambda dry: sync.refresh_all()),
    "tours": ("Komoot-Touren laden", lambda dry: (sync.refresh_tours(), photos.assign_all())),
    "routes": ("Routen laden", lambda dry: routes.fetch_missing(sync._komoot())),
    "geo": ("Regionen bestimmen", lambda dry: extras.geo_fill()),
    "peaks": ("Gipfel bestimmen", lambda dry: more.peaks_fill()),
    "weather": ("Wetter laden", lambda dry: more2.weather_fill()),
    "photos": ("Fotos indizieren", lambda dry: photos.scan()),
    "photo-import": ("Fotos übernehmen", lambda dry: (photos.import_from(), photos.scan())),
    "elev-local": ("Höhenmeter lokaler Touren neu berechnen", lambda dry: elev.recompute_local()),
    "export": ("Zepp-Import (ohne Upload)", lambda dry: sync.export_zepp()),
}


@app.post("/api/jobs/{name}")
def api_job(name: str, dry_run: bool = False):
    if name not in JOBS:
        raise HTTPException(404)
    label, fn = JOBS[name]
    if not jobs.start(label, fn, dry_run):
        raise HTTPException(409, "Es läuft bereits ein Job")
    return {"started": label}


@app.post("/api/zepp-upload")
async def api_zepp_upload(request: Request):
    """Lädt ausdrücklich gewählte Zepp-Trainings zu Komoot hoch."""
    d = await request.json()
    ids = [int(x) for x in d.get("trackids", [])]
    if not ids:
        raise HTTPException(400, "Nichts ausgewählt")
    dry = bool(d.get("dry_run"))
    ps = [p for p in d.get("portals", ["komoot"] if not d.get("local_only") else []) if p in portals.PORTALS]
    label = "Übernehmen" if not ps else "Upload zu " + ", ".join(portals.PORTALS[p] for p in ps)
    if not jobs.start(label + (" (Probelauf)" if dry else ""), lambda: sync.upload_selected(ids, dry, ps, local_only=not ps)):
        raise HTTPException(409, "Es läuft bereits ein Job")
    return {"started": len(ids)}


@app.get("/api/jobs")
def api_jobs():
    return jobs.snapshot()


@app.post("/api/import-files")
async def api_import_files(files: list[UploadFile] = File(...), dry_run: bool = False, portals_: str = Query("", alias="portals")):
    items = [(f.filename, (await f.read()).decode("utf-8", "replace"), f.filename) for f in files]
    ps = tuple(p for p in portals_.split(",") if p in portals.PORTALS)
    if not jobs.start("Datei-Import", lambda: sync.import_items(items, ps, dry_run)):
        raise HTTPException(409, "Es läuft bereits ein Job")
    return {"started": len(items)}


# ---------- Teilen-Ziel (Android: „Teilen mit Meine Touren“) ----------
SHARE_ACT = (".gpx", ".fit", ".tcx", ".zip", ".gz")
SHARE_IMG = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")
SHARE_MAX = 300 * 1024 * 1024


@app.post("/api/share-target")
async def api_share_target(files: list[UploadFile] = File(default=[])):
    """Nimmt Dateien an, die per Android-Teilen-Menü gesendet wurden: Tourendateien werden sofort übernommen, Fotos
    kommen in den Eingangsordner und werden im Hintergrund zugeordnet. Danach Weiterleitung zur Ergebnisseite."""
    import re as _re
    act_dir, img_dir = config.INBOX_DIR / "touren", config.INBOX_DIR / "teilen"
    n_act = n_img = n_bad = total = 0
    for f in files:
        name = _re.sub(r"[^\w.\- ]+", "_", (f.filename or "datei").replace("\\", "/").split("/")[-1])[:120] or "datei"
        ext = Path(name).suffix.lower()
        dest = act_dir if ext in SHARE_ACT else img_dir if ext in SHARE_IMG else None
        if dest is None:
            n_bad += 1
            continue
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / name
        if target.exists():
            target = dest / f"{int(time.time())}_{name}"
        size = 0
        with open(target, "wb") as out:
            while True:
                chunk = await f.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                total += len(chunk)
                if total > SHARE_MAX:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, "Zu viele Daten auf einmal")
                out.write(chunk)
        if ext in SHARE_ACT:
            n_act += 1
        else:
            n_img += 1
    imported = dup = 0
    if n_act:
        root = act_dir
        paths = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SHARE_ACT]
        res = await asyncio.get_running_loop().run_in_executor(None, contextvars.copy_context().run, lambda: _share_import(paths))
        imported, dup = res
    if n_img:
        jobs.start("Geteilte Fotos", sync.import_inbox)
    q = f"?t={imported}&d={dup}&a={n_act}&p={n_img}&x={n_bad}"
    return RedirectResponse("/#/shared" + q, status_code=303)


@app.post("/api/rec-photos")
async def api_rec_photos(request: Request, files: list[UploadFile] = File(default=[])):
    """Fotos, die in der Android-App während einer Aufzeichnung aufgenommen wurden (mit Aufnahmezeit und GPS im EXIF)."""
    import re as _re
    img_dir = config.INBOX_DIR / "teilen"
    img_dir.mkdir(parents=True, exist_ok=True)
    saved, total = 0, 0
    for f in files:
        name = _re.sub(r"[^\w.\- ]+", "_", (f.filename or "foto.jpg").replace("\\", "/").split("/")[-1])[:120] or "foto.jpg"
        if Path(name).suffix.lower() not in SHARE_IMG:
            continue
        target = img_dir / name
        if target.exists():
            target = img_dir / f"{int(time.time())}_{name}"
        with open(target, "wb") as out:
            while True:
                chunk = await f.read(1 << 20)
                if not chunk:
                    break
                total += len(chunk)
                if total > SHARE_MAX:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, "Zu viele Daten auf einmal")
                out.write(chunk)
        photos.add_offset(target, request.headers.get("x-utc-offset"))
        saved += 1
    if saved:
        jobs.start("Fotos der Aufzeichnung", sync.import_inbox)
    return {"saved": saved}


@app.post("/api/record/upload")
async def api_record_upload(request: Request):
    """Aufzeichnung aus der Android-App: JSON {gpx, name, sport}. Legt eine lokale Tour an (doppelte werden erkannt)."""
    try:
        d = await request.json()
    except Exception:  # noqa
        raise HTTPException(400, "Ungültige Daten")
    gpx = str(d.get("gpx") or "")
    if "<trkpt" not in gpx or len(gpx) > 60 * 1024 * 1024:
        raise HTTPException(400, "Keine GPS-Punkte")
    name = (str(d.get("name") or "").strip() or None)
    sport = str(d.get("sport") or "").strip() or None
    try:
        c = gpxtools.convert(gpx, "rec.gpx", db.get("default_sport") or "hike")
    except gpxtools.NoGps:
        raise HTTPException(400, "Keine GPS-Punkte")
    tid = f"g{c['start_ts']}"
    if db.one("SELECT 1 FROM tours WHERE id=?", (tid,)):
        return {"id": tid, "dup": True}
    if sport not in gpxtools.LABEL:
        sport = None
    t, _ = await asyncio.get_running_loop().run_in_executor(None, contextvars.copy_context().run, lambda: tracks.adopt(gpx, "rec.gpx", name=name, sport=sport))
    try:
        photos.assign_all()
        wait = config.INBOX_DIR / "teilen"
        if wait.is_dir() and any(wait.iterdir()):
            jobs.start("Fotos der Aufzeichnung", sync.import_inbox)        # Fotos aus der App, die noch im Eingang liegen
    except Exception:  # noqa
        pass
    more2.notify_event(f"Neue Tour gespeichert: {t['name']} ({(t['dist_m'] or 0) / 1000:.1f} km, {round(t['up_m'] or 0)} m aufwärts)", "Neue Tour")
    return {"id": t["id"], "dup": False}


@app.post("/api/record/rescue")
async def api_record_rescue(request: Request):
    """Admin: App-Aufzeichnungen, die vor 2.3.2 versehentlich im Altbestand (ohne Benutzer) gelandet sind, in den eigenen Bestand übernehmen."""
    u = getattr(request.state, "user", None)
    if u and u["role"] != "admin":
        raise HTTPException(403, "Nur für Administratoren")
    legacy = config.user_dir(None) / "tracks"
    found, done = 0, []
    uid = ctx.uid()
    if uid and legacy.is_dir():
        for f in sorted(legacy.glob("g*.gpx")):
            if time.time() - f.stat().st_mtime > 30 * 86400:
                continue
            tid = f.stem
            if db.one("SELECT 1 FROM tours WHERE id=?", (tid,)):
                continue
            found += 1
            try:
                t, _ = tracks.adopt(f.read_text(encoding="utf-8"), "rec.gpx", ident=tid)
                done.append({"id": t["id"], "name": t["name"], "km": round((t["dist_m"] or 0) / 1000, 1), "date": t["start_ts"]})
            except Exception:  # noqa
                pass
        try:
            photos.assign_all()
        except Exception:  # noqa
            pass
    return {"found": found, "imported": done}


def _share_import(paths):
    from . import devices
    tot = devices.import_paths(paths)
    done = config.INBOX_DIR / "touren" / "erledigt"
    done.mkdir(parents=True, exist_ok=True)
    for p in paths:
        try:
            p.replace(done / p.name)
        except OSError:
            pass
    try:
        photos.assign_all()
    except Exception:  # noqa
        pass
    if tot["imported"]:
        more2.notify_event(f"{tot['imported']} Tour{'en' if tot['imported'] != 1 else ''} per Teilen-Menü übernommen.", "Neue Tour")
    return tot["imported"], tot["dup"]


# ---------- Fotos ----------
def _photos_located(limit, year=0):
    rows = db.query("SELECT p.id,p.taken_ts,p.tour_id,p.lat,p.lng,p.manual,p.offset_s,t.name AS tour_name,t.start_ts AS t0 FROM photos p LEFT JOIN tours t ON t.id=p.tour_id "
                    "WHERE COALESCE(p.manual,0)!=2 ORDER BY p.taken_ts DESC LIMIT ?", (max(1, min(limit, 60000)),))
    out, cache = [], {}
    for r in rows:
        if year and datetime.fromtimestamp(r["taken_ts"] or 0, tz=TZ).year != year:
            continue
        if r["lat"] is not None and r["lng"] is not None:
            out.append({**{k: r[k] for k in ("id", "taken_ts", "tour_id", "lat", "lng", "tour_name")}, "est": 0})
            continue
        if not r["tour_id"] or r["t0"] is None or r["taken_ts"] is None:
            continue
        pts = cache.get(r["tour_id"])
        if pts is None:
            pts = cache[r["tour_id"]] = [p for p in (photos.track_pts(r["tour_id"]) or []) if p[2] is not None]
        if len(pts) < 2:
            continue
        sec = r["taken_ts"] - r["t0"]
        if sec <= pts[0][2]:
            a = pts[0]
        elif sec >= pts[-1][2]:
            a = pts[-1]
        else:
            lo, hi = 0, len(pts) - 1
            while hi - lo > 1:
                m = (lo + hi) // 2
                lo, hi = (m, hi) if pts[m][2] <= sec else (lo, m)
            u = (sec - pts[lo][2]) / ((pts[hi][2] - pts[lo][2]) or 1)
            a = (pts[lo][0] + (pts[hi][0] - pts[lo][0]) * u, pts[lo][1] + (pts[hi][1] - pts[lo][1]) * u)
        out.append({**{k: r[k] for k in ("id", "taken_ts", "tour_id", "tour_name")}, "lat": round(a[0], 5), "lng": round(a[1], 5), "est": 1})
    return out


@app.get("/api/photos")
def api_photos(tour_id: str = "", year: int = 0, random: bool = False, limit: int = 500, unassigned: bool = False, gps: bool = False, est: bool = False):
    where, args = ["1=1"], []
    if gps and est:        # Fotos ohne eigenen Aufnahmeort: Position über die Uhrzeit auf der Strecke der Tour berechnen (est=1)
        return _photos_located(limit, year)
    if gps:
        where.append("p.lat IS NOT NULL AND p.lng IS NOT NULL")
    if tour_id:
        where.append("p.tour_id=?"); args.append(tour_id)
    if unassigned:
        where.append("p.tour_id IS NULL")
    if year:
        a = int(datetime(year, 1, 1, tzinfo=TZ).timestamp()); b = int(datetime(year + 1, 1, 1, tzinfo=TZ).timestamp())
        where.append("p.taken_ts>=? AND p.taken_ts<?"); args += [a, b]
    order = "RANDOM()" if random else "p.taken_ts"
    rows = db.query(f"SELECT p.id,p.taken_ts,p.tour_id,p.lat,p.lng,p.manual,p.offset_s,t.name AS tour_name FROM photos p LEFT JOIN tours t ON t.id=p.tour_id WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ?", (*args, limit))
    return rows


@app.post("/api/photo-assign")
def api_photo_assign(body: dict):
    try:
        return photos.assign_manual(body.get("ids", []), body.get("tour_id"), bool(body.get("shift")),
                                    body.get("minutes", 0), body.get("scope", "selected"))
    except KeyError:
        raise HTTPException(404, "Tour oder Foto nicht gefunden")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/photo-shift")
def api_photo_shift(body: dict):
    try:
        return photos.shift_photos(body.get("tour_id"), body.get("delta_s", 0), body.get("scope", "tour"), bool(body.get("reset")))
    except KeyError:
        raise HTTPException(404, "Tour nicht gefunden")
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/photo-shift-ids")
def api_photo_shift_ids(body: dict):
    try:
        return photos.shift_ids(body.get("ids"), body.get("delta_s", 0))
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/photo-unassign")
def api_photo_unassign(body: dict):
    if not body.get("ids"):
        raise HTTPException(400, "Keine Fotos gewählt")
    photos.unassign_manual(body["ids"], bool(body.get("reset_time")), bool(body.get("exclude")))
    return {"ok": True}


@app.post("/api/photo-delete")
def api_photo_delete(body: dict):
    ids = body.get("ids") or []
    if not ids:
        raise HTTPException(400, "Keine Fotos gewählt")
    return {"ok": True, "deleted": photos.delete_photos(ids)}


@app.get("/api/photo-library")
def photo_library(split: int = 0):
    """Relative Pfade (ohne Endung) aller Bilder der Bibliothek – damit der Browser Vorhandenes überspringt (auch gelöschte)."""
    root = config.LIB_DIR
    have = [p.relative_to(root).with_suffix("").as_posix() for p in root.rglob("*.jpg")] if root.exists() else []
    gone = [r["rel"] for r in db.query("SELECT rel FROM photo_deleted")]
    if split:
        return {"have": have, "deleted": gone}
    return have + gone


@app.post("/api/photo-upload")
async def photo_upload(file: UploadFile = File(...), rel: str = Form(...), taken: str = Form(""), mtime: int = Form(0),
                       tour: str = Form(""), shift_s: int = Form(0), lat: str = Form(""), lng: str = Form(""), force: str = Form(""), offset: str = Form(""), raw_mode: str = Form("")):
    """Nimmt ein im Browser verkleinertes Foto an und schreibt die Aufnahmezeit als EXIF hinein."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    if not parts:
        raise HTTPException(400, "Ungültiger Pfad")
    dst = (config.LIB_DIR.joinpath(*parts)).with_suffix(".jpg")
    if config.LIB_DIR.resolve() not in dst.resolve().parents:
        raise HTTPException(400, "Ungültiger Pfad")
    import re as _re
    offset = offset if _re.match(r"^[+-]\d\d:\d\d$", offset or "") else ""
    ts = photos._raw_ts(taken, offset or None)
    if shift_s and ts is not None:      # Zeitverschiebung (Kamera nicht auf Ortszeit): Aufnahmezeit korrigieren
        ts += shift_s
        zone = photos.timezone(photos.timedelta(seconds=(1 if offset[0] == "+" else -1) * (int(offset[1:3]) * 3600 + int(offset[4:6]) * 60))) if offset else photos.TZ
        taken = datetime.fromtimestamp(ts, zone).strftime("%Y:%m:%d %H:%M:%S")
    if not tour and not force and photos.only_tracked() and not photos.in_track(ts, photos.track_windows()):
        return {"ok": True, "skipped": True}     # keine GPS-Strecke zu diesem Foto
    raw = await file.read()
    if raw_mode:                      # Original (HEIC, großes JPEG …): der Server verkleinert
        try:
            raw = photos.to_jpeg_bytes(raw)
        except ValueError as e:
            raise HTTPException(415, str(e))
    elif raw[:2] != b"\xff\xd8":
        raise HTTPException(415, "Kein gültiges JPEG")
    dup = photos.find_duplicate(ts, photos.fingerprint(raw), str(dst))
    if dup:
        return {"ok": True, "skipped": True, "duplicate": True}      # dasselbe Bild ist schon in der Bibliothek
    try:
        la, lo = (float(lat), float(lng)) if lat != "" and lng != "" else (None, None)
    except ValueError:
        la = lo = None
    data = photos.with_exif_time(raw, taken, la, lo, offset or None)
    rel_key = "/".join(parts); rel_key = rel_key.rsplit(".", 1)[0] if "." in parts[-1] and parts[-1].lower().endswith(".jpg") else rel_key
    db.execute("DELETE FROM photo_deleted WHERE rel=?", (rel_key,))      # bewusst erneut hochgeladen: nicht mehr als gelöscht merken
    if tour:
        db.execute("INSERT INTO photo_pref(path,tour_id) VALUES(?,?) ON CONFLICT(path) DO UPDATE SET tour_id=excluded.tour_id", (str(dst), tour))
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    tmp.write_bytes(data)
    if mtime:
        os.utime(tmp, (mtime, mtime))
    tmp.replace(dst)
    return {"ok": True}


@app.post("/api/photo-meta")
async def photo_meta(file: UploadFile = File(...)):
    """Aufnahmezeit, Zeitzonen-Zusatz und Aufnahmeort aus einem Bild lesen (für HEIC, die der Browser nicht selbst lesen kann)."""
    import io
    raw, offs, la, lo = photos.exif_fields(io.BytesIO(await file.read()))
    if raw is None and la is None:
        return {"ok": False}
    t = str(raw).strip()[:19] if raw else ""
    return {"ok": True, "t": t, "o": str(offs) if offs else "", "lat": la, "lng": lo}


@app.post("/api/photo-plan")
def photo_plan(body: dict):
    """Vor dem Import: je Aufnahmetag passende Tour(en) und Vorschläge bei Unklarheit (Zeitverschiebung, Aufnahmeort)."""
    return {"only": photos.only_tracked(), "days": photos.plan(body.get("items") or [], body.get("tour") or None)}


@app.get("/api/photo-offset")
def photo_offset(tour_id: str):
    """Passen die Foto-Zeiten zur Strecke? Aus dem Aufnahmeort der Fotos wird ein Zeitversatz der Kamerauhr vorgeschlagen."""
    try:
        return photos.suggest_offset(tour_id)
    except KeyError:
        raise HTTPException(404, "Tour nicht gefunden")


@app.post("/api/photo-offset")
def photo_offset_apply(body: dict):
    try:
        return photos.apply_offset(body.get("tour_id"), body.get("delta_s", 0), body.get("ids"))
    except KeyError:
        raise HTTPException(404, "Tour nicht gefunden")
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/clock-check")
def clock_check():
    """Touren, bei denen die Kamerauhr nach dem Aufnahmeort der Fotos falsch gegangen sein muss (Vorschlag zum Korrigieren)."""
    return photos.clock_check()


@app.post("/api/clock-check/ignore")
def clock_check_ignore(body: dict):
    import json as _j
    try:
        cur = set(_j.loads(db.get("clock_ignore") or "[]"))
    except ValueError:
        cur = set()
    cur.add(str(body.get("tour_id")))
    db.put("clock_ignore", _j.dumps(sorted(cur)))
    return {"ok": True}


@app.get("/api/photo-windows")
def photo_windows():
    """Zeitfenster der Touren (Sekunden, UTC) – der Browser lädt nur Fotos hoch, die hineinfallen."""
    return {"only": photos.only_tracked(), "windows": photos.track_windows()}


@app.get("/api/photo-info")
def photo_info():
    r = db.one("SELECT COUNT(*) n, SUM(tour_id IS NOT NULL) a, MIN(taken_ts) mi, MAX(taken_ts) ma FROM photos")
    years = db.query("SELECT DISTINCT CAST(strftime('%Y', taken_ts, 'unixepoch') AS INT) y FROM photos ORDER BY y DESC")
    undated = db.one("SELECT COUNT(*) n FROM photos WHERE dated=0")["n"]
    return {"count": r["n"], "assigned": r["a"] or 0, "undated": undated, "years": [y["y"] for y in years],
            "folder_exists": config.PHOTOS_DIR.exists(), "heic": photos.heic_supported(), "lib_dir": str(config.LIB_DIR), "source_dir": str(config.PHOTOS_DIR), "slideshow_seconds": db.get_int("slideshow_seconds", 6), "tz": config.TZ_NAME}


@app.get("/pic/{photo_id}")
@app.get("/photo/{photo_id}")
def photo(photo_id: int, request: Request, size: int = 1600):
    size = max(120, min(size, 3000))
    p = photos.thumb(photo_id, size)
    if not p:
        raise HTTPException(404)
    # Immer beim Server nachfragen (ETag → 304): verhindert, dass der Browser Bilder eines früheren Servers unter derselben Adresse anzeigt
    return photos.respond(request, p)


app.include_router(extras.router)
app.include_router(more.router)
app.include_router(more2.router)
app.include_router(gear.router)
app.include_router(plan.router)
app.include_router(pdfgen.router)
app.include_router(users_api.router)
app.include_router(security.router)
app.include_router(portals.router)
app.include_router(health.router)
app.include_router(devices.router)
app.include_router(updater.router)
app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
