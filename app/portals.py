"""Portale für den Upload von Touren: Komoot und Strava. Die Strecken liegen lokal; hier wird nur gesendet."""
import json
import time
import urllib.parse

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from . import config, db, tracks
from .jobs import log

router = APIRouter()

STRAVA_SPORT = {
    "hike": "Hike", "mountaineering": "Hike", "jogging": "Run", "touringbicycle": "Ride", "e_touringbicycle": "EBikeRide",
    "racebike": "Ride", "mtb": "MountainBikeRide", "skialpin": "AlpineSki", "skitour": "BackcountrySki",
    "snowshoe": "Snowshoe", "nordic": "NordicSki", "nordicwalking": "Walk",
}
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
        raise PortalError("Strava ist nicht verbunden (Verwaltung → Portale)")
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
                      data={"data_type": "gpx", "name": name, "sport_type": STRAVA_SPORT.get(sport, "Hike"), "external_id": ext_id},
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
def komoot_upload(gpx, sport, name):
    from . import sync
    return sync._komoot().upload(gpx, sport, name)


def komoot_check(tid):
    """Fragt bei Komoot nach, ob die hochgeladene Tour wirklich dort liegt. Fehlt sie, wird der Upload-Vermerk gelöscht."""
    from . import sync
    old = status_of(tid).get("komoot")
    if not old or not old["remote_id"] or old["status"] not in ("uploaded", "pending"):
        return {"checked": False}
    try:
        t = sync._komoot().tour(old["remote_id"])
    except Exception as e:  # noqa
        if "nicht gefunden" in str(e):
            db.execute("DELETE FROM tour_uploads WHERE tour_id=? AND portal='komoot'", (str(tid),))
            return {"checked": True, "exists": False}
        return {"checked": False, "msg": str(e)}
    return {"checked": True, "exists": True, "type": t.get("status"), "name": t.get("name")}


# ---------- gemeinsam ----------
def status_of(tid):
    return {r["portal"]: {"status": r["status"], "remote_id": r["remote_id"], "msg": r["msg"], "ts": r["ts"]}
            for r in db.query("SELECT * FROM tour_uploads WHERE tour_id=?", (str(tid),))}


def record(tid, portal, status, remote="", msg=""):
    db.execute("INSERT OR REPLACE INTO tour_uploads(tour_id,portal,remote_id,status,msg,ts) VALUES(?,?,?,?,?,?)",
               (str(tid), portal, remote or "", status, msg or "", int(time.time())))


def remote_url(portal, remote):
    if not remote:
        return ""
    return {"komoot": f"https://www.komoot.com/tour/{remote}", "strava": f"https://www.strava.com/activities/{remote}"}.get(portal, "")


def upload_tour(tid, portal, gpx=None, force=False, dry_run=False):
    """Eine Tour zu einem Portal senden. Gibt (status, remote_id, meldung) zurück:
    uploaded | duplicate | already | skipped | would_upload."""
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
        raise PortalError("Strava ist nicht verbunden (Verwaltung → Portale)")
    gpx = gpx or tracks.gpx_for(tid)
    name = t["name"] or tid
    try:
        if portal == "komoot":
            st, rid = komoot_upload(gpx, t["sport"] or "hike", name)
            st = "created" if st == "created" else "duplicate"
        else:
            st, rid = strava_upload(gpx, t["sport"] or "hike", name, f"meine-touren-{tid}")
    except Exception as e:  # noqa
        record(tid, portal, "error", "", str(e)[:300])
        raise
    if st == "duplicate":
        record(tid, portal, "duplicate", rid, "Das Portal kennt die Tour bereits")
        log(f"  {name}: {PORTALS[portal]} kennt die Tour schon")
        return "duplicate", rid, "Das Portal kennt die Tour bereits"
    record(tid, portal, "uploaded" if st == "created" else "pending", rid, "")
    if portal == "komoot":
        chk = komoot_check(tid)
        if chk.get("checked") and not chk.get("exists"):
            raise PortalError("Komoot hat den Upload angenommen, die Tour ist dort aber nicht auffindbar. Bitte erneut versuchen.")
        if chk.get("exists"):
            typ = {"tour_recorded": "als aufgezeichnete Tour", "tour_planned": "als geplante Route (unter „Geplant“ in Komoot)"}.get(chk.get("type"), chk.get("type") or "")
            record(tid, portal, "uploaded", rid, f"bei Komoot geprüft: {typ}")
            log(f"  {name}: bei Komoot geprüft ({chk.get('type')})")
    log(f"  {name}: zu {PORTALS[portal]} hochgeladen {rid}")
    return "uploaded", rid, ""


def info():
    ts = strava_tokens()
    return [
        {"id": "komoot", "name": "Komoot", "configured": bool(db.get("komoot_email") and db.get("komoot_password")), "connected": bool(db.get("komoot_email") and db.get("komoot_password")), "account": db.get("komoot_email") or ""},
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


@router.post("/api/tours/{tour_id}/upload")
def api_tour_upload(tour_id: str, body: dict):
    res = {}
    for p in body.get("portals", []):
        try:
            st, rid, msg = upload_tour(tour_id, p, force=bool(body.get("force")), dry_run=bool(body.get("dry_run")))
            res[p] = {"status": st, "remote_id": rid, "msg": msg, "url": remote_url(p, rid)}
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
