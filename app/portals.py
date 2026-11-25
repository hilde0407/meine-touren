"""Portale für den Upload von Touren: Komoot und Strava. Die Strecken liegen lokal; hier wird nur gesendet."""
import json
import time
import urllib.parse

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from . import config, db, gpxtools, tracks
from .jobs import log

router = APIRouter()

# 3.60.0: genau die 29 Aktivitäten des Katalogs (gpxtools.CATALOG); entfernte Schlüssel älterer Touren gehen als ihr Rückfall (sende_sport)
STRAVA_SPORT = {
    "hike": "Hike", "walk": "Walk", "mountaineering": "Hike", "climbing": "RockClimbing", "nordicwalking": "Walk", "jogging": "Run", "trailrun": "TrailRun",
    "touringbicycle": "Ride", "racebike": "Ride", "mtb": "MountainBikeRide", "mtb_easy": "GravelRide", "e_touringbicycle": "EBikeRide",
    "e_mtb": "EMountainBikeRide", "bikepacking": "Ride",
    "skialpin": "AlpineSki", "skitour": "BackcountrySki", "nordic": "NordicSki", "snowboard": "Snowboard", "snowshoe": "Snowshoe",
    "kayak": "Kayaking", "rowing": "Rowing", "dragonboat": "Canoeing", "rafting": "Canoeing", "boat": "Workout",
    "skateboard": "Skateboard", "skaten": "InlineSkate", "horse": "Workout", "paraglide": "Workout", "other": "Workout",
}
# Aktivitäten, die Komoot nicht kennt, gehen mit einer ähnlichen Komoot-Sportart hin (Komoot-Kennungen e_mtb, mtb_easy, climbing, snowboard, skaten
# gehen unverändert); alles ohne Entsprechung als Wandern
KOMOOT_SPORT = {"walk": "hike", "trailrun": "jogging", "bikepacking": "touringbicycle", "skateboard": "skaten"}
KOMOOT_SPORT.update({k: "hike" for k in ("kayak", "rowing", "dragonboat", "rafting", "boat", "horse", "paraglide", "other")})


def sende_sport(sport):
    """3.60.0: Sportart einer Tour zum Senden – entfernte Aktivitäten (gpxtools.RUECKFALL, z. B. ältere Touren „Gassigehen“) gehen als Rückfall-Aktivität."""
    return gpxtools.norm(sport or "hike")[0] or "hike"


PORTALS = {"komoot": "Komoot", "strava": "Strava"}


class PortalError(Exception):
    pass


# ---------- Strava ----------
SB = "https://www.strava.com"


def strava_tokens():
    try:
        return json.loads(db.get("strava_tokens") or "{}")
    except ValueError:
        return {}


def strava_configured():
    return bool(db.get("strava_client_id") and db.get("strava_client_secret"))


def strava_connected():
    return bool(strava_tokens().get("refresh_token"))


def _tok_post(data):
    r = requests.post(f"{SB}/oauth/token", data={"client_id": db.get("strava_client_id"), "client_secret": db.get("strava_client_secret"), **data}, timeout=30)
    if r.status_code != 200:
        raise PortalError(f"Strava-Anmeldung abgelehnt (HTTP {r.status_code}): {r.text[:160]}")
    j = r.json()
    old = strava_tokens()
    ath = j.get("athlete") or {}
    new = {"access_token": j["access_token"], "refresh_token": j["refresh_token"], "expires_at": j["expires_at"],
           "athlete": old.get("athlete") or ((ath.get("firstname") or "") + " " + (ath.get("lastname") or "")).strip() or ath.get("username") or ""}
    db.put("strava_tokens", json.dumps(new))
    return new


def strava_access():
    t = strava_tokens()
    if not t.get("refresh_token"):
        raise PortalError("Strava ist nicht verbunden (Verwaltung → Hochladen & Planen → Portale)")
    if t.get("expires_at", 0) < time.time() + 90:
        t = _tok_post({"grant_type": "refresh_token", "refresh_token": t["refresh_token"]})
    return t["access_token"]


def strava_auth_url(redirect):
    if not strava_configured():
        raise PortalError("Zuerst Client-ID und Client-Secret der Strava-App eintragen")
    q = urllib.parse.urlencode({"client_id": db.get("strava_client_id"), "response_type": "code", "redirect_uri": redirect,
                                "approval_prompt": "auto", "scope": "activity:write,activity:read"})
    return f"{SB}/oauth/authorize?{q}"


def strava_exchange(code):
    code = (code or "").strip()
    if "code=" in code:                                  # ganze Adresse eingefügt
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get("code", [""])[0]
    if not code:
        raise PortalError("Kein Code")
    return _tok_post({"grant_type": "authorization_code", "code": code})


def strava_upload(gpx, sport, name, ext_id):
    h = {"Authorization": f"Bearer {strava_access()}"}
    r = requests.post(f"{SB}/api/v3/uploads", headers=h, timeout=120,
                      data={"data_type": "gpx", "name": name, "sport_type": STRAVA_SPORT.get(sende_sport(sport), "Hike"), "external_id": ext_id},
                      files={"file": (f"{ext_id}.gpx", gpx.encode("utf-8"), "application/gpx+xml")})
    if r.status_code == 401:
        raise PortalError("Strava hat den Zugriff abgelehnt – in der Verwaltung neu verbinden (Berechtigung „Aktivitäten hochladen“)")
    if r.status_code == 429:
        raise PortalError("Strava-Limit erreicht – später erneut versuchen")
    if r.status_code not in (200, 201):
        raise PortalError(f"Strava-Upload fehlgeschlagen (HTTP {r.status_code}): {r.text[:200]}")
    j = r.json()
    for _ in range(25):                                  # Strava verarbeitet asynchron
        if j.get("error") or j.get("activity_id"):
            break
        time.sleep(2)
        rr = requests.get(f"{SB}/api/v3/uploads/{j['id']}", headers=h, timeout=30)
        if rr.status_code == 200:
            j = rr.json()
    err = j.get("error") or ""
    if err:
        if "duplicate" in err.lower():
            return "duplicate", ""
        raise PortalError(f"Strava: {err}")
    if not j.get("activity_id"):
        return "pending", str(j.get("id", ""))
    return "created", str(j["activity_id"])


# ---------- Komoot ----------
# 3.58.0: Komoot gibt jeder hochgeladenen Tour die Standard-Sichtbarkeit des Kontos (laut kompy; ein Parameter beim Upload wirkt nicht).
# Meine Touren setzt deshalb gleich nach dem Upload „private“ (PATCH) und liest danach nach (GET). Nie wird etwas öffentlich gemacht.
VIS_LABEL = {"private": "privat", "friends": "für Freunde sichtbar", "public": "öffentlich", "unbekannt": "Sichtbarkeit unbestätigt"}
CHECK_PAUSE_S = 0.4          # Pause zwischen zwei Touren bei der gesammelten Prüfung (gedrosselt)
CHECK_MAX = 10               # höchstens so viele Touren je Aufruf


def with_notes_enabled():
    return (db.get("komoot_with_notes") or "1") != "0"


def wps_for(tid):
    """Pins (tour_wps) und – falls benannt – den Gipfel (tour_peak) einer Tour als Wegpunkte für eine GPX-Kopie."""
    out = []
    try:
        rows = db.query("SELECT ts,lat,lng,note FROM tour_wps WHERE tour_id=? ORDER BY ts,id", (str(tid),))
    except Exception:  # noqa  (Tabelle fehlt in sehr alten Datenbanken)
        rows = []
    for i, r in enumerate(rows, 1):
        note = (r["note"] or "").strip()
        first = note.split("\n", 1)[0].strip()
        out.append({"lat": r["lat"], "lng": r["lng"], "ts": r["ts"] or None, "name": first or f"Wegpunkt {i}", "desc": note})
    pk = db.one("SELECT name,alt,lat,lng FROM tour_peak WHERE id=?", (str(tid),))
    if pk and (pk["name"] or "").strip() and pk["lat"] is not None and pk["lng"] is not None:
        out.append({"lat": pk["lat"], "lng": pk["lng"], "ele": pk["alt"], "name": f"Gipfel: {pk['name'].strip()}", "sym": "Summit"})
    return out


def note_for(tid):
    r = db.one("SELECT note FROM tour_notes WHERE id=?", (str(tid),))
    return (r["note"] or "").strip() if r else ""


def upload_copy(tid, gpx, with_notes=True):
    """GPX-Kopie zum Senden: mit Notiz (Beschreibung) und Pins (Wegpunkte), wenn gewünscht. Die gespeicherte Datei bleibt unverändert.
    Gibt (gpx, anzahl_wegpunkte, notiz_dabei) zurück."""
    if not with_notes:
        return gpx, 0, False
    w, n = wps_for(tid), note_for(tid)
    if not w and not n:
        return gpx, 0, False
    return gpxtools.with_waypoints(gpx, w, n), len(w), bool(n)


def _vis_from(v):
    return v if v in ("private", "friends", "public") else ("unbekannt" if v is None else v)


def komoot_upload(gpx, sport, name, info=None):
    """Hochladen und danach die Sichtbarkeit auf „privat“ setzen und prüfen. info (dict) bekommt:
    vis      – Ergebnis nach der Prüfung: private | friends | public | unbekannt
    vorher   – Sichtbarkeit direkt nach dem Upload (= Konto-Vorgabe), soweit bekannt
    geaendert – True, wenn Meine Touren sie geändert hat; fehler – Text, falls Setzen oder Prüfen scheiterte."""
    from . import sync
    k = sync._komoot()
    info = info if info is not None else {}
    up = {}
    try:
        st, rid = k.upload(gpx, sport, name, info=up)
    except TypeError as e:                               # ältere Client-Nachbildungen ohne info-Parameter
        if "info" not in str(e):
            raise
        st, rid = k.upload(gpx, sport, name)
    info.update(vis="unbekannt", vorher=up.get("vis"), geaendert=False, fehler="")
    if not rid:
        info["fehler"] = "Komoot hat keine Tour-Kennung genannt"
        return st, rid
    if st == "duplicate" and not up.get("wiederholt"):
        try:                                            # vorhandene Tour: nur nachsehen, nichts ändern (Änderung nur per Klick)
            info["vis"] = _vis_from(k.visibility(rid))
        except Exception as e:  # noqa
            info["fehler"] = str(e)[:200]
        return st, rid
    if st == "duplicate":                               # zweiter Versuch nach Netzfehler/5xx: der erste ist wohl angekommen – wie neu behandeln
        st = "created"
    try:
        vorher = up.get("vis") or k.visibility(rid)
        info["vorher"] = vorher
        if vorher != "private":
            k.set_visibility(rid, "private")
            info["geaendert"] = True
    except Exception as e:  # noqa
        info["fehler"] = f"Sichtbarkeit setzen: {str(e)[:200]}"
    try:
        info["vis"] = _vis_from(k.visibility(rid))       # immer nachlesen – erst das bestätigt „privat“
    except Exception as e:  # noqa
        info["vis"] = "unbekannt"
        info["fehler"] = (info["fehler"] + "; " if info["fehler"] else "") + f"Sichtbarkeit prüfen: {str(e)[:200]}"
    return st, rid


def set_vis(tid, vis):
    db.execute("UPDATE tour_uploads SET vis=?, vis_ts=? WHERE tour_id=? AND portal='komoot'", (vis, int(time.time()), str(tid)))


def vis_text(vis, vorher=None):
    """Kurztext für Upload-Vermerk und Oberfläche."""
    if vis == "private":
        return "bei Komoot privat (bestätigt)"
    if vis == "public":
        return "ACHTUNG: bei Komoot öffentlich – bitte in Komoot prüfen"
    if vis == "friends":
        return "bei Komoot für Freunde sichtbar – bitte in Komoot prüfen"
    return "Sichtbarkeit nicht bestätigt, bitte in Komoot prüfen"


def komoot_check(tid, visibility=True):
    """Fragt bei Komoot nach, ob die hochgeladene Tour wirklich dort liegt (nur lesend). Fehlt sie, wird der Upload-Vermerk gelöscht.
    3.58.0: liest dabei auch die Sichtbarkeit und speichert sie im Vermerk (vis); geprüft werden alle Vermerke mit Komoot-Kennung."""
    from . import komoot as komoot_mod, sync
    old = status_of(tid).get("komoot")
    if not old or not old["remote_id"] or old["status"] not in ("uploaded", "pending", "duplicate", "linked"):
        return {"checked": False}
    try:
        raw = sync._komoot().tour_raw(old["remote_id"])
    except komoot_mod.KomootNotFound:
        db.execute("DELETE FROM tour_uploads WHERE tour_id=? AND portal='komoot'", (str(tid),))
        return {"checked": True, "exists": False}
    except Exception as e:  # noqa
        if "nicht gefunden" in str(e):
            db.execute("DELETE FROM tour_uploads WHERE tour_id=? AND portal='komoot'", (str(tid),))
            return {"checked": True, "exists": False}
        return {"checked": False, "msg": str(e)[:300], "vis": old.get("vis")}
    vis = _vis_from(komoot_mod._vis(raw))
    if visibility:
        set_vis(tid, vis)
    return {"checked": True, "exists": True, "type": raw.get("type", "tour_recorded"), "name": raw.get("name", ""), "vis": vis, "vis_text": vis_text(vis)}


def komoot_make_private(tid):
    """Nur auf ausdrücklichen Klick: eine schon hochgeladene Tour bei Komoot auf „privat“ setzen und nachlesen."""
    from . import sync
    old = status_of(tid).get("komoot")
    if not old or not old["remote_id"]:
        raise PortalError("Zu dieser Tour ist keine Komoot-Tour bekannt")
    k = sync._komoot()
    err = ""
    try:
        k.set_visibility(old["remote_id"], "private")
    except Exception as e:  # noqa
        err = str(e)[:200]
    try:
        vis = _vis_from(k.visibility(old["remote_id"]))
    except Exception as e:  # noqa
        vis, err = "unbekannt", (err + "; " if err else "") + str(e)[:200]
    set_vis(tid, vis)
    log(f"  Tour {tid}: Komoot-Sichtbarkeit auf privat gesetzt → {vis}{' (' + err + ')' if err else ''}")
    return {"vis": vis, "vis_text": vis_text(vis), "ok": vis == "private", "msg": err}


def komoot_uploaded():
    """Alle Touren mit Komoot-Kennung aus dem Upload-Vermerk (hochgeladen, Duplikat, verknüpft) – für die gesammelte Prüfung."""
    rows = db.query("SELECT u.tour_id,u.remote_id,u.status,u.vis,u.vis_ts,u.ts,t.name,t.start_ts FROM tour_uploads u LEFT JOIN tours t ON t.id=u.tour_id "
                    "WHERE u.portal='komoot' AND u.remote_id!='' AND u.status IN ('uploaded','pending','duplicate','linked') ORDER BY t.start_ts DESC")
    return [{"id": r["tour_id"], "name": r["name"] or r["tour_id"], "start_ts": r["start_ts"], "remote_id": r["remote_id"], "status": r["status"],
             "vis": r["vis"], "vis_ts": r["vis_ts"], "url": remote_url("komoot", r["remote_id"])} for r in rows]


def count_vis(items):
    z = {"oeffentlich": 0, "freunde": 0, "privat": 0, "unbekannt": 0, "fehlt": 0}
    for v in items:
        z[{"public": "oeffentlich", "friends": "freunde", "private": "privat", "fehlt": "fehlt"}.get(v, "unbekannt")] += 1
    return z


# ---------- gemeinsam ----------
def status_of(tid):
    out = {}
    for r in db.query("SELECT * FROM tour_uploads WHERE tour_id=?", (str(tid),)):
        o = {"status": r["status"], "remote_id": r["remote_id"], "msg": r["msg"], "ts": r["ts"]}
        if r["portal"] == "komoot":
            o["vis"], o["vis_ts"] = r.get("vis"), r.get("vis_ts")
            if o["vis"]:
                o["vis_text"] = vis_text(o["vis"])
        out[r["portal"]] = o
    return out


def record(tid, portal, status, remote="", msg="", vis=None):
    db.execute("INSERT OR REPLACE INTO tour_uploads(tour_id,portal,remote_id,status,msg,ts,vis,vis_ts) VALUES(?,?,?,?,?,?,?,?)",
               (str(tid), portal, remote or "", status, msg or "", int(time.time()), vis, int(time.time()) if vis else None))


def remote_url(portal, remote):
    if not remote:
        return ""
    return {"komoot": f"https://www.komoot.com/tour/{remote}", "strava": f"https://www.strava.com/activities/{remote}"}.get(portal, "")


def upload_tour(tid, portal, gpx=None, force=False, dry_run=False, with_notes=None, info=None):
    """Eine Tour zu einem Portal senden. Gibt (status, remote_id, meldung) zurück:
    uploaded | duplicate | already | skipped | would_upload.
    3.58.0 (Komoot): with_notes (None = Einstellung „komoot_with_notes“) schreibt Notiz und Pins in die gesendete Kopie; danach wird die Tour
    auf „privat“ gesetzt und geprüft. info (dict) bekommt vis, vis_text, warnung, wegpunkte, notiz."""
    info = info if info is not None else {}
    tid = str(tid)
    if portal not in PORTALS:
        raise PortalError(f"Unbekanntes Portal {portal}")
    t = db.one("SELECT * FROM tours WHERE id=?", (tid,))
    if not t:
        raise PortalError("Tour nicht gefunden")
    if portal == "komoot" and (t.get("source") or "komoot") == "komoot":
        return "already", tid, "Die Tour stammt von Komoot"
    old = status_of(tid).get(portal)
    if old and old["status"] in ("uploaded", "linked", "duplicate") and not force:
        return "already", old["remote_id"], "Schon hochgeladen"
    if dry_run:
        return "would_upload", "", ""
    if portal == "strava" and not strava_connected():
        raise PortalError("Strava ist nicht verbunden (Verwaltung → Hochladen & Planen → Portale)")
    gpx = gpx or tracks.gpx_for(tid)
    name = t["name"] or tid
    sport = sende_sport(t["sport"])               # 3.60.0: entfernte Aktivitäten als Rückfall (Gassigehen -> Spazieren, SUP -> Kajak, sonst Sonstiges)
    if sport == "hike" and db.one("SELECT 1 x FROM tour_tags WHERE id=? AND tag=?", (tid, gpxtools.SCHNEESCHUH_TAG)):
        sport = "snowshoe"                     # 3.50.0: Wandern mit Schlagwort „Schneeschuh“ geht als Schneeschuhwanderung zu Komoot/Strava
    kinfo = {}
    try:
        if portal == "komoot":
            wn = with_notes_enabled() if with_notes is None else bool(with_notes)
            send, nw, nn = upload_copy(tid, gpx, wn)
            info.update(wegpunkte=nw, notiz=nn)
            st, rid = komoot_upload(send, KOMOOT_SPORT.get(sport, sport), name, info=kinfo)
            st = "created" if st == "created" else "duplicate"
        else:
            st, rid = strava_upload(gpx, sport, name, f"meine-touren-{tid}")
    except Exception as e:  # noqa
        record(tid, portal, "error", "", str(e)[:300])
        raise
    vis = kinfo.get("vis") if portal == "komoot" else None
    if portal == "komoot":
        info.update(vis=vis, vis_text=vis_text(vis), vorher=kinfo.get("vorher"), geaendert=kinfo.get("geaendert"))
        if vis != "private":
            info["warnung"] = _vis_warning(vis, kinfo, st == "duplicate")
            log(f"  {name}: WARNUNG Komoot-Sichtbarkeit {vis} ({kinfo.get('fehler') or 'nicht bestätigt'})")
    if st == "duplicate":
        record(tid, portal, "duplicate", rid, "Das Portal kennt die Tour bereits" + (f" · {vis_text(vis)}" if portal == "komoot" and rid else ""), vis=vis if rid else None)
        log(f"  {name}: {PORTALS[portal]} kennt die Tour schon")
        return "duplicate", rid, "Das Portal kennt die Tour bereits"
    extra = ""
    if portal == "komoot":
        extra = vis_text(vis) + (f" · {info.get('wegpunkte')} Wegpunkte" if info.get("wegpunkte") else "") + (" · mit Notiz" if info.get("notiz") else "")
    record(tid, portal, "uploaded" if st == "created" else "pending", rid, extra, vis=vis)
    if portal == "komoot" and rid:
        chk = komoot_check(tid, visibility=False)          # Sichtbarkeit ist schon geprüft; hier nur „liegt sie dort?“ und als was
        if chk.get("checked") and not chk.get("exists"):
            raise PortalError("Komoot hat den Upload angenommen, die Tour ist dort aber nicht auffindbar. Bitte erneut versuchen.")
        if chk.get("exists"):
            typ = {"tour_recorded": "als aufgezeichnete Tour", "tour_planned": "als geplante Route (unter „Geplant“ in Komoot)"}.get(chk.get("type"), chk.get("type") or "")
            record(tid, portal, "uploaded", rid, f"bei Komoot geprüft: {typ} · {extra}", vis=vis)
            log(f"  {name}: bei Komoot geprüft ({chk.get('type')})")
    log(f"  {name}: zu {PORTALS[portal]} hochgeladen {rid}")
    return "uploaded", rid, ""


def _vis_warning(vis, kinfo, duplicate=False):
    if duplicate:
        if vis == "public":
            return "Komoot kannte die Tour schon – sie ist dort ÖFFENTLICH. Meine Touren ändert eine vorhandene Tour nicht von selbst: „Bei Komoot auf privat setzen“ oder in Komoot ändern."
        return "Komoot kannte die Tour schon. " + vis_text(vis) + "."
    if kinfo.get("vorher") == "public":
        return ("Deine Komoot-Vorgabe für neue Aktivitäten ist „öffentlich“, und das Zurücksetzen auf „privat“ hat nicht geklappt. "
                "Die Tour (mit Notiz und Pins, falls mitgesendet) kann gerade für alle sichtbar sein. Bitte sofort in Komoot auf „Nur ich“ stellen oder die Tour dort löschen.")
    return "Die Sichtbarkeit bei Komoot ist nicht bestätigt. Bitte in Komoot prüfen (Tour öffnen → Sichtbarkeit „Nur ich“)."


def info():
    ts = strava_tokens()
    return [
        {"id": "komoot", "name": "Komoot", "configured": bool(db.get("komoot_email") and db.get("komoot_password")), "connected": bool(db.get("komoot_email") and db.get("komoot_password")), "account": db.get("komoot_email") or "", "with_notes": with_notes_enabled()},
        {"id": "strava", "name": "Strava", "configured": strava_configured(), "connected": strava_connected(), "account": ts.get("athlete", "")},
    ]


# ---------- API ----------
def _redirect(request: Request):
    custom = (db.get("strava_redirect") or "").strip()
    if custom:
        return custom
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}/api/strava/callback"


@router.get("/api/portals")
def api_portals(request: Request):
    return {"portals": info(), "redirect": _redirect(request)}


@router.get("/api/strava/connect")
def api_strava_connect(request: Request):
    try:
        return {"url": strava_auth_url(_redirect(request)), "redirect": _redirect(request)}
    except PortalError as e:
        raise HTTPException(400, str(e))


@router.get("/api/strava/callback")
def api_strava_callback(code: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse("/#/admin?strava=abgelehnt")
    try:
        strava_exchange(code)
    except PortalError as e:
        return RedirectResponse("/#/admin?strava=" + urllib.parse.quote(str(e)[:120]))
    return RedirectResponse("/#/admin?strava=ok")


@router.post("/api/strava/code")
def api_strava_code(body: dict):
    try:
        t = strava_exchange(body.get("code", ""))
    except PortalError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "athlete": t.get("athlete", "")}


@router.post("/api/strava/disconnect")
def api_strava_disconnect():
    try:
        if strava_connected():
            requests.post(f"{SB}/oauth/deauthorize", headers={"Authorization": f"Bearer {strava_access()}"}, timeout=20)
    except Exception:  # noqa
        pass
    db.put("strava_tokens", "")
    return {"ok": True}


@router.get("/api/tours/{tour_id}/uploads")
def api_tour_uploads(tour_id: str):
    out = status_of(tour_id)
    for k, v in out.items():
        v["url"] = remote_url(k, v["remote_id"])
    return out


@router.post("/api/tours/{tour_id}/komoot-check")
def api_komoot_check(tour_id: str):
    return komoot_check(tour_id)


@router.post("/api/tours/{tour_id}/komoot-privat")
def api_komoot_privat(tour_id: str):
    """3.58.0: nur auf ausdrücklichen Klick – eine hochgeladene Tour bei Komoot auf „privat“ setzen (Betrachter: gesperrt wie jedes POST)."""
    try:
        return komoot_make_private(tour_id)
    except PortalError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa
        raise HTTPException(502, f"Komoot: {str(e)[:200]}")


@router.get("/api/komoot/hochgeladen")
def api_komoot_hochgeladen():
    """3.58.0: Touren, die bei Komoot liegen (laut Upload-Vermerk), mit der zuletzt gelesenen Sichtbarkeit – ohne Anfrage an Komoot."""
    items = komoot_uploaded()
    return {"touren": items, "zaehler": count_vis([x["vis"] for x in items])}


@router.post("/api/komoot/sichtbarkeit")
def api_komoot_sichtbarkeit(body: dict):
    """3.58.0: Sichtbarkeit bei Komoot nachlesen (nur lesend), höchstens CHECK_MAX Touren je Aufruf, mit Pause dazwischen.
    Die Oberfläche ruft das in kleinen Gruppen nacheinander auf und zeigt den Fortschritt."""
    ids = [str(x) for x in (body.get("ids") or []) if str(x).strip()][:CHECK_MAX]
    out = {}
    for i, tid in enumerate(ids):
        if i:
            time.sleep(CHECK_PAUSE_S)
        try:
            c = komoot_check(tid)
        except Exception as e:  # noqa
            c = {"checked": False, "msg": str(e)[:200]}
        if c.get("checked") and not c.get("exists"):
            out[tid] = {"vis": "fehlt", "msg": "bei Komoot nicht (mehr) gefunden"}
        elif c.get("checked"):
            out[tid] = {"vis": c["vis"], "vis_text": c.get("vis_text")}
        else:
            out[tid] = {"vis": "unbekannt", "msg": c.get("msg") or "nicht geprüft"}
    return {"ergebnis": out, "zaehler": count_vis([v["vis"] for v in out.values()])}


@router.post("/api/tours/{tour_id}/upload")
def api_tour_upload(tour_id: str, body: dict):
    res = {}
    wn = body.get("with_notes")
    for p in body.get("portals", []):
        info = {}
        try:
            st, rid, msg = upload_tour(tour_id, p, force=bool(body.get("force")), dry_run=bool(body.get("dry_run")),
                                       with_notes=None if wn is None else bool(wn), info=info)
            res[p] = {"status": st, "remote_id": rid, "msg": msg, "url": remote_url(p, rid)}
            if p == "komoot" and "vis" in info:
                res[p].update({k: info.get(k) for k in ("vis", "vis_text", "warnung", "wegpunkte", "notiz", "vorher") if info.get(k) is not None})
        except Exception as e:  # noqa
            res[p] = {"status": "error", "msg": str(e)}
    return res


@router.get("/api/tours/{tour_id}/gpx")
def api_tour_gpx(tour_id: str):
    t = db.one("SELECT name FROM tours WHERE id=?", (tour_id,))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    try:
        g = tracks.gpx_for(tour_id)
    except RuntimeError as e:
        raise HTTPException(404, str(e))
    fn = "".join(c if c.isalnum() or c in " -_." else "_" for c in (t["name"] or tour_id))[:80].strip() or tour_id
    return Response(g, media_type="application/gpx+xml", headers={"Content-Disposition": f'attachment; filename="{fn}.gpx"'})


@router.delete("/api/tours/{tour_id}")
def api_tour_delete(tour_id: str):
    try:
        tracks.delete_local(tour_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}
